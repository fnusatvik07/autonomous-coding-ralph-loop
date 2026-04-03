"""Healer - iteratively fixes issues found by the QA sentinel.

Fixes: now includes task context and guardrails reference.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from ralph.models import AgentResult, QAResult
from ralph.prompts.templates import HEALER_SYSTEM_PROMPT, HEALER_USER_TEMPLATE
from ralph.providers.base import BaseProvider

console = Console()


async def run_healer(
    qa_result: QAResult,
    provider: BaseProvider,
    task_id: str = "",
    task_title: str = "",
    max_attempts: int = 5,
    attempt: int = 1,
    workspace_dir: str = "",
) -> AgentResult:
    """Run one healer iteration to fix QA issues."""
    issues_text = "\n".join(f"- {issue}" for issue in qa_result.issues)
    if qa_result.suggestions:
        issues_text += "\n\nSuggestions:\n"
        issues_text += "\n".join(f"- {s}" for s in qa_result.suggestions)

    user_message = HEALER_USER_TEMPLATE.format(
        task_id=task_id,
        task_title=task_title,
        attempt=attempt,
        max_attempts=max_attempts,
        issues=issues_text,
        test_output=qa_result.test_output[:5000],
    )

    # Inject guardrails if available
    if workspace_dir:
        guardrails_path = Path(workspace_dir) / ".ralph" / "guardrails.md"
        if guardrails_path.exists():
            guardrails_content = guardrails_path.read_text()
            if guardrails_content and "No guardrails" not in guardrails_content:
                user_message += f"\n\n## Known Pitfalls (from guardrails.md):\n{guardrails_content[:3000]}"

    console.print(
        f"    [magenta]Healer: attempt {attempt}/{max_attempts}[/magenta]"
    )

    return await provider.run_session(
        system_prompt=HEALER_SYSTEM_PROMPT,
        user_message=user_message,
        max_turns=100,
        on_tool=lambda name, _: console.print(f"    [dim]Heal> {name}[/dim]"),
    )
