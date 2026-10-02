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
config.toml              every machine: tools, env, vars, shell aliases, tasks, doctor checks
config.macos.toml        every Mac (loaded by platform): brew casks, ssh agent, wireguard
config.personal.toml     the MacBook's own packages
miserc.toml              shared early-init settings (env_conf_d, auto_env)
conf.d/
  zsh/                   zsh + z4h + p10k (Macs)
  macos-defaults/        `defaults write`, declaratively (Macs)
  k8s-dns/               pick which cluster resolves the internal zone (MacBook)
  zen-history/           Zen history snapshots → Nextcloud (MacBook)
  neko/                  the neko/xfce container, whole
  cachyos/               the CachyOS gaming desktop, whole
home/                    sources for the root configs (git, ssh, kube, wireguard, BTT)
fnox.toml                Proton Pass secret references (no values)
scripts/                 pass-preflight (gates every apply on a Proton Pass session)
```

Each `conf.d/` folder holds its own config and the files it uses; inside it,
`mise.<env>.toml` loads only for that machine class or platform.

### Machines

| class | machine | selected by |
| --- | --- | --- |
| `personal` | the MacBook | auto (macOS) |
| `neko` | XFCE desktop in a k8s pod ([neko](https://github.com/m1k1o/neko)) | auto (`/etc/neko`) |
| `cachyos` | CachyOS KDE gaming desktop | auto (`/etc/os-release`) |

`miserc.toml` detects the class; an untracked `miserc.local.toml`
(`env = ["..."]`) overrides it. Platform files (`*.macos.toml`, `*.linux.toml`)
load on their own. `~/.config/mise` → `~/.dotfiles` is itself a `[dotfiles]`
entry in `config.toml`, so mise creates and maintains the link.

## Set up a machine

```sh
sh -c "$(curl -fsLs https://raw.githubusercontent.com/h-wb/dotfiles/refs/heads/main/install.sh)"
```

On a Mac, sign in to iCloud and the App Store first. The installer installs mise,
clones to `~/.dotfiles` and runs `mise bootstrap` under
fnox. Override the detected class with `DOTFILES_ENV=personal|neko|cachyos`.

## Everyday use

```sh
mise run diff           # preview what apply would change
mise run apply          # provision everything, with secrets
mise doctor project     # the repo's invariants (wiring, lockfiles, file modes, ...)
mise run dns:edge       # (MacBook) resolve the internal zone via the edge cluster
```

Aliases (`g`, `repo`, `dfa`, ...) are `[shell_alias]` in the configs, set by
`mise activate` in zsh and fish alike.

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
