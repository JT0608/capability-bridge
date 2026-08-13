from pydantic import BaseModel


class CapabilityResult(BaseModel):
    """Uniform result envelope. `structured_data` is capability-specific, never a universal dump."""

    content: str
    structured_data: dict | None = None
    provider: str
    model: str
    latency_ms: int
    warnings: list[str] = []


class VisionResult(CapabilityResult):
    """Vision capability result. May attach structured objects in `structured_data` later."""


class OCRResult(CapabilityResult):
    """OCR capability result."""
