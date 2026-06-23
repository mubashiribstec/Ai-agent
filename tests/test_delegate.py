"""delegate_task: an agent can spawn its own sub-agents (with a depth limit)."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.core.config import load_config
from xplogent.core.events import EventBus
from xplogent.core.orchestrator import AgentSpec, Orchestrator
from xplogent.memory.store import Store
from xplogent.memory.vector import Embedder
from xplogent.providers.base import Message, Role, ToolCall
from xplogent.safety.approval import SafetyManager
from xplogent.tools.collab import DelegateTool, collab_tools
from xplogent.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_delegate_tool_respects_depth_limit():
    calls = []

    async def deleg(task, role, depth):
        calls.append((task, role, depth))
        return "ok"

    within = DelegateTool(deleg, depth=0, max_depth=2)
    res = await within.run("do x")
    assert res.ok
    assert calls[0] == ("do x", "operator", 1)

    at_limit = DelegateTool(deleg, depth=2, max_depth=2)
    res2 = await at_limit.run("do y")
    assert not res2.ok
    assert "depth limit" in res2.error


def test_collab_tools_omits_delegate_at_max_depth():
    async def deleg(task, role, depth):
        return ""

    bus = object()
    has = [t.name for t in collab_tools(bus, "a", "alice", delegate=deleg, depth=0, max_depth=2)]
    assert "delegate_task" in has
    none = [t.name for t in collab_tools(bus, "a", "alice", delegate=deleg, depth=2, max_depth=2)]
    assert "delegate_task" not in none


@pytest.mark.asyncio
async def test_worker_delegates_to_subagent(monkeypatch):
    cfg = load_config()
    cfg.orchestrator["max_concurrent_agents"] = 3
    cfg.roles = {"operator": {"allowed_tools": "*",
                              "policy": {"low": "auto", "medium": "auto",
                                         "high": "auto", "critical": "deny"}}}
    import xplogent.core.orchestrator as orch_mod

    counter = {"n": 0}

    def provider(_spec, **_kw):
        counter["n"] += 1
        if counter["n"] == 1:  # the lead agent delegates, then synthesizes
            return ScriptedProvider([
                Message(role=Role.ASSISTANT, content="",
                        tool_calls=[ToolCall(id="c1", name="delegate_task",
                                             arguments={"task": "research the topic"})]),
                Message(role=Role.ASSISTANT, content="final synthesis"),
            ])
        return ScriptedProvider([Message(role=Role.ASSISTANT, content="sub result")])

    monkeypatch.setattr(orch_mod, "build_provider", provider)
    orch = Orchestrator(
        cfg, bus=EventBus(), store=Store(":memory:"),
        embedder=Embedder(ScriptedProvider([])),
        base_tools=ToolRegistry.from_config(["filesystem"]),
        base_safety=SafetyManager(policy={"low": "auto", "medium": "auto",
                                          "high": "auto", "critical": "deny"}),
    )
    result = await orch.run_team([AgentSpec(name="lead", role="operator", task="coordinate")])
    assert result["results"]["lead"] == "final synthesis"
    assert counter["n"] >= 2  # a sub-agent provider was built → delegation happened
    await orch.aclose()
