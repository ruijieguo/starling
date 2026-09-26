> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](2026-09-17-socialmem-grounded-answer.md)。

> **本轮优化已验收（2026-09-17）**：相同冻结C++候选完成开发及保留集，全量392/1031=38.02%（原baseline20.47%），保留集119/298=39.93%；模型/评分保持，核心逻辑由C++统一实现。当前设计与结论见[最新报告](2026-09-17-socialmem-source-focus.md)；下文保留原阶段历史事实。

# SocialMemBench Overall Progress and Optimization
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。


> 后继结果（2026-09-13 核验）：[生成契约完整性诊断](2026-09-12-socialmem-generation.md)已完成，状态为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、对象覆盖 12/14、主题/联合各 1/14；原生技术失败 5，Q1/Q9 结构化及链接组仍为 0/3，质量门槛未通过。以下保留各自阶段的历史结果。

Updated: 2026-09-12. Execution authorized by the user's request to report, plan,
and implement improvements. This is the current navigation entrypoint.

The approved [Source-Grounded Claim Contract](../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md) is implemented in C++, with thin language bindings. Full engineering validation and independent review passed; its [fixed real diagnostic](2026-09-11-socialmem-claim-contract.md) completed and verified with errors. Controls 59/64, strict synthetic 13/16→9/16 and combined P1 decline fail the quality gates. Q1 gains from linked excerpts; Q9 linked/full are unavailable due to SSL failures. Defaults remain off.

## 2026-09-16 当前目标与进展

最终目标是补齐 Starling 社会记忆能力并提高 SocialMemBench 端到端得分。最新完成的 schema 实验仅发送16次能力探测：旧schema 8/8，新schema 6/8，提供商拒绝 uniqueItems 后停止。尚无当前版本1031题结果。后续拟贯通原生写入、来源/时间、多人物检索及证据回答，首轮采用覆盖Q1–Q9的48题配对开发评测；方案与预算待确认。下面原有表格均是历史阶段证据，不作为当前进度。

## Evidence and Coverage

Local dataset: 43 networks, 430 personas, 7,355 conversation rows and 1,031 QA
(214 multiple choice, 640 long form, 177 short answer). The four local Parquet
files were verified against their repository LFS hashes. There is no current
representative 1,031-question Starling result.

| Stage | Scope and evidence | Result and implication |
| --- | --- | --- |
| Historical ladder | 22 questions; historical code/model state | Median S_full .864, S_rag .455, S_star_oracle .789, S_star .227. A diagnostic gap, not current health. |
| Reviewed end-to-end | Q1 and Q9 Sessions 1-5; frozen ingestion | Immediate majority 0/2, sleep 1/2; full dialogue and speaker RAG 2/2. Sleep improves eligibility but Q9 still fails. |
| Native polarity | Same selected rows, new paired answers | Negative relations now render explicitly. Direct permanence probe fixed; whole-question accuracy did not improve. |
| Preference contract | 12 synthetic cases and 50 P1 cases | Subject 2/12 to 12/12; complete relation 2/12 to 11/12. Long passages still omit claims. |
| Source/time inputs | Four Q9 extraction input shapes | Eight memory answers 0/3 votes; full dialogue 3/3. All 57 rows consolidated/embedded. Missing semantics persist. |
| Predicate factors | 16 synthetic cases, P1 and scoped checks | Majority support 4/16 baseline to 14/16 vocabulary. Legacy metrics regress; duplicate GF arrays interrupt scoped runs. |
| Follow-up | 136 extraction calls | Single-array GF 7/18 to 18/18 strict JSON; native failures 2 to 0, but content loss remains. |
| Relation/coverage contracts | 236 extractions, 96 votes | Both vocabulary variants 13/16 supported. GF coverage 18/18 strict JSON, 8/8 generic exact; long-dialogue omissions and wrong subjects remain. |
| Independent supplement | 100 extractions, 6 answers, 114 votes; verified | Synthetic 3/16 to 13/16, but reviewed QA remains 0/2 in both memory arms versus full dialogue 2/2. New semantic false positives prevent promotion. |
| Semantic admission | 76 admission calls, 96 votes; 116 verified native replays | Strict gate has 72 format failures; synthetic 13/16 to 3/16. Post-hoc envelope handling scores 25/32 controls with seven false accepts. Not promoted. |
| Source-grounded claim contract |76 extractions, 92 admissions, 64 fixed injections, 8 answer attempts, 120 judge attempts; 140 native replays/144 DBs verified | Controls 59/64; synthetic 13/16→9/16 (including judge instability and technical failure); Q1 linked 2/3,full 3/3; Q9 linked/full transport failed. Not promoted. |

These denominators are different and must not be pooled. Synthetic sufficiency
judgments are not benchmark answers. Repeated votes from one model are not
independent judges. Q4 and Q9 Sessions 6-8 remain outside the reviewed scope.

Historical fresh three-arm P1 run (all 50 unchanged cases):

| Metric | Baseline | Vocabulary | Contract | Existing threshold |
| --- | ---: | ---: | ---: | ---: |
| holder | .7500 | .7037 | .7205 | .85 |
| perspective | .7000 | .6667 | .6957 | .80 |
| predicate | .7875 | .7531 | .7702 | .75 |
| object | .7875 | .7531 | .7702 | .70 |
| depth-1 | .5455 | .5455 | .5455 | .60 |

All arms fail holder, perspective and depth. The predicate/object metrics share
an exact pair matcher and are not independent semantic measures.
The subsequent frozen-base supplement preserves all 89 base statements but adds
41 unmatched rows; combined holder/perspective/predicate-object F1 becomes
.5970/.5572/.6269. Extra-label coverage and actual semantic false positives both
occur, so preserved base output does not establish compatibility.

## Problems and Priorities

1. Representation: the ten core belief predicates cannot express several common
   emotions, uncertainty, decisions, indifference and trust directly. Adding five
   relations improves targeted coverage but changes legacy extraction behavior.
2. Fidelity: native noun-theme normalization also processes full clauses,
   singularizing `colleagues`, `keys`, `upstairs` and stripping quantifiers.
   Prompt improvements cannot prevent this deterministic downstream damage.
3. Attribution and scope: desirer/target confusion, holder/perspective errors,
   doubled negation, omitted alternatives and unresolved pronouns remain.
   An enum-valid statement is not necessarily semantically valid.
4. Time and retrieval: grouping per speaker loses topic context; source windows
   do not identify claim event times. Q9 can retrieve nervousness and still
   misinterpret the earlier/later contrast. Eligibility, extraction coverage,
   selection and answer reasoning require separate measurements.
5. General facts: output-envelope compliance is improved experimentally, but
   source facts can still be omitted or assigned to the wrong entity. Increasing
   the number of rows is not a coverage metric.
6. Evaluation: only two reviewed recent QA records; judges sometimes accept
   wrong polarity or missing time qualifiers. The existing P1 labels omit
   subject, modality and polarity. No current full benchmark score is justified.
7. Admission reliability: exact source quotes alone do not validate a complete
   claim. The new model gate accepts conditional consequences, doubled negation,
   UNKNOWN uncertainty and historical feelings without time qualifiers. A bare
   JSON instruction also fails on 72/76 completions. Formatting and semantic
   error rates must be tracked separately.

## Execution Plan and Acceptance

| Priority | Work | Acceptance | Status |
| --- | --- | --- | --- |
| P0 | Explicit free-text preservation in native parsing/config | Exact object retained, hash of retained value, quantifiers remain distinct, default theme behavior and full C++/Python suites pass | Implemented and verified |
| P0 | Independent supplemental mental-state extraction | Original belief prompt/raw output retained; added relations separately measured; no question/reference in extraction; native provenance and failures archived | Implemented and evaluated; not promoted due to semantic errors and P1 gate failure |
| P0 | Bounded paired diagnostic | Original synthetic/P1 cases plus reviewed dialogue evidence; fixed denominators and negative controls; no quality retries | Complete and verified: 100 extraction calls, 6 answers, 114 votes |
| P0 | Source-grounded semantic admission | All 32 bilingual controls correct without technical failures, unchanged base semantics, no synthetic sufficiency loss | Implemented and evaluated; strict protocol fails, and offline envelope sensitivity still has seven false accepts |
| P1 | Clause evidence and structured time | Reviewed clause inventory with actor, topic, negation and temporal qualifiers; measure raw/stored/eligible/retrieved/answered coverage separately | Implemented and diagnosed; contract gates fail, source context/topic/time work remains. See current report |
| P1 | General-fact production candidate | Strict JSON and exact control coverage, plus reviewed long-dialogue fact precision/recall and attribution | Pending; existing candidate not promoted |
| P1 | Return to reviewed end-to-end QA | Frozen common base ingestion, original k=10 native selection, source-only full-dialogue control, original judge plus semantic audit | Executed; baseline and supplement both 0/2, full dialogue 2/2. Fresh complete ingestion remains pending |
| P2 | Representative evaluation | Resolve MC/temporal review queue, freeze stratified development and untouched holdout cohorts, paired controls and full run | Pending |

The supplemental pass is a bounded experiment using the existing native
Extractor and additive ValidationPolicy. Its distinct prompt handles only the
five new relations; it does not rewrite the original belief prompt. Free-text
preservation is enabled only for this path. Shared corpus ingestion must keep
normalization policy stable: changing it does not migrate previous values or
hashes, and preserved text is not intended for normalized entity-theme queries.

No production-wide vocabulary/threshold change is authorized by a diagnostic
improvement alone. Real-model compatibility and broader QA remain acceptance
work, even when deterministic tests pass. No commit or push is part of this task.

## Implemented Native Configuration

`ExtractionConfig(preserve_text_objects=True)` forwards to C++
`ValidationPolicy.preserve_text_objects`. The JSON parser retains the exact
nonblank object and calls the unchanged canonical hash API on it. It rejects
objects whose canonical text is empty. The default remains false, preserving
existing noun-theme grounding. Episodic entity objects continue to normalize.

Regression checks cover plural words, quantities, scope, relative-time text,
hash correspondence, distinct quantifiers and blank objects. Independent review
identified the blank-object bypass; a failing native integration test reproduced
it before repair. Final native build/CTest: **1,010 passed, 1 skipped**. Full
Python: **1,162 passed, 15 skipped**. The old native binary and changed source
files were retained in `build/socialmem_20260910_optimization_before/` before
rebuilding; historical archives were not changed.

The [supplemental-pass experiment](2026-09-10-socialmem-supplement.md) documents
the fixed inputs, evidence boundary and real-run results.

The subsequent [semantic-admission experiment](2026-09-11-socialmem-admission.md)
adds an optional experimental filter over 117 frozen supplemental candidates and
32 bilingual controls. All 76 model calls, 96 fresh judge votes and 116 native
replays are complete and verified with `complete_with_errors`. Five inherited
input failures and 72 new format failures remain explicit; all base memories
are preserved. Strict controls score 0/32 because all 32 responses are fenced.

A separate post-hoc analysis of those same raw responses accepts one complete
JSON code fence and reruns unchanged schema/quote checks, with no model calls,
native persistence or judge scoring. It gives 25/32 correct controls, including
16/16 positives but only 9/16 negatives. It does not revise the strict run or
establish a QA gain. P1 strict-filter F1 returns to the frozen baseline only
because all 41 additional rows are removed; this is not semantic improvement.

That admission stage completed Python validation: **1,186 passed, 15 skipped**, including admission
and envelope-diagnosis tests. This stage changes no C++ source or native binary;
the preceding full C++ result remains 1,010 passed, 1 skipped.

## Remaining Optimization Gates

Native text fidelity, the independent supplemental pass, paired QA and the first
semantic-admission experiment have been executed. The results below define the
remaining work and do not establish a production-qualified improvement.

1. **Semantic admission before widening vocabulary.** Add bilingual contrast
   cases for cognitive `feels that`/Chinese `觉得` versus emotion, belief versus
   interpersonal trust, desire versus settled decision, and conditional versus
   actual state. Keep the original P1 labels unchanged and annotate additional
   supported claims separately. Require correct subject/source, no conditional
   false positives, and full format/exact control compliance before promotion.
   The initial admission experiment is now complete but fails: 72/76 strict
   format failures, synthetic 13/16 to 3/16, and seven semantic false accepts
   even in post-hoc envelope sensitivity. Next, freeze an explicit envelope
   policy and field/scope checks; expand untouched bilingual controls before
   another fresh comparison. Complete source quotes must include conditionals
   and time, and their content must entail every retained semantic field.
2. **Clause evidence and general facts.** Review the two source dialogues at
   turn/clause granularity, then measure actor/topic/negation/time fidelity in
   raw output and stored memory separately. Extend the already tested GF
   clause-coverage candidate against a long-dialogue fact inventory. Acceptance
   requires preserving reviewed facts such as residence/history and resolving
   the subject of properties/actions, not just increasing statement counts.
3. **Time-aware evidence retrieval.** Preserve utterance order and exact source
   references; test structured recall with linked source excerpts under a fixed
   token budget. Compare it with structure-only recall and full-dialogue control.
   For Q9, answer evidence must support earlier communication style and later
   candour without treating source timestamps as the onset of a mental state.
   For Q1, retrieve residential-character/history evidence as well as traffic
   concern. Require both reviewed QA judgments and semantic evidence checks.
4. **Representative evaluation after these gates.** Resolve the remaining
   temporal and multiple-choice review queue; freeze development and untouched
   holdout cohorts stratified by question type/network/cognitive requirement.
   Rerun fresh paired full ingestion with explicit transport/failure accounting,
   then the eligible full 1,031-question corpus. Record excluded items and avoid
   selecting questions or retrying generations based on model correctness.

The immediate deployment decision is to retain the tested optional native
fidelity path while keeping the supplemental prompt and admission gate experimental. There is no
demonstrated benchmark-wide or reviewed-QA gain to justify changing defaults.

## Reports

- [Initial status and corpus](2026-09-09-socialmembench-status.md)
- [Reviewed scope](2026-09-09-socialmem-scoped.md)
- [Polarity repair](2026-09-09-socialmem-polarity.md)
- [Preference extraction](2026-09-09-socialmem-extraction.md)
- [Source and temporal experiment](2026-09-09-socialmem-temporal.md)
- [Predicate experiment](2026-09-10-socialmem-predicates.md)
- [P1 and GF follow-up](2026-09-10-socialmem-followup.md)
- [Relation and coverage contracts](2026-09-10-socialmem-contracts.md)
- [Independent supplemental pass](2026-09-10-socialmem-supplement.md)
- [Source-grounded semantic admission](2026-09-11-socialmem-admission.md)


## Current engineering evidence (2026-09-12)

The optional claim-contract implementation passed full build, 1273 Python tests (15 skipped), and 1025 C++ cases across the full run plus isolated sandbox-listener rerun. All three independent review findings were corrected after failing tests: direct Bus contract bypass, unrecorded query embedding degradation, and QA context/selection provenance. A final common native model-metadata binding correction was also test-first and revalidated before live calls. [Design synchronization inventory](../design/claim_contract_sync.md) covers all current subsystems, affected specialized specs and both technical reports. These engineering checks do not override the failed real-model quality gates.
