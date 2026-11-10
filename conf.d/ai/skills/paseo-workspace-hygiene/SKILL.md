---
name: paseo-workspace-hygiene
description: Use when spawning Paseo agents for repo tasks. A Paseo project is a repo; each agent gets its OWN new workspace/worktree inside that project — never reuse another agent's existing workspace. Work in a worktree, never the bare ~/Repositories checkout. Branch + PR, never push to main directly. Once the PR is merged and the agent is idle, archive its own workspace. Scratch /workspace workspaces are only for non-repo tasks (fixtures, analysis).
---

# Paseo workspace hygiene

Rules for any agent (Claude Code, Codex, OpenCode, Vibe, Paseo pods) doing work
on a repo:

1. **A project is a repo; each agent gets its own NEW workspace.** Register
   the repo once as a Paseo project (`paseo project create <path>`, or
   `paseo clone <repo>`), then create a NEW workspace for yourself inside that
   project (`paseo workspace create --project <project-id> --isolation
   worktree ...`) and pass it as `workspaceId`. Never reuse another agent's
   existing workspace — every agent works in its own worktree.
2. **Work in a worktree, never the bare checkout.** Create the workspace with
   worktree isolation (branch off a new branch). The bare
   `~/Repositories/<repo>` checkout stays clean on its default branch.
3. **Branch + PR.** Commit on a feature branch, push the branch, open a PR.
   Never push to the default branch (main/master) directly.
4. **Scratch workspaces are only for non-repo tasks.** A `/workspace`-style
   scratch workspace is for fixtures, analysis, one-off scripts — not repo work.
5. **Archive your own workspace when done.** Once your PR is merged and you are
   idle, archive your own workspace (paseo CLI, e.g.
   `paseo workspace archive <id>`; check `paseo workspace --help`) so finished
   work does not linger. Do NOT archive while review/CI follow-ups may still
   need the worktree.

Example:

```text
# one project per repo, one NEW workspace per agent — never attach to
# another agent's workspace
create_agent(prompt="...", workspaceId="wks_<your own new workspace id>")
```
