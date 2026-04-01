"""Tests for provider creation and mock provider."""

import pytest
from ralph.providers import create_provider, PROVIDERS
from ralph.providers.claude_sdk import ClaudeSDKProvider
from ralph.providers.deep_agents import DeepAgentsProvider
from ralph.models import AgentResult
from tests.conftest import MockProvider


class TestProviderFactory:
    def test_available_providers(self):
        assert "claude-sdk" in PROVIDERS
        assert "deep-agents" in PROVIDERS
        assert len(PROVIDERS) == 2

    def test_create_claude_sdk(self):
        p = create_provider("claude-sdk", model="test", workspace_dir="/tmp")
        assert isinstance(p, ClaudeSDKProvider)

    def test_create_deep_agents(self):
        p = create_provider("deep-agents", model="test", workspace_dir="/tmp")
        assert isinstance(p, DeepAgentsProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider("nonexistent", model="x", workspace_dir="/tmp")


class TestMockProvider:
    @pytest.mark.asyncio
    async def test_returns_canned_response(self):
        mock = MockProvider(
            responses=[
                AgentResult(success=True, final_response="Hello!"),
            ],
            workspace_dir="/tmp",
        )
        result = await mock.run_session(
            system_prompt="test", user_message="hi"
        )
        assert result.success
        assert result.final_response == "Hello!"

    @pytest.mark.asyncio
    async def test_logs_calls(self):
        mock = MockProvider(
            responses=[AgentResult(success=True, final_response="ok")],
            workspace_dir="/tmp",
        )
        await mock.run_session(
            system_prompt="sys", user_message="user msg"
        )
        assert len(mock.call_log) == 1
        assert "sys" in mock.call_log[0]["system_prompt"]
        assert "user msg" in mock.call_log[0]["user_message"]

    @pytest.mark.asyncio
    async def test_exhausted_responses(self):
        mock = MockProvider(responses=[], workspace_dir="/tmp")
        result = await mock.run_session(
            system_prompt="test", user_message="hi"
        )
        assert not result.success
        assert "No more mock responses" in result.error

    @pytest.mark.asyncio
    async def test_mock_file_write(self, tmp_path):
        mock = MockProvider(
            responses=[
                AgentResult(
                    success=True,
                    final_response="MOCK_WRITE:.ralph/prd.json:{\"project_name\": \"test\", \"tasks\": []}",
                ),
            ],
            workspace_dir=str(tmp_path),
        )
        await mock.run_session(system_prompt="s", user_message="u")
        assert (tmp_path / ".ralph" / "prd.json").exists()

    @pytest.mark.asyncio
    async def test_on_text_callback(self):
        texts = []
        mock = MockProvider(
            responses=[AgentResult(success=True, final_response="streamed text")],
            workspace_dir="/tmp",
        )
        await mock.run_session(
            system_prompt="s", user_message="u",
            on_text=lambda t: texts.append(t),
        )
        assert "streamed text" in texts
