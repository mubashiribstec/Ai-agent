"""FastAPI server exposing Xplogent over REST + WebSocket.

REST is convenient for one-shot calls and inspection; the WebSocket streams the
full agent event log live and carries the approval round-trip (the browser
dashboard resolves ``approval_required`` events). The server is created lazily so
importing this module never requires FastAPI unless you actually serve.
"""

from __future__ import annotations

import asyncio
import os
import uuid

from xplogent.core.config import load_config
from xplogent.core.events import EventBus
from xplogent.core.orchestrator import AgentSpec
from xplogent.memory.store import Store
from xplogent.monitor.recorder import TraceRecorder
from xplogent.providers.registry import available_providers
from xplogent.runtime import build_orchestrator, build_runtime
from xplogent.safety.approval import ApprovalRequest


def create_app():
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    app = FastAPI(title="Xplogent Agent API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    class RunRequest(BaseModel):
        task: str

    class AgentSpecModel(BaseModel):
        name: str
        role: str = "operator"
        task: str = ""
        model: str | None = None

    class OrchestrateRequest(BaseModel):
        goal: str | None = None
        specs: list[AgentSpecModel] | None = None
        max_concurrent: int | None = None
        mode: str = "auto"

    # Live multi-agent runs, keyed by run_id, for monitoring + control.
    active_runs: dict[str, dict] = {}

    @app.get("/health")
    async def health() -> dict:
        cfg = load_config()
        return {"status": "ok", "model": cfg.model, "providers": available_providers()}

    @app.get("/config")
    async def config() -> dict:
        cfg = load_config()
        return {
            "model": cfg.model,
            "reflection_model": cfg.reflection_model,
            "embedding_model": cfg.embedding_model,
            "tools_enabled": cfg.tools.get("enabled", []),
            "providers": available_providers(),
        }

    @app.get("/skills")
    async def skills() -> dict:
        cfg = load_config()
        store = Store(cfg.db_path)
        out = [
            {"name": s.name, "description": s.description, "uses": s.uses}
            for s in store.all_skills()
        ]
        store.close()
        return {"skills": out}

    @app.get("/memory/search")
    async def memory_search(q: str) -> dict:
        cfg = load_config()
        store = Store(cfg.db_path)
        facts = [f.content for f in store.all_facts() if q.lower() in f.content.lower()]
        msgs = store.search_messages(q, limit=10)
        store.close()
        return {"facts": facts, "messages": msgs}

    @app.post("/run")
    async def run(req: RunRequest) -> dict:
        """One-shot run. Confirmation-tier tools are blocked (no interactive approver)."""
        bus = EventBus()
        runtime = build_runtime(bus=bus)
        answer = await runtime.agent.run(req.task)
        await runtime.aclose()
        return {"answer": answer}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        await websocket.accept()
        bus = EventBus()
        loop = asyncio.get_event_loop()
        pending: dict[str, asyncio.Future] = {}

        async def approve(reqo: ApprovalRequest) -> bool:
            approval_id = uuid.uuid4().hex[:8]
            fut: asyncio.Future = loop.create_future()
            pending[approval_id] = fut
            await websocket.send_json({
                "type": "approval_required", "id": approval_id,
                "tool": reqo.tool, "risk": reqo.risk.value,
                "reason": reqo.reason, "arguments": reqo.arguments,
            })
            try:
                return await asyncio.wait_for(fut, timeout=300)
            except TimeoutError:
                return False

        runtime = build_runtime(bus=bus, approve=approve)

        async def forward() -> None:
            async for ev in bus.stream():
                await websocket.send_json({"type": ev.type.value, **ev.data})

        forwarder = asyncio.create_task(forward())

        async def handle_task(task: str) -> None:
            await runtime.agent.run(task)
            await websocket.send_json({"type": "done"})

        try:
            while True:
                msg = await websocket.receive_json()
                kind = msg.get("type")
                if kind == "task":
                    asyncio.create_task(handle_task(msg.get("task", "")))
                elif kind == "approval":
                    fut = pending.pop(msg.get("id", ""), None)
                    if fut and not fut.done():
                        fut.set_result(bool(msg.get("allowed")))
        except WebSocketDisconnect:
            pass
        finally:
            await bus.close()
            forwarder.cancel()
            await runtime.aclose()

    # ── Multi-agent orchestration + deep monitoring ──────────────────────────
    @app.post("/orchestrate")
    async def orchestrate(req: OrchestrateRequest) -> dict:
        """Launch a multi-agent run in the background; returns its run_id.

        Connect to ``/ws/monitor?run_id=<id>`` to watch it live, or poll
        ``/runs/{id}`` and ``/agents``.
        """
        mbus = EventBus()
        runtime = build_orchestrator(bus=mbus)
        orch = runtime.orchestrator
        recorder = TraceRecorder(mbus, runtime.store, orch.run_id)
        recorder.start()

        async def go() -> None:
            try:
                if req.specs:
                    specs = [AgentSpec(**s.model_dump()) for s in req.specs]
                    await orch.run_team(specs, max_concurrent=req.max_concurrent)
                else:
                    await orch.run_goal(req.goal or "", max_concurrent=req.max_concurrent,
                                        mode=req.mode)
            finally:
                await mbus.close()
                await recorder.stop()
                await runtime.aclose()
                active_runs.pop(orch.run_id, None)

        task = asyncio.create_task(go())
        active_runs[orch.run_id] = {
            "orchestrator": orch, "recorder": recorder, "bus": mbus, "task": task,
        }
        return {"run_id": orch.run_id, "mode": "manual" if req.specs else req.mode}

    @app.get("/runs")
    async def runs() -> dict:
        store = Store(load_config().db_path)
        out = store.list_runs()
        store.close()
        return {"runs": out, "active": list(active_runs)}

    @app.get("/runs/{run_id}")
    async def run_detail(run_id: str) -> dict:
        store = Store(load_config().db_path)
        info = store.get_run(run_id)
        store.close()
        live = active_runs.get(run_id)
        metrics = live["recorder"].snapshot() if live else []
        return {"run": info, "metrics": metrics}

    @app.get("/runs/{run_id}/events")
    async def run_events(run_id: str) -> dict:
        store = Store(load_config().db_path)
        out = store.run_events(run_id)
        store.close()
        return {"events": out}

    @app.get("/agents")
    async def agents() -> dict:
        live = []
        for rid, info in active_runs.items():
            for a in info["orchestrator"].live_agents():
                live.append({"run_id": rid, **a})
        return {"agents": live}

    @app.get("/messages")
    async def messages(run_id: str | None = None) -> dict:
        store = Store(load_config().db_path)
        out = store.list_agent_messages(run_id)
        store.close()
        return {"messages": out}

    @app.post("/agents/{agent_id}/{action}")
    async def control_agent(agent_id: str, action: str) -> dict:
        if action not in {"pause", "resume", "cancel"}:
            return {"ok": False, "error": "unknown action"}
        for info in active_runs.values():
            if info["orchestrator"].control(agent_id, action):
                return {"ok": True}
        return {"ok": False, "error": "agent not found"}

    @app.websocket("/ws/monitor")
    async def ws_monitor(websocket: WebSocket) -> None:
        await websocket.accept()
        run_id = websocket.query_params.get("run_id")
        info = active_runs.get(run_id) if run_id else (
            next(iter(active_runs.values()), None)
        )
        if not info:
            await websocket.send_json({"type": "error", "message": "no such run"})
            await websocket.close()
            return
        queue = info["bus"].subscribe()
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                await websocket.send_json({"type": event.type.value, **event.data})
        except WebSocketDisconnect:
            pass
        finally:
            info["bus"].unsubscribe(queue)

    return app


def run_server(host: str | None = None, port: int | None = None) -> None:
    import uvicorn

    host = host or os.environ.get("XPLOGENT_API_HOST", "127.0.0.1")
    port = int(port or os.environ.get("XPLOGENT_API_PORT", 8765))
    uvicorn.run(create_app(), host=host, port=port)
