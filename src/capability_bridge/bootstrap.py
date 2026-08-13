from __future__ import annotations

from capability_bridge.core.capabilities.vision import VisionCapability
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.registry.config import (
    Config,
    ProviderConfig,
    api_key_for,
    load_config,
    resolve_config_path,
)
from capability_bridge.core.routing.policy import RoutingPolicy
from capability_bridge.providers.gemini import GeminiProvider
from capability_bridge.providers.openai_compat import OpenAICompatProvider

_PROVIDER_TYPES = {
    "openai_compatible": OpenAICompatProvider,
    "gemini": GeminiProvider,
}


def _instantiate(key: str, cfg: Config) -> object:
    entry = cfg.models[key]
    pcfg: ProviderConfig = cfg.providers[entry.provider]
    cls = _PROVIDER_TYPES[pcfg.type]
    common = {
        "name": entry.provider,
        "model": entry.model,
        "capabilities": {c: True for c in entry.capabilities},
    }
    if pcfg.type == "openai_compatible":
        return cls(base_url=pcfg.base_url, api_key=api_key_for(pcfg), **common)
    return cls(api_key=api_key_for(pcfg), **common)


def build_capability(config: Config) -> VisionCapability:
    instances = {key: _instantiate(key, config) for key in config.models}
    policies: dict[str, RoutingPolicy] = {}
    for capability, model_keys in config.routing.model_dump().items():
        providers = [instances[k] for k in model_keys if k in instances]
        policies[capability] = RoutingPolicy(
            providers,
            timeout_seconds=config.policy.timeout_seconds,
            max_retries=config.policy.max_retries,
        )
    return VisionCapability(ImagePreprocessor(), policies)


def build_from_path(config_path: str | None = None) -> VisionCapability:
    if config_path is None:
        config_path = resolve_config_path()
    return build_capability(load_config(config_path))
