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

The [`home/`](home/) directory is the source of truth for dotfiles. chezmoi maps these definitions to their destinations:

| Definition | Destination | Purpose |
| --- | --- | --- |
| [`home/dot_gitconfig`](home/dot_gitconfig) | `~/.gitconfig` | Git commit identity and explicit-identity enforcement |
| [`home/dot_zprofile`](home/dot_zprofile) | `~/.zprofile` | MacPorts PATH |
| [`home/dot_zshrc`](home/dot_zshrc) | `~/.zshrc` | mise activation |
| [`home/dot_config/mise/config.toml`](home/dot_config/mise/config.toml) | `~/.config/mise/config.toml` | Tool declarations and version constraints |
| [Ghostty configuration](home/Library/Application%20Support/com.mitchellh.ghostty/config) | `~/Library/Application Support/com.mitchellh.ghostty/config` | Ghostty font settings |

- bootstrap converges the machine with `chezmoi apply --source=./home --force`
- Manual edits on the machine are treated as temporary experiments. To keep a change, edit a file under `home/` and submit a PR

### Git

Git commit identity and explicit-identity enforcement are defined in the [Git configuration](home/dot_gitconfig). The managed identity uses a public GitHub username and GitHub-provided noreply address, not a private email address or credential. Bootstrap applies this file through chezmoi; repository-local Git settings can override the managed defaults when needed.

### Ghostty

Font settings are defined in the [Ghostty configuration](home/Library/Application%20Support/com.mitchellh.ghostty/config). Edit that file to change them; `./bootstrap.sh` applies it to Ghostty's macOS-native configuration path as part of the dotfiles step.

Restart Ghostty after applying font changes. Ghostty itself must be installed separately.

## macOS defaults

GUI-only macOS settings scripted to avoid manual reconfiguration on a new Mac.

- Applied by bootstrap, or run standalone:

  ```sh
  ./macos/defaults.sh
  ```

- Idempotent: every run re-applies all settings and verifies each one by reading the value back (auto-verification, OK/NG)
- The configured settings and their values are defined in [`macos/defaults.sh`](macos/defaults.sh). Edit that script rather than maintaining a separate settings list here.

> Note: some settings may require logging out and back in to take effect.

## Update

```sh
git pull
./bootstrap.sh
```

Tool declarations and version constraints are defined in the [mise configuration](home/dot_config/mise/config.toml). `mise install` installs missing versions but does not upgrade installed versions that still satisfy those constraints.

To upgrade the globally configured tools within their declared constraints, without changing the declarations:

```sh
mise -C "$HOME" up
```

OS-level package declarations are maintained separately in [`macports/ports.txt`](macports/ports.txt).

## Cleanup

### Remove tool declarations and unused installations

To stop managing tools, remove their declarations from the [mise configuration](home/dot_config/mise/config.toml), then apply the dotfiles from the repository root and preview which installed versions are now unused:

```sh
chezmoi apply --source=./home --force
mise prune --dry-run
```

Review the preview before running `mise prune`. Versions still referenced by other tracked configurations are retained. This uses the configuration itself as the tool list, so no separate list of tool names or versions is needed.

### Uninstall all tools while keeping configuration

To remove **every installed mise tool and runtime**, including those not managed by this repository, preview the operation first:

```sh
mise uninstall --all --dry-run
```

After reviewing the preview:

```sh
mise uninstall --all
```

This covers all installed tools, regardless of backend, and keeps both the applied configuration and the repository definitions. Running `./bootstrap.sh` reinstalls the configured tools.
