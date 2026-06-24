"""Skills hub: SKILL.md parsing, bundled library, and installing packs."""

from __future__ import annotations

import pytest

from xplogent.skills.pack import parse_skill_md, render_skill_md


def test_parse_skill_md_frontmatter():
    text = ("---\nname: Code Review\ndescription: review code\n"
            "trigger: when reviewing\ntools: [read_file, shell]\n---\n\n# body\n1. do it\n")
    m = parse_skill_md(text)
    assert m["name"] == "code_review"
    assert m["description"] == "review code"
    assert m["trigger"] == "when reviewing"
    assert m["tools"] == ["read_file", "shell"]
    assert "do it" in m["body"]


def test_parse_skill_md_without_frontmatter():
    m = parse_skill_md("# Deploy Site\n> ship it\n1. build\n")
    assert m["name"] == "deploy_site"
    assert m["description"] == "ship it"


def test_render_roundtrip():
    md = render_skill_md("greet", "say hi", "1. wave", tools=["shell"], trigger="on hello")
    m = parse_skill_md(md)
    assert m["name"] == "greet" and m["tools"] == ["shell"] and m["trigger"] == "on hello"


def test_list_bundled_finds_starter_packs():
    from xplogent.skills.hub import list_bundled
    names = {p["name"] for p in list_bundled()}
    assert "code_review" in names
    assert "web_research" in names


@pytest.mark.asyncio
async def test_install_bundled_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    monkeypatch.setattr("xplogent.core.config._migrated", True)
    from tests.conftest import ScriptedProvider
    from xplogent.memory.manager import MemoryManager
    from xplogent.memory.store import Store
    from xplogent.memory.vector import Embedder
    from xplogent.skills.hub import install_pack

    store = Store(tmp_path / "xplogent.db")
    mem = MemoryManager(store, Embedder(ScriptedProvider([])), session_id=store.create_session("c"))
    res = await install_pack("code_review", mem)
    assert res["ok"] and "code_review" in res["installed"]
    skill = next(s for s in store.all_skills() if s.name == "code_review")
    assert skill.source == "installed"
    assert "read_file" in skill.tools
    assert skill.trigger
    store.close()


@pytest.mark.asyncio
async def test_install_text(tmp_path, monkeypatch):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    monkeypatch.setattr("xplogent.core.config._migrated", True)
    from tests.conftest import ScriptedProvider
    from xplogent.memory.manager import MemoryManager
    from xplogent.memory.store import Store
    from xplogent.memory.vector import Embedder
    from xplogent.skills.hub import install_text

    store = Store(tmp_path / "xplogent.db")
    mem = MemoryManager(store, Embedder(ScriptedProvider([])), session_id=store.create_session("c"))
    res = await install_text("---\nname: x\ndescription: d\ntools: [shell]\n---\nbody", mem)
    assert res["installed"] == ["x"]
    store.close()
