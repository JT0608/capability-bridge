import pytest

from capability_bridge.core.registry.config import (
    Config,
    ModelEntry,
    PolicyConfig,
    ProviderConfig,
    RoutingConfig,
    api_key_for,
    load_config,
    resolve_config_path,
    validate_config,
)

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


def test_load_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "k1")
    monkeypatch.setenv("GEMINI_API_KEY", "k2")
    p = tmp_path / "config.yaml"
    p.write_text(SAMPLE, encoding="utf-8")
    cfg = load_config(str(p))
    assert isinstance(cfg, Config)
    assert cfg.policy.timeout_seconds == 3
    assert cfg.policy.max_retries == 1
    assert cfg.providers["qwen"].type == "openai_compatible"
    assert cfg.providers["qwen"].base_url == "https://example.com/v1"
    assert cfg.providers["qwen"].api_key_env == "QWEN_API_KEY"
    assert cfg.models["qwen-vl"].model == "qwen3-vl-flash"
    assert cfg.models["qwen-vl"].capabilities == ["vision", "ocr"]
    assert cfg.routing.vision == ["qwen-vl", "gemini-flash"]
    assert cfg.routing.ocr == ["qwen-vl"]


def test_resolve_config_path_env(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve_config_path() is None
    cfg = tmp_path / "config.yaml"
    cfg.write_text(SAMPLE, encoding="utf-8")
    assert resolve_config_path() == str(cfg)


def test_api_key_from_env(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "secret-value")
    pcfg = ProviderConfig(type="openai_compatible", base_url="https://x", api_key_env="QWEN_API_KEY")
    assert api_key_for(pcfg) == "secret-value"


def _valid_cfg() -> Config:
    return Config(
        policy=PolicyConfig(),
        providers={
            "qwen": ProviderConfig(type="openai_compatible", base_url="https://x", api_key_env="QWEN_API_KEY"),
            "gemini": ProviderConfig(type="gemini", api_key_env="GEMINI_API_KEY"),
        },
        models={
            "qwen-vl": ModelEntry(provider="qwen", model="qwen3-vl-flash", capabilities=["vision", "ocr"]),
            "gemini-flash": ModelEntry(provider="gemini", model="gemini-2.5-flash", capabilities=["vision"]),
        },
        routing=RoutingConfig(vision=["qwen-vl", "gemini-flash"], ocr=["qwen-vl"]),
    )


def test_validate_unknown_provider(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    cfg = _valid_cfg()
    cfg.models["qwen-vl"].provider = "nope"
    with pytest.raises(ValueError, match="not defined in providers"):
        validate_config(cfg)


def test_validate_unknown_routing_model(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    cfg = _valid_cfg()
    cfg.routing.vision = ["qwen-vl", "does-not-exist"]
    with pytest.raises(ValueError, match="does-not-exist"):
        validate_config(cfg)


def test_validate_capability_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    cfg = _valid_cfg()
    cfg.routing.ocr = ["gemini-flash"]  # gemini-flash declares only vision
    with pytest.raises(ValueError, match="does not declare capability 'ocr'"):
        validate_config(cfg)


def test_validate_missing_base_url(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "k")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    cfg = _valid_cfg()
    cfg.providers["qwen"].base_url = None
    with pytest.raises(ValueError, match="requires base_url"):
        validate_config(cfg)


def test_validate_missing_key(monkeypatch) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "k")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    cfg = _valid_cfg()
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        validate_config(cfg)
