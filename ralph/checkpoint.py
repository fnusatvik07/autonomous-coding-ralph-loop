"""Git checkpoint system - atomic snapshots before each task.

Creates a lightweight git tag before each coding iteration so that
if the agent breaks something, we can rollback to the last good state.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone

logger = logging.getLogger("ralph")


def create_checkpoint(workspace_dir: str, task_id: str, iteration: int) -> str | None:
    """Create a git checkpoint (tag) before starting a task.

    Returns the checkpoint tag name, or None if git is not available.
    """
    tag = f"ralph-checkpoint/iter-{iteration}-before-{task_id}"
    try:
        # Stage and commit any uncommitted changes first
        subprocess.run(
            ["git", "add", "-A"],
            cwd=workspace_dir, capture_output=True, check=False,
        )
        subprocess.run(
            ["git", "commit", "-m", f"[ralph-checkpoint] before {task_id}",
             "--allow-empty"],
            cwd=workspace_dir, capture_output=True, check=False,
        )
        # Create a lightweight tag
        subprocess.run(
            ["git", "tag", "-f", tag],
            cwd=workspace_dir, capture_output=True, check=True,
        )
        logger.info("checkpoint created: %s", tag)
        return tag
    except subprocess.CalledProcessError as e:
        logger.warning("checkpoint creation failed: %s", e)
        return None


def rollback_to_checkpoint(workspace_dir: str, tag: str) -> bool:
    """Rollback to a previous checkpoint."""
    try:
        subprocess.run(
            ["git", "reset", "--hard", tag],
            cwd=workspace_dir, capture_output=True, check=True,
        )
        # Clean untracked files
        subprocess.run(
            ["git", "clean", "-fd", "--exclude=.ralph"],
            cwd=workspace_dir, capture_output=True, check=False,
        )
        logger.info("rolled back to: %s", tag)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("rollback failed: %s", e)
        return False


def list_checkpoints(workspace_dir: str) -> list[str]:
    """List all Ralph checkpoint tags."""
    try:
        r = subprocess.run(
            ["git", "tag", "-l", "ralph-checkpoint/*"],
            cwd=workspace_dir, capture_output=True, text=True, check=True,
        )
        return [t.strip() for t in r.stdout.strip().splitlines() if t.strip()]
    except subprocess.CalledProcessError:
        return []


def cleanup_checkpoints(workspace_dir: str) -> int:
    """Remove all Ralph checkpoint tags (after successful completion)."""
    tags = list_checkpoints(workspace_dir)
    for tag in tags:
        subprocess.run(
            ["git", "tag", "-d", tag],
            cwd=workspace_dir, capture_output=True, check=False,
        )
    if tags:
        logger.info("cleaned up %d checkpoint tags", len(tags))
    return len(tags)
