"""QA Sentinel - quality gate that blocks bad code from progressing.

Fixes applied:
- Deletes stale qa_result.json before each run
- Passes test_command from PRD task
- Handles session failure explicitly
- Robust JSON extraction (brace-depth, not regex)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rich.console import Console

from ralph.models import QAResult, Task
from ralph.prompts.templates import QA_SYSTEM_PROMPT, QA_USER_TEMPLATE
from ralph.providers.base import BaseProvider

console = Console()
logger = logging.getLogger("ralph")

RALPH_DIR = ".ralph"


async def run_sentinel(
    task: Task,
    provider: BaseProvider,
    workspace_dir: str,
) -> QAResult:
    """Run the QA sentinel check on the latest changes."""
    # Clean stale result to prevent false positives
    qa_path = Path(workspace_dir) / RALPH_DIR / "qa_result.json"
    if qa_path.exists():
        qa_path.unlink()

    acceptance = "\n".join(f"- {ac}" for ac in task.acceptance_criteria)

    user_message = QA_USER_TEMPLATE.format(
        task_id=task.id,
        task_title=task.title,
        acceptance_criteria=acceptance,
        test_command=task.test_command or "Run the project's test suite",
    )

    console.print(f"  [bold yellow]QA Sentinel: {task.id}[/bold yellow]")

    result = await provider.run_session(
        system_prompt=QA_SYSTEM_PROMPT,
        user_message=user_message,
        max_turns=50,
        on_tool=lambda name, _: console.print(f"    [dim]QA> {name}[/dim]"),
    )

    session_cost = result.cost_usd
    session_duration = result.duration_ms

    # Fail fast if session itself failed
    if not result.success:
        logger.warning("QA session failed: %s", result.error)
        return QAResult(
            passed=False,
            issues=[f"QA session error: {result.error}"],
            cost_usd=session_cost, duration_ms=session_duration,
        )

    # Try to load the QA result the LLM wrote
    if qa_path.exists():
        try:
            data = json.loads(qa_path.read_text())
            return QAResult(
                passed=data.get("passed", False),
                issues=data.get("issues", []),
                test_output=data.get("test_output", ""),
                suggestions=data.get("suggestions", []),
                cost_usd=session_cost, duration_ms=session_duration,
            )
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: parse from response
    qa_data = _extract_qa_json(result.final_response)
    if qa_data:
        return QAResult(
            passed=qa_data.get("passed", False),
            issues=qa_data.get("issues", []),
            test_output=qa_data.get("test_output", ""),
            suggestions=qa_data.get("suggestions", []),
            cost_usd=session_cost, duration_ms=session_duration,
        )

    # Can't determine -> assume failure (safe default)
    return QAResult(
        passed=False,
        issues=["Could not parse QA result from sentinel"],
        test_output=result.final_response[:1000],
        cost_usd=session_cost, duration_ms=session_duration,
    )


def _extract_qa_json(text: str) -> dict | None:
    """Extract QA result JSON using brace-depth parsing (not fragile regex)."""
    import re

    # Try code block first
    match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Find { containing "passed" and parse with brace depth
    idx = text.find('"passed"')
    if idx == -1:
        return None

    # Walk backwards to find opening brace
    start = text.rfind("{", 0, idx)
    if start == -1:
        return None

    # Walk forward counting braces
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
                return None

    return None
