<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.2 同库 v6/v7 QA 对照实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 R5.1 冻结的 v6/v7 检索上下文上，用相同 qwen3.8-27B legacy/native answer/judge 协议完成 QA 对照。

**Architecture:** 冻结 R5.0 runner/core 负责提示、回答协议和裁判；Python 只校验 provenance、复用 v7 回执、调用 v6 的 answer/judge、维护请求账本和计算 paired/network 统计。

**Tech Stack:** C++ Starling core、pybind11、冻结 Python runner、SQLite BudgetLedger、DashScope qwen3.8-27B、pytest。

**Spec:** `docs/superpowers/specs/2026-09-25-socialmem-r52-v6-v7-qa-design.md`

## Global Constraints

- R5.1 v6/v7 context 和 R5.0 retry4 v7 answer/judge 只能按哈希复用。
- answer/judge model、endpoint、max_tokens、thinking 和评分协议固定。
- v6 失败终态保留并计零；不重试未完成任务，不修改历史目录。
- 所有设计、实施计划和评测报告用中文；核心选择逻辑不在 Python 重写。

### Task 1: QA provenance RED

**Files:**
- Create: `tests/python/test_socialmem_r52_v6_v7_qa.py`
- Test: `scripts/run_socialmem_r52_v6_v7_qa.py`

- [x] **Step 1: 写失败测试**

测试必须拒绝缺少 R5.1 seal、v7 回执 prompt 漂移、answer policy 漂移、重复题目和非终态结果；并验证 v6/v7 配对统计方向为 `v7-v6`。

- [x] **Step 2: 运行 RED**

运行：`python -m pytest tests/python/test_socialmem_r52_v6_v7_qa.py -q`。预期因入口脚本不存在而失败。

### Task 2: 实现冻结 QA runner

**Files:**
- Create: `scripts/run_socialmem_r52_v6_v7_qa.py`

- [x] **Step 1: 实现输入与提示校验**

校验 R5.1 两臂 57 个 recall、R5.0 legacy/native 回执、模型配置和 prompt；加载冻结 `run_socialmem_r44.py` 的 `worker_modules`，不加载当前未封存的 Python 评分逻辑。

- [x] **Step 2: 写最小 answer/judge 执行**

按 policy/item 预留 ledger，调用冻结 `OpenAIAdapter` answer/judge；使用冻结 option parser/judge parser；完整写入 response receipt 和终态状态。默认模式只生成 v6 并复用 v7 回执；`--fresh-v7` 模式对 v7 也执行同样的 answer/judge。

- [x] **Step 3: 复用 v7 回执并配对统计**

将 retry4 legacy/native 回执原样封存到 v7 arm，校验与 R5.1 prompt 逐题一致；计算 v7-v6 正确数、四格转移、共同正常子集、network bootstrap、tokens 和请求账本。

- [x] **Step 4: 运行 GREEN**

补充：`--fresh-v7` 在同一进程内生成 v6/v7 两臂；默认模式仍保持 v7 回执复用，以便复核历史成本受限诊断。

运行专项 pytest；再执行真实命令：`python scripts/run_socialmem_r52_v6_v7_qa.py --contexts build/socialmem_20260925_r51_same_db_v6_v7 --out build/socialmem_20260925_r52_v6_v7_qa`。

### Task 3: 报告与回归

**Files:**
- Create: `docs/eval/2026-09-25-socialmem-r52-v6-v7-qa.md`
- Modify: `docs/eval/2026-09-25-socialmem-r50-semantic-event-evidence.md`
- Modify: `docs/Starling_Technical_Report.zh-CN.md`

- [x] **Step 1: 运行专项和相关回归**

运行 R5.2 pytest、R5.1 pytest、冻结 recall/answer guard 测试和相关 C++ retrieval 测试；复用模式结果只能标为诊断，正式单变量结论使用 `--fresh-v7`。

- [x] **Step 2: 复核封存**

独立核对 4 个 policy×arm 的题目覆盖、request ledger、prompt/context hash、技术失败和 summary 数值。

- [x] **Step 3: 写中文报告**

结果：fresh 双臂共 228 个终态任务、400 次请求，legacy 为 v6 22/57、v7 12/57，grounded_memory_v1 为 v6 24/57、v7 11/57；两种 policy 的 v7 均无改善题，未达到晋升门槛。详见 `docs/eval/2026-09-25-socialmem-r52-v6-v7-qa.md`。

报告 QA 差异、共同正常子集、network bootstrap、judge 翻转和成本，明确 v7 是否达到晋升门槛，并同步 R5.0 报告后续结论和技术报告入口。
