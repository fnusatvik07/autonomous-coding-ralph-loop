"""Auto-aggregate learnings every N tasks.

Reads reflections + guardrails, extracts common patterns, and writes
consolidated learnings to the "Codebase Patterns" section of progress.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ralph.memory.guardrails import get_guardrails
from ralph.memory.progress import update_codebase_patterns
from ralph.reflexion import get_reflections

logger = logging.getLogger("ralph")

AGGREGATE_EVERY_N = 10  # Aggregate learnings every N completed tasks
RALPH_DIR = ".ralph"


def _count_completed_tasks(workspace_dir: str) -> int:
    """Count tasks with status 'passed' in prd.json."""
    import json
    prd_path = Path(workspace_dir) / RALPH_DIR / "prd.json"
    if not prd_path.exists():
        return 0
    try:
        data = json.loads(prd_path.read_text())
        count = 0
        for feat in data.get("features", []):
            for task in feat.get("tasks", []):
                if task.get("status") == "passed":
                    count += 1
        # Also handle flat format
        for task in data.get("tasks", []):
            if task.get("status") == "passed":
                count += 1
        return count
    except (json.JSONDecodeError, KeyError):
        return 0


def _extract_patterns(reflections: str, guardrails: str) -> list[str]:
    """Extract actionable patterns from reflections and guardrails.

    Simple heuristic extraction — looks for repeated themes and
    concrete lessons.
    """
    patterns = []

    # Extract lessons from reflections
    if reflections:
        lines = reflections.split("\n")
        for line in lines:
            line = line.strip()
            # Look for analysis/lesson lines
            if any(marker in line.lower() for marker in [
                "should", "always", "never", "avoid", "instead",
                "pattern:", "lesson:", "fix:",
            ]):
                cleaned = line.lstrip("- *#>").strip()
                if len(cleaned) > 20 and len(cleaned) < 200:
                    patterns.append(cleaned)

    # Extract key guardrails
    if guardrails and "No guardrails" not in guardrails:
        lines = guardrails.split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("_") and len(line) > 15:
                if not line.startswith("Sign") and not line.startswith("Read"):
                    patterns.append(line)

    # Deduplicate (simple)
    seen = set()
    unique = []
    for p in patterns:
        key = p.lower()[:50]
        if key not in seen:
            seen.add(key)
            unique.append(p)

    return unique[:10]  # Cap at 10 patterns


def maybe_aggregate_learnings(workspace_dir: str) -> bool:
    """Aggregate learnings if we've hit the N-task milestone.

    Returns True if aggregation was performed.
    """
    completed = _count_completed_tasks(workspace_dir)
    if completed == 0 or completed % AGGREGATE_EVERY_N != 0:
        return False

    # Check if we already aggregated for this milestone
    marker_path = Path(workspace_dir) / RALPH_DIR / f".aggregated_{completed}"
    if marker_path.exists():
        return False

    logger.info("aggregating learnings at %d completed tasks", completed)

    reflections = get_reflections(workspace_dir, max_entries=20)
    guardrails = get_guardrails(workspace_dir)
    patterns = _extract_patterns(reflections, guardrails)

    if patterns:
        update_codebase_patterns(workspace_dir, patterns)
        logger.info("wrote %d patterns to progress.md", len(patterns))

    # Mark this milestone as aggregated
    marker_path.parent.mkdir(exist_ok=True)
    marker_path.write_text(f"aggregated at {completed} tasks")

    return True
