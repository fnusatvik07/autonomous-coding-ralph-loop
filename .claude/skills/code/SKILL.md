---
name: code
description: "Execute one Ralph Loop coding iteration. Reads the PRD, picks the next
  pending task, implements it, runs tests, and updates progress. Use for manual
  stepping through the loop one task at a time."
disable-model-invocation: true
argument-hint: "[task-id]"
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Ralph Coding Iteration

Execute ONE coding iteration of the Ralph Loop.

## Protocol (follow EXACTLY)

### Phase 1: Orient
1. Read `.ralph/prd.json` — find your current task (or use $ARGUMENTS if a task ID is given)
2. Read `.ralph/progress.md` — what was done before
3. Read `.ralph/guardrails.md` — known pitfalls to avoid
4. Use `Glob` to understand current project structure
5. Run `git log --oneline -10` to see recent history

### Phase 2: Regression Check
- If there are previously completed tasks, run the test suite first
- If tests fail, fix regressions BEFORE starting new work

### Phase 3: Implement
1. Pick the highest-priority PENDING task
2. Read all relevant existing code before changing anything
3. Implement following the project's existing patterns
4. Write tests for your changes

### Phase 4: Verify
1. Run the full test suite
2. If tests fail, fix issues (up to 5 attempts)
3. ALL tests must pass, not just your new ones

### Phase 5: Commit & Report
1. `git add -A && git commit -m "feat: TASK-XXX - description"`
2. Update `.ralph/prd.json` — set task status to "passed"
3. Append progress to `.ralph/progress.md`

## Rules

- NEVER skip Phase 1. You have NO memory of previous sessions.
- NEVER commit code with failing tests.
- NEVER modify other tasks' status.
- Keep changes focused and minimal — no unrelated refactoring.
- If stuck, write observations to `.ralph/guardrails.md`.
