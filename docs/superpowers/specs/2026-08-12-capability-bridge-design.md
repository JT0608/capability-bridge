# capability-bridge — 设计文档 (Design Spec)

- **日期**: 2026-08-12
- **状态**: 已收敛,待用户审阅
- **工作名**: `capability-bridge`(架构/工作名,非最终品牌名)
- **版本**: v0.1
- **语言**: Python 3.12+ / uv
- **包名**: `capability_bridge` / 核心模块 `capability_bridge.core` / CLI `capability-bridge`

---

## 1. 定位

> **A transport-agnostic model capability bridge. MCP is the first transport; Vision is the first capability.**

面向用户:

> Give text-only coding agents vision through MCP, with pluggable multimodal providers and automatic fallback.

**项目本体是 Capability Core,不是 MCP Server。MCP 只是它现在的第一个 transport(入口适配器)。** 为纯文本 agent(Claude Code / Codex / Cursor)通过 MCP 提供视觉能力;视觉模型可插拔,失败自动降级。

主模型不换、不动客户端生态。DeepSeek 只是当前用户,不是项目的名字或边界。

---

## 2. 背景与问题

DeepSeek 等纯文本模型无视觉能力。用户在 Claude Code(经 cc-switch 接入 DeepSeek)中遇到图片无法理解。方案不是让 DeepSeek 学会看图,而是把视觉做成**能力**:

```
主模型(Claude Code + DeepSeek)
   │  tool call
   ▼
vision_analyze(image, question)
   │
   ▼  (交给视觉模型)
返回文字结果
   │
   ▼
主模型把结果放回上下文,继续推理
```

调用链 `request → capability → result`,**本层无状态**。对话状态、上下文、工具结果注入是 Host(Claude Code / Codex)的责任,本项目不做。

---

## 3. 目标与边界

### v0.1 做

- **Capability Core**(transport-agnostic)
- **Vision Capability**: 两个工具 `vision_analyze` / `vision_ocr`
- **Transport**: MCP stdio(第一个 transport)
- **Provider**: OpenAI-compatible 适配器 + 一个非 OpenAI-compatible 适配器(Gemini);具体适配器在 core 之外
- **Routing**: ordered fallback(priority / timeout / retry),**无打分**
- **图片预处理**: 正式模块,Provider 只接受 `NormalizedImage`
- **结构化操作日志**(隐私友好)
- **Registry 配置**(只记客观运行信息)
- **集成**: Claude Code + Codex + 一份共享触发规则
- **测试**: 单测 + 可选集成测试

### v0.1 明确不做

Gateway、OpenAI/Anthropic API server、Context/Conversation Manager、Memory、Agent loop、Workflow、Multi-Agent、UI、Desktop、PDF、Search、Browser、Video、bbox、打分 Router、Skill engine、Marketplace、**远程图片(HTTP URL)抓取**。

### 边界原则

- 状态是 Host 的责任,本层基本无状态
- cc-switch / 主模型配置不在项目范围内,二者与项目是**平行关系**,互不触碰
- 项目名不含 DeepSeek

---

## 4. 架构约束(PR 审阅红线,每条 PR 必查)

> **Core must never depend on MCP, Claude Code, Codex, or any specific provider. Transports and providers depend inward on Core, never the reverse.**

1. 任何 `import mcp` 的代码**只允许存在**于 `transports/mcp/`
2. `core/` 内部不得 import MCP、Anthropic SDK、OpenAI SDK、任何客户端运行时
3. `core/` 内部不得 import 具体 provider 适配器(`providers/openai_compat.py`、`providers/gemini.py`)——具体适配器**位于 core 之外**,实现 `core/providers/base.py` 的接口
4. provider 适配器只能依赖 Core 定义的接口与 schema,不得反向依赖
5. `capability_bridge` 的核心逻辑不依赖任何具体的视觉模型名

违反任一条 = PR 不过。CI 应有对应断言(见 §13)。

---

## 5. 架构

```
                    Agent (Claude Code / Codex)
                       │  MCP stdio
                       ▼
               Transport: MCP (transports/mcp/server.py)
                       │   ★ 唯一 import mcp 的地方
                       │   ★ 也是组合根:读 registry 配置 → 实例化具体 providers → 接线 capability
                       ▼
                Capability Core (core)
   ├─ Capabilities    做什么   — Vision: vision_analyze / vision_ocr
   ├─ Routing Policy  怎么做   — ordered fallback
   ├─ Providers 接口  谁来做   — core/providers/base.py (ModelProvider ABC)
   ├─ Preprocessing   输入归一 — NormalizedImage
   ├─ Schemas         返回结构 — CapabilityResult 等
   ├─ Errors          错误分类
   ├─ Registry        配置加载(只输出配置数据,不实例化 provider)
   └─ Observability   结构化日志
                       ▲
                       │  实现 core 的接口,依赖向内,物理上位于 core 之外
        Provider Adapters (providers/)
              openai_compat.py / gemini.py
```

**依赖方向(必须向内):**

```
  transports  →  core  ←  providers(实现 core 的 ABC)
```

具体适配器在 `src/capability_bridge/providers/`(core 之外),依赖 core;core 绝不反向依赖具体适配器。组合根在 transport/入口,负责把 registry 配置、具体 provider 实例、capability 接起来——**core 不知道也不关心"现在是哪个模型在回答"**。

未来加 Gateway 只是加 transport(`transports/openai` / `transports/anthropic`),Core 完全不动。

---

## 6. 目录结构

```
capability-bridge/
├─ pyproject.toml
├─ README.md
├─ config.example.yaml
├─ src/capability_bridge/
│  ├─ core/
│  │  ├─ capabilities/vision.py       # vision_analyze / vision_ocr 定义
│  │  ├─ providers/base.py            # ModelProvider ABC + ModelRequest/ModelResponse(仅接口)
│  │  ├─ routing/policy.py            # ordered fallback (priority/timeout/retry)
│  │  ├─ preprocessing/image.py       # ImageInput → NormalizedImage
│  │  ├─ schemas/result.py            # CapabilityResult / VisionResult / OCRResult
│  │  ├─ errors/__init__.py           # 错误分类
│  │  ├─ observability/logging.py     # 结构化日志(隐私白名单)
│  │  └─ registry/config.py           # 加载配置 → 输出配置数据,不 import 具体 provider
│  ├─ providers/                      # ★ 具体适配器,在 core 之外,实现 core/providers/base.py
│  │  ├─ openai_compat.py             # 一个适配器:GLM/Qwen/Kimi/MiniMax/OpenRouter/SiliconFlow/自建
│  │  └─ gemini.py                    # Google 专用协议适配器
│  └─ transports/
│     └─ mcp/server.py                # ★ 唯一允许 import mcp 的地方;组合根
├─ integrations/
│  ├─ claude-code/                    # .mcp.json 配置 + CLAUDE.md 触发规则
│  └─ codex/                          # mcp.json 配置 + AGENTS.md 触发规则
├─ prompts/
│  └─ vision-trigger.md               # 触发规则唯一来源(复制进 CLAUDE.md / AGENTS.md)
├─ scripts/
│  └─ setup.py                        # 写 MCP 配置 + 复制触发规则
├─ tests/
│  ├─ test_preprocessing.py
│  ├─ test_routing.py
│  ├─ test_config.py
│  ├─ test_errors.py
│  └─ test_architecture.py            # 断言 core/ 不 import mcp / 客户端 SDK / 具体 provider
└─ docs/superpowers/specs/
```

---

## 7. 核心组件

### 7.1 ModelProvider 接口(在 core 内,只定义"谁来做"的契约)

```python
# core/providers/base.py —— 仅接口,无实现
class ModelProvider(ABC):
    capabilities: CapabilitySet       # {"vision": True, "ocr": True, ...}
    @abstractmethod
    async def invoke(self, request: ModelRequest) -> ModelResponse:
        ...
```

- 用 `ModelProvider` 而非 `VisionProvider`,为未来 Document / Audio / Video / Reasoning 能力留位
- **具体实现一律在 `providers/`(core 之外)**,实现该 ABC,依赖向内

### 7.2 能力与 Provider 严格分离

- **能力定义"做什么"**,**Provider 定义"谁来做"**
- 不存在 `QwenVisionSkill` 这类绑定模型的对象
- 调用链:`vision_analyze` → Vision Capability → Routing Policy → [qwen, glm, gemini] 具体 provider

### 7.3 Routing Policy(不是 Router)

- 仅由**有序列表 + timeout + retry + 失败降级**构成
- 无打分、无质量/速度/成本权重(等真实指标积累后再考虑)
- 规则与错误分类联动,见 §9
- RoutingPolicy 接收的是**组合根已实例化好的 provider 实例**,core 自己不做实例化

### 7.4 图片预处理(正式模块)

```
ImageInput → validate → MIME detect → resize → compress → encode → NormalizedImage
```

- Provider 只接受 `NormalizedImage`
- adapter 内部**禁止**出现 `if image.endswith(".webp")` 这类格式判断——图片逻辑只存在于 preprocessing,三份 Provider 绝无三份图片代码
- **v0.1 输入范围**: 本地路径、`file://`、base64 data URI。**不支持 HTTP(S) URL**(下载/重定向/MIME 欺骗/SSRF/内网访问等交给以后独立的 fetch 层)

### 7.5 Schemas(不为统一而统一)

```python
class CapabilityResult(BaseModel):
    content: str                    # 模型主要答案(保留信息)
    structured_data: dict | None = None   # 各能力自定义扩展
    provider: str
    model: str
    latency_ms: int
    warnings: list[str] = []

class OCRResult(CapabilityResult):  # 各能力自定义 schema,非万能 JSON
    structured_data: ...            # OCR 自己的结构
```

**不做一个 UniversalAIResult 包打天下**(截图/OCR/图表/UI 结构不同,塞进统一字段会变成"万能 JSON 垃圾桶")。

### 7.6 错误分类(一等公民)

```
ProviderError
├─ AuthenticationError    401     → 不 fallback(用户 key 错了,降级也没用)
├─ RateLimitError         429     → fallback
├─ TimeoutError           超时    → fallback
├─ ModelUnavailableError  模型不可用 → fallback
├─ UnsupportedInputError  输入/格式错 → 不 fallback(输入本身就错)
└─ InvalidResponseError   响应不符 schema → 重试/fallback
```

- **禁止裸 `try/except` 链**(那是屎山的种子)
- Router 依据错误类型决定是否降级

### 7.7 可观测性(结构化日志,进入 v0.1)

每次调用记录:

```
request_id, capability, provider, model, latency_ms, success, error_type, fallback_count
```

**隐私白名单**:不记录图片内容、prompt 全文、模型完整响应。这些指标是未来动态 Router 的第一批真实数据(积累了 latency / 错误率 / cost 才升级,不是现在)。

### 7.8 配置(只记客观信息)

- key 走环境变量(`api_key_env` 指定环境变量名)
- registry **不做模型评分大百科**(`reasoning: 8 / coding: 7` 这类主观打分不进 v0.1;`free: true` 这类账户/地区/额度状态也不进)
- 结构:`providers`(type/base_url/api_key_env)+ `models`(provider/model/capabilities)+ `routing`(按能力列优先顺序)
- registry 只**输出配置数据**;具体 provider 的实例化发生在组合根(transport)

---

## 8. 配置示例

```yaml
# config.example.yaml
policy:
  timeout_seconds: 15
  max_retries: 1

providers:
  qwen:
    type: openai_compatible
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: QWEN_API_KEY
  glm:
    type: openai_compatible
    base_url: https://open.bigmodel.cn/api/paas/v4
    api_key_env: GLM_API_KEY
  gemini:
    type: gemini
    api_key_env: GEMINI_API_KEY

models:
  qwen-vl-flash:
    provider: qwen
    model: qwen3-vl-flash
    capabilities: [vision, ocr]
  glm-vl-flash:
    provider: glm
    model: glm-4.6v-flash
    capabilities: [vision, ocr]
  gemini-flash:
    provider: gemini
    model: gemini-2.x-flash
    capabilities: [vision, ocr]

routing:
  vision:
    - qwen-vl-flash
    - glm-vl-flash
    - gemini-flash
  ocr:
    - qwen-vl-flash
    - glm-vl-flash
```

---

## 9. Fallback 规则

1. 按 `routing.<capability>` 列表顺序尝试
2. 命中 `TimeoutError` / `RateLimitError` / `ModelUnavailableError` → 降级下一个
3. 命中 `AuthenticationError` / `UnsupportedInputError` → **直接报错,不降级**
4. 全部失败 → 返回明确错误信息(含 provider / model / error_type)
5. 每次降级计入 `fallback_count` 并写结构化日志

---

## 10. MCP 工具

- `vision_analyze(image: str, prompt?: str, task?: str = "general")` → CapabilityResult
  - `image`: 本地路径 | `file://` | base64 data URI(**v0.1 不支持 http(s) URL**)
  - `prompt`: 可选,聚焦提问
  - `task`: v0.1 仅 `general`;`ui` / `chart` 等留给未来
- `vision_ocr(image: str)` → OCRResult

OCR 独立成工具是合理的:prompt、输出结构、模型选择、后处理都明显不同。

---

## 11. 集成与触发

- **Claude Code**: `integrations/claude-code/.mcp.json` 一行配置;触发规则复制进 `CLAUDE.md`
- **Codex**: `integrations/codex/mcp.json`;触发规则复制进 `AGENTS.md`
- **触发规则唯一来源**: `prompts/vision-trigger.md`(一份 source,两份落位,内容不分裂)
- **`scripts/setup.py`**: 帮用户写 MCP 配置 + 复制触发规则 + 生成 config 从 example

触发规则内容示例(复制进 CLAUDE.md / AGENTS.md):「当收到图片/图片解析失败时,调用 vision_analyze 工具并传入图片路径;需要提取图中文字时调用 vision_ocr。」

---

## 12. 运行时与依赖

- Python 3.12+,包管理 `uv`
- **FastMCP 或官方 Python MCP SDK** —— 依赖只允许出现在 `transports/mcp/`
- Pydantic v2、httpx、Pillow、pydantic-settings / PyYAML

---

## 13. 测试策略

- **单测(必跑,CI 内)**:
  - ImagePreprocessor(validate/resize/compress/encode/MIME)
  - Routing Policy(用 mock provider:超时→降级、401→不降级、429→降级)
  - Registry/Config 加载(env key 解析)
  - 错误分类
  - **架构红线测试 `test_architecture.py`**: 静态断言 `core/` 与 `providers/` 不含 `import mcp`、客户端 SDK、`providers/*` 反向引用——让 §4 的红线在 CI 里强制执行
- **集成测试(opt-in,需要真实 key)**: 真实 provider 冒烟;CI 默认跳过
- **MCP transport**: 用 FastMCP 测试客户端验证工具往返

---

## 14. 演进路径(留接缝,不实现)

- **v0.2**: HTTP transport(Streamable HTTP)→ gateway-lite
- **v0.3+**: 若做 Gateway,加 `transports/openai` / `transports/anthropic` —— Core 不变
- **远程图片 fetch 层**: 单独的安全模块(限大小/超时/禁内网/防 MIME 欺骗),不在 v0.1
- **新能力**: Document / Search / Browser / Audio → 各为 `core/capabilities/` 下一个模块,Provider 层不变
- **动态 Router**: 等真实 latency/错误率/cost 指标积累后,用现有结构化日志数据升级

**好预留 = 当前抽象不阻止未来加入**,不是第一天就放一堆空目录(`agents/ memory/ workflow/ ...` 全部没有)。

---

## 15. 待定 / 可改项

- 默认模型 ID: 以各厂商 API 实际可用为准(`config.example.yaml` 里填默认值,用户可改)
- 第二个 provider adapter 选 Gemini(v0.1);若有更好的非 OpenAI-compatible 候选可替换
- Cursor 集成:放 v0.2
- 最终品牌名 / 仓库名: v0.1 用工作名 `capability-bridge`,正式开源前再定
