> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：开发332/733=45.29%，对上一轮37.24%提升8.05百分点；60回答截断等74技术失败计零。本文历史结果保留原冻结身份；最新开发结论及限制见[当前报告](2026-09-17-socialmem-grounded-answer.md)，无本轮保留或全量成绩。

# SocialMemBench Independent Mental-State Supplement

Status: real run completed and verified on 2026-09-10. See the [overall report](2026-09-10-socialmem-overview.md)
for preceding evidence and the optimization plan.

Synthetic majority support improves from **3/16 to 13/16**, but both reviewed
memory QA arms remain **0/2**, versus **2/2** for full dialogue. The native text
fidelity option is implemented and tested; the specialist prompt remains
experimental because it introduces semantic false positives and fails P1 and
the strict control gate. This establishes no full-benchmark accuracy gain.

## Intervention and Frozen Protocol

The new experiment tests a separate specialist prompt for `feels`,
`uncertain_about`, `decided_on`, `indifferent_to` and `trusts`. It uses the
existing native Extractor with additive predicate registration and the new
`preserve_text_objects=True` policy. The original belief prompt and core
predicate registry remain unchanged. The specialist pass does not replace,
filter or rewrite the original responses or their native statements.

This intervention combines an independent prompt with lossless object storage;
it does not identify separate causal effects for every instruction. It is an
experimental runner, not an additional automatic production ingestion channel.

| Track | Fixed inputs and comparison | New extraction calls |
| --- | --- | ---: |
| P1 | 50 unchanged records; archived baseline raw responses plus fresh supplement | 50 |
| Synthetic | Original 16 cases; fresh baseline and supplement in rotating order | 32 |
| Controls | Eight new cases frozen before calls; six expected-empty and two exact relations | 8 |
| Reviewed speakers | Same ten grouped speaker inputs as earlier diagnostics | 10 |

Total: 100 new extractions. P1 compatibility is measured against frozen base
responses, not a fresh baseline completion round. Both complete combined-output
P1 scores and preservation of base native semantics are recorded. Additional
facts can count as false positives against unchanged P1 labels; simply retaining
the base prompt cannot establish non-regression of the combined output.

Synthetic judgments compare all native baseline statements against baseline
plus supplement. All 16 questions remain included, including preference/world
fact cases outside the new specialist vocabulary. Each condition gets three
unchanged canonical judge calls. These are sufficiency judgments, not generated
benchmark answers.

Reviewed QA uses the original Q1 and Q9 Sessions 1-5 frozen databases, with
source record and database hashes checked. Each is copied into baseline and
supplement arms. The supplement arm adds the new native statements. Both run
native default sleep, embedding and Planner retrieval with total k=10 across
actual holders. Both receive new answers, plus a complete reviewed-dialogue
control. This is six answers and 18 QA votes; together with 96 synthetic votes,
the protocol contains 114 judge calls. No historical answer is reused.

Grouping, question, reference, answer template and scoring are unchanged. The
experiment does not introduce source-context enrichment or fabricated historical
event timestamps. Source records contain only reviewed turns. Neither questions
nor references enter extraction. Multi-holder recall is the full-conversation
observer protocol, not participant-specific knowledge-frontier validation.

Extraction model: DashScope `deepseek-v3`, temperature 0, max tokens 4096;
answer/judge model: `gpt-5.5`, limits 512/8; embedding:
`qwen3.7-text-embedding`, dimension 1024. Existing transport retries are retained
and are distinct from quality retries. There is one completion per planned
condition; malformed/failed responses are retained, not repaired or regenerated.

## Native Fix and Validation

The default theme path still maps `the cabbages` to `cabbage`. The explicit
free-text path retains `noise from upstairs`, `Ren with the keys`, `all three
options` and plural/temporal clauses exactly, hashing the preserved text with
the existing canonicalization API. Blank canonical objects are rejected.
Changing this setting does not migrate old values or hashes, so deployments
must choose a stable policy per corpus. Theme-based ToM query primitives still
expect normalized entity themes.

Final full native validation: 1,010 passed, 1 skipped. Full Python after the
verifier regression fixes: 1,162 passed, 15 skipped. Complete offline smoke exercised
100 FakeLLM completions, six fixed fake answers, 114 fixed NO votes, 88 databases
and 84 native case replays. It is explicitly labelled `offline_smoke`; none
of its scores are real-model evidence.

## Extraction Results

All 100 planned extraction calls completed. The 84 supplemental conditions
contain 80 native successes and four failures, all on P1 empty responses that
duplicated the array (`[]` followed by a fenced `[]`). All four remain in the
denominator. Strict bare-array compliance is 36/84; most other successful calls
use a single Markdown fence, which the existing native parser accepts.

All extraction transports succeeded, including the 16 fresh synthetic baseline
calls, which also persisted successfully. The specialist emits 117 stored rows
in 44 nonempty conditions. All 80 successful supplemental conditions preserve the raw object multiset in
native storage. Empty successful responses are included in this condition count;
it is not a claim of 80 nonempty correct relations. Base semantic fields remain
unchanged in every case. There are zero unlisted supplemental predicates and
zero narrow subject-kind/modality/polarity-enum violations, but eight raw holder
mismatches. Native default holder override must not hide those attribution errors.

The fixed eight-control gate is **5/8**. The six expected-empty cases produce
one semantic false positive: conditional `If the route were cancelled, I would
feel worried` becomes an affirmative current feeling. Negative-feeling and
scoped-trust controls store the intended exact relations, retaining both keys,
but have fenced output and therefore fail the predeclared combined format/exact
gate. This explanation does not change their scored outcomes.

### P1 Compatibility

All 89 base statements remain intact. The specialist adds 41 rows across 18
P1 cases. The original labels contain no matched new relation, so the added
rows leave TP/FN unchanged and increase FP by 41 in the four flat metrics:

| Metric | Frozen baseline | Combined output | Existing threshold |
| --- | ---: | ---: | ---: |
| holder | .7500 | .5970 | .85 |
| perspective | .7000 | .5572 | .80 |
| predicate | .7875 | .6269 | .75 |
| object | .7875 | .6269 | .70 |
| depth-1 | .5455 | .5455 | .60 |

These scores do not distinguish a correct extra claim absent from P1 labels
from an invented claim. Source inspection shows both, so the label limitation
cannot justify dismissing the regression:

- `eval-032/034` retain explicit future routing actions as decisions. These
  are absent from the original responsibility-oriented labels.
- `eval-000` turns ordinary beliefs about responsibility into `trusts` relations,
  including `Bob trusts Bob is responsible for auth`. Believing a proposition
  is not evidence of interpersonal trust under the declared relation contract.
- `eval-035/043/045` turn cognitive judgments, including Chinese `觉得`, into
  `feels` rows. They state beliefs about ownership/causes, not emotions.
- `eval-013/015/023` treat a current responsibility claim as a chosen future
  action. `eval-008` attributes an instruction to the instructed person's
  counterpart as that counterpart's own decision.
- Promise and preference utterances are also sometimes duplicated as decisions,
  despite the intended division between the legacy and specialist passes.

The experiment demonstrates preserved base output, not semantic compatibility
of the combined output. It does not pass the unchanged P1 acceptance gate.

### Source Fidelity and Remaining Gaps

Q9 Marcus gains five rows, including `a bit nervous about starting over` and
affirmed uncertainty about `going for the new hub in Swindon`. Q1 Claudette gains
the irritation at parking permanence and fear about traffic/development.
However, `indifferent_to/either way` still has no resolved topic, and Claudette's
`feels/not convinced ...` with NEG duplicates the denial.

The original synthetic negative-emotion case now stores the explicit feeling
with correct NEG scope. Mixed emotions retain `colleagues`; topic-reference
retains `upstairs`. The decision-change case still omits both `last week` and
`today`, and the property/desire case still lacks the boiler property and uses
an unresolved `it`. Preserving raw text prevents native damage but cannot
recover information already omitted or misinterpreted by extraction.

## Synthetic Judgments and Reviewed QA

Both synthetic arms complete 16 cases with 48 valid votes each. Baseline has
3/16 majority-supported cases; baseline plus supplement has 13/16. The three
remaining supplemented failures are positive emotion, reported distrust and
the mixed property/desire case. Positive emotion and reported distrust contain
the intended added relations but receive only 1/3 accepting votes. The judges
do not provide reasons, so these votes do not identify the cause. Existing
incorrect base relations also remain in the combined candidate.

The decision-change candidate receives 3/3 votes despite losing both temporal
qualifiers. Semantic clause checks remain necessary alongside judge scores.

| Reviewed question | Frozen-base memory votes | Base plus supplement votes | Full reviewed dialogue votes |
| --- | ---: | ---: | ---: |
| Q1 | 0/3 | 0/3 | 3/3 |
| Q9 Sessions 1-5 | 0/3 | 0/3 | 3/3 |

Q1 adds 27 statements, giving 59 total; Q9 adds 29, giving 109 total. All 56
new rows embed successfully. Baseline arms reuse existing vectors; no embedding
failure occurs. Native selection includes eight new rows in Q1 and five in Q9.
Missing eligibility or complete failure to retrieve the new predicates therefore
does not explain these two answer failures.

Q1's supplemented answer now describes opposition to bulk, traffic danger for
children and mixed views on parking. It still lacks the reference's historical
residential-character frame. The newly retrieved `NOT (Claudette feels not
convinced ...)` also demonstrates remaining negation-scope damage at extraction.
Q9 retrieves the nervousness, but the answer describes earlier Marcus as
indifferent about the move using topic-free `either way`. Full dialogue supports
his earlier terse/detached manner and later more candid reflection. These are
manual evidence observations, not inferred reasons supplied by the judge.

This comparison is incremental augmentation of historical databases. Existing
base errors remain, and new rows have fresh ingestion times, which can affect
native ranking. Its result is the effect of the complete incremental strategy,
not an isolated vocabulary or recency effect. A fresh complete paired ingestion
is still needed before making a production or benchmark-wide claim.

## Verification Maintenance

During native replay of a failed supplemental case, the verifier incorrectly
compared pipeline statuses and stored object lists in random UUID order. Focused
reproductions failed; the verifier now compares their multiplicities and separately checks each
channel's failure receipt and native semantics. This is a verifier correction,
not a changed extraction, scoring rule or response.

The real run's original manifest and executed source archive remain unchanged.
`--allow-verifier-update` permits only the verifier file itself to differ and
records both hashes in the verification receipt. All executed runner/dependency
sources, input/output artifacts and the native binary remain subject to exact
hash checks. This flag cannot excuse changes to executed experiment code.
Final verification at `2026-09-10T10:55:16Z` passed all 88 databases, 84 native
case replays, 100 recorded extraction calls, six answers and 114 judge votes.
Seven focused supplemental-runner/verifier tests pass, including mixed
failed/finished pipelines and multi-object replay order.

## Artifacts

- `scripts/eval_socialmem_supplement.py`: fixed runner and specialist prompt.
- `scripts/verify_socialmem_supplement.py`: native replay and evidence verifier.
- `tests/data/eval_socialmem_supplement_controls.json`: new frozen controls.
- `build/socialmem_20260910_supplement_run/`: real inputs, sources, native binary,
  raw calls, databases, judgments and results.
- `build/socialmem_20260910_supplement_smoke/`: offline-only verified run.
- `build/socialmem_20260910_optimization_before/`: retained old binary and sources.
- `build/socialmem_20260910_optimization_build_final.log`: native validation.
- `build/socialmem_20260910_optimization_pytest_verified.log`: Python validation.

The real run ran from `2026-09-10T10:38:46Z` to `2026-09-10T10:53:35Z`
(14 minutes 49 seconds). Its fixed query clock is
`2026-09-11T00:00:00Z`, used for ingestion/lifecycle comparison, not as a source
event date. The loaded native binary SHA-256 is
`080c933c343519620b603b99fe0715c25218fe76c563b92554d68a3bf0b6e569`.

```sh
.venv/bin/python scripts/eval_socialmem_supplement.py \
  --previous build/socialmem_20260910_contracts_run \
  --scoped build/socialmem_20260909_scoped_run \
  --out build/socialmem_supplement_repeat_fresh

.venv/bin/python scripts/verify_socialmem_supplement.py \
  build/socialmem_20260910_supplement_run --allow-verifier-update
```
