> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench Source-Grounded Semantic Admission

Status: real run completed with errors and verified on 2026-09-11 (Asia/Shanghai).
This executes the first next-stage gate in the
[overall optimization plan](2026-09-10-socialmem-overview.md).

The next implementation design is proposed in
[`docs/superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md`](../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md)
and was approved by the user on 2026-09-11. This report remains the historical evidence baseline; the native implementation and its [fixed real diagnostic](2026-09-11-socialmem-claim-contract.md) are complete and verified with errors (2026-09-12). New controls59/64 and strict synthetic13/16→9/16 fail promotion; the successor report separates source loss, judge instability and Q9 transport failures.

The admission gate is **not qualified for promotion**. Of 76 completions, 72
violate the strict bare-JSON protocol. Synthetic majority sufficiency falls
from **13/16 to 3/16**. Separate post-hoc envelope analysis recovers the model's
decisions but still falsely accepts **7 of 16 negative controls**. Predicate
coverage needs source-scope correctness as well as output-format reliability.

## Problem and Intervention

The independent supplemental pass preserved base memories but added incorrect
relations: belief about responsibility became interpersonal trust, cognitive
`feel that`/Chinese `觉得` became emotion, wishes became decisions, and conditional
states became current facts. Its 117 added rows and all original responses are
frozen in the verified `build/socialmem_20260910_supplement_run/` archive.

This experiment adds a source-grounded semantic admission pass to those fixed
candidates. It only retains/rejects complete existing candidate rows, without
rewriting a predicate, object, source, holder, polarity or timestamp. Each retained
row requires a model verdict supporting every semantic field and exact contiguous
quotes from the original source. Deterministic checks require a complete verdict
index set, supported schema/holder/perspective and unique exact source quotes.
Quote UTF-8 byte ranges and payload hashes are recorded in experiment receipts.

These checks establish source traceability, not semantic truth. The language
model still decides whether quoted words support the relation. That decision is
tested with positive/negative controls and downstream sufficiency judgments.
No second correction pass, output repair or quality retry is allowed. One malformed
verdict invalidates the entire admission response; all candidates then fail closed.

The existing C++ Extractor, preserved-text policy, writer and lifecycle hooks
persist the unchanged accepted rows. The original source is stored as an engram;
quote ranges stay in the experiment sidecar, not production source-span fields.
This is an experimental evaluation workflow, not a default production gate.

## Frozen Scope and Acceptance

| Track | Input records | Original candidate rows | Admission calls |
| --- | ---: | ---: | ---: |
| P1 | 50 | 41 | 18 |
| Synthetic | 16 | 17 | 14 |
| Original controls | 8 | 3 | 3 |
| Reviewed speaker groups | 10 | 56 | 9 |
| New bilingual controls | 32 | 32 | 32 |

The original 84 records include 44 nonempty inputs, 35 valid empty inputs and
five malformed upstream outputs. Four contain duplicate arrays; the fifth is a
non-object array accepted as empty by the previous native parser but rejected
by this gate's structured input parser. Empty/failed inputs do not need a model call;
upstream failures stay failures, not successful rejections. There are 76 planned
admission completions and 116 native database/replay conditions. No new extraction,
QA answer, embedding or retrieval calls are made in this round.

The 32 newly authored controls are 16 positive and 16 negative candidate cases,
balanced between English and Chinese. Eight categories contrast emotion/cognition,
actual/conditional states, interpersonal trust/belief, settled choice/desire,
relation negation/doubled denial, correct/reported bearer, affirmed/unknown
uncertainty, and preserved/missing historical time. These are fixed candidate
admission tests, not unseen extraction or benchmark accuracy tests. Gold retain
labels are never sent to the admission model.

Admission sees only source holder, source text and proposed rows. Benchmark
questions and reference answers are used only after admission, in the unchanged
canonical judge. All 16 original synthetic cases compare complete base-plus-
supplement memory before/after filtering with three fresh votes each, rotating
arm order: 32 candidates, 96 votes. Even empty or technically failed candidates
remain in the fixed denominator; technical failures cannot qualify as supported.
Both arms sort the same semantic-field projection deterministically before
serialization, preserving duplicate rows. Random statement UUIDs and insertion
order cannot change judge input when the semantic multisets are identical.

The unchanged P1 evaluator scores complete combined outputs. P1 has no gold for
the new relations, so fewer admitted rows can mechanically improve F1. Such an
increase is not evidence of semantic correctness by itself. Separate bilingual
false-accept/false-reject counts, source audit and synthetic sufficiency identify
whether a useful reduction in errors or an excessive loss of coverage occurred.
Original P1 labels and thresholds are not changed.

Promotion requires zero technical failures on the new controls, all 16 positive
controls retained and all 16 negative controls rejected, preserved base semantics,
and no synthetic sufficiency loss. Original upstream failures stay visible.
Even passing these development diagnostics would not establish representative
SocialMemBench accuracy or complete the pending time/fact-coverage work.

## Reproducibility

Runner/verifier: `scripts/eval_socialmem_admission.py`.
Controls: `tests/data/eval_socialmem_admission_controls.json`.
Admission: DashScope `deepseek-v3`, temperature 0, max tokens 4096, original
60-second timeout and three transport retries. Judge: `gpt-5.5`, max tokens 8,
three votes using the existing canonical prompt and transport adapter.

Inputs, templates, executed source files, parent verification hash and current
native binary hash are frozen before calls. The parent archive is never edited.
Verification checks all frozen source/input hashes, exact model prompts,
recomputed admission/quote decisions, native database hashes and source payloads,
native semantic replays, judge inputs/verdicts and recomputed metrics.
Any inherited, admission, native, fidelity, scoring or judge technical failure
sets `complete_with_errors`. Verification success establishes reproducibility;
its receipt also retains the run status and each error count. Error counts by
stage can overlap when one upstream failure propagates through persistence.

Offline smoke uses source-quoting retain-all FakeLLM replies and fixed NO judges;
it verifies 116 databases/replays and 96 votes but is not quality evidence.

```sh
.venv/bin/python scripts/eval_socialmem_admission.py run \
  --previous build/socialmem_20260910_supplement_run \
  --out build/socialmem_20260911_admission_run

.venv/bin/python scripts/eval_socialmem_admission.py verify \
  build/socialmem_20260911_admission_run
```

## Real Results

Archive: `build/socialmem_20260911_admission_run/`. All 76 planned admission
completions and 96 judge votes completed; all transports succeeded and all judge
votes were valid. The verifier checked 116 databases and native semantic replays,
source payloads, executed source hashes, exact judge inputs and recomputed scores.
Manifest status is `complete_with_errors`; receipt status `verified` establishes
artifact consistency, not a passing quality gate.

| Track | Candidate rows | Strictly retained | Envelope sensitivity only |
| --- | ---: | ---: | ---: |
| P1 | 41 | 0 | 16 |
| Synthetic | 17 | 2 | 17 |
| Original controls | 3 | 0 | 2 |
| Reviewed speakers | 56 | 18 | 47 |
| New bilingual controls | 32 | 0 | 23 |

Five upstream failures propagate unchanged: four duplicate-array P1 responses
and Q9 Dev's array-of-arrays response. The previous native parser silently
discarded the latter's eight non-object rows and reported successful empty
extraction. This gate detects that input-schema failure explicitly. The 72 new
strict-admission failures all begin with a Markdown fence. Together these cause
77 failed supplemental native conditions; stage counts overlap. There are no
base-persistence, object-fidelity or P1-scoring failures.

All 89 original P1 statements remain intact. With all 41 supplemental P1 rows
removed, holder/perspective/predicate-object F1 returns from .5970/.5572/.6269
to .7500/.7000/.7875; depth remains .5455. This is deletion of unmatched rows,
mostly through format failure, not evidence of better semantic extraction.
The unchanged holder, perspective and depth thresholds still fail.

The same 16 full-memory synthetic inputs receive fresh judgments in both arms:
original supplement **13/16**, strict admission **3/16**, with zero invalid
votes. The new controls score **0/32**, with **32 technical failures**. The
reported 16 positive-control false rejections overlap these technical failures;
they do not establish 16 semantic decisions to reject. No new QA was generated.
The preceding reviewed-QA evidence remains 0/2 for memory versus 2/2 for full
dialogue; there is still no representative 1,031-question result.

## Post-Hoc Envelope Diagnosis

The live run exposed frequent whole-response Markdown fences despite the bare
JSON instruction. A separate offline analysis was added after observing this
failure. It preserves the strict experiment and its scores, makes no new model
calls and does not retry or rewrite any verdict or candidate.

`scripts/analyze_socialmem_admission.py` accepts only a single complete `json`
or unlabelled code fence around the entire response. Its contents still pass
the original JSON, index, schema and exact-quote checks. Prose, multiple arrays,
multiple fences and malformed JSON are not repaired. The analysis first checks
every verified parent artifact hash and archives its own executed source.

This sensitivity analysis reports candidate decisions and control labels only.
It performs no native persistence, sufficiency judgment or QA, and cannot replace
the predeclared promotion gate. It isolates an output-envelope effect to inform
the next separately frozen protocol.

```sh
.venv/bin/python scripts/analyze_socialmem_admission.py \
  build/socialmem_20260911_admission_run \
  --out build/socialmem_20260911_admission_envelope_analysis
```

The verified-parent analysis identifies 72 whole-response fences. After that
single envelope change, 75/76 admission responses pass deterministic checks.
The remaining failure, `eval-045`, quotes `先找Bob` where the original says
`先找 Bob`; exact-quote enforcement rejects the whole verdict. No whitespace
repair is applied. The five upstream failures remain failures.

Controls become **25/32 correct**: all 16 positive controls retained, nine
negative controls rejected, and seven negative controls falsely admitted.
There are zero control technical failures in this offline sensitivity arm.

| Category | Correct controls | Remaining false acceptance |
| --- | ---: | --- |
| Emotion vs cognition | 4/4 | None in these controls |
| Actual vs conditional | 3/4 | Chinese hypothetical worry accepted as current |
| Trust vs belief | 4/4 | None in these controls |
| Decision vs desire | 4/4 | None in these controls |
| Negation | 2/4 | English and Chinese double denial both accepted |
| Attribution | 4/4 | None in these controls |
| Uncertainty polarity | 2/4 | UNKNOWN accepted for explicitly affirmed uncertainty in both languages |
| Time | 2/4 | Historical feelings accepted without their time qualifier in both languages |

These eight categories each have two positive and two negative cases. Control
successes do not establish general precision. Auditing the frozen original
candidates exposes further errors even after envelope handling:

- `eval-000`, `eval-035` and `eval-043`: several responsibility-as-trust and
  cognitive-as-emotion rows are correctly rejected. `eval-032/034` retain the
  explicit routing commitments absent from P1 labels.
- `eval-013`: reported current responsibility is still admitted as Bob's
  `decided_on`, with Alice's FIRST_PERSON perspective. `eval-015` still admits
  Charlie's inferred responsibility belief as `trusts` with FIRST_PERSON.
- `decision_change`: both original supplemental rows are retained despite
  missing `last week` and `today`. All 17 synthetic supplemental candidates
  survive this sensitivity arm, including that known temporal defect.
- Q1 Claudette's doubled negative `feels/not convinced` is rejected, but Q9
  Marcus's topic-free `indifferent_to/either way` remains admitted.
- `zh_conditional_no`: the model quotes only the consequence, `我会担心自己的合同`,
  omitting the conditional antecedent. The quote is exact and unique, yet does
  not establish an actual current state.

The sensitivity arm would retain 82 of the 117 original valid candidate rows.
That is not an estimate of precision, coverage or benchmark gain. Its accepted
rows were not persisted or rejudged, and the original strict scores are unchanged.

## Implementation Verification

Independent review identified three defects before any real calls: random UUID
ordering in judge inputs, overlapping source-quote occurrences counted as unique,
and completed runs hiding technical errors in their status. All three were
reproduced with focused regression tests, repaired and reviewed again.

The fresh `build/socialmem_20260911_admission_smoke_v2/` archive verifies 116
databases and native replays, 76 fake admission calls and 96 fixed NO votes. It
correctly reports five inherited failures in `complete_with_errors` and zero
new admission/native fidelity/judge failures. The earlier smoke archive remains
unchanged and is superseded for this implementation check.

Final Python suite: **1,186 passed, 15 skipped**; log:
`build/socialmem_20260911_admission_pytest_final.log`. This includes seven tests
of the separate envelope diagnosis. `git diff --check` passes. No C++ source or
native binary was changed in this stage; the last full C++ result belongs to the
preceding supplement stage. Native binary SHA-256 remains
`080c933c343519620b603b99fe0715c25218fe76c563b92554d68a3bf0b6e569`.

## Decision and Next Work

Keep this gate experimental. The frozen positive/negative, format and synthetic
non-regression requirements all fail. No production predicate, extraction,
retrieval or threshold default changes in this stage.

1. **Output contract:** define a separately versioned single-array/single-fence
   envelope policy, using the tested offline handler as evidence. Keep duplicate
   arrays, prose and malformed rows explicit failures. Do not relabel this run
   as successful or treat its post-hoc analysis as a fresh evaluation.
2. **Field and scope contracts:** enforce unambiguous structural invariants such
   as FIRST_PERSON subject/holder agreement and the uncertainty relation's
   polarity contract. Evaluate negation and attribution at the clause level;
   English/Chinese string matching alone must not substitute for scope parsing.
3. **Clause evidence and time:** record actor, proposition, negation, asserted
   versus conditional status, topic and event-time qualifiers independently.
   Require the whole clause, including antecedents, to support a retained row.
   Source utterance timestamps must remain distinct from event time.
4. **Fresh acceptance and QA:** freeze new bilingual contrasts beyond these
   development cases, then rerun the fixed regression controls and synthetic
   comparison. Review Q1 residence/history and Q9 earlier/later evidence before
   returning to source-linked retrieval and fresh paired QA. Representative
   evaluation remains downstream of these gates.

The admission implementation, three reviewer fixes, offline envelope diagnosis
and real diagnostic execution are complete. Output-contract promotion, stronger
semantic admission, clause inventory and broader QA remain uncompleted work.
