from capability_bridge.bootstrap import build_capability
from capability_bridge.core.capabilities.vision import VisionCapability
from capability_bridge.core.registry.config import load_config

SAMPLE = """
policy:
  timeout_seconds: 3
  max_retries: 1
providers:
  qwen:
    type: openai_compatible
    base_url: https://example.com/v1
    api_key_env: QWEN_API_KEY
  gemini:
    type: gemini
    api_key_env: GEMINI_API_KEY
models:
  qwen-vl:
    provider: qwen
    model: qwen3-vl-flash
    capabilities: [vision, ocr]
  gemini-flash:
    provider: gemini
    model: gemini-2.5-flash
    capabilities: [vision]
routing:
  vision: [qwen-vl, gemini-flash]
  ocr: [qwen-vl]
"""


def test_build_capability_wires_providers_in_order(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "k1")
    monkeypatch.setenv("GEMINI_API_KEY", "k2")
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(SAMPLE, encoding="utf-8")

    capability = build_capability(load_config(str(cfg_path)))
    assert isinstance(capability, VisionCapability)

    vision_providers = capability._policies["vision"].providers
    assert [p.name for p in vision_providers] == ["qwen", "gemini"]
    assert vision_providers[0].model == "qwen3-vl-flash"
    assert vision_providers[0].api_key == "k1"

    assert len(capability._policies["ocr"].providers) == 1
    assert capability._policies["ocr"].providers[0].model == "qwen3-vl-flash"
