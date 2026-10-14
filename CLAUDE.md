# Delegation (main session is the orchestrator)

Goal: the least usage and the smallest main-session context that still gets the work right.
Delegate when a worker saves more reading than its startup costs (about 10k tokens); small edits
in files already in context stay here.

| Agent | Model | Use for |
|---|---|---|
| Explore | Haiku, low | Read-only: search, read code, logs or docs, return the conclusion. |
| fixer | Sonnet, medium | A specified change, docs, mechanical edits; device-check driving. |
| fixer-opus | Opus, high | Geometry, layout, design, policy with arithmetic, diff review, bugs whose cause is unknown. |

- Subagents never run on Fable, even when this session does. Fable is the main session's model
  only, chosen by the user.
- Workers may spawn Explore for wide reading and nothing else; Explore spawns nothing. The
  model-gate hook enforces both.
- Workers never use skills.
- Effort stays at the agent's default; raise it for one hard task, never as a habit.

# Worktree round trip

1. Commit before delegating. Workers branch from this session's HEAD only when the project sets
   `worktree.baseRef: head` (otherwise from origin/main). Never ask a worker to reset or checkout.
2. Parallel workers get disjoint file sets; otherwise run them one after another.
3. Workers compile their module and run only the test class they wrote. After the report, read
   the full diff and list what is wrong or less ideal before merging (--no-ff or --squash).
4. Verify once, here: run the project's build/test into a log file, have Explore report only the
   failures with file:line.
5. Remove the worktree and delete the branch. `/wrap-up` does this before a session closes.
- A brief states the goal and the method separately; workers stop and report when the method
  contradicts the goal.

# Brief template (every delegation)

Goal · Files in scope · Constraints · What is already known · Report format (branch, hash, files,
verify-first, device checks owed — recorded where the project says)

# Lavish

Lavish runs only in this main session, never from a worker. The moment the server prints the URL,
paste it into chat, before polling.
