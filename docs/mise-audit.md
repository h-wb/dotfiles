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
