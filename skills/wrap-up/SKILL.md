---
name: wrap-up
description: Close out a session before the user ends it - land or park this session's branches, remove its worktrees, and update memory. Use when the user says "wrap up", "wrapping up", "closing this session" or similar.
disable-model-invocation: true
---

Close out this session's own work. Touch nothing another session owns.

1. **Branches and worktrees this session created or used.** For each one:
   - merged: remove the worktree and delete the branch;
   - finished but not merged: say so and ask whether to merge it now;
   - unfinished: commit it as WIP on its branch (never on a shared branch), keep it, and note it.
2. **Background work.** Stop any Waydroid, logcat or monitor loop this session started. Stop
   emulators by releasing every `ad` lease this session holds (`ad lease status` marks them
   "(you)"); a release stops the emulator that lease started.
3. **Unpushed commits.** List them per branch; push only if the user says so.
4. **Memory.** Update the project's open-threads memory with anything still open (one line each,
   with the branch name). Save durable facts and decisions; never a status log of what was done.
5. **Report** in five lines or fewer: what landed, what is parked and where, what is unpushed.

Anything left after this is caught by the daily `agent-tidy` timer only once it is merged.
