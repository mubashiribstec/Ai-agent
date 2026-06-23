"""Skill proficiency levels, outcome tracking, fact dedup, embed provenance."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.memory.manager import MemoryManager
from xplogent.memory.store import Store, skill_level
from xplogent.memory.vector import Embedder


def test_skill_level_thresholds():
    assert skill_level(0, 0, 0) == ("novice", 1)
    assert skill_level(4, 3, 0) == ("proficient", 2)
    assert skill_level(10, 9, 1) == ("expert", 3)
    assert skill_level(10, 1, 9) == ("novice", 1)  # high uses but mostly fails


def test_record_outcome_changes_level(tmp_path):
    store = Store(tmp_path / "m.db")
    store.upsert_skill("deploy", "deploy site", "steps", [0.1] * 8)
    for _ in range(8):
        store.increment_skill_use("deploy")
    for _ in range(8):
        store.record_skill_outcome("deploy", True)
    s = next(s for s in store.all_skills() if s.name == "deploy")
    assert s.successes == 8
    assert s.level == "expert"
    assert s.stars == 3
    store.close()


@pytest.mark.asyncio
async def test_fact_dedup_skips_near_duplicate(tmp_path):
    store = Store(tmp_path / "m.db")
    mem = MemoryManager(store, Embedder(ScriptedProvider([])), session_id=store.create_session("c"))
    id1 = await mem.remember("the user likes dark mode")
    id2 = await mem.remember("the user likes dark mode")  # identical → same id
    assert id1 == id2
    assert len(store.all_facts()) == 1
    store.close()


@pytest.mark.asyncio
async def test_embed_model_recorded(tmp_path):
    store = Store(tmp_path / "m.db")
    mem = MemoryManager(store, Embedder(ScriptedProvider([])), session_id=store.create_session("c"))
    await mem.remember("a fact")
    fact = store.all_facts()[0]
    assert fact.embed_model == mem.embed_model
    assert "scripted" in fact.embed_model


def test_rename_session(tmp_path):
    store = Store(tmp_path / "m.db")
    sid = store.create_session("chat")
    store.rename_session(sid, "My project")
    assert store.list_sessions()[0]["title"] == "My project"
    store.close()
