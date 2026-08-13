from PIL import Image

from capability_bridge.core.errors import (
    AuthenticationError,
    InvalidResponseError,
    ModelUnavailableError,
    RateLimitError,
    TimeoutError,
)
from capability_bridge.core.providers.base import ModelProvider, ModelRequest, ModelResponse


class FakeProvider(ModelProvider):
    """Deterministic provider for tests. behavior: ok|timeout|auth|rate|unavailable|invalid."""

    def __init__(self, name: str, model: str = "fake-model", capabilities=None, behavior: str = "ok") -> None:
        self.name = name
        self.model = model
        self.capabilities = capabilities if capabilities is not None else {"vision": True, "ocr": True}
        self.behavior = behavior
        self.calls = 0
        self.closed = False
        self.aclose_calls = 0
        self.last_request: ModelRequest | None = None

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        self.last_request = request  # lets tests assert prompt/capability reached the provider verbatim
        if self.behavior == "timeout":
            raise TimeoutError("provider timed out")
        if self.behavior == "auth":
            raise AuthenticationError("401 unauthorized")
        if self.behavior == "rate":
            raise RateLimitError("429 rate limited")
        if self.behavior == "unavailable":
            raise ModelUnavailableError("500 model unavailable")
        if self.behavior == "invalid":
            raise InvalidResponseError("response schema mismatch")
        return ModelResponse(content=f"result-from-{self.name}")

    async def aclose(self) -> None:
        self.aclose_calls += 1
        self.closed = True


def make_image(tmp_path, size=(100, 50), fmt="PNG", name="img.png") -> str:
    img = Image.new("RGB", size, "white")
    p = tmp_path / name
    img.save(p, format=fmt)
    return str(p)
