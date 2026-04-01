"""Tests for auto-formatting module."""

import pytest
from ralph.formatting import auto_format, auto_lint


class TestAutoFormat:
    @pytest.mark.asyncio
    async def test_returns_tuple(self, workspace):
        success, output = await auto_format(str(workspace))
        assert isinstance(success, bool)
        assert isinstance(output, str)

    @pytest.mark.asyncio
    async def test_lint_returns_tuple(self, workspace):
        success, output = await auto_lint(str(workspace))
        assert isinstance(success, bool)
        assert isinstance(output, str)
