---
name: paseo-workspace-hygiene
description: Use when spawning Paseo agents for repo tasks. Attach the agent to the repo's existing workspace via workspaceId; if none exists, register the repo and create its workspace. Work in a worktree, never the bare ~/Repositories checkout. Branch + PR, never push to main directly. Scratch /workspace workspaces are only for non-repo tasks (fixtures, analysis).
---

# Paseo workspace hygiene

Rules for any agent (Claude Code, Codex, OpenCode, Vibe, Paseo pods) doing work
on a repo:

1. **Attach to the repo's workspace.** Pass the repo's existing workspace as
   `workspaceId`. If the repo has no workspace yet, register it
   (`paseo project create <path>`, or `paseo clone <repo>`) and create its
   workspace first — do not fall back to a scratch dir.
2. **Work in a worktree, never the bare checkout.** Create the workspace with
   worktree isolation (branch off a new branch). The bare
   `~/Repositories/<repo>` checkout stays clean on its default branch.
3. **Branch + PR.** Commit on a feature branch, push the branch, open a PR.
   Never push to the default branch (main/master) directly.
4. **Scratch workspaces are only for non-repo tasks.** A `/workspace`-style
   scratch workspace is for fixtures, analysis, one-off scripts — not repo work.

Example:

```text
create_agent(prompt="...", workspaceId="wks_<repo workspace id>")
```
