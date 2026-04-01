"""Tests for multi-model routing."""

from ralph.routing import classify_task, get_model_for_task, get_model_for_phase, Complexity


class TestClassifyTask:
    def test_simple_scaffold(self):
        assert classify_task("Project scaffold", "init project setup", []) == Complexity.SIMPLE

    def test_simple_rename(self):
        assert classify_task("Rename variable", "rename typo in format function", ["works"]) == Complexity.SIMPLE

    def test_moderate_feature(self):
        result = classify_task(
            "Add user model",
            "Create user database model with id, name, email fields",
            ["Model has id", "Model has name", "Migration works"],
        )
        assert result == Complexity.MODERATE

    def test_complex_refactor(self):
        result = classify_task(
            "Refactor authentication system",
            "Redesign the multi-file authentication and authorization middleware to fix security race condition",
            ["No race condition", "All auth tests pass", "JWT validated", "Sessions work", "Rate limiting works"],
        )
        assert result == Complexity.COMPLEX

    def test_complex_debug(self):
        result = classify_task(
            "Debug flaky integration test",
            "Performance optimization: fix flaky test caused by race condition in database connection pool",
            ["Test passes 100/100 times", "No deadlock"],
        )
        assert result == Complexity.COMPLEX


class TestGetModelForTask:
    def test_override_always_wins(self):
        result = get_model_for_task("scaffold", "simple", [], override_model="my-model")
        assert result == "my-model"

    def test_routes_simple_to_haiku(self):
        result = get_model_for_task("rename typo", "fix typo in import", [], provider="claude-sdk")
        assert "haiku" in result

    def test_routes_complex_to_opus(self):
        result = get_model_for_task(
            "Refactor auth middleware",
            "Multi-file redesign of security authentication system to fix race condition",
            ["No race", "All pass", "JWT works", "Sessions work", "Rate limit"],
            provider="claude-sdk",
        )
        assert "opus" in result

    def test_langchain_format(self):
        result = get_model_for_task("scaffold init", "setup boilerplate", [], provider="deep-agents")
        assert result.startswith("anthropic:")


class TestGetModelForPhase:
    def test_spec_uses_complex(self):
        result = get_model_for_phase("spec", "claude-sdk")
        assert "opus" in result

    def test_qa_uses_moderate(self):
        result = get_model_for_phase("qa", "claude-sdk")
        assert "sonnet" in result

    def test_override_wins(self):
        result = get_model_for_phase("spec", override_model="my-model")
        assert result == "my-model"
