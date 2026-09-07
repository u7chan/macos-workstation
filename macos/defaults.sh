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
#    反映に再ログインが必要な場合がある
echo "==> trackpad: tracking speed (max)"
defaults write -g com.apple.trackpad.scaling -float 3.0
check -g com.apple.trackpad.scaling "3" "trackpad tracking speed"

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
