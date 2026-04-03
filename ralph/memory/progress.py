"""Progress tracking - proper scratchpad for the coding agent.

Sections:
- Current State: auto-scanned workspace info
- Codebase Patterns: consolidated learnings (written by learning.py)
- Iteration Log: per-iteration entries
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("ralph")

PROGRESS_HEADER = """\
# Project Progress

## Current State
_Will be updated automatically after each task._

## Codebase Patterns
_Patterns discovered across iterations will be consolidated here._

## Iteration Log

"""


def init_progress(workspace_dir: str) -> None:
    """Initialize progress file if it doesn't exist."""
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    progress_path.parent.mkdir(exist_ok=True)
    if not progress_path.exists():
        progress_path.write_text(PROGRESS_HEADER)


def append_progress(
    workspace_dir: str,
    iteration: int,
    task_id: str,
    task_title: str,
    status: str,
    notes: str = "",
    patterns: list[str] | None = None,
    files_changed: list[str] | None = None,
    test_results: str = "",
) -> None:
    """Append a progress entry for the current iteration."""
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    entry = f"\n### Iteration {iteration} - {timestamp}\n"
    entry += f"- **Task**: {task_id} - {task_title}\n"
    entry += f"- **Status**: {status}\n"
    if notes:
        entry += f"- **Notes**: {notes}\n"
    if files_changed:
        entry += f"- **Files changed**: {', '.join(files_changed[:10])}\n"
    if test_results:
        entry += f"- **Test results**: {test_results}\n"
    if patterns:
        entry += "- **Patterns learned**:\n"
        for p in patterns:
            entry += f"  - {p}\n"

    with open(progress_path, "a") as f:
        f.write(entry)


def update_project_state(workspace_dir: str) -> None:
    """Scan workspace and update the Current State section in progress.md."""
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    if not progress_path.exists():
        return

    content = progress_path.read_text()

    # Build new state
    files = _scan_files(workspace_dir)
    test_summary = _run_tests_quiet(workspace_dir)

    state_lines = [
        f"_Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n",
    ]
    if files:
        state_lines.append(f"- **Files**: {len(files)} source files")
        # Show top-level structure
        dirs = sorted({f.split("/")[0] for f in files if "/" in f})
        if dirs:
            state_lines.append(f"- **Directories**: {', '.join(dirs[:10])}")
    if test_summary:
        state_lines.append(f"- **Tests**: {test_summary}")

    new_state = "\n".join(state_lines)

    # Replace Current State section
    marker_start = "## Current State"
    marker_end = "## Codebase Patterns"
    idx_start = content.find(marker_start)
    idx_end = content.find(marker_end)

    if idx_start != -1 and idx_end != -1:
        content = (
            content[:idx_start]
            + f"{marker_start}\n{new_state}\n\n"
            + content[idx_end:]
        )
        progress_path.write_text(content)


def update_codebase_patterns(workspace_dir: str, patterns: list[str]) -> None:
    """Append patterns to the Codebase Patterns section of progress.md."""
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    if not progress_path.exists():
        return

    content = progress_path.read_text()

    marker = "## Codebase Patterns"
    next_section = "## Iteration Log"
    idx_start = content.find(marker)
    idx_end = content.find(next_section)

    if idx_start == -1 or idx_end == -1:
        return

    # Get existing patterns section
    existing = content[idx_start + len(marker):idx_end].strip()

    # Add new patterns
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    new_patterns = f"\n### Patterns ({timestamp})\n"
    for p in patterns:
        new_patterns += f"- {p}\n"

    content = (
        content[:idx_start]
        + f"{marker}\n{existing}\n{new_patterns}\n\n"
        + content[idx_end:]
    )
    progress_path.write_text(content)


def get_progress_summary(workspace_dir: str) -> str:
    """Read the current progress file."""
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    if not progress_path.exists():
        return "No progress recorded yet."
    return progress_path.read_text()


def _scan_files(workspace_dir: str) -> list[str]:
    """Walk workspace files, excluding .ralph/.venv/node_modules etc."""
    exclude_dirs = {".ralph", ".venv", "venv", "node_modules", "__pycache__", ".git", ".tox"}
    files = []
    ws = Path(workspace_dir)
    try:
        for p in ws.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(ws))
                parts = rel.split("/")
                if not any(part in exclude_dirs for part in parts):
                    files.append(rel)
    except (PermissionError, OSError):
        pass
    return sorted(files)[:200]  # Cap to avoid huge lists


def _run_tests_quiet(workspace_dir: str) -> str:
    """Quick pytest summary — returns one-line result or empty string."""
    try:
        r = subprocess.run(
            ["python", "-m", "pytest", "--tb=no", "-q", "--no-header"],
            cwd=workspace_dir,
            capture_output=True, text=True, timeout=30,
        )
        # Extract last meaningful line (e.g., "15 passed in 0.5s")
        lines = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
        if lines:
            return lines[-1]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ""
