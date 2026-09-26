> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench source-context diagnostic, 2026-09-09

This follows [the preference extraction diagnostic](2026-09-09-socialmem-extraction.md).
Preserving source sessions, timestamps and surrounding dialogue did **not** repair
the reviewed Marcus Q9 answer in this run. All eight memory-based answers received
**0/3** accepted judge votes; the complete reviewed dialogue received **3/3**.
All four extraction conditions omitted the explicit nervousness and undecided
state before retrieval. Source-time presentation cannot recover those lost claims.

The run completed from **23:29:24 to 23:38:01 Asia/Shanghai**, about 8 minutes
37 seconds. This is a one-item, target-holder, belief-branch diagnostic, not a
SocialMemBench score. No production prompt or C++ semantics changed in this round.
No commit or push was made.

## What Was Tested

The existing speaker-grouped extraction path in `scripts/eval_ladder.py` joins
all utterances by one speaker into a single text. Session boundaries, timestamps
and other speakers' replies are absent from that extraction payload.

`scripts/eval_socialmem_temporal.py` now compares four fixed input shapes using
the current production belief prompt:

| Variant | Input | Extraction completions |
| --- | --- | ---: |
| `legacy` | Original Marcus-only concatenation, byte-for-byte | 1 |
| `grouped` | Same 27 Marcus turns as one structured source record | 1 |
| `sessions` | Structured Marcus turns split into five sessions | 5 |
| `session_context` | Five sessions with all speakers, extracting Marcus's target turns only | 5 |

Structured inputs retain network ID, target speaker, target turn IDs, and each
turn's original session, message index, speaker, text and timestamp. They share
one focus instruction that restricts claims to Marcus, allows other turns only
as context, and asks the extractor to preserve uncertainty and meaning. Legacy
has no added focus instruction: **legacy versus grouped changes both input
representation and instruction**, so it cannot isolate the effect of metadata.
Splitting sessions also changes completion count and per-session context length.

The source is the previously reviewed `Q9_a0b1c2d3`, network `grp_f4a5b6c7`:
**113 dialogue turns, Sessions 1-5, 27 Marcus turns**. Sessions 6-8 remain excluded.
The runner validates the prepared fingerprint, fixed item/network/session scope,
unique ordered source turns, and target-holder output before native persistence.
Neither question nor reference answer enters extraction. Gold is used only by
the judge; the question is used by retrieval and answering.

Each raw extraction response is archived before being replayed through native
`memory_remember_prepare`, `memory_extract_llm`, and `memory_remember_commit`.
FakeLLM supplies the recorded response for the exact rendered prompt hash; native
parsing, normalization, validation, writing and post-write processing still run.
This uses the belief branch only, not the complete episodic/general-fact pipeline.
There is one new database per condition.

After all inputs in one condition are persisted, one default native sleep pass
runs without an optional gist LLM, followed by actual embeddings and native
Planner retrieval for holder Marcus, `k=10`. The query/replay/embedding clock is
fixed at `2026-09-09T16:00:00Z`, later than every actual ingestion timestamp.
It is a controlled runtime clock, not a source event time.

Each condition's **single selected ID list and order** feeds two answer calls:
native rendered lines, and those exact lines prefixed with source session/time
ranges verified through the statements' `evidence_json.engram_ref`. Presentation
order alternates across conditions. An abstaining retrieval preserves the same
native abstention text in both presentations. The separate full-history control
uses all 113 reviewed dialogue turns with their original timestamps.

The source timestamps have **unspecified timezone** and are retained verbatim.
Each annotation is the first-to-last Marcus utterance window in its extraction
unit. For `legacy` and `grouped`, all statements share the broad Sessions 1-5
window; split conditions have session-specific windows. These are **not exact
statement timestamps or claim event times**. The annotation contains no source
utterance text, missing claims or gold anchors.

Native `src/extractor/json_parser.cpp` still sets belief `observed_at` to the
actual extraction clock. `remember_prepare.created_at_iso8601` supplies the
engram/pipeline clock and does not assign a source event time to beliefs. No
native temporal schema or event-time ingestion support is claimed by this
application-level evidence presentation experiment.

## Execution And Results

Extractor: `deepseek-v3` via the explicitly configured DashScope endpoint,
temperature 0, max_tokens 4096, timeout 60 seconds, native max_retries 3.
Embedding: `qwen3.7-text-embedding`, 1,024 dimensions. Answerer and judge:
`gpt-5.5`, temperature 0, max_tokens 512 and 8 respectively.

Exactly **12 extraction completions, 9 answers and 27 judge verdicts** were
archived. Each answer receives three fixed YES/NO calls; majority vote is primary.
All votes within each cell were unanimous. Transport retry attempts are not
separately exposed in this journal, and embedding calls are not part of these
completion counts. No answer or extraction was regenerated based on quality.

| Variant | Stored / embedded | Consolidated before / after sleep | Retrieved | Native votes | Source-range votes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `legacy` | 13 / 13 | 0 / 13 | 10 | 0/3 | 0/3 |
| `grouped` | 15 / 15 | 0 / 15 | 10 | 0/3 | 0/3 |
| `sessions` | 15 / 15 | 3 / 15 | 10 | 0/3 | 0/3 |
| `session_context` | 14 / 14 | 3 / 14 | 10 | 0/3 | 0/3 |
| Full reviewed dialogue | N/A | N/A | 113 turns | 3/3 | N/A |

All twelve recorded extraction pipelines finished, including two valid empty
responses (`sessions` Session 2 and `session_context` Session 1). No embedding
failed. All 57 statements were consolidated after sleep; no new gist was created.
The failed answers therefore cannot be attributed solely to lifecycle exclusion
or a partially embedded store in this run.

## Source Claim Findings

The following is a qualitative comparison of already diagnosed source claims,
not a newly calibrated coverage score over all 27 target turns.

| Source claim | Raw extraction and stored evidence |
| --- | --- |
| Session 3, `s03_t018`: "might be going for it" | Recast as positive `prefers going for it` or `prefers going for new hub` in all four conditions. |
| Session 3, `s03_t020`: "swindon. not decided yet" | No explicit undecided-state statement in any condition. |
| Session 5, `s05_t006`: "more the change honestly. ready for something different" | Some change preference is retained in every condition. Legacy stores it but its top 10 omits it; the other conditions retrieve it. |
| Session 5, `s05_t019`: "bit nervous about starting over ... same spot for three years" | No condition retains nervousness or the explicit three-year stagnation. Legacy, sessions and session_context instead produce `Marcus prefers starting over`; grouped omits that statement as well. |

Turn IDs in this table have the common prefix `grp_f4a5b6c7_`. Raw responses,
source payloads and native rows are available together in the run directory.
The nervousness loss is visible in the raw JSON before native replay, so it is
not introduced by the source annotation or renderer. The current prompt's
`OBJECT BREVITY` rule says to drop hedges and elaborations and restricts predicate
vocabulary; these are plausible contributors, not causes isolated by this run.

Topic context is also lost. In Session 4, "if they're quiet about it" concerns
commercial short-term rentals. Legacy emits `Marcus prefers quiet about it`,
and its native answer interprets this as wanting his move kept quiet. Merely
adding a broad source range still leaves the underlying statement ambiguous.
Session-context extraction resolves the subject to Airbnb, but emits the invalid
preference `Airbnb prefers no problem if quiet`; it likewise emits
`onigiri prefers good`. Both are stored with entity subjects and neither enters
that condition's top 10. Correct subjects on the previous twelve synthetic
cases therefore do not establish correctness on contextual social dialogue.

Even session-range annotations do not guarantee correct topic attribution:
the `sessions/source_ranges` answer uses "do it this afternoon" from Session 1
as part of Marcus's earlier moving stance. The memory lacks the conversational
referent. This is a semantic/context problem in addition to chronology.

The full-history answer correctly describes him as "mixed but resolved", admits
he was "a bit nervous about starting over", and contrasts this with earlier
understated, noncommittal replies. All three judges accept it. This control has
complete reviewed dialogue rather than ten target-holder belief statements, so
the gap does not isolate a single component or quantify production performance.
Repeated votes from one judge are not independent backbones, and one answer per
condition does not estimate answer-generation variance.

## Verification And Artifacts

Seventeen new focused tests pass, covering source scope/order, original payload
parity, no gold leakage, native evidence mapping and persistence, unchanged paired
selection, and native embedding/retrieval/database archiving in all four variants.
Independent review identified and verified the fixed-scope and abstention guards
before the real run. Fresh full Python validation: **1,111 passed, 15 skipped**.

Offline verification checks all archived source hashes, input turns and payload
bytes, the canonical native engram content hashes, all database integrity checks,
tenant/holder scope, pipeline completion, vector coverage, selection and annotation
correspondence, exact answer/judge prompts, fixed call counts and recomputed votes.
After final review, it additionally replays all twelve archived responses through
the native pipeline offline and compares per-input stored semantic fields,
including normalized objects. All forty selected lines are checked against their
database statements and score order, and vectors are checked by statement ID and
byte length. All pass. These offline replays make no new model calls.

A verifier-only assumption that content_hash was plain SHA-256(payload)
was corrected after reading `src/evidence/engram.cpp`: its byte-preserving form is
SHA-256(`v1\x1f` + payload + `\x1f`). Run artifacts did not need repair or retries.

The loaded core SHA-256 remains
`ebd2c36a7f4a17760cdbed74da279d8c6204157102e6e79189fc365a2da4a376`,
unchanged from the preceding polarity round, whose C++ validation was
**1,007 passed, 1 skipped**. No fresh C++ build or test run is claimed here.

- `scripts/eval_socialmem_temporal.py`: fixed diagnostic runner.
- `tests/python/test_eval_socialmem_temporal.py`: focused offline/native tests.
- `build/socialmem_20260909_temporal_run/`: inputs, reviewed record, exact
  extraction/answer/judge journals, four databases, before/after states, selected
  evidence, manifest, source archive, results and verification receipt.
- `build/socialmem_20260909_temporal_pytest.log`: full Python validation.
- `build/socialmem_20260909_temporal_verify.py`: offline verifier.

```sh
.venv/bin/python build/socialmem_20260909_temporal_verify.py

.venv/bin/python scripts/eval_socialmem_temporal.py --real-run \
  --prepared build/socialmem_20260909_scoped_corpus \
  --out build/socialmem_temporal_repeat_fresh \
  --now-iso <UTC-time-later-than-expected-ingestion-completion>
```

## Predicate Coverage Follow-Up, 2026-09-10

The project owner supplied an earlier evaluation finding: insufficient predicate
richness prevented many questions from being answered correctly. This makes
predicate expressiveness a primary follow-up, alongside the observed semantic
loss. That broader historical finding is project context; this one-item run does
not independently measure how many benchmark questions it affects.

Current source inspection distinguishes three parts of the contract:

- `predicate_registry.hpp` registers 32 predicates across belief (10), action
  (10), perception (4), and general-fact (8) classes. Unregistered non-OCCURRED
  predicates are accepted with `REVIEW_REQUESTED`; OCCURRED actions are open-domain.
  Thus the whole native store is not limited to ten predicates.
- The belief prompt still restricts output to ten predicates and instructs the
  model to choose the closest one. Its brevity rule also removes hedges and
  elaborations. Emotional states and decision uncertainty have no explicit
  dedicated relations in that vocabulary.
- The general-fact prompt supplies attributes and relations but excludes voiced
  opinions and other conversational mental-state claims. The episodic prompt
  targets physical events. A richer registry therefore does not by itself ensure
  that the appropriate extraction channel preserves a social or emotional claim.

In this completed run, **46 of 57 stored statements use `prefers`** (11, 12, 10,
and 13 across the four conditions). The mistakes documented above show that this
is not simply a high frequency of genuine preferences. However, the earlier
reviewed-scope archive contains statement
`c0462c8b-142f-8a9e-de3c-bd6b5464c4ec` with predicate `believes` and an object
retaining "bit nervous about starting over" and the stagnation explanation
(`build/socialmem_20260909_scoped_run/item_1/ingestion.json`). Existing relations
can sometimes retain the information in a full clause. Vocabulary coverage,
object compression, and inconsistent extraction must therefore be tested
separately; adding predicate names alone is not yet a verified repair.

## Next Work

The predicate/fidelity follow-up is now recorded in
[2026-09-10-socialmem-predicates.md](2026-09-10-socialmem-predicates.md). Defined
predicate extensions improve synthetic support from 4/16 to 14/16, but combined
regresses on P1. Three scoped memory cells fail on malformed general-fact JSON;
Q9 combined retrieves explicit nervousness but still scores 0/3 on the complete
temporal comparison. The archive is verified; production defaults are unchanged.

Prioritize the predicate/semantic contract before native event-time changes.
Use generic emotion, uncertainty, indifference, social-relation and topic-reference
cases independent of Q9. Compare richer clause preservation with a minimal
general-purpose predicate extension while holding source inputs and model fixed;
do not change both at once and attribute the result solely to vocabulary.
`ExtractionConfig.extra_core_predicates` already provides an additive validation
policy for an isolated trial, but the extraction prompt and downstream consumers
must also understand the proposed relations.

Audit the production three-channel route to identify which channel owns each
claim. Then check raw extraction, stored semantic fidelity, retrieval coverage
and answers separately, retaining the unchanged P1 corpus as a regression check.
Source session retention remains useful provenance, but this run does not justify
adopting session splitting as a proven QA improvement or treating temporal
metadata as the main remaining bottleneck.
