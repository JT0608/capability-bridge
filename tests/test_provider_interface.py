from helpers import FakeProvider, make_image

from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.providers.base import ModelRequest, ModelResponse


async def test_fake_provider_invocation(tmp_path) -> None:
    provider = FakeProvider(name="fake")
    image = ImagePreprocessor().normalize(make_image(tmp_path))
    response = await provider.invoke(ModelRequest(capability="vision", image=image))
    assert isinstance(response, ModelResponse)
    assert response.content == "result-from-fake"
    assert provider.calls == 1


async def test_fake_provider_capabilities_default() -> None:
    assert FakeProvider("x").capabilities == {"vision": True, "ocr": True}


async def test_fake_provider_aclose() -> None:
    provider = FakeProvider("fake")
    await provider.aclose()
    assert provider.closed is True
