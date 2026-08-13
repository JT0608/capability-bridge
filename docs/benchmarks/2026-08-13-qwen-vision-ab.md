# capability-bridge v0.1 — Qwen Vision A/B Benchmarks

> 日期:2026-08-13。目的:决定 v0.1 默认视觉模型(`qwen3-vl-flash` vs `qwen3.7-plus`),并验证"Visual Brief 是第一杠杆"的产品假设。
> 所有调用都经 capability-bridge 真实链路(MCP → VisionCapability → RoutingPolicy → OpenAICompatProvider → 真实 DashScope API)。
> 模型:qwen3-vl-flash、qwen3.7-plus(真实 API,非 mock)。评分:人工 rubric(具体性 30 / 问题命中 25 / 幻觉率-反 20 / Brief 遵循 15 / 可行动性 10)。原始输出见 `raw/`。

## 实验 1 — Context A/B:裸 prompt vs Visual Brief

- 图片固定:Nebula SaaS 仪表盘;模型固定 qwen3.7-plus。
- **A(裸)**"分析这个界面。":41.4s → **图片描述**,夸"设计成熟、UX 良好",无批评、无可行动建议。
- **B(精炼 brief)**:58.5s → **真正的设计评审**(5 问题 + hex 色值/px 规格 + P0-P4 优先级)。
- **结论:从通用 prompt 换成 task-scoped brief,把两个模型都从"描述式看图"变成"可行动的视觉评审"。Brief 质量是第一杠杆,影响远大于模型升级。**

## 实验 2 + 3 — Model A/B:Flash vs Plus(同一 brief)

| 场景 | Flash | Plus | 结论 |
|---|---|---|---|
| 复杂 UI + brief | 26.2s,实用质量相当 | 68.5s,实用质量相当 | 快 2.6×,质量相当 |
| 简单读取 | 0.7s,正确 | 4.9s,正确 | 快 7×,都正确 |
| 艺术鉴赏 | 21.2s,表达强 | 29.5s,表达强 | 快 ~1.4×,都有强表达 |

- 艺术场景两者都读出了同一句书封文字("成为一只平静的龙要流多少眼泪"),用户确认真实存在——跨模型重合,非幻觉。
- **但两者在艺术鉴赏上都存在"策展人腔"式过度阐释**(自创流派名"后数字浪漫主义/新拟物主义"、精确到"12 层黄调"的不可核验细节)——评论文风生成,非图中可验证事实。应用"保留不确定性"原则。

## 实验 4 — Context Complexity A/B/C:上下文复杂度

同一张复杂 UI;A 裸 / B 精炼 brief / C = B + 项目背景/技术栈/修改历史 + 无关噪声(webpack/CI/DB)。

| 档位 | Flash 评分 | Plus 评分 | Flash 延迟 | Plus 延迟 |
|---|---|---|---|---|
| A 裸任务 | 42 | 46 | 24s | 45s |
| B 精炼 brief | 86 | 87 | 30s | 50s |
| C 富上下文 | 88 | 87 | 33s | 63s |

- **A→B 两个模型几乎翻倍**(42→86 / 46→87):brief 主导。
- **B→C 基本不动**(Flash +2、Plus 0):额外上下文既不明显帮忙也不明显稀释;Plus 在富上下文的结构化 UI 评审上**没有拉开差距**。
- 含义:Host 提炼 task-scoped context 比让视觉模型自己扛大上下文更重要——支持"无 Context Manager、Host 持有上下文"的架构判断,并降低了对视觉 Provider 长上下文能力的要求。

## 结论(限定表述)

> **In the tested coding-oriented visual workloads, qwen3-vl-flash achieved comparable practical output quality to qwen3.7-plus when given the same task-scoped Visual Brief, at substantially lower latency.**

### Caveats(不泛化)

- 样本小;多数为单图任务;人工评分。
- Plus 在**微妙感知**(实测到一次"环形图颜色 ↔ KPI 卡颜色隐含对应"的洞察)、**多图推理**或其它未测负载上可能保留优势。
- 本结论不表示"Flash 视觉能力比 Plus 强"。

## v0.1 决策

```text
default vision model  = qwen3-vl-flash
default timeout       = 60s
qwen3.7-plus          = 可选高能力档(接受更高延迟),不自动路由
decision basis        = F1-F4 benchmark 见上
```

- README 表述:默认 Flash 的原因是目前 coding-oriented benchmarks 下 latency/quality trade-off 最好;Plus 为可选更高能力模型,接受更高延迟。不宣称 Flash"视觉能力更强"。
- v0.2 的 `fast/deep` 自动路由需要更多数据再决定,不由本 benchmark 提前定死。
