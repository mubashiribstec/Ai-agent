# Troubleshooting

## The dashboard doesn't open / shows a blank page
`xplogent up` serves the dashboard from `web/dist`. If you don't have it built:

```bash
cd web && npm install && npm run build
```

Then run `xplogent up` again. Without Node.js, run the API (`xplogent serve`) and
the dev server (`cd web && npm run dev`) separately.

## "confirmation required but no approver" / actions blocked
Over the API and MCP there's no human to approve `confirm`-tier actions, so they
are blocked by default. Either lower the risk policy for that tier in **Settings
→ Safety**, use a role whose policy is `auto` for it, or enable auto-approval for
MCP.

## Ollama errors / no response
Make sure Ollama is running and the models are pulled:

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
```

Check `OLLAMA_HOST` if it isn't on the default `http://localhost:11434`.

## GUI automation does nothing (headless server)
Mouse/keyboard/screenshot tools need a real display. On a headless machine they
report "no display available" — drive Xplogent through the dashboard/API instead.

## Update says "not a git checkout"
One-click update only works for git-clone/editable installs. Reinstall from the
repository, or update via your package manager.
