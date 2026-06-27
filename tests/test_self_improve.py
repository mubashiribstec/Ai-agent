"""Self-improvement loop: reflection saves a skill (even for tool-less chat) and recalls it."""

from __future__ import annotations

import json

import pytest

from tests.conftest import ScriptedProvider
from xplogent.core.agent import Agent
from xplogent.core.config import load_config
from xplogent.memory.manager import MemoryManager
from xplogent.memory.store import Store
from xplogent.memory.vector import Embedder
from xplogent.providers.base import Message, Role
from xplogent.safety.approval import SafetyManager
from xplogent.skills.manager import SkillManager
from xplogent.skills.reflection import Reflector
from xplogent.tools.registry import ToolRegistry

_SKILL_JSON = json.dumps({
    "success": True,
    "facts": ["the user is building an AI agent framework"],
    "skill": {"name": "greet_user", "description": "how to greet the user warmly",
              "body": "1. say hello\n2. be friendly"},
})


@pytest.mark.asyncio
async def test_reflection_fires_on_toolless_chat(tmp_path):
    store = Store(tmp_path / "m.db")
    mem = MemoryManager(store, Embedder(ScriptedProvider([])), session_id=store.create_session("c"))
    skills = SkillManager(mem, tmp_path / "skills")
    reflector = Reflector(ScriptedProvider([Message(role=Role.ASSISTANT, content=_SKILL_JSON)]))
    main = ScriptedProvider([Message(role=Role.ASSISTANT, content="hello there!")])

    agent = Agent(
        # reflect_min_steps=0 opts into reflecting even on tool-less chat (default is 1).
        load_config(overrides={"skills": {"reflect_min_steps": 0}}),
        main, ToolRegistry.from_config([]),
        SafetyManager(policy={"low": "auto", "medium": "auto", "high": "auto", "critical": "deny"}),
        memory=mem, reflector=reflector, skills=skills,
    )
    await agent.run("teach me to greet")     # no tools used at all

    # reflection ran and persisted a skill + a fact
    assert any(s.name == "greet_user" for s in store.all_skills())
    assert store.all_facts()
    store.close()


@pytest.mark.asyncio
async def test_skill_saved_then_recalled(tmp_path):
    store = Store(tmp_path / "m.db")
    mem = MemoryManager(store, Embedder(ScriptedProvider([])), session_id=store.create_session("c"))
    await mem.save_skill("deploy_site", "how to deploy the website", "build then push")
    recalled = await mem.relevant_skills("how to deploy the website")
    assert recalled and recalled[0].name == "deploy_site"
    store.close()


def test_first_user_message_titles_the_session(tmp_path):
    store = Store(tmp_path / "m.db")
    sid = store.create_session("chat")
    mem = MemoryManager(store, Embedder(ScriptedProvider([])), session_id=sid)
    mem.log("user", "what is my public ip address")
    mem.log("assistant", "it is 1.2.3.4")
    mem.log("user", "second question")          # must NOT overwrite the title
    title = store.list_sessions()[0]["title"]
    assert title == "what is my public ip address"
