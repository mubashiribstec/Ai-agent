"""Xplogent CLI/TUI.

Commands:
    xplogent chat                 interactive agent session (streaming + inline approvals)
    xplogent run "<task>"         run a single task and exit
    xplogent model <provider:model>   set the active model
    xplogent memory search <q>    search episodic memory and facts
    xplogent skills list          list learned skills
    xplogent providers            list available providers
    xplogent serve                start the REST + WebSocket API
    xplogent orchestrate "<goal>" run a multi-agent team on a goal
    xplogent team --agent ...     run named agents concurrently
"""

from __future__ import annotations

import asyncio

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from xplogent.core.config import load_config, xplogent_home
from xplogent.core.events import EventBus, EventType
from xplogent.core.orchestrator import AgentSpec
from xplogent.memory.store import Store
from xplogent.providers.registry import available_providers
from xplogent.runtime import build_orchestrator, build_runtime
from xplogent.safety.approval import ApprovalRequest

app = typer.Typer(add_completion=False, help="Xplogent — your self-improving AI agent.")
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
            title="🧠 Xplogent",
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
            console.print("[bold blue]xplogent›[/] ", end="")
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
    from xplogent.interfaces.api.server import run_server

    run_server(host=host, port=port)


@app.command()
def voice(seconds: int = 6) -> None:
    """Talk to Xplogent (needs the 'voice' extra)."""
    from xplogent.interfaces.voice.audio import voice_loop

    async def _go() -> None:
        bus = EventBus()
        runtime = build_runtime(bus=bus, approve=_make_approver())
        try:
            await voice_loop(runtime, seconds=seconds)
        finally:
            await bus.close()
            await runtime.aclose()

    asyncio.run(_go())


# ── multi-agent ───────────────────────────────────────────────────────────────
async def _render_multi(bus: EventBus) -> None:
    """Concise per-agent rendering for multi-agent runs (token streams omitted)."""
    async for ev in bus.stream():
        d = ev.data
        who = d.get("agent_name", "?")
        if ev.type == EventType.RUN_PROGRESS:
            console.print(f"[bold cyan]🧭 planned {d.get('planned_tasks')} subtasks[/]")
        elif ev.type == EventType.AGENT_SPAWN:
            console.print(f"[green]🟢 {who}[/] ([dim]{d.get('role')}[/]) started")
        elif ev.type == EventType.TASK_UPDATE:
            console.print(f"[blue]📋 {d.get('title')}[/]: {d.get('status')}")
        elif ev.type == EventType.AGENT_MESSAGE:
            to = d.get("recipient") or "all"
            console.print(f"[magenta]💬 {d.get('sender')} → {to}:[/] {d.get('content')}")
        elif ev.type == EventType.TOOL_CALL:
            console.print(f"   [cyan]{who} → {d.get('tool')}[/]")
        elif ev.type == EventType.TOOL_RESULT:
            mark = "[green]✓[/]" if d.get("ok") else "[red]✗[/]"
            console.print(f"   {mark} [dim]{str(d.get('output',''))[:200]}[/]")
        elif ev.type == EventType.MESSAGE:
            console.print(f"[bold]{who}:[/] {d.get('content')}")
        elif ev.type == EventType.SKILL:
            console.print(f"[magenta]✨ {who} learned {d.get('facts',0)} fact(s)[/]")
        elif ev.type == EventType.ERROR:
            console.print(f"[red]error ({who}):[/] {d.get('message')}")


def _print_taskboard(tasks: list[dict]) -> None:
    if not tasks:
        return
    table = Table(title="task board", show_lines=False)
    table.add_column("task")
    table.add_column("role")
    table.add_column("status")
    for t in tasks:
        color = {"done": "green", "failed": "red", "active": "yellow"}.get(t["status"], "white")
        table.add_row(t["title"], t["role"], f"[{color}]{t['status']}[/]")
    console.print(table)


@app.command()
def orchestrate(goal: str, max: int = 0, mode: str = "auto") -> None:
    """Run a multi-agent team on a goal (auto-decomposed into subtasks)."""

    async def _go() -> None:
        bus = EventBus()
        runtime = build_orchestrator(bus=bus, approve=_make_approver())
        console.print(Panel(f"Goal: [bold]{goal}[/]\nmax concurrent: "
                            f"{max or runtime.orchestrator.default_max}",
                            title="🧠 Xplogent orchestrator", border_style="cyan"))
        consumer = asyncio.create_task(_render_multi(bus))
        result = await runtime.orchestrator.run_goal(goal, max_concurrent=max or None, mode=mode)
        await bus.close()
        await consumer
        _print_taskboard(result.get("tasks", []))
        console.print(f"[dim]peak concurrency: {result.get('peak_concurrency')} · "
                      f"run {result.get('run_id')}[/]")
        await runtime.aclose()

    asyncio.run(_go())


@app.command()
def team(agent: list[str] = typer.Option(None, "--agent", "-a",
         help="Repeatable. Format: name:role:task"), max: int = 0) -> None:
    """Run named agents concurrently. Example:
    xplogent team -a "researcher:researcher:find facts about X" -a "writer:coder:write a summary"
    """
    if not agent:
        console.print("[red]provide at least one --agent name:role:task[/]")
        raise typer.Exit(1)
    specs = []
    for spec in agent:
        parts = spec.split(":", 2)
        if len(parts) != 3:
            console.print(f"[red]bad --agent '{spec}', expected name:role:task[/]")
            raise typer.Exit(1)
        specs.append(AgentSpec(name=parts[0], role=parts[1], task=parts[2]))

    async def _go() -> None:
        bus = EventBus()
        runtime = build_orchestrator(bus=bus, approve=_make_approver())
        consumer = asyncio.create_task(_render_multi(bus))
        result = await runtime.orchestrator.run_team(specs, max_concurrent=max or None)
        await bus.close()
        await consumer
        for name, answer in result.get("results", {}).items():
            console.print(Panel(answer or "(no answer)", title=name, border_style="green"))
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
    cfg_path = xplogent_home() / "config.yaml"
    data = {}
    if cfg_path.exists():
        data = yaml.safe_load(cfg_path.read_text()) or {}
    data["model"] = spec
    cfg_path.write_text(yaml.safe_dump(data))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
