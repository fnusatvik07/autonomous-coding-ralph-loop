---
name: spec
description: "Generate a Ralph Loop PRD (prd.json) from a task description. Use when
  creating a new spec, planning a feature, or converting a task into atomic user stories.
  Triggers on: create spec, generate prd, plan this task, ralph spec."
disable-model-invocation: true
argument-hint: "<task-description>"
allowed-tools: Read, Write, Bash, Glob, Grep
---

# Ralph Spec Generator

Generate a `prd.json` file for the Ralph Loop autonomous agent from a task description.

## Steps

1. Read the task description from $ARGUMENTS
2. Use `Glob` and `Read` to examine the current workspace (existing code, package.json, pyproject.toml, etc.)
3. Break the task into **atomic user stories** — each completable in ONE coding session
4. Order by dependency: infrastructure → backend → frontend → polish
5. Write `.ralph/prd.json` with the structured output
6. Write `.ralph/spec.md` with a human-readable summary

## Output Format (prd.json)

```json
{
  "project_name": "my-project",
  "branch_name": "ralph/feature-name",
  "description": "One paragraph description",
  "tasks": [
    {
      "id": "TASK-001",
      "title": "Short title",
      "description": "What to build and why",
      "acceptance_criteria": [
        "GIVEN ... WHEN ... THEN ...",
        "All tests pass"
      ],
      "priority": 1,
      "status": "pending",
      "test_command": "pytest tests/test_x.py -v",
      "notes": ""
    }
  ]
}
```

## Sizing Rules

**RIGHT-SIZED** (one iteration): Add a DB model, add one API endpoint, add one UI component, write tests for one module.

**TOO BIG** (split these): "Build the entire dashboard", "Add authentication", "Refactor the API".

Rule: if you cannot describe the change in 2-3 sentences, split it.

## Acceptance Criteria Rules

- Every criterion MUST be verifiable by running a command or checking output
- Always include "All tests pass" as the final criterion
- BAD: "Works correctly" — GOOD: "POST /api/todos returns 201 with created todo"

## Before Writing

- Check if `.ralph/prd.json` already exists — warn if overwriting
- Respect existing project architecture and conventions
