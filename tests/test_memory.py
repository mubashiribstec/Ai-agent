"""Memory: store persistence and semantic recall."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.memory.manager import MemoryManager
from xplogent.memory.store import Store
from xplogent.memory.vector import Embedder, cosine


def test_cosine_bounds():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_remember_and_recall(tmp_path):
    store = Store(tmp_path / "mem.db")
    embedder = Embedder(ScriptedProvider([]))
    mem = MemoryManager(store, embedder)

    await mem.remember("The user's favorite language is Python")
    await mem.remember("The user lives in Karachi")

    results = await mem.recall("what programming language does the user like")
    assert any("Python" in r for r in results)
    store.close()


@pytest.mark.asyncio
async def test_skill_save_and_retrieve(tmp_path):
    store = Store(tmp_path / "mem.db")
    mem = MemoryManager(store, Embedder(ScriptedProvider([])))
    await mem.save_skill("deploy_site", "How to deploy the website", "1. build\n2. push")
    skills = await mem.relevant_skills("deploy the website now")
    assert skills and skills[0].name == "deploy_site"
    store.close()


def test_episodic_logging(tmp_path):
    store = Store(tmp_path / "mem.db")
    sid = store.create_session("t")
    mem = MemoryManager(store, Embedder(ScriptedProvider([])), session_id=sid)
    mem.log("user", "hello world")
    found = store.search_messages("hello")
    assert found and found[0]["content"] == "hello world"
    store.close()
