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
- **`mise.personal.toml`** — profile overlay (loaded via `MISE_ENV=personal`).
- **`fnox.toml`** — Proton Pass secret references (no secret values).
- **`home/`** — dotfile sources (symlinked, or `.tmpl` rendered via Tera).

## Set up a new Mac

1. Sign in to iCloud and the App Store.
2. Run `sh -c "$(curl -fsLs https://raw.githubusercontent.com/h-wb/dotfiles/refs/heads/main/install.sh)"`

This installs mise, clones the repo to `~/.dotfiles`, symlinks its `mise.toml`
as the global mise config, and runs `mise bootstrap` under fnox.

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
