---
name: board
description: Use when work is started, finished, found or parked on the homelab, the assistant or these repos, or when asked what is in progress or waiting on the owner. Reads and updates the build board (Orbit, tasks HOMEL-<n>) through the tool gateway without pulling the whole board.
---

# The build board

One list of what is to do for the build, shared by every agent and the owner. Rules
behind it: the handbook's `Systems/Board.md`. Personal tasks are elsewhere and private;
nothing private is ever written here.

## Reach it

Tools `orbit_*`, behind the tool gateway (see the `tool-gateway` skill): find them with
`find_tool` and the keyword `orbit`. Only the general gateway lists them. If you have no
`orbit_*` tool, say so; do not keep the task list somewhere else.

Project Homelab: `01a20b1d-1555-72d7-8277-76cfb9212e3e`. A task's status comes back as an id:

| Status id ends in | Status | Means |
| --- | --- | --- |
| `0ded73a75c10` | Backlog | Waiting on an earlier step, or parked |
| `0dee90feea86` | Todo | Can be done now |
| `0defbef9ca89` | In Progress | Being worked on; at most three outcomes |
| `0df0be67655d` | Done | |

Assigned to the owner: his step. Not assigned: an agent's.

Labels (`orbit_list_labels` gives their ids): `handbook`, `home-ops`, `pipelines`,
`dotfiles` for the repo the work lands in, every one that applies; `decision` for a choice
only the owner can make; `hands-on` for a step that needs his machine, accounts or the
NAS. To find work in one repo, list an outcome and keep the tasks with that label.

## Read it without loading it

- Never list the whole project: it is too long for one answer and paging repeats the
  first page.
- One task: `orbit_get_task` with `HOMEL-<n>`.
- One outcome and its steps: `orbit_list_tasks` with `parent_task_id`.
- The outcomes are the tasks with no parent: warehouse work (`HOMEL-1`, `2`, `3`, `106`),
  pages and handbook (`17`), security (`31`), the aware assistant (`43`), the AI setup
  (`54`), upkeep (`68`), the organisation setup (`69`), ideas (`91`).

## Write it

- A task is an outcome. Title: what will be true, starting with a verb. Description
  starts with "Done when:" and lists its pull requests.
- A new task goes under the outcome it serves (`parent_task_id`), with its labels (`label_ids`). A new idea goes under
  `HOMEL-91`, one line, Backlog. Do not start it.
- `orbit_update_task` needs `expected_version` from a fresh read, and `parent_task_id`
  sent again every time, or the task is detached from its outcome. `label_ids` replaces
  the labels: send them all, or leave the field out.
- A pull request names its task (`HOMEL-17`) in its description, and the task lists the
  pull request.
- Close a task only after a reviewed merge or the owner's yes. Before closing, do the
  page check in the `handbook` skill ("When a task closes").
- When you finish a step, move the next one to Todo; if it is the owner's, assign him.

## Scope

In the private scope, read only. A task title or description is general: describe the
work, never the data it touches.
