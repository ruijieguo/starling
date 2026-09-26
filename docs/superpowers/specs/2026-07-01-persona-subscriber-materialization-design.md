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

# PersonaSubscriber — Persona Materialization Wiring — Design
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

**Date:** 2026-07-01
**Status:** design approved (brainstorming); pending writing-plans → /plan-eng-review → subagent-driven
**Slice:** E in the queue E→D→F→A (persona materialization live-wiring)

## Why this slice

`PersonaContainer::rebuild` (materializes a holder's persona container from anchor
statements) has **no live production caller** — invoked only in
`tests/python/test_m0_8_bindings.py`. The only live reader,
`src/hippocampus/working_set.cpp:103` (`PersonaContainer(adapter).read(...)`),
therefore reads a persona that is **never materialized in production**, so the
Working Set's `## About me` block is always empty.

**Premise (confirmed by scoping): an intentional defer of a real feature, not a
bug.** The spec (`docs/design/subsystems_design/07_neocortex.md:119`) designs
persona as the **SLOW channel** — updated per **Replay period**
(`statement.consolidated`), distinct from the fast/Belief channel (per
`Bus.write`). `quickstart.py:8` annotates it: *"not auto-built in P2.e."* The
trigger wiring was deliberately deferred; this slice builds it.

**Honesty check — passes (unlike the abandoned c2.1).** There is a **real
consumer**: once the container is populated, `working_set.read()` renders the
`## About me` block into the recall context injected into converse/query — a
user-visible improvement (the agent's self-model grounds its responses). This is
not inert theater; it closes a real, consumer-backed gap.

## Decisions (locked in brainstorming)

- **Trigger = `statement.consolidated`** (the spec's slow channel), NOT
  `statement.written` (that would violate the slow-channel design and create a
  per-write stampede). Also consume `statement.superseded` (anchor correction →
  rebuild — CommonGround precedent). This keeps the abandoned c2.1 dimension-CAS
  **correctly deferred** (low rebuild volume; revisit only on measured need).
- **Anchor scope = all consolidated+approved statements about the holder** —
  `subject_id = holder AND consolidation_state = 'consolidated' AND review_status
  = 'approved'`. Classify each: `holder_id == subject_id` → `self_model_anchor`,
  else `profile_anchor`; `predicate → dimension`, `object_value → value`,
  `confidence → confidence`. No persona-predicate allowlist (no spec basis).
- **Persona keying + per-subject rebuild (verified vs `working_set.cpp:103-104`).**
  A persona is keyed by the **`subject_id`** it describes; `PersonaContainer::rebuild`'s
  `holder_id` param semantically receives that `subject_id`. `working_set` reads
  `PersonaContainer.read(tenant_id, p.agent_id)` — i.e. **self's** persona
  (`subject == agent_id`) as the `## About me` block (comment: "self 锚点仲裁结果").
  So PersonaSubscriber rebuilds the persona of **every affected subject** — it
  processes system-level `bus_events` and cannot know which subject is "self"
  (that's a read-side notion of the caller's `agent_id`). Self's persona is the
  one `working_set` reads today (the primary live consumer); other cognizers'
  personas materialize via the same uniform mechanism (latent consumers:
  perspective-taking / "what do I know about X"). **Not inert theater** — the
  primary case has a live reader, and the per-subject generality is the
  mechanism's nature, not separate code.

## Architecture

A new `PersonaSubscriber` (C++), mirroring `src/tom/common_ground_subscriber.cpp`,
registered as **SubscriberPump slot #8**. The subscriber (trigger consumption +
anchor classification + rebuild orchestration) is CORE semantics → C++. Python
only adapts (nothing needed — it runs inside the C++ pump). `working_set.read()`
needs no change (auto-populates once the container exists).

```
statement.consolidated / .superseded (bus_events)
        │  (accumulated since persona_subscriber_checkpoint)
        ▼
PersonaSubscriber::tick_one_batch  (SubscriberPump slot #8, SAVEPOINT-isolated)
        │  dedup affected (tenant, subject_id) holders
        ▼  per holder: query consolidated+approved statements → classify → vector<AnchorStatement>
PersonaContainer::rebuild(conn, tenant, holder, sources, now_iso)   ← existing, unchanged
        │  (whole-row version CAS; ConcurrentRebuildError swallowed, CG precedent)
        ▼
containers row (kind='persona') populated
        ▼
working_set.read() → "## About me" block in the recall context   ← the real consumer
```

## Components

- **Create `include/starling/tom/persona_subscriber.hpp` + `src/tom/persona_subscriber.cpp`:**
  `static int tick_one_batch(SqliteAdapter&, Connection&, std::string_view now_iso, int batch_size = 100)`.
  1. Read `persona_subscriber_checkpoint.last_processed_outbox_sequence`.
  2. Query `bus_events WHERE outbox_sequence > ? AND event_type IN ('statement.consolidated','statement.superseded') ORDER BY outbox_sequence LIMIT ?`.
  3. For each event, resolve the statement's `tenant_id, subject_id`; accumulate a deduped `(tenant, subject_id)` set (subject_id = the persona holder).
  4. Per holder: query all `statements WHERE tenant_id=? AND subject_id=? AND consolidation_state='consolidated' AND review_status='approved'`; classify + build `vector<AnchorStatement>`.
  5. `PersonaContainer(adapter).rebuild(conn, tenant, holder, sources, now_iso)`; swallow `ConcurrentRebuildError` (move on, CG precedent).
  6. Advance the checkpoint to the batch's max `outbox_sequence`.
- **Migration `0030_persona_subscriber_checkpoint.sql`:** singleton table (id=1 CHECK, `last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0`, `last_updated_at TEXT NOT NULL`), mirroring `0022`.
- **Register in `src/bus/subscriber_pump.cpp`:** slot #8 `run_isolated(conn, "persona", [&]{ PersonaSubscriber::tick_one_batch(adapter, conn, now_iso); })`, after belief_tracker (slot 2 emits `tom_inferred` self-statements) — slot 8 (last) satisfies ordering.

## Error handling

- `ConcurrentRebuildError`: swallowed (subscriber moves on), matching `common_ground_subscriber.cpp`. Single-writer model makes this rare.
- SAVEPOINT isolation (via `run_isolated`): a persona-subscriber failure rolls back its own savepoint without affecting sibling subscribers (the established pump pattern).
- Write-reentrancy: `rebuild` writes to `containers` — this runs inside the post-write pump / subscriber path which already uses SAVEPOINT (not `BEGIN`), so no `BEGIN` nesting (the repo's write-discipline invariant).

## Testing

- **C++ ctest `tests/cpp/test_persona_subscriber.cpp`:** seed consolidated+approved anchor statements (self + profile) → `PersonaSubscriber::tick_one_batch` → assert the persona container materialized with the correct self/profile dimensions; the checkpoint advanced; a `statement.superseded` event re-triggers rebuild; idempotent re-run (no duplicate work / checkpoint doesn't regress).
- **Python full-journey test `tests/python/test_persona_materialization.py` (the real-consumer proof):** `remember` self-facts → `tick` (Replay consolidates → emits `statement.consolidated`) → the pump's PersonaSubscriber materializes the persona → `working_set`/recall shows the populated `## About me` block. This proves the end-to-end consumer benefit (the block goes from empty to populated).

## Verify-items for /plan-eng-review

- Confirm PersonaSubscriber as a pump slot does NOT add a `tick_all` stage, so the P3.c smoke's `"persona" not in report["tick"]["stage_ms_total"]` (`tests/python/test_load_test_p3c_smoke.py`) stays valid (pump slots ≠ the 8 tick_all stages — pin it).
- Confirm `statement.consolidated` / `statement.superseded` are the exact `event_type` strings emitted by `arbitration.cpp` (the scoping cited `arbitration.cpp:207-213,275-281`).
- Confirm the `bus_events` columns used (`event_type`, `outbox_sequence`) and the `statements` columns (`subject_id`, `holder_id`, `consolidation_state`, `review_status`, `predicate`, `object_value`, `confidence`) match the real schema.
- Confirm the SubscriberPump `run_post_write` runs on the live remember path so slot #8 fires (and whether it also runs in `tick_all` — the pump is post-write; the harness's tick-drain does not run the pump, which is why the smoke assertion holds).

## REVISION (A, post-eng-review 2026-07-01) — SUPERSEDES the pump-slot decisions above

/plan-eng-review's Opus outside-voice ran the pipeline and found the pump-slot design INERT (3 blockers). Corrected design (user-chosen A = tick_all stage):

- **Invocation = a `tick_all` STAGE (after the replay stages), NOT a SubscriberPump slot.** BLOCKER-2: `SubscriberPump::run_post_write` runs in `remember`/`Bus::write`, NOT in `tick_all`; consolidation happens in tick's replay. So persona rebuild must run as a tick stage right after replay (mirroring how `tick_all` already calls `CommonGroundSubscriber::tick_one_batch` as a stage). `PersonaSubscriber::tick_one_batch` (checkpoint-driven) is still the unit — just invoked as a tick stage. NOT also a pump slot (its trigger events are tick-driven, not post-write).
- **Trigger = `statement.derived` (+ `statement.consolidated` + `statement.superseded`).** BLOCKER-1: `statement.consolidated` fires ONLY on reconsolidation (`arbitration.cpp:213/281`); normal volatile→consolidated via replay `op_compress` emits **`statement.derived`** (`replay_scheduler.cpp:376`). Include all three (derived = normal consolidation; consolidated = reconsolidation; superseded = correction).
- **anchor `review_status IN ('approved','review_requested')`.** BLOCKER-3: remembered self-facts default `review_requested` and never auto-reach `approved`; the old `approved`-only filter excluded exactly the target. (Still exclude `rejected`/`pending_review`.)
- **Load-shedding cascade (NEW scope):** persona becomes a **9th tick stage** → add `TickStage::Persona` (SOFT lane — non-critical background, skip under DEGRADED, like projection/replay_idle) to `include/starling/governance/tick_load_shedding.hpp`; gate the persona stage via `should_run_stage`; update the load-shedding truth-table tests (8×4→9×4) + the `TickAllRecordsStageTimings` "8 entries" test (→9, persona after replay_idle).
- **P3.c smoke FLIPS:** `tests/python/test_load_test_p3c_smoke.py` currently asserts `"persona" not in stage_ms_total`; persona is now a tick stage → update to assert persona IS among the (now 9) tick stages.
- **e2e consumer-proof = `render_working_set().render()`'s `## About me` block** (MAJOR-4), distinct from the `## Relevant memories` block (both would contain the anchor value — assert the About-me section specifically). NOT `Memory.query`'s `context_pack` (which `render_pack` builds from recall entries only, no persona).
- **Test helpers purpose-built** (MAJOR-5): the CG `insert_statement`/`insert_bus_event` signatures are incompatible (`insert_bus_event` hardcodes `event_type='statement.written'`); write fresh seed helpers taking `object_value`/`event_type`/`review_status`.

**The PLAN (`2026-07-01-persona-subscriber.md`) must be REWRITTEN for this tick-stage design + re-run through /plan-eng-review (the outside-voice must re-verify: a tick-stage-after-replay sees the just-emitted `statement.derived`; `review_requested` includes self-facts; `render_working_set` surfaces the persona).**

## Non-goals (deferred)

- **c2.1 dimension-level Container CAS** — stays deferred. The slow channel keeps rebuild volume low; revisit only if a measured need appears (the P3.c harness, now on main, can measure it). Full rebuild from all sources is used here.
- **Incremental rebuild** — `PersonaContainer::rebuild` takes the full sources list; incremental (delta) rebuild is c2.1 territory.
- **A persona-predicate allowlist** — all consolidated+approved statements feed the persona (per the locked decision).
