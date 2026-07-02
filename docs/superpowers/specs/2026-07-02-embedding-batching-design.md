# Embedding Batching — Design Spec

**Slice:** P3.c embedding batching (the measured next optimization).
**Date:** 2026-07-02
**Status:** Approved (brainstorm) → writing-plans next.

## 1. Motivation (measured)

Real-embedder baseline (`scripts/load_test_p3c.py --real-embed`, DashScope
`text-embedding-v3` 1024-dim, memory `p3c-bottleneck-is-embedding-not-scan`):

- The **embed stage is ~99% of the maintenance tick** (n=2000: 345s of a 348s
  tick), **sequential + un-batched at ~172 ms/statement** → ~29 min to embed
  10,000 statements. This is THE bottleneck.
- The `O(n)` cosine scan is negligible (~30 ms at n=10,000). The earlier
  "optimize the scan" signal was a pure 8-dim-stub artifact.

`EmbeddingWorker::tick_one_batch` already collects up to `batch_size` (32)
pending statements per tick into a snapshot vector, then loops calling
`embedder_.embed(text)` **one at a time** (`src/embedding/embedding_worker.cpp:158-164`).
The OpenAI/DashScope `/embeddings` API accepts `input` as an **array** of
strings and returns one embedding per input — so N sequential round-trips
collapse to one. That is this slice.

## 2. Scope

**In scope:** batch the embed worker's per-statement API calls.

**Deferred (honest boundary — NOT built here):**
- **Query-embed cache** (retrieval side). `vector_recall` re-embeds the query
  synchronously (`semantic_retriever.cpp:26`) — the flat ~132 ms retrieval
  floor. A cache helps only *repeated* query texts; the benchmark uses unique
  queries (zero benchmark win), and the real-world repeat rate is unmeasured.
  Gated on a future measured repeat rate. (Decision this slice: batching-only.)
- **Vector scan / ANN (c2.1 dimension-CAS, c3).** Negligible per the baseline.

## 3. Real-time invariant (load-bearing)

Batching improves throughput but can wreck latency if it sits on a real-time
path and *waits to accumulate a batch* ("凑批" delay). This design keeps
batching off every real-time path, verified against the code:

- `remember()` → `memoryops::remember` writes the statement **without a
  vector** (synchronous, fast). It never calls the embed worker.
- Embedding happens **only** in the background maintenance tick
  `Memory.tick()` → `memoryops::tick_all` → embed stage
  (`memory_ops.cpp:214`). This is the host's periodic/idle cadence.
- The synchronous post-write pump (`subscriber_pump.cpp:40-73`) runs
  backfill/belief/reconsolidation/projection/common-ground — it does **not**
  touch the embed worker. A write never blocks on embedding.
- Retrieval (`vector_recall`) re-embeds the query synchronously on the hot
  path. Queries arrive singly; batching them would *introduce* the凑批 trap.
  Retrieval is therefore **not** batched — its lever is the deferred cache.

**INVARIANT (implementation + review must hold this):** embed batching acts
only on the background `tick_all` async worker. The worker processes
"all currently-pending rows, up to `batch_size`" — it **never holds or waits
to fill a batch**. One pending row ⇒ `embed_batch({one})` ⇒ one API call,
identical latency to today. No buffer-and-flush, no fill-threshold, no timer.

Consequence: batching *reduces* tick wall-time (one tick's embed stage goes
from up to 32 × ~172 ms ≈ 5.5 s sequential to ~1 round-trip ~172–300 ms),
which is strictly better for the load-shed-aware Soft-stage governance.

**Non-claim:** batching does NOT change write→searchable freshness (a new
statement is vector-searchable only after the next background embed tick,
batch or not). "Embed sooner" is a separate cadence question, out of scope.

## 4. Architecture boundary

Batching is CORE semantics → C++ (`include/starling/embedding/` +
`src/embedding/`). Python only forwards (the existing `set_embedder` binding;
no Python semantics). Passes the "换绑定语言是否需要重写" test.

## 5. Components

### 5.1 Interface — `EmbeddingAdapter::embed_batch` (virtual, default impl)

`include/starling/embedding/embedding_adapter.hpp` — add to the base class:

```cpp
// Batch entry point. Default: loop embed() — keeps StubEmbeddingAdapter and
// any future adapter working unchanged. OpenAIEmbeddingAdapter overrides it
// with a single multi-input API call. Returns results in INPUT ORDER, one per
// input text. On a transient batch failure, throws EmbeddingError (whole
// batch); on a permanent failure, throws std::runtime_error.
virtual std::vector<EmbeddingResult>
embed_batch(const std::vector<std::string>& texts) {
    std::vector<EmbeddingResult> out;
    out.reserve(texts.size());
    for (const auto& t : texts) out.push_back(embed(std::string_view(t)));
    return out;
}
```

Virtual-with-default (not pure virtual) → backward-compatible, minimal blast
radius. `StubEmbeddingAdapter` inherits the loop (local, instant); its
`fail_next` hook still fires per-text inside the loop.

### 5.2 Worker restructure — `EmbeddingWorker::tick_one_batch`

`src/embedding/embedding_worker.cpp`. The ONLY change is hoisting the `embed()`
calls out of the per-row loop. Everything else (scan, neighbor search, pattern
separation, SAVEPOINT write, outbox event) is unchanged.

New flow after the existing scan populates `pending`:

1. Render all texts up-front: `std::vector<std::string> texts` where
   `texts[i] = render_text(pending[i].subject_id, .predicate, .object_value)`.
2. One batched embed call, wrapped for transient failure:
   ```cpp
   std::vector<EmbeddingResult> results;
   try {
       results = embedder_.embed_batch(texts);
   } catch (const EmbeddingError&) {
       // Transient: mark EVERY row in this tick's batch failed + bump retry
       // (batch granularity of the existing per-row mark_failed path).
       for (const auto& row : pending) { mark_failed(conn, row, dim, model, now_iso); stats.failed++; }
       return stats;
   }
   ```
   (A permanent `std::runtime_error` propagates as today — hard failure.)
3. Loop `pending[i]` paired with `results[i]`, running the unchanged per-row
   body: `search_topk` neighbors → `separate` → `SAVEPOINT emb` UPSERT
   `statement_vectors` + `MAY_OVERLAP_WITH` edges + `vector.embedded` event.

Behavior-neutral guarantee: with the same embedder, the rows written are
identical to the old per-row path (same vectors, same neighbors, same edges).

### 5.3 OpenAI adapter batch call — `OpenAIEmbeddingAdapter::embed_batch`

`include/starling/embedding/openai_embedding_adapter.hpp` +
`src/embedding/openai_embedding_adapter.cpp`. Override `embed_batch`.

**Request:** `body["input"]` = JSON array of the texts (vs the single string in
`embed()`). Same endpoint, headers, `http_post_json`.

**Response reorder (correctness trap):** the API response `data[]` elements
each carry an `index` field ("The index of the embedding in the list of
embeddings", confirmed against the OpenAI embeddings API reference). Order is
NOT guaranteed to match input order — results MUST be placed by `index`.

**Extract a pure, offline-testable helper** (must be reachable from ctest —
declare it as a `static` method on `OpenAIEmbeddingAdapter` or in a small
detail header, NOT hidden in an anonymous namespace in the `.cpp`):
```cpp
// Parse an /embeddings batch response body into `expected_count` vectors,
// placed by each element's "index". Throws std::runtime_error("malformed_response")
// on any structural problem (missing data, count mismatch, index out of range,
// duplicate index). No network — unit-testable with crafted JSON.
std::vector<std::vector<float>>
parse_embeddings_batch(const std::string& body, int expected_count);
```
`embed_batch` = build request → `http_post_json` (reuse the existing ok/error
branch: `permanent_` prefix → `std::runtime_error`, else `EmbeddingError`) →
`parse_embeddings_batch` → wrap each vector into `EmbeddingResult{vec, dim, model}`.

**Chunking:** chunk `texts` into sub-batches of at most
`cfg_.max_batch_inputs` (new Config field), issue one request per chunk, and
concatenate results in order. If any chunk fails, the exception propagates
(the worker then marks the whole tick batch failed — §5.2). Rationale:
DashScope's OpenAI-compatible endpoint caps inputs-per-call below OpenAI's 2048
(exact number provider-specific → **VERIFY-ITEM V1**); a conservative default
keeps the MVP provider-safe.

### 5.4 Config

`OpenAIEmbeddingAdapter::Config` — add `int max_batch_inputs = 25;`
(conservative: safe for DashScope compatible-mode, far under OpenAI's 2048).
`Config::from_env()` reads optional `EMBEDDING_MAX_BATCH` (parse to int if set).

`WorkerConfig.batch_size` stays 32 (tuning it is an independent follow-up).

No migration — `statement_vectors` schema is unchanged. Transparent to tick
governance / load-shedding (embed stays a Soft stage; only its StageTimer time
shrinks).

## 6. Error handling

| Case | Behavior |
|------|----------|
| Transient batch failure (`EmbeddingError`, e.g. 429/5xx/network) | Whole tick batch marked `failed`, `retry_count` bumped; recovered by re-embed on a later tick. |
| Permanent failure (`permanent_` HTTP prefix → `std::runtime_error`) | Propagates as a hard failure, as today. |
| Malformed/short/misindexed batch response | `parse_embeddings_batch` throws `std::runtime_error("malformed_response")` → hard failure (not silently short-writing). |
| Stub / default `embed_batch` | Loops `embed()`; per-text `fail_next` still throws `EmbeddingError` (propagates out of `embed_batch`). |

Successful-chunk waste on a mid-batch chunk failure (the already-embedded
chunks are re-embedded next tick) is accepted — background cadence,
`batch_size`=32, correctness over micro-efficiency.

## 7. Testing

- **Parity (stub):** `embed_batch({a,b,c})` equals `{embed(a),embed(b),embed(c)}`
  element-for-element (pins the default impl contract).
- **Worker golden (behavior-neutral):** seed N statements, run
  `tick_one_batch` with a `StubEmbeddingAdapter`, assert the written
  `statement_vectors` rows (vectors, status, edges) are identical to the
  pre-batching per-row path. This is the proof the restructure changed nothing
  observable but call count.
- **`parse_embeddings_batch` reorder unit test:** feed a crafted response whose
  `data[]` is deliberately OUT of index order; assert vectors come back in
  input order. Plus malformed cases (missing `data`, count mismatch, duplicate
  index) → `malformed_response`.
- **Worker batch failure:** extend the stub with a batch-fail hook; assert a
  batch failure marks **all** rows in the tick failed + bumps `retry_count`,
  and a later successful tick re-embeds them.
- **Chunking:** with `max_batch_inputs` < pending count, assert the stub path
  still returns all N in order (chunk boundaries don't reorder/drop).

Build canonical: `python scripts/configure_build.py --build --python-editable`
(C++ + binding rebuild; no migration). clang-tidy CI-only gate on
`src/|bindings/` `.cpp` + headers — write clean by construction
(memory `clang-tidy-ci-only-gate-gotchas`: identifier-length ≥ 3, sized enums,
`nodiscard`, no empty catch, avoid new const/ref data members).

## 8. Verify-items (confirm during plan / eng-review)

- **V1 — DashScope batch input cap.** Confirm the OpenAI-compatible-mode
  max-inputs-per-call for `text-embedding-v3`; set the `max_batch_inputs`
  default at or below it. (OpenAI text-embedding-3 = 2048 inputs / 300k tokens
  per request, confirmed.)
- **V2 — response `index` field.** Confirmed present on each `data[]` element
  (OpenAI embeddings API reference). Ensure the batch response parser is robust
  to unordered `data[]`.
- **V3 — GIL / binding.** `bind_13_memory_ops.cpp` already releases the GIL for
  `tick_all` (network calls) — confirm no new GIL interaction; `embed_batch` is
  called from within that released region.

## 9. Out of scope / non-goals

Query-embed cache; vector-scan/ANN; changing `batch_size`; changing embed
cadence or making writes embed synchronously; concurrent/parallel embedding.
