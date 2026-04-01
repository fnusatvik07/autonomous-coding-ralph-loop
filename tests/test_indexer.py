"""Tests for codebase indexer."""

from ralph.indexer import index_codebase, _extract_python_signatures
from pathlib import Path


class TestIndexCodebase:
    def test_empty_workspace(self, workspace):
        result = index_codebase(str(workspace))
        assert "Codebase Index" in result
        assert "File Tree" in result

    def test_indexes_python_files(self, workspace):
        (workspace / "app").mkdir()
        (workspace / "app" / "main.py").write_text(
            "def hello(name: str) -> str:\n    return f'Hello {name}'\n\n"
            "class Server:\n    pass\n"
        )
        result = index_codebase(str(workspace))
        assert "hello" in result
        assert "Server" in result

    def test_skips_venv(self, workspace):
        (workspace / ".venv").mkdir()
        (workspace / ".venv" / "junk.py").write_text("x = 1")
        result = index_codebase(str(workspace))
        assert "junk" not in result

    def test_truncates_large_output(self, workspace):
        # Create many files
        (workspace / "src").mkdir()
        for i in range(50):
            (workspace / "src" / f"mod_{i}.py").write_text(
                f"def func_{i}(x: int) -> int: return x + {i}\n" * 20
            )
        result = index_codebase(str(workspace), max_tokens=500)
        assert len(result) < 3000  # Truncated


class TestExtractSignatures:
    def test_functions(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
        sigs = _extract_python_signatures(f)
        assert any("add" in s for s in sigs)

    def test_classes(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("class MyModel(BaseModel):\n    name: str\n")
        sigs = _extract_python_signatures(f)
        assert any("MyModel" in s for s in sigs)

    def test_async_functions(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("async def fetch(url: str) -> str:\n    pass\n")
        sigs = _extract_python_signatures(f)
        assert any("async" in s and "fetch" in s for s in sigs)

    def test_syntax_error_returns_empty(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def broken(:\n")
        sigs = _extract_python_signatures(f)
        assert sigs == []
