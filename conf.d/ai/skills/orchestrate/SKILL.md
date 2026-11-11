---
name: orchestrate
description: Use when you run in a Paseo workshop and are asked to orchestrate a change, or the change needs more than one step. You plan, write the spec and decide; cheaper agents started from profiles read the code, build and review. Covers when not to delegate, the spec, the order and when to stop.
---

# Orchestrating a change

You are the most expensive model here. A change costs what its agents read,
times the turns they take, so keep your context small and your turns few:
plan, write the spec, decide. Reading code, editing and running checks belong
to workers.

## Delegate or not

Do the change yourself when it is small and you already know the edit and its
check. A worker starts with no context, so the hand-off costs more than the
edit.

Delegate when the work needs reading you cannot scope, touches more than a few
files, or is long and mechanical.

## Workers

Workers are Paseo agents started from profiles. Read the `paseo` skill, call
`list_profiles` once, and start each worker with `create_agent` from the
profile whose note fits: Explore, Build, Review.

- Omit `workspaceId`. A worker is your sub-agent and works in your workspace,
  on your branch. This is the one exception to the own-workspace rule of
  `paseo-workspace-hygiene`: the workspace is yours and the workers are part
  of your task.
- One worker that edits at a time.
- After `create_agent`, end your turn. Paseo notifies you when the worker is
  done. Do not poll.
- Your harness's built-in sub-agents run on your own model or its vendor's, so
  they save nothing. Use the profiles.
- Without `list_profiles` and `create_agent` you cannot delegate here: do the
  work yourself, in the same order.

## Order

1. **Find out.** If you do not know the code, start Explore with one question.
   Ask for paths and line numbers, not file contents. Then read only what it
   points at.
2. **Write the spec** to a file outside the repo, such as
   `/tmp/spec-<branch>.md`:
   - Goal: one sentence.
   - Files to change, and what must not be touched.
   - Decisions already made, so the builder does not reopen them.
   - Check: the exact command, and what passing looks like.
3. **Build.** Start Build with: "Implement the spec at `<path>`, in this
   workspace. Stay inside the spec. Do not commit, push, or create a workspace
   or a branch. Run the check. Report the changed paths and the last lines of
   the check."
4. **Check.** Run the check yourself and read only the end of its output.
5. **Review**, only for a change in behaviour or a real risk: permissions,
   secrets, stored data, CI. Not for prose, formatting, renames or routine
   config. Start Review with: "Review `git diff` in this workspace against the
   spec at `<path>`. Report concrete defects only, most severe first. Make no
   edits." Do not add your reasoning.
6. **Decide.** Read `git diff --stat` and the hunks the review names. Fix a
   small defect yourself.
7. **Finish.** Commit, then push and open the pull request as the repo and
   `paseo-workspace-hygiene` say. Report what changed, the check's result, and
   what was skipped and why.

## When it fails

Send the same worker the failing output once, with `send_agent_prompt`. If it
fails again, finish the work yourself or ask the user. Never a third round.

## Keep prompts small

- Pass paths, never file contents or a transcript.
- Ask every worker for a short report: findings, changed paths, check output.
- Do not re-read what a worker summarised unless your decision depends on it.
