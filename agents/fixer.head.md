---
name: fixer
description: The default builder (Sonnet). Use for a specified change of any size whose cause and approach are known, including geometry or layout with a checkable spec. It commits, compiles and runs the tests of what it changed. Not for edits under about 30 lines in files the caller has open, or for open investigations.
model: sonnet
effort: medium
isolation: worktree
maxTurns: 150
disallowedTools: [Skill]
---

