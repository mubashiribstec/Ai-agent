# Multi-agent teams

Xplogent can run several agents at the same time. You choose how many run
concurrently (`max_concurrent_agents`).

## Two ways to run a team

**Auto** — give one goal; the orchestrator decomposes it into subtasks and runs
role-scoped agents, honoring dependencies:

```bash
xplogent orchestrate "research the top 3 vector DBs and write a comparison" --max 3
```

**Manual** — define named agents yourself:

```bash
xplogent team -a "scout:researcher:find facts about X" \
              -a "writer:coder:write a summary to notes.md"
```

In the dashboard, open **Mission Control**, type a goal, set the concurrency
slider, and click **Launch team**.

## How agents collaborate

Agents share a message bus and can:
- **broadcast** status to the whole team,
- **send_message** directly to a named agent,
- **read_inbox** to see what others told them.

A shared **task board** tracks each subtask (pending → active → done/failed).

## Monitoring

Mission Control shows a live card per agent (status, current tool, steps,
tokens), the task board, and the inter-agent chatter. You can **pause**,
**resume**, or **cancel** any agent mid-run.
