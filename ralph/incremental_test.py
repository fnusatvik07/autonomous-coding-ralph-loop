"""Incremental test running - only run affected tests first.

Instead of running the entire test suite after every change,
detect which tests are likely affected and run those first.
Falls back to full suite at commit time.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("ralph")


def get_changed_files(workspace_dir: str) -> list[str]:
    """Get list of files changed since last commit."""
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=workspace_dir, capture_output=True, text=True,
        )
        staged = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            cwd=workspace_dir, capture_output=True, text=True,
        )
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=workspace_dir, capture_output=True, text=True,
        )
        all_files = set()
        for output in [r.stdout, staged.stdout, untracked.stdout]:
            for f in output.strip().splitlines():
                if f.strip():
                    all_files.add(f.strip())
        return sorted(all_files)
    except subprocess.CalledProcessError:
        return []


def find_affected_tests(
    workspace_dir: str,
    changed_files: list[str],
) -> list[str]:
    """Find test files likely affected by the changed files.

    Heuristics:
    1. If a test file changed, include it directly
    2. If app/foo.py changed, look for tests/test_foo.py
    3. If any __init__.py changed, run all tests
    """
    ws = Path(workspace_dir)
    affected = set()

    for f in changed_files:
        fp = Path(f)

        # Direct test file changes
        if fp.name.startswith("test_") and fp.suffix == ".py":
            affected.add(str(fp))
            continue

        # Map source to test: app/foo.py -> tests/test_foo.py
        if fp.suffix == ".py" and not fp.name.startswith("test_"):
            stem = fp.stem
            # Try common test locations
            for test_dir in ["tests", "test", "."]:
                test_path = ws / test_dir / f"test_{stem}.py"
                if test_path.exists():
                    affected.add(str(test_path.relative_to(ws)))

        # If __init__.py or conftest.py changed, run everything
        if fp.name in ("__init__.py", "conftest.py"):
            return []  # Empty = run all

    return sorted(affected)


def build_test_command(
    workspace_dir: str,
    affected_tests: list[str],
    full: bool = False,
) -> str:
    """Build the pytest command.

    If full=True or no affected tests found, run the full suite.
    Otherwise run only affected tests.
    """
    ws = Path(workspace_dir)

    # Detect test directory
    if (ws / "tests").exists():
        test_dir = "tests/"
    elif (ws / "test").exists():
        test_dir = "test/"
    else:
        test_dir = "."

    if full or not affected_tests:
        return f"python3 -m pytest {test_dir} -v --tb=short"

    files = " ".join(affected_tests)
    return f"python3 -m pytest {files} -v --tb=short"
