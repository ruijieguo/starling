<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.1 同库 v6/v7 检索对照实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 R5.0 retry4 同一冻结数据库上生成 v6/v7 检索上下文对照，为后续共享回答/裁判评测提供可审计输入。

**Architecture:** 复用现有冻结评测模块和 C++ `ObserverRetriever`。Python 只校验 provenance、复制临时数据库、设置 `ObserverQuery`、记录回执和汇总差异；v6/v7 的语义回链、事件邻域、排序和预算仍由 C++ 完成。

**Tech Stack:** C++ Starling core、pybind11、Python 3、SQLite、pytest、DashScope qwen embedding。

**Spec:** `docs/superpowers/specs/2026-09-25-socialmem-r51-same-db-v6-v7-design.md`

## Global Constraints

- 输入固定为 `build/socialmem_20260925_r50_semantic_real_retry4`，以 `runs/*/frozen.db` 和已封存 `summary.json` 为实际 QA 快照；不得使用 `source-databases/*/frozen.db` 替代。
- 双臂唯一变量为 `source_strategy=evidence_profile_v6|evidence_profile_v7`。
- Python 不实现任何检索选择、source 回链或事件排序逻辑。
- v7 直接复用 retry4 已封存的真实回执，真实阶段只为 v6 调用 qwen3.7-text-embedding；不调用 answer/judge。
- 所有设计、计划、评测文档使用中文；默认策略保持不变。

### Task 1: 写防漂移测试

**Files:**
- Create: `tests/python/test_socialmem_r51_same_db.py`
- Test: `scripts/run_socialmem_r51_same_db.py`

- [ ] **Step 1: 写失败测试**

覆盖以下合同：输入目录必须存在且 identity/config 哈希一致；只允许 v6/v7 两臂；7 个 scope 快照必须存在；回执必须同时包含同一数据库哈希和策略；缺失终态或策略漂移必须拒绝。

- [ ] **Step 2: 运行测试确认 RED**

运行：`python -m pytest tests/python/test_socialmem_r51_same_db.py -q`

预期：因 `scripts/run_socialmem_r51_same_db.py` 尚不存在而失败，失败原因必须是缺少入口或合同函数。

### Task 2: 实现只读双臂编排

**Files:**
- Create: `scripts/run_socialmem_r51_same_db.py`

- [ ] **Step 1: 实现 provenance 校验**

实现 `sha256(path)`、`read_json(path)`、`validate_parent(parent)`，逐项验证 retry4 的 `config.json`、`identity.json`、`scope-manifest.json`、`summary.json`、`sample.json`、`groups.json`、7 个 `runs/*/frozen.db` 和冻结核心文件，并拒绝以 `source-databases/*/frozen.db` 代替。

- [ ] **Step 2: 实现 C++ 查询装配**

实现 `recall_arm(parent, out, "evidence_profile_v6", embedding_kind)`：加载冻结 Python 模块并替换为当前核心扩展；每题复制对应 `runs/<group_id>/frozen.db` 到临时目录；创建 C++ `OpenAIEmbeddingAdapter` 或 `StubEmbeddingAdapter`；调用既有 `recall_observer_block`，只传 `source_strategy` 变量；写入完整回执。实现 `reuse_v7_summary(parent, out)`，校验 retry4 summary 的 57 个 v7 回执和数据库哈希后原样封存为 v7 arm。

- [ ] **Step 3: 实现封存比较**

实现 `compare_arms(out)`：按题目对齐 v6/v7，比较规范化 `source_refs` 和 `block` SHA-256，统计 `changed_questions`、`semantic/event/relevance` 选择计数、embedding 请求和拒绝诊断；写 `comparison.json` 与 `seal.json`。

- [ ] **Step 4: 运行 RED 测试转 GREEN**

运行：`python -m pytest tests/python/test_socialmem_r51_same_db.py -q`

预期：所有合同测试通过；测试不发送网络请求，使用 Stub embedding 和临时 fixture。

### Task 3: 离线回归与真实上下文生成

**Files:**
- Create: `docs/eval/2026-09-25-socialmem-r51-same-db-v6-v7.md`

- [ ] **Step 1: 运行离线结构回归**

运行：`python -m pytest tests/python/test_socialmem_r51_same_db.py tests/python/test_source_comparison_guard.py -q`，并运行对应 C++ retrieval 测试。

- [ ] **Step 2: 生成真实 qwen embedding 双臂上下文**

运行：`python scripts/run_socialmem_r51_same_db.py --parent build/socialmem_20260925_r50_semantic_real_retry4 --out build/socialmem_20260925_r51_same_db_v6_v7 --embedding dashscope`。

预期：v6 57/57 题新生成、v7 57/57 题通过 retry4 回执复用，0 answer/judge 请求；失败必须保留逐题错误和请求账本，不能伪造完成。

- [ ] **Step 3: 写中文诊断报告**

记录输入 provenance、核心哈希、两臂终态、source/block 变化、车道计数、拒绝计数、请求成本和“只能证明上下文变化”的解释边界；不写 QA 提升或晋升结论。
