"""Inter-agent messaging: broadcast, direct, inbox, and persistence."""

from __future__ import annotations

import pytest

from xplogent.core.events import EventBus
from xplogent.core.messaging import MessageBus
from xplogent.memory.store import Store
from xplogent.tools.collab import collab_tools


def _bus_with_two(store=None):
    mb = MessageBus(EventBus(), store=store, run_id="run1")
    mb.register_agent("a1", "alice", "researcher")
    mb.register_agent("a2", "bob", "coder")
    return mb


@pytest.mark.asyncio
async def test_broadcast_reaches_others_not_self():
    mb = _bus_with_two()
    await mb.broadcast("a1", "alice", "starting research")
    assert mb.read_inbox("a1") == []          # sender doesn't receive own broadcast
    bob_msgs = mb.read_inbox("a2")
    assert len(bob_msgs) == 1 and bob_msgs[0].content == "starting research"


@pytest.mark.asyncio
async def test_direct_message_addresses_by_name():
    mb = _bus_with_two()
    result = await mb.send("a1", "alice", "bob", "please build the parser")
    assert "delivered" in result
    msgs = mb.read_inbox("a2")
    assert msgs[0].recipient == "bob"
    # inbox cleared after read
    assert mb.read_inbox("a2") == []


@pytest.mark.asyncio
async def test_send_to_unknown_agent():
    mb = _bus_with_two()
    result = await mb.send("a1", "alice", "nobody", "hi")
    assert "no agent" in result


@pytest.mark.asyncio
async def test_messages_persisted_to_store(tmp_path):
    store = Store(tmp_path / "m.db")
    mb = _bus_with_two(store=store)
    await mb.broadcast("a1", "alice", "hello team")
    rows = store.list_agent_messages("run1")
    assert rows and rows[0]["content"] == "hello team"
    store.close()


@pytest.mark.asyncio
async def test_collab_tools_round_trip():
    mb = _bus_with_two()
    tools = {t.name: t for t in collab_tools(mb, "a1", "alice")}
    await tools["broadcast"].run(content="hi all")
    bob_tools = {t.name: t for t in collab_tools(mb, "a2", "bob")}
    inbox = await bob_tools["read_inbox"].run()
    assert "hi all" in inbox.output
    agents = await tools["list_agents"].run()
    assert "bob" in agents.output
