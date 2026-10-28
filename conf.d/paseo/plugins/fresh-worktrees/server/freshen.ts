import { execFile } from "node:child_process";
import { promisify } from "node:util";

const run = promisify(execFile);

// The hook timeout is 30s and aborts the whole creation; stay well under it.
const BUDGET_MS = 20_000;

async function git(cwd: string, args: string[], signal: AbortSignal): Promise<string> {
  const { stdout } = await run("git", ["-C", cwd, ...args], {
    signal,
    env: { ...process.env, GIT_TERMINAL_PROMPT: "0" },
  });
  return stdout.trim();
}

async function tryGit(cwd: string, args: string[], signal: AbortSignal): Promise<string | null> {
  try {
    return await git(cwd, args, signal);
  } catch {
    return null;
  }
}

/** Path of the worktree that has `refs/heads/<branch>` checked out, if any. */
async function checkoutOf(cwd: string, branch: string, signal: AbortSignal): Promise<string | null> {
  const list = await git(cwd, ["worktree", "list", "--porcelain"], signal);
  let path: string | null = null;
  for (const line of list.split("\n")) {
    if (line.startsWith("worktree ")) path = line.slice("worktree ".length);
    else if (line === `branch refs/heads/${branch}`) return path;
  }
  return null;
}

export async function freshen(
  cwd: string,
  baseBranch: string | undefined,
  fastForward: boolean,
  hookSignal: AbortSignal,
): Promise<void> {
  const signal = AbortSignal.any([hookSignal, AbortSignal.timeout(BUDGET_MS)]);
  const started = Date.now();
  try {
    await git(cwd, ["fetch", "--quiet", "--prune", "origin"], signal);
    if (!fastForward) return;

    // origin/<x> bases are fresh after the fetch; only local branches need moving.
    let branch = baseBranch;
    if (!branch) {
      const head = await tryGit(cwd, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], signal);
      if (!head) return;
      branch = head.replace(/^origin\//, "");
    }
    if (branch.startsWith("origin/")) return;
    if ((await tryGit(cwd, ["rev-parse", "--verify", "--quiet", `refs/remotes/origin/${branch}`], signal)) === null) return;

    const checkout = await checkoutOf(cwd, branch, signal);
    if (checkout) {
      // Never disturb a checkout with work in it; ff-only refuses anything else.
      if ((await git(checkout, ["status", "--porcelain", "--untracked-files=no"], signal)) !== "") {
        console.log(`[fresh-worktrees] ${checkout}: ${branch} has local changes, left as is`);
        return;
      }
      await git(checkout, ["merge", "--ff-only", "--quiet", `origin/${branch}`], signal);
    } else {
      // Updates the ref only when it is a fast-forward.
      await git(cwd, ["fetch", "--quiet", ".", `origin/${branch}:${branch}`], signal);
    }
    console.log(`[fresh-worktrees] ${cwd}: ${branch} at origin/${branch} (${Date.now() - started}ms)`);
  } catch (error) {
    const message = error instanceof Error ? error.message.split("\n")[0] : String(error);
    console.error(`[fresh-worktrees] ${cwd}: left as is: ${message}`);
  }
}
