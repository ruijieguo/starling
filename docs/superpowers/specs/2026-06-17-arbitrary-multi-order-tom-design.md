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

# Arbitrary Multi-Order Theory-of-Mind — Design
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

**Date:** 2026-06-17
**Status:** IMPLEMENTED (2026-06-17) — plan `docs/superpowers/plans/2026-06-17-arbitrary-multi-order-tom.md`; commits `c530c80`..`a4884b2` on main; ctest 599 / pytest 614; final review APPROVED.
**Owner ruling (2026-06-17):** Starling structurally represents mental states, so
it MUST support *arbitrary* multi-order nested-belief reasoning ("self believes X
believes Y believes Z believes …"). The current deliberate cap at 3rd-order
(`nesting_depth ≤ 2`, "成人三阶 ToM 容量约束", `09_tom.md:120`) is lifted.

---

## 1. Goal

Make nested-belief **representation, production, and recall** support arbitrary
nesting depth, bounded only by *principled runaway guards* (cycle detection +
configurable soft resource caps), not by a hard semantic order cap. After this
change a caller can store, auto-produce, and fully recall an N-deep belief chain
for any N within the configured resource ceiling.

Non-goal: changing the *first-order* flat-extraction path (LLM still emits
`object_kind='str'`), the six-state consolidation machine, conflict arbitration,
or the Bus event model beyond decoupling one mislabeled field (§4.B).

## 2. Current state — the three coupled caps (file:line)

Depth↔order: `nesting_depth=0` = 1st-order (flat "X believes P"); `=1` = 2nd-order
("self believes X believes P"); `=2` = 3rd-order; etc.

| # | Mechanism | Location | Effect today |
|---|-----------|----------|--------------|
| 1 | Representation hard cap | `src/tom/nesting_depth_writer.cpp:34` `if (result > 2) throw NestingDepthOverflow` (type `include/starling/tom/nesting_depth_writer.hpp:8-14`, msg `"nesting_depth > 2 hard limit (P2.a)"`) | Any write that would land at depth ≥ 3 is rejected, on the universal write path `src/bus/statement_writer.cpp:335`. |
| 2 | Production-gate "chain" cap | `src/tom/second_order.cpp:125` `gate.causation_chain_len = src.nesting_depth` + `src/tom/limiting.cpp:11` `if (in.causation_chain_len >= kChainMax) return false` (`kChainMax = 3`) | The limiter is fed *nesting_depth* as if it were chain length (comment "嵌套层数即本链深度"), so producing from a depth-≥3 source is gated — a second, intentional nesting cap. |
| 3 | Cascade runaway guard | `src/tom/limiting.cpp:10` `if (in.derived_depth >= kDerivedDepthMax) return false` (`kDerivedDepthMax = 3`); `gate.derived_depth = src.derived_depth` (`second_order.cpp:124`) | Bounds the *event-causation* chain when auto-production cascades. Currently never deeply exercised because the auto path skips nested sources (`skip_nested_source`, `second_order.cpp:190`). This is the legitimate runaway guard, aligned to the Bus `CausationOverflow` cap (`include/starling/bus/bus_event.hpp:31`). |

Recall gap: `what_does_X_think_Y_believes` (`src/tom/mentalizing_more.cpp:48-100`)
filters `o.nesting_depth >= 1` and self-JOINs `i.id = o.object_value` exactly
**once** — a depth-2 outer surfaces with its depth-1 inner, but the depth-0
innermost is not recursively unwrapped. META_BELIEF intent
(`src/retrieval/retrieval_planner.cpp:158-161`) adds `AND nesting_depth >= 1` with
no upper bound. Estimator `count_to_depth` (`src/tom/depth_estimator.cpp:54-58`)
saturates at 2.

Caps #1 and #2 are the cognitive cap; #3 + the window rate-limiter
(`rate_limiter::allow_tom_inferred_write`) are the runaway guards. #1 and #2 are
lifted/decoupled; #3 is kept but made configurable.

**No schema migration.** `nesting_depth` is already an unbounded `INTEGER NOT NULL
DEFAULT 0` with no CHECK constraint (`migrations/0001_initial_schema.sql:57`); every
cap is enforced in C++. This change touches zero migrations and needs no data
backfill — existing depth-0/1/2 rows remain valid.

## 3. Architecture overview

Replace the hard order cap with **two invariants enforced at write time** and one
**configurable cascade guard**:

1. **Acyclicity (DAG):** a nested statement's `object_value` ancestor chain must
   not contain the statement itself. Belief nesting forms a DAG.
2. **Soft resource ceiling:** `tom.max_nesting_depth` (default 32) — a runaway
   guard, *not* a semantic order limit. 0/negative ⇒ unbounded (cycle guard still
   applies).
3. **Cascade ceiling:** `tom.max_cascade_depth` (default 8, replaces the hardcoded
   `kDerivedDepthMax = 3`) — bounds a single auto-production *event cascade*; deeper
   chains accrete across ticks/batches, never in one runaway cascade.

Nesting depth (a belief-structure property) and event-causation chain length (an
event-propagation property) become independent dimensions.

## 4. Components

All core logic is C++ (`src/tom/`, `include/starling/tom/`); Python is binding
forwarding only. New bindings that issue recursive SQL release the GIL
(`gil_scoped_release`).

### A. Representation guard — `nesting_depth_writer` (replaces cap #1)

`compute_nesting_depth` keeps returning `parent.nesting_depth + 1` for
`object_kind='statement'`. Replace the `result > 2` throw with:

- **Cycle check (write-time ancestor walk):** before accepting, walk the parent
  chain via `object_value` (each hop loads the parent's `object_kind`/`object_value`);
  if the new statement's own id appears, throw a new `NestingCycle` exception.
  The walk is O(depth) and depth is shallow by construction. (A self-referential
  write — new row pointing at an ancestor — is the only way to form a cycle, since
  inner statements pre-exist; the walk makes the invariant explicit and defensive.)
- **Soft ceiling:** if `max_nesting_depth > 0 && result > max_nesting_depth`, throw
  `NestingDepthOverflow` (kept as the type, message updated to reference the
  configurable ceiling, no longer "hard limit (P2.a)").

`NestingCycle` and the (now soft) `NestingDepthOverflow` are caught on the ToM
auto path the same way other skips are (returned as `out.reason`, never rolling
back the frontier accounting — `maybe_persist_second_order` already wraps in a
SAVEPOINT and swallows to `reason`).

### B. Production-gate decoupling — `second_order.cpp` + `limiting` (cap #2)

The `causation_chain_len = src.nesting_depth` feed (`second_order.cpp:125`) existed
*only* to cap nesting through a misused field (comment "嵌套层数即本链深度"). It is
removed: the ToM production gate no longer feeds nesting_depth into the limiter,
and the `causation_chain_len >= kChainMax` branch is dropped from the ToM gate
(nesting is now governed solely by §4.A's cycle + soft ceiling). The single
cascade guard that remains in the gate is `derived_depth` vs `max_cascade_depth`
(§4.F) — the genuine event-causation runaway guard — so nesting depth and event
chain length are no longer conflated. (`kChainMax` / the Bus `CausationOverflow`
cap on actual causation chains is untouched elsewhere; this change only stops the
ToM path from abusing it as a nesting limiter.)

### C. Recursive recall — `mentalizing_more.cpp` (fills the core gap)

Rewrite `what_does_X_think_Y_believes` to fully unwrap the chain with a
`WITH RECURSIVE` CTE: anchor on the requested holder's `nesting_depth >= 1`
belief about the partner, then recursively join `inner.id = outer.object_value`
down to the depth-0 leaf, returning every level (`level`, `holder_id`,
`subject_id`, `predicate`, `object_kind`, `object_value`). Add a `max_unwrap`
parameter (default = `tom.max_nesting_depth`) so a pathological row cannot drive
an unbounded query. The return type grows from a single `inner` to an ordered
chain; the existing `.inner` accessor is preserved as "the immediate inner" for
backward compatibility, with a new `.chain` exposing all levels.

META_BELIEF intent recall is already depth-agnostic (`>= 1`); no change beyond
benefiting from the richer chain when callers request it.

### D. Auto-production + estimator generalization — `depth_estimator` + `second_order.cpp`

- **Estimator:** `count_to_depth` generalizes from {0,1,2} to an arbitrary-order
  estimate, monotone non-decreasing in the partner's demonstrated nesting (the
  deepest `nesting_depth` the partner authored over the 7-day window, subject to
  the existing per-depth count threshold so a single fluke does not credit an
  order). It preserves today's {0,1,2} outputs for shallow partners and extends
  upward; it may return any non-negative int. The exact monotone formula is fixed
  in the plan. Cache table unchanged (the cached value's domain widens).
- **Auto path (grounded mirroring), NOT estimator-gated:** remove the
  `skip_nested_source` hard skip (`second_order.cpp:190`) and model self's belief
  about a partner's depth-k statement → self depth-(k+1), for any k. This mirrors a
  belief the partner *actually authored*, so the partner has by definition
  demonstrated that order — an estimator gate here would be a tautological no-op for
  observed sources. (The estimator's real job is gating *fabrication* on the
  explicit path, §4.E, where the attributed belief is NOT directly observed.) Auto
  depth is therefore driven by the source's depth — partner nested statements arrive
  via multi-holder / programmatic ingestion — not by cascading: an auto-produced row
  is self-held and the auto path already skips self-held sources
  (`second_order.cpp:193`), so it never re-triggers itself. Bounds: §4.A's soft
  ceiling + cycle guard (representation), the window rate-limiter (thrash), and the
  cascade ceiling (§3.3) as defense-in-depth. The Adaptive-ToM-Order intent
  ("don't over-reason about low-order partners", `09_tom.md:289`) is preserved
  because over-reasoning = fabrication, which stays estimator-gated on the explicit
  path; mirroring an observed belief is never over-reasoning.

### E. Explicit production generalization — `persist_meta_belief` (mechanical)

Replace the `estimate(partner) < 2 → gated_order` gate (`second_order.cpp:213`)
with `estimate(partner) < target_order → gated_order`, and wrap any depth-k source
→ depth-(k+1) (it already requires a nested source). No depth-2 special-casing.

### F. Configuration

Two **configurable** limits (per the owner's 配置 intent), defaulting to
runaway-safe values. Today the related limits are compile-time `constexpr` in
`limiting.hpp` (`kDerivedDepthMax`, `kChainMax`); the plan moves these two to
runtime-config-sourced values (resolving Starling's config path) that fall back to
the defaults below. `0` for `max_nesting_depth` means unbounded (cycle guard still
applies):

| key | default | meaning |
|-----|---------|---------|
| `tom.max_nesting_depth` | 32 | soft ceiling on belief nesting; 0 ⇒ unbounded (cycle guard still applies) |
| `tom.max_cascade_depth` | 8 | ceiling on a single auto-production event cascade (replaces `kDerivedDepthMax = 3`) |

## 5. Data flow — a 4th-order belief, end to end

1. Partner P authors a depth-2 statement (P believes Q believes R) via programmatic
   / multi-agent ingestion. `nesting_depth_writer` accepts it (≤ 32, acyclic).
2. `belief_tracker_tick` observes P's depth-2 `statement.written` and — grounded
   mirroring, no estimator gate — models "self believes P believes [that]" → self
   depth-3 (4th-order), `provenance=tom_inferred`, accepted under the soft ceiling
   (≤ 32) and cycle guard. (Fabricating a belief P did NOT author — e.g. a fifth
   level P never stated — would instead go through the explicit, estimator-gated
   path of §4.E.)
3. `mem.tick()` consolidates it (salience inheritance unchanged).
4. `what_does_X_think_Y_believes(self, P)` returns the full 4-level chain via the
   recursive CTE; META_BELIEF recall surfaces the depth-3 row.

## 6. Error handling

- `NestingCycle` — write rejected; on the ToM auto path returned as
  `reason="skip_cycle"`, never persisted, never an event.
- `NestingDepthOverflow` (soft) — `reason="gated_soft_cap"`.
- Cascade ceiling hit — existing `reason="gated_limiting"`.
- All ToM-path exceptions remain swallowed inside the handler's SAVEPOINT; a ToM
  failure must not roll back the triggering statement's frontier accounting.

## 7. Testing (TDD; red→green per change)

- `tests/cpp/test_nesting_depth_writer.cpp` — REPLACE the depth-3 `NestingDepthOverflow`
  assertions (`:146-190`) with: depth 3/4/5 accepted under default config; soft-cap
  overflow throws when `max_nesting_depth` is set low; **a self-referential write
  throws `NestingCycle`**.
- `tests/cpp/test_tom_second_order.cpp` — estimator returns ≥3 for a partner who
  demonstrated depth-2+; explicit `persist_meta_belief` persists depth-3; auto path
  produces depth-(k+1) gated by estimator; cascade ceiling stops a runaway cascade.
- `tests/cpp/test_depth_estimator*` (or in the above) — `count_to_depth` arbitrary-order
  generalization.
- `tests/cpp/test_mentalizing*` — recursive CTE returns the full N-level chain;
  `max_unwrap` bounds it.
- `tests/python/test_tom2_e2e.py` — extend: seed a 3-deep multi-holder chain →
  `belief_tracker_tick` → `mem.tick()` → recursive recall returns all levels.
- No regression to ctest 589 / pytest 609 beyond the intentionally-changed cap
  assertions; six-state, conflict-arbitration, recalled-idempotency pins intact.

## 8. Spec-doc revision — `docs/design/subsystems_design/09_tom.md`

Revise `:120` ("默认追踪深度 ≤ 2；深度 3 仅显式触发（成人三阶 ToM 容量约束)") and the
field docs at `:194/:273` and Adaptive-ToM-Order `:90-95` to state: arbitrary
nesting depth, bounded by acyclicity + `tom.max_nesting_depth` (soft) +
`tom.max_cascade_depth` (cascade); estimator returns the partner's demonstrated
order (any int); the cap is a runaway guard, not a cognitive-capacity limit.

## 9. Constraints

Core logic C++ only (`src/tom`, `include/starling/tom`); Python binding-forward
only. New/changed bindings issuing recursive SQL use `gil_scoped_release`.
explicit-path `git add`; no `--no-verify`/`--amend`. Rebuild editable
`_core` after C++/binding changes (`--python-editable`); build from repo root.
Subscriber code uses SAVEPOINT, never BEGIN IMMEDIATE.
