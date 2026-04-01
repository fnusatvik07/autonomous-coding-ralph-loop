"""Reflexion pattern - learn from failures across iterations.

After a failed iteration, the agent explicitly reflects on WHY it failed.
These reflections persist in .ralph/reflections.md and are injected into
subsequent prompts so the agent doesn't repeat mistakes.

Different from guardrails.md:
- Guardrails = simple "don't do X" signs
- Reflections = structured analysis: what failed, why, what to do instead
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ralph.models import AgentResult, QAResult
from ralph.providers.base import BaseProvider

logger = logging.getLogger("ralph")

RALPH_DIR = ".ralph"
REFLECTIONS_FILE = "reflections.md"


def init_reflections(workspace_dir: str) -> None:
    """Initialize reflections file if it doesn't exist."""
    path = Path(workspace_dir) / RALPH_DIR / REFLECTIONS_FILE
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        path.write_text(
            "# Ralph Reflections\n\n"
            "Structured failure analysis from previous iterations.\n"
            "Read these BEFORE starting work to avoid repeating mistakes.\n\n"
        )


def get_reflections(workspace_dir: str, max_entries: int = 10) -> str:
    """Get recent reflections for injection into prompts."""
    path = Path(workspace_dir) / RALPH_DIR / REFLECTIONS_FILE
    if not path.exists():
        return ""
    content = path.read_text()
    # Return last N reflection entries
    sections = content.split("## Reflection")
    if len(sections) <= 1:
        return ""
    recent = sections[-max_entries:]
    return "## Lessons from previous failures:\n\n" + "\n".join(
        "## Reflection" + s for s in recent
    )


async def reflect_on_failure(
    workspace_dir: str,
    provider: BaseProvider,
    task_id: str,
    task_title: str,
    iteration: int,
    failure_type: str,
    error_context: str,
) -> str:
    """Ask the LLM to reflect on why a failure occurred.

    Returns the reflection text that was stored.
    """
    reflection_prompt = f"""Analyze this failure from an autonomous coding session.

## Failed Task: {task_id} - {task_title}
## Failure Type: {failure_type}
## Error Context:
{error_context[:3000]}

## Your Analysis (be SPECIFIC and ACTIONABLE):
1. What exactly went wrong?
2. What was the root cause (not just the symptom)?
3. What should be done differently next time?
4. What specific patterns or approaches should be avoided?

Keep your analysis under 200 words. Be concrete, not vague."""

    result = await provider.run_session(
        system_prompt="You are a debugging expert analyzing autonomous coding failures. Be specific and actionable.",
        user_message=reflection_prompt,
        max_turns=1,  # Single response, no tools needed
    )

    reflection_text = result.final_response if result.success else f"Reflection failed: {result.error}"

    # Store the reflection
    _append_reflection(
        workspace_dir,
        task_id=task_id,
        task_title=task_title,
        iteration=iteration,
        failure_type=failure_type,
        reflection=reflection_text,
    )

    logger.info("reflection stored for %s: %s", task_id, reflection_text[:100])
    return reflection_text


def _append_reflection(
    workspace_dir: str,
    task_id: str,
    task_title: str,
    iteration: int,
    failure_type: str,
    reflection: str,
) -> None:
    """Append a reflection entry to the reflections file."""
    path = Path(workspace_dir) / RALPH_DIR / REFLECTIONS_FILE
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    entry = (
        f"\n## Reflection: {task_id} (Iteration {iteration}, {timestamp})\n"
        f"**Task:** {task_title}\n"
        f"**Failure:** {failure_type}\n"
        f"**Analysis:**\n{reflection}\n"
        f"---\n"
    )

    with open(path, "a") as f:
        f.write(entry)


def add_simple_reflection(
    workspace_dir: str,
    task_id: str,
    iteration: int,
    lesson: str,
) -> None:
    """Add a simple reflection without LLM call (for budget-constrained runs)."""
    _append_reflection(
        workspace_dir,
        task_id=task_id,
        task_title="",
        iteration=iteration,
        failure_type="auto",
        reflection=lesson,
    )
