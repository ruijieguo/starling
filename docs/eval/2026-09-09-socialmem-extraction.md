> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench preference extraction diagnostic, 2026-09-09

This follows [the native polarity repair](2026-09-09-socialmem-polarity.md).
The belief prompt's preference-subject example contradicted the native desire
contract: it taught `weekend prefers outdoors`, whereas the preference subject
must identify the desirer. The example and scope instructions are now corrected.

In a fixed 12-case diagnostic, native stored subject accuracy rose from **2/12
to 12/12**, and exact subject/object/polarity relation accuracy rose from **2/12
to 11/12**. Longer source passages still lose important claims. These findings
do not establish a SocialMemBench QA improvement or a general extraction gate.
The completed run took 7 minutes 57 seconds, from **22:14:15 to 22:22:12
Asia/Shanghai**. No commit or push was made.

## Diagnosis And Change

`python/starling/extractor/prompts.py` previously gave this worked example:

```text
Li Hua: I want to spend the weekend outdoors
subject=weekend, subject_kind=entity, predicate=prefers, object=outdoors
```

`src/extractor/extractor.cpp::is_first_order_desire` explicitly treats the
subject of a desire/preference as the attitude bearer. The prompt also said
holder and subject are usually different, without explaining first-person
preferences. The updated example uses `subject=Li Hua`, `subject_kind=cognizer`,
and `object=spend the weekend outdoors`. New instructions distinguish preference
bearer from target and preserve meaning-bearing target qualifiers.

Polarity was previously only an enum in the prompt schema. The new instructions
define relation-level scope, distinguishing `NEG prefers downtime` from
`POS prefers no downtime`, and retain both negations when they have different
scopes. Examples use unrelated rollout/downtime content, not SocialMemBench
question text or reference answers. No parser, renderer, stored-data migration,
holder reassignment, eligibility threshold or scoring threshold changed here.

Historical successful nonempty extraction-attempt rows have empty `raw_output`,
so the historical model JSON cannot be reconstructed from that ledger. Static
tracing shows that the parser directly reads `subject` and `polarity`; the new
experiment additionally archives raw model responses before native replay.
It reproduces the upstream error directly: the old prompt turns `Nora: I prefer
tea.` into `subject=tea, subject_kind=entity, predicate=prefers, object=tea`.

## Protocol

The before prompt was copied from the working tree before editing. Both prompts
are archived verbatim. The fixed inputs were selected before calls:

- Twelve newly authored polarity/preference cases, including positive/negative
  pairs, negative targets, quantity qualifiers, an aversion, a reported bearer,
  uncertainty and Chinese statements. These are targeted synthetic tests.
- The exact speaker-grouped text used by the prior scoped protocol for Claudette
  in Q1 and Marcus in Q9. Source turn IDs and text are retained. These two groups
  are qualitative checks, not scored new benchmark questions.
- All 50 existing `tests/data/eval_p1_corpus.jsonl` records, unchanged, scored with
  the original P1 raw-JSON evaluator.

Each case gets one completion per prompt, alternating phase order by case index:
**128 raw completions total**. Model: `deepseek-v3` through the existing native
DashScope-compatible adapter, temperature 0, max_tokens 4096, timeout 60 seconds,
native transport max_retries 3. Transport attempts within a completion are not
separately exposed by the binding. No answerer, judge, embedding or sleep calls
were made in this experiment, and no quality-based regeneration was used.

Every raw response is replayed through the native belief branch:
`memory_remember_prepare`, `memory_extract_llm`, `memory_remember_commit`.
FakeLLM only delivers the already recorded response. Native JSON parsing,
normalization, cognizer resolution, validation, writing and post-write processing
execute normally. The result is archived using a consistent SQLite backup.
This isolates the belief pass; it does not test episodic/general-fact interactions,
the full three-channel transaction, retrieval selection or downstream answers.

The twelve-case relation criterion requires exactly one preference row matching
the fixed bearer, cognizer kind, target wording and polarity. It measures stored
relation fidelity. It does not score modality or perspective, and native default
holder override means its holder check is not a test of raw model attribution.
Object aliases were frozen in the input file before the run; scores were not
relaxed after seeing responses.

## Results

| Targeted diagnostic | Before | After |
| --- | ---: | ---: |
| Correct preference subject and kind | 2/12 | 12/12 |
| Correct complete stored relation | 2/12 | 11/12 |

The remaining failed case is `Noise bothers me. I dislike noise.` The new
response uses the correct subject Nora but emits `object=no noise, polarity=NEG`.
This double-encodes the aversion, contrary to the intended `object=noise,
polarity=NEG`. The row is preserved as emitted. Prompt scope guidance reduces
errors but is not a semantic guarantee.

The unchanged P1 evaluator gives these single-round F1 values:

| Metric | Before | After | Existing threshold | After threshold |
| --- | ---: | ---: | ---: | --- |
| holder | 0.744 | 0.769 | 0.85 | Below |
| holder_perspective | 0.744 | 0.744 | 0.80 | Below |
| predicate | 0.795 | 0.833 | 0.75 | Above |
| object | 0.795 | 0.833 | 0.70 | Above |
| nesting_depth_1 | 0.545 | 0.636 | 0.60 | Above |

No existing metric decreased in this run. Holder and perspective still fail their
absolute thresholds. One completion per phase is not enough to establish general
non-regression. P1's scoring also omits subject, subject kind, polarity and
modality; its F1 values cannot certify those fields. No committed baseline was
updated and no cross-model historical score comparison is claimed.

## Source Passage Findings

| Source group | Before statements / preference rows | After statements / preference rows |
| --- | ---: | ---: |
| Claudette, Q1 | 8 / 8 | 5 / 3 |
| Marcus, Q9 | 11 / 4 | 5 / 2 |

For Claudette, all eight old preference rows use entity subjects; all three new
preference rows use Claudette. The old prompt repeats the problematic
`street prefers no more bulk, NEG` and `traffic prefers less, NEG`. The new
response captures her joint-letter, trial-period and residents-only preferences,
but omits important opposition/aversion claims. Both new calls omit the explicit
permanence-aversion relation that was present in the historical frozen database.

For Marcus, both prompts omit the later nervousness statement in this run. The
new prompt produces two correctly attributed preference rows but fewer total
claims. The old call labels `not my fight` as a positive preference, whereas the
historical database labeled that object negative. The changed extraction cannot
be treated as the historical extraction with only its subject fixed.

These observations separate structural correctness from coverage: fewer invalid
entity preferences do not imply that all needed evidence survived. The large
belief prompt contains other restrictive rules, including focal-speaker and
explicit-self-attribution requirements. Their contribution to omitted claims
remains a hypothesis; this run changed only the preference example and relation
scope guidance and cannot assign omission causality to a specific remaining rule.

## Verification And Provenance

A contract test failed on the old entity-subject example and passed after repair.
Native replay tests cover POS/NEG/UNKNOWN, negative object wording, an invalid
model subject retained without rewriting, and conflicting predictions. Further
tests cover malformed output, raw-cache matching and provider configuration.

The first run stopped after its first raw response because the source database
had an uncheckpointed WAL. This was an archive failure before any score, not a
model-quality retry. After switching to SQLite backup, the next run reused the
exact first raw response and completed the remaining 127 calls. The failed run,
its manifest and response remain intact; cache hashes verify the reuse.

Independent review found that the shared adapter helper could silently fall back
to OPENAI configuration when a DashScope key was absent. The current runner now
requires explicit DashScope settings and archives the resolved endpoint, token
limit, timeout and retry settings; new raw-cache reuse also requires matching
transport configuration. This hardening happened after the completed process
started, so its manifest retains the original executed source hashes. The live
environment was independently checked while that process ran: the DashScope key
was present, and the configured endpoint was
`https://dashscope.aliyuncs.com/compatible-mode/v1`. `provider_audit.json` records
that later observation separately, not as an original process receipt.

Offline verification checks all 128 raw prompts/responses, their phase order,
native databases and integrity/hash values, source payload bytes, completed
pipelines, raw-cache provenance, archived sources and independently recomputed
scores. All passed. Fresh full Python validation: **1,094 passed, 15 skipped**.
The native binary is unchanged from the preceding polarity round, whose C++
validation was **1,007 passed, 1 skipped**; no new C++ test run is claimed here.

Artifacts:

- `build/socialmem_20260909_extract_inputs/prompts_before.py`: old prompt module.
- `build/socialmem_20260909_extract_run/`: interrupted archive attempt and first response.
- `build/socialmem_20260909_extract_run_v2/`: complete inputs, prompts, 128 raw
  responses, native result databases, journal, source archive, results and
  verification/provider-audit receipts.
- `build/socialmem_20260909_extract_verified_pytest.log`: final Python results.
- `build/socialmem_20260909_extract_verify.py`: offline evidence verifier.

```sh
.venv/bin/python build/socialmem_20260909_extract_verify.py

.venv/bin/python scripts/eval_socialmem_extraction.py --real-run \
  --before-prompt build/socialmem_20260909_extract_inputs/prompts_before.py \
  --out build/socialmem_extraction_repeat_fresh
```

The current strict raw-cache transport check intentionally rejects the old run's
incomplete transport manifest. Use its archived executed runner only to reproduce
the historical resume behavior; do not edit old manifests to bypass validation.

## Remaining Work

The source grouping/time/context comparison has now run and is documented in
[the source-context follow-up](2026-09-09-socialmem-temporal.md). All four Q9
extraction conditions omitted explicit nervousness and the undecided state;
their eight paired answers received 0/3 judge votes, versus 3/3 for full reviewed
dialogue. This narrows the next work to semantic fidelity and channel coverage.

The next priority is generic emotion, uncertainty and topic-reference fidelity
with correct speaker ownership, plus an audit of coverage across the production
three-channel route. Remaining negative-target ambiguity needs broader
scope-specific cases. A new full scoped ingestion/answer run is still needed
after those changes; these diagnostics do not replace a SocialMemBench score.
