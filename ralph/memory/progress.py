"""Progress tracking - persists learnings across iterations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def init_progress(workspace_dir: str) -> None:
    """Initialize progress file if it doesn't exist."""
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    progress_path.parent.mkdir(exist_ok=True)
    if not progress_path.exists():
        progress_path.write_text(
            "# Ralph Loop Progress\n\n"
            "## Codebase Patterns\n"
            "_Patterns discovered across iterations will be consolidated here._\n\n"
            "## Iteration Log\n\n"
        )


def append_progress(
    workspace_dir: str,
    iteration: int,
    task_id: str,
    task_title: str,
    status: str,
    notes: str = "",
    patterns: list[str] | None = None,
) -> None:
    """Append a progress entry for the current iteration."""
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    entry = f"\n### Iteration {iteration} - {timestamp}\n"
    entry += f"- **Task**: {task_id} - {task_title}\n"
    entry += f"- **Status**: {status}\n"
    if notes:
        entry += f"- **Notes**: {notes}\n"
    if patterns:
        entry += "- **Patterns learned**:\n"
        for p in patterns:
            entry += f"  - {p}\n"

    with open(progress_path, "a") as f:
        f.write(entry)


def get_progress_summary(workspace_dir: str) -> str:
    """Read the current progress file."""
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    if not progress_path.exists():
        return "No progress recorded yet."
    return progress_path.read_text()
