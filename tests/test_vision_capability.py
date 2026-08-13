import pytest

from capability_bridge.core.capabilities.vision import VisionCapability
from capability_bridge.core.errors import UnsupportedInputError
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.routing.policy import RoutingPolicy
from capability_bridge.core.schemas.result import VisionResult, OCRResult
from helpers import FakeProvider, make_image


def _capability() -> VisionCapability:
    policy = RoutingPolicy([FakeProvider("qwen")], timeout_seconds=5)
    return VisionCapability(ImagePreprocessor(), {"vision": policy, "ocr": policy})


async def test_analyze_returns_vision_result(tmp_path) -> None:
    result = await _capability().analyze(make_image(tmp_path), prompt="what is this?")
    assert isinstance(result, VisionResult)
    assert result.content == "result-from-qwen"
    assert result.provider == "qwen"


async def test_ocr_returns_ocr_result(tmp_path) -> None:
    result = await _capability().ocr(make_image(tmp_path))
    assert isinstance(result, OCRResult)
    assert result.content == "result-from-qwen"


async def test_missing_file_propagates_unsupported(tmp_path) -> None:
    with pytest.raises(UnsupportedInputError):
        await _capability().analyze("missing/file.png")


async def test_aclose_closes_providers() -> None:
    policy = RoutingPolicy([FakeProvider("qwen")], timeout_seconds=5)
    capability = VisionCapability(ImagePreprocessor(), {"vision": policy, "ocr": policy})
    await capability.aclose()
    assert policy.providers[0].closed is True
    assert policy.providers[0].aclose_calls == 1


async def test_aclose_closes_shared_provider_once() -> None:
    shared = FakeProvider("qwen")
    vision_policy = RoutingPolicy([shared], timeout_seconds=5)
    ocr_policy = RoutingPolicy([shared], timeout_seconds=5)
    capability = VisionCapability(ImagePreprocessor(), {"vision": vision_policy, "ocr": ocr_policy})
    await capability.aclose()
    assert shared.aclose_calls == 1


async def test_unsupported_task_rejected(tmp_path) -> None:
    with pytest.raises(UnsupportedInputError, match="unsupported vision task"):
        await _capability().analyze(make_image(tmp_path), task="ui_review")


async def test_prompt_reaches_provider_unchanged(tmp_path) -> None:
    """End-to-end fidelity: the prompt the main model builds is exactly what the provider receives."""
    provider = FakeProvider("qwen")
    policy = RoutingPolicy([provider], timeout_seconds=5)
    capability = VisionCapability(ImagePreprocessor(), {"vision": policy, "ocr": policy})
    prompt = "Analyze hierarchy, spacing, typography, and color as a senior product designer."
    await capability.analyze(make_image(tmp_path), prompt=prompt)
    assert provider.last_request is not None
    assert provider.last_request.prompt == prompt
