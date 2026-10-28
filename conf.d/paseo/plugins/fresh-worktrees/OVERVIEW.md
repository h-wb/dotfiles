Fetches the repository and fast-forwards its local default branch (or the chosen base branch) right before Paseo creates a worktree, so new worktrees start from what is on origin instead of from whatever the checkout last pulled.

A checkout with uncommitted changes to tracked files, a branch that has diverged from origin, or a failed or slow fetch (20 second limit) is left as is, and the worktree is created from the local branch as before. The plugin never blocks worktree creation. It runs `git` on the daemon with the daemon's own credentials and logs each update to the plugin log.
