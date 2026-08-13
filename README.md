# capability-bridge

> **Love your coding model, but it can't see? Give it eyes.**

Keep DeepSeek, MiniMax, or any text-only model as your coding brain. capability-bridge adds
vision through MCP — without switching your main model.

*A transport-agnostic model capability bridge. MCP is the first transport; Vision is the first capability.*

## Quickstart (30 seconds)

```bash
# 1. install the CLI once
uv tool install .
# 2. one-shot setup: config + key check + MCP wiring + trigger, optionally a live provider test
capability-bridge setup --target claude-code --test
# 3. in Claude Code / Codex: send a screenshot and ask "what's wrong here?"
```

`setup` never overwrites an existing `.mcp.json` — it merges only the `capability-bridge` entry.
Missing API keys are reported by name; `--test` makes one real call to verify the first provider.

Running from the source repo during development? Start the server with `uv run capability-bridge`
instead of the installed CLI.

## How it works

`vision_analyze(image, prompt?)` and `vision_ocr(image)` hand your image to a vision model
(Qwen-VL, GLM-4.6V, Kimi, Gemini, ...) and return the text to your main model. Providers are
tried in the order in `config.yaml`; if one times out, is rate-limited, or is unavailable, the
next one is tried automatically.

## Configuration

`config.yaml` holds three objective sections: `providers` (endpoint type + api key env var),
`models` (provider/model/capabilities), and `routing` (ordered fallback list per capability).
Only objective facts live here — no subjective model scoring. A broken config (unknown model,
missing key) fails fast at startup with the exact field named.

## Default model

The shipped config defaults to `qwen3-vl-flash`. In the tested coding-oriented visual workloads
(simple reading, complex UI review, art analysis, and varying context density) it delivers the
best latency/quality trade-off: comparable practical output quality to the higher-capability model
when given the same task-scoped Visual Brief, at substantially lower latency. Benchmark details in
`docs/benchmarks/2026-08-13-qwen-vision-ab.md`.

To use a higher-capability model, change the `model:` line of the vision model entry in
`config.yaml` (e.g. to `qwen3.7-plus`) — a documented optional profile for users who accept higher
latency. This does not claim flash is "better vision" in general.

## Tested providers

`OpenAICompatProvider` speaks any endpoint that accepts OpenAI-style multimodal
`/chat/completions` with `image_url` content parts.

**Live tested (v0.1):** Qwen (DashScope), GLM (Zhipu native, `glm-4.6v-flash`), MiniMax-M3 (hosted
on DashScope — needs the model activated in the Bailian console).

**Implemented, automated-tested only:** Gemini native (`GeminiProvider`) — its contract is covered
by tests but it is not in the v0.1 live-provider acceptance matrix.

Compatibility with an OpenAI-compatible endpoint depends on that endpoint actually supporting
multimodal `image_url` inputs (e.g. MiniMax's own API is OpenAI-compatible for text but not for
vision).

## Architecture

```
Agent (Claude Code / Codex)
  │ MCP stdio
  ▼
Transport: MCP            <- only place that imports mcp
  ▼
Capability Core           <- transport-agnostic, stateless
  Capabilities -> Routing -> Providers(interface) <- adapters
```

Concrete provider adapters live outside `core/` and implement the `ModelProvider` interface.
The composition root (`bootstrap.py`) wires config → providers → routing → capability.

## Development

```bash
uv run pytest
```

`tests/test_architecture.py` enforces the red lines (core never imports MCP / clients / concrete providers).
