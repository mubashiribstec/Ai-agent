"""Runtime factory.

One place that assembles a fully-wired :class:`Agent` from a :class:`Config`:
provider, tool registry, safety gate, memory (store + embedder), and the
self-improvement pieces (reflector + skill manager). Every interface (CLI, API,
voice) builds its agent through here so behavior stays consistent.
"""

from __future__ import annotations

from dataclasses import dataclass

from nexus.core.agent import Agent, ApproveCallback
from nexus.core.config import Config, load_config
from nexus.core.events import EventBus
from nexus.memory.manager import MemoryManager
from nexus.memory.store import Store
from nexus.memory.vector import Embedder
from nexus.plugins.loader import load_plugins
from nexus.providers.registry import build_provider
from nexus.safety.approval import SafetyManager
from nexus.skills.manager import SkillManager
from nexus.skills.reflection import Reflector
from nexus.tools.registry import ToolRegistry


@dataclass
class Runtime:
    config: Config
    agent: Agent
    store: Store | None
    bus: EventBus

    async def aclose(self) -> None:
        await self.agent.provider.aclose()
        if self.agent.memory:
            await self.agent.memory.embedder.provider.aclose()
        if self.agent.reflector:
            await self.agent.reflector.provider.aclose()
        if self.store:
            self.store.close()


def build_runtime(
    config: Config | None = None,
    *,
    bus: EventBus | None = None,
    approve: ApproveCallback | None = None,
    with_memory: bool = True,
) -> Runtime:
    config = config or load_config()
    bus = bus or EventBus()

    provider = build_provider(config.model)
    tools = ToolRegistry.from_config(config.tools.get("enabled"))
    load_plugins(tools)  # drop-in plugins extend the same registry
    safety = SafetyManager.from_config(config.safety)

    memory: MemoryManager | None = None
    reflector: Reflector | None = None
    skills: SkillManager | None = None
    store: Store | None = None

    if with_memory and config.memory.get("enabled", True):
        store = Store(config.db_path)
        session_id = store.create_session(title="session")
        embed_provider = build_provider(config.embedding_model)
        embedder = Embedder(embed_provider)
        memory = MemoryManager(store, embedder, session_id=session_id)

        if config.skills.get("enabled", True):
            reflector = Reflector(build_provider(config.reflection_model))
            skills = SkillManager(memory, config.skills_dir)

    agent = Agent(
        config, provider, tools, safety,
        memory=memory, reflector=reflector, skills=skills, bus=bus, approve=approve,
    )
    return Runtime(config=config, agent=agent, store=store, bus=bus)
