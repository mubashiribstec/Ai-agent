"""Live Canvas — let the agent render an interactive HTML/CSS/JS workspace.

Instead of being limited to chat text, the agent can call ``canvas`` to render a
dashboard, chart, form, or visualization. The HTML is shipped to the dashboard via
a ``CANVAS`` event and displayed in a sandboxed iframe (OpenClaw's Canvas idea).
"""

from __future__ import annotations

from xplogent.core.events import Event, EventBus, EventType
from xplogent.safety.approval import RiskLevel
from xplogent.tools.base import Tool, ToolResult


class CanvasTool(Tool):
    name = "canvas"
    description = (
        "Render an interactive visual workspace for the user from HTML (with optional "
        "inline CSS and JavaScript). Use this for dashboards, charts, tables, forms, or "
        "any rich layout that is clearer than plain chat text. Provide a complete, "
        "self-contained HTML fragment or document."
    )
    parameters = {
        "type": "object",
        "properties": {
            "html": {"type": "string", "description": "Self-contained HTML to render."},
            "title": {"type": "string", "description": "Optional panel title."},
        },
        "required": ["html"],
    }
    risk = RiskLevel.LOW

    def __init__(self, bus: EventBus, agent_id: str = "", agent_name: str = "") -> None:
        self._bus, self._id, self._name = bus, agent_id, agent_name

    async def run(self, html: str, title: str = "Canvas") -> ToolResult:
        await self._bus.publish(Event(
            type=EventType.CANVAS,
            data={"html": html, "title": title, "agent_id": self._id, "agent_name": self._name},
        ))
        return ToolResult.success(f"Rendered '{title}' to the canvas ({len(html)} chars of HTML).")
