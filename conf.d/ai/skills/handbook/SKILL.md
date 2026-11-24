---
name: handbook
description: Use before answering how the homelab, the assistant, the warehouse or any of these repos works, before changing a page, and when a task closes. Finds the one page that answers without loading the rest, and keeps pages true after a change.
---

# Finding and keeping the pages

What is known is written in pages, once: the handbook (`h-wb/handbook`) for what spans
repos, each repo for what its code can make wrong. Read the page; do not answer from
memory, and do not load a whole folder.

## Find the page, cheaply

1. Look in the repo you are in first: its `AGENTS.md`, then its `README.md`, which link
   its pages.
2. For anything wider, the handbook. Every page there and in the repos starts with a
   one-line `summary`, so the summaries are the index. With a clone on disk
   (`~/Repositories/handbook`, or wherever the repos are):

   ```sh
   grep -r --include='*.md' --exclude-dir=Templates '^summary: .' ~/Repositories/handbook
   ```

   About 50 lines. Pick one page from it and read that page only.
3. Without a clone (the assistant, a pod with no checkout), read through the GitHub tool
   of your tool gateway, owner `h-wb`, repo `handbook`: `README.md` first, then the one
   page it points to. A system is a page named for its role in `Systems/` (`Warehouse`,
   `Board`, `Assistant`); the product is an alias on that page.
4. A system page ends with "Where its code is": follow that link into the repo for
   mechanics. Follow one link at a time and stop when the question is answered.

Stop at the answer. Two or three pages is normal; reading ten means the index was skipped.

## When your change makes a page wrong

- Fix the page in the same pull request. A page states what is true today.
- Something not done yet is a task on the board, not a line in a page. Where the gap
  matters to the reader, write today's fact and the task number: "does not read the
  warehouse today (HOMEL-49)".
- Set `reviewed:` to today only if you checked the page against the code or the cluster.
  An edit alone does not count.
- How a page is written, its header and where it lives: the handbook's
  `Resources/Write a page.md`. Read it before writing a new page.

## When a task closes

Search its number in every repo you have, and bring each line up to date:

```sh
grep -rn --include='*.md' 'HOMEL-49\b' ~/Repositories/{handbook,home-ops,pipelines,dotfiles}
```

The line then states the new fact without the number. A closed task's number left in a
page is a stale page.

## Scope

Private data goes in no page. In the private scope, read pages freely and write none:
pages are general, and information only flows from general to private.
