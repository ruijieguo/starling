# P2.a Extractor v12 Prompt — EVAL Regression Fallback Decision

**Date:** 2026-05-27
**Task:** P2.a Task 31 — extractor v12 prompt explicit_negation + EVAL fallback decision

## Summary

The v12 extractor prompt (which added `negation_subject` field recognition for
"X 不知道 Y" / "I didn't tell Bob X" patterns) was evaluated against the P1 EVAL
corpus (`tests/data/eval_p1_corpus.jsonl`, 50 records, 3 rounds).

Per spec §10.2 fallback decision tree, the v12 prompt is **reverted to v11** because
the `holder` F1 on the last round dropped below the 0.85 threshold.

## 3-Round F1 Results (v12)

| field             | round 1 | round 2 | round 3 | threshold | last >= threshold |
|---|---|---|---|---|---|
| holder            | 0.855   | 0.849   | 0.818   | 0.85      | **FAIL**          |
| holder_perspective | 0.869  | 0.849   | 0.832   | 0.80      | PASS              |
| predicate         | 0.883   | 0.877   | 0.847   | 0.75      | PASS              |
| object            | 0.883   | 0.877   | 0.847   | 0.70      | PASS              |
| nesting_depth_1   | 0.667   | 0.700   | 0.778   | 0.60      | PASS              |

Full report: `build/eval_p1_v12.md`

## Root Cause Note

Round 3 experienced 7 transient SSL EOF errors (evals 000–006) at the start.
Each failed record produced empty extractions (all FN), which depressed the
`holder` F1 from ~0.85 (rounds 1–2 pattern) to 0.818. However, per spec §10.2
the decision tree applies to the last-round F1 regardless of root cause, so
the fallback path is mandatory.

## Decision

Per spec §10.2 fallback path:

- **v12 prompt changes are reverted** (`git restore scripts/eval_p1_extractor.py`).
  `scripts/eval_p1_extractor.py` stays at v11.
- **`explicit_not_told` stays empty in P2.a.** No `negation_subject` fields will
  be emitted by the v11 extractor, so `KnowledgeFrontier::record_explicit_negation`
  will never be called in P2.a production code.
- **P2.b extractor revision will revisit** explicit_negation with a more robust
  prompt design that protects the `holder` F1 from degrading when negation examples
  are added to the few-shot block.

## BeliefTracker Handler Status

`src/tom/belief_tracker_handlers.cpp::handle_statement_written` line 114 already
has a "skip if absent" comment for `negation_subject`:

```cpp
// 4. negation_subject — P2.a v11 prompt has no such field; skip if absent.
// (P2.a v12+ may add this; no-op if absent)
```

The handler does NOT crash on v11 statements (which omit `negation_subject`).
`KnowledgeFrontier::record_explicit_negation` is callable but unused — the method
is preserved for future use in P2.b.
