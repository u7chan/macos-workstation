# macos-workstation

[![macOS](https://img.shields.io/badge/macOS-gray?logo=apple&logoColor=white)](https://www.apple.com/macos/)
[![MacPorts](https://img.shields.io/badge/MacPorts-1E79E9?logo=macports&logoColor=white)](https://www.macports.org/)
[![mise](https://img.shields.io/badge/mise-53BFFD)](https://mise.jdx.dev/)
[![chezmoi](https://img.shields.io/badge/chezmoi-5B5B5B)](https://www.chezmoi.io/)
[![Bash](https://img.shields.io/badge/Bash-4EAA25?logo=gnubash&logoColor=white)](https://www.gnu.org/software/bash/)

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

- `~/.zprofile` (MacPorts PATH) / `~/.zshrc` (mise activation) / `~/.config/mise/config.toml` (mise global config) are managed by chezmoi
- The source of truth is the `home/` directory in this repository. bootstrap converges the machine with `chezmoi apply --source=./home --force`
- Manual edits on the machine are treated as temporary experiments. To keep a change, edit a file under `home/` and submit a PR

## Update

```sh
git pull
./bootstrap.sh
```

## Cleanup

Remove globally configured tools and their runtimes:

```sh
# remove from global config (~/.config/mise/config.toml) and uninstall runtimes
mise unuse -g node@26 python@3.13 uv@latest

# remove all installed runtimes (keeps config)
mise uninstall --all
```