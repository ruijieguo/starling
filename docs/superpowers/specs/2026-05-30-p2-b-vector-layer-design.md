# P2.b 第二阶段：向量基础层（M0.9）— 设计规格

## 0. 背景与范围

roadmap 把 P2.b（类脑动力学，6 周）定为一个里程碑。Brainstorming 阶段发现 P2.b 内嵌一个**未建的 embedding/向量/图/logprobs 基础层**，代码库零向量基础设施，因此 P2.b 拆为两阶段：

- **M0.8（已交付，已合并 main，merge `4e70c82`）= 无向量脑动力学核心**：Replay Scheduler、Reconsolidation Engine、Neocortex Persona/CommonGround Container、CommonGround Grounding Acts writer、Projection Index 6 类 SQL 投影、SubscriberPump。全部基于现有 SQLite + statement 字段，零新基础设施。
- **M0.9（本 spec）= 向量基础层**：embedding adapter + 向量后端（adapter 抽象，本期 SQLite-BLOB 暴力实现，seekdb 后端延后）+ 异步 embedding worker + 模式分离（反相似偏移 + MAY_OVERLAP_WITH 软边）+ vector_recall + idx_vector_payload（第 7 类投影，让 §16.3-3/-6 repair guard 真正生效）。

### Brainstorming 锁定的 4 个决策

1. **范围**：仅向量基础层。模式补全（PPR/CA3 图游走）、EM-LLM/logprobs/EpisodicEvent 事件切分 → 后续里程碑。
2. **向量后端**：`VectorIndex` adapter 接口 + `SqliteBlobVectorIndex`（BLOB 存向量 + C++ 暴力 cosine）。seekdb 后端延后（seekdb 无 C++ SDK，向量操作走 MySQL-wire SQL，需独立 daemon + MySQL client 依赖 + 两引擎协调，超出本期；adapter seam 让其将来在 dist-store 落地，零 caller 改动）。
3. **embedding 时机**：异步，脱离写路径。写路径零改动；由独立的 `EmbeddingWorker` tick（runtime 驱动，类比 Replay idle tick）扫描排空待嵌入 statement。
4. **验收标准**：tests-only gate（CI 注入 `StubEmbeddingAdapter` 确定性向量，零 live API）+ §16.3-3/-6 向量投影 repair guard CRITICAL。真 embedding 的规模化 eval（§16.2-11）不在本期。

### §16.3 准入对照

- **§16.3-3 / -6**（Projection repair safety / guard）的**向量投影部分**由 M0.9 覆盖（M0.8 已覆盖 6 类 SQL 投影的 guard 机制，但因 6 类皆 1:1 而 dormant；idx_vector_payload 的 ground_truth 与物化行数天然不同，guard 在此真正触发）。
- 其余 -4/-7/-9 已由 M0.8 覆盖；-8/-10 属 P2.c / 评测体系。M0.9 不引入新的 §16.3 eval 约束。

---

## 1. 目标与非目标

### 目标

- 给 Statement 提供 embedding 向量与基于向量的语义召回能力，脱离写路径异步计算。
- 写入时模式分离（DG 风格反相似偏移），降低相似记忆的错误召回，并建 MAY_OVERLAP_WITH 软边留待后续巩固决策。
- 补齐 Projection Index 第 7 类（idx_vector_payload），让 §16.3-3/-6 repair guard 真正生效。
- 全程 adapter 抽象，seekdb / 其他后端将来可零 caller 改动接入。
- 无向量配置下系统 DEGRADED（非 UNREADY）运行：写 + basic_retrieve 完全正常。

### 非目标（本期明确不做）

- 模式补全（Personalized PageRank / CA3 图游走）、消费 MAY_OVERLAP_WITH 做合并决策。
- EM-LLM 事件切分 / LLM logprobs / EpisodicEvent。
- seekdb 后端 `VectorIndex` 具体实现（dist-store 里程碑）。
- 真 embedding 的规模化 eval（§16.2-11 的 50→5000 扩展验证）。
- 向量在 Replay 巩固期的消费（compress/abstract 用向量相似度）。

---

## 2. 架构总览

```
写路径（不变）
  Bus.write → commit statement + outbox 事件        ← 零网络调用,零改动

异步 embedding 管线（runtime 驱动,写路径之外）
  EmbeddingWorker.tick_one_batch(conn, embedder, index, now)
    ① 扫描:statements LEFT JOIN statement_vectors → 无向量行 = 待嵌入队列
    ② embedder.embed(text)        [唯一 HTTP 调用]   → EmbeddingAdapter
    ③ index.search_topk(e, k)     [找近邻]          → VectorIndex
    ④ PatternSeparator.separate(e, neighbors)        → index_vector + MAY_OVERLAP_WITH
    ⑤ 原子写 statement_vectors + statement_edges + emit vector.embedded

投影（SubscriberPump 内,既有 ProjectionMaintainer 扩展）
  consume statement.* + vector.embedded → upsert idx_vector_payload
  rebuild + repair guard（ground_truth=已嵌入向量数,rebuilt=物化行数 → truncation_suspected）

查询路径
  SemanticRetriever.vector_recall(query, k, scope)
    embedder.embed(query) → index.search_topk(可见性 scope 内) → StatementRow[] + receipt
```

**组件边界**（每个单一职责、接口清晰、可独立测试）：

| 组件 | 职责 | 依赖 | 层 |
|---|---|---|---|
| `EmbeddingAdapter`（抽象）+ `OpenAIEmbeddingAdapter` / `StubEmbeddingAdapter` | 文本 → float32[] 向量 | libcurl（具体实现）| C++ core |
| `VectorIndex`（抽象）+ `SqliteBlobVectorIndex` | insert / search_topk / delete | SQLite | C++ core |
| `PatternSeparator` | 反相似偏移 + 软边计算（纯计算）| 无 IO | C++ core |
| `EmbeddingWorker` | 扫描排空待嵌入 statement | 上述三者 | C++ core |
| `SemanticRetriever` | vector_recall（隐私先行）| EmbeddingAdapter + VectorIndex | C++ core |
| `idx_vector_payload`（ProjectionMaintainer 扩展）| 第 7 类投影 + repair guard | SQLite | C++ core |

---

## 3. 组件设计

### 3.1 EmbeddingAdapter

镜像现有 `include/starling/extractor/llm_adapter.hpp`（抽象基类）+ `src/extractor/openai_adapter.cpp`（libcurl + nlohmann/json + retry/backoff）的模式,但打 `/embeddings` 端点,返回 `std::vector<float>`。

```cpp
// include/starling/embedding/embedding_adapter.hpp
namespace starling::embedding {

struct EmbeddingResult {
    std::vector<float> vector;   // dim 维
    int dim = 0;
    std::string model;
};

class EmbeddingAdapter {
public:
    virtual ~EmbeddingAdapter() = default;
    // 抛 EmbeddingError 表示可重试失败（网络/5xx/429）。
    virtual EmbeddingResult embed(std::string_view text) = 0;
    virtual int dim() const = 0;
    virtual std::string model() const = 0;
};

}  // namespace starling::embedding
```

- `OpenAIEmbeddingAdapter`：env 读 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `EMBEDDING_MODEL`（默认 `text-embedding-3-small`，dim=1536），复用 openai_adapter 的 `is_retryable_curl_code` / `is_retryable_status` + 指数退避。API key 仅从 env 读,绝不日志/落库/绑定 Python。
- `StubEmbeddingAdapter`（测试专用,位于 `starling::testing` 或测试 TU）：`embed(text)` = 从 `text` 的 hash 种子生成确定性单位向量（可配置 dim,测试用小维度如 8 加速,默认 1536 对齐真实模型）。CI 全程用它,零 live API。
- Python binding：`EmbeddingAdapter` 仅暴露构造 + `dim()`/`model()`,`embed` 不必暴露给 Python(worker 在 C++ 内调)。真 API 的 smoke 测试 env-gated、非阻塞。

### 3.2 VectorIndex

```cpp
// include/starling/vector/vector_index.hpp
namespace starling::vector {

struct ScoredId { std::string stmt_id; double score; };  // score = cosine ∈ [-1,1]

struct SearchScope {            // 圈定可搜索集（隐私先行用）
    std::string tenant_id;
    std::optional<std::string> holder_id;
    std::optional<std::string> holder_perspective;
    bool visible_only = true;   // consolidation_state IN(consolidated,archived) + review_status 过滤
};

class VectorIndex {
public:
    virtual ~VectorIndex() = default;
    virtual void insert(persistence::Connection&, std::string_view stmt_id,
                        const std::vector<float>& vec) = 0;
    virtual std::vector<ScoredId> search_topk(persistence::Connection&,
                        const std::vector<float>& query, int k,
                        const SearchScope& scope) = 0;
    virtual void remove(persistence::Connection&, std::string_view stmt_id) = 0;
};

}  // namespace starling::vector
```

- `SqliteBlobVectorIndex`：后端即 `statement_vectors.index_vector`（BLOB）。`insert` = UPSERT;`search_topk` = 载入 scope 内 `status='embedded'` 的 `(stmt_id, index_vector)`,算 cosine,堆排 top-k;`remove` = 标记/删除索引行。M0.9 规模（~5k）暴力亚毫秒。
- `search_topk` 被两处复用：PatternSeparator（embed 时 scope=tenant）与 SemanticRetriever（query 时 scope=tenant+holder+perspective+visible）。
- seekdb 后端将来实现同接口：`search_topk` 映射为 `SELECT ... ORDER BY cosine_distance(vec, ?) APPROXIMATE LIMIT k`（scope 谓词下推为 `WHERE` 子句）。

### 3.3 PatternSeparator（纯计算,无 IO,独立单测）

```cpp
// include/starling/vector/pattern_separator.hpp
struct SeparationResult {
    std::vector<float> index_vector;                 // 归一化后的索引向量
    std::vector<std::pair<std::string,double>> overlaps;  // (neighbor_id, similarity) → MAY_OVERLAP_WITH
};

// θ_sep 默认 0.85,strength 默认 0.5（可配置）。
SeparationResult separate(const std::vector<float>& e,
                          const std::vector<vector::ScoredId>& neighbors,
                          const std::vector<std::vector<float>>& neighbor_vecs,
                          double theta_sep, double strength);
```

算法（见 §6）：max_sim > θ_sep 时 Gram-Schmidt 反相似偏移 + 建软边;否则直接归一化。

### 3.4 EmbeddingWorker

```cpp
// include/starling/embedding/embedding_worker.hpp
struct EmbeddingStats { int embedded=0; int failed=0; int overlaps_created=0; };

class EmbeddingWorker {
public:
    EmbeddingWorker(persistence::SqliteAdapter&, embedding::EmbeddingAdapter&,
                    vector::VectorIndex&);
    EmbeddingStats tick_one_batch(persistence::Connection&, std::string_view now_iso,
                                  int batch_size = 32);
    // 配置:θ_sep, strength, top_k_neighbors, max_retry, retry_backoff_minutes
private:
    // ...
};
```

- 扫描驱动（见 §5）；tick 之间不并发（同 Replay tick,runtime 串行驱动）。
- 由 Python runtime 主循环驱动（像 `ReplayScheduler.run_idle`）；DEGRADED 时不调度。

### 3.5 SemanticRetriever

在 `src/retrieval/` 新增,与 `BasicRetriever` 并列。

```cpp
struct SemanticRetrieverParams {
    std::string tenant_id, holder_id;
    std::optional<std::string> holder_perspective;
    std::string query_text;
    int k = 10;
    std::string trace_id, query_id;
};
struct SemanticResult {
    std::vector<StatementRow> rows;     // 按 cosine 降序
    RetrievalReceipt receipt;           // 含 semantic_score[], degraded 标记
};
SemanticResult vector_recall(persistence::Connection&, embedding::EmbeddingAdapter&,
                             vector::VectorIndex&, const SemanticRetrieverParams&);
```

隐私先行：可见性谓词下推进 `search_topk` 的 scope（见 §7）。Python binding：`semantic_retrieve()`。

---

## 4. Schema delta（migrations 0016–0018,当前最高 0015）

### 0016_statement_vectors.sql

```sql
-- M0.9 向量存储。独立表,保持 statements 精简,向量可选/异步。
CREATE TABLE statement_vectors (
    stmt_id        TEXT PRIMARY KEY,
    tenant_id      TEXT NOT NULL,
    index_vector   BLOB,               -- 模式分离后的索引向量（float32 紧凑）
    raw_embedding  BLOB,               -- 原始 embedding（留待将来重分离）
    dim            INTEGER NOT NULL,
    model          TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'embedded'
                   CHECK (status IN ('embedded','failed')),
    retry_count    INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    embedded_at    TEXT
);
CREATE INDEX idx_statement_vectors_scope
    ON statement_vectors(tenant_id, status);
```

> "缺 statement_vectors 行" = 待嵌入队列;`status='failed'` 行带 `retry_count` + `last_attempt_at` 做有界退避重试。无独立 checkpoint 表（扫描驱动）。

### 0017_may_overlap_edges.sql

```sql
-- MAY_OVERLAP_WITH 软边的元数据列（edge_kind 枚举值已存在,列没有）。
ALTER TABLE statement_edges ADD COLUMN similarity REAL;          -- cos(src,dst),写入时刻
ALTER TABLE statement_edges ADD COLUMN resolved   INTEGER NOT NULL DEFAULT 0;  -- 巩固期置 1
```

> 软边不阻止两端 Statement 独立存在;M0.9 只建边、不消费（消费属后续里程碑）。

### 0018_idx_vector_payload.sql

```sql
-- 第 7 类投影:已嵌入向量的 statement 元数据 scoping 索引。
CREATE TABLE proj_vector_payload (
    tenant_id          TEXT NOT NULL,
    holder_id          TEXT NOT NULL,
    consolidation_state TEXT NOT NULL,
    modality           TEXT,
    review_status      TEXT NOT NULL,
    stmt_id            TEXT NOT NULL,
    PRIMARY KEY (stmt_id)
);
CREATE INDEX idx_proj_vector_payload_scope
    ON proj_vector_payload(tenant_id, holder_id, consolidation_state);
-- projection_rebuild_state 复用既有表（M0.8 0015）,新增一行 projection_name='proj_vector_payload'。
```

---

## 5. 数据流（异步 embedding 管线）

`EmbeddingWorker.tick_one_batch`：

```
① 选取待嵌入:
   SELECT s.id, <文本字段> FROM statements s
     LEFT JOIN statement_vectors v ON v.stmt_id = s.id
   WHERE v.stmt_id IS NULL
     AND s.consolidation_state NOT IN ('archived','forgotten')
   LIMIT batch_size
   UNION  status='failed' 且 retry_count<max 且 last_attempt_at 超退避窗口的行
② 逐条:
   e = embedder.embed(render_text(s))            -- 唯一 HTTP,写路径之外
   失败 → UPSERT statement_vectors(status='failed', retry_count+1, last_attempt_at=now); continue
   neighbors = index.search_topk(e, top_k, scope=tenant)
   (index_vector, overlaps) = PatternSeparator.separate(e, neighbors, θ_sep, strength)
   SAVEPOINT 内原子:
     UPSERT statement_vectors(stmt_id, index_vector, raw_embedding, dim, model,
                              status='embedded', embedded_at=now)
     for (nid, sim) in overlaps:
        INSERT statement_edges(MAY_OVERLAP_WITH, src=s.id, dst=nid, similarity=sim, resolved=0)
     emit outbox vector.embedded(primary_id=s.id)
③ 返回 EmbeddingStats
```

- 写路径零改动;worker 由 runtime 驱动,DEGRADED 时不调度。
- `render_text(s)`：把 statement 渲染为可嵌入文本（subject_id + predicate + object_value 拼接,与 extractor 输入同风格;确切拼接模板在 plan 内定稿）。
- `vector.embedded` 事件驱动 idx_vector_payload 投影增量更新。

---

## 6. 模式分离算法（§7 of 06_hippocampus）

设新向量 $\mathbf{e}$，top-K 邻居 $\mathcal{N}$，阈值 $\theta_{\text{sep}}$，偏移强度 $s$。

```
max_sim = max_{n∈N} cos(e, n.index_vector)
若 max_sim > θ_sep:                                   -- DG 稀疏编码
    对每个邻居归一化 n̂_i = n_i / ‖n_i‖
    v_perp = e - Σ_i (e · n̂_i) · n̂_i                  -- Gram-Schmidt 去分量
    index_vector = normalize(e + s · v_perp)          -- 主动偏离聚类
    overlaps = [(n.id, cos(e, n.index_vector)) | n ∈ N]
否则:
    index_vector = normalize(e); overlaps = []
```

- 默认 `θ_sep = 0.85`、`strength = 0.5`、`top_k_neighbors = 5`（皆可配置）。
- `raw_embedding` 保留原始 $\mathbf{e}$（将来重分离/换模型用）。
- MAY_OVERLAP_WITH 软边 `resolved=0`,留待 Replay 巩固期决策。

---

## 7. vector_recall / 检索

```
q = embedder.embed(params.query_text)
scope = SearchScope{ tenant, holder, perspective, visible_only=true }
candidates = index.search_topk(q, k, scope)   -- 扫描只覆盖 scope 内可见且 status='embedded' 的向量
rows = 按 candidates 顺序 SELECT statements（再次校验可见性）
receipt = { semantic_score[], threshold, degraded=false }
```

**隐私先行**：可见性谓词（`tenant + holder + perspective + consolidation_state IN('consolidated','archived') + review_status NOT IN('rejected','pending_review')`）**下推进扫描范围**,保证 top-k 天然已可见,绝不"先 top-k 再过滤"导致越权或返回不足。暴力后端零成本;seekdb 后端对应原生混合查询 `WHERE <scope> ORDER BY cosine_distance APPROXIMATE LIMIT k`。

Python：`semantic_retrieve()` 与 `basic_retrieve()` 并列。

---

## 8. idx_vector_payload 投影 + repair guard

### 增量 tick

`ProjectionMaintainer.tick_one_batch` 扩展:消费 `statement.*` + `vector.embedded` 事件 → 从 `statements JOIN statement_vectors` upsert `proj_vector_payload`（仅 `status='embedded'`）;`archived`/`forgotten` → 删行。

### Repair guard（§16.3-3/-6 真正生效,闭合 M0.8 finding #6）

```
count_ground_truth = SELECT COUNT(*) FROM statement_vectors WHERE status='embedded' <+可见>
recompute_rebuilt  = SELECT COUNT(*) FROM proj_vector_payload        -- 物化表实际行数,非源表
若 rebuilt < ground_truth:
    → status='truncation_suspected' + emit projection.rebuild_failed + 保留 active 投影不替换
否则:
    → 原子 DELETE+INSERT 物化 + status='active'
```

> 与 M0.8 关键区别:idx_vector_payload 的两个计数**天然不同**（源 = 已嵌入向量数,物化 = 投影行数）,guard 在此真正可触发。M0.8 的 6 类 SQL 投影是真 1:1（`recompute_rebuilt` = `COUNT(*) statements` = ground_truth）,guard 正确地永不误触发,**保持原样不动**。

---

## 9. DEGRADED / capability / preflight

- `vector_index` capability：`ProfileCapability.vector_backend`（`include/starling/profile_capability.hpp`,既有字段）非空 = 向量可用。
- preflight（`src/preflight.cpp`）：`vector_index` 列为**非关键**项 → 未配置 → `RuntimeHealth.DEGRADED`（非 UNREADY,不 exit 78）。
- DEGRADED 行为：`EmbeddingWorker` tick 不调度（no-op）;`vector_recall` 返回 `degraded=true` 的空结果 + receipt 标记;`basic_retrieve` 与所有写完全正常。
- 运行时 provider 临时挂（API down）≠ capability 缺失:worker 标 `failed` 有界重试,系统仍 READY,该 statement 暂不进索引、不被 vector_recall 召回。

---

## 10. 错误处理

| 场景 | 处理 |
|---|---|
| embedding API 临时失败（网络/5xx/429）| adapter 内指数退避重试;仍失败 → `statement_vectors(status='failed', retry_count+1)`,下个 tick 超退避窗后重试,达 max_retry 后停 |
| embedding 维度与既有索引不一致（换模型）| worker 校验 `dim == index.dim()`,不一致则 skip + 告警（换模型属后续迁移,非本期）|
| vector.embedded 事件 idempotency 冲突 | tolerate（同 M0.8 emit_event 模式）|
| worker 与 retire（archived）竞争 | retire 走 SubscriberPump 同步路径置状态 + `VectorIndex.remove`;worker 扫描跳过 archived/forgotten |
| 投影 truncation | §8 repair guard:保留 active,emit projection.rebuild_failed |
| capability 缺失 | DEGRADED,非崩溃 |

---

## 11. 测试矩阵（tests-only gate,CI 注入 StubEmbeddingAdapter,零 live API）

| 层 | 用例 |
|---|---|
| C++ unit | PatternSeparator Gram-Schmidt 正交化数学 + θ_sep 边界 + normalize;SqliteBlobVectorIndex search_topk 排序正确性 + cosine 助手;EmbeddingAdapter stub 确定性 |
| C++ integration | EmbeddingWorker.tick(stub) → statement_vectors 落库 + MAY_OVERLAP_WITH 边 + 失败重试退避;**idx_vector_payload truncation guard（CRITICAL §16.3-3/-6）**;vector_recall 隐私 scoping（越权不返回）;retire → VectorIndex.remove |
| Python integration | semantic_retrieve binding smoke;端到端（seed → stub worker tick → ranked 召回）;DEGRADED 降级（无 vector_backend → degraded receipt,basic_retrieve 不受影响）|
| 回归 | M0.8 + P2.a 全绿:新子系统纯增量;SubscriberPump 仅 ProjectionMaintainer 扩展 consume vector.embedded;statements 表不动 |
| 可选非阻塞 | 真 OpenAI embedding 的 semantic smoke（env-gated,CI skip）|

### CRITICAL 测试（准入）

- **TC-VEC-REPAIR**：idx_vector_payload rebuild 物化行数 < 已嵌入向量数 → `truncation_suspected` + `projection.rebuild_failed` + active 投影不替换。对应 §16.3-3/-6 向量部分。

---

## 12. 实施偏序（供 writing-plans）

1. **Schema**：migrations 0016（statement_vectors）、0017（MAY_OVERLAP_WITH 列）、0018（proj_vector_payload）。
2. **纯计算 + 索引**：cosine 助手 → PatternSeparator（单测）→ VectorIndex 抽象 + SqliteBlobVectorIndex（单测）。
3. **Embedding adapter**：抽象 + StubEmbeddingAdapter（单测）+ OpenAIEmbeddingAdapter（复用 openai_adapter 模式）。
4. **EmbeddingWorker**：扫描 + tick（stub 集成测试,含失败重试）。
5. **投影**：ProjectionMaintainer 扩展 consume vector.embedded + idx_vector_payload upsert/rebuild + **TC-VEC-REPAIR CRITICAL**。
6. **检索**：SemanticRetriever.vector_recall（隐私 scoping 测试）。
7. **DEGRADED/preflight**：vector_index capability 非关键项接入 + 降级测试。
8. **pybind**：暴露 EmbeddingWorker / SemanticRetriever / VectorIndex / EmbeddingAdapter（构造）给 Python；`cmake --install` + `pip install -e . --no-deps --force-reinstall`。
9. **回归**：M0.8 + P2.a 全绿。
10. **里程碑关闭**：roadmap flip（P2.b M0.9 部分 ✅）+ final review + merge。

---

## 13. 元数据

- **里程碑代号**：M0.9（P2.b 第二阶段,向量基础层）
- **依赖**：M0.8 close（main `4e70c82` / `f6ac18b`）
- **后继**：模式补全（PPR）+ EM-LLM/logprobs → 然后 P2.c（Prospective/Affect）
- **roadmap 行**：P2.b（M0.9 待写部分）
- **分支**：worktree-m0-9-vector-layer，--no-ff 合并 main
- **输入设计文档**：06_hippocampus.md（模式分离/补全）、10_replay.md、system_design.md §16.3、M0.8 spec 标注的向量延后项、v23_research_seekdb.md（seekdb 集成分析）
- **2026-05-30 v1**：初版 spec。基于 brainstorming 阶段 4 个决策（范围/后端/embedding 时机/验收标准）+ Section A-C 逐段确认。
