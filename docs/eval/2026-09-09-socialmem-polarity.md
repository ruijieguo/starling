> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench native polarity diagnostic, 2026-09-09

This continues [the reviewed-scope diagnostic](2026-09-09-socialmem-scoped.md).
The native context renderer now preserves stored negative and unknown polarity.
The fixed-selection comparison confirms the text repair, but does **not** show
better whole-question judge scores. This remains a two-item diagnostic, not a
benchmark estimate. No commit or push was made.
The API comparison ran from **21:47:03 to 21:51:20 Asia/Shanghai** (4 minutes
17 seconds); offline evidence verification finished at 21:52:07.

## Native Change

`src/retrieval/context_pack.cpp::render_line` now wraps the entire stored relation:

```text
Before: [FACT] permanence prefers permanence (conf 0.70, holder Claudette)
After:  [FACT] NOT (permanence prefers permanence) (conf 0.70, holder Claudette)
```

`polarity=unknown` similarly produces `UNKNOWN (subject predicate object)`.
Positive and legacy empty polarity retain their previous formatting. Labels,
confidence, holder, subject, predicate and object text retain their values.
The fix is in C++; Python only forwards native rendering and runs experiments.

This does not normalize extraction. For example, the archived negative row with
object `no more bulk` now reads `NOT (street prefers no more bulk)`. The combination
of a negative polarity and negative wording in the object needs an extraction
contract audit. It must not be silently rewritten using language heuristics in
the renderer. The awkward subject `permanence` in `permanence prefers permanence`
also remains a separate representation concern.

## Fixed Inputs

The experiment uses the four archived Starling result databases from the prior
scoped run: Q1/Q9, immediate/sleep. It performs no new extraction, embedding or
sleep pass. The selected statement IDs, order, labels and original ranking
receipts come directly from the prior `journal.jsonl`.

The old installed native binary was copied before rebuilding. Its SHA-256 is
`22fb14f14652a43da961f80f97272cb422127dbf1727a3a97efe71a94efeed03`.
The rebuilt and reinstalled binary has SHA-256
`ebd2c36a7f4a17760cdbed74da279d8c6204157102e6e79189fc365a2da4a376`.
Both binaries and the corresponding renderer source are archived.

To obtain read-only Python-bound native rows, the exporter runs subject/predicate
Planner lookups on disposable SQLite copies, with empty query text and a stub
embedder. It then selects only the previously recorded IDs and renders them with
their previously recorded labels. These lookups do not determine the experiment's
selection or order. Every exposed native field is compared with its archived SQL
value. `BasicRetriever` is unsuitable for this export because it excludes entity
subjects such as `permanence`.

All four old context blocks and answer prompts exactly reproduce the prior
journal. Source database hashes, selected rows including polarity and evidence,
labels, order, questions and references match across exports. Only the following
rendered lines change:

| Item / condition | Selected entries | Changed negative lines |
| --- | ---: | ---: |
| Q1 immediate | 9 | 4 |
| Q1 sleep | 10 | 2 |
| Q9 immediate | 6 | 1 |
| Q9 sleep | 10 | 1 |

There are 35 selected entry occurrences, with eight changed lines and 27 unchanged
lines. Some statement IDs occur in both lifecycle conditions. No unknown-polarity
row appears in this cohort; that behavior is covered by regression tests.

## Answer Comparison

Both phases receive newly generated answers using the same existing recall-only
prompt and API adapter: `gpt-5.5`, temperature 0, answer limit 512 tokens. Each
benchmark answer is judged three times with the unchanged canonical prompt;
majority is primary. The phase order alternates by item/condition. One answer per
cell is retained, without regeneration or selection based on correctness.

These are eight new benchmark answers and 24 recorded judge verdicts. Historical
answers were not reused as the before arm. Repeated calls to one model are not
independent judges, and temperature 0 does not guarantee identical outputs.

| Item / condition | Before accepted votes | After accepted votes |
| --- | ---: | ---: |
| Q1 immediate | 0/3 | 0/3 |
| Q1 sleep | 3/3 | 0/3 |
| Q9 immediate | 0/3 | 0/3 |
| Q9 sleep | 0/3 | 0/3 |

Q1 sleep before again says Claudette "seems to value permanence", and all three
judges accept it. After says she "rejects permanence", but all three judges reject
the whole answer. The reference requires broader planning motivations and street
character evidence; fixing this one relation does not supply those details.
The votes alone do not identify why a judge rejected an answer, and cannot
establish that the polarity repair caused a general quality regression.

Q9 immediate abstains in both arms. Q9 sleep identifies the later nervousness,
but both arms still describe the earlier Marcus as more decisive. The expected
contrast is earlier terse reserve versus later candour. This renderer change does
not repair the chronological evidence/interpretation problem.

## Direct Polarity Probe

Four additional answer calls use the same selected context and ask:
`Does Claudette prefer permanence? Answer YES, NO, or UNKNOWN.`
This is an unscored diagnostic question, not an added benchmark item or reference
change. It uses exact `NO` as the success criterion, without an LLM judge. The
criterion was fixed before calls from Claudette's source turn
`grp_5e6f7a8b_s02_t009`:

> a trial period I could live with. Permanence is what irritates me

| Q1 condition | Before response | After response | Expected |
| --- | --- | --- | --- |
| Immediate | YES | NO | NO |
| Sleep | YES | UNKNOWN | NO |

The immediate probe corrects the observed reversal. The sleep probe stops
affirming it but abstains, so it remains incorrect under the fixed criterion.
Notably, the new sleep benchmark answer says "rejects permanence" while its
separate probe says `UNKNOWN`. Preserving the bit in native text does not guarantee
consistent downstream interpretation. No prompt tuning or answer retries were
used to hide this result.

## Validation And Artifacts

Three C++ regression tests cover the observed negative relation, all canonical
polarities plus legacy empty polarity, and preservation of negative object text.
Two parametrized Python cases exercise native Planner context, its renderer
binding, and the evaluation recall path. Nine pairing tests reject changed
inputs, missing selections, row mutation, prompt injection and object rewriting.
Independent review found no blocking correctness issue.

Fresh full validation after the fix:

- Canonical build and CTest: **1,007 passed, 1 skipped**, 1,008 discovered.
- Editable native extension rebuilt and reinstalled separately.
- Full Python suite: **1,084 passed, 15 skipped**.
- Offline evidence verification: all database integrity/hash checks, both binary
  archives, source archives, paired rows/prompts, eight answers, 24 strict judge
  verdicts, four probes and aggregation checks passed.

Artifacts are local and retained:

- `build/socialmem_20260909_polarity_before/`: old binary/source and native export.
- `build/socialmem_20260909_polarity_after/`: new binary/source and native export.
- `build/socialmem_20260909_polarity_run/`: immutable input exports, manifest,
  raw answer/judge journals, results, source archive and `verification.json`.
- `build/socialmem_20260909_polarity_{ctest,install,pytest,run}.log`: validation/run logs.
- `build/socialmem_20260909_polarity_verify.py`: offline evidence verifier.

The old scoped-run manifest remains unchanged and correctly records the old
binary. Its historical verifier requires that binary and must not be interpreted
as a check of the newly installed core.

Offline verification and a fresh comparison using the retained native exports:

```sh
.venv/bin/python build/socialmem_20260909_polarity_verify.py

.venv/bin/python scripts/eval_socialmem_polarity.py compare --real-run \
  --before build/socialmem_20260909_polarity_before/renderings.json \
  --after build/socialmem_20260909_polarity_after/renderings.json \
  --out build/socialmem_polarity_repeat_fresh
```

The comparison uses the configured credentials and normalizes the process-local
API base path to `/v1`. Output directories are exclusive and cannot overwrite
previous runs. No corpus download is needed.

## Next Work

The [preference extraction follow-up](2026-09-09-socialmem-extraction.md) now
documents the subject/prompt contract repair and a raw-response/native-write
comparison. Targeted relation accuracy improves, but negative-target ambiguity
and long-passage coverage remain unresolved. Q9 chronology/evidence preservation,
the remaining temporal/MC review queue and larger stratified evaluation remain
pending; these diagnostics do not justify a full SocialMemBench score claim.
