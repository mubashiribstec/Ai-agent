"""Agent evals: an LLM-judged suite runs each case and records pass-rate,
plus per-turn usage persists to the analytics table."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from tests.conftest import ScriptedProvider
from xplogent.core.agent import Agent
from xplogent.core.config import load_config
from xplogent.core.evals import promote_variant, run_ab, run_suite
from xplogent.memory.manager import MemoryManager
from xplogent.memory.store import Store
from xplogent.memory.vector import Embedder
from xplogent.providers.base import Message, Provider, Role, StreamEvent, StreamKind
from xplogent.safety.approval import SafetyManager
from xplogent.tools.registry import ToolRegistry


class _SmartProvider(Provider):
    """Answers prompts normally but returns a JSON verdict to the LLM judge,
    distinguished by the 'evaluator' marker in the judge's system prompt."""

    name = "scripted"

    def __init__(self, model: str = "scripted", **_kw) -> None:
        super().__init__(model="scripted")

    async def stream(  # type: ignore[override]
        self, messages: list[Message], tools=None, **kwargs
    ) -> AsyncIterator[StreamEvent]:
        system = messages[0].content.lower() if messages else ""
        if "evaluator" in system:
            content = '{"pass": true, "score": 0.9, "reason": "mentions 4"}'
        else:
            content = "The answer is 4."
        yield StreamEvent(kind=StreamKind.TOKEN, text=content)
        yield StreamEvent(kind=StreamKind.DONE, message=Message(role=Role.ASSISTANT, content=content))

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_run_suite_judges_and_records(monkeypatch):
    cfg = load_config()
    store = Store(cfg.db_path)
    eid = store.upsert_eval("math", "basic arithmetic")
    store.add_eval_case(eid, "what is 2+2?", "answer mentions 4")
    store.close()

    monkeypatch.setattr("xplogent.runtime.build_provider", lambda m, **k: _SmartProvider(m))
    monkeypatch.setattr("xplogent.core.evals.build_provider", lambda m, **k: _SmartProvider(m))

    res = await run_suite(eid, cfg)
    assert res["total"] == 1
    assert res["passed"] == 1
    assert res["score"] == 0.9
    assert res["results"][0]["passed"] is True

    store = Store(cfg.db_path)
    suite = store.list_evals()[0]
    assert suite["runs"][0]["passed"] == 1
    store.close()


@pytest.mark.asyncio
async def test_ab_runs_variants_and_picks_winner(monkeypatch):
    cfg = load_config()
    store = Store(cfg.db_path)
    eid = store.upsert_eval("math")
    store.add_eval_case(eid, "2+2?", "mentions 4")
    store.close()

    monkeypatch.setattr("xplogent.runtime.build_provider", lambda m, **k: _SmartProvider(m))
    monkeypatch.setattr("xplogent.core.evals.build_provider", lambda m, **k: _SmartProvider(m))

    res = await run_ab(eid, [
        {"name": "A", "system_prompt": "be terse"},
        {"name": "B", "model": "openai:gpt-4o"},
    ])
    assert {v["name"] for v in res["variants"]} == {"A", "B"}
    assert res["winner"] in {"A", "B"}
    assert all(v["total"] == 1 for v in res["variants"])

    # Each variant recorded a labelled run in history.
    store = Store(cfg.db_path)
    labels = [r["model"] for r in store.list_evals()[0]["runs"]]
    assert any(label.startswith("A ·") for label in labels)
    store.close()


def test_promote_variant_writes_config(monkeypatch, tmp_path):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    out = promote_variant(system_prompt="be excellent", model="openai:gpt-4o")
    assert out["ok"] and "agent" in out["promoted"] and "model" in out["promoted"]
    cfg = load_config()
    assert cfg.agent.get("system_prompt") == "be excellent"
    assert cfg.model == "openai:gpt-4o"


@pytest.mark.asyncio
async def test_usage_persists_for_analytics():
    cfg = load_config()
    store = Store(cfg.db_path)
    embedder = Embedder(ScriptedProvider([]))
    sid = store.create_session("t")
    memory = MemoryManager(store, embedder, session_id=sid)

    reply = Message(role=Role.ASSISTANT, content="hi",
                    usage={"input_tokens": 50, "output_tokens": 7})
    agent = Agent(cfg, ScriptedProvider([reply]), ToolRegistry.from_config([]),
                  SafetyManager(), memory=memory)
    await agent.run("hello")

    rows = store.usage_rows()
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 50
    assert rows[0]["output_tokens"] == 7
    store.close()
