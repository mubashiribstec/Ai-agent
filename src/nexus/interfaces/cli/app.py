"""Nexus CLI/TUI.

Commands:
    nexus chat                 interactive agent session (streaming + inline approvals)
    nexus run "<task>"         run a single task and exit
    nexus model <provider:model>   set the active model
    nexus memory search <q>    search episodic memory and facts
    nexus skills list          list learned skills
    nexus providers            list available providers
    nexus serve                start the REST + WebSocket API
"""

from __future__ import annotations

import asyncio

import typer
import yaml
from rich.console import Console
from rich.panel import Panel

from nexus.core.config import load_config, nexus_home
from nexus.core.events import EventBus, EventType
from nexus.memory.store import Store
from nexus.providers.registry import available_providers
from nexus.runtime import build_runtime
from nexus.safety.approval import ApprovalRequest

app = typer.Typer(add_completion=False, help="Nexus — your self-improving AI agent.")
console = Console()


# ── shared helpers ────────────────────────────────────────────────────────────
def _make_approver():
    async def approve(req: ApprovalRequest) -> bool:
        console.print(
            Panel(
                f"[bold]{req.tool}[/]  risk=[yellow]{req.risk.value}[/]\n"
                f"{req.reason or ''}\n\n{req.arguments}",
                title="⚠ approval required",
                border_style="yellow",
            )
        )
        ans = await asyncio.to_thread(console.input, "[bold yellow]approve? \\[y/N][/] ")
        return ans.strip().lower() in {"y", "yes"}

    return approve


async def _render_events(bus: EventBus) -> None:
    async for ev in bus.stream():
        if ev.type == EventType.TOKEN:
            console.print(ev.data.get("text", ""), end="")
        elif ev.type == EventType.MESSAGE:
            console.print()  # newline after streamed tokens
        elif ev.type == EventType.TOOL_CALL:
            console.print(f"\n[cyan]→ {ev.data['tool']}[/] {ev.data.get('arguments', {})}")
        elif ev.type == EventType.TOOL_RESULT:
            ok = ev.data.get("ok")
            mark = "[green]✓[/]" if ok else "[red]✗[/]"
            out = str(ev.data.get("output", ""))
            console.print(f"{mark} [dim]{out[:500]}[/]")
        elif ev.type == EventType.MEMORY:
            console.print(
                f"[dim]🧠 recalled {ev.data.get('facts',0)} facts, "
                f"{ev.data.get('skills',0)} skills[/]"
            )
        elif ev.type == EventType.SKILL:
            skill = ev.data.get("skill")
            console.print(
                f"[magenta]✨ learned {ev.data.get('facts',0)} fact(s)"
                + (f", new skill '{skill}'" if skill else "")
                + "[/]"
            )
        elif ev.type == EventType.ERROR:
            console.print(f"[red]error:[/] {ev.data.get('message')}")


# ── commands ──────────────────────────────────────────────────────────────────
@app.command()
def chat() -> None:
    """Start an interactive agent session."""
    asyncio.run(_chat_loop())


async def _chat_loop() -> None:
    bus = EventBus()
    runtime = build_runtime(bus=bus, approve=_make_approver())
    console.print(
        Panel(
            f"Model: [bold]{runtime.config.model}[/]\n"
            "Type your task. Commands: /exit, /model <name>, /skills",
            title="🧠 Nexus",
            border_style="cyan",
        )
    )
    consumer = asyncio.create_task(_render_events(bus))
    try:
        while True:
            user = await asyncio.to_thread(console.input, "\n[bold green]you›[/] ")
            user = user.strip()
            if not user:
                continue
            if user in {"/exit", "/quit", "exit", "quit"}:
                break
            if user == "/skills":
                _print_skills(runtime.store)
                continue
            if user.startswith("/model "):
                _set_model(user.split(" ", 1)[1].strip())
                console.print("[dim]restart chat to apply[/]")
                continue
            console.print("[bold blue]nexus›[/] ", end="")
            await runtime.agent.run(user)
    finally:
        await bus.close()
        await consumer
        await runtime.aclose()
        console.print("\n[dim]session saved. bye![/]")


@app.command()
def run(task: str) -> None:
    """Run a single task non-interactively and print the answer."""

    async def _go() -> None:
        bus = EventBus()
        runtime = build_runtime(bus=bus, approve=_make_approver())
        consumer = asyncio.create_task(_render_events(bus))
        answer = await runtime.agent.run(task)
        await bus.close()
        await consumer
        await runtime.aclose()
        console.print(Panel(answer or "(no answer)", title="answer", border_style="green"))

    asyncio.run(_go())


@app.command()
def model(spec: str) -> None:
    """Set the active model, e.g. 'ollama:llama3.1' or 'openai:gpt-4o'."""
    _set_model(spec)
    console.print(f"[green]model set to[/] {spec}")


@app.command()
def providers() -> None:
    """List available providers."""
    for name in available_providers():
        console.print(f"• {name}")


@app.command(name="serve")
def serve(host: str | None = None, port: int | None = None) -> None:
    """Start the REST + WebSocket API server (needs the 'api' extra)."""
    from nexus.interfaces.api.server import run_server

    run_server(host=host, port=port)


@app.command()
def voice(seconds: int = 6) -> None:
    """Talk to Nexus (needs the 'voice' extra)."""
    from nexus.interfaces.voice.audio import voice_loop

    async def _go() -> None:
        bus = EventBus()
        runtime = build_runtime(bus=bus, approve=_make_approver())
        try:
            await voice_loop(runtime, seconds=seconds)
        finally:
            await bus.close()
            await runtime.aclose()

    asyncio.run(_go())


memory_app = typer.Typer(help="Inspect memory.")
skills_app = typer.Typer(help="Inspect learned skills.")
app.add_typer(memory_app, name="memory")
app.add_typer(skills_app, name="skills")


@memory_app.command("search")
def memory_search(query: str) -> None:
    """Search episodic messages and stored facts."""
    cfg = load_config()
    store = Store(cfg.db_path)
    facts = [f for f in store.all_facts() if query.lower() in f.content.lower()]
    msgs = store.search_messages(query, limit=10)
    console.print(f"[bold]Facts ({len(facts)})[/]")
    for f in facts:
        console.print(f"  • {f.content}")
    console.print(f"[bold]Messages ({len(msgs)})[/]")
    for m in msgs:
        console.print(f"  [{m['role']}] {m['content'][:120]}")
    store.close()


@skills_app.command("list")
def skills_list() -> None:
    """List learned skills."""
    cfg = load_config()
    store = Store(cfg.db_path)
    _print_skills(store)
    store.close()


# ── small utilities ───────────────────────────────────────────────────────────
def _print_skills(store: Store | None) -> None:
    if store is None:
        console.print("[dim]memory disabled[/]")
        return
    skills = store.all_skills()
    if not skills:
        console.print("[dim]no skills learned yet[/]")
        return
    for s in skills:
        console.print(f"[magenta]{s.name}[/] (used {s.uses}×) — {s.description}")


def _set_model(spec: str) -> None:
    cfg_path = nexus_home() / "config.yaml"
    data = {}
    if cfg_path.exists():
        data = yaml.safe_load(cfg_path.read_text()) or {}
    data["model"] = spec
    cfg_path.write_text(yaml.safe_dump(data))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
