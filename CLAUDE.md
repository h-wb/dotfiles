# CLAUDE.md — working in this repo

macOS dotfiles + full machine provisioning, managed **entirely by mise** (chezmoi
was removed — see git history around `refactor: migrate from chezmoi to full-mise`).
Secrets come from **fnox** backed by **Proton Pass**. Repo lives at `~/.dotfiles`.
Two machine classes share it: the Macs (env `personal`) and a neko/xfce container
in k8s (env `neko`) — see the neko section below before touching anything Linux.

## Layout

- `mise.toml` — the config: `[tools]`, `[env]`, `[bootstrap.*]`, `[dotfiles]`, `[tasks]`. Symlinked to `~/.config/mise/config.toml` (so it's the global config too).
- `mise.personal.toml` — env overlay (packages), loaded only when `personal` is an active env.
- `mise.neko.toml` — env overlay for the **neko/xfce container** (Debian trixie, user
  `neko`, fish shell, XFCE). Active env there is `neko`. Companion fragments:
  `conf.d/xfce.neko.toml` (xfconf settings) and `conf.d/neko-apps.neko.toml` (GUI apps).
- `conf.d/` — fragments merged into the global config: `macos-defaults.toml` + `settings.toml` (always load), `xfce.neko.toml` / `neko-apps.neko.toml` (env-scoped). Symlinked to `~/.config/mise/conf.d`.
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
  `fnox --if-missing error exec -c fnox.toml -- mise bootstrap --yes`.
- `mise run diff` — same, `--dry-run` (changes nothing).
- Both tasks set `dir = ~/.dotfiles` (see gotcha #3) and both refuse to run without
  secrets (see gotcha #12) — that guard is deliberate, don't drop it to "just apply".

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
8. **macOS `defaults` are scalar-only.** Arrays / nested dicts / ByHost values can't
   be expressed in `[bootstrap.macos.defaults.*]`; they live in the
   `[bootstrap.hooks.post-defaults]` shell hook (Dock array, symbolichotkeys, battery %).
9. **Hooks fire on a full `mise bootstrap`, and with `--only <step>`.** They do
   NOT fire for the sub-commands (`mise bootstrap macos defaults apply`). So
   `mise bootstrap --only dotfiles` DOES run pre/post-dotfiles, which is how the
   permission hook below stays effective without a whole bootstrap.
10. **A LaunchAgent must set `PATH` before invoking fnox.** fnox shells out to
    `pass-cli`, and launchd's default PATH has no mise shims — get this wrong and
    every secret fails with "CLI tool 'pass-cli' not found" while the agent looks
    perfectly healthy. See the pass-cli-ssh-agent args in `mise.toml`.
11. **Templated dotfiles never name a secret source.** They read `{{ vars.x }}`;
    `mise.toml`'s `[vars]` default each one to `get_env(...)` (the fnox path on
    macOS), and an untracked `mise.local.toml` overrides the same names with
    literals (the neko path, since fnox cannot run there). Local wins over env.
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
    `scripts/pass-preflight` first, which `pass-cli test`s the session and offers a
    `pass-cli login` when stdin is a TTY. `fnox check` does NOT help here — it only
    validates config shape and reports "healthy" with no session at all.

## The neko/xfce container (env `neko`)

Runs in k8s from `ghcr.io/m1k1o/neko/xfce`: Debian trixie, user `neko` (uid 1000),
passwordless sudo, **supervisord as pid 1 — no systemd, no launchd**, XFCE streamed
over WebRTC.

13. **Only `/home/neko` is on a PVC.** `/usr` and `/etc` are image state and are wiped
    on every pod roll. Never "fix" this by mounting volumes over them: an empty volume
    over `/usr` leaves the container with no binaries, and it pins a stale copy of the
    image. Consequences that shape the config: `[bootstrap.packages]` (apt) is a
    *per-start* cost, so it stays tiny; `[tools]` is free (`~/.local/share/mise` is on
    the PVC); GUI apps are `~/.local/opt` tarballs, not apt.
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

- **`os` filters exist for `[tools]` and `[bootstrap.packages]`, but NOT `[dotfiles]`.**
  That's why the shared `mise.toml` tags every cask `os = "macos"`, while the
  macOS-only BetterTouchTool *dotfile* had to move into `mise.personal.toml`.
- **Same-named hooks ACCUMULATE across configs; same-named tasks OVERRIDE.** The
  container runs `mise.toml`'s macOS `pre-packages` hook *and* `mise.neko.toml`'s
  (the first exits on `uname != Darwin`), but `mise.neko.toml`'s `[tasks.bootstrap]`
  fully replaces the shared one.
- **Tasks defined in `conf.d/` fragments do load** and can be `depends`-ed on — but
  only through the global config dir (`~/.config/mise/conf.d`), which is why CI has to
  set up the symlink + miserc to test them.
- **`mise run <task> -- --flag` does NOT become `$1` in a multi-line `run` script** —
  mise appends it to the last line, which is a syntax error. Use an env var instead
  (`NEKO_APPS_UPGRADE=1 mise run neko:apps`).
- **`[vars]` cannot hold nested tables.** `[vars.apps.obsidian]` fails with
  "Environment variable 'apps' has no value", so a Tera `{% for %}` over a vars table
  is not a way to drive a task — hence the app catalog being a here-doc table.
- **Bare `mise bootstrap` really bootstraps.** It is not a help/list command; running it
  to "see what it does" converges the machine. Use `--dry-run`.

## Don'ts

- **Don't add GUI apps to the neko container with apt** — /usr is ephemeral, so it is a
  re-download on every pod roll. Tarball into `~/.local/opt` (see
  `conf.d/neko-apps.neko.toml`), or bake a derived image.
- **Never run `chezmoi apply`** — chezmoi is removed and its source layout is dismantled.
- Don't add `MISE_EXPERIMENTAL` removal blindly — `bootstrap` needed it through 2026.8.x.
- Don't change a launchd agent's plist name expectations — mise forces `dev.mise.<key>`
  and rejects `Label`/`EnvironmentVariables`/`Standard*Path`.

## The container has no secrets — by choice, not because it cannot

The default pass-cli setup does not work in the neko container: it keeps its local
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

So secrets in the container are **possible**; we simply chose not to. The
container has nothing that needs them: `~/.ssh/config` gets its values through
`[vars]` (gotcha #11) from `mise.local.toml` or a plain env var, and `wg0.home.conf`
is macOS-only. That choice is what keeps `home/bin/neko-bootstrap` a straight line
instead of an fnox/preflight/fallback ladder. If that changes, wire up
`PROTON_PASS_KEY_PROVIDER=fs` plus a one-time `pass-cli login` (the session dir
lives on the PVC) rather than reaching for Unconfined seccomp.

## mise renders dotfiles 0755

Which is wrong for anything holding credentials — a kubeconfig embeds client certs,
and `~/.ssh/config` and `wg0.home.conf` were world-readable and executable for
months. `[dotfiles]` has no permission field, so `[bootstrap.hooks.post-dotfiles]`
in `mise.toml` chmods them to 600 (and their directories to 700). It is a *hook*
rather than a line in `[tasks.bootstrap]` because same-named hooks accumulate
across configs, so one copy covers the Macs and the container; the tasks do not,
since `mise.neko.toml` overrides the shared one. Add any new credential-bearing
dotfile to that list.

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
