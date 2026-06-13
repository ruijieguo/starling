# P3.b1 存储抽象 — 三类 Store × Profile 架构设计稿

> 状态:**已批准,执行中**(2026-06-13)。用户裁定推进方式 = **先抽象 + zvec,
> LadybugDB(phase 6)后置 PoC 定夺**:phase 1–5(三类接口 + StoreBundle/Profile/
> Capability + MetaStore 读写收编 + GraphStore 接口 SQLite backend + zvec 向量换装)
> 先落地;phase 6 LadybugDB backend 在 GraphStore 接口稳定后先跑基线 PoC 再 go/no-go;
> phase 7 keystore 保留。旧"写收编/读不强制"草案作废。

## 0. 用户裁定(2026-06-13)

1. **统一接口抽象,所有读写均经存储层接口**(不止写——读也收编)。
2. **三类存储**:文本/Meta、向量、关系/图,各自解耦引擎选型;profile 化
   (当前 local-store;未来 dist-store / cloud-store)。
3. **local-store 引擎**:文本/Meta=**SQLite**、向量=**zvec**、关系/图=**LadybugDB**。

此裁定与 `04_substrate.md` §"Adapter 接口契约"原设计一致(三类
RelationalAdapter/VectorAdapter/GraphAdapter + ProfileCapability + AdapterRegistry),
仅精化引擎选型:文本/Meta 由原 seekdb 改 SQLite(延续现状,免迁移)、
向量明确 zvec。

## 1. 现状(实测)

- 163 写点散落 44 个 C++ 文件(persistence/ 外),无表所有权、SQL 无单源。
- 一切在单一 SQLite,单写者 ACID。
- 向量层**已有 seam**:`VectorIndex` 抽象 + `SqliteBlobVectorIndex`(BLOB 暴力扫描——确有性能债)。
- 图遍历是应用层算法(`PatternCompletor` 扩散激活)叠在简单 SQL JOIN 上。

## 2. 引擎可行性结论(两份代码审计,2026-06-13)

| 引擎 | 形态 | 结论 |
|---|---|---|
| **zvec** | 纯进程内 C++17 库(vendorable,macOS arm64 一级,NEON) | ✅ **绿灯**。`Collection::CreateAndOpen/Insert/Query/Delete` 干净映射 `VectorIndex`;7 索引 + cosine/L2/IP;运行时维度可配;原子性非问题(向量本就异步) |
| **LadybugDB** | 纯进程内 C++20 库(Kuzu 接班人,成熟 ACID,Cypher) | ✅ 可行但**有取舍**:我们图需求小(边少、单跳"取某 kind 邻居"为主),收益偏"代码优雅"非"性能飞跃";引入跨引擎一致性成本(冲突边现同事务写,迁出后转最终一致) |

## 3. 目标架构:三类 Store × 三档 Profile

```
子系统层(bus/replay/recon/tom/retrieval/…)
   │  只调 Store 语义方法(读+写),不再手搓 SQL / 不接触引擎
   ▼
Store 接口层(本期新增,include/starling/store/)
   MetaStore   VectorStore   GraphStore       ← 三类抽象
   │             │              │
   ▼             ▼              ▼
local-store backend(src/store/local/)
   SqliteMetaStore  ZvecVectorStore  LadybugGraphStore
   (SQLite)         (zvec)           (LadybugDB)
   │
   ▼ (future profiles,seam 留好)
dist-store: Postgres / pgvector / AGE   cloud-store: 托管三形态
```

- **StoreBundle**:三类 store 的持有者 + profile 工厂(`StoreBundle::open(config)` 按 `profile` 装配 backend)。
- **ProfileCapability**:每 bundle 声明能力(`cross_partition_transaction` / `transactional_outbox` / …),preflight 校验(沿用 04_substrate §Capability)。
- **AdapterRegistry**:backend 名 → 工厂注册表(内置静态注册;Python entry_points 留 P3.b 后期)。

**表 → 类别归属:**
- **MetaStore**(文本/Meta,SQLite):statements、engrams、commitments 族、proj_* 投影、bus_events 族、cognizers 族、common_ground 族、containers、各 checkpoint、estimator cache、replay/recon 状态表…(≈40 表,绝大多数)
- **VectorStore**(向量,zvec):statement_vectors
- **GraphStore**(关系/图,LadybugDB):statement_edges、cognizer_relations

## 4. 一致性模型(关键设计)

单引擎 ACID 在三引擎拆分后失效。`04_substrate` 的 `ProfileCapability` 已预置
此情形:

- local-store 三引擎独立 → `cross_partition_transaction=false`、`transactional_outbox=true`。
- **MetaStore(SQLite)是 ACID 锚**:业务写 + outbox 事件**同 SQLite 事务**(现 bus 架构)。
- **向量/图异步从事件物化**(saga/outbox):
  - 向量:**零改动**——`EmbeddingWorker` 本就读 pending 语句异步写向量,从不在语句事务内。换 zvec 不丢任何现有原子性。
  - 图:`MAY_OVERLAP_WITH` 边本就 embedding_worker 异步写;**冲突边**现于 `Bus::write` 同步入事务——迁 GraphStore 后改由订阅者消费 `belief.conflict` 事件异步写(时序由同步变最终一致,代价见 §7)。
- 跨引擎崩溃恢复:outbox 重放 + 消费者 checkpoint + 幂等 upsert(P2.o 出箱派发已是此形态)。

**原则:MetaStore 持有真相与不变式;Vector/Graph 是可重建的派生投影**(向量丢了可重嵌,边丢了可从冲突探测重算)——这正是把它们放独立引擎的安全前提。

## 5. 接口契约(YAGNI 子集,落地 04_substrate)

只实现当前用到的方法,接口可扩展(不预建 `ppr`/`hybrid_search`/`jsonb_query` 等未用项)。

```cpp
// include/starling/store/meta_store.hpp —— 文本/Meta(读+写全收编)
class MetaStore {
  // 写:语义动词(不变式 store 持有),非裸 SQL 转发
  virtual StatementWriteOutcome insert_statement(const ExtractedStatement&, ...) = 0;
  virtual int mark_consolidated(ids, tenant, batch) = 0;   // 六态机各转换
  virtual int archive(ids, tenant, reason) = 0;
  virtual void apply_mild_correction(...) = 0;
  // …(StatementStore 16 法 + 其余表的 owner 方法)
  // 读:类型化查询(替代散落 SELECT)
  virtual std::vector<StatementRow> query_statements(const StatementFilter&) = 0;
  virtual std::optional<StatementRow> get_statement(id, tenant) = 0;
  // 事务边界(子系统跨多表写时用)
  virtual std::unique_ptr<Txn> begin() = 0;
};

// include/starling/store/vector_store.hpp —— 向量(VectorIndex 泛化)
class VectorStore {
  virtual void upsert(id, tenant, const std::vector<float>&) = 0;
  virtual std::vector<ScoredId> search_topk(query, k, const SearchScope&) = 0;
  virtual void remove(id, tenant) = 0;
};

// include/starling/store/graph_store.hpp —— 关系/图
class GraphStore {
  virtual void upsert_edge(src, dst, kind, tenant, weight, conflict_key) = 0;
  virtual std::vector<std::string> neighbors(src, tenant, kinds, depth) = 0;
  virtual void upsert_relation(...) = 0;   // cognizer_relations
};
```

读路径收编(req #1)采用**类型化查询方法**(`query_statements(filter)`),不暴露
裸 SQL 给上层——这样换引擎时上层零改。dashboard 的只读检视 SQL(Python
`queries.py`)维持现状(边界规范允许的只读检视,非核心写路径)。

## 6. 分阶段(abstract first, swap second)

每 phase 独立全绿可合并。**1–4 纯抽象(SQLite everywhere,零行为变化),5–6 引擎换装(隔离、可回滚)。**

| Phase | 内容 | 行为变化 | 风险 |
|---|---|---|---|
| **1** | `store/` 骨架:三接口 + StoreBundle + ProfileCapability + AdapterRegistry;`open_local()` 装配 SQLite-backed 三类(meta=SqliteMetaStore 壳、vector=现 SqliteBlobVectorIndex 适配、graph=SqliteGraphStore 壳) | 无 | 低 |
| **2** | MetaStore 写收编:statements/edges 全部写经 StatementStore 内核(16 语义法);replay/recon/bus/tom 切调用 | 无 | 中(钉测密集区) |
| **3** | MetaStore 读收编 + 其余 meta 表 owner 方法化(投影/承诺/共识/cognizer/checkpoint…类型化读写) | 无 | 中 |
| **4** | GraphStore 接口固化:edges + cognizer_relations 走 GraphStore(SQLite backend);PatternCompletor 经 GraphStore.neighbors | 无 | 中 |
| **5** | **zvec backend**:ZvecVectorStore + vendored zvec;VectorStore 切 zvec;统一态/重嵌/维度热换保持;性能基线对标 | 向量引擎换装 | 中(隔离,可回滚到 SQLite backend) |
| **6** | **LadybugDB backend**:LadybugGraphStore + vendored;冲突边同步→异步订阅者;**go/no-go**(§7) | 图引擎换装 + 冲突边时序 | 高(隔离;**建议 PoC 后定**) |
| **7** | crypto_erasure 局部 keystore(LocalFileKms 替 NullKms,EngramStore 之后顺势) | 加密落地 | 中 |

每 phase 出口:ctest 564+ / pytest 595+ 全绿;phase 1–4 行为零变化、零 migration、零 Python 改。

## 7. 关键取舍与风险(诚实登记)

- **LadybugDB 换装的边际收益(phase 6)**:当前边量小、查询简单,图库收益偏代码优雅;且把冲突边从「`Bus::write` 同步入事务」改成「订阅者异步」是**真实语义变化**(冲突可见性从即时变最终一致,需核 C2/§16.3 冲突仲裁钉测不被破坏)。**建议**:phase 1–5(抽象 + zvec)先落地兑现 req #1/#2 + 向量明确收益;phase 6 的 LadybugDB backend 在 GraphStore 接口稳定后**先 PoC 基线再 go/no-go**——接口已就位,换或不换都低成本,不阻塞前 5 phase。
- **vendoring 构建成本**:zvec(18 依赖)/LadybugDB(31 依赖)各 +2–3min 编译;二进制增 MB 级。
- **zvec v0.4 / LadybugDB 0.18 成熟度**:均开源数月;backend 隔离 + SQLite fallback 工厂留好,生产前充分 PoC。

## 8. 验收

- 写点普查脚本复跑:statements/edges/vectors 的写 SQL 只在 store/(+testing 豁免)。
- ci_static_scan 新红线:store/persistence/testing 外出现 `INSERT INTO statements` 即 fail。
- ProfileCapability preflight 生效;`StoreBundle::open_local()` 装配三引擎。
- 全量门 + dashboard remember→tick→recall 闭环不变(phase 1–4);zvec 换装后召回质量不退(phase 5)。
