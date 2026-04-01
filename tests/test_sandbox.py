"""Tests for sandbox module (unit tests only, no Docker required)."""

from ralph.sandbox import SandboxConfig, is_docker_available


class TestSandboxConfig:
    def test_defaults(self):
        cfg = SandboxConfig()
        assert cfg.enabled is False
        assert cfg.image == "python:3.13-slim"
        assert cfg.memory_limit == "2g"
        assert "pypi.org" in cfg.network_allow

    def test_custom_config(self):
        cfg = SandboxConfig(
            enabled=True,
            image="node:20-slim",
            extra_packages=["express"],
            memory_limit="4g",
        )
        assert cfg.enabled is True
        assert cfg.image == "node:20-slim"
        assert "express" in cfg.extra_packages


class TestDockerAvailability:
    def test_check_returns_bool(self):
        result = is_docker_available()
        assert isinstance(result, bool)
