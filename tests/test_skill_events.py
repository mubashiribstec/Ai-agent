"""Skill activity history, end-of-conversation export, and learn/update events."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.memory.manager import MemoryManager
from xplogent.memory.store import Store
from xplogent.memory.vector import Embedder
from xplogent.skills.manager import SkillManager
from xplogent.skills.reflection import ReflectionResult, SkillDraft


def _skill_mgr(tmp_path):
    store = Store(tmp_path / "m.db")
    mem = MemoryManager(store, Embedder(ScriptedProvider([])), session_id=store.create_session("c"))
    return SkillManager(mem, tmp_path / "skills"), store


@pytest.mark.asyncio
async def test_learn_then_update_records_events_and_files(tmp_path):
    sm, store = _skill_mgr(tmp_path)

    s1 = await sm.apply(ReflectionResult(skill=SkillDraft("deploy", "deploy the site", "step 1")))
    assert s1["skill"] == "deploy" and s1["skill_action"] == "learned"
    assert (tmp_path / "skills" / "deploy.md").exists()   # written to the folder

    s2 = await sm.apply(ReflectionResult(skill=SkillDraft("deploy", "deploy the site v2", "step 1, 2")))
    assert s2["skill_action"] == "updated"

    events = store.skill_events()
    actions = [(e["name"], e["action"]) for e in events]
    assert ("deploy", "updated") in actions
    assert ("deploy", "learned") in actions
    store.close()


@pytest.mark.asyncio
async def test_export_all_mirrors_db_to_folder(tmp_path):
    sm, store = _skill_mgr(tmp_path)
    await sm.memory.save_skill("a", "skill a", "body a")
    await sm.memory.save_skill("b", "skill b", "body b")
    # remove the auto-written files, then re-export everything
    for p in (tmp_path / "skills").glob("*.md"):
        p.unlink()
    n = sm.export_all()
    assert n == 2
    assert (tmp_path / "skills" / "a.md").exists()
    assert (tmp_path / "skills" / "b.md").exists()
    store.close()
