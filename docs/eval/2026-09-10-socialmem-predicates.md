> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench Predicate and Fidelity Diagnostic

Status: completed with errors; offline artifacts verified on 2026-09-10.

Defined predicate extensions improve synthetic majority support from 4/16 to
14/16, versus 5/16 for object fidelity alone. Combined regresses on unchanged P1.
Three of four scoped memory conditions fail on malformed general-fact output;
the one completed memory answer receives 0/3, while both full-dialogue controls
receive 3/3. These results support further predicate-contract work, but do not
qualify the trial configuration for production or establish a benchmark gain.

The completed [vocabulary-only and general-fact follow-up](2026-09-10-socialmem-followup.md)
now isolates the open P1 question: vocabulary alone also regresses in the fresh
paired run. Its single-array general-fact intervention eliminates observed parse
failures but loses facts. Neither follow-up candidate is production-qualified;
the original results below remain unchanged.

## Motivation

The previous temporal diagnostic stored 57 statements, 46 with `prefers`, and
lost Q9's explicit nervousness and unresolved decision before retrieval. The
project owner also reported insufficient predicate richness in earlier runs.
This experiment separates a controlled vocabulary extension from stronger
semantic preservation in the belief prompt. It does not change production
defaults or claim a full SocialMemBench score.

The existing registry has 32 predicates, while the belief prompt permits ten.
Unregistered non-OCCURRED predicates are stored with `review_requested`, rather
than rejected. Existing `believes` objects can sometimes preserve a full mental
state proposition, so vocabulary size alone is not an established explanation
for every failure.

## Fixed Protocol

| Arm | Belief vocabulary | Object instructions |
| --- | --- | --- |
| baseline | Current ten predicates | Current brevity rules |
| fidelity | Current ten predicates | Preserve full semantic qualifiers |
| vocabulary | Five additional defined predicates | Current brevity rules |
| combined | Five additional defined predicates | Preserve full semantic qualifiers |

The additions are `feels`, `uncertain_about`, `decided_on`, `indifferent_to`, and
`trusts`. Only vocabulary/combined configure native `extra_core_predicates`.
The baseline template is byte-identical to the current production template.
The two transformations commute. Belief, general-fact and episodic templates
are archived; only the belief template varies across arms.

Three fixed tracks:

1. Sixteen generic synthetic cases, four arms each. Each response is persisted
   through the native parser and policy. The canonical QA judge then evaluates
   all stored semantic fields directly against a question/reference, with three
   repeated votes and no answer generation. This is judge-assisted statement
   sufficiency, not official QA accuracy or an exhaustive semantic audit.
2. All unchanged 50 P1 cases, baseline/combined only, with original raw-output
   matching and F1 metrics. These arms were selected before observing results.
3. Two reviewed SocialMemBench records, baseline/combined plus full-dialogue
   controls. Q1 contains 50 turns and Q9 113 turns, both from Sessions 1-5.
   Each memory condition uses all five speakers, alphabetically ordered,
   grouping each speaker's turns exactly as in the prior extraction route.
   Each input runs belief, general-fact and episodic extraction, followed by
   native default sleep, real embeddings, and native multi-holder Planner
   retrieval with total k=10. Each condition receives one answer and three votes.

Extraction sees source passages, never questions or reference answers. Arm
order rotates across synthetic/P1 cases and reverses for the second scoped item.
There is no selection of prompts from observed scores and no quality retry.
Transport-level retry configuration remains archived in the manifest.

Originally planned maximum: 224 extraction responses, 6 answers, 210 judge votes.
The three votes use the same model and prompt; they are repeated judgments, not
independent judges. Two reviewed records are diagnostic coverage only. Q4 and
Q9 Sessions 6-8 remain excluded, with no gold changes.

## Runtime and Evidence

- Working-tree HEAD: `8b6cc91b309aff4b6bcf02bb62393871dafa435f`; preexisting local
  modifications remain part of the evaluated checkout. Archived source hashes
  identify the actual evaluated code.
- Extraction: DashScope `deepseek-v3`, temperature 0, max tokens 4096.
- Answer/judge: `gpt-5.5`; answer budget 512, judge budget 8 tokens.
- Embeddings: `qwen3.7-text-embedding`, dimension 1024.
- Native query time: `2026-09-09T19:00:00Z`, checked against actual write times.
- Native binary SHA-256:
  `ebd2c36a7f4a17760cdbed74da279d8c6204157102e6e79189fc365a2da4a376`.
- This round adds an isolated evaluation runner, fixtures, tests and verifier.
  It does not edit the production prompt, registry, parser or retrieval code.

Source grouping retains utterance order within a speaker but omits session
labels from extraction. Source timestamps do not become native claim event
times. The trial uses an observer protocol across holders, not an individual
participant's knowledge frontier. It cannot independently resolve temporal
attribution or all structured query intents.

## Results

### Synthetic Statement Sufficiency

| Arm | Majority supported | Unanimously supported | Raw holder mismatches |
| --- | --- | --- | --- |
| baseline | 4/16 (25%) | 4/16 | 0 |
| fidelity | 5/16 (31.25%) | 3/16 | 0 |
| vocabulary | 14/16 (87.5%) | 14/16 | 0 |
| combined | 14/16 (87.5%) | 14/16 | 0 |

Each cell below is the number of accepting votes out of three. Majority support
requires at least two votes; no verdicts were manually overridden.

| Case | baseline | fidelity | vocabulary | combined |
| --- | --- | --- | --- | --- |
| emotion_positive | 0 | 0 | 3 | 3 |
| emotion_negative | 0 | 0 | 3 | 3 |
| relief_cause | 0 | 0 | 3 | 3 |
| mixed_emotions | 0 | 0 | 0 | 1 |
| undecided | 0 | 0 | 3 | 3 |
| possible_not_decided | 0 | 0 | 3 | 3 |
| decided_decline | 0 | 0 | 3 | 3 |
| decision_change | 0 | 0 | 3 | 3 |
| indifference | 0 | 0 | 3 | 3 |
| preference_contrast | 3 | 3 | 3 | 3 |
| trust_target | 0 | 2 | 3 | 3 |
| reported_distrust | 0 | 2 | 3 | 3 |
| preference_qualifiers | 3 | 3 | 3 | 3 |
| negative_target_scope | 3 | 3 | 3 | 3 |
| property_and_desire | 0 | 0 | 0 | 0 |
| topic_reference | 3 | 0 | 3 | 3 |

Baseline stores 17 `prefers` rows out of 19; fidelity stores 17 out of 20.
Vocabulary stores six `prefers` rows out of 21, and combined six out of 20.
Both extended arms use all five added relations: six `feels`, three
`uncertain_about`, two `decided_on`, one `indifferent_to`, and two `trusts` rows.

Within these selected diagnostic cases, the extension with explicit relation
definitions has a much larger observed effect than changing the brevity rules.
There is no additional majority-score gain from fidelity on top of vocabulary.
This factor includes relation definitions and native additive policy, not just
five names appended to a whitelist. One extraction per condition and sixteen
selected cases do not establish a population-wide benchmark effect.

For `property_and_desire`, all four arms retain only `Lou prefers it inspected
tomorrow`, omitting both the noisy-boiler fact and an explicit referent for
`it`. This track uses belief extraction only. The omission does not prove that
the separate general-fact channel would fail on that sentence.

### Unchanged P1 Regression Check

All 50 original cases completed in both preselected arms. Scores use the
original raw-output evaluator, which first matches exact `(predicate, object)`
pairs; they are not semantic judgments of normalized native rows.

| Field | baseline F1 | combined F1 | Existing threshold | baseline / combined |
| --- | --- | --- | --- | --- |
| holder | 0.7375 | 0.7044 | 0.85 | FAIL / FAIL |
| holder_perspective | 0.6875 | 0.6667 | 0.80 | FAIL / FAIL |
| predicate | 0.8000 | 0.7421 | 0.75 | PASS / FAIL |
| object | 0.8000 | 0.7421 | 0.70 | PASS / PASS |
| nesting_depth_1 | 0.5455 | 0.4545 | 0.60 | FAIL / FAIL |

Baseline is already below three thresholds. Combined falls below four and
regresses on all five metrics, so this run does not qualify it to replace the
production configuration. Predicate/object counts are `(TP, FP, FN)=(64,25,7)`
for baseline and `(59,29,12)` for combined. Eleven case pairs have differing
count records.

Some regressions are exact-format compatibility changes: `eval-022` changes
`code review` to `code review before merging`; `eval-044` changes `two approvals`
to `two approvals before any production release`; `eval-030` adds `the` before
`auth rollout requires MFA`. Other changes affect claim selection and
canonicalization: `eval-041` omits the expected responsibility claim, and
`eval-047` substitutes specific tasks for canonical `responsible_for/auth`.
The losses therefore cannot all be described as harmless richer wording.

P1 raw holder mismatches against the run holder total 26 for baseline and 23 for
combined. These are recorded attribution differences, not automatic errors:
P1 includes quoted authors, policy holders and multi-speaker claims. Its official
metrics use the raw holder. Native persistence retains the run holder under the
unchanged default policy. Synthetic raw holder mismatches remain zero.

Because P1 tested only baseline/combined, this trial cannot isolate how much of
the regression comes from vocabulary definitions versus broader object fidelity.
Vocabulary-only P1 was untested in this trial; the linked follow-up above now
reports that isolated comparison and does not establish a passing alternative.

### Scoped QA

| Record | baseline memory | combined memory | Full reviewed dialogue |
| --- | --- | --- | --- |
| Q1_a5s1c1 | Technical failure; no answer/votes | Technical failure; no answer/votes | 3/3 |
| Q9_a0b1c2d3 | Technical failure; no answer/votes | 0/3 | 3/3 |

The three technical failures all contain the same raw general-fact response:

````text
[]
```json
[]
```
````

Both the Python envelope check and the native JSON parser reject its two
top-level arrays. The failure occurs for Femi in Q1 baseline, Claudette in Q1
combined, and Yuki in Q9 baseline. Their databases retain respectively 9, 0 and
48 rows from previously completed input units. Failed units do not enter the
trial's native commit because its precheck fails first. A separate offline
native reproduction also reports extraction failure on these exact bytes.

The initial run stopped at Q1 baseline. An explicitly archived continuation
preserved all 164 completed synthetic/P1 conditions and their votes, the first
169 extraction records, and the failed baseline database. It then attempted
every remaining preselected condition and both full controls. Failed cells stay
in the four-cell outcome table; they are neither removed nor assigned invented
0/3 votes. No failed completion was retried or repaired. This continuation is a
failure-handling amendment after observing an operational error, not a fully
uninterrupted execution of the original protocol.

Actual archived totals are **200 extraction responses, 3 answers and 201 judge
votes**. The 24 remaining extraction slots, 3 answer slots and 9 judge slots were
not run after their respective cell failures. These counts describe logical
responses in the journals, not all HTTP attempts inside transport retries.

Q9 combined completes all five source inputs, storing 65 rows: 18 held by Marcus,
36 by Sandra, and 11 by Yuki. Claire and Dev each return empty arrays from all
three channels. Default sleep consolidates 59 rows, creates no gist, and leaves
65 consolidated rows; all 65 receive 1024-dimensional vectors. Multi-holder
Planner queries the three actual holders and selects ten Marcus rows.

The selected statement `79f61742-bf53-92e0-6151-cf71c54e1bf8` is:

```text
[FACT] Marcus feels nervous about starting over (conf 0.70, holder Marcus)
```

That is a concrete extraction-to-retrieval recovery of emotional information.
The answer correctly mentions nervousness but says the memories do not provide
enough detail about his earlier presentation. Its three votes reject the full
comparison. Marcus's raw belief response and his stored rows omit earlier
`not decided yet`, the desire-for-change contrast, and the three-year stagnation
explanation. They contain `decided_on swindon job` without the earlier/current
distinction. This information is already missing before retrieval; the failure
cannot be attributed only to k=10. The full dialogue supplies a successful
earlier-detached versus later-reflective comparison.

Q9 baseline has no valid answer in this fresh run, so it does not support a
paired accuracy comparison with combined. The historical temporal run remains
separate evidence. There is no formal SocialMemBench score from this diagnostic.

## Interpretation Checks

The synthetic verdict is not a complete schema validator. For example,
`undecided` emits `uncertain_about` with polarity `UNKNOWN` in both extended
arms, and all three votes accept it. Under the documented relation-level
polarity contract, explicitly asserting uncertainty should affirm that
uncertainty relation; `UNKNOWN` instead leaves the relation itself uncertain.
This conflict must be resolved before treating these predicates as a production
contract. Accepted votes do not establish correct structured polarity.

Likewise, `decision_change` receives 3/3 in both extended arms despite storing
only `uncertain_about workshop` and `decided_on attend`, without the explicit
`last week`/`today` qualifiers. These votes do not establish temporal fidelity.

Native normalization also changes objects independently of the LLM. In
`mixed_emotions`, both extended arms store `sad to leave my colleague` after
the raw response says `sad to leave my colleagues`. The native belief parser
applies `normalize_theme`, whose noun-oriented singularization acts on a whole
object string. Vocabulary/combined store identical semantic candidates for
this case but receive 0/3 and 1/3 votes respectively. Both fail majority; the
different votes on identical judge prompts also demonstrate judge variation.
Neither the normalization effect nor that variation is a vocabulary-only result.

The trial's `FACT_LOOKUP` retrieval can embed and render arbitrary registered
relation strings. That does not establish compatibility with every structured
intent: `QueryIntent::PREFERENCE` specifically filters `predicate='prefers'`,
so a future indifference relation needs an explicit consumer decision. Emotion,
uncertainty, decision and trust semantics also require defined subject, object,
modality, polarity, temporal qualifiers and perspective, beyond adding names to
the whitelist.

## Validation and Next Work

The final verifier passes with 168 databases, 174 offline native input replays,
and ten selected context entries checked against stored rows and score order.
It checks all source/input/prompt hashes, unchanged initial artifacts and journal
prefixes, exact call ordering, the three terminal parse failures, native engram
payload bytes and hashes, statement semantics and deterministic temporal fields,
episodic metadata, vector identities/dimensions/byte lengths, exact answer/judge
prompts, raw-to-validated votes, and recomputed P1/synthetic results. Score order
is checked against archived native receipts; query embeddings and scores are
not independently recomputed. A verified archive can faithfully contain failed
conditions, as it does here.

Validation: 15 focused tests pass; the full Python suite reports **1126 passed,
15 skipped** in `build/socialmem_20260910_predicates_pytest_complete.log`.
Tests include failure archival, default pending gist lineage, event-time and
episodic-field tampering, invalid abstention content, and native rejection of
duplicate arrays. No fresh C++ build/test run was needed for this experiment-only
round; the unchanged native binary hash is recorded above.

Next work should define explicit polarity/modality and temporal/reference
contracts for the new relations, preserve existing P1 canonical object rules
where required, and separate clause-valued objects from noun normalization.
Stabilize general-fact structured output with explicit failure reporting before
another scoped QA comparison. The linked follow-up completes the predeclared
vocabulary-only P1 check and a general-fact output-format test, revealing
remaining P1 regressions and fact omissions. Repeat the reviewed QA only after
the semantic contracts and output-format checks are established; retain these
failed and negative results as baseline evidence. Production defaults remain
unchanged.

## Reproduction

```sh
.venv/bin/python scripts/eval_socialmem_predicates.py --real-run \
  --prepared build/socialmem_20260909_scoped_corpus \
  --out build/socialmem_predicates_repeat_fresh \
  --now-iso <UTC-time-later-than-expected-ingestion-completion>

.venv/bin/python scripts/verify_socialmem_predicates.py \
  --run build/socialmem_20260910_predicates_continued \
  --prepared build/socialmem_20260909_scoped_corpus
```

The immutable initial run is `build/socialmem_20260910_predicates_run/`. The
completed aggregate is `build/socialmem_20260910_predicates_continued/`, with its
`initial_manifest.json`, `scoped_failures.jsonl` and `verification.json` retaining
the failure and continuation evidence. `scripts/continue_socialmem_predicates.py`
implements this specific first-cell failure continuation using a fresh output
directory and exact cached artifacts.

The aggregate directory archives inputs, exact templates, source files, all raw
extraction/answer/judge replies, parsed judgments, cases, ingestion receipts,
168 databases, before/after states, retrieved IDs/labels/scores, and results.
Raw judge replies are saved before strict YES/NO validation. Native databases
are backed up even when a later pipeline, embedding or retrieval step fails.
