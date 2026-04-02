"""Auto-aggregate learnings — consolidates reflections + guardrails into patterns.

Runs every 10 completed tasks. A brief LLM session reads all accumulated
reflections and guardrails, then writes consolidated "Codebase Patterns"
to progress.md so future agents read lessons first.

Inspired by Metaswarm's auto-aggregate pattern.
"""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console

from ralph.memory.progress import update_codebase_patterns
from ralph.providers.base import BaseProvider

console = Console()
logger = logging.getLogger("ralph")

AGGREGATE_EVERY_N = 10  # Run every N completed tasks


async def maybe_aggregate_learnings(
    workspace_dir: str,
    provider: BaseProvider,
    completed_count: int,
) -> None:
    """Run learning aggregation if we've hit the N-task milestone."""
    if completed_count == 0 or completed_count % AGGREGATE_EVERY_N != 0:
        return

    ralph_dir = Path(workspace_dir) / ".ralph"
    reflections = _read_file(ralph_dir / "reflections.md")
    guardrails = _read_file(ralph_dir / "guardrails.md")
    progress = _read_file(ralph_dir / "progress.md")

    # Skip if nothing to aggregate
    if len(reflections) < 100 and len(guardrails) < 100:
        return

    console.print(f"  [dim]Aggregating learnings ({completed_count} tasks)...[/dim]")

    user_message = f"""\
## Task
Analyze the reflections and guardrails below from an autonomous coding project.
Extract 5-15 concise, actionable patterns that future coding agents should follow.

Focus on:
- Framework/library conventions used in this project
- Error patterns to avoid (things that failed)
- Testing patterns that work
- Architecture decisions made
- File organization conventions

## Reflections (failure analysis)
{reflections[:5000]}

## Guardrails (known pitfalls)
{guardrails[:5000]}

## Current Codebase Patterns (update/extend these)
{_extract_patterns_section(progress)}

Output ONLY a bullet list of patterns, one per line, starting with "- ".
Keep each pattern under 100 characters. Be specific, not generic.
Example:
- Use sqlite3.Row for dict-like access in database.py
- TestClient needs lifespan override for in-memory DB
- Always verify file exists after Write tool (can silently fail)
"""

    try:
        result = await provider.run_session(
            system_prompt="You are a technical analyst extracting coding patterns from project history. Output only a bullet list.",
            user_message=user_message,
            max_turns=5,
        )

        if result.success and result.final_response:
            patterns = _parse_patterns(result.final_response)
            if patterns:
                update_codebase_patterns(workspace_dir, patterns)
                console.print(f"  [dim]Added {len(patterns)} patterns to progress.md[/dim]")
                logger.info("aggregated %d patterns at %d tasks", len(patterns), completed_count)
    except Exception as e:
        logger.warning("learning aggregation failed (non-critical): %s", e)


def _read_file(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _extract_patterns_section(progress: str) -> str:
    """Extract existing Codebase Patterns section."""
    start = progress.find("## Codebase Patterns")
    end = progress.find("## Iteration Log")
    if start != -1 and end != -1:
        return progress[start:end].strip()
    return "No patterns recorded yet."


def _parse_patterns(text: str) -> list[str]:
    """Parse bullet list from LLM response."""
    patterns = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- ") and len(line) > 5:
            patterns.append(line[2:].strip())
    return patterns[:15]  # Cap at 15
