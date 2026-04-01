"""Custom MCP server for Ralph-specific tools.

Exposes project-specific tools (test runner, linter, coverage, db check)
as an MCP server that can be used by any MCP-compatible agent.

Usage:
    # Run as MCP server
    python -m ralph.mcp_tools

    # Or register in Claude Code settings:
    # "mcpServers": {
    #   "ralph-tools": {
    #     "command": "python",
    #     "args": ["-m", "ralph.mcp_tools"],
    #   }
    # }
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def create_mcp_server():
    """Create and return the MCP server with Ralph tools."""
    from mcp.server import FastMCP

    app = FastMCP("ralph-tools")

    @app.tool()
    def run_tests(test_path: str = ".", verbose: bool = True, timeout: int = 120) -> str:
        """Run the project's test suite and return results."""
        # Auto-detect test framework
        cwd = os.getenv("PROJECT_ROOT", ".")
        cmd = _detect_test_cmd(cwd, test_path, verbose)

        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=cwd, timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        return f"Exit code: {result.returncode}\n{output}"

    @app.tool()
    def lint_code(file_path: str = ".") -> str:
        """Run linter (ruff or flake8) on a file or directory."""
        cwd = os.getenv("PROJECT_ROOT", ".")
        for linter in ["ruff check", "flake8"]:
            cmd_name = linter.split()[0]
            if subprocess.run(["which", cmd_name], capture_output=True).returncode == 0:
                result = subprocess.run(
                    f"{linter} {file_path}",
                    shell=True, capture_output=True, text=True, cwd=cwd,
                )
                return result.stdout or "No issues found."
        return "No linter (ruff or flake8) found. Install with: pip install ruff"

    @app.tool()
    def check_types(file_path: str = ".") -> str:
        """Run type checker (mypy or pyright) on a file or directory."""
        cwd = os.getenv("PROJECT_ROOT", ".")
        for checker in ["mypy", "pyright"]:
            if subprocess.run(["which", checker], capture_output=True).returncode == 0:
                result = subprocess.run(
                    [checker, file_path],
                    capture_output=True, text=True, cwd=cwd,
                )
                return result.stdout or "No type errors found."
        return "No type checker found. Install with: pip install mypy"

    @app.tool()
    def get_test_coverage(source_dir: str = ".") -> str:
        """Run tests with coverage and return the report."""
        cwd = os.getenv("PROJECT_ROOT", ".")
        result = subprocess.run(
            f"python -m pytest --cov={source_dir} --cov-report=term-missing -q",
            shell=True, capture_output=True, text=True, cwd=cwd, timeout=120,
        )
        return result.stdout or result.stderr

    @app.tool()
    def ralph_status() -> str:
        """Get the current Ralph Loop status (PRD progress)."""
        cwd = os.getenv("PROJECT_ROOT", ".")
        prd_path = Path(cwd) / ".ralph" / "prd.json"
        if not prd_path.exists():
            return "No Ralph PRD found."

        data = json.loads(prd_path.read_text())
        tasks = data.get("tasks", [])
        total = len(tasks)
        passed = sum(1 for t in tasks if t["status"] == "passed")
        failed = sum(1 for t in tasks if t["status"] == "failed")
        pending = total - passed - failed

        lines = [f"Project: {data.get('project_name', '?')}", f"Progress: {passed}/{total}"]
        for t in tasks:
            lines.append(f"  {t['id']} [{t['status']}] {t['title']}")
        return "\n".join(lines)

    @app.tool()
    def git_diff_summary() -> str:
        """Get a summary of uncommitted changes."""
        cwd = os.getenv("PROJECT_ROOT", ".")
        result = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True, text=True, cwd=cwd,
        )
        if not result.stdout.strip():
            return "No uncommitted changes."
        return result.stdout

    return app


def _detect_test_cmd(cwd: str, test_path: str, verbose: bool) -> str:
    """Auto-detect the test command based on project files."""
    v = "-v" if verbose else "-q"
    ws = Path(cwd)

    if (ws / "pyproject.toml").exists() or (ws / "pytest.ini").exists():
        return f"python -m pytest {test_path} {v} --tb=short"

    if (ws / "package.json").exists():
        try:
            pkg = json.loads((ws / "package.json").read_text())
            if "test" in pkg.get("scripts", {}):
                return "npm test"
        except (json.JSONDecodeError, OSError):
            pass
        return "npx jest" if (ws / "jest.config.js").exists() else "npm test"

    if (ws / "Cargo.toml").exists():
        return "cargo test"

    if list(ws.glob("**/*.go")):
        return "go test ./..."

    return f"python -m pytest {test_path} {v} --tb=short"


if __name__ == "__main__":
    server = create_mcp_server()
    server.run(transport="stdio")
