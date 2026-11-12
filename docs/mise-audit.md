# mise audit — 2026-10-27

Reviewed the configuration, bootstrap entry points, shell setup, tasks, lockfiles,
and CI against the released mise source and docs through **2026.10.20**.
The installed version is **2026.10.19**. Both versions pass the local regression
suite; the minimum remains .19 because these changes do not require .20.

The existing architecture is a good fit for mise: this checkout is the global
config directory, machine layers select folder fragments, and bootstrap owns
packages, dotfiles and services. Keep using that structure. Native capabilities
take priority over adding scripts that duplicate mise.

## Findings addressed

| Finding | Change |
| --- | --- |
| Bitwarden's generic GitHub backend selected `python-v2.1.0` and locked Python wheels instead of `bws`. | Use the registry's `bitwarden-secrets-manager`, backed by Aqua's `bws-v` release selection. Regenerated all three workstation platform entries. |
| Paseo's Chrome DevTools MCP lock referenced an absent npm dependency sidecar. | Regenerated and included the exact locked sidecar. Its digest matches the existing lock entry. |
| `DOTFILES_ENV=neko` persisted only `neko`, dropping `workstation` and `pod`; other overrides also dropped their layers. | Persist the complete layer list and reject unknown classes before installing or cloning. |
| The installer always required Proton Pass, including for Paseo. Preflight also ran before mise supplied neko's key-provider environment. | Select the fnox path from the loaded workstation config and run its preflight inside `mise exec`. Paseo bootstraps directly. |
| Setup checked for any `mise` on PATH, then invoked a different, hardcoded path. Failed downloads in `curl \| sh` could also look successful. | Check the managed executable actually used by this repo; download the installer successfully before running it. Share the existing minimum-version helper with `install.sh` and propagate failures. |
| Neko could overwrite an edge-only kubeconfig without secrets. Its hold marker did not prevent mise installation or self-update. | Protect either kubeconfig; check the hold before ensuring mise. |
| `apply --dry-run --upgrade` still self-updated mise. | Suppress self-update in preview mode. |
| Paseo's config script swallowed JSON parse errors, could overwrite malformed app state, and rewrote unchanged files. | Native JSON merges: enforce only Claude's `enabled = false`, supply `version = 1` only when missing. Preserve app-owned keys and newer versions. |
| Zsh's completion file cached a spec under a May release name and depended on the old external completion protocol. | Load the completion implementation emitted by the installed mise. Put mise and its shims on PATH before zsh's noninteractive early return. |
| Doctor accepted a symlink to any Git repo. Config and file-mode pipelines could hide command failures. | Compare physical directories and preserve command failures. Use native `mise tasks validate` and `mise install --locked --dry-run` for task and lock checks. |

## Feature review

| Area | Decision and rationale |
| --- | --- |
| [Configuration and folder fragments](https://mise.jdx.dev/configuration.html) | Keep native `config.<env>.toml`, `conf.d/<feature>/mise.<env>.toml` and early `miserc.toml`. They already provide the isolation needed here. |
| [Environment selection](https://mise.jdx.dev/configuration/environments.html) | Keep explicit `auto_env` and `env_conf_d` opt-ins. Whole-list local overrides must include layers. No additional momentary environments for DNS selection. |
| [Variables](https://mise.jdx.dev/configuration/vars.html) | Keep saved `mise vars` for the DNS choice, process-env-backed vars for shared templates, and untracked local overrides. |
| [Tool backends](https://mise.jdx.dev/dev-tools/backends/) | Prefer registry definitions where they encode release selection, as with Bitwarden. Keep explicit custom assets and pinned HTTP tools when release autodetection cannot identify the intended application reliably. |
| [Lockfiles](https://mise.jdx.dev/dev-tools/mise-lock.html) | Keep v3 locks, existing platform scopes, and native npm/uv dependency graphs. Use mise's locked-install preview instead of maintaining a second lock parser. It checks the active platform, not every possible platform. |
| [Release-age policy](https://mise.jdx.dev/configuration/settings.html#minimum_release_age) | Keep mise's built-in release-age policy. Adding another identical setting gives no benefit. Exact pins and already locked versions have different semantics from resolving `latest`. |
| [Task configuration](https://mise.jdx.dev/tasks/task-configuration.html) | Keep sequential `run = [{ task = ... }]` for privileged/bootstrap operations, `skip_if` for state checks, and usage specs for arguments. Native task validation supplements the existing template checks. |
| [Task caching](https://mise.jdx.dev/tasks/task-caching.html) | Provisioning depends on external machine state; file timestamps and cached outputs do not establish that a service, package, or setting remains correct. Do not add task caching here. |
| [Dotfile edits](https://mise.jdx.dev/dotfiles/edits.html) | Adopt `merge = true` and `merge = "missing"` for Paseo. Retain the Claude Desktop hook: merge edits cannot set `permissions`, and this file contains a secret. Its existing atomic write sets mode 0600. |
| [Dotfile groups](https://mise.jdx.dev/dotfiles/groups.html) | Existing feature folders already group a modest number of explicit targets. A second grouping abstraction would add indirection without removing meaningful duplication. |
| [Dotfile history and sync](https://mise.jdx.dev/dotfiles/history.html) | Keep Git as the source history. Tracking rendered credential files introduces a separate history containing secrets; that is not needed for this setup. |
| [Bootstrap resources](https://mise.jdx.dev/bootstrap.html) | Packages, repos, root-owned files, defaults, launchd, systemd and firewall already use native resources. Keep application-specific XFCE/KDE and supervisor steps where native resources do not express the operation. |
| [Login shell and activation](https://mise.jdx.dev/bootstrap/shell.html) | Native activation skips startup files already managed as whole dotfiles. Keep activation in the owned zsh/fish sources. Keep neko's `sudo chsh`: native login-shell application invokes `chsh` directly, which can request a password in this unattended container. |
| [Bootstrap secrets](https://mise.jdx.dev/bootstrap/secrets.html) | Keep required resolver inputs fail-closed. Keep the fresh/protect/secret modes for neko; making every shared template require secrets would prevent provisioning a fresh PVC. |
| [fnox integration](https://mise.jdx.dev/environments/secrets/fnox.html) | Keep explicit `fnox --if-missing error exec` for provisioning. Per-task secret grants are unavailable to global tasks and bootstrap-started tasks; shell-wide secret injection is unnecessary. |
| [Bootstrap planning](https://mise.jdx.dev/cli/bootstrap/plan.html) | Useful for machine-readable resource plans, but excludes dotfiles, tools, hooks, repos, defaults and several other steps. Preserve the full-bootstrap dry-run wrapper. |
| [Bootstrap from a repository](https://mise.jdx.dev/bootstrap/from-repository.html) | 2026.10.21's `--from --config-dir` and 2026.11.0's `--update` match this layout and work (verified 2026-11-08). Keep the `[dotfiles]` self-link entry, the `MISE_CONFIG_DIR` exports and `pull_dotfiles` — see the addendum. |
| [Editor integration](https://mise.jdx.dev/ide-integration.html) | `mise lsp` and the current editor integration are useful for config completion and diagnostics. No need to manage an editor's complete personal settings just to enable this. |
| Remote bootstrap, modules, Compose, OCI, daemons and monorepo tasks | Available for different workloads. The existing host provisioning, Kubernetes-managed pods, supervisor and systemd ownership do not need another deployment or process-management layer. |

## Releases that matter here

- [2026.10.20](https://github.com/jdx/mise/releases/tag/v2026.10.20): fixes
  sidecar placement for symlinked config directories and respects tool OS filters
  when locking. Adds release-tag regex filters, existing systemd user-service
  management, launchd events, and optional Homebrew cask metadata. The latter
  features do not solve an additional requirement in this repo today.
- [2026.10.19](https://github.com/jdx/mise/releases/tag/v2026.10.19): already
  required for `mise_config_dir`; also includes substantial trust, archive,
  checksum and provenance hardening.
- [2026.10.18](https://github.com/jdx/mise/releases/tag/v2026.10.18) and
  [2026.10.17](https://github.com/jdx/mise/releases/tag/v2026.10.17): native LSP,
  doctor dependencies/templates and login-shell name resolution.
- Earlier September/October changes already in use include folder fragments,
  platform environments, permissions, bootstrap upgrades, saved variables and
  state-based task guards. JSON merges were the useful unused native feature.

Updating the installed mise to .20 is worthwhile with `mise self-update`.
No application upgrades or live bootstrap were performed by this audit.
When .20 rewrites a lockfile it may relocate older `locks/` sidecars beneath
`.mise/locks/`, based on this checkout's physical path; commit its generated
paths together with the lockfile.

## Validation and limits

`python3 tests/test_setup.py -v` uses isolated homes, offline mise commands,
and fake provisioning executables. It covers class loading and task rendering,
installer routing, early failures, neko protection, native JSON merge behavior,
native sidecar validation, diagnostic failures, preview behavior and zsh.
Both 2026.10.19 and 2026.10.20 pass locally on macOS.

CI runs the regressions on macOS and Linux with the minimum and latest mise,
plus the existing machine matrix's dotfile/resolver checks. Native lock preview
of PyPI graphs needs an installed interpreter, so that matrix installs locked
Python and uv before doctor. Linux CI and actual pod/system provisioning were
not executed locally; package installation, PAM, launchd, systemd and desktop
session behavior still require their respective hosts.

## Addendum: bootstrap from a checkout (2026-11-08)

[#15025](https://github.com/jdx/mise/pull/15025) shipped as
[`bootstrap --from --config-dir`](https://mise.jdx.dev/bootstrap/from-repository.html)
in [2026.10.21](https://github.com/jdx/mise/releases/tag/v2026.10.21), and
`bootstrap --update` fast-forwarding a linked checkout in
[2026.11.0](https://github.com/jdx/mise/releases/tag/v2026.11.0): mise's native
version of what `install.sh`, `neko-bootstrap` and `paseo-bootstrap` hand-roll.
Checked against a sandbox clone of this repo (mise 2026.11.4):

- `mise bootstrap --from <url> --from-dir ~/.dotfiles --config-dir . --only
  dotfiles` clones to `~/.dotfiles`, links `~/.config/mise` to the checkout,
  and reads `config.toml`, `config.<env>.toml`, `conf.d/` and `miserc.toml` as
  global config in that same run — `.` is the checkout itself, so this flat
  layout needs no restructuring. Re-runs reuse the existing checkout and
  accept the link they already made; a reused dirty checkout does not block
  (without `--update`); a non-empty `~/.config/mise` is refused and left alone.
- Not adopted. `--config-dir` requires `--from`, so flag-free runs cannot
  maintain the link and the first `[dotfiles]` entry stays the maintainer.
  `install.sh` needs the checkout *before* bootstrap can run — the min_version
  gate, `miserc.local.toml`, pass-preflight and the workstation detection that
  wraps bootstrap in fnox — so mise cannot own the clone there. And
  `bootstrap --update` aborts the whole run when the fast-forward hits local
  changes (`could not fast-forward the global config`), where `pull_dotfiles`
  warns and continues and re-executes a changed script; the pods need that
  tolerance. A two-phase bootstrap (wire with `--config-dir`, then wrap) costs
  more than the one-line `MISE_CONFIG_DIR` export.
- The changelog's `mise dot track ~/.config/mise` recommendation is
  `mode = "track"` again, at directory scale — a second history over the git
  checkout that already is the config. Stays rejected.

If the config ever moves under `.config/mise/` inside the checkout, this
flips: `install.sh` would adopt the flags, drop its manual clone and the
`MISE_CONFIG_DIR` export, and `.local.toml` files stay per-machine unchanged.

## Addendum: release review, 2026.10.21 → 2026.11.4 (2026-11-08)

Re-read every release since the first addendum (checked against sandbox clones
of this repo on mise 2026.11.4) and adopted what pays for itself:

- **`[env_sets]` in `miserc.toml` (2026.11.1).** Each machine class is one
  name, and `miserc.local.toml` (`install.sh`, CI) records the class — the
  layer list is defined once in the shared miserc instead of being copied into
  the installer, the workflow matrix and the tests, and `mise -E neko` selects
  a whole machine. Requires `min_version` 2026.11.1: an older mise loads a
  pinned class on its own and silently drops its layers. Verified that a set
  named like the class (`neko = ["workstation", "neko"]`) expands, one-level
  expansion handles `paseo = ["paseo"]`, and auto-detected machines are
  unaffected. `paseo-overlay` stays `/etc`-detected and in no set.
- **Sidecars are back at `locks/` (2026.10.23).** The `.mise/locks/` layout was
  the 2026.10.20–.22 window: misinformed by .20, the repo had committed
  sidecars twice (one paseo graph under `.mise/locks/`) and defended itself with
  `git checkout -- mise*.lock` after every bootstrap, because mise normalised
  committed `locks/` pointers to `.mise/locks/`. 2026.10.23+ resolves both the
  link and `MISE_CONFIG_DIR` forms to `locks/`, so the paseo graph moved there,
  the pointer in `mise.paseo.lock` now matches what every current mise
  computes, and the restore steps are gone from `install.sh` and
  `neko-bootstrap`. Nothing normalises the lockfiles dirty any more (verified:
  re-locking the same request against a `locks/`-shaped file rewrites no
  content; only the pointer's stale shape used to).
- **Worth knowing, not adopted now:** task `lock` (2026.11.0) would serialise
  same-named Proton sessions on a multi-agent pod; merge entries can set
  `permissions` on creation (2026.10.22); `--output summary` and
  `mise tasks history` (2026.11.3) exist for pod provisioning logs. 2026.11.1
  verifies npm provenance by default (packages that publish none install as
  before) and warns that lockfiles are format version 3 — converting is
  `mise lock --upgrade`, i.e. the next `mise run upgrade`, and every machine
  must be ≥ 2026.11.1 to read v4, which `min_version` now guarantees.
- **Fixed by the upgrade itself:** the cachyos `home-lan` firewall rule
  (source CIDR, no port) never converged — 2026.11.4 fixes ufw CIDR matching;
  backends load config again when the config dir is its own git checkout
  (2026.11.0); tool completion through shims works (2026.11.4).
- **Coming with the next `mise run upgrade`:** `node = "lts"` moves from 24 to
  26 (2026.10.22); the lockfile rewrite will also move to format version 4.

## Addendum: conf.d layout, and releases 2026.11.5 → 2026.11.7 (2026-11-11)

**Layout.** `conf.d` held three kinds of folder with nothing to tell them
apart: machines (`neko`), features of one machine (`anki`, `k8s-dns`) and
features of every machine (`ai`). The Mac was the odd one out, split between
two root files, `home/` and five folders. Now every machine is a folder named
like its environment, a feature only that machine has is `<machine>-<feature>`,
and a folder with no machine in its name loads on several; the root keeps the
two shared layers. `conf.d` cannot nest (mise reads one level) and `include`
carries no `[dotfiles]`, `[tasks]` or `[settings]`, so the name is the only
native place to put the grouping. Dotfile groups stay unused: they group files
by directory tree, not config by machine.

The same pass removed the LM Studio folder (unused) and moved the two
Paseo-only skills from `conf.d/ai` to `conf.d/paseo`. The resolver file is now
`/etc/resolver/k8s-gateway`, with the zone as its `domain` line: a bootstrap
secret, like the nameserver.

**Adopted** (all at or below `min_version`, checked in sandbox homes):

- LaunchAgent `environment`, `stdout_path` and `stderr_path`. The claim that
  mise rejects them was out of date; the ssh agent keeps `sh -c` only for
  `$(mise which pass-cli)`, and the Zen snapshot runs mise with no shell.
- `[bootstrap.macos.login_items]` for the apps that are login items today and
  that a cask here installs. Additive, and a no-op on the current MacBook.
- Task `lock` on the `proton-login` template (2026.11.0). Extending tasks
  inherit it, so logins on a multi-agent pod take turns.
- Hook `description` (2026.10.22) on the bootstrap hooks.

**Not adopted:**

- `mode = "fnox"` (2026.10.23) for the kubeconfigs and WireGuard. fnox keeps
  such files under `[files]` in its *global* config, keyed by target path, and
  `conf.d/ai` keeps no global fnox config on purpose. The values are also
  Proton Pass fields that other consumers read. Worth another look if the
  whole-file secrets ever move out of `[vars]`: it is the native answer to the
  silent-overwrite trap for those three files, not for `~/.ssh/config` or git.
- Unprefixed `[bootstrap.packages]` keys (2026.11.6): each class has one
  package manager and its own file, so the prefix costs nothing.
- `bootstrap --save-env` (2026.11.1): `install.sh` needs `miserc.local.toml`
  before its first `mise config`, earlier than bootstrap runs.
- The Claude Code `SessionStart` hook from the new "Coding agents" page
  (`eval "$(mise hook-env -s bash)"` into `$CLAUDE_ENV_FILE`): it gives an
  agent's shell a project's `[env]`, where shims only give it to the tool they
  launch. A change to every agent session on every machine, so left as a
  decision; it would be a merge entry in `conf.d/ai`.
- `shims.fallback_to_installed`, `mise run --multi`, task tags, history and
  logs, launchd resource limits, the named `[bootstrap.macos.dock]`/`finder`
  sections: nothing here needs them.

**Free with the upgrade:** 2026.11.7 drops the new-version notice and hints
when it detects a coding agent, and 2026.11.6 changes the prompt theme to
`base16`.
