"""Auto-formatting - runs ruff/black after code generation.

Ensures consistent code style regardless of which model generated it.
Runs after each successful coding session, before QA sentinel review.
"""

from __future__ import annotations

import asyncio
import logging
import shutil

logger = logging.getLogger("ralph")


async def auto_format(workspace_dir: str) -> tuple[bool, str]:
    """Run auto-formatter on the workspace. Returns (success, output).

    Tries ruff first (fast, modern), falls back to black.
    """
    # Try ruff format
    if shutil.which("ruff"):
        return await _run_formatter(
            ["ruff", "format", "."], workspace_dir, "ruff"
        )

    # Try black
    if shutil.which("black"):
        return await _run_formatter(
            ["black", "."], workspace_dir, "black"
        )

    # Try from project venv
    for tool in ["ruff", "black"]:
        venv_path = f"{workspace_dir}/.venv/bin/{tool}"
        if shutil.which(venv_path):
            cmd = [venv_path, "format" if tool == "ruff" else ".", "."] if tool == "ruff" else [venv_path, "."]
            return await _run_formatter(cmd, workspace_dir, tool)

    logger.debug("no formatter available (ruff/black)")
    return True, "No formatter found"


async def auto_lint(workspace_dir: str) -> tuple[bool, str]:
    """Run linter and auto-fix. Returns (success, output)."""
    if shutil.which("ruff"):
        return await _run_formatter(
            ["ruff", "check", "--fix", "."], workspace_dir, "ruff check"
        )
    return True, "No linter found"


async def _run_formatter(
    cmd: list[str], workspace_dir: str, name: str
) -> tuple[bool, str]:
    """Run a formatting command."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workspace_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        output = (stdout or b"").decode() + (stderr or b"").decode()

        if proc.returncode == 0:
            logger.info("%s: formatted successfully", name)
        else:
            logger.warning("%s: exit %d: %s", name, proc.returncode, output[:200])

        return proc.returncode == 0, output.strip()

    except asyncio.TimeoutError:
        logger.warning("%s timed out", name)
        return False, f"{name} timed out"
    except Exception as e:
        logger.warning("%s failed: %s", name, e)
        return False, str(e)
