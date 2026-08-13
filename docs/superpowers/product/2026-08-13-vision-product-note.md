# Vision Product Note — 视觉推理,不是图片描述

> 产品语义锁定(2026-08-13,检查点 1 之后确认)。这是**产品定义**,不是功能设计。

## The definition

> **Vision means visual reasoning, not image captioning.**
>
> `vision_analyze(image, prompt)` is an **intent-driven visual reasoning primitive**: the main
> model asks the vision model a question about the image.
>
> Valid uses of the same capability: UI critique, visual debugging, composition/style analysis,
> artwork interpretation, and general visual understanding.
>
> v0.1 exposes only the generic primitive: free-form `prompt`, `task="general"` only. Specialized
> task profiles (`ui_review`, `art_analysis`, ...) are deferred until real usage validates them.
> The `task` seam already reserves the extension point — Core architecture does not need to change.
>
> Output quality depends on the selected visual model AND the quality of the visual question.
> capability-bridge provides transport, routing, and intent delivery — it does not guarantee
> aesthetic judgment quality.

## 中文说明

产品定义:

> 不是给文本模型一个 OCR 工具。
> 也不是给文本模型一个图片 caption 工具。
> 而是给它一条通往"视觉推理模型"的通道。

- **意图驱动**:主模型把用户意图翻译成针对性视觉分析 prompt(如"改高级点"→ UI 评审:层级/间距/字体/配色/一致性)。**只有当意图可从上下文推断时才构造针对性 prompt;意图不明则用中性通用分析,不许替用户发明审美/调试/设计目标。**
- **链路**:用户意图 → 主模型构造 prompt → `vision_analyze(image, prompt)` → 视觉模型做视觉判断 → 主模型做代码推理与修改。
- **v0.1 承诺**:通用原语可用("传对 prompt + 选对模型,就能做审美/UI/艺术分析");不做专业 task profile。
- **质量边界**:审美上限在视觉模型与提问质量,不在桥。桥决定"用户意图是否完整地交给一个有审美能力的模型"。

## 实测升级(2026-08-13,benchmark F1-F4)

> 原先是理论,现在有真实数据:

> **Visual Brief quality is a first-order capability factor.**
>
> In our tests, moving from a generic prompt to a task-scoped brief changed both Flash and Plus
> from descriptive image narration into actionable visual critique; adding substantially more
> unrelated context provided little additional benefit.

- 数据见 `docs/benchmarks/2026-08-13-qwen-vision-ab.md`:A(裸)→B(brief)两个模型几乎翻倍(Flash 42→86 / Plus 46→87),B→C(富上下文)基本持平。
- 含义:Host 提炼 task-scoped context 比让视觉模型自己扛大上下文更重要;capability-bridge 的职责是**把 brief 原样送到视觉模型**(已由 prompt 保真测试锁定),而不是替 Host 维护上下文。

## 落地位置(对应计划修订)

- `prompts/vision-trigger.md`(Task 14):触发规则落实"意图驱动"措辞,禁止裸描述兜底。
- Task 6/7 测试:`test_explicit_prompt_is_forwarded_unchanged`——显式 prompt 原样传递、优先级高于默认。
- Task 11:Capability→Provider 的 prompt 端到端保真测试;`task != "general"` 明确报错(不允许 silent ignore)。
- **技术债**:`_DEFAULT_PROMPTS` 目前复制在 Task 6/7 适配器内。待 Capability 承担 task profile 时把 general/ui_review/art_analysis prompt 收敛到能力层——现在不做 DRY 重构。
