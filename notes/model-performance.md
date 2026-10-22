# Model performance ledger

What each subagent model did on real briefs, so the delegation table in `CLAUDE.md` rests on
evidence. One entry per comparison or notable outcome; newest first.

## Sonnet 5.5 as `fixer`

**Policy from 2026-10-22:** give `fixer` (Sonnet 5.5) tasks that would otherwise go to
`fixer-opus`, one notch harder each time, and record where it fails. The aim is its upper limit,
not a tally of wins. Keep `fixer-opus` for anything the ledger already shows Sonnet failing at.

### 2026-10-22 · termux-launcher · "font size setting relaunch lands on the terminal"

Same brief to `fixer-opus` (Opus, high) and `fixer` (Sonnet 5.5, medium), each in its own
worktree. The brief's premise was wrong: the app's own font size setting never recreates the
activity.

| | Opus | Sonnet 5.5 |
|---|---|---|
| Found the premise false | yes | yes |
| Committed a speculative fix | no | no |
| Deliverable | device-check item with three reproduction paths, exact commands, next suspects | device-check item, one path, a logcat test that settles it |
| Named a candidate cause | after `landWall`: pane-layout restore, display window, widget page reset; process death | null saved state from `clearTaskOnLaunch`, with the cold-start side effect of a fallback |
| Tokens / tool calls / wall time | 152k / 70 / 6.6 min | 131k / 50 / 4.1 min |

Verdict: equal on correctness and honesty; Opus more thorough in the write-up. No quality gap
that justified Opus for an investigation of this size. A reproduction on pong afterwards agreed
with both (Home page 1 stays).

### Open questions to settle with later briefs

- A change spanning 3+ files with a pure policy class and a test (the `fixer-opus` default).
- Geometry or layout arithmetic (dock bands, pane shapes).
- A bug whose cause is unknown and needs a reproduction on the emulator.
- Review of another worker's diff.
