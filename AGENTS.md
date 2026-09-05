# AGENTS.md

個人の macOS 端末の構成管理。

- このリポジトリでは `main` への直 push は禁止（必ずブランチを作成して PR を出す）
- Homebrew は使用しない（パッケージ管理は MacPorts / mise を使用）
- このリポジトリは public。機密情報・個人情報はコミットしない（コミット・push 前に検知する）
- 詳細ルールは責務ごとに以下のファイルへ分離している

## Tech Stack

- [x] mise — runtime/tool version management (mise.toml, bootstrap.sh)
- [x] MacPorts — OS-level packages incl. git, chezmoi (macports/ports.txt, bootstrap.sh)
- [x] chezmoi — dotfiles management (home/, bootstrap.sh)
- [ ] macOS defaults — (TODO)

## References

- [.agents/rules/git.md](.agents/rules/git.md) — ブランチ名・コミットメッセージ・マージ方式
- [.agents/rules/pull-request.md](.agents/rules/pull-request.md) — PR タイトル・本文・Issue キーワード・フィードバック対応
