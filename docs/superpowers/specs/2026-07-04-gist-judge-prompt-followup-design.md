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

# gist v2 Judge-Prompt Follow-up — Design Spec
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

**Date:** 2026-07-04
**Slice:** Fix the consolidation JUDGE prompt so it produces promotable gist summaries — the second (post-entailment) blocker to gist v2 promoting end-to-end.
**Branch:** `feat/gist-judge-prompt` (off `main@c5ce05a`, which has the entailment fix PR #47).

## Problem / Context

PR #47 fixed the Phase-4 entailment gate (it no longer structurally rejects every
semantic cluster; a faithful summary now passes). But end-to-end, gist v2 still does not
promote with a real LLM: the earlier bottleneck simply moved **upstream to the JUDGE**
(`build_norm_gist_prompt` / `kNormGistPromptTemplate`), which produces summaries the
(now-correct) verify then gates.

Two failure modes, measured 2026-07-04 with real qwen-plus (temp 0):

1. **Verbose + adds interpretive scope.** Tired set {exhausted, very tired, worn out,
   fatigued, drained} → judge summary "People commonly report feeling … as a shared
   subjective experience of physical or mental depletion." The "physical or mental
   depletion" clause introduces scope beyond the objects → the set-level tightness verify
   correctly returns `entailed:false`.
2. **Over-skeptical — refuses to generalize.** Coffee set {espresso, cappuccino, latte,
   macchiato, americano} → `confidence:0.35` + a summary that is a meta-commentary:
   "…suggestive but insufficient to establish a genuine, generalizable norm without
   evidence of broader cultural, demographic, or behavioral consistency beyond this small,
   unrepresentative sample." This is not a norm sentence → fails both the confidence floor
   and the verify.

Both stem from the judge prompt's framing: "a genuine, generalizable NORM — something
people **in general** believe or do" invites demographic skepticism, and "one concise
sentence" is too weak to stop qwen adding interpretation. The system's design intent is
that ≥K independent holders IS the norm evidence (representativeness is the clustering
K-threshold's job, not the judge's) and the gist consolidates THIS memory's observed
consensus, not a claim about the wider population.

## Goal / Non-Goals

**Goal:** Reword `kNormGistPromptTemplate` so the judge (a) treats the holders' independent
agreement as sufficient evidence (no demographic/sample-size skepticism), and (b) emits one
short norm sentence adding no cause/scope/interpretation — aligned with what the set-level
tightness verify accepts — while **remaining a coherence filter** (it can still reject a
genuinely incoherent / coincidental mis-cluster via low confidence).

**Non-Goals (narrow scope, decided 2026-07-04):**
- The entity judge (`kEntityGistPromptTemplate`) — a separate default-OFF mode, not the
  validated failure; left unchanged.
- `min_confidence` floor, `similarity_threshold`, and the v2 default-OFF state — untouched.
- The entailment verify prompts (`kEntailmentPromptTemplate`, `kSemanticEntailmentTemplate`)
  — already correct (PR #47); untouched.
- Turning the judge into a pure renderer (rejected fork — keep the coherence gate).

## Design: reword `kNormGistPromptTemplate`

Replace the template (`src/replay/gist_prompt.cpp:18-28`) with:

```
You are the consolidation faculty of a brain-like memory system. Several DISTINCT holders have INDEPENDENTLY asserted the same belief. Their independent agreement IS the evidence — you are consolidating THIS memory's observed consensus, NOT judging whether the wider population holds it, so do NOT require demographic, cultural, or sample-size evidence. Judge only whether their shared belief is a COHERENT, generalizable belief worth recording as a norm, rather than a coincidental or incoherent overlap.

Candidate norm:
  predicate: {predicate}
  object: {object}
  asserted by {holder_count} distinct holders: {holders}

Reply with ONLY a JSON object (no prose, no markdown):
{"confidence": <number 0.0-1.0 — how coherent and generalizable the shared belief is, GIVEN the holders' agreement as sufficient evidence>, "summary": "<ONE short plain sentence stating ONLY the shared belief; add no cause, scope, category, interpretation, or detail beyond what the holders assert>"}
```

How each clause targets a failure mode:
- **Over-skepticism** ← "Their independent agreement IS the evidence … consolidating THIS
  memory's observed consensus, NOT judging whether the wider population holds it … do NOT
  require demographic, cultural, or sample-size evidence" + confidence reframed to "how
  coherent and generalizable … GIVEN the holders' agreement as sufficient evidence."
- **Verbose / over-scope** ← "ONE short plain sentence stating ONLY the shared belief; add
  no cause, scope, category, interpretation, or detail beyond what the holders assert" —
  deliberately mirrors the set-level verify's tightness criterion so a compliant judge
  summary passes verification.
- **Coherence gate preserved** ← "Judge only whether their shared belief is a COHERENT,
  generalizable belief … rather than a coincidental or incoherent overlap" — a truly
  mis-clustered / incoherent set still earns low confidence.

### Correctness constraint — single placeholder occurrences

`build_norm_gist_prompt` fills placeholders with `replace_first` (not `replace_all`), so
each of `{predicate}`, `{object}`, `{holder_count}`, `{holders}` must appear **exactly
once** in the template. The reworded intro deliberately says "Several DISTINCT holders"
(no count) and keeps the single `{holder_count}` in the Candidate block — a second
`{holder_count}` would be left as a literal. (Only the norm-judge template is touched;
`build_norm_gist_prompt`'s substitution code is unchanged.)

## Blast Radius / Behavior

`kNormGistPromptTemplate` is used by **every people-norm gist** — v1 (exact, same-object
clusters) AND v2 semantic (varied-object clusters). This is a wider blast radius than the
entailment fix (which was scoped to semantic clusters only). The reword is strictly
*clearer* (concise + consensus-is-evidence), so it is expected to help v1 rather than
regress it — but v1 non-regression MUST be validated (see Testing). The entity-gist path
and all thresholds are untouched.

Existing gist unit tests drive `FakeLLMAdapter` with canned `{confidence, summary}` JSON
(`set_default_response` / `SequencedLLM`); none pin the template's prose. So the reword
does not break them by construction — but that also means unit tests cannot prove the
reword *works*; that is the re-dogfood's job.

## Testing

**Unit (C++ ctest + pytest) — no regression:** full `ctest` + `pytest tests/python` green,
unchanged. The FakeLLM-driven gist tests do not pin prompt prose, so they stay green; run
them to confirm nothing depended on the old wording.

**Real-LLM re-dogfood (manual, not a CI gate) — the payoff + the v1 guard:** with real
qwen-plus + text-embedding-v3, seed volatile clusters, embed via `worker.tick_one_batch`,
`run_replay("sleep")`:
- **v2 semantic** (varied objects, `similarity_threshold=0.5`): the tired-synonym set and
  the coffee set now reach `abstracted=1` (pre-fix both were `gist_gated=1`), with a
  concise promoted summary. Capture the summary + the counts.
- **v1 people-norm** (same-object cluster, `similarity_threshold=0`): a 3-holder exact
  cluster still reaches `abstracted=1` — the reword did not regress the working v1 path.
- Optionally re-confirm false-merge safety still holds (a poisoned varied set still gates)
  — the verify is unchanged, so this is a sanity check, not the focus.

Record before/after numbers + the promoted summaries in the PR.

**Realistic success bar (LLM is stochastic).** Even at temperature 0 the verify verdict
has shown run-to-run variance, so success is NOT "abstracted=1 on every single run." It is:
(1) the judge now emits a **concise, no-added-scope** norm sentence (the primary,
directly-observable fix — inspect the summary text), and (2) at least one **clean
end-to-end `abstracted=1`** for a v2 semantic cluster within a small number of attempts
(pre-fix was a hard 0 across all attempts), and (3) **no v1 regression**. If the judge's
summaries are now concise/faithful but end-to-end promotion is still only intermittent,
that is honest signal that judge determinism (not this reword) is a further follow-up —
report it rather than tuning further in this slice.

## Build & Commit Gates

- `kNormGistPromptTemplate` is a `constexpr std::string_view` in `starling_core`. Build:
  `python scripts/configure_build.py --build --python-editable` (rebuild `_core` so the
  Python re-dogfood sees the new prompt — a bare `pip install -e .` is not enough).
- Commit gate: full `ctest` + `pytest tests/python` green.
- clang-tidy is CI-only; this is a string-literal edit (no identifiers/logic) — no new
  lint surface.
- git: explicit-path `git add` only (no `git add .` / `-A`); no `--no-verify` / `--amend`.

## Out of Scope (restated)

Entity judge prompt; confidence floor; similarity_threshold; v2 default-flip; entailment
verify prompts; making the judge a pure renderer. If the reworded judge still under-yields
end-to-end, that is a follow-up measurement — not this slice.
