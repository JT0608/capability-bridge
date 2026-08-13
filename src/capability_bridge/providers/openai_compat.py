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


class OpenAICompatProvider(ModelProvider):
    """Adapter for any OpenAI-compatible /chat/completions vision endpoint
    (GLM, Qwen, Kimi, OpenRouter, SiliconFlow, self-hosted...). NOTE: MiniMax vision is NOT
    OpenAI-compatible (own VL protocol) — it needs a dedicated provider type, out of v0.1 scope."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        name: str,
        capabilities: dict[str, bool] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.name = name
        self.capabilities = capabilities if capabilities is not None else {"vision": True, "ocr": True}
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=30.0)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _payload(self, request: ModelRequest) -> dict:
        data_uri = f"data:{request.image.media_type};base64,{base64.b64encode(request.image.data).decode()}"
        prompt = request.prompt or _DEFAULT_PROMPTS.get(request.capability, _DEFAULT_PROMPTS["vision"])
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
        }

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = await self._client.post(url, json=self._payload(request), headers=headers)
        except httpx.TimeoutException as exc:
            raise TimeoutError("provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise ModelUnavailableError(f"transport error: {exc}") from exc

        if response.status_code == 401:
            raise AuthenticationError("401: invalid api key")
        if response.status_code == 429:
            raise RateLimitError("429: rate limited")
        if response.status_code >= 400:
            raise ModelUnavailableError(f"{response.status_code}: {response.text[:200]}")

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise InvalidResponseError(f"unexpected response shape: {exc}") from exc
        if not isinstance(content, str) or not content.strip():
            raise InvalidResponseError("empty content in response")
        return ModelResponse(content=content)
