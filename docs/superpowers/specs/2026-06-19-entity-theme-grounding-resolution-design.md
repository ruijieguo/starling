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

# Entity & Theme Grounding Resolution — Design
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **2026-09-11 契约补充**：实验文本对象保真、actor/holder 约束；旧主题规范化不变。 当前扩展见 [已确认语义证据设计](2026-09-11-source-grounded-claim-contract-design.md)。下文保留本版本原有适用范围。


**Date:** 2026-06-19
**Status:** Approved (design); pending implementation plan.
**Context:** A funded end-to-end ToMBench eval scored **0.39 (39/100)**. The diagnosis isolated the bottleneck precisely: sub-project B's perception machinery is **39/41 = 95% correct on every probe that grounds** (0 crashes, only 2 wrong beliefs), but **59/100 probes never ground** — extraction produces no `perception_state` row whose `(cognizer, theme)` matches the queried tuple. Decomposition of the no-ground misses: ~34 are the *leaver* (the initial "find X in Y" location is never extracted), ~22 are the *mover* (suspected cognizer-name surface drift), 2 are theme plurals/articles. The cause is **surface drift at the grounding seam**: extracted `subject_id` (cognizer names like "Xiao Hong" vs "XiaoHong") and `object_value` (themes like "cabbage" vs "the cabbage" vs "cabbages") are written **raw** and compared by **exact match** downstream, so identical entities split into non-matching buckets. This spec generalizes the grounding seam — deterministic, parity-safe resolution of cognizer and theme surfaces to canonical identities — instead of patching the action vocabulary per failing case. It is the first of a sequence (this **resolution** spec → extraction **completeness** spec [the "find" initial-location gap] → **configurability** spec); those two are explicitly out of scope here.

---

## 1. Goal & scope

Resolve extracted **cognizer names** and **theme surfaces** to canonical identities at the **extraction write path** (and symmetrically at the query input), so downstream exact-match grounding (ToM beliefs + B perception) stops splitting on surface drift. Deterministic and **byte-parity-safe** (the `canonical_object_hash` contract is preserved). Reuse the existing cognizer entity machinery where it fits.

**In scope:** (a) cognizer-name resolution (case / internal-whitespace / punctuation drift) via the existing `CognizerHub`/`alias_normalizer` (or a thin equivalent if that API doesn't fit — G1); (b) theme normalization (leading-article stripping + conservative singularization); (c) a two-track grounding-recall measurement.

**Out of scope (deferred, named here so the boundary is explicit):**
- **Extraction completeness** — the "find/see X in Y" initial-location gap (~34 leaver misses). That is a *prompt/extraction* change, a separate spec; resolution cannot recover a fact extraction never produced (G3).
- **Configurability** — injectable prompts/vocab/model per domain (a separate spec).
- **Coreference / nicknames** — "Hong" as a short form of "Xiao Hong" does NOT resolve here (normalized "hong" ≠ "xiaohong"); deterministic resolution covers *surface drift* only. Semantic/LLM coreference is a deferred **seam** (S7).
- **Semantic synonymy** — "cabbage" = "vegetable" is not resolved (the deferred semantic seam); a non-deterministic resolver cannot drive the parity-stable hash (decision 1).
- **Non-extraction write sources** — dashboard manual entry / directly-seeded statements bypass the extraction write path and are not resolved (the eval is extraction-driven). (S5/S8.)

## 2. Current state (file:line)

- **Extraction is LLM-based** (both passes). Belief: `python/starling/extractor/prompts.py` `EXTRACTION_PROMPT` → `src/memory/memory_ops.cpp:62` `Extractor::run` (`src/extractor/extractor.cpp:198`). Episodic: `python/starling/extractor/episodic_prompt.py` `EPISODIC_EXTRACTION_PROMPT` → `src/extractor/episodic_extractor.cpp:72`. Dual pass orchestrated in `python/starling/_memory_core.py:124-149`.
- **`subject_id` written raw, zero entity resolution:** belief `src/extractor/json_parser.cpp:97`; episodic `src/extractor/episodic_extractor.cpp:142` (actor) + the `participants_json` it writes from the event's `participants` array. Downstream ToM grounding keys on exact `subject_id` equality (`src/tom/mentalizing_shared.cpp`, `src/tom/second_order.cpp`, `src/tom/common_ground_subscriber.cpp`) and B perception keys on `cognizer_id` (= the resolved actor) + `theme_id` (= `object_value`).
- **`canonical_object_hash`:** `schema::canonicalize_object` → `canonicalize_string` (`src/schema/canonicalize.cpp:194-242`): NFC + lowercase + whitespace-fold → sha256. **Case/whitespace-insensitive only — NOT article/plural/synonym-aware.** Computed at `json_parser.cpp:116` (belief) + `episodic_extractor.cpp:145` (episodic). **C++/Python byte-parity is a hard contract** (`tests/python/test_canonicalize_parity.py`).
- **Existing cognizer entity machinery (the reuse target — G1):** `src/cognizer/cognizer_hub.cpp` (register API composing `canonical_name` + raw aliases + normalized aliases, with an **`AliasCollision`** check); `src/cognizer/alias_normalizer.cpp` `normalize_alias` (`:17-47`: trim + collapse whitespace runs + ASCII case-fold; **non-ASCII passes through, and a single internal space between tokens is NOT removed** — so it does NOT currently fold "Xiao Hong" vs "XiaoHong"); schema `migrations/0008_cognizer_schema.sql`. **This machinery is NOT called by the extraction write path today.**

## 3. Architecture

### 3.0 Decisions locked (brainstorming)

1. **Deterministic + registry-indirection** resolution. The content hash must stay deterministic + parity-stable, so resolution that affects grounding is deterministic; semantic/LLM resolution is a deferred seam that can only *populate a registry*, never drive the hash.
2. **Write-path resolution** for cognizers (store canonical ids; query inputs resolved the same way; downstream SQL exact-match unchanged).
3. **Theme normalization runs *before* `canonicalize_object`** (which is left UNCHANGED — parity intact, no hash migration).
4. **Two-track measurement** — deterministic resolution unit tests + a gated real-model ToMBench grounding-recall metric.

### 3.1 Cognizer resolution (decision 2; reuse target G1)

At the extraction write path, each cognizer surface (`subject_id`/`actor`, **and every name in `participants_json`** — G4) is passed through **`resolve_or_register(surface, tenant)` → canonical id**:
- First occurrence in a tenant **registers** a canonical entity whose **`canonical_name` is the first-seen surface, preserved verbatim** (NOT lowercased — so a lone "Sally" stays "Sally"; S5).
- Later surfaces whose **strengthened normalization** matches an existing entity's normalized aliases **resolve** to that canonical id.
- The stored `subject_id` / `participants` become the canonical id; surface variants live as the entity's aliases.

**Strengthened normalization (beyond today's `alias_normalizer`):** fold case + collapse ALL internal whitespace (so "Xiao Hong" → "xiaohong" matches "XiaoHong") + strip surrounding punctuation. This is a deterministic, ASCII-and-CJK-safe function; today's `normalize_alias` keeps the internal space, so it must be extended (or a new normalizer added) — confirmed gap (§2).

**G1 — reuse-pending-verification + fallback.** The *first* implementation step is to grep/verify `CognizerHub`'s actual public API: does a usable `resolve_or_register` (or `resolve` + `register`) exist, and does `AliasCollision` mean "resolve to the existing canonical" (usable) vs "throw" (must be caught and turned into a resolve)? **If `CognizerHub` fits, reuse it.** If its API does not expose a clean resolve-or-register, the **fallback** is a thin extraction-side `name_resolver` (its own per-tenant normalized-alias table + the same strengthened normalization) — still deterministic, still write-path, still keyed identically. The design principle (deterministic write-path name resolution) holds either way; "reuse `CognizerHub`" is the *preferred* impl, not a guaranteed-clean one.

`holder_id` needs no resolution (overridden to the agent/self at write — `json_parser.cpp:90-93`); only `subject_id`/`actor`/`participants` carry the drift.

**Why participant resolution is load-bearing for B (M3).** B's `PerceptionReconstructor` is a post-pass that reads the just-written `statements.subject_id` (actor) + `episodic_events.participants_json` to build its presence cast and to key `perception_state.cognizer_id`. Because the episodic write now stores **resolved** actor + participants (G4), the reconstructor's cast and `perception_state` are canonical ids — so a query `what_does_X_think(resolve(x), …)` matches. If participants were left raw while the actor was resolved, the cast would mix canonical + raw surfaces and presence reconstruction would silently break — which is exactly why G4 covers *every* participant, not just the actor.

### 3.2 Theme normalization (decision 3)

A new deterministic C++ function `normalize_theme(surface) → surface` (in `src/schema/`, beside `canonicalize.cpp`):
- **Strip leading articles** `the` / `a` / `an` (the safe core).
- **Conservative singularization** (the riskier half — S3): suffix rules (`-ies → -y`, `-es → ∅` after s/x/z/ch/sh or o, else `-s → ∅`), a small **irregular map** (leaves→leaf, knives→knife, …), and a **stoplist** of non-plural `-s` endings (`-ss`, `-us`, `-is`, plus specific words: bus, glass, boss, lens, series, …) so "bus"→"bus", "glass"→"glass". Unknown words pass through unchanged (no false merge). If singularization proves to mis-merge in the grounding-recall benchmark, it degrades to **article-strip-only** (the safe core) without redesign.

`normalize_theme` runs **before** `canonicalize_object` at every write site (so both the stored `object_value` and the hash are on the normalized surface) and at every query input. **`canonicalize_object` / `canonicalize_string` are UNCHANGED** — the parity test stays green, no existing hash migrates. `normalize_theme` has a single C++ implementation; Python calls it through the binding if needed (no dual-implementation parity burden).

**Applicability (M8) — must not corrupt non-theme objects.** `normalize_theme` applies ONLY to **entity / string theme** object_values (the grounding target: containers/objects like basket, cabbage, "Smarties tube"). It is **NOT** applied when `object_kind` ∈ {`int`, `float`, `bool`, `datetime`, `cognizer`, `statement`} — those pass to `canonicalize_object` unchanged (singularizing "2026" or stripping an article from a nested-statement id would corrupt it). The belief parser hardcodes `object_kind="str"` (`json_parser.cpp:100`), so belief objects ARE normalized; the conservative article-strip + stoplist rules avoid mangling incidental non-theme strings (e.g. quantity phrases), and the false-positive ctests guard it. Episodic events are always `object_kind=entity` (a theme) — always normalized.

**Provenance (M7) — asymmetry, by design.** The stored `object_value` becomes the *normalized* surface; the original phrasing ("the cabbages") survives in the **engram / raw text**, not the statement — a deliberate grounding choice (there is no theme registry, by decision 3). Cognizer surfaces, by contrast, ARE preserved (as `CognizerHub` aliases). This asymmetry is acceptable: the raw text is always recoverable from the engram.

### 3.3 Touch points — write + query symmetry (G2/S2, the silent-mismatch risk)

Resolution must be applied at **every** point where a cognizer or theme surface enters or is queried; missing one silently breaks matching. The complete enumeration (the plan implements a guard test that round-trips a plural theme + a drifted name through write→query):

| Surface | Write sites | Query sites |
|---|---|---|
| cognizer (`subject_id`/`actor`/`participants`) | `json_parser.cpp` (belief subject) ; `episodic_extractor.cpp` (actor + each participant) | inside `what_does_X_think` (the `x` and `observer` args) ; inside `does_X_know` / `FactKey` construction ; B `perceived_for_theme`/`last_known` callers |
| theme (`object_value`) | `json_parser.cpp` + `episodic_extractor.cpp` — `normalize_theme` **before** `canonicalize_object` | inside `what_does_X_think` (the `theme` arg) ; inside `does_X_know` FactKey object |

Resolution is centralized **inside the query primitives** (so any caller passing a raw name/theme — incl. the eval harness — is normalized internally), not duplicated in callers.

### 3.4 Deferred semantic seam (decision 1)

Resolution is invoked through a narrow interface (the `resolve_or_register` call + `normalize_theme`); the deterministic impl ships now. A later **semantic/LLM resolver** (coreference, synonymy) can *populate the cognizer registry's aliases* or pre-map theme surfaces — but it never computes the hash (which stays deterministic). No semantic code is built here; the seam is just the interface boundary.

## 4. Data flow

```
remember(text) → extraction (LLM) → per statement/event:
   subject_id / actor / each participant → resolve_or_register(tenant) → canonical id   [store canonical]
   object_value → normalize_theme() → canonical surface → canonicalize_object(hash)      [store normalized]
→ stored statements/events carry canonical entities → downstream exact-match grounding hits
query: what_does_X_think(x, theme[, observer]) / does_X_know(FactKey):
   x / observer → resolve;  theme → normalize_theme  → match stored canonical (SQL exact-join unchanged)
```

## 5. Parity & regression safety

- `canonicalize_object` / `canonicalize_string` **unchanged** → `test_canonicalize_parity.py` stays green; no `canonical_object_hash` migration; existing data unaffected.
- `normalize_theme`: single C++ impl, Python via binding → no dual-parity burden.
- Cognizer resolution is in the **extraction write path only** (NOT `StatementWriter`) → directly-seeded ctest (most of the suite) is unaffected; only real-extraction e2e tests exercise resolution. For a **single-surface name the canonical equals the surface** (idempotent) → existing belief/ToM/B pins stay green (S5/S8). The cognizer-registration write is **best-effort within the write SAVEPOINT**.

## 6. Error handling

- Resolution failure (hub error, malformed surface) → **fall back to the raw surface** (best-effort; never fail `remember`).
- Conservative singularization stoplist/irregular-map prevents over-merge; unknown words pass through.
- Tenant-scoped, single-scene assumption inherited from B: cross-narrative same-name collisions within one tenant are out of scope.

## 7. Testing (decision 4, two tracks)

1. **Deterministic ctest** (no LLM): `normalize_theme` (`cabbages→cabbage`, `the cabbage→cabbage`, `boxes→box`, `tomatoes→tomato`, `leaves→leaf` [irregular], and the false-positive guards `bus→bus`, `glass→glass`, `boss→boss`); cognizer resolution (`"Xiao Hong"`/`"XiaoHong"`/`"xiao hong"` → same canonical id; distinct names → distinct; first-seen surface preserved as canonical_name); a **write→query round-trip** test (a plural theme + a drifted name written via extraction, then queried, must ground — G2). The `canonicalize` parity test stays green (unchanged).
2. **Gated real-model grounding-recall** (`STARLING_RUN_LLM_E2E` / the eval gate): extend the perception eval to report **`grounding-rate`** (% probes producing any belief) as a first-class metric **separate from accuracy**, and to **decompose** the no-ground misses into *name-drift-recoverable* vs *extraction-incompleteness*. **Decomposition mechanism (M5):** for each no-ground probe, query whether ANY `OCCURRED` event for the *normalized* theme exists (with any cognizer); if an event exists, the miss is **name-drift / resolution-addressable**; if no event exists for the theme at all, it is **extraction-incompleteness** (the next spec's concern, not this one's). The report thus shows how much resolution alone can lift — G3. Exit signal = re-run the perception eval and **measure** the lift; **no fixed target is promised** (the 0.39 → ? lift is whatever the name-drift subset turns out to be; the residual leaver/extraction-incompleteness is the next spec's).
3. **Regression:** ctest 638 / pytest 624 stay green (cognizer write-resolution is the only behavioral touch; pinned by the single-surface-idempotent property).

## 8. Constraints

Core logic **C++** (`normalize_theme` in `src/schema/`; cognizer resolution wiring in `src/extractor/`; reuse `src/cognizer/` machinery or a thin equivalent); Python forwards/binds only. **`canonicalize_object` byte-parity preserved** (do not modify it). Reuse `CognizerHub`/`alias_normalizer` where the API fits (G1 fallback otherwise). Resolution **best-effort** (never fail `remember`); registration within the write SAVEPOINT. Do not break belief / multi-order-ToM / six-state / conflict / A-episodic / B-perception pins. `perceived_by_json` immutable. TDD; explicit-path `git add` (never `.`/`-A`); no `--no-verify`/`--amend`; rebuild editable `_core` (`--python-editable`) after C++/binding changes; build from repo root `/Users/jaredguo-mini/develop/memory/starling`, ctest via `.venv/bin/ctest --test-dir build`.
