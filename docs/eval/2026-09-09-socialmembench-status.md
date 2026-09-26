> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench continuation, 2026-09-09

> 后继结果（2026-09-12）：[来源话轮与独立扩展标签诊断](2026-09-12-socialmem-source-turn.md)已完成并核验，固定候选 61/64、synthetic 契约 8/16、扩展对象覆盖 9/14/联合覆盖 1/14，质量门槛未通过。以下保留各自阶段的历史结果。

Current overview: [overall progress, problems and optimization execution](2026-09-10-socialmem-overview.md).
The historical and first two diagnostic rounds below retain their original protocols and scores.

## Scope and evidence

This checkout is `starling-web`, on `main` at
`8b6cc91b309aff4b6bcf02bb62393871dafa435f`. The changes described below are
uncommitted. Existing `.context/` and the untracked benchmark downloads are retained.

The benchmark named SocialMemoryBench in the request is the existing
[SocialMemBench dataset](https://huggingface.co/datasets/anon4data/socialmembench).
Its current dataset card states "All data is synthetic", "Generated with Claude
(Anthropic)", and CC BY 4.0. All four local Parquet SHA-256 hashes match the
public repository's LFS hashes. Re-running `adapt_socialmembench` over those
Parquet files reproduces every record in `build/socialmembench_corpus.jsonl`.

| Source | Rows |
| --- | ---: |
| Networks | 43 |
| Personas | 430 |
| Conversations | 7,355 |
| QA | 1,031 |
| Multiple choice | 214 |
| Long form | 640 |
| Short answer | 177 |

Source verification: `build/socialmembench_provenance.json`,
`build/socialmembench_dataset_card.md`, and
`build/socialmembench_remote_files_raw.json`.

## Historical status

`build/t9_fact.json` is the latest prior ladder report: 22 selected questions,
two answer backbones (`gpt-5.5`, `gpt-5.6`), seed 0, `deepseek-v3` extraction,
and `qwen3.7-text-embedding`. These are historical scores, not a fresh run of
the current checkout.

| Stage | Overall median |
| --- | ---: |
| S0 | 0.250 |
| S_rand | 0.205 |
| S_full | 0.864 |
| S_rag | 0.455 |
| S_star_oracle | 0.789 |
| S_star | 0.227 |

One oracle cell scored 21 of 22 items; the other cells scored 22. No real judge
audit accompanied these reports. They do not establish an advantage for Starling.
The extraction-coverage diagnosis in `build/t11_final_report.md` is based on
selected examples. Keyword absence alone does not establish the causal source
of the aggregate gap or rule out paraphrased evidence.

## Reproduced and repaired

The HEAD commit message and historical final report describe actual-holder
retrieval, but HEAD's `recall_block` still used `querier="alice"`. Meanwhile,
`make_real_extract_fn` writes each speaker's statements under that speaker.
New offline tests reproduced the resulting empty recall even when the correct
statements and embeddings were present.

The evaluation adapter now runs the existing C++ Planner once for each actual
holder in the per-question database's `default` tenant. It merges accepted
entries using the core scores, with a **total** top-k budget and a stable
statement-ID tiebreaker. An explicitly supplied holder remains a single scope.
The core's existing line renderer is exposed through a forwarding Python binding.

The runner also accepts an optional `diagnostics` dictionary containing the
database path, embedding counts, ingest duration, recall block, per-holder
receipts, answer prompt, response, and parsed MC prediction. It does not change
the question, gold answer, model prompts, extraction predicates, or thresholds.

This is an observer-level, full-conversation evaluation protocol. Iterating
speaker-owned stores does not demonstrate a participant-specific knowledge
frontier, perspective masking, or theory-of-mind capability.

## Verification

- Canonical build: `.venv/bin/python scripts/configure_build.py --build --test --no-network`.
- Rebuilt and reinstalled the Python extension using `--python-editable`.
- Full C++ suite after reinstall: 1,004 passed, 1 skipped, 0 failed.
- Full Python suite: 1,043 passed, 15 skipped, 0 failed.
- Added tests cover actual speakers, tenant isolation (including the same
  statement ID in another tenant), explicit scope, total top-k, end-to-end
  prompt visibility, diagnostic output, cross-holder score ordering, and
  preservation of successful scopes when another holder abstains.
- Logs: `build/socialmem_20260909_ctest.log` and
  `build/socialmem_20260909_pytest.log`.

## Diagnostic run

The current `OPENAI_BASE_URL` has an empty path and returned HTTP 200 HTML at
`/chat/completions`. The same host with `/v1` returned a valid model response.
The probe overrides the API path only inside its own process. The original
embedding model was independently verified to return 1,024 dimensions.

The bounded probe uses three preselected, untruncated cases:

| Item | Type | Format | Turns |
| --- | --- | --- | ---: |
| Q4_c0s2c2 | Q4 | Multiple choice | 50 |
| Q1_a5s1c1 | Q1 | Long form | 50 |
| Q9_a0b1c2d3 | Q9 | Long form | 178 |

It runs all six stages with `gpt-5.5`, seed 0, `deepseek-v3` extraction through
the configured DashScope endpoint, `qwen3.7-text-embedding` at 1,024 dimensions,
and total k=10. The two free-text cases receive up to three generated judge
distractors each. This small audit cannot calibrate a benchmark-wide error band.

Reproduction driver: `build/socialmem_20260909_probe.py`.
Command (use a fresh output directory):

```sh
.venv/bin/python build/socialmem_20260909_probe.py --real-run \
  --chat-api-path /v1 --out build/socialmem_20260909_probe
```

Output directory: `build/socialmem_20260909_probe/`. `manifest.json` records the
HEAD, source and binary hashes, selected corpus hash, and run configuration;
`journal.jsonl` preserves each answer and the actual database statements;
`ladder.json`, `judge_audit.json`, and `judge_candidates.json` record results.
Only ingest wall time is measured; token usage and monetary cost remain unknown.

## Fresh diagnostic results

Completed at 2026-09-09 16:03:12 Asia/Shanghai, after 11 minutes 3 seconds.
All 18 distinct item-stage observations completed without exceptions. Source
fingerprints still match the final implementation. Three archived S_star
databases passed SQLite integrity checks.

| Stage | MC correct (1 item) | Free-text correct (2 items) | Total correct |
| --- | ---: | ---: | ---: |
| S0 | 0 | 0 | 0/3 |
| S_rand | 0 | 0 | 0/3 |
| S_full | 0 | 1 | 1/3 |
| S_rag | 0 | 0 | 0/3 |
| S_star_oracle | 0 | 1 | 1/3 |
| S_star | 1 | 0 | 1/3 |

The judge rejected 6/6 generated distractors (observed false acceptance 0/6).
A separate known-correct arithmetic control returned `YES`. These observations
verify that the judge path operates; they do not establish a zero error rate,
judge sensitivity on this benchmark, or a calibrated significance threshold.

| S_star item | Written and embedded | State/review eligible | Volatile | Stored holders |
| --- | ---: | ---: | ---: | ---: |
| Q4_c0s2c2 | 15 | 3 | 12 | 1 |
| Q1_a5s1c1 | 26 | 9 | 17 | 4 |
| Q9_a0b1c2d3 | 68 | 6 | 62 | 3 |

No embedding failures were recorded. `src/retrieval/retrieval_planner.cpp`
and `src/retrieval/semantic_retriever.cpp` apply the normal
`consolidated|archived` state filter. Thus "all statements embedded" does not
mean "all statements retrievable" in this immediate post-ingest experiment.
This is a measured lifecycle difference, not evidence that those excluded
statements contain the answer or that removing the guard would improve quality.

Manual inspection of the stored prompts and outputs:

- Q4: S_star chose the correct option, but its three memories concern a meeting
  time, a hard stop, and Soho. They do not support the career-success comparison.
  This correct answer is not evidence of successful retrieval of the gold facts.
- Q1: S_star retrieved "no more bulk" and traffic/parking preferences, but its
  answer described a cautious stance rather than the stronger, historically
  grounded opposition in the reference. The judge rejected it. S_full and the
  evidence oracle passed this case.
- Q9: S_star recalled an intention to move and a desire for change, then answered
  that the memories did not establish the person's emotional state or its change.
  S_full captured nervousness but asserted continuity instead of the reference's
  contrast with earlier reserve; the judge rejected that answer as well.

The next diagnostic should therefore separate extraction coverage, lifecycle
eligibility, and answer/judge disagreement. The probe does **not** confirm that
the vocabulary is the sole cause, that the cognitive layer improves accuracy,
or that the repaired harness meets the full benchmark acceptance criteria.

`extraction_audit.json` and `databases/*.db` preserve the S_star write attempts,
raw empty extraction outputs where recorded, statement states, and token
counters. Recorded extraction-attempt tokens total 119,482 across the three
cases. This excludes unrecorded extraction calls, answer/judge calls, and
embeddings, so it is not the total API cost. S_star ingest wall time was 273.1s;
complete S_star evaluation wall time was 308.7s.

Archive command: `.venv/bin/python build/socialmem_20260909_audit.py`.

## Remaining evaluation limits

- The normalized oracle contains question-specific evidence excerpts. Its gap
  over S_star combines evidence selection and extraction; it is not a pure
  extraction-tax or cognition-only estimate.
- The current flat RAG baseline omits speaker labels from its memory text,
  while S_full and attributed statements retain them. A fair attribution
  comparison needs a speaker-preserving RAG control.
- Speaker-grouped extraction removes intervening replies and session context.
  Evidence coverage needs semantic inspection across more than one example.
- Immediate post-ingest evaluation also encounters lifecycle filtering: the
  core's default retrieval excludes `volatile` statements. Count eligible
  statements independently of written/embedded statements before attributing
  an empty candidate pool to embedding, ranking, or the extraction vocabulary.
- The generic journal key omits corpus/code/configuration hashes. Never resume
  a historical journal after changing these inputs. This probe uses a fresh
  output directory and records its fingerprints separately.
- Three diagnostic items, one backbone, and one seed cannot support benchmark
  superiority, regression significance, or a representative accuracy estimate.
- Expand only after reviewing stored statements, recall receipts, answers, and
  gold evidence. Use a fixed, stratified set with network-aware analysis, then
  independent backbone replication and a sufficiently sized judge audit.

## Follow-up protocol

1. Define the ingestion-to-query lifecycle explicitly. Compare immediate recall
   with the normal core consolidation/review lifecycle on the same stored
   histories; retain production visibility guards in both conditions.
2. Add a speaker-preserving flat RAG control with the same overall retrieval
   budget. Audit gold evidence coverage in written, eligible, and recalled
   statements separately, including the raw utterances needed for inference.
3. Review the two free-text disagreements against source conversations and
   expand judge testing with both known-correct and known-incorrect answers.
4. Freeze these choices before a larger stratified run. Keep the current three
   cases as diagnostics; never substitute their accuracy for the 1,031-item
   benchmark or combine it with the historical 22-item results.

## Completed frozen-ingest controls

The follow-up completed at 2026-09-09 17:06:11 Asia/Shanghai, after 8 minutes
44 seconds. All 12 item-variant observations completed, using the same three
questions, `gpt-5.5`, embedding model/dimension, and total k=10 as above.
There were no new extraction calls. The two Starling conditions start from
identical SQLite backups of each archived post-query database, including its
stored embeddings and prior access state. The source databases were not changed.

The conditions are explicit evaluation settings:

- `star_immediate`: query the frozen database without further replay.
- `star_sleep`: one native `ReplayScheduler.run_sleep()` call with production
  defaults and `llm=None`, then the normal embedding worker and Planner.
- `rag_legacy`: historical flat utterance text, without speaker labels.
- `rag_speakers`: `speaker: text` in both embedding input and recalled text.

The new runner passes a fixed query/replay/embedding time of
`2026-09-09T09:00:00Z`. The old Planner wrapper hard-coded June 1 despite actual
statement creation in September. Both frozen conditions now use the same time
after source writes. This comparison isolates the additional sleep pass within
the new round; it is not an exact replay of the previous immediate condition.

| Item | Eligible before | Eligible after sleep | Compressed | Gists | Sleep recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q4_c0s2c2 | 3 | 15 | 12 | 0 | 10 |
| Q1_a5s1c1 | 9 | 26 | 17 | 0 | 10 |
| Q9_a0b1c2d3 | 6 | 68 | 62 | 0 | 10 |

All volatile rows were consolidated by this single native pass. Review-status
counts stayed identical. No TTL archiving, forced consolidation, gist generation,
or new Starling embeddings occurred. This demonstrates lifecycle eligibility
changing, not a benefit from gist synthesis or the entire maintenance system.

| Variant | Q4 MC | Q1 free text | Q9 free text | Initial correct |
| --- | --- | --- | --- | ---: |
| star_immediate | wrong | rejected | rejected | 0/3 |
| star_sleep | wrong | accepted | rejected | 1/3 |
| rag_legacy | wrong | accepted | rejected | 1/3 |
| rag_speakers | wrong | rejected | accepted | 1/3 |

These are the first recorded judgments, without replacing scores after seeing
repeated judgments. They do not establish improvement, equivalence, or a
representative accuracy estimate.

## Evidence and judge inspection

Inspection covered the stored statements, recalled IDs/text, raw utterances,
and source Parquet records, rather than keyword absence alone:

- Q4: the frozen store has only Mei-owned statements. Neither her eight-person
  team and two senior hires nor Leon's funding/profitability distinction is
  represented in the 15 stored statements. Sleep makes more unrelated details
  eligible. Speaker-preserving RAG retrieves both gold excerpts, but the MC
  response remains index 1 (`Leon`). The raw question asks for **two roles**,
  whereas all four choices are single names and the designated answer is
  index 2 (`Mei`). The raw reference says Leon projects success and Mei reports
  accomplished progress. This ambiguity is present in the public source and
  must be audited before treating the MC score as clean evidence of failure.
- Q1: all seven Claudette-owned statements were already consolidated before
  sleep. They retain preferences such as "no more bulk" but lose the historical
  comparison and explicit development-to-traffic reasoning. Sleep increases the
  global pool but leaves only three of her statements in the final top 10.
  Its short answer was accepted while the more detailed `rag_speakers` answer
  was initially rejected. The latter contains the objection, development/traffic
  link, collective action, and distinction between temporary and permanent change.
- Q9: all 13 Marcus-owned statements were inspected. They retain moving, the
  Swindon job and desire for change, but not nervousness about starting over or
  the contrast with earlier reserve. Both Starling variants answer unknown.
  `rag_speakers` retrieves Marcus's direct "bit nervous ... same spot for three
  years" utterance and earlier terse replies, and its answer passes. The legacy
  RAG query mostly retrieves other people's mentions of Marcus. This control
  changes both ranking input and visible attribution; it does not separate their
  individual effects.

All eight judge controls behaved as expected: four positives (exact references
and human-written paraphrases) were accepted; four negatives (unknown answers
and explicit contradictions) were rejected. This small control set is not a
benchmark-wide calibration.

The identical original judge prompts for Q1 `star_sleep` and `rag_speakers` were
then repeated three times each with the same model, temperature and token limit.
Both were accepted 3/3. In particular, `rag_speakers` changed from the initial
`NO` to three `YES` results without changing its candidate or prompt. The raw
responses contain actual YES/NO tokens, so this observed variation is not an
empty-response parsing artifact. The initial score table remains unchanged.

There is also a temporal-scope issue in Q9. The question explicitly restricts
evidence to Sessions 1-5, but `adapt_socialmembench` includes all 178 turns from
Sessions 1-8 and discards session indices. Sessions 1-5 contain 113 turns. The
legacy RAG condition actually recalls Sandra's Session-6 message announcing
Marcus's safe arrival. This makes temporal filtering and preservation of source
session/turn IDs necessary before a larger comparison. No question text, gold
answer, or historical corpus was silently rewritten in this experiment.

## Reproduction and validation

```sh
.venv/bin/python scripts/eval_socialmem_controls.py --real-run \
  --probe build/socialmem_20260909_probe \
  --out build/socialmem_controls_fresh \
  --now-iso 2026-09-09T09:00:00Z \
  --judge-controls docs/eval/2026-09-09-socialmem-judge-controls.json
```

Results: `build/socialmem_20260909_controls/`. The manifest records corpus,
core, source database and code fingerprints. `journal.jsonl` contains before/after
states, raw answers, prompts, recall receipts and judge responses; all 12 result
databases are archived. `verification.json` confirms identical starting states
for all three frozen pairs, unchanged source databases, matching core/code
archives, database integrity, review preservation and retrieval budgets.

Independent review found two boundary issues, now fixed with regression tests:
timezone offsets are normalized to UTC before native calls, and nonempty source
WAL files are rejected by the frozen-database fingerprint check. The completed
run used UTC `Z` and checkpointed sources, so these fixes do not change its
inputs. Its exact pre-hardening code is retained in `source_archive/` and matches
the run manifest. Final source hashes are recorded separately in
`verification.json`; the manifest was not rewritten to claim the API run used
the later hardening changes.

- Final full Python suite: **1,052 passed, 15 skipped**.
- Log: `build/socialmem_20260909_controls_final_pytest.log`.
- No further C++/binding changes in this follow-up; the binary matches the
  earlier fully tested core recorded above.
- Repeated judge experiment: `build/socialmem_20260909_judge_repeat/`, driven by
  `build/socialmem_20260909_judge_repeat.py`.
- Artifact verification: `.venv/bin/python build/socialmem_20260909_controls_verify.py`.

The next evaluation step is to preserve source session/turn identity, define
question-specific temporal scope explicitly, and audit ambiguous MC items before
freezing a stratified cohort. Extraction evidence coverage remains a separate
workstream; broader scores should include repeated-judge sensitivity analysis.
