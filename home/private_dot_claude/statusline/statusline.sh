#!/usr/bin/env bash
# statusLine エントリポイント。
# statusLine JSON にはカレントブランチ名が入らない (worktree 時の worktree.branch のみ) ため、
# git から補って --arg branch で statusline.jq に渡す。
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

input=$(cat)
dir=$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // empty')
branch=""
if [ -n "$dir" ]; then
  branch=$(git -C "$dir" branch --show-current 2>/dev/null) || branch=""
fi

printf '%s' "$input" | jq -jr --arg branch "$branch" -f "$HERE/statusline.jq"
