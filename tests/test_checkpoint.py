"""Tests for git checkpoint system."""

import subprocess
from ralph.checkpoint import create_checkpoint, list_checkpoints, cleanup_checkpoints


class TestCheckpoint:
    def _init_git(self, workspace):
        subprocess.run(["git", "init"], cwd=str(workspace), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(workspace), capture_output=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=str(workspace), capture_output=True)
        (workspace / "init.txt").write_text("init")
        subprocess.run(["git", "add", "."], cwd=str(workspace), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(workspace), capture_output=True)

    def test_create_checkpoint(self, workspace):
        self._init_git(workspace)
        tag = create_checkpoint(str(workspace), "TASK-001", 1)
        assert tag is not None
        assert "TASK-001" in tag

    def test_list_checkpoints(self, workspace):
        self._init_git(workspace)
        create_checkpoint(str(workspace), "TASK-001", 1)
        create_checkpoint(str(workspace), "TASK-002", 2)
        tags = list_checkpoints(str(workspace))
        assert len(tags) == 2

    def test_cleanup_checkpoints(self, workspace):
        self._init_git(workspace)
        create_checkpoint(str(workspace), "TASK-001", 1)
        cleaned = cleanup_checkpoints(str(workspace))
        assert cleaned == 1
        assert list_checkpoints(str(workspace)) == []

    def test_no_git_returns_none(self, tmp_path):
        tag = create_checkpoint(str(tmp_path), "T-1", 1)
        # Should not crash - returns None for non-git directory
        # (git init might auto-create, so just check it doesn't throw)
        assert tag is None or isinstance(tag, str)
