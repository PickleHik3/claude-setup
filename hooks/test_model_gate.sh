#!/usr/bin/env bash
# Gate cases: empty stdout = allow, "deny" in stdout = deny.
cd "$(dirname "$0")" || exit 1
fail=0
check() {  # name expected json
  out=$(printf '%s' "$3" | python3 model-gate.py)
  got=allow; [[ $out == *deny* ]] && got=deny
  if [[ $got == "$2" ]]; then echo "ok   $1 -> $got"; else echo "FAIL $1: wanted $2, got $got"; fail=1; fi
}
check "workflow mentions fable and solver, model sonnet" allow \
  '{"tool_name":"Workflow","tool_input":{"script":"agent({prompt: \"write a sudoku solver about Fable\", model: '"'sonnet'"'})"}}'
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
exit $fail
