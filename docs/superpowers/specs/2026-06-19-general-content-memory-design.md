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

# General-Content Memory (Sub-Project C) — Design
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **2026-09-11 契约补充**：三通道 C++ 编排将通用事实保持在旧策略路径。 当前扩展见 [已确认语义证据设计](2026-09-11-source-grounded-claim-contract-design.md)。下文保留本版本原有适用范围。


**Date:** 2026-06-19
**Status:** Approved (design); pending implementation plan.
**Context:** Final stage of the general-memory arc (A episodic events ✅ → B perception/knowledge ✅ → **C arbitrary content**), driven by "end-to-end ToMBench showed the claim extractor extracts 0 from non-conversational, non-event text." A added a physical-event pass; B added perception/knowledge tracking; the grounding sequence (resolution/completeness/configurability ✅) fixed entity/theme grounding and made prompts/vocab/thresholds injectable. **C closes the remaining extraction gap:** declarative world-facts that fall through BOTH existing passes — definitions ("X is a Y"), statives, relationships ("A reports to B"), quantities ("the budget is $40k"), attributes — produce **zero statements** today (`_memory_core.py` runs only the belief pass + the episodic pass; no catch-all). The A spec's Non-goals explicitly defer "**arbitrary unstructured content**" to C (`docs/superpowers/specs/2026-06-17-episodic-event-memory-design.md:13`).

---

## 1. Goal & scope

Add a **third extraction pass** ("general fact") to `remember` that captures arbitrary declarative facts as **self-held `BELIEVES` statements**, so any text becomes recallable structured facts. The pass **reuses the existing belief `Extractor`** (no new C++ extractor): a new general-fact prompt produces the same claim-JSON schema the belief `Extractor` already parses/validates/writes, with `holder=self`, `perspective=FIRST_PERSON`, `modality=BELIEVES`, a general predicate, and the value as object. A new curated **`kGeneralFactPredicates`** class makes common attributive/relational predicates core (so they are approved, not downgraded to `REVIEW_REQUESTED`), mirroring A's `kActionPredicates` and B's `kPerceptionPredicates`.

**Decisions locked (brainstorming):**
1. **Direction = general arbitrary-content memory** (not the remaining ToMBench cognitive dimensions — emotion/desire/intention/non-literal are out of scope here).
2. **Representation = self-held `BELIEVES`** + a 4th curated predicate class. No new modality, no schema migration.
3. **Recall = extraction-first.** Self-held facts hit the existing default `recall(holder=self, perspective=first_person)` — no new recall surface, no holder-agnostic search.
4. **The third pass is ON by default** (`general_fact_prompt` defaults to the new constant; `remember` always runs three passes). Cost: one extra LLM call per `remember`, accepted for out-of-the-box general-content memory.

**Why reuse the belief Extractor (not a new extractor):** the belief `Extractor` is prompt-driven — it parses the LLM's claim-JSON, runs `validate_extracted_statement`, resolves the cognizer surface via `CognizerHub`, and writes (`src/memory/memory_ops.cpp:66-69`). The "conversation machinery" lives in the *prompt*, not the C++. A general-fact prompt that emits the same JSON schema (`prompts.py:21`) is handled identically. This makes C mostly **prompt data + one predicate class + wiring**, the lightest of the three sub-projects.

**Out of scope (deferred):**
- **Holder-agnostic / cross-holder semantic recall** + surfacing the verbatim engram on the recall path (the A-spec's *second* C non-goal). Self-held facts are recallable by default; a general "search everything by meaning" surface is a separate change.
- **Remaining ToMBench dimensions** (emotion/desire/intention/non-literal communication).
- **A new modality** for world-facts (`ASSERTED`/`FACT`). `BELIEVES` is reused.
- **De-duplication across passes.** The three passes may emit overlapping facts; per-statement content-hash idempotency already collapses exact duplicates, and differing framings landing as separate recall surfaces is acceptable.

## 2. Current state (file:line)

- **Two passes, no catch-all:** `python/starling/_memory_core.py:118-166` — belief via `_core.memory_remember(adapter, llm, belief_prompt, …, policy=…)` (creates the engram + extracts), then episodic via `_core.EpisodicExtractor(conn, llm, adapter, episodic_prompt).extract(…)` on the returned `engram_ref`. Content matching neither pattern → 0 statements.
- **The claim-JSON schema the belief Extractor consumes** (`python/starling/extractor/prompts.py:21`): `{"holder": str, "holder_perspective": "FIRST_PERSON"|"QUOTED"|"HEARSAY"|"INFERRED", "subject": str, "predicate": str, "object": str, "modality": "BELIEVES"|"DESIRES"|"INTENDS"|"COMMITS"|"ENFORCES"|"OBSERVES", "polarity": "POS"|"NEG"|"UNKNOWN", "nesting_depth": int}`. The general-fact prompt emits THIS shape.
- **Idempotent re-extraction is confirmed:** `src/memory/memory_ops.cpp:48-69` — `append_evidence` returns Accepted **or Idempotent** → both set `engram_ref` and **run `Extractor.run`** (only `NoStore`/`Rejected` early-return at `:57`/`:60`). So a **second `memory_remember` call with the same payload + a different prompt** re-extracts on the idempotent engram. This is the third-pass wiring.
- **Predicate registry** `include/starling/extractor/predicate_registry.hpp:16-50` — three `inline constexpr std::array` (`kCoreBeliefPredicates` {believes,doubts,forbids,knows,located_at,member_of,prefers,promises,requires,responsible_for}; `kActionPredicates`; `kPerceptionPredicates`) + `is_core_predicate` linear scan. Out-of-set non-OCCURRED predicates → `REVIEW_REQUESTED` (`statement_validator.cpp:88`).
- **Injection seam exists (from #3):** `ExtractionConfig` (`python/starling/extractor/config.py`) carries `belief_prompt`/`episodic_prompt`; `MemoryCore` stores `self._extraction` and `_build_policy`. Adding a `general_fact_prompt` field + a third pass slots into this.
- **Recall default** `_memory_core.py` `recall` → `holder = holder or self.agent`, `perspective="first_person"` → semantic retriever scopes to that holder/perspective. Self-held `BELIEVES` facts match.

## 3. Architecture

### 3.1 The general-fact prompt (new Python prompt data — the content lever)

`python/starling/extractor/general_fact_prompt.py` — `GENERAL_FACT_EXTRACTION_PROMPT` (single `{convo}` placeholder, `str.replace`, mirroring `prompts.py`). It instructs the model to extract **declarative world-facts** from any passage — the content the belief pass (focal-speaker mental-state claims) and episodic pass (physical events) skip:
- **Targets:** definitions / taxonomy ("X is a Y" → `is_a`), attributes/properties ("the server has 64GB RAM" → `has_property`/`has_value`), quantities ("budget is $40k" → `has_value`, object may be a number string), relationships ("Alice reports to Bob" → `reports_to`; "auth depends on the token service" → `depends_on`), composition ("the API is part of the platform" → `part_of`).
- **Output:** the belief claim-JSON schema (`prompts.py:21`) with `holder=`the self/agent name (a `{self}` placeholder filled by `MemoryCore` — §3.2), `holder_perspective="FIRST_PERSON"`, `modality="BELIEVES"`, `polarity="POS"`, `nesting_depth=0`, `subject`=the entity, `predicate`=a general-fact predicate (§3.3), `object`=the value (canonical short noun, or a number/string for quantities).
- **Anti-overlap guidance:** do NOT re-extract a focal speaker's *opinion/commitment* (belief pass owns those) or a *physical event* (episodic pass owns those); emit `[]` when the passage is purely conversational/eventful with no standalone declarative fact.
- The prompt is an LLM-behaviour bet steered by worked examples; real-model iteration tunes it (like A/B/completeness).

### 3.2 Wiring the third pass (`MemoryCore.remember`)

After the belief + episodic passes, run a third pass on the **same engram**:
```python
gf = _core.memory_remember(
    self.rt.adapter, self.llm, self._extraction.general_fact_prompt,
    tenant_id=self.tenant, holder_id=holder_id, interlocutor=interlocutor or "",
    adapter_name=self.adapter_name, source_prefix=self.source_prefix,
    created_at_iso8601=created_iso, payload=text.encode("utf-8"),
    policy=_build_policy(self._extraction))
# merge gf["statement_ids"] into out["statement_ids"]
```
The second `memory_remember` sees the engram as **idempotent** (same `sha256(payload)` key) → re-extracts with `general_fact_prompt` → general-fact statements (confirmed `memory_ops.cpp:48-69`). Belief + general both go through `memory_remember`/`Extractor` (different prompts); episodic stays on `EpisodicExtractor`. Statement-id merge mirrors the existing episodic merge.

**Holder = self.agent (the recall-default holder) — the one integration point to nail.** General facts must land with `holder = self.agent` so the default `recall(holder=self, first_person)` hits them. Mechanism: the `general_fact_prompt` carries a **`{self}` placeholder** (in addition to `{convo}`); `MemoryCore.remember` fills it with `self.agent` via Python `str.replace` **before** passing the prompt to `memory_remember` (whose C++ side then fills `{convo}`) — a clean two-stage fill. So every general fact is emitted with `holder=<self.agent>` + `FIRST_PERSON`, stored under the recall-default holder, robust for ANY `agent=` (default `"self"` or a custom name) and independent of how the `Extractor` treats the `holder_id` param. A custom injected `general_fact_prompt` without a `{self}` marker simply gets a no-op replace (caller's choice). **Acceptance is behavioural: a general fact is retrievable via the default `recall`/`query` for `self`** (the e2e asserts this, not the internal holder string).

### 3.3 `kGeneralFactPredicates` (new C++ predicate class)

`include/starling/extractor/predicate_registry.hpp` — add a 4th `inline constexpr std::array` and extend `is_core_predicate` to scan it (mirrors `kActionPredicates`/`kPerceptionPredicates`):
```cpp
inline constexpr std::array<std::string_view, N> kGeneralFactPredicates = {
    "is_a", "instance_of", "has_property", "has_value",
    "part_of", "related_to", "depends_on", "reports_to",
};
```
(Representative set; the plan finalizes the exact list. **No overlap** with `kCoreBeliefPredicates` — `located_at`/`member_of`/`knows` already core, so spatial/membership general facts reuse those.) These predicates are then **approved, not `REVIEW_REQUESTED`**, when emitted by the general pass. The prompt's predicate vocabulary line stays in sync with this array (the `prompts.py`↔`predicate_registry.hpp` sync convention). This is the only C++ change.

### 3.4 `ExtractionConfig.general_fact_prompt` (reuse #3's carrier)

Add a 4th field to `python/starling/extractor/config.py`:
```python
general_fact_prompt: str = GENERAL_FACT_EXTRACTION_PROMPT
```
`MemoryCore.remember` reads `self._extraction.general_fact_prompt` (default = the new constant → the third pass is ON by default, decision 4). Per-deployment override rides the existing injectable carrier.

### 3.5 Grounding reuse + recall (unchanged)

The general pass goes through the same `Extractor` → `CognizerHub` subject resolution + `normalize_theme` object normalization as the belief pass (grounding consistency, no new code). Recall is unchanged: self-held `BELIEVES` facts match the default holder/perspective scope; the embedding worker already indexes all modalities, so semantic recall over general facts works once they're stored.

## 4. Data flow

```
"Postgres is a relational database. The deploy budget is $40k. Alice reports to Bob."
→ belief pass    (no focal-speaker mental-state claim)      → []
→ episodic pass  (no physical event)                        → []
→ general pass (NEW): self BELIEVES is_a(Postgres, relational database),
                      self BELIEVES has_value(deploy budget, $40k),
                      self BELIEVES reports_to(Alice, Bob)   → 3 statements (holder=self, approved)
→ recall("who does Alice report to", holder=self) → hits reports_to(Alice, Bob)
```
Default path (no `extraction=` override): `general_fact_prompt` = the new constant, the third pass runs. With a stub/real LLM that returns `[]` for the general prompt (no declarative facts), the pass is a no-op — behaviour for belief/episodic-only content is unchanged.

## 5. Error handling

- The third pass is **best-effort** (like episodic): an empty/failed general extraction yields no statements, never crashes `remember`. The engram + belief/episodic results are unaffected (the general pass runs last on the idempotent engram).
- Overlap with belief/episodic facts → content-hash idempotency collapses exact duplicates; near-duplicates land as separate recall surfaces (acceptable).
- A general fact whose predicate is outside `kGeneralFactPredicates` (model picks a novel relation) is still **accepted**, just `REVIEW_REQUESTED` — recallable, flagged for vetting (same lightweight-tier semantics as today).
- Single-tenant/self-holder assumptions inherited from A/B.

## 6. Testing

1. **C++ ctest** (`tests/cpp/`, extend the predicate-registry/validator test): the new `kGeneralFactPredicates` members return true from `is_core_predicate`; a general-fact predicate (e.g. `is_a`) on a non-OCCURRED statement is **not** `REVIEW_REQUESTED` under the default policy; a non-registered relation still is. Confirms the 4th class is wired into `is_core_predicate`.
2. **Python e2e — roundtrip** (`tests/python/`, stub-LLM): a `make_stub_llm` returning canned declarative-fact claim-JSON (`is_a`/`has_value`/`reports_to`, `holder="self"`, `modality="BELIEVES"`, `confidence≥0.5`); `Memory.open(agent="self", …).remember(<declarative text>)`; assert the general facts (a) are **stored** with an approved review status (not `REVIEW_REQUESTED`), and (b) are **retrievable via the default `recall`/`query` for `self`** (the behavioural holder=self.agent acceptance, §3.2). **Attribution caveat (stub artifact):** the belief `Extractor` accepts the SAME claim-JSON schema, so a single `default_response` stub would let the *belief* pass also write these facts (the stub ignores the prompt; the *real* belief prompt skips declarative facts). To attribute the facts to the **general** pass specifically, EITHER prompt-key the stub so only the general prompt returns the facts (belief/episodic → `[]`; the plan computes the built-prompt hash via `Extractor.compute_prompt_input_hash`), OR rely on §6.3's spy (which proves the third `memory_remember` runs with `general_fact_prompt`) for the wiring proof and let this e2e assert only the end-to-end storage+recall. The plan picks; the default-on, holder=self.agent, approved-status, recallable assertions are the load-bearing ones.
3. **Default-on / config:** `ExtractionConfig().general_fact_prompt == GENERAL_FACT_EXTRACTION_PROMPT`; an injected custom `general_fact_prompt` is the one forwarded to the third `memory_remember` (spy, mirroring #3's wiring test).
4. **Real-model general-content eval** (`STARLING_RUN_LLM_E2E` gate; on-demand, after the tokenkey.dev budget window recovers — this spec burns no API): a small declarative-fact corpus → remember → recall, measuring general-fact grounding-rate. No fixed lift promised; the run validates the prompt elicits clean self-held facts.
5. **Regression:** ctest (650 + the new general-fact ctest) / pytest (current + new) stay green. The third pass is additive; belief/episodic/six-state/multi-order-ToM/conflict/perception/grounding/completeness/configurability pins are independent of the new prompt (their stub LLMs are prompt-keyed) and unaffected.

## 7. Constraints

Core logic is C++ where it must be — the new `kGeneralFactPredicates` class + `is_core_predicate` extension (`predicate_registry.hpp`); everything else is Python prompt data (`general_fact_prompt.py`) + carrier (`ExtractionConfig.general_fact_prompt`) + wiring (`_memory_core.py` third pass). **Reuse the belief `Extractor`** — do NOT add a new C++ extractor. Do NOT touch `canonicalize_*`, the reconstructor, `validate_*` logic, or the belief/episodic prompt *content*. No new modality, no migration. General facts are self-held `BELIEVES` and must be recallable via the default `recall` (the behavioural acceptance). `perceived_by_json` immutable. The third pass is best-effort (never fails `remember`). TDD: failing test → red → minimal impl → green → commit. After C++/binding changes rebuild with `--python-editable`; C++ tests via `.venv/bin/ctest --test-dir build`; build from repo root `/Users/jaredguo-mini/develop/memory/starling`. explicit-path `git add` (never `.`/`-A`); no `--no-verify`/`--amend`. Design phase burns no API.

**Phasing (for the plan):** ① `kGeneralFactPredicates` (C++ predicate class + `is_core_predicate` + ctest) → ② `general_fact_prompt` constant + `ExtractionConfig.general_fact_prompt` field (Python) → ③ third-pass wiring in `MemoryCore.remember` + holder=self verification + roundtrip e2e. Each phase keeps the suite green.
