#!/usr/bin/env python3
"""PreToolUse hook on SendMessage: say what resuming a cold worker costs before it happens.

A subagent's prompt cache lives 5 minutes (1 hour if its last request wrote 1-hour entries). A
message to a worker idle longer than that rewrites its whole context at the cache-write price.
This hook reads the worker's own transcript and:

- worker idle under the cache lifetime (minus a margin), or not found: allows silently;
- cold, but no handoff written or context under 60k tokens: allows, with the numbers as context;
- cold, a handoff exists and context is 60k or more: denies once with the numbers and the handoff
  path. The same message sent again goes through, so the main session makes the call.

A handoff is the last file the worker wrote (Write or Edit) under a `handoffs/` directory (the
`delegating` skill names the path in each brief). Decisions and data: docs/orchestration.md,
"Resuming workers".

It is advice, not policy, so it fails open: any error allows the call.

What it relies on, checked on Claude Code 2.1.330 (2026-11-23): the hook input carries
`session_id`, `transcript_path` and `tool_input.to`; a subagent's transcript is
`<transcript dir>/<session_id>/subagents/agent-<id>.jsonl`, with `timestamp` on each line and the
API `usage` on assistant lines. None of this is documented and may change.
"""
import glob, hashlib, json, os, sys, time
from datetime import datetime

MARGIN_S = 30                 # the resume itself takes a moment; treat "almost expired" as cold
MIN_CONTEXT = 60_000          # below this a cold rewrite is cheaper than any fresh spawn
STATE = os.path.expanduser(os.environ.get("RESUME_GATE_STATE", "~/.cache/claude-resume-gate"))
PRICES = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "usage", "prices.json")


def epoch(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def find_transcript(data):
    to = str((data.get("tool_input") or {}).get("to") or "").strip()
    tp = data.get("transcript_path") or ""
    sid = data.get("session_id") or os.path.basename(tp)[:-6]
    if not to or not tp:
        return None, to
    d = os.path.join(os.path.dirname(tp), sid, "subagents")
    exact = os.path.join(d, f"agent-{to}.jsonl")
    if os.path.isfile(exact):
        return exact, to
    hits = glob.glob(os.path.join(d, f"agent-{glob.escape(to)}*.jsonl"))
    return (hits[0], to) if len(hits) == 1 else (None, to)


def read_worker(path):
    last_ts = None; usage = None; model = None; handoff = None
    for line in open(path, errors="ignore"):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        m = o.get("message") or {}
        if o.get("type") != "assistant" or not isinstance(m, dict):
            continue
        if m.get("usage"):
            usage, model = m["usage"], m.get("model")
            if o.get("timestamp"):
                last_ts = epoch(o["timestamp"])
        for b in m.get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Write", "Edit"):
                fp = str((b.get("input") or {}).get("file_path") or "")
                if "/handoffs/" in fp:
                    handoff = fp
    return last_ts, usage, model, handoff


def write_price(model, ttl_1h):
    try:
        models = json.load(open(PRICES))["models"]
        p = models.get(model) or models.get((model or "").rsplit("-", 1)[0])
        return p["cache_write_1h" if ttl_1h else "cache_write_5m"]
    except Exception:
        return None


def out(decision, text):
    key = "permissionDecisionReason" if decision == "deny" else "additionalContext"
    spec = {"hookEventName": "PreToolUse", key: text}
    if decision == "deny":
        spec["permissionDecision"] = "deny"
    print(json.dumps({"hookSpecificOutput": spec}))


def main():
    data = json.load(sys.stdin)
    if data.get("tool_name") != "SendMessage":
        return
    path, to = find_transcript(data)
    if not path:
        return
    last_ts, usage, model, handoff = read_worker(path)
    if last_ts is None or not usage:
        return
    cc = usage.get("cache_creation") or {}
    ttl_1h = bool(cc.get("ephemeral_1h_input_tokens"))
    ttl = 3600 if ttl_1h else 300
    idle = time.time() - last_ts
    if idle < ttl - MARGIN_S:
        return
    ctx = (usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
           + usage.get("cache_read_input_tokens", 0))
    price = write_price(model, ttl_1h)
    cost = f"~${ctx * price / 1e6:.2f}" if price else "unknown cost"
    facts = (f"Worker {to} has been idle {idle / 60:.1f} min; its {ttl // 60}-minute cache has "
             f"expired, so resuming it rewrites its {ctx / 1000:.0f}k-token context ({cost}, {model}).")
    if not handoff or not os.path.isfile(handoff) or ctx < MIN_CONTEXT:
        why = "no handoff on disk" if not handoff or not os.path.isfile(handoff) else "the context is small"
        out("allow", f"{facts} Resumed anyway: {why}.")
        return
    os.makedirs(STATE, exist_ok=True)
    key = hashlib.sha1(f"{path}|{last_ts}".encode()).hexdigest()
    mark = os.path.join(STATE, key)
    if os.path.exists(mark):
        return  # second send for the same cold period: the main session has decided
    open(mark, "w").close()
    out("deny", f"{facts} Its handoff is {handoff}. Decide: start a fresh worker with the handoff "
        "as its brief (cheaper when the follow-up is covered by it), or send the same message "
        "again to resume (right when the follow-up needs what the worker read but the handoff "
        "leaves out). See the delegating skill, 'Resuming a worker'.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open
    sys.exit(0)
