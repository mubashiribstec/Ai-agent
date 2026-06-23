"""Vision tool — let the agent actually *see* an image.

The agent captures the screen (``screenshot``) or a page (``browser``) as a PNG
path, then calls ``analyze_image`` to have a vision-capable model describe it or
answer a question about it. This closes the see→decide→act loop for GUI/browser
automation. The image is sent only on this one-off request, never threaded into
the normalized message history (which also flows to non-vision providers).
"""

from __future__ import annotations

from pathlib import Path

from xplogent.providers.base import Message, Role
from xplogent.safety.approval import RiskLevel
from xplogent.tools.base import Tool, ToolResult


class AnalyzeImageTool(Tool):
    name = "analyze_image"
    description = (
        "Look at an image file (e.g. a screenshot) with a vision-capable model and "
        "answer a question about it. Use after 'screenshot' to read the screen, find "
        "UI elements, or extract text before clicking/typing."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the image file (PNG/JPG)."},
            "question": {"type": "string",
                         "description": "What to ask about the image."},
        },
        "required": ["path"],
    }
    risk = RiskLevel.LOW

    async def run(self, path: str, question: str = "Describe this image in detail.") -> ToolResult:
        img = Path(path).expanduser()
        if not img.exists():
            return ToolResult.failure(f"No such image: {img}")
        # Resolve the vision model lazily so the tool stays zero-arg in the registry.
        from xplogent.core.config import load_config
        from xplogent.providers.registry import build_provider

        cfg = load_config()
        model = (getattr(cfg, "vision_model", "") or "").strip() or cfg.model
        provider = build_provider(model)
        try:
            msg = Message(role=Role.USER, content=question, images=[str(img)])
            reply = await provider.complete([msg])
        except Exception as exc:  # noqa: BLE001
            return ToolResult.failure(
                f"Vision request failed (is '{model}' vision-capable?): {exc}"
            )
        finally:
            await provider.aclose()
        text = (reply.content or "").strip()
        return ToolResult.success(text or "(the model returned no description)")


def vision_tools() -> list[Tool]:
    return [AnalyzeImageTool()]
