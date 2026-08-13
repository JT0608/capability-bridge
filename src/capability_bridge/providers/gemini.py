from __future__ import annotations

import base64

import httpx

from capability_bridge.core.errors import (
    AuthenticationError,
    InvalidResponseError,
    ModelUnavailableError,
    RateLimitError,
    TimeoutError,
)
from capability_bridge.core.providers.base import ModelProvider, ModelRequest, ModelResponse

_DEFAULT_PROMPTS = {
    "vision": "Describe this image accurately and concisely.",
    "ocr": "Extract all text from this image.",
}


class GeminiProvider(ModelProvider):
    """Adapter for Google Gemini generateContent (its own protocol)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        name: str = "gemini",
        capabilities: dict[str, bool] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.name = name
        self.capabilities = capabilities if capabilities is not None else {"vision": True, "ocr": True}
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=120.0)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        prompt = request.prompt or _DEFAULT_PROMPTS.get(request.capability, _DEFAULT_PROMPTS["vision"])
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": request.image.media_type,
                                "data": base64.b64encode(request.image.data).decode(),
                            }
                        },
                    ]
                }
            ]
        }
        params = {"key": self.api_key}
        try:
            response = await self._client.post(url, json=body, params=params)
        except httpx.TimeoutException as exc:
            raise TimeoutError("provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise ModelUnavailableError(f"transport error: {exc}") from exc

        if response.status_code in (401, 403):
            raise AuthenticationError(f"{response.status_code}: invalid api key")
        if response.status_code == 429:
            raise RateLimitError("429: rate limited")
        if response.status_code >= 400:
            raise ModelUnavailableError(f"{response.status_code}: {response.text[:200]}")

        try:
            parts = response.json()["candidates"][0]["content"]["parts"]
            content = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise InvalidResponseError(f"unexpected response shape: {exc}") from exc
        if not content.strip():
            raise InvalidResponseError("empty content in response")
        return ModelResponse(content=content)
