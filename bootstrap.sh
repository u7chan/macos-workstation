#!/usr/bin/env bash
set -euo pipefail

# 0) Xcode Command Line Tools 導入（未導入の場合のみ・最大5分待機）
if ! xcode-select -p >/dev/null 2>&1; then
  echo "==> installing Xcode Command Line Tools (follow the GUI dialog)"
  xcode-select --install
  for _ in $(seq 1 60); do
    if xcode-select -p >/dev/null 2>&1; then
      break
    fi
    sleep 5
  done
  if ! xcode-select -p >/dev/null 2>&1; then
    echo "ERROR: Xcode Command Line Tools installation did not complete. Run 'xcode-select --install' manually and re-run this script." >&2
    exit 1
  fi
fi

# 1) MacPorts 導入（OS寄りパッケージ管理。未導入の場合のみ）
if [ ! -x /opt/local/bin/port ]; then
  echo "==> installing MacPorts (sudo required)"
  sudo -v
  MP_API="$(curl -fsSL https://api.github.com/repos/macports/macports-base/releases/latest)"
  MP_RELEASE="$(printf '%s' "$MP_API" | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p')"
  MP_VERSION="${MP_RELEASE#v}"
  MACOS_MAJOR="$(sw_vers -productVersion | cut -d. -f1)"
  MP_PKG="$(printf '%s' "$MP_API" | grep -o "MacPorts-${MP_VERSION}-${MACOS_MAJOR}-[A-Za-z]*\.pkg" | head -1)"
  if [ -z "$MP_PKG" ]; then
    echo "ERROR: no MacPorts package found for macOS ${MACOS_MAJOR}" >&2
    exit 1
  fi
  echo "==> downloading ${MP_PKG}"
  curl -fL -o "/tmp/${MP_PKG}" "https://github.com/macports/macports-base/releases/download/${MP_RELEASE}/${MP_PKG}"
  sudo installer -pkg "/tmp/${MP_PKG}" -target /
  rm -f "/tmp/${MP_PKG}"
fi
export PATH="/opt/local/bin:$PATH"

# 2) ポート導入（macports/ports.txt に従う。空行・# コメント行は無視し、導入済みポートはスキップされる）
PORTS=""
while IFS= read -r line; do
  case "$line" in ''|\#*) continue ;; esac
  PORTS="$PORTS $line"
done < macports/ports.txt
if [ -n "$PORTS" ]; then
  echo "==> sudo port -N install ($PORTS)"
  sudo port -N install $PORTS
  if [ -x /opt/local/bin/git ]; then
    echo "==> MacPorts git: $(/opt/local/bin/git --version)"
  fi
fi

# 3) dotfiles 適用（chezmoi。source はリポジトリの home/ ディレクトリ）
#     ~/.zprofile（MacPorts PATH）/ ~/.zshrc（mise activate）/ ~/.config/mise/config.toml
#     （グローバル設定）を正本（GitHub）へ収束させる。
#     --force: マシン上の手編集は一時的な実験扱いとし、正本で上書きする（収束方式）
echo "==> chezmoi apply (source: $(pwd)/home)"
chezmoi apply --source="$(pwd)/home" --force

# 4) mise 導入
if ! command -v mise >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/mise" ]; then
  echo "==> installing mise"
  curl https://mise.run | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# 5) ランタイム導入（~/.config/mise/config.toml のグローバル設定に従う。ステップ3 で適用済み）
echo "==> mise install"
mise install

echo "==> installed versions"
mise exec -- node -v
mise exec -- python3 -V

echo "==> next: restart the terminal, then verify MacPorts git takes over:"
echo "    command -v git   # expect /opt/local/bin/git"
echo "    git --version"