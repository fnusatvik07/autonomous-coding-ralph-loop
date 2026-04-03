"""WebRalphLoop - subclass that emits WebSocket events during execution."""

from __future__ import annotations

import asyncio
import logging

from ralph.config import Config
from ralph.loop import RalphLoop
from ralph.models import PRD, QAResult, TaskStatus
from ralph.web.events import EventBus, EventType

logger = logging.getLogger("ralph")


class WebRalphLoop(RalphLoop):
    """RalphLoop that emits events to connected WebSocket clients."""

    def __init__(self, config: Config, event_bus: EventBus):
        super().__init__(config)
        self.event_bus = event_bus

    def on_text(self, text: str) -> None:
        """Override: emit text to WebSocket AND console."""
        super().on_text(text)
        if text.strip():
            self.event_bus.emit(EventType.AGENT_TEXT, {"text": text.strip()})

    def on_tool(self, name: str, tool_input: dict) -> None:
        """Override: emit tool call to WebSocket AND console."""
        super().on_tool(name, tool_input)
        self.event_bus.emit(EventType.AGENT_TOOL_CALL, {
            "tool_name": name,
        })

    async def run(self, task_description: str) -> None:
        self.event_bus.emit(EventType.RUN_STARTED, {
            "run_id": self.run_id,
            "task": task_description[:500],
            "provider": self.config.provider,
            "model": self.config.model,
        })
        try:
            await super().run(task_description)
            self.event_bus.emit(EventType.RUN_COMPLETED, {
                "run_id": self.run_id,
                "total_cost": self.cumulative_cost,
            })
        except Exception as e:
            self.event_bus.emit(EventType.RUN_ERROR, {
                "run_id": self.run_id,
                "error": str(e),
            })
            raise

    def request_stop(self) -> None:
        """Request graceful stop of the loop."""
        super().request_stop()
        logger.info("stop requested for run %s", self.run_id)
