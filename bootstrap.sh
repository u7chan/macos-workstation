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

# 1) mise 導入
if ! command -v mise >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/mise" ]; then
  echo "==> installing mise"
  curl https://mise.run | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# 2) zsh 連携 (TODO: 暫定対応。chezmoi 導入後に dotfiles 側へ移行する)
if ! grep -qs 'mise activate zsh' "$HOME/.zshrc"; then
  echo "==> append mise activation to ~/.zshrc"
  {
    echo ""
    echo "# TODO: mise activate (bootstrap.sh 追加分。chezmoi 導入後に移行)"
    echo 'eval "$(~/.local/bin/mise activate zsh)"'
  } >>"$HOME/.zshrc"
fi

# 3) グローバル設定: リポジトリの mise.toml を ~/.config/mise/config.toml に配布
#    どのディレクトリでも node / python などを使用できるようにする
#    (TODO: 配布元は chezmoi 導入後に dotfiles 側へ移行する)
if ! cmp -s mise.toml "$HOME/.config/mise/config.toml"; then
  echo "==> install mise global config (~/.config/mise/config.toml)"
  mkdir -p "$HOME/.config/mise"
  cp mise.toml "$HOME/.config/mise/config.toml"
fi

# 4) ランタイム導入 (グローバル + リポジトリ設定に従う)
echo "==> mise install"
mise install

echo "==> installed versions"
mise exec -- node -v
mise exec -- python3 -V
