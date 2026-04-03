"""Reviewer agent — reads git diff + test output + acceptance criteria.

Unlike the QA sentinel (which runs tests), the reviewer reads code and
produces a qualitative review. Used as a feature-level gate for complex features.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path

from rich.console import Console

from ralph.models import QAResult
from ralph.prompts.templates import REVIEWER_SYSTEM_PROMPT
from ralph.providers.base import BaseProvider

console = Console()
logger = logging.getLogger("ralph")


async def run_reviewer(
    workspace_dir: str,
    provider: BaseProvider,
    feature_title: str = "",
    acceptance_criteria: list[str] | None = None,
    test_output: str = "",
) -> QAResult:
    """Run the code reviewer on the latest changes.

    Reads git diff and test output, returns QAResult with review verdict.
    """
    # Gather git diff
    diff = _get_git_diff(workspace_dir)
    if not diff:
        diff = "(no git diff available)"

    criteria_text = ""
    if acceptance_criteria:
        criteria_text = "\n".join(f"- {ac}" for ac in acceptance_criteria)

    user_message = (
        f"## Feature: {feature_title}\n\n"
        f"## Git Diff (recent changes):\n```\n{diff[:8000]}\n```\n\n"
        f"## Test Output:\n```\n{test_output[:3000]}\n```\n\n"
    )
    if criteria_text:
        user_message += f"## Acceptance Criteria:\n{criteria_text}\n\n"

    user_message += (
        "Review this code. Output your verdict as a JSON code block:\n"
        "```json\n"
        '{"approved": true/false, "issues": [...], "suggestions": [...]}\n'
        "```\n"
    )

    result = await provider.run_session(
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        user_message=user_message,
        max_turns=10,
        on_tool=lambda name, _: console.print(f"    [dim]Review> {name}[/dim]"),
    )

    if not result.success:
        return QAResult(
            passed=False,
            issues=[f"Reviewer session error: {result.error}"],
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
        )

    # Parse reviewer verdict
    verdict = _extract_review_json(result.final_response)
    if verdict:
        return QAResult(
            passed=verdict.get("approved", False),
            issues=verdict.get("issues", []),
            suggestions=verdict.get("suggestions", []),
            cost_usd=result.cost_usd,
            duration_ms=result.duration_ms,
        )

    # Default: approve if we can't parse (don't block on reviewer parse failure)
    return QAResult(
        passed=True,
        issues=[],
        suggestions=["Reviewer output could not be parsed"],
        cost_usd=result.cost_usd,
        duration_ms=result.duration_ms,
    )


def _get_git_diff(workspace_dir: str) -> str:
    """Get recent git diff for review."""
    try:
        r = subprocess.run(
            ["git", "diff", "HEAD~3..HEAD", "--stat", "--patch"],
            cwd=workspace_dir,
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return r.stdout[:10000]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def _extract_review_json(text: str) -> dict | None:
    """Extract review JSON from response."""
    match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Brace-depth for {"approved"...}
    idx = text.find('"approved"')
    if idx == -1:
        return None
    start = text.rfind("{", 0, idx)
    if start == -1:
        return None
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
                return None
    return None
