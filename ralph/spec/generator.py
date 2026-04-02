"""Spec generator - creates spec.md then prd.json from any user input.

Handles: one-liners, bullet points, detailed specs, uploaded files.
Normalizes ALL inputs into standard spec.md → hierarchical prd.json.

Generates both in a SINGLE session to avoid cold-start overhead.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rich.console import Console

from ralph.models import PRD, Feature, Task, TaskStatus
from ralph.prompts.templates import (
    SPEC_SYSTEM_PROMPT, SPEC_USER_TEMPLATE,
    PRD_SYSTEM_PROMPT, PRD_USER_TEMPLATE,
)
from ralph.providers.base import BaseProvider
from ralph.routing import classify_task, Complexity

console = Console()

# Combined prompt for single-session spec + PRD generation
COMBINED_SYSTEM = SPEC_SYSTEM_PROMPT + "\n\n---\n\nAFTER writing spec.md, IMMEDIATELY proceed to create the task list.\n\n" + PRD_SYSTEM_PROMPT

COMBINED_USER = """\
## User Input

{task_description}

## Instructions

Complete BOTH steps in this single session:

**Step 1:** Examine the workspace, then write a comprehensive spec to `.ralph/spec.md`.
Expand the user's input into a full specification regardless of how vague or detailed it is.

**Step 2:** Read your spec.md back, then create `.ralph/prd.json` with the hierarchical
feature → task structure. Group related tasks into features.

Also create `init.sh` in the workspace root.

Write both files using the Write tool. If Write fails for prd.json (file too large),
output the complete JSON in a ```json code block.
"""


async def generate_spec(
    task_description: str,
    provider: BaseProvider,
    workspace_dir: str,
) -> PRD:
    """Generate spec.md and prd.json from any user input in one session."""
    ralph_dir = Path(workspace_dir) / ".ralph"
    ralph_dir.mkdir(exist_ok=True)

    prd_path = ralph_dir / "prd.json"
    spec_path = ralph_dir / "spec.md"

    if prd_path.exists():
        console.print("[dim]Loading existing PRD...[/dim]")
        return load_prd(workspace_dir)

    # Step 1: Generate spec.md
    if not spec_path.exists():
        console.print("[bold cyan]Step 1/2: Generating specification (spec.md)...[/bold cyan]")
        console.print(f"  Task: {task_description[:120]}...")

        result = await provider.run_session(
            system_prompt=SPEC_SYSTEM_PROMPT,
            user_message=SPEC_USER_TEMPLATE.format(task_description=task_description),
            max_turns=50,
            on_tool=lambda name, _: console.print(f"  [dim]{name}[/dim]"),
        )

        if not result.success:
            raise RuntimeError(f"Spec generation failed: {result.error}")

        # Save spec from response text (we told LLM not to use Write tool)
        spec_content = _extract_spec(result.final_response)
        spec_path.write_text(spec_content)
        console.print(f"  [dim]Saved spec ({len(spec_content)} chars)[/dim]")

    console.print(f"  [green]spec.md ready ({spec_path.stat().st_size} bytes)[/green]")

    # Step 1.5: Adversarial spec review (max 2 cycles)
    # Skip for tiny specs (mock/test) — only review real specs (>500 chars)
    if spec_path.stat().st_size > 500:
        from ralph.spec.reviewer import review_and_revise_spec
        console.print("[bold cyan]Step 1.5: Adversarial spec review...[/bold cyan]")
        await review_and_revise_spec(spec_path, provider, workspace_dir)

    # Step 2: Generate prd.json from spec.md
    if not prd_path.exists():
        console.print("[bold cyan]Step 2/2: Generating task list (prd.json)...[/bold cyan]")
        console.print("  [dim]Reading spec and creating hierarchical feature → task list...[/dim]")

        result = await provider.run_session(
            system_prompt=PRD_SYSTEM_PROMPT,
            user_message=PRD_USER_TEMPLATE,
            max_turns=150,
            on_tool=lambda name, _: console.print(f"  [dim]{name}[/dim]"),
        )

        if not result.success:
            raise RuntimeError(f"PRD generation failed: {result.error}")

        if not prd_path.exists():
            prd_data = _extract_json(result.final_response)
            if prd_data:
                prd_path.write_text(json.dumps(prd_data, indent=2))
                console.print("  [dim]Extracted PRD from response[/dim]")
            else:
                raise RuntimeError(
                    "LLM did not create .ralph/prd.json and no JSON found in response."
                )

    prd = load_prd(workspace_dir)
    console.print(f"  [green]spec.md: {spec_path.stat().st_size} bytes[/green]")
    console.print(f"  [green]prd.json: {len(prd.features)} features, {len(prd.tasks)} tasks[/green]")
    return prd


def load_prd(workspace_dir: str) -> PRD:
    """Load PRD from .ralph/prd.json.

    Handles both:
    - v3 hierarchical format: {"features": [{"tasks": [...]}]}
    - v2 flat format: {"tasks": [...]}  (backward compat)
    """
    prd_path = Path(workspace_dir) / ".ralph" / "prd.json"
    if not prd_path.exists():
        raise FileNotFoundError(f"No PRD found at {prd_path}")

    data = json.loads(prd_path.read_text())

    # v3 hierarchical format
    if "features" in data:
        features = []
        for f in data["features"]:
            tasks = []
            for t in f.get("tasks", []):
                tasks.append(_parse_task(t))
            features.append(Feature(
                id=f["id"],
                title=f.get("title", ""),
                priority=f.get("priority", 0),
                tasks=tasks,
            ))
        return PRD(
            project_name=data.get("project_name", "unknown"),
            branch_name=data.get("branch_name", "main"),
            description=data.get("description", ""),
            features=features,
        )

    # v2 flat format — wrap all tasks in a single feature
    if "tasks" in data:
        tasks = [_parse_task(t) for t in data["tasks"]]
        feature = Feature(id="FEAT-001", title="All Tasks", priority=1, tasks=tasks)
        return PRD(
            project_name=data.get("project_name", "unknown"),
            branch_name=data.get("branch_name", "main"),
            description=data.get("description", ""),
            features=[feature],
        )

    raise ValueError("prd.json has neither 'features' nor 'tasks' key")


def _parse_task(t: dict) -> Task:
    """Parse a task dict into a Task model.

    If complexity is missing or 'simple' (default), auto-classify using
    heuristics from routing.py so the smart gate works without LLM help.
    """
    raw_complexity = t.get("complexity", "")
    title = t.get("title", "")
    description = t.get("description", "")
    criteria = t.get("acceptance_criteria", [])

    # Auto-populate complexity if not explicitly set by the LLM
    if raw_complexity in ("", "simple"):
        classified = classify_task(title, description, criteria)
        complexity = classified.value
    else:
        complexity = raw_complexity

    return Task(
        id=t["id"],
        category=t.get("category", "functional"),
        complexity=complexity,
        title=title,
        description=description,
        acceptance_criteria=criteria,
        status=TaskStatus(t.get("status", "pending")),
        test_command=t.get("test_command", ""),
        notes=t.get("notes", ""),
    )


def save_prd(prd: PRD, workspace_dir: str) -> None:
    """Save PRD to .ralph/prd.json in v3 hierarchical format."""
    prd_path = Path(workspace_dir) / ".ralph" / "prd.json"
    prd_path.parent.mkdir(exist_ok=True)

    data = {
        "project_name": prd.project_name,
        "branch_name": prd.branch_name,
        "description": prd.description,
        "features": [
            {
                "id": f.id,
                "title": f.title,
                "priority": f.priority,
                "tasks": [
                    {
                        "id": t.id,
                        "category": t.category,
                        "complexity": t.complexity,
                        "title": t.title,
                        "description": t.description,
                        "acceptance_criteria": t.acceptance_criteria,
                        "status": t.status.value,
                        "test_command": t.test_command,
                        "notes": t.notes,
                    }
                    for t in f.tasks
                ],
            }
            for f in prd.features
        ],
    }
    prd_path.write_text(json.dumps(data, indent=2))


def _extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response text."""
    # Code block
    for pattern in [r"```json\s*\n(.*?)\n```", r"```\s*\n(\{.*?\})\n```"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    # Brace-depth for {..."project_name"...} or {..."features"...}
    for key in ('"project_name"', '"features"'):
        idx = text.find(key)
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
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_spec(text: str) -> str:
    """Extract the spec markdown from the LLM response.

    Looks for '# Application Specification' header and takes everything from there.
    If not found, returns the full response.
    """
    # Find the start of the actual spec
    markers = ["# Application Specification", "# Specification:", "## Overview"]
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            return text[idx:].strip()

    # If no marker found, return full text (it might be the spec itself)
    return text.strip()
