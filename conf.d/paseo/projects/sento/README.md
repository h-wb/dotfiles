# Sento on the Paseo host

These files supply the maintainer's private service URLs and Proton Pass
references. The public Sento repository does not own them.

The Paseo dotfiles profile copies them to `~/Repositories/sento/`. Sento's
worktree setup copies these ignored files from `PASEO_SOURCE_CHECKOUT_PATH`
before running mise, so new and nested worktrees inherit the integration.
Existing files are preserved. The backend watcher receives only qBittorrent
and Prowlarr secrets, scoped to its task; the rest of the shell and the offline
harness receive no resolved credentials. The host's `paseo:pass-login` task
owns authentication, using the token supplied by home-ops.

Use `mise x --secrets GH_TOKEN -- gh ...` for repository-scoped GitHub access.
Never print the granted environment. The offline fixtures remain independent
of these clients and secrets.
