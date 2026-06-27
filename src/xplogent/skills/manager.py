"""Skill persistence.

Skills are stored two ways: as markdown files under ``$XPLOGENT_HOME/skills`` (human
readable / editable) and in the memory store with an embedding (for semantic
retrieval). Facts go to long-term memory. Together with the reflector this closes
the self-improvement loop: act → reflect → consolidate → reuse.
"""

from __future__ import annotations

from pathlib import Path

from xplogent.memory.manager import MemoryManager
from xplogent.skills.reflection import ReflectionResult


class SkillManager:
    def __init__(self, memory: MemoryManager, skills_dir: Path) -> None:
        self.memory = memory
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    async def apply(self, result: ReflectionResult) -> dict[str, int | str | None]:
        """Persist a reflection result. Returns a small summary for events."""
        for fact in result.facts:
            await self.memory.remember(fact, source="reflection")

        relations = 0
        if result.relations:
            from xplogent.memory.graph import ingest_relations

            relations = ingest_relations(self.memory.store, result.relations, source="reflection")

        skill_name: str | None = None
        if result.skill:
            await self.memory.save_skill(
                result.skill.name, result.skill.description, result.skill.body
            )
            self._write_markdown(result.skill.name, result.skill.description, result.skill.body)
            skill_name = result.skill.name

        return {"facts": len(result.facts), "relations": relations, "skill": skill_name}

    def _write_markdown(self, name: str, description: str, body: str) -> None:
        from xplogent.skills.pack import render_skill_md

        path = self.skills_dir / f"{name}.md"
        path.write_text(render_skill_md(name, description, body), encoding="utf-8")
