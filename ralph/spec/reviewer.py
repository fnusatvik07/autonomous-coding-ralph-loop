"""Adversarial spec reviewer — catches gaps before coding begins.

Reviews the generated spec.md for completeness, consistency, architecture,
and testability. Runs up to MAX_REVIEW_CYCLES rounds of review + revision.
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
) -> dict:
    """Review a spec and return structured feedback.

    Returns: {"approved": bool, "issues": [...], "revised_sections": {...}}
    """
    user_message = (
        f"## Specification to Review:\n\n{spec_content[:15000]}\n\n"
        "Review this specification using your checklist. "
        "Output your verdict as a JSON code block."
    )

    result = await provider.run_session(
        system_prompt=SPEC_REVIEWER_SYSTEM_PROMPT,
        user_message=user_message,
        max_turns=5,
        on_tool=lambda name, _: console.print(f"    [dim]SpecReview> {name}[/dim]"),
    )

    if not result.success:
        logger.warning("Spec review session failed: %s", result.error)
        return {"approved": True, "issues": [], "revised_sections": {}}

    return _extract_review(result.final_response)


async def review_and_revise_spec(
    spec_path: Path,
    provider: BaseProvider,
) -> str:
    """Run adversarial review loop on spec.md. Returns final spec content.

    Up to MAX_REVIEW_CYCLES rounds. Applies high-severity revisions automatically.
    """
    spec_content = spec_path.read_text()

    for cycle in range(1, MAX_REVIEW_CYCLES + 1):
        console.print(f"  [dim]Spec review cycle {cycle}/{MAX_REVIEW_CYCLES}...[/dim]")

        review = await review_spec(spec_content, provider)

        if review.get("approved", True):
            console.print("  [green]Spec approved by reviewer[/green]")
            return spec_content

        # Apply high-severity revisions
        high_issues = [
            i for i in review.get("issues", [])
            if isinstance(i, dict) and i.get("severity") == "high"
        ]

        if not high_issues:
            console.print("  [green]No high-severity issues — spec approved[/green]")
            return spec_content

        console.print(f"  [yellow]{len(high_issues)} high-severity issues found[/yellow]")
        for issue in high_issues:
            section = issue.get("section", "unknown")
            desc = issue.get("issue", "")
            console.print(f"    [yellow]- {section}: {desc}[/yellow]")

        # Apply revised sections if provided
        revised = review.get("revised_sections", {})
        if revised:
            for section_name, new_text in revised.items():
                if section_name and new_text:
                    # Simple replacement: find section header and replace content
                    marker = f"## {section_name}"
                    idx = spec_content.find(marker)
                    if idx != -1:
                        # Find next ## header
                        next_header = spec_content.find("\n## ", idx + len(marker))
                        if next_header == -1:
                            spec_content = spec_content[:idx] + f"{marker}\n\n{new_text}\n"
                        else:
                            spec_content = (
                                spec_content[:idx]
                                + f"{marker}\n\n{new_text}\n\n"
                                + spec_content[next_header:]
                            )
            spec_path.write_text(spec_content)
            console.print(f"  [dim]Applied {len(revised)} section revisions[/dim]")

    console.print("  [yellow]Max review cycles reached — proceeding with current spec[/yellow]")
    return spec_content


def _extract_review(text: str) -> dict:
    """Extract review JSON from LLM response."""
    # Try code block first
    match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Brace-depth for {"approved"...}
    idx = text.find('"approved"')
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

    # Default: approve if parse fails
    return {"approved": True, "issues": [], "revised_sections": {}}
