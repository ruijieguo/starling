<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Substrate Adapter
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **语义证据契约状态（2026-09-12）**：已实现并通过完整工程验证；真实诊断已完成并核验，质量门槛未通过，默认关闭，设计见 [Source-Grounded Claim Contract](../../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md)。Substrate 只承载兼容的 Statement/Engram 数据；新证据字段作为可选嵌入值对象，不改变旧 schema 的默认语义。

## 2026-09-11 语义证据契约

本次契约由 C++ 实现，语言 binding 只映射类型、配置和调用。SQLite 通过 migration 0034 新增可空 `statements.semantic_claim_json`；旧行保持 NULL，不重写语义值或 canonical hash。所有证据关联查询使用 `(id, tenant_id)`，不增加第二套事实表。

实现状态与评测证据统一见 [同步清单](../claim_contract_sync.md)。

## 功能定义

把上层逻辑层（Statement / Container / Engram）与底层物理存储完全隔离。提供三档 profile（local-store / dist-store / cloud-store），每档支持文本、向量、图三类索引与检索。它不做：业务逻辑、查询计划器、缓存、事务补偿（补偿由 Reconsolidation Engine 负责）。

> **实现状态（2026-07-28）**：当前 local-store 以 SQLite 作为 Meta/Graph 真相源；向量后端默认 `sqlite`，构建时启用 `STARLING_VECTOR_ZVEC` 后可选 `zvec`。LadybugDB PoC 的结论为 no-go，seekdb / dist-store / cloud-store 仍是目标态而非当前实现。Zvec 文档主键从旧的全局 `stmt_id` 升级为版本化复合键 `starling:v1:<tenant_len>:<stmt_len>:<tenant><stmt>`；读取兼容旧裸键，重新嵌入时惰性删除旧裸键。旧全局键无法恢复已经发生的跨租户覆盖，因此升级既有 Zvec store 必须从 SQLite Statement 真相源执行一次完整向量重建，不能只依赖惰性改键。

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

| Profile | 部署形态 | 关系+向量+FTS | 图 | 适用阶段 | 单机/分布式 | License |
|---|---|---|---|---|---|---|
| **local-store** | 同机 daemon + 真 in-process | seekdb（local daemon, MySQL wire over unix socket） | LadybugDB（C++ in-process） | P1 | 单机 | Apache 2.0 + MIT |
| **dist-store** | 分布式集群 | Postgres 18 + pgvector | Apache AGE | P2 | 主从 + 副本 | OSI 许可 |
| **cloud-store** | 云托管 | 三形态可选 | 三形态可选 | P3 | 跨区域 | 商业 SaaS |

三档共享同一 Adapter 接口契约（见下文 §Adapter 接口契约），数据可经 migration tool 在档间迁移。

## P1: local-store（嵌入式单机）

### 选型

| 类别 | 系统 | 版本 | License | 实现 | 部署形态 | 关键能力 |
|---|---|---|---|---|---|---|
| 关系+向量+FTS | seekdb | v1.2+ | Apache 2.0 | C++（fork OceanBase observer） | local daemon + MySQL wire | ACID, JSON, HNSW+IVF 向量, BM25 FTS, Hybrid search |
| 图 | LadybugDB | v0.16+ | MIT（Kuzu fork） | C++ | in-process | Cypher, PageRank, columnar OLAP |

### seekdb 选型理由

OceanBase 于 2025-11 开源的 AI-native 数据库，C++ 实现，约 2.5k stars，Apache 2.0，最新 v1.2.0（2026-04）。单引擎合并关系/JSON/向量/FTS/Hybrid search/事务，相对四件套（OLTP + 向量库 + OLAP 查询引擎 + 图库）显著简化。MySQL 协议兼容，跨表 ACID 事务原生支持 outbox 模式。向量索引覆盖 HNSW、HNSW_SQ、HNSW_BQ、IVF、IVF_PQ 五种，维度上限 16000，底层 VSAG（OceanBase 自研开源向量库）。FTS 支持 BM25 与多 tokenizer（含中文 ik），`DBMS_HYBRID_SEARCH` 与 SQL `ORDER BY vector_distance APPROXIMATE` 原生表达 hybrid。继承 OceanBase observer 内核工程信誉，单机 OLTP 10k+ QPS，对 P1 100-1000 QPS 点写需求绰绰有余。

### LadybugDB 选型理由

Kuzu 上游 2025-10 归档。LadybugDB 是 Kuzu 的 MIT fork，自述「formerly known as Kuzu」，继承 Kuzu 全部代码与历史，v0.16.1（2026-05），1.1k stars，5885 commits，C++ in-process 调用，单文件 .lbug 持久化，内置 algo 扩展支持 PageRank（PPR 仍需 NetworkX 回退，与 Kuzu 同样限制）。RyuGraph 与 Bighorn 是同期 fork，活跃度均低于 LadybugDB，作为切换备选。

### 嵌入形态：同机 daemon vs 真 in-process

seekdb 的嵌入形态是**同机 daemon**：Starling C++ 内核进程通过 MySQL wire protocol over unix socket 连接 seekdb daemon。这不是 SQLite/LanceDB 那种严格 in-process 链接库形态，但同机 unix socket 延迟 < 100μs，对 P1 100-1000 QPS 单行写入可接受。

LadybugDB 走真正的 C++ in-process 链接，无 IPC。

部署单元：Starling C++ 内核 + seekdb daemon + LadybugDB 文件，三者打包为单一发行物（容器或可执行 + 配置目录）。Starling 启动时拉起 seekdb daemon 子进程，监听 unix socket，进程生命周期由 Starling supervisor 管理；shutdown 时反向回收。

### 已知风险

1. **C++ SDK 缺失**：seekdb 公开 SDK 仅 Python（pyseekdb / pylibseekdb）、JS（seekdb-js）、Go（ob-labs/seekdb-go），C/C++ 没有。Starling C++ 内核通过 MySQL wire 接 daemon（用 mariadb-connector-c 或 libmysqlclient）；不通过私有 ABI 链接 libseekdb。
2. **Windows 不支持 embedded 模式**：macOS embedded 自 v1.1.0（2026-01）起支持。Windows 用户走容器化或 client-server 模式。
3. **版本升级需数据迁移**：v1.0 → v1.1、v1.1 → v1.2 均不支持 in-place 升级，需 OBDUMPER/OBLOADER 逻辑导出导入。Starling 锁定 seekdb v1.2 minor 版本，跨 minor 升级走 export/import 流程。
4. **公开 benchmark 数字不透明**：seekdb VectorDBBench 跑法已发布，具体 p99/QPS 未公开披露。建议先 spike 1 周：用真实 C++ 客户端跑 10⁶ 向量 + 混合 SQL 工作负载，量 QPS/p99，再做最终承诺。
5. **冷启动秒级**：observer 全套堆栈链入 daemon 进程，二进制体积估上百 MB，冷启动秒级。对追求"几百 KB amalgamation 毫秒启动"的场景不适配。

### 备选与简化变体

- 量级 ≤ 10⁵ 且追求极简：SQLite (sqlite-vec + FTS5 + JSON1) + LadybugDB 两件套，全平台 C amalgamation，所有依赖毫秒级冷启动。
- LadybugDB 后续若停滞，可切 RyuGraph（API 兼容）跟随安全补丁，Bighorn 作第二备选。

### 不推荐及理由

| 候选 | 理由 |
|---|---|
| LanceDB | 无跨表事务，无 autoincrement，无 JOIN/GROUP BY，官方反对单行写 OLTP |
| DuckDB（作 OLTP 主表）| FTS 不自动更新索引，单行 INSERT 比 batched 慢 10×，多进程并发写仍 beta |
| Memgraph | BSL 1.1，商业嵌入分发受限，且需服务进程 |
| FalkorDB | SSPL + Redis 服务进程，license 与嵌入式硬约束双重违反 |
| Weaviate embedded | 实为本地子进程 + IPC，非 in-process |
| Qdrant local mode | 是 Python client 功能子集模拟，与 server mode 不等价 |
| Neo4j Embedded | 仅 Java 嵌入，C++ 必须经 Bolt 协议走网络 |
| igraph | GPL-2.0+，商业闭源分发存在传染风险 |
| graph-tool | 安装链复杂（Boost + CGAL），不符合单 binary 发布 |
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
3. **从 P1 迁移路径短**：seekdb MySQL 协议 + JSON + 向量 / pgvector 在 schema 与查询语义上可 1:1 映射；LadybugDB 与 Apache AGE 都走 Cypher 子集，图迁移走 Cypher 重导。

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

所有 store backend 实现统一 Adapter 接口，便于配置切换与插件扩展。核心实现以 **C++ 抽象类** 表达，对外通过 pybind11 / nanobind 暴露 Python binding，通过 NAPI 暴露 JS binding，通过 cffi 暴露 C / Rust binding。

三类 Adapter：RelationalAdapter、VectorAdapter、GraphAdapter。seekdb 单引擎覆盖前两者（同一个 `SeekDbAdapter` 类实例同时实现 `RelationalAdapter` 与 `VectorAdapter` 接口），LadybugDB 实现 `GraphAdapter`。

### RelationalAdapter

```cpp
class RelationalAdapter {
public:
    virtual std::unique_ptr<Transaction> begin_transaction() = 0;
    virtual CommitResult commit(Transaction& tx) = 0;
    virtual void rollback(Transaction& tx) = 0;
    virtual InsertResult insert(const std::string& table,
                                const std::vector<Row>& rows,
                                Transaction* tx) = 0;
    virtual RowSet query(const std::string& sql, const Params& params) = 0;
    virtual std::vector<Row> fts_search(const std::string& table,
                                        const std::string& query,
                                        const Filters& filters) = 0;
    virtual std::vector<Row> jsonb_query(const std::string& table,
                                          const std::string& jsonpath,
                                          const Filters& filters) = 0;
    virtual std::filesystem::path export_dump(DumpFormat fmt) = 0;
    virtual ImportResult import_dump(const std::filesystem::path& path) = 0;
    virtual ~RelationalAdapter() = default;
};
```

### VectorAdapter

```cpp
class VectorAdapter {
public:
    virtual void upsert(const std::vector<Vector>& vectors,
                        const std::vector<Metadata>& metadata,
                        Transaction* tx) = 0;
    virtual std::vector<ScoredHit> search(const Vector& query,
                                           int k,
                                           const Filters& filters) = 0;
    virtual std::vector<ScoredHit> filter_search(const Vector& query,
                                                  int k,
                                                  const std::string& sql_filter) = 0;
    virtual std::vector<ScoredHit> hybrid_search(const Vector& vec,
                                                  const std::string& text,
                                                  int k,
                                                  float alpha,
                                                  const Filters& filters) = 0;
    virtual void delete_ids(const std::vector<std::string>& ids, Transaction* tx) = 0;
    virtual RebuildReport rebuild_index(const IndexParams& params) = 0;
    virtual ~VectorAdapter() = default;
};
```

`hybrid_search` 在 seekdb 端走 `DBMS_HYBRID_SEARCH` 或 `ORDER BY vector_distance APPROXIMATE` 原生混合查询，单引擎一次返回。`alpha` 控制向量分数与 BM25 分数权重。P2（pgvector + Postgres FTS）实现需在 Adapter 内部拼合双路召回 + RRF rerank。

### GraphAdapter

```cpp
class GraphAdapter {
public:
    virtual ResultSet execute_cypher(const std::string& cypher,
                                      const Params& params,
                                      Transaction* tx) = 0;
    virtual NodeId upsert_node(const std::string& label,
                                const Properties& props,
                                Transaction* tx) = 0;
    virtual EdgeId upsert_edge(NodeId src, NodeId dst,
                                const std::string& kind,
                                const Properties& props,
                                Transaction* tx) = 0;
    virtual std::vector<NodeId> neighbors(NodeId node,
                                           const std::vector<std::string>& edge_kinds,
                                           int depth) = 0;
    virtual std::vector<ScoredNode> ppr(const std::vector<NodeId>& seeds,
                                         float damping,
                                         int top_k) = 0;
    virtual std::filesystem::path export_dump(GraphDumpFormat fmt) = 0;
    virtual ~GraphAdapter() = default;
};
```

注：seekdb 的 `RelationalAdapter` 与 `VectorAdapter` 实例可以由同一个 `SeekDbAdapter` 类承担，因 seekdb 单引擎覆盖两者；Adapter 接口分两个是为了 P2/P3 切换其他 backend 时维持抽象稳定。

### Python / JS / Rust binding

C++ 核心通过 pybind11 或 nanobind 暴露 Python API。Python 端调用形态：

```python
import starling
s = starling.open("./starling.config.json")
s.bus.write(Statement(...))  # 实际转发到 C++ 内核 → seekdb daemon
results = s.retrieve(intent="FACT_LOOKUP", holder=self_id)
```

JS binding 通过 NAPI 暴露 Node.js API；C / Rust 通过 cffi。所有 binding 共享同一 C++ 内核，行为一致由 Adapter 抽象类契约保证。

### Capability 声明

每个 Adapter 实例必须声明其 ProfileCapability：

```cpp
struct ProfileCapability {
    std::string profile_name;               // local-store / dist-store / cloud-store-aws / ...

    // 三模能力
    std::string relational_backend;         // 例 "seekdb" / "postgres" / "aurora"
    std::string vector_backend;             // 例 "seekdb" / "pgvector" / "opensearch-knn"
    std::string graph_backend;              // 例 "ladybugdb" / "age" / "neptune"

    // 核心实现
    bool c_plus_plus_core;                  // 内核语言（true = C++，binding 经 pybind/NAPI/cffi）

    // 事务能力
    bool cross_partition_transaction;       // 三模同事务（severe path 直接路径）
    bool transactional_outbox;              // outbox 与主表同事务
    bool consumer_checkpoint;               // 订阅者位点持久化

    // 多租户
    std::string tenant_isolation;           // "app_filter" / "storage_enforced"

    // 加密
    bool engram_per_record_key;             // crypto_erasure 前置条件
    bool engram_refcount;                   // Engram 共享引用计数

    // 索引
    bool projection_index_supported;        // P2+ 物化视图
    bool dimension_versions_supported;      // P3 dimension-level CAS

    // 测试约束
    bool testing_helper_marker;             // 必须 true，CI 静态扫描标记
};
```

## 配置化与插件扩展

### 配置文件

部署时声明 profile 与具体 backend，格式 JSON：

```json
{
  "profile": "local-store",
  "core": {
    "implementation": "cpp",
    "bindings": ["python", "javascript"]
  },
  "relational_vector_fts": {
    "backend": "seekdb",
    "version": "1.2",
    "deployment": "local-daemon",
    "connection": {
      "mode": "unix_socket",
      "path": "/tmp/starling-seekdb.sock"
    },
    "data_dir": "./data/seekdb",
    "options": {
      "vector_index": "hnsw",
      "vector_m": 32,
      "vector_ef_construction": 200,
      "fts_analyzer": "standard"
    }
  },
  "graph": {
    "backend": "ladybugdb",
    "version": "0.16",
    "deployment": "embedded",
    "data_dir": "./data/ladybug"
  },
  "runtime": {
    "outbox_table": "outbox",
    "consumer_checkpoint_table": "checkpoints"
  }
}
```

切换到 P2 仅需替换 backend 名与连接串，应用代码不变：

```json
{
  "profile": "dist-store",
  "relational": {
    "backend": "postgres",
    "connection": "postgres://user:pwd@pg-primary:5432/starling"
  },
  "vector": {
    "backend": "pgvector",
    "connection": "${relational.connection}"
  },
  "graph": {
    "backend": "apache-age",
    "connection": "${relational.connection}"
  }
}
```

### 插件注册

第三方 store backend 通过两条路径注册：

1. **C++ 内置 / 静态链接插件**：在编译期注册到 `AdapterRegistry`，启动时自动可见。
2. **Python entry_points**：Python 端实现的 Adapter 通过 pybind 反向暴露给 C++ 内核：

```python
# pyproject.toml
[project.entry-points."starling.adapters.relational"]
my_relational = "my_pkg.adapter:MyRelationalAdapter"

[project.entry-points."starling.adapters.vector"]
my_vector = "my_pkg.adapter:MyVectorAdapter"

[project.entry-points."starling.adapters.graph"]
my_graph = "my_pkg.adapter:MyGraphAdapter"
```

启动时 Substrate Adapter 扫描内置注册表 + entry_points，与配置文件 `backend` 名匹配后实例化。

### 验证流程

```
启动
  ↓
加载 starling.config.json
  ↓
拉起 seekdb daemon 子进程（local-store profile 专属）
  ↓
查找匹配 backend 的 Adapter 实现（内置 or 插件）
  ↓
实例化 Adapter（C++ 内核 + binding 双层）
  ↓
调用 Adapter.declare_capability() 获取 ProfileCapability
  ↓
preflight 校验：
  - 必备能力（transactional_outbox, consumer_checkpoint, tenant_isolation, engram_per_record_key, c_plus_plus_core）
  - 当前阶段所需能力（P1: 全部本地；P2: cross_partition_transaction 必须；P3: 跨区域副本）
  ↓
任一不满足 → UNREADY fail-closed
  ↓
全部满足 → READY，开始接收 Bus 调用
```

## 主要流程

### preflight 启动流程

```
[1] 读取 config.json
[2] 解析 profile 声明
[3] 若 profile=local-store：supervisor 拉起 seekdb daemon 子进程，等待 unix socket 就绪
[4] 加载 Adapter（内置 / 插件）
[5] Adapter.connect()
[6] Adapter.declare_capability()
[7] preflight 校验 → READY / UNREADY
[8] READY: 注册 Adapter 到 Bus 路由
[9] UNREADY: emit runtime.unready，进程退出非 0；附带回收 seekdb daemon
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
  [1] P1 端 export_dump（seekdb 走 OBDUMPER 输出 CSV/Parquet + 向量列；LadybugDB 输出 Cypher）
  [2] 转换为 Postgres 格式（schema 映射 + 向量直接复用 + Cypher 重导到 Apache AGE）
  [3] P2 端 import_dump
  [4] 校验 row count + checksum
  [5] 切换 config.json 的 profile
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

```cpp
PreflightResult preflight(const Adapter& adapter,
                          const std::vector<std::string>& required_caps) {
    ProfileCapability declared = adapter.declare_capability();
    std::vector<std::string> missing;
    for (const auto& cap : required_caps) {
        if (!capability_has(declared, cap)) {
            missing.push_back(cap);
        }
    }
    if (!missing.empty()) {
        return {PreflightStatus::UNREADY, missing};
    }
    return {PreflightStatus::READY, {}};
}
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

注：seekdb 单引擎覆盖 relational + vector + FTS，三类写在同一 MySQL 协议事务内完成，cross_partition_transaction 对 P1 关系/向量维度天然为 true；图维度走 LadybugDB 单独事务，跨 seekdb / LadybugDB 的图 + 关系联合写仍需 outbox。

### testing helper 双防线

CI 静态扫描禁止 prod entrypoint 引用 `starling::testing` 命名空间（C++ 端）或 `starling.testing.*`（Python binding 端）；运行时 preflight 检测模块 marker `kStarlingTestingOnly = true`，prod profile 加载到该模块即 fail-closed 退出。两条防线独立生效：

- 防线 1：CI 阶段 include graph 与 Python import graph 静态分析，违反即 PR 拒绝合并
- 防线 2：进程启动时 symbol / sys.modules 扫描，违反即 emit runtime.unready

## 数据结构

### Adapter 注册表

```cpp
class AdapterRegistry {
public:
    std::unordered_map<std::string, RelationalAdapterFactory> relational;
    std::unordered_map<std::string, VectorAdapterFactory> vector;
    std::unordered_map<std::string, GraphAdapterFactory> graph;

    void register_relational(const std::string& name, RelationalAdapterFactory f);
    void register_vector(const std::string& name, VectorAdapterFactory f);
    void register_graph(const std::string& name, GraphAdapterFactory f);
    void discover_plugins();  // 扫描内置静态注册 + Python entry_points
};
```

### 内置 Adapter 矩阵

```
local-store:
  relational+vector+fts: SeekDbAdapter   # 单实例同时实现 RelationalAdapter + VectorAdapter
  graph:                 LadybugDbAdapter

dist-store:
  relational: PostgresAdapter
  vector:     PgVectorAdapter
  graph:      ApacheAgeAdapter

cloud-store-aws:
  relational: AuroraPostgresAdapter
  vector:     OpenSearchKnnAdapter | PgVectorAuroraAdapter
  graph:      NeptuneAdapter | NeptuneAnalyticsAdapter

cloud-store-gcp:
  relational: AlloyDbAdapter
  vector:     VertexVectorSearchAdapter | PgVectorAlloyDbAdapter
  graph:      SpannerGraphAdapter

cloud-store-azure:
  relational: AzurePostgresAdapter
  vector:     AzureAiSearchAdapter
  graph:      CosmosGremlinAdapter（仅小规模）

cloud-store-multicloud:
  relational: TiDbCloudAdapter | YugabyteAeonAdapter | CockroachCloudAdapter
  vector:     PineconeAdapter | QdrantCloudAdapter | WeaviateCloudAdapter
  graph:      Neo4jAuraAdapter
```

local-store 行从 4 项压缩到 2 项（seekdb 合并 relational + vector + fts，不需独立 query engine），dist-store / cloud-store 行保持三项分立。

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
- c_plus_plus_core：核心实现语言标记，C++ 内核 + binding 双层结构
- cross_partition_transaction：三模 Adapter 同事务能力，severe path 直接路径条件
- saga 补偿：cross_partition_transaction 缺失时的备用一致性方案
- testing helper marker：CI + 运行时双防线，prod 拒绝 testing 命名空间
- engram_per_record_key：crypto_erasure 的前置 Adapter 能力
- entry_points：Python binding 端插件注册机制，配合 C++ 静态注册表
- migration tool：跨档导出/导入工具，标准化 dump 格式（Parquet / CSV / Cypher）
- 引用 [Statement Bus](05_bus.md), [Runtime Governance](05_governance.md), [EngramStore](06_engramstore.md), [Reconsolidation Engine](11_reconsolidation.md)


## 来源话轮实现核对（2026-09-12）

版本化来源话轮由 C++ 生成与解析，直接证据回读共用严格验证。该子系统继续消费已有证据与时间契约，不新增语言 binding 中的语义逻辑。来源观察时间不作为绝对事件时间；本轮核对与诊断统一见 [设计同步清单](../claim_contract_sync.md) 和 [来源话轮评测报告](../../eval/2026-09-12-socialmem-source-turn.md)。


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](../../superpowers/specs/2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](../../eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](../../superpowers/specs/2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已完成并由原生验证器核验为 `verified / complete_with_errors`：140 条重放、144 个数据库；固定候选 56/64（TP 30、TN 26、误收 0、误拒 1、技术失败 7），synthetic 冻结 11/16、契约 11/16（有效分母 15/16），P1 combined F1 为 holder 0.7317、holder/perspective 0.6829、predicate/object 0.7683；扩展标签 object/topic/scope/time/joint 为 12/14、2/14、12/14、12/14、2/14（有效目标 13）；Q1/Q9 的 baseline、structured、linked 均为 0/3，full 均为 3/3；实际证据链仍受入库与证据聚合限制。原生技术失败共 10 条，主要为重复 JSON 键和准入 JSON 后追加文本；无效裁判票 0。`promotion_ready=false`，生产默认保持关闭，不运行 1,031 题全量。默认、原标签、检索与历史归档保持。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
