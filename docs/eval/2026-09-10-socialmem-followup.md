> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench Vocabulary Isolation and General-Fact Output Follow-Up

Status: completed; all 136 conditions and offline native replays verified on
2026-09-10. Two baseline general-fact conditions failed parsing and remain in
the results.

Vocabulary alone regresses on four of five P1 metrics; nesting-depth F1 is
unchanged. The single-array intervention eliminates the two observed native
parse failures, but loses a predefined mixed-sentence fact and all six baseline
Sandra statements. Neither candidate qualifies for production adoption. This round
contains no answer generation or QA judging and establishes no SocialMemBench
accuracy improvement.

The completed [relation-contract and clause-coverage experiment](2026-09-10-socialmem-contracts.md)
now tests the next revisions. It corrects two explicit-uncertainty polarity
cases and restores mixed-clause/Sandra facts, but retains P1 regressions,
temporal loss and other semantic defects. Its synthetic majority result is
13/16 in both fresh vocabulary arms; neither candidate is promoted to production.

## Question and Fixed Scope

The [predicate/fidelity diagnostic](2026-09-10-socialmem-predicates.md) improved
synthetic support with richer predicates but regressed on P1 when combined with
broader object preservation. Three scoped memory conditions failed on duplicate
empty JSON arrays. This follow-up separates vocabulary-only P1 compatibility
from the general-fact output-envelope problem.

The two predeclared tracks use 136 new extraction calls and no answer/judge calls:

- All unchanged 50 P1 cases, fresh baseline versus the exact archived
  `vocabulary` arm. The ten original belief predicates gain the same five
  defined relations; original object-brevity rules remain unchanged. Native
  `extra_core_predicates` applies only to vocabulary. Each arm runs once per
  case, with alternating order. This round does not revise the five relations
  after observing their earlier results.
- All ten speaker-group inputs from the reviewed Q1/Q9 Sessions 1-5 corpus,
  plus eight fixed general controls, baseline versus `single_array` general-fact
  templates. The controls cover acknowledgments, preferences, physical events,
  undecided statements, definitions, quantities, organizational relations and
  a declarative property mixed with a desire. Each runs once per arm.

`single_array` adds an explicit one-array/no-fences/no-explanation instruction
and moves the existing empty-example explanation before its JSON output. It
preserves the explanation's text, inclusion/exclusion rules, predicate set,
statement schema, `{self}` and `{convo}` substitutions. This is a combined
output-instruction/example-layout intervention; its two parts are not separately
isolated here. Template inspection identifies conflicting output demonstrations
as a hypothesis, not proof of the model's internal reason for duplicate arrays.

General-fact responses use the same native belief parser and commit operation
used by `remember_extract_all` for that channel, after literal holder
substitution. Belief and episodic channels are not called in this isolated
general-fact track. It is not a repeat of the full three-channel QA experiment.

## Metrics and Failure Handling

P1 uses the original exact `(predicate, object)` matching on raw responses and
the existing thresholds. Native storage is independently archived and replayed.
Invalid prediction fields that cause the old metric function to raise are
recorded as `metric_error` and receive empty-prediction counts. This explicit
failure rule retains the fixed denominator. Successful original metric calls
are unmodified.

General-fact measurements are separate:

- `strict_json`: the entire response parses as one JSON array of dictionaries,
  with no prose or Markdown envelope. It does not establish statement validity.
- `parse_error`: the same optional-envelope check used in the preceding trial.
- `native_ok`: transport succeeded and the native commit did not report
  `extraction_failed`. Native parsing can discard individual invalid statements,
  so this is not a comprehensive schema-validity guarantee.
- `generic_exact`: on the eight controls, stored subject/predicate/object/polarity
  tuples exactly match the predefined expected tuples, ignoring case. The
  number of parsed raw statements must equal stored rows, preventing discarded
  invalid objects such as `[{}]` from passing an expected-empty control. This
  narrow metric does not independently grade all perspective/modality fields.

Every response is journaled before parsing or scoring. The native replay carries
the original `ok` and `error` flags, so a transport failure cannot become a
successful empty extraction. Each condition gets its own archived database,
including failed native pipelines. No response repair, quality retry, prompt
selection or gold injection is permitted. Transport retries remain the existing
adapter setting and are distinct from a new quality attempt.

## Provenance

- Prior verified archive: `build/socialmem_20260910_predicates_continued/`.
- New run: `build/socialmem_20260910_followup_run/`.
- Extraction: DashScope `deepseek-v3`, temperature 0, max tokens 4096;
  configuration must exactly match the prior archive.
- Query clock: `2026-09-10T09:00:00Z`.
- Actual run: `2026-09-10T07:00:00Z` to `2026-09-10T07:07:22Z`.
- Native binary: `ebd2c36a7f4a17760cdbed74da279d8c6204157102e6e79189fc365a2da4a376`.
- Actual working-tree source bytes, prompts, inputs and parent verification
  hashes are in the manifest. Preexisting local changes are retained.
- This experiment changes no production prompt or C++ defaults.

## Results

### Vocabulary-Only P1

All 100 conditions completed with successful transport, native persistence and
metric computation. The 50-case corpus and metric implementation are unchanged.
This is one paired diagnostic round, not the original P1 harness's three-round
acceptance procedure.

| Field | Fresh baseline F1 | Vocabulary F1 | Threshold | Baseline / vocabulary |
| --- | --- | --- | --- | --- |
| holder | 0.7821 | 0.7375 | 0.85 | FAIL / FAIL |
| holder_perspective | 0.7179 | 0.6750 | 0.80 | FAIL / FAIL |
| predicate | 0.8205 | 0.7875 | 0.75 | PASS / PASS |
| object | 0.8205 | 0.7875 | 0.70 | PASS / PASS |
| nesting_depth_1 | 0.5455 | 0.5455 | 0.60 | FAIL / FAIL |

Predicate/object counts `(TP, FP, FN)` change from `(64, 21, 7)` to
`(63, 26, 8)`. The shared exact `(predicate, object)` matcher makes these two
metrics identical here; they are not independent semantic measurements.
Raw/native statement counts are 85 for baseline and 89 for vocabulary.

Six case pairs have different metric count records:

| Case | Observed difference in vocabulary relative to baseline |
| --- | --- |
| eval-015 | The first matching `responsible_for/auth` claim changes holder from Alice to Bob and modality from BELIEVES to COMMITS. Holder F1 loses a match; modality is not scored. The matcher selects the first exact pair, even though a later Alice claim exists. |
| eval-019 | Adds an `ENFORCES` claim requiring Bob for authentication questions; also attributes the second responsibility claim to Bob. The additional claim increases the fixed-gold FP count. |
| eval-022 | The team-policy claim changes perspective from FIRST_PERSON to QUOTED, losing a perspective match. |
| eval-040 | Responsibility is attributed to Carol instead of Alice, and an additional `requires/Bob` claim increases FP counts. |
| eval-044 | The inferred responsibility claim changes from INFERRED to FIRST_PERSON, losing a perspective match. |
| eval-047 | Replaces canonical `responsible_for/auth` with specific task objects and preferences. Three responsibility claims incorrectly use tasks as entity subjects; the original matching pair is lost. |

These include attribution and subject/claim-selection changes, not only longer
object wording. Conversely, an additional prediction counted as FP against this
fixed corpus is not by itself proof that the source does not support it.

Only one stored P1 statement uses an added relation: `eval-041` emits
`decided_on`, with the login-timeout problem as an entity subject and recording
the impact scope as its object. That violates the trial definition's requirement
that the subject be the person who decided. This case has unchanged metric
counts: a new invalid relation replaces another unmatched prediction. Thus,
equal P1 counts do not establish equal statement validity, and most measured
regressions concern the existing relations.

Raw holders differ from the run holder 21 times for baseline and 24 for
vocabulary. As in the preceding trial, these are attribution observations, not
automatic errors; the original metric scores raw holders, while native default
storage uses the run holder.

The fresh baseline itself differs from the preceding run (for example, holder
F1 was 0.7375 and is now 0.7821) despite unchanged baseline prompt/model settings
and temperature zero. The within-round comparison shows that this candidate
has not demonstrated P1 compatibility. It does not estimate a stable effect size
or separate prompt sensitivity from model variation across repetitions.

### General-Fact Format and Control Accuracy

All 36 calls have successful transport. Native failures are separately retained.

| Measurement | Baseline | Single array |
| --- | --- | --- |
| Strict JSON array, all inputs | 7/18 | 18/18 |
| Optional-envelope parse failures | 2/18 | 0/18 |
| Native extraction successes | 16/18 | 18/18 |
| Exact predefined control tuples | 8/8 | 7/8 |

The baseline again returns `[]` followed by a fenced second `[]` for Q1
Claudette and Femi. Both native pipelines fail, with zero stored statements;
their raw responses and databases are preserved. Single array returns `[]` for
both. Nine other baseline responses are accepted by the native parser: seven
single fenced arrays and two empty arrays followed by explanations (Q1 Marcus
and Q9 Claire). This explains why strict-JSON failures exceed native failures.

All eight generic controls were inspected:

| Control | Baseline exact | Single array exact | Observation |
| --- | --- | --- | --- |
| empty_ack | PASS | PASS | Both return an empty array. |
| empty_preference | PASS | PASS | No general fact extracted. |
| empty_event | PASS | PASS | No general fact extracted. |
| empty_uncertainty | PASS | PASS | No general fact extracted. |
| definition | PASS | PASS | Both store `thermistor is_a temperature-sensitive resistor`. |
| quantity | PASS | PASS | Both store `budget has_value $40000`. |
| relation | PASS | PASS | Both store `Nina reports_to Pavel`. |
| mixed | PASS | FAIL | Baseline stores `boiler has_property noisy`; single array returns `[]`. |

The mixed input is `Lena: The boiler is noisy. I want it inspected tomorrow.`
The modified output drops the declarative property even though the prompt's
fact-inclusion text is unchanged. It is a semantic omission already visible in
the raw output, not native filtering or a failure to parse valid JSON.

### Reviewed Speaker Inputs

The following observations are a manual audit of source passages and archived
outputs, not an additional gold-scored benchmark or a complete fact inventory.

- Q9 Sandra: baseline stores six statements, while single array returns `[]`.
  Lost source information includes the app still showing Wednesday, and the
  brown, green and blue bins' respective uses. Baseline also stores the changed
  collection schedule and the parking proposal; those event/proposal encodings
  need their own semantic review. Six fewer rows does not imply six correct
  baseline facts, but the explicit bin properties make the loss concrete.
- Q9 Marcus: baseline stores seven statements and single array six. The new
  output omits the doorbell's malfunction since Tuesday and misclassifies the
  Patels household as an entity instead of a cognizer group. Baseline's
  `Marcus reports_to Swindon job` is unsupported as an organizational relation;
  the modified output instead attaches `moving end of the month` to the job as
  its subject. Neither representation correctly attributes the move to Marcus.
  Baseline also combines a negative doorbell object with NEG polarity, so it is
  not a semantic oracle for the modified arm. Both arms store the subjective
  assessment that rent is "getting stupid" as a general fact, contrary to the
  prompt's exclusion of personal opinions; this shared defect is not specific
  to single array.
- The remaining eight speaker inputs store no general facts in either arm,
  including the two baseline parser failures. A valid empty array is only a
  format/native-success observation. For example, Femi's source includes a
  consultation deadline and parking permit quantities that still warrant a
  cross-channel completeness audit; this track does not score their recall.

Together, the predefined mixed control and Sandra's output establish that
format compliance did not preserve fact coverage in this run. Because output
instructions and empty-example layout changed together, the experiment does
not identify which part caused the improvement or omissions. No response was
repaired, rerun, or removed after inspection.

## Validation and Decision

`verification.json` reports 136 archived databases and 136 offline native
replays, including the two native failures. The verifier confirms every frozen
input/source/template hash, exact call order, archived database identity,
source bytes and evidence references, pipeline states, replayed semantics and
recomputed results. All 136 recorded transport responses have `ok=true`.

Ten focused tests passed before the real run; the full Python suite reports
**1136 passed, 15 skipped** in
`build/socialmem_20260910_followup_pytest_final.log`. A complete 136-condition
FakeLLM run and its verifier also passed before real execution. These validate
the harness; they do not establish real-model semantic quality. No C++ code or
production template was changed in this follow-up, and no new C++ build is
claimed.

Keep both candidates experimental. The next predicate revision needs explicit
person-subject, relation-level polarity/modality and temporal/reference rules,
plus checks that existing responsibility and perspective behavior is retained.
The output-format revision must preserve mixed-clause and dialogue facts as
well as valid JSON; the current `single_array` candidate does not meet that
condition. Freeze any new variants and coverage checks before new model calls,
and retain this round's omissions as diagnostic regression cases. Repeat the
reviewed three-channel QA comparison only after these checks. No production
promotion or full SocialMemBench score follows from this round.

## Reproduction

```sh
.venv/bin/python scripts/eval_socialmem_followup.py \
  --previous build/socialmem_20260910_predicates_continued \
  --out build/socialmem_followup_repeat_fresh \
  --now-iso <UTC-time-later-than-expected-write-completion>

.venv/bin/python scripts/verify_socialmem_followup.py \
  --run build/socialmem_20260910_followup_run
```

The verifier checks frozen source/input/template hashes, the previous verified
archive, every expected call and database identity, native success/failure
parity, statement semantics and deterministic temporal fields, exact source
engram bytes and content hashes, evidence references, pipeline terminal states,
and recomputed metrics. It makes no model calls.
