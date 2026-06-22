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
async def test_auto_approve_lets_agents_run_high_risk_tools(monkeypatch):
    # A worker asks for a high-risk tool; with an approver it runs, without it blocks.
    from xplogent.providers.base import ToolCall
    from xplogent.safety.approval import RiskLevel
    from xplogent.tools.base import Tool, ToolResult

    ran = {"count": 0}

    class _DangerTool(Tool):
        name = "danger"
        description = "high risk"
        parameters = {"type": "object", "properties": {}}
        risk = RiskLevel.HIGH

        async def run(self, **kw):
            ran["count"] += 1
            return ToolResult.success("did it")

    def provider(_spec, **_kw):
        return ScriptedProvider([
            Message(role=Role.ASSISTANT, content="",
                    tool_calls=[ToolCall(id="c1", name="danger", arguments={})]),
            Message(role=Role.ASSISTANT, content="done"),
        ])

    import xplogent.core.orchestrator as orch_mod
    monkeypatch.setattr(orch_mod, "build_provider", provider)

    reg = ToolRegistry()
    reg.register(_DangerTool())

    async def approve(_req):  # auto-approve
        return True

    cfg = load_config()
    # role policy: high=confirm so it routes through the approver
    cfg.roles = {"operator": {"allowed_tools": "*",
                              "policy": {"low": "auto", "medium": "auto",
                                         "high": "confirm", "critical": "deny"}}}
    orch = orch_mod.Orchestrator(
        cfg, bus=EventBus(), store=Store(":memory:"),
        embedder=Embedder(ScriptedProvider([])), base_tools=reg,
        base_safety=SafetyManager.from_config(cfg.safety), approve=approve,
    )
    await orch.run_team([AgentSpec(name="w", role="operator", task="go")])
    assert ran["count"] == 1            # approved → ran
    await orch.aclose()


@pytest.mark.asyncio
async def test_run_goal_completes_all_tasks(monkeypatch):
    orch = _orchestrator(monkeypatch, reply="subtask done", max_concurrent=3)
    # Patch the planner to avoid an LLM call: two independent tasks.
    import xplogent.core.orchestrator as orch_mod
    from xplogent.core.taskboard import Task

    async def fake_decompose(self, goal, roles, count=3):
        return [
            Task(id="t1", title="research", description="research X", role="operator"),
            Task(id="t2", title="write", description="write Y", role="operator", deps=["t1"]),
        ]

    monkeypatch.setattr(orch_mod.Planner, "decompose", fake_decompose)
    result = await orch.run_goal("do a thing", max_concurrent=3)
    statuses = {t["id"]: t["status"] for t in result["tasks"]}
    assert statuses == {"t1": "done", "t2": "done"}
    # the whole team is pre-registered so agents can see each other
    assert len(orch.message_bus.agents()) == 2
    await orch.aclose()


@pytest.mark.asyncio
async def test_run_goal_passes_team_size_to_planner(monkeypatch):
    orch = _orchestrator(monkeypatch, reply="done", max_concurrent=4)
    import xplogent.core.orchestrator as orch_mod
    from xplogent.core.taskboard import Task

    seen = {}

    async def fake_decompose(self, goal, roles, count=3):
        seen["count"] = count
        return [Task(id=f"t{i}", title=f"m{i}", description=f"method {i}", role="operator")
                for i in range(count)]

    monkeypatch.setattr(orch_mod.Planner, "decompose", fake_decompose)
    result = await orch.run_goal("all agents check my IP differently", max_concurrent=4)
    assert seen["count"] == 4
    assert len([t for t in result["tasks"] if t["status"] == "done"]) == 4
    await orch.aclose()
