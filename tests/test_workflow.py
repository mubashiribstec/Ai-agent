"""Visual workflow executor: dependency order, output passing, cycle detection."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.core.config import load_config
from xplogent.core.workflow import run_workflow
from xplogent.memory.store import Store
from xplogent.providers.base import Message, Role


@pytest.mark.asyncio
async def test_runs_in_dependency_order_and_passes_output(monkeypatch):
    # The agent node echoes its (interpolated) prompt so we can assert wiring.
    def fake_provider(*_a, **_k):
        return ScriptedProvider([Message(role=Role.ASSISTANT, content="AGENT_SAW_INPUT")])

    monkeypatch.setattr("xplogent.runtime.build_provider", fake_provider)

    graph = {
        "nodes": [
            {"id": "a", "type": "input", "name": "seed", "config": {"value": "hello world"}},
            {"id": "b", "type": "agent", "name": "writer", "config": {"prompt": "Use: {{input}}"}},
        ],
        "edges": [{"from": "a", "to": "b"}],
    }
    res = await run_workflow(graph, load_config())
    assert res["ok"]
    assert res["outputs"]["a"] == "hello world"
    assert res["outputs"]["b"] == "AGENT_SAW_INPUT"
    statuses = {r["node_id"]: r["status"] for r in res["results"]}
    assert statuses == {"a": "done", "b": "done"}
    # 'a' must appear before 'b' in execution order.
    order = [r["node_id"] for r in res["results"]]
    assert order.index("a") < order.index("b")


@pytest.mark.asyncio
async def test_cycle_is_rejected():
    graph = {
        "nodes": [{"id": "a", "type": "input", "config": {}}, {"id": "b", "type": "input", "config": {}}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}],
    }
    res = await run_workflow(graph, load_config())
    assert res["ok"] is False
    assert "cycle" in res["error"]


def test_workflow_persistence(tmp_path):
    store = Store(tmp_path / "m.db")
    graph = {"nodes": [{"id": "a", "type": "input", "config": {"value": "x"}}], "edges": []}
    wid = store.save_workflow("demo", graph)
    got = store.get_workflow(wid)
    assert got["name"] == "demo"
    assert got["graph"]["nodes"][0]["id"] == "a"
    store.save_workflow("demo2", graph, workflow_id=wid)  # update in place
    assert store.get_workflow(wid)["name"] == "demo2"
    assert len(store.list_workflows()) == 1
    store.delete_workflow(wid)
    assert store.get_workflow(wid) is None
    store.close()
