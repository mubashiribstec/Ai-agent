"""Agent-curated MEMORY.md via the batched `memory` tool."""

from __future__ import annotations

import pytest

from xplogent.core.persona import load_memory, memory_path
from xplogent.tools.memory import MemoryTool


@pytest.mark.asyncio
async def test_add_replace_remove_apply_atomically(tmp_path, monkeypatch):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    tool = MemoryTool(max_chars=6000)

    r = await tool.run(operations=[
        {"op": "add", "text": "User prefers dark mode"},
        {"op": "add", "text": "User ships on Fridays"},
    ])
    assert r.ok
    mem = load_memory()
    assert "User prefers dark mode" in mem
    assert "User ships on Fridays" in mem

    # replace one line, remove another
    r2 = await tool.run(operations=[
        {"op": "replace", "match": "dark mode", "text": "User prefers light mode"},
        {"op": "remove", "match": "Fridays"},
    ])
    assert r2.ok
    mem2 = load_memory()
    assert "light mode" in mem2
    assert "dark mode" not in mem2
    assert "Fridays" not in mem2


@pytest.mark.asyncio
async def test_over_budget_batch_is_rejected_and_file_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    tool = MemoryTool(max_chars=120)
    load_memory()  # seed the default file
    before = memory_path().read_text(encoding="utf-8")

    r = await tool.run(operations=[{"op": "add", "text": "x" * 500}])
    assert not r.ok
    assert "budget" in r.error
    assert memory_path().read_text(encoding="utf-8") == before  # unchanged


@pytest.mark.asyncio
async def test_invalid_op_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    tool = MemoryTool(max_chars=6000)
    assert not (await tool.run(operations=[{"op": "delete", "text": "nope"}])).ok
    assert not (await tool.run(operations=[])).ok
