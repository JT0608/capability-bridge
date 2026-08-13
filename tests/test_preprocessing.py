import base64

import pytest
from PIL import Image

from capability_bridge.core.errors import UnsupportedInputError
from capability_bridge.core.preprocessing.image import (
    MAX_EDGE,
    ImagePreprocessor,
    NormalizedImage,
)


def _make_image(tmp_path, size=(100, 50), fmt="PNG", name="img.png") -> str:
    img = Image.new("RGB", size, "red")
    p = tmp_path / name
    img.save(p, format=fmt)
    return str(p)


def test_local_path(tmp_path) -> None:
    norm = ImagePreprocessor().normalize(_make_image(tmp_path))
    assert isinstance(norm, NormalizedImage)
    assert norm.media_type == "image/jpeg"
    assert norm.width == 100
    assert norm.height == 50


def test_file_uri(tmp_path) -> None:
    p = tmp_path / "img.png"
    Image.new("RGB", (64, 64), "blue").save(p)
    norm = ImagePreprocessor().normalize(p.as_uri())
    assert norm.width == 64


def test_data_uri(tmp_path) -> None:
    path = _make_image(tmp_path, size=(32, 32))
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    uri = f"data:image/png;base64,{b64}"
    norm = ImagePreprocessor().normalize(uri)
    assert norm.width == 32


def test_oversized_image_resized(tmp_path) -> None:
    path = _make_image(tmp_path, size=(4000, 2000))
    norm = ImagePreprocessor().normalize(path)
    assert max(norm.width, norm.height) <= MAX_EDGE
    assert (norm.width, norm.height) == (2048, 1024)


def test_missing_file_rejected() -> None:
    with pytest.raises(UnsupportedInputError):
        ImagePreprocessor().normalize("does-not-exist.png")


def test_http_url_rejected() -> None:
    with pytest.raises(UnsupportedInputError):
        ImagePreprocessor().normalize("https://example.com/img.png")
