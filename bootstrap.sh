#!/usr/bin/env bash
set -euo pipefail

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

# 3) ランタイム導入 (mise.toml に従う)
echo "==> mise install"
mise install

echo "==> installed versions"
mise exec -- node -v
mise exec -- python3 -V
