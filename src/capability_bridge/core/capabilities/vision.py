from __future__ import annotations

import uuid

from capability_bridge.core.errors import UnsupportedInputError
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.providers.base import ModelRequest
from capability_bridge.core.routing.policy import RoutingPolicy
from capability_bridge.core.schemas.result import VisionResult, OCRResult


class VisionCapability:
    """Capability layer: 'what to do'. Routing answers 'who did it'; this layer shapes the result."""

    def __init__(self, preprocessor: ImagePreprocessor, policies: dict[str, RoutingPolicy]) -> None:
        self._preprocessor = preprocessor
        self._policies = policies

    async def analyze(self, image_input: str, prompt: str | None = None, task: str = "general") -> VisionResult:
        # v0.1 ships one task profile; reject unknown values loudly instead of silently ignoring
        # them (otherwise task="ui_review" would "look like it works" until its real semantics arrive).
        if task != "general":
            raise UnsupportedInputError(f"unsupported vision task: {task}; v0.1 supports only 'general'")
        normalized = self._preprocessor.normalize(image_input)
        request = ModelRequest(capability="vision", image=normalized, prompt=prompt)
        routed = await self._policies["vision"].execute(request, request_id=str(uuid.uuid4()))
        return VisionResult(
            content=routed.response.content,
            structured_data=routed.response.structured_data,
            provider=routed.provider,
            model=routed.model,
            latency_ms=routed.latency_ms,  # end-to-end total (per-attempt latencies live in the routing log)
            warnings=routed.warnings,
        )

    async def ocr(self, image_input: str) -> OCRResult:
        normalized = self._preprocessor.normalize(image_input)
        request = ModelRequest(capability="ocr", image=normalized)
        routed = await self._policies["ocr"].execute(request, request_id=str(uuid.uuid4()))
        return OCRResult(
            content=routed.response.content,
            structured_data=routed.response.structured_data,
            provider=routed.provider,
            model=routed.model,
            latency_ms=routed.latency_ms,  # end-to-end total (per-attempt latencies live in the routing log)
            warnings=routed.warnings,
        )

    async def aclose(self) -> None:
        """Release every provider held by this capability's routing policies, each exactly once.

        A single provider instance can be shared across policies (one vision+ocr model appears in
        both routing lists), so dedupe by identity before closing.
        """
        seen: set[int] = set()
        for policy in self._policies.values():
            for provider in policy.providers:
                if id(provider) in seen:
                    continue
                seen.add(id(provider))
                await provider.aclose()
