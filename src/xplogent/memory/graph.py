"""Knowledge-graph memory.

The reflector extracts ``(subject, relation, object)`` triples from finished
tasks; they're stored as nodes + edges so the agent accumulates a structured map
of the user's world (people, projects, preferences, systems). On a new task we
surface the neighbourhood of any known entity mentioned in the prompt, giving the
model relational context that flat facts can't express.
"""

from __future__ import annotations

import re

from xplogent.memory.store import Store

_WORD = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]+")


def ingest_relations(store: Store, relations: list[tuple[str, str, str]], source: str = "") -> int:
    """Upsert a batch of triples. Returns how many were stored."""
    n = 0
    for subj, rel, obj in relations:
        subj, rel, obj = subj.strip(), rel.strip(), obj.strip()
        if subj and rel and obj:
            store.add_edge(subj, rel, obj, source=source)
            n += 1
    return n


def context_block(store: Store, query: str, max_entities: int = 4) -> str:
    """A compact 'known entities/relations' block for entities named in ``query``.

    Returns an empty string when nothing relevant is known, so callers can append
    it unconditionally.
    """
    names = store.kg_node_names()
    if not names:
        return ""
    lowered = query.lower()
    # Match known entities mentioned in the prompt (case-insensitive, whole-ish).
    hit = [n for n in names if n.lower() in lowered]
    if not hit:
        # Fall back to token overlap so multi-word entities still match.
        tokens = {t.lower() for t in _WORD.findall(query)}
        hit = [n for n in names if any(t in tokens for t in n.lower().split())]
    if not hit:
        return ""

    lines: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for entity in hit[:max_entities]:
        for e in store.neighbors(entity):
            key = (e["subject"], e["relation"], e["object"])
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- {e['subject']} {e['relation']} {e['object']}")
    if not lines:
        return ""
    return "## Knowledge graph (relevant relations)\n" + "\n".join(lines[:20])
