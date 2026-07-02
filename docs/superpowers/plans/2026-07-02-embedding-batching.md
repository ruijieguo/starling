# Embedding Batching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the embed worker's N sequential per-statement embedding API calls per tick into one multi-input batched call, directly attacking the measured ~99%-of-tick embed cost.

**Architecture:** Add a `embed_batch` entry point to the `EmbeddingAdapter` interface (virtual, default impl loops `embed()` — backward-compatible). Restructure `EmbeddingWorker::tick_one_batch` to render all pending texts up-front and embed them in one `embed_batch` call, keeping the per-row neighbor-search / pattern-separation / SAVEPOINT-write body unchanged. Override `embed_batch` on `OpenAIEmbeddingAdapter` with a real multi-input `/embeddings` request, reordering the response by each element's `index` and chunking to a configurable per-call cap.

**Tech Stack:** C++20, SQLite, nlohmann/json, GoogleTest (ctest), pybind11 (unchanged — no binding edits).

## Global Constraints

_Every task's requirements implicitly include this section. Values are binding._

- **Architecture boundary:** batching is CORE → C++ only (`include/starling/embedding/` + `src/embedding/`); Python only forwards (existing `set_embedder` binding); no Python semantics. The "换绑定语言是否需要重写" test.
- **Real-time invariant:** embed batching acts ONLY on the background `tick_all` async worker; the worker processes "all currently-pending, up to `batch_size`" and NEVER holds/waits to fill a batch (1 pending → `embed_batch` of 1 → 1 call); NEVER batch the synchronous write path or the hot retrieval path (retrieval's lever is the deferred query cache).
- **Behavior-neutral:** with the same embedder, the batched worker writes identical `statement_vectors` rows (vectors/status/edges) and `vector.embedded` events to the old per-row path.
- **Batch failure = all-or-nothing per `embed_batch` call:** transient `EmbeddingError` → whole tick batch marked `failed` + retry bumped; permanent → `std::runtime_error` hard failure; malformed response → `std::runtime_error("malformed_response")` (never silent short-write).
- **Response reorder:** OpenAI/DashScope `/embeddings` batch `data[]` carries a per-element `index`; MUST place results by `index`, never trust array order (confirmed vs the OpenAI embeddings API reference).
- **No migration** (`statement_vectors` schema unchanged). `WorkerConfig.batch_size` stays 32. Transparent to tick governance (embed stays a Soft load-shed stage; only its `StageTimer` time shrinks).
- **Build canonical:** `python scripts/configure_build.py --build --python-editable` (C++ + binding rebuild). ctest + `pytest tests/python` must be green.
- **clang-tidy CI-only gate** on `src/|bindings/` `.cpp` + headers — write clean by construction: identifier length ≥ 3 in NEW code (no `r`/`i`/`v` — use `resp`/`pos`/`vec`), sized enums, `[[nodiscard]]` on pure value-returning helpers, NO empty/comment-only catch, avoid NEW const/ref data members. `tests/cpp` is NOT linted (test helpers may use short names / public members freely).
- **git:** explicit-path `git add` only (no `git add .` / `-A`); no `--no-verify` / `--amend`.

**Deferred / out of scope (do NOT build):** query-embed cache; vector scan c2.1/c3; changing `batch_size`; changing embed cadence / synchronous-write embedding; concurrent/parallel embedding.

**Verify-items (surfaced; confirm in review, do not block the batching-only default):**
- **V1 — DashScope compatible-mode max-inputs-per-call** for `text-embedding-v3`: set `max_batch_inputs` default at/below it (default 25 is conservative; OpenAI text-embedding-3 = 2048 inputs / 300k tokens per request, confirmed).
- **V2 — response `index` field** confirmed present on each `data[]` element (OpenAI API reference).
- **V3 — GIL:** `bind_13_memory_ops.cpp` already releases the GIL for `tick_all` (network calls); `embed_batch` runs inside that released region — confirm no new GIL interaction.

---

## File Structure

- `include/starling/embedding/embedding_adapter.hpp` — **modify**: add `embed_batch` to the base `EmbeddingAdapter` (virtual, default loops `embed()`). (Task 1)
- `tests/cpp/test_stub_embedding_adapter.cpp` — **modify**: stub parity + fail-propagation for `embed_batch`. (Task 1, already registered in `tests/cpp/CMakeLists.txt`)
- `src/embedding/embedding_worker.cpp` — **modify**: hoist the `embed()` calls out of the per-row loop into one `embed_batch` call + batch-failure handling. (Task 2)
- `tests/cpp/test_embedding_worker.cpp` — **modify**: `CountingAdapter` call-count anchor + batch-failure-all test; existing 4 tests are the behavior-neutral guard. (Task 2)
- `include/starling/embedding/openai_embedding_adapter.hpp` + `src/embedding/openai_embedding_adapter.cpp` — **modify**: override `embed_batch`; add pure static helpers `parse_embeddings_batch` + `chunk_ranges`; add `Config.max_batch_inputs` + `EMBEDDING_MAX_BATCH`. (Task 3)
- `tests/cpp/test_openai_embedding_adapter.cpp` — **modify**: offline unit tests for `parse_embeddings_batch` (reorder + malformed) and `chunk_ranges`; `from_env` reads `EMBEDDING_MAX_BATCH`. (Task 3)

No `CMakeLists.txt` change (all three test files already registered). No migration.

---

## Task 1: `EmbeddingAdapter::embed_batch` interface + Stub parity

**Files:**
- Modify: `include/starling/embedding/embedding_adapter.hpp`
- Test: `tests/cpp/test_stub_embedding_adapter.cpp`

**Interfaces:**
- Produces: `EmbeddingAdapter::embed_batch(const std::vector<std::string>& texts) -> std::vector<EmbeddingResult>` — virtual, default impl loops `embed()`; returns one result per input in INPUT ORDER. `StubEmbeddingAdapter` inherits the default (does not override).

- [ ] **Step 1: Write the failing tests**

Append to `tests/cpp/test_stub_embedding_adapter.cpp`:

```cpp
TEST(StubEmbeddingAdapter, EmbedBatchParityWithSingles) {
    StubEmbeddingAdapter a(8);
    std::vector<std::string> texts{"alpha", "beta", "gamma"};
    auto batch = a.embed_batch(texts);
    ASSERT_EQ(batch.size(), texts.size());
    for (size_t pos = 0; pos < texts.size(); ++pos) {
        auto single = a.embed(texts[pos]);
        EXPECT_EQ(batch[pos].vector, single.vector);
        EXPECT_EQ(batch[pos].dim, single.dim);
    }
}
TEST(StubEmbeddingAdapter, EmbedBatchPropagatesFailure) {
    StubEmbeddingAdapter a(8);
    a.fail_next("beta");  // one text in the batch throws
    std::vector<std::string> texts{"alpha", "beta", "gamma"};
    EXPECT_THROW(a.embed_batch(texts), EmbeddingError);
}
```

Also add `#include <string>` and `#include <vector>` to the test file's includes if not already present (the file currently includes only the adapter header + gtest).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R StubEmbeddingAdapter --output-on-failure`
Expected: FAIL to COMPILE — `embed_batch` is not a member of `EmbeddingAdapter`.

- [ ] **Step 3: Add `embed_batch` to the base interface**

In `include/starling/embedding/embedding_adapter.hpp`, inside `class EmbeddingAdapter`, add the method after the pure-virtual `embed`:

```cpp
class EmbeddingAdapter {
public:
    virtual ~EmbeddingAdapter() = default;
    virtual EmbeddingResult embed(std::string_view text) = 0;

    // Batch entry point. Default: loop embed() — keeps StubEmbeddingAdapter and
    // any future adapter working unchanged. OpenAIEmbeddingAdapter overrides it
    // with a single multi-input API call. Returns one result per input, in
    // INPUT ORDER. A transient failure throws EmbeddingError (whole batch); a
    // permanent failure throws std::runtime_error.
    virtual std::vector<EmbeddingResult>
    embed_batch(const std::vector<std::string>& texts) {
        std::vector<EmbeddingResult> out;
        out.reserve(texts.size());
        for (const auto& text : texts) {
            out.push_back(embed(std::string_view(text)));
        }
        return out;
    }

    virtual int dim() const = 0;
    virtual std::string model() const = 0;
};
```

(`<vector>`, `<string>`, `<string_view>` are already included at the top of the header.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R StubEmbeddingAdapter --output-on-failure`
Expected: PASS (4 tests: the 2 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add include/starling/embedding/embedding_adapter.hpp tests/cpp/test_stub_embedding_adapter.cpp
git commit -m "feat(embedding): add EmbeddingAdapter::embed_batch (default loops embed)"
```

---

## Task 2: Worker restructure — one batched embed per tick (behavior-neutral)

**Files:**
- Modify: `src/embedding/embedding_worker.cpp:154-267` (the section from `const int dim` through the per-row processing loop)
- Test: `tests/cpp/test_embedding_worker.cpp`

**Interfaces:**
- Consumes: `EmbeddingAdapter::embed_batch(const std::vector<std::string>&) -> std::vector<EmbeddingResult>` (Task 1).
- Produces: no new interface — same `EmbeddingStats tick_one_batch(Connection&, now_iso)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/cpp/test_embedding_worker.cpp`. First, a local counting adapter (test-only — not linted) that distinguishes a single `embed_batch` call from N `embed` calls; place it in the file's anonymous `namespace {` block, after `count(...)`:

```cpp
// Test spy: counts embed vs embed_batch calls to prove the worker batches.
// embed_batch delegates to an INNER stub (not this->embed), so embed_calls
// stays 0 when the worker uses the batch path.
class CountingAdapter : public starling::embedding::EmbeddingAdapter {
public:
    int embed_calls = 0;
    int embed_batch_calls = 0;
    starling::embedding::EmbeddingResult embed(std::string_view text) override {
        ++embed_calls;
        return inner_.embed(text);
    }
    std::vector<starling::embedding::EmbeddingResult>
    embed_batch(const std::vector<std::string>& texts) override {
        ++embed_batch_calls;
        std::vector<starling::embedding::EmbeddingResult> out;
        out.reserve(texts.size());
        for (const auto& text : texts) out.push_back(inner_.embed(text));
        return out;
    }
    int dim() const override { return inner_.dim(); }
    std::string model() const override { return "counting"; }
private:
    starling::embedding::StubEmbeddingAdapter inner_{8};
};
```

Then the two test cases (after the existing tests):

```cpp
TEST(EmbeddingWorker, CallsEmbedBatchOncePerTick) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "s1", "x0");
    seed_stmt(db, "s2", "x1");
    seed_stmt(db, "s3", "x2");

    CountingAdapter emb;
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st.embedded, 3);
    EXPECT_EQ(emb.embed_batch_calls, 1);  // ONE batched call...
    EXPECT_EQ(emb.embed_calls, 0);        // ...not three per-statement calls
}

TEST(EmbeddingWorker, BatchFailureMarksAllFailedThenReembeds) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "a", "x0");
    seed_stmt(db, "b", "x1");
    seed_stmt(db, "c", "x2");

    StubEmbeddingAdapter emb(8);
    emb.fail_next("bob knows x1");  // one text in the batch throws → whole batch fails
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st1 = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st1.failed, 3);      // ALL three, not just the one that threw
    EXPECT_EQ(st1.embedded, 0);
    EXPECT_EQ(count(db, "SELECT COUNT(*) FROM statement_vectors WHERE status='failed'"), 3);

    auto st2 = w.tick_one_batch(conn, "2026-05-30T10:01:00Z");  // fail consumed
    EXPECT_EQ(st2.embedded, 3);    // later tick re-embeds all
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R EmbeddingWorker --output-on-failure`
Expected: FAIL — `CallsEmbedBatchOncePerTick` sees `embed_batch_calls == 0` / `embed_calls == 3` (old per-row loop); `BatchFailureMarksAllFailedThenReembeds` sees `st1.failed == 1` and `st1.embedded == 2` (old per-row `continue` embeds the other two).

- [ ] **Step 3: Restructure the worker**

In `src/embedding/embedding_worker.cpp`, replace the block starting at `const int dim = embedder_.dim();` (currently line 154) down to the start of the per-row loop body. Specifically, replace lines 154-170 (the `dim`/`model` reads, the `for (const auto& row : pending)` loop header, and the inner per-row `embed()` try/catch) with:

```cpp
    const int dim = embedder_.dim();
    const std::string model = embedder_.model();

    // 2. Render every pending text and embed the whole batch in ONE call.
    //    Real-time invariant: this runs only in the background tick; we embed
    //    whatever is pending (up to batch_size) and NEVER wait to fill a batch.
    std::vector<std::string> texts;
    texts.reserve(pending.size());
    for (const auto& row : pending) {
        texts.push_back(render_text(row.subject_id, row.predicate, row.object_value));
    }

    std::vector<EmbeddingResult> results;
    try {
        results = embedder_.embed_batch(texts);
    } catch (const EmbeddingError&) {
        // Transient batch failure → mark EVERY row in this tick's batch failed
        // and bump retry for backoff (batch granularity of the per-row path).
        // A permanent std::runtime_error propagates as a hard failure, as before.
        for (const auto& row : pending) {
            mark_failed(conn, row, dim, model, now_iso);
            stats.failed++;
        }
        return stats;
    }

    // 3. Process each pending statement with its embedding.
    for (size_t pos = 0; pos < pending.size(); ++pos) {
        const auto& row = pending[pos];
        const EmbeddingResult& er = results[pos];
```

The rest of the loop body — from `// 3. Find neighbors via search_topk` (currently line 172) through `stats.embedded++;` / `stats.overlaps_created += ...` and the closing `}` of the loop (line 267) — stays VERBATIM. It already refers to `row` and `er`; `er` is now `results[pos]` instead of a local from `embed()`. Delete the old `// 2. Process each pending statement.` comment (line 157), the old `for (const auto& row : pending) {` header (line 158), and the old `const std::string text = render_text(...); EmbeddingResult er; try { er = embedder_.embed(text); } catch (const EmbeddingError&) { mark_failed(...); stats.failed++; continue; }` (lines 159-170) — they are superseded by the block above.

Renumber the trailing comments only if desired (`// 3.`→`// 4.` etc.); not required for correctness.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R EmbeddingWorker --output-on-failure`
Expected: PASS — all 6 tests. The existing 4 (`EmbedsPendingAndEmitsEvent`, `SecondTickNoOpAlreadyEmbedded`, `FailureMarksFailedWithRetry`, `PatternSeparationBuildsOverlapEdge`) pass **unchanged** — that is the behavior-neutral proof. (`FailureMarksFailedWithRetry` seeds ONE statement, so batch-of-1 failure still marks that one failed — assertion holds.)

- [ ] **Step 5: Commit**

```bash
git add src/embedding/embedding_worker.cpp tests/cpp/test_embedding_worker.cpp
git commit -m "feat(embedding): batch the worker's per-tick embed into one embed_batch call"
```

---

## Task 3: `OpenAIEmbeddingAdapter::embed_batch` — real batch call + reorder + chunking

**Files:**
- Modify: `include/starling/embedding/openai_embedding_adapter.hpp`
- Modify: `src/embedding/openai_embedding_adapter.cpp`
- Test: `tests/cpp/test_openai_embedding_adapter.cpp`

**Interfaces:**
- Consumes: `EmbeddingAdapter::embed_batch` (overrides it).
- Produces:
  - `OpenAIEmbeddingAdapter::embed_batch(const std::vector<std::string>&) -> std::vector<EmbeddingResult>` (override).
  - `static std::vector<std::vector<float>> OpenAIEmbeddingAdapter::parse_embeddings_batch(const std::string& body, int expected_count)` — pure; places each `data[]` element's vector by its `index`; throws `std::runtime_error("malformed_response")` on missing `data` / size≠`expected_count` / index out-of-range / duplicate index.
  - `static std::vector<std::pair<std::size_t,std::size_t>> OpenAIEmbeddingAdapter::chunk_ranges(std::size_t count, int max_inputs)` — pure; half-open `[start,end)` ranges of ≤`max_inputs` (clamped to ≥1); empty when `count==0`.
  - `Config.max_batch_inputs` (int, default 25); `from_env()` reads optional `EMBEDDING_MAX_BATCH`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/cpp/test_openai_embedding_adapter.cpp` (add `#include <string>`, `#include <vector>`, `#include <utility>`):

```cpp
TEST(OpenAIEmbeddingBatch, ParseReordersByIndex) {
    // data[] deliberately OUT of index order — must come back in input order.
    const std::string body = R"({"data":[
        {"index":1,"embedding":[1.0,1.0]},
        {"index":0,"embedding":[0.0,0.0]}
    ]})";
    auto vecs = OpenAIEmbeddingAdapter::parse_embeddings_batch(body, 2);
    ASSERT_EQ(vecs.size(), 2u);
    EXPECT_FLOAT_EQ(vecs[0][0], 0.0f);  // index 0 first
    EXPECT_FLOAT_EQ(vecs[1][0], 1.0f);  // index 1 second
}
TEST(OpenAIEmbeddingBatch, ParseMissingDataThrows) {
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch("{}", 1),
                 std::runtime_error);
}
TEST(OpenAIEmbeddingBatch, ParseCountMismatchThrows) {
    const std::string body = R"({"data":[{"index":0,"embedding":[0.0]}]})";
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch(body, 2),
                 std::runtime_error);
}
TEST(OpenAIEmbeddingBatch, ParseDuplicateIndexThrows) {
    const std::string body = R"({"data":[
        {"index":0,"embedding":[0.0]},
        {"index":0,"embedding":[1.0]}
    ]})";
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch(body, 2),
                 std::runtime_error);
}
TEST(OpenAIEmbeddingBatch, ChunkRangesSplitsToMax) {
    auto r = OpenAIEmbeddingAdapter::chunk_ranges(32, 25);
    ASSERT_EQ(r.size(), 2u);
    EXPECT_EQ(r[0], std::make_pair(std::size_t{0}, std::size_t{25}));
    EXPECT_EQ(r[1], std::make_pair(std::size_t{25}, std::size_t{32}));
}
TEST(OpenAIEmbeddingBatch, ChunkRangesSingleWhenUnderMax) {
    auto r = OpenAIEmbeddingAdapter::chunk_ranges(5, 25);
    ASSERT_EQ(r.size(), 1u);
    EXPECT_EQ(r[0], std::make_pair(std::size_t{0}, std::size_t{5}));
}
TEST(OpenAIEmbeddingBatch, ChunkRangesEmptyAndClamp) {
    EXPECT_TRUE(OpenAIEmbeddingAdapter::chunk_ranges(0, 25).empty());
    EXPECT_EQ(OpenAIEmbeddingAdapter::chunk_ranges(3, 0).size(), 3u);  // clamp step→1
}
TEST(OpenAIEmbeddingAdapter, FromEnvReadsMaxBatch) {
    setenv("OPENAI_API_KEY", "sk-test", 1);
    setenv("EMBEDDING_MAX_BATCH", "10", 1);
    auto c = OpenAIEmbeddingAdapter::Config::from_env();
    EXPECT_EQ(c.max_batch_inputs, 10);
    unsetenv("OPENAI_API_KEY"); unsetenv("EMBEDDING_MAX_BATCH");
}
TEST(OpenAIEmbeddingAdapter, FromEnvDefaultMaxBatch) {
    setenv("OPENAI_API_KEY", "sk-test", 1);
    unsetenv("EMBEDDING_MAX_BATCH");
    auto c = OpenAIEmbeddingAdapter::Config::from_env();
    EXPECT_EQ(c.max_batch_inputs, 25);
    unsetenv("OPENAI_API_KEY");
}
```

_(No live-network test: the raw HTTP round-trip is validated manually via `scripts/load_test_p3c.py --real-embed`, PR #41. The two risky pieces — index reorder and chunk math — are pure and fully covered offline here.)_

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R OpenAIEmbedding --output-on-failure`
Expected: FAIL to COMPILE — `parse_embeddings_batch` / `chunk_ranges` / `max_batch_inputs` don't exist yet.

- [ ] **Step 3a: Declare the interface in the header**

In `include/starling/embedding/openai_embedding_adapter.hpp`, add `#include <cstddef>` and `#include <vector>` at the top, then extend the class:

```cpp
class OpenAIEmbeddingAdapter : public EmbeddingAdapter {
public:
    struct Config {
        std::string base_url;
        std::string api_key;                       // 仅 env 读,绝不日志/绑定 Python
        std::string model = "text-embedding-3-small";
        int dim = 1536;
        int timeout_ms = 60000;
        int max_retries = 3;
        int max_batch_inputs = 25;                 // per-call input cap (DashScope-safe; see V1)
        static Config from_env();                  // throw std::runtime_error if api_key unset
    };
    explicit OpenAIEmbeddingAdapter(Config cfg) : cfg_(std::move(cfg)) {}
    EmbeddingResult embed(std::string_view text) override;
    std::vector<EmbeddingResult> embed_batch(const std::vector<std::string>& texts) override;
    int dim() const override { return cfg_.dim; }
    std::string model() const override { return cfg_.model; }

    // Pure, offline-testable helpers (static — reachable from ctest, no network).
    [[nodiscard]] static std::vector<std::vector<float>>
        parse_embeddings_batch(const std::string& body, int expected_count);
    [[nodiscard]] static std::vector<std::pair<std::size_t, std::size_t>>
        chunk_ranges(std::size_t count, int max_inputs);
private:
    Config cfg_;
};
```

- [ ] **Step 3b: Implement in the .cpp**

In `src/embedding/openai_embedding_adapter.cpp`, add includes: `#include <algorithm>`, `#include <charconv>`, `#include <cstddef>`, `#include <cstring>`, `#include <utility>`. Then:

1. In `Config::from_env()`, before `return c;`, read the optional cap (no exceptions, no empty catch):

```cpp
    const char* max_batch = std::getenv("EMBEDDING_MAX_BATCH");
    if (max_batch != nullptr && *max_batch != '\0') {
        int parsed = 0;
        const auto res = std::from_chars(max_batch, max_batch + std::strlen(max_batch), parsed);
        if (res.ec == std::errc() && parsed > 0) {
            c.max_batch_inputs = parsed;
        }
    }
```

2. Add the two pure helpers and the override (after `embed()`):

```cpp
std::vector<std::pair<std::size_t, std::size_t>>
OpenAIEmbeddingAdapter::chunk_ranges(std::size_t count, int max_inputs) {
    const std::size_t step = max_inputs > 0 ? static_cast<std::size_t>(max_inputs) : 1;
    std::vector<std::pair<std::size_t, std::size_t>> ranges;
    for (std::size_t start = 0; start < count; start += step) {
        ranges.emplace_back(start, std::min(count, start + step));
    }
    return ranges;
}

std::vector<std::vector<float>>
OpenAIEmbeddingAdapter::parse_embeddings_batch(const std::string& body, int expected_count) {
    std::vector<std::vector<float>> out(static_cast<std::size_t>(expected_count));
    std::vector<bool> seen(static_cast<std::size_t>(expected_count), false);
    try {
        const auto parsed = nlohmann::json::parse(body);
        const auto& data = parsed.at("data");
        if (static_cast<int>(data.size()) != expected_count) {
            throw std::runtime_error("count");
        }
        for (const auto& item : data) {
            const int index = item.at("index").get<int>();
            if (index < 0 || index >= expected_count || seen[static_cast<std::size_t>(index)]) {
                throw std::runtime_error("index");
            }
            const auto& emb = item.at("embedding");
            std::vector<float> vec;
            vec.reserve(emb.size());
            for (const auto& elem : emb) {
                vec.push_back(elem.get<float>());
            }
            out[static_cast<std::size_t>(index)] = std::move(vec);
            seen[static_cast<std::size_t>(index)] = true;
        }
    } catch (const std::exception&) {
        // Any structural problem (parse error, missing/short data, bad index) →
        // one normalized hard failure; never a silent short-write.
        throw std::runtime_error("malformed_response");
    }
    return out;
}

std::vector<EmbeddingResult>
OpenAIEmbeddingAdapter::embed_batch(const std::vector<std::string>& texts) {
    std::vector<EmbeddingResult> out;
    out.reserve(texts.size());
    for (const auto& [start, end] : chunk_ranges(texts.size(), cfg_.max_batch_inputs)) {
        nlohmann::json input = nlohmann::json::array();
        for (std::size_t pos = start; pos < end; ++pos) {
            input.push_back(texts[pos]);
        }
        nlohmann::json body = {{"model", cfg_.model}, {"input", std::move(input)}};
        const auto resp = net::http_post_json(
            cfg_.base_url + "/embeddings",
            {"Authorization: Bearer " + cfg_.api_key},
            body.dump(), cfg_.timeout_ms, cfg_.max_retries);
        if (!resp.ok) {
            if (resp.error.rfind("permanent_", 0) == 0) {
                throw std::runtime_error(resp.error);
            }
            throw EmbeddingError(resp.error);
        }
        auto vecs = parse_embeddings_batch(resp.body, static_cast<int>(end - start));
        for (auto& vec : vecs) {
            out.push_back(EmbeddingResult{std::move(vec), cfg_.dim, cfg_.model});
        }
    }
    return out;
}
```

Note the `catch (const std::exception&)` block contains a `throw` — it is NOT empty (satisfies `bugprone-empty-catch`). All new identifiers are ≥ 3 chars.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R OpenAIEmbedding --output-on-failure`
Expected: PASS — the 2 existing `from_env` tests + 9 new.

- [ ] **Step 5: Full build + suite + commit**

Run: `python scripts/configure_build.py --build --python-editable --test` (full ctest), then `pytest tests/python -q` (confirm no Python regression — no Python changed, but the binding rebuilt).
Expected: all green.

```bash
git add include/starling/embedding/openai_embedding_adapter.hpp src/embedding/openai_embedding_adapter.cpp tests/cpp/test_openai_embedding_adapter.cpp
git commit -m "feat(embedding): OpenAIEmbeddingAdapter::embed_batch (multi-input, index-reorder, chunked)"
```

---

## Self-Review (author checklist — completed)

- **Spec coverage:** §5.1 interface → Task 1; §5.2 worker restructure + §6 failure table → Task 2; §5.3 OpenAI batch + reorder + chunking + §5.4 config → Task 3; §7 testing → the tests in each task; §3 real-time invariant → Task 2 code comment + Global Constraints; §8 verify-items → Global Constraints. No spec section unmapped.
- **Placeholder scan:** every code step shows complete code + exact commands; no TBD/"handle errors"/"similar to".
- **Type consistency:** `embed_batch(const std::vector<std::string>&) -> std::vector<EmbeddingResult>` identical across Tasks 1/2/3; `parse_embeddings_batch(const std::string&, int) -> std::vector<std::vector<float>>` and `chunk_ranges(std::size_t, int) -> std::vector<std::pair<std::size_t,std::size_t>>` consistent between the header decl (3a), impl (3b), and tests (Step 1); `EmbeddingResult{vector,dim,model}` matches the existing struct.
