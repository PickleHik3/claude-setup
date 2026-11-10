# Delegation

The main session orchestrates; the goal is the least usage and the smallest main context that
still gets the work right. Delegate when a worker saves more reading than its startup costs
(about 10k tokens); small edits in files already in context stay here.

| Agent | Model | Use for |
|---|---|---|
| Explore | Haiku | Read-only search and reading; returns the conclusion with `path:line`. |
| fixer | Sonnet | The default builder: any specified change at any size, including geometry or layout with a checkable spec. |
| fixer-opus | Opus | Only when the premise may be wrong, a fixer round already missed once, a renderer or pipeline is being replaced, or the spec should be challenged before building. |
| lead | Opus | One bounded wave of multi-step work that needs judgement at a few points and typing in between. It fixes the list, briefs fixers one at a time, checks them and hands back one report with raw evidence. |

- Investigation (unknown cause) goes to Explore or a reproduction first, never to a builder with
  the investigation in the brief.
- Subagents never run on Fable; Fable is the main session's model, chosen by the user. Workers may
  spawn only Explore; Explore spawns nothing. The exception is `lead`, which may also spawn
  `fixer` and `device-checker`, never `lead` or `fixer-opus`. `hooks/model-gate.py` enforces all
  of it.
- Opus is for judgement, not typing. Once the premise is settled and the change list is fixed
  (a verbatim move, a substitution, a scripted pass), the builder is `fixer`, however large the
  change; the guard is a mechanical check of the result, which works the same for any model.
- Use `lead` when the main session would otherwise read every worker's report for one wave:
  most of all when the main session runs on Fable, where each report costs the most. When the
  main session runs on Opus it can lead a wave itself, so `lead` earns its place only for a long
  wave, or two waves running side by side. One lead per wave; the main session keeps the user's
  decisions, merges into shared checkouts, real devices, memory and the ledger.
- A worker's full report goes to a file; what comes back into the main context is short (the
  outcome, the raw result lines, what was not verified, the file's path).
- Effort stays at the agent's default; for one hard task pass `effort: high` on the Agent call
  (text in a brief does not change effort).
- Reuse a worker per area of code (SendMessage keeps what it has read); retire it when it compacts
  or the area changes.
- Log each worker outcome in a private ledger: the file at `$CLAUDE_LEDGER` if set, else
  `~/.claude/model-performance.md` (date, agent, effort, task kind, pass / pass with review /
  fail, what it missed, tokens and calls). Route by what the ledger shows, not by habit.

# Briefs

Goal · files in scope with the method names and line numbers to edit (verified at the base
commit) · constraints · what is known, including the cause for a fix · verify commands to run (or
"per AGENTS.md") · report format.

- One goal per brief. Builders build: cause-finding goes to Explore or a reproduction first. When
  the cause is unclear or one fix has already missed, reproduce it and put that in the brief.
- State the goal and the method separately; the worker stops and reports if they contradict.
- Media never goes to a worker; the brief carries the numbers or timeline read from it.
- If a worker cannot pin a runtime cause, it commits temporary tagged logging as its own commit;
  this session builds that branch, reproduces once, captures the tagged lines and sends them back.
  The fix goes on top and the log is reverted, never merged.

# Worktrees and merging

1. Commit before delegating. With the default base, a worker's worktree can be cut from origin
   rather than this session's local HEAD, and the session's cwd can silently reset to the main
   checkout after a background command. Every brief names the expected base hash and tells the
   worker to stop if `git merge-base --is-ancestor <hash> HEAD` fails (or to fast-forward with
   `git merge --ff-only <hash>` when the brief allows it). When it matters, create the worktree
   yourself (`git worktree add -b <branch> <path> <base>`) and spawn the worker without
   isolation, told to work in that path.
2. A worker that stops with no commits loses its worktree; continue it with a fresh spawn, not
   SendMessage, or it edits this session's tree.
3. One worker per seam (one file, one view hierarchy, one hook); parallel workers only on disjoint
   modules.
4. Before merging, read the worker's report and `git diff --stat`. Read the full hunks only where
   the report flags something ("outside the brief", "verify first", a failed or skipped check) or
   for geometry and layout work. Say in the merge what you read.
5. After merging, run the project's build and tests once into a log; have Explore report only the
   failures. Then remove the worktree and branch (`/wrap-up` does this at session end).
- Never switch branches in a shared main checkout, and address other worktrees with `git -C
  <path>` in background chains.

# Seeing the work

- For a visual change, look at the result yourself before calling it done; a checker's "passed" is
  a claim. Before/after comparisons are for changes whose look is the point, not every tweak.

# Asking and showing

- Grilling (`grilling`, `grill-me`, `grill-with-docs`) asks through AskUserQuestion: one question
  per decision, the recommended option first marked "(Recommended)", a `preview` for mockups.
