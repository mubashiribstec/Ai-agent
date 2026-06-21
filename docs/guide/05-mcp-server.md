# Use Xplogent from other tools (MCP)

Xplogent can run **as an MCP server**, so any MCP client — Claude Desktop, Claude
Code, or another agent — can call into it.

```bash
pip install -e ".[mcp]"
xplogent mcp                                          # stdio (default)
xplogent mcp --transport streamable-http --port 8766  # remote / HTTP
```

## Register it

**Claude Code:**

```bash
claude mcp add xplogent -- xplogent mcp
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "xplogent": { "command": "xplogent-mcp" }
  }
}
```

## What's exposed

- `xplogent_run_agent(task)` — delegate a whole task to one agent.
- `xplogent_orchestrate(goal, max_concurrent)` — launch a multi-agent team.
- `xplogent_search_memory`, `xplogent_list_skills`, `xplogent_remember`.
- Each PC-control tool (shell, files, GUI, browser) — toggle with
  `mcp.server.expose_raw_tools`.

MCP-driven runs use the `mcp.server.agent_role` profile; confirm-tier actions are
blocked unless `mcp.server.auto_approve` is on. Use a `restricted` role for
untrusted clients.
