"""Chrome-extension bridge: request/response correlation, snapshot, tool routing."""

from __future__ import annotations

import asyncio

import pytest

from xplogent.core.extension import ExtensionBridge
from xplogent.tools.browser_extension import BrowserExtensionTool


class _FakeWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, obj):
        self.sent.append(obj)


@pytest.mark.asyncio
async def test_request_resolves_on_matching_reply():
    bridge = ExtensionBridge()
    ws = _FakeWS()
    bridge.attach(ws)

    async def replier():
        # wait for the command to be sent, then answer it
        for _ in range(50):
            if ws.sent:
                break
            await asyncio.sleep(0.001)
        rid = ws.sent[-1]["id"]
        bridge.resolve(rid, True, [{"id": 1, "title": "Tab", "url": "https://x", "active": True}])

    task = asyncio.create_task(replier())
    res = await bridge.request("list_tabs")
    await task
    assert res["ok"] is True
    assert res["data"][0]["title"] == "Tab"
    assert ws.sent[-1]["action"] == "list_tabs"


@pytest.mark.asyncio
async def test_request_without_connection_raises():
    bridge = ExtensionBridge()
    with pytest.raises(ConnectionError):
        await bridge.request("read")


def test_snapshot_keeps_recent_inputs_and_redaction():
    bridge = ExtensionBridge()
    bridge.update_snapshot(
        tabs=[{"id": 1, "title": "G", "url": "https://g", "active": True}],
        inputs=[{"field": "password", "type": "password", "redacted": True, "page": "Login"}])
    st = bridge.status()
    assert st["tabs"][0]["title"] == "G"
    assert st["inputs"][-1]["redacted"] is True


@pytest.mark.asyncio
async def test_tool_reports_when_not_connected(monkeypatch):
    bridge = ExtensionBridge()  # not attached → not connected
    monkeypatch.setattr("xplogent.core.extension.get_bridge", lambda: bridge)
    res = await BrowserExtensionTool().run(action="list_tabs")
    assert not res.ok
    assert "extension" in res.error.lower()


@pytest.mark.asyncio
async def test_tool_routes_through_bridge(monkeypatch):
    bridge = ExtensionBridge()
    bridge.attach(_FakeWS())

    async def fake_request(action, params=None, timeout=20.0):
        return {"ok": True, "data": "page text here"}

    bridge.request = fake_request  # type: ignore[assignment]
    monkeypatch.setattr("xplogent.core.extension.get_bridge", lambda: bridge)

    res = await BrowserExtensionTool().run(action="read")
    assert res.ok and "page text here" in res.output
