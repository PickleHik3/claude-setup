# claude-setup

A pure Claude Code orchestration setup. The main session orchestrates and keeps its context small;
`Explore` (Haiku) does the reading, `fixer` (Sonnet) builds by default, `fixer-opus` (Opus)
takes the named cases that need it, and `lead` (Opus) runs one wave of work through fixers and
hands back a single report. A PreToolUse hook enforces who may spawn what: subagents never
run on Fable (the main session's model), a worker may spawn only Explore, and a lead may also
spawn `fixer` and `device-checker`. Everything installs into one
`~/.claude`, with no sudo; the one third-party piece is the mattpocock-skills plugin. An optional Android module adds
device driving for apps.

Start with [docs/orchestration.md](docs/orchestration.md).

## What's here

| Path | What it is |
|---|---|
| `CLAUDE.md` | Global instructions: delegation table, briefs, worktrees and merging |
| `agents/Explore.md` | Read-only scout on Haiku, at medium effort |
| `agents/lead.md` | Opus lead for one wave: decides, briefs fixers, checks them, reports once |
| `agents/fixer.head.md`, `fixer-opus.head.md`, `fixer.body.md` | Parts of the two builder agents; the installer joins head and body into `fixer.md` and `fixer-opus.md` |
| `hooks/model-gate.py` | PreToolUse gate on `Agent` and `Workflow` calls |
| `docs/orchestration.md` | How the pieces fit together |
| `skills/delegating/` | Loaded before a brief or a merge: the parts of a brief, worktree rules, the merge review |
| `skills/wrap-up/` | `/wrap-up`: land or park a session's branches and remove its worktrees |
| `bin/agent-tidy`, `systemd/agent-tidy.*` | Daily cleanup of merged agent worktrees (dry run unless `--apply`; timer off by default) |
| `android/` | Optional module, see below |

## Install

```bash
./install.sh             # core
./install.sh --android   # core plus the Android module
```

It installs into `$CLAUDE_CONFIG_DIR` when that is set and into `~/.claude` otherwise; for
several profiles, run it once per profile, or link each profile's `agents`, `skills`, `rules` and
`CLAUDE.md` to one of them and merge the settings below by hand. It is safe to re-run and touches
only the config directory, `~/.local/bin`, `~/.config/systemd/user` and `~/.config/ad`. Files are symlinked into place; a real file already at a target is moved aside to
`<name>.bak`. It also merges these into `~/.claude/settings.json` (the old file is kept as
`settings.json.bak`, every other key is preserved): `CLAUDE_CODE_SUBAGENT_MODEL=sonnet`,
`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=3` (main, lead, fixer, Explore), the model-gate hook with `onFailure: block`,
and `skillOverrides` setting `mattpocock-skills:diagnosing-bugs` to `user-invocable-only` (its
description matches every bug report and it stops for a scripted reproduction; `/diagnosing-bugs`
still runs it).

`fixer.md` and `fixer-opus.md` are generated files, not links. Edit the parts under `agents/` in
this repo and re-run `./install.sh`.

The agent-tidy timer is off by default: `systemctl --user enable --now agent-tidy.timer`.

## The one dependency

`mattpocock-skills` from the official marketplace, used for grilling. The installer runs
`claude plugin install mattpocock-skills@claude-plugins-official` when `claude` is on your PATH,
and prints the command if that fails.

## Android module

`./install.sh --android` adds:

- `ad` (`android/skills/android-control/`): drives a device over adb. Fast steps (tap, type,
  swipe, look, zoom, frame capture), user conditions (dark mode, font size, locale, airplane),
  installs, logs, and `runas` into a debuggable app. Devices may be local, or named in
  `~/.config/ad/targets` and reached over Tailscale.
- Device leases: one driver per device at a time across sessions; anything that changes a device
  needs its lease.
- An emulator pool of two slots (`android/systemd/`), with a reaper timer that stops an emulator
  left up with no live lease. Enable with `systemctl --user enable --now emu-reaper.timer`; edit
  the unit's AVD names and SDK path for your machine.
- `device-checker` (`android/agents/`): a subagent that checks a change the way an end user meets
  it and reports with evidence. Hand device-level goals to it.
- `android/rules/android.md`: Android rules, linked to `~/.claude/rules/`.

An app opts into faster, cheaper checks with a `docs/agents/device-map.md` in its repository
(package, build and install, how to reach each screen); `ad` and `device-checker` read it when
present. Edit `~/.config/ad/targets` (copied from `android/targets.example`) to name your devices.

## Not included

- Per-account settings beyond the merged keys, and credentials.
- Memory and transcripts.
- The private model-performance ledger.

## What is policy and what is Claude Code

Claude Code allows a subagent on any model and lets subagents spawn subagents up to the spawn
depth. "Subagents never run on Fable", "a worker spawns only Explore" and "a lead spawns only
fixer, Explore and device-checker" are this setup's rules, enforced by `hooks/model-gate.py`, which
fails closed. The model tiers (Haiku reads, Sonnet builds, Opus judges) are a choice, not an
Anthropic recommendation.

Checked on Claude Code 2.1.322. The setup uses `onFailure` on a hook, `maxTurns` and `effort` in
agent files, path-scoped rules, the `agent_type` field of hook input and the Agent tool's
`effort` input; the hooks page gives 2.1.295 as the first version with `onFailure`. Two things it
relies on are not in the docs: the Agent tool's `effort` input (present in the tool's schema) and
the shape of the transcript lines the gate reads the main session's model from.
