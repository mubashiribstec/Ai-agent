"""Tool base classes.

A :class:`Tool` exposes a JSON-schema signature to the model for function
calling, declares a base risk level for the safety layer, and runs
asynchronously returning a uniform :class:`ToolResult`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from xplogent.providers.base import ToolSpec
from xplogent.safety.approval import RiskLevel


@dataclass
class ToolResult:
    ok: bool
    output: str = ""
    error: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        """Render the result for feeding back to the model."""
        if self.ok:
            return self.output or "(no output)"
        return f"ERROR: {self.error}"

    @classmethod
    def success(cls, output: str = "", **data: Any) -> ToolResult:
        return cls(ok=True, output=output, data=data)

    @classmethod
    def failure(cls, error: str, **data: Any) -> ToolResult:
        return cls(ok=False, error=error, data=data)


class Tool(ABC):
    name: str = "tool"
    description: str = ""
    parameters: dict[str, Any] = {"type": "object", "properties": {}}
    risk: RiskLevel = RiskLevel.MEDIUM

    def risk_for(self, arguments: dict[str, Any]) -> RiskLevel:
        """Override to vary risk by argument (e.g. read vs write)."""
        return self.risk

    def spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, parameters=self.parameters)

    @abstractmethod
    async def run(self, **kwargs: Any) -> ToolResult:
        raise NotImplementedError


def optional_import_error(package: str, extra: str) -> ToolResult:
    """Standard message when an optional dependency is missing."""
    return ToolResult.failure(
        f"This action needs the '{package}' package. Install it with: "
        f"pip install 'xplogent[{extra}]'"
    )
