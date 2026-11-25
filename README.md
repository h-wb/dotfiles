---
area: "[[Homelab]]"
categories:
  - "[[Resources]]"
reviewed: 2026-11-25
summary: What this repo sets up on each machine, how to bootstrap one, where each part lives, and how secrets reach the files.
topics:
  - "[[Workshop]]"
  - "[[Device collector]]"
created: 2022-02-20T21:04
---

<div align="center">

### ~/.dotfiles&nbsp;

#### \> Managed with *mise*&nbsp;

</div>

## Overview

Dotfiles and full machine setup for five machine classes, managed entirely by [mise](https://mise.jdx.dev): packages (Homebrew formulae and casks, Mac App Store, pacman, apt, flatpak), macOS defaults and login items, LaunchAgents, systemd units, the firewall, tools and dotfiles. It also defines what every coding agent gets: its tool and memory servers, rendered per scope, and the skill groups it takes from [h-wb/skills](https://github.com/h-wb/skills). Secrets are injected by [fnox](https://github.com/jdx/fnox) from Proton Pass; none is committed.

How this fits with the other repos is in the [handbook](https://github.com/h-wb/handbook): [dotfiles](https://github.com/h-wb/handbook/blob/main/Repos/dotfiles.md), and [Workshop](https://github.com/h-wb/handbook/blob/main/Systems/Workshop.md) for agents.

| Class | Machine | Declared by | Layers | Page |
| --- | --- | --- | --- | --- |
| `personal` | the MacBook | `DOTFILES_ENV=personal install.sh`, once | `workstation` | [macos](conf.d/macos/README.md) |
| `neko` | an XFCE desktop in a pod ([neko](https://github.com/m1k1o/neko)) | home-ops (`components/dotfiles`) | `workstation`, `pod`, `fish` | [neko](conf.d/neko/README.md) |
| `cachyos` | a CachyOS KDE gaming desktop | `DOTFILES_ENV=cachyos install.sh`, once | `workstation`, `fish` | [cachyos](conf.d/cachyos/README.md) |
| `paseo` | the headless coding-agent pods | home-ops, `mise -E paseo,paseo-overlay bootstrap` | none | [paseo](conf.d/paseo/README.md) |
| `code-server` | the owner's browser editor in a pod | home-ops (`components/dotfiles`) | `workstation`, `pod`, `fish` | [code-server](conf.d/code-server/README.md) |

What several classes share is a layer, not a copy in each:

| Layer | Holds |
| --- | --- |
| `workstation` (`config.workstation.toml`) | what assumes a person and a Proton Pass session: credentialed CLIs (aws, bws, metabase), the `apply`, `diff`, `upgrade` and `land` tasks, both kubeconfigs |
| `pod` (`conf.d/pod/`) | a workstation in a pod: pass-cli's key on the volume, the repos a fresh volume needs, doctor `pod-start`. The Paseo pods do not load it |
| `fish` (`conf.d/fish/`) | one `config.fish`, the starship prompt and `ef`; not the fish binary. A machine's own lines go in `conf.d/<machine>/fish/<machine>.fish`, linked into `~/.config/fish/conf.d/` |

Nothing is detected: the caller declares the environment, and `mise bootstrap --save-env` writes it to the untracked `miserc.local.toml` (`env = ["neko"]`). `[env_sets]` in `miserc.toml` adds the class's layers. With nothing declared, only `config.toml` and the shared folders load, and doctor `wiring` fails. How that works: [docs/mise.md](docs/mise.md#how-a-machine-picks-its-files).

## Layout

This repo is mise's config directory: `~/.config/mise` is a symlink to `~/.dotfiles`, so mise reads every file here under its native name.

```
config.toml              every machine: tools, env, vars, shell aliases, doctor checks
config.workstation.toml  layer workstation
miserc.toml              each class's layers ([env_sets])
conf.d/                  one folder per machine, and the features
  ai/                    every machine: the agents' tool and memory servers, the skill group every machine takes
  proton-pass/           every machine: the named-session login task other repos extend
  pod/                   layer: a workstation in a pod (neko, code-server)
  fish/                  layer: config.fish and the starship prompt (neko, cachyos, code-server)
  macos/                 the Macs: apps, zsh, ssh agent, WireGuard; the MacBook's own packages
  macos-defaults/        `defaults write`, declared
  macos-k8s-dns/         which cluster resolves the internal zone (MacBook)
  macos-miroir-collector/ the device collector, hourly, with Proton Pass tokens (MacBook)
  neko/                  the neko/xfce container
  neko-anki/             Anki with AnkiConnect and AnkiMCP, kept running there
  neko-obsidian/         Obsidian with the Local REST API, kept running there
  cachyos/               the CachyOS gaming desktop
  paseo/                 the coding-agent pods, and the skill group only they take
  code-server/           the code-server pod: the fish binary and its editor settings
home/                    sources for the root configs (git, ssh, kube)
fnox.toml                Proton Pass references for provisioning (no values); the agents' own are in conf.d/ai/
scripts/                 the apply task's body, the Proton Pass preflight, land
tests/                   regressions, run in throwaway homes
docs/                    how this repo uses mise
vendor/skills/           the skills catalogue, h-wb/skills, a submodule that follows its main
```

A folder's name says where it loads: a machine's folder is named like its environment (`neko`), a feature only that machine has is `<machine>-<feature>` (`neko-anki`), and a folder with no machine in its name loads on several (`ai`). Inside a folder, `mise.<env>.toml` says exactly when: `macos/` holds `mise.macos.toml` for any Mac and `mise.personal.toml` for the MacBook.

## Set up a machine

```sh
sh -c "$(curl -fsLs https://raw.githubusercontent.com/h-wb/dotfiles/refs/heads/master/install.sh)"
```

Run it with `DOTFILES_ENV=personal` (the MacBook) or `DOTFILES_ENV=cachyos` the first time; `mise bootstrap --save-env` keeps it in `miserc.local.toml`, so later runs need it only to change it. On a Mac, sign in to iCloud and the App Store first. The installer installs mise where it is missing, then runs the two steps every machine runs ([docs/mise.md](docs/mise.md#one-bootstrap-two-steps)): `mise bootstrap --from` clones to `~/.dotfiles` (an existing checkout is used as it is: update it with git) and saves the environment, then `mise run apply` provisions with secrets.

The pods run the same two steps from home-ops at every start, at one pinned commit of this repo (`DOTFILES_REF`, bumped by reviewed Renovate pull requests) and with the pod's declared environment; their pages say how. A pod's `~/.dotfiles` is checked out again at every start, so edit this repo in `~/Repositories/dotfiles` there.

## Everyday use

```sh
mise run diff           # preview what apply would change (dotfile templates are not rendered)
mise run apply          # provision everything, with secrets
mise run upgrade        # the same, with mise, packages and tools upgraded; then commit the lockfiles
mise doctor project     # wiring, config keys, locked-install preview, tasks, file modes
mise run dns:use edge   # (MacBook) resolve the internal zone through the edge cluster
mise run land <pr>      # apply a workflow patch the bot posted on a pull request, and push it as yourself
```

Aliases (`g`, `repo`, `dfa`, ...) are `[shell_alias]` in the configs, set by `mise activate` in zsh, fish and bash alike.

## Secrets

Templates read `{{ vars.x }}` and never name a source. Each var defaults to the process environment, so a value can come from:

| Source | Used by |
| --- | --- |
| `fnox exec` injecting Proton Pass secrets (`fnox.toml`) | every workstation (`mise run apply`) |
| an untracked `config.local.toml` `[vars]` (highest precedence) | a machine that prefers a literal |
| a real env var (the pod's `envFrom`) | the neko container, the pods |

A var with no source renders empty and the templates skip their block, so a partial set still produces valid files. That is also the trap: a dead Proton Pass session would render every secret empty over the good copies, so `apply` checks the session first (`scripts/pass-preflight`) and fnox runs with `--if-missing error`.

Two files are the exception, because an empty value would break them: the Mac's resolver and the collector's config read their values as bootstrap secrets, which abort the run before anything is written. Proton Pass sessions, vaults and grants: [proton-pass](conf.d/proton-pass/README.md).

The kubeconfigs are `~/.kube/main.yaml` and `~/.kube/edge.yaml`, from one Proton Pass item with a field per cluster; `KUBECONFIG` lists both. `~/.kube/config` is deliberately unmanaged and left out, so a stale hand-written file cannot win a context-name collision.

## Validate changes

```sh
python3 tests/test_setup.py -v  # Python 3.11+; isolated homes, nothing here is provisioned
mise doctor project
```

CI runs the same tests on macOS and Linux with the minimum and the latest mise, then loads and renders each of the five classes. A green `test` run on `master` is required before merging a home-ops pin update. It fails on `master` today (HOMEL-121). Commit dependency sidecars (`locks/`) along with `mise*.lock`; `mise lock --global --sidecars` lists them.

## Pages

- [AGENTS.md](AGENTS.md): instructions for agents working on this repo.
- [docs/mise.md](docs/mise.md): how this repo uses mise, what is easy to get wrong, and what was rejected.
- [conf.d/ai](conf.d/ai/README.md): the agents' servers, scopes, keys and skills.
- [conf.d/proton-pass](conf.d/proton-pass/README.md): managed Proton Pass sessions and the vault layout.
- One page per machine, in the table above.

## Inspiration

- https://github.com/onedr0p/dotfiles
- https://github.com/jdx/dotfiles
