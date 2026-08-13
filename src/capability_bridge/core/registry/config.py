from __future__ import annotations

import os
import pathlib
from typing import Literal

import yaml
from pydantic import BaseModel, Field

ProviderType = Literal["openai_compatible", "gemini"]


class PolicyConfig(BaseModel):
    timeout_seconds: float = 15.0
    max_retries: int = 1


class ProviderConfig(BaseModel):
    type: ProviderType
    base_url: str | None = None
    api_key_env: str


class ModelEntry(BaseModel):
    provider: str
    model: str
    capabilities: list[str] = ["vision"]


class RoutingConfig(BaseModel):
    vision: list[str] = []
    ocr: list[str] = []


class Config(BaseModel):
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    providers: dict[str, ProviderConfig]
    models: dict[str, ModelEntry]
    routing: RoutingConfig


def resolve_config_path() -> str | None:
    env = os.environ.get("CAPABILITY_BRIDGE_CONFIG")
    if env:
        return env
    for candidate in ("config.yaml", "config.yml"):
        path = pathlib.Path(candidate)
        if path.exists():
            return str(path.absolute())
    return None


def load_config(path: str | None = None, *, validate: bool = True) -> Config:
    if path is None:
        path = resolve_config_path()
    if path is None:
        raise FileNotFoundError(
            "config not found: pass a path, set CAPABILITY_BRIDGE_CONFIG, "
            "or create config.yaml (see config.example.yaml)"
        )
    raw = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    config = Config.model_validate(raw)
    if validate:
        validate_config(config)
    return config


def api_key_for(cfg: ProviderConfig) -> str:
    return os.environ.get(cfg.api_key_env, "")


def validate_config(config: Config) -> None:
    """Fail fast on broken config instead of failing obscurely at call time:
    unknown references, capability mismatches, missing base_url, missing API keys."""
    errors: list[str] = []

    for key, entry in config.models.items():
        if entry.provider not in config.providers:
            errors.append(f"models.{key}: provider '{entry.provider}' is not defined in providers")

    routing_keys = set(config.routing.vision) | set(config.routing.ocr)
    for capability, model_keys in config.routing.model_dump().items():
        for key in model_keys:
            if key not in config.models:
                errors.append(f"routing.{capability}: model '{key}' is not defined in models")
                continue
            if capability not in config.models[key].capabilities:
                errors.append(f"routing.{capability}: model '{key}' does not declare capability '{capability}'")

    used_providers = {config.models[k].provider for k in routing_keys if k in config.models}
    for name, pcfg in config.providers.items():
        if pcfg.type == "openai_compatible" and not pcfg.base_url:
            errors.append(f"providers.{name}: openai_compatible requires base_url")
        if name in used_providers and not api_key_for(pcfg):
            errors.append(f"providers.{name}: env var '{pcfg.api_key_env}' is not set (missing API key)")

    if errors:
        raise ValueError("config validation failed:\n- " + "\n- ".join(errors))
