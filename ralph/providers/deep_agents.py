"""Deep Agents SDK provider - LangGraph-based deep agent.

Fixed issues from real testing:
- Sets API key in os.environ so langchain can authenticate
- Estimates cost from token usage via langchain callbacks
- Proper logging integration
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from typing import Callable

from ralph.models import AgentResult
from ralph.providers.base import BaseProvider

logger = logging.getLogger("ralph")

# Same safety patterns as claude_sdk
BLOCKED_PATTERNS_RE = [
    r"\brm\s+(-\w+\s+)*-?r\w*f\w*\s+[/~.]",
    r"\brm\s+(-\w+\s+)*-r\s+(-\w+\s+)*-f\s+[/~.]",
    r"\bsudo\b", r"/usr/bin/sudo\b",
    r"\bshutdown\b", r"\breboot\b", r"\bpoweroff\b",
    r":\(\)\s*\{", r">\s*/dev/sd", r"\bmkfs\b", r"\bdd\s+if=",
    r"\bcurl\b.*\|\s*\bbash\b", r"\bchmod\s+777\b",
]

# Only these env vars are passed to agent shell subprocesses
SAFE_ENV_KEYS = {
    "PATH", "HOME", "USER", "SHELL", "LANG", "LC_ALL", "TERM",
    "TMPDIR", "PYTHONPATH", "NODE_PATH", "GOPATH",
}

# Rough cost estimates per 1K tokens (input/output) for common models
COST_PER_1K = {
    "claude-opus": (0.015, 0.075),
    "claude-sonnet": (0.003, 0.015),
    "claude-haiku": (0.00025, 0.00125),
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "o3": (0.01, 0.04),
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Rough cost estimate based on model name and token counts."""
    model_lower = model.lower()
    for key, (inp_cost, out_cost) in COST_PER_1K.items():
        if key in model_lower:
            return (input_tokens / 1000 * inp_cost) + (output_tokens / 1000 * out_cost)
    return 0.0  # Unknown model


class DeepAgentsProvider(BaseProvider):
    """Provider using the Deep Agents SDK (LangGraph-based).

    Works with any LangChain model: anthropic:claude-sonnet-4-20250514,
    openai:gpt-4o, etc. Set the API key for your chosen provider.
    """

    def __init__(self, model: str, workspace_dir: str, **kwargs):
        super().__init__(model, workspace_dir)
        self._api_key = kwargs.get("api_key", "")
        self._max_retries = kwargs.get("max_retries", 3)
        self._retry_delay = kwargs.get("retry_delay", 5.0)

    async def run_session(
        self,
        system_prompt: str,
        user_message: str,
        max_turns: int = 200,
        on_text: Callable[[str], None] | None = None,
        on_tool: Callable[[str, dict], None] | None = None,
    ) -> AgentResult:
        last_error = ""

        for attempt in range(1, self._max_retries + 1):
            result = await self._try_session(
                system_prompt, user_message, max_turns, on_text, on_tool
            )
            if result.success:
                return result

            last_error = result.error
            is_retryable = any(s in last_error.lower() for s in [
                "rate limit", "overloaded", "timeout", "connection",
                "529", "503", "502", "500",
            ])

            if not is_retryable or attempt == self._max_retries:
                logger.error("deep-agents failed (attempt %d): %s", attempt, last_error)
                return result

            delay = self._retry_delay * (2 ** (attempt - 1))
            jitter = random.uniform(0, delay * 0.3)
            logger.warning("deep-agents retry %d/%d in %.1fs", attempt, self._max_retries, delay + jitter)
            await asyncio.sleep(delay + jitter)

        return AgentResult(success=False, error=last_error)

    async def _try_session(
        self,
        system_prompt: str,
        user_message: str,
        max_turns: int,
        on_text: Callable[[str], None] | None,
        on_tool: Callable[[str, dict], None] | None,
    ) -> AgentResult:
        from deepagents import create_deep_agent
        from deepagents.backends import LocalShellBackend

        # Set API key so langchain can authenticate
        if self._api_key:
            if "anthropic" in self.model.lower() or "claude" in self.model.lower():
                os.environ["ANTHROPIC_API_KEY"] = self._api_key
            else:
                os.environ["OPENAI_API_KEY"] = self._api_key

        safe_env = {k: v for k, v in os.environ.items() if k in SAFE_ENV_KEYS}

        agent = create_deep_agent(
            model=self.model,
            system_prompt=system_prompt,
            backend=LocalShellBackend(root_dir=self.workspace_dir, env=safe_env),
            debug=False,
        )

        start = time.monotonic()
        tool_calls = 0
        final_text = ""
        total_input_tokens = 0
        total_output_tokens = 0

        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": user_message}]},
                config={"recursion_limit": max_turns},
            )

            messages = result.get("messages", [])

            for msg in messages:
                # Count tool calls
                tc = getattr(msg, "tool_calls", [])
                tool_calls += len(tc)
                if tc and on_tool:
                    for call in tc:
                        on_tool(call.get("name", "?"), call.get("args", {}))

                # Track token usage from response metadata
                usage = getattr(msg, "usage_metadata", None)
                if usage:
                    total_input_tokens += getattr(usage, "input_tokens", 0) or usage.get("input_tokens", 0) if isinstance(usage, dict) else 0
                    total_output_tokens += getattr(usage, "output_tokens", 0) or usage.get("output_tokens", 0) if isinstance(usage, dict) else 0

            # Extract final text
            for msg in reversed(messages):
                if getattr(msg, "type", "") != "ai":
                    continue
                content = getattr(msg, "content", "")
                if isinstance(content, str) and content.strip():
                    final_text = content
                    break
                if isinstance(content, list):
                    text_parts = [
                        b.get("text", "") if isinstance(b, dict) else str(b)
                        for b in content
                        if (isinstance(b, dict) and b.get("type") == "text") or isinstance(b, str)
                    ]
                    combined = "\n".join(p for p in text_parts if p.strip())
                    if combined:
                        final_text = combined
                        break

            if on_text and final_text:
                on_text(final_text)

            elapsed = int((time.monotonic() - start) * 1000)
            estimated_cost = _estimate_cost(self.model, total_input_tokens, total_output_tokens)

            if estimated_cost > 0:
                logger.info("deep-agents tokens: in=%d out=%d est_cost=$%.4f",
                            total_input_tokens, total_output_tokens, estimated_cost)

            return AgentResult(
                success=True,
                final_response=final_text,
                tool_calls_made=tool_calls,
                cost_usd=estimated_cost,
                duration_ms=elapsed,
            )

        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(
                success=False,
                error=str(e),
                tool_calls_made=tool_calls,
                duration_ms=elapsed,
            )
