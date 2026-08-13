from __future__ import annotations

import base64
import io
import pathlib
import urllib.parse
import urllib.request
from dataclasses import dataclass

from PIL import Image

from capability_bridge.core.errors import UnsupportedInputError

MAX_EDGE = 2048
MAX_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class NormalizedImage:
    data: bytes
    media_type: str = "image/jpeg"
    width: int = 0
    height: int = 0


class ImagePreprocessor:
    """Validate, resize, compress and re-encode an image into a uniform NormalizedImage."""

    def normalize(self, image_input: str) -> NormalizedImage:
        raw = self._read_bytes(image_input)
        if len(raw) > MAX_BYTES:
            raise UnsupportedInputError(f"image exceeds {MAX_BYTES} bytes")
        img = self._open(raw)
        img = self._normalize_img(img)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return NormalizedImage(data=buf.getvalue(), width=img.width, height=img.height)

    def _read_bytes(self, image_input: str) -> bytes:
        if image_input.startswith("data:"):
            header, _, b64 = image_input.partition(",")
            if "base64" not in header:
                raise UnsupportedInputError("only base64 data URIs are supported")
            try:
                return base64.b64decode(b64)
            except Exception as exc:
                raise UnsupportedInputError(f"invalid base64 data URI: {exc}") from exc
        if image_input.lower().startswith(("http://", "https://")):
            raise UnsupportedInputError("remote image URLs are not supported in v0.1")
        if image_input.startswith("file://"):
            path = urllib.request.url2pathname(urllib.parse.urlparse(image_input).path)
        else:
            path = image_input
        p = pathlib.Path(path)
        if not p.exists():
            raise UnsupportedInputError(f"image not found: {p}")
        return p.read_bytes()

    def _open(self, raw: bytes) -> Image.Image:
        try:
            return Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:
            raise UnsupportedInputError(f"cannot decode image: {exc}") from exc

    def _normalize_img(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        if max(w, h) > MAX_EDGE:
            scale = MAX_EDGE / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        return img
