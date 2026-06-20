"""Embeddings + cosine similarity for semantic recall.

The embedder wraps any provider that implements ``embed`` (Ollama's
``nomic-embed-text`` by default, fully local). If embeddings are unavailable
(e.g. the model isn't pulled), callers fall back to keyword search.
"""

from __future__ import annotations

import math

from nexus.providers.base import Provider


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def top_k(query_vec: list[float], items: list[tuple[object, list[float]]],
          k: int = 5) -> list[tuple[object, float]]:
    """Rank ``(item, embedding)`` pairs by cosine similarity to ``query_vec``."""
    scored = [(item, cosine(query_vec, emb)) for item, emb in items if emb]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:k]


class Embedder:
    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        self.available = True

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.available:
            return [[] for _ in texts]
        try:
            return await self.provider.embed(texts)
        except Exception:  # noqa: BLE001 - embeddings are best-effort
            self.available = False
            return [[] for _ in texts]

    async def embed_one(self, text: str) -> list[float]:
        out = await self.embed([text])
        return out[0] if out else []
