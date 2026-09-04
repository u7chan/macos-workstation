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
