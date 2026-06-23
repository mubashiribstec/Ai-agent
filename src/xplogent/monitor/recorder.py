"""TraceRecorder — persist the event stream and compute per-agent metrics.

Subscribes to a run's :class:`EventBus`, writes every event to the store
(tagged by run/agent), and maintains live metrics (steps, tool calls, approx
tokens, status) so the dashboard can show deep, per-agent telemetry.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from xplogent.core.events import EventBus, EventType
from xplogent.memory.store import Store


def _new_metric() -> dict[str, Any]:
    return {"name": "", "role": "", "steps": 0, "tool_calls": 0,
            "approx_tokens": 0, "input_tokens": 0, "output_tokens": 0,
            "status": "idle", "current_tool": None}


class TraceRecorder:
    def __init__(self, bus: EventBus, store: Store, run_id: str) -> None:
        self.bus = bus
        self.store = store
        self.run_id = run_id
        self.metrics: dict[str, dict[str, Any]] = defaultdict(_new_metric)
        self._queue = bus.subscribe()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._consume())

    async def _consume(self) -> None:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            data = event.data
            agent_id = str(data.get("agent_id", "")) or "_"
            # persist
            self.store.add_event(self.run_id, agent_id, str(event.type), data)
            # metrics
            m = self.metrics[agent_id]
            if data.get("agent_name"):
                m["name"] = data["agent_name"]
            if data.get("role"):
                m["role"] = data["role"]
            if event.type == EventType.STEP_START:
                m["steps"] += 1
            elif event.type == EventType.TOOL_CALL:
                m["tool_calls"] += 1
                m["current_tool"] = data.get("tool")
            elif event.type == EventType.TOKEN:
                m["approx_tokens"] += max(1, len(str(data.get("text", ""))) // 4)
            elif event.type == EventType.USAGE:
                # real counts when the provider reports them
                m["input_tokens"] += int(data.get("input_tokens", 0))
                m["output_tokens"] += int(data.get("output_tokens", 0))
            elif event.type == EventType.AGENT_STATUS:
                m["status"] = data.get("status", m["status"])
                m["current_tool"] = data.get("current_tool")
            elif event.type == EventType.RUN_END:
                m["status"] = "cancelled" if data.get("cancelled") else "done"

    def snapshot(self) -> list[dict[str, Any]]:
        return [{"agent_id": aid, **m} for aid, m in self.metrics.items() if aid != "_"]

    async def stop(self) -> None:
        if self._task:
            self.bus.unsubscribe(self._queue)
            self._task.cancel()
