import type { PluginServerContext } from "@getpaseo/plugin/server";
import { freshen } from "./server/freshen";

// Paseo branches a new worktree off the repo's *local* default branch, which only
// moves when the pod restarts (mise bootstrap repos). Fetch and fast-forward it
// first so agents start from what is on origin. Never fails the creation: a
// throwing before-hook would abort it, so freshen() swallows its own errors.
export default function contribute(server: PluginServerContext) {
  server.before("workspace.create", async ({ request }, { signal }) => {
    const { source } = request;
    if (source.kind === "worktree" && source.cwd) {
      const branchOff = source.action !== "checkout";
      await freshen(source.cwd, branchOff ? source.baseBranch : undefined, branchOff, signal);
    }
    return undefined;
  });
  return () => {};
}
