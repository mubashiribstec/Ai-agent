"""search_docs — let the agent answer from the user's ingested documents (RAG)."""

from __future__ import annotations

from xplogent.safety.approval import RiskLevel
from xplogent.tools.base import Tool, ToolResult


class SearchDocsTool(Tool):
    name = "search_docs"
    description = (
        "Search the user's ingested documents/knowledge base and return the most "
        "relevant passages with their source. Use this to answer questions about the "
        "user's own files, notes, or codebase, and cite the sources you used."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look for."},
            "k": {"type": "integer", "description": "How many passages (default 5)."},
        },
        "required": ["query"],
    }
    risk = RiskLevel.LOW

    async def run(self, query: str, k: int = 5) -> ToolResult:
        from xplogent.core.config import load_config
        from xplogent.core.rag import hybrid_search
        from xplogent.memory.store import Store
        from xplogent.memory.vector import Embedder
        from xplogent.providers.registry import build_provider

        cfg = load_config()
        store = Store(cfg.db_path)
        provider = build_provider(cfg.embedding_model)
        try:
            hits = await hybrid_search(store, Embedder(provider), query, k=int(k or 5))
        finally:
            await provider.aclose()
            store.close()
        if not hits:
            return ToolResult.success("(no matching documents — ingest some first)")
        blocks = [f"[{h['source']}]\n{h['content'][:1200]}" for h in hits]
        return ToolResult.success("\n\n---\n\n".join(blocks))


def documents_tools() -> list[Tool]:
    return [SearchDocsTool()]
