"""Tests for spec generator - PRD load/save and JSON extraction."""

import json
import pytest
from ralph.spec.generator import load_prd, save_prd, _extract_json
from ralph.models import PRD, Task, TaskStatus


class TestLoadPRD:
    def test_load_valid_prd(self, workspace_with_prd):
        prd = load_prd(str(workspace_with_prd))
        assert prd.project_name == "test-project"
        assert len(prd.tasks) == 3
        assert prd.tasks[0].id == "TASK-001"
        assert prd.tasks[0].status == TaskStatus.PENDING
        assert prd.tasks[0].category == "functional"
        assert prd.tasks[2].category == "integration"
        assert len(prd.tasks[0].acceptance_criteria) == 2

    def test_load_missing_prd_raises(self, workspace):
        with pytest.raises(FileNotFoundError):
            load_prd(str(workspace))

    def test_load_preserves_priority(self, workspace_with_prd):
        prd = load_prd(str(workspace_with_prd))
        assert prd.tasks[0].priority == 1
        assert prd.tasks[1].priority == 2
        assert prd.tasks[2].priority == 3


class TestSavePRD:
    def test_save_and_reload(self, workspace_with_ralph):
        prd = PRD(
            project_name="roundtrip-test",
            branch_name="ralph/roundtrip",
            description="Testing save/load",
            tasks=[
                Task(
                    id="T-1", category="validation", title="Task One", description="d",
                    priority=1, acceptance_criteria=["it works"],
                    test_command="pytest -v",
                ),
                Task(
                    id="T-2", category="quality", title="Task Two", description="d",
                    priority=2, status=TaskStatus.PASSED,
                ),
            ],
        )

        save_prd(prd, str(workspace_with_ralph))
        loaded = load_prd(str(workspace_with_ralph))

        assert loaded.project_name == "roundtrip-test"
        assert loaded.branch_name == "ralph/roundtrip"
        assert len(loaded.tasks) == 2
        assert loaded.tasks[0].acceptance_criteria == ["it works"]
        assert loaded.tasks[0].category == "validation"
        assert loaded.tasks[1].category == "quality"
        assert loaded.tasks[1].status == TaskStatus.PASSED

    def test_save_creates_ralph_dir(self, workspace):
        prd = PRD(project_name="test", tasks=[])
        save_prd(prd, str(workspace))
        assert (workspace / ".ralph" / "prd.json").exists()


class TestExtractJSON:
    def test_json_in_code_block(self):
        text = 'Here is the spec:\n```json\n{"project_name": "x", "tasks": []}\n```\nDone.'
        result = _extract_json(text)
        assert result is not None
        assert result["project_name"] == "x"

    def test_raw_json(self):
        text = '{"project_name": "y", "tasks": []}'
        result = _extract_json(text)
        assert result is not None
        assert result["project_name"] == "y"

    def test_no_json(self):
        result = _extract_json("No JSON here at all.")
        assert result is None

    def test_invalid_json(self):
        result = _extract_json('```json\n{broken json\n```')
        assert result is None
