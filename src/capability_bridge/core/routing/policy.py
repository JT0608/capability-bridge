from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from capability_bridge.core.errors import (
    CapabilityError,
    ProviderError,
    TimeoutError,
    is_fallback_error,
)
from capability_bridge.core.observability.logging import log_call
from capability_bridge.core.providers.base import ModelProvider, ModelRequest, ModelResponse


@dataclass
class RoutedResponse:
    """Routing answers ONLY 'who succeeded'. Capability output shape is the capability layer's job."""

    response: ModelResponse
    provider: str
    model: str
    latency_ms: int
    warnings: list[str] = field(default_factory=list)


class RoutingPolicy:
    """Ordered fallback: try providers in order, retry transient errors, never fallback on hard errors.
    Records ONE structured log line per provider attempt (success and failure alike)."""

    def __init__(
        self,
        providers: list[ModelProvider],
        timeout_seconds: float = 15.0,
        max_retries: int = 1,
        request_id: str = "-",
    ) -> None:
        self.providers = providers
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.request_id = request_id

    async def execute(self, request: ModelRequest, *, request_id: str | None = None) -> RoutedResponse:
        request_id = request_id or self.request_id
        started = time.monotonic()
        warnings: list[str] = []
        fallback_count = 0
        last_error: Exception | None = None

        for index, provider in enumerate(self.providers):
            for _ in range(1 + self.max_retries):
                attempt_started = time.monotonic()  # per-attempt latency (feeds the routing log)
                try:
                    response = await asyncio.wait_for(provider.invoke(request), timeout=self.timeout_seconds)
                    log_call(
                        request_id=request_id,
                        capability=request.capability,
                        provider=provider.name,
                        model=provider.model,
                        latency_ms=int((time.monotonic() - attempt_started) * 1000),
                        success=True,
                        fallback_count=fallback_count,
                    )
                    return RoutedResponse(
                        response=response,
                        provider=provider.name,
                        model=provider.model,
                        latency_ms=int((time.monotonic() - started) * 1000),  # end-to-end total
                        warnings=warnings,
                    )
                except asyncio.TimeoutError as exc:
                    last_error = TimeoutError(str(exc))
                except ProviderError as exc:
                    last_error = exc
                except Exception as exc:  # pragma: no cover - defensive
                    last_error = exc
                log_call(
                    request_id=request_id,
                    capability=request.capability,
                    provider=provider.name,
                    model=provider.model,
                    latency_ms=int((time.monotonic() - attempt_started) * 1000),
                    success=False,
                    error_type=type(last_error).__name__,
                    fallback_count=fallback_count,
                )
                if not (isinstance(last_error, ProviderError) and is_fallback_error(last_error)):
                    break  # hard error: no retry, no fallback

            if isinstance(last_error, ProviderError) and is_fallback_error(last_error) and index < len(self.providers) - 1:
                warnings.append(
                    f"{provider.name}/{provider.model} failed ({type(last_error).__name__}); falling back"
                )
                fallback_count += 1
                continue

            raise last_error

        raise CapabilityError("no providers configured for capability")
