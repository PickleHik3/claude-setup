---
name: delegating
description: Briefing a worker and merging its branch - the parts of a brief, the base-hash and worktree rules, the review before a merge and the checks after. Use before spawning fixer or fixer-opus, and before merging a worker's work.
---

# Briefs

Goal · files in scope with the method names and line numbers to edit (verified at the base
commit) · constraints · what is known, including the cause for a fix · verify commands to run (or
"per AGENTS.md") · report format · handoff path: `<scratchpad>/handoffs/<branch>.md` (the
session's scratchpad directory, written out in full; fixers write a handoff there before every
report).

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

# Resuming a worker

A worker's prompt cache lasts 5 minutes from its last request. Within it a resume is cheap; after
it the resume rewrites the worker's whole context (about 25x a warm resume: ~$1.10 for a 220k
fixer-opus, ~$0.45 for a 150k fixer).
- Send a fix-up as soon as the report and diff show it is needed, before the build, the full suite
  and any other long check; merge after the worker's second round.
- When `resume-gate` denies a message to a cold worker, choose: a fresh worker (same agent, or a
  different model) briefed with the handoff path and the follow-up, when the handoff covers what
  the follow-up needs; or the same message again to resume, when the follow-up depends on what the
  worker read and the handoff leaves out. Record a fresh worker with `--retry-of <first id>`.
- A worker that stopped with no commits is always continued fresh (step 2 above).

# Recording the outcome

Right after the merge review of each worker (step 4 above), before briefing the next one, run
`cc-usage outcome <agent-id> pass|review|fail --kind <kind>` from this session's Bash (review =
passed after you fixed something; fail = not merged as it was). Give `--missed` when it failed,
and `--retry-of <first id>` on a re-brief, so a retry's cost counts toward its task. Use `--pair` to tie two workers given the
same task to compare models. The agent id is in the worker's completion notice; a unique prefix
works. Written comparisons still go in the markdown ledger.
