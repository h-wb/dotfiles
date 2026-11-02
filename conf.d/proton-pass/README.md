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
