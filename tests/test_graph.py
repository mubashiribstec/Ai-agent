"""Knowledge-graph memory: reflection extracts triples, recall surfaces them."""

from __future__ import annotations

import json

import pytest

from tests.conftest import ScriptedProvider
from xplogent.memory.graph import context_block, ingest_relations
from xplogent.memory.store import Store
from xplogent.providers.base import Message, Role
from xplogent.skills.reflection import Reflector


def test_ingest_and_neighbors(tmp_path):
    store = Store(tmp_path / "m.db")
    ingest_relations(store, [
        ("Alice", "manages", "project Phoenix"),
        ("project Phoenix", "deploys to", "prod"),
        ("user", "prefers", "dark mode"),
    ], source="test")

    snap = store.graph_snapshot()
    assert {n["name"] for n in snap["nodes"]} >= {"Alice", "project Phoenix", "prod", "user"}
    assert len(snap["edges"]) == 3

    nb = store.neighbors("project Phoenix")
    rels = {(e["subject"], e["relation"], e["object"]) for e in nb}
    assert ("Alice", "manages", "project Phoenix") in rels
    assert ("project Phoenix", "deploys to", "prod") in rels
    store.close()


def test_edges_dedupe(tmp_path):
    store = Store(tmp_path / "m.db")
    ingest_relations(store, [("a", "rel", "b"), ("a", "rel", "b")])
    assert len(store.graph_snapshot()["edges"]) == 1
    store.close()


def test_context_block_matches_query_entities(tmp_path):
    store = Store(tmp_path / "m.db")
    ingest_relations(store, [("Phoenix", "owned by", "Alice")])
    block = context_block(store, "what's the status of Phoenix?")
    assert "Phoenix owned by Alice" in block
    assert context_block(store, "totally unrelated question") == ""
    store.close()


@pytest.mark.asyncio
async def test_reflector_extracts_relations():
    payload = json.dumps({
        "success": True,
        "facts": ["the user ships on Fridays"],
        "relations": [["user", "ships on", "Friday"], ["bad triple"]],
        "skill": None,
    })
    reflector = Reflector(ScriptedProvider([Message(role=Role.ASSISTANT, content=payload)]))
    result = await reflector.reflect("task", "transcript")
    assert ("user", "ships on", "Friday") in result.relations
    assert len(result.relations) == 1  # the malformed triple is dropped
