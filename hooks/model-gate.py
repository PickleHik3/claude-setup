#!/usr/bin/env python3
"""PreToolUse gate on Agent/Workflow: who may spawn which model.

- The main session may spawn anything except Fable (model param, agent frontmatter, or a fork
  while the main session itself runs Fable). Fable is for the main session only, chosen by the user.
- A subagent may spawn only the Explore agent (Haiku); nothing else, and no model override.
"""
import json, os, re, sys

NESTED_OK = {"Explore"}


def frontmatter_model(name, cwd):
    for d in (os.path.join(cwd, ".claude", "agents"), os.path.expanduser("~/.claude/agents")):
        p = os.path.join(d, f"{name}.md")
        if os.path.isfile(p):
            head = open(p).read().split("\n---", 1)[0]
            m = re.search(r"^model:\s*(\S+)", head, re.M)
            return m.group(1).lower() if m else None
    return None


def main_model(transcript):
    """The model of the main session's latest assistant message, from the transcript."""
    model = ""
    try:
        for line in open(transcript):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("type") == "assistant" and not e.get("isSidechain"):
                model = (e.get("message") or {}).get("model") or model
    except OSError:
        pass
    return model.lower()


def deny(reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}, sys.stdout)


def main():
    d = json.load(sys.stdin)
    tool, ti = d.get("tool_name"), d.get("tool_input") or {}
    nested = bool(d.get("agent_id"))

    if tool == "Workflow":
        if nested:
            return deny("Subagents do not run workflows; report back and let the main session decide.")
        if re.search(r"fable|solver", json.dumps(ti), re.I):
            return deny("Workflow agents never run on Fable; use opus, sonnet or haiku.")
        return
    if tool != "Agent":
        return

    st = ti.get("subagent_type") or ""
    model = (ti.get("model") or "").lower()

    if nested:
        if st in NESTED_OK and model in ("", "haiku"):
            return
        return deny("A subagent may spawn only the Explore agent (Haiku) for reading, with no model "
                    "override. Do the work yourself or report what you need to the main session.")

    if "fable" in model:
        return deny("Subagents never run on Fable. Use fixer-opus, or model 'opus'.")
    if st == "fork":
        if "fable" in main_model(d.get("transcript_path", "")):
            return deny("A fork inherits this session's Fable model. Use fixer-opus or "
                        "general-purpose with model 'opus' instead.")
        return
    if st and "fable" in (frontmatter_model(st, d.get("cwd", ".")) or ""):
        return deny(f"Agent '{st}' runs on Fable; subagents never do. Use fixer-opus instead.")


if __name__ == "__main__":
    main()
