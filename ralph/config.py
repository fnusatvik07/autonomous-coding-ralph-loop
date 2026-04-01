"""Configuration management - loads from .env and CLI overrides."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator

DEFAULT_MODELS = {
    "claude-sdk": "claude-sonnet-4-20250514",
    "deep-agents": "anthropic:claude-sonnet-4-20250514",
}

VALID_PROVIDERS = {"claude-sdk", "deep-agents"}


class Config(BaseModel):
    """Ralph Loop configuration."""

    provider: str = Field(default="claude-sdk")
    model: str = Field(default="")

    anthropic_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")

    use_foundry: bool = Field(default=False)
    foundry_api_key: str = Field(default="")
    foundry_base_url: str = Field(default="")

    workspace_dir: Path = Field(default=Path("."))

    max_iterations: int = Field(default=50)
    max_healer_attempts: int = Field(default=5)
    max_turns_per_session: int = Field(default=200)
    max_incomplete_retries: int = Field(default=3)
    session_timeout_seconds: int = Field(default=600)

    max_budget_usd: float = Field(default=0.0)
    approve_spec: bool = Field(default=False)

    max_retries: int = Field(default=3)
    retry_delay_seconds: float = Field(default=5.0)

    # Multi-model routing
    auto_route_models: bool = Field(
        default=False,
        description="Auto-select model per task based on complexity",
    )

    # Reflexion
    enable_reflexion: bool = Field(
        default=True,
        description="LLM reflects on failures to learn from mistakes",
    )

    # Sandbox
    sandbox_enabled: bool = Field(default=False)
    sandbox_image: str = Field(default="python:3.13-slim")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v):
        if v not in VALID_PROVIDERS:
            raise ValueError(f"provider must be one of {VALID_PROVIDERS}, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_foundry(self):
        if self.use_foundry:
            if not self.foundry_api_key:
                raise ValueError("foundry_api_key required when use_foundry=True")
            if not self.foundry_base_url:
                raise ValueError("foundry_base_url required when use_foundry=True")
        return self

    @classmethod
    def load(
        cls,
        provider: str | None = None,
        model: str | None = None,
        workspace_dir: str | None = None,
        max_iterations: int | None = None,
        max_budget_usd: float | None = None,
        approve_spec: bool = False,
        env_file: str | None = None,
    ) -> Config:
        load_dotenv(env_file or ".env")

        cfg_provider = provider or os.getenv("RALPH_PROVIDER", "claude-sdk")
        cfg_model = model or os.getenv("RALPH_MODEL", "")
        if not cfg_model:
            # Respect Foundry model env vars if set
            cfg_model = (
                os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL")
                or os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL")
                or DEFAULT_MODELS.get(cfg_provider, "claude-sonnet-4-20250514")
            )

        return cls(
            provider=cfg_provider,
            model=cfg_model,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            use_foundry=os.getenv("CLAUDE_CODE_USE_FOUNDRY", "") == "1",
            foundry_api_key=os.getenv("ANTHROPIC_FOUNDRY_API_KEY", ""),
            foundry_base_url=os.getenv("ANTHROPIC_FOUNDRY_BASE_URL", ""),
            workspace_dir=Path(workspace_dir).resolve() if workspace_dir else Path.cwd(),
            max_iterations=max_iterations if max_iterations is not None else int(os.getenv("RALPH_MAX_ITERATIONS", "50")),
            max_healer_attempts=int(os.getenv("RALPH_MAX_HEALER_ATTEMPTS", "5")),
            max_turns_per_session=int(os.getenv("RALPH_MAX_TURNS", "200")),
            max_incomplete_retries=int(os.getenv("RALPH_MAX_INCOMPLETE_RETRIES", "3")),
            session_timeout_seconds=int(os.getenv("RALPH_SESSION_TIMEOUT", "600")),
            max_budget_usd=max_budget_usd if max_budget_usd is not None else float(os.getenv("RALPH_MAX_BUDGET_USD", "0")),
            max_retries=int(os.getenv("RALPH_MAX_RETRIES", "3")),
            retry_delay_seconds=float(os.getenv("RALPH_RETRY_DELAY", "5.0")),
            approve_spec=approve_spec,
        )
