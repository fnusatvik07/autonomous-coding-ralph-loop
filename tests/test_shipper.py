"""Tests for shipper agent."""

from ralph.shipper import is_gh_available, has_remote, _build_pr_body
from ralph.models import PRD, Feature, Task, TaskStatus


class TestShipperUtils:
    def test_gh_available_returns_bool(self):
        result = is_gh_available()
        assert isinstance(result, bool)

    def test_has_remote_no_git(self, tmp_path):
        assert has_remote(str(tmp_path)) is False


class TestBuildPRBody:
    def test_generates_markdown(self):
        prd = PRD(
            project_name="test-project",
            description="A test project",
            features=[
                Feature(id="F-1", title="Core", priority=1, tasks=[
                    Task(id="T-1", title="Create app", status=TaskStatus.PASSED),
                    Task(id="T-2", title="Add tests", status=TaskStatus.PASSED),
                ]),
                Feature(id="F-2", title="Polish", priority=2, tasks=[
                    Task(id="T-3", title="Add docs", status=TaskStatus.FAILED, notes="blocked by missing info"),
                ]),
            ],
        )
        body = _build_pr_body(
            prd,
            completed=[t for t in prd.tasks if t.status == TaskStatus.PASSED],
            failed=[t for t in prd.tasks if t.status == TaskStatus.FAILED],
            cost=3.50,
        )
        assert "## Summary" in body
        assert "test-project" in body
        assert "T-1" in body
        assert "T-2" in body
        assert "Tasks Failed" in body
        assert "T-3" in body
        assert "$3.50" in body
        assert "Ralph Loop" in body

    def test_no_failures(self):
        prd = PRD(
            project_name="clean",
            features=[Feature(id="F-1", title="All", tasks=[
                Task(id="T-1", title="Done", status=TaskStatus.PASSED),
            ])],
        )
        body = _build_pr_body(prd, completed=prd.tasks, failed=[], cost=1.0)
        assert "Tasks Failed" not in body
