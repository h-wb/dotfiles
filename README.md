<div align="center">

### ~/.dotfiles&nbsp;

#### \> Managed with *mise*&nbsp;

</div>

## Overview

Dotfiles and full machine setup for four machines, managed entirely by
[mise](https://mise.jdx.dev): packages (Homebrew, Mac App Store, pacman, apt,
flatpak), macOS defaults and login items, LaunchAgents, systemd units, the
firewall, tools and dotfiles. Secrets are injected by
[fnox](https://github.com/jdx/fnox) from Proton Pass; none is committed.

| class | machine | detected by |
| --- | --- | --- |
| `personal` | the MacBook | macOS |
| `neko` | XFCE desktop in a k8s pod ([neko](https://github.com/m1k1o/neko)) | `/etc/neko` |
| `cachyos` | CachyOS KDE gaming desktop | `/etc/pacman.d/cachyos-mirrorlist` |
| `paseo` | headless coding-agent pods | `/etc/paseo` |

## Layout

**This repo is mise's config directory.** `~/.config/mise` is a symlink to
`~/.dotfiles`, so mise reads every file here under its native name:

```
config.toml              every machine: tools, env, vars, shell aliases, doctor checks
config.workstation.toml  personal, neko, cachyos: credentialed CLIs, kubeconfigs, the apply tasks
miserc.toml              picks this machine's class and layers
conf.d/                  one folder per machine, and the features
  ai/                    every machine: the agents' MCP servers and shared skills
  proton-pass/           every machine: the named-session login task other repos extend
  macos/                 the Macs: apps, zsh, ssh agent, wireguard, BetterTouchTool; the MacBook's own packages
  macos-defaults/        `defaults write`, declaratively
  macos-k8s-dns/         pick which cluster resolves the internal zone (MacBook)
  macos-zen-history/     Zen history snapshots → Nextcloud (MacBook)
  neko/                  the neko/xfce container
  neko-anki/             Anki + AnkiConnect (n8n) + AnkiMCP (ToolHive), kept running there
  neko-obsidian/         Obsidian + Local REST API (n8n), kept running there
  cachyos/               the CachyOS gaming desktop
  paseo/                 the coding-agent pods, and the skills only they use
home/                    sources for the two root configs (git, ssh, kube)
fnox.toml                Proton Pass secret references (no values); the agents' own in conf.d/ai/
scripts/                 first-install helpers and the Proton Pass preflight
tests/                   regressions, run in throwaway homes
```

Each `conf.d/` folder holds its own config and the files it uses, and its name
says where it loads:

- a machine's folder is named like its environment (`neko`);
- a feature only that machine has is `<machine>-<feature>` (`neko-anki`);
- a folder with no machine in its name loads on several (`ai`).

Inside a folder, `mise.<env>.toml` says exactly when: `macos/` holds
`mise.macos.toml` for any Mac and `mise.personal.toml` for the MacBook.

`miserc.toml` detects the class and adds its layers: `personal`, `neko` and
`cachyos` also load `workstation`. An untracked `miserc.local.toml` pins a
class by name (`env = ["neko"]`). Platform files (`*.macos.toml`) load on
their own.

## Set up a machine

```sh
sh -c "$(curl -fsLs https://raw.githubusercontent.com/h-wb/dotfiles/refs/heads/master/install.sh)"
```

On a Mac, sign in to iCloud and the App Store first. The installer installs
mise, clones to `~/.dotfiles` and runs `mise bootstrap`, under fnox on a
workstation and directly on a Paseo pod. `DOTFILES_ENV=personal|neko|cachyos|paseo`
overrides the detected class; the installer saves it in `miserc.local.toml`.

## Everyday use

```sh
mise run diff           # preview what apply would change
mise run apply          # provision everything, with secrets
mise run upgrade        # the same, with packages and tools upgraded (then commit the lockfiles)
mise doctor project     # wiring, config keys, locked-install preview, tasks, file modes
mise run dns:edge       # (MacBook) resolve the internal zone via the edge cluster
```

Aliases (`g`, `repo`, `dfa`, ...) are `[shell_alias]` in the configs, set by
`mise activate` in zsh, fish and bash alike.

`apply`, `diff` and `upgrade` belong to the workstation layer; the Paseo pods
reprovision at every start instead (`mise bootstrap --from` in home-ops).
`diff` previews the bootstrap steps but does not render templates.

## Secrets

Templates read `{{ vars.x }}` and never name a source. Each var defaults to
the environment, so a value can come from:

| source | used by |
| --- | --- |
| `fnox exec` injecting Proton Pass secrets | every workstation (`mise run apply`) |
| an untracked `config.local.toml` `[vars]` (highest precedence) | a machine that prefers a literal |
| a real env var (k8s `envFrom`) | the neko container, the pods |

A var with no source renders empty and the templates skip their block, so a
partial set still produces valid files. That is also the trap: a dead Proton
Pass session would render every secret empty over the good copies, so `apply`
checks the session first and fnox runs with `--if-missing error`.

The k8s-dns resolver is the exception. It reads its zone and nameserver as
bootstrap secrets, which abort the run before anything is written.

## Validate changes

```sh
python3 tests/test_setup.py -v  # Python 3.11+; isolated homes, nothing here is provisioned
mise doctor project
```

CI runs the same tests on macOS and Linux with the minimum and the latest
mise, then renders each machine class's dotfiles. Commit dependency sidecars
(`locks/`) along with `mise*.lock`; `mise lock --global --sidecars` lists them.

## Machine notes

### The neko/xfce container

Only `/home/neko` is persisted (a PVC). `/usr` and `/etc` are wiped on every
pod roll, and there is no systemd or launchd. So GUI apps are mise `[tools]`
(on the PVC), the apt list is tiny and reinstalled per start, and
`~/.config/autostart/mise-bootstrap.desktop` runs
`conf.d/neko/bin/neko-bootstrap` to reprovision the desktop at every session
start. `touch ~/.neko-hold` pauses it; the log is
`~/.local/state/neko-bootstrap.log`.

To add a GUI app: a `[tools]` entry in `conf.d/neko/mise.neko.toml`, a
`.desktop` file in `conf.d/neko/xfce/applications/` and its `[dotfiles]` line.

### macOS permissions to grant by hand

Apps this repo installs that ask on first launch:

- **Full Disk Access:** Ghostty
- **Accessibility:** AltTab, BetterTouchTool, Plexamp, Raycast
- **Screen Recording:** AltTab, ScreenMemory

## More

- [CLAUDE.md](CLAUDE.md): how the repo works in depth, and what is easy to break.
- [conf.d/ai](conf.d/ai/README.md): the agents' MCP servers, scopes, keys and skills.
- [conf.d/proton-pass](conf.d/proton-pass/README.md): managed Proton Pass sessions and the vault layout.
- [docs/mise-audit.md](docs/mise-audit.md): which mise features are used, which are not, and why.

## Inspiration

- https://github.com/onedr0p/dotfiles
- https://github.com/jdx/dotfiles
