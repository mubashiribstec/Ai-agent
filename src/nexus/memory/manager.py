"""Three-tier memory manager.

* **short-term** — the rolling conversation (managed by the agent loop / context).
* **long-term** — durable facts & preferences, recalled semantically.
* **episodic** — searchable history of past sessions and messages.

Also stores and retrieves **skills** (used by the self-improvement subsystem).
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus.memory.store import SkillRow, Store
from nexus.memory.vector import Embedder, top_k


@dataclass
class RetrievedSkill:
    name: str
    description: str
    body: str
    score: float


class MemoryManager:
    def __init__(self, store: Store, embedder: Embedder, session_id: int | None = None) -> None:
        self.store = store
        self.embedder = embedder
        self.session_id = session_id

    # -- episodic logging ------------------------------------------------------
    def log(self, role: str, content: str) -> None:
        """Record a message in the current session (episodic memory)."""
        if self.session_id is not None and content:
            self.store.add_message(self.session_id, role, content)

    # -- long-term facts -------------------------------------------------------
    async def remember(self, content: str, source: str = "") -> int:
        vec = await self.embedder.embed_one(content)
        return self.store.add_fact(content, vec, source)

    async def recall(self, query: str, k: int = 5) -> list[str]:
        facts = self.store.all_facts()
        if not facts:
            return []
        qvec = await self.embedder.embed_one(query)
        if qvec:
            ranked = top_k(qvec, [(f, f.embedding) for f in facts], k)
            return [f.content for f, score in ranked if score > 0.2]  # type: ignore[attr-defined]
        # keyword fallback
        q = query.lower()
        return [f.content for f in facts if q in f.content.lower()][:k]

    # -- episodic --------------------------------------------------------------
    def search_history(self, query: str, limit: int = 10) -> list[dict]:
        return self.store.search_messages(query, limit)

    # -- skills ----------------------------------------------------------------
    async def save_skill(self, name: str, description: str, body: str) -> None:
        vec = await self.embedder.embed_one(f"{name}: {description}")
        self.store.upsert_skill(name, description, body, vec)

    async def relevant_skills(self, query: str, k: int = 3) -> list[RetrievedSkill]:
        skills: list[SkillRow] = self.store.all_skills()
        if not skills:
            return []
        qvec = await self.embedder.embed_one(query)
        if qvec:
            ranked = top_k(qvec, [(s, s.embedding) for s in skills], k)
            picked = [(s, score) for s, score in ranked if score > 0.25]
        else:
            q = query.lower()
            picked = [(s, 1.0) for s in skills if q in (s.name + s.description).lower()][:k]
        out = []
        for s, score in picked:
            self.store.increment_skill_use(s.name)  # type: ignore[attr-defined]
            out.append(RetrievedSkill(s.name, s.description, s.body, score))  # type: ignore[attr-defined]
        return out

    def list_skills(self) -> list[SkillRow]:
        return self.store.all_skills()
