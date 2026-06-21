"""Multi-agent orchestration: concurrency bounding, manual teams, and auto goals."""

from __future__ import annotations

import asyncio

import pytest

from tests.conftest import ScriptedProvider
from xplogent.core.config import load_config
from xplogent.core.events import EventBus
from xplogent.core.orchestrator import AgentSpec, Orchestrator
from xplogent.memory.store import Store
from xplogent.memory.vector import Embedder
from xplogent.providers.base import Message, Role
from xplogent.safety.approval import SafetyManager
from xplogent.tools.registry import ToolRegistry


class ConcurrencyTracker:
    """Wraps the orchestrator's worker provider to observe in-flight count."""

    def __init__(self):
        self.active = 0
        self.peak = 0


def _orchestrator(monkeypatch, tracker=None, reply="done", max_concurrent=2):
    """Build an Orchestrator whose workers use a scripted (offline) provider."""
    cfg = load_config()
    cfg.orchestrator["max_concurrent_agents"] = max_concurrent
    bus = EventBus()
    store = Store(":memory:")
    embedder = Embedder(ScriptedProvider([]))

    # Patch build_provider used inside the orchestrator to return a scripted one
    # that optionally records concurrency and yields after a tick.
    import xplogent.core.orchestrator as orch_mod

    def fake_build_provider(_spec, **_kw):
        return _SlowScripted(reply, tracker)

    monkeypatch.setattr(orch_mod, "build_provider", fake_build_provider)

    return Orchestrator(
        cfg, bus=bus, store=store, embedder=embedder,
        base_tools=ToolRegistry.from_config(["filesystem"]),
        base_safety=SafetyManager(policy={"low": "auto", "medium": "auto",
                                           "high": "auto", "critical": "deny"}),
    )


class _SlowScripted(ScriptedProvider):
    """Scripted provider that records concurrency and awaits a tick mid-stream."""

    def __init__(self, reply, tracker):
        super().__init__([Message(role=Role.ASSISTANT, content=reply)])
        self._tracker = tracker

    async def stream(self, messages, tools=None, **kwargs):
        if self._tracker is not None:
            self._tracker.active += 1
            self._tracker.peak = max(self._tracker.peak, self._tracker.active)
        await asyncio.sleep(0.02)  # hold the slot so overlap is observable
        try:
            async for ev in super().stream(messages, tools, **kwargs):
                yield ev
        finally:
            if self._tracker is not None:
                self._tracker.active -= 1


@pytest.mark.asyncio
async def test_run_team_concurrency_is_bounded(monkeypatch):
    tracker = ConcurrencyTracker()
    orch = _orchestrator(monkeypatch, tracker=tracker, max_concurrent=2)
    specs = [AgentSpec(name=f"w{i}", role="operator", task="do it") for i in range(5)]
    result = await orch.run_team(specs)
    assert len(result["results"]) == 5
    assert tracker.peak <= 2                     # never more than the limit in flight
    assert orch.peak_concurrency <= 2
    await orch.aclose()


@pytest.mark.asyncio
async def test_run_team_collaboration_messages(monkeypatch):
    # Worker replies with a broadcast tool call, then a final answer.
    cfg = load_config()
    bus = EventBus()
    store = Store(":memory:")
    import xplogent.core.orchestrator as orch_mod
    from xplogent.providers.base import ToolCall

    def two_step_provider(_spec, **_kw):
        return ScriptedProvider([
            Message(role=Role.ASSISTANT, content="",
                    tool_calls=[ToolCall(id="c1", name="broadcast",
                                         arguments={"content": "hello team"})]),
            Message(role=Role.ASSISTANT, content="finished"),
        ])

    monkeypatch.setattr(orch_mod, "build_provider", two_step_provider)
    orch = Orchestrator(
        cfg, bus=bus, store=store, embedder=Embedder(ScriptedProvider([])),
        base_tools=ToolRegistry.from_config(["filesystem"]),
        base_safety=SafetyManager(policy={"low": "auto", "medium": "auto",
                                          "high": "auto", "critical": "deny"}),
    )
    result = await orch.run_team([
        AgentSpec(name="alice", role="operator", task="a"),
        AgentSpec(name="bob", role="operator", task="b"),
    ])
    contents = [m["content"] for m in result["messages"]]
    assert "hello team" in contents
    await orch.aclose()


@pytest.mark.asyncio
async def test_run_goal_completes_all_tasks(monkeypatch):
    orch = _orchestrator(monkeypatch, reply="subtask done", max_concurrent=3)
    # Patch the planner to avoid an LLM call: two independent tasks.
    import xplogent.core.orchestrator as orch_mod
    from xplogent.core.taskboard import Task

    async def fake_decompose(self, goal, roles):
        return [
            Task(id="t1", title="research", description="research X", role="operator"),
            Task(id="t2", title="write", description="write Y", role="operator", deps=["t1"]),
        ]

    monkeypatch.setattr(orch_mod.Planner, "decompose", fake_decompose)
    result = await orch.run_goal("do a thing", max_concurrent=3)
    statuses = {t["id"]: t["status"] for t in result["tasks"]}
    assert statuses == {"t1": "done", "t2": "done"}
    await orch.aclose()
