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

# bootstrap: installs Xcode CLT (if missing) + MacPorts + dotfiles (chezmoi) + mise + runtimes + agent skills
./bootstrap.sh
```

## Dotfiles

The [`home/`](home/) directory is the source of truth for dotfiles. chezmoi maps these definitions to their destinations:

| Definition | Destination | Purpose |
| --- | --- | --- |
| [`home/dot_gitconfig`](home/dot_gitconfig) | `~/.gitconfig` | Git commit identity, aliases, and explicit-identity enforcement |
| [`home/dot_zprofile`](home/dot_zprofile) | `~/.zprofile` | MacPorts PATH |
| [`home/dot_zshrc`](home/dot_zshrc) | `~/.zshrc` | mise activation and shell aliases |
| [`home/dot_config/mise/config.toml`](home/dot_config/mise/config.toml) | `~/.config/mise/config.toml` | Tool declarations and version constraints |
| [Harness launcher](home/dot_local/bin/executable_agent-harness-exec) | `~/.local/bin/agent-harness-exec` | Process-local environment for upstream GitHub/review harnesses |
| [Harness invocation rule](home/private_dot_pi/private_agent/modify_private_AGENTS.md) | `~/.pi/agent/AGENTS.md` | Updates only a marked instruction block, preserving other instructions |
| [Ghostty configuration](home/Library/Application%20Support/com.mitchellh.ghostty/config) | `~/Library/Application Support/com.mitchellh.ghostty/config` | Ghostty font settings |

- bootstrap converges the machine with `chezmoi apply --source=./home --force`
- Manual edits on the machine are treated as temporary experiments. To keep a change, edit a file under `home/` and submit a PR

### Git

Git commit identity, aliases, and explicit-identity enforcement are defined in the [Git configuration](home/dot_gitconfig). The managed identity uses a public GitHub username and GitHub-provided noreply address, not a private email address or credential. Bootstrap applies this file through chezmoi; repository-local Git settings can override the managed defaults when needed.

### Ghostty

Font settings are defined in the [Ghostty configuration](home/Library/Application%20Support/com.mitchellh.ghostty/config). Edit that file to change them; `./bootstrap.sh` applies it to Ghostty's macOS-native configuration path as part of the dotfiles step.

Restart Ghostty after applying font changes. Ghostty itself must be installed separately.

## Agent skills

Bootstrap installs or updates the skill package using the source and branch defined in [`agents/sync-skills.sh`](agents/sync-skills.sh). Each run resolves the upstream branch head to a commit and installs that revision through pi; upstream skill changes do not require a change to this repository. The revision is printed and saved in pi's user package settings. Development checkouts are not used or modified, and other pi settings are preserved.

Run bootstrap between tasks, then `/reload` or restart every running pi session before using the updated skills.

Package installation alone does not provision skill-specific dependencies or guarantee macOS compatibility. Bootstrap provisions the limited GitHub/review dependencies declared in [`macports/ports.txt`](macports/ports.txt); other skill dependencies remain out of scope.

### GitHub and review harnesses

Use the [managed launcher](home/dot_local/bin/executable_agent-harness-exec) for the supported upstream entrypoints listed in its dispatch guard. Resolve each absolute entrypoint path from the installed `SKILL.md` you actually read, not from a development checkout. For example, with `GH_SKILL_DIR` set to that installed skill directory:

```sh
"$HOME/.local/bin/agent-harness-exec" "$GH_SKILL_DIR/scripts/gh.sh" pr.read request.json
```

The launcher adds the MacPorts GNU compatibility directory to PATH **only on macOS, only for the harness and its descendants**. It checks dependencies and fails without installing anything or falling back to incompatible commands. On other operating systems it leaves PATH unchanged. It delegates to the upstream harness without changing API authorization rules, arguments, stdin, working directory, or exit status.

Do not source the launcher, add its GNU directory to shell startup files, wrap a whole pi session, or run review-target tests through it. Run tests and ordinary commands separately in their normal environment. The entrypoint guard prevents accidental broad use; it is not a security boundary.

The [managed invocation rule](home/private_dot_pi/private_agent/modify_private_AGENTS.md) routes skill calls through this launcher. chezmoi creates or updates only its marked block in the default pi user instructions, leaving unrelated content and settings intact. The pi directories and instruction file are managed as private to avoid widening access to existing user data. Incomplete or duplicate markers stop application rather than discarding user content. If you use a custom pi agent directory or an overriding context file such as `AGENTS.override.md`, include the managed rule in your active instructions yourself. Run `/reload` or restart pi after applying instruction changes.

#### Verification

Run the focused control-flow and chezmoi integration tests:

```sh
python3 -m unittest discover -s tests -v
```

For real-machine checks, record the installed upstream revision, then:

1. Confirm that ordinary `command -v grep`, `command -v sed`, and `command -v stat` results are unchanged after bootstrap and after launcher execution. Review-target tests must retain this ordinary environment.
2. Through the launcher, retrieve an actual PR with the upstream dispatcher's read-only actions, validate a representative review payload, and exercise the recheck helper. Follow the loaded skills for each input format.
3. Record successes and failures with the tested revision. Do not post test reviews or comments. Check posting and retrieval only during a separately authorized real review.

Automated tests exercise our own control logic and are not a substitute for these macOS checks. Upstream currently documents Linux-only support; this integration does not establish complete macOS support. The dependency scope is defined in the [MacPorts declarations](macports/ports.txt), not a promise to satisfy every upstream prerequisite.

## macOS defaults

GUI-only macOS settings scripted to avoid manual reconfiguration on a new Mac.

- Applied by bootstrap, or run standalone:

  ```sh
  ./macos/defaults.sh
  ```

- Idempotent: every run re-applies all settings and verifies each one by reading the value back (auto-verification, OK/NG)
- The configured settings and their values are defined in [`macos/defaults.sh`](macos/defaults.sh). Edit that script rather than maintaining a separate settings list here.

> Note: some settings may require a reboot to take effect. The script prints a restart notice after a successful run only when the trackpad tracking speed changes; it does not track whether a reboot is still pending.

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
