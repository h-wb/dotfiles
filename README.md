<div align="center">

### ~/.dotfiles&nbsp;

#### \> Managed with *mise*&nbsp;

</div>

## Overview

Dotfiles and full machine setup managed entirely by [mise](https://mise.jdx.dev):
packages (Homebrew, Mac App Store, pacman, apt, flatpak), macOS defaults,
LaunchAgents, services, firewall, tools and dotfiles, with secrets injected by
[fnox](https://github.com/jdx/fnox) from Proton Pass.

**This repo is mise's config directory.** `~/.config/mise` is a symlink to
`~/.dotfiles`, so mise reads every file here under its native name:

```
config.toml              every machine, paseo included: tools, env, vars, shell aliases, doctor checks
config.macos.toml        every Mac (loaded by platform): brew casks, ssh agent, wireguard
config.workstation.toml  personal/neko/cachyos: credentialed CLIs, kubeconfigs, apply tasks
config.personal.toml     the MacBook's own packages
miserc.toml              shared early-init settings (env_conf_d, auto_env)
conf.d/
  zsh/                   zsh + z4h + p10k (Macs)
  macos-defaults/        `defaults write`, declaratively (Macs)
  k8s-dns/               pick which cluster resolves the internal zone (MacBook)
  local-llm/             LM Studio GPU memory limit and RAM triage (MacBook)
  zen-history/           Zen history snapshots → Nextcloud (MacBook)
  claude-desktop/        Claude Desktop → the mcp-ops ToolHive gateway (MacBook)
  neko/                  the neko/xfce container, whole
  anki/                  Anki + AnkiConnect (n8n) + AnkiMCP (ToolHive) (neko)
  cachyos/               the CachyOS gaming desktop, whole
  paseo/                 the headless coding-agent pod
  pod/                   shared pod tools, locale and repositories
home/                    sources for the root configs (git, ssh, kube, wireguard, BTT)
fnox.toml                Proton Pass secret references (no values)
scripts/                 first-install helpers and Proton Pass preflight
```

Each `conf.d/` folder holds its own config and the files it uses; inside it,
`mise.<env>.toml` loads only for that machine class or platform.

### Machines

| class | machine | selected by |
| --- | --- | --- |
| `personal` | the MacBook | auto (macOS) |
| `neko` | XFCE desktop in a k8s pod ([neko](https://github.com/m1k1o/neko)) | auto (`/etc/neko`) |
| `cachyos` | CachyOS KDE gaming desktop | auto (`/etc/pacman.d/cachyos-mirrorlist`) |
| `paseo` | headless coding-agent pod | auto (`/etc/paseo`) |

`miserc.toml` detects the class; an untracked `miserc.local.toml`
overrides the complete layer list (for example,
`env = ["workstation", "pod", "neko"]`). `personal`, `neko` and `cachyos` use
`workstation`; `neko` and `paseo` use `pod`. Platform files (`*.macos.toml`, `*.linux.toml`)
load on their own. `~/.config/mise` → `~/.dotfiles` is itself a `[dotfiles]`
entry in `config.toml`, so mise creates and maintains the link.

## Set up a machine

```sh
sh -c "$(curl -fsLs https://raw.githubusercontent.com/h-wb/dotfiles/refs/heads/main/install.sh)"
```

On a Mac, sign in to iCloud and the App Store first. The installer installs mise,
clones to `~/.dotfiles` and runs `mise bootstrap` under fnox for workstation
machines, or directly for Paseo. Override the detected class with
`DOTFILES_ENV=personal|neko|cachyos|paseo`; the installer persists its layers too.

## Everyday use

```sh
mise run diff           # preview what apply would change
mise run apply          # provision everything, with secrets
mise run upgrade        # the same, with packages and tools upgraded (then commit the lockfiles)
mise doctor project     # wiring, config keys, native locked-install preview, tasks, file modes
mise run dns:edge       # (MacBook) resolve the internal zone via the edge cluster
```

Aliases (`g`, `repo`, `dfa`, ...) are `[shell_alias]` in the configs, set by
`mise activate` in zsh and fish alike.

`apply`, `diff` and `upgrade` belong to the workstation layer. Paseo reprovisions
with `paseo-bootstrap`. `diff` previews bootstrap steps; it does not show rendered
template differences. `mise bootstrap plan` covers only the resource planner's
subset of bootstrap, so it is not a replacement for that preview.

## Validate changes

```sh
python3 tests/test_setup.py -v  # Python 3.11+; isolated homes, no provisioning of this machine
mise tasks validate
mise install --locked --dry-run
```

The locked-install preview uses mise's own validation. PyPI dependency graphs
need their Python interpreter installed even for a preview; CI installs the
locked Python and uv first. Commit dependency sidecars along with `mise*.lock`;
`mise lock --global --sidecars` lists them. mise 2026.10.20 uses `.mise/locks/`
for this checkout's physical location; older `locks/` references remain readable
and migrate when mise rewrites the owning lockfile.

See [the mise audit](docs/mise-audit.md) for the feature review and remaining
tradeoffs.

### Where values come from

Templates read `{{ vars.x }}` and never name a source. `config.toml` defaults
each var to the environment, so a value can come from:

| source | used by |
| --- | --- |
| `fnox exec` injecting Proton Pass secrets | every machine (`mise run apply`) |
| an untracked `config.local.toml` `[vars]` (highest precedence) | a machine that prefers a literal |
| a real env var (e.g. k8s `envFrom`) | the neko container |

A var with no source renders empty and the templates skip their block, so a
partial set still produces valid files. The k8s-dns resolver is the exception:
it reads its IPs as bootstrap secrets, which abort the run instead.

## The neko/xfce container

Only `/home/neko` is persisted (a PVC); `/usr` and `/etc` are wiped on every pod
roll, and there is no systemd or launchd. So GUI apps are mise `[tools]` (on the
PVC), the apt list is tiny and reinstalled per start, and
`~/.config/autostart/mise-bootstrap.desktop` → `conf.d/neko/bin/neko-bootstrap`
re-provisions the desktop at every session start (`touch ~/.neko-hold` to pause
it; log at `~/.local/state/neko-bootstrap.log`).

To add a GUI app: a `[tools]` entry in `conf.d/neko/mise.neko.toml`, plus a
`.desktop` file in `conf.d/neko/xfce/applications/` and its `[dotfiles]` line.

## macOS permissions to grant by hand

- **Full Disk Access:** iTerm
- **Screen Recording:** AltTab
- **Accessibility:** AltTab, Discord, Plexamp, Raycast, KeyClu, Mos

## Inspiration

- https://github.com/onedr0p/dotfiles
- https://github.com/jdx/dotfiles
