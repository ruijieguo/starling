# Substrate Adapter

## 功能定义

把上层逻辑层（Statement / Container / Engram）与底层物理存储完全隔离。提供三档 profile（local-store / dist-store / cloud-store），每档支持文本、向量、图三类索引与检索。它不做：业务逻辑、查询计划器、缓存、事务补偿（补偿由 Reconsolidation Engine 负责）。

## 输入

- 上层 Bus.write / append_evidence / rebuild_container / query 调用
- ProfileCapability 声明文件（来自部署配置）
- Adapter plugin 注册请求（自定义 store backend）
- 索引重建 / 迁移命令（migration tool 触发）

## 输出

- 持久化结果（行 ID、commit timestamp、affected rows）
- preflight 校验结果（READY / UNREADY + 缺失能力清单）
- Projection Index 物化视图查询结果
- 索引重建报告（success / truncation_suspected）
- 迁移产物（标准格式 dump：CSV / Parquet / Cypher）

## 三档 Profile 总览

按部署规模与可用资源切换：

| Profile | 部署形态 | 文本/关系 | 向量 | 图 | 适用阶段 | 单机/分布式 | License 安全性 |
|---|---|---|---|---|---|---|---|
| **local-store** | 嵌入式，零服务进程 | SQLite (JSON1+FTS5) | LanceDB | LadybugDB | P1 | 单机 | 全部 OSI 许可 |
| **dist-store** | 分布式集群 | Postgres 18 | pgvector | Apache AGE | P2 | 主从 + 副本 | 全部 OSI 许可 |
| **cloud-store** | 云托管 | 三形态可选 | 三形态可选 | 三形态可选 | P3 | 跨区域 | 商业 SaaS |

三档共享同一 Adapter 接口契约（见下文 §Adapter 接口契约），数据可经 migration tool 在档间迁移。

## P1: local-store（嵌入式单机）

### 选型

| 类别 | 系统 | 版本 | License | 持久化 | 关键能力 |
|---|---|---|---|---|---|
| 关系/文档 | SQLite | 3.46+ | Public Domain | 文件 | JSON1, FTS5, WAL |
| 向量 | LanceDB | 0.30+ | Apache-2.0 | 文件 | HNSW + IVF, 元数据过滤, 列存 |
| 图 | LadybugDB | 0.16+ | MIT | 文件 | Cypher, PageRank, columnar OLAP |

### 选型理由

- **SQLite**：唯一 Python 标准库内置，事务 + JSON1 + FTS5 一站到位，100GB 量级单机性能稳定，WAL 模式下并发读多写一适合 outbox。
- **LanceDB**：Apache-2.0 真嵌入式，列存 + 持久化原生，10⁶ 量级 p99 < 50ms 已被多份 benchmark 验证，pip 单包安装。
- **LadybugDB**：Kuzu 上游 2025-10 归档。LadybugDB 是 Kuzu 的 MIT fork，自述「formerly known as Kuzu」，继承 Kuzu 全部代码与历史，v0.16.1（2026-05），1.1k stars，5885 commits，pip install ladybug 即可 Python in-process 调用，单文件 .lbug 持久化，内置 algo 扩展支持 PageRank（PPR 仍需 NetworkX 回退，与 Kuzu 同样限制）。RyuGraph 与 Bighorn 是同期 fork，活跃度均低于 LadybugDB，作为切换备选。

### query engine：DuckDB（read-only 检索 + OLAP 层）

DuckDB 不是 OLTP 主表，是 P1 的 query engine。承担：

1. **跨格式 SQL 检索**：read-only `ATTACH 'starling.db' (TYPE sqlite)` + `LOAD lance` 后，一条 SQL 可以同时跑向量召回 + BM25 + JOIN Statement 元数据 + ranking。利用 Lance × DuckDB 集成（2026-01-12 公告，DuckDB 1.5.1 进 core extension）的三个 SQL table function：`lance_vector_search` / `lance_fts` / `lance_hybrid_search`。
2. **OLAP 分析**：审计、Replay 候选采样、retro 分析、PipelineRun 长任务统计。

写入路径不动 DuckDB。SQLite 是 source of truth，DuckDB 是派生引擎。

| 字段 | 值 |
|---|---|
| 系统 | DuckDB |
| 版本 | 1.5+ |
| License | MIT |
| 部署 | in-process Python（同 SQLite / LanceDB） |
| ATTACH SQLite | sqlite_scanner 扩展 |
| 查询 LanceDB | lance core extension |

**为什么 DuckDB 不替代 SQLite 做 OLTP 主表**：

| 阻断点 | 详情 |
|---|---|
| FTS 索引不自动更新 | 官方文档：「The FTS index will not update automatically when the input table changes」，必须手动重建。Starling BM25 召回是查询路径关键，频繁单行写入下不可用。SQLite FTS5 通过 trigger 自动同步。 |
| 单行 INSERT 性能差 | benchmark：batched 比 individual 快 10×；官方明示「avoid using lots of individual row-by-row INSERT statements」；auto-commit 每条触发 fsync。 |
| 不支持 PRIMARY KEY AUTOINCREMENT | outbox 顺序投递需 CREATE SEQUENCE + nextval()，可用但风格不同 |
| 不支持部分/表达式/覆盖索引 | 仅 ART + zonemap |
| UPDATE 索引列 = DELETE+INSERT | confidence 频繁 mild correction 受影响 |
| 多进程并发写仍 beta | Quack 协议 2026-05-12 刚发，需等 v2.0 |

12 个月后重新评估方案 B（DuckDB 替代 SQLite）的触发条件：DuckDB FTS 自动索引同步 + Quack v2.0 GA + 单行 INSERT 优化到 SQLite 量级 + partial index 支持。

**为什么 LanceDB 不替代 SQLite 做 OLTP 主表**：

| 阻断点 | 详情 |
|---|---|
| 无跨表事务 | Lance Transactions Spec：原子性单元是 dataset/manifest，每次写一张表一个 commit |
| 无 autoincrement / sequence | outbox 顺序投递契约直接断裂 |
| 无 JOIN / GROUP BY | OSS API 仅单表 filter + top-k |
| JSON 仅 filter | 局部更新需全行重写 |
| 官方反对 OLTP | 「avoid inserting one row at a time」 |
| 无 CHECK / FK / UNIQUE | 约束需 Validator 重新实现 |

### 备选与简化变体

- 量级 ≤ 10⁵ 时可改用 sqlite-vec 把向量塞进 SQLite 同事务（栈从 3 减到 2），向量与 Statement 主表同库同备份。
- LadybugDB 后续若停滞，可切 RyuGraph（API 兼容）跟随安全补丁，Bighorn 作第二备选。

### 不推荐及理由

| 候选 | 理由 |
|---|---|
| DuckDB vss | persistence 仍 experimental，HNSW 全量序列化、崩溃恢复需手动 ATTACH |
| Memgraph | BSL 1.1，商业嵌入分发受限，且需服务进程 |
| FalkorDB | SSPL + Redis 服务进程，license 与嵌入式硬约束双重违反 |
| Weaviate embedded | 实为本地子进程 + IPC，非 in-process |
| Qdrant local mode | 是 Python client 功能子集模拟，与 server mode 不等价 |
| Neo4j Embedded | 仅 Java 嵌入，Python 必须经 Bolt 协议走网络 |
| igraph | GPL-2.0+，商业闭源分发存在传染风险 |
| graph-tool | 安装链复杂（Boost + CGAL），不符合 pip 单 binary |
| sqlite-vss | 作者已标记 deprecated，被 sqlite-vec 取代 |
| DuckPGQ | property graph 是 transient（连接断开消失），不适合持久边 |
| ArcadeDB | JVM 内嵌，需打包 JRE + 150MB 体积 |

## P2: dist-store（分布式集群）

### 选型

| 类别 | 系统 | 版本 | License | 部署 | 关键能力 |
|---|---|---|---|---|---|
| 关系/文档 | PostgreSQL | 18+ | PostgreSQL License | 主从 + Patroni | ACID, JSONB, FTS, partial index |
| 向量 | pgvector | 0.9+ | PostgreSQL License | 同 PG 集群 | HNSW + IVF, hybrid filter, iterative scan |
| 图 | Apache AGE | 1.5+ | Apache-2.0 | 同 PG 集群 | openCypher, 同事务跨模 |

### 选型理由

三模一体（同库同事务）：

1. **cross_partition_transaction capability 直接满足**：Statement + vector + graph 同事务原子提交，severe path（Statement 主表 + vector + graph + outbox 同事务 4 项）天然支持。这是其他所有方案做不到的。
2. **运维半径最小**：单数据库引擎，备份、监控、HA、TLS、连接池一套到底，相比三库分离少 2-3 个常驻服务的负担。
3. **从 P1 迁移路径短**：SQLite → Postgres 是行业标准路径，pgvector 与 LanceDB schema 可映射，AGE 与 Kuzu 都用 Cypher 子集，schema 几乎可 1:1 移植。

### 容量定位

10⁷ Statement、10⁸ 向量、10⁸ 边、5 跳遍历、PPR <1s on 1k 子图：单台 256GB RAM / 1TB NVMe 可承载。突破时按维度独立外迁，不一开始就三库分离。

### 已知坑

1. **AGE 与 Citus 不兼容**：AGE 把图标签存为系统级 schema，Citus 分片元数据不识别；横向分片时 AGE 留协调节点或走 schema-based sharding。
2. **HNSW 索引重建慢**：10⁷ × 1024 维构建 HNSW 在 16 核机约 30-90 分钟；删除留 tombstone，需定期 REINDEX。
3. **AGE ≥5 跳查询计划退化**：Cypher 重写为 LATERAL JOIN 链，planner 递归路径估算差。建议超过 4 跳改多次 1-跳 + 应用层 BFS，或主表 WITH RECURSIVE 物化路径。
4. **PPR 在 AGE 内置缺失**：1k 子图取出经 PL/Python + NetworkX 跑 PPR < 100ms 满足要求；高频热路径建议外迁 NebulaGraph 或 Neo4j Enterprise。
5. **HNSW 跨 shard recall 下降**：Citus 分片后每 shard 独立建 HNSW，跨 shard 查询 union+top-k recall 下降 5-15%，需增大 ef_search 补偿。
6. **多租户 partial index 数量膨胀**：> 1000 租户时 catalog 爆炸；用 partition + tenant_id 列 + 全局 HNSW + pgvector filter scan 替代。
7. **AGE 写入比 SQL 慢 2-3 倍**：批量导入用 COPY + 后置建图，避免 Cypher 循环 CREATE。
8. **TOAST vacuum 抖动影响 p99**：vector(1024) 存 TOAST，删除大量行后 vacuum 时间线性增长；调 autovacuum_vacuum_scale_factor=0.05 + autovacuum_vacuum_cost_limit=2000。

### 备选

- **重图负载场景**：Postgres + pgvector + NebulaGraph 集群（图独立外迁），cross_partition_transaction 降级为 eventual 走 outbox。
- **重向量负载场景**：Postgres + Qdrant cluster（向量独立外迁，Tiered Multitenancy 解决 noisy neighbor），需 saga 补偿。

### 不推荐及理由

| 候选 | 理由 |
|---|---|
| CockroachDB | 自 2024 改 CSL，非 OSI；且不能装 AGE / pgvector C 扩展 |
| ArangoDB | BUSL 1.1，非 OSI 开源；Community 仅单节点 |
| TigerGraph | 商业闭源 + Free Enterprise 限 50GB |
| Memgraph | BSL 1.1，Community 不支持分布式 |
| SurrealDB | BUSL，3.0 GA 不到 3 个月，规模验证窗口不足 |
| MySQL InnoDB Cluster | JSON 弱、无向量、无图，对 AI 工作负载不友好 |
| ClickHouse | OLAP 引擎，不支持事务，1k QPS 点写反模式 |
| Neo4j Community | 不支持集群，仅单机 |
| JanusGraph | Cassandra/HBase 后端 + Gremlin，运维复杂度高 |
| OrientDB | 2024 后无活跃 release，项目近乎停滞 |
| FalkorDB / RedisGraph | RedisGraph 停更，FalkorDB AGPL 且生态尚不成熟 |

## P3: cloud-store（云托管，三形态）

### 形态 1：单云原生（推荐 90% 用户）

| 云 | 关系 | 向量 | 图 | 备注 |
|---|---|---|---|---|
| AWS | Aurora Postgres / Aurora Serverless | OpenSearch (k-NN) / pgvector on Aurora | Neptune / Neptune Analytics | Bedrock KB 原生集成 |
| GCP | Cloud SQL / AlloyDB | Vertex AI Vector Search / pgvector on AlloyDB | Spanner Graph (2025 GA) | Vertex AI 一体化 |
| Azure | Azure DB for PostgreSQL Flexible | Azure AI Search / pgvector | Cosmos DB Gremlin（小规模）| Azure OpenAI 集成 |

IAM、VPC、Private Link、KMS、CloudWatch 一套搞定，同 region 内组件互通延迟低，与云上托管 LLM 原生集成。代价是 vendor lock-in 与跨区域 egress 成本。

### 形态 2：混合托管

云的关系库（PG-wire 兼容）+ 自托管向量/图（K8s）。从 P2 演化最自然：关系作为核心数据资产托管（自动备份、PITR、跨区域副本），向量/图作为衍生数据自管降本 + 多云可移植。

### 形态 3：跨云 SaaS

| 类别 | 推荐 | 协议 |
|---|---|---|
| 关系 | YugabyteDB Aeon / TiDB Cloud / CockroachDB Cloud | PG-wire / MySQL-wire |
| 向量 | Pinecone / Qdrant Cloud / Weaviate Cloud | 自有 API |
| 图 | Neo4j Aura | openCypher |
| 消息 | Confluent Cloud | Kafka-wire |

每组件都跨云、可任意组合 AWS/GCP/Azure，每类的"专家产品"质量高于通用云的同类托管。代价是多家 SaaS 账单 + 多家 VPC peering + 跨厂商一致性靠应用层 outbox。

### 协议选型决定锁定深度

- **关系**：优先 PG-wire（Aurora / AlloyDB / Azure PG / Yugabyte / TiDB / CockroachDB），与 P2 自托管 Postgres 零摩擦迁移。避免 DynamoDB / Cosmos NoSQL / Spanner 私有协议。
- **图**：优先 openCypher（Neo4j Aura 跨云），避免 Cosmos Gremlin（10⁹+ 节点跨分区扇出崩塌）、Spanner Graph（强绑 GCP）。
- **消息**：优先 Kafka-wire（Confluent / MSK / Aiven），outbox 跨云可移。
- **向量**：算法变化快（DiskANN / pgvectorscale / GPU k-NN / ScaNN），建议双路线（SaaS + pgvector）+ 定期 benchmark，不 all-in 单一索引算法。

### 2026 关键产品状态

- Spanner Graph 2025-02 GA（唯一全球一致 + 图 + 关系 + 向量同库）
- Bedrock KB GraphRAG with Neptune Analytics 已 GA
- Cosmos DB MongoDB vCore DiskANN 已 GA + Filtered ANN GA
- OpenSearch GPU k-NN 已 GA，billion-scale 提速 10x
- Aurora PostgreSQL Limitless 自动 sharding 已 GA
- Neo4j InfiniGraph 横向扩展架构 GA

### 不推荐

| 候选 | 理由 |
|---|---|
| AWS DocumentDB | MongoDB 兼容版本落后 Atlas，无新增价值 |
| Firestore | 文档 API 私有，多区域写有限制，移动/Web 同步定位 |
| Azure SQL Hyperscale | T-SQL 与 P2 Postgres 不兼容 |
| Cosmos Gremlin（10⁹+ 边）| 跨分区高扇出查询性能崩塌 |
| Kendra | 已被 Bedrock KB + OpenSearch 替代覆盖 |
| DynamoDB（作 Statement 主表）| KV 模型，无法表达 JSONB / 向量复合查询 |
| Bigtable（作 Statement 主表）| 同上，适合时序日志非主表 |
| MotherDuck（作 P3 主存）| ≤ 10TB B2B 分析甜区，不适合 1B+ statement |

## Adapter 接口契约

所有 store backend 实现统一 Adapter 接口，便于配置切换与插件扩展。三类 Adapter 协议：

### 文本/关系 Adapter

```python
class RelationalAdapter(Protocol):
    def begin_transaction(self) -> Transaction: ...
    def commit(self, tx: Transaction) -> CommitResult: ...
    def rollback(self, tx: Transaction) -> None: ...
    def insert(self, table: str, rows: list[dict], tx: Transaction) -> InsertResult: ...
    def query(self, sql: str, params: dict) -> RowSet: ...
    def fts_search(self, table: str, query: str, filters: dict) -> list[Row]: ...
    def jsonb_query(self, table: str, jsonpath: str, filters: dict) -> list[Row]: ...
    def export_dump(self, format: Literal["sqlite", "csv", "parquet"]) -> Path: ...
    def import_dump(self, path: Path) -> ImportResult: ...
```

### 向量 Adapter

```python
class VectorAdapter(Protocol):
    def upsert(self, vectors: list[Vector], metadata: list[dict], tx: Transaction | None) -> None: ...
    def search(self, query: Vector, k: int, filters: dict) -> list[ScoredHit]: ...
    def filter_search(self, query: Vector, k: int, sql_filter: str) -> list[ScoredHit]: ...
    def delete(self, ids: list[str], tx: Transaction | None) -> None: ...
    def rebuild_index(self, params: IndexParams) -> RebuildReport: ...
    def export_dump(self, format: Literal["parquet", "lance"]) -> Path: ...
```

### 图 Adapter

```python
class GraphAdapter(Protocol):
    def execute_cypher(self, cypher: str, params: dict, tx: Transaction | None) -> ResultSet: ...
    def upsert_node(self, label: str, props: dict, tx: Transaction | None) -> NodeId: ...
    def upsert_edge(self, src: NodeId, dst: NodeId, kind: str, props: dict, tx: Transaction | None) -> EdgeId: ...
    def neighbors(self, node: NodeId, edge_kinds: list[str], depth: int) -> list[NodeId]: ...
    def ppr(self, seeds: list[NodeId], damping: float, top_k: int) -> list[ScoredNode]: ...
    def export_dump(self, format: Literal["cypher", "csv", "parquet"]) -> Path: ...
```

### QueryEngine Adapter

QueryEngine 是只读 SQL 引擎，跨 Relational / Vector / Graph 三类 backend 提供统一 SQL 接口。它不写入，写入仍走原生 Adapter。P1 实现是 DuckDB（ATTACH SQLite + LOAD lance）。

```python
class QueryEngineAdapter(Protocol):
    def attach(self, source: AdapterRef) -> None:
        """挂载只读数据源（SQLite database / Lance dataset / 图导出）"""

    def execute_sql(self, sql: str, params: dict) -> RowSet:
        """执行只读 SQL，可跨已挂载源"""

    def vector_search(self, dataset: str, query: Vector, k: int, filters: str) -> list[ScoredHit]:
        """向量检索表函数（lance_vector_search 等价）"""

    def fts_search(self, dataset: str, query: str, filters: str) -> list[ScoredHit]:
        """BM25 全文检索表函数"""

    def hybrid_search(self, dataset: str, vec: Vector, text: str, k: int, alpha: float) -> list[ScoredHit]:
        """向量 + BM25 混合检索 + RRF rerank"""

    def detach(self, source: AdapterRef) -> None: ...
```

QueryEngine 与三个写入 Adapter 共享同一物理底座（SQLite 文件 / Lance 目录 / 图文件），但**只读挂载**避免跨进程锁竞争。Bus.write 走原生 Adapter；Retrieval Planner / OLAP 走 QueryEngine。

### Capability 声明

每个 Adapter 实例必须声明其 ProfileCapability：

```python
class ProfileCapability:
    profile_name: str                       # local-store / dist-store / cloud-store-aws / ...

    # 三模能力
    relational_backend: str                 # 例 "sqlite" / "postgres" / "aurora"
    vector_backend: str                     # 例 "lancedb" / "pgvector" / "opensearch-knn"
    graph_backend: str                      # 例 "kuzu" / "age" / "neptune"

    # 事务能力
    cross_partition_transaction: bool       # 三模同事务（severe path 直接路径）
    transactional_outbox: bool              # outbox 与主表同事务
    consumer_checkpoint: bool               # 订阅者位点持久化

    # 多租户
    tenant_isolation: Literal["app_filter", "storage_enforced"]

    # 加密
    engram_per_record_key: bool             # crypto_erasure 前置条件
    engram_refcount: bool                   # Engram 共享引用计数

    # 索引
    projection_index_supported: bool        # P2+ 物化视图
    dimension_versions_supported: bool      # P3 dimension-level CAS

    # 测试约束
    testing_helper_marker: bool             # 必须 true，CI 静态扫描标记
```

## 配置化与插件扩展

### 配置文件

部署时声明 profile 与具体 backend：

```yaml
# starling.config.yaml
profile: local-store
relational:
  backend: sqlite
  connection: file:./data/starling.db
  options:
    journal_mode: WAL
    synchronous: NORMAL
vector:
  backend: lancedb
  connection: file:./data/lance
  options:
    index_type: hnsw
    m: 32
    ef_construction: 200
graph:
  backend: ladybugdb
  connection: file:./data/ladybug
runtime:
  outbox_table: outbox
  consumer_checkpoint_table: checkpoints
```

切换到 P2 仅需替换 backend 名与连接串，应用代码不变：

```yaml
profile: dist-store
relational:
  backend: postgres
  connection: postgres://user:pwd@pg-primary:5432/starling
vector:
  backend: pgvector
  connection: ${relational.connection}
graph:
  backend: apache-age
  connection: ${relational.connection}
```

### 插件注册

第三方 store backend 经 entry_points 注册：

```python
# pyproject.toml
[project.entry-points."starling.adapters.relational"]
my_relational = "my_pkg.adapter:MyRelationalAdapter"

[project.entry-points."starling.adapters.vector"]
my_vector = "my_pkg.adapter:MyVectorAdapter"

[project.entry-points."starling.adapters.graph"]
my_graph = "my_pkg.adapter:MyGraphAdapter"
```

启动时 Substrate Adapter 扫描 entry_points，与配置文件 `backend` 名匹配后实例化。

### 验证流程

```
启动
  ↓
加载 starling.config.yaml
  ↓
查找匹配 backend 的 Adapter 实现（内置 or 插件）
  ↓
实例化 Adapter
  ↓
调用 Adapter.declare_capability() 获取 ProfileCapability
  ↓
preflight 校验：
  - 必备能力（transactional_outbox, consumer_checkpoint, tenant_isolation, engram_per_record_key）
  - 当前阶段所需能力（P1: 全部本地；P2: cross_partition_transaction 必须；P3: 跨区域副本）
  ↓
任一不满足 → UNREADY fail-closed
  ↓
全部满足 → READY，开始接收 Bus 调用
```

## 主要流程

### preflight 启动流程

```
[1] 读取 config.yaml
[2] 解析 profile 声明
[3] 加载 Adapter（内置 / 插件）
[4] Adapter.connect()
[5] Adapter.declare_capability()
[6] preflight 校验 → READY / UNREADY
[7] READY: 注册 Adapter 到 Bus 路由
[8] UNREADY: emit runtime.unready，进程退出非 0
```

### Bus.write 路由

```
Bus.write(stmt)
  ↓
Validator.check()
  ↓
ConflictProbe.scan()
  ↓
Adapter 路由（按 stmt.consolidation_state）：
  - VOLATILE → Hippocampus 分区（写 RelationalAdapter + VectorAdapter，同事务）
  - CONSOLIDATED → Neocortex 分区（写 RelationalAdapter + VectorAdapter + GraphAdapter，同事务）
  ↓
若 ProfileCapability.cross_partition_transaction=true：
  - 三类 Adapter 在同一 Transaction 内 commit
否则：
  - 走 saga 补偿路径（先写主表 + outbox，异步同步向量/图）
  ↓
outbox.append() 同事务
  ↓
commit
```

### 跨档迁移

```
P1 → P2:
  [1] P1 端 export_dump（SQLite/Lance/LadybugDB）
  [2] 转换为 Postgres 格式（schema 映射 + 向量直接复用 + Cypher 重导）
  [3] P2 端 import_dump
  [4] 校验 row count + checksum
  [5] 切换 config.yaml 的 profile
  [6] 重启 Substrate Adapter
  [7] preflight 通过 → 流量切换

P2 → P3:
  按维度独立外迁（关系层 / 向量层 / 图层 三选一先迁）
  [1] 搭建 P3 backend（Aurora / Pinecone / Neo4j Aura 等）
  [2] dual-write 期：同时写 P2 与 P3
  [3] checksum 校验数据一致性
  [4] 流量切到 P3
  [5] 拆 P2 backend
```

### 维度独立外迁触发条件

按维度独立检查，只拆撑不住的那一个：

| 维度 | 触发阈值 | 外迁目标 |
|---|---|---|
| 向量 | > 5×10⁷ 且 p99 > 200ms | Qdrant cluster / Pinecone |
| 图边 | > 5×10⁸ 或 6 跳常规 | NebulaGraph / Neo4j Aura |
| Statement | > 10⁸ 行 | YugabyteDB / Aurora Limitless |

## 核心算法

### preflight Capability matching

```python
def preflight(adapter: Adapter, required_caps: list[str]) -> PreflightResult:
    declared = adapter.declare_capability()
    missing = []
    for cap in required_caps:
        if not getattr(declared, cap, False):
            missing.append(cap)
    if missing:
        return PreflightResult(status="UNREADY", missing=missing)
    return PreflightResult(status="READY")
```

### cross_partition_transaction 路径决策

```
if ProfileCapability.cross_partition_transaction:
    用 Adapter.begin_transaction() 同事务写所有维度
else:
    用 saga 模式：
      step 1: 写主表（含 outbox 行）
      step 2: 监听 outbox，异步写向量
      step 3: 监听 outbox，异步写图
      失败回滚：emit reconsolidation.compensated 撤销已完成步骤
```

### testing helper 双防线

CI 静态扫描禁止 prod entrypoint 引用 `starling.testing.*` 命名空间；运行时 preflight 检测模块 marker `__starling_testing_only__=True`，prod profile 加载到该模块即 fail-closed 退出。两条防线独立生效：

- 防线 1：CI 阶段 import graph 静态分析，违反即 PR 拒绝合并
- 防线 2：进程启动时 sys.modules 扫描，违反即 emit runtime.unready

## 数据结构

### Adapter 注册表

```python
class AdapterRegistry:
    relational: dict[str, type[RelationalAdapter]]
    vector: dict[str, type[VectorAdapter]]
    graph: dict[str, type[GraphAdapter]]
    query_engine: dict[str, type[QueryEngineAdapter]]

    def register(self, kind: str, name: str, cls: type) -> None: ...
    def get(self, kind: str, name: str) -> type: ...
    def discover_plugins(self) -> None:  # entry_points 扫描
        ...
```

### 内置 Adapter 矩阵

```
local-store:
  relational: SqliteAdapter
  vector: LanceDbAdapter
  graph: LadybugDbAdapter
  query_engine: DuckDbAdapter

dist-store:
  relational: PostgresAdapter
  vector: PgVectorAdapter
  graph: ApacheAgeAdapter
  query_engine: PostgresAdapter

cloud-store-aws:
  relational: AuroraPostgresAdapter
  vector: OpenSearchKnnAdapter | PgVectorAuroraAdapter
  graph: NeptuneAdapter | NeptuneAnalyticsAdapter
  query_engine: AuroraPostgresAdapter

cloud-store-gcp:
  relational: AlloyDbAdapter
  vector: VertexVectorSearchAdapter | PgVectorAlloyDbAdapter
  graph: SpannerGraphAdapter
  query_engine: AlloyDbAdapter

cloud-store-azure:
  relational: AzurePostgresAdapter
  vector: AzureAiSearchAdapter
  graph: CosmosGremlinAdapter（仅小规模）
  query_engine: AzurePostgresAdapter

cloud-store-multicloud:
  relational: TiDbCloudAdapter | YugabyteAeonAdapter | CockroachCloudAdapter
  vector: PineconeAdapter | QdrantCloudAdapter | WeaviateCloudAdapter
  graph: Neo4jAuraAdapter
  query_engine: TiDbCloudAdapter | YugabyteAeonAdapter | CockroachCloudAdapter
```

### 容量决策矩阵

| 工作负载 | 默认（三模一体） | 升级 1（vector 拆分） | 升级 2（graph 拆分） | 重负载 |
|---|---|---|---|---|
| Statement 数 | ≤ 5×10⁷ | ≤ 10⁸ | ≤ 10⁸ | > 10⁸ → P3 |
| Vector 数 | ≤ 5×10⁷ | ≤ 5×10⁸ | ≤ 10⁸ | > 5×10⁸ → P3 |
| Graph 边数 | ≤ 5×10⁸ | ≤ 5×10⁸ | ≤ 10⁹ | > 10⁹ → P3 |
| N 跳深度 | ≤ 4 | ≤ 4 | ≤ 7 | > 7 → P3 |
| PPR 频率 | 离线 / 低频 | 离线 / 低频 | 高频 | 高频 + 大子图 → P3 |
| cross_partition_transaction | strict | strict（vector 仍同库时）| eventual | eventual / disabled |
| 运维节点数 | 1×PG（+1-2 replica）| 1×PG + Qdrant cluster | 1×PG + Nebula cluster | 三库分离全套 |

## 相关概念

- ProfileCapability：Adapter 声明的能力清单，preflight 校验用
- cross_partition_transaction：三模 Adapter 同事务能力，severe path 直接路径条件
- saga 补偿：cross_partition_transaction 缺失时的备用一致性方案
- testing helper marker：CI + 运行时双防线，prod 拒绝 testing 命名空间
- engram_per_record_key：crypto_erasure 的前置 Adapter 能力
- entry_points：Python 标准包元数据机制，插件注册
- migration tool：跨档导出/导入工具，标准化 dump 格式（Parquet / CSV / Cypher）
- 引用 [Statement Bus](v22_05_bus.md), [Runtime Governance](v22_05_governance.md), [EngramStore](v22_06_engramstore.md), [Reconsolidation Engine](v22_11_reconsolidation.md)
