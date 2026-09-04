# Git 規約

## ブランチ

- `main` への直 push は禁止。必ずブランチを作成して PR を出す
  - （ruleset で強制済み: PR 必須・force push 禁止・削除禁止・squash merge のみ）
- ブランチ名は小文字の kebab-case（例: `update/mise-config`）

## コミットメッセージ

- prefix 付きで英語で記述する（例: `feat(mise): add uv to tools`）

## マージ

- PR のマージはスカッシュマージで行う（コミット履歴はまとめられ、マージコミットを作らない）

## ファイル

- テキストファイルは末尾改行（LF）で終わらせる（`\ No newline at end of file` の diff ノイズ防止）

## セキュリティ

- このリポジトリは public のため、コミット・push 前に機密情報（トークン・鍵・資格情報）と個人情報（メールアドレス等）が含まれないことを確認する（公開履歴は永続する）
- スキャン例: `rg -n -i "(gh[pous]_|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY)" . --glob '!.git/**'`
- 誤って公開した場合は履歴削除より**トークン・鍵の失効（revoke）を最優先**する

