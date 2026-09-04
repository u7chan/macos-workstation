# macos-workstation

Personal reproducible Mac development environment configuration (MacPorts + mise + chezmoi + macOS defaults).

## Setup

Prerequisites:

- macOS (Intel / Ventura)
- Xcode Command Line Tools: `xcode-select --install`

```sh
# clone
git clone https://github.com/u7chan/macos-workstation.git
cd macos-workstation

# bootstrap: installs mise + runtimes defined in mise.toml
./bootstrap.sh
```

What `bootstrap.sh` does:

1. Install mise (if not already installed)
2. Append mise activation to `~/.zshrc`
3. Install runtimes from `mise.toml` (node, python, uv)

> Open a new shell after running so `mise activate` takes effect and `node` / `python3` become available.

## Status

- [x] mise — runtime/tool version management (mise.toml, bootstrap.sh)
- [ ] MacPorts — OS-level packages (not defined yet)
- [ ] chezmoi — dotfiles management (not yet)
- [ ] macOS defaults — (not yet)
