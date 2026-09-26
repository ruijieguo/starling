> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench Relation Contracts and General-Fact Clause Coverage

Status: completed and verified on 2026-09-10. All 236 extraction conditions and
96 judge responses are archived; one baseline native parse failure is retained.

The relation contract corrects affirmed uncertainty in two diagnostic cases,
but both vocabulary variants receive support on 13/16 cases and remain below
baseline on four P1 metrics. Clause coverage restores the mixed-property control
and explicit Sandra facts while retaining 18/18 strict JSON, but still omits
and misattributes other source facts. Both candidates remain experimental;
this run establishes no downstream SocialMemBench QA accuracy improvement.

## Motivation and Fixed Interventions

The [preceding follow-up](2026-09-10-socialmem-followup.md) found P1 regressions
with vocabulary alone. Its single-array general-fact intervention improved
format compliance but lost a mixed-sentence property and explicit dialogue
facts. This experiment tests bounded prompt changes without altering production
templates, C++ validation, object normalization, storage or retrieval defaults.

`contract` starts from the exact archived vocabulary arm. It retains the same
five relations and native additive predicate registration. It adds explicit
cognizer-subject, modality, relation-polarity, unresolved-choice and temporal
object rules. It limits the old noun-brevity rules to original predicates,
preserving their existing canonicalization, holder, perspective and nesting
instructions. These are one combined semantic-contract intervention, not
separate causal estimates for each sentence. In this candidate, `decided_on`
represents a settled choice of future action with INTENDS; the other four new
relations assert a mental state/relation with BELIEVES. An explicitly asserted
uncertainty is POS on `uncertain_about`, not UNKNOWN.

This mapping is a proposed experimental contract, guided by the design's
orthogonal modality/polarity distinction. It is not an already established
production contract. The prompt asks for relative time phrases in the corresponding
objects; the experiment does not implement historical event-time columns or repair
native noun normalization.

`clause_coverage` starts from the exact preceding `single_array` arm and adds
clause-level eligibility instructions: retain declarative facts inside dialogue
and mixed utterances, exclude individual ineligible clauses, inspect the entire
passage before returning an empty array, and preserve the actual subject. It
also clarifies that unmarked subjective evaluations remain opinions. The
predicate set, schema, original examples and output-envelope instructions remain
unchanged. This is a combined coverage/eligibility intervention.

## Fixed Execution and Measurements

| Track | Inputs | Arms | Extraction calls |
| --- | --- | --- | --- |
| P1 | All unchanged 50 cases | baseline, vocabulary, contract | 150 |
| Synthetic | All original 16 cases | vocabulary, contract | 32 |
| General fact | Ten reviewed speaker inputs and eight original controls | baseline, single_array, clause_coverage | 54 |

Total: **236 new extraction calls**, then **96 judge calls**, no answer
generation or embeddings. Extraction uses the same archived DashScope
`deepseek-v3` configuration, temperature 0 and max tokens 4096. Each condition
gets one completion, with rotating arm order. No response repair, quality retry
or adaptive prompt selection is allowed. Extraction sees the passage only;
questions and reference answers are reserved for judging.

These are logical completion counts, not all HTTP attempts. Existing extraction
transport retry settings are frozen in the manifest; the archived judge adapter
retains its four-attempt transport retry policy. Invalid returned YES/NO content
does not trigger a quality retry.

The original P1 exact-match metrics and thresholds are retained. A metric
exception is explicit and scored as an empty prediction while retaining the
case. This one-round comparison is not the original three-round P1 acceptance
procedure. The baseline is rerun alongside both vocabulary variants.

Synthetic candidates contain all native statement semantic fields in receipt
order. The canonical `gpt-5.5` judge receives each candidate three times, with an
eight-token budget. Invalid or failed verdicts are archived and count as
unsuccessful votes in the fixed denominator. A technical extraction failure
cannot qualify as supported, even if its candidate receives accepting votes.
Judge-assisted statement sufficiency is not full QA accuracy or complete schema
validation; the three votes are repetitions of the same judge, not independent
judges. All 16 cases remain included, including the mixed property/desire case
that a belief-only channel may not fully cover.

Separate rule diagnostics record emitted new relations and violations of
nonempty subject, cognizer subject-kind, proposed modality and polarity-enum
rules, on both raw and native representations. Zero emitted relations is not a
semantic success. These rules do not determine whether the named person is
correct or whether a valid polarity value has the right semantic scope.
Two explicit-undecided cases additionally check for affirmed uncertainty and
absence of a settled decision; the decision-change case checks literal
`last week`/`today` qualifiers on the respective objects. These narrow signals
are not exhaustive temporal or object-reference accuracy metrics.

General-fact measurements retain strict JSON, optional-envelope parsing, native
success, and exact predefined control tuples with no silently discarded raw
statements. All ten speaker outputs were inspected against their passages,
especially mixed-clause loss and Sandra/Marcus subject and coverage differences.
This manual audit is not a new exhaustive gold inventory.

## Provenance and Failure Handling

The real run is `build/socialmem_20260910_contracts_run/`, started at
`2026-09-10T08:00:04Z` and completed at `2026-09-10T08:22:06Z`, with fixed native query clock
`2026-09-10T12:00:00Z`. The clock is later than planned ingestion and is not used
to invent historical source dates. The working-tree HEAD is
`8b6cc91b309aff4b6bcf02bb62393871dafa435f`; preexisting local changes remain.
The native binary SHA-256 is
`ebd2c36a7f4a17760cdbed74da279d8c6204157102e6e79189fc365a2da4a376`.

The parent is `build/socialmem_20260910_followup_run/`, whose verification hash,
artifact hashes and grandparent lineage are checked. The runner freezes inputs,
templates, the parent's archived source file set and the new runner/verifier before
calling a model. Every raw reply is archived before parsing/scoring. Each native
database is backed up even on failure, and transport flags are retained during
offline native replay. The verifier checks all expected calls, exact prompts,
database identities, engram bytes/evidence, native semantics, pipeline states,
judge inputs/verdicts and recomputed metrics. Offline smoke runs are explicitly
labelled in their manifest and cannot be reported as real-model runs.

The cases reuse diagnostic inputs already inspected in earlier rounds; this is
a development experiment, not an unseen evaluation set. No benchmark-wide gain
or production promotion follows from a positive diagnostic result alone.

## Results

All 236 extraction conditions and 96 judge calls completed. All recorded
transport calls succeeded and all judge verdicts were valid. One general-fact
baseline native parse failure remains in the fixed denominator.

### P1 Compatibility

All 150 P1 calls succeeded in transport, parsing, native persistence and metric
computation. Each arm completed the original 50 cases.

| Field | Baseline F1 | Vocabulary F1 | Contract F1 | Threshold |
| --- | --- | --- | --- | --- |
| holder | 0.7500 | 0.7037 | 0.7205 | 0.85 |
| holder_perspective | 0.7000 | 0.6667 | 0.6957 | 0.80 |
| predicate | 0.7875 | 0.7531 | 0.7702 | 0.75 |
| object | 0.7875 | 0.7531 | 0.7702 | 0.70 |
| nesting_depth_1 | 0.5455 | 0.5455 | 0.5455 | 0.60 |

Contract improves the four exact-match metrics relative to vocabulary in this
run, but remains below baseline on all four. All arms fail holder, perspective
and nesting-depth thresholds; all pass predicate/object thresholds. Depth
counts are identical in every case, not only at the aggregate level.
Predicate/object counts `(TP, FP, FN)` are `(63, 26, 8)` for baseline,
`(61, 30, 10)` for vocabulary and `(62, 28, 9)` for contract. The common exact
pair matcher makes predicate/object F1 identical; they are not independent
semantic measurements. The corresponding native row totals are 89, 91 and 90.

The differences contain both recoveries and remaining regressions:

- `eval-033`: contract restores Alice/FIRST_PERSON on the policy claim, matching
  baseline and the unchanged label; vocabulary uses the policy as holder with
  QUOTED perspective.
- `eval-048`: contract restores `responsible_for/auth`, whereas vocabulary uses
  `OAuth rollout`. Both extended arms also emit two unlisted `intends`
  predicates, stored with `review_requested`. Native success does not mean the
  output complied with the prompt's allowed vocabulary.
- `eval-041`: vocabulary emits two `decided_on` statements with problems/tasks
  as entity subjects. Contract emits no added relations, but replaces the source
  with four `requires` claims and omits the expected responsibility claim.
  Baseline retains that responsibility claim. Suppressing invalid new relations
  therefore does not establish a semantic repair.
- `eval-015`: contract still attributes the first matching responsibility quote
  to Bob, while the unchanged label requires Alice. The first-match evaluator
  does not choose a later matching pair to optimize holder credit.

Vocabulary emits only two added relations across P1, both of them the invalid
`eval-041` decisions. Contract emits none. Accordingly, its zero local-rule
violations on P1 cannot be interpreted as evidence of correct new-predicate
coverage. The observed score changes mostly concern the original predicates.

Baseline and vocabulary scores also differ from the preceding run despite
unchanged templates and model settings. These single completions provide a
within-run diagnostic, not a statistically established causal effect or stable
population-wide compatibility result.

### Synthetic Semantic Checks

Both arms store 20 statements across the same 16 cases, including 14 uses of
the added relations, with zero violations of the narrow subject-kind/modality/
polarity-enum checks in both raw and native representations. The more specific
checks expose differences that this zero-violation count misses:

| Predeclared signal | Vocabulary | Contract |
| --- | --- | --- |
| Affirmed uncertainty on two explicit-undecided cases | 0/2 | 2/2 |
| No settled decision on those two cases | 2/2 | 2/2 |
| Both literal temporal qualifiers on decision-change case | 0/1 | 0/1 |

These results agree before and after native persistence. Rosa and Victor change
from UNKNOWN polarity on their uncertainty relation to POS. The decision-change
case still omits both `last week` and `today` from raw output, and still stores
only `workshop` and `attend` as its two objects. There is no demonstrated temporal
or referent recovery from the new object instructions.

Manual inspection identifies remaining failures:

- For negative emotion, vocabulary stores `feels/certification exam` with NEG,
  omitting the actual feeling. Contract retains `not anxious about the
  certification exam` inside the object while also assigning NEG, duplicating
  the same denial. Neither is the intended `feels/anxious ...` relation with
  NEG. Both pass the narrow enum/subject-kind rules.
- Both arms emit two feelings for the mixed-emotion case. Native normalization
  changes raw `colleagues` to `colleague`; it also changes `keys` to `key` in the
  reported-distrust case and `upstairs` to `upstair` in the topic-reference case.
  These changes remain outside this prompt intervention and are not repaired by
  longer object instructions.
- Both arms retain only `prefers/it inspected tomorrow` for property-and-desire,
  with no explicit boiler referent and no noisy-boiler statement. This is a
  belief-only test, so its result does not measure combined channel coverage.

The complete fixed judgment results are:

| Measurement | Vocabulary | Contract |
| --- | --- | --- |
| Majority supported | 13/16 | 13/16 |
| Unanimously supported | 13/16 | 13/16 |
| Invalid or failed verdicts | 0/48 | 0/48 |

| Case | Vocabulary accepting votes | Contract accepting votes |
| --- | --- | --- |
| emotion_positive | 3/3 | 3/3 |
| emotion_negative | 0/3 | 1/3 |
| relief_cause | 3/3 | 3/3 |
| mixed_emotions | 1/3 | 0/3 |
| undecided | 3/3 | 3/3 |
| possible_not_decided | 3/3 | 3/3 |
| decided_decline | 3/3 | 3/3 |
| decision_change | 3/3 | 3/3 |
| indifference | 3/3 | 3/3 |
| preference_contrast | 3/3 | 3/3 |
| trust_target | 3/3 | 3/3 |
| reported_distrust | 3/3 | 3/3 |
| preference_qualifiers | 3/3 | 3/3 |
| negative_target_scope | 3/3 | 3/3 |
| property_and_desire | 0/3 | 0/3 |
| topic_reference | 3/3 | 3/3 |

All three votes accept both decision-change candidates despite the missing
temporal qualifiers, and accept UNKNOWN uncertainty in vocabulary as well as
POS uncertainty in contract. These acceptance results therefore do not establish
correct structured polarity or temporal fidelity. Mixed-emotion candidates have
the same semantic statement content but receive different votes; both fail
majority. No votes were overridden to fit the manual audit.

### General-Fact Format and Coverage

All 54 calls succeeded in transport. One baseline native pipeline failed on
the same duplicate-array response for Q1 Claudette; its raw reply, empty database
and failed pipeline are retained.

| Measurement | Baseline | Single array | Clause coverage |
| --- | --- | --- | --- |
| Strict JSON array | 10/18 | 18/18 | 18/18 |
| Native extraction success | 17/18 | 18/18 | 18/18 |
| Optional-envelope parse failures | 1/18 | 0/18 | 0/18 |
| Exact predefined control tuples | 7/8 | 7/8 | 8/8 |

All arms pass the four empty controls and the definition, quantity and
organizational-relation controls. Only clause coverage passes the mixed input:
`Lena: The boiler is noisy. I want it inspected tomorrow.` It stores
`boiler has_property noisy`, whereas baseline and single array return no facts.
Baseline passed this case in the preceding follow-up but fails here; the fresh
within-run controls are the comparison, not a selected historical baseline.

All ten speaker inputs were manually inspected. The following is a source/output
audit, not an exhaustive gold-scored recall metric:

- Q9 Sandra: baseline and single array return no statements; clause coverage
  returns eight. It recovers the explicit brown/green/blue bin uses and the app
  still showing Wednesday. It also retains the collection-schedule change,
  parking proposal and consultation deadline. The eighth statement describes
  the street's agreement against commercial short-term rentals as a property
  of the street, an encoding that still needs normative-channel and subject
  review. Eight added rows does not mean eight validated correct facts.
- Q9 Marcus: baseline/single array/clause coverage store 9/8/5 statements.
  Clause coverage drops the subjective rent evaluation, but still classifies
  the Patels household as an entity, attaches moving at month end to the job
  instead of Marcus, and loses the explicit doorbell malfunction since Tuesday.
  It also emits `new one has_property helpped set up`, leaving the referent
  unresolved and treating a past setup action as a property. This candidate
  therefore still has coverage and eligibility defects despite the control gain.
- The remaining eight speaker inputs store no general facts in any arm,
  including the one baseline parse failure. Femi still yields no facts despite
  source quantities and a consultation deadline. Empty output is not a measured
  semantic success on these unlabelled speaker inputs.

Clause coverage repairs the selected mixed-property omission and restores
several explicit Sandra facts while retaining output compliance. It does not
establish complete general-fact coverage, stable correctness on unseen inputs,
or a downstream SocialMemBench QA improvement.

## Harness Validation

Before real execution, all 20 focused tests across contracts/follow-up passed.
The full Python suite reports **1146 passed, 15 skipped** in
`build/socialmem_20260910_contracts_pytest.log`. A full offline smoke exercise
reused archived extraction replies with FakeLLM and fixed NO judge replies,
and verified all 236 databases and 96 judgment records, including two malformed
general-fact responses. Its log is
`build/socialmem_20260910_contracts_smoke.log`; its temporary artifacts were
labelled `offline_smoke`. These checks establish harness behavior, not real-model
quality. Independent review found no blocker before real execution. No C++ code
changed in this round and no new C++ build/test result is claimed.

Final real-run verification passed at `2026-09-10T08:22:30Z`:
**236 archived databases, 236 offline native replays, 96 judge responses, one
native failure and zero invalid judge verdicts**. The verification receipt and
artifact/database hashes are in
`build/socialmem_20260910_contracts_run/verification.json`.

## Decision and Next Work

The observed gains are narrow: explicitly affirmed uncertainty is represented
with the intended relation polarity, and clause-level instructions recover a
mixed property plus several explicit dialogue facts. The existing exact-match
P1 regression, unlisted `intends`, repeated emotion negation, lost temporal
qualifiers and remaining general-fact omissions prevent production adoption.

The next experiment should isolate an additional mental-state extraction pass
from the unchanged legacy belief prompt, with explicit checks on combined
coverage and attribution. Current prompt growth changes original-predicate
outputs even when no new relation is emitted; a separate pass can test that
interaction directly. Its correctness and additional runtime cost still need
measurement. Clause-valued objects also need a separate native normalization
check: `src/extractor/json_parser.cpp` currently applies `normalize_theme` to
every extracted string before hashing, including complete clauses. Any native
normalization revision must be evaluated separately with its own build/tests
and preserved raw-to-stored evidence. These are next-step candidates, not
implemented or validated outcomes of this round.

Retain this run's positive and negative artifacts as development evidence, and
include unseen cases before claiming generalization. A new full three-channel
QA comparison remains outstanding; no answer, retrieval or benchmark-wide
accuracy result was produced here.

## Reproduction

```sh
.venv/bin/python scripts/eval_socialmem_contracts.py \
  --previous build/socialmem_20260910_followup_run \
  --out build/socialmem_contracts_repeat_fresh \
  --now-iso <UTC-time-later-than-expected-write-completion>

.venv/bin/python scripts/verify_socialmem_contracts.py \
  --run build/socialmem_20260910_contracts_run
```
