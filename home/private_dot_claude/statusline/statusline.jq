# Status line: model / effort / ctx / prompt cache / rate limits
# Input: Claude Code status line JSON on stdin. Run with: jq -jrf statusline.jq
# アイコンに Nerd Font の私用領域の文字を使うため、表示側のフォントが必要。
def R: "\u001b[0m";
def MODEL_COLOR: "\u001b[0;35m";
def DIVIDER: "\u001b[38;2;150;150;150m";
def COLD_COLOR: "\u001b[1;38;2;255;70;70m";
def WARN_COLOR: "\u001b[1;38;2;255;90;60m";
def REBUILD_COLOR: "\u001b[38;2;220;200;60m";
# 残りがこれを切ったら警告色。TTL の 20% か 10 分の小さい方
def warn_at($ttl_sec): [600, $ttl_sec * 0.2] | min;
def BLOCKS: " ▏▎▍▌▋▊▉█";
def FULL_BLOCK: "█";
def EMPTY_BLOCK: "░";
def WIDTH: 5;

def effort_color($e):
  {low: "\u001b[38;2;100;200;100m",
   medium: "\u001b[38;2;220;200;60m",
   high: "\u001b[38;2;255;150;50m",
   xhigh: "\u001b[38;2;255;90;60m",
   max: "\u001b[38;2;255;60;120m"}[$e] // MODEL_COLOR;

def gradient($pct):
  if $pct < 50 then "\u001b[38;2;\(($pct * 5.1) | floor);200;80m"
  else "\u001b[38;2;255;\([(200 - ($pct - 50) * 4) | floor, 0] | max);60m" end;

def bar($pct):
  ([[$pct, 0] | max, 100] | min) as $p
  | ($p * WIDTH / 100) as $filled
  | ($filled | floor) as $full
  | ((($filled - $full) * 8) | floor) as $frac
  | (FULL_BLOCK * $full)
    + (if $full < WIDTH
       then BLOCKS[$frac:$frac + 1] + (EMPTY_BLOCK * (WIDTH - $full - 1))
       else null end);

def fmt($label; $pct):
  "\($label) \(gradient($pct))\(bar($pct)) \($pct | round)%\(R)";

# 3661 -> "1h1m" / 1234 -> "20m34s" / 42 -> "42s"
def dur($sec):
  ($sec | floor) as $s
  | (($s / 3600) | floor) as $h
  | ((($s % 3600) / 60) | floor) as $m
  | ($s % 60) as $ss
  | if $h > 0 then "\($h)h\($m)m"
    elif $m > 0 then "\($m)m\(if $ss < 10 then "0" else "" end)\($ss)s"
    else "\($ss)s" end;

# 89000 -> "89k" / 1230000 -> "1.2M"
def tokens($n):
  if $n >= 1000000 then "\(($n / 100000 | round) / 10)M"
  elif $n >= 1000 then "\($n / 1000 | round)k"
  else "\($n)" end;

def time_left($resets_at):
  if $resets_at == null then ""
  else (($resets_at - now) | floor) as $d
  | if $d <= 0 then ""
    else (($d / 60) | floor) as $mins
    | (($mins / 60) | floor) as $h
    | ($mins % 60) as $m
    | if $h > 0 then "\($h)h\($m)m" else "\($m)m" end
    end
  end;

def reset_weekday($resets_at):
  if $resets_at == null then "" else ($resets_at | localtime | strftime("%a")) end;

def rate_limit_part($label; $data; $weekday):
  ($data.used_percentage) as $pct
  | if $pct == null then empty
    else fmt($label; $pct) as $part
    | (if $weekday then reset_weekday($data.resets_at) else time_left($data.resets_at) end) as $suffix
    | if $suffix == "" then $part else "\($part) \(MODEL_COLOR)(\($suffix))\(R)" end
    end;

# prompt cache: warm なら残り時間、切れていたら経過時間
def cache_part:
  .prompt_cache
  | if . == null or .expires_at == null then empty
    else (.ttl // "5m") as $ttl
    | (.expires_at - now) as $left
    # recache_tokens_if_cold == null は「prefix の破棄が予約済み」= compact 直後。
    # 残り時間はもう当てにならないのでカウントを止める。
    | if (has("recache_tokens_if_cold") and .recache_tokens_if_cold == null)
      then "\(REBUILD_COLOR)\udb86\udda0 compacted\(R)"
      elif .warm == true and $left > 0
      then ({"5m": 300, "1h": 3600}[$ttl] // 300) as $ttl_sec
        | ([[$left / $ttl_sec, 0] | max, 1] | min) as $pct_left
        | (if $left < warn_at($ttl_sec) then WARN_COLOR
           else gradient((1 - $pct_left) * 100) end) as $color
        | "\($color)\udb81\udd1f \(dur($left))\(R)"
      # 切れた後は経過時間を数えない。意味があるのは復帰コストだけ
      else (.recache_tokens_if_cold // 0) as $recache
        | "\(COLD_COLOR)\udb86\udd9f \(if $recache > 0 then tokens($recache) else "expired" end)\(R)"
      end
    end;

# --- Issue / PR ---------------------------------------------------------
def ISSUE_COLOR: "\u001b[38;2;90;170;255m";
def PR_COLOR: "\u001b[38;2;130;200;110m";

# OSC 8 ハイパーリンク。終端 ST は ESC + backslash なので \u005c で実バイトとして埋める
def osc8($url; $text):
  "\u001b]8;;\($url)\u001b\u005c\($text)\u001b]8;;\u001b\u005c";

# origin remote 由来の repo から https://host/owner/name を組む。無ければ null
def repo_base:
  .workspace.repo
  | if . == null then null
    elif (.host // "") == "" or (.owner // "") == "" or (.name // "") == "" then null
    else "https://\(.host)/\(.owner)/\(.name)"
    end;

def issues_path($base):
  if ($base | test("://gitlab")) then "\($base)/-/issues" else "\($base)/issues" end;

# ブランチ名から issue 番号を拾う。誤検出を避けるため明示的な形だけを対象にする:
#   #863 / issue-820 / issues/820 / fix/863-foo
# issue(s) の直前はブランチ先頭か区切り文字に限定する (reissue-401 / tissue-42 を除外)
# prefix 直後の数字は先頭ゼロを除外する (feature/02-parts-... を issue と誤認しないため)
def issue_number($b):
  ([$b | scan("#([0-9]+)")] | .[0][0]?)
  // ([$b | scan("(?i)(?:^|[^a-z0-9])issues?[-_/]([0-9]+)")] | .[0][0]?)
  // ([$b | scan("^[^/]+/([1-9][0-9]*)[-_]")] | .[0][0]?);

def issue_part:
  issue_number($branch) as $n
  | if $n == null then empty
    else repo_base as $base
    | "#\($n)" as $t
    | ISSUE_COLOR
      + (if $base == null then $t else osc8(issues_path($base) + "/" + $n; $t) end)
      + R
    end;

# PR は statusLine JSON がカレントブランチの open PR を直接くれる (GitLab なら MR)
def pr_part:
  .pr.number as $n
  | if $n == null then empty
    else "PR#\($n)" as $t
    | PR_COLOR
      + (if .pr.url == null then $t else osc8(.pr.url; $t) end)
      + R
    end;

def model_part:
  # "Opus 5 (1M context)" -> "Opus 5 (1M)"
  ((.model.display_name // "Claude") | sub(" context\\)"; ")")) as $model
  | (.effort.level) as $effort
  | "\(MODEL_COLOR)\($model)\(R)"
    + (if $effort then " \(effort_color($effort))\($effort)\(R)" else "" end);

[ issue_part,
  pr_part,
  model_part,
  # ctx label = nf-md-memory (U+F035B)
  (if .context_window.used_percentage != null
   then fmt("\udb80\udf5b"; .context_window.used_percentage) else empty end),
  cache_part,
  rate_limit_part("5h"; .rate_limits.five_hour // {}; false),
  rate_limit_part("7d"; .rate_limits.seven_day // {}; true)
] | join(" \(DIVIDER)│\(R) ")
