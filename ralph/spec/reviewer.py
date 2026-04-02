"""Adversarial Spec Review — catches bad specs before wasting coding time.

Flow: Planner writes spec.md → Reviewer critiques → Planner revises (max 2 cycles).
Only then does PRD generation happen.

Inspired by Liza's adversarial planning pattern.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from rich.console import Console

from ralph.prompts.templates import SPEC_REVIEWER_SYSTEM_PROMPT
from ralph.providers.base import BaseProvider

console = Console()
logger = logging.getLogger("ralph")

MAX_REVIEW_CYCLES = 2


async def review_spec(
    spec_content: str,
    provider: BaseProvider,
    workspace_dir: str,
) -> dict:
    """Review a spec and return structured feedback.

    Returns: {"approved": bool, "blocking_issues": [...], "suggestions": [...]}
    """
    user_message = f"""\
## Specification to Review

{spec_content[:20000]}

Review this specification. Output your verdict as a JSON code block.
"""

    console.print("  [magenta]Spec Reviewer: analyzing...[/magenta]")

    result = await provider.run_session(
        system_prompt=SPEC_REVIEWER_SYSTEM_PROMPT,
        user_message=user_message,
        max_turns=10,
        on_tool=lambda name, _: console.print(f"    [dim]SpecReview> {name}[/dim]"),
    )

    if not result.success:
        logger.warning("spec review failed: %s", result.error)
        return {"approved": True, "blocking_issues": [], "suggestions": []}

    verdict = _extract_review_json(result.final_response)
    if verdict:
        return verdict

    return {"approved": True, "blocking_issues": [], "suggestions": []}


async def review_and_revise_spec(
    spec_path: Path,
    provider: BaseProvider,
    workspace_dir: str,
) -> str:
    """Run adversarial spec review loop: review → revise → review (max 2 cycles).

    Returns the final (possibly revised) spec content.
    """
    spec_content = spec_path.read_text()

    for cycle in range(1, MAX_REVIEW_CYCLES + 1):
        console.print(f"  [magenta]Spec review cycle {cycle}/{MAX_REVIEW_CYCLES}[/magenta]")

        review = await review_spec(spec_content, provider, workspace_dir)

        if review.get("approved", True):
            console.print("  [green]Spec approved by reviewer[/green]")
            return spec_content

        issues = review.get("blocking_issues", [])
        if not issues:
            console.print("  [green]No blocking issues — spec approved[/green]")
            return spec_content

        console.print(f"  [yellow]Reviewer found {len(issues)} blocking issue(s):[/yellow]")
        for issue in issues[:5]:
            console.print(f"    [yellow]• {issue}[/yellow]")

        # Revise the spec
        console.print("  [cyan]Revising spec...[/cyan]")
        revision_prompt = (
            f"The spec reviewer found these blocking issues:\n\n"
            + "\n".join(f"- {i}" for i in issues)
            + "\n\nRevise the specification to address ALL blocking issues. "
            "Output the COMPLETE revised specification as markdown."
        )

        revision_result = await provider.run_session(
            system_prompt="You are a technical writer revising a specification. Fix the issues listed, keep everything else the same. Output the COMPLETE revised spec.",
            user_message=f"## Current Spec\n\n{spec_content[:15000]}\n\n## Issues to Fix\n\n{revision_prompt}",
            max_turns=10,
        )

        if revision_result.success and revision_result.final_response.strip():
            spec_content = revision_result.final_response.strip()
            spec_path.write_text(spec_content)
            console.print(f"  [dim]Spec revised ({len(spec_content)} chars)[/dim]")
        else:
            logger.warning("spec revision failed, keeping original")
            break

    return spec_content


def _extract_review_json(text: str) -> dict | None:
    """Extract review JSON from response."""
    match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

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
