---
area: "[[Homelab]]"
categories:
  - "[[Resources]]"
reviewed: 2026-11-25
summary: How the owner's code-server pod is provisioned from this repo at every start, and what its shell, Git and Proton Pass rely on.
created: 2026-11-24T21:05
---

# The code-server pod

The owner's own environment in the cluster: `ghcr.io/coder/code-server`, Debian, user `coder`, in a browser behind the cluster's login. The owner works there as themselves (`gh auth login`, `mise run land <pr>`). Class `code-server` is layers `workstation`, `pod`, `nonroot` and `fish` plus `conf.d/code-server/`, which holds only what is about this image: the fish binary and the editor's terminal profile.

## Provisioning

home-ops' `dotfiles` Component ([README](https://github.com/h-wb/home-ops/blob/main/kubernetes/components/dotfiles/README.md)), in the init container, downloads the pinned commit's tarball and swaps it in at `~/.dotfiles` (whatever was there goes; `.pinned-commit` names the commit), then runs `scripts/pod-bootstrap code-server` by path. It is never a link the bootstrap manages, so a rolled pod comes back provisioned. Do not move the script without changing home-ops with it.

`scripts/pod-bootstrap ENVIRONMENT` is the one implementation for the workstation pods, neko's too:

- The environment from its one argument, saved by `mise bootstrap --save-env`; mise from `scripts/provision.sh`.
- Three modes: `secrets` (a live Proton Pass session), `fresh` (no session, nothing to lose), `protect` (no session and secrets on disk: dotfiles skipped). fnox and pass-cli come from `mise exec`, on demand, so a fresh volume's token works in its first run.
- One log, `~/.local/state/pod-bootstrap.log`, and a status file, `RESULT MODE DATE COMMIT`: `ok`, `degraded` without secrets, `error`, or `stale` when home-ops' download failed and an older commit ran. Doctor `pod-bootstrap` (layer `pod`) reads it and flags what older bootstraps left behind (`~/.dotfiles.broken-*`, `~/.dotfiles.pre-pin`, `~/home-ops`, `~/.neko-hold`). Only the status line reaches stdout, since pod logs are readable by the agents' cluster tools.
- It never fetches or pulls. `~/.dotfiles` is replaced at every start, so edit this repo in `~/Repositories/dotfiles`, which layer `pod` clones (the `dotfiles` alias opens it).

The pinned commit runs with the owner's token in the pod: review the exact revision before merging a Renovate pin update, and keep `master` protected and its CI green before enabling auto-merge. Rollback is in the Component's README.

## What it relies on

- Proton Pass: one token, from the pod's Bitwarden secret `code-server`, as `PROTON_PASS_TOKEN` (what repos' `pass:login` reads); pod-bootstrap logs the default session in with it. Never the Paseo pod's token. Layer `pod` keeps pass-cli's key on the volume (`PROTON_PASS_KEY_PROVIDER=fs`).
- Shell: fish from layer `fish`. The image has none, so the binary is fish's own static build (`github:fish-shell/fish-shell`, pinned) in the home volume. The image's login shell is bash and `/etc` does not survive a roll, so the editor's terminal starts fish by its install path, set in the Machine `settings.json`; the User one stays the settings UI's. Not the shim: a shim exits 1 in a folder whose mise config errors, leaving no terminal to fix it from.
- GitHub: git uses `gh auth git-credential`, with `gh` by its shim path because the editor's own git has no mise on `PATH`. The credential branch in `home/git/config.tmpl` follows the declared environment.
- Credentials live on the volume and in its backups: rotate them rather than rely on deletion.
