"""Claude Agent SDK provider — uses the official query() API.

Authentication: set ANTHROPIC_API_KEY in .env (or Foundry/Bedrock/Vertex env vars).
The SDK reads these automatically — no manual key passing needed.

Docs: https://platform.claude.com/docs/en/agent-sdk/overview
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from typing import Callable

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    HookMatcher,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)

from ralph.models import AgentResult
from ralph.providers.base import BaseProvider

logger = logging.getLogger("ralph")

# Regex patterns for dangerous bash commands
BLOCKED_PATTERNS_RE = [
    r"\brm\s+(-\w+\s+)*-?r\w*f\w*\s+[/~.]",
    r"\brm\s+(-\w+\s+)*-f\s+(-\w+\s+)*-r\s+[/~.]",
    r"\brm\s+(-\w+\s+)*-r\s+(-\w+\s+)*-f\s+[/~.]",
    r"\bsudo\b",
    r"/usr/bin/sudo\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r":\(\)\s*\{",
    r">\s*/dev/sd",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bcurl\b.*\|\s*\bbash\b",
    r"\bchmod\s+777\b",
    r"\bchown\b.*root",
]


def _is_dangerous_command(cmd: str) -> str | None:
    for pattern in BLOCKED_PATTERNS_RE:
        if re.search(pattern, cmd):
            return pattern
    return None


class ClaudeSDKProvider(BaseProvider):
    """Provider using the Claude Agent SDK query() API.

    The SDK handles the full agent loop: tool calls, execution, retries.
    We just provide prompts and receive results.

    Auth is handled via environment variables (loaded from .env by dotenv):
    - Direct API: ANTHROPIC_API_KEY
    - Azure Foundry: CLAUDE_CODE_USE_FOUNDRY=1 + ANTHROPIC_FOUNDRY_API_KEY + ANTHROPIC_FOUNDRY_BASE_URL
    - AWS Bedrock: CLAUDE_CODE_USE_BEDROCK=1 + AWS credentials
    - Google Vertex: CLAUDE_CODE_USE_VERTEX=1 + Google Cloud credentials
    """

    def __init__(self, model: str, workspace_dir: str, **kwargs):
        super().__init__(model, workspace_dir)
        self._env = kwargs.get("env", {})
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
                logger.error("claude-agent-sdk failed (attempt %d): %s", attempt, last_error)
                return result

            delay = self._retry_delay * (2 ** (attempt - 1))
            jitter = random.uniform(0, delay * 0.3)
            total_delay = delay + jitter
            logger.warning(
                "claude-agent-sdk retry %d/%d in %.1fs: %s",
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
        # Bash safety hook — blocks dangerous commands
        async def bash_safety_hook(input_data, tool_use_id, session):
            cmd = input_data.get("tool_input", {}).get("command", "")
            blocked = _is_dangerous_command(cmd)
            if blocked:
                logger.warning("BLOCKED dangerous bash: %s", cmd[:100])
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"Blocked: {blocked}",
                    }
                }
            return {}

        # Built-in tools
        allowed = ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebFetch"]

        # Puppeteer MCP for browser testing (optional)
        use_puppeteer = self._env.get("RALPH_ENABLE_PUPPETEER", "") == "1"
        if use_puppeteer:
            allowed += [
                "mcp__puppeteer__puppeteer_navigate",
                "mcp__puppeteer__puppeteer_screenshot",
                "mcp__puppeteer__puppeteer_click",
                "mcp__puppeteer__puppeteer_fill",
                "mcp__puppeteer__puppeteer_evaluate",
            ]

        # Build options
        opts: dict = {
            "system_prompt": system_prompt,
            "allowed_tools": allowed,
            "permission_mode": "acceptEdits",
            "cwd": str(self.workspace_dir),
            "add_dirs": [str(self.workspace_dir)],
            "max_turns": max_turns,
            "env": self._env,
            "hooks": {
                "PreToolUse": [HookMatcher(matcher="Bash", hooks=[bash_safety_hook])],
            },
        }

        if self.model:
            opts["model"] = self.model
        if self._max_budget_usd > 0:
            opts["max_budget_usd"] = self._max_budget_usd

        # Sandbox (optional, requires Docker)
        if self._env.get("RALPH_ENABLE_SANDBOX", "") == "1":
            opts["sandbox"] = {
                "enabled": True,
                "autoAllowBashIfSandboxed": True,
            }

        # Puppeteer MCP server
        if use_puppeteer:
            opts["mcp_servers"] = {
                "puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]}
            }

        options = ClaudeAgentOptions(**opts)
        final_text_parts: list[str] = []
        tool_calls = 0
        total_cost = 0.0
        start = time.monotonic()

        try:
            # Use the query() API — the SDK handles the full agent loop
            async for message in query(prompt=user_message, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            final_text_parts.append(block.text)
                            if on_text:
                                on_text(block.text)
                        elif isinstance(block, ToolUseBlock):
                            tool_calls += 1
                            if on_tool:
                                on_tool(block.name, block.input)
                        elif isinstance(block, ThinkingBlock):
                            pass  # Extended thinking — not surfaced

                elif isinstance(message, ResultMessage):
                    total_cost = message.total_cost_usd or 0.0

            elapsed = int((time.monotonic() - start) * 1000)
            return AgentResult(
                success=True,
                final_response="\n".join(final_text_parts),
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
