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

# gist v2 Semantic Entailment Fix — Design Spec
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **2026-09-11 契约补充**：新摘要保留父链，不继承直接准入证书。 当前扩展见 [已确认语义证据设计](2026-09-11-source-grounded-claim-contract-design.md)。下文保留本版本原有适用范围。


**Date:** 2026-07-04
**Slice:** Fix the design bug that makes gist v2 semantic clustering inert end-to-end.
**Branch:** `feat/gist-semantic-entailment` (off `main@ceb4c61`).

## Problem / Root Cause

The #38-C v2 semantic-clustering gist feature (opt-in via `similarity_threshold > 0`)
clusters statements with the SAME predicate but VARIED objects by vector similarity —
that is its entire purpose (e.g. `espresso`, `cappuccino`, `latte` → one "people enjoy
coffee drinks" gist). Clustering works mechanically (`find_semantic_gist_clusters` →
`gist_candidates=1` for a coffee corpus).

But **every semantic cluster is then gated 100% of the time by the Phase-4 entailment
verify**, so no semantic gist is ever promoted. The gate
(`gist_writer.cpp` `gate_candidate`, calling `build_entailment_prompt`,
`gist_prompt.cpp:37`) checks the summary against **each varied member object
individually**, with the strict instruction that the summary must be entailed by holders
agreeing on `predicate + {that one object}` "WITHOUT adding any claim, scope, cause, or
detail not supported by the bare fact that those holders agree on this predicate +
object." A summary that generalizes ACROSS varied objects is, by construction, never
entailed by any single object → the per-member check rejects it.

**The two v2 features contradict:** semantic clustering groups varied objects; the
per-member entailment gate requires the summary to add no scope beyond each individual
object. They cannot both hold.

**Confirmed with a real LLM** (2026-07-04 dogfood, DashScope qwen-plus + text-embedding-v3):
- `member_objects.size()>1` semantic clusters form (`gist_candidates=1` at
  `similarity_threshold=0.5`) but are gated (`abstracted=0, gist_gated=1`) for both a
  loose ("coffee drinks") and a tight-synonym ("exhausted/worn out/fatigued") cluster.
- Raw entailment probes: `object=espresso` + summary "People enjoy various coffee drinks"
  → `{"entailed": false}`; `object=coffee` + "People enjoy coffee" → `{"entailed": true}`;
  even `object="worn out"` + "People feel tired" → `{"entailed": false}`. Only exact
  (same-object, v1 NORM) clusters pass.

The `FakeLLMAdapter` used in unit tests rubber-stamps `entailed=true`, so this is the
classic CI-green-but-inert-on-real-data gap — it only manifests with a real LLM.

## Goal / Non-Goals

**Goal:** Make gist v2 semantic clustering promote faithful gists when enabled, by
replacing the structurally-wrong per-member entailment (for semantic clusters only) with
a **set-level faithful-generalization** check that preserves false-merge safety.

**Non-Goals (this slice — narrow scope, decided 2026-07-04):**
- Threshold precision/recall tuning (the OTHER inert reason: real paraphrase cosine is
  only ~0.50–0.60; a safe-yet-firing `similarity_threshold` is unresolved).
- Flipping the v2 semantic default ON. `similarity_threshold` default stays `0.0` (OFF);
  v2 semantic remains opt-in. Whether to flip the default is a separate future decision
  gated on the threshold question above.
- Entity-semantic clusters: they do not exist (see Invariant below), so no work.

## Design: Set-Level Faithful-Generalization Entailment

### The clean invariant (verified in current code)

`GistCluster.member_objects` holds the distinct member object strings.
- `member_objects.size() > 1` ⟺ **semantic cluster** (varied objects). Only
  `expand_semantic_cluster` (`gist_clustering.cpp`) populates a multi-element
  `member_objects`, and it never sets `subject_id` → a semantic cluster is always
  people-norm (`subject_id` empty).
- Exact people-norm clusters and entity clusters both have `member_objects.size() <= 1`.
  Entity clusters (`find_norm_gist_clusters(by_subject=true)`) cluster by
  `(subject, predicate, canonical_object_hash)` — same hash = same object = exact. So
  entity clusters carry a subject but a single object.

Therefore the branch discriminator is exactly `cluster.member_objects.size() > 1`, and it
selects precisely the people-norm semantic clusters. Exact + entity paths are untouched.

### Why set-level (not per-member)

A faithful generalization gist must satisfy two safety properties:
1. **Coverage (false-merge safety):** every member object is an instance/case of the
   summary. A k-NN-mis-clustered outlier ("hates coffee" pulled in with espresso/latte)
   is not an instance → must gate.
2. **Tightness (no confabulated over-generalization):** the summary is no broader than
   the set of objects warrants ("people enjoy all beverages" from 5 coffee objects
   over-reaches → must gate).

**Tightness is inherently a set-level property** — a per-member call sees only one object
and cannot judge whether the summary is broader than the whole set. So the per-member
approach structurally cannot verify tightness; only a set-level check can. The set-level
check also catches coverage (it lists every object and gates if any is not an instance)
and costs **one** LLM call instead of N.

### New prompt template (people-norm semantic only)

Add `kSemanticEntailmentTemplate` to `gist_prompt.cpp`. It reuses the existing
`{"entailed": <bool>}` reply shape, so `parse_entailment_verdict` is unchanged.

```
You are the verification faculty of a memory system. A consolidation step produced a
candidate NORM summary generalizing over {holder_count} distinct holders who each
INDEPENDENTLY assert a related belief with the SAME predicate ({predicate}) but VARIED
objects:
  {objects}
Check whether the summary is a FAITHFUL GENERALIZATION of this set — (a) COVERAGE: every
listed object is an instance or case of the summary; (b) TIGHTNESS: the summary
introduces no scope, claim, category, or detail broader than this set of objects
warrants. If ANY listed object is not an instance of the summary, or the summary
over-reaches beyond what the set supports, it is NOT faithful.

Candidate summary: {summary}

Reply with ONLY a JSON object (no prose, no markdown):
{"entailed": <true if the summary covers EVERY listed object AND stays within the set's scope; false otherwise>}
```

`{objects}` is `join_with_commas(cluster.member_objects)` (the same helper
`build_norm_gist_prompt` uses). `{holder_count}` / `{predicate}` filled as elsewhere.

### New builder

```cpp
// gist_prompt.hpp
[[nodiscard]] std::string build_semantic_entailment_prompt(const GistCluster& cluster,
                                                           std::string_view summary);
```
`gist_prompt.cpp`: fill `kSemanticEntailmentTemplate` with `holder_count`, `predicate`,
`objects = join_with_commas(cluster.member_objects)`, `summary`. People-norm only — it is
never called for an entity cluster (those never have `member_objects.size() > 1`).

### gate_candidate branch (`gist_writer.cpp`)

Replace the current unconditional per-member loop (lines ~115–125) with:

```cpp
if (cluster.member_objects.size() > 1) {
    // Semantic cluster: one set-level faithful-generalization check. The summary
    // generalizes across varied objects, so per-member "no scope beyond this object"
    // is structurally wrong; verify coverage + tightness over the whole set at once.
    const extractor::LLMResponse verify_resp =
        gist_llm.generate(build_semantic_entailment_prompt(cluster, judgment.summary));
    if (!verify_resp.ok) { return GateDecision::Failed; }
    const EntailmentVerdict verdict = parse_entailment_verdict(verify_resp.raw_xml);
    if (!verdict.ok) { return GateDecision::Failed; }
    if (!verdict.entailed) { return GateDecision::Gated; }
} else {
    // Exact / entity cluster: unchanged — verify the one shared object (byte-identical).
    const std::vector<std::string> objects =
        cluster.member_objects.empty() ? std::vector<std::string>{cluster.object_value}
                                       : cluster.member_objects;
    for (const auto& object : objects) {
        const extractor::LLMResponse verify_resp =
            gist_llm.generate(build_entailment_prompt(cluster, object, judgment.summary));
        if (!verify_resp.ok) { return GateDecision::Failed; }
        const EntailmentVerdict verdict = parse_entailment_verdict(verify_resp.raw_xml);
        if (!verdict.ok) { return GateDecision::Failed; }
        if (!verdict.entailed) { return GateDecision::Gated; }
    }
}
```

Note the else-branch keeps `member_objects.empty() ? {object_value} : member_objects` so a
`member_objects.size()==1` cluster (a degenerate single-object case) still verifies its
one object exactly as today.

### Correctness (the three cases)

| Cluster | Summary | Set-level verdict |
|---|---|---|
| Tight synonyms {exhausted, worn out, fatigued, drained} | "people feel tired" | **PASS** — each an instance, not broader (old per-member wrongly gated) |
| False merge {espresso, latte, cappuccino, **hates coffee**} | "people enjoy coffee" | **GATE** — "hates coffee" not an instance (coverage) |
| Over-broad {espresso, latte, cappuccino} | "people enjoy all beverages" | **GATE** — broader than the set (tightness; only set-level can catch) |

### Behavior-neutrality

- Exact people-norm + entity clusters take the else-branch, byte-identical to today.
- Semantic clusters were 100%-gated (inert) before, and v2 semantic is default-OFF
  (`similarity_threshold=0.0`). So there is zero production behavior change; the only
  change is that an opt-in semantic run can now promote a faithful gist instead of
  gating everything.

## Files Touched

- `include/starling/replay/gist_prompt.hpp` — declare `build_semantic_entailment_prompt`.
- `src/replay/gist_prompt.cpp` — add `kSemanticEntailmentTemplate` + the builder.
- `src/replay/gist_writer.cpp` — branch `gate_candidate` on `member_objects.size() > 1`.
- `tests/cpp/` — unit tests (mechanism).
- `tests/python/` — optional parity/integration if a Python seam is convenient; primary
  end-to-end validation is the manual real-LLM re-dogfood (below).

No changes to clustering, scheduler, bindings, or Python core. `parse_entailment_verdict`
and `EntailmentVerdict` are reused unchanged.

## Testing Strategy

**Critical nuance:** `FakeLLMAdapter` returns a canned `entailed` verdict regardless of
prompt, and the OLD code already "passed" semantic clusters under a rubber-stamp
`entailed=true`. So a FakeLLM cannot demonstrate the semantic *correctness* of the fix —
it can only verify the *mechanism*. Semantic correctness is proven by the real-LLM
re-dogfood.

`gate_candidate` is file-static (anonymous namespace) → not directly unit-testable; tests
drive it through the public `write_gist_proposals` (C++) or `run_replay` (Python).
`FakeLLMAdapter` is already used from Python in `tests/python/test_consolidation_gist_llm.py`
(the natural template); a pure C++ test in `tests/cpp/` is equally fine if it records LLM
calls more cleanly. Pick the seam that lets the test assert the entailment call count/shape.

**Unit (mechanism):**
1. A semantic cluster (`member_objects` = 3+ distinct) drives `write_gist_proposals` /
   `run_replay` through a recording FakeLLM. Assert:
   - Exactly **one** entailment call is made (not N), and its prompt contains **every**
     member object (the joined set) — i.e. `build_semantic_entailment_prompt` was used.
   - With the FakeLLM returning `entailed=true`, the candidate → `Pass` (promoted).
   - With a prompt-conditional / sequenced FakeLLM returning `entailed=false` for the
     set-level call, the candidate → `Gated`.
2. An exact cluster (`member_objects` empty or size 1) still makes a per-object
   `build_entailment_prompt` call (else-branch unchanged), `entailed=true` → `Pass`.
3. Entity cluster (subject set, single object) unchanged — still entity entailment path.

Use whatever prompt-recording capability `FakeLLMAdapter` already exposes; if it lacks
per-prompt responses, a sequenced-response fake (return values in call order) suffices to
distinguish 1-call vs N-call.

**Real-LLM re-dogfood (manual, post-build) — semantics:**
Re-run the controlled dogfood (seed a semantic cluster raw, embed via
`worker.tick_one_batch` to keep the rows volatile, `run_replay("sleep")` with
`similarity_threshold=0.5`, real qwen consolidation LLM). Expected AFTER the fix:
- Tight-synonym cluster ("exhausted/worn out/…") → `abstracted=1` (a gist promoted, with
  a sensible summary), where before it was `gist_gated=1`.
- A deliberately-poisoned cluster (inject a "hates …" outlier) → still `gist_gated=1`
  (false-merge safety intact).

Record the before/after numbers in the PR description.

## Build & Commit Gates

- Build: `python scripts/configure_build.py --build --python-editable` (C++ + rebuild
  `_core`; a bare `pip install -e .` is not enough for binding/core changes). This slice
  touches no bindings, but `gist_prompt`/`gist_writer` are in `starling_core`, so the
  editable reinstall keeps `_core` in sync for the Python dogfood.
- Commit gate: full `ctest` + `pytest tests/python` green.
- clang-tidy is CI-only; write the new C++ clean by construction (identifier length ≥ 3,
  no raw-pointer arithmetic, `[[nodiscard]]` on the new builder, designated initializers,
  no new const/ref data members).
- git: explicit-path `git add` only (no `git add .` / `-A`); no `--no-verify` / `--amend`.

## Out of Scope (restated)

Threshold precision/recall tuning; v2 semantic default-flip; entity-semantic (nonexistent);
the entity and exact people-norm entailment paths (unchanged).
