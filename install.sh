#!/usr/bin/env bash
# Install the Claude orchestration setup into the Claude config directory (safe to re-run).
#   ./install.sh [--android]
# The config directory is $CLAUDE_CONFIG_DIR when set, else ~/.claude. Run it once per profile:
#   CLAUDE_CONFIG_DIR=~/.claude_work ./install.sh
# Touches only that directory, ~/.local/bin, ~/.config/systemd/user and ~/.config/ad.
# Existing real files are moved aside to <name>.bak before a link replaces them.
# CLAUDE_SETUP_NO_SYSTEM=1 skips the plugin install and systemctl (for testing).
set -euo pipefail

ANDROID=0
for a in "$@"; do
  case "$a" in
    --android) ANDROID=1 ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "unknown option: $a (usage: ./install.sh [--android])" >&2; exit 2 ;;
  esac
done

R="$(cd "$(dirname "$0")" && pwd)"
CLAUDE="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CLAUDE="${CLAUDE%/}"
UNITS="$HOME/.config/systemd/user"

link() { # <repo path> <target>
  mkdir -p "$(dirname "$2")"
  if [ -e "$2" ] && [ ! -L "$2" ]; then mv "$2" "$2.bak"; echo "moved aside: $2.bak"; fi
  ln -sfn "$R/$1" "$2"; echo "linked $2"
}

# 1. Core links.
link CLAUDE.md "$CLAUDE/CLAUDE.md"
link agents/Explore.md "$CLAUDE/agents/Explore.md"
link agents/lead.md "$CLAUDE/agents/lead.md"
link hooks/model-gate.py "$CLAUDE/hooks/model-gate.py"
link skills/wrap-up "$CLAUDE/skills/wrap-up"
link skills/delegating "$CLAUDE/skills/delegating"
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
python3 - "$SETTINGS" "$CLAUDE" <<'PY'
import json, shutil, sys
path, config_dir = sys.argv[1], sys.argv[2]
with open(path) as f:
    text = f.read()
data = json.loads(text) if text.strip() else {}
shutil.copyfile(path, path + ".bak")
env = data.setdefault("env", {})
env["CLAUDE_CODE_SUBAGENT_MODEL"] = "sonnet"
# main -> lead -> fixer -> Explore is three deep.
env["CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"] = "3"
pre = data.setdefault("hooks", {}).setdefault("PreToolUse", [])
gates = [h for entry in pre for h in entry.get("hooks", [])
         if "model-gate.py" in h.get("command", "")]
if not gates:
    # The path is written out, so the hook runs the same whichever profile starts the session.
    gate = {"type": "command",
            "command": 'python3 "%s/hooks/model-gate.py"' % config_dir,
            "timeout": 10}
    pre.append({"matcher": "^(Agent|Workflow)$", "hooks": [gate]})
    gates = [gate]
for gate in gates:
    # A gate that crashes or times out blocks the call instead of letting it through.
    gate["onFailure"] = "block"
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
