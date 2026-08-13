# capability-bridge v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build capability-bridge v0.1 — a transport-agnostic Capability Core with Vision as the first capability and MCP stdio as the first transport, giving text-only agents (Claude Code / Codex) vision via `vision_analyze` / `vision_ocr` with pluggable providers and ordered fallback.

**Architecture:** Capability Core (`src/capability_bridge/core/`) is the project body — stateless `request → capability → result`. Concrete provider adapters live OUTSIDE core in `src/capability_bridge/providers/` and implement the `ModelProvider` ABC. The MCP transport (`src/capability_bridge/transports/mcp/`) is the only place that imports MCP, and `bootstrap.py` (composition root) wires registry config → provider instances → routing policy → capability.

**Tech Stack:** Python 3.12+, uv, FastMCP (MCP only inside `transports/mcp/`), Pydantic v2, httpx, Pillow, PyYAML, pytest + pytest-asyncio.

## Global Constraints

- `import mcp` / `import fastmcp` is allowed ONLY in `src/capability_bridge/transports/mcp/`.
- `core/` must never import MCP, client SDKs (anthropic/openai), or concrete providers/transports.
- Concrete provider adapters live in `src/capability_bridge/providers/`, implement `core/providers/base.py:ModelProvider`, depend inward on core only.
- Registry records ONLY objective info: `type`, `base_url`, `api_key_env`, `model`, `capabilities`. NO `free`, NO scoring.
- v0.1 image input: local path | `file://` | base64 data URI only. **NO http(s) URLs** (raise `UnsupportedInputError`).
- Errors via taxonomy in `core/errors/`; fallback ONLY on Timeout/RateLimit/ModelUnavailable/InvalidResponse. Authentication/UnsupportedInput = no fallback.
- Structured logs carry ONLY: `request_id, capability, provider, model, latency_ms, success, error_type, fallback_count`. NEVER log image bytes, prompt text, or full model response.
- No Context/Memory/Agent-loop/Workflow in v0.1. Stateless.
- Python 3.12+, uv. Deps: pydantic>=2, httpx, Pillow, PyYAML, fastmcp (transport only).
- Setup/install tooling must MERGE into existing agent config — never overwrite other MCP servers in an existing `.mcp.json`, and never overwrite an existing `config.yaml` / `CLAUDE.md` / `AGENTS.md`.
- **Before the first commit:** configure git identity (`git config user.name "..."` and `git config user.email "..."`). The design spec is already staged from the design phase — land it as its own commit first (see Task 1).

---

## Product Definition of Done (v0.1 release gate)

A new user — who has NOT read the source, has NOT edited Python, and does NOT understand MCP —
must be able to do all of the following, or v0.1 is NOT shippable:

- [ ] **No clobbering:** installing into a project that already has an `.mcp.json` (other MCP
      servers) leaves those servers untouched; only the `capability-bridge` entry is added.
- [ ] **One key:** the shipped default config needs exactly one provider, so giving a single API
      key (one env var) is enough to get a first successful result — no need to understand or
      fill in the other providers.
- [ ] **5-minute install:** from repo clone to first successful `vision_analyze` result is under
      5 minutes, via `uv tool install .` (run in the repo) + `capability-bridge setup`.
- [ ] **Tools visible:** the `vision_analyze` / `vision_ocr` tools appear in Claude Code and Codex
      after setup.
- [ ] **Main model stays:** the user sends a screenshot and their existing coding model keeps
      doing the reasoning; the bridge only adds vision.
- [ ] **Fallback works:** when two or more providers are configured, fallback works automatically —
      a failing provider rolls to the next one without the user doing anything.
- [ ] **Install once, run anywhere:** the CLI is installed once (a tool, not a venv per project)
      and works from any project directory — no `uv run` inside an agent's cwd.
- [ ] **Clear failure messages:** a missing API key is reported by env-var name; a broken config
      names the exact offending field.
- [ ] **Self-test:** `capability-bridge setup --test` makes one real provider call and reports
      provider / model / latency before the user trusts the setup.
- [ ] **First screen sells the product:** the README's first screen communicates "keep your model,
      add what it lacks" — not architecture.

---

## Execution Protocol

Rules for whoever runs this plan (Subagent-Driven: one fresh subagent per task; the parent agent
holds the frozen spec + architecture and reviews every diff).

- **Checkpoint cadence:** every task = subagent implements → parent reviews the diff (against the
  frozen spec's red lines, the task's interface contracts, and the scope red lines) → tests pass →
  commit. Human/vertical checkpoints at: Task 1–5 (core contract), Task 6–10 (providers + registry
  + routing), Task 11–13 (full internal chain), Task 14 (real product E2E). The human does NOT
  review every function; the parent agent is the one that must guard the architecture.
- **Review is executable, not just eyeballed.** On every task the parent runs: a static import check
  (no imports pointing at modules that don't exist — the `core.registry.models` bug above), the
  task's pytest, and the full architecture red-line test.
- **Deviations are graded, never silent:**
  - *Level 1 (implementation):* an API response field differs from the mock, a library
    minor-version quirk. Subagent may make the minimal fix and MUST record the deviation for review.
  - *Level 2 (contract):* a `ModelProvider` method, a `RoutedResponse` field, or a config schema
    would need to change. Subagent must NOT decide alone — parent review.
  - *Level 3 (product / architecture):* adding HTTP image input, Memory, a new capability, a new
    transport, binding core to MCP, changing the Gateway. STOP that direction immediately and go
    back to the frozen spec.
  - Never "refactor the architecture so the test passes."
- **The plan is a blueprint, not law.** The frozen things are: behavior, boundaries, interface
  contracts, Product DoD. The pasted code is a construction drawing. If real implementation shows a
  designed piece is unnecessary, DELETING it is allowed — and must be recorded; adding new
  abstractions just for "completeness" is not.
- **Toolchain fidelity:** uv is the product toolchain — install it; do NOT silently swap the test
  environment to pip/venv, or the environment tested diverges from what users install. Python 3.14
  is not assumed safe just because `>=3.12`: Task 1's `uv sync` + full dependency install is the
  compatibility gate. If a dependency fails on 3.14, decide THEN whether to lock the dev/CI baseline
  to 3.12/3.13 — don't pre-guess now.
- **Git identity** is set by the human, repo-local, before execution starts:
  `git config user.name "..."` / `git config user.email "..."`. The executor never invents one.

---

## File Structure Map

| Path | Responsibility |
|---|---|
| `pyproject.toml` | uv project, deps, console script `capability-bridge`, pytest config |
| `src/capability_bridge/__init__.py` | package marker |
| `src/capability_bridge/core/errors/__init__.py` | error taxonomy + `is_fallback_error` |
| `src/capability_bridge/core/schemas/result.py` | `CapabilityResult` / `VisionResult` / `OCRResult` |
| `src/capability_bridge/core/providers/base.py` | `ModelProvider` ABC, `ModelRequest`, `ModelResponse`, `CapabilitySet` |
| `src/capability_bridge/core/preprocessing/image.py` | `NormalizedImage`, `ImagePreprocessor` |
| `src/capability_bridge/core/registry/config.py` | Pydantic config models, YAML loading, env resolution |
| `src/capability_bridge/core/observability/logging.py` | structured logging with privacy whitelist |
| `src/capability_bridge/core/routing/policy.py` | `RoutingPolicy` — ordered fallback + retry + timeout |
| `src/capability_bridge/core/capabilities/vision.py` | `VisionCapability.analyze()` / `.ocr()` |
| `src/capability_bridge/providers/openai_compat.py` | OpenAI-compatible adapter (GLM/Qwen/Kimi/...), httpx |
| `src/capability_bridge/providers/gemini.py` | Google Gemini adapter |
| `src/capability_bridge/bootstrap.py` | composition root: config → provider instances → routing → capability |
| `src/capability_bridge/setup.py` | importable installer: `ensure_config`, `merge_mcp_config`, `append_trigger`, `check_keys`, `setup_main` |
| `src/capability_bridge/cli.py` | entry point dispatch: default = MCP server, `setup` = installer |
| `src/capability_bridge/resources/` | bundled runtime resources (`config.example.yaml`, `vision-trigger.md`, `claude-code.mcp.json`, `codex.config.toml`) — read via `importlib.resources`, ship in the wheel |
| `src/capability_bridge/transports/mcp/server.py` | FastMCP server + tools + `main()`; ONLY mcp-importing file |
| `config.example.yaml` | dev-facing mirror of the bundled config template (frozen spec §6); the CLI copies the bundled `resources/` one |
| `prompts/vision-trigger.md` | dev-facing mirror of the bundled trigger (kept per frozen spec §6) |
| `integrations/claude-code/.mcp.json` + `integrations/codex/config.toml.snippet` | dev-facing mirrors of the bundled MCP snippets (kept per frozen spec §6) |
| `tests/helpers.py` | `FakeProvider`, `make_image` (no fixtures — plain importable helpers) |
| `tests/test_architecture.py` | enforces §4 red lines via AST scan |
| `tests/test_errors.py`, `test_schemas.py`, `test_preprocessing.py`, `test_provider_interface.py`, `test_openai_compat.py`, `test_gemini.py`, `test_config.py`, `test_observability.py`, `test_routing.py`, `test_vision_capability.py`, `test_bootstrap.py`, `test_mcp.py`, `test_setup.py` | per-module tests |

---

### Task 1: Project scaffold + architecture red-line test

**Files:**
- Create: `pyproject.toml`
- Create: `src/capability_bridge/__init__.py`, `src/capability_bridge/core/__init__.py`, `src/capability_bridge/providers/__init__.py`, `src/capability_bridge/transports/__init__.py`, `src/capability_bridge/transports/mcp/__init__.py`
- Test: `tests/test_architecture.py`

**Interfaces:**
- Consumes: nothing (foundation).
- Produces: an installable `capability_bridge` package; `uv run pytest` works; the architecture red-line test guards all later tasks.

- [ ] **Step 1: Write the architecture red-line test**

Create `tests/test_architecture.py`:

```python
import ast
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
CORE = PROJECT_ROOT / "src" / "capability_bridge" / "core"
PROVIDERS = PROJECT_ROOT / "src" / "capability_bridge" / "providers"

FORBIDDEN_ANYWHERE = {"mcp", "fastmcp", "anthropic", "openai"}


def _import_module_names(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _top_level(names: list[str]) -> set[str]:
    return {n.split(".")[0] for n in names}


def test_core_never_imports_mcp_clients_or_concrete_layers() -> None:
    for py in CORE.rglob("*.py"):
        names = _import_module_names(py)
        assert not (_top_level(names) & FORBIDDEN_ANYWHERE), (
            f"{py.relative_to(PROJECT_ROOT)} imports {_top_level(names) & FORBIDDEN_ANYWHERE}"
        )
        assert not any(
            n.startswith("capability_bridge.providers")
            or n.startswith("capability_bridge.transports")
            for n in names
        ), f"{py.relative_to(PROJECT_ROOT)} imports a concrete layer"


def test_providers_never_import_mcp_or_transports() -> None:
    for py in PROVIDERS.rglob("*.py"):
        names = _import_module_names(py)
        assert not (_top_level(names) & FORBIDDEN_ANYWHERE), (
            f"{py.relative_to(PROJECT_ROOT)} imports {_top_level(names) & FORBIDDEN_ANYWHERE}"
        )
        assert not any(n.startswith("capability_bridge.transports") for n in names), (
            f"{py.relative_to(PROJECT_ROOT)} imports transports"
        )


def test_core_and_providers_directories_exist() -> None:
    assert CORE.is_dir(), "core/ directory missing"
    assert PROVIDERS.is_dir(), "providers/ directory missing"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd d:/BTD/deepseek-vision && uv run pytest tests/test_architecture.py -v`
Expected: FAIL — `core` and `providers` directories don't exist yet (`FileNotFoundError` from `rglob`).

- [ ] **Step 3: Create the scaffold**

`pyproject.toml`:

```toml
[project]
name = "capability-bridge"
version = "0.1.0"
description = "A transport-agnostic model capability bridge. MCP is the first transport; Vision is the first capability."
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.7",
    "httpx>=0.27",
    "pillow>=10.0",
    "pyyaml>=6.0",
    "fastmcp>=2.0",
]

[project.scripts]
capability-bridge = "capability_bridge.transports.mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.hatch.build.targets.wheel]
packages = ["src/capability_bridge"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Create the four `__init__.py` files with an empty file (or a one-line docstring). Run `uv sync` to install deps.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_architecture.py -v`
Expected: PASS (constraint holds vacuously).

- [ ] **Step 5: Land the design spec + commit**

The design spec is already staged from the design phase. Commit it as its own commit (git identity must be set first):

```bash
git config user.name "your-name"
git config user.email "your-email"
git commit -m "docs: v0.1 design spec for capability-bridge"
```

---

### Task 2: Error taxonomy

**Files:**
- Create: `src/capability_bridge/core/errors/__init__.py`
- Test: `tests/test_errors.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `CapabilityError`, `ProviderError`, `AuthenticationError`, `RateLimitError`, `TimeoutError`, `ModelUnavailableError`, `UnsupportedInputError`, `InvalidResponseError`, and `is_fallback_error(exc) -> bool`. Later tasks import these exact names.

- [ ] **Step 1: Write the failing test**

Create `tests/test_errors.py`:

```python
import pytest

from capability_bridge.core.errors import (
    AuthenticationError,
    CapabilityError,
    InvalidResponseError,
    ModelUnavailableError,
    ProviderError,
    RateLimitError,
    TimeoutError,
    UnsupportedInputError,
    is_fallback_error,
)

PROVIDER_ERRORS = [
    AuthenticationError,
    RateLimitError,
    TimeoutError,
    ModelUnavailableError,
    UnsupportedInputError,
    InvalidResponseError,
]


def test_hierarchy() -> None:
    for cls in PROVIDER_ERRORS:
        assert issubclass(cls, ProviderError)
    assert issubclass(ProviderError, CapabilityError)


def test_fallback_classification() -> None:
    assert is_fallback_error(TimeoutError())
    assert is_fallback_error(RateLimitError())
    assert is_fallback_error(ModelUnavailableError())
    assert is_fallback_error(InvalidResponseError())
    assert not is_fallback_error(AuthenticationError())
    assert not is_fallback_error(UnsupportedInputError())
    assert not is_fallback_error(ValueError("unrelated"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: capability_bridge.core.errors`.

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/core/errors/__init__.py`:

```python
class CapabilityError(Exception):
    """Base error for capability-bridge."""


class ProviderError(CapabilityError):
    """A provider failed while handling a request."""


class AuthenticationError(ProviderError):
    """Credentials are invalid (e.g. HTTP 401). Never fallback."""


class RateLimitError(ProviderError):
    """Rate limited (e.g. HTTP 429). Fallback allowed."""


class TimeoutError(ProviderError):
    """The provider request timed out. Fallback allowed."""


class ModelUnavailableError(ProviderError):
    """The model/provider is unavailable or errored. Fallback allowed."""


class UnsupportedInputError(ProviderError):
    """The input is invalid (bad image, unsupported scheme). Never fallback."""


class InvalidResponseError(ProviderError):
    """The provider returned a response that failed schema checks. Retry/fallback allowed."""


#: Error types that should trigger retry/fallback.
_FALLBACK_ERRORS = (
    RateLimitError,
    TimeoutError,
    ModelUnavailableError,
    InvalidResponseError,
)


def is_fallback_error(exc: Exception) -> bool:
    """Return True if this error should trigger fallback to another provider."""
    return isinstance(exc, _FALLBACK_ERRORS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_errors.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/core/errors tests/test_errors.py
git commit -m "feat(core): error taxonomy with fallback classification"
```

---

### Task 3: Core result schemas

**Files:**
- Create: `src/capability_bridge/core/schemas/__init__.py`, `src/capability_bridge/core/schemas/result.py`
- Test: `tests/test_schemas.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `CapabilityResult(content: str, structured_data: dict|None, provider: str, model: str, latency_ms: int, warnings: list[str])`, plus `VisionResult(CapabilityResult)` and `OCRResult(CapabilityResult)`. Pydantic `BaseModel` — `result.model_dump()` used by the MCP layer later.

- [ ] **Step 1: Write the failing test**

Create `tests/test_schemas.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/core/schemas/result.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/core/schemas tests/test_schemas.py
git commit -m "feat(core): result schemas (CapabilityResult / VisionResult / OCRResult)"
```

---

### Task 4: Image preprocessing

**Files:**
- Create: `src/capability_bridge/core/preprocessing/__init__.py`, `src/capability_bridge/core/preprocessing/image.py`
- Test: `tests/test_preprocessing.py`

**Interfaces:**
- Consumes: `UnsupportedInputError`.
- Produces: `NormalizedImage(data: bytes, media_type: str, width: int, height: int)` and `ImagePreprocessor().normalize(image_input: str) -> NormalizedImage`. Accepts local path, `file://` URI, base64 data URI. Rejects http(s) with `UnsupportedInputError`. Resizes longest edge to ≤ 2048 and re-encodes as JPEG.

- [ ] **Step 1: Write the failing test**

Create `tests/test_preprocessing.py`:

```python
import base64

import pytest
from PIL import Image

from capability_bridge.core.errors import UnsupportedInputError
from capability_bridge.core.preprocessing.image import (
    MAX_EDGE,
    ImagePreprocessor,
    NormalizedImage,
)


def _make_image(tmp_path, size=(100, 50), fmt="PNG", name="img.png") -> str:
    img = Image.new("RGB", size, "red")
    p = tmp_path / name
    img.save(p, format=fmt)
    return str(p)


def test_local_path(tmp_path) -> None:
    norm = ImagePreprocessor().normalize(_make_image(tmp_path))
    assert isinstance(norm, NormalizedImage)
    assert norm.media_type == "image/jpeg"
    assert norm.width == 100
    assert norm.height == 50


def test_file_uri(tmp_path) -> None:
    p = tmp_path / "img.png"
    Image.new("RGB", (64, 64), "blue").save(p)
    norm = ImagePreprocessor().normalize(p.as_uri())
    assert norm.width == 64


def test_data_uri(tmp_path) -> None:
    path = _make_image(tmp_path, size=(32, 32))
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    uri = f"data:image/png;base64,{b64}"
    norm = ImagePreprocessor().normalize(uri)
    assert norm.width == 32


def test_oversized_image_resized(tmp_path) -> None:
    path = _make_image(tmp_path, size=(4000, 2000))
    norm = ImagePreprocessor().normalize(path)
    assert max(norm.width, norm.height) <= MAX_EDGE
    assert (norm.width, norm.height) == (2048, 1024)


def test_missing_file_rejected() -> None:
    with pytest.raises(UnsupportedInputError):
        ImagePreprocessor().normalize("does-not-exist.png")


def test_http_url_rejected() -> None:
    with pytest.raises(UnsupportedInputError):
        ImagePreprocessor().normalize("https://example.com/img.png")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_preprocessing.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/core/preprocessing/image.py`:

```python
from __future__ import annotations

import base64
import io
import pathlib
import urllib.parse
from dataclasses import dataclass

from PIL import Image

from capability_bridge.core.errors import UnsupportedInputError

MAX_EDGE = 2048
MAX_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class NormalizedImage:
    data: bytes
    media_type: str = "image/jpeg"
    width: int = 0
    height: int = 0


class ImagePreprocessor:
    """Validate, resize, compress and re-encode an image into a uniform NormalizedImage."""

    def normalize(self, image_input: str) -> NormalizedImage:
        raw = self._read_bytes(image_input)
        if len(raw) > MAX_BYTES:
            raise UnsupportedInputError(f"image exceeds {MAX_BYTES} bytes")
        img = self._open(raw)
        img = self._normalize_img(img)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return NormalizedImage(data=buf.getvalue(), width=img.width, height=img.height)

    def _read_bytes(self, image_input: str) -> bytes:
        if image_input.startswith("data:"):
            header, _, b64 = image_input.partition(",")
            if "base64" not in header:
                raise UnsupportedInputError("only base64 data URIs are supported")
            try:
                return base64.b64decode(b64)
            except Exception as exc:
                raise UnsupportedInputError(f"invalid base64 data URI: {exc}") from exc
        if image_input.lower().startswith(("http://", "https://")):
            raise UnsupportedInputError("remote image URLs are not supported in v0.1")
        if image_input.startswith("file://"):
            path = urllib.parse.urlparse(image_input).path
        else:
            path = image_input
        p = pathlib.Path(path)
        if not p.exists():
            raise UnsupportedInputError(f"image not found: {p}")
        return p.read_bytes()

    def _open(self, raw: bytes) -> Image.Image:
        try:
            return Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:
            raise UnsupportedInputError(f"cannot decode image: {exc}") from exc

    def _normalize_img(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        if max(w, h) > MAX_EDGE:
            scale = MAX_EDGE / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        return img
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_preprocessing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/core/preprocessing tests/test_preprocessing.py
git commit -m "feat(core): ImagePreprocessor -> NormalizedImage (resize/compress, no remote URLs)"
```

---

### Task 5: Provider interface + test helpers

**Files:**
- Create: `src/capability_bridge/core/providers/__init__.py`, `src/capability_bridge/core/providers/base.py`
- Create: `tests/helpers.py`, `tests/test_provider_interface.py`

**Interfaces:**
- Consumes: `NormalizedImage`, error classes.
- Produces: `CapabilitySet = dict[str, bool]`; `ModelRequest(capability, image, prompt=None)`; `ModelResponse(content, structured_data=None)`; `ModelProvider` ABC with `name: str`, `model: str`, `capabilities: CapabilitySet`, and `async invoke(request: ModelRequest) -> ModelResponse`. Also `tests/helpers.py` exposes `FakeProvider` and `make_image` for every later test.

- [ ] **Step 1: Write the failing test + helper**

Create `tests/helpers.py`:

```python
from PIL import Image

from capability_bridge.core.errors import (
    AuthenticationError,
    InvalidResponseError,
    ModelUnavailableError,
    RateLimitError,
    TimeoutError,
)
from capability_bridge.core.providers.base import ModelProvider, ModelRequest, ModelResponse


class FakeProvider(ModelProvider):
    """Deterministic provider for tests. behavior: ok|timeout|auth|rate|unavailable|invalid."""

    def __init__(self, name: str, model: str = "fake-model", capabilities=None, behavior: str = "ok") -> None:
        self.name = name
        self.model = model
        self.capabilities = capabilities if capabilities is not None else {"vision": True, "ocr": True}
        self.behavior = behavior
        self.calls = 0
        self.closed = False
        self.aclose_calls = 0
        self.last_request: ModelRequest | None = None

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        self.last_request = request  # lets tests assert prompt/capability reached the provider verbatim
        if self.behavior == "timeout":
            raise TimeoutError("provider timed out")
        if self.behavior == "auth":
            raise AuthenticationError("401 unauthorized")
        if self.behavior == "rate":
            raise RateLimitError("429 rate limited")
        if self.behavior == "unavailable":
            raise ModelUnavailableError("500 model unavailable")
        if self.behavior == "invalid":
            raise InvalidResponseError("response schema mismatch")
        return ModelResponse(content=f"result-from-{self.name}")

    async def aclose(self) -> None:
        self.aclose_calls += 1
        self.closed = True


def make_image(tmp_path, size=(100, 50), fmt="PNG", name="img.png") -> str:
    img = Image.new("RGB", size, "white")
    p = tmp_path / name
    img.save(p, format=fmt)
    return str(p)
```

Create `tests/test_provider_interface.py`:

```python
from helpers import FakeProvider, make_image

from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.providers.base import ModelRequest, ModelResponse


async def test_fake_provider_invocation(tmp_path) -> None:
    provider = FakeProvider(name="fake")
    image = ImagePreprocessor().normalize(make_image(tmp_path))
    response = await provider.invoke(ModelRequest(capability="vision", image=image))
    assert isinstance(response, ModelResponse)
    assert response.content == "result-from-fake"
    assert provider.calls == 1


async def test_fake_provider_capabilities_default() -> None:
    assert FakeProvider("x").capabilities == {"vision": True, "ocr": True}


async def test_fake_provider_aclose() -> None:
    provider = FakeProvider("fake")
    await provider.aclose()
    assert provider.closed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_provider_interface.py -v`
Expected: FAIL with `ModuleNotFoundError` (`capability_bridge.core.providers.base` missing).

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/core/providers/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from capability_bridge.core.preprocessing.image import NormalizedImage

CapabilitySet = dict[str, bool]


@dataclass(frozen=True)
class ModelRequest:
    capability: str
    image: NormalizedImage
    prompt: str | None = None


@dataclass(frozen=True)
class ModelResponse:
    content: str
    structured_data: dict | None = None


class ModelProvider(ABC):
    """Contract for a concrete model adapter. Implementations live in providers/ (outside core)."""

    name: str
    model: str
    capabilities: CapabilitySet

    @abstractmethod
    async def invoke(self, request: ModelRequest) -> ModelResponse:
        ...

    async def aclose(self) -> None:
        """Release resources this provider OWNS. Default no-op; adapters close only
        clients they created themselves — injected clients stay open (external owns them)."""
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_provider_interface.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/core/providers tests/helpers.py tests/test_provider_interface.py
git commit -m "feat(core): ModelProvider ABC + ModelRequest/ModelResponse + test helpers"
```

---

### Task 6: OpenAI-compatible provider adapter

**Files:**
- Create: `src/capability_bridge/providers/openai_compat.py`
- Test: `tests/test_openai_compat.py`

**Interfaces:**
- Consumes: `ModelProvider`/`ModelRequest`/`ModelResponse`, error classes, `NormalizedImage`.
- Produces: `OpenAICompatProvider(*, base_url, api_key, model, name, capabilities=None, client: httpx.AsyncClient|None = None)` — sends an OpenAI `chat/completions` payload with an `image_url` data-URI and maps HTTP errors onto the taxonomy.

- [ ] **Step 1: Write the failing test**

Create `tests/test_openai_compat.py`:

```python
import json

import httpx
import pytest

from capability_bridge.core.errors import (
    AuthenticationError,
    InvalidResponseError,
    ModelUnavailableError,
    RateLimitError,
    TimeoutError,
)
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.providers.base import ModelRequest
from capability_bridge.providers.openai_compat import OpenAICompatProvider
from helpers import make_image


def _provider(handler, *, model="qwen3-vl-flash") -> OpenAICompatProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return OpenAICompatProvider(
        base_url="https://example.com/v1", api_key="test-key", model=model,
        name="qwen", client=client,
    )


@pytest.fixture
def image(tmp_path):
    return ImagePreprocessor().normalize(make_image(tmp_path))


async def test_success_payload_and_content(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "qwen3-vl-flash"
        content_parts = body["messages"][0]["content"]
        assert content_parts[1]["type"] == "image_url"
        assert content_parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"choices": [{"message": {"content": "a cat"}}]})

    response = await _provider(handler).invoke(ModelRequest(capability="vision", image=image))
    assert response.content == "a cat"


async def test_explicit_prompt_is_forwarded_unchanged(image) -> None:
    sent = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent["prompt"] = body["messages"][0]["content"][0]["text"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    prompt = "Analyze hierarchy, spacing, typography, and color as a senior product designer."
    await _provider(handler).invoke(ModelRequest(capability="vision", image=image, prompt=prompt))
    assert sent["prompt"] == prompt  # explicit prompt wins over _DEFAULT_PROMPTS, verbatim


async def test_401_maps_to_authentication(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(AuthenticationError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_429_maps_to_rate_limit(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "slow down"})

    with pytest.raises(RateLimitError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_500_maps_to_unavailable(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(ModelUnavailableError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_timeout_maps_to_timeout(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(TimeoutError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_malformed_response_maps_to_invalid(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    with pytest.raises(InvalidResponseError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_aclose_closes_own_client() -> None:
    # NOTE: construct WITHOUT an injected client so the provider OWNS it and aclose() must close it.
    # (Reusing _provider(handler) here would inject a client -> _owns_client=False -> the impl
    # intentionally does NOT close it; that case is covered by the next test.)
    provider = OpenAICompatProvider(
        base_url="https://example.com/v1", api_key="test-key", model="qwen3-vl-flash", name="qwen"
    )
    assert not provider._client.is_closed
    await provider.aclose()
    assert provider._client.is_closed


async def test_aclose_leaves_injected_client_open() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})))
    provider = OpenAICompatProvider(
        base_url="https://example.com/v1", api_key="k", model="m", name="qwen", client=client
    )
    await provider.aclose()
    assert not client.is_closed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_openai_compat.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/providers/openai_compat.py`:

```python
from __future__ import annotations

import base64

import httpx

from capability_bridge.core.errors import (
    AuthenticationError,
    InvalidResponseError,
    ModelUnavailableError,
    RateLimitError,
    TimeoutError,
)
from capability_bridge.core.providers.base import ModelProvider, ModelRequest, ModelResponse

_DEFAULT_PROMPTS = {
    "vision": "Describe this image accurately and concisely.",
    "ocr": "Extract all text from this image.",
}


class OpenAICompatProvider(ModelProvider):
    """Adapter for any OpenAI-compatible /chat/completions vision endpoint
    (GLM, Qwen, Kimi, OpenRouter, SiliconFlow, self-hosted...). NOTE: MiniMax vision is NOT
    OpenAI-compatible (own VL protocol) — it needs a dedicated provider type, out of v0.1 scope."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        name: str,
        capabilities: dict[str, bool] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.name = name
        self.capabilities = capabilities if capabilities is not None else {"vision": True, "ocr": True}
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=120.0)  # Level 1: > policy timeout so routing bounds the request

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _payload(self, request: ModelRequest) -> dict:
        data_uri = f"data:{request.image.media_type};base64,{base64.b64encode(request.image.data).decode()}"
        prompt = request.prompt or _DEFAULT_PROMPTS.get(request.capability, _DEFAULT_PROMPTS["vision"])
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
        }

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = await self._client.post(url, json=self._payload(request), headers=headers)
        except httpx.TimeoutException as exc:
            raise TimeoutError("provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise ModelUnavailableError(f"transport error: {exc}") from exc

        if response.status_code == 401:
            raise AuthenticationError("401: invalid api key")
        if response.status_code == 429:
            raise RateLimitError("429: rate limited")
        if response.status_code >= 400:
            raise ModelUnavailableError(f"{response.status_code}: {response.text[:200]}")

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise InvalidResponseError(f"unexpected response shape: {exc}") from exc
        if not isinstance(content, str) or not content.strip():
            raise InvalidResponseError("empty content in response")
        return ModelResponse(content=content)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_openai_compat.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/providers tests/test_openai_compat.py
git commit -m "feat(providers): OpenAI-compatible adapter with error taxonomy mapping"
```

---

### Task 7: Gemini provider adapter

**Files:**
- Create: `src/capability_bridge/providers/gemini.py`
- Test: `tests/test_gemini.py`

**Interfaces:**
- Consumes: same as Task 6.
- Produces: `GeminiProvider(*, api_key, model, name="gemini", capabilities=None, client=None)` — calls `generateContent` with `inline_data` (base64) and maps errors onto the taxonomy.

- [ ] **Step 1: Write the failing test**

Create `tests/test_gemini.py`:

```python
import json

import httpx
import pytest

from capability_bridge.core.errors import AuthenticationError, InvalidResponseError, RateLimitError
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.providers.base import ModelRequest
from capability_bridge.providers.gemini import GeminiProvider
from helpers import make_image


def _provider(handler, *, model="gemini-2.5-flash") -> GeminiProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return GeminiProvider(api_key="test-key", model=model, name="gemini", client=client)


@pytest.fixture
def image(tmp_path):
    return ImagePreprocessor().normalize(make_image(tmp_path))


async def test_success_payload_and_content(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "generateContent" in str(request.url)
        assert request.url.params["key"] == "test-key"
        body = json.loads(request.content)
        parts = body["contents"][0]["parts"]
        assert parts[1]["inline_data"]["mime_type"] == "image/jpeg"
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "a dog"}]}}]},
        )

    response = await _provider(handler).invoke(ModelRequest(capability="vision", image=image))
    assert response.content == "a dog"


async def test_explicit_prompt_is_forwarded_unchanged(image) -> None:
    sent = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent["prompt"] = body["contents"][0]["parts"][0]["text"]
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "x"}]}}]},
        )

    prompt = "Analyze composition, light, color, and mood as an art critic."
    await _provider(handler).invoke(ModelRequest(capability="vision", image=image, prompt=prompt))
    assert sent["prompt"] == prompt  # explicit prompt wins over _DEFAULT_PROMPTS, verbatim


async def test_401_maps_to_authentication(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "denied"})

    with pytest.raises(AuthenticationError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_429_maps_to_rate_limit(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "quota"})

    with pytest.raises(RateLimitError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_malformed_response_maps_to_invalid(image) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"nope": True})

    with pytest.raises(InvalidResponseError):
        await _provider(handler).invoke(ModelRequest(capability="vision", image=image))


async def test_aclose_closes_own_client() -> None:
    # NOTE: construct WITHOUT an injected client so the provider OWNS it and aclose() must close it.
    provider = GeminiProvider(api_key="test-key", model="gemini-2.5-flash", name="gemini")
    assert not provider._client.is_closed
    await provider.aclose()
    assert provider._client.is_closed


async def test_aclose_leaves_injected_client_open() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})))
    provider = GeminiProvider(api_key="k", model="m", name="gemini", client=client)
    await provider.aclose()
    assert not client.is_closed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gemini.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/providers/gemini.py`:

```python
from __future__ import annotations

import base64

import httpx

from capability_bridge.core.errors import (
    AuthenticationError,
    InvalidResponseError,
    ModelUnavailableError,
    RateLimitError,
    TimeoutError,
)
from capability_bridge.core.providers.base import ModelProvider, ModelRequest, ModelResponse

_DEFAULT_PROMPTS = {
    "vision": "Describe this image accurately and concisely.",
    "ocr": "Extract all text from this image.",
}


class GeminiProvider(ModelProvider):
    """Adapter for Google Gemini generateContent (its own protocol)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        name: str = "gemini",
        capabilities: dict[str, bool] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.name = name
        self.capabilities = capabilities if capabilities is not None else {"vision": True, "ocr": True}
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=120.0)  # Level 1: > policy timeout so routing bounds the request

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def invoke(self, request: ModelRequest) -> ModelResponse:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        prompt = request.prompt or _DEFAULT_PROMPTS.get(request.capability, _DEFAULT_PROMPTS["vision"])
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": request.image.media_type,
                                "data": base64.b64encode(request.image.data).decode(),
                            }
                        },
                    ]
                }
            ]
        }
        params = {"key": self.api_key}
        try:
            response = await self._client.post(url, json=body, params=params)
        except httpx.TimeoutException as exc:
            raise TimeoutError("provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise ModelUnavailableError(f"transport error: {exc}") from exc

        if response.status_code in (401, 403):
            raise AuthenticationError(f"{response.status_code}: invalid api key")
        if response.status_code == 429:
            raise RateLimitError("429: rate limited")
        if response.status_code >= 400:
            raise ModelUnavailableError(f"{response.status_code}: {response.text[:200]}")

        try:
            parts = response.json()["candidates"][0]["content"]["parts"]
            content = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise InvalidResponseError(f"unexpected response shape: {exc}") from exc
        if not content.strip():
            raise InvalidResponseError("empty content in response")
        return ModelResponse(content=content)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_gemini.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/providers tests/test_gemini.py
git commit -m "feat(providers): Gemini adapter with error taxonomy mapping"
```

---

### Task 8: Registry config loading + config.example.yaml

**Files:**
- Create: `src/capability_bridge/core/registry/__init__.py`, `src/capability_bridge/core/registry/config.py`
- Create: `config.example.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: pydantic, yaml.
- Produces: `Config`, `PolicyConfig`, `ProviderConfig`, `ModelEntry`, `RoutingConfig`; `load_config(path=None) -> Config`; `resolve_config_path() -> str | None`; `api_key_for(cfg: ProviderConfig) -> str`. `Config.providers: dict[str, ProviderConfig]`, `Config.models: dict[str, ModelEntry]`, `Config.routing: RoutingConfig` with `.vision` / `.ocr` lists of model keys.

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/core/registry/config.py`:

```python
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
        if pathlib.Path(candidate).exists():
            return candidate
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
```

Create `config.example.yaml` (project root):

```yaml
# Copy to config.yaml, set your API keys as env vars, then:
#   capability-bridge            (installed CLI; from source during dev: uv run capability-bridge)
#
# The default is intentionally ONE provider, so a new user sets a single key and gets a first
# result immediately (Product DoD: "one key -> first success"). Uncomment the fallback examples
# at the bottom to enable automatic failover.

policy:
  timeout_seconds: 60   # Level 1 (live E2E 2026-08-13): 真实 UI 截图 + 设计评审约需 25s,15s 默认太短
  max_retries: 1

providers:
  qwen:
    type: openai_compatible
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: QWEN_API_KEY

models:
  qwen-vl-flash:
    provider: qwen
    model: qwen3-vl-flash
    capabilities: [vision, ocr]

routing:
  vision: [qwen-vl-flash]
  ocr: [qwen-vl-flash]

# ---- Optional fallbacks (advanced) -----------------------------------------
# Uncomment a second provider, add it to the routing lists below, and fallback kicks in
# automatically. Each enabled provider needs its own API key env var.
#
# NOTE: MiniMax has TWO vision paths (2026-08-14):
#  - MiniMax OWN API (understand_image / Token Plan) is NOT OpenAI-compatible -> needs a dedicated
#    provider type, future scope (v0.2).
#  - MiniMax/MiniMax-M3 HOSTED ON DashScope IS OpenAI-compatible -> VERIFIED via the existing
#    openai_compatible adapter (uses the DashScope base_url + the same DashScope key as qwen;
#    requires activating MiniMax-M3 in the Bailian console).
#
# providers:
#   glm:
#     type: openai_compatible
#     base_url: https://open.bigmodel.cn/api/paas/v4
#     api_key_env: GLM_API_KEY
#   kimi:
#     type: openai_compatible
#     base_url: https://api.moonshot.cn/v1
#     api_key_env: KIMI_API_KEY
#   minimax:
#     type: openai_compatible
#     base_url: https://dashscope.aliyuncs.com/compatible-mode/v1   # hosted on DashScope
#     api_key_env: QWEN_API_KEY                                    # same key, needs activation
#   gemini:
#     type: gemini
#     api_key_env: GEMINI_API_KEY
#
# models:
#   glm-vl-flash:
#     provider: glm
#     model: glm-4.6v-flash
#     capabilities: [vision, ocr]
#   kimi-vl:
#     provider: kimi
#     model: kimi-k2.6
#     capabilities: [vision, ocr]
#   minimax-m3:
#     provider: minimax
#     model: MiniMax/MiniMax-M3
#     capabilities: [vision]
#   gemini-flash:
#     provider: gemini
#     model: gemini-2.5-flash
#     capabilities: [vision, ocr]
#
# routing:
#   vision: [qwen-vl-flash, glm-vl-flash, kimi-vl, minimax-m3, gemini-flash]
#   ocr: [qwen-vl-flash, glm-vl-flash]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/core/registry config.example.yaml tests/test_config.py
git commit -m "feat(core): registry config loading + config.example.yaml"
```

---

### Task 9: Structured observability logging

**Files:**
- Create: `src/capability_bridge/core/observability/__init__.py`, `src/capability_bridge/core/observability/logging.py`
- Test: `tests/test_observability.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ALLOWED_FIELDS` tuple; `setup_logging(level) -> None`; `log_call(**fields) -> None` (drops any field not in the whitelist — the privacy gate).

- [ ] **Step 1: Write the failing test**

Create `tests/test_observability.py`:

```python
import json
import logging

from capability_bridge.core.observability.logging import ALLOWED_FIELDS, log_call, setup_logging


def test_log_call_whitelist(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="capability_bridge"):
        log_call(
            request_id="r1",
            capability="vision",
            provider="qwen",
            model="qwen3-vl-flash",
            latency_ms=5,
            success=True,
            fallback_count=0,
            secret_prompt="NEVER log me",
            image_bytes="NEVER log me either",
        )
    record = json.loads(caplog.records[-1].getMessage())
    assert set(record.keys()) <= set(ALLOWED_FIELDS)
    assert "NEVER log me" not in caplog.text
    assert record["request_id"] == "r1"
    assert record["success"] is True


def test_setup_logging_installs_handler() -> None:
    setup_logging()
    assert logging.getLogger("capability_bridge").handlers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_observability.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/core/observability/logging.py`:

```python
from __future__ import annotations

import json
import logging

#: The ONLY fields a call may log. Anything else is dropped at the gate (privacy).
ALLOWED_FIELDS = (
    "request_id",
    "capability",
    "provider",
    "model",
    "latency_ms",
    "success",
    "error_type",
    "fallback_count",
)


def setup_logging(level: int = logging.INFO) -> None:
    logger = logging.getLogger("capability_bridge")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(level)


def log_call(**fields) -> None:
    record = {key: fields[key] for key in ALLOWED_FIELDS if key in fields}
    logging.getLogger("capability_bridge").info(json.dumps(record, ensure_ascii=False))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_observability.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/core/observability tests/test_observability.py
git commit -m "feat(core): structured logging with privacy whitelist"
```

---

### Task 10: Routing policy (ordered fallback + retry)

**Files:**
- Create: `src/capability_bridge/core/routing/__init__.py`, `src/capability_bridge/core/routing/policy.py`
- Test: `tests/test_routing.py`

**Interfaces:**
- Consumes: `ModelProvider`, `ModelRequest`, `CapabilityResult`, error classes + `is_fallback_error`, `log_call`.
- Produces: `RoutingPolicy(providers: list[ModelProvider], timeout_seconds: float = 15.0, max_retries: int = 1, request_id: str = "-")` with `async execute(request: ModelRequest, *, request_id: str | None = None) -> RoutedResponse`. Retries each provider up to `1 + max_retries` times on fallback-able errors; on Authentication/UnsupportedInput raises immediately; falls to the next provider otherwise; raises the last error when exhausted. **Latency semantics (locked at Checkpoint 1):** every attempt log line carries that attempt's OWN latency (measured per attempt, so the routing log stays per-provider data for the future dynamic router); `RoutedResponse.latency_ms` is the END-TO-END total (from `execute()` start to the successful return) — that is what the user perceives and what `VisionResult.latency_ms` reports.

- [ ] **Step 1: Write the failing test**

Create `tests/test_routing.py`:

```python
import asyncio
import json
import logging

import pytest

from capability_bridge.core.errors import AuthenticationError, ModelUnavailableError
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.providers.base import ModelRequest
from capability_bridge.core.routing.policy import RoutingPolicy, RoutedResponse
from helpers import FakeProvider, make_image


def _req(tmp_path, capability: str = "vision") -> ModelRequest:
    return ModelRequest(capability=capability, image=ImagePreprocessor().normalize(make_image(tmp_path)))


async def test_success_on_first_provider(tmp_path) -> None:
    p1, p2 = FakeProvider("a"), FakeProvider("b")
    result = await RoutingPolicy([p1, p2]).execute(_req(tmp_path))
    assert isinstance(result, RoutedResponse)
    assert result.provider == "a"
    assert result.response.content == "result-from-a"
    assert p2.calls == 0


async def test_timeout_falls_back(tmp_path) -> None:
    p1, p2 = FakeProvider("a", behavior="timeout"), FakeProvider("b")
    result = await RoutingPolicy([p1, p2]).execute(_req(tmp_path))
    assert result.provider == "b"
    assert result.response.content == "result-from-b"
    assert any("falling back" in w for w in result.warnings)


async def test_auth_does_not_fallback(tmp_path) -> None:
    p1, p2 = FakeProvider("a", behavior="auth"), FakeProvider("b")
    with pytest.raises(AuthenticationError):
        await RoutingPolicy([p1, p2]).execute(_req(tmp_path))
    assert p2.calls == 0


async def test_retry_then_fallback(tmp_path) -> None:
    p1, p2 = FakeProvider("a", behavior="timeout"), FakeProvider("b")
    result = await RoutingPolicy([p1, p2], max_retries=1).execute(_req(tmp_path))
    assert result.provider == "b"
    assert p1.calls == 2  # 1 initial attempt + 1 retry


async def test_all_fail_raises_last_error(tmp_path) -> None:
    p1, p2 = FakeProvider("a", behavior="unavailable"), FakeProvider("b", behavior="unavailable")
    with pytest.raises(ModelUnavailableError):
        await RoutingPolicy([p1, p2]).execute(_req(tmp_path))


async def test_every_attempt_is_logged(caplog, tmp_path) -> None:
    p1, p2 = FakeProvider("a", behavior="timeout"), FakeProvider("b")
    policy = RoutingPolicy([p1, p2], max_retries=1)
    with caplog.at_level(logging.INFO, logger="capability_bridge"):
        await policy.execute(_req(tmp_path))
    lines = [json.loads(r.getMessage()) for r in caplog.records]
    failures = [line for line in lines if not line["success"]]
    successes = [line for line in lines if line["success"]]
    assert len(failures) == 2  # provider a: attempt 1 + retry
    assert len(successes) == 1  # provider b success
    assert all(line["provider"] == "a" for line in failures)
    assert failures[0]["fallback_count"] == 0
    assert successes[0]["fallback_count"] == 1


async def test_attempt_log_latency_is_per_attempt_not_cumulative(caplog, tmp_path) -> None:
    """Attempt logs carry each provider's OWN latency; the result carries the end-to-end total."""

    class SlowProvider(FakeProvider):
        def __init__(self, name: str, behavior: str = "ok", delay: float = 0.05) -> None:
            super().__init__(name, behavior=behavior)
            self.delay = delay

        async def invoke(self, request):
            await asyncio.sleep(self.delay)
            return await super().invoke(request)

    p1, p2 = SlowProvider("a", behavior="timeout"), SlowProvider("b")
    policy = RoutingPolicy([p1, p2], max_retries=1)
    with caplog.at_level(logging.INFO, logger="capability_bridge"):
        result = await policy.execute(_req(tmp_path))
    lines = [json.loads(r.getMessage()) for r in caplog.records]
    success = next(line for line in lines if line["success"])
    assert success["provider"] == "b"
    # b ran only its own ~50ms; its log line must NOT include provider a's timeout time.
    assert success["latency_ms"] < 100, "fallback provider's log leaked cumulative latency"
    # end-to-end total accumulates a(50ms) + retry(50ms) + b(50ms) >> b's own attempt.
    assert result.latency_ms > success["latency_ms"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_routing.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/core/routing/policy.py`:

```python
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from capability_bridge.core.errors import (
    CapabilityError,
    ProviderError,
    TimeoutError,
    is_fallback_error,
)
from capability_bridge.core.observability.logging import log_call
from capability_bridge.core.providers.base import ModelProvider, ModelRequest, ModelResponse


@dataclass
class RoutedResponse:
    """Routing answers ONLY 'who succeeded'. Capability output shape is the capability layer's job."""

    response: ModelResponse
    provider: str
    model: str
    latency_ms: int
    warnings: list[str] = field(default_factory=list)


class RoutingPolicy:
    """Ordered fallback: try providers in order, retry transient errors, never fallback on hard errors.
    Records ONE structured log line per provider attempt (success and failure alike)."""

    def __init__(
        self,
        providers: list[ModelProvider],
        timeout_seconds: float = 15.0,
        max_retries: int = 1,
        request_id: str = "-",
    ) -> None:
        self.providers = providers
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.request_id = request_id

    async def execute(self, request: ModelRequest, *, request_id: str | None = None) -> RoutedResponse:
        request_id = request_id or self.request_id
        started = time.monotonic()
        warnings: list[str] = []
        fallback_count = 0
        last_error: Exception | None = None

        for index, provider in enumerate(self.providers):
            for _ in range(1 + self.max_retries):
                attempt_started = time.monotonic()  # per-attempt latency (feeds the routing log)
                try:
                    response = await asyncio.wait_for(provider.invoke(request), timeout=self.timeout_seconds)
                    log_call(
                        request_id=request_id,
                        capability=request.capability,
                        provider=provider.name,
                        model=provider.model,
                        latency_ms=int((time.monotonic() - attempt_started) * 1000),
                        success=True,
                        fallback_count=fallback_count,
                    )
                    return RoutedResponse(
                        response=response,
                        provider=provider.name,
                        model=provider.model,
                        latency_ms=int((time.monotonic() - started) * 1000),  # end-to-end total
                        warnings=warnings,
                    )
                except asyncio.TimeoutError as exc:
                    last_error = TimeoutError(str(exc))
                except ProviderError as exc:
                    last_error = exc
                except Exception as exc:  # pragma: no cover - defensive
                    last_error = exc
                log_call(
                    request_id=request_id,
                    capability=request.capability,
                    provider=provider.name,
                    model=provider.model,
                    latency_ms=int((time.monotonic() - attempt_started) * 1000),
                    success=False,
                    error_type=type(last_error).__name__,
                    fallback_count=fallback_count,
                )
                if not (isinstance(last_error, ProviderError) and is_fallback_error(last_error)):
                    break  # hard error: no retry, no fallback

            if isinstance(last_error, ProviderError) and is_fallback_error(last_error) and index < len(self.providers) - 1:
                warnings.append(
                    f"{provider.name}/{provider.model} failed ({type(last_error).__name__}); falling back"
                )
                fallback_count += 1
                continue

            raise last_error

        raise CapabilityError("no providers configured for capability")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_routing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/core/routing tests/test_routing.py
git commit -m "feat(core): routing policy with ordered fallback + retry + error classification"
```

---

### Task 11: Vision capability

**Files:**
- Create: `src/capability_bridge/core/capabilities/__init__.py`, `src/capability_bridge/core/capabilities/vision.py`
- Test: `tests/test_vision_capability.py`

**Interfaces:**
- Consumes: `ImagePreprocessor`, `RoutingPolicy`, `ModelRequest`, error classes.
- Produces: `VisionCapability(preprocessor: ImagePreprocessor, policies: dict[str, RoutingPolicy])` with `async analyze(image_input, prompt=None, task="general") -> CapabilityResult` and `async ocr(image_input) -> CapabilityResult`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_vision_capability.py`:

```python
import pytest

from capability_bridge.core.capabilities.vision import VisionCapability
from capability_bridge.core.errors import UnsupportedInputError
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.routing.policy import RoutingPolicy
from capability_bridge.core.schemas.result import VisionResult, OCRResult
from helpers import FakeProvider, make_image


def _capability() -> VisionCapability:
    policy = RoutingPolicy([FakeProvider("qwen")], timeout_seconds=5)
    return VisionCapability(ImagePreprocessor(), {"vision": policy, "ocr": policy})


async def test_analyze_returns_vision_result(tmp_path) -> None:
    result = await _capability().analyze(make_image(tmp_path), prompt="what is this?")
    assert isinstance(result, VisionResult)
    assert result.content == "result-from-qwen"
    assert result.provider == "qwen"


async def test_ocr_returns_ocr_result(tmp_path) -> None:
    result = await _capability().ocr(make_image(tmp_path))
    assert isinstance(result, OCRResult)
    assert result.content == "result-from-qwen"


async def test_missing_file_propagates_unsupported(tmp_path) -> None:
    with pytest.raises(UnsupportedInputError):
        await _capability().analyze("missing/file.png")


async def test_aclose_closes_providers() -> None:
    policy = RoutingPolicy([FakeProvider("qwen")], timeout_seconds=5)
    capability = VisionCapability(ImagePreprocessor(), {"vision": policy, "ocr": policy})
    await capability.aclose()
    assert policy.providers[0].closed is True
    assert policy.providers[0].aclose_calls == 1


async def test_aclose_closes_shared_provider_once() -> None:
    shared = FakeProvider("qwen")
    vision_policy = RoutingPolicy([shared], timeout_seconds=5)
    ocr_policy = RoutingPolicy([shared], timeout_seconds=5)
    capability = VisionCapability(ImagePreprocessor(), {"vision": vision_policy, "ocr": ocr_policy})
    await capability.aclose()
    assert shared.aclose_calls == 1


async def test_unsupported_task_rejected(tmp_path) -> None:
    with pytest.raises(UnsupportedInputError, match="unsupported vision task"):
        await _capability().analyze(make_image(tmp_path), task="ui_review")


async def test_prompt_reaches_provider_unchanged(tmp_path) -> None:
    """End-to-end fidelity: the prompt the main model builds is exactly what the provider receives."""
    provider = FakeProvider("qwen")
    policy = RoutingPolicy([provider], timeout_seconds=5)
    capability = VisionCapability(ImagePreprocessor(), {"vision": policy, "ocr": policy})
    prompt = "Analyze hierarchy, spacing, typography, and color as a senior product designer."
    await capability.analyze(make_image(tmp_path), prompt=prompt)
    assert provider.last_request is not None
    assert provider.last_request.prompt == prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_vision_capability.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/core/capabilities/vision.py`:

```python
from __future__ import annotations

import uuid

from capability_bridge.core.errors import UnsupportedInputError
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.providers.base import ModelRequest
from capability_bridge.core.routing.policy import RoutingPolicy
from capability_bridge.core.schemas.result import VisionResult, OCRResult


class VisionCapability:
    """Capability layer: 'what to do'. Routing answers 'who did it'; this layer shapes the result."""

    def __init__(self, preprocessor: ImagePreprocessor, policies: dict[str, RoutingPolicy]) -> None:
        self._preprocessor = preprocessor
        self._policies = policies

    async def analyze(self, image_input: str, prompt: str | None = None, task: str = "general") -> VisionResult:
        # v0.1 ships one task profile; reject unknown values loudly instead of silently ignoring
        # them (otherwise task="ui_review" would "look like it works" until its real semantics arrive).
        if task != "general":
            raise UnsupportedInputError(f"unsupported vision task: {task}; v0.1 supports only 'general'")
        normalized = self._preprocessor.normalize(image_input)
        request = ModelRequest(capability="vision", image=normalized, prompt=prompt)
        routed = await self._policies["vision"].execute(request, request_id=str(uuid.uuid4()))
        return VisionResult(
            content=routed.response.content,
            structured_data=routed.response.structured_data,
            provider=routed.provider,
            model=routed.model,
            latency_ms=routed.latency_ms,  # end-to-end total (per-attempt latencies live in the routing log)
            warnings=routed.warnings,
        )

    async def ocr(self, image_input: str) -> OCRResult:
        normalized = self._preprocessor.normalize(image_input)
        request = ModelRequest(capability="ocr", image=normalized)
        routed = await self._policies["ocr"].execute(request, request_id=str(uuid.uuid4()))
        return OCRResult(
            content=routed.response.content,
            structured_data=routed.response.structured_data,
            provider=routed.provider,
            model=routed.model,
            latency_ms=routed.latency_ms,  # end-to-end total (per-attempt latencies live in the routing log)
            warnings=routed.warnings,
        )

    async def aclose(self) -> None:
        """Release every provider held by this capability's routing policies, each exactly once.

        A single provider instance can be shared across policies (one vision+ocr model appears in
        both routing lists), so dedupe by identity before closing.
        """
        seen: set[int] = set()
        for policy in self._policies.values():
            for provider in policy.providers:
                if id(provider) in seen:
                    continue
                seen.add(id(provider))
                await provider.aclose()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_vision_capability.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/core/capabilities tests/test_vision_capability.py
git commit -m "feat(core): VisionCapability (analyze / ocr)"
```

---

### Task 12: Bootstrap (composition root)

**Files:**
- Create: `src/capability_bridge/bootstrap.py`
- Test: `tests/test_bootstrap.py`

**Interfaces:**
- Consumes: `Config`/`load_config`/`api_key_for`/`resolve_config_path`, concrete `OpenAICompatProvider` / `GeminiProvider`, `VisionCapability`, `ImagePreprocessor`, `RoutingPolicy`.
- Produces: `build_capability(config: Config) -> VisionCapability` and `build_from_path(config_path: str | None = None) -> VisionCapability`. This is the ONLY place concrete providers are instantiated; core never sees them.

- [ ] **Step 1: Write the failing test**

Create `tests/test_bootstrap.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_bootstrap.py -v`
Expected: FAIL with `ModuleNotFoundError: capability_bridge.bootstrap`.

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/bootstrap.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_bootstrap.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/bootstrap.py tests/test_bootstrap.py
git commit -m "feat: bootstrap composition root (config -> providers -> routing -> capability)"
```

---

### Task 13: MCP transport

**Files:**
- Create: `src/capability_bridge/transports/mcp/server.py`
- Test: `tests/test_mcp.py`

**Interfaces:**
- Consumes: `build_from_path`, `VisionCapability`, `resolve_config_path`.
- Produces: `create_server(capability: VisionCapability) -> FastMCP` (tools `vision_analyze`, `vision_ocr`) and `main() -> None` (console script `capability-bridge`). **Only file that imports fastmcp/mcp.**

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp.py`:

```python
from fastmcp import Client

from capability_bridge.core.capabilities.vision import VisionCapability
from capability_bridge.core.preprocessing.image import ImagePreprocessor
from capability_bridge.core.routing.policy import RoutingPolicy
from capability_bridge.transports.mcp.server import create_server
from helpers import FakeProvider, make_image


def _server() -> object:
    policy = RoutingPolicy([FakeProvider("qwen")], timeout_seconds=5)
    capability = VisionCapability(ImagePreprocessor(), {"vision": policy, "ocr": policy})
    return create_server(capability)


async def test_tools_exposed() -> None:
    async with Client(_server()) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert {"vision_analyze", "vision_ocr"} <= names


async def test_vision_analyze_call(tmp_path) -> None:
    async with Client(_server()) as client:
        result = await client.call_tool(
            "vision_analyze", {"image": make_image(tmp_path), "prompt": "describe this"}
        )
        assert "result-from-qwen" in str(result.content)


async def test_prompt_passes_through_mcp_to_provider_unchanged(tmp_path) -> None:
    """Checkpoint 3: full-chain fidelity — MCP tool -> VisionCapability -> RoutingPolicy ->
    FakeProvider.last_request.prompt must be byte-identical to what the tool was given."""
    provider = FakeProvider("qwen")
    policy = RoutingPolicy([provider], timeout_seconds=5)
    capability = VisionCapability(ImagePreprocessor(), {"vision": policy, "ocr": policy})
    prompt = "Analyze hierarchy, spacing, typography, and color as a senior product designer."
    async with Client(create_server(capability)) as client:
        await client.call_tool("vision_analyze", {"image": make_image(tmp_path), "prompt": prompt})
    assert provider.last_request is not None
    assert provider.last_request.prompt == prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp.py -v`
Expected: FAIL with `ModuleNotFoundError: capability_bridge.transports.mcp`.

- [ ] **Step 3: Write minimal implementation**

Create `src/capability_bridge/transports/mcp/server.py`:

```python
from __future__ import annotations

import sys

from fastmcp import FastMCP

from capability_bridge.bootstrap import build_from_path
from capability_bridge.core.capabilities.vision import VisionCapability
from capability_bridge.core.registry.config import resolve_config_path


def create_server(capability: VisionCapability) -> FastMCP:
    mcp = FastMCP("capability-bridge")

    @mcp.tool()
    async def vision_analyze(image: str, prompt: str | None = None, task: str = "general") -> dict:
        """Analyze an image with a vision model and return a text description.

        Args:
            image: local path, file:// URI, or base64 data URI (no remote URLs in v0.1).
            prompt: optional question to focus the analysis.
            task: v0.1 only supports "general".
        """
        result = await capability.analyze(image, prompt=prompt, task=task)
        return result.model_dump()

    @mcp.tool()
    async def vision_ocr(image: str) -> dict:
        """Extract text (OCR) from an image.

        Args:
            image: local path, file:// URI, or base64 data URI.
        """
        result = await capability.ocr(image)
        return result.model_dump()

    return mcp


def main() -> None:
    config_path = resolve_config_path()
    if config_path is None:
        print(
            "error: no config found. Copy config.example.yaml to config.yaml, "
            "set your API keys as env vars, then re-run.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        capability = build_from_path(config_path)
    except ValueError as exc:
        print(f"error: invalid config — {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    create_server(capability).run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/capability_bridge/transports/mcp tests/test_mcp.py
git commit -m "feat(transport): MCP stdio server with vision_analyze / vision_ocr"
```

> Note: the `capability-bridge` console script (Task 1) still points at `server:main` — fine
> through Task 13. Task 14 repoints it to `capability_bridge.cli:main`, which adds the `setup`
> subcommand while keeping the default "serve the MCP server" behavior.

---

### Task 14: Trigger rule, integrations, setup CLI, README

**Files:**
- Create: `src/capability_bridge/setup.py` (installer logic, importable)
- Create: `src/capability_bridge/cli.py` (subcommand dispatch: default = serve MCP, `setup` = installer)
- Create: `src/capability_bridge/resources/config.example.yaml`, `vision-trigger.md`, `claude-code.mcp.json`, `codex.config.toml` (runtime resources — read via `importlib.resources`, bundled in the wheel; repo-root `config.example.yaml` / `prompts/` / `integrations/` are kept as dev-facing mirrors, guarded by `test_bundled_resources_match_repo_copies`)
- Create: `README.md`
- Modify: `pyproject.toml` (console script → `capability_bridge.cli:main`)
- Test: `tests/test_setup.py`

**Interfaces:**
- Consumes: the frozen spec's §11 integration design.
- Produces: the single-source trigger rule; per-client MCP config snippets; `capability-bridge setup [--target claude-code|codex] [--test]` one-shot installer (merge-safe `.mcp.json`, missing-key report, optional live provider test); a README whose first screen sells "keep your model, add what it lacks".

- [ ] **Step 1: Write the failing test**

Create `tests/test_setup.py` (the installer is now a package module — importable, no subprocess):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_setup.py -v`
Expected: FAIL with `ModuleNotFoundError: capability_bridge.setup`.

- [ ] **Step 3: Write the files**

Create `prompts/vision-trigger.md`:

```markdown
# Vision trigger rule

When the user provides an image — a screenshot, terminal error, UI mockup, document scan,
diagram, or any picture — or when an image cannot be read directly, call the `vision_analyze`
MCP tool with the image's local path and a `prompt` derived from the user's intent.

Vision is visual reasoning, not image captioning. Build the `prompt` from what the user actually
wants to know:
- If the intent is inferable from context, turn it into a targeted analysis prompt. Example:
  "make this page look more polished" → review the UI as a designer (hierarchy, spacing,
  typography, color, consistency, and the changes that would most improve it); "analyze this
  painting" → composition, light, color, style, mood.
- If the intent is unclear, pass a neutral general visual-analysis prompt. Do NOT invent
  aesthetic, debugging, or design goals the user did not ask for.

When the user needs text extracted from an image, call the `vision_ocr` MCP tool with the
image's local path instead.

Treat the tool result as the agent's visual observation of the image. Use it for subsequent
reasoning, but preserve uncertainty when the result is ambiguous or incomplete.
```

Create `integrations/claude-code/.mcp.json` (installed CLI — `uv tool install .` puts
`capability-bridge` on PATH, so no `uv run`, no cwd dependency):

```json
{
  "mcpServers": {
    "capability-bridge": {
      "command": "capability-bridge"
    }
  }
}
```

Create `integrations/codex/config.toml.snippet` (Codex reads `~/.codex/config.toml`; this is a
snippet to paste or the source for `codex mcp add`):

```toml
[mcp_servers.capability-bridge]
command = "capability-bridge"
```

Create the BUNDLED resources — the same four files, byte-identical, inside the package so the
installed CLI can read them from the wheel (`config.example.yaml` already exists from Task 8):

```
src/capability_bridge/resources/
├── config.example.yaml      # copy of the root config.example.yaml (Task 8)
├── vision-trigger.md        # copy of prompts/vision-trigger.md
├── claude-code.mcp.json     # copy of integrations/claude-code/.mcp.json
└── codex.config.toml        # copy of integrations/codex/config.toml.snippet
```

`test_bundled_resources_match_repo_copies` (Step 1) enforces byte-equality — keep them in sync.

Create `src/capability_bridge/setup.py` (importable installer logic; `merge_mcp_config` merges
ONLY the `capability-bridge` entry and refuses to clobber an invalid existing file; the `--test`
self-test runs inside a single `asyncio.run` so the provider client and its `aclose()` share one
event loop):

```python
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
```

Create `src/capability_bridge/cli.py` (entry point dispatch — `capability-bridge` serves the MCP
server by default; `capability-bridge setup` runs the installer):

```python
"""capability-bridge entry point.

Default (no args)      -> run the MCP stdio server.
setup ...              -> one-shot installer (see capability_bridge/setup.py).
"""

from __future__ import annotations

import sys


def main() -> None:
    if sys.argv[1:] and sys.argv[1] == "setup":
        from capability_bridge.setup import setup_main

        setup_main(sys.argv[2:])
        return
    from capability_bridge.transports.mcp.server import main as server_main

    server_main()


if __name__ == "__main__":
    main()
```

Modify `pyproject.toml` — repoint the console script at the new dispatcher:

```toml
[project.scripts]
capability-bridge = "capability_bridge.cli:main"
```

(The old `scripts/setup.py` design is gone — never created in this plan; the installed CLI owns
setup now.)

Create `README.md` (first screen is user-facing marketing, not architecture):

```markdown
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_setup.py -v`
Expected: PASS. (Also re-run the full suite: `uv run pytest` — Task 13's server must still pass, since cli.py imports `transports.mcp.server`.)

- [ ] **Step 5: Manual E2E smoke (product gate — needs one real API key)**

Step 5a — install the CLI from the REPO (this is where `uv tool install .` runs; a throwaway
directory has no `pyproject.toml` to install):

- [ ] In the repo, `uv tool install .` succeeds and `capability-bridge` is on PATH.

Step 5b — verify install-once / run-anywhere in a throwaway project directory:

- [ ] `mkdir /tmp/cb-e2e && cd /tmp/cb-e2e` (a plain directory with no repo).
- [ ] In a directory that already has a `.mcp.json` with another server, run
      `capability-bridge setup`; the other server entry survives (merge, not overwrite).
- [ ] With no API key set, `setup` prints each missing env var by name; `--test` says skipped.
- [ ] Set one key; `capability-bridge setup --test` prints `[test] OK provider=...` — proves the
      bundled resources (config template, trigger, MCP snippets) resolved from the installed
      wheel, not from a source repo layout.
- [ ] In Claude Code (or Codex), the `vision_analyze` tool appears; send a screenshot and the
      main model reasons from the result.
- [ ] (fallback, optional) Enable a second provider in the generated `config.yaml`, point its
      `base_url` at a dead URL, and verify a call still returns a result from the next provider,
      with the log showing one line per failed attempt sharing the same `request_id`.

- [ ] **Step 6: Commit**

```bash
git add src/capability_bridge/cli.py src/capability_bridge/setup.py \
        src/capability_bridge/resources \
        prompts integrations README.md pyproject.toml tests/test_setup.py
git commit -m "feat: capability-bridge setup CLI + merge-safe install + product copy"
```

---

## Self-Review Notes

- **Spec coverage:** every §3 "v0.1 做" item maps to a task (§4 constraints → Task 1 + 5 + 6 + 7 + 12; §7 components → Tasks 2-11; §8 config → Task 8; §9 fallback → Task 10; §10 tools → Task 13; §11 integrations → Task 14; §12 deps → Task 1; §13 tests → per-task tests). §14/§15 are explicitly deferred — no code. Product DoD (release gate) is captured in the header section and verified by Task 14 Step 5.
- **Placeholder scan:** every code step has concrete, complete code. No "TBD" / "add appropriate handling".
- **Type consistency:** `ModelRequest`/`ModelResponse`/`CapabilityResult`/`NormalizedImage` signatures are identical across Tasks 5→11→13. `RoutingPolicy.execute(request, *, request_id=None)` returns `RoutedResponse` (Task 10), and `VisionCapability.analyze()/ocr()` shape it into `VisionResult`/`OCRResult` (Task 11) — Routing answers only "who executed". Provider constructors (`OpenAICompatProvider(base_url=, api_key=, model=, name=, capabilities=, client=)` and `GeminiProvider(api_key=, model=, name=, capabilities=, client=)`) match the `**common` kwargs built in Task 12. Setup helpers (`ensure_config`, `merge_mcp_config`, `append_trigger`, `check_keys`, `setup_main`) match the Task 14 test imports exactly.
- **Import-path fix (from review):** Tasks 6/7 tests import `capability_bridge.providers.*` — the adapters live OUTSIDE core, so `core.providers.*` was wrong. Compile-level review of generated plans is required, not just semantic review. Same lesson re-checked in Task 14: the `core.registry.models` import was dead AND pointed at a nonexistent module — removed.
- **Install contract:** console script is `capability_bridge.cli:main` (Task 14); integrations reference `command: capability-bridge` (installed via `uv tool install .` in the repo) — no `uv run`, no cwd dependency. Before Task 14 the script points at `server:main` (Task 1), which is compatible. Task 14 Step 5 runs `uv tool install .` IN the repo, then validates install-once/run-anywhere from a throwaway directory.
- **Bundled resources (release contract):** all runtime assets (`config.example.yaml`, `vision-trigger.md`, `claude-code.mcp.json`, `codex.config.toml`) live in `src/capability_bridge/resources/` and are read via `importlib.resources` — the CLI never depends on the repo layout on disk (works from a wheel). Root copies remain per frozen spec §6 as dev-facing mirrors; `test_bundled_resources_match_repo_copies` enforces the "one source" invariant.
- **Single-provider default:** `config.example.yaml` enables only qwen by default; GLM/Kimi/Gemini are commented-out fallback examples. Strict `validate_config` stays correct because routing only references enabled providers, and Product DoD's "one key → first success" holds.
- **`aclose()` lifecycle:** `ModelProvider.aclose()` (default no-op) closes only self-created httpx clients (`_owns_client`); `VisionCapability.aclose()` closes each provider exactly once (deduped by identity — a single vision+ocr instance is shared across policies); composition root `bootstrap.py` is package-level and `--test` runs provider + aclose in a single `asyncio.run`.
- **Execution mode:** Subagent-Driven (one fresh subagent per task, parent reviews each diff with import check + pytest + architecture test, no subagent may change architecture). Execution Protocol section defines checkpoints, the 3-level deviation rule, and "plan is a blueprint, not law". git identity must be set by the user locally (repo-local) — not invented by the executor; the spec commit lands first (Task 1).
- **Vision semantics (Product Note):** `vision_analyze` is intent-driven visual reasoning, not captioning. Task 6/7 forward explicit `prompt` verbatim (default only when `None`); Task 11 rejects `task != "general"` (no silent ignore) and tests prompt end-to-end fidelity (`FakeProvider.last_request.prompt`); Task 14 trigger rule instructs the agent to derive intent-driven prompts without inventing user goals. See `docs/superpowers/product/2026-08-13-vision-product-note.md`.
- **Tech debt (recorded, not fixed):** `_DEFAULT_PROMPTS` is duplicated in both Task 6 and Task 7 adapters. When the Capability layer takes on task profiles (`ui_review`, `art_analysis`, ...), consolidate default prompts there. Do NOT do this DRY refactor now.
