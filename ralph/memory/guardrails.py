"""Guardrails - failure memory that persists across iterations.

When an agent fails, it writes a "sign" here. Future agents read these signs
to avoid repeating mistakes, without needing conversation history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def init_guardrails(workspace_dir: str) -> None:
    """Initialize guardrails file if it doesn't exist."""
    path = Path(workspace_dir) / ".ralph" / "guardrails.md"
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        path.write_text(
            "# Ralph Guardrails\n\n"
            "Signs left by previous iterations to help future agents avoid known pitfalls.\n"
            "Read this file BEFORE starting any work.\n\n"
        )


def add_guardrail(workspace_dir: str, sign: str, context: str = "") -> None:
    """Add a guardrail sign for future iterations."""
    path = Path(workspace_dir) / ".ralph" / "guardrails.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    entry = f"\n## ⚠ Sign ({timestamp})\n"
    entry += f"{sign}\n"
    if context:
        entry += f"_Context: {context}_\n"

    with open(path, "a") as f:
        f.write(entry)


def get_guardrails(workspace_dir: str) -> str:
    """Read all guardrails."""
    path = Path(workspace_dir) / ".ralph" / "guardrails.md"
    if not path.exists():
        return "No guardrails set."
    return path.read_text()
