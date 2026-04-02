"""Shipper Agent — pushes code to GitHub and creates a PR.

Runs after all tasks are complete. Requires GITHUB_TOKEN in .env.
If gh CLI is not available, falls back to git push only.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from ralph.models import PRD

logger = logging.getLogger("ralph")


def is_gh_available() -> bool:
    """Check if GitHub CLI is installed and authenticated."""
    try:
        r = subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def has_remote(workspace_dir: str) -> bool:
    """Check if git remote 'origin' is configured."""
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=workspace_dir, capture_output=True, timeout=5,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


async def ship(
    workspace_dir: str,
    prd: PRD,
    branch: str = "",
    base_branch: str = "main",
    cumulative_cost: float = 0.0,
) -> dict:
    """Push code and create PR.

    Returns: {"pushed": bool, "pr_url": str|None, "error": str|None}
    """
    result = {"pushed": False, "pr_url": None, "error": None}
    branch = branch or prd.branch_name or "ralph/delivery"

    # Check prerequisites
    if not has_remote(workspace_dir):
        result["error"] = "No git remote configured. Set up with: git remote add origin <url>"
        return result

    # Ensure we're on the right branch
    try:
        current = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=workspace_dir, capture_output=True, text=True, timeout=5,
        ).stdout.strip()

        if current != branch:
            # Create branch if it doesn't exist
            subprocess.run(
                ["git", "checkout", "-B", branch],
                cwd=workspace_dir, capture_output=True, check=True,
            )
    except subprocess.CalledProcessError as e:
        result["error"] = f"Branch error: {e}"
        return result

    # Push
    try:
        r = subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=workspace_dir, capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            result["error"] = f"Push failed: {r.stderr[:200]}"
            return result
        result["pushed"] = True
        logger.info("pushed to origin/%s", branch)
    except subprocess.TimeoutExpired:
        result["error"] = "Push timed out"
        return result

    # Create PR if gh CLI available
    if not is_gh_available():
        logger.info("gh CLI not available, skipping PR creation")
        return result

    # Build PR description
    completed = [t for t in prd.tasks if t.status.value == "passed"]
    failed = [t for t in prd.tasks if t.status.value in ("failed", "blocked")]
    body = _build_pr_body(prd, completed, failed, cumulative_cost)

    title = f"feat: {prd.project_name}"
    if len(completed) == len(prd.tasks):
        title += f" ({len(completed)} tasks complete)"
    else:
        title += f" ({len(completed)}/{len(prd.tasks)} tasks)"

    try:
        r = subprocess.run(
            ["gh", "pr", "create",
             "--title", title,
             "--body", body,
             "--base", base_branch,
             "--head", branch],
            cwd=workspace_dir, capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            result["pr_url"] = r.stdout.strip()
            logger.info("PR created: %s", result["pr_url"])
        else:
            # PR might already exist
            if "already exists" in r.stderr:
                logger.info("PR already exists")
            else:
                result["error"] = f"PR creation failed: {r.stderr[:200]}"
    except subprocess.TimeoutExpired:
        result["error"] = "PR creation timed out"

    return result


def _build_pr_body(
    prd: PRD,
    completed: list,
    failed: list,
    cost: float,
) -> str:
    """Build a PR description from the PRD data."""
    lines = [
        "## Summary",
        f"Autonomous coding session for **{prd.project_name}**.",
        "",
        f"{prd.description}",
        "",
        "## Tasks Completed",
    ]

    for feat in prd.features:
        feat_tasks = [t for t in feat.tasks if t.status.value == "passed"]
        if feat_tasks:
            lines.append(f"\n### {feat.title}")
            for t in feat_tasks:
                lines.append(f"- **{t.id}**: {t.title}")

    if failed:
        lines.append("\n## Tasks Failed/Blocked")
        for t in failed:
            lines.append(f"- **{t.id}**: {t.title} — {t.notes[:100]}")

    lines.extend([
        "",
        "## Metrics",
        f"- Tasks: {len(completed)}/{len(prd.tasks)}",
        f"- Cost: ${cost:.2f}",
        "",
        "## Verification",
        "- [ ] All tests pass locally",
        "- [ ] Code review completed",
        "- [ ] No regressions",
        "",
        "_Generated by [Ralph Loop](https://github.com/fnusatvik07/autonomous-coding-ralph-loop)_",
    ])

    return "\n".join(lines)
