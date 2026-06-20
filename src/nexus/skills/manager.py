"""Skill persistence.

Skills are stored two ways: as markdown files under ``$NEXUS_HOME/skills`` (human
readable / editable) and in the memory store with an embedding (for semantic
retrieval). Facts go to long-term memory. Together with the reflector this closes
the self-improvement loop: act → reflect → consolidate → reuse.
"""

from __future__ import annotations

from pathlib import Path

from nexus.memory.manager import MemoryManager
from nexus.skills.reflection import ReflectionResult


class SkillManager:
    def __init__(self, memory: MemoryManager, skills_dir: Path) -> None:
        self.memory = memory
        self.skills_dir = skills_dir
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    async def apply(self, result: ReflectionResult) -> dict[str, int | str | None]:
        """Persist a reflection result. Returns a small summary for events."""
        for fact in result.facts:
            await self.memory.remember(fact, source="reflection")

        skill_name: str | None = None
        if result.skill:
            await self.memory.save_skill(
                result.skill.name, result.skill.description, result.skill.body
            )
            self._write_markdown(result.skill.name, result.skill.description, result.skill.body)
            skill_name = result.skill.name

        return {"facts": len(result.facts), "skill": skill_name}

    def _write_markdown(self, name: str, description: str, body: str) -> None:
        path = self.skills_dir / f"{name}.md"
        path.write_text(
            f"# {name}\n\n> {description}\n\n{body}\n", encoding="utf-8"
        )
