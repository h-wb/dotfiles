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
- `conf.d/` — fragments merged into the global config: `macos-defaults.toml` + `settings.toml` (always load), `prefect-worker.personal.toml` (env-scoped). Symlinked to `~/.config/mise/conf.d`.
- `miserc.toml.example` → per-machine `~/.config/mise/miserc.toml` (untracked): picks active `env` + `env_conf_d`.
- `mise.local.toml` (gitignored) — per-machine values, e.g. `[vars] git_email`.
- `fnox.toml` — Proton Pass secret *references* only (no values). Safe to commit.
- `home/` — dotfile sources: symlinked into `$HOME`, or `*.tmpl` rendered via Tera.
  `home/zsh|zshrc|p10k.zsh` are the Macs' shell; `home/fish/` + `home/starship.toml`
  are the container's. `home/bin/` is symlinked into `~/.local/bin` (neko only).
- `scripts/` — repo tooling, not dotfiles. `pass-preflight` gates every apply on a
  live Proton Pass session (see gotcha #11).
- `install.sh` — fresh-machine bootstrap (Mac or neko container; picks the env from
  `/etc/neko`, override with `DOTFILES_ENV=`); `.github/workflows/test.yml` renders templates in a throwaway HOME.

## Commands

- `mise run apply` — installs everything. Runs `scripts/pass-preflight`, then
  `fnox --if-missing error exec -c fnox.toml -- mise bootstrap --yes`.
- `mise run diff` — same, `--dry-run` (changes nothing).
- Both tasks set `dir = ~/.dotfiles` (see gotcha #3) and both refuse to run without
  secrets (see gotcha #11) — that guard is deliberate, don't drop it to "just apply".

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
9. **Hooks fire only on a full `mise bootstrap`.** Sub-commands like
   `mise bootstrap macos defaults apply` do NOT run pre/post hooks.
10. **Secrets:** templated dotfiles read secrets via `get_env(name="X", default="")`
    and gate blocks on presence, so bare `mise bootstrap` (no fnox) renders empty and
    doesn't error. `[vars]` boolean overrides via `mise.<env>.toml` do NOT apply.
11. **`fnox exec` defaults to `--if-missing warn`** — an unresolved secret (expired
    pass-cli session, renamed vault item) is a WARN, fnox exits 0, and the bootstrap
    runs with the secret unset. Combined with #10 that is silent data loss: the
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

12. **Only `/home/neko` is on a PVC.** `/usr` and `/etc` are image state and are wiped
    on every pod roll. Never "fix" this by mounting volumes over them: an empty volume
    over `/usr` leaves the container with no binaries, and it pins a stale copy of the
    image. Consequences that shape the config: `[bootstrap.packages]` (apt) is a
    *per-start* cost, so it stays tiny; `[tools]` is free (`~/.local/share/mise` is on
    the PVC); GUI apps are `~/.local/opt` tarballs, not apt.
13. **`[bootstrap.linux.systemd.units]` is useless there** — mise writes those with
    `systemctl --user`, and there is no systemd. The launchd-agent equivalent is
    `~/.config/autostart/mise-bootstrap.desktop` → `home/bin/neko-bootstrap`, which
    re-runs `mise bootstrap` at every XFCE session start. That is what makes a fresh
    pod reprovision itself.
14. **`xfconf-query` needs a D-Bus session bus.** It works from inside the XFCE session
    (i.e. from the autostart run) but not from a bare `kubectl exec` shell, so
    `tasks."neko:xfce"` detects that and no-ops instead of failing the bootstrap.
15. **`chsh` doesn't stick** (it writes `/etc/passwd`, which resets on every roll). It's
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
- **`flatpak-user`:** the real alternative, and mise drives it declaratively. Installs
  into `~/.local/share/flatpak` (on the PVC), but every app runs through bubblewrap,
  which needs an unprivileged **user namespace**. Verify in the pod with
  `unshare -Ur true` before betting on it; it failed under a default-seccomp Docker
  container here, which is suggestive but NOT conclusive for k8s. Ready-to-enable
  config in `conf.d/neko-flatpak.neko.toml.example`. Note mise "does not install
  Flatpak or configure remotes implicitly" — the flathub remote must be added by a
  pre-packages hook, and that hook must install the flatpak CLI itself, since the
  `apt:flatpak` entry only lands during the packages step that needs it.
- **What is used instead:** `home/bin/neko-app` unpacks tarballs / AppImages / .debs
  into `~/.local/opt` — no privileges at all — and writes the .desktop entry, icon and
  `~/.local/bin` symlink. The catalog is a table in `conf.d/neko-apps.neko.toml`; one
  line per app. It records the *resolved* download URL, so a new upstream release
  changes the URL and the app reinstalls itself on the next bootstrap.
  AppImages are extracted, never mounted: there is no `/dev/fuse` in the pod.

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

## Prefect worker (fixed, then disabled 2026-09-05)

`conf.d/prefect-worker.personal.toml` is commented out: paperless-gpt reaches LM
Studio directly over the WireGuard tunnel, so nothing needs a local worker. The
debugging below is kept because the fragment is still there to re-enable, and
because two of the three findings are not Prefect-specific.

It had been crash-looping ~25,800 times. The note that used to live here —
"waiting on a `Prefect` item in the Proton Pass `Dev` vault" — was wrong: the item
exists and fnox resolves it. Three real causes, all now fixed and verified working
(the worker did start and create its pool) before it was switched off:

1. **prefect 3.6.7 ships a broken dependency list.** `prefect/workers/base.py`
   imports `importlib_metadata` unconditionally, but the wheel declares no
   `Requires-Dist` for it, so uv never installed it and every start died at import.
   The final hook installs it explicitly, checked separately from venv creation so
   an existing venv gets it too. Drop that when upstream fixes the metadata.
2. **`PREFECT_API_URL` is the site root, not the API root.** Prefect's client wants
   `.../api`; without it requests hit the UI, get 302'd into the Kanidm/oauth2-proxy
   login flow, and the worker dies parsing an HTML login page as JSON
   (`JSONDecodeError: Expecting value: line 1 column 1`). `home/bin/prefect-worker-start`
   appends `/api` when missing, so the stored secret can hold either form.
   The SSO is already scoped correctly cluster-side — `/api/*` is exempt from
   oauth2-proxy (`/api/health` → `200 true`), only the UI sits behind Kanidm. A 401
   on `/api/*` is Prefect's own auth, satisfied by `PREFECT_API_AUTH_STRING`.
3. **The `macbook-pool` work pool did not exist** (404) and the worker ran without
   `--type`, so it exited instead of creating it. The start script passes
   `--type process`, which creates the pool on first run.

**Gotcha that outlives this service:** a LaunchAgent must set `PATH` *before*
invoking fnox. fnox shells out to `pass-cli`, and launchd's default PATH has no
mise shims — get it wrong and every secret fails with "CLI tool 'pass-cli' not
found" while the agent looks healthy. Same shape as the pass-cli-ssh-agent.

## Secrets: the silent-overwrite trap

`fnox exec` defaults to `--if-missing warn`: a dead Proton Pass session is only a
WARN, fnox still exits 0, and bootstrap then renders the secret-gated templates
EMPTY over the good copies — `~/.ssh/config` loses its hosts, `wg0.home.conf`
truncates to 0 bytes. Anything that runs bootstrap unattended must therefore:

- gate on `scripts/pass-preflight` (exit 0 = live session; `DOTFILES_NO_LOGIN=1`
  checks without ever prompting), and
- pass `--if-missing error` so a mid-run failure is loud, and
- `--skip dotfiles` on any no-secrets fallback path, never a plain bootstrap.

`home/bin/neko-bootstrap` does all three; that is the pattern to copy.
