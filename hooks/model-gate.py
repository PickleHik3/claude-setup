#!/usr/bin/env python3
"""PreToolUse gate on Agent/Workflow: who may spawn which model.

- The main session may spawn anything except Fable (model param, agent frontmatter, or a fork
  while the main session itself runs Fable). Fable is for the main session only, chosen by the user.
- A subagent may spawn only the Explore agent (Haiku); nothing else, and no model override.
- The one exception is the `lead` agent (Opus): it may also spawn `fixer` and `device-checker`,
  with no model override, so it can run one wave of work and hand back a single report. A lead
  never spawns another lead or `fixer-opus`.
- A Workflow is denied when a model is set to Fable (a `model` option in its script, or a `model`
  key anywhere in its input; merely mentioning Fable in a prompt is allowed). From a main session
  that runs Fable, or whose model cannot be read, it is also denied unless every `agent(` call in
  its script names a model: a workflow agent with no model runs on the session's model.

These are this setup's policies; Claude Code itself allows any of it. The gate fails closed: an
error inside it denies the call, because a gate that lets a call through when it breaks is no gate.

What it relies on, checked on Claude Code 2.1.322 (2026-11-10): a tool call made by a subagent
carries `agent_id` and `agent_type`, and `agent_type` is the agent's name ("fixer", "lead"); the
Agent tool's input has `subagent_type` (with "fork" for a fork) and `model`. The main session's
model is read from the transcript's JSON lines, whose shape is not documented and may lag a turn,
so an unreadable model is treated as Fable.
"""
import json, os, re, sys

NESTED_OK = {"Explore"}
LEAD_OK = {"Explore", "fixer", "device-checker"}


def agent_dirs(cwd):
    """Where an agent file may live: every .claude/agents from cwd upward, then the user's."""
    d = os.path.abspath(cwd or ".")
    while True:
        yield os.path.join(d, ".claude", "agents")
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if config:
        yield os.path.join(os.path.expanduser(config), "agents")
    yield os.path.expanduser("~/.claude/agents")


def frontmatter_model(name, cwd):
    for d in agent_dirs(cwd):
        p = os.path.join(d, f"{name}.md")
        if os.path.isfile(p):
            try:
                head = open(p).read().split("\n---", 1)[0]
            except OSError:
                return None
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


def model_values(obj):
    """Every string stored under a `model` key, at any depth."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "model" and isinstance(v, str):
                yield v
            else:
                yield from model_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from model_values(v)


def workflow_uses_fable(ti):
    script = ti.get("script")
    if isinstance(script, str) and re.search(r"""model\s*[:=]\s*['"][^'"]*fable""", script, re.I):
        return True
    return any("fable" in v.lower() for v in model_values(ti))


def workflow_script(ti):
    script = ti.get("script")
    if isinstance(script, str):
        return script
    path = ti.get("scriptPath")
    if isinstance(path, str):
        try:
            return open(os.path.expanduser(path)).read()
        except OSError:
            return None
    return None


def workflow_names_every_model(ti):
    """True when the script can be read and has a `model` option for each `agent(` call."""
    script = workflow_script(ti)
    if script is None:
        return False
    agents = len(re.findall(r"\bagent\s*\(", script))
    models = len(re.findall(r"\bmodel\s*:", script))
    return models >= agents


def session_may_be_fable(d):
    model = main_model(d.get("transcript_path", ""))
    return not model or "fable" in model


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
        if workflow_uses_fable(ti):
            return deny("Workflow agents never run on Fable; use opus, sonnet or haiku.")
        if session_may_be_fable(d) and not workflow_names_every_model(ti):
            return deny("This session runs Fable (or its model could not be read), and a workflow "
                        "agent with no model runs on the session's model. Give every agent() call "
                        "a model (opus, sonnet or haiku) and pass the script inline.")
        return
    if tool != "Agent":
        return

    st = ti.get("subagent_type") or ""
    model = (ti.get("model") or "").lower()

    if nested:
        if st in NESTED_OK and model in ("", "haiku"):
            return
        if d.get("agent_type") == "lead":
            if st in LEAD_OK and not model:
                return
            return deny("A lead may spawn only fixer, Explore and device-checker, with no model "
                        "override. Do the rest yourself or return it under 'Decisions needed'.")
        return deny("A subagent may spawn only the Explore agent (Haiku) for reading, with no model "
                    "override. Do the work yourself or report what you need to the main session.")

    if "fable" in model:
        return deny("Subagents never run on Fable. Use fixer-opus, or model 'opus'.")
    if st == "fork":
        if session_may_be_fable(d):
            return deny("A fork inherits this session's model, which is Fable or could not be "
                        "read. Use fixer-opus or general-purpose with model 'opus' instead.")
        return
    if st and "fable" in (frontmatter_model(st, d.get("cwd", ".")) or ""):
        return deny(f"Agent '{st}' runs on Fable; subagents never do. Use fixer-opus instead.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # fail closed: a broken gate must not wave a call through
        deny(f"model-gate.py failed ({type(e).__name__}: {e}); the call is denied until the "
             "gate is fixed. Run hooks/test_model_gate.sh in the claude-setup repo.")
