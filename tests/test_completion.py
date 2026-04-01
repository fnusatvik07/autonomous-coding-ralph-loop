"""Tests for completion and blocked detection in the loop."""

from ralph.loop import _detect_completion, _detect_blocked


class TestDetectCompletion:
    def test_xml_marker_matching_id(self, tmp_path):
        resp = "Done! <ralph:task_complete>TASK-001</ralph:task_complete>"
        assert _detect_completion(resp, str(tmp_path), "TASK-001") is True

    def test_xml_marker_wrong_id(self, tmp_path):
        resp = "<ralph:task_complete>TASK-002</ralph:task_complete>"
        assert _detect_completion(resp, str(tmp_path), "TASK-001") is False

    def test_no_marker(self, tmp_path):
        resp = "I'm still working on this..."
        assert _detect_completion(resp, str(tmp_path), "TASK-001") is False

    def test_phrase_with_current_task_id(self, tmp_path):
        resp = "I successfully implemented TASK-005 and all tests pass."
        assert _detect_completion(resp, str(tmp_path), "TASK-005") is True

    def test_phrase_with_wrong_task_id(self, tmp_path):
        """Regression: should NOT match old task IDs from previous iterations."""
        resp = "This is similar to TASK-001 which was done before. I successfully implemented the feature."
        assert _detect_completion(resp, str(tmp_path), "TASK-003") is False

    def test_prd_signal_matching_task(self, tmp_path):
        """Signal 2: agent updated prd.json directly."""
        import json
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        prd = {"tasks": [{"id": "TASK-001", "status": "passed"}]}
        (ralph_dir / "prd.json").write_text(json.dumps(prd))
        assert _detect_completion("no marker", str(tmp_path), "TASK-001") is True

    def test_prd_signal_stale_task(self, tmp_path):
        """Regression: stale passed task should NOT trigger for different current task."""
        import json
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        prd = {"tasks": [
            {"id": "TASK-001", "status": "passed"},  # old, already done
            {"id": "TASK-002", "status": "pending"},  # current
        ]}
        (ralph_dir / "prd.json").write_text(json.dumps(prd))
        assert _detect_completion("no marker", str(tmp_path), "TASK-002") is False

    def test_us_prefix(self, tmp_path):
        resp = "Task complete! <ralph:task_complete>US-001</ralph:task_complete>"
        assert _detect_completion(resp, str(tmp_path), "US-001") is True


class TestDetectBlocked:
    def test_xml_blocked(self):
        resp = "<ralph:task_blocked>missing dependency X</ralph:task_blocked>"
        assert _detect_blocked(resp) == "missing dependency X"

    def test_no_blocked(self):
        assert _detect_blocked("Everything is fine") is None

    def test_cannot_proceed(self):
        resp = "I cannot proceed because the database is not configured."
        result = _detect_blocked(resp)
        assert result is not None
        assert "cannot proceed" in result.lower()

    def test_stuck(self):
        resp = "I am stuck and unable to fix this circular import issue."
        assert _detect_blocked(resp) is not None
