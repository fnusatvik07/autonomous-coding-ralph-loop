"""Claude Agent SDK provider - wraps the real Claude Code CLI.

Uses ClaudeSDKClient with:
- PreToolUse hooks with REGEX safety (not substring)
- Retry with exponential backoff + jitter
- ProcessError structured handling
- acceptEdits permission model with add_dirs
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from typing import Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ProcessError,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)

from ralph.models import AgentResult
from ralph.providers.base import BaseProvider

logger = logging.getLogger("ralph")

# Regex patterns for dangerous commands - NOT bypassable with spacing tricks
BLOCKED_PATTERNS_RE = [
    r"\brm\s+(-\w+\s+)*-?r\w*f\w*\s+[/~.]",  # rm -rf / variants
    r"\brm\s+(-\w+\s+)*-f\s+(-\w+\s+)*-r\s+[/~.]",  # rm -f -r / (reversed flags)
    r"\brm\s+(-\w+\s+)*-r\s+(-\w+\s+)*-f\s+[/~.]",  # rm -r -f / (separated flags)
    r"\bsudo\b",
    r"/usr/bin/sudo\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r":\(\)\s*\{",  # fork bomb
    r">\s*/dev/sd",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bcurl\b.*\|\s*\bbash\b",  # pipe to bash
    r"\bchmod\s+777\b",
    r"\bchown\b.*root",
]


def _is_dangerous_command(cmd: str) -> str | None:
    """Check if a command matches any dangerous pattern. Returns pattern or None."""
    for pattern in BLOCKED_PATTERNS_RE:
        if re.search(pattern, cmd):
            return pattern
    return None


class ClaudeSDKProvider(BaseProvider):
    """Provider using the Claude Agent SDK (wraps Claude Code CLI)."""

    def __init__(self, model: str, workspace_dir: str, **kwargs):
        super().__init__(model, workspace_dir)
        self._extra_env = kwargs.get("env", {})
        self._max_retries = kwargs.get("max_retries", 3)
        self._retry_delay = kwargs.get("retry_delay", 5.0)
        self._max_budget_usd = kwargs.get("max_budget_usd", 0.0)

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
                logger.error("claude-sdk failed (attempt %d): %s", attempt, last_error)
                return result

            # Exponential backoff WITH jitter
            delay = self._retry_delay * (2 ** (attempt - 1))
            jitter = random.uniform(0, delay * 0.3)
            total_delay = delay + jitter
            logger.warning(
                "claude-sdk retryable error (attempt %d/%d), retry in %.1fs: %s",
                attempt, self._max_retries, total_delay, last_error[:200],
            )
            await asyncio.sleep(total_delay)

        return AgentResult(success=False, error=last_error)

    async def _try_session(
        self,
        system_prompt: str,
        user_message: str,
        max_turns: int,
        on_text: Callable[[str], None] | None,
        on_tool: Callable[[str, dict], None] | None,
    ) -> AgentResult:
        async def bash_safety_hook(input_data, tool_use_id, session):
            cmd = input_data.get("tool_input", {}).get("command", "")
            blocked = _is_dangerous_command(cmd)
            if blocked:
                logger.warning("BLOCKED dangerous bash (pattern=%s): %s", blocked, cmd[:100])
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"Blocked dangerous command matching: {blocked}",
                    }
                }
            return {}

        opts: dict = {
            "system_prompt": system_prompt,
            "allowed_tools": ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebFetch"],
            "permission_mode": "acceptEdits",
            "cwd": str(self.workspace_dir),
            "add_dirs": [str(self.workspace_dir)],
            "max_turns": max_turns,
            "env": self._extra_env,
            "hooks": {
                "PreToolUse": [HookMatcher(matcher="Bash", hooks=[bash_safety_hook])],
            },
        }
        if self.model:
            opts["model"] = self.model
        if self._max_budget_usd > 0:
            opts["max_budget_usd"] = self._max_budget_usd

        options = ClaudeAgentOptions(**opts)
        total_cost = 0.0
        final_text_parts: list[str] = []
        tool_calls = 0
        start = time.monotonic()

        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(user_message)
                async for msg in client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                final_text_parts.append(block.text)
                                if on_text:
                                    on_text(block.text)
                            elif isinstance(block, ToolUseBlock):
                                tool_calls += 1
                                if on_tool:
                                    on_tool(block.name, block.input)
                            elif isinstance(block, ThinkingBlock):
                                pass  # Extended thinking - not surfaced
                            else:
                                logger.debug("unhandled block: %s", type(block).__name__)
                    elif isinstance(msg, ResultMessage):
                        total_cost = getattr(msg, "total_cost_usd", 0.0) or 0.0
                    else:
                        logger.debug("unhandled message: %s", type(msg).__name__)

            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(
                success=True,
                final_response="\n".join(final_text_parts),
                tool_calls_made=tool_calls,
                cost_usd=total_cost,
                duration_ms=elapsed,
            )

        except ProcessError as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(
                success=False,
                final_response="\n".join(final_text_parts),
                error=f"ProcessError(exit={getattr(e, 'exit_code', '?')}): {e}",
                tool_calls_made=tool_calls,
                cost_usd=total_cost,
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(
                success=False,
                final_response="\n".join(final_text_parts),
                error=str(e),
                tool_calls_made=tool_calls,
                cost_usd=total_cost,
                duration_ms=elapsed,
            )
