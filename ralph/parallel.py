"""Parallel task execution via git worktrees.

When tasks have no dependencies on each other, they can run concurrently
in isolated git worktrees. Each worktree gets its own copy of the repo
and its own agent instance.

Usage:
    independent = find_independent_tasks(prd)
    results = await run_parallel(independent, config)
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from ralph.config import Config
from ralph.models import PRD, Task, TaskStatus

logger = logging.getLogger("ralph")


def find_independent_tasks(prd: PRD, max_parallel: int = 3) -> list[list[Task]]:
    """Group tasks into batches that can run in parallel.

    Tasks are independent if they have consecutive priorities and none
    reference each other in descriptions/notes. Returns batches where
    each batch can run concurrently.

    Simple heuristic: tasks at the same priority level are independent.
    """
    pending = prd.pending_tasks
    if not pending:
        return []

    # Group by priority
    by_priority: dict[int, list[Task]] = {}
    for task in pending:
        by_priority.setdefault(task.priority, []).append(task)

    batches = []
    for priority in sorted(by_priority.keys()):
        group = by_priority[priority]
        if len(group) > 1:
            # Multiple tasks at same priority = can parallelize
            batches.append(group[:max_parallel])
        else:
            batches.append(group)

    return batches


async def run_task_in_worktree(
    repo_dir: str,
    task: Task,
    config: Config,
) -> tuple[str, bool]:
    """Run a single task in an isolated git worktree.

    Returns (task_id, success).
    """
    worktree_path = f"/tmp/ralph-worktree-{task.id.lower()}"
    branch_name = f"ralph/{task.id.lower()}"

    try:
        # Create worktree
        subprocess.run(
            ["git", "-C", repo_dir, "worktree", "add", "-b",
             branch_name, worktree_path, "HEAD"],
            check=True, capture_output=True,
        )
        logger.info("worktree created: %s -> %s", task.id, worktree_path)

        # Copy .ralph state to worktree
        ralph_src = Path(repo_dir) / ".ralph"
        ralph_dst = Path(worktree_path) / ".ralph"
        if ralph_src.exists():
            import shutil
            if ralph_dst.exists():
                shutil.rmtree(ralph_dst)
            shutil.copytree(ralph_src, ralph_dst)

        # Run ralph for this single task in the worktree
        proc = await asyncio.create_subprocess_exec(
            "ralph", "run", "",
            "--workspace", worktree_path,
            "--provider", config.provider,
            "--model", config.model,
            "--max-iterations", "3",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=config.session_timeout_seconds * 3
        )

        success = proc.returncode == 0
        logger.info("worktree task %s: %s", task.id, "success" if success else "failed")
        return task.id, success

    except asyncio.TimeoutError:
        logger.error("worktree task %s timed out", task.id)
        return task.id, False
    except subprocess.CalledProcessError as e:
        logger.error("worktree creation failed for %s: %s", task.id, e)
        return task.id, False
    finally:
        # Cleanup worktree
        try:
            subprocess.run(
                ["git", "-C", repo_dir, "worktree", "remove", "--force", worktree_path],
                capture_output=True,
            )
        except Exception:
            pass


async def run_parallel_batch(
    repo_dir: str,
    tasks: list[Task],
    config: Config,
) -> dict[str, bool]:
    """Run a batch of independent tasks in parallel worktrees.

    Returns {task_id: success}.
    """
    if len(tasks) <= 1:
        return {}  # No point parallelizing a single task

    logger.info("parallel batch: %d tasks", len(tasks))

    results = await asyncio.gather(*[
        run_task_in_worktree(repo_dir, task, config)
        for task in tasks
    ])

    return {task_id: success for task_id, success in results}


async def merge_worktree_branches(
    repo_dir: str,
    successful_task_ids: list[str],
) -> None:
    """Merge successful worktree branches back into the main branch."""
    for task_id in successful_task_ids:
        branch = f"ralph/{task_id.lower()}"
        try:
            subprocess.run(
                ["git", "-C", repo_dir, "merge", "--no-ff",
                 "-m", f"Merge parallel task {task_id}", branch],
                check=True, capture_output=True,
            )
            # Cleanup branch
            subprocess.run(
                ["git", "-C", repo_dir, "branch", "-d", branch],
                capture_output=True,
            )
            logger.info("merged parallel branch: %s", branch)
        except subprocess.CalledProcessError as e:
            logger.error("merge failed for %s: %s", branch, e)
