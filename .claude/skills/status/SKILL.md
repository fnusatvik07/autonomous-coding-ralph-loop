---
name: status
description: "Show Ralph Loop progress — which tasks are done, pending, or failed.
  Use when checking progress or asking what remains."
allowed-tools: Read, Glob
---

# Ralph Status

Show a clear summary of the Ralph Loop progress.

## Steps

1. Read `.ralph/prd.json` for the task list
2. Read `.ralph/progress.md` for the iteration log
3. Read `.ralph/guardrails.md` for known issues

## Output Format

```
## Ralph Loop: [Project Name]

| ID       | Task                    | Status  | P |
|----------|-------------------------|---------|---|
| TASK-001 | Project scaffolding     | passed  | 1 |
| TASK-002 | Database models         | passed  | 2 |
| TASK-003 | CRUD endpoints          | pending | 3 |

Progress: 2/3 (67%)

### Recent Activity
- Iteration 1: TASK-001 passed
- Iteration 2: TASK-002 passed

### Guardrails
- (any known issues from guardrails.md)
```

If no `.ralph/` directory exists, tell the user to run `/spec` first or `ralph run` to start.
