#!/usr/bin/env bash
# Link this repo's files into place (safe to re-run), fetch the third-party skills, and copy the
# managed settings (needs sudo). Existing real files are moved aside to <name>.bak first.
set -euo pipefail
R="$(cd "$(dirname "$0")" && pwd)"
link() { # <repo path> <target>
  mkdir -p "$(dirname "$2")"
  if [ -e "$2" ] && [ ! -L "$2" ]; then mv "$2" "$2.bak"; echo "moved aside: $2.bak"; fi
  ln -sfn "$R/$1" "$2"; echo "linked $2"
}
link CLAUDE.md ~/.claude/CLAUDE.md
for f in "$R"/agents/*.md; do link "agents/$(basename "$f")" ~/.claude/agents/"$(basename "$f")"; done
link hooks/model-gate.py ~/.claude/hooks/model-gate.py
for s in "$R"/skills/*/; do s="$(basename "$s")"; link "skills/$s" ~/.claude/skills/"$s"; done
link bin/agent-tidy ~/.local/bin/agent-tidy
for u in agent-tidy.service agent-tidy.timer reports-http.service; do link "systemd/$u" ~/.config/systemd/user/"$u"; done
[ -f ~/.config/ad/targets ] || { mkdir -p ~/.config/ad; cp "$R/ad/targets.example" ~/.config/ad/targets; echo "edit ~/.config/ad/targets"; }

# Third-party skills, fetched from their own repos rather than republished here.
fetch_skill() { # <name> <repo> <path in repo>
  local dst=~/.claude/skills/$1 tmp; [ -e "$dst" ] && return
  tmp="$(mktemp -d)"; git clone -q --depth 1 "$2" "$tmp" && cp -r "$tmp/$3" "$dst"; rm -rf "$tmp"
  echo "fetched $1 from $2"
}
fetch_skill pixel-perfect     https://github.com/Yu-369/VibeCurb skills/pixel-perfect
fetch_skill visual-redesign   https://github.com/Yu-369/VibeCurb skills/visual-redesign
fetch_skill imagegen-frontend https://github.com/Yu-369/VibeCurb skills/imagegen-frontend

sudo install -Dm644 "$R/managed-settings.json" /etc/claude-code/managed-settings.json
systemctl --user daemon-reload
systemctl --user enable --now reports-http.service
tailscale serve --bg --set-path /reports http://127.0.0.1:8787 || echo "tailscale serve failed: run 'sudo tailscale set --operator=$USER' once, then re-run"
echo "done. The agent-tidy timer is off: systemctl --user enable --now agent-tidy.timer"
