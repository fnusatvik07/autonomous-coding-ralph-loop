"""Tests for GitHub PR creation."""

from ralph.github_pr import generate_pr_body, is_gh_available


class TestGeneratePRBody:
    def test_generates_markdown(self):
        body = generate_pr_body(
            project_name="test-project",
            tasks_completed=[
                {"id": "T-1", "title": "Add feature"},
                {"id": "T-2", "title": "Add tests"},
            ],
            total_cost=1.50,
            total_tests=15,
        )
        assert "## Summary" in body
        assert "test-project" in body
        assert "T-1" in body
        assert "T-2" in body
        assert "$1.50" in body
        assert "15" in body
        assert "Ralph Loop" in body

    def test_empty_tasks(self):
        body = generate_pr_body("x", [], 0.0, 0)
        assert "## Summary" in body


class TestGHAvailability:
    def test_returns_bool(self):
        result = is_gh_available()
        assert isinstance(result, bool)
