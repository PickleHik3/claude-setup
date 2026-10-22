# claude-setup

My Claude Code setup: the global instructions, agents, hooks, skills and helpers, kept in one place
so they can be versioned and reinstalled. `install.sh` symlinks everything into place, so editing a
file here and editing it under `~/.claude` are the same thing.

## What's here

| Path | What it is |
|---|---|
| `CLAUDE.md` | Global instructions: the main session orchestrates; Explore (Haiku), fixer (Sonnet) and fixer-opus (Opus) do the work |
| `agents/` | `Explore` (read-only Haiku scout), `fixer`, `fixer-opus` (worktree workers), `device-checker` (black-box Android checks) |
| `hooks/model-gate.py` | PreToolUse gate: subagents never run on Fable; a subagent may spawn only Explore |
| `managed-settings.json` | Installed to `/etc/claude-code/` so every account shares it: subagents default to Sonnet, nest at most 2 deep, and pass the model gate |
| `skills/android-control` | `ad`: drive Android devices over adb, with per-device leases so sessions don't collide, `ad run` (mobilerun) and `ad codex` goal agents, zoom/frame capture, `ad runas` |
| `skills/wrap-up` | `/wrap-up`: land or park a session's branches, remove its worktrees, update memory |
| `bin/agent-tidy`, `systemd/` | Daily cleanup of merged agent worktrees and old work logs (dry run unless `--apply`; timer off by default) |
| `systemd/reports-http.service` | Serves `~/reports` on 127.0.0.1:8787; `tailscale serve` proxies it at `https://<host>.<tailnet>.ts.net/reports/` (tailnet only) |
| `systemd/emu-reaper.*` | Every 5 min, `ad emu reap` stops the emulator once it has been up 15 min with no live `emu` lease (a forgotten release, a killed session) |
| `notes/model-performance.md` | Ledger of what each subagent model did on real briefs; drives the delegation table |
| `ad/targets.example` | Named devices for `ad`; copy to `~/.config/ad/targets` and fill in |

An app opts into faster device checks with a `docs/agents/device-map.md` in its repo (package,
build, how to reach each screen); the skill and `device-checker` read it when present.

## Plugins

- [show-your-work, our fork](https://github.com/PickleHik3/claude-show-your-work) (tag
  `v0.6.3-pk.2`): shows screenshots and plays recordings inline in a kitty-graphics terminal, at no
  token cost. The fork turns telemetry and auto-update off in code and points the prompts at `ad`
  recordings instead of Playwright. Install: `claude plugin marketplace add
  https://github.com/PickleHik3/claude-show-your-work.git#v0.6.3-pk.2`, then
  `claude plugin install show-your-work@picklehik3`.

## Not included

- Third-party skills are fetched by `install.sh` from their sources, not republished:
  `pixel-perfect`, `visual-redesign`, `imagegen-frontend` from
  [Yu-369/VibeCurb](https://github.com/Yu-369/VibeCurb). Also used, installed by their own tools:
  [lavish](https://github.com/kunchenguid) (lavish-axi), terminal-browser, and herdr's Claude hooks.
- Per-account `settings.json`, credentials, memory and transcripts.
