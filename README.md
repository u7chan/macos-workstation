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

# bootstrap: installs Xcode CLT (if missing) + MacPorts + dotfiles and fonts (chezmoi) + mise + runtimes, then runs myupdate
./bootstrap.sh
```

## Dotfiles

The [`home/`](home/) directory is the source of truth for dotfiles. chezmoi maps these definitions to their destinations:

| Definition | Destination | Purpose |
| --- | --- | --- |
| [`home/dot_gitconfig`](home/dot_gitconfig) | `~/.gitconfig` | Git commit identity, aliases, and explicit-identity enforcement |
| [`home/dot_zprofile`](home/dot_zprofile) | `~/.zprofile` | MacPorts and user command PATH |
| [`home/dot_zshrc`](home/dot_zshrc) | `~/.zshrc` | mise activation, shell aliases, and prompt initialization |
| [`home/dot_config/mise/config.toml`](home/dot_config/mise/config.toml) | `~/.config/mise/config.toml` | Tool declarations and version constraints |
| [`gpc`](home/dot_local/bin/executable_gpc) | `~/.local/bin/gpc` | Update a base branch or clean up the current merged PR branch |
| [`myupdate`](home/dot_local/bin/executable_myupdate) | `~/.local/bin/myupdate` | Daily user-level Pi, managed package, and skill updates |
| [Harness launcher](home/dot_local/bin/executable_agent-harness-exec) | `~/.local/bin/agent-harness-exec` | Process-local environment for upstream GitHub/review harnesses |
| [Harness invocation rule](home/private_dot_pi/private_agent/modify_private_AGENTS.md) | `~/.pi/agent/AGENTS.md` | Updates only a marked instruction block, preserving other instructions |
| [Font archive declaration](home/.chezmoiexternal.toml) | User font directory declared in the file | Pinned font download, checksum, and included files |
| [Ghostty configuration](home/Library/Application%20Support/com.mitchellh.ghostty/config) | `~/Library/Application Support/com.mitchellh.ghostty/config` | Ghostty font settings |

- bootstrap converges the machine with `chezmoi apply --source=./home --force`
- Manual edits on the machine are treated as temporary experiments. To keep a change, edit a file under `home/` and submit a PR

### Git

Git commit identity, aliases, and explicit-identity enforcement are defined in the [Git configuration](home/dot_gitconfig). The managed identity uses a public GitHub username and GitHub-provided noreply address, not a private email address or credential. Bootstrap applies this file through chezmoi; repository-local Git settings can override the managed defaults when needed.

#### Update and clean up with `gpc`

The managed [`gpc` command](home/dot_local/bin/executable_gpc) is installed by the existing chezmoi step in `./bootstrap.sh`. Open a new login terminal after applying the [PATH configuration](home/dot_zprofile), then run `gpc` from a repository's primary worktree.

On a supported base branch, `gpc` only pulls from `origin` with `--ff-only`; it does not query GitHub or delete branches. On a work branch, it verifies that the matching PR in the GitHub repository configured as `origin` is merged and that the local tip matches the PR head. It then switches to the PR base, pulls with `--ff-only`, and deletes only the original work branch after confirming that the PR merge commit is present. This also supports squash merges. Supported base branches are defined in the script.

Uncommitted changes, untracked files, detached HEADs, and linked worktrees stop the command. Pull failures or diverged history stop cleanup without deleting the work branch; if switching has already succeeded, you remain on the base branch. The command never stashes, resets, or sweeps other branches.

Run `gpc --help` for a usage summary. Automated tests use temporary Git repositories and a simulated GitHub CLI; verify the installed command's PATH and actual GitHub PR lookup separately on a real machine.

### Shell prompt

[Starship](https://starship.rs/) is managed through the [mise configuration](home/dot_config/mise/config.toml) and initialized after mise activation in the [zsh configuration](home/dot_zshrc). It uses the default prompt without a custom Starship configuration.

Run `./bootstrap.sh`, then open a new terminal window to load the prompt. Verify the installation with `starship --version`. The managed [Ghostty font settings](home/Library/Application%20Support/com.mitchellh.ghostty/config) use a Nerd Font for prompt symbols; other terminals need a compatible font selected separately.

### Ghostty

Font settings are defined in the [Ghostty configuration](home/Library/Application%20Support/com.mitchellh.ghostty/config). The [font archive declaration](home/.chezmoiexternal.toml) defines the upstream release URL, SHA-256 checksum, destination, and included font and license files. Font binaries are downloaded by chezmoi, not committed to this repository; unrelated user fonts are left untouched.

`./bootstrap.sh` installs the declared fonts and applies the configuration to Ghostty's macOS-native path as part of the dotfiles step. chezmoi caches the pinned archive and verifies its checksum; repeated runs converge the managed files without installing duplicate copies. To update the font release, change the URL and checksum together in the declaration, checking the checksum against the upstream release's `SHA-256.txt`.

Restart Ghostty after applying font changes. Ghostty itself must be installed separately. For a real-machine check, run `ghostty +list-fonts` and confirm that the family configured above is available, then check regular, bold, italic, Japanese text, and Nerd Font symbols in a new terminal window.

## Agent skills

Bootstrap delegates Pi package and skill installation to the installed [`myupdate` command](home/dot_local/bin/executable_myupdate), which defines the managed package sources and skill branch. There is no separate bootstrap-only skill updater. Each run resolves the upstream skill branch head to a commit and installs that revision through pi; upstream skill changes do not require a change to this repository. The revision is printed and saved in pi's user package settings. Development checkouts are not used or modified, and unrelated pi settings and package resource filters are preserved.

Run updates between tasks, then `/reload` or restart every running pi session before using updated packages and skills. A new Pi version requires a restart.

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

### Daily Pi updates

After starting the computer, run this manually before beginning work:

```sh
myupdate
```

Bootstrap installs this command through chezmoi, prepares the mise runtimes, then invokes it once. The installed command works from any directory without the repository checkout. It updates only Pi through mise (within the global tool constraint), installs or refreshes the npm packages declared in the [command](home/dot_local/bin/executable_myupdate), and resolves and installs the latest configured skill-branch commit. Existing managed Pi installations are kept so running sessions do not lose their files. Missing packages are installed on the first run; Pi owns package registration and preserves unrelated settings and resource filters.

The command uses the global mise configuration, ignores project-local Pi configuration, and never runs `sudo`, schedules itself, or updates other runtimes, MacPorts, or macOS settings. It stops on the first failure without retrying or reporting success; already completed updates are not rolled back. Invalid Pi settings stop the command before any update. An atomic directory lock prevents concurrent `myupdate` runs. If an interrupted run leaves a stale lock, check that no update is running before removing the empty lock directory shown in the error.

Restart Pi after an update, or use `/reload` for package/skill-only changes. Check the printed Pi version, user package list, and skill revision. For a real-machine smoke check, confirm the declared extensions load and exercise a public web search and a search for a known local session. Session query can send selected past conversations to the query model; the current project is not a privacy boundary, and WSL sessions are not synchronized automatically.

### Reapply workstation configuration

```sh
git pull --ff-only
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
