"""RAG: chunking, ingest, and hybrid (semantic + bm25) search with citations."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.core.rag import chunk_text, hybrid_search, ingest_path, ingest_text
from xplogent.memory.store import Store
from xplogent.memory.vector import Embedder


def test_chunk_text_splits_on_paragraphs():
    text = "\n\n".join(f"paragraph number {i} with some words" for i in range(200))
    chunks = chunk_text(text, size=400, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 700 for c in chunks)


@pytest.mark.asyncio
async def test_ingest_and_search(tmp_path):
    store = Store(tmp_path / "m.db")
    embedder = Embedder(ScriptedProvider([]))
    f = tmp_path / "notes.md"
    f.write_text("# Deploy\n\nWe deploy the website every Friday to the prod server.\n\n"
                 "# Pets\n\nThe office cat is named Mochi.")
    res = await ingest_path(store, embedder, str(f))
    assert res["ok"] and res["chunks"] >= 1
    assert store.list_documents()[0]["title"] == "notes.md"

    hits = await hybrid_search(store, embedder, "when do we deploy the website", k=3)
    assert hits
    assert any("Friday" in h["content"] for h in hits)
    assert hits[0]["source"] == "notes.md"
    store.close()


@pytest.mark.asyncio
async def test_ingest_dedupes_by_hash(tmp_path):
    store = Store(tmp_path / "m.db")
    embedder = Embedder(ScriptedProvider([]))
    await ingest_text(store, embedder, "same content here", "a")
    await ingest_text(store, embedder, "same content here", "b")  # identical → skipped
    assert len(store.list_documents()) == 1
    store.close()


@pytest.mark.asyncio
async def test_delete_document(tmp_path):
    store = Store(tmp_path / "m.db")
    embedder = Embedder(ScriptedProvider([]))
    await ingest_text(store, embedder, "delete me please", "x")
    doc_id = store.list_documents()[0]["id"]
    store.delete_document(doc_id)
    assert store.list_documents() == []
    assert await hybrid_search(store, embedder, "delete me", k=3) == []
    store.close()
