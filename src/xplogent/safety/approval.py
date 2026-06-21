"""Risk classification + approval policy.

Every tool call is routed through :class:`SafetyManager` before it runs. The
tool declares a base risk; the manager may escalate it (e.g. a shell command
matching a deny pattern becomes ``critical``) and then applies the configured
policy: ``auto`` (run), ``confirm`` (ask the user), or ``deny`` (block).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}


def max_risk(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    return a if _ORDER[a] >= _ORDER[b] else b


@dataclass
class ApprovalRequest:
    tool: str
    arguments: dict[str, Any]
    risk: RiskLevel
    reason: str = ""


@dataclass
class ApprovalDecision:
    allowed: bool
    risk: RiskLevel
    reason: str = ""
    needed_confirmation: bool = False


# An interface supplies this; returns True to allow a "confirm"-tier action.
ApprovalCallback = Callable[[ApprovalRequest], Awaitable[bool]]


_DEFAULT_DENY = [
    r"rm\s+-rf\s+/",
    r"mkfs",
    r":\(\)\s*\{.*\};:",
    r"dd\s+if=.*of=/dev/",
]


@dataclass
class SafetyManager:
    policy: dict[str, str] = field(
        default_factory=lambda: {
            "low": "auto",
            "medium": "confirm",
            "high": "confirm",
            "critical": "deny",
        }
    )
    deny_patterns: list[str] = field(default_factory=lambda: list(_DEFAULT_DENY))
    allowed_write_roots: list[str] = field(default_factory=list)

    @classmethod
    def from_config(cls, safety_cfg: dict[str, Any]) -> SafetyManager:
        return cls(
            policy=safety_cfg.get("policy") or cls().policy,
            deny_patterns=safety_cfg.get("deny_patterns") or list(_DEFAULT_DENY),
            allowed_write_roots=safety_cfg.get("allowed_write_roots") or [],
        )

    def _matches_deny(self, arguments: dict[str, Any]) -> bool:
        blob = " ".join(str(v) for v in arguments.values())
        return any(re.search(p, blob, re.IGNORECASE) for p in self.deny_patterns)

    def classify(self, tool: Any, arguments: dict[str, Any]) -> tuple[RiskLevel, str]:
        """Determine the effective risk of a tool call."""
        base = tool.risk_for(arguments) if hasattr(tool, "risk_for") else RiskLevel.MEDIUM
        reason = ""
        if self._matches_deny(arguments):
            return RiskLevel.CRITICAL, "matches a configured deny pattern"
        return base, reason

    async def evaluate(
        self,
        tool: Any,
        arguments: dict[str, Any],
        approve: ApprovalCallback | None = None,
    ) -> ApprovalDecision:
        risk, reason = self.classify(tool, arguments)
        action = self.policy.get(risk.value, "confirm")

        if action == "deny":
            return ApprovalDecision(False, risk, reason or "blocked by policy")
        if action == "auto":
            return ApprovalDecision(True, risk, reason)

        # action == "confirm"
        if approve is None:
            # No interactive approver available → fail safe by blocking.
            return ApprovalDecision(False, risk, "confirmation required but no approver")
        ok = await approve(ApprovalRequest(tool=getattr(tool, "name", str(tool)),
                                           arguments=arguments, risk=risk, reason=reason))
        return ApprovalDecision(ok, risk, reason, needed_confirmation=True)
