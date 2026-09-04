# CLAUDE.md — working in this repo

macOS dotfiles + full machine provisioning, managed **entirely by mise** (chezmoi
was removed — see git history around `refactor: migrate from chezmoi to full-mise`).
Secrets come from **fnox** backed by **Proton Pass**. Repo lives at `~/.dotfiles`.

## Layout

- `mise.toml` — the config: `[tools]`, `[env]`, `[bootstrap.*]`, `[dotfiles]`, `[tasks]`. Symlinked to `~/.config/mise/config.toml` (so it's the global config too).
- `mise.personal.toml` — env overlay (packages), loaded only when `personal` is an active env.
- `conf.d/` — fragments merged into the global config: `macos-defaults.toml` + `settings.toml` (always load), `prefect-worker.personal.toml` (env-scoped). Symlinked to `~/.config/mise/conf.d`.
- `miserc.toml.example` → per-machine `~/.config/mise/miserc.toml` (untracked): picks active `env` + `env_conf_d`.
- `mise.local.toml` (gitignored) — per-machine values, e.g. `[vars] git_email`.
- `fnox.toml` — Proton Pass secret *references* only (no values). Safe to commit.
- `home/` — dotfile sources: symlinked into `$HOME`, or `*.tmpl` rendered via Tera.
- `install.sh` — fresh-Mac bootstrap; `.github/workflows/test.yml` renders templates in a throwaway HOME.

## Commands

- `mise run apply` — `fnox exec -c fnox.toml -- mise bootstrap --yes` (installs everything).
- `mise run diff` — same, `--dry-run` (changes nothing).
- Both tasks set `dir = ~/.dotfiles` (see gotcha #3).

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

## Don'ts

- **Never run `chezmoi apply`** — chezmoi is removed and its source layout is dismantled.
- Don't add `MISE_EXPERIMENTAL` removal blindly — `bootstrap` needed it through 2026.8.x.
- Don't change a launchd agent's plist name expectations — mise forces `dev.mise.<key>`
  and rejects `Label`/`EnvironmentVariables`/`Standard*Path`.

## Known open item

`dev.mise.prefect-worker` crash-loops until a **`Prefect` item exists in the Proton
Pass `Dev` vault** (`url` + `password` fields; referenced as `pass://Dev/Prefect/*`
in `fnox.toml`). This is user data, not a config bug.
