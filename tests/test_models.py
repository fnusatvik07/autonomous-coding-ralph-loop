"""Tests for data models."""

import pytest
from ralph.models import PRD, Feature, Task, TaskStatus, AgentResult, QAResult


class TestTask:
    def test_default_status(self):
        t = Task(id="T-1", title="Test")
        assert t.status == TaskStatus.PENDING

    def test_default_complexity(self):
        t = Task(id="T-1", title="Test")
        assert t.complexity == "simple"

    def test_default_category(self):
        t = Task(id="T-1", title="Test")
        assert t.category == "functional"


class TestFeature:
    def test_pending_tasks(self):
        f = Feature(id="F-1", title="Test", tasks=[
            Task(id="T-1", title="A", status=TaskStatus.PASSED),
            Task(id="T-2", title="B"),
        ])
        assert len(f.pending_tasks) == 1
        assert len(f.completed_tasks) == 1

    def test_is_complete(self):
        f = Feature(id="F-1", title="Test", tasks=[
            Task(id="T-1", title="A", status=TaskStatus.PASSED),
        ])
        assert f.is_complete

    def test_not_complete(self):
        f = Feature(id="F-1", title="Test", tasks=[
            Task(id="T-1", title="A"),
        ])
        assert not f.is_complete

    def test_max_complexity(self):
        f = Feature(id="F-1", title="Test", tasks=[
            Task(id="T-1", title="A", complexity="simple"),
            Task(id="T-2", title="B", complexity="complex"),
            Task(id="T-3", title="C", complexity="moderate"),
        ])
        assert f.max_complexity == "complex"

    def test_max_complexity_all_simple(self):
        f = Feature(id="F-1", title="Test", tasks=[
            Task(id="T-1", title="A", complexity="simple"),
        ])
        assert f.max_complexity == "simple"


class TestPRD:
    def test_empty_prd(self):
        prd = PRD(project_name="test")
        assert prd.tasks == []
        assert prd.pending_tasks == []
        assert prd.progress_pct == 0.0
        assert prd.get_next_task() is None
        assert prd.get_next_feature() is None

    def test_flat_task_view(self):
        prd = PRD(project_name="test", features=[
            Feature(id="F-1", title="A", priority=1, tasks=[
                Task(id="T-1", title="X"),
                Task(id="T-2", title="Y"),
            ]),
            Feature(id="F-2", title="B", priority=2, tasks=[
                Task(id="T-3", title="Z"),
            ]),
        ])
        assert len(prd.tasks) == 3

    def test_get_next_feature(self):
        prd = PRD(project_name="test", features=[
            Feature(id="F-2", title="Second", priority=2, tasks=[Task(id="T-2", title="B")]),
            Feature(id="F-1", title="First", priority=1, tasks=[Task(id="T-1", title="A")]),
        ])
        assert prd.get_next_feature().id == "F-1"

    def test_get_next_feature_skips_complete(self):
        prd = PRD(project_name="test", features=[
            Feature(id="F-1", title="Done", priority=1, tasks=[
                Task(id="T-1", title="A", status=TaskStatus.PASSED),
            ]),
            Feature(id="F-2", title="Next", priority=2, tasks=[
                Task(id="T-2", title="B"),
            ]),
        ])
        assert prd.get_next_feature().id == "F-2"

    def test_mark_task_in_feature(self):
        prd = PRD(project_name="test", features=[
            Feature(id="F-1", title="A", tasks=[
                Task(id="T-1", title="X"),
            ]),
        ])
        prd.mark_task("T-1", TaskStatus.PASSED, notes="done")
        assert prd.features[0].tasks[0].status == TaskStatus.PASSED

    def test_mark_nonexistent_raises(self):
        prd = PRD(project_name="test", features=[])
        with pytest.raises(ValueError, match="not found"):
            prd.mark_task("T-999", TaskStatus.PASSED)

    def test_progress_pct(self):
        prd = PRD(project_name="test", features=[
            Feature(id="F-1", title="A", tasks=[
                Task(id="T-1", title="X", status=TaskStatus.PASSED),
                Task(id="T-2", title="Y", status=TaskStatus.PASSED),
            ]),
            Feature(id="F-2", title="B", tasks=[
                Task(id="T-3", title="Z"),
                Task(id="T-4", title="W"),
            ]),
        ])
        assert prd.progress_pct == 50.0

    def test_all_complete(self):
        prd = PRD(project_name="test", features=[
            Feature(id="F-1", title="A", tasks=[
                Task(id="T-1", title="X", status=TaskStatus.PASSED),
            ]),
        ])
        assert prd.get_next_feature() is None
        assert prd.progress_pct == 100.0


class TestAgentResult:
    def test_success(self):
        r = AgentResult(success=True, final_response="done", cost_usd=0.05)
        assert r.success
        assert r.cost_usd == 0.05

    def test_failure(self):
        r = AgentResult(success=False, error="boom")
        assert not r.success


class TestQAResult:
    def test_passed(self):
        qa = QAResult(passed=True)
        assert qa.passed
        assert qa.issues == []

    def test_failed_with_issues(self):
        qa = QAResult(passed=False, issues=["test fails", "no coverage"])
        assert len(qa.issues) == 2
