"""The Xplogent agent loop.

Ties together providers, tools, safety, memory, and self-improvement into a
single streaming ReAct loop: think → (maybe) call tools → observe → repeat,
until the model returns a final answer. Emits events on an :class:`EventBus` so
any interface can render the run live.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable

from xplogent.core.config import Config
from xplogent.core.context import ShortTermMemory, build_system_prompt
from xplogent.core.events import Event, EventBus, EventType
from xplogent.core.logging import get_logger
from xplogent.core.retry import RETRYABLE, RetryPolicy, classify_error
from xplogent.memory.manager import MemoryManager
from xplogent.providers.base import Message, Provider, Role, StreamKind
from xplogent.safety.approval import ApprovalRequest, SafetyManager
from xplogent.skills.manager import SkillManager
from xplogent.skills.reflection import Reflector
from xplogent.tools.registry import ToolRegistry

ApproveCallback = Callable[[ApprovalRequest], Awaitable[bool]]
_log = get_logger("agent")


class CancelledByUser(Exception):
    """Raised internally when an agent is cancelled mid-run."""


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
        gen_params: dict | None = None,
        agent_id: str | None = None,
        name: str = "agent",
        role: str = "operator",
        run_id: str | None = None,
        max_steps: int | None = None,
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
        # identity (used to tag every event for deep monitoring)
        self.agent_id = agent_id or uuid.uuid4().hex[:8]
        self.name = name
        self.role = role
        self.run_id = run_id
        self.stm = ShortTermMemory(
            max_tokens=int(config.memory.get("short_term_max_tokens", 6000))
        )
        self._max_steps = int(max_steps or config.agent.get("max_steps", 25))
        self._temperature = float(config.agent.get("temperature", 0.7))
        # generation params: temperature / effort / thinking / max_tokens
        self.gen_params: dict = gen_params or {}
        # live control
        self._pause = asyncio.Event()
        self._pause.set()  # set == not paused
        self._cancelled = False
        self.status = "idle"
        self.current_tool: str | None = None
        self.steps_taken = 0

    def load_history(self, limit: int = 40) -> None:
        """Seed short-term memory from the persisted session so chat continues."""
        if not self.memory or self.memory.session_id is None:
            return
        rows = self.memory.store.session_messages(self.memory.session_id)
        for row in rows[-limit:]:
            role = Role.USER if row["role"] == "user" else Role.ASSISTANT
            self.stm.add(Message(role=role, content=row["content"]))

    async def _emit(self, type_: EventType, **data) -> None:
        # tag every event with this agent's identity + run for the monitor
        data.setdefault("agent_id", self.agent_id)
        data.setdefault("agent_name", self.name)
        data.setdefault("role", self.role)
        if self.run_id:
            data.setdefault("run_id", self.run_id)
        await self.bus.publish(Event(type=type_, data=data))

    # -- live control ----------------------------------------------------------
    def pause(self) -> None:
        self._pause.clear()

    def resume(self) -> None:
        self._pause.set()

    def cancel(self) -> None:
        self._cancelled = True
        self._pause.set()  # unblock if paused so the loop can exit

    async def _set_status(self, status: str) -> None:
        self.status = status
        await self._emit(EventType.AGENT_STATUS, status=status,
                         step=self.steps_taken, current_tool=self.current_tool)

    async def _checkpoint(self) -> None:
        """Honor pause/cancel between steps."""
        if self._cancelled:
            raise CancelledByUser
        if not self._pause.is_set():
            await self._set_status("paused")
            await self._pause.wait()
            await self._set_status("running")

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
        await self._set_status("running")
        self.stm.add(Message(role=Role.USER, content=task))
        if self.memory:
            self.memory.log("user", task)
        transcript: list[str] = [f"USER: {task}"]
        tool_steps = 0
        final_answer = ""

        try:
            for step in range(self._max_steps):
                await self._checkpoint()
                self.steps_taken = step + 1
                await self._emit(EventType.STEP_START, step=step)
                messages = await self._build_messages(task)
                tool_specs = self.tools.specs()

                assistant = await self._stream_assistant(messages, tool_specs)
                if assistant is None:  # provider failed; error already emitted
                    final_answer = "(failed: the model provider returned an error)"
                    break

                self.stm.add(assistant)
                if assistant.content:
                    transcript.append(f"ASSISTANT: {assistant.content}")
                    await self._emit(EventType.MESSAGE, content=assistant.content)

                if not assistant.tool_calls:
                    final_answer = assistant.content
                    break

                # Execute each requested tool through the safety gate.
                for call in assistant.tool_calls:
                    tool_steps += 1
                    result_text = await self._run_tool(call.name, call.arguments)
                    transcript.append(
                        f"TOOL[{call.name}]({_short(call.arguments)}) -> {_short(result_text)}"
                    )
                    self.stm.add(
                        Message(role=Role.TOOL, content=result_text,
                                tool_call_id=call.id, name=call.name)
                    )
                self.stm.trim()
            else:
                final_answer = "(stopped: reached the maximum number of steps)"
        except CancelledByUser:
            final_answer = "(cancelled by user)"
            await self._set_status("cancelled")
            await self._emit(EventType.RUN_END, answer=final_answer, cancelled=True)
            return final_answer

        if self.memory:
            self.memory.log("assistant", final_answer)
        await self._set_status("done")
        await self._emit(EventType.RUN_END, answer=final_answer)
        await self._post_task(task, "\n".join(transcript), tool_steps)
        return final_answer

    async def _stream_assistant(self, messages, tool_specs) -> Message | None:
        """Stream one assistant turn, retrying transient provider failures.

        A retry only happens if the error arrives *before* any token was streamed,
        so the user never sees duplicated output.
        """
        params = {"temperature": self._temperature, **self.gen_params}
        policy = RetryPolicy.from_attempts(int(self.config.agent.get("provider_retries", 2)))
        for attempt in range(1, policy.max_attempts + 1):
            assistant: Message | None = None
            emitted = False
            try:
                async for ev in self.provider.stream(messages, tool_specs, **params):
                    if ev.kind == StreamKind.TOKEN:
                        emitted = True
                        await self._emit(EventType.TOKEN, text=ev.text)
                    elif ev.kind == StreamKind.DONE:
                        assistant = ev.message
                return assistant or Message(role=Role.ASSISTANT, content="")
            except Exception as exc:  # noqa: BLE001 - one agent's failure must not crash others
                kind = classify_error(exc)
                if emitted or kind not in RETRYABLE or attempt >= policy.max_attempts:
                    _log.warning("provider error for agent %s: %s", self.name, exc)
                    await self._emit(EventType.ERROR, message=f"provider error: {exc}")
                    return None
                _log.warning("provider %s for agent %s; retry %d", kind, self.name, attempt)
                await asyncio.sleep(policy.delay_for(attempt))
        return None

    async def _run_tool(self, name: str, arguments: dict) -> str:
        tool = self.tools.get(name)
        if tool is None:
            return f"ERROR: unknown tool '{name}'"
        self.current_tool = name
        await self._emit(EventType.TOOL_CALL, tool=name, arguments=arguments)

        decision = await self.safety.evaluate(tool, arguments, self.approve)
        if decision.needed_confirmation:
            await self._emit(EventType.APPROVAL_RESOLVED, tool=name, allowed=decision.allowed)
        if not decision.allowed:
            text = f"BLOCKED by safety policy ({decision.risk.value}): {decision.reason}"
            await self._emit(EventType.TOOL_RESULT, tool=name, ok=False, output=text)
            self.current_tool = None
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
        finally:
            self.current_tool = None

    async def _post_task(self, task: str, transcript: str, tool_steps: int) -> None:
        """Self-improvement: reflect, then consolidate memory and skills."""
        if not (self.reflector and self.skills and self.config.skills.get("reflect_after_tasks", True)):
            return
        if tool_steps < int(self.config.skills.get("reflect_min_steps", 0)):
            return  # optional gate; default 0 reflects after every task (incl. chat)
        result = await self.reflector.reflect(task, transcript)
        summary = await self.skills.apply(result)
        if summary.get("facts") or summary.get("skill"):
            await self._emit(EventType.SKILL, **summary)


def _short(value, limit: int = 300) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + "…"
