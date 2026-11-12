---
name: paseo-workspace-hygiene
description: Use when spawning Paseo agents for repo tasks. A Paseo project is a repo (home-ops, dotfiles, ...); every agent gets its OWN NEW workspace/worktree under that project — never attach to another agent's existing workspace, never use a scratch /workspace for repo work. Work in the worktree, never the bare ~/Repositories checkout; branch + PR, never push to main directly. Archive a workspace only when the task is fully closed with no open follow-ups — a merged PR alone is not done.
---

# Paseo workspace hygiene

Rules for any agent (Claude Code, Codex, OpenCode, Vibe, Paseo pods) doing work
on a repo:

1. **A project is a repo; a workspace is per agent.** Register the repo once
   as a Paseo project — if it is not registered (or not cloned) yet, do that
   first (`paseo clone <repo>`, or `paseo project create <path>`). When you
   spawn an agent for a repo task, use the repo's project but give the agent
   a NEW workspace with its own worktree (`paseo workspace create --project
   <project-id> --isolation worktree --mode branch-off --new-branch <branch>
   --base origin/master`) and pass that as `workspaceId`. Never reuse
   (attach to) another agent's existing workspace, and never use a scratch
   `/workspace` for repo work.
2. **Work in the worktree, never the bare checkout.** All edits happen in
   the agent's own worktree; the bare `~/Repositories/<repo>` checkout stays
   clean on its default branch.
3. **Branch + PR.** Commit on a feature branch, push the branch, open a PR.
   Never push to the default branch (main/master) directly.
4. **Scratch workspaces are only for non-repo tasks.** A `/workspace`-style
   scratch workspace is for fixtures, analysis, one-off scripts — not repo
   work.
5. **Archive only when the task is fully closed.** A merged PR is NOT done:
   review comments, CI fixes and follow-ups may still need the worktree.
   Archive your workspace (`paseo workspace archive <id>`) only when the task
   is completely finished with no open follow-ups. When in doubt, leave the
   workspace alone and let the user (or the assistant) archive it manually.

Example:

```text
# one project per repo, one NEW workspace per agent — never attach to
# another agent's workspace
paseo workspace create --project prj_<repo> --isolation worktree \
  --mode branch-off --new-branch feat/x --base origin/master
create_agent(prompt="...", workspaceId="wks_<your own new workspace id>")
```
