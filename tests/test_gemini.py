import json

import httpx
import pytest

from capability_bridge.core.errors import AuthenticationError, InvalidResponseError, RateLimitError
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.providers.base import ModelRequest
from capability_bridge.providers.gemini import GeminiProvider
from helpers import make_image


def _provider(handler, *, model="gemini-2.5-flash") -> GeminiProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return GeminiProvider(api_key="test-key", model=model, name="gemini", client=client)


@pytest.fixture
def image(tmp_path):
    return ImagePreprocessor().normalize(make_image(tmp_path))


async def test_success_payload_and_content(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "generateContent" in str(request.url)
        assert request.url.params["key"] == "test-key"
        body = json.loads(request.content)
        parts = body["contents"][0]["parts"]
        assert parts[1]["inline_data"]["mime_type"] == "image/jpeg"
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "a dog"}]}}]},
        )

    response = await _provider(handler).invoke(ModelRequest(capability="vision", image=image))
    assert response.content == "a dog"


async def test_explicit_prompt_is_forwarded_unchanged(image) -> None:
    sent = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent["prompt"] = body["contents"][0]["parts"][0]["text"]
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "x"}]}}]},
        )

    prompt = "Analyze composition, light, color, and mood as an art critic."
    await _provider(handler).invoke(ModelRequest(capability="vision", image=image, prompt=prompt))
    assert sent["prompt"] == prompt  # explicit prompt wins over _DEFAULT_PROMPTS, verbatim


async def test_401_maps_to_authentication(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "denied"})

    with pytest.raises(AuthenticationError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_429_maps_to_rate_limit(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "quota"})

    with pytest.raises(RateLimitError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_malformed_response_maps_to_invalid(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"nope": True})

    with pytest.raises(InvalidResponseError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_aclose_closes_own_client() -> None:
    # NOTE: construct WITHOUT an injected client so the provider OWNS it and aclose() must close it.
    provider = GeminiProvider(api_key="test-key", model="gemini-2.5-flash", name="gemini")
    assert not provider._client.is_closed
    await provider.aclose()
    assert provider._client.is_closed


async def test_aclose_leaves_injected_client_open() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})))
    provider = GeminiProvider(api_key="k", model="m", name="gemini", client=client)
    await provider.aclose()
    assert not client.is_closed
