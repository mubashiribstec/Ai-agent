# 🧠 Xplogent — a self-improving AI agent framework

Xplogent is a personal AI agent you fully own and run yourself. It works with **any
LLM provider** (including **local Ollama**, fully offline), keeps **its own
persistent memory**, **improves itself** by reflecting on tasks and writing
reusable skills, and can **control your whole PC** (shell, files, mouse/keyboard,
screen, browser) — all behind a configurable **safety/approval layer**.

It's inspired by [Hermes](https://github.com/NousResearch/hermes-agent) and the
OpenClaw ecosystem, but built as a leaner, cleanly-architected core that's easy
to extend with plugins and MCP servers. It runs on **Windows and Linux** (and macOS).

## Why Xplogent

| Capability | Xplogent |
|---|---|
| **Providers** | Ollama (local/offline), OpenAI, Anthropic, OpenRouter (200+ models) — switch with one config value |
| **Memory** | SQLite + local embeddings; short-term, long-term, and episodic recall |
| **Self-improvement** | Reflects after tasks, consolidates memory, auto-creates & reuses skills |
| **Multi-agent** | Run many agents at once (you set the limit); orchestrator auto-decomposes a goal, or define named agents |
| **Collaboration** | Agents broadcast status and send direct messages to each other |
| **Deep monitoring** | Live per-agent telemetry, kanban task board, agent chatter, persisted run traces |
| **Agent rights** | Per-agent role profiles: allowed tools, risk policy, filesystem path scope, network |
| **PC control** | Shell, filesystem, Python, web, GUI (mouse/keyboard/screenshots), browser |
| **Safety** | Every risky action is risk-classified and gated (`auto` / `confirm` / `deny`) |
| **Interfaces** | CLI/TUI, REST + WebSocket API, Web dashboard (Chat + Mission Control), Voice |
| **Extensible** | Drop-in Python plugins + MCP servers via one unified tool registry |

## Multi-agent teams

```bash
# Auto: the orchestrator plans subtasks and runs a team (max 3 at once)
xplogent orchestrate "research the top 3 vector DBs and write a comparison file" --max 3

# Manual: define named agents (name:role:task), run them concurrently
xplogent team -a "scout:researcher:find facts about X" \
              -a "writer:coder:write a summary to notes.md"
```

Agents share a **message bus** (broadcast + direct messages) and a **task board**.
Each agent runs under a **role profile** (see `roles:` in `config/default.yaml`)
that limits its tools, risk policy, filesystem paths, and network access — so you
control exactly what every agent may do. Watch it all live in the **Mission
Control** dashboard (agent cards with pause/cancel, kanban, agent chatter) or in
the terminal.

## Architecture

```
              CLI/TUI · Voice · Web (Chat + Mission Control)
                                  │
                  REST + WebSocket API (FastAPI)  ── monitor ──┐
                                  │                            │
                          Event bus (async)            TraceRecorder → SQLite
                                  │
                       ┌──────────┴──────────┐  semaphore(max_concurrent)
                       │ Orchestrator + Plan │  auto-decompose OR named agents
                       └──────────┬──────────┘
            ┌─────────────────────┼─────────────────────┐
        Agent(researcher)    Agent(coder)        Agent(reviewer)
            │ permission profile · own memory · collab tools │
            └──── MessageBus (broadcast + direct) · TaskBoard ┘
                                  │
        per agent: providers │ memory │ tools │ safety │ skills │ plugins
```

See `src/xplogent/` for the implementation; each subsystem is a self-contained
package behind a small interface, so providers, tools, and memory backends are
swappable.

## Quick start

```bash
# 1. Install (Ollama-only base; add extras as needed)
pip install -e ".[providers,memory,api]"        # or ".[all]"

# 2. Run a local model with Ollama
ollama pull llama3.1
ollama pull nomic-embed-text            # for memory embeddings

# 3. Configure
cp .env.example .env                    # set XPLOGENT_MODEL / API keys if using hosted

# 4. Chat in the terminal
xplogent chat

# Other commands
xplogent model openai:gpt-4o               # switch provider/model
xplogent serve                             # start REST + WebSocket API
xplogent memory search "what do you know about me"
xplogent skills list
```

### Web dashboard

```bash
xplogent serve            # backend API on :8765
cd web && npm install && npm run dev    # dashboard on :5173
```

## Installation extras

| Extra | Adds |
|---|---|
| `providers` | OpenAI + Anthropic SDKs |
| `control` | `pyautogui`, `mss`, Playwright (GUI + browser control) |
| `memory` | `sqlite-vec` + local embeddings |
| `api` | FastAPI + Uvicorn (REST/WebSocket) |
| `voice` | Whisper STT + TTS |
| `mcp` | MCP client for external tool servers |
| `all` | everything above + dev tools |

## Safety

Full PC control is powerful, so it is **safe by default**. Every tool call is
risk-classified (`low`/`medium`/`high`/`critical`) and routed through an
approval policy you control in `config/default.yaml`. Destructive commands match
a deny-list and are blocked outright. In the CLI you approve inline; over the API
the agent emits an `approval_required` event your UI resolves.

> ⚠️ GUI automation (`pyautogui`) needs a real display. On a headless/remote
> machine, drive Xplogent through the API/dashboard instead.

## Status

Active development. Build order and design live in the project plan. Contributions
and issues welcome on the `claude/custom-ai-agent-framework-wxq891` branch.

## License

MIT
