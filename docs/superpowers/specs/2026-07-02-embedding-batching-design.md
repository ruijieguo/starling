<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->


> **R6.2 最终状态合同（2026-09-26）**：`EmbeddingStats.failed` 与 `embed_seeded.failed` 是累计失败尝试数；空 tick 不代表所有向量健康。新增 C++ `EmbeddingWorker::health` 与只读 `frozen_embedding_health`，按活动声明、租户关联、模型、维度及有限非零 raw/index 向量检查最终状态；binding 只透传。已恢复的失败保留计数且可继续，耗尽或损坏仍阻断。历史封存协议保留，新恢复入口重新原生核验。
<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Embedding Batching — Design Spec
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **2026-09-11 契约补充**：C++ OpenAIEmbeddingAdapter 暴露只读原子 request_count、embed_calls、batch_calls；request_count 统计实际 HTTP 尝试（含失败和重试），空批次不产生请求，未执行的分块不计数。语言 binding 只暴露属性；共同的 model()/dim() 接口直接调用原生虚函数，读取配置元数据不发起网络请求。 当前扩展见 [已确认语义证据设计](2026-09-11-source-grounded-claim-contract-design.md)。下文保留本版本原有适用范围。

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
