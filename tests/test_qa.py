"""Tests for QA sentinel result parsing (brace-depth, not regex)."""

from ralph.qa.sentinel import _extract_qa_json


class TestExtractQAJson:
    def test_json_in_code_block(self):
        text = '```json\n{"passed": true, "issues": [], "test_output": "ok"}\n```'
        result = _extract_qa_json(text)
        assert result is not None
        assert result["passed"] is True

    def test_failed_result(self):
        text = '```json\n{"passed": false, "issues": ["test_x fails"], "test_output": "1 failed"}\n```'
        result = _extract_qa_json(text)
        assert result is not None
        assert result["passed"] is False
        assert len(result["issues"]) == 1

    def test_inline_json(self):
        text = 'The result is {"passed": true, "issues": []}'
        result = _extract_qa_json(text)
        assert result is not None
        assert result["passed"] is True

    def test_no_json(self):
        assert _extract_qa_json("No JSON verdict here.") is None

    def test_with_suggestions(self):
        text = '```json\n{"passed": true, "issues": [], "suggestions": ["add edge case"]}\n```'
        result = _extract_qa_json(text)
        assert result is not None
        assert result["suggestions"] == ["add edge case"]

    def test_nested_json(self):
        """Regression: old regex couldn't handle nested braces."""
        text = '{"passed": false, "issues": ["bad"], "metadata": {"version": 1, "details": {"x": 2}}}'
        result = _extract_qa_json(text)
        assert result is not None
        assert result["passed"] is False
        assert result["metadata"]["version"] == 1
