"""Tests for progress tracking and guardrails."""

from pathlib import Path
from ralph.memory.progress import init_progress, append_progress, get_progress_summary
from ralph.memory.guardrails import init_guardrails, add_guardrail, get_guardrails


class TestProgress:
    def test_init_creates_file(self, workspace_with_ralph):
        init_progress(str(workspace_with_ralph))
        path = workspace_with_ralph / ".ralph" / "progress.md"
        assert path.exists()
        assert "# Project Progress" in path.read_text()

    def test_init_idempotent(self, workspace_with_ralph):
        init_progress(str(workspace_with_ralph))
        init_progress(str(workspace_with_ralph))  # Should not fail or duplicate
        content = (workspace_with_ralph / ".ralph" / "progress.md").read_text()
        assert content.count("# Project Progress") == 1

    def test_append_progress(self, workspace_with_ralph):
        init_progress(str(workspace_with_ralph))
        append_progress(
            str(workspace_with_ralph),
            iteration=1,
            task_id="TASK-001",
            task_title="Setup project",
            status="PASSED",
            notes="Went smoothly",
            patterns=["Use pyproject.toml not setup.py"],
        )
        content = get_progress_summary(str(workspace_with_ralph))
        assert "Iteration 1" in content
        assert "TASK-001" in content
        assert "PASSED" in content
        assert "Went smoothly" in content
        assert "Use pyproject.toml" in content

    def test_multiple_appends(self, workspace_with_ralph):
        init_progress(str(workspace_with_ralph))
        for i in range(1, 4):
            append_progress(
                str(workspace_with_ralph),
                iteration=i,
                task_id=f"T-{i:03d}",
                task_title=f"Task {i}",
                status="PASSED",
            )
        content = get_progress_summary(str(workspace_with_ralph))
        assert "Iteration 1" in content
        assert "Iteration 3" in content


class TestGuardrails:
    def test_init_creates_file(self, workspace_with_ralph):
        init_guardrails(str(workspace_with_ralph))
        path = workspace_with_ralph / ".ralph" / "guardrails.md"
        assert path.exists()
        assert "# Ralph Guardrails" in path.read_text()

    def test_add_guardrail(self, workspace_with_ralph):
        init_guardrails(str(workspace_with_ralph))
        add_guardrail(
            str(workspace_with_ralph),
            sign="Do not use sqlite for auth tokens",
            context="TASK-003 auth implementation",
        )
        content = get_guardrails(str(workspace_with_ralph))
        assert "Do not use sqlite" in content
        assert "TASK-003" in content

    def test_multiple_guardrails(self, workspace_with_ralph):
        init_guardrails(str(workspace_with_ralph))
        add_guardrail(str(workspace_with_ralph), sign="Sign 1")
        add_guardrail(str(workspace_with_ralph), sign="Sign 2")
        content = get_guardrails(str(workspace_with_ralph))
        assert "Sign 1" in content
        assert "Sign 2" in content

    def test_get_guardrails_no_file(self, workspace):
        result = get_guardrails(str(workspace))
        assert "No guardrails" in result
