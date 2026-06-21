"""The Xplogent agent loop.

Ties together providers, tools, safety, memory, and self-improvement into a
single streaming ReAct loop: think → (maybe) call tools → observe → repeat,
until the model returns a final answer. Emits events on an :class:`EventBus` so
any interface can render the run live.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from xplogent.core.config import Config
from xplogent.core.context import ShortTermMemory, build_system_prompt
from xplogent.core.events import Event, EventBus, EventType
from xplogent.memory.manager import MemoryManager
from xplogent.providers.base import Message, Provider, Role, StreamKind
from xplogent.safety.approval import ApprovalRequest, SafetyManager
from xplogent.skills.manager import SkillManager
from xplogent.skills.reflection import Reflector
from xplogent.tools.registry import ToolRegistry

ApproveCallback = Callable[[ApprovalRequest], Awaitable[bool]]


class Agent:
    def __init__(
        self,
        config: Config,
        provider: Provider,
        tools: ToolRegistry,
        safety: SafetyManager,
        *,
        memory: MemoryManager | None = None,
        reflector: Reflector | None = None,
        skills: SkillManager | None = None,
        bus: EventBus | None = None,
        approve: ApproveCallback | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.tools = tools
        self.safety = safety
        self.memory = memory
        self.reflector = reflector
        self.skills = skills
        self.bus = bus or EventBus()
        self.approve = approve
        self.stm = ShortTermMemory(
            max_tokens=int(config.memory.get("short_term_max_tokens", 6000))
        )
        self._max_steps = int(config.agent.get("max_steps", 25))
        self._temperature = float(config.agent.get("temperature", 0.7))

    async def _emit(self, type_: EventType, **data) -> None:
        await self.bus.publish(Event(type=type_, data=data))

    async def _build_messages(self, task: str) -> list[Message]:
        facts: list[str] = []
        skills: list[tuple[str, str, str]] = []
        if self.memory:
            facts = await self.memory.recall(task, k=int(self.config.memory.get("retrieval_top_k", 5)))
            relevant = await self.memory.relevant_skills(task, k=3)
            skills = [(s.name, s.description, s.body) for s in relevant]
            if facts or skills:
                await self._emit(EventType.MEMORY, facts=len(facts), skills=len(skills))
        system = build_system_prompt(self.config.agent.get("system_prompt"), facts, skills)
        return [Message(role=Role.SYSTEM, content=system), *self.stm.render()]

    async def run(self, task: str) -> str:
        """Run one task to completion and return the final answer."""
        await self._emit(EventType.RUN_START, task=task)
        self.stm.add(Message(role=Role.USER, content=task))
        if self.memory:
            self.memory.log("user", task)
        transcript: list[str] = [f"USER: {task}"]
        final_answer = ""

        for step in range(self._max_steps):
            await self._emit(EventType.STEP_START, step=step)
            messages = await self._build_messages(task)
            tool_specs = self.tools.specs()

            assistant: Message | None = None
            async for ev in self.provider.stream(
                messages, tool_specs, temperature=self._temperature
            ):
                if ev.kind == StreamKind.TOKEN:
                    await self._emit(EventType.TOKEN, text=ev.text)
                elif ev.kind == StreamKind.DONE:
                    assistant = ev.message

            assistant = assistant or Message(role=Role.ASSISTANT, content="")
            self.stm.add(assistant)
            if assistant.content:
                transcript.append(f"ASSISTANT: {assistant.content}")
                await self._emit(EventType.MESSAGE, content=assistant.content)

            if not assistant.tool_calls:
                final_answer = assistant.content
                break

            # Execute each requested tool through the safety gate.
            for call in assistant.tool_calls:
                result_text = await self._run_tool(call.name, call.arguments)
                transcript.append(f"TOOL[{call.name}]({_short(call.arguments)}) -> {_short(result_text)}")
                self.stm.add(
                    Message(role=Role.TOOL, content=result_text,
                            tool_call_id=call.id, name=call.name)
                )
            self.stm.trim()
        else:
            final_answer = "(stopped: reached the maximum number of steps)"

        if self.memory:
            self.memory.log("assistant", final_answer)
        await self._emit(EventType.RUN_END, answer=final_answer)
        await self._post_task(task, "\n".join(transcript))
        return final_answer

    async def _run_tool(self, name: str, arguments: dict) -> str:
        tool = self.tools.get(name)
        if tool is None:
            return f"ERROR: unknown tool '{name}'"
        await self._emit(EventType.TOOL_CALL, tool=name, arguments=arguments)

        decision = await self.safety.evaluate(tool, arguments, self.approve)
        if decision.needed_confirmation:
            await self._emit(EventType.APPROVAL_RESOLVED, tool=name, allowed=decision.allowed)
        if not decision.allowed:
            text = f"BLOCKED by safety policy ({decision.risk.value}): {decision.reason}"
            await self._emit(EventType.TOOL_RESULT, tool=name, ok=False, output=text)
            return text

        try:
            result = await tool.run(**arguments)
            text = result.as_text()
            await self._emit(EventType.TOOL_RESULT, tool=name, ok=result.ok, output=text)
            return text
        except TypeError as exc:
            return f"ERROR: bad arguments for {name}: {exc}"
        except Exception as exc:  # noqa: BLE001
            await self._emit(EventType.TOOL_RESULT, tool=name, ok=False, output=str(exc))
            return f"ERROR running {name}: {exc}"

    async def _post_task(self, task: str, transcript: str) -> None:
        """Self-improvement: reflect, then consolidate memory and skills."""
        if not (self.reflector and self.skills and self.config.skills.get("reflect_after_tasks", True)):
            return
        result = await self.reflector.reflect(task, transcript)
        summary = await self.skills.apply(result)
        if summary.get("facts") or summary.get("skill"):
            await self._emit(EventType.SKILL, **summary)


def _short(value, limit: int = 300) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + "…"
