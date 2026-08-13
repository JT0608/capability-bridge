import json
import pathlib

import pytest

from capability_bridge.core.registry.config import load_config
from capability_bridge.setup import (
    _resource_text,
    append_trigger,
    check_keys,
    ensure_config,
    merge_mcp_config,
)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# (root copy, for developer reading per frozen spec) -> (bundled resource the CLI reads at runtime).
RESOURCE_MAP = {
    "config.example.yaml": "config.example.yaml",
    "prompts/vision-trigger.md": "vision-trigger.md",
    "integrations/claude-code/.mcp.json": "claude-code.mcp.json",
    "integrations/codex/config.toml.snippet": "codex.config.toml",
}

SAMPLE = """
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


def test_ensure_config_copies_example(tmp_path) -> None:
    target = tmp_path / "config.yaml"
    assert ensure_config(target) is True
    assert target.exists()
    assert ensure_config(target) is False


def test_merge_mcp_config_preserves_existing(tmp_path, monkeypatch) -> None:
    existing = {"mcpServers": {"github": {"command": "gh", "args": ["mcp"]}}}
    (tmp_path / ".mcp.json").write_text(json.dumps(existing), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert merge_mcp_config() is True
    merged = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert "github" in merged["mcpServers"]  # untouched
    assert merged["mcpServers"]["capability-bridge"]["command"] == "capability-bridge"


def test_merge_mcp_config_creates_when_absent(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert merge_mcp_config() is True
    data = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert "capability-bridge" in data["mcpServers"]


def test_merge_mcp_config_refuses_invalid_existing(tmp_path, monkeypatch) -> None:
    (tmp_path / ".mcp.json").write_text("not json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="not valid JSON"):
        merge_mcp_config()


def test_append_trigger_appends_once(tmp_path) -> None:
    md = tmp_path / "CLAUDE.md"
    md.write_text("hello\n", encoding="utf-8")
    assert append_trigger(md) is True
    assert "vision_analyze" in md.read_text(encoding="utf-8")
    assert append_trigger(md) is False


def test_check_keys_reports_missing(tmp_path, monkeypatch) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setenv("QWEN_API_KEY", "k1")
    cfg = load_config(str(cfg_path), validate=False)  # validate would raise on missing key
    missing = check_keys(cfg)
    assert "GEMINI_API_KEY" in missing
    assert "QWEN_API_KEY" not in missing


def test_bundled_resources_match_repo_copies() -> None:
    """Guards the 'one source' invariant: the package resources the CLI reads at runtime are
    byte-identical to the repo-root copies kept for developer reading (frozen spec §6)."""
    for repo_rel, resource in RESOURCE_MAP.items():
        repo_text = (PROJECT_ROOT / repo_rel).read_text(encoding="utf-8")
        assert _resource_text(resource) == repo_text
