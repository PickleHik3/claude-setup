#!/usr/bin/env bash
# resume-gate cases: "deny", "context" (allowed with numbers) or "allow" (silent).
cd "$(dirname "$0")" || exit 1
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
S="$T/sess"; mkdir -p "$S/subagents"; : > "$T/sess.jsonl"
export RESUME_GATE_STATE="$T/state"
ago() { date -u -d "@$(( $(date +%s) - $1 ))" +%Y-%m-%dT%H:%M:%S.000Z; }
worker() {  # id seconds-ago context handoff(0/1)
  local hp="$T/handoffs/$1.md" line
  if [[ $4 == 1 ]]; then mkdir -p "$T/handoffs"; echo "# handoff" > "$hp"; fi
  line='{"type":"assistant","timestamp":"'"$(ago "$2")"'","message":{"model":"claude-opus-5-5","usage":{"input_tokens":2,"cache_creation_input_tokens":1000,"cache_read_input_tokens":'"$3"'},"content":[{"type":"tool_use","name":"Write","input":{"file_path":"'"$hp"'"}}]}}'
  printf '%s\n' "$line" > "$S/subagents/agent-$1.jsonl"
}
fail=0
check() {  # name expected to
  out=$(printf '%s' '{"tool_name":"SendMessage","session_id":"sess","transcript_path":"'"$T"'/sess.jsonl","tool_input":{"to":"'"$3"'","message":"x"}}' | python3 resume-gate.py)
  got=allow; [[ $out == *additionalContext* ]] && got=context; [[ $out == *'"deny"'* ]] && got=deny
  if [[ $got == "$2" ]]; then echo "ok   $1 -> $got"; else echo "FAIL $1: wanted $2, got $got ($out)"; fail=1; fi
}
worker warm 60 200000 1;    check "warm worker" allow warm
worker cold 600 200000 1;   check "cold, handoff, big" deny cold
                            check "same send again" allow cold
worker nohand 600 200000 0; check "cold, no handoff" context nohand
worker small 600 20000 1;   check "cold, small context" context small
check "prefix of a decided worker" allow col   # only agent-cold matches, already denied once
worker uniq123 600 200000 1; check "unique prefix" deny uniq
check "unknown worker" allow nobody
exit $fail
