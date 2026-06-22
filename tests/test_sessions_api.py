"""Persistent chat sessions: history seeding + sessions endpoints."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.providers.base import Message, Role


@pytest.mark.asyncio
async def test_history_seeds_short_term_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    import xplogent.runtime as rt
    monkeypatch.setattr(
        rt, "build_provider",
        lambda *_a, **_k: ScriptedProvider([Message(role=Role.ASSISTANT, content="hi there")]),
    )

    rt1 = rt.build_runtime()
    sid = rt1.agent.memory.session_id
    await rt1.agent.run("hello")          # logs user + assistant to the session
    await rt1.aclose()

    # Reconnect to the same session → STM is seeded from history.
    rt2 = rt.build_runtime(session_id=sid)
    contents = [m.content for m in rt2.agent.stm.messages]
    assert "hello" in contents
    assert "hi there" in contents
    await rt2.aclose()


def test_sessions_endpoints(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from xplogent.interfaces.api.server import create_app

    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    c = TestClient(create_app())
    sid = c.post("/sessions").json()["id"]
    assert c.get("/sessions").json()["sessions"][0]["id"] == sid
    assert c.get(f"/sessions/{sid}/messages").json()["messages"] == []
    assert c.delete(f"/sessions/{sid}").json()["ok"]
    assert all(s["id"] != sid for s in c.get("/sessions").json()["sessions"])
