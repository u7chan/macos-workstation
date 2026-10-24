# AGENTS.md

個人の macOS 端末の構成管理。

- このリポジトリでは `main` への直 push は禁止（必ずブランチを作成して PR を出す）
- Homebrew は使用しない（パッケージ管理は MacPorts / mise を使用）
- このリポジトリは public。機密情報・個人情報はコミットしない（コミット・push 前に検知する）
- README などのユーザー向けドキュメントは英語で統一する（PR タイトルの英語規約と同様のポリシー）
- テストの説明文（docstring・コメント）は日本語で記述する
- 設定値・ツール一覧・バージョンは定義ファイルを唯一の情報源（SSOT）とし、README などには手書きで転記せず定義ファイルへの参照を記載する
- 自前の制御ロジックは、回帰検知の効果と保守コストを考慮して自動テストする。特に、失敗時の停止や既存データを保護する挙動を重視する。
- テストは一時ディレクトリ・一時 HOME・一時リポジトリで隔離し、実際のユーザー環境を変更しない。
- Git・chezmoi との連携自体を検証する場合は実物を使い、外部サービスや再現困難な失敗条件は必要に応じて模擬する。
- CI ではテスト依存を明示的に用意し、依存不足によるスキップを成功扱いで見逃さない。
- OS・実機依存の設定反映は実機確認を最終判断とする。モックや Linux CI の成功で代替しない。
- 詳細ルールは責務ごとに以下のファイルへ分離している

## Tech Stack

- [x] mise — runtime/tool version management incl. GitHub CLI via Aqua (home/dot_config/mise/config.toml, bootstrap.sh)
- [x] MacPorts — OS-level packages incl. git, chezmoi (macports/ports.txt, bootstrap.sh)
- [x] chezmoi — dotfiles management (home/, bootstrap.sh)
- [x] macOS defaults — (macos/defaults.sh, bootstrap.sh)

## References

- [.agents/rules/git.md](.agents/rules/git.md) — ブランチ名・コミットメッセージ・マージ方式
- [.agents/rules/pull-request.md](.agents/rules/pull-request.md) — PR タイトル・本文・Issue キーワード・フィードバック対応
