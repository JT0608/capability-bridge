from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from capability_bridge.core.preprocessing.image import NormalizedImage

CapabilitySet = dict[str, bool]


@dataclass(frozen=True)
class ModelRequest:
    capability: str
    image: NormalizedImage
    prompt: str | None = None


@dataclass(frozen=True)
class ModelResponse:
    content: str
    structured_data: dict | None = None


class ModelProvider(ABC):
    """Contract for a concrete model adapter. Implementations live in providers/ (outside core)."""

    name: str
    model: str
    capabilities: CapabilitySet

    @abstractmethod
    async def invoke(self, request: ModelRequest) -> ModelResponse:
        ...

    async def aclose(self) -> None:
        """Release resources this provider OWNS. Default no-op; adapters close only
        clients they created themselves — injected clients stay open (external owns them)."""
        ...
