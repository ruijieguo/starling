> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench reviewed-scope diagnostic, 2026-09-09

This continues [the earlier diagnostic rounds](2026-09-09-socialmembench-status.md).
The run completed at **2026-09-09 21:06:05 Asia/Shanghai**, after 8 minutes
19 seconds. It is a two-item diagnosis, not a benchmark score or a stratified
sample. No commit or push was made.

## Protocol repairs

`adapt_socialmembench` now retains network identity, source QA identity, session
and message indices, turn IDs, original MC reference text, and source evidence
and temporal anchors. Passthrough retains source and review metadata.

The public data contain **four reused QA IDs across different networks**, affecting
eight different questions. They formerly shared the same normalized `item_id`.
When processing the full source table, colliding IDs now become
`network_id/qa_id`; `source.qa_id` retains the original value. The full normalized
table has 1,031 distinct evaluation IDs. Always normalize the full source table
before selecting subsets, since collision detection depends on that table.
Existing corpus files and journals were retained, not migrated or resumed.

All 1,031 normalized records were compared against the historical corpus after
projecting away new metadata and restoring source IDs. Question, options,
answer, original history text/order/timestamps and gold contents all match.
Evidence joins now use `(network_id, turn_id)` and reject duplicate turn identity.

The explicit [review manifest](2026-09-09-socialmem-protocol.json) binds decisions
to source Parquet hashes, network ID and exact question text:

| Item | Decision | History |
| --- | --- | --- |
| Q1_a5s1c1 | Include, unchanged scope | 50 turns, Sessions 1-5 |
| Q9_a0b1c2d3 | Include, explicit question restriction | 113 turns, Sessions 1-5; omit 65 later turns |
| Q4_c0s2c2 | Exclude from this adjusted diagnostic | Preserve original question, choices and gold |

Q4 asks for two contrasting roles but supplies single-name choices. The source
reference says Leon projects success and Mei reports accomplished progress;
the designated answer is Mei. The exclusion is a documented audit decision
made after observing the ambiguity, not an official dataset correction or a
new score for the historical run. No gold answer was changed.

Session filtering happens **before extraction and every evaluation stage**.
Missing sessions, stale question/network matches, missing explicit scope choices,
and gold evidence outside the allowed turns raise errors. Only reviewed included
records enter the new runner. Its cutoff comes from the explicit manifest;
no natural-language heuristic or gold-anchor maximum silently chooses a cutoff.

All ten source Q9 rows lack structured temporal anchors. Only the diagnosed
Marcus item was reviewed here. The priority queue contains **nine remaining Q9
items and 213 MC items**, all unreviewed, not automatically classified defective.
There are 1,028 unreviewed questions overall. Review of temporal restrictions in
other query types also remains necessary before expanding the cohort.

## Experiment

- Answer/judge: `gpt-5.5`, temperature 0 through the existing API adapter.
- Extractor: `deepseek-v3` through DashScope, production prompt configuration.
- Embedding: `qwen3.7-text-embedding`, 1,024 dimensions; total retrieval k=10.
- Query/replay/embedding clock: fixed `2026-09-09T14:00:00Z`, later than all
  actual ingestion timestamps. This controlled clock is not the run wall time.
- Fresh extraction once per item, followed by embedding and a **pre-query**
  SQLite backup. Immediate and sleep variants each copy that same backup.
- Sleep: one native offline pass, default thresholds, no optional gist LLM.
- Controls: complete scoped history and flat speaker-preserving RAG.
- Each free-text answer receives exactly three canonical judge calls. Majority
  vote is primary; first-vote and unanimous-acceptance counts are also retained.
  Repeated calls to one judge are sensitivity checks, not independent backbones.

| Item | Written / embedded | Eligible immediately | Eligible after sleep | New gists |
| --- | ---: | ---: | ---: | ---: |
| Q1 | 32 | 9 | 32 | 0 |
| Q9 | 80 | 6 | 80 | 0 |

No embedding failures occurred, and both Starling conditions reused all stored
vectors without new embeddings. All 20 recorded belief/general-fact extraction
pipelines finished. A transient Q1 extraction failure was recovered by the
native retry path. Recorded extraction-attempt tokens were 41,769 and 46,908;
these counters exclude answer/judge, embedding and any unrecorded calls.

Archived raw ingestion payloads were compared byte-for-byte with the expected
speaker-grouped text from the allowed histories. All ten payloads matched.
This verifies that Q9's omitted Sessions 6-8 never reached extraction in this
round. Both frozen input pairs match, all eight result databases pass integrity
checks, and all full/RAG source turn IDs are within the allowed histories.

## Results

Cells below show accepted judge votes out of three. No answer was regenerated
or selected based on its score.

| Variant | Q1 votes | Q9 votes | Majority correct | First / unanimous correct |
| --- | ---: | ---: | ---: | ---: |
| Starling immediate | 1/3 | 0/3 | 0/2 | 0/2, 0/2 |
| Starling sleep | 3/3 | 0/3 | 1/2 | 1/2, 1/2 |
| Full scoped history | 3/3 | 3/3 | 2/2 | 2/2, 2/2 |
| Speaker-preserving RAG | 3/3 | 3/3 | 2/2 | 2/2, 2/2 |

Q1 immediate received `NO, NO, YES` on an identical candidate and prompt. All
other cells had unanimous votes. Majority scoring exposes that sensitivity;
it does not calibrate or eliminate judge error.

Q9's fresh extraction **does contain** the nervousness/flat-stagnation statement:
`c0462c8b-142f-8a9e-de3c-bd6b5464c4ec`. It is initially volatile. Sleep consolidates
it and it appears in the final top 10. The answer then identifies the final
emotional state but incorrectly describes the earlier Marcus as more decisively
committed. Full history and RAG correctly contrast earlier terse reserve with
later candour. Thus the current failure cannot be summarized as "the extractor
never captured nervousness". Coverage, lifecycle eligibility, chronology/context,
and answer interpretation are distinct parts of the remaining error.

Q1 exposes a separate representation issue. The database stores
`permanence / prefers / permanence` with `polarity='neg'`, but native
`src/retrieval/context_pack.cpp::render_line` renders
`[FACT] permanence prefers permanence ...` without polarity. The sleep answer
says Claudette "seems to value permanence", contrary to her original
"Permanence is what irritates me". All three judge calls nevertheless accept
that answer. This is a concrete stored-state-to-text loss and a judge coverage
limitation; an accepted cell is not proof that every recalled claim is correct.
The core renderer was not changed in this protocol experiment.

The two fresh extractions differ from previous rounds (Q1 previously 26
statements; Q9 previously 68). Q9 input scope also changed. Therefore cross-round
score differences cannot isolate the effect of session filtering. Within this
round, the two Starling conditions hold extraction and embeddings fixed.

## Reproduction

Preparation uses a Python environment with PyArrow (the current system
`python3` has it). It is offline and validates the existing public source hashes:

```sh
python3 scripts/eval_socialmem_protocol.py \
  --data tests/data/eval_socialmembench \
  --review docs/eval/2026-09-09-socialmem-protocol.json \
  --out build/socialmem_scoped_corpus_fresh
```

Run with a fresh directory and an explicit UTC clock later than the expected
ingestion completion time. The runner validates actual write times before querying:

```sh
.venv/bin/python scripts/eval_socialmem_scoped.py --real-run \
  --prepared build/socialmem_scoped_corpus_fresh \
  --out build/socialmem_scoped_run_fresh \
  --now-iso 2026-09-09T14:00:00Z --judge-repeats 3
```

Current artifacts:

- `build/socialmem_20260909_scoped_corpus/`: source-preserving full corpus,
  filtered diagnostic corpus, exclusions, review queue and source fidelity audit.
- `build/socialmem_20260909_scoped_run/`: manifest, raw answers and judge calls,
  initial/final states, per-item frozen/result databases, evidence audit and
  verification receipts. `source_archive/` preserves exact run sources.
- `.venv/bin/python build/socialmem_20260909_scoped_verify.py`: offline verification.

Independent review identified a final extraction-status check missing from the
old adapter. It now checks the native `extraction_failed` outcome, returns holder
receipts, and the scoped runner rejects unfinished/failed recorded pipelines.
Regression tests cover genuine core failure and successful empty extraction.
These checks were added after the API process started; the manifest retains its
original code hashes. The completed databases were independently checked and all
recorded pipelines finished. `verification.json` records later source hashes
separately, without presenting the hardened code as the executed API version.

Final validation: **1,073 Python tests passed, 15 skipped**;
`build/socialmem_20260909_scoped_final_pytest.log`. No C++ or binding code changed
in this round; the binary matches the earlier fully tested core. `git diff
--check` is clean.

## Next Work

The native polarity repair and frozen-selection answer comparison are now
documented in [the polarity follow-up](2026-09-09-socialmem-polarity.md). Stored
negative/unknown polarity is preserved, but the two-item comparison does not
improve whole-question judge scores. Extraction subject/negation semantics,
chronological evidence loss in speaker-grouped extraction, and the remaining
temporal/MC review queue still need separate work before a larger stratified run.
