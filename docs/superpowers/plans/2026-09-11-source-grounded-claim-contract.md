<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Source-Grounded Claim Contract Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。


> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans task by task. Preserve all pre-existing work; no commits or pushes are requested.

**Goal:** Implement and evaluate the approved optional semantic evidence path through native ingestion and retrieval.
**Architecture:** Native Extractor owns conservative source units, v2 parsing and a retain/reject admission completion. StatementWriter persists optional evidence; existing retrieval reads and reports it. Python exposes config/schema and runs a provenance-preserving diagnostic.
**Tech Stack:** Existing C++/SQLite/Python stack; no new dependency.
**Spec:** [approved design](../specs/2026-09-11-source-grounded-claim-contract-design.md), including the implementation clarification.

## Global constraints and sequencing

- Documentation first, failing test cases second, implementation third, offline/full validation fourth, real evaluation and analysis last.
- Default policy off; no legacy object migration, no base prompt/P1 label change, no historical archive edits.
- Identity is `(statement_id, tenant_id)`; all new secondary lookups remain scoped.
- No generated offsets, fabricated event-time anchors or quality retries.
- Current workspace contains the approved prior native changes and untracked diagnostic sources. Preserve that state and archive its content hashes and native binary before building. Work in this existing task workspace; no branch integration or commit is implied.
- Implementation tasks have disjoint file ownership. Each agent writes its tests and records the expected failure before modifying its implementation files. Main agent coordinates native configure/build/install after edits are complete.

## Task 1: Native evidence extraction and admission

**Own:** new `include/starling/extractor/claim_contract.hpp`, `src/extractor/claim_contract.cpp`; existing `extracted_statement.hpp`, `statement_validator.hpp/.cpp`, `extractor.hpp/.cpp`, `bind_06_extractor.cpp`; new focused C++/Python tests. Main agent owns CMake source-list changes.

**Interfaces:** Add `ExtractedStatement.semantic_claim_json` (string, empty for legacy); policy bools `semantic_claim_contract` and `claim_allow_code_fence` (false). Provide `claim_source_units(payload)` as JSON and `claim_extraction_prompt(payload, holder)` / `claim_admission_prompt(payload, candidates)` helpers via native bindings. Contract parsing is an independent strict v2 parser, with unchanged legacy parser. Store raw admission response/error alongside extraction attempt; bind a receipt accessor suitable for archiving both actual prompts/responses.

- [x] Write tests for v2 native ingestion, exact Chinese spans, source-only units, conditional consequence rejection, combined scopes, holder mismatch, UNKNOWN uncertainty, missing time, duplicate keys, code-fence policy, atomic failure, legacy compatibility and zero semantic retries.
- [x] Demonstrate failure before adding flags/helper/fields. A positive fixture is Mina `feels/sad about leaving the team`, `c0`, ASSERTED; a negative fixture reports Jules' emotion as Mina's FIRST_PERSON claim.
- [x] Implement strict source/schema/scope validation and preserve original object. Whole response technical errors commit no candidates. Semantic rejection is a valid empty result.
- [x] Run extraction then a single retain/reject admission through the existing LLM adapter outside the write transaction; ignore any attempted rewrite. Complete prompt/source data are archived. Contract mode may not automatically reattribute holder.
- [x] At persist, attach trusted observation time and validate the source payload/hash matches the prepared Engram. Keep malformed/transport/semantic outcomes distinguishable in the attempt receipt.
- [x] Re-run focused tests after coordinated native build; report real failures and limitations.

## Task 2: Storage and evidence-linked retrieval

**Own:** migration `0034_semantic_claim_evidence.sql`; `src/bus/statement_writer.cpp`; `src/store/sqlite_meta_store.cpp`; retrieval row/receipt headers, basic/planner/context-pack/reranker code and their bindings; storage/retrieval C++ tests. Task 1 owns ExtractedStatement field and extractor bindings.

**Interfaces:** Read `ExtractedStatement.semantic_claim_json`, persist nullable `statements.semantic_claim_json`. Expose `StatementRow.semantic_claim_json`; expose evidence annotations and source-time fallback counts in retrieval receipts. JSON `source_span` includes Engram ref, byte bounds and payload hash.

- [x] Write failure tests for optional evidence persistence/readback, source_spans consistency, old rows null, same ID in two tenants, conditional scope rendering, event/source-time distinction and native planner receipt links.
- [x] Add migration and writer support with existing transaction. Never mutate existing semantic values or evidence certificates on state-only replay.
- [x] Carry evidence through all row readers (basic, planner and MetaStore/semantic retrieval). Keep existing filtering before ranking; contract rows with inconsistent evidence fail closed with a counted reason.
- [x] Render scope/attribution/time within existing eight label scheme. Event-time ranking uses explicit intervals; unresolved time uses source recency with a receipt annotation, never a fake event interval.
- [x] Audit derived replay/ToM/reconsolidation paths: preserve unchanged source rows, retain parent lineage for new propositions, never grant copied direct-evidence certification.
- [x] Run storage/retrieval tests and report evidence-boundary checks.

## Task 3: Python surface and fixed evaluation

**Own (main agent):** Python schema/config forwarding, `CMakeLists.txt`, `tests/python/test_claim_contract_surface.py`, new 32 control fixture, `scripts/eval_socialmem_claim_contract.py`, verifier, documentation.

- [x] Update approved/pending wording in current design documents and add a synchronization matrix for historical versus active specs.
- [x] Write and run failing config/schema roundtrip tests before adding value object/flags.
- [x] Expose optional evidence schema and policy flags; reject incompatible config combinations explicitly.
- [x] Freeze 64 controls; preserve archived inputs for 50 P1, 16 synthetic and ten reviewed speaker groups. Native v2 extraction is fresh; base responses remain frozen and clearly labelled.
- [x] Write runner/verifier tests before implementation: no QA gold in extraction/admission, failures stay denominators, exact provenance/units checked, canonical multiset judge ordering, tamper rejection, separate semantic/technical counts.
- [x] Implement archive of sources, inputs, prompts, both model channels, pre-build core fingerprint, policies, databases, judgments and stage metrics. No inherited verifier requiring the old current core may be run against the new core.
- [x] Diagnostic scope: 76 fresh extractions (50 P1 + 16 synthetic + 10 speaker groups) and 64 injected fixed candidate controls; compute exact schedule from fixed inputs and assert counts before calls. Admission is at most one per valid nonempty candidate set. QA compares frozen baseline, fresh supplement with structured recall, fresh supplement with linked source excerpts, and full reviewed dialogue; use three votes each.

**Exact schedule ruling:** 50 + 16 + 10 + 64 = **140 records**, comprising **76 fresh extraction calls and 64 injected controls**. Control labels apply to the fixed candidate; asking generation to recreate it would confound admission and generation accuracy. There are no separate eight original supplement controls in the new generation track; their previous raw evidence remains historical. Maximum 140 admission calls, actual count determined by valid nonempty candidates (no content retry). Synthetic 2 arms ×16×3 =96 votes. Reviewed QA 4 arms ×2 questions =8 answers and24 votes. Total120 judge votes. Archive planned maxima and actual channel counts independently; injection/persistence does not count as a model extraction call.

## Task 4: Validation, evaluation and documentation closeout

- [x] Configure/build, install refreshed native module, full CTest and Python suites; confirm imported `_core` path/hash. Preserve before-build binary for historical replay.
- [x] Run full fake smoke and verifier before any real calls. Fix implementation errors before freezing the real run; never edit frozen executed sources mid-run.
- [x] Run the exact real schedule with existing DashScope `deepseek-v3` and `gpt-5.5` judge/answer configuration, recording endpoint/model/token limits without credentials. Native adapter handles transport retries only.
- [x] Verify every DB/receipt/source hash and exact candidate semantics; recompute native evidence and score paths without live calls.
- [x] Analyze 64 control confusion matrix, source-span/format failures, paired synthetic differences, unchanged and combined P1, Q1/Q9 raw/stored/eligible/retrieved/answered coverage. A failed quality gate is a completed diagnostic, not a proven optimization.
- [x] Update all active design documents, impacted historical-spec supersession notices, both technical reports and evaluation overview with actual status/evidence. Historical run archives and `docs/design/history` remain immutable.
- [x] Independent code review, fixes with targeted regression tests, then final checks. Report what passed and what remains experimental.

## Execution ledger

- 2026-09-11: User approved. Clarified orthogonal scope markers, conservative units, source-time authority and JSON storage before test creation. No promotion, commit or push authorized by quality diagnostics alone.


## Closeout (2026-09-12)

All approved tasks completed. [Result report](../../eval/2026-09-11-socialmem-claim-contract.md): real run complete_with_errors and archive verified; quality gates failed. Full Python 1273 passed/15 skipped, C++ 1025 passed across full suite plus isolated listener rerun. Independent review findings fixed test-first and re-reviewed. Final source/core hashes reside in the real manifest; startup failure before model calls remains separate. Defaults remain off; no full 1031-question run, commit or push. SSL failures in 2 QA answer channels and 1 judge vote remain explicit and were not replaced by extra calls or historical results.

## 声明范围后继方案（2026-09-15）

本计划保留其实施时点和勾选结果。后继[声明范围定位与覆盖诊断方案](../specs/2026-09-15-claim-scope-localization-design.md)已获用户确认并完成 L/R0 本地实现与回归，在 C++ 共享链路处理受限句首声明并提供原始行索引；无新增模型调用，不改变本计划对应历史结果。
