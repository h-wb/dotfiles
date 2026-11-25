---
area: "[[Homelab]]"
categories:
  - "[[Resources]]"
reviewed: 2026-11-24
summary: What every Mac and the MacBook get from this repo, and how their LaunchAgents, defaults, cluster DNS and collector are set up.
topics:
  - "[[Device collector]]"
created: 2026-11-24T20:45
---

# The Macs

`macos` is the platform env, active on any Mac; `personal` is the MacBook's class (layer `workstation` plus `personal`). Five folders hold them:

| Folder | Loads on | Holds |
| --- | --- | --- |
| `conf.d/macos/` | `mise.macos.toml` any Mac, `mise.personal.toml` the MacBook | casks, zsh, the Proton Pass ssh agent, WireGuard; the MacBook's own apps |
| `conf.d/macos-defaults/` | any Mac | `defaults write`, declared |
| `conf.d/macos-k8s-dns/` | the MacBook | which cluster resolves the internal zone |
| `conf.d/macos-miroir-collector/` | the MacBook | the [device collector](https://github.com/h-wb/handbook/blob/main/Systems/Device%20collector.md), hourly |
| `conf.d/ai/mise.personal.toml` | the MacBook | Claude Desktop's tool servers ([ai](../ai/README.md)) |

## Packages

Homebrew itself is not installed: mise installs `brew:` formulae and `brew-cask:` casks into `/opt/homebrew` (formulae on Apple Silicon only), and an existing Homebrew sees and manages them. The `pre-packages` hook adds Rosetta and puts `/opt/homebrew/bin` in `/etc/paths`. Mac App Store apps are `mas:` entries; sign in to the App Store before the first apply.

## LaunchAgents

- mise names every agent `dev.mise.<key>`, whatever the key says.
- launchd's PATH has no mise shims. An agent that needs a tool resolves it with `$HOME/.local/bin/mise which <tool>`, which is why the ssh agent runs under `sh -c`. Get this wrong and every fnox secret fails while the agent looks healthy. An agent that needs no lookup runs mise directly (`miroir-collector`).
- Env and logs are the agent's own `environment`, `stdout_path` and `stderr_path` keys (launchd appends).
- `SSH_AUTH_SOCK` points at the Proton Pass agent's socket here only, so Linux needs no override.

## Login items

`[bootstrap.macos.login_items]` is additive (what an app registered itself stays) and combined across files: every Mac's two sit in `mise.macos.toml`, the MacBook's three in `mise.personal.toml`, next to the casks that install them. List only apps a cask here installs: mise adds the path as written.

## Defaults

`conf.d/macos-defaults/` is the scalar table plus `[[bootstrap.macos.defaults_entries]]` for the rest: `value` takes real TOML types, `path` addresses one key inside a shared dict (components are literal, dots do not separate), `host = "current"` is `-currentHost`. Those five fields are the whole schema. There is no `killall`: Raycast and Switch would be quit and left dead.

## Cluster DNS

Both clusters run k8s-gateway authoritative for the same zone, with no fallthrough: the first to answer returns an authoritative NXDOMAIN for a route that exists only on the other. A second nameserver therefore buys nothing, and the choice is a switch.

```sh
mise run dns:use edge    # or main; dns:main and dns:edge are one-line wrappers
mise run dns:status
dscacheutil -flushcache; sudo killall -HUP mDNSResponder   # after a switch, or lookups keep the old answer
```

- The choice is `vars.k8s_dns_cluster`. Precedence, lowest first: `default = "main"`, the answer `dns:use` saves with `mise vars` (machine state, so it survives `apply`), any config file (`config.local.toml`), a lowercase `k8s_dns_cluster` env var (what the tests drive). `dns:use` reads the value back and fails if a higher source still wins.
- `/etc/resolver/k8s-gateway` is a `[bootstrap.files]` template over three bootstrap secrets: the zone (`SECRET_DOMAIN`) and the two gateway addresses (`K8S_GATEWAY_IP_MAIN`, `K8S_GATEWAY_IP_EDGE`). A missing one aborts the run before anything is written. The file is not named after the zone, because keys are not templated and the domain is never committed: the zone is its `domain` line, which `resolver(5)` reads in place of the name. An unknown cluster falls back to main.
- The tasks and doctor `k8s-dns` read the zone back from the installed file, so none needs a secret. The check also fails when a file named after the zone exists, since it would keep its own nameserver across a switch; the `final` hook removes the one an older layout left.

## The collector

mise installs `miroir-collector` from a pipelines release tag (`collector-vX.Y.Z`) and renders its JSON config at bootstrap, with the server's address built from `SECRET_DOMAIN` as a bootstrap secret. The LaunchAgent runs `mise run --quiet miroir:collect` every hour; that task runs the collector under the folder's own `fnox.toml`, which injects each source's delivery token at run time. A token missing from Proton Pass fails the whole run, so add it before the source. The Mac's default Proton Pass session must be live: the agent never prompts. The program itself: [collector/README.md](https://github.com/h-wb/pipelines/blob/main/collector/README.md).

## Permissions to grant by hand

Apps this repo installs ask on first launch:

- Full Disk Access: Ghostty
- Accessibility: Plexamp, Raycast, Switch
- Screen Recording: ScreenMemory (Switch only for thumbnails, which are off)

(not checked: these depend on the apps' current versions)
