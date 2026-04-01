"""Spec generator - creates spec.md then prd.json from a task description.

Two-step flow:
  1. Task description → spec.md (human-readable application spec)
  2. spec.md → prd.json (atomic task list for the coding loop)
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


async def generate_spec(
    task_description: str,
    provider: BaseProvider,
    workspace_dir: str,
) -> PRD:
    """Generate spec.md then prd.json from a task description.

    Step 1: LLM writes .ralph/spec.md (application specification)
    Step 2: LLM reads spec.md and writes .ralph/prd.json (task list)
    """
    ralph_dir = Path(workspace_dir) / ".ralph"
    ralph_dir.mkdir(exist_ok=True)

    # Step 1: Generate spec.md
    spec_path = ralph_dir / "spec.md"
    if not spec_path.exists():
        console.print("[bold cyan]Step 1: Generating specification (spec.md)...[/bold cyan]")
        console.print(f"  Task: {task_description[:100]}...")

        result = await provider.run_session(
            system_prompt=SPEC_SYSTEM_PROMPT,
            user_message=SPEC_USER_TEMPLATE.format(task_description=task_description),
            max_turns=30,
            on_tool=lambda name, _: console.print(f"  [dim]{name}[/dim]"),
        )

        if not result.success:
            raise RuntimeError(f"Spec generation failed: {result.error}")

        # If agent didn't write spec.md via Write tool, save from response
        if not spec_path.exists():
            spec_path.write_text(result.final_response)
            console.print("  [dim]Saved spec from response text[/dim]")

    console.print(f"  [green]spec.md ready ({spec_path.stat().st_size} bytes)[/green]")

    # Step 2: Generate prd.json from spec.md
    prd_path = ralph_dir / "prd.json"
    if not prd_path.exists():
        console.print("[bold cyan]Step 2: Generating task list (prd.json)...[/bold cyan]")

        result = await provider.run_session(
            system_prompt=PRD_SYSTEM_PROMPT,
            user_message=PRD_USER_TEMPLATE,
            max_turns=20,
            on_tool=lambda name, _: console.print(f"  [dim]{name}[/dim]"),
        )

        if not result.success:
            raise RuntimeError(f"PRD generation failed: {result.error}")

        # If agent didn't write prd.json via Write tool, try to extract JSON
        if not prd_path.exists():
            prd_data = _extract_json(result.final_response)
            if prd_data:
                prd_path.write_text(json.dumps(prd_data, indent=2))
            else:
                raise RuntimeError(
                    "LLM did not create .ralph/prd.json and "
                    "no JSON found in response"
                )

    return load_prd(workspace_dir)


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

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
