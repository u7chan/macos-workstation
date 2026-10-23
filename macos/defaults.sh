#!/usr/bin/env bash
set -euo pipefail

# macOS defaults — GUI で手動設定している macOS 設定をスクリプト化する（冪等）
#
# 適用方法:
#   ./macos/defaults.sh    # 単体実行
#   ./bootstrap.sh         # bootstrap の最終ステップからも適用される
#
# 検証:
#   各設定は書き込み後に読み戻し、期待値と一致するかを自動判定する（OK / NG）
#   NG が 1 件でもあれば exit 1 で終了する

FAILED=0

# 検証: キーを読み戻して期待値と比較する
check() {
  local domain="$1" key="$2" expected="$3" label="$4"
  local actual
  actual="$(defaults read "$domain" "$key" 2>/dev/null)" || actual="<unset>"
  if [ "$actual" = "$expected" ]; then
    echo "OK: $label"
  else
    echo "NG: $label (expected=$expected, actual=$actual)" >&2
    FAILED=1
  fi
}

# 1) トラックパッド: トラッキングの速さ（MAX）
#    反映に再起動が必要な場合があるため、変更時のみ末尾で案内する
TRACKPAD_SCALING=3
TRACKPAD_SCALING_BEFORE="$(defaults read -g com.apple.trackpad.scaling 2>/dev/null)" || TRACKPAD_SCALING_BEFORE="<unset>"
echo "==> trackpad: tracking speed (max)"
defaults write -g com.apple.trackpad.scaling -float "$TRACKPAD_SCALING"
check -g com.apple.trackpad.scaling "$TRACKPAD_SCALING" "trackpad tracking speed"

# 2) Finder: すべてのファイル名拡張子を表示
echo "==> finder: show all filename extensions"
defaults write -g AppleShowAllExtensions -bool true
check -g AppleShowAllExtensions "1" "show all filename extensions"
killall Finder 2>/dev/null || true

if [ "$FAILED" -ne 0 ]; then
  echo "ERROR: some defaults did not apply correctly" >&2
  exit 1
fi
echo "==> all defaults applied and verified"

# 数値として比較し、同じ値の表記差（3 と 3.0 など）では案内しない
if ! awk -v before="$TRACKPAD_SCALING_BEFORE" -v after="$TRACKPAD_SCALING" \
  'BEGIN { exit (before == after ? 0 : 1) }'; then
  echo "==> Trackpad tracking speed changed. A restart may be required for the change to take effect."
fi
