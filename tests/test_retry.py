"""Error classification + retry policy, and orchestrator task-level retry."""

from __future__ import annotations

import httpx
import pytest

from xplogent.core.retry import (
    ErrorClass,
    RetryPolicy,
    classify_error,
    with_retry,
)


def test_classify_buckets():
    assert classify_error(TimeoutError()) == ErrorClass.TIMEOUT
    assert classify_error(httpx.ConnectError("boom")) == ErrorClass.TRANSIENT
    assert classify_error(Exception("HTTP 429 rate limit")) == ErrorClass.RATE_LIMIT
    assert classify_error(Exception("connection reset by peer")) == ErrorClass.TRANSIENT
    assert classify_error(ValueError("bad argument")) == ErrorClass.FATAL


def test_policy_backoff_grows_and_caps():
    p = RetryPolicy(max_attempts=4, base_delay=1, factor=2, max_delay=5)
    assert p.delay_for(1) == 1
    assert p.delay_for(2) == 2
    assert p.delay_for(3) == 4
    assert p.delay_for(4) == 5  # capped


@pytest.mark.asyncio
async def test_with_retry_succeeds_after_transient():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("temporary")
        return "ok"

    res = await with_retry(flaky, RetryPolicy(max_attempts=3, base_delay=0))
    assert res == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_with_retry_reraises_fatal():
    async def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        await with_retry(boom, RetryPolicy(max_attempts=3, base_delay=0))


@pytest.mark.asyncio
async def test_orchestrator_retries_then_completes(monkeypatch):
    """A worker that fails twice (transient) then succeeds should complete."""
    from tests.test_orchestrator import _orchestrator
    from xplogent.core.taskboard import Task

    orch = _orchestrator(monkeypatch, reply="done", max_concurrent=2)
    orch.task_retries = 3
    import xplogent.core.orchestrator as orch_mod

    async def fake_decompose(self, goal, roles, count=3):
        return [Task(id="t1", title="x", description="do x", role="operator")]

    monkeypatch.setattr(orch_mod.Planner, "decompose", fake_decompose)

    attempts = {"n": 0}
    real_spawn = orch._spawn

    async def flaky_spawn(agent, task):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.ConnectError("temporary network")
        return await real_spawn(agent, task)

    monkeypatch.setattr(orch, "_spawn", flaky_spawn)
    result = await orch.run_goal("do a thing", max_concurrent=2)
    statuses = {t["id"]: t["status"] for t in result["tasks"]}
    assert statuses == {"t1": "done"}
    assert attempts["n"] == 3
    await orch.aclose()


@pytest.mark.asyncio
async def test_orchestrator_fatal_fails_fast(monkeypatch):
    from tests.test_orchestrator import _orchestrator
    from xplogent.core.taskboard import Task

    orch = _orchestrator(monkeypatch, reply="done", max_concurrent=2)
    orch.task_retries = 3
    import xplogent.core.orchestrator as orch_mod

    async def fake_decompose(self, goal, roles, count=3):
        return [Task(id="t1", title="x", description="do x", role="operator")]

    monkeypatch.setattr(orch_mod.Planner, "decompose", fake_decompose)

    attempts = {"n": 0}

    async def fatal_spawn(agent, task):
        attempts["n"] += 1
        raise ValueError("bad request")

    monkeypatch.setattr(orch, "_spawn", fatal_spawn)
    result = await orch.run_goal("do a thing", max_concurrent=2)
    statuses = {t["id"]: t["status"] for t in result["tasks"]}
    assert statuses == {"t1": "failed"}
    assert attempts["n"] == 1  # fatal → no retry
    await orch.aclose()
