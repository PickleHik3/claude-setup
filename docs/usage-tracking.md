# Usage tracking

`cc-usage` shows, across sessions, what the main chat, leads, fixers, Explore and other
subagents cost in tokens, dollars and time, and whether each worker's task worked. Use it to tune
which model and effort each kind of task gets.

## Use

```bash
cc-usage collect                      # scan transcripts into the database (incremental)
cc-usage outcome <agent-id> pass|review|fail --kind build [--missed TEXT] [--retry-of ID] [--pair ID] [--note TEXT]
cc-usage report [--since 7d|YYYY-MM-DD] [--profile SUBSTR] [--project SUBSTR] [--session ID] [--html PATH]
```

`report` prints: totals by role, totals by profile, workers by role x model x effort x kind, lead waves, cost per
accepted outcome with retries, retries that changed model or effort, pair groups, the ten costliest
agents, and workers with no recorded outcome. `--html` writes one self-contained file (inline SVG,
dark mode, no requests).

The database is `$CC_USAGE_DB`, default `~/.claude-memory/claude-setup/usage.db`. Prices are
`usage/prices.json`, or the file `$CC_USAGE_PRICES`. `collect --reprice` recomputes every cost
after a price change. `collect` reads every Claude Code profile: `~/.claude`, each `~/.claude_*` directory that has a
`projects/` folder, and `$CLAUDE_CONFIG_DIR` if set. To restrict it, set `CC_USAGE_CONFIG_DIRS` to a
colon-separated list of profile directories (it replaces the default list). Each agent records its
profile (the folder name, e.g. `.claude_famn`); `report --profile famn` keeps one profile, and the
report header lists the profiles included. All profiles share the one database. A database made
before profiles existed is upgraded on first use, the profile read back from its stored file paths.
`collect` holds a lock file (`collect.lock` beside the database); a second collect that starts
meanwhile exits quietly, so two hooks firing together cannot collide.

`./install.sh` enables the hook (`hooks/usage-collect.py`, on SessionEnd and SubagentStop, timeout
60) in the profile it installs into, unless that profile's settings already name `usage-collect.py`.
It collects all profiles whichever one ends a session. The first collect reads every
transcript (minutes for several GB); later runs read only what was appended.

## What is measured

Per API request: time, model, effort, the five token buckets (input, 5-minute cache write, 1-hour
cache write, cache read, output) and cost. One response split over several transcript lines is
counted once. Per agent: role (`main` or the agent type), parent, spawn depth, description,
model, effort, start and end, wall time, active time (gaps between consecutive lines, each capped at
300 s), requests and tool calls. A lead's wave is the lead plus every agent below it through
`parentAgentId`.

## How cost is computed

Tokens times the model's price per million, per bucket. Thinking tokens are inside output tokens
and bill as output. A Haiku 5.5 request over 100K prompt tokens (input plus cache read plus cache
write) uses the long-context rates. A request with `speed: "fast"` on Opus 5.5 costs twice and is
flagged. A model id is matched exactly, then without a date suffix; an unknown model has no cost
and a warning, never a guess.

## Limits

- Cost is the API list-price equivalent. On a subscription it is a comparison figure, not a bill.
- Wall time of parallel agents overlaps, so wall times do not add up to the session's length.
  Active time ignores idle gaps over five minutes but still includes waiting on tools.
- An outcome is a judgement, recorded by hand. The latest label for an agent wins.
- The transcript format is undocumented (checked on Claude Code 2.1.330). `collect` warns, with the
  version, when a field it needs is missing; the totals are then low.
- A subagent with no meta file has role `unknown` (or the line's `attributionAgent`) and no parent.
- An outcome recorded before `collect` has seen the agent is matched at report time by id prefix.
