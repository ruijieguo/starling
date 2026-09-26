<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Embedding Batching Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the embed worker's N sequential per-statement embedding API calls per tick into one (or a few, chunked) multi-input batched call, directly attacking the measured ~99%-of-tick embed cost.

**Architecture:** Add a `embed_batch` entry point to the `EmbeddingAdapter` interface (virtual, default impl loops `embed()` — backward-compatible). Restructure `EmbeddingWorker::tick_one_batch` to render all pending texts up-front and embed them in one `embed_batch` call, with a per-row fallback on failure, keeping the per-row neighbor-search / pattern-separation / SAVEPOINT-write body unchanged. Override `embed_batch` on `OpenAIEmbeddingAdapter` with a real multi-input `/embeddings` request, reordering the response by each element's `index` and chunking to a configurable per-call cap.

**Tech Stack:** C++20, SQLite, nlohmann/json, GoogleTest (ctest), pybind11 (unchanged — no binding edits).

## Global Constraints

_Every task's requirements implicitly include this section. Values are binding._

- **Architecture boundary:** batching is CORE → C++ only (`include/starling/embedding/` + `src/embedding/`); Python only forwards (existing `set_embedder` binding); no Python semantics. The "换绑定语言是否需要重写" test.
- **Real-time invariant:** embed batching acts ONLY on the background `tick_all` async worker; the worker processes "all currently-pending, up to `batch_size`" and NEVER holds/waits to fill a batch (1 pending → `embed_batch` of 1 → 1 call); NEVER batch the synchronous write path or the hot retrieval path (retrieval's lever is the deferred query cache).
- **Behavior-neutral (success path):** with the same embedder, the batched worker writes identical `statement_vectors` rows (vectors/status/edges) and `vector.embedded` events to the old per-row path.
- **Two-tier batch-failure semantics (eng-review D1):**
  - *Transient* batch failure (`EmbeddingError` — 429/5xx/network, endpoint-wide): mark every row in the tick batch `failed` + bump `retry_count`, then return. A per-row retry storm would just re-fail every row.
  - *Permanent/structural* batch failure (a `permanent_<code>` 4xx from one bad input, or a result-count mismatch): fall back to per-row `embed()` so healthy rows still embed and only the offending row(s) are marked `failed`. A poison row no longer wedges its healthy batch-mates. (This bounds a permanent single-row error to `max_retry` attempts then a drop, instead of the legacy abort-the-tick-forever — a deliberate, documented improvement.)
  - Malformed response → `std::runtime_error("malformed_response")` (never a silent short-write).
- **Fail-closed (eng-review B):** the worker only consumes a batched result when `results.size() == pending.size()`; a mismatch routes to the per-row fallback (never index a short vector → no UB).
- **Response reorder:** OpenAI/DashScope `/embeddings` batch `data[]` carries a per-element `index`; MUST place results by `index`, never trust array order (confirmed vs the OpenAI embeddings API reference).
- **No migration** (`statement_vectors` schema unchanged). `WorkerConfig.batch_size` stays 32. Transparent to tick governance (embed stays a Soft load-shed stage; only its `StageTimer` time shrinks).
- **Build canonical:** `python scripts/configure_build.py --build --python-editable` (C++ + binding rebuild). ctest + `pytest tests/python` must be green.
- **clang-tidy CI-only gate** on `src/|bindings/` `.cpp` + headers — write clean by construction: identifier length ≥ 3 in NEW code (no `r`/`i`/`v` — use `resp`/`pos`/`vec`), sized enums, `[[nodiscard]]` on pure value-returning helpers, NO empty/comment-only catch (every catch here has a body), avoid NEW const/ref data members. `tests/cpp` is NOT linted (test helpers may use short names / public members freely).
- **git:** explicit-path `git add` only (no `git add .` / `-A`); no `--no-verify` / `--amend`.

**Deferred / out of scope (do NOT build):** query-embed cache; vector scan c2.1/c3; changing `batch_size`; changing embed cadence / synchronous-write embedding; concurrent/parallel embedding; token/body-size-aware chunking (our rendered texts are short — tens of tokens — so 25 inputs is far under the 300k-token/request limit; the per-row fallback also catches an oversize 400); surfacing `failed` in `tick_all` observability (touches the fragile `TickStats(**dict)` Python boundary — see TODO).

**Verify-items (surfaced; confirm in review, do not block the batching-only default):**
- **V1 — DashScope compatible-mode max-inputs-per-call** for `text-embedding-v3`: set `max_batch_inputs` default at/below it (default 25 is conservative; OpenAI text-embedding-3 = 2048 inputs / 300k tokens per request, confirmed). If 25 is still too high, the per-row fallback (D1) degrades gracefully rather than hard-failing.
- **V2 — response `index` field** confirmed present on each `data[]` element (OpenAI API reference).
- **V3 — GIL:** `bind_13_memory_ops.cpp` already releases the GIL for `tick_all` (network calls); `embed_batch` runs inside that released region — confirm no new GIL interaction.

**Eng-review revisions (2026-07-02, this review):** D1 two-tier failure + per-row fallback (was all-or-nothing); B fail-closed size guard; C pure `build_embeddings_request` + shared `throw_for_http_error` helpers for offline request coverage + DRY; F `parse_embeddings_batch` validates embedding length; empty-pending early return; "one call/tick" wording corrected (2 chunks at defaults).

---

## File Structure

- `include/starling/embedding/embedding_adapter.hpp` — **modify**: add `embed_batch` to the base `EmbeddingAdapter` (virtual, default loops `embed()`). (Task 1)
- `tests/cpp/test_stub_embedding_adapter.cpp` — **modify**: stub parity + fail-propagation for `embed_batch`. (Task 1, already registered)
- `src/embedding/embedding_worker.cpp` — **modify**: hoist the `embed()` calls out of the per-row loop into one `embed_batch` call + two-tier failure + fail-closed + empty guard. (Task 2)
- `tests/cpp/test_embedding_worker.cpp` — **modify**: `ScriptedAdapter` driving fast-path / transient / permanent-isolation / count-mismatch; existing 4 tests are the behavior-neutral guard. (Task 2)
- `include/starling/embedding/openai_embedding_adapter.hpp` + `src/embedding/openai_embedding_adapter.cpp` — **modify**: override `embed_batch`; add pure static helpers `build_embeddings_request` + `parse_embeddings_batch` (dim-checked) + `chunk_ranges`; a shared `throw_for_http_error` (.cpp anon-namespace); `Config.max_batch_inputs` + `EMBEDDING_MAX_BATCH`. (Task 3)
- `tests/cpp/test_openai_embedding_adapter.cpp` — **modify**: offline unit tests for the pure helpers; `from_env` reads `EMBEDDING_MAX_BATCH`. (Task 3)

No `CMakeLists.txt` change (all three test files already registered). No migration.

---

## Task 1: `EmbeddingAdapter::embed_batch` interface + Stub parity

**Files:**
- Modify: `include/starling/embedding/embedding_adapter.hpp`
- Test: `tests/cpp/test_stub_embedding_adapter.cpp`

**Interfaces:**
- Produces: `EmbeddingAdapter::embed_batch(const std::vector<std::string>& texts) -> std::vector<EmbeddingResult>` — virtual, default impl loops `embed()`; returns one result per input in INPUT ORDER. `StubEmbeddingAdapter` inherits the default (does not override).

- [ ] **Step 1: Write the failing tests**

Append to `tests/cpp/test_stub_embedding_adapter.cpp` (add `#include <string>` and `#include <vector>`):

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

## Task 2: Worker restructure — batch fast-path + per-row fallback

**Files:**
- Modify: `src/embedding/embedding_worker.cpp` (the section from `const int dim` through the per-row processing loop, currently lines 154-267)
- Test: `tests/cpp/test_embedding_worker.cpp`

**Interfaces:**
- Consumes: `EmbeddingAdapter::embed_batch(const std::vector<std::string>&) -> std::vector<EmbeddingResult>` (Task 1).
- Produces: no new interface — same `EmbeddingStats tick_one_batch(Connection&, now_iso)`.

**Design:** the batch call is a fast path. On a *transient* batch failure (`EmbeddingError`, endpoint-wide) mark the whole batch failed + retry and return. On a *permanent/structural* batch failure (a `permanent_<code>` 4xx, or a result-count mismatch) fall back to per-row `embed()` so healthy rows still embed and only the offending row is marked failed. Empty pending returns early. The per-row write body is unchanged.

- [ ] **Step 1: Write the failing tests**

Append a scripted test adapter to the anonymous `namespace {` block of `tests/cpp/test_embedding_worker.cpp` (after `count(...)`). Test-only code — not clang-tidy'd, so short names / public members are fine:

```cpp
// Scripted spy: drives each batch-failure branch of the worker, and counts
// embed vs embed_batch calls. embed_batch delegates to an INNER stub (not
// this->embed), so embed_calls counts ONLY the worker's per-row fallback.
class ScriptedAdapter : public starling::embedding::EmbeddingAdapter {
public:
    enum class BatchMode { Succeed, ThrowTransient, ThrowPermanent, WrongCount };
    BatchMode batch_mode = BatchMode::Succeed;
    std::string poison;  // a render_text that fails in the per-row fallback
    int embed_calls = 0;
    int embed_batch_calls = 0;

    starling::embedding::EmbeddingResult embed(std::string_view text) override {
        ++embed_calls;
        if (!poison.empty() && std::string(text) == poison) {
            throw starling::embedding::EmbeddingError("poison");
        }
        return inner_.embed(text);
    }
    std::vector<starling::embedding::EmbeddingResult>
    embed_batch(const std::vector<std::string>& texts) override {
        ++embed_batch_calls;
        if (batch_mode == BatchMode::ThrowTransient) {
            throw starling::embedding::EmbeddingError("batch transient");
        }
        if (batch_mode == BatchMode::ThrowPermanent) {
            throw std::runtime_error("permanent_batch");
        }
        std::vector<starling::embedding::EmbeddingResult> out;
        out.reserve(texts.size());
        for (const auto& text : texts) out.push_back(inner_.embed(text));
        if (batch_mode == BatchMode::WrongCount && !out.empty()) {
            out.pop_back();  // return N-1 → force the fail-closed per-row fallback
        }
        return out;
    }
    int dim() const override { return inner_.dim(); }
    std::string model() const override { return "scripted"; }
private:
    starling::embedding::StubEmbeddingAdapter inner_{8};
};
```

Then the test cases (after the existing tests):

```cpp
TEST(EmbeddingWorker, FastPathCallsEmbedBatchOnce) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "s1", "x0");
    seed_stmt(db, "s2", "x1");
    seed_stmt(db, "s3", "x2");

    ScriptedAdapter emb;  // Succeed
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st.embedded, 3);
    EXPECT_EQ(emb.embed_batch_calls, 1);  // ONE batched call...
    EXPECT_EQ(emb.embed_calls, 0);        // ...no per-row fallback
}

TEST(EmbeddingWorker, TransientBatchFailureMarksAllThenRecovers) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "a", "x0");
    seed_stmt(db, "b", "x1");
    seed_stmt(db, "c", "x2");

    ScriptedAdapter emb;
    emb.batch_mode = ScriptedAdapter::BatchMode::ThrowTransient;
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st1 = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st1.failed, 3);          // whole batch marked failed...
    EXPECT_EQ(st1.embedded, 0);
    EXPECT_EQ(emb.embed_calls, 0);     // ...WITHOUT a per-row retry storm
    EXPECT_EQ(count(db, "SELECT COUNT(*) FROM statement_vectors WHERE status='failed'"), 3);

    emb.batch_mode = ScriptedAdapter::BatchMode::Succeed;  // transient outage over
    auto st2 = w.tick_one_batch(conn, "2026-05-30T10:01:00Z");
    EXPECT_EQ(st2.embedded, 3);        // all re-embed
}

TEST(EmbeddingWorker, PermanentBatchFailureIsolatesPoisonRow) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "a", "x0");
    seed_stmt(db, "b", "x1");
    seed_stmt(db, "c", "x2");

    ScriptedAdapter emb;
    emb.batch_mode = ScriptedAdapter::BatchMode::ThrowPermanent;  // batch 400s
    emb.poison = "bob knows x1";  // only row b fails in the per-row fallback
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st.embedded, 2);  // a and c embed via the per-row fallback...
    EXPECT_EQ(st.failed, 1);    // ...only the poison row b is marked failed
    EXPECT_EQ(count(db, "SELECT COUNT(*) FROM statement_vectors WHERE stmt_id='b' AND status='failed'"), 1);
    EXPECT_EQ(count(db, "SELECT COUNT(*) FROM statement_vectors WHERE status='embedded'"), 2);
}

TEST(EmbeddingWorker, WrongResultCountFallsBackToPerRow) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "a", "x0");
    seed_stmt(db, "b", "x1");

    ScriptedAdapter emb;
    emb.batch_mode = ScriptedAdapter::BatchMode::WrongCount;  // returns N-1
    SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);

    auto st = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st.embedded, 2);        // fail-closed → per-row fallback embeds all
    EXPECT_GE(emb.embed_calls, 2);    // fallback used embed()
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R EmbeddingWorker --output-on-failure`
Expected: FAIL — `FastPathCallsEmbedBatchOnce` sees `embed_batch_calls == 0` (old per-row loop); the failure-branch tests can't compile/pass against the old body.

- [ ] **Step 3: Restructure the worker**

In `src/embedding/embedding_worker.cpp`, replace the block from `const int dim = embedder_.dim();` (currently line 154) through the per-row `embed()` try/catch and the loop header (currently line 170) with the following. Insert the empty-pending guard immediately before it:

```cpp
    if (pending.empty()) {
        return stats;  // nothing pending this tick — no batch call
    }

    const int dim = embedder_.dim();
    const std::string model = embedder_.model();

    // 2. Render every pending text up-front.
    std::vector<std::string> texts;
    texts.reserve(pending.size());
    for (const auto& row : pending) {
        texts.push_back(render_text(row.subject_id, row.predicate, row.object_value));
    }

    // 3. Embed. Fast path = ONE batched call. Failure handling is two-tier:
    //    - transient (EmbeddingError: 429/5xx/network) is endpoint-wide → mark
    //      the whole batch failed + bump retry and return (a per-row retry would
    //      just re-fail every row);
    //    - permanent/structural (a permanent_<code> 4xx, or a result-count
    //      mismatch) → fall back to per-row embed() so healthy rows still embed
    //      and only the offending row is marked failed.
    //    Real-time invariant: runs only in the background tick; embeds whatever
    //    is pending (up to batch_size), never waiting to fill a batch.
    std::vector<std::optional<EmbeddingResult>> embeds(pending.size());
    bool batched = false;
    try {
        std::vector<EmbeddingResult> results = embedder_.embed_batch(texts);
        if (results.size() == pending.size()) {  // fail-closed: never index a short result
            for (size_t pos = 0; pos < results.size(); ++pos) {
                embeds[pos] = std::move(results[pos]);
            }
            batched = true;
        }
        // else: adapter returned the wrong count → fall through to per-row.
    } catch (const EmbeddingError&) {
        // Transient, endpoint-wide → mark all failed + retry; no per-row storm.
        for (const auto& row : pending) {
            mark_failed(conn, row, dim, model, now_iso);
            stats.failed++;
        }
        return stats;
    } catch (const std::exception&) {
        // Permanent/structural batch failure → isolate via per-row below.
        batched = false;
    }
    if (!batched) {
        for (size_t pos = 0; pos < pending.size(); ++pos) {
            try {
                embeds[pos] = embedder_.embed(std::string_view(texts[pos]));
            } catch (const std::exception&) {
                // This row can't embed (transient or permanent) → mark failed,
                // bump retry; a poison row no longer wedges its batch-mates.
                mark_failed(conn, pending[pos], dim, model, now_iso);
                stats.failed++;
            }
        }
    }

    // 4. Persist every row that embedded successfully.
    for (size_t pos = 0; pos < pending.size(); ++pos) {
        if (!embeds[pos].has_value()) {
            continue;  // failed row — already marked above
        }
        const auto& row = pending[pos];
        const EmbeddingResult& er = *embeds[pos];
```

Everything from `// 3. Find neighbors via search_topk` (currently line 172) through `stats.embedded++;` / `stats.overlaps_created += ...` and the loop's closing `}` (line 267) stays VERBATIM — it already refers to `row` and `er`. Delete the old `// 2. Process each pending statement.` comment, the old `for (const auto& row : pending) {` header, and the old `const std::string text = ...; EmbeddingResult er; try { er = embedder_.embed(text); } catch (const EmbeddingError&) { mark_failed(...); stats.failed++; continue; }` block (lines 157-170) — superseded above. `<optional>` and `<string_view>` are already included (lines 27, 30).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R EmbeddingWorker --output-on-failure`
Expected: PASS — all 8 tests. The existing 4 (`EmbedsPendingAndEmitsEvent`, `SecondTickNoOpAlreadyEmbedded`, `FailureMarksFailedWithRetry`, `PatternSeparationBuildsOverlapEdge`) pass **unchanged** — the behavior-neutral proof. (`FailureMarksFailedWithRetry` seeds ONE statement with `fail_next` on its text: `embed_batch`'s default loop throws `EmbeddingError` → the transient branch marks it failed — assertion still holds.)

- [ ] **Step 5: Commit**

```bash
git add src/embedding/embedding_worker.cpp tests/cpp/test_embedding_worker.cpp
git commit -m "feat(embedding): batch the worker's per-tick embed with per-row fallback"
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
  - `static std::string OpenAIEmbeddingAdapter::build_embeddings_request(const std::string& model, const std::vector<std::string>& texts)` — pure; returns the dumped JSON body `{"model":…,"input":[…]}`.
  - `static std::vector<std::vector<float>> OpenAIEmbeddingAdapter::parse_embeddings_batch(const std::string& body, int expected_count, int expected_dim)` — pure; places each `data[]` element's vector by its `index`; throws `std::runtime_error("malformed_response")` on missing `data` / size≠`expected_count` / index out-of-range / duplicate index / (when `expected_dim > 0`) any embedding whose length ≠ `expected_dim`.
  - `static std::vector<std::pair<std::size_t,std::size_t>> OpenAIEmbeddingAdapter::chunk_ranges(std::size_t count, int max_inputs)` — pure; half-open `[start,end)` ranges of ≤`max_inputs` (clamped to ≥1); empty when `count==0`.
  - `Config.max_batch_inputs` (int, default 25); `from_env()` reads optional `EMBEDDING_MAX_BATCH`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/cpp/test_openai_embedding_adapter.cpp` (add `#include <nlohmann/json.hpp>`, `#include <string>`, `#include <vector>`, `#include <utility>`):

```cpp
TEST(OpenAIEmbeddingBatch, BuildRequestEmitsInputArray) {
    const std::string body =
        OpenAIEmbeddingAdapter::build_embeddings_request("text-embedding-3-small",
                                                         {"alpha", "beta"});
    auto j = nlohmann::json::parse(body);
    EXPECT_EQ(j.at("model"), "text-embedding-3-small");
    ASSERT_TRUE(j.at("input").is_array());
    ASSERT_EQ(j.at("input").size(), 2u);
    EXPECT_EQ(j.at("input")[0], "alpha");
    EXPECT_EQ(j.at("input")[1], "beta");
}
TEST(OpenAIEmbeddingBatch, ParseReordersByIndex) {
    const std::string body = R"({"data":[
        {"index":1,"embedding":[1.0,1.0]},
        {"index":0,"embedding":[0.0,0.0]}
    ]})";
    auto vecs = OpenAIEmbeddingAdapter::parse_embeddings_batch(body, 2, /*dim=*/0);
    ASSERT_EQ(vecs.size(), 2u);
    EXPECT_FLOAT_EQ(vecs[0][0], 0.0f);  // index 0 first
    EXPECT_FLOAT_EQ(vecs[1][0], 1.0f);  // index 1 second
}
TEST(OpenAIEmbeddingBatch, ParseMissingDataThrows) {
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch("{}", 1, 0),
                 std::runtime_error);
}
TEST(OpenAIEmbeddingBatch, ParseCountMismatchThrows) {
    const std::string body = R"({"data":[{"index":0,"embedding":[0.0]}]})";
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch(body, 2, 0),
                 std::runtime_error);
}
TEST(OpenAIEmbeddingBatch, ParseDuplicateIndexThrows) {
    const std::string body = R"({"data":[
        {"index":0,"embedding":[0.0]},
        {"index":0,"embedding":[1.0]}
    ]})";
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch(body, 2, 0),
                 std::runtime_error);
}
TEST(OpenAIEmbeddingBatch, ParseWrongDimThrows) {
    // expected_dim=2 but the embedding has length 1 → malformed.
    const std::string body = R"({"data":[{"index":0,"embedding":[0.0]}]})";
    EXPECT_THROW(OpenAIEmbeddingAdapter::parse_embeddings_batch(body, 1, /*dim=*/2),
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

_(No live-network test: the raw HTTP round-trip stays network-bound, validated manually via `scripts/load_test_p3c.py --real-embed`, PR #41. Request construction, index-reorder, dim-check, and chunk math are now all pure and fully covered offline.)_

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R OpenAIEmbedding --output-on-failure`
Expected: FAIL to COMPILE — the helpers / `max_batch_inputs` don't exist yet.

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
    [[nodiscard]] static std::string
        build_embeddings_request(const std::string& model,
                                 const std::vector<std::string>& texts);
    [[nodiscard]] static std::vector<std::vector<float>>
        parse_embeddings_batch(const std::string& body, int expected_count, int expected_dim);
    [[nodiscard]] static std::vector<std::pair<std::size_t, std::size_t>>
        chunk_ranges(std::size_t count, int max_inputs);
private:
    Config cfg_;
};
```

- [ ] **Step 3b: Implement in the .cpp**

In `src/embedding/openai_embedding_adapter.cpp`, add includes: `#include <algorithm>`, `#include <charconv>`, `#include <cstddef>`, `#include <cstring>`, `#include <utility>`. Then:

1. Add a shared error-mapping helper in the file's anonymous namespace (DRY — used by both `embed` and `embed_batch`):

```cpp
namespace {
// Map a failed HttpResult to the historical type split: permanent_<code> → hard
// std::runtime_error; everything else (transient_after_retry / transport_error)
// → retryable EmbeddingError. No-op when resp.ok.
void throw_for_http_error(const net::HttpResult& resp) {
    if (resp.ok) {
        return;
    }
    if (resp.error.rfind("permanent_", 0) == 0) {
        throw std::runtime_error(resp.error);
    }
    throw EmbeddingError(resp.error);
}
}  // namespace
```

2. In `Config::from_env()`, before `return c;`, read the optional cap (no exceptions, no empty catch):

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

3. Refactor the existing `embed()` error branch to use the helper (replace its `if (!r.ok) { ... throw ... }` block with `throw_for_http_error(r);` — the code after it that parses `data.at(0)` is unchanged).

4. Add the pure helpers and the override (after `embed()`):

```cpp
std::string
OpenAIEmbeddingAdapter::build_embeddings_request(const std::string& model,
                                                 const std::vector<std::string>& texts) {
    nlohmann::json input = nlohmann::json::array();
    for (const auto& text : texts) {
        input.push_back(text);
    }
    nlohmann::json body = {{"model", model}, {"input", std::move(input)}};
    return body.dump();
}

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
OpenAIEmbeddingAdapter::parse_embeddings_batch(const std::string& body,
                                               int expected_count, int expected_dim) {
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
            if (expected_dim > 0 && static_cast<int>(emb.size()) != expected_dim) {
                throw std::runtime_error("dim");
            }
            std::vector<float> vec;
            vec.reserve(emb.size());
            for (const auto& elem : emb) {
                vec.push_back(elem.get<float>());
            }
            out[static_cast<std::size_t>(index)] = std::move(vec);
            seen[static_cast<std::size_t>(index)] = true;
        }
    } catch (const std::exception&) {
        // Any structural problem (parse error, missing/short data, bad index,
        // wrong dim) → one normalized hard failure; never a silent short-write.
        throw std::runtime_error("malformed_response");
    }
    return out;
}

std::vector<EmbeddingResult>
OpenAIEmbeddingAdapter::embed_batch(const std::vector<std::string>& texts) {
    std::vector<EmbeddingResult> out;
    out.reserve(texts.size());
    for (const auto& [start, end] : chunk_ranges(texts.size(), cfg_.max_batch_inputs)) {
        std::vector<std::string> chunk(texts.begin() + static_cast<std::ptrdiff_t>(start),
                                       texts.begin() + static_cast<std::ptrdiff_t>(end));
        const auto resp = net::http_post_json(
            cfg_.base_url + "/embeddings",
            {"Authorization: Bearer " + cfg_.api_key},
            build_embeddings_request(cfg_.model, chunk), cfg_.timeout_ms, cfg_.max_retries);
        throw_for_http_error(resp);
        auto vecs = parse_embeddings_batch(resp.body, static_cast<int>(end - start), cfg_.dim);
        for (auto& vec : vecs) {
            out.push_back(EmbeddingResult{std::move(vec), cfg_.dim, cfg_.model});
        }
    }
    return out;
}
```

All new identifiers are ≥ 3 chars; every catch has a body (no `bugprone-empty-catch`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R OpenAIEmbedding --output-on-failure`
Expected: PASS — the 2 existing `from_env` tests + 11 new.

- [ ] **Step 5: Full build + suite + commit**

Run: `python scripts/configure_build.py --build --python-editable --test` (full ctest), then `pytest tests/python -q`.
Expected: all green.

```bash
git add include/starling/embedding/openai_embedding_adapter.hpp src/embedding/openai_embedding_adapter.cpp tests/cpp/test_openai_embedding_adapter.cpp
git commit -m "feat(embedding): OpenAIEmbeddingAdapter::embed_batch (multi-input, reorder, dim-checked, chunked)"
```

---

## Self-Review (author checklist — completed)

- **Spec coverage:** §5.1 interface → Task 1; §5.2 worker restructure + §6 failure table → Task 2 (two-tier, eng-review D1); §5.3 OpenAI batch + reorder + chunking + §5.4 config → Task 3; §7 testing → the tests in each task; §3 real-time invariant → Task 2 code comment + Global Constraints; §8 verify-items → Global Constraints. No spec section unmapped.
- **Placeholder scan:** every code step shows complete code + exact commands; no TBD / "handle errors" / "similar to".
- **Type consistency:** `embed_batch(const std::vector<std::string>&) -> std::vector<EmbeddingResult>` identical across Tasks 1/2/3; `build_embeddings_request(const std::string&, const std::vector<std::string>&) -> std::string`, `parse_embeddings_batch(const std::string&, int, int) -> std::vector<std::vector<float>>`, and `chunk_ranges(std::size_t, int) -> std::vector<std::pair<std::size_t,std::size_t>>` consistent between the header decl (3a), impl (3b), and tests (Step 1); `EmbeddingResult{vector,dim,model}` matches the existing struct.

## NOT in scope

- **Query-embed cache** (retrieval re-embed) — deferred; helps only repeated query texts, unmeasured repeat rate, zero benchmark win.
- **Vector-scan / ANN (c2.1 dimension-CAS, c3)** — negligible per the baseline (~30 ms at n=10k).
- **`batch_size` tuning** — stays 32; independent perf knob.
- **Embed cadence / synchronous-write embedding** — separate freshness question; batching does not change write→searchable latency.
- **Concurrent/parallel embedding** — throughput lever for the 100-QPS target; separate slice.
- **Token/body-size-aware chunking** — our rendered texts are short; the per-row fallback catches an oversize 400.
- **`failed` in `tick_all` observability** — real (a mass batch failure looks like "nothing embedded"), but touches the `TickStats(**dict)` / broadcast-gate Python boundary that has broken consumers before; deferred to a TODO.

## What already exists (reused, not rebuilt)

- `EmbeddingWorker::tick_one_batch` already collects `pending` per tick — Task 2 only hoists the `embed()` calls out of its loop; the scan, neighbor search, pattern separation, SAVEPOINT write, and `vector.embedded` emit are untouched.
- `net::http_post_json` (single retry/backoff impl) — `embed_batch` reuses it; `throw_for_http_error` DRYs the ok/error mapping already used by `embed()`.
- `StubEmbeddingAdapter` — inherits the default `embed_batch` loop; its `fail_next` hook drives the failure tests unchanged.
- `WorkerConfig` / `statement_vectors` schema — unchanged (no migration).

## Failure modes (new codepaths)

| Codepath | Failure | Test | Error handling | User-visible |
|---|---|---|---|---|
| `embed_batch` transient (429/5xx) | endpoint down | `TransientBatchFailureMarksAllThenRecovers` | mark all failed + retry | statements re-embed next tick |
| `embed_batch` permanent (one bad input 400) | poison row | `PermanentBatchFailureIsolatesPoisonRow` | per-row fallback isolates it | healthy rows embed; poison retried→dropped |
| adapter returns wrong count | adapter bug | `WrongResultCountFallsBackToPerRow` | fail-closed → per-row | no UB; healthy rows embed |
| malformed response | provider garbles | `ParseMissingData/CountMismatch/WrongDim` | `malformed_response` hard fail | tick aborts (loud), not silent short-write |

No failure mode is both silent AND unhandled — no critical gap.

## Parallelization

Sequential: Task 2 consumes Task 1's interface; Task 3 overrides it. All three touch `include/starling/embedding` + `src/embedding`. No parallel lanes.

## Implementation Tasks
Synthesized from this review's findings. Each derives from a specific finding above.

- [ ] **T1 (P1, human: ~1h / CC: ~15min)** — embed worker — two-tier batch-failure + per-row fallback + fail-closed size guard + empty guard
  - Surfaced by: Architecture / Code Quality (D1, B) + Codex outside voice (poison-row, count-mismatch UB)
  - Files: `src/embedding/embedding_worker.cpp`, `tests/cpp/test_embedding_worker.cpp`
  - Verify: `ctest --test-dir build -R EmbeddingWorker`
- [ ] **T2 (P2, human: ~45min / CC: ~10min)** — OpenAI adapter — pure `build_embeddings_request` + shared `throw_for_http_error` + `parse_embeddings_batch` dim-check
  - Surfaced by: Test review (C, offline request coverage + DRY) + Code Quality (F, dim validation)
  - Files: `include/starling/embedding/openai_embedding_adapter.hpp`, `src/embedding/openai_embedding_adapter.cpp`, `tests/cpp/test_openai_embedding_adapter.cpp`
  - Verify: `ctest --test-dir build -R OpenAIEmbedding`
- [ ] **T3 (P3, follow-up TODO)** — tick observability — surface `failed` alongside `embedded` in `tick_all`
  - Surfaced by: Codex outside voice — mass batch failures look like "nothing embedded"
  - Files: `src/memory/memory_ops.cpp` + the `TickStats` Python boundary (fragile — see `tickoutcome-dict-field-breaks-python-consumers`)
  - Verify: deferred; not this slice

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 12 raised; 4 folded (D1/B/C/F), rest deferred with rationale |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 2 decisions + 2 folded fixes, all resolved |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **CODEX:** the outside voice independently confirmed the failure-semantics regression (poison-row / collateral retry retirement) and the `results[pos]` count-mismatch UB. Its findings drove D1 (per-row fallback), B (fail-closed size guard), C (offline request-construction coverage + DRY), and F (embedding-dim validation). Remaining items (token-size chunking, `failed` observability) deferred with rationale in NOT-in-scope / T3.
- **CROSS-MODEL:** no tension — Codex and the Claude review agreed on every point; the failure-semantics finding is double-confirmed.
- **VERDICT:** ENG CLEARED — ready to implement (subagent-driven-development).

NO UNRESOLVED DECISIONS
