"""Live Canvas tool emits a CANVAS event with the agent's HTML."""

from __future__ import annotations

import pytest

from xplogent.core.events import EventBus, EventType
from xplogent.tools.canvas import CanvasTool


@pytest.mark.asyncio
async def test_canvas_tool_emits_event():
    bus = EventBus()
    queue = bus.subscribe()
    tool = CanvasTool(bus, agent_id="a1", agent_name="agent")
    res = await tool.run(html="<h1>Hi</h1>", title="Dash")
    await bus.close()

    assert res.ok
    seen = []
    while True:
        ev = await queue.get()
        if ev is None:
            break
        if ev.type == EventType.CANVAS:
            seen.append(ev.data)
    assert seen and seen[0]["html"] == "<h1>Hi</h1>"
    assert seen[0]["title"] == "Dash"


@pytest.mark.asyncio
async def test_runtime_registers_canvas_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    monkeypatch.setattr("xplogent.core.config._migrated", True)
    from xplogent.core.config import load_config
    from xplogent.runtime import build_runtime

    cfg = load_config()
    rt = build_runtime(cfg, with_memory=False)
    assert rt.agent.tools.get("canvas") is not None
    await rt.aclose()
