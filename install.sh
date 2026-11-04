#!/usr/bin/env bash
# Install the Claude orchestration setup into ~/.claude (safe to re-run).
#   ./install.sh [--android]
# Touches only ~/.claude, ~/.local/bin, ~/.config/systemd/user and ~/.config/ad.
# Existing real files are moved aside to <name>.bak before a link replaces them.
# CLAUDE_SETUP_NO_SYSTEM=1 skips the plugin install and systemctl (for testing).
set -euo pipefail

ANDROID=0
for a in "$@"; do
  case "$a" in
    --android) ANDROID=1 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "unknown option: $a (usage: ./install.sh [--android])" >&2; exit 2 ;;
  esac
done

R="$(cd "$(dirname "$0")" && pwd)"
CLAUDE="$HOME/.claude"
UNITS="$HOME/.config/systemd/user"

link() { # <repo path> <target>
  mkdir -p "$(dirname "$2")"
  if [ -e "$2" ] && [ ! -L "$2" ]; then mv "$2" "$2.bak"; echo "moved aside: $2.bak"; fi
  ln -sfn "$R/$1" "$2"; echo "linked $2"
}

# 1. Core links.
link CLAUDE.md "$CLAUDE/CLAUDE.md"
link agents/Explore.md "$CLAUDE/agents/Explore.md"
link hooks/model-gate.py "$CLAUDE/hooks/model-gate.py"
link skills/wrap-up "$CLAUDE/skills/wrap-up"
link bin/agent-tidy "$HOME/.local/bin/agent-tidy"
link systemd/agent-tidy.service "$UNITS/agent-tidy.service"
link systemd/agent-tidy.timer "$UNITS/agent-tidy.timer"

# 2. Generated agents: head + shared body, written to a temp file then moved into place
# (which also replaces any old symlink).
mkdir -p "$CLAUDE/agents"
for pair in "fixer:fixer.head.md" "fixer-opus:fixer-opus.head.md"; do
  name="${pair%%:*}"; head="${pair#*:}"
  tmp="$(mktemp "$CLAUDE/agents/.$name.XXXXXX")"
  cat "$R/agents/$head" "$R/agents/fixer.body.md" > "$tmp"
  chmod 644 "$tmp"
  mv -f "$tmp" "$CLAUDE/agents/$name.md"
  echo "generated $CLAUDE/agents/$name.md"
done
echo "note: fixer.md and fixer-opus.md are generated. Edit the agents/fixer*.md parts in the repo and re-run ./install.sh."

# 3. Merge the settings this setup needs, keeping every other key.
SETTINGS="$CLAUDE/settings.json"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
python3 - "$SETTINGS" <<'PY'
import json, shutil, sys
path = sys.argv[1]
with open(path) as f:
    text = f.read()
data = json.loads(text) if text.strip() else {}
shutil.copyfile(path, path + ".bak")
env = data.setdefault("env", {})
env["CLAUDE_CODE_SUBAGENT_MODEL"] = "sonnet"
env["CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"] = "2"
pre = data.setdefault("hooks", {}).setdefault("PreToolUse", [])
has = any("model-gate.py" in h.get("command", "")
          for entry in pre for h in entry.get("hooks", []))
if not has:
    pre.append({"matcher": "^(Agent|Workflow)$",
                "hooks": [{"type": "command",
                           "command": 'python3 "$HOME/.claude/hooks/model-gate.py"',
                           "timeout": 10}]})
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
echo "merged settings into $SETTINGS (previous copy: $SETTINGS.bak)"

# Android module.
if [ "$ANDROID" = 1 ]; then
  link android/agents/device-checker.md "$CLAUDE/agents/device-checker.md"
  link android/skills/android-control "$CLAUDE/skills/android-control"
  link android/rules/android.md "$CLAUDE/rules/android.md"
  for u in "$R"/android/systemd/*; do link "android/systemd/$(basename "$u")" "$UNITS/$(basename "$u")"; done
  if [ ! -f "$HOME/.config/ad/targets" ]; then
    mkdir -p "$HOME/.config/ad"
    cp "$R/android/targets.example" "$HOME/.config/ad/targets"
    echo "created ~/.config/ad/targets: edit it to name your devices"
  fi
fi

# 4 and 5. Plugin dependency and systemd.
if [ "${CLAUDE_SETUP_NO_SYSTEM:-}" != 1 ]; then
  PLUGIN="mattpocock-skills@claude-plugins-official"
  if command -v claude >/dev/null 2>&1; then
    if claude plugin list 2>/dev/null | grep -q "mattpocock-skills"; then
      echo "plugin mattpocock-skills already installed"
    else
      claude plugin install "$PLUGIN" || echo "plugin install failed: run  claude plugin install $PLUGIN"
    fi
  else
    echo "claude not on PATH: later run  claude plugin install $PLUGIN"
  fi
  if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload || echo "systemctl --user daemon-reload failed (no user session?)"
  fi
  echo "The agent-tidy timer is off by default. Enable it with: systemctl --user enable --now agent-tidy.timer"
  if [ "$ANDROID" = 1 ]; then
    echo "Android: enable the emulator reaper with: systemctl --user enable --now emu-reaper.timer"
  fi
fi
echo "done."
