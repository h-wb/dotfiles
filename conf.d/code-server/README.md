---
area: "[[Homelab]]"
categories:
  - "[[Resources]]"
reviewed: 2026-11-25
summary: How the owner's code-server pod is provisioned from this repo at every start, and what its shell, Git and Proton Pass rely on.
created: 2026-11-24T21:05
---

# The code-server pod

The owner's own environment in the cluster: `ghcr.io/coder/code-server`, Debian, user `coder`, in a browser behind the cluster's login. The owner works there as themselves (`gh auth login`, `mise run land <pr>`). Class `code-server` is layers `workstation`, `pod` and `fish` plus `conf.d/code-server/`, which holds only what is about this image: the fish binary and the editor's terminal profile.

## Provisioning

home-ops' `dotfiles` Component ([README](https://github.com/h-wb/home-ops/blob/main/kubernetes/components/dotfiles/README.md)) runs the two steps every machine runs ([docs/mise.md](../../docs/mise.md#one-bootstrap-two-steps)) in the init container, at every start:

1. The checkout: `mise -E code-server bootstrap --from …?ref=<pin> --update --save-env --only final-hook` moves the `~/.dotfiles` clone to the pinned commit (cloning it on a fresh volume) and saves the environment. A local change stops the move; the pod then runs the previous commit and reports it `stale`.
2. `mise run apply --unattended`. With a live Proton Pass session it applies everything under fnox. Without one it applies what needs no secret: `fresh` on a new volume, or `protect`, without dotfiles, once secrets are on disk.

- mise comes from the `ghcr.io/jdx/mise` image, mounted at `/opt/mise` and first on `PATH` in both containers, because the shims point at it. Its tag must stay at or above `min_version`.
- The log is `~/.local/state/dotfiles.log`, and the status `~/.local/state/dotfiles.status`, `RESULT MODE DATE COMMIT`: `ok`, `degraded` without secrets, `error`, or `stale`. Doctor `pod-start` (layer `pod`) reads it. Only the status line reaches the init container's log, since pod logs are readable by the agents' cluster tools.
- Edit this repo in `~/Repositories/dotfiles`, which layer `pod` clones (the `dotfiles` alias opens it).

The pinned commit runs with the owner's token in the pod: review the exact revision before merging a Renovate pin update, and keep `master` protected and its CI green before enabling auto-merge. Rollback is in the Component's README.

## What it relies on

- Proton Pass: one token, from the pod's Bitwarden secret `code-server`, as `PROTON_PASS_TOKEN` (what repos' `pass:login` reads); `apply --unattended` logs the default session in with it. Never the Paseo pod's token. Layer `pod` keeps pass-cli's key on the volume (`PROTON_PASS_KEY_PROVIDER=fs`).
- Shell: fish from layer `fish`. The image has none, so the binary is fish's own static build (`github:fish-shell/fish-shell`, pinned) in the home volume. The image's login shell is bash and `/etc` does not survive a roll, so the editor's terminal starts fish by its install path, set in the Machine `settings.json`; the User one stays the settings UI's. Not the shim: a shim exits 1 in a folder whose mise config errors, leaving no terminal to fix it from.
- GitHub: git uses `gh auth git-credential`, with `gh` by its shim path because the editor's own git has no mise on `PATH`. The credential branch in `home/git/config.tmpl` follows the declared environment.
- Credentials live on the volume and in its backups: rotate them rather than rely on deletion.
