"""Parallel task execution via git worktrees.

In v3, parallelism is at the FEATURE level — independent features can
run concurrently in separate worktrees. Features at the same priority
level are considered independent.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from ralph.config import Config
from ralph.models import PRD, Feature, TaskStatus

logger = logging.getLogger("ralph")


def find_independent_features(prd: PRD, max_parallel: int = 3) -> list[list[Feature]]:
    """Group features into batches that can run in parallel.

    Features at the same priority level are independent.
    Returns batches where each batch can run concurrently.
    """
    pending = [f for f in prd.features if f.pending_tasks]
    if not pending:
        return []

    by_priority: dict[int, list[Feature]] = {}
    for feat in pending:
        by_priority.setdefault(feat.priority, []).append(feat)

    batches = []
    for priority in sorted(by_priority.keys()):
        group = by_priority[priority]
        if len(group) > 1:
            batches.append(group[:max_parallel])
        else:
            batches.append(group)

    return batches


async def run_feature_in_worktree(
    repo_dir: str,
    feature: Feature,
    config: Config,
) -> tuple[str, bool]:
    """Run a feature in an isolated git worktree."""
    worktree_path = f"/tmp/ralph-worktree-{feature.id.lower()}"
    branch_name = f"ralph/{feature.id.lower()}"

    try:
        subprocess.run(
            ["git", "-C", repo_dir, "worktree", "add", "-b",
             branch_name, worktree_path, "HEAD"],
            check=True, capture_output=True,
        )
        logger.info("worktree created: %s -> %s", feature.id, worktree_path)

        ralph_src = Path(repo_dir) / ".ralph"
        ralph_dst = Path(worktree_path) / ".ralph"
        if ralph_src.exists():
            import shutil
            if ralph_dst.exists():
                shutil.rmtree(ralph_dst)
            shutil.copytree(ralph_src, ralph_dst)

        proc = await asyncio.create_subprocess_exec(
            "ralph", "run", "",
            "--workspace", worktree_path,
            "--provider", config.provider,
            "--model", config.model,
            "--max-iterations", "3",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=config.session_timeout_seconds * 3)

        success = proc.returncode == 0
        return feature.id, success

    except (asyncio.TimeoutError, subprocess.CalledProcessError) as e:
        logger.error("worktree %s failed: %s", feature.id, e)
        return feature.id, False
    finally:
        try:
            subprocess.run(
                ["git", "-C", repo_dir, "worktree", "remove", "--force", worktree_path],
                capture_output=True,
            )
        except Exception:
            pass


async def merge_worktree_branches(
    repo_dir: str,
    successful_feature_ids: list[str],
) -> None:
    """Merge successful worktree branches back."""
    for feat_id in successful_feature_ids:
        branch = f"ralph/{feat_id.lower()}"
        try:
            subprocess.run(
                ["git", "-C", repo_dir, "merge", "--no-ff",
                 "-m", f"Merge parallel feature {feat_id}", branch],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo_dir, "branch", "-d", branch],
                capture_output=True,
            )
            logger.info("merged: %s", branch)
        except subprocess.CalledProcessError as e:
            logger.error("merge failed for %s: %s", branch, e)
