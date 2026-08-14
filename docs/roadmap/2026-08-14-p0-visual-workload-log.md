# P0 — 真实视觉使用记录规范(Visual Workload Log)

> 目的:在真实 coding 项目中观察"主模型 + capability-bridge + 视觉专家"协作的**真实摩擦**,
> 用数据决定 v0.2 的第一刀,而不是靠我们想象用户缺什么。
> 这是纯观测,不建自动循环、不改 Core、不加 task/mode、不实现多图。

## 为什么先做这个

F1–F4 目前唯一被强数据证明的是:**Visual Brief 质量是一级变量**。`fast/deep` 路由、多图对比、
task profiles 都还是候选概念,需要真实使用暴露的重复摩擦来验证优先级。

**退出条件**:连续积累 **10 个真实 coding-oriented 视觉任务**,某个同类型摩擦出现 **≥3 次**,
才把对应项升级为 v0.2 功能。例如:

```text
6/10 需要"和上一版/参考稿比一下"    → 多图 compare 升 v0.2 P0
5/10 嫌输出太长                     → 先做 result profile,而不是多图
4/10 都只是"快速看一下"             → fast/deep 路由提前
几乎没人要第二张图                  → 多图 P1 延后
```

## 记录方式:两层

1. **机器事实层(自动,不用填)**:桥的 attempt 级结构化日志已记录
   `request_id / capability / provider / model / latency_ms / success / error_type / fallback_count`
   (隐私白名单,不含图片/prompt/响应全文)。查看方式:capability-bridge 的 stdout 日志。
2. **人工层(每次 ≤30s,只填主观字段)**:下表。

## 记录表(每真实调用一行)

| timestamp | host | task_goal | image_count | brief_length | provider | model | latency_ms | useful? | changed_code? | second_visual_call? | main_failure_reason | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| _(示例)2026-08-14 14:30_ | claude-code | 看这个页面为什么显得廉价 | 1 | ~180 字 | qwen | qwen3.6-flash | 24539 | partial | yes | no | F7 | 指出问题但没对上 Hero.tsx |

字段说明:

- `host`: claude-code / codex / 其他
- `task_goal`: 用户原始意图(简短)
- `image_count`: 这次调用用了几张图(目前只能是 1;这是将来多图需求的计数来源)
- `brief_length`: DeepSeek 发的 prompt 大致长度(短/中/长 或字数)
- `provider` / `model`: 桥实际路由到的(机器日志可回查)
- `latency_ms`: 端到端耗时(机器日志可回查)
- `useful?`: yes / partial / no —— 视觉回答对主模型是否有用
- `changed_code?`: no / yes / planned —— 这次视觉结果是否推动改代码
- `second_visual_call?`: yes / no —— 同一轮是否需要再调一次视觉(第二张图/复评)
- `main_failure_reason`: 见摩擦码,或留空(没用摩擦就空)
- `notes`: 一句补充

## 摩擦码(让"≥3 次同类"可数)

| 码 | 摩擦 |
|---|---|
| F1 | 主模型根本没触发视觉 |
| F2 | brief 太泛,输出退化成描述 |
| F3 | 视觉输出太长,主模型不知道怎么执行 |
| F4 | 需要参考图/上一版截图对比 |
| F5 | 需要局部 crop,而不是整张图 |
| F6 | 延迟太高 |
| F7 | 视觉指出的问题对不上具体组件 |
| F8 | 模型能力不足以完成该任务 |

## 本阶段明确不做

- ❌ 自动"评审→改→复评"循环脚本(会把行为预设化,遮住真实摩擦)
- ❌ 修改 Core / 新增 task/mode / 多图实现
- ❌ 每次调用打多维质量分(那是 benchmark 的事,不混进日常记录)

## 怎么跑

1. 在真实前端项目里,正常用 Claude Code/Codex + DeepSeek 工作;
2. 遇到需要看图的任务时,通过 capability-bridge 的 `vision_analyze`;
3. 每次调用填一行上表(机器字段从桥日志回查);
4. 攒满 10 行后停下来,统计摩擦码频率 → 决定 v0.2 第一刀。
