"""A shared task board (kanban) for multi-agent runs.

Subtasks have dependencies; a task is *ready* once all its dependencies are
done. The orchestrator schedules ready tasks onto workers and records results
back here. Every change emits ``TASK_UPDATE`` for live monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from xplogent.core.events import Event, EventBus, EventType


class TaskStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Task:
    id: str
    title: str
    description: str
    role: str = "operator"
    deps: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assignee: str | None = None
    result: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "description": self.description,
            "role": self.role, "deps": self.deps, "status": self.status.value,
            "assignee": self.assignee, "result": self.result,
        }


class TaskBoard:
    def __init__(self, bus: EventBus, run_id: str | None = None) -> None:
        self.bus = bus
        self.run_id = run_id
        self.tasks: dict[str, Task] = {}

    def add(self, task: Task) -> None:
        self.tasks[task.id] = task

    async def _emit(self, task: Task) -> None:
        await self.bus.publish(Event(
            type=EventType.TASK_UPDATE,
            data={"run_id": self.run_id, **task.to_dict()},
        ))

    def ready_tasks(self) -> list[Task]:
        """Pending tasks whose dependencies are all done."""
        out = []
        for t in self.tasks.values():
            if t.status != TaskStatus.PENDING:
                continue
            if all(self.tasks.get(d) and self.tasks[d].status == TaskStatus.DONE for d in t.deps):
                out.append(t)
        return out

    def dependency_results(self, task: Task) -> dict[str, str]:
        return {self.tasks[d].title: self.tasks[d].result
                for d in task.deps if d in self.tasks and self.tasks[d].result}

    async def claim(self, task_id: str, assignee: str) -> None:
        t = self.tasks[task_id]
        t.status = TaskStatus.ACTIVE
        t.assignee = assignee
        await self._emit(t)

    async def complete(self, task_id: str, result: str) -> None:
        t = self.tasks[task_id]
        t.status = TaskStatus.DONE
        t.result = result
        await self._emit(t)

    async def fail(self, task_id: str, error: str) -> None:
        t = self.tasks[task_id]
        t.status = TaskStatus.FAILED
        t.result = error
        await self._emit(t)

    def all_settled(self) -> bool:
        return all(t.status in (TaskStatus.DONE, TaskStatus.FAILED) for t in self.tasks.values())

    def snapshot(self) -> list[dict]:
        return [t.to_dict() for t in self.tasks.values()]
