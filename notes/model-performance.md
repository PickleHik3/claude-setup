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

### 2026-10-22 · claude-setup · "emulator pool in `ad`: slots, --any leases, boot flock, RAM and 4th-slot guards"

`fixer` (Sonnet 5.5) alone on shell concurrency policy (a `fixer-opus`-grade brief): a slot table
replacing a hard-coded serial across ~10 call sites, cross-session flock spacing launches 20 s
apart, first-free lease selection preferring running slots, per-slot reaper, plus two SKILL.md
edits. 81k tokens, 20 tool calls, 2.9 min. It exercised every non-booting path against a temp
lease dir, added a meminfo override to test the RAM refusal, and named the boot-lock subshell as
the thing to verify first. Diff was idiomatic; only miss: `--any` dies when `ANDROID_SERIAL` names
a phone. Verdict: pass (live boot test by the caller below in the session).

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

### 2026-10-23: termux-launcher, X11 PulseAudio for Linux apps (fixer, Sonnet 5.5)

A specified change across 3 classes plus tests and docs, with the cause and fix design given.
85k / 25 / 3.5 min, then a review round of 22k / 19 / 3.7 min. The first pass was clean code and
tests, but the shell design was wrong: `pulseaudio --start` in the shared runtime dir fails beside
an existing server, and TCP sat on the daemon command line, so one busy port killed the whole
daemon. It flagged the first of these itself as "verify first" without fixing it. The second pass
applied the review exactly, and the emulator confirmed all four cases. It declined the emulator
step, correctly: worker rules forbid adb.
Verdict: pass on code. It does not foresee daemon and process interactions in shell; it names the
risk but does not design around it. Say "design for an already-running instance" in briefs.

### 2026-10-23: termux-launcher, Resize reset (pre) and Keyboard over display rows (fixer, Sonnet 5.5)

Three specified tasks:
1. **The pre port of a store fix.** It added a one-time reset under a shared flag, and changed the
   snapshot restore so the keyboard mode is no longer written when only the default was in effect.
   70k / 21 / 3 min. Correct first time. It flagged what the reset costs a deliberate Resize choice.
2. **A Settings row on pre.** It added a search-landing case in SettingsActivity, unasked and right.
3. **The same row on v2.** It correctly found that v2's settings index needs no code change.

The full suite was green on both branches, and the emulator check of the pre release build passed.
Verdict: pass. Settings rows and small store changes with a clear spec are within Sonnet's range.
Neither row worker noticed the old docs sentence about the Layout editor being stale; the caller
had to point it out.

### Open questions to settle with later briefs

- A change spanning 3+ files with a pure policy class and a test (the `fixer-opus` default).
- Geometry or layout arithmetic (dock bands, pane shapes).
- A bug whose cause is unknown and needs a reproduction on the emulator.
- Review of another worker's diff.

### 2026-10-23: tlstore, herdr built from source for bionic (fixer, Sonnet 5.5)

Two runs. The spike was 97k / 31 tools / 16 min, with no cause given beyond the seccomp kill. It
stopped correctly at the first blocker (build.rs rejects android, the build needs Zig), proposed
options, then got libghostty-vt plus Rust building for both arches when told to go on. It found the
`target_os = "linux"` gating itself, and suggested a sed over a big patch. The wiring run was
134k / 53 tools / 25 min across 9 files (recipe, patch, CI, upstream-watch, tests, docs). The
x86_64 asset worked on the device first time and the suite stayed at 0 failed. It kept
upstream-watch's asset mode covered with a fixture. One miss: it left the launcher script calling
the binary "upstream's own".
Verdict: pass. A cross-compile investigation with unknown blockers is within Sonnet's range when
the brief says to stop at a heavy blocker. It does not reread comments copied verbatim.

### 2026-10-23: #143 status bar row geometry seam (fixer, Sonnet 5.5)

One run, 71k / 23 tools / 2.6 min. Brief gave the three activity sites with their arithmetic and asked
for a pure `rowGeometry` value plus tests, in two commits (module, then activity) so a parallel worker
in the same file could merge first. It reproduced the arithmetic exactly, moved the duplicated `22`
literal to a named constant, wrote three tests over edge × capsule × compact × collapsed × 3 densities,
kept the compare-before-set writes, and reported the two open choices it made (compact = collapsed in the
rest pass; edge passed to the fold pass although rows don't depend on it) and that the value's
`thickness` field is unused by both passes. Merged unchanged.
Verdict: pass. A specified arithmetic seam with named call sites is comfortably within Sonnet's range;
next notch: a seam where the call sites are not listed.

### 2026-10-23: #147 delete the dock icon reflection (fixer, Sonnet 5.5)

One run, 123k / 43 tools / 5 min. Brief gave the owner class, the shader's uniform and draw sites,
the activity's binding sites and the feeding view from a survey. It deleted 800 lines across 10
files, kept the activity in its own commit as asked, fixed five stale test assertions, added a
negative test on the AGSL source, reported which `reflect` references it left and why, and named
two callers (drawnPageOffsetPx, onOverflowPagePositionChanged) that are now unused. Two javadoc
lines rejoined past 100 columns; fixed at merge.
Verdict: pass. A guided deletion across ten files is within range; next notch: a deletion with no
survey, where it must find the owner itself.

## 2026-10-24 night · fixer (Sonnet 5.5) · a new full-screen stepped flow from a spec + wireframe

Task: replace the "Set up Linux apps" preference page with a stepped guide (steps vary by edition
and source, progress pills, Back/Next footer, selection cards with a wrapping badge), keep every
key and the command builder, reword the Input page, docs. One run, 179k / 43 tools / 10 min.
It built the fragment in code (717 lines) plus a pure policy class with tests for step lists per
edition/source and for font scale 1.3/2.0 fit, registered it in SettingsTree, aliased the old
class, and correctly refused the spec's wrong line about the nix edition (no routes → no steps)
instead of inventing one. Not device-checked by it (rules).
Verdict: pass. A new multi-step UI from a wireframe is within range; next notch: a change that
needs an unknown root cause first, or geometry with measured rules.

## 2026-10-24 night · fixer (Sonnet 5.5) · two small fixes (clock meta column, pref default)

Clock widget period stacked over the seconds by reusing the status bar's path, removing the
inline path; found and fixed a dp/sp tracking bug on the way; flagged a width workaround it did
not root-cause. Verdict: pass with a flag.

## 2026-10-24 evening · fixer (Sonnet 5.5) · remove a gating pref, add a gesture switch

Drop the "Swipe down for app drawer" switch (treat the drawer as always on) and add a quick-reply
swipe switch. One run, 75k / 18 tools / 4 min. Brief named the page, the gating sites from a grep and
the quick-reply wiring entry points. It found every gate (including warm-up and the package-change
receivers), gated quick reply at the two decision points so a badged icon behaves as an unbadged one,
fixed three tests and the docs, and flagged the always-true `consumesPackageChanges` change for review.
Left always-true parameters in place because tests implement them, and said so.
Verdict: pass. Next notch: a settings change where the gate sites are not surveyed in the brief.

## 2026-10-24 evening · fixer (Sonnet 5.5) · editor hidden-items stack (geometry + drag + per-half state)

Two parts: 3-choice segment rows inline with shrunk text, folder-limit removal; then a stack of
equal cards left of the live frame listing hidden items, frame shifted right, drag to hide/show,
Home and Workspace always separate. One run, 215k / 67 tools / 14 min. It found why Numerals went
inline (2 choices only), added a pure HiddenStackPolicy (card size, shared label fit) with tests,
a Reserve on EditorFramePose for the shift, and a lazy "own Home layout" fork before the first
hide/show. Gaps it reported itself: Search field and Drawer tile can't be dragged (no canvas block),
and the shrink applies to every 3-choice row, not only the two asked for. Not yet device-checked.
Verdict: pass with gaps (pending device check). Geometry with measured rules plus drag wiring is
reachable; it narrowed scope where the canvas lacked a block instead of building one.

## 2026-10-24 evening · fixer (Sonnet 5.5) · built-in widget settings sheet, two rounds

Round 1 from a written spec (compact dialog, X, single Save, ⓘ help, Additional clocks): 86k / 21
tools / 5 min, clean diff, tests green; icon right edges off by 5–14dp and sections too loose, fixed
by hand after measuring. The developer then rejected the spec's direction for their own mockup.
Round 2, resumed with the mockup image + Codex glyphs: 165k / 33 tools / 11 min. It rebuilt the
sheet as a BottomSheetDialog of cards, matched the mockup closely, and on its own added a
Robolectric native-graphics preview PNG, which replaced emulator checks. Flagged honestly that
filled MaterialButtons drew invisible text under Robolectric and worked around it. Three small
deviations (chevron direction, tile tint, title gap) fixed at review.
Verdict: pass. A mockup-matched UI rebuild is within range when the image is in the brief; next
notch: geometry with measured rules and no image.

## 2026-10-24 — fixer (Sonnet 5.5): dev patch, headless X test display + pinned wrapper download
Port of a bash script change (free display pick, reliable server stop on every exit path, sha256-
pinned download routed into existing cleanup) plus a three-path Java guard, with the method fully
specified in the brief. Clean, shellcheck-clean, tests added, honest about what it could not check.
One miss at review: the fallback `pkill -f "…:$N -ac"` also matched `:1N`.
Verdict: pass. Specified multi-file shell+Java patches are in range; next notch: one where the
method has to be derived (e.g. reading native code to answer a behavioural question).

- 2026-10-25 fixer (Sonnet 5.5), unknown-cause regression (keyboard/extra-keys glass cut after a dock merge), diagnosed by reading diffs: found a coherent cause (stale card rect shaping shared glass with the keyboard up), small fix, said plainly it was unreproduced; skipped the unit test, citing another worker's file ownership. Outcome: FAIL on pong — the real cause was the host glass layers laid out at the card inset (32,95), which a dumpsys of the view tree showed at once; the code-reading theory was plausible but wrong. Lesson: for a visual regression, give fixer a view-tree dump, not only diffs.

## 2026-10-25 · fixer (Sonnet 5.5) · extra keys editor rebuilt to wireframes + unknown-cause bug

Brief: find why Page 2 can't take a new key (cause unknown), then rebuild a 940-line settings editor
to a five-screen HTML wireframe, with pure draft logic. One run, 243k / 84 tools / 18 min. It drove
the old editor's Page 2 path in Robolectric and said plainly it could not reproduce the bug rather
than inventing a cause. The rebuild was clean: a pure ExtraKeysDraft with Undo snapshots, picker
catalog, option sheets, tests, and native-graphics renders of every screen in both themes. It
reported every spec deviation honestly. Review fixes, made by hand: the drag handle used a 3-bar
icon that read as the ⋮ beside it; Reset sat on its own line because it assumed an app-bar action
needed SettingsActivity changes (a fragment MenuProvider does it); an empty page still needed
"Add row" before any + showed, which is the reported trap again.
Verdict: pass with review fixes. A mockup-matched rebuild of a whole screen is in range; it misses
framework shortcuts (MenuProvider) and judges by "matches the spec" more than "solves the complaint".

## 2026-10-25 · fixer (Sonnet 5.5) · VN CRM ticket 37: hand-over from the access list (page + policy + server API)
Brief gave the goal and pointed at the files; the method was half-derived (it found `takers` in vn_staff_read itself,
extended vn_access_change with a param instead of bypassing it, and kept decide-before-write). 138k / 43 tools / 6 min.
Offline driver + 126 staff harness checks green; reported plainly that the live write path is untested. Review found
nothing to fix. Verdict: pass. A specified multi-file feature across JS page, pure policy and RestrictedPython API is in
range; next notch: a feature where the brief gives only the goal and no file pointers.

## 2026-10-25 · fixer (Sonnet 5.5) · VN CRM Deal Export/Import buttons (Frappe source research + perms ownership)
Brief named goal, a few files and where to read Frappe's installed source; the method was mostly derived. 81k / 25 tools /
2 min. It found by reading data_import.py that Deal's DocType-level allow_import was off (would have failed even with the
right), and that the seed never overwrites existing perm rows, so it introduced a code-owned flag rather than a silent no-op.
Reported plainly what was unverified (rendering, dialog). Review found nothing to fix before live.
Verdict: pass. Research-then-build against third-party framework source is in range; next notch: goal-only brief, no files.

## 2026-10-25 · fixer (Sonnet 5.5) · Termux Launcher power-user round, wave 1 (four tasks)
- Drawer hides Home (Host seam + pure policy): 78k / 23 tools / 4 min. Chose alpha on the whole widget pane to avoid
  colliding with page-transition alphas on its children, and flagged that float panes fade too. Review: nothing to fix.
- Widget picker under the dock: 63k / 10 tools / 4 min. Found the real cause (picker MATCH_PARENT in the pane, dock band
  only given to grid and dots) and reused the measured reserve. Admitted it did not compare with other sheets as asked.
  Side effect it did not mention: the scrim no longer covers the dock, so the dock stays tappable. Pass.
- Theme hint bubble: 84k / 21 tools / 4 min. Clean; kept the pref out of backups via the existing first_run_ prefix.
  Minor: hint appears at full alpha while the bar fades in. Pass.
- Hardware keys (the notch-harder task, cause unknown, brief's suspected cause wrong): 98k / 29 tools / 5 min. Could
  not reproduce in Robolectric, stopped as told, and showed with file:line why the brief's hypothesis was wrong, then
  named the likelier cause (focus on a third view) and a real gap in the Android-keyboard field. Pass: stop-and-report
  on a wrong hypothesis is in range.
- Accessibility (ExploreByTouchHelper on a drawn palette + popup window): 156k / 40 tools / 7 min. Correct virtual-view
  tree, invalidation only on content change, separate strings file to avoid parallel conflicts; honest that the popup
  fix is unconfirmed. Pass.
Verdict: all four in range. Next notch: a cause-unknown task that needs a device-level reproduction.

## 2026-10-25 · fixer (Sonnet 5.5) · Termux Launcher follow-ups + pin requests (goal-only notch)
- Contrast level + dim blend (arithmetic in a pure policy, renderer wiring): 96k / 21 tools / 4 min. Correct mapping from
  the existing contrast levels, flagged a real WCAG edge (saturated hues) honestly. Pass.
- A–Z warm on touch: 93k / 21 tools / 4 min. Reused the existing prefetch and budgeted cache instead of new machinery;
  fixed the side finding. Pass.
- Drawer arrow-key highlight in three view types (a previous Sonnet called it too large): 116k / 19 tools / 5 min. Did
  all three; one misplaced Javadoc. Pass.
- Lock layout switch: replaced the existing lock rows rather than adding a second control (good judgement) but shipped a
  half-width row that clipped and a card that slid off on toggle; both found on the emulator and fixed by hand. Pass with
  fixes: it does not check bottom-sheet behaviour when content height changes.
- Settings reopen timer: found the older 30-minute persisted stack itself and gated it. Pass.
- Pin requests, goal-only brief (manifest, confirm activity, placement, widget bind, target-28 reasoning): 213k / 50 tools
  / 11 min. Flow and per-edition handling right; it built a legacy INSTALL_SHORTCUT receiver it knew could never fire and
  accepted before writing. Both fixed on a review round. Pass with review fixes. Next notch: a goal-only brief that needs
  a device-level reproduction.
- 2026-10-26 editor redesign, wave 1 emulator fixes (fixer / Sonnet 5.5): four findings, causes unknown in the brief
  (door lost on page switch, dark-theme label ink, door table change, shared Frost key): 85k / 30 tools / 6 min. Found
  all four causes, fixed at the seams with tests, no scope creep. The Frost fix keeps per-half position in a
  session-only map (a workaround it flagged itself). Pass. Next notch: a geometry change with screenshots to match.
- 2026-10-26 editor redesign, migration test fallout (fixer / Sonnet 5.5): brief guessed a wrong cause; it found the real
  one (grid left in shared keys nobody reads after v14, a user-facing bug), fixed in the migration only: 51k / 11 tools
  / 2 min. Pass. Notch: unknown-cause test failure with a misleading hint.
- 2026-10-26 editor redesign, wave 2a emulator fixes (fixer / Sonnet 5.5): four unknown-cause UI findings (label ink
  under theme dim, reset no-op on two cards with two separate causes, tooltip on a non-clickable view, a readback
  that was not a bug): all four diagnosed right, scoped fixes, tests; it listed what reset still misses. Pass.
- 2026-10-26 editor redesign, wave 2 emulator fixes (fixer / Sonnet 5.5): theme-dark ink (found: label sampled only
  when the editor paints the wallpaper), bars drag (no fault found, hardened honestly and said so), tile heights,
  shortcut tile: 82k / 23 tools / 4 min. Pass; declined the bigger ChipsRow redraw and asked. Notch for next time: a
  drag/touch bug it must reproduce under instrumentation before fixing.
- 2026-10-26 editor redesign, dock command-palette tile (fixer / Sonnet 5.5, a new dock element across designs):
  followed the Drawer-tile pattern, pure policy + tests, honest about the one geometry gap (bead pinning only pins one
  tile, so its tile slides mid-swipe) and left it. Pass with a geometry follow-up for Opus.
- 2026-10-26 editor redesign, wave 4b icons/words sweep (fixer / Sonnet 5.5, app-wide, 21 files + docs): correct
  reading of "which icon means what", drew two 24dp glyphs itself, kept proper nouns, confirmed a door instead of
  changing it. Pass; glyph legibility owed on device.
- 2026-10-26 editor redesign, Change wallpaper tile (fixer / Sonnet 5.5): clean, followed the shortcut-tile pattern, left
  dead code deliberately to avoid another worker's files and said so. Pass.
- 2026-10-26 editor redesign, page-label ink (fixer-opus): asked to reproduce on the emulator; refused per its rules +
  the 10-24 ban memory, fixed from code with a plausible root cause (storage permission denies the wallpaper read).
  Note: briefs that need a device must go to device-checker, or the rule must say the developer allowed it.
