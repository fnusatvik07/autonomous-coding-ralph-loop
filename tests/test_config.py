"""Tests for configuration."""

import pytest
from ralph.config import Config


class TestConfig:
    def test_defaults(self):
        c = Config()
        assert c.provider == "claude-sdk"
        assert c.max_iterations == 50
        assert c.max_incomplete_retries == 3
        assert c.session_timeout_seconds == 600

    def test_load_with_overrides(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("RALPH_PROVIDER=deep-agents\nRALPH_MODEL=gpt-4o\n")
        c = Config.load(env_file=str(env_file))
        assert c.provider == "deep-agents"
        assert c.model == "gpt-4o"

    def test_cli_overrides_env(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("RALPH_PROVIDER=deep-agents\n")
        c = Config.load(provider="claude-sdk", env_file=str(env_file))
        assert c.provider == "claude-sdk"

    def test_default_model_per_provider(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("")
        monkeypatch.delenv("RALPH_MODEL", raising=False)
        monkeypatch.delenv("ANTHROPIC_DEFAULT_SONNET_MODEL", raising=False)
        monkeypatch.delenv("ANTHROPIC_DEFAULT_OPUS_MODEL", raising=False)
        c = Config.load(provider="claude-sdk", env_file=str(env_file))
        assert c.model == "claude-sonnet-4-20250514"
        c = Config.load(provider="deep-agents", env_file=str(env_file))
        assert c.model == "anthropic:claude-sonnet-4-20250514"

    def test_approve_spec_flag(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("")
        c = Config.load(approve_spec=True, env_file=str(env_file))
        assert c.approve_spec is True

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="provider must be"):
            Config(provider="nonexistent")

    def test_foundry_validation(self):
        with pytest.raises(ValueError, match="foundry_api_key"):
            Config(use_foundry=True, foundry_api_key="", foundry_base_url="https://x")

    def test_max_iterations_zero(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("")
        c = Config.load(max_iterations=0, env_file=str(env_file))
        assert c.max_iterations == 0

    def test_budget_zero_means_unlimited(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("")
        c = Config.load(max_budget_usd=0.0, env_file=str(env_file))
        assert c.max_budget_usd == 0.0
