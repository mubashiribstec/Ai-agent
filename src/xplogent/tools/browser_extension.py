"""`web_browser` tool — drive the user's real Chrome through the extension.

Unlike the Playwright ``browser`` tool (a separate automated Chromium), this acts
on the user's actual browser via the connected Xplogent extension: it can see all
open tabs and act inside the page the user is really looking at. Every command is
routed through the shared :class:`ExtensionBridge`; if no extension is connected
the tool returns a helpful message instead of failing hard.
"""

from __future__ import annotations

import json
from typing import Any

from xplogent.safety.approval import RiskLevel
from xplogent.tools.base import Tool, ToolResult

_READ_ONLY = {"list_tabs", "read", "snapshot"}


class BrowserExtensionTool(Tool):
    name = "web_browser"
    description = (
        "Control the user's real Chrome browser via the Xplogent extension. Actions: "
        "'list_tabs' (open tabs), 'open_tab' (url), 'activate_tab' (tab_id), 'navigate' "
        "(url in the active tab), 'read' (visible text of the active tab), 'click' "
        "(css selector), 'type' (selector+text), 'close_tab' (tab_id). Use this to see "
        "and act on what the user is actually browsing."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["list_tabs", "open_tab", "activate_tab", "navigate",
                                "read", "click", "type", "close_tab"]},
            "url": {"type": "string"},
            "selector": {"type": "string", "description": "CSS selector."},
            "text": {"type": "string"},
            "tab_id": {"type": "integer"},
        },
        "required": ["action"],
    }
    risk = RiskLevel.MEDIUM

    def risk_for(self, arguments: dict[str, Any]) -> RiskLevel:
        return RiskLevel.LOW if arguments.get("action") in _READ_ONLY else RiskLevel.MEDIUM

    async def run(self, action: str, url: str | None = None, selector: str | None = None,
                  text: str | None = None, tab_id: int | None = None) -> ToolResult:
        from xplogent.core.extension import get_bridge

        bridge = get_bridge()
        if not bridge.connected:
            return ToolResult.failure(
                "No browser extension connected. Install the Xplogent Chrome extension "
                "(see extension/ in the repo) and make sure it's enabled.")
        params = {k: v for k, v in
                  {"url": url, "selector": selector, "text": text, "tab_id": tab_id}.items()
                  if v is not None}
        try:
            res = await bridge.request(action, params)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.failure(f"browser command failed: {exc}")
        if not res.get("ok"):
            return ToolResult.failure(str(res.get("data") or "browser action failed"))
        data = res.get("data")
        out = data if isinstance(data, str) else json.dumps(data)[:8000]
        return ToolResult.success(out, data=data if isinstance(data, dict) else {})


def browser_extension_tools() -> list[Tool]:
    return [BrowserExtensionTool()]
