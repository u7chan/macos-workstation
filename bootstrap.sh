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
  MP_RELEASE="$(curl -fsSL https://api.github.com/repos/macports/macports-base/releases/latest | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p')"
  MP_VERSION="${MP_RELEASE#v}"
  MACOS_MAJOR="$(sw_vers -productVersion | cut -d. -f1)"
  MP_PKG="$(curl -fsSL "https://api.github.com/repos/macports/macports-base/releases/latest" | grep -o "MacPorts-${MP_VERSION}-${MACOS_MAJOR}-[A-Za-z]*\.pkg" | head -1)"
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

# 2) ポート導入（macports/ports.txt に従う。導入済みポートはスキップされる）
if [ -s macports/ports.txt ]; then
  echo "==> sudo port -N install ($(tr '\n' ' ' < macports/ports.txt))"
  sudo port -N install $(cat macports/ports.txt)
  if [ -x /opt/local/bin/git ]; then
    echo "==> MacPorts git: $(/opt/local/bin/git --version)"
  fi
fi

# 3) mise 導入
if ! command -v mise >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/mise" ]; then
  echo "==> installing mise"
  curl https://mise.run | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# 4) zsh 連携 (TODO: 暫定対応。chezmoi 導入後に dotfiles 側へ移行する)
if ! grep -qs 'mise activate zsh' "$HOME/.zshrc"; then
  echo "==> append mise activation to ~/.zshrc"
  {
    echo ""
    echo "# TODO: mise activate (bootstrap.sh 追加分。chezmoi 導入後に移行)"
    echo 'eval "$(~/.local/bin/mise activate zsh)"'
  } >>"$HOME/.zshrc"
fi

# 5) グローバル設定: リポジトリの mise.toml を ~/.config/mise/config.toml に配布
#    どのディレクトリでも node / python などを使用できるようにする
#    (TODO: 配布元は chezmoi 導入後に dotfiles 側へ移行する)
if ! cmp -s mise.toml "$HOME/.config/mise/config.toml"; then
  echo "==> install mise global config (~/.config/mise/config.toml)"
  mkdir -p "$HOME/.config/mise"
  cp mise.toml "$HOME/.config/mise/config.toml"
fi

# 6) ランタイム導入 (グローバル + リポジトリ設定に従う)
echo "==> mise install"
mise install

echo "==> installed versions"
mise exec -- node -v
mise exec -- python3 -V

echo "==> next: restart the terminal, then verify MacPorts git takes over:"
echo "    command -v git   # expect /opt/local/bin/git"
echo "    git --version"
