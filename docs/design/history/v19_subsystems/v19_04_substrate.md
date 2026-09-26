<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../../../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../../../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Substrate Adapter

## 功能定义

Substrate Adapter 是 Starling 的存储隔离层，把上层逻辑层（[Statement Bus](v19_05_bus.md)、[Hippocampus](v19_06_hippocampus.md)、[Neocortex](v19_07_neocortex.md) 等）与底层物理存储完全解耦。最小定义：将标准化接口调用路由到当前 profile 对应的物理底座，并在启动阶段通过 preflight 校验确认底座具备所需能力。

它不是 ORM，不做 SQL 方言转译，不是查询计划器，不持有业务缓存，不参与跨分区事务协调（事务补偿由 [Reconsolidation Engine](v19_11_reconsolidation.md) 负责）。

## 主要流程

### 1. 启动 preflight

```
系统启动
  │
  ├─ 读取当前 profile 配置
  │
  ├─ 实例化 ProfileCapability（所有 boolean flag）
  │
  ├─ 逐条执行 fail-closed 校验规则（见 §核心算法）
  │       │
  │       ├─ 全部通过 ──→ 状态 = READY
  │       │             写入 system.profile_checked outbox 事件
  │       │             更新 RuntimeHealth.capability_status
  │       │
  │       └─ 任一规则不满足 ──→ FAIL（启动中止，不降级）
  │
  └─ testing helper 双防线检查（仅 production profile）
          ├─ CI 静态扫描：import graph 中禁止出现 starling.testing.* 引用
          └─ 运行时 marker 检查：production entrypoint 不得加载 helper 包
```

### 2. 读写代理（Bus.write 路由）

```
Bus.write(statement)
  │
  ├─ SubstrateAdapter.route(op="kv_put", payload=statement)
  │       │
  │       ├─ profile=local-lite    ──→ SQLite KV put
  │       ├─ profile=local-graph   ──→ SQLite KV put + FalkorDB node upsert
  │       ├─ profile=cloud-graphiti──→ Postgres jsonb put + Neo4j node upsert
  │       ├─ profile=letta-bridge  ──→ Letta archival put（委派）
  │       └─ profile=cognee-bridge ──→ cognee DataPoint subclass put（委派）
  │
  ├─ 命令边界隔离层（storage_enforced 时强制注入 tenant_id/holder_scope）
  │
  └─ 返回写入确认；同步触发 outbox 写入（由 Bus 主事务包含）
```

### 3. Profile 选择决策树

```
部署者指定 profile（或 autodetect）
  │
  ├─ 单机开发，无图需求              ──→ local-lite
  ├─ 单机开发，需要图查询             ──→ local-graph
  ├─ 生产，需要 Postgres + 图 + 向量  ──→ cloud-graphiti
  ├─ 已有 Letta 部署，嵌入使用        ──→ letta-bridge
  └─ 已有 cognee 部署，复用 DataPoint ──→ cognee-bridge
          │
          └─ 各 profile 均通过 preflight 后方可激活
```

## 核心算法

### 1. ProfileCapability preflight fail-closed 校验清单

以下规则按顺序检查，任一失败则整体 FAIL，不允许跳过或降级：

```
规则 R1（production 强制能力）：
  IF profile_is_production:
    REQUIRE transactional_outbox=true
    REQUIRE consumer_checkpoint=true
    REQUIRE tenant_isolation="storage_enforced"
    REQUIRE container_cas=true

规则 R2（storage_enforced 依赖链）：
  IF tenant_isolation="storage_enforced":
    REQUIRE command_boundary_filter=true
    REQUIRE unknown_data_command_reject=true
    REQUIRE id_operation_scope_guard=true

规则 R3（crypto_erasure 依赖）：
  IF retention_mode=crypto_erasure:
    REQUIRE drawer_per_record_key=true
    REQUIRE crypto_erasure=true
    # 不得自动降级为逻辑隐藏

规则 R4（共享 Engram）：
  IF shared_engram_enabled:
    REQUIRE drawer_refcount=true OR refcount_split_strategy_provided

规则 R5（Projection Index）：
  IF projection_index_enabled:
    REQUIRE projection_rebuild_from_watermark=true
    REQUIRE vector_payload_delete=true
    # 否则标记 projection_disabled_reason，Retrieval 降级主表直查

规则 R6（app_filter 时写入 fail-closed）：
  IF tenant_isolation="app_filter":
    所有写入/检索必须显式携带 tenant_id/holder_scope，缺失则 reject

规则 R7（none 模式限制）：
  IF tenant_isolation="none":
    只允许单租户开发模式，禁止生产部署

规则 R8（tenant_id 落库）：
  所有 SQLite 查询模板必须包含 tenant_id 谓词
  # P0 可用 testing adapter 的 final query assertion 校验占位符存在
```

### 2. testing helper 双防线检测逻辑

```
防线 A -- CI 静态扫描（构建时）：
  对 production entrypoint 的 import graph 做 AST/依赖分析
  IF any import path matches "starling.testing.*":
    → 构建失败，阻断合并

防线 B -- 运行时 marker 检查（启动时）：
  IF profile_is_production AND testing_helper_marker_present_in_loaded_modules:
    → 启动中止（preflight FAIL）
```

### 3. cross_partition_transaction 各 profile 判定

| profile | cross_partition_transaction | 说明 |
|---|---|---|
| `local-lite` | `true` | SQLite 单库，事务自然原子 |
| `local-graph` | `true` | SQLite 主表 + 内置图引擎单事务 |
| `cloud-graphiti` | `false` | Postgres + Neo4j + Qdrant 跨库，无原子保证 |
| `letta-bridge` | 按宿主声明 | 取决于底层 Letta 能力 |
| `cognee-bridge` | 按宿主声明 | 取决于底层 cognee 能力 |

`false` 时，[Reconsolidation Engine](v19_11_reconsolidation.md) 的 severe path 必须走 saga 补偿路径：先写新版 Statement 与 supersedes 边，后 emit 事件，最后将旧版标为 ARCHIVED；任一步失败则 emit `reconsolidation.compensated`，旧版保持 CONSOLIDATED。

### 4. Capability matching 算法（Profile 选择时）

```python
def select_profile(required_capabilities: set[str], available_profiles: list[ProfileCapability]) -> ProfileCapability:
    candidates = []
    for p in available_profiles:
        cap_flags = {k for k, v in p.__dict__.items() if v is True}
        if required_capabilities.issubset(cap_flags):
            candidates.append(p)
    if not candidates:
        raise ProfileMatchError("no profile satisfies required capabilities")
    # 贪心：优先选满足条件中 capability 集合最小的 profile（最小权限原则）
    return min(candidates, key=lambda p: sum(1 for v in p.__dict__.values() if v is True))
```

### 5. 底座命令边界隔离

各底座类型的强制注入规则：

| 底座类型 | 注入位置 | 缺失时策略 |
|---|---|---|
| SQL/Postgres | query builder finalizer 追加 `(tenant_id, holder_scope)` 谓词；空 scope 的 delete/update 禁止 | reject |
| Mongo/DocStore | command/listener/finalizer 层对 find/insert/update/delete/aggregate 注入 tenant filter | 未识别数据命令 → reject |
| Elasticsearch/BM25 | search/count/delete_by_query 外层 bool.filter 注入 tenant；不可安全注入的操作（bulk delete、mget）禁用 | 未识别 endpoint → reject |
| Vector/Milvus/Qdrant | search/query/delete payload filter 强制含 tenant/holder；写入 payload force-set tenant | 空 delete expr 或无 payload delete 能力 → reject |

所有隔离器必须输出审计计数器：`tenant_scope_missing_count`、`unknown_data_command_count`、`id_scope_guard_count`，并汇入 `RetrievalReceipt.filters_applied` 或 `PipelineRun.counters`。

## 数据结构

### ProfileCapability

```python
class ProfileCapability(BaseModel):
    profile_name: str

    # 事务与消费者
    transactional_outbox: bool
    consumer_checkpoint: bool

    # 租户隔离
    tenant_isolation: Literal["none", "app_filter", "storage_enforced"]
    command_boundary_filter: bool      # 底座命令边界注入 tenant/holder filter
    unknown_data_command_reject: bool  # 未知数据面命令 fail-closed
    id_operation_scope_guard: bool     # get/delete by id 必须带 tenant/holder scope

    # Engram / 加密擦除
    drawer_per_record_key: bool        # per-record 加密 key，crypto_erasure 前置条件
    drawer_refcount: bool              # Engram 共享引用计数
    crypto_erasure: bool               # 支持加密擦除

    # 向量与投影
    vector_payload_delete: bool
    projection_rebuild_from_watermark: bool

    # 并发与分布式
    container_cas: bool
    distributed_lock_or_lease: bool

    # 可观测性
    stage_timing: bool

    # 跨分区事务（Hippocampus/Neocortex/Outbox 三分区原子提交）
    cross_partition_transaction: bool
```

### 5 个 Profile 配置

| profile | transactional_outbox | tenant_isolation | cross_partition_transaction | 底座组合 |
|---|---|---|---|---|
| `local-lite` | true | app_filter | true | SQLite + Chroma + 本地 fs |
| `local-graph` | true | app_filter | true | SQLite + FalkorDB + Chroma |
| `cloud-graphiti` | true | storage_enforced | false | Postgres + Graphiti/Neo4j + Qdrant |
| `letta-bridge` | 按宿主 | 按宿主 | 按宿主 | 委派 Letta |
| `cognee-bridge` | 按宿主 | 按宿主 | 按宿主 | cognee DataPoint 子类机制 |

### 索引清单

**P0 主表必要索引**（Statement 主表，非投影索引）：

```sql
-- 点查必须走该索引，禁止全表扫描
-- Validator 检查 derived_from、跨 tenant 派生、SUPERSEDES、evidence 传播均依赖此索引
CREATE INDEX idx_statement_id_tenant ON statements(id, tenant_id);
```

**P2 Projection Index（7 类，详见 §4.1）**：

| 索引名 | 主键/分片 | 面向查询 |
|---|---|---|
| `idx_holder_state_time` | `(holder, consolidation_state, valid_from, valid_to)` | FACT/HISTORY 基础过滤 |
| `idx_holder_subgraph` | `(holder, consolidation_state, modality, subject)` | holder 子图快速过滤 |
| `idx_entity_statement` | `(tenant_id, holder, entity_id, role, consolidation_state, statement_id)` | entity→Statement 桥 |
| `idx_salience_hot` | `(holder, salience_bucket, last_accessed)` | 高 salience 热路径 |
| `idx_commitment_due` | `(beneficiary, deadline, state)` | COMMITMENT_DUE |
| `idx_common_ground` | `(party_hash, statement_id)` | COMMON_GROUND |
| `idx_vector_payload` | vector id + payload(holder,state,modality,review_status) | semantic/hybrid recall |

Projection Index 由 outbox subscriber 异步物化，不阻塞 `Bus.write` 主事务。Freshness SLA：Online 模式 < 2s，Idle/Sleep 批处理 < 30s；超过 SLA 时 [Retrieval Planner](v19_13_retrieval.md) 降级主表直查或标记结果 stale。

`idx_holder_state_time` 是唯一允许 P1 提前引入的轻量投影。

**Projection 重建安全规则**：重建在 shadow table/index 完成后，必须用独立真相源校验 `expected_row_count`、`max_outbox_sequence`、抽样 `content_hash`/payload count。若 extraction count 低于主表 ground truth，或命中底座默认分页上限且无法交叉验证，必须拒绝 atomic swap 并 emit `projection.rebuild_failed(truncation_suspected)`。

## 相关概念

**Logical layer**：[Statement Bus](v19_05_bus.md)、[Hippocampus](v19_06_hippocampus.md)、[Neocortex](v19_07_neocortex.md) 等上层子系统所在的语义操作层，通过标准接口调用 Substrate Adapter，不感知底层物理存储类型。

**Partition layer**：逻辑上划分为 Hippocampus 分区（情节/工作记忆）、Neocortex 分区（语义知识）、Outbox 分区（事件队列）三个分区，物理映射由 profile 决定。

**Physical layer**：实际存储引擎，包括 SQLite、Postgres、Neo4j/FalkorDB/Graphiti、Chroma/Qdrant/Milvus、本地 fs/S3、Letta/cognee 宿主存储。

**ProfileCapability**：描述一个存储 profile 所具备的能力集合的数据结构，所有 flag 均为 boolean，在启动 preflight 阶段校验。见上方数据结构定义。

**storage_enforced tenant isolation**：`tenant_isolation="storage_enforced"` 级别的租户隔离，要求在数据库命令边界（而非业务层）强制注入 `tenant_id/holder_scope` 谓词，并同时满足 `command_boundary_filter=true`、`unknown_data_command_reject=true`、`id_operation_scope_guard=true`。低于此级别的 `app_filter` 不能用于生产 profile。

**Projection Index**：从 Statement 主表派生的物化投影索引，P2 起引入，由 outbox subscriber 异步维护，可由主表 + outbox sequence 完全重建，不作为权威事实源。与主表索引（如 `idx_statement_id_tenant`）的区别：主表索引服务于点查和一致性校验，Projection Index 服务于高频 Retrieval 的多维过滤。详见 [Retrieval Planner](v19_13_retrieval.md)。

**testing helper marker**：在 `starling.testing.*` 命名空间下的辅助包中设置的运行时标记，用于 preflight 双防线检测。production profile 启动时若检测到该 marker 则立即中止，防止测试辅助代码污染生产环境。

**fail-closed**：能力校验失败时的默认策略 -- 拒绝启动或拒绝操作，不自动降级。与 fail-open（降级继续运行）相对。Substrate Adapter 所有 preflight 规则均采用 fail-closed 策略。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
