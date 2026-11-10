#!/usr/bin/env bash
# Gate cases: empty stdout = allow, "deny" in stdout = deny.
cd "$(dirname "$0")" || exit 1
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
printf '%s\n' '{"type":"assistant","message":{"model":"claude-fable-5-2"}}' > "$T/fable.jsonl"
printf '%s\n' '{"type":"assistant","message":{"model":"claude-opus-5-5"}}' > "$T/opus.jsonl"
fail=0
check() {  # name expected json
  out=$(printf '%s' "$3" | python3 model-gate.py)
  got=allow; [[ $out == *deny* ]] && got=deny
  if [[ $got == "$2" ]]; then echo "ok   $1 -> $got"; else echo "FAIL $1: wanted $2, got $got"; fail=1; fi
}
check "workflow mentions fable and solver, model sonnet" allow \
  '{"tool_name":"Workflow","transcript_path":"'"$T"'/opus.jsonl","tool_input":{"script":"agent({prompt: \"write a sudoku solver about Fable\", model: '"'sonnet'"'})"}}'
check "workflow model fable" deny \
  '{"tool_name":"Workflow","tool_input":{"script":"agent({prompt: \"x\", model: \"fable\"})"}}'
check "agent from main, model fable" deny \
  '{"tool_name":"Agent","tool_input":{"subagent_type":"fixer","model":"fable"}}'
check "nested Explore" allow \
  '{"tool_name":"Agent","agent_id":"a1","tool_input":{"subagent_type":"Explore"}}'
check "nested fixer" deny \
  '{"tool_name":"Agent","agent_id":"a1","tool_input":{"subagent_type":"fixer"}}'
check "lead spawns fixer" allow \
  '{"tool_name":"Agent","agent_id":"a1","agent_type":"lead","tool_input":{"subagent_type":"fixer"}}'
check "lead spawns device-checker" allow \
  '{"tool_name":"Agent","agent_id":"a1","agent_type":"lead","tool_input":{"subagent_type":"device-checker"}}'
check "lead spawns fixer-opus" deny \
  '{"tool_name":"Agent","agent_id":"a1","agent_type":"lead","tool_input":{"subagent_type":"fixer-opus"}}'
check "lead spawns lead" deny \
  '{"tool_name":"Agent","agent_id":"a1","agent_type":"lead","tool_input":{"subagent_type":"lead"}}'
check "lead spawns fixer with a model" deny \
  '{"tool_name":"Agent","agent_id":"a1","agent_type":"lead","tool_input":{"subagent_type":"fixer","model":"opus"}}'
check "fixer under a lead spawns Explore" allow \
  '{"tool_name":"Agent","agent_id":"a2","agent_type":"fixer","tool_input":{"subagent_type":"Explore"}}'
check "fixer under a lead spawns fixer" deny \
  '{"tool_name":"Agent","agent_id":"a2","agent_type":"fixer","tool_input":{"subagent_type":"fixer"}}'
check "lead runs a workflow" deny \
  '{"tool_name":"Workflow","agent_id":"a1","agent_type":"lead","tool_input":{"script":"x"}}'
check "fable session, workflow with a model on every agent" allow \
  '{"tool_name":"Workflow","transcript_path":"'"$T"'/fable.jsonl","tool_input":{"script":"agent({prompt: \"a\", model: \"sonnet\"}); agent({prompt: \"b\", model: \"opus\"})"}}'
check "fable session, workflow with an agent that names no model" deny \
  '{"tool_name":"Workflow","transcript_path":"'"$T"'/fable.jsonl","tool_input":{"script":"agent({prompt: \"a\", model: \"sonnet\"}); agent({prompt: \"b\"})"}}'
check "fable session, saved workflow by name" deny \
  '{"tool_name":"Workflow","transcript_path":"'"$T"'/fable.jsonl","tool_input":{"name":"review"}}'
check "opus session, workflow with no models" allow \
  '{"tool_name":"Workflow","transcript_path":"'"$T"'/opus.jsonl","tool_input":{"script":"agent({prompt: \"a\"})"}}'
check "unreadable session model, workflow with no models" deny \
  '{"tool_name":"Workflow","transcript_path":"'"$T"'/missing.jsonl","tool_input":{"script":"agent({prompt: \"a\"})"}}'
check "fork from a fable session" deny \
  '{"tool_name":"Agent","transcript_path":"'"$T"'/fable.jsonl","tool_input":{"subagent_type":"fork"}}'
check "fork from an opus session" allow \
  '{"tool_name":"Agent","transcript_path":"'"$T"'/opus.jsonl","tool_input":{"subagent_type":"fork"}}'
check "fork, unreadable session model" deny \
  '{"tool_name":"Agent","transcript_path":"'"$T"'/missing.jsonl","tool_input":{"subagent_type":"fork"}}'
check "agent from main, plain fixer" allow \
  '{"tool_name":"Agent","transcript_path":"'"$T"'/fable.jsonl","cwd":"/tmp","tool_input":{"subagent_type":"fixer"}}'
check "malformed input fails closed" deny 'not json'
check "other tool is ignored" allow '{"tool_name":"Bash","tool_input":{"command":"ls"}}'
exit $fail
