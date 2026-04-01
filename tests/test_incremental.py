"""Tests for incremental test detection."""

from ralph.incremental_test import find_affected_tests, build_test_command, get_changed_files


class TestFindAffectedTests:
    def test_direct_test_change(self, workspace):
        (workspace / "tests").mkdir()
        (workspace / "tests" / "test_foo.py").write_text("pass")
        affected = find_affected_tests(str(workspace), ["tests/test_foo.py"])
        assert "tests/test_foo.py" in affected

    def test_source_maps_to_test(self, workspace):
        (workspace / "tests").mkdir()
        (workspace / "tests" / "test_models.py").write_text("pass")
        affected = find_affected_tests(str(workspace), ["app/models.py"])
        assert "tests/test_models.py" in affected

    def test_init_py_returns_all(self, workspace):
        affected = find_affected_tests(str(workspace), ["app/__init__.py"])
        assert affected == []  # Empty means run all

    def test_unrelated_file(self, workspace):
        affected = find_affected_tests(str(workspace), ["README.md"])
        assert affected == []

    def test_multiple_changes(self, workspace):
        (workspace / "tests").mkdir()
        (workspace / "tests" / "test_api.py").write_text("pass")
        (workspace / "tests" / "test_models.py").write_text("pass")
        affected = find_affected_tests(
            str(workspace),
            ["app/api.py", "app/models.py"],
        )
        assert "tests/test_api.py" in affected
        assert "tests/test_models.py" in affected


class TestBuildTestCommand:
    def test_full_suite(self, workspace):
        (workspace / "tests").mkdir()
        cmd = build_test_command(str(workspace), [], full=True)
        assert "tests/" in cmd

    def test_affected_only(self, workspace):
        cmd = build_test_command(str(workspace), ["tests/test_foo.py"])
        assert "test_foo.py" in cmd
        # Should run specific file, not "tests/ -v"
        assert cmd.count("tests/") == 1  # Only the specific file path

    def test_no_affected_runs_all(self, workspace):
        (workspace / "tests").mkdir()
        cmd = build_test_command(str(workspace), [])
        assert "tests/" in cmd
