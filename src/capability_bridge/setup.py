"""capability-bridge setup: one-shot installer for a coding-agent host.

Run as: capability-bridge setup [--target ...] [--test]. Runtime resources are bundled inside
the package (src/capability_bridge/resources/) and read via importlib.resources, so the CLI
works identically from a wheel install and from the source tree — it never depends on the repo
layout on disk.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import importlib.resources
import io
import json
import pathlib

from PIL import Image

from capability_bridge.core.registry.config import Config, api_key_for, load_config

RESOURCES = importlib.resources.files("capability_bridge.resources")


def _resource_text(name: str) -> str:
    """Read a bundled runtime resource (works in source mode AND inside the installed wheel)."""
    return (RESOURCES / name).read_text(encoding="utf-8")


def ensure_config(target: pathlib.Path) -> bool:
    """Copy the bundled config.example.yaml -> target. Never overwrites an existing file."""
    if target.exists():
        return False
    target.write_bytes((RESOURCES / "config.example.yaml").read_bytes())
    return True


def merge_mcp_config(dest: pathlib.Path | None = None) -> bool:
    """Merge the capability-bridge entry into an existing .mcp.json. Never clobbers other servers."""
    dest = dest or pathlib.Path(".mcp.json")
    snippet = json.loads(_resource_text("claude-code.mcp.json"))
    if dest.exists():
        try:
            data = json.loads(dest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"error: {dest} is not valid JSON; fix it manually (refusing to overwrite)"
            ) from exc
    else:
        data = {"mcpServers": {}}
    data.setdefault("mcpServers", {})["capability-bridge"] = snippet["mcpServers"]["capability-bridge"]
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(dest)  # atomic on POSIX and Windows
    return True


def append_trigger(path: pathlib.Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if "vision_analyze" in text:
        return False
    trigger = _resource_text("vision-trigger.md")
    path.write_text(text.rstrip() + "\n\n" + trigger + "\n", encoding="utf-8")
    return True


def check_keys(config: Config) -> list[str]:
    """Env var names that are missing for providers referenced by any routing list."""
    used_names = set(config.routing.vision) | set(config.routing.ocr)
    used_providers = {config.models[name].provider for name in used_names if name in config.models}
    return [
        provider.api_key_env
        for provider_name, provider in config.providers.items()
        if provider_name in used_providers and not api_key_for(provider)
    ]


async def _verify(capability: object, data_uri: str):
    result = await capability.analyze(data_uri, prompt="Reply with the single word OK.")
    await capability.aclose()
    return result


def run(config_path: str, target: str, test: bool) -> int:
    config_file = pathlib.Path(config_path)
    print(f"[config] {config_file} created={ensure_config(config_file)}")

    cfg = load_config(str(config_file), validate=False)  # setup must work with keys unset
    missing = check_keys(cfg)
    for env in missing:
        print(f"[key] MISSING env var: {env}")

    if target == "claude-code":
        print(f"[mcp] merged into .mcp.json={merge_mcp_config()}")
        print("[mcp] alternative: claude mcp add --scope project capability-bridge -- capability-bridge")
        print(f"[trigger] CLAUDE.md appended={append_trigger(pathlib.Path('CLAUDE.md'))}")
    else:
        print("[mcp] add to ~/.codex/config.toml (see integrations/codex/config.toml.snippet):")
        print(_resource_text("codex.config.toml").rstrip())
        print("[mcp] or run: codex mcp add capability-bridge -- capability-bridge")
        print(f"[trigger] AGENTS.md appended={append_trigger(pathlib.Path('AGENTS.md'))}")

    if test:
        if missing:
            print("[test] skipped: set the missing API keys first, then re-run --test")
        else:
            buf = io.BytesIO()
            Image.new("RGB", (16, 16), "white").save(buf, format="PNG")
            data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
            from capability_bridge.bootstrap import build_from_path

            capability = build_from_path(str(config_file))
            try:
                result = asyncio.run(_verify(capability, data_uri))
                print(f"[test] OK provider={result.provider} model={result.model} latency={result.latency_ms}ms")
            except Exception as exc:  # noqa: BLE001 — report-and-exit for the user
                print(f"[test] FAILED {type(exc).__name__}: {exc}")

    print('[ready] launch your agent and try: "analyze ./error.png"')
    return 0


def setup_main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="capability-bridge setup")
    parser.add_argument("--config", default="config.yaml", help="config file to create")
    parser.add_argument("--target", choices=["claude-code", "codex"], default="claude-code")
    parser.add_argument("--test", action="store_true", help="make one real call to verify the first provider")
    args = parser.parse_args(argv)
    raise SystemExit(run(args.config, args.target, args.test))
