# Changelog

## v0.1.0 (2026-08-14)

Initial release — a transport-agnostic model capability bridge. MCP is the first transport;
Vision is the first capability. License: Apache-2.0.

### Features

- **MCP stdio server** exposing `vision_analyze(image, prompt)` and `vision_ocr(image)`.
- **Capability Core**: error taxonomy with fallback classification, result schemas
  (`CapabilityResult` / `VisionResult` / `OCRResult`), image preprocessing (local path /
  `file://` / base64 data URI, no remote URLs), routing with ordered fallback + retry + timeout,
  per-attempt structured logging (privacy whitelist).
- **Providers**: `OpenAICompatProvider` (any OpenAI-compatible vision endpoint) and `GeminiProvider`
  (native protocol). Architecture red lines (core never imports MCP / clients / concrete providers)
  enforced by `tests/test_architecture.py`.
- **`capability-bridge setup`** one-shot installer: merge-safe `.mcp.json`, missing-key report by
  env-var name, bundled resources (read via `importlib.resources`, ship in the wheel), `--test`
  live self-test. Install once with `uv tool install .`, run from any project.
- **Trigger rule** (intent-driven visual briefs) + product README.

### Defaults / decisions

- Default vision model `qwen3.6-flash` with a 120s timeout. `qwen3-vl-flash` (the F1–F4 benchmark
  subject) is retired by DashScope on 2026-10-10; `qwen3.6-flash` is its official unified
  text+vision successor (same OpenAI-compatible interface). `qwen3.7-plus` is a documented optional
  profile. Benchmark: `docs/benchmarks/2026-08-13-qwen-vision-ab.md`.
- **Live-tested providers**: Qwen (DashScope), GLM (Zhipu, `glm-4.6v-flash`), MiniMax-M3
  (DashScope-hosted; requires activation in the Bailian console). **Implemented + contract-tested**
  only: Gemini native. See README "Tested providers".
- Product note: *Vision means visual reasoning, not image captioning* — the Visual Brief is a
  first-order capability factor (`docs/superpowers/product/2026-08-13-vision-product-note.md`).
