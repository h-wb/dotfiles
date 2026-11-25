---
area: "[[Homelab]]"
categories:
  - "[[Resources]]"
reviewed: 2026-11-25
summary: What the Paseo agent pods take from this repo, how they apply it at every start, and the one file they share with home-ops.
topics:
  - "[[Workshop]]"
created: 2026-11-24T21:00
---

# The Paseo pods

The [workshops](https://github.com/h-wb/handbook/blob/main/Systems/Workshop.md): one pod per scope, general and private. Both are class `paseo`, detected by `/etc/paseo`, and `PASEO_DATA_SCOPE` names the scope. They load no `workstation` layer, so no kubeconfigs, credentialed CLIs or `apply` tasks. How the pods are built, what each can reach and how scopes are kept apart is home-ops': [paseo/README.md](https://github.com/h-wb/home-ops/blob/main/kubernetes/apps/main/llm/paseo/README.md).

## What this class gives them

- The agents' tool and memory servers, from `conf.d/ai/mise.paseo.toml` like on every machine: the scope's gateway, its memini and the Chromium sidecar's `chrome-devtools` ([ai](../ai/README.md)).
- The skills only a pod can use: `mise.paseo.toml` declares `orchestrate` and `paseo-workspace-hygiene` from [h-wb/skills](https://github.com/h-wb/skills), beside the three every machine declares, in the same two folders ([ai](../ai/README.md#skills)). The private pod takes them too.
- CLIs (node 24, as 26 needs a library the image lacks), the repos agents work on in `~/Repositories`, `bashrc` and the starship prompt. `trusted_config_paths` covers `~/Repositories` and `~/.paseo/worktrees`, since an untrusted repo config fails every shim run.
- `[bootstrap.repos]` with a `ref` are put back on their base branch at every start when clean, as agents work in Paseo worktrees. A `ref` makes the init container fetch, so only public repos have one.
- Git identity: the general pod commits as the bot, the private pod as the owner.
- Proton Pass: one session per scope, `paseo-<scope>`, logged in by `paseo:pass-login`, which extends the shared template ([proton-pass](../proton-pass/README.md)).

## Provisioning

```mermaid
flowchart LR
  I["tools init container"] -->|"mise bootstrap --from dotfiles.git --config-dir ."| D["~/.dotfiles (emptyDir)"]
  D --> R[rendered home]
  E["/etc/paseo/config/paseo.json"] -->|paseo-overlay| P["~/.paseo/config.json"]
  R --> A[app container]
  P --> A
```

- home-ops' `tools` init container runs `mise bootstrap --from <dotfiles.git> --from-dir ~/.dotfiles --config-dir . --yes --force-dotfiles --skip-dirty --locked`, with no script. The private pod adds `--skip=repos,task`, so it clones no repos and runs no login. mise re-reads `miserc.toml` after the first clone.
- The clone leaves the `vendor/skills` submodule empty; the `pre-dotfiles` hook in `conf.d/ai` brings it to h-wb/skills main before the skills are linked, so the init container needs GitHub (it has it for the clone). The private pod skips `repos`, not `dotfiles`, so it runs the hook too.
- `~/.dotfiles` is an `emptyDir`, cloned fresh at every start and read-only in the app container, because `--update` only fast-forwards: an agent's commit there once blocked the pod. Edit dotfiles in `~/Repositories/dotfiles`, in a Paseo worktree.
- Shims link to the mise that made them, so mise is the jdx/mise image mounted at `/opt/mise` in every container, first on `PATH`. The image tag is the mise version: keep it at or above `min_version`.
- Never set `MISE_CONFIG_DIR=~/.dotfiles` there: through the real directory, mise rewrites the lock sidecar paths, and the checkout is read-only anyway. The link is enough.
- `paseo-overlay` is its own env, detected by `/etc/paseo/config/paseo.json`, because a merge with a missing source is an error. It merges that file into `~/.paseo/config.json`. That path, `PASEO_DATA_SCOPE` and the URL and key variables are the whole contract with home-ops.
- No sshd: terminals come from Paseo, admin shells from `kubectl exec`.
