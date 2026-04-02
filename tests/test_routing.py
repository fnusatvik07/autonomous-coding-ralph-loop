"""Tests for multi-model routing and review gating."""

from ralph.routing import (
    classify_task, get_model_for_task, get_model_for_phase, Complexity,
    classify_review_need, should_review_feature,
)
from ralph.models import Task, Feature


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
        assert get_model_for_task("scaffold", "simple", [], override_model="my-model") == "my-model"

    def test_routes_simple_to_haiku(self):
        assert "haiku" in get_model_for_task("rename typo", "fix typo in import", [], provider="claude-sdk")

    def test_routes_complex_to_opus(self):
        result = get_model_for_task(
            "Refactor auth middleware",
            "Multi-file redesign of security authentication system to fix race condition",
            ["No race", "All pass", "JWT works", "Sessions work", "Rate limit"],
            provider="claude-sdk",
        )
        assert "opus" in result

    def test_langchain_format(self):
        assert get_model_for_task("scaffold init", "setup boilerplate", [], provider="deep-agents").startswith("anthropic:")


class TestGetModelForPhase:
    def test_spec_uses_complex(self):
        assert "opus" in get_model_for_phase("spec", "claude-sdk")

    def test_qa_uses_moderate(self):
        assert "sonnet" in get_model_for_phase("qa", "claude-sdk")

    def test_override_wins(self):
        assert get_model_for_phase("spec", override_model="my-model") == "my-model"


class TestClassifyReviewNeed:
    def test_simple_validation_task(self):
        t = Task(id="T-1", category="validation", title="POST rejects empty name",
                 acceptance_criteria=["returns 422"])
        assert classify_review_need(t) == "simple"

    def test_simple_functional_few_criteria(self):
        t = Task(id="T-1", category="functional", title="Create pyproject.toml",
                 acceptance_criteria=["file exists", "deps listed"])
        assert classify_review_need(t) == "simple"

    def test_moderate_functional_multiple_criteria(self):
        t = Task(id="T-1", category="functional", title="POST /books creates a book",
                 acceptance_criteria=["returns 201", "body has id", "stored in DB", "author linked"])
        assert classify_review_need(t) == "moderate"

    def test_complex_integration(self):
        t = Task(id="T-1", category="integration", title="Author-Book cascade delete",
                 description="Integration test for cascade behavior",
                 acceptance_criteria=["create author", "create books", "delete author", "books gone", "verify DB clean"])
        assert classify_review_need(t) == "complex"

    def test_complex_security_keyword(self):
        t = Task(id="T-1", category="functional", title="Add JWT authentication middleware",
                 description="Implement auth security token validation with encryption",
                 acceptance_criteria=["token validated", "expired rejected", "refresh works", "audit logged", "rate limited"])
        assert classify_review_need(t) == "complex"

    def test_moderate_auth_few_criteria(self):
        t = Task(id="T-1", category="functional", title="Add auth check",
                 description="Implement token validation",
                 acceptance_criteria=["token validated", "expired rejected"])
        assert classify_review_need(t) == "moderate"

    def test_complex_error_handling_many_criteria(self):
        t = Task(id="T-1", category="error_handling", title="Handle concurrent updates",
                 acceptance_criteria=["lock acquired", "conflict detected", "retry works", "data consistent", "no deadlock"])
        assert classify_review_need(t) == "complex"


class TestShouldReviewFeature:
    def test_all_simple_no_review(self):
        f = Feature(id="F-1", title="Setup", tasks=[
            Task(id="T-1", category="functional", title="Create file", acceptance_criteria=["exists"]),
            Task(id="T-2", category="validation", title="Reject empty", acceptance_criteria=["422"]),
        ])
        assert should_review_feature(f) is False

    def test_one_complex_needs_review(self):
        f = Feature(id="F-1", title="Auth", tasks=[
            Task(id="T-1", category="functional", title="Create file", acceptance_criteria=["exists"]),
            Task(id="T-2", category="integration", title="Auth middleware integration",
                 description="Security token validation",
                 acceptance_criteria=["token works", "expired rejected", "missing rejected", "refresh works", "audit logged"]),
        ])
        assert should_review_feature(f) is True

    def test_two_moderate_needs_review(self):
        f = Feature(id="F-1", title="CRUD", tasks=[
            Task(id="T-1", category="functional", title="POST creates item",
                 acceptance_criteria=["201", "body correct", "stored", "timestamps"]),
            Task(id="T-2", category="functional", title="PUT updates item",
                 acceptance_criteria=["200", "body updated", "stored", "timestamps"]),
        ])
        assert should_review_feature(f) is True

    def test_one_moderate_no_review(self):
        f = Feature(id="F-1", title="Simple", tasks=[
            Task(id="T-1", category="functional", title="GET returns list",
                 acceptance_criteria=["200", "array", "correct count"]),
            Task(id="T-2", category="validation", title="Rejects bad input",
                 acceptance_criteria=["422"]),
        ])
        assert should_review_feature(f) is False
