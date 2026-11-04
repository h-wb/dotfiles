# Managed Proton Pass sessions

Dotfiles defines the global `proton-login` mise task template and the
`proton:login` task. All machine classes load them. Repositories extend the
template rather than implementing their own authentication:

```toml
[env]
PROTON_PASS_SESSION_DIR = "{{env.HOME}}/.local/state/pass-cli/home-ops"

[tasks."pass:login"]
extends = "proton-login"
env.PROTON_PASS_LOGIN_SESSION = "home-ops"

[tasks.deploy]
depends = ["pass:login"]
# secrets = [...]  # resolved only when deploy starts, after authentication
run = "..."
```

Run `mise run pass:login` in the repository. To authenticate a named session
from anywhere, use `mise -C ~ run proton:login home-ops`. The explicit home
directory also works with mise 2026.10.19/20, whose monorepo task lookup does
not reliably resolve a global task's bare name; inherited templates work in
both ordinary repositories and monorepos.

The session name selects `$HOME/.local/state/pass-cli/<session>` and, on macOS,
the `pass-cli-<session>` Keychain service for the current user. Linux uses
`PROTON_PASS_TOKEN` from the pod environment. Tokens are never task arguments.
A failed macOS Keychain lookup cannot fall back to a different environment's
token.

The shared implementation fingerprints the selected token, reuses a matching
healthy session, and logs in again on rotation or expiry. Missing or rejected
credentials clear that named session's cache and fail the task. Other sessions
are left alone. Secret-consuming tasks depend on login so the credential is
checked before fnox fetches their grants.

This manages local cached authentication; revoke superseded tokens in Proton
Pass too. Actual token grants define access. Different session directories do
not narrow the grants of a shared token. Legacy untracked session directories
still need the migration cleanup documented in home-ops.

`scripts/pass-preflight` remains the workstation's separate interactive
account-login preflight for dotfiles provisioning. It does not use these
managed agent sessions.

## Paseo rollout order

Before updating an existing Paseo host to this dotfiles revision, install the
read-only `/etc/paseo/scope` inputs in its tools, app and sshd containers and
verify the rolled pod is healthy. The staging change is
[home-ops PR 4758](https://github.com/h-wb/home-ops/pull/4758); it preserves the
existing host's MCP endpoint and credentials. Updating dotfiles first would
fail bootstrap because these required inputs are missing on older pods.

Then update dotfiles and dependent repository tooling. The separate
general/private host rollout replaces the transitional inputs with its own
scope fragments after its credential and provisioning prerequisites are met.

OpenCode's config is rendered through mise's native template mode. Existing
hosts without `PASEO_DATA_SCOPE=general` retain their previous tools; scoped
general gets the corresponding MCP endpoints and runtime environment references.
No credential values are rendered into this file. Bootstrap replaces the old
managed symlink when applying the template.

## Credential naming and ownership

Vault names describe purpose, not the consuming repository:

| Vault | Contents |
| --- | --- |
| `Automation` | Source API credentials, GitHub tool tokens, WireGuard profiles and integration keys |
| `Infrastructure` | Infrastructure connections, SSH keys, kubeconfigs, bootstrap and recovery material |
| Existing personal/Homelab vaults | Human account logins, reused where appropriate |

Machine item names use lowercase kebab-case: `github-workstation`,
`github-pipelines`, `github-sento`, `truenas-ssh`, `kubernetes-gateway`,
`kubeconfig`, `anki-connect`, `anki-mcp`, and `mcp-general-desktop`. Existing
custom field names are preserved. Repositories reference the same canonical
item when they use the same credential. Distinct SSH versus website credentials,
or WireGuard full/split routing profiles, remain distinct items.

The 2026-11-03 migration consolidated the three legacy `env-*` vaults into
`Automation`, `Infrastructure` and the existing human account vaults. The old
vaults have no active items. Runtime BWS/Kubernetes ownership is unchanged;
moving an existing Proton operator copy does not remove its duplication with
the runtime source. Vault access grants must follow the items' new locations.

Routine agent tokens need viewer access only. AI-agent tokens remain read-only
even if their reported vault role is Editor; administrative item organization
requires a regular short-lived PAT with write grants. Never install that
temporary administrative token as a workload's runtime token.

Older checkouts on this host have reference-only `fnox.local.toml` compatibility
overrides. Remove those once their tracked maps include this migration. These
files contain references, not credential values; current code uses the native
fnox/mise paths without a second secret loader.

## Item-scoped general reader

The host-owned Sento configuration selects fnox's `paseo-general` profile when
`PASEO_DATA_SCOPE=general`. The profile contains direct item-share/item-ID
references for the approved general reader; an explicit `FNOX_PROFILE` takes
precedence. Unscoped hosts retain the default named-vault references. Other
repositories declare this selection in their own mise config, so unrelated
projects do not inherit a profile they have not defined. Credentials are still
resolved only for each task's secret grants.

## Readable names with item-only grants

Dotfiles installs `~/.config/fnox/proton-pass-items.lua`, a read-only fnox Lua
provider for readable `Item Title/field` references:

```toml
[providers.protonpass]
type = "lua"
plugin = "~/.config/fnox/proton-pass-items.lua"
options = { vault = "Personal", agent_reason = "obsidian-workspace fnox" }

[secrets]
OBSIDIAN_EMAIL = { provider = "protonpass", value = "Obsidian/email" }
```

On an account with vault access, it searches only the configured vault. If that
vault is invisible to an item-scoped token, it resolves the title only among
explicit Item shares granted to that token. The fallback cannot verify the
containing vault's name, so the token's item grants define its access. Duplicate
titles fail rather than choosing an arbitrary item. Folder shares and other
vaults are never searched as a fallback.

Share/item IDs are discovered from metadata for each batch and remain in memory;
there is no hardcoded ID map or credential cache. Only requested fields are
read. Every CLI operation checks the session first; authentication remains the
global `proton-login` task's responsibility. Missing fields follow fnox's
`if_missing` setting (use `error`). The provider does not write items, change
grants, log credentials or copy raw CLI diagnostics into errors.

Existing repositories using the native `proton-pass` provider are unaffected.
