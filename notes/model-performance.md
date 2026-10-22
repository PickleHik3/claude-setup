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

### 2026-10-22 · termux-launcher · "write the three-tier pong install rule into AGENTS.md, the releasing doc and the install script"

`fixer` (Sonnet 5.5) alone. Docs plus a script comment, four files, the policy text given in the
brief. 59k tokens, 6 tool calls, 47 s. Replaced every sentence of the old rule and listed each
with file:line; added the two per-drop emulator checks and cross-referenced the existing
migrations item instead of duplicating it. One gap, reported honestly: the brief asserted staging
builds carry `+dev.<sha>`, the script only did that for release, and Sonnet wrote the doc claim
as given rather than making the script true. It also said it had not counted the "sixteen"
debug branches it quoted. Verdict: pass for a docs task; it does not fix a brief's false
premise in code when told the code is out of scope, which is the rule, so the caller closed the
gap (one script edit).

### 2026-10-22 · termux-launcher · "Home widgets follow the shared Text size through WidgetTokens"

`fixer` (Sonnet 5.5) alone, one notch up: 15 files, a Follower on the widget base view with a
per-frame coalesced rebuild, a pure scale function, fit tests at 0.8/1.5 × font scale 1.0/1.3.
89k tokens, 18 tool calls, 3.9 min. Diff was idiomatic (compare-before-rebuild, postOnAnimation,
@After resets the static), stayed inside the widget package, and the report named the two real
risks (sources restart on rebuild; editor picker preview unverified). Verdict: pass. Next notch:
a change spanning packages with a policy class, then an unknown-cause bug.

### 2026-10-22 · termux-launcher · "Split gap slider on the editor's Terminal tap, Margin cut loose from the pane gap"

`fixer` (Sonnet 5.5) alone: an editor control end to end (enum, per-surface list, string,
read/legend/write, geometry preview reuse), dead code removed, two test classes changed. 78k
tokens, 16 tool calls, 2.1 min. Every Gradle run it tried died on an environment fault (a stale
Gradle daemon failing AAPT2 startup in worktrees; `--no-daemon` works) and it said so plainly,
committed on a by-eye review, and listed exactly what to verify first. The caller ran the tests
without the daemon: all green, diff clean. Verdict: pass; honest under a broken toolchain.

### 2026-10-22 · termux-launcher · shader and latency series (five `fixer` briefs)

Sonnet 5.5 took a run of graphics and performance work that would have gone to `fixer-opus`:

1. **Round-1 latency telemetry** (trace sections across four modules, async spans, frame-source
   counters, a gated echo redraw, a shader pre-warm through `HardwareRenderer`). 121k tokens, 41
   calls, 8.6 min. Correct and well scoped. One slip: it put new fields between a Javadoc and the
   field the Javadoc described.
2. **Press-highlight experiment** (a RenderNode overlay that animates the pressed cap without
   re-recording the keyboard, behind a runtime switch). 126k / 39 / 8.2 min. It found the real
   per-frame cause (a scale on the whole cap) before writing code. The overlay was pixel-identical
   on the device, and it chose `legacy` as the default because it could not verify that. It
   reported honestly that the third item ("refresh runs 10 times a frame") was one refresh per
   surface, but still shipped a gate that saved nothing. The caller dropped that commit.
3. **Overlay default plus a Buffer Stuffing root-cause** from existing Perfetto traces. 101k / 34 /
   6.6 min. Strong analysis: it read AOSP's classifier, joined frames to display frames, measured
   the standing queue and the platform offsets, and ruled out GPU composition and refresh switching.
   It also corrected an earlier mislabel ("presented" was buffer-ready).
4. **Touch-down ADPF hint experiment.** 62k / 23 / 3.4 min. It noticed that `sendHint` is @hide in
   SDK 36 and used reflection with a guarded fallback. On the device, hint sessions turned out to be
   unsupported; it had flagged that as the first thing to verify.
5. **Contour wallpaper-scene prototype** (a new AGSL program, an event-slot model, a Choreographer
   loop, a low-res pass, wiring into the activity). 137k / 38 / 9 min. It compiled and drew on the
   first device run with no crash. It correctly stopped short of the large glass rework and
   described what that rework would take. Design miss: it put the scene inside the launcher window,
   so every scene frame repainted the whole window (+10-15 ms of GPU). The brief didn't forbid
   that, and the caller hadn't foreseen it either.

Verdict: pass on all five. Specified graphics work, and analysis from traces, are within Sonnet's
range. It doesn't foresee a whole-window repaint cost unless the brief names it, and the caller
missed it too.

### Open questions to settle with later briefs

- A change spanning 3+ files with a pure policy class and a test (the `fixer-opus` default).
- Geometry or layout arithmetic (dock bands, pane shapes).
- A bug whose cause is unknown and needs a reproduction on the emulator.
- Review of another worker's diff.
