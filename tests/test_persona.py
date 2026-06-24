"""SOUL.md persona + MEMORY.md: seeding, system-prompt injection, compaction."""

from __future__ import annotations

import pytest

from xplogent.core import persona
from xplogent.core.context import build_system_prompt


def test_soul_and_memory_seed_and_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    monkeypatch.setattr("xplogent.core.config._migrated", True)
    soul = persona.load_soul()
    assert "SOUL" in soul and persona.soul_path().exists()
    persona.save_soul("# SOUL\nYou are Bob, a pirate.")
    assert "pirate" in persona.load_soul()
    persona.save_memory("- user likes tea")
    assert "tea" in persona.load_memory()


def test_build_system_prompt_orders_persona_first():
    out = build_system_prompt(
        "BASE INSTRUCTIONS", ["fact one"],
        [("deploy", "ship the site", "step1", "when deploying", ["shell", "git"])],
        persona="# SOUL\nYou are Ada.", memory_md="- prefers dark mode",
    )
    assert out.index("You are Ada") < out.index("BASE INSTRUCTIONS")
    assert "Curated memory" in out and "prefers dark mode" in out
    assert "fact one" in out
    assert "When:" in out and "shell, git" in out


@pytest.mark.asyncio
async def test_compact_memory_writes_curated(tmp_path, monkeypatch):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    monkeypatch.setattr("xplogent.core.config._migrated", True)
    from tests.conftest import ScriptedProvider
    from xplogent.memory.store import Store
    from xplogent.providers.base import Message, Role

    store = Store(tmp_path / "xplogent.db")
    sid = store.create_session("chat")
    store.add_message(sid, "user", "I always deploy on Fridays")
    store.add_fact("user prefers Python", [0.1], source="test")
    provider = ScriptedProvider([Message(role=Role.ASSISTANT, content="# MEMORY\n- deploys on Fridays")])
    content = await persona.compact_memory(store, provider)
    assert "Fridays" in content
    assert "Fridays" in persona.load_memory()
    store.close()
