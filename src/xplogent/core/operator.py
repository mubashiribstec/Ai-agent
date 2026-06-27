"""Computer-use operator.

A preset agent that drives the screen directly in a bounded
**screenshot → analyze → act → observe** loop. It reuses the normal agent loop
(so safety/approval gating, step budget, pause/cancel, and event streaming all
apply) but scopes the toolset to vision + GUI (+ browser) tools and swaps in a
computer-use system prompt. Every mouse/keyboard action is already HIGH risk, so
each is approval-gated by the existing safety layer.
"""

from __future__ import annotations

from xplogent.core.agent import ApproveCallback
from xplogent.core.config import load_config
from xplogent.core.events import EventBus
from xplogent.runtime import Runtime, build_runtime

OPERATOR_PROMPT = """You are Xplogent in COMPUTER-USE mode, operating the user's screen directly.

Work in a careful loop, taking ONE action at a time:
1. Call `screenshot` to capture the current screen.
2. Call `analyze_image` on that screenshot to read what's visible and locate your target.
3. Decide the single next action and perform it with `mouse` (move/click at x,y) or
   `keyboard` (type text or press a hotkey).
4. Screenshot + analyze again to confirm the result before continuing.

Rules:
- Be deliberate. Every mouse/keyboard action may require the user's approval.
- Prefer reliable keyboard shortcuts over precise clicks when possible.
- If the goal is ambiguous or you get stuck, STOP and explain rather than guessing.
- When the goal is achieved, STOP and give a short summary WITHOUT calling more tools."""

OPERATOR_TOOLS = {"screenshot", "mouse", "keyboard", "analyze_image"}


def build_operator(*, bus: EventBus | None = None, approve: ApproveCallback | None = None,
                   max_steps: int = 30, include_browser: bool = True) -> Runtime:
    """Build a runtime scoped for computer use (vision + GUI [+ browser] tools)."""
    cfg = load_config(overrides={"agent": {"system_prompt": OPERATOR_PROMPT,
                                           "max_steps": max_steps}})
    # Prefer a vision-capable model for the driving loop when one is configured.
    model = cfg.vision_model or cfg.model
    rt = build_runtime(cfg, bus=bus, approve=approve, with_memory=False, model=model)

    allowed = set(OPERATOR_TOOLS)
    if include_browser:
        allowed |= {t.name for t in rt.agent.tools.all() if t.name.startswith("browser")}
    rt.agent.tools = rt.agent.tools.filtered(allowed)
    rt.agent.name = "operator"
    return rt


async def run_operator(goal: str, *, bus: EventBus | None = None,
                       approve: ApproveCallback | None = None, max_steps: int = 30) -> str:
    """Run the operator loop on a goal and return its final summary."""
    rt = build_operator(bus=bus, approve=approve, max_steps=max_steps)
    try:
        return await rt.agent.run(goal)
    finally:
        await rt.aclose()
