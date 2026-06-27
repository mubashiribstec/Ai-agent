"""Cost guardrails: daily/session caps and the agent's on_exceed behavior."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.core.agent import Agent
from xplogent.core.budget import check_budget, today_spend
from xplogent.core.config import load_config
from xplogent.core.events import EventBus, EventType
from xplogent.memory.manager import MemoryManager
from xplogent.memory.store import Store
from xplogent.memory.vector import Embedder
from xplogent.providers.base import Message, Role
from xplogent.safety.approval import SafetyManager
from xplogent.tools.registry import ToolRegistry


def test_today_spend_and_check(tmp_path):
    store = Store(tmp_path / "m.db")
    store.add_usage("openai:gpt-4o", 1000, 1000, 0.40, None)
    store.add_usage("openai:gpt-4o", 1000, 1000, 0.40, None)
    assert today_spend(store) == pytest.approx(0.80)

    # daily cap tripped
    v = check_budget({"daily_usd": 0.5, "on_exceed": "pause"}, store, 0.0)
    assert v.exceeded and v.scope == "daily" and v.action == "pause"
    # under cap
    assert not check_budget({"daily_usd": 5.0}, store, 0.0).exceeded
    # session cap tripped (independent of the store)
    v2 = check_budget({"session_usd": 0.25}, None, 0.30)
    assert v2.exceeded and v2.scope == "session"
    store.close()


@pytest.mark.asyncio
async def test_agent_pauses_when_daily_cap_exceeded():
    cfg = load_config(overrides={"budget": {"daily_usd": 0.01, "on_exceed": "pause"}})
    store = Store(cfg.db_path)
    store.add_usage("openai:gpt-4o", 100, 100, 5.0, None)  # already way over the cap
    memory = MemoryManager(store, Embedder(ScriptedProvider([])), session_id=store.create_session("t"))

    bus = EventBus()
    queue = bus.subscribe()
    agent = Agent(cfg, ScriptedProvider([Message(role=Role.ASSISTANT, content="hi")]),
                  ToolRegistry.from_config([]), SafetyManager(), memory=memory, bus=bus)
    answer = await agent.run("hello")
    await bus.close()

    assert "budget" in answer.lower()
    seen = []
    while True:
        ev = await queue.get()
        if ev is None:
            break
        if ev.type == EventType.BUDGET:
            seen.append(ev.data)
    assert seen and seen[0]["action"] == "pause"
    store.close()
