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
- `mise doctor project` — runs the `[doctor.checks.*]` in `mise.toml` (+
  `mise.neko.toml` on the container). Each check is an invariant this repo has
  broken before: source files committed executable, a lockfile entry with no
  checksum, credential dotfiles that are not 600, `~/.config/mise` not symlinked
  here, a container whose autostart entry is missing or parked on `~/.neko-hold`.
  Fields are `description`/`run`/`hint`; mise rejects any other key. Add one
  whenever you catch a regression by hand.
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
   `mise bootstrap --only dotfiles` DOES run pre/post-dotfiles, which is how the
   permission hook below stays effective without a whole bootstrap.
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
  container runs `mise.toml`'s macOS `pre-packages` hook *and* `mise.neko.toml`'s
  (the first exits on `uname != Darwin`), but `mise.neko.toml`'s `[tasks.bootstrap]`
  fully replaces the shared one.
- **Tasks defined in `conf.d/` fragments do load** and can be `depends`-ed on — but
  only through the global config dir (`~/.config/mise/conf.d`), which is why CI has to
  set up the symlink + miserc to test them.
- **`mise run <task> -- --flag` does NOT become `$1` in a multi-line `run` script** —
  mise appends it to the last line, which is a syntax error. Use an env var instead.
- **`[vars]` cannot hold nested tables.** `[vars.apps.obsidian]` fails with
  "Environment variable 'apps' has no value", so a Tera `{% for %}` over a vars table
  is not a way to drive a task — hence the app catalog being a here-doc table.
- **Bare `mise bootstrap` really bootstraps.** It is not a help/list command; running it
  to "see what it does" converges the machine. Use `--dry-run`.
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

## Dotfile permissions: mise copies the SOURCE's mode

It does **not** render 0755, which this file claimed for a long time. Verified on
2026.9.1 and 2026.9.9: `mode = "template"` gives the target the source file's
permissions, and a later apply *repairs* a changed target mode.

    source 600 → rendered 600      source 644 → rendered 644
    chmod 777 the target, re-apply → back to 600

The real cause of the world-readable `~/.ssh/config` and `wg0.home.conf` was this
repo: `home/ssh/config.tmpl`, `home/wireguard/wg0.home.conf.tmpl` and
`home/git/config.tmpl` were committed **100755**. They are 100644 now, and
`git ls-files -s | awk '$1!="100644"'` should only ever list the four real scripts
(`install.sh`, `scripts/*`, `home/bin/neko-bootstrap`).

`[bootstrap.hooks.post-dotfiles]` in `mise.toml` still chmods the credential
dotfiles to 600 and their directories to 700, and still has to: **git only records
the executable bit**, so a source cannot be committed 600 — a fresh clone gives
644. The hook is what turns 644 into 600. It is a *hook* rather than a line in
`[tasks.bootstrap]` because same-named hooks accumulate across configs, so one copy
covers the Macs and the container; the tasks do not, since `mise.neko.toml`
overrides the shared one. Add any new credential-bearing dotfile to that list.

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
