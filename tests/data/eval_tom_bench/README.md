# ToMBench eval corpora

Multiple-choice Theory-of-Mind corpora consumed by `scripts/eval_tom_bench.py`.
Each line is one JSON record:

```json
{"question_id": "...", "context": "...", "question": "...",
 "options": ["a", "b", "c", "d"], "answer": 0, "ability": "..."}
```

`answer` is a 0-based index into `options`. The harness filters records by
`ability` (first-order vs second-order subset) and reports per-round accuracy.

## `first_order.jsonl` — first-order ToM (admission threshold 0.55)

Hand-authored original questions in the classic first-order false-belief
paradigm (Sally-Anne, Baron-Cohen et al. 1985). Abilities:
`unexpected-outcome`, `desire`, `persuade`, `world-knowledge`.

## `second_order.jsonl` — second-order ToM (P3.a2 admission threshold 0.70)

The 200 second-order false-belief items extracted from **ToMBench**, the English
side of its bilingual `data/False Belief Task.jsonl` (records whose ABILITY field
contains `"Belief: Second-order beliefs"` — 100 location + 100 content
second-order). These are the Perner & Wimmer (1985) second-order paradigm:
"where does A *think* B looks for the object?", whose answer is the object's
original location because A knows B never saw it moved (A's belief about B's
false belief). All records are tagged `ability: "second-order"`.

- **Source:** ToMBench — Chen et al., *ToMBench: Benchmarking Theory of Mind in
  Large Language Models*, ACL 2024. https://github.com/zhchen18/ToMBench
- **License:** MIT (redistribution permitted with attribution).
- **Upstream notice:** ToMBench is released for **evaluation only** — do not use
  it for model training, to avoid benchmark contamination. This corpus is used
  solely to measure an LLM's second-order ToM accuracy for the P3.a2 admission
  gate; it is never an input to Starling's own learning/extraction paths.
- **Regenerate:**
  ```bash
  python scripts/build_tombench_second_order_corpus.py \
    --tombench-file "/path/to/ToMBench/data/False Belief Task.jsonl" \
    --out tests/data/eval_tom_bench/second_order.jsonl
  ```

### Known English translation-drift items (4/200)

Four items carry a translation defect on ToMBench's **English** side: a Chinese
near-synonym (橱柜/柜子, 手提袋/手提包, 箱子) is rendered one way in the English
STORY and a different way in the English OPTIONS, so the English gold option
never appears in the English story and is unanswerable as labelled. The Chinese
side is internally consistent; deepseek-v4-pro reliably picks the
story-consistent option, not the broken gold — i.e. these are corpus defects,
not model or Starling failures.

| qid | broken EN gold | story-consistent answer |
|-----|----------------|-------------------------|
| tb-so-002 | Wardrobe | Cabinet |
| tb-so-035 | Tote bag | Handbag |
| tb-so-047 | Chest | Box |
| tb-so-053 | Tote bag | Handbag |

The records are kept verbatim (faithful extraction). Both eval tracks exclude
these four qids from the clean precision: `scripts/eval_tom2_starling.py` skips
them via `_KNOWN_DRIFT_QIDS`; for the track-1 LLM floor the raw 200-item score is
194/200 = 0.970 and the clean score is 194/196 = 0.990 (the four drift items are
exactly four of the six raw misses, confirmed individually).
