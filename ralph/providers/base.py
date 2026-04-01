"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from ralph.models import AgentResult


class BaseProvider(ABC):
    """Base class for LLM providers.

    Each provider wraps an agent SDK that handles the full tool-use loop
    internally. Ralph just sends prompts and receives results.
    """

    def __init__(self, model: str, workspace_dir: str, **kwargs):
        self.model = model
        self.workspace_dir = workspace_dir

    @abstractmethod
    async def run_session(
        self,
        system_prompt: str,
        user_message: str,
        max_turns: int = 200,
        on_text: Callable[[str], None] | None = None,
        on_tool: Callable[[str, dict], None] | None = None,
    ) -> AgentResult:
        """Run a complete agent session.

        The SDK handles the full ReAct loop (tool calls, execution, etc.).
        We just provide the prompt and receive the result.

        Args:
            system_prompt: System instructions.
            user_message: The task prompt.
            max_turns: Max tool-use turns.
            on_text: Streaming callback for text output.
            on_tool: Callback when a tool is called (name, input).

        Returns:
            AgentResult with response, cost, and metadata.
        """
        ...
