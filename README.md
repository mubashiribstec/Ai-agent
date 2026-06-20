# 🧠 Nexus — a self-improving AI agent framework

Nexus is a personal AI agent you fully own and run yourself. It works with **any
LLM provider** (including **local Ollama**, fully offline), keeps **its own
persistent memory**, **improves itself** by reflecting on tasks and writing
reusable skills, and can **control your whole PC** (shell, files, mouse/keyboard,
screen, browser) — all behind a configurable **safety/approval layer**.

It's inspired by [Hermes](https://github.com/NousResearch/hermes-agent) and the
OpenClaw ecosystem, but built as a leaner, cleanly-architected core that's easy
to extend with plugins and MCP servers.

## Why Nexus

| Capability | Nexus |
|---|---|
| **Providers** | Ollama (local/offline), OpenAI, Anthropic, OpenRouter (200+ models) — switch with one config value |
| **Memory** | SQLite + local embeddings; short-term, long-term, and episodic recall |
| **Self-improvement** | Reflects after tasks, consolidates memory, auto-creates & reuses skills |
| **PC control** | Shell, filesystem, Python, web, GUI (mouse/keyboard/screenshots), browser |
| **Safety** | Every risky action is risk-classified and gated (`auto` / `confirm` / `deny`) |
| **Interfaces** | CLI/TUI, REST + WebSocket API, Web dashboard, Voice |
| **Extensible** | Drop-in Python plugins + MCP servers via one unified tool registry |

## Architecture

```
                ┌───────────── Interfaces ─────────────┐
   CLI/TUI ──┐  Voice (STT/TTS) ──┐   Web Dashboard (TS) ─┐
             │                    │                       │
             └──────── REST + WebSocket API (FastAPI) ────┘
                                  │
                          Event bus (async)
                                  │
        ┌─────────────────── Agent loop (core) ───────────────────┐
        │  providers │ memory │ tools │ safety │ skills │ plugins  │
        └──────────────────────────────────────────────────────────┘
```

See `src/nexus/` for the implementation; each subsystem is a self-contained
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
cp .env.example .env                    # set NEXUS_MODEL / API keys if using hosted

# 4. Chat in the terminal
nexus chat

# Other commands
nexus model openai:gpt-4o               # switch provider/model
nexus serve                             # start REST + WebSocket API
nexus memory search "what do you know about me"
nexus skills list
```

### Web dashboard

```bash
nexus serve            # backend API on :8765
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
> machine, drive Nexus through the API/dashboard instead.

## Status

Active development. Build order and design live in the project plan. Contributions
and issues welcome on the `claude/custom-ai-agent-framework-wxq891` branch.

## License

MIT
