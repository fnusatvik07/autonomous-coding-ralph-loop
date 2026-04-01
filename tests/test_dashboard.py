"""Tests for web dashboard."""

import json
from ralph.dashboard import generate_dashboard_html


class TestDashboard:
    def test_generates_html(self, workspace_with_ralph):
        html = generate_dashboard_html(str(workspace_with_ralph))
        assert "<!DOCTYPE html>" in html
        assert "Ralph Loop Dashboard" in html

    def test_with_prd_data(self, workspace_with_prd):
        html = generate_dashboard_html(str(workspace_with_prd))
        assert "test-project" in html
        assert "TASK-001" in html

    def test_with_sessions(self, workspace_with_ralph):
        # Write a session entry
        sessions = workspace_with_ralph / ".ralph" / "sessions.jsonl"
        entry = {"iteration": 1, "phase": "coding", "task_id": "T-1",
                 "success": True, "cost_usd": 0.15, "duration_ms": 5000, "tool_calls": 10}
        sessions.write_text(json.dumps(entry) + "\n")
        html = generate_dashboard_html(str(workspace_with_ralph))
        assert "$0.15" in html or "0.1500" in html

    def test_empty_workspace(self, workspace_with_ralph):
        # Should not crash with no data
        html = generate_dashboard_html(str(workspace_with_ralph))
        assert "Ralph Loop Dashboard" in html
