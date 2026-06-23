"""Image input (vision) reaches the provider, and the /status aggregate endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from xplogent.core.agent import Agent
from xplogent.core.config import load_config
from xplogent.providers.base import Message, Provider, Role, StreamEvent, StreamKind
from xplogent.safety.approval import SafetyManager
from xplogent.tools.registry import ToolRegistry


class _CaptureProvider(Provider):
    name = "capture"

    def __init__(self):
        super().__init__("capture")
        self.seen_images: list[str] = []

    async def stream(self, messages, tools=None, *, temperature=0.7, **kw) -> AsyncIterator[StreamEvent]:
        for m in messages:
            if m.role == Role.USER and m.images:
                self.seen_images.extend(m.images)
        yield StreamEvent(kind=StreamKind.DONE, message=Message(role=Role.ASSISTANT, content="ok"))


@pytest.mark.asyncio
async def test_agent_run_forwards_images_to_provider():
    provider = _CaptureProvider()
    agent = Agent(load_config(), provider, ToolRegistry.from_config([]), SafetyManager())
    await agent.run("what is this?", images=["/tmp/shot.png"])
    assert provider.seen_images == ["/tmp/shot.png"]


@pytest.mark.asyncio
async def test_agent_run_without_images_is_unaffected():
    provider = _CaptureProvider()
    agent = Agent(load_config(), provider, ToolRegistry.from_config([]), SafetyManager())
    await agent.run("hello")
    assert provider.seen_images == []


def test_status_endpoint(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    from fastapi.testclient import TestClient

    import xplogent.interfaces.api.server as srv
    client = TestClient(srv.create_app())
    data = client.get("/status").json()
    assert data["status"] == "ok"
    assert "providers" in data
    assert "secrets" in data
    assert "reachable" in data["ollama"]
