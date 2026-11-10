---
name: delegating
description: Briefing a worker and merging its branch - the parts of a brief, the base-hash and worktree rules, the review before a merge and the checks after. Use before spawning fixer, fixer-opus or lead, and before merging a worker's work.
---

# Briefs

Goal · files in scope with the method names and line numbers to edit (verified at the base
commit) · constraints · what is known, including the cause for a fix · verify commands to run (or
"per AGENTS.md") · report format.

- One goal per brief. Builders build: cause-finding goes to Explore or a reproduction first. When
  the cause is unclear or one fix has already missed, reproduce it and put that in the brief.
- State the goal and the method separately; the worker stops and reports if they contradict.
- Media stays with this session; the brief carries the numbers or timeline read from it.
- Scouts miss callers made by method reference and by reflection: say so in a scout's brief, and
  check a "never called" before a builder relies on it.
- If a worker cannot pin a runtime cause, it commits temporary tagged logging as its own commit;
  this session builds that branch, reproduces once, captures the tagged lines and sends them back.
  The fix goes on top and the log is reverted, never merged.

# Worktrees and merging

1. Commit before delegating. With the default base, a worker's worktree can be cut from origin
   rather than this session's local HEAD, and the session's cwd can silently reset to the main
   checkout after a background command. Every brief names the expected base hash and tells the
   worker to stop if `git merge-base --is-ancestor <hash> HEAD` fails (or to fast-forward with
   `git merge --ff-only <hash>` when the brief allows it). When it matters, create the worktree
   yourself (`git worktree add -b <branch> <path> <base>`) and tell the worker to work in that
   path and create no other.
2. A worker that stops with no commits loses its worktree; continue it with a fresh spawn, not
   SendMessage, or it edits this session's tree.
3. One worker per seam (one file, one view hierarchy, one hook); parallel workers only on disjoint
   modules.
4. Before merging, read the worker's report and `git diff --stat`. Read the full hunks only where
   the report flags something ("outside the brief", "verify first", a failed or skipped check) or
   for geometry and layout work. For code that was moved, compare each moved method with its
   body at the base mechanically; every difference should be a field or call that changed owner.
   Say in the merge what you read.
5. After merging, run the project's build and its full unit suite once into a log (a worker's
   scoped run misses tests in other packages and tests that scan sources); have Explore report
   only the failures. Then remove the worktree and branch (`/wrap-up` does this at session end).
- Stay on the branch a shared main checkout is on, and address other worktrees with `git -C
  <path>` in background chains.
