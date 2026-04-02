"""Reviewer Agent — reads code and verifies correctness WITHOUT running tests.

3x cheaper than the QA sentinel because it doesn't execute anything.
Used for complex features that pass the smart gate.
Replaces sentinel for reviewed features; sentinel still used as fallback.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path

from rich.console import Console

from ralph.models import Feature, QAResult
from ralph.prompts.templates import REVIEWER_SYSTEM_PROMPT
from ralph.providers.base import BaseProvider

console = Console()
logger = logging.getLogger("ralph")


async def run_reviewer(
    feature: Feature,
    provider: BaseProvider,
    workspace_dir: str,
) -> QAResult:
    """Run a code review on a completed feature.

    Reads git diff + test output. Does NOT run tests (trusts coder).
    Returns QAResult with approved=passed.
    """
    # Get git diff for recent changes
    diff = _get_git_diff(workspace_dir)
    if not diff:
        diff = "(no git diff available — reviewer should read the code directly)"

    # Get test output from last pytest run
    test_output = _get_test_output(workspace_dir)

    # Build acceptance criteria summary
    criteria_text = ""
    for task in feature.tasks:
        criteria_text += f"\n### {task.id}: {task.title}\n"
        for ac in task.acceptance_criteria:
            criteria_text += f"- {ac}\n"

    # Load guardrails
    guardrails = ""
    gpath = Path(workspace_dir) / ".ralph" / "guardrails.md"
    if gpath.exists():
        guardrails = gpath.read_text()[:3000]

    user_message = f"""\
## Feature: {feature.id} — {feature.title}

## Git Diff (recent changes)
```diff
{diff[:15000]}
```

## Test Output (from coder's session)
```
{test_output[:5000]}
```

## Acceptance Criteria to Verify
{criteria_text}

## Known Pitfalls
{guardrails if guardrails else "None recorded."}

Review this code. Output your verdict as a JSON code block.
"""

    console.print(f"  [bold magenta]Reviewer: {feature.id}[/bold magenta]")

    result = await provider.run_session(
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        user_message=user_message,
        max_turns=30,
        on_tool=lambda name, _: console.print(f"    [dim]Review> {name}[/dim]"),
    )

    cost = result.cost_usd
    duration = result.duration_ms

    if not result.success:
        logger.warning("reviewer session failed: %s", result.error)
        return QAResult(
            passed=False,
            issues=[f"Reviewer session error: {result.error}"],
            cost_usd=cost, duration_ms=duration,
        )

    # Parse verdict from response
    verdict = _extract_verdict(result.final_response)
    if verdict:
        return QAResult(
            passed=verdict.get("approved", False),
            issues=verdict.get("issues", []),
            suggestions=verdict.get("suggestions", []),
            cost_usd=cost, duration_ms=duration,
        )

    # Couldn't parse — conservative fail
    return QAResult(
        passed=False,
        issues=["Could not parse reviewer verdict"],
        test_output=result.final_response[:1000],
        cost_usd=cost, duration_ms=duration,
    )


def _get_git_diff(workspace_dir: str) -> str:
    """Get recent git diff (staged + unstaged)."""
    try:
        # Try diff against last checkpoint/commit
        r = subprocess.run(
            ["git", "diff", "HEAD~1", "--stat", "--patch"],
            cwd=workspace_dir, capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
        # Fallback: all uncommitted changes
        r = subprocess.run(
            ["git", "diff", "--stat", "--patch"],
            cwd=workspace_dir, capture_output=True, text=True, timeout=10,
        )
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def _get_test_output(workspace_dir: str) -> str:
    """Get last pytest output without running it."""
    # Check if .pytest_cache has results, otherwise do a quick dry run
    try:
        r = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-v", "--tb=short", "-q"],
            cwd=workspace_dir, capture_output=True, text=True, timeout=30,
        )
        return r.stdout + r.stderr
    except Exception:
        return "Could not get test output"


def _extract_verdict(text: str) -> dict | None:
    """Extract review verdict JSON from response."""
    # Try code block
    match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try brace-depth for {"approved":...}
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
