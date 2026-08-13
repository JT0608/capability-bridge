import asyncio
import json
import logging

import pytest

from capability_bridge.core.errors import AuthenticationError, ModelUnavailableError
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.providers.base import ModelRequest
from capability_bridge.core.routing.policy import RoutingPolicy, RoutedResponse
from helpers import FakeProvider, make_image


def _req(tmp_path, capability: str = "vision") -> ModelRequest:
    return ModelRequest(capability=capability, image=ImagePreprocessor().normalize(make_image(tmp_path)))


async def test_success_on_first_provider(tmp_path) -> None:
    p1, p2 = FakeProvider("a"), FakeProvider("b")
    result = await RoutingPolicy([p1, p2]).execute(_req(tmp_path))
    assert isinstance(result, RoutedResponse)
    assert result.provider == "a"
    assert result.response.content == "result-from-a"
    assert p2.calls == 0


async def test_timeout_falls_back(tmp_path) -> None:
    p1, p2 = FakeProvider("a", behavior="timeout"), FakeProvider("b")
    result = await RoutingPolicy([p1, p2]).execute(_req(tmp_path))
    assert result.provider == "b"
    assert result.response.content == "result-from-b"
    assert any("falling back" in w for w in result.warnings)


async def test_auth_does_not_fallback(tmp_path) -> None:
    p1, p2 = FakeProvider("a", behavior="auth"), FakeProvider("b")
    with pytest.raises(AuthenticationError):
        await RoutingPolicy([p1, p2]).execute(_req(tmp_path))
    assert p2.calls == 0


async def test_retry_then_fallback(tmp_path) -> None:
    p1, p2 = FakeProvider("a", behavior="timeout"), FakeProvider("b")
    result = await RoutingPolicy([p1, p2], max_retries=1).execute(_req(tmp_path))
    assert result.provider == "b"
    assert p1.calls == 2  # 1 initial attempt + 1 retry


async def test_all_fail_raises_last_error(tmp_path) -> None:
    p1, p2 = FakeProvider("a", behavior="unavailable"), FakeProvider("b", behavior="unavailable")
    with pytest.raises(ModelUnavailableError):
        await RoutingPolicy([p1, p2]).execute(_req(tmp_path))


async def test_every_attempt_is_logged(caplog, tmp_path) -> None:
    p1, p2 = FakeProvider("a", behavior="timeout"), FakeProvider("b")
    policy = RoutingPolicy([p1, p2], max_retries=1)
    with caplog.at_level(logging.INFO, logger="capability_bridge"):
        await policy.execute(_req(tmp_path))
    lines = [json.loads(r.getMessage()) for r in caplog.records]
    failures = [line for line in lines if not line["success"]]
    successes = [line for line in lines if line["success"]]
    assert len(failures) == 2  # provider a: attempt 1 + retry
    assert len(successes) == 1  # provider b success
    assert all(line["provider"] == "a" for line in failures)
    assert failures[0]["fallback_count"] == 0
    assert successes[0]["fallback_count"] == 1


async def test_attempt_log_latency_is_per_attempt_not_cumulative(caplog, tmp_path) -> None:
    """Attempt logs carry each provider's OWN latency; the result carries the end-to-end total."""

    class SlowProvider(FakeProvider):
        def __init__(self, name: str, behavior: str = "ok", delay: float = 0.05) -> None:
            super().__init__(name, behavior=behavior)
            self.delay = delay

        async def invoke(self, request):
            await asyncio.sleep(self.delay)
            return await super().invoke(request)

    p1, p2 = SlowProvider("a", behavior="timeout"), SlowProvider("b")
    policy = RoutingPolicy([p1, p2], max_retries=1)
    with caplog.at_level(logging.INFO, logger="capability_bridge"):
        result = await policy.execute(_req(tmp_path))
    lines = [json.loads(r.getMessage()) for r in caplog.records]
    success = next(line for line in lines if line["success"])
    assert success["provider"] == "b"
    # b ran only its own ~50ms; its log line must NOT include provider a's timeout time.
    assert success["latency_ms"] < 100, "fallback provider's log leaked cumulative latency"
    # end-to-end total accumulates a(50ms) + retry(50ms) + b(50ms) >> b's own attempt.
    assert result.latency_ms > success["latency_ms"]
