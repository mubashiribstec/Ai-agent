"""/undo turn rollback + cheaper (gated/batched) reflection."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.core.agent import Agent
from xplogent.core.config import load_config
from xplogent.memory.manager import MemoryManager
from xplogent.memory.store import Store
from xplogent.memory.vector import Embedder
from xplogent.providers.base import Message, Role
from xplogent.safety.approval import SafetyManager
from xplogent.skills.reflection import ReflectionResult
from xplogent.tools.registry import ToolRegistry


def test_delete_last_turns_removes_exchange_and_fts(tmp_path):
    store = Store(tmp_path / "m.db")
    sid = store.create_session("t")
    store.add_message(sid, "user", "first question")
    store.add_message(sid, "assistant", "first answer")
    store.add_message(sid, "user", "second question about pelicans")
    store.add_message(sid, "assistant", "second answer")

    removed = store.delete_last_turns(sid, 1)
    assert removed == 2
    roles = [m["role"] for m in store.session_messages(sid)]
    assert roles == ["user", "assistant"]
    # FTS no longer finds the removed turn.
    assert not any("pelicans" in m["content"] for m in store.search_messages("pelicans"))
    # Undo the remaining turn.
    assert store.delete_last_turns(sid, 1) == 2
    assert store.session_messages(sid) == []
    store.close()


class _CountingReflector:
    def __init__(self):
        self.calls = 0

    async def reflect(self, task, transcript):
        self.calls += 1
        return ReflectionResult()


class _NoopSkills:
    async def apply(self, result):
        return {"facts": 0, "skill": None}


def _agent(cfg, reflector):
    store = Store(cfg.db_path)
    mem = MemoryManager(store, Embedder(ScriptedProvider([])), session_id=store.create_session("t"))
    agent = Agent(cfg, ScriptedProvider([Message(role=Role.ASSISTANT, content="hi")]),
                  ToolRegistry.from_config([]), SafetyManager(), memory=mem,
                  reflector=reflector, skills=_NoopSkills())
    return agent, store


@pytest.mark.asyncio
async def test_reflection_skips_plain_chat_turns():
    cfg = load_config(overrides={"skills": {"reflect_min_steps": 1, "reflect_every": 1}})
    ref = _CountingReflector()
    agent, store = _agent(cfg, ref)
    await agent._post_task("hello", "USER: hi", tool_steps=0)   # no tools → skip
    assert ref.calls == 0
    await agent._post_task("do x", "...", tool_steps=2)         # used tools → reflect
    assert ref.calls == 1
    store.close()


@pytest.mark.asyncio
async def test_reflect_every_batches():
    cfg = load_config(overrides={"skills": {"reflect_min_steps": 1, "reflect_every": 2}})
    ref = _CountingReflector()
    agent, store = _agent(cfg, ref)
    for _ in range(4):
        await agent._post_task("t", "...", tool_steps=1)
    assert ref.calls == 2  # every 2nd qualifying task
    store.close()
