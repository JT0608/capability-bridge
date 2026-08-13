from capability_bridge.core.schemas.result import CapabilityResult, OCRResult, VisionResult


def test_capability_result_defaults() -> None:
    r = CapabilityResult(content="hello", provider="qwen", model="qwen3-vl-flash", latency_ms=10)
    assert r.structured_data is None
    assert r.warnings == []


def test_vision_and_ocr_are_subclasses() -> None:
    v = VisionResult(content="a cat", provider="p", model="m", latency_ms=1)
    o = OCRResult(content="line 1", provider="p", model="m", latency_ms=1)
    assert isinstance(v, CapabilityResult)
    assert isinstance(o, CapabilityResult)


def test_dump_includes_all_fields() -> None:
    r = CapabilityResult(
        content="x", provider="p", model="m", latency_ms=5,
        structured_data={"k": "v"}, warnings=["w"],
    )
    dumped = r.model_dump()
    assert dumped["structured_data"] == {"k": "v"}
    assert dumped["warnings"] == ["w"]
    assert dumped["latency_ms"] == 5
