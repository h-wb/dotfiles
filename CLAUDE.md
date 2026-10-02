# CLAUDE.md — working in this repo

Dotfiles + full machine provisioning, managed **entirely by mise** (chezmoi is
long gone). Secrets come from **fnox** backed by **Proton Pass**. Three machine
classes share the repo — the MacBook (`personal`), an XFCE desktop in a k8s pod
(`neko`) and a CachyOS KDE gaming desktop (`cachyos`). Read the section for a
machine before touching anything it loads.

## The layout: this repo IS mise's config dir

`~/.config/mise` is a **symlink to `~/.dotfiles`** (made by `scripts/wire`), so
mise reads everything here under its native names — no per-file symlink farm,
and every relative path resolves inside the repo.

| file | loads when |
| --- | --- |
| `config.toml` | always (global config: tools, env, vars, `[shell_alias]`, `apply`/`diff`, doctor) |
| `config.macos.toml` | any Mac — **platform environment** via `auto_env` |
| `config.personal.toml` | machine class `personal` |
| `conf.d/<feature>/mise.<env>.toml` | that env or platform — **folder fragments** |
| `config.local.toml` | always, last (untracked per-machine `[vars]`) |
| `miserc.toml` | early init, committed: `env_conf_d`, `auto_env` |
| `miserc.local.toml` | early init, untracked: `env = ["<class>"]` |

- **Folder fragments** (mise 2026.9.14): a folder in `conf.d/` reads only
  `mise.toml`, `mise.local.toml`, `mise.<env>.toml`, `mise.<env>.local.toml` —
  nothing else, not recursively. Relative sources resolve **inside the folder**,
  and its tasks **run in the folder** (2026.9.15). Each machine class and each
  self-contained feature is one folder: `zsh/`, `macos-defaults/`, `k8s-dns/`,
  `zen-history/`, `neko/`, `cachyos/`.
- **`home/`** holds sources for the root `config*.toml` files only (git, ssh,
  kube, wireguard, BTT). A folder fragment never reaches into `home/`.
- **Platform environments** (`auto_env = true` in `miserc.toml`): `macos`,
  `linux`, `unix`, `<os>-<arch>` are active automatically, below explicit envs
  in precedence. This replaced `os = "macos"` on every brew entry and every
  `variants = [{ os = ... }]` in `[dotfiles]`. `[tools]`/`[bootstrap.packages]`
  still accept `os =` for the odd cross-cutting entry (the neko GUI apps keep it
  so a stray `-E neko` on a Mac fails clean).
- **`min_version = { hard = "2026.9.17" }`** in `config.toml` — global
  `miserc.local.toml` is that release. `conf.d/neko/bin/neko-bootstrap`
  self-updates below it, because `auto_update` skips unattended runs; keep
  its `MIN_MISE` in step.

## Commands

- `mise run apply` — `scripts/pass-preflight`, then
  `fnox --if-missing error exec -c fnox.toml -- mise bootstrap --yes`
  (`--force-dotfiles` added on Linux by a Tera `os()` branch: the distro/image
  writes its own `~/.config/fish/config.fish` first). One task for every
  machine — there are no per-class overrides any more.
- `mise run diff` — the same, `--dry-run`. Note a dry run does **not** render
  dotfile templates (it prints `(if changed)`).
- `mise doctor project` — the `[doctor.checks.*]`: wiring, file modes, lockfile
  checksums, credential perms, plus per-class ones (k8s-dns, neko-hold,
  neko-autostart, gamescope-projector). Fields are `description`/`run`/`hint`
  only. A check's `run` is **not** templated — one that needs `[vars]` calls a
  task (`dns:check`). Add a check whenever you catch a regression by hand.
- `mise lock --global` — refresh lockfiles. Without `--platform` it reuses the
  platforms each lockfile already lists, which is what you want (see Lockfiles).

## Secrets: the silent-overwrite trap

`fnox exec` defaults to `--if-missing warn`: a dead Proton Pass session is a
WARN, fnox exits 0, the bootstrap runs with every secret unset, and the
secret-gated templates render their empty fallback **over the good copies**
(`~/.ssh/config` loses its hosts, `wg0.home.conf` goes to 0 bytes). Hence:

- every fnox call is `fnox --if-missing error exec ...` (a **global** flag,
  before the subcommand);
- `apply`/`diff`/`install.sh` run `scripts/pass-preflight` first (exit 0 = live
  session; `PASS_CLI_PAT` logs in without a TTY; `DOTFILES_NO_LOGIN=1` never
  prompts). `fnox check` does NOT help — it validates config shape only.
- Templates read `{{ vars.x }}`; `config.toml`'s `[vars]` default each to
  `get_env(...)`. **mise's `[env]` does not feed `get_env()`** — that reads the
  real process env — which is why the indirection is `[vars]`.
  `config.local.toml` overrides with literals. On neko a value in the `neko` BWS
  secret arrives via `envFrom` and works the same way. String `[vars]`
  overrides in `config.<env>.toml` work; **boolean** ones do not.

### `[bootstrap.secrets]`: used for k8s-dns, deliberately NOT for the shared templates

A declared secret is resolved **before any mutation**; missing or empty, the
whole bootstrap aborts with nothing written. Only secrets the *selected*
template branch references are resolved (verified 2026-10-01: with `edge`
picked, a missing main IP is fine).

- **Right for `/etc/resolver`** — the only alternative outcome there is a
  resolver with no nameserver, which breaks the zone. (The MacBook always runs
  under fnox anyway.)
- **Wrong for the shared templates**, because the abort is global. On a fresh
  neko PVC with no Proton Pass session, `neko-bootstrap`'s `fresh` mode applies
  dotfiles with no secrets on purpose — that is what gives a new container its
  fish config and autostart entry. Under `secret()` it would get nothing. The
  `secrets`/`fresh`/`protect` modes in `neko-bootstrap` cover that ground more
  precisely; keep them.
- **Never `remove_empty = true` on a secret-gated template**: a dead session
  would then *delete* `~/.ssh/config` instead of blanking it.

## mise behaviour worth knowing (verified, not guessed)

- **Task fields (`dir`, `run`, `env`) are Tera-templated — the whole body,
  comments included.** A malformed `{{ }}` inside a `#` comment fails the task.
  `mise tasks info <task>` validates a body without running it; CI runs it on
  every task.
- **Templated vs literal.** Templated: task fields, dotfile *content*
  (`mode = "template"`), `[bootstrap.files]` content **with `template = true`**,
  launchd agent and systemd unit values, hook commands, `[shell_alias]`.
  Literal: every *key* (so `/etc/resolver/wlab.ovh` is spelled out), dotfile
  `source`, package specs, macOS defaults, doctor `run`.
- **`mise run <task> -- --flag` does not become `$1`** in a multi-line script —
  it is appended to the last line. Pass values through an env var.
- **Same-named hooks accumulate across configs; same-named tasks override.**
- **Hooks fire on a full `mise bootstrap` and with `--only <step>`**, not for
  sub-commands like `mise bootstrap macos defaults apply`.
- **A hook that writes a file the dotfiles step renders is erased by it** — git
  resolves `--global` to the rendered `~/.config/git/config`. Anything that must
  stick goes in the *source template*.
- **Templates can branch on the platform**: `{% if os() == "linux" %}`
  (`os_family()` → `unix`, `arch()` → `x64`).
- **`[dotfiles]` never sudos.** `[bootstrap.files]` (phase 3) is the only way to
  write a root-owned path; keys must be absolute; no `os`/`variants`, so scope
  comes from which config holds it.
- **`permissions = "0600"`** states a dotfile target's mode outright and repairs
  drift (git only records the executable bit, so a source can never be
  committed 0600). Works on template/copy/content, not symlinks. A
  permissions-only entry (no source) never creates the path.
- **`mode = "absent"` removes a file or symlink** — use it when a refactor
  orphans a previously managed target (the old fish aliases link, the old
  rendered resolver).
- **`[vars]` cannot hold nested tables** (`[vars.apps.x]` errors).
- **Bare `mise bootstrap` really bootstraps** — use `--dry-run` to look.
- **`mise env` in a `#!/bin/sh` script needs `--shell bash`**: it honours an
  inherited `MISE_SHELL`, and from fish it emits `set -gx`, on which dash
  *exits* (POSIX special builtin), past any `|| true`.
- **`[shell_alias]` is set by `mise activate`** (zsh, bash, fish), templated,
  merged across configs like everything else — and not available in tasks or
  `mise exec`.
- **`--from` / `--adopt`** were evaluated and are still not used: the
  config-dir model is effectively `--adopt`, but neither writes
  `miserc.local.toml` or detects the class, which is what `scripts/wire` is for.

### Testing a config change without touching the live machine

- Build a sandbox `HOME` whose `.config/mise` symlinks to a copy (or worktree),
  then run **from a directory inside that sandbox**. Run from `~/.dotfiles`
  instead and mise walks up to the real `/Users/hugo/.config/mise` and loads
  your *live* config as a project config on top — results are garbage
  (`not trusted` errors, settings warnings).
- `[bootstrap.files]` entries apply for real even in a "test": probing the
  resolver template applies `/etc/resolver` too unless the entry itself is
  retargeted. CI retargets in place for that reason (runners have passwordless
  sudo).
- Linux checks without the CachyOS box: the neko pod has a stock userland; use
  a temporary mise in `/tmp` and `MISE_CONFIG_DIR=/tmp/<copy>`. Tar from a Mac
  with `COPYFILE_DISABLE=1 tar --no-mac-metadata` or you ship `._*` files.

## Lockfiles

mise writes one lockfile per config *file*, and with the repo as config dir
they all land in the repo: `mise.lock` (config.toml **and** env-less folder
fragments), `mise.macos.lock`, `mise.personal.lock`, `mise.neko.lock`,
`mise.cachyos.lock` (env-scoped files, folder ones included). Lockfile format
is v3 (`mise lock --upgrade`).

- **Scope each env lockfile to the platforms that class runs on.** Locking
  Ludo (an AppImage-only release) for macos-arm64/linux-arm64 made mise pick the
  Decky plugin zip — a different artifact. `mise.macos.lock`/`personal` are
  macos-arm64, `cachyos` linux-x64, `neko` linux-x64 + arm64; `mise.lock` keeps
  them all. A later plain `mise lock --global` preserves each file's set.
- **The checksum check was vacuous until 2026-10-01**: headers are
  `[tools.x."platforms.linux-x64"]` and the check matched `.platforms.`
  (dot-dot), so it inspected nothing. It matches `"platforms.` now — and
  surfaced that **aws-cli has never had Linux checksums**: AWS publishes none
  and `mise lock` does not download, so only a platform that installed it gets
  one. aws-cli is exempted in the check, by name, with that reason.
- `http:` tools are pinned by hand: bump the version and every URL, then lock.

## The MacBook (`personal`) and every Mac (`macos`)

- `config.macos.toml`: Rosetta/Homebrew hook, casks, the Proton Pass ssh-agent
  LaunchAgent (`SSH_AUTH_SOCK` is set here only, so Linux needs no override),
  wireguard, BTT. `config.personal.toml`: MacBook-only packages.
- **A LaunchAgent must find pass-cli itself**: launchd's PATH has no mise shims,
  so the agent resolves it with `$HOME/.local/bin/mise which pass-cli`. Get this
  wrong and every fnox secret fails while the agent looks healthy. mise forces
  the label `dev.mise.<key>` and rejects `Label`/`EnvironmentVariables`/
  `Standard*Path`, so logging is folded into the `sh -c` string.
- **macOS defaults** (`conf.d/macos-defaults/`): the scalar table, plus
  `[[bootstrap.macos.defaults_entries]]` for the rest — `value` takes real TOML
  types, `path` addresses one key inside a shared dict (components are literal;
  dots are not separators), `host = "current"` is `-currentHost`. Those five
  fields are the whole schema. No killall: Raycast/AltTab/BTT would be quit and
  left dead.
- Don't drop `MISE_EXPERIMENTAL` without testing launchd + defaults on a Mac.

### k8s-gateway DNS (`conf.d/k8s-dns/`)

Both clusters run k8s-gateway **authoritative for the same zone** with no
`fallthrough`, so the first to answer returns an authoritative NXDOMAIN for a
route that only exists on the other. **A second nameserver buys nothing** — it
is a switch: `mise run dns:main` / `dns:edge` / `dns:status`.

- The selection is `vars.k8s_dns_cluster`: default `main` < `$K8S_DNS_CLUSTER`
  < `config.local.toml` (written by `dns:select`). Local winning is what makes
  a switch survive `apply`. `dns:select` **unsets** `$K8S_DNS_CLUSTER` before
  re-applying, or a failed write to `config.local.toml` would look like success.
- `/etc/resolver/wlab.ovh` is a `[bootstrap.files]` template over two bootstrap
  secrets (`K8S_GATEWAY_IP_MAIN`/`_EDGE` in fnox — internal IPs, public repo).
  The zone had to be a literal (keys are not templated); `dns:check` asserts it
  matches the var. An unknown cluster falls back to main.
- Flush after a switch (`dscacheutil -flushcache; killall -HUP mDNSResponder`)
  or lookups keep the old answer, which reads exactly like the switch failing.

### Kubeconfigs

`~/.kube/main.yaml` + `~/.kube/edge.yaml` from the `Kubeconfig` item (one field
per cluster); `[env] KUBECONFIG` lists both so kubectl merges them.
`~/.kube/config` is deliberately unmanaged and **not** in the list, so a stale
hand-written file cannot win a context-name collision.

## The neko container (`conf.d/neko/`)

`ghcr.io/m1k1o/neko/xfce` in k8s: Debian trixie, user `neko`, passwordless sudo,
**supervisord as pid 1 — no systemd, no launchd**.

- **Only `/home/neko` is on a PVC.** `/usr` and `/etc` are wiped every pod roll.
  Never mount volumes over them (an empty `/usr` volume leaves no binaries).
  So apt (`[bootstrap.packages]`) is a per-start cost and stays tiny; GUI apps
  are `[tools]` (`~/.local/share/mise` is on the PVC); `chsh` and the timezone
  are re-applied each run.
- **Reprovisioning**: `~/.config/autostart/mise-bootstrap.desktop` →
  `bin/neko-bootstrap` at every XFCE session start (the launchd equivalent;
  `[bootstrap.linux.systemd.units]` is useless without systemd). It wires
  `~/.config/mise`, picks `secrets`/`fresh`/`protect`, runs bootstrap once with
  `--skip-dirty` (one dirty repo must not stop provisioning), logs to
  `~/.local/state/neko-bootstrap.log`, `notify-send`s on failure.
- **`touch ~/.neko-hold` parks it** — survives a pod roll, so a desktop parked
  mid-surgery comes back parked. Doctor flags it.
- **`xfconf-query` needs the session D-Bus** — works from the autostart run,
  no-ops from `kubectl exec`.
- **pass-cli**: the default backend keeps its key in the kernel keyring, which
  this pod's seccomp blocks (`keyctl` EPERM even as root; gnome-keyring does not
  help — different store). `PROTON_PASS_KEY_PROVIDER=fs` keeps it on the PVC;
  a session-start run logs in from `PASS_CLI_PAT`. Never reach for
  `seccompProfile: Unconfined`.
- **GUI apps**: not brew (installs outside the PVC; Linux casks are font-only),
  not apt (wiped), not flatpak (bubblewrap needs a user namespace; a sandboxed
  VS Code cannot see the mise toolchain). `github:` with `extract_all`, or a
  pinned `http:` with a `[platforms]` table (Obsidian: its GitHub "latest" is an
  APK). `ubi:` is deprecated. Menu entries' `Exec` is the mise shim, stable
  across bumps.
- **Not protected**: the PVC is `reclaimPolicy: Delete` under a pruning Flux
  Kustomization; the backstop is kopiur (daily 04:45 to the NAS) — check
  `kubectl get snapshotpolicy -n default neko-desktop -o yaml` before trusting it.

## The CachyOS desktop (`conf.d/cachyos/`)

A real Arch box (`hugo@192.168.18.4`, KDE Plasma, fish, NVIDIA, systemd) — none
of the neko constraints: apps are `pacman:` packages.

- **Scope is "what was added after the installer"**, from `/var/log/pacman.log`
  (install dates are useless: a full `-Syu` on 2026-09-27 reset them). Theme,
  cursor, animation speed and the fish prompt are CachyOS's `/etc/skel`
  defaults — don't re-declare them. `pacman -Qm` lib32 entries are orphans.
- No AUR helper needed (zen-browser-bin, gamescope-session-cachyos are in the
  cachyos repo). RetroDECK is a *system* flatpak; Arch's flatpak ships the
  flathub remote, so the pre-packages hook only ensures flatpak exists.
- **KDE settings are `kwriteconfig6` keys, not dotfiles** — Plasma and Claude
  Code rewrite those rc files and `mimeapps.list` themselves. No D-Bus needed.
- **Projector fix**: a gamescope-session drop-in pinning `OUTPUT_CONNECTOR`, and
  a gamescope Lua display script forcing SDR Rec.709/D65 (the projector's EDID
  claims HDR the 2080 Ti cannot drive at 4K60, and a bogus white point). The
  doctor check catches a session-script update renaming the variable.
- **Decky Loader**: official installer, which cannot be piped to `sh` (`exec
  sudo "$0"`, bash `<<<`) and needs Steam to have run once. The romm-tender
  plugin's settings hold a RomM API token — not managed.
- **sudo needs a password there** — anything touching privileged state
  (firewall plan) needs `ssh -t`.

## Rejected, and why (so nobody re-tries them)

- **`mode = "track"` for dotfiles** — a version-history feature for people
  without a dotfiles repo: no rendering step (would push rendered secrets into
  git history), no `target` variants, and it needs its git remote before
  anything is provisioned. `symlink` + this repo's git already give both halves.
- **An extra env as a per-moment toggle** (e.g. `env = ["personal", "edge"]`
  for DNS): works, but puts a toggle into config *discovery* and `MISE_ENV`
  order is literal last-wins — `["edge", "personal"]` silently picks main.
- **`[bootstrap.secrets]` everywhere** — see Secrets above.

## Don'ts

- Don't add GUI apps to neko with apt — `/usr` is ephemeral.
- Don't change a launchd agent's key expecting a different label — mise forces
  `dev.mise.<key>`.
- Don't commit a source executable unless it is a real script (`install.sh`,
  `scripts/*`, `conf.d/*/bin/*`) — a template takes its source's mode.
- Don't run `chezmoi apply` — chezmoi is gone.
