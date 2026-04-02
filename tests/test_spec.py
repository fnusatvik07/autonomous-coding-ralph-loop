"""Tests for spec generator - PRD load/save with hierarchical format."""

import json
import pytest
from ralph.spec.generator import load_prd, save_prd, _extract_json
from ralph.models import PRD, Feature, Task, TaskStatus


class TestLoadPRD:
    def test_load_hierarchical_prd(self, workspace_with_prd):
        prd = load_prd(str(workspace_with_prd))
        assert prd.project_name == "test-project"
        assert len(prd.features) == 2
        assert prd.features[0].id == "FEAT-001"
        assert prd.features[0].title == "Infrastructure"
        assert len(prd.features[0].tasks) == 1
        assert len(prd.features[1].tasks) == 2
        assert prd.features[0].tasks[0].category == "functional"
        assert prd.features[1].tasks[1].category == "integration"
        assert prd.features[1].tasks[1].complexity == "complex"

    def test_flat_task_view(self, workspace_with_prd):
        prd = load_prd(str(workspace_with_prd))
        assert len(prd.tasks) == 3

    def test_load_flat_format_backward_compat(self, workspace_with_ralph, sample_prd_data_flat):
        prd_path = workspace_with_ralph / ".ralph" / "prd.json"
        prd_path.write_text(json.dumps(sample_prd_data_flat))
        prd = load_prd(str(workspace_with_ralph))
        assert prd.project_name == "flat-project"
        assert len(prd.features) == 1
        assert len(prd.tasks) == 1

    def test_load_missing_prd_raises(self, workspace):
        with pytest.raises(FileNotFoundError):
            load_prd(str(workspace))

    def test_load_preserves_priority(self, workspace_with_prd):
        prd = load_prd(str(workspace_with_prd))
        assert prd.features[0].priority == 1
        assert prd.features[1].priority == 2


class TestSavePRD:
    def test_save_and_reload(self, workspace_with_ralph):
        prd = PRD(
            project_name="roundtrip-test",
            branch_name="ralph/roundtrip",
            description="Testing save/load",
            features=[
                Feature(id="FEAT-001", title="Setup", priority=1, tasks=[
                    Task(id="T-1", category="validation", complexity="simple",
                         title="Task One", description="d",
                         acceptance_criteria=["it works"], test_command="pytest -v"),
                ]),
                Feature(id="FEAT-002", title="Core", priority=2, tasks=[
                    Task(id="T-2", category="quality", complexity="complex",
                         title="Task Two", description="d", status=TaskStatus.PASSED),
                ]),
            ],
        )

        save_prd(prd, str(workspace_with_ralph))
        loaded = load_prd(str(workspace_with_ralph))

        assert loaded.project_name == "roundtrip-test"
        assert len(loaded.features) == 2
        assert loaded.features[0].tasks[0].category == "validation"
        assert loaded.features[0].tasks[0].complexity == "simple"
        assert loaded.features[1].tasks[0].complexity == "complex"
        assert loaded.features[1].tasks[0].status == TaskStatus.PASSED

    def test_save_creates_ralph_dir(self, workspace):
        prd = PRD(project_name="test", features=[])
        save_prd(prd, str(workspace))
        assert (workspace / ".ralph" / "prd.json").exists()


class TestExtractJSON:
    def test_json_in_code_block(self):
        text = 'Here:\n```json\n{"project_name": "x", "features": []}\n```'
        result = _extract_json(text)
        assert result is not None
        assert result["project_name"] == "x"

    def test_raw_json(self):
        assert _extract_json('{"project_name": "y", "features": []}')["project_name"] == "y"

    def test_no_json(self):
        assert _extract_json("No JSON here.") is None

    def test_invalid_json(self):
        assert _extract_json('```json\n{broken\n```') is None
