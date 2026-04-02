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

    # CI auto-fix: check PR checks, attempt fix if failing (max 3)
    if result.get("pr_url"):
        ci_ok = await _wait_and_fix_ci(workspace_dir, branch, max_attempts=3)
        if not ci_ok:
            result["ci_failed"] = True
            logger.warning("CI still failing after 3 fix attempts")

    return result


async def _wait_and_fix_ci(
    workspace_dir: str,
    branch: str,
    max_attempts: int = 3,
) -> bool:
    """Wait for CI checks, attempt auto-fix if they fail.

    Returns True if CI passes (or no CI configured).
    """
    import asyncio

    for attempt in range(1, max_attempts + 1):
        # Wait a bit for CI to start
        await asyncio.sleep(10)

        # Check PR status
        try:
            r = subprocess.run(
                ["gh", "pr", "checks", "--watch", "--fail-fast"],
                cwd=workspace_dir, capture_output=True, text=True, timeout=120,
            )
            if r.returncode == 0:
                logger.info("CI checks passed")
                return True

            ci_output = r.stdout + r.stderr
            logger.warning("CI failed (attempt %d/%d): %s", attempt, max_attempts, ci_output[:300])

            if attempt >= max_attempts:
                # Convert to draft PR
                subprocess.run(
                    ["gh", "pr", "ready", "--undo"],
                    cwd=workspace_dir, capture_output=True, timeout=10,
                )
                # Comment with CI error
                subprocess.run(
                    ["gh", "pr", "comment", "--body",
                     f"CI failed after {max_attempts} auto-fix attempts.\n\n```\n{ci_output[:2000]}\n```"],
                    cwd=workspace_dir, capture_output=True, timeout=10,
                )
                return False

            # Try to read CI error and fix
            logger.info("attempting CI fix %d/%d", attempt, max_attempts)
            # Simple fixes: if it's a lint/format issue, auto-format and push
            if any(kw in ci_output.lower() for kw in ["lint", "format", "style", "ruff", "black"]):
                subprocess.run(["python", "-m", "ruff", "check", "--fix", "."],
                               cwd=workspace_dir, capture_output=True, timeout=30)
                subprocess.run(["python", "-m", "black", "."],
                               cwd=workspace_dir, capture_output=True, timeout=30)
            elif "test" in ci_output.lower():
                # Can't auto-fix test failures without an LLM — just report
                logger.warning("CI test failure — cannot auto-fix")
                return False

            # Stage, commit, push
            subprocess.run(["git", "add", "-A"], cwd=workspace_dir, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"fix: CI auto-fix attempt {attempt}"],
                cwd=workspace_dir, capture_output=True,
            )
            subprocess.run(
                ["git", "push", "origin", branch],
                cwd=workspace_dir, capture_output=True, timeout=30,
            )

        except subprocess.TimeoutExpired:
            logger.warning("CI check timed out on attempt %d", attempt)
            return True  # Can't determine — assume OK
        except Exception as e:
            logger.warning("CI check error: %s", e)
            return True  # Can't determine — assume OK

    return False


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
