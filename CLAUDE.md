# CLAUDE.md — working in this repo

macOS dotfiles + full machine provisioning, managed **entirely by mise** (chezmoi
was removed — see git history around `refactor: migrate from chezmoi to full-mise`).
Secrets come from **fnox** backed by **Proton Pass**. Repo lives at `~/.dotfiles`.
Three machine classes share it: the Macs (env `personal`), a neko/xfce container
in k8s (env `neko`) and a CachyOS KDE gaming desktop (env `cachyos`) — see the
neko and CachyOS sections below before touching anything Linux.

## Layout

- `mise.toml` — the config: `[tools]`, `[env]`, `[bootstrap.*]`, `[dotfiles]`, `[tasks]`. Symlinked to `~/.config/mise/config.toml` (so it's the global config too).
- `mise.personal.toml` — env overlay (packages), loaded only when `personal` is an active env.
- `mise.neko.toml` — env overlay for the **neko/xfce container** (Debian trixie, user
  `neko`, fish shell, XFCE). Active env there is `neko`. Companion fragments:
  `conf.d/xfce.neko.toml` (xfconf settings) and `conf.d/neko-apps.neko.toml` (GUI apps).
- `mise.cachyos.toml` — env overlay for the **CachyOS desktop** (Arch, KDE Plasma,
  fish, systemd). Companion fragment: `conf.d/kde.cachyos.toml` (kwriteconfig6
  settings); sources under `home/cachyos/`; lockfile `mise.cachyos.lock`.
- `conf.d/` — fragments merged into the global config: `macos-defaults.toml` + `settings.toml` (always load), `xfce.neko.toml` / `neko-apps.neko.toml` / `k8s-dns.personal.toml` (env-scoped). Symlinked to `~/.config/mise/conf.d`. A fragment can hold **any** section — `[vars]`, `[dotfiles]`, `[bootstrap.*]`, `[tasks]` and `[doctor.checks]` all load from one (verified 2026-09-27), which is what lets a whole feature live in a single file.
- `miserc.toml.example` → per-machine `~/.config/mise/miserc.toml` (untracked): picks active `env` + `env_conf_d`.
- `mise.local.toml` (gitignored) — per-machine values, e.g. `[vars] git_email`.
- `fnox.toml` — Proton Pass secret *references* only (no values). Safe to commit.
- `home/` — dotfile sources: symlinked into `$HOME`, or `*.tmpl` rendered via Tera.
  `home/zsh|zshrc|p10k.zsh` are the Macs' shell; `home/fish/` + `home/starship.toml`
  are the container's. `home/bin/` is symlinked into `~/.local/bin` (neko only).
- `scripts/` — repo tooling, not dotfiles. `pass-preflight` gates every apply on a
  live Proton Pass session (see gotcha #12).
- `install.sh` — fresh-machine bootstrap (Mac or neko container; picks the env from
  `/etc/neko`, override with `DOTFILES_ENV=`); `.github/workflows/test.yml` renders templates in a throwaway HOME.

## Commands

- `mise run apply` — installs everything. Runs `scripts/pass-preflight`, then
  `fnox --if-missing error exec -c fnox.toml -- mise bootstrap --skip files --yes`,
  then `mise run dns:apply`. The two steps are not optional — see the k8s-gateway
  DNS section for why `files` cannot run in its own phase here.
- `mise run diff` — same, `--dry-run` (changes nothing). Unlike `apply` this task is
  NOT overridden in `mise.neko.toml`, so it runs in the container too and must stay
  free of macOS-only tasks and vars.
- `mise doctor project` — runs the `[doctor.checks.*]` in `mise.toml`,
  `conf.d/k8s-dns.personal.toml` and (on the container) `mise.neko.toml`. Each check
  is an invariant this repo has broken before: source files committed executable, a
  lockfile entry with no checksum, credential dotfiles that are not 600,
  `~/.config/mise` not symlinked here, `/etc/resolver` disagreeing with the selected
  cluster, a container whose autostart entry is missing or parked on `~/.neko-hold`.
  Fields are `description`/`run`/`hint`; mise rejects any other key. Add one
  whenever you catch a regression by hand. A check's `run` is **not** templated
  (unlike a task's), so anything needing `[vars]` has to be a task the check calls —
  that is what `dns:check` is.
- Both tasks set `dir = ~/.dotfiles` (see gotcha #3) and both refuse to run without
  secrets (see gotcha #12) — that guard is deliberate, don't drop it to "just apply".
- `mise run dns:main` / `dns:edge` / `dns:status` — pick which cluster resolves the
  internal zone. See the k8s-gateway DNS section below; `dns:apply` is the privileged
  write that `apply` and `install.sh` call after the dotfiles step.

## mise gotchas that WILL bite you (learned the hard way)

1. **launchd agent args are NOT Tera-templated.** `{{env.HOME}}` is passed through
   literally and the agent exits 127. Use shell `$HOME` (program is `/bin/sh -c`;
   launchd sets `HOME`). Applies to `[bootstrap.macos.launchd.agents.*].args`.
2. **`[dotfiles]` `source` paths are NOT templated either**, and they resolve
   **relative to the config file's directory**. Because `mise.toml` is *symlinked*
   into `~/.config/mise/`, a standalone `mise bootstrap` from `$HOME` looks for
   sources under `~/.config/mise/home/...` and fails.
3. **Fix for #2:** run bootstrap **from the repo** so mise loads `~/.dotfiles/mise.toml`
   as the *project* config (sources then resolve to the repo). The `apply`/`diff`
   tasks encode this with `dir = "{{env.HOME}}/.dotfiles"`. `install.sh` already
   `cd`s into the repo. (This is how onedr0p's setup resolves too.)
4. **Task fields (`dir`, `run`) ARE templated** — the asymmetry with #1/#2 is real.
5. **Env selection + `env_conf_d` must live in `~/.config/mise/miserc.toml`** (or the
   `MISE_ENV`/`MISE_ENV_CONF_D` env vars), NOT in `mise.toml` — they drive config
   *discovery*, which happens before `mise.toml` is read. Quirk: `mise settings get
   env_conf_d` prints "not set" even when miserc enables it; the behavior still works
   (verify with `mise config` + which fragments load).
6. **env-scoped conf.d:** with `env_conf_d = true`, `conf.d/<name>.<env>.toml` loads
   only when `<env>` is active; plain `conf.d/<name>.toml` always loads. Dots split
   name from env, so keep multi-word names hyphenated (`macos-defaults.toml`).
7. **`[settings]` is ignored (and warns) when a config is read as project/local.**
   Machine-global settings (e.g. `auto_update`) live in `conf.d/settings.toml`.
8. **`[bootstrap.macos.defaults.*]` is scalar-only — use `defaults_entries` for
   the rest.** Arrays, nested dicts and ByHost values still cannot go in the
   scalar table, but since mise 2026.9.5 they do not need a shell hook either:
   `[[bootstrap.macos.defaults_entries]]` takes `domain`, `key`, `value` (real
   TOML types, `[]` included), `path` (a list of literal keys addressing a nested
   value without replacing its siblings — dots are NOT separators) and
   `host = "current"` (= `defaults -currentHost`). Those five are the whole field
   set; mise rejects anything else as a parse error, which is a cheap way to check
   a spelling. The Dock array, the symbolichotkeys entry and the battery % moved
   there and `[bootstrap.hooks.post-defaults]` is gone. Not verified ON macOS —
   this box is Linux — only that mise accepts the schema; CI's macOS job does not
   apply defaults either.
9. **Hooks fire on a full `mise bootstrap`, and with `--only <step>`.** They do
   NOT fire for the sub-commands (`mise bootstrap macos defaults apply`). So
   `mise bootstrap --only dotfiles` DOES run pre/post-dotfiles. (The permission
   hook that used to rely on this is gone — see the `permissions` section below —
   but the rule still holds for any hook added later.)
10. **A LaunchAgent must set `PATH` before invoking fnox.** fnox shells out to
    `pass-cli`, and launchd's default PATH has no mise shims — get this wrong and
    every secret fails with "CLI tool 'pass-cli' not found" while the agent looks
    perfectly healthy. See the pass-cli-ssh-agent args in `mise.toml`.
11. **Templated dotfiles never name a secret source.** They read `{{ vars.x }}`;
    `mise.toml`'s `[vars]` default each one to `get_env(...)` (the fnox path on
    macOS), and an untracked `mise.local.toml` overrides the same names with
    literals (a machine that prefers a literal; fnox runs in the container too,
    see the secrets section below). Local wins over env.
    **`mise`'s own `[env]` does NOT feed `get_env()`** — that reads the real
    process environment — which is why the indirection is `[vars]`, not `[env]`.
    On the container a third source needs no file: a value in the `neko` BWS
    secret arrives as a real env var through `envFrom` and `get_env()` finds it.
    Because every block is gated on presence, a bare `mise bootstrap` with no
    source at all renders empty rather than erroring. (`[vars]` *boolean*
    overrides via `mise.<env>.toml` still do NOT apply — only `mise.local.toml`.)
12. **`fnox exec` defaults to `--if-missing warn`** — an unresolved secret (expired
    pass-cli session, renamed vault item) is a WARN, fnox exits 0, and the bootstrap
    runs with the secret unset. Combined with #11 that is silent data loss: the
    templates render their empty fallback and OVERWRITE the real files (`~/.ssh/config`
    loses the truenas host; `wg0.home.conf` truncates to 0 bytes). Every fnox call in
    this repo therefore passes **`--if-missing error`** (it is a *global* flag —
    `fnox --if-missing error exec ...`, before the subcommand), and `apply`/`diff` run
    `scripts/pass-preflight` first, which `pass-cli info`s the session and offers a
    `pass-cli login` when stdin is a TTY. `fnox check` does NOT help here — it only
    validates config shape and reports "healthy" with no session at all.

### Why NOT `[bootstrap.secrets]` (evaluated 2026-09-15, rejected)

mise 2026.9.7 added `[bootstrap.secrets]` + `{{ secret(name="x") }}`, which looks
like a drop-in replacement for the `[vars]` + `get_env` indirection in #11 and the
`--if-missing error` guard in #12. It is not, and the reason is worth keeping.

Verified on 2026.9.9:

- A declared secret that is **missing or empty** makes the entry fail to render,
  and mise **does not write the file** — the good copy on disk survives. That part
  is genuinely better than what we have: it protects the file no matter how
  bootstrap was invoked, where `--if-missing error` only covers runs that go
  through fnox.
- But the failure takes down the **whole dotfiles step**. A single unresolved
  secret stopped an unrelated non-secret dotfile from being applied at all.

That second property is fatal here. On a fresh PVC with no Proton Pass session
yet, `home/bin/neko-bootstrap`'s `fresh` mode deliberately applies dotfiles with
no secrets — the templates gate on presence and render their empty fallback — and
that is what gives a new container its fish config, its autostart entry and its
menu entries. Under `[bootstrap.secrets]` that machine would get **no dotfiles at
all** and never finish provisioning.

The three modes in `neko-bootstrap` (`secrets` / `fresh` / `protect`) already
cover the same ground more precisely: they only withhold dotfiles when there is
secret-DERIVED content on disk that a secretless render would blank. Keep them.
If mise ever makes a failed secret skip just its own entry, revisit this.

### Why NOT `mode = "track"` (evaluated 2026-09-24, rejected)

`track` reads like a fifth deployment mode next to `symlink`/`copy`/`template`.
It is not one — it is not even in mise's modes table. It is a **version-history**
feature for people who do *not* have a dotfiles repo:

```toml
[dotfiles]
"~/.zshrc" = { mode = "track" }   # no source
```

The file stays exactly where it is; mise saves **checkpoints into a separate local
Git history repo** (`mise dot save` / `track` / `rollback` / `undo`, or the
`[bootstrap.services.mise-history] builtin = "history-watch"` watcher). Sharing
across machines is a *second* Git remote (`mise dot origin set`, `history.sync`).

It does not replace anything here, for three reasons:

1. **No rendering step.** Half of `[dotfiles]` is `mode = "template"` precisely
   because `~/.ssh/config`, the kubeconfigs and `wg0.home.conf` must differ per
   machine and come from fnox. `track` would sync the *rendered* bytes — i.e.
   push Proton Pass secrets into a git history. (`history` has an `encrypt`
   option; that is still the wrong shape.)
2. **No `variants`.** Tracking variants select separate history *streams* at one
   path and do not accept a `target` override, so they cannot do what
   `variants = [{ os = "macos", target = ... }]` does.
3. **Wrong bootstrap order.** A fresh machine would need the history remote and
   its Git credentials *before* anything is provisioned — the same chicken-and-egg
   the container's `secrets`/`fresh`/`protect` modes exist to avoid.

`symlink` already gives the in-place editing that makes `track` attractive, and
`git log` in this repo already gives the history. `track` entries *can* coexist
with managed ones if some unmanaged file ever wants snapshots; nothing here does.

## The neko/xfce container (env `neko`)

Runs in k8s from `ghcr.io/m1k1o/neko/xfce`: Debian trixie, user `neko` (uid 1000),
passwordless sudo, **supervisord as pid 1 — no systemd, no launchd**, XFCE streamed
over WebRTC.

13. **Only `/home/neko` is on a PVC.** `/usr` and `/etc` are image state and are wiped
    on every pod roll. Never "fix" this by mounting volumes over them: an empty volume
    over `/usr` leaves the container with no binaries, and it pins a stale copy of the
    image. Consequences that shape the config: `[bootstrap.packages]` (apt) is a
    *per-start* cost, so it stays tiny; `[tools]` is free (`~/.local/share/mise` is on
    the PVC); GUI apps are `[tools]` entries under `~/.local/share/mise`, not apt.
14. **`[bootstrap.linux.systemd.units]` is useless there** — mise writes those with
    `systemctl --user`, and there is no systemd. The launchd-agent equivalent is
    `~/.config/autostart/mise-bootstrap.desktop` → `home/bin/neko-bootstrap`, which
    re-runs `mise bootstrap` at every XFCE session start. That is what makes a fresh
    pod reprovision itself.
15. **`xfconf-query` needs a D-Bus session bus.** It works from inside the XFCE session
    (i.e. from the autostart run) but not from a bare `kubectl exec` shell, so
    `tasks."neko:xfce"` detects that and no-ops instead of failing the bootstrap.
16. **`chsh` doesn't stick** (it writes `/etc/passwd`, which resets on every roll). It's
    re-applied each bootstrap for exec shells; the terminal gets fish from
    `home/xfce/terminalrc` (`RunCustomCommand`), which *is* on the PVC.

## The CachyOS desktop (env `cachyos`)

A real Arch machine (`hugo@192.168.18.4`, login shell fish, KDE Plasma, NVIDIA,
systemd) — none of the neko constraints apply: `/usr` persists, so apps are
`pacman:` packages, not `[tools]`. `link-mise-config` picks the env from
`ID=cachyos` in `/etc/os-release`.

- **Scope is "what was added after the installer"**, read from
  `/var/log/pacman.log` (Calamares + cachyos-hello on 2026-04-18, then by hand).
  Package install dates are useless: a full `-Syu` on 2026-09-27 reset them all.
  Theme, cursor, animation speed and the fish prompt are CachyOS's own
  `/etc/skel` defaults (cachyos-kde-settings, cachyos-fish-config) — don't
  re-declare them. `pacman -Qm` lists lib32 AUR orphans; they are not additions.
- **No AUR helper needed** — zen-browser-bin and gamescope-session-cachyos are in
  the cachyos repo. RetroDECK is a *system* flatpak; Arch's flatpak package ships
  the flathub remote, so the pre-packages hook only ensures flatpak exists.
- **KDE settings are `kwriteconfig6` keys, not dotfiles**: Plasma and Claude Code
  rewrite those rc files (and `mimeapps.list`) themselves. kwriteconfig6 needs no
  D-Bus, unlike xfconf-query, so the task works over ssh.
- **The projector fix is two symlinked files** (gamescope-session drop-in pinning
  `OUTPUT_CONNECTOR=HDMI-A-1`, and a gamescope Lua display script forcing SDR
  Rec.709/D65). `doctor.checks.gamescope-projector` catches a session-script
  update that renames the variable. Write-up: `~/gamescope-projector-setup.md`
  on the desktop.
- **Decky Loader comes from its official installer** (in `[tasks.bootstrap]`),
  which cannot be piped to `sh` (it `exec sudo "$0"`s and uses bash `<<<`) and
  needs Steam to have run once. The romm-tender plugin and its settings (RomM API
  token) are deliberately not managed.
- **`sudo` needs a password there**, so anything that inspects privileged state
  (`mise bootstrap plan` → firewall) needs a TTY: `ssh -t`, not a batch ssh.
- `mise.cachyos.toml` overrides `apply` (the shared one calls the Mac-only
  `dns:apply`), `EDITOR` (no VS Code) and `SSH_AUTH_SOCK` (no Proton Pass agent).

## Installing GUI apps in the container (verified, not guessed)

mise's package managers were each checked against this box before settling on
`home/bin/neko-app`:

- **`brew` / `brew-cask`:** brew works on Linux without Homebrew, but installs into
  `/home/linuxbrew/.linuxbrew`, which is *not* the PVC (only `/home/neko` is), so it
  is wiped every roll. And on Linux `brew-cask` is **font-casks only** — every other
  cask type is reported unavailable and skipped. No GUI apps this way, full stop.
- **`apt`:** works, but `/usr` is image state → a fresh 300 MB download per pod start.
- **`flatpak-user`:** considered and rejected. It installs into
  `~/.local/share/flatpak` (on the PVC) and mise drives it declaratively, but: every
  app runs through bubblewrap, which needs an unprivileged **user namespace**
  (`unshare -Ur true` failed under default-seccomp Docker here — suggestive, not
  conclusive for k8s), and a sandboxed VS Code cannot see the mise toolchain in
  `~/.local/share/mise` without `--filesystem` grants and `flatpak-spawn`. On a box
  that exists to use that toolchain, that is a worse trade than one small installer.
  If it is ever revisited: mise "does not install Flatpak or configure remotes
  implicitly", so a pre-packages hook must add the flathub remote *and* install the
  flatpak CLI itself — an `apt:flatpak` entry lands during the packages step that
  already needs it.
- **What is used instead:** plain `[tools]` entries in `conf.d/neko-apps.neko.toml`.
  `github:` with `extract_all` for release archives, `http:` with a `[platforms]`
  table for vendor URLs. mise picks the arch, downloads, extracts, checksums into the
  lockfile and shims the binary onto PATH; installs land in `~/.local/share/mise`,
  which is on the PVC. The XFCE menu entries are static `.desktop` files in
  `home/xfce/applications/`, applied like any other dotfile; their `Exec` points at
  `~/.local/share/mise/shims/<name>`, which is stable across version bumps, so
  upgrading an app never means touching its menu entry. `home/xfce/mimeapps.list`
  sets the default browser declaratively instead of calling `xdg-settings`.
  Two things learned wiring it up: `ubi:` is deprecated in favour of `github:` (gone
  in mise 2027.1.0), and Obsidian cannot use `github:` at all because that repo
  publishes Android APKs as "latest" — the backend then fails with "could not find a
  release asset after filtering for archive files from Obsidian-x.y.z.apk", so it is
  pinned via `http:`. `http:` entries are pinned by hand; bumping is a version and
  two URLs. Give every app entry `os = "linux"`: a stray `MISE_ENV=neko` on a Mac
  otherwise tries to install them and errors on the missing macos platform URL.

## More mise behaviour worth knowing (verified, not guessed)

- **`[dotfiles]` takes no `os` key, but `variants` is the filter** (mise 2026.9.5).
  `[tools]` and `[bootstrap.packages]` take a plain `os =`; `[dotfiles]` entries
  instead carry `variants = [{ os = "macos", target = "..." }]`, where the target
  path moves into the variant. Verified on 2026.9.9: an entry whose selectors all
  fail and which has no `default = true` applies **nothing**, which is what makes
  this a filter and not just a per-OS path map. Selectors are `os` (or os/arch),
  `profile` (the active `MISE_ENV`) and `default`; scoring is profile 2 / os 1 /
  arch 1, highest wins, ties error. This is why `mise.personal.toml` no longer has
  a `[dotfiles]` section — BetterTouchTool and wg0.home.conf were only exiled
  there because the filter did not exist.
- **Same-named hooks ACCUMULATE across configs; same-named tasks OVERRIDE.** The
  container used to run `mise.toml`'s macOS `pre-packages` hook *and*
  `mise.neko.toml`'s `apt-get update` one (the first exits on `uname != Darwin`;
  the second is gone — since 2026.9.15 mise refreshes apt lists itself when an
  install simulation fails, and `mise.neko.toml` now sets `min_version` to match),
  while `mise.neko.toml`'s `[tasks.apply]`
  fully replaces `mise.toml`'s. That override is load-bearing: it is what lets
  `mise.toml`'s `apply` call the Mac-only `dns:apply`. `diff` has no such override,
  so it must stay portable. (`bootstrap` used to be the example here; `mise.toml`
  no longer defines one, so `mise.neko.toml`'s is now the only one in the repo.)
- **`conf.d/` fragments load ONLY through the global config dir**
  (`~/.config/mise/conf.d`) — never from a `conf.d/` sitting next to the project
  config. So tasks in a fragment do load and can be `depends`-ed on, but any CI step
  touching a fragment has to set up `MISE_CONFIG_DIR` + the symlink + a miserc first;
  moving `HOME` is not enough. Getting this wrong is silent: the fragment is simply
  absent and its `[dotfiles]` entries never render (which is how the k8s-dns CI step
  first failed — and why that step now asserts `mise config` lists the fragment
  before testing anything). **Verifying this on a Mac needs a real sandbox**: with
  this repo installed, `~/.config/mise/conf.d` already exists, so an
  `MISE_CONFIG_DIR` override still picked the fragment up from the live config dir
  and the test passed locally while CI failed. Clone into a temp dir with a temp
  `HOME`.
- **`mise run <task> -- --flag` does NOT become `$1` in a multi-line `run` script** —
  mise appends it to the last line, which is a syntax error. Use an env var instead.
- **`[vars]` cannot hold nested tables.** `[vars.apps.obsidian]` fails with
  "Environment variable 'apps' has no value", so a Tera `{% for %}` over a vars table
  is not a way to drive a task — hence the app catalog being a here-doc table.
- **Bare `mise bootstrap` really bootstraps.** It is not a help/list command; running it
  to "see what it does" converges the machine. Use `--dry-run`.
- **`mise env` in a `#!/bin/sh` script needs `--shell bash`** (found 2026-09-20).
  It honours an inherited `MISE_SHELL`, so `neko-bootstrap` run by hand from a
  fish session got `set -gx FOO bar` — and because `set` is a POSIX *special
  builtin*, dash EXITS on the usage error rather than continuing past the
  `|| true`. The script died at the eval with status 2: past the `~/.neko-hold`
  check, before choosing a mode, and without reaching its own `notify-send`, so
  the only evidence was an empty exit code. `--shell bash` emits plain
  `export FOO='bar'`, which dash evals happily. There is no `--shell sh` (values
  are bash/zsh/fish/nu/elvish/xonsh/pwsh). Session-start runs were unaffected —
  `MISE_SHELL` is unset there — which is exactly why it went unnoticed.
- **A hook that writes into a file the dotfiles step renders is erased by it**
  (found 2026-09-20). `[bootstrap.hooks.pre-repos]` in `mise.neko.toml` ran
  `git config --global credential.helper store` at step 10; git resolves
  `--global` to `~/.config/git/config` whenever that file exists, and that is the
  dotfile rendered at step 11 — so the helper was wiped by every bootstrap and
  `~/.git-credentials` sat unused for days, with `git push` failing on a box whose
  `gh` was perfectly logged in. Anything a hook must make stick belongs in the
  *source template*, not in a `git config`/`defaults write` against a managed path.
- **Dotfile templates can branch on the OS: `{% if os() == "linux" %}`** (verified
  2026-09-20 by rendering into a throwaway HOME — `os()` → `linux`, `os_family()`
  → `unix`, `arch()` → `x64`). This is the per-*content* counterpart to `variants`,
  which only picks a target path. `home/git/config.tmpl` uses it to give the
  container `credential.helper = store` without putting plaintext credentials on
  the Macs.
- **`[bootstrap.files]` is the ONLY way mise writes a root-owned path** (verified
  2026-09-27). `[dotfiles]` applies as the invoking user and never sudos, so a
  `/etc/resolver/...` target dies with `Permission denied`. `[bootstrap.files]` is
  bootstrap **phase 3**, keyed by absolute path (a relative one is rejected:
  "managed system path must be absolute"), and the whole field set is `content`,
  `source`, `mode`, `owner`, `group`, `state` — **no `variants` and no `os`**, so
  platform scoping has to come from which config the entry lives in.
- **Neither the `[bootstrap.files]` key NOR its `content` is templated** (verified
  2026-09-27) — a third instance of the gotcha #1/#2 asymmetry. `content =
  "nameserver {{ vars.x }}"` writes those 29 bytes literally. `source` **does**
  accept a `~`-relative path that honours `$HOME`, which is the escape hatch: render
  a normal `[dotfiles]` template and point `source` at it, and secrets stay in fnox.
- **A `[bootstrap.files]` entry with a missing `source` is fatal to the WHOLE
  bootstrap** (verified 2026-09-27: exit 1, and the dotfiles phase *never ran*).
  Since phase 3 precedes the phase-4 dotfiles that render such a source, a fresh
  machine would abort before provisioning anything — the same failure shape that got
  `[bootstrap.secrets]` rejected above. Hence `mise bootstrap --skip files` followed
  by an explicit `mise bootstrap files apply`, in both `[tasks.apply]` and
  `install.sh`.
- **`MISE_ENV` is an additive LIST and env overlays merge last-wins** (verified
  2026-09-27). `MISE_ENV=a,b` loads both overlays, and a same-path
  `[bootstrap.files]` entry or same-named `[vars]` in the later one **overrides**
  the earlier. So a toggle layered on top of a machine class is possible — but
  order is literal, and `["b", "a"]` silently selects `a`'s value. That footgun is
  why the DNS switch is a plain var and not an extra env; see that section.
- **`[vars]` STRING overrides via `mise.<env>.toml` DO work** (verified 2026-09-27),
  which narrows gotcha #11's warning: that caveat is specific to **booleans**.
- **A `[doctor.checks.*]` `run` is NOT templated, but a `[tasks.*]` `run` IS**
  (verified 2026-09-27: a check body received the literal `{{ vars.x }}`). So a
  check that needs a `[vars]` value has to delegate to a task — the check becomes
  one line, `run = "mise run dns:check"`.
- **A task body is templated in full BEFORE any shell sees it — comments included.**
  A `{{ ... }}` inside a `#` comment in a `run` script is still parsed by Tera and a
  malformed one fails the whole task with "invalid task script template" (hit
  2026-09-27 while writing a comment *about* Tera references). `mise tasks info
  <task>` validates a body without running it, which is the cheap way to check.
- **`[doctor.checks]`, `[tasks]`, `[vars]`, `[dotfiles]` and `[bootstrap.*]` all
  load from a `conf.d/` fragment** (verified 2026-09-27), so a whole feature can be
  one env-scoped file instead of being spread across the root configs.
- **`--from` / `--adopt` do NOT replace `install.sh`** (evaluated 2026-09-15).
  `mise bootstrap --from <url>` clones a repo and bootstraps from its config, and
  `--adopt` adopts it as the global config. Neither writes the per-machine
  `miserc.toml` that selects the env (`scripts/link-mise-config` auto-detects
  `neko` from `/etc/neko`), symlinks `conf.d`, or maps `mise.<env>.toml` to the
  `config.<env>.toml` names mise looks for. That wiring is most of what the
  installer does, so it stays.

## Don'ts

- **Don't add GUI apps to the neko container with apt** — /usr is ephemeral, so it is a
  re-download on every pod roll. Add a `[tools]` entry in `mise.neko.toml` (they land
  in `~/.local/share/mise`, on the PVC), or bake a derived image.
- **Never run `chezmoi apply`** — chezmoi is removed and its source layout is dismantled.
- Don't add `MISE_EXPERIMENTAL` removal blindly — `bootstrap` needed it through 2026.8.x.
  (A dotfiles+tools `--dry-run` on 2026.9.9 ran clean without it, but that did not
  exercise launchd or macos-defaults. Test those before dropping it.)
- Don't change a launchd agent's plist name expectations — mise forces `dev.mise.<key>`
  and rejects `Label`/`EnvironmentVariables`/`Standard*Path`.

## Working ON the dotfiles FROM the desktop

The desktop re-runs `mise bootstrap` at every XFCE session start, which is what
makes a rolled pod come back configured — and also means an unfinished edit gets
applied to the machine you are editing from. `touch ~/.neko-hold` makes
`neko-bootstrap` exit before doing anything; remove it to resume. The flag lives
in $HOME, so it survives a pod roll: a desktop parked mid-surgery comes back
parked rather than repairing itself into a broken state.

What is already safe without it: `--skip-dirty` means a repo with uncommitted work
never fails the bootstrap, the git pull is `--ff-only` so local commits are never
clobbered, and a failed bootstrap leaves the session running (it is a separate
process from XFCE) with a notify-send and a log at
`~/.local/state/neko-bootstrap.log`.

What is NOT protected: the PVC has `reclaimPolicy: Delete` and the Flux
Kustomization has `prune: true`, so removing the app from git deletes the volume
and the Ceph image with it. The backstop there is kopiur, which snapshots
/home/neko to the NAS daily at 04:45 — verify with
`kubectl get snapshotpolicy -n default neko-desktop -o yaml` before trusting it.

## The container DOES have secrets, via PROTON_PASS_KEY_PROVIDER=fs

(It did not, once. `mise.neko.toml` now runs `scripts/pass-preflight` and
`fnox --if-missing error` exactly like the Macs — see the `apply` task there and
the `secrets`/`fresh`/`protect` modes in `home/bin/neko-bootstrap`. The section
below is why that took a detour.)

The *default* pass-cli setup does not work in the neko container: it keeps its local
encryption key in the **kernel keyring**, and the container runtime's seccomp
profile blocks `add_key`/`keyctl`/`request_key`. In the pod, `keyctl add user probe
v @u` fails with EPERM **even as root** (`/proc/1/status` → `Seccomp: 2`), so it
dies with `NoStorageAccess(PermissionDenied)` before a login can start.

Two dead ends worth not repeating:

- **gnome-keyring does not help.** It provides the D-Bus Secret Service, a
  *different* store. Installed, the service came up and the default collection
  unlocked (`aliases/default` → `Locked=false`) — and pass-cli failed identically,
  because it never asks the Secret Service anything.
- **`seccompProfile: Unconfined`** on the pod would work, but trades away syscall
  filtering for the whole container.

**The actual escape hatch is `PROTON_PASS_KEY_PROVIDER`** (`fs`, `env` or
`keyring`; fnox's own error message names it). With `PROTON_PASS_KEY_PROVIDER=fs`
the keyring error is gone and pass-cli gets as far as "there is no session" — the
normal not-logged-in state. `env` instead takes the key from
`PROTON_PASS_ENCRYPTION_KEY`, which in k8s could come straight from the BWS secret
via `envFrom`, leaving no key material on the PVC.

That is what the container uses. `PROTON_PASS_KEY_PROVIDER=fs` is set in
`mise.neko.toml`'s `[env]`, which keeps the key beside the session under
`~/.local/share/proton-pass-cli` — on the PVC, so both survive a pod roll. The one
remaining difference from the Macs is how a session *starts*: a session-start
bootstrap has no TTY, so `scripts/pass-preflight` logs in from `PASS_CLI_PAT` (a
Proton Pass Personal Access Token delivered by the k8s secret) instead of
prompting. Never reach for `seccompProfile: Unconfined` to solve this.

`home/bin/neko-bootstrap` is therefore not a straight line — it picks one of three
modes (`secrets` / `fresh` / `protect`) so that a box with no session never renders
secret-derived dotfiles empty over good copies. `[vars]` (gotcha #11) still works
as a third source and still wins over fnox, which is what `mise.local.toml` is for.

## Dotfile permissions: state them with `permissions`, not a chmod hook

Two facts, in order.

**mise copies the SOURCE's mode** (it does *not* render 0755, which this file
claimed for a long time — verified 2026.9.1, 2026.9.9): `mode = "template"` gives
the target the source file's permissions, and a later apply *repairs* a changed
target mode. That is why the world-readable `~/.ssh/config` and `wg0.home.conf`
were this repo's fault, not mise's: `home/ssh/config.tmpl`,
`home/wireguard/wg0.home.conf.tmpl` and `home/git/config.tmpl` were committed
**100755**. They are 100644 now, and `git ls-files -s | awk '$1!="100644"'` should
only ever list the four real scripts (`install.sh`, `scripts/*`,
`home/bin/neko-bootstrap`).

**But a source can never be committed 600** — git only records the executable bit,
so a fresh clone gives 644 and 644 is what the target got. A
`[bootstrap.hooks.post-dotfiles]` chmod loop used to repair that afterwards.

**`permissions` (mise 2026.9.13) replaced the hook.** An octal string on the entry
states the target mode directly, independent of the source:

```toml
"~/.ssh/config" = { source = "home/ssh/config.tmpl", mode = "template", permissions = "0600" }
"~/.ssh"        = { permissions = "0700" }   # permissions-only: no source, no content
```

Verified 2026-09-24 in a throwaway HOME:

    source 644 + permissions "0600" → target 600
    chmod 777 the target, re-apply    → back to 600
    in between, `dotfiles status` says `differs (permissions differ)`

Worth knowing:

- Works on `template`, `copy` and inline `content`. **Not** on `symlink` /
  `symlink-each` (a link has no mode of its own), not on `track`, not on a
  directory source — mise rejects those combinations.
- A **permissions-only** entry (no `source`, no `content`) manages the mode of a
  path that already exists and **never creates it**. A missing target is a WARN,
  and `status` counts it `applied (target absent; permissions not applied)`, so
  `status --missing` does not fail — which is what makes `~/.kube` safe to declare
  in the shared config even though the container has no such directory.
- `variants` works on permissions-only entries too, and a variant that matches
  nothing skips silently (no warning).
- Because these are `[dotfiles]` entries in the shared `mise.toml`, they reach the
  Macs *and* the container — configs merge; only same-named **tasks** override.
  That is why the `chmod 700 ~/.ssh` lines are gone from the hook and from both
  `[tasks.bootstrap]` bodies — one of which, `mise.toml`'s, no longer exists at all.

Add any new credential-bearing dotfile as a `permissions = "0600"` entry, and add
it to `[doctor.checks.credential-perms]`, which still checks the mode on disk.

## k8s-gateway DNS: one zone, two clusters, pick one

Both clusters run `k8s-gateway` **authoritative for the same zone** (`wlab.ovh`),
with no `fallthrough` in either Corefile. So the cluster that answers first
returns an authoritative NXDOMAIN for a route that only exists on the other, and
mDNSResponder stops there. **A second `nameserver` line in `/etc/resolver/<zone>`
buys nothing** — this is a switch, not a merge.

```
mise run dns:edge     mise run dns:main     mise run dns:status
```

**The whole feature is `conf.d/k8s-dns.personal.toml`** — `[vars]`, the
`[dotfiles]` wiring, the `[bootstrap.files]` privileged write, five tasks and the
doctor check — plus `home/k8s-dns/resolver.tmpl` and two `fnox.toml` lines.
`.personal.toml` is the scope, because `/etc/resolver` is macOS-only and
`[bootstrap.files]` accepts no `os` key; the env suffix is the only filter there
is. Things worth knowing:

- **The selection is a var with three sources**, lowest priority first: the
  `"main"` default; `$K8S_DNS_CLUSTER` (ad-hoc, one command, and what CI drives);
  and `[vars]` in the untracked `mise.local.toml`, written by `dns:select`. Local
  outranks both (gotcha #11), which is what makes a switch survive
  `mise run apply` — the old inline resolver step hardcoded one IP and silently
  reverted every switch. An unknown cluster name falls back to main rather than
  rendering empty.
- **`dns:select` unsets `$K8S_DNS_CLUSTER` before re-rendering.** Otherwise the
  render would pick the right IP from the environment even if the write to
  `mise.local.toml` had failed — the switch would look like it worked and then
  revert on the next apply.
- **It is NOT an extra active env.** That was tried and works: `MISE_ENV` is an
  additive list, so `env = ["personal", "edge"]` plus a `mise.edge.toml` overlay
  switches the var. But it puts a per-moment toggle into the file that drives
  config *discovery* (gotcha #5), spreads the feature over three more files, and
  adds a footgun — `["edge", "personal"]` silently selects main, because last-wins
  is literal. A plain var needed none of that.
- **`source = "../home/..."`** on the `[dotfiles]` entry, because a fragment's
  source resolves relative to `~/.config/mise/conf.d` (gotcha #2), not the repo.
  Not a hack: `conf.d` is a symlink into the repo, so the kernel follows it and
  `..` lands on the repo root. A bare `home/...` fails, and `~/...` is not expanded
  for a `[dotfiles]` source at all.
- **Four things cannot be templated, so they are literals that `dns:check`
  asserts**: the `[bootstrap.files]` key and its `source`, checked against
  `vars.k8s_dns_zone` and `vars.k8s_dns_source`. That is why the duplication is
  safe — it cannot drift without failing `mise doctor project`.
- **The zone is public, the IPs are not.** A `[bootstrap.files]` key cannot be
  templated, so `wlab.ovh` had to be committed — but `source` points at a rendered
  template, so both IPs stay fnox secrets (`K8S_GATEWAY_IP_MAIN` / `_EDGE`, two
  fields on the one `k8s gateway` item).
- **`--skip files` then `dns:apply`** — not a style choice. `[bootstrap.files]` is
  phase 3 and the source it reads is rendered by `[dotfiles]` in phase 4, and a
  missing source is fatal to the entire bootstrap, so a fresh Mac would abort
  before provisioning anything. `apply` and `install.sh` both use the two-step;
  `apply` can call the Mac-only `dns:apply` because `mise.neko.toml` overrides that
  whole task.
- **`dns:apply` refuses an empty source** (`[ -s ]`). The template renders 0 bytes
  when the chosen cluster has no IP, and a nameserver-less resolver file would
  break the zone as thoroughly as a wrong IP — the same silent-overwrite rule as
  the rest of this repo, applied to `/etc/resolver`.

Not a `[dotfiles]` entry: mise applies dotfiles as the invoking user and never
sudos, so a `/etc/resolver` target fails with `Permission denied`.

## Kubeconfigs

`~/.kube/main.yaml` + `~/.kube/edge.yaml`, rendered from the `Kubeconfig` item in
the Dev vault (one custom field per cluster), with `[env] KUBECONFIG` listing both
so kubectl merges them — no YAML merging anywhere. `~/.kube/config` is deliberately
left out of that list and unmanaged: keeping the default path out means a stale
hand-written file cannot silently win a context-name collision. Contexts are
`main`, `edge` and `steamdeck`.

## Secrets: the silent-overwrite trap (macOS)

`fnox exec` defaults to `--if-missing warn`: a dead Proton Pass session is only a
WARN, fnox still exits 0, and bootstrap then renders the secret-gated templates
EMPTY over the good copies — `~/.ssh/config` loses its hosts, `wg0.home.conf`
truncates to 0 bytes. Anything that runs bootstrap unattended must therefore:

- gate on `scripts/pass-preflight` (exit 0 = live session; `DOTFILES_NO_LOGIN=1`
  checks without ever prompting), and
- pass `--if-missing error` so a mid-run failure is loud, and
- `--skip dotfiles` on any no-secrets fallback path, never a plain bootstrap.

`install.sh` does the first two. This no longer applies to the neko container,
which has no secret-gated dotfiles at all — see the section above.
