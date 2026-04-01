"""Tests for data models."""

import pytest
from ralph.models import PRD, Task, TaskStatus, AgentResult, QAResult


class TestTask:
    def test_default_status(self):
        t = Task(id="T-1", title="Test", description="d")
        assert t.status == TaskStatus.PENDING

    def test_acceptance_criteria_default(self):
        t = Task(id="T-1", title="Test", description="d")
        assert t.acceptance_criteria == []


class TestPRD:
    def test_empty_prd(self):
        prd = PRD(project_name="test")
        assert prd.pending_tasks == []
        assert prd.completed_tasks == []
        assert prd.progress_pct == 0.0
        assert prd.get_next_task() is None

    def test_get_next_task_by_priority(self):
        prd = PRD(project_name="test", tasks=[
            Task(id="T-2", title="Second", description="d", priority=2),
            Task(id="T-1", title="First", description="d", priority=1),
            Task(id="T-3", title="Third", description="d", priority=3),
        ])
        assert prd.get_next_task().id == "T-1"

    def test_pending_skips_completed(self):
        prd = PRD(project_name="test", tasks=[
            Task(id="T-1", title="Done", description="d", priority=1, status=TaskStatus.PASSED),
            Task(id="T-2", title="Next", description="d", priority=2),
        ])
        assert prd.get_next_task().id == "T-2"
        assert len(prd.pending_tasks) == 1
        assert len(prd.completed_tasks) == 1

    def test_mark_task(self):
        prd = PRD(project_name="test", tasks=[
            Task(id="T-1", title="Test", description="d"),
        ])
        prd.mark_task("T-1", TaskStatus.PASSED, notes="done")
        assert prd.tasks[0].status == TaskStatus.PASSED
        assert prd.tasks[0].notes == "done"

    def test_mark_nonexistent_task_raises(self):
        prd = PRD(project_name="test", tasks=[])
        with pytest.raises(ValueError, match="not found"):
            prd.mark_task("T-999", TaskStatus.PASSED)

    def test_progress_pct(self):
        prd = PRD(project_name="test", tasks=[
            Task(id="T-1", title="A", description="d", status=TaskStatus.PASSED),
            Task(id="T-2", title="B", description="d", status=TaskStatus.PASSED),
            Task(id="T-3", title="C", description="d"),
            Task(id="T-4", title="D", description="d"),
        ])
        assert prd.progress_pct == 50.0

    def test_all_complete(self):
        prd = PRD(project_name="test", tasks=[
            Task(id="T-1", title="A", description="d", status=TaskStatus.PASSED),
        ])
        assert prd.get_next_task() is None
        assert prd.progress_pct == 100.0


class TestAgentResult:
    def test_success(self):
        r = AgentResult(success=True, final_response="done", cost_usd=0.05)
        assert r.success
        assert r.cost_usd == 0.05

    def test_failure(self):
        r = AgentResult(success=False, error="boom")
        assert not r.success
        assert r.error == "boom"


class TestQAResult:
    def test_passed(self):
        qa = QAResult(passed=True)
        assert qa.passed
        assert qa.issues == []

    def test_failed_with_issues(self):
        qa = QAResult(passed=False, issues=["test fails", "no coverage"])
        assert not qa.passed
        assert len(qa.issues) == 2
