"""MCP (Model Context Protocol) client integration.

Connects to external MCP servers and surfaces their tools through the same
:class:`ToolRegistry` the agent already uses, giving instant access to the MCP
ecosystem. Requires the optional ``mcp`` extra; if it's missing this is a no-op.
"""

from __future__ import annotations

from typing import Any

from xplogent.safety.approval import RiskLevel
from xplogent.tools.base import Tool, ToolResult
from xplogent.tools.registry import ToolRegistry


class MCPTool(Tool):
    """Wraps a single tool exposed by an MCP server."""

    risk = RiskLevel.MEDIUM

    def __init__(self, session: Any, name: str, description: str, schema: dict) -> None:
        self._session = session
        self.name = f"mcp_{name}"
        self._remote_name = name
        self.description = description or f"MCP tool '{name}'"
        self.parameters = schema or {"type": "object", "properties": {}}

    async def run(self, **kwargs: Any) -> ToolResult:
        try:
            result = await self._session.call_tool(self._remote_name, kwargs)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.failure(f"MCP call failed: {exc}")
        parts = []
        for item in getattr(result, "content", []) or []:
            parts.append(getattr(item, "text", str(item)))
        return ToolResult.success("\n".join(parts) or "(no content)")


async def connect_mcp_server(registry: ToolRegistry, command: str, args: list[str]) -> int:
    """Connect to a stdio MCP server and register its tools. Returns tool count.

    Returns 0 (no-op) if the optional ``mcp`` package is not installed.
    """
    try:
        from mcp import ClientSession, StdioServerParameters  # type: ignore
        from mcp.client.stdio import stdio_client  # type: ignore
    except ImportError:
        return 0

    params = StdioServerParameters(command=command, args=args)
    count = 0
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listing = await session.list_tools()
            for tool in listing.tools:
                registry.register(
                    MCPTool(session, tool.name, tool.description or "",
                            tool.inputSchema or {})
                )
                count += 1
    return count
