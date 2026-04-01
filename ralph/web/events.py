"""Event system for real-time WebSocket streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("ralph")


class EventType(str, Enum):
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_ERROR = "run_error"
    ITERATION_STARTED = "iteration_started"
    AGENT_TEXT = "agent_text"
    AGENT_TOOL_CALL = "agent_tool_call"
    SESSION_COMPLETE = "session_complete"
    TASK_STATUS_CHANGED = "task_status_changed"
    QA_RESULT = "qa_result"
    COST_UPDATE = "cost_update"
    PRD_UPDATED = "prd_updated"
    SPEC_AWAITING_APPROVAL = "spec_awaiting_approval"
    BUDGET_WARNING = "budget_warning"


class EventBus:
    """Broadcast events to all connected WebSocket clients."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers = [s for s in self._subscribers if s is not q]

    def emit(self, event_type: EventType, data: dict[str, Any] | None = None) -> None:
        event = {
            "type": event_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# Global event bus singleton
event_bus = EventBus()
