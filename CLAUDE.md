# Delegation (main session is the orchestrator)

Goal: the least usage and the smallest main-session context that still gets the work right.
Delegate when a worker saves more reading than its startup costs (about 10k tokens); small edits
in files already in context stay here.

| Agent | Model | Use for |
|---|---|---|
| Explore | Haiku, low | Read-only: search, read code, logs or docs, return the conclusion. |
| fixer | Sonnet, medium | A specified change, docs, mechanical edits; device-check driving. |
| fixer-opus | Opus, medium | Geometry, layout, design, policy with arithmetic, diff review. Raise to high in the brief for one task with arithmetic or an unknown cause, never as a habit. |

- From 2026-10-22: hand `fixer` (Sonnet 5.5) tasks that would go to `fixer-opus`, one notch harder
  each time, to find its upper limit; keep `fixer-opus` for what `notes/model-performance.md`
  already shows Sonnet failing at. Record every outcome there.
- Subagents never run on Fable, even when this session does. Fable is the main session's model
  only, chosen by the user.
- Workers may spawn Explore for wide reading and nothing else; Explore spawns nothing. The
  model-gate hook enforces both.
- Workers never use skills.
- Effort stays at the agent's default; raise it for one hard task, never as a habit.
- Reuse a worker. One long-lived worker per area of code (SendMessage resumes it with what it has
  read), tasks sent to it one after another; retire it when it compacts or the area changes, and
  start the next with a brief that carries exact anchors. The token figure in a task notice is
  cumulative spend, not the live window; the ceiling that matters is the first compaction.
  2026-10-26: a fresh worker spent about a hundred tool calls finding its way around a 25k-line
  file before its first edit.

# Worktree round trip

1. Commit before delegating. Workers branch from this session's HEAD only when the project sets
   `worktree.baseRef: head` (otherwise from origin/main). Never ask a worker to reset or checkout.
2. One worker per wave, one after another, each cutting from the previous worker's merged
   commit. Parallel workers only for separate modules with disjoint file sets; never two workers
   on one seam (one file, one view hierarchy, one hook). 2026-10-26: three parallel card workers
   on one sheet seam cost two resolver rounds and re-broke rows an earlier worker had tuned.
3. Workers compile their module and run only the test class they wrote. After the report, read
   the full diff and list what is wrong or less ideal before merging (--no-ff or --squash).
4. Verify once, here: run the project's build/test into a log file, have Explore report only the
   failures with file:line.
5. Remove the worktree and delete the branch. `/wrap-up` does this before a session closes.
- A brief states the goal and the method separately; workers stop and report when the method
  contradicts the goal.
- A bug is reproduced before it is fixed. The brief for a fix carries the reproduced failing
  state (screenshot, log line, test or measurement) and what the fixed state must show; a worker
  that cannot reproduce it reports that instead of changing code. 2026-10-26: one label-ink bug
  was "fixed" from code four times; the cause was a missing storage permission, found only once
  it was reproduced.

# Seeing the work (the gate before any merge)

- The main session reads the full diff and opens the screenshots itself before merging; a
  checker's or worker's "passed" is a claim, not a check. The merge message says both were done.
- The user's device is the truth for layout. An emulator pass stands in only for throwaway
  shots; width, font scale, wallpaper and permissions differ on the phone. When the user has
  allowed a device for a named piece of work, a build goes on it after the skeleton wave and after
  each wave, not at the end. 2026-10-26: six waves were emulator-checked before the first phone
  build; the phone showed clipped tiles and wrong ink the emulator never did.
- Fewer layers between the user and the picture: for visual work, no device-checker between a
  worker and this session; the session takes the shots (or has the worker's branch built and
  shot) and compares before/after itself.
- A diagnostic build when the code does not say. If a worker cannot pin a runtime cause from
  reading (it reports a guess, or two fixes have missed), stop guessing: the worker commits
  temporary logging under one tag (uptime, the state that matters, six caller frames) as its own
  commit on its branch; this session builds that branch's APK from the worker's worktree, installs
  it on the phone or the emulator, reproduces once while capturing `adb logcat -s <tag>`, and
  sends the lines back. The log commit is never merged: the fix goes on top and the log is
  reverted in a separate commit. 2026-10-26: two fixes shipped on guesses for a dock that looked
  wrong after a home press; one tagged log showed the Design was right and a stale glass backdrop
  was the cause.

# Brief template (every delegation)

Goal · Files in scope · Constraints · What is already known · Report format (branch, hash, files,
verify-first, device checks owed — recorded where the project says)

- Anchors, not areas: every file in scope comes with the method names and line numbers the
  worker will edit, verified at the base commit by this session or a scout. A file over 5k lines
  gets the exact slice, never "~:23150".
- Builders build. No "find the cause" in a fixer brief; cause-finding goes to Explore or a
  reproduction step first, and the builder gets the cause and the reproduction.
- One goal per brief, and a cap: the worker reports at 60 tool calls even if unfinished. Media
  (recordings, frame dumps, pages) never go to a builder; the brief carries the timeline or the
  numbers read from them.

# Lavish

Lavish runs only in this main session, never from a worker. The moment the server prints the URL,
paste it into chat, before polling.

# Grilling

- `grilling`, `grill-me` and `grill-with-docs` ask each round through AskUserQuestion, not as a
  markdown list: one question per decision (up to 4 per call, more calls for a bigger round), the
  recommended answer as the first option marked "(Recommended)", a `preview` for ASCII mockups or
  code. Plain text only for a question that can't be reduced to options.
- A visual question shows its images first, in a herdr pane stacked below this one (phone-friendly):
  `herdr pane split --current --direction down --cwd "$PWD" --no-focus`, then
  `herdr pane run <pane_id> "timg -pk --title --grid=2 a.png b.png"`. Options name the image by its
  title. Close the pane (`herdr pane close <pane_id>`) once the round is answered. Use `timg -pk`,
  never `kitten`. Outside herdr (`$HERDR_PANE_ID` empty), skip the pane and say where the images are.
