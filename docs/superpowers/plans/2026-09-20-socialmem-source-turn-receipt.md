<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench SourceTurn 输入与三通道抽取回执实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 SocialMemBench 每个 holder 的真实抽取使用带 SourceTurn 元数据的 C++ payload，并归档 belief/general-fact/episodic 三通道 native 回执。

**Architecture:** C++ 扩展 episodic 回执并组合三通道 bundle receipt；Python 只调用 SourceTurn/bundle binding 和写入 scope 产物。按 speaker 的显式 holder 分组保留，抽取与 commit 仍使用既有三相流程。

**Tech Stack:** C++17、nlohmann/json、pybind11、SQLite、pytest、GoogleTest。

**Spec:** `docs/superpowers/specs/2026-09-20-socialmem-source-turn-receipt-design.md`

## Global Constraints

- 中文设计文档优先。
- 核心逻辑必须在 C++，Python 只能做 binding 调用、配置透传、评测编排和归档。
- 不修改题目、参考答案、裁判协议或历史评测目录。
- 本阶段不追加 DashScope 请求。
- 遵循 RED → GREEN：先运行新增失败测试，再写最小实现。

---

### Task 1: C++ 回执与 SourceTurn 入口契约测试

**Files:**
- Modify: `tests/cpp/test_structured_memory_closure.cpp`
- Create: `tests/cpp/test_source_turn_receipt.cpp`
- Modify: `tests/python/test_source_turn_input.py`
- Create: `tests/python/test_source_turn_receipt.py`

**Interfaces:**
- Consumes: existing `claim_source_turn_payload`, `RememberLlmBundle` and `make_real_extract_fn`.
- Produces: executable expectations for `memory_remember_bundle_receipt`, native episodic receipt fields, holder payload metadata, and scope receipt archive.

- [x] **Step 1: Write failing tests.** Assert that a real extraction payload contains the six SourceTurn fields, that a bundle receipt has exactly `belief`, `general_fact`, and `episodic`, and that every archived holder has all three channels.
- [x] **Step 2: Run the focused C++ and Python tests.**

Run: `.venv/bin/pytest -q tests/python/test_source_turn_input.py tests/python/test_source_turn_receipt.py` and the focused GoogleTest binary after configuring the build.

Expected: RED because the binding and receipt helper do not exist and the current extractor sends plain `speaker: text` lines.

### Task 2: Native episodic and bundle receipt

**Files:**
- Modify: `include/starling/extractor/episodic_extractor.hpp`
- Modify: `src/extractor/episodic_extractor.cpp`
- Modify: `include/starling/memory/memory_ops.hpp`
- Modify: `src/memory/memory_ops.cpp`
- Modify: `bindings/python/bind_13_memory_ops.cpp`
- Modify: `tests/cpp/test_source_turn_receipt.cpp`

**Interfaces:**
- Consumes: `EpisodicLlmResult`, `claim_extraction_receipt`, and `RememberLlmBundle`.
- Produces: `episodic_extraction_receipt(const EpisodicLlmResult&)` and `memory_remember_bundle_receipt(const RememberLlmBundle&)` returning UTF-8 JSON strings.

- [x] **Step 1: Add only the fields needed to preserve episodic prompt, hash and raw response.** Populate them in `EpisodicExtractor::extract_llm` before early returns.
- [x] **Step 2: Implement native serializers.** Parse the two claim receipts inside C++ and compose a stable schema-versioned bundle; serialize all raw episodic response metadata.
- [x] **Step 3: Expose one pybind function.** Keep `RememberLlmBundle` opaque; Python must not inspect or rebuild channel internals.
- [x] **Step 4: Run focused C++ tests and the binding test.** Expected: GREEN with no Python semantic duplication.

### Task 3: SourceTurn payload and scope archive wiring

**Files:**
- Modify: `scripts/eval_ladder.py`
- Modify: `scripts/run_socialmem_baseline.py`
- Modify: `tests/python/test_source_turn_receipt.py`
- Modify: `tests/python/test_socialmem_source_pipeline.py`

**Interfaces:**
- Consumes: `core.claim_source_turn_payload`, `core.memory_remember_bundle_receipt`, and explicit holder grouping.
- Produces: extraction outcomes containing native receipt JSON and `extraction.receipts.json` containing one receipt per holder.

- [x] **Step 1: Replace plain text assembly.** Map each source turn to the C++ accepted field set, call the renderer once per holder, and pass the returned UTF-8 payload to all three native channels.
- [x] **Step 2: Attach the opaque bundle receipt.** Call the C++ serializer immediately after `memory_remember_extract_all`; decode only the outer JSON for archival.
- [x] **Step 3: Write independent scope receipt artifact.** Archive schema version, holder list, source payload hash and the exact native channel receipts without changing scoring fields.
- [x] **Step 4: Run Python RED/GREEN tests and offline coverage analysis fixtures.**

### Task 4: Regression verification and documentation synchronization

**Files:**
- Modify: `docs/eval/2026-09-20-socialmem-structured-coverage-diagnosis.md`
- Create: `docs/eval/2026-09-20-socialmem-source-turn-receipt-implementation.md`
- Create: `build/socialmem_20260920_source_turn_receipt/final-verification.json`

- [x] **Step 1: Build the native extension with `.venv/bin/cmake`.**
- [x] **Step 2: Run focused C++ tests, focused Python tests, and the existing local HTTP suite.**
- [x] **Step 3: Run the offline structured coverage analyzer against the frozen historical archive to establish the pre-fix comparison.**
- [x] **Step 4: Record hashes, test counts, skipped/environment failures, and the zero external-request fact.**
- [x] **Step 5: Update the diagnosis with the new evidence and remaining predicate/admission work; do not call coverage a QA/F1 gain.**
