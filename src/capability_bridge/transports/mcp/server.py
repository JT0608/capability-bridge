from __future__ import annotations

import sys

from fastmcp import FastMCP

from capability_bridge.bootstrap import build_from_path
from capability_bridge.core.capabilities.vision import VisionCapability
from capability_bridge.core.registry.config import resolve_config_path


def create_server(capability: VisionCapability) -> FastMCP:
    mcp = FastMCP("capability-bridge")

    @mcp.tool()
    async def vision_analyze(image: str, prompt: str | None = None, task: str = "general") -> dict:
        """Analyze an image with a vision model and return a text description.

        Args:
            image: local path, file:// URI, or base64 data URI (no remote URLs in v0.1).
            prompt: optional question to focus the analysis.
            task: v0.1 only supports "general".
        """
        result = await capability.analyze(image, prompt=prompt, task=task)
        return result.model_dump()

    @mcp.tool()
    async def vision_ocr(image: str) -> dict:
        """Extract text (OCR) from an image.

        Args:
            image: local path, file:// URI, or base64 data URI.
        """
        result = await capability.ocr(image)
        return result.model_dump()

    return mcp


def main() -> None:
    config_path = resolve_config_path()
    if config_path is None:
        print(
            "error: no config found. Copy config.example.yaml to config.yaml, "
            "set your API keys as env vars, then re-run.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        capability = build_from_path(config_path)
    except ValueError as exc:
        print(f"error: invalid config — {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    create_server(capability).run()


if __name__ == "__main__":
    main()
