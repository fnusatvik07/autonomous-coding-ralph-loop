"""Tests for the Reflexion pattern."""

from ralph.reflexion import (
    init_reflections, get_reflections, add_simple_reflection, _append_reflection,
)


class TestReflections:
    def test_init_creates_file(self, workspace_with_ralph):
        init_reflections(str(workspace_with_ralph))
        path = workspace_with_ralph / ".ralph" / "reflections.md"
        assert path.exists()
        assert "# Ralph Reflections" in path.read_text()

    def test_init_idempotent(self, workspace_with_ralph):
        init_reflections(str(workspace_with_ralph))
        init_reflections(str(workspace_with_ralph))
        content = (workspace_with_ralph / ".ralph" / "reflections.md").read_text()
        assert content.count("# Ralph Reflections") == 1

    def test_get_empty_reflections(self, workspace_with_ralph):
        init_reflections(str(workspace_with_ralph))
        result = get_reflections(str(workspace_with_ralph))
        assert result == ""  # No reflections yet

    def test_add_and_get_reflection(self, workspace_with_ralph):
        init_reflections(str(workspace_with_ralph))
        add_simple_reflection(
            str(workspace_with_ralph),
            task_id="TASK-001",
            iteration=1,
            lesson="Don't use sqlite for production auth tokens",
        )
        result = get_reflections(str(workspace_with_ralph))
        assert "Lessons from previous failures" in result
        assert "sqlite" in result
        assert "TASK-001" in result

    def test_multiple_reflections(self, workspace_with_ralph):
        init_reflections(str(workspace_with_ralph))
        for i in range(3):
            add_simple_reflection(
                str(workspace_with_ralph),
                task_id=f"T-{i}",
                iteration=i,
                lesson=f"Lesson {i}",
            )
        result = get_reflections(str(workspace_with_ralph))
        assert "Lesson 0" in result
        assert "Lesson 2" in result

    def test_max_entries_limits_output(self, workspace_with_ralph):
        init_reflections(str(workspace_with_ralph))
        for i in range(20):
            add_simple_reflection(
                str(workspace_with_ralph),
                task_id=f"T-{i}",
                iteration=i,
                lesson=f"Lesson {i}",
            )
        result = get_reflections(str(workspace_with_ralph), max_entries=3)
        # Should only have the last 3
        assert "Lesson 17" in result
        assert "Lesson 19" in result

    def test_no_file_returns_empty(self, workspace):
        result = get_reflections(str(workspace))
        assert result == ""
