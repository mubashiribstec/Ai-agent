# Automation: schedules, vision & sandboxed execution

Three capabilities let Xplogent work on its own, see what it's doing, and run
commands somewhere safer than your bare machine.

## Scheduled jobs (natural-language cron)

Open the **Schedules** tab (or use the CLI) to have the agent run on a timer —
unattended, with full tools, memory and skills. Jobs are saved to disk and
survive restarts.

Write the timing in plain English or as a 5-field cron string:

| Example | Meaning |
| --- | --- |
| `every day at 9am` | daily at 09:00 |
| `every 2 hours` | every two hours |
| `every monday at 08:00` | weekly, Monday morning |
| `every 15 minutes` | quarter-hourly |
| `in 30 minutes` | once, then done |
| `0 9 * * 1` | cron (needs `pip install 'xplogent[scheduler]'`) |

From the CLI:

```bash
xplogent schedule add "every day at 9am" "summarize my unread email"
xplogent schedule list
xplogent schedule toggle 3      # pause/resume
xplogent schedule remove 3
```

Scheduled runs auto-approve tools up to **high** risk so they can actually do
work; **critical** actions (and anything matching the deny-list) stay blocked.
Pick **single agent** or **agent team** mode per job.

## Vision — let the agent see

The `analyze_image` tool sends an image (e.g. a screenshot) to a vision-capable
model and returns a description or answer. Combined with `screenshot`/`browser`
this closes the see → decide → act loop:

1. `screenshot` → saves a PNG and returns its path
2. `analyze_image(path, "where is the login button?")`
3. `mouse`/`keyboard`/`browser` act on the answer

Set a **Vision model** in Settings (e.g. `openai:gpt-4o`,
`anthropic:claude-sonnet-4-6`, or local `ollama:llava`). Leave it blank to reuse
your active model if it already supports images.

## Sandboxed execution backends

By default `shell` and `python_exec` run on your machine (`local`). In
**Settings → Execution backend** you can switch them to:

- **docker** — run inside a container (`python:3.11-slim` by default, or a named
  long-lived container you already have running).
- **ssh** — run on a remote host (set host/user/key).

This limits the agent's reach without changing any tool. The safety deny-list
still runs *before* a command is dispatched, on every backend. Docker/SSH use the
system `docker`/`ssh` clients; if they aren't installed you'll get a clear error
instead of a crash.
