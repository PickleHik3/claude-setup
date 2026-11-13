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
  the investigation in the brief. A cause is unknown when nothing in the code fits what the user
  described, not when it is merely unproven: the user's description counts as the reproduction,
  and a likely cause that fits it goes straight to a fix.
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
  (the Agent tool takes `effort`; text in a brief does not change effort).
- Reuse a worker per area of code (SendMessage keeps what it has read); retire it when it compacts
  or the area changes.
- Log each worker outcome in a private ledger: the file at `$CLAUDE_LEDGER` if set, else
  `~/.claude/model-performance.md` (date, agent, effort, task kind, pass / pass with review /
  fail, what it missed, tokens and calls). Route by what the ledger shows, not by habit.

# Briefs and merging

Load the `delegating` skill before writing a brief for a worker and before merging a worker's
branch: it holds the parts of a brief, the worktree rules and the merge review. Three of its
rules hold even when it is not loaded:

- Commit before delegating, and name the base hash in every brief.
- One worker per seam; parallel workers only on disjoint modules.
- A shared main checkout stays on its branch; branch work happens in a worktree.

# Seeing the work

- For a visual change, look at the result yourself before calling it done; a checker's "passed" is
  a claim. Before/after comparisons are for changes whose look is the point, not every tweak.

# Asking and showing

- Grilling (`grilling`, `grill-me`, `grill-with-docs`) asks through AskUserQuestion: one question
  per decision, the recommended option first marked "(Recommended)", a `preview` for mockups.
