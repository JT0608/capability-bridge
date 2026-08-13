import json

import httpx
import pytest

from capability_bridge.core.errors import (
    AuthenticationError,
    InvalidResponseError,
    ModelUnavailableError,
    RateLimitError,
    TimeoutError,
)
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.providers.base import ModelRequest
from capability_bridge.providers.openai_compat import OpenAICompatProvider
from helpers import make_image


def _provider(handler, *, model="qwen3-vl-flash") -> OpenAICompatProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return OpenAICompatProvider(
        base_url="https://example.com/v1", api_key="test-key", model=model,
        name="qwen", client=client,
    )


@pytest.fixture
def image(tmp_path):
    return ImagePreprocessor().normalize(make_image(tmp_path))


async def test_success_payload_and_content(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "qwen3-vl-flash"
        content_parts = body["messages"][0]["content"]
        assert content_parts[1]["type"] == "image_url"
        assert content_parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": "a cat"}}]})

    response = await _provider(handler).invoke(ModelRequest(capability="vision", image=image))
    assert response.content == "a cat"


async def test_explicit_prompt_is_forwarded_unchanged(image) -> None:
    sent = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent["prompt"] = body["messages"][0]["content"][0]["text"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    prompt = "Analyze hierarchy, spacing, typography, and color as a senior product designer."
    await _provider(handler).invoke(ModelRequest(capability="vision", image=image, prompt=prompt))
    assert sent["prompt"] == prompt  # explicit prompt wins over _DEFAULT_PROMPTS, verbatim


async def test_401_maps_to_authentication(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(AuthenticationError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_429_maps_to_rate_limit(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "slow down"})

    with pytest.raises(RateLimitError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_500_maps_to_unavailable(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(ModelUnavailableError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_timeout_maps_to_timeout(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(TimeoutError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_malformed_response_maps_to_invalid(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    with pytest.raises(InvalidResponseError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_aclose_closes_own_client() -> None:
    # NOTE: constructs the provider WITHOUT an injected client, so it OWNS its
    # client and aclose() must close it. (Deviation Level 1: the plan's pasted
    # test reused _provider(handler), which injects a client -> _owns_client is
    # False -> the plan's implementation intentionally does NOT close it. The
    # injected-client case is covered by test_aclose_leaves_injected_client_open.)
    provider = OpenAICompatProvider(
        base_url="https://example.com/v1", api_key="test-key", model="qwen3-vl-flash", name="qwen"
    )
    assert not provider._client.is_closed
    await provider.aclose()
    assert provider._client.is_closed


async def test_aclose_leaves_injected_client_open() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})))
    provider = OpenAICompatProvider(
        base_url="https://example.com/v1", api_key="k", model="m", name="qwen", client=client
    )
    await provider.aclose()
    assert not client.is_closed
