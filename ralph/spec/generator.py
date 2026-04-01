"""Spec generator - creates spec.md then prd.json from a task description.

Generates both in a SINGLE session to avoid the cold-start overhead
of two sessions. For large projects this can take 5-15 minutes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rich.console import Console

from ralph.models import PRD, Task, TaskStatus
from ralph.prompts.templates import (
    SPEC_SYSTEM_PROMPT, SPEC_USER_TEMPLATE,
    PRD_SYSTEM_PROMPT, PRD_USER_TEMPLATE,
)
from ralph.providers.base import BaseProvider

console = Console()

# Combined prompt that generates both spec.md AND prd.json in one session
COMBINED_SYSTEM = SPEC_SYSTEM_PROMPT + """

---

AFTER writing spec.md, IMMEDIATELY proceed to create the task list.

""" + PRD_SYSTEM_PROMPT

COMBINED_USER = """\
## Task Description

{task_description}

## Instructions

Complete BOTH steps in this single session:

**Step 1:** Use Glob and Read to examine the workspace. Then write a comprehensive \
application specification to `.ralph/spec.md`.

**Step 2:** Read your spec.md back, then create `.ralph/prd.json` with the \
test-case-driven task list. Scale tasks to project complexity (20-200). \
Each task = one testable behavior.

Also create `init.sh` in the workspace root to set up the dev environment.

Write both files using the Write tool. If Write fails for prd.json (file too large), \
output the complete JSON in a ```json code block in your response.
"""


async def generate_spec(
    task_description: str,
    provider: BaseProvider,
    workspace_dir: str,
) -> PRD:
    """Generate spec.md and prd.json from a task description in one session."""
    ralph_dir = Path(workspace_dir) / ".ralph"
    ralph_dir.mkdir(exist_ok=True)

    prd_path = ralph_dir / "prd.json"
    spec_path = ralph_dir / "spec.md"

    # If PRD already exists, just load it
    if prd_path.exists():
        console.print("[dim]Loading existing PRD...[/dim]")
        return load_prd(workspace_dir)

    # Generate both spec + PRD in ONE session
    console.print("[bold cyan]Generating specification + task list...[/bold cyan]")
    console.print(f"  Task: {task_description[:100]}...")
    console.print("  [dim]This may take 5-15 minutes for complex projects.[/dim]")

    result = await provider.run_session(
        system_prompt=COMBINED_SYSTEM,
        user_message=COMBINED_USER.format(task_description=task_description),
        max_turns=200,  # Needs many turns for spec + 50-200 tasks
        on_tool=lambda name, _: console.print(f"  [dim]{name}[/dim]"),
    )

    if not result.success:
        raise RuntimeError(f"Generation failed: {result.error}")

    # Save spec from response if Write tool didn't work
    if not spec_path.exists():
        spec_path.write_text(result.final_response)
        console.print("  [dim]Saved spec from response[/dim]")

    # Save PRD from response if Write tool didn't work
    if not prd_path.exists():
        prd_data = _extract_json(result.final_response)
        if prd_data:
            prd_path.write_text(json.dumps(prd_data, indent=2))
            console.print("  [dim]Extracted PRD from response[/dim]")
        else:
            raise RuntimeError(
                "LLM did not create .ralph/prd.json and no JSON found in response. "
                "The session may have timed out. Try again or use a smaller task."
            )

    prd = load_prd(workspace_dir)
    console.print(f"  [green]spec.md: {spec_path.stat().st_size} bytes[/green]")
    console.print(f"  [green]prd.json: {len(prd.tasks)} tasks[/green]")
    return prd


def load_prd(workspace_dir: str) -> PRD:
    """Load PRD from .ralph/prd.json."""
    prd_path = Path(workspace_dir) / ".ralph" / "prd.json"
    if not prd_path.exists():
        raise FileNotFoundError(f"No PRD found at {prd_path}")

    data = json.loads(prd_path.read_text())

    tasks = []
    for t in data.get("tasks", []):
        tasks.append(Task(
            id=t["id"],
            category=t.get("category", "functional"),
            title=t["title"],
            description=t.get("description", ""),
            acceptance_criteria=t.get("acceptance_criteria", []),
            priority=t.get("priority", 0),
            status=TaskStatus(t.get("status", "pending")),
            test_command=t.get("test_command", ""),
            notes=t.get("notes", ""),
        ))

    return PRD(
        project_name=data.get("project_name", "unknown"),
        branch_name=data.get("branch_name", "main"),
        description=data.get("description", ""),
        tasks=tasks,
    )


def save_prd(prd: PRD, workspace_dir: str) -> None:
    """Save PRD to .ralph/prd.json."""
    prd_path = Path(workspace_dir) / ".ralph" / "prd.json"
    prd_path.parent.mkdir(exist_ok=True)

    data = {
        "project_name": prd.project_name,
        "branch_name": prd.branch_name,
        "description": prd.description,
        "tasks": [
            {
                "id": t.id,
                "category": t.category,
                "title": t.title,
                "description": t.description,
                "acceptance_criteria": t.acceptance_criteria,
                "priority": t.priority,
                "status": t.status.value,
                "test_command": t.test_command,
                "notes": t.notes,
            }
            for t in prd.tasks
        ],
    }
    prd_path.write_text(json.dumps(data, indent=2))


def _extract_json(text: str) -> dict | None:
    """Try to extract a JSON object from LLM response text."""
    # Try code block first (most reliable)
    patterns = [
        r"```json\s*\n(.*?)\n```",
        r"```\s*\n(\{.*?\})\n```",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    # Try brace-depth parsing for {..."project_name"...}
    idx = text.find('"project_name"')
    if idx != -1:
        start = text.rfind("{", 0, idx)
        if start != -1:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    # Last resort: try whole text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
