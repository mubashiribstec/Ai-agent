"""FastAPI server exposing Nexus over REST + WebSocket.

REST is convenient for one-shot calls and inspection; the WebSocket streams the
full agent event log live and carries the approval round-trip (the browser
dashboard resolves ``approval_required`` events). The server is created lazily so
importing this module never requires FastAPI unless you actually serve.
"""

from __future__ import annotations

import asyncio
import os
import uuid

from nexus.core.config import load_config
from nexus.core.events import EventBus
from nexus.memory.store import Store
from nexus.providers.registry import available_providers
from nexus.runtime import build_runtime
from nexus.safety.approval import ApprovalRequest


def create_app():
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    app = FastAPI(title="Nexus Agent API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    class RunRequest(BaseModel):
        task: str

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

    return app


def run_server(host: str | None = None, port: int | None = None) -> None:
    import uvicorn

    host = host or os.environ.get("NEXUS_API_HOST", "127.0.0.1")
    port = int(port or os.environ.get("NEXUS_API_PORT", 8765))
    uvicorn.run(create_app(), host=host, port=port)
