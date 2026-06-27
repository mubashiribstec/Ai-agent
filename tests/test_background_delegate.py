"""Background subagents: delegate_task(background=true) + collect_tasks."""

from __future__ import annotations

import asyncio

import pytest

from xplogent.core.messaging import MessageBus
from xplogent.tools.collab import BackgroundTasks, CollectTasksTool, DelegateTool, collab_tools


@pytest.mark.asyncio
async def test_background_delegate_returns_immediately_then_collect():
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_delegate(task: str, role: str, depth: int) -> str:
        started.set()
        await release.wait()          # stays "running" until we release it
        return f"done: {task}"

    bg = BackgroundTasks()
    delegate_tool = DelegateTool(fake_delegate, depth=0, max_depth=2, background_tasks=bg)
    collect = CollectTasksTool(bg)

    # Dispatch returns right away with a task id, without waiting for the helper.
    res = await delegate_tool.run(task="crunch the numbers", background=True)
    assert res.ok and "bg1" in res.output
    await asyncio.wait_for(started.wait(), timeout=1)
    assert bg.pending() == 1

    # Nothing finished yet.
    pending = await collect.run()
    assert "still running" in pending.output

    # Let it finish, then collect the result exactly once.
    release.set()
    await asyncio.sleep(0)  # let the background task complete
    for _ in range(10):
        out = await collect.run()
        if "done: crunch the numbers" in out.output:
            break
        await asyncio.sleep(0.01)
    assert "done: crunch the numbers" in out.output
    assert bg.collect() == []  # already drained


@pytest.mark.asyncio
async def test_foreground_delegate_still_waits():
    async def fake_delegate(task: str, role: str, depth: int) -> str:
        return "immediate answer"

    tool = DelegateTool(fake_delegate, depth=0, max_depth=2, background_tasks=BackgroundTasks())
    res = await tool.run(task="do it now")  # background defaults to False
    assert res.output == "immediate answer"


def test_collab_tools_includes_collect_when_background_present():
    bus = MessageBus(None)
    names = {t.name for t in collab_tools(bus, "a1", "lead",
                                          delegate=lambda *a: None, depth=0, max_depth=2,
                                          background_tasks=BackgroundTasks())}
    assert "delegate_task" in names and "collect_tasks" in names
