# Delegation

The main session orchestrates; the goal is the least usage and the smallest main context that
still gets the work right. Delegate when a worker saves more reading than its startup costs
(about 10k tokens); small edits in files already in context stay here.

| Agent | Model | Use for |
|---|---|---|
| Explore | Haiku | Read-only search and reading; returns the conclusion with `path:line`. |
| fixer | Sonnet | A specified change, docs, mechanical edits. |
| fixer-opus | Opus | What `notes/model-performance.md` shows Sonnet failing at. |
| device-checker | Sonnet | Batched functional checks on a device, from a user-facing summary. |

- Since 2026-10-22, hand `fixer` the harder tasks too, one notch at a time, to find Sonnet's limit;
  log each outcome in `notes/model-performance.md` (this repo).
- Subagents never run on Fable; Fable is the main session's model, chosen by the user. Workers may
  spawn only Explore; Explore spawns nothing. `hooks/model-gate.py` enforces both.
- Effort stays at the agent's default; raise it in the brief for one hard task only.
- Reuse a worker per area of code (SendMessage keeps what it has read); retire it when it compacts
  or the area changes.

# Briefs

Goal · files in scope with the method names and line numbers to edit (verified at the base
commit) · constraints · what is known, including the cause for a fix · report format.

- One goal per brief. Builders build: cause-finding goes to Explore or a reproduction first. When
  the cause is unclear or one fix has already missed, reproduce it and put that in the brief.
- State the goal and the method separately; the worker stops and reports if they contradict.
- Media never goes to a worker; the brief carries the numbers or timeline read from it.
- If a worker cannot pin a runtime cause, it commits temporary tagged logging as its own commit;
  this session builds and installs that branch, reproduces once with `adb logcat -s <tag>`, and
  sends the lines back. The fix goes on top and the log is reverted, never merged.

# Worktrees and merging

1. Commit before delegating. With `worktree.baseRef: head`, a worker's worktree is cut from the
   HEAD of the worktree this session is in, and the session's cwd can silently reset to the main
   checkout after a background command. Every brief names the expected base hash and tells the
   worker to stop if `git merge-base --is-ancestor <hash> HEAD` fails. When it matters, create the
   worktree yourself (`git worktree add -b <branch> <path> <base>`) and spawn the worker without
   isolation, told to work in that path.
2. A worker that stops with no commits loses its worktree; continue it with a fresh spawn, not
   SendMessage, or it edits this session's tree.
3. One worker per seam (one file, one view hierarchy, one hook); parallel workers only on disjoint
   modules.
4. Before merging, read the worker's report and `git diff --stat`. Read the full hunks only where
   the report flags something ("outside the brief", "verify first", a failed or skipped check) or
   for geometry and layout work from `fixer`. Say in the merge what you read.
5. After merging, run the project's build and tests once into a log; have Explore report only the
   failures. Then remove the worktree and branch (`/wrap-up` does this at session end).
- Never switch branches in a shared main checkout, and address other worktrees with `git -C
  <path>` in background chains.

# Seeing the work

- For a visual change, look at the result yourself before calling it done; a checker's "passed" is
  a claim. Before/after comparisons are for changes whose look is the point, not every tweak.
- The user's phone is the truth for layout and motion; emulators differ in width, font scale,
  wallpaper and permissions. When the user has allowed the phone for a piece of work, a build goes
  on it after each wave, not only at the end.

# Asking and showing

- Grilling (`grilling`, `grill-me`, `grill-with-docs`) asks through AskUserQuestion: one question
  per decision, the recommended option first marked "(Recommended)", a `preview` for mockups.
- To show images in herdr: `herdr pane split --current --direction down --cwd "$PWD" --no-focus`,
  then `herdr pane run <id> "timg -pk --title --grid=2 a.png b.png"`; close the pane after.
  Outside herdr (`$HERDR_PANE_ID` empty), say where the images are.
- Lavish runs only in the main session; paste its URL into chat as soon as it prints.
- Discord: sessions started with `--channels plugin:discord@claude-plugins-official` are reachable
  from DMs; setup is in `notes/discord-channel.md`.
