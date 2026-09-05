<div align="center">

### ~/.dotfiles&nbsp;

#### \> Managed with *mise*&nbsp;

</div>

## Overview

Dotfiles and full machine setup managed entirely by [mise](https://mise.jdx.dev)
— packages (Homebrew formulae/casks + Mac App Store), macOS defaults, LaunchAgents,
tools, and dotfiles — with secrets injected by [fnox](https://github.com/jdx/fnox)
from Proton Pass. No chezmoi.

- **`mise.toml`** — the single config: `[vars]`, `[tools]`, `[env]`, `[bootstrap.*]`, `[dotfiles]`, `[tasks]`.
- **`conf.d/`** — split-out fragments merged into the global config: `macos-defaults.toml`, `settings.toml` (always loaded), and env-scoped ones like `prefect-worker.personal.toml` (loaded only when that env is active).
- **`mise.personal.toml`** — env overlay, loaded when `personal` is an active env.
- **`mise.neko.toml`** — env overlay for the neko/xfce container (Debian, fish, XFCE); see below.
- **`miserc.toml.example`** — template for the per-machine `~/.config/mise/miserc.toml` (which env(s) are active + `env_conf_d`); see below.
- **`fnox.toml`** — Proton Pass secret references (no secret values).
- **`home/`** — dotfile sources (symlinked, or `.tmpl` rendered via Tera).

### Environments

Which overlays load is decided per machine by `~/.config/mise/miserc.toml` (untracked, copied from `miserc.toml.example` by `install.sh`):

```toml
env = ["personal"]   # loads mise.personal.toml + conf.d/*.personal.toml
env_conf_d = true    # enable env-scoped conf.d/<name>.<env>.toml filenames
```

Machines in use: `["personal"]` on the MacBook, `["neko"]` in the neko container.

`miserc.toml` must live at `~/.config/mise/` (not in `mise.toml`) because it controls config *discovery*, which runs before `mise.toml` is read. To scope something to this machine class, name its fragment `conf.d/<name>.personal.toml`; plain `conf.d/<name>.toml` always loads.

## Set up a new Mac

1. Sign in to iCloud and the App Store.
2. Run `sh -c "$(curl -fsLs https://raw.githubusercontent.com/h-wb/dotfiles/refs/heads/main/install.sh)"`

This installs mise, clones the repo to `~/.dotfiles`, symlinks its `mise.toml`
as the global mise config, and runs `mise bootstrap` under fnox.

## The neko/xfce container

A browser-accessible XFCE desktop ([neko](https://github.com/m1k1o/neko),
`ghcr.io/m1k1o/neko/xfce`) running in k8s. Same repo, same `install.sh`, `env = ["neko"]`
— but the box is shaped differently, and the config follows that shape:

| macOS | neko container |
| --- | --- |
| Homebrew casks | `~/.local/opt` unpacked apps — one catalog line each (`conf.d/neko-apps.neko.toml`) |
| `defaults write` | `xfconf-query` (`conf.d/xfce.neko.toml`) |
| LaunchAgents | `~/.config/autostart/mise-bootstrap.desktop` → `home/bin/neko-bootstrap` |
| zsh + z4h + p10k | fish + starship (`home/fish/`, `home/starship.toml`) |

**Only `/home/neko` is persisted** (a PVC); `/usr` and `/etc` come from the image and
are wiped on every pod roll. Do *not* mount volumes over those — an empty volume over
`/usr` leaves the container with no binaries, and it freezes a stale copy of the image.
Instead: everything durable lives in `$HOME` (mise itself, all `[tools]`, dotfiles, the
`~/.local/opt` apps), and the small apt list is reinstalled automatically at each
session start by the autostart entry. If that list ever grows expensive, bake a derived
image (`FROM ghcr.io/m1k1o/neko/xfce`) rather than persisting more paths.

There is no systemd and no launchd in that container (supervisord is pid 1), so
`[bootstrap.linux.systemd.units]` is not usable there — hence the autostart entry.

```sh
# first run, inside the container's terminal
sh -c "$(curl -fsLs https://raw.githubusercontent.com/h-wb/dotfiles/refs/heads/main/install.sh)"
tail -f ~/.local/state/neko-bootstrap.log   # what the autostart run did
NEKO_APPS_UPGRADE=1 mise run neko:apps      # force-reinstall the GUI apps at latest
```

### Adding a GUI app

Homebrew is not usable for this — on Linux `brew-cask` handles font casks only, and
mise's brew prefix (`/home/linuxbrew/.linuxbrew`) isn't on the PVC. So apps are
unpacked into `~/.local/opt` by `home/bin/neko-app`, and adding one is a line in the
catalog in `conf.d/neko-apps.neko.toml`:

```
# name   | source                                                            | exe      | args         | display  | categories
obsidian | gh:obsidianmd/obsidian-releases:obsidian-[0-9.]+{,-arm64}\.tar\.gz | obsidian | --no-sandbox | Obsidian | Office;TextEditor;
```

`gh:` picks the newest matching release asset, `url:` follows a vendor "latest"
redirect; `{a,b}` selects by architecture. Tarballs, AppImages (extracted, not
FUSE-mounted) and `.deb`s all work. The resolved URL is recorded, so new upstream
releases reinstall themselves on the next bootstrap.

Flatpak would be nicer still — `~/.local/share/flatpak` is on the PVC and mise
supports `flatpak-user:` entries — but it needs bubblewrap to create a user
namespace. Check with `unshare -Ur true` in the container; if it prints nothing and
exits 0, enable `conf.d/neko-flatpak.neko.toml.example`.

## Everyday use

```sh
mise run diff     # preview what bootstrap would change
mise run apply    # apply everything (packages, macOS, dotfiles, tools) with secrets via fnox
```

Bare `mise bootstrap` works on a machine without secrets (secret-guarded dotfiles
render empty). Per-machine overrides go in an untracked `mise.local.toml`.

## Security & Privacy System Preferences

Grant permissions to these apps:

- **Full Disk Access:** iTerm
- **Screen Recording:** AltTab
- **Accessibility:** AltTab, Discord, Plexamp, Raycast, KeyClu, Mos

## Inspiration

- https://github.com/onedr0p/dotfiles
- https://github.com/jdx/dotfiles
