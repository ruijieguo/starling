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

# P2.b 第二阶段：向量基础层（M0.9）— 设计规格
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **2026-09-11 契约补充**：检索候选在 C++ 中校验来源证据后才暴露链接。 当前扩展见 [已确认语义证据设计](2026-09-11-source-grounded-claim-contract-design.md)。下文保留本版本原有适用范围。


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
