"""Codebase indexing for large repos.

Generates a compact codebase summary that fits in a prompt, so the agent
doesn't waste tokens reading irrelevant files one by one.

Approach: AST-based extraction of function/class signatures + file tree.
No external dependencies (uses built-in ast module).
"""

from __future__ import annotations

import ast
import logging
import os
from pathlib import Path

logger = logging.getLogger("ralph")

SKIP_DIRS = {
    ".git", ".ralph", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    ".egg-info", ".tox", "htmlcov",
}

SKIP_FILES = {".env", ".DS_Store", "Thumbs.db"}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs",
    ".java", ".rb", ".php", ".c", ".cpp", ".h",
}

CONFIG_EXTENSIONS = {
    ".toml", ".yaml", ".yml", ".json", ".cfg", ".ini",
}


def index_codebase(workspace_dir: str, max_tokens: int = 4000) -> str:
    """Generate a compact codebase summary.

    Returns a string suitable for injection into an LLM prompt.
    Includes: file tree, function/class signatures, config files.
    """
    ws = Path(workspace_dir)
    parts = ["## Codebase Index\n"]

    # File tree
    tree_lines = _build_file_tree(ws)
    parts.append("### File Tree\n```")
    parts.extend(tree_lines[:100])
    parts.append("```\n")

    # Python signatures
    py_files = list(ws.rglob("*.py"))
    py_files = [f for f in py_files if not any(skip in f.parts for skip in SKIP_DIRS)]

    if py_files:
        parts.append("### Python Signatures\n")
        for py_file in sorted(py_files)[:30]:
            sigs = _extract_python_signatures(py_file)
            if sigs:
                rel = py_file.relative_to(ws)
                parts.append(f"**{rel}**:")
                for sig in sigs[:10]:
                    parts.append(f"  {sig}")
                parts.append("")

    # Config files
    config_files = []
    for ext in CONFIG_EXTENSIONS:
        config_files.extend(ws.glob(f"*{ext}"))

    if config_files:
        parts.append("### Config Files\n")
        for cf in sorted(config_files)[:5]:
            rel = cf.relative_to(ws)
            content = cf.read_text(errors="replace")[:500]
            parts.append(f"**{rel}** (first 500 chars):\n```\n{content}\n```\n")

    result = "\n".join(parts)

    # Rough token estimate (4 chars per token)
    if len(result) > max_tokens * 4:
        result = result[: max_tokens * 4] + "\n... (truncated)"

    return result


def _build_file_tree(ws: Path, prefix: str = "", max_depth: int = 4) -> list[str]:
    """Build a tree-style file listing."""
    lines = []

    def _walk(path: Path, depth: int, prefix: str):
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and e.name not in SKIP_DIRS]
        files = [e for e in entries if e.is_file() and e.name not in SKIP_FILES]

        for f in files[:20]:
            size = f.stat().st_size
            lines.append(f"{prefix}{f.name} ({size}b)")

        for d in dirs[:10]:
            lines.append(f"{prefix}{d.name}/")
            _walk(d, depth + 1, prefix + "  ")

    _walk(ws, 0, "")
    return lines


def _extract_python_signatures(filepath: Path) -> list[str]:
    """Extract function and class signatures from a Python file."""
    try:
        source = filepath.read_text(errors="replace")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    sigs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            args = _format_args(node.args)
            ret = ""
            if node.returns:
                ret = f" -> {ast.unparse(node.returns)}"
            prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            sigs.append(f"{prefix}def {node.name}({args}){ret}")

        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            sigs.append(f"class {node.name}({bases})" if bases else f"class {node.name}")

    return sigs


def _format_args(args: ast.arguments) -> str:
    """Format function arguments concisely."""
    parts = []
    for arg in args.args:
        ann = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
        parts.append(f"{arg.arg}{ann}")
    if len(parts) > 5:
        parts = parts[:5] + ["..."]
    return ", ".join(parts)
