<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Episodic Event Memory (sub-project A) — Design
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

**Date:** 2026-06-17
**Status:** Approved (design); pending implementation plan.
**Context:** First of three sub-projects (A episodic events → B perception/knowledge → C arbitrary content) extending Starling from a conversational social-mind memory into a general open-interaction memory. Driver: an end-to-end ToMBench run revealed Starling's conversational-claim extractor extracts **0** statements from physical-action narratives ("Sally puts her ball in the basket and leaves; Anne moves it to the box"), so most ToMBench tasks (and open-interaction episodic content) cannot be ingested. A makes physical-action narratives ingestible as **episodic events**; B (separate spec) will layer perception→knowledge→stale-belief on top; together they unlock the ToMBench False-Belief and Knowledge tasks end-to-end.

---

## 1. Goal & scope

Make Starling represent, extract, store, and recall **episodic events** — "who did what to what, when, where, with whom present". Scope A to the ToMBench-critical event class first (object/location/state-change actions: put, place, move, take, give, remove, transfer, leave …), extensible to arbitrary actions. A records events only; the per-cognizer knowledge/perspective derivation ("where does B *think* the ball is") is sub-project B.

Non-goals (deferred to B/C): perception/knowledge inference (who witnessed/knows an event), access/visibility, arbitrary unstructured content, semantic vector recall over events (the embedded facade uses a stub embedder).

## 2. Current state (file:line)

- Extractor `python/starling/extractor/prompts.py` is a **conversation** extractor (focal speaker's claims); controlled predicate vocab {responsible_for, knows, prefers, promises, forbids, requires, located_at, member_of, believes, doubts}; no event/action path → physical-action narratives extract nothing (verified, real LLM).
- `Modality` enum `include/starling/schema/statement_enums.hpp:21` = mental-state attitudes only {BELIEVES, KNOWS, ASSUMES, DOUBTS, DESIRES, INTENDS, COMMITS, PREFERS, NORM_OUGHT, NORM_FORBID, RECANTED} — no event modality.
- `statements` table: holder/subject/predicate/object/modality/… + `observed_at` (ingest time); **no `event_time` column**. The design (`docs/design/system_design.md:553,948-1000`) envisions `EpisodicEvent(Statement)` + `event_time`/`perceived_by`/`EpisodicView` but explicitly defers EpisodicEvent's fields to P3 (`:1000` "未落库，排 P3"). Extension-table precedent: commitments (migrations 0018-0020).

## 3. Architecture

An episodic event is a first-class `statements` row tagged `modality=OCCURRED`, plus an `episodic_events` extension row carrying the event-specific fields. Events are Statements (not a separate table) so they flow through the existing write/consolidation/recall pipeline and can be referenced as the object of a perception/belief (which B needs: "X perceived event-E" via `object_kind='statement'`).

### 3.1 Representation (decision A1)

"Sally puts her ball in the basket" →
```
statements: { holder_id=self, holder_perspective=FIRST_PERSON,
              subject_kind=cognizer, subject_id="Sally",   # actor
              predicate="put",                              # action (§3.2)
              object_kind=entity, object_value="ball",      # theme
              modality=OCCURRED, polarity=POS,
              observed_at=<ingest>, provenance=user_input }
episodic_events (extension, keyed by statement id):
            { statement_id, tenant_id,
              seq=<monotonic ordinal within the ingestion — REQUIRED>,  # event order
              event_time=<absolute story time if stated, else NULL>,
              location="basket",        # theme's resulting location/place (nullable)
              participants_json=["Sally"],  # cognizers NAMED in THIS event (raw; B derives presence)
              action_raw="put" }        # surface verb (when predicate canonicalised/free-form)
```
"Anne moves the ball to the box" → another OCCURRED row (subject=Anne, predicate="move", object=ball) + ext {location="box", seq=2, …}. The theme's location over time is its OCCURRED events ordered by `seq` (then `event_time`); A exposes a `latest_event_location(theme)` helper for the ground-truth current state, and B derives the per-cognizer last-known location from which events each cognizer perceived.

`holder=self`: an episodic event is the system's own record of something that happened (not an attitude attributed to a cognizer). `subject`=the actor.

### 3.2 Action vocabulary (decision: curated class + free-form OCCURRED fallback)

Add a curated **action** predicate class to the registry (`include/starling/extractor/predicate_registry.hpp`): put, place, move, take, give, remove, transfer, leave, open, close (the common ToMBench/object-manipulation verbs). The validator: for `modality=OCCURRED` rows, an out-of-set predicate is **accepted as free-form** (NOT downgraded to review_requested) — open-domain actions are kept verbatim; in-set actions are canonical for matching. For non-OCCURRED (belief/relation) rows the existing strict downgrade is unchanged. `action_raw` preserves the surface verb regardless.

### 3.3 Event time & extension schema (migration, commitments-pattern)

New migration adds the `episodic_events` extension table: `statement_id` (PK, FK→statements.id), `tenant_id`, `seq` (INTEGER, monotonic event order within an ingestion — **REQUIRED** so B can order events even when `event_time` is unknown; narrative order suffices for the False-Belief sequence), `event_time` (TEXT ISO8601, nullable), `location` (TEXT, nullable), `participants_json` (TEXT, default '[]'), `action_raw` (TEXT). `event_time` lives in the extension (A scope: only events have it) — no change to the 38-field `statements` table. A `store::EpisodicEventStore` (C++, in `src/store/`, owning this table) is the single writer/reader, mirroring `SqliteStatementStore`/commitments ownership.

### 3.4 OCCURRED modality

Add `OCCURRED` to the `Modality` enum + its serialization (the modality string map in the schema/validator + the Python binding enum). This is an additive enum value; existing rows/tests unaffected.

### 3.5 Extraction (decision E1: separate episodic pass)

Add a dedicated **episodic extraction prompt** (`python/starling/extractor/episodic_prompt.py`, narrative-framed: "Given a passage, extract the physical events…") producing a JSON array of events `{actor, action, theme, location, time, participants[]}`. A C++ `EpisodicExtractor` (mirroring `Extractor`, injected with the prompt) parses + writes OCCURRED statements + episodic_events rows. `remember(text)` runs **both** passes: the existing claim `Extractor` AND the `EpisodicExtractor` (dual-pass), so any input yields both attitudes and events. Each pass is independent; an empty result from either is fine. (Per-input pass-skipping is a future optimization, not in A.)

The episodic prompt MUST: (a) emit **presence-change events (enter/leave** — in the action vocab) as their own OCCURRED rows — a departure is precisely what makes a later event unwitnessed, so it cannot be dropped; (b) assign each event a `seq` in narrative order; (c) set `participants` to the cognizers **named in that event only** — it does NOT compute who-is-present (that reconstruction from the ordered enter/leave sequence is B's job). Theme identity relies on the existing `canonical_object_hash` so "ball" links across its events.

### 3.6 Pipeline integration — events are facts, not contestable beliefs

OCCURRED events participate in **consolidation** (six-state machine) and **recall** like any statement, BUT are **excluded** from the belief-specific machinery:
- `belief_tracker` / `tom::second_order` auto-nesting already only fires for *other-holder* first-hand belief statements; OCCURRED events are `holder=self`, so they are naturally skipped — but add an explicit `modality != OCCURRED` guard to be safe.
- **Conflict arbitration**: two OCCURRED events about the same theme's location at different times are a temporal *sequence*, NOT a conflict. OCCURRED rows must be excluded from `canonical_conflict_key` conflict detection (else "ball put in basket" vs "ball moved to box" would be flagged conflicting). Guard: skip conflict-key assignment/arbitration for `modality=OCCURRED`.
This keeps existing belief/ToM/conflict pins green while letting events store + recall.

## 4. Data flow

narrative text → `remember()` → [claim Extractor → belief/relation statements] + [EpisodicExtractor → OCCURRED statements + episodic_events rows] → consolidation → recall (`query`/`recall` return events; OCCURRED rows carry their extension on read via EpisodicEventStore). B (next spec) reads these events + participants to derive perception→knowledge→per-cognizer state.

## 5. A/B boundary

A delivers: the event representation, the OCCURRED modality, the episodic_events store (incl. `seq` order + `latest_event_location` helper), the episodic extractor, dual-pass remember, and event recall. A records, per event, the `participants` named in it **plus the ordered enter/leave events** — the raw spatial-presence signal. B (separate spec) reconstructs who was *present/perceiving* at each event from that ordered sequence (a departure removes a cognizer from presence, so a later event is unwitnessed by them), then adds perception→knowledge inference, per-cognizer last-known state, and the false-belief query. A must not pre-build B; it only ensures events, `seq` order, named participants, and enter/leave events are represented + retrievable.

## 6. Error handling

EpisodicExtractor failures (bad JSON, LLM error) degrade gracefully — the claim pass still runs; remember never fails because the episodic pass returned nothing. Out-of-set OCCURRED predicates are accepted (not errors). Missing event_time/location are nullable. EpisodicEventStore writes are best-effort within the write SAVEPOINT (a failed extension write must not roll back the statement).

## 7. Testing (TDD)

- C++: `EpisodicEventStore` CRUD; OCCURRED modality round-trips; validator accepts curated actions + free-form OCCURRED predicates, still downgrades out-of-set belief predicates; conflict arbitration skips OCCURRED (two location events on one theme → no conflict flagged); belief_tracker/ToM skips OCCURRED.
- Python e2e: `remember("Sally puts her ball in the basket and leaves; Anne moves it to the box")` → OCCURRED statements for both events with correct actor/action/theme + episodic_events rows (location basket/box, participants); recall returns the events. (Real-LLM gated, like the eval harnesses.)
- Regression: ctest 610 / pytest 615 stay green (additive enum + table + extractor pass; the conflict/ToM guards are the only behavioural touches and are pinned).

## 8. Constraints

Core logic C++ (`src/`, `include/starling/`; EpisodicEventStore in `src/store/`); Python = extractor prompt + binding/adapter forwarding only. New table via migration (commitments-pattern, single-owner store). Subscriber/handler code uses SAVEPOINT. Do not break existing belief/multi-order-ToM/six-state/conflict pins. TDD; explicit-path git add; rebuild editable `_core` after C++/binding changes. Reuse the deferred `EpisodicEvent`/`event_time` design intent; do not start a parallel model.
