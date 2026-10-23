# AGENTS.md

個人の macOS 端末の構成管理。

- このリポジトリでは `main` への直 push は禁止（必ずブランチを作成して PR を出す）
- Homebrew は使用しない（パッケージ管理は MacPorts / mise を使用）
- このリポジトリは public。機密情報・個人情報はコミットしない（コミット・push 前に検知する）
- README などのユーザー向けドキュメントは英語で統一する（PR タイトルの英語規約と同様のポリシー）
- テストの説明文（docstring・コメント）は日本語で記述する
- 設定値・ツール一覧・バージョンは定義ファイルを唯一の情報源（SSOT）とし、README などには手書きで転記せず定義ファイルへの参照を記載する
- 自前の制御ロジックは必要に応じて自動テストし、OS・実機依存の設定反映は実機確認を最終判断とする（モック成功で代替せず、常設テストは効果と保守コストを考慮して追加する）。
- 詳細ルールは責務ごとに以下のファイルへ分離している

## Tech Stack

- [x] mise — runtime/tool version management incl. GitHub CLI via Aqua (home/dot_config/mise/config.toml, bootstrap.sh)
- [x] MacPorts — OS-level packages incl. git, chezmoi (macports/ports.txt, bootstrap.sh)
- [x] chezmoi — dotfiles management (home/, bootstrap.sh)
- [x] macOS defaults — (macos/defaults.sh, bootstrap.sh)

## References

- [.agents/rules/git.md](.agents/rules/git.md) — ブランチ名・コミットメッセージ・マージ方式
- [.agents/rules/pull-request.md](.agents/rules/pull-request.md) — PR タイトル・本文・Issue キーワード・フィードバック対応
