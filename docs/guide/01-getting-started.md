# Getting started

Xplogent is a personal, self-improving AI agent you run yourself. It works with
any LLM provider (including local **Ollama**, fully offline), keeps its own
memory, can run **many agents at once**, and can control your PC behind a safety
layer.

## Install

```bash
# Linux / macOS
bash install.sh
# Windows (PowerShell)
./install.ps1
```

The installer creates a virtual environment, installs Xplogent, and builds the
dashboard (if Node.js is present).

## Configure

Run the wizard once:

```bash
xplogent setup
```

It asks for your provider (Ollama / OpenAI / Anthropic / OpenRouter), the model,
and an API key if you chose a hosted provider. For Ollama it can pull the models
for you. Everything is saved under `~/.xplogent/`.

## Launch

```bash
xplogent up
```

This starts the backend, serves the dashboard, and opens your browser. From
there you can chat, run multi-agent teams in **Mission Control**, change every
setting in **Settings**, and read this guide.

Prefer the terminal? `xplogent chat` for a single agent, or
`xplogent orchestrate "your goal" --max 3` for a team.
