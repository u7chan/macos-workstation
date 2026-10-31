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
| [`home/dot_zshrc`](home/dot_zshrc) | `~/.zshrc` | mise activation, shell aliases, Yazi integration, and prompt initialization |
| [`home/dot_config/mise/config.toml`](home/dot_config/mise/config.toml) | `~/.config/mise/config.toml` | Tool declarations and version constraints |
| [`gpc`](home/dot_local/bin/executable_gpc) | `~/.local/bin/gpc` | Update a base branch or clean up the current merged PR branch |
| [`myupdate`](home/dot_local/bin/executable_myupdate) | `~/.local/bin/myupdate` | Daily user-level tool, Pi package, and skill updates |
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

### Yazi

[Yazi](https://yazi-rs.github.io/) is the managed terminal file manager. Its tool declaration and portable search, navigation, and preview helpers are defined in the [mise configuration](home/dot_config/mise/config.toml); OS-level helpers are defined in the [MacPorts declarations](macports/ports.txt). No custom Yazi configuration or plugins are installed; upstream defaults are used. Heavyweight document, video, and image-conversion preview helpers are left for separate configuration.

Run `./bootstrap.sh` to install and apply the declarations, then open a new Ghostty window. As with other bootstrap runs, exit all Pi sessions first because bootstrap also runs the daily Pi updater.

Launch with `y` to return to the directory selected in Yazi when pressing `q`. Press `Q` to leave the shell directory unchanged, or launch with `yazi` when directory synchronization is not needed. The wrapper and directory-history initialization are managed in the [zsh configuration](home/dot_zshrc). Failed launches leave the shell directory unchanged and remove the temporary directory-transfer file.

Current Ghostty and Yazi releases support image previews without additional terminal configuration. The existing managed fonts provide the file icons. For a real-machine check, open a fresh login shell, run `ya env` to inspect terminal and dependency detection, and check image, SVG, and archive previews. Also verify filename/content search, directory-history navigation, and both exit behaviors. If using tmux, follow the upstream [image-preview instructions](https://yazi-rs.github.io/docs/image-preview/#tmux-users); tmux configuration is not managed here.

### JavaScript tools and global CLIs

Declare shared JavaScript tools in the [global mise configuration](home/dot_config/mise/config.toml), which is the source of truth for installed tools and version constraints. Bootstrap installs those declarations; the existing [zsh configuration](home/dot_zshrc) activates mise so their commands are available from any working directory. Project-local mise settings can select a different version. pnpm uses an explicit npm backend so Intel Macs do not depend on Aqua's standalone-binary platform coverage; keep that backend explicit rather than using the registry-dependent shorthand. Its narrowly scoped build-script approval lets the package replace command stubs with its native executable; do not broaden that approval to all packages.

For an npm-distributed CLI, add an `npm:<package-name>` tool entry to that configuration instead of installing it with `npm install -g`, `bun add -g`, or `pnpm add -g`. mise manages each CLI separately from those package managers' global prefixes, so use `mise ls --global` rather than `npm list -g` to inspect the managed tools. Keep project dependencies in each project's `package.json` and lockfile.

[`myupdate`](home/dot_local/bin/executable_myupdate) discovers declared global npm CLIs automatically and updates them and the supported JavaScript runtime/package-manager tools through mise. It does not import, update, or delete packages previously installed into standalone npm, Bun, or pnpm global directories. Inspect existing commands with `command -v` and migrate duplicates separately; they can shadow mise-managed commands on PATH. Do not use a tool's self-updater to replace a mise-managed binary.

For a real-machine check after bootstrap, open a new login terminal and verify `command -v bun`, `bun -v`, `command -v pnpm`, and `pnpm -v` from an unrelated directory. Check `mise ls --global` and confirm that project-specific version selections and dependencies are unchanged. Automated update tests simulate external installations and do not replace this check.

### Herdr

[Herdr](https://herdr.dev/) is managed through the [mise configuration](home/dot_config/mise/config.toml). Bootstrap installs it with the other declared tools, and [`myupdate`](home/dot_local/bin/executable_myupdate) refreshes it within that declaration's version constraint. Herdr configuration, plugins, and workspace layouts are not managed here.

Run `./bootstrap.sh` after exiting all Pi sessions, then open a new terminal. Check `command -v herdr` and `herdr --version`, then launch `herdr`. An existing standalone installation can shadow the mise-managed binary on PATH; inspect and migrate it separately rather than deleting it automatically.

Updates use mise, not `herdr update`. The updater retains old binaries and never stops or restarts Herdr servers or panes. Launch Herdr again after an update to use the new client; a compatible running server remains on its existing version. Apply server-side changes later with a deliberate restart, following the upstream [update guidance](https://herdr.dev/docs/install/#update). Stopping a server also stops its pane processes, so finish work first.

Automated tests cover update scope, failure propagation, and chezmoi deployment in an isolated HOME. For a real-machine check, verify the resolved binary and version, then check launching, splitting panes, and detaching and reattaching. Tests do not establish terminal rendering or running-server compatibility.

## Agent skills

Bootstrap delegates Pi package and skill installation to the installed [`myupdate` command](home/dot_local/bin/executable_myupdate), which defines the managed package sources and skill branch. There is no separate bootstrap-only skill updater. Each run resolves the upstream skill branch head to a commit and installs that revision through pi; upstream skill changes do not require a change to this repository. The revision is printed and saved in pi's user package settings. Development checkouts are not used or modified, and unrelated pi settings and package resource filters are preserved.

Exit all Pi sessions before running `myupdate` or bootstrap, then start Pi again after updates finish. See [Daily user-level updates](#daily-user-level-updates) for the normal workflow.

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

### Daily user-level updates

After starting the computer, exit all Pi sessions, including those in other terminal windows or panes. Then run this manually before beginning work:

```sh
myupdate
```

Bootstrap installs this command through chezmoi, prepares the mise runtimes, then invokes it once. The installed command works from any directory without the repository checkout. It updates Pi and Herdr plus the declared global JavaScript tools through mise (within the global tool constraints), installs or refreshes the Pi packages declared in the [command](home/dot_local/bin/executable_myupdate), and resolves and installs the latest configured skill-branch commit. The command reads the global configuration's tool declarations through mise's configuration metadata, without resolving versions, and selects the supported JavaScript runtime/package-manager tools and all `npm:` entries; adding another global npm CLI does not require editing the updater. Version-resolution failures cannot silently omit a declared CLI from this selection. Git packages that track a branch are refreshed to its latest commit on each run. Missing packages are installed on the first run; Pi owns package registration and preserves unrelated settings and resource filters. Existing extension installations are not removed or migrated; check package documentation for conflicts before loading overlapping extensions.

The `--no-prune` safeguard retains old installations for every updated mise tool so their files remain available to running processes. It does not make live Pi package or skill updates safe, and old versions are not scheduled for automatic removal. Herdr servers and panes are left running; see [Herdr](#herdr) for the separate server-restart considerations. See [Remove old Pi versions](#remove-old-pi-versions) for optional manual cleanup.

The command uses the global mise configuration and ignores project-local mise and Pi configuration. It never runs `sudo` or schedules itself, and it does not update Node.js, Python, other mise tools outside its selection policy, project dependencies, standalone package-manager global directories, MacPorts, or macOS settings. It stops on the first failure without retrying or reporting success; already completed updates are not rolled back. Invalid Pi settings or missing, invalid, or unreadable global declaration metadata stop the command before any update. An atomic directory lock prevents concurrent `myupdate` runs. If an interrupted run leaves a stale lock, check that no update is running before removing the empty lock directory shown in the error.

Start Pi again after the update completes. Check the printed Pi and Herdr versions, user package list, and skill revision. For a real-machine smoke check, confirm the declared extensions load and exercise a public web search and a search for a known local session. Session query can send selected past conversations to the query model; the current project is not a privacy boundary, and WSL sessions are not synchronized automatically.

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

### Remove old Pi versions

`myupdate` keeps old Pi installations with `--no-prune`, so upgrades to new versions can accumulate old ones. Repeating an update without a new version does not create another copy. This optional cleanup does not stop managing Pi: keep its declaration in the [global mise configuration](home/dot_config/mise/config.toml) unchanged.

Exit all Pi sessions before cleanup. Preview unused versions for Pi only:

```sh
mise -C "$HOME" prune --tools --dry-run npm:@earendil-works/pi-coding-agent
```

Review the candidates and confirm that all Pi sessions are closed before deleting them. Do not treat a dry-run as a check that no running process uses those files.

```sh
mise -C "$HOME" prune --tools npm:@earendil-works/pi-coding-agent
```

Versions still referenced by tracked configurations or tool stubs are retained. Cleanup is a separate manual operation; `myupdate` does not run it automatically.

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

## CI

Workflow action dependencies are locked by the [lockfile](.github/workflows/actions.lock), so a workflow keeps readable version tags while the runner executes the commit SHA recorded there. The lockfile covers every direct and transitive action dependency of the workflows in [`.github/workflows/`](.github/workflows).

The lockfile is machine-generated; do not edit it by hand. Regenerate it with `gh actions-lock` (the GitHub CLI extension `github/gh-actions-lock`, installed at the pinned version used by the [tests workflow](.github/workflows/tests.yml)). When you add or change an action or a workflow, regenerate the lockfile in the same pull request. The `actions-lock` job in that workflow runs `gh actions-lock --verify` and fails when the lockfile does not cover the current workflow references, so a missing pin is caught before merge rather than at review time.

[Dependabot](.github/dependabot.yml) opens weekly pull requests that update the action references and the lockfile together. Review a lockfile diff as a dependency update: `commit` is the code that will run, and a change to `owner_id` or `repo_id` means the reference repository itself changed.

Out of scope for the lockfile: the runner image, container images, tools installed by `run:` steps, and reusable workflows. Reusable workflow calls are not covered, so a call site must be pinned to a full commit SHA; this repository currently makes none.
