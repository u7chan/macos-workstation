# macos-workstation

Personal reproducible Mac development environment configuration (MacPorts + mise + chezmoi + macOS defaults).

## Setup

### Fresh macOS (git not installed)

Stage 0: fetch the repository with macOS built-ins only (curl + tar), then run bootstrap.

```sh
curl -L https://github.com/u7chan/macos-workstation/archive/refs/heads/main.tar.gz | tar xz
cd macos-workstation-main
./bootstrap.sh
```

Once bootstrap finishes, git is available. Discard the disposable archive copy and clone the repository properly:

```sh
cd ..
rm -rf macos-workstation-main
git clone https://github.com/u7chan/macos-workstation.git
cd macos-workstation
```

### git already available

```sh
git clone https://github.com/u7chan/macos-workstation.git
cd macos-workstation

# bootstrap: installs Xcode CLT (if missing) + MacPorts + dotfiles (chezmoi) + mise + runtimes
./bootstrap.sh
```

## Dotfiles

- `~/.zprofile`（MacPorts PATH）/ `~/.zshrc`（mise activate）/ `~/.config/mise/config.toml`（mise グローバル設定）を chezmoi で管理する
- 正本はリポジトリの `home/` ディレクトリ。bootstrap が `chezmoi apply --source=./home --force` でマシンへ収束させる
- マシン上の手編集は一時的な実験扱い。残したい変更は `home/` を編集して PR で取り込む

## Update

```sh
git pull
./bootstrap.sh
# or: ./bootstrap.sh のうち dotfiles 適用だけなら:
# chezmoi apply --source="$PWD/home" --force
```

## Cleanup

Remove globally configured tools and their runtimes:

```sh
# remove from global config (~/.config/mise/config.toml) and uninstall runtimes
mise unuse -g node@26 python@3.13 uv@latest

# remove all installed runtimes (keeps config)
mise uninstall --all
```
