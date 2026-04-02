"""Progress tracking — the scratchpad that carries context between agents.

This is THE most important file for cross-session continuity.
Each fresh agent reads this FIRST to understand:
- What has been built so far
- Which files exist and what they do
- Patterns and conventions in the codebase
- What failed and why
- What to work on next
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def init_progress(workspace_dir: str) -> None:
    """Initialize progress file with project state template."""
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    progress_path.parent.mkdir(exist_ok=True)
    if not progress_path.exists():
        progress_path.write_text(
            "# Project Progress\n\n"
            "## Current State\n"
            "_Updated automatically after each iteration._\n\n"
            "## Codebase Patterns\n"
            "_Conventions and patterns discovered across iterations._\n\n"
            "## Iteration Log\n\n"
        )


def append_progress(
    workspace_dir: str,
    iteration: int,
    task_id: str,
    task_title: str,
    status: str,
    notes: str = "",
    files_changed: list[str] | None = None,
    test_results: str = "",
    patterns: list[str] | None = None,
) -> None:
    """Append a detailed progress entry for the current iteration.

    This is what the next agent reads. Be specific and actionable.
    """
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    entry = f"\n### Iteration {iteration} — {task_id} — {status} ({timestamp})\n"
    entry += f"**Task**: {task_title}\n"

    if notes:
        entry += f"**What happened**: {notes}\n"

    if files_changed:
        entry += "**Files touched**: " + ", ".join(f"`{f}`" for f in files_changed[:15]) + "\n"

    if test_results:
        entry += f"**Tests**: {test_results}\n"

    if patterns:
        entry += "**Patterns learned**:\n"
        for p in patterns:
            entry += f"  - {p}\n"

    with open(progress_path, "a") as f:
        f.write(entry)


def update_project_state(workspace_dir: str, prd_summary: str = "") -> None:
    """Update the 'Current State' section with a snapshot of what exists.

    Called after each iteration so the next agent knows exactly
    what the project looks like right now.
    """
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    if not progress_path.exists():
        return

    # Scan workspace for actual code files
    file_tree = _scan_files(workspace_dir)
    test_result = _run_tests_quiet(workspace_dir)

    state_lines = [
        "## Current State\n",
        f"_Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n",
    ]

    if prd_summary:
        state_lines.append(f"\n**Progress**: {prd_summary}\n")

    if file_tree:
        state_lines.append("\n**Files in workspace**:\n")
        state_lines.append("```\n")
        state_lines.append(file_tree)
        state_lines.append("\n```\n")

    if test_result:
        state_lines.append(f"\n**Test status**: {test_result}\n")

    state_block = "\n".join(state_lines)

    # Replace the Current State section
    content = progress_path.read_text()
    start = content.find("## Current State")
    end = content.find("## Codebase Patterns")

    if start != -1 and end != -1:
        content = content[:start] + state_block + "\n" + content[end:]
        progress_path.write_text(content)


def update_codebase_patterns(workspace_dir: str, new_patterns: list[str]) -> None:
    """Add newly discovered patterns to the Codebase Patterns section."""
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    if not progress_path.exists() or not new_patterns:
        return

    content = progress_path.read_text()
    start = content.find("## Codebase Patterns")
    end = content.find("## Iteration Log")

    if start == -1 or end == -1:
        return

    existing = content[start:end]

    # Append new patterns (avoid duplicates)
    additions = ""
    for p in new_patterns:
        if p not in existing:
            additions += f"- {p}\n"

    if additions:
        content = content[:end] + additions + "\n" + content[end:]
        progress_path.write_text(content)


def get_progress_summary(workspace_dir: str) -> str:
    """Read the current progress file."""
    progress_path = Path(workspace_dir) / ".ralph" / "progress.md"
    if not progress_path.exists():
        return "No progress recorded yet."
    return progress_path.read_text()


def _scan_files(workspace_dir: str) -> str:
    """Get a compact file tree of the workspace (excluding .ralph, .venv, etc)."""
    skip = {".ralph", ".venv", "venv", ".git", "__pycache__", ".pytest_cache",
            "node_modules", ".egg-info", "todo_app.egg-info"}
    lines = []

    ws = Path(workspace_dir)
    try:
        for root, dirs, files in os.walk(ws):
            dirs[:] = [d for d in dirs if d not in skip and not d.endswith(".egg-info")]
            rel = Path(root).relative_to(ws)
            depth = len(rel.parts)
            if depth > 3:
                continue
            indent = "  " * depth
            if depth > 0:
                lines.append(f"{indent}{rel.name}/")
            for f in sorted(files):
                if f.startswith(".") and f not in (".gitignore", ".env.example"):
                    continue
                fpath = Path(root) / f
                size = fpath.stat().st_size
                lines.append(f"{indent}  {f} ({size}B)")
    except Exception:
        pass

    return "\n".join(lines[:50])  # Cap at 50 lines


def _run_tests_quiet(workspace_dir: str) -> str:
    """Run pytest quietly and return a one-line summary."""
    try:
        r = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-v", "--tb=no", "-q"],
            cwd=workspace_dir, capture_output=True, text=True, timeout=30,
        )
        # Extract the summary line like "13 passed in 0.19s"
        for line in reversed(r.stdout.strip().splitlines()):
            if "passed" in line or "failed" in line or "error" in line:
                return line.strip()
        return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "no tests found"
    except Exception:
        return ""
