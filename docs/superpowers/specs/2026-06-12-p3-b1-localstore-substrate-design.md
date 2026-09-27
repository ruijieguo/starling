<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

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

# P3.b1 存储抽象 — 三类 Store × Profile 架构设计稿
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

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

- 写点普查脚本复跑:statements 的写 SQL 只在 store/ + `bus/statement_writer.cpp`(statements INSERT 唯一受控授权写者)+ testing;edges/vectors 写只在 store/(+testing)。
- ci_static_scan 红线#2(已落 phase 2):store/ + statement_writer.cpp + testing 外出现 `INSERT INTO statements` / `UPDATE statements` 即 fail。
- 注:`StatementWriter`(bus/)是 statements INSERT 的既有受控授权接口(返回 `StatementWriteOutcome`),已满足 req #1「写经接口」实质;物理迁移到 `src/store/`(纯命名空间 bus→store)降级为后续清理项,phase 2 不做。
- ProfileCapability preflight 生效;`StoreBundle::open_local()` 装配三引擎。
- 全量门 + dashboard remember→tick→recall 闭环不变(phase 1–4);zvec 换装后召回质量不退(phase 5)。
