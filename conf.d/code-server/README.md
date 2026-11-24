---
area: "[[Homelab]]"
categories:
  - "[[Resources]]"
reviewed: 2026-11-24
summary: How the owner's code-server pod is provisioned from this repo at every start, and what its shell, Git and Proton Pass rely on.
created: 2026-11-24T21:05
---

# The code-server pod

The owner's own environment in the cluster: `ghcr.io/coder/code-server`, Debian, user `coder`, in a browser behind the cluster's login. The owner works there as themselves (`gh auth login`, `mise run land <pr>`). Class `code-server` is layers `workstation`, `pod` and `fish` plus `conf.d/code-server/`, which holds only what is about this image: the fish binary, the editor's terminal profile and doctor `pod-bootstrap`.

## Provisioning

home-ops' `dotfiles` Component ([README](https://github.com/h-wb/home-ops/blob/main/kubernetes/components/dotfiles/README.md)) clones `~/.dotfiles` at start when `scripts/pod-bootstrap` is missing, moving a cut-off clone aside, then runs that script by path. It is never a link the bootstrap manages, so a rolled pod comes back provisioned. Do not move the script without changing home-ops with it.

`scripts/pod-bootstrap` is the one implementation for workstation pods:

- mise from `scripts/provision.sh`, then neko's three modes: `secrets` (a live Proton Pass session), `fresh` (no session, nothing to lose), `protect` (no session and secrets on disk: dotfiles skipped).
- A second run when the first installed fnox and the pod's token works, so secrets apply at this start rather than the next.
- A status file for doctor `pod-bootstrap`; only the status line on stdout, since pod logs are readable by the agents' cluster tools. The log is `~/.local/state/pod-bootstrap.log`.
- Options for other pods: `--pull`, `--hold FILE`, `--log NAME`, `--timeout SEC`. neko still runs its own `neko-bootstrap`.

It never pulls on code-server: it runs unattended with the owner's token, so it applies the checkout already on the volume, and only an empty volume clones `master`. Updating is done by hand, as on the Mac: `git -C ~/.dotfiles pull`, read it, `mise run apply`. Keep `master` protected (a pull request and the owner's review), since the first clone and every pull take it.

## What it relies on

- Proton Pass: one token, from the pod's Bitwarden secret `code-server`, as `PROTON_PASS_TOKEN` (what repos' `pass:login` reads); pod-bootstrap logs the default session in with it. Never the Paseo pod's token. Layer `pod` keeps pass-cli's key on the volume (`PROTON_PASS_KEY_PROVIDER=fs`).
- Shell: fish from layer `fish`. The image has none, so the binary is fish's own static build (`github:fish-shell/fish-shell`, pinned) in the home volume. The image's login shell is bash and `/etc` does not survive a roll, so the editor's terminal starts fish by its install path, set in the Machine `settings.json`; the User one stays the settings UI's. Not the shim: a shim exits 1 in a folder whose mise config errors, leaving no terminal to fix it from.
- GitHub: git uses `gh auth git-credential`, with `gh` by its shim path because the editor's own git has no mise on `PATH`. The credential branch in `home/git/config.tmpl` follows the class.
- Credentials live on the volume and in its backups: rotate them rather than rely on deletion.
