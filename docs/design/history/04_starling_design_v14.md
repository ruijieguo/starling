# Starling Memory v14:多主体社会心智 + 类脑动力学的智能体记忆系统设计方案

> **版本说明**:本文为 v14,以 v13 为基线做"整合收敛"审查。v14 不再继续吸纳 9 个开源库的新能力,而是防止外部优秀机制把 Starling 拼成多套体系:所有外来机制只能映射到 Starling 原生原语(Statement / DrawerRecord / BusEvent / PipelineRun / RetrievalScopePlan / ActionPolicyGraph / Projection Index),不能引入第二套事实源、第二套生命周期或第二套权限边界。
>
> **v14 相对 v13 的修复**(详见 §17.13 v13 → v14 修复记录):
>
> *Major 级*:
> 1. **证据锚语义收敛** — `SourceSpanRef/TemporalAnchor` 只对直接抽取 Statement 强制;Replay/ToM/Container 派生 Statement 继承 evidence chain,但不得伪造直接 source span(§3.2/§5.1/§10.3)
> 2. **Run Ledger 单一化** — `ExtractionAttempt` 明确是 `PipelineRun(kind="extraction")` 的 item-level 明细,不再构成第二套任务生命周期;终态、重试、dead-letter 以 PipelineRun 为权威(§5.1/§5.6)
> 3. **外部能力吸收原则** — 新增"原生原语优先/Adapter 边界/单一生命周期/权威事实源"四条整合规则,约束后续从开源库借鉴机制的落点(§0.1)
> 4. **检索 scope 命名去外部化** — `RetrievalScopePlan` 的 scope 收敛为 Starling 逻辑 scope,`session/trace/graph_context/graph` 等外部库术语只能出现在 adapter metadata,避免 Planner 变成仓库名拼盘(§13.1/§13.3)
>
> *Minor 级*:
> 5. **事件表补齐** — 补 `statement.review_requested/action.policy_blocked` 等 v13 已引用但事件表未列出的事件,并把 `pipeline.run_completed` 明确覆盖 partial/degraded completed(§5.3)
> 6. **复用资产降格** — §20 从"能力复用清单"改为"外部机制 → Starling 原语映射表",防止实现团队直接照搬外部数据结构(§20)
>
> **v13 相对 v12 的修复**(详见 §17.12 v12 → v13 修复记录):
>
> **v13 相对 v12 的修复**(详见 §17.12 v12 → v13 修复记录):
>
> *Major 级*:
> 1. **SourceSpanRef + TemporalAnchor** — Statement 不只指向 DrawerRecord,还要记录源片段/episode/segment 与相对时间解析锚;历史语料中的 "recently/today/last week" 必须按观察时间而非系统当前时间落地(§3.2/§3.8/§5.1)
> 2. **Attribution immutability** — `holder/speaker/source_span/perceived_by/temporal_anchor` 写入后不可原地改写;归因纠错必须新建 corrected Statement + supersedes,避免 UPDATE 污染信念历史(§5.1/§11.2)
> 3. **RetrievalScopePlan** — 完整 Planner 需显式声明 scope 顺序、短路/合并策略、过滤继承规则和 stop reason;多 scope 检索不得混用全局 filter 与 per-scope filter,Receipt 必须记录 skipped/degraded scopes(§13.3/§13.6.1)
> 4. **Pipeline step failure_policy** — 每个 step 声明 `critical/non_fatal/skip_downstream`;非致命失败只能在 downstream requires 满足时继续,并写入 warning/counter,避免长任务局部失败被误报成功(§5.6)
> 5. **ActionPolicyGraph** — Prospective Loop 若触发真实工具/外部动作,必须先经行动策略图约束 required-before-exit、requires-approval、max-count、terminal/parent-child 关系;提醒可以轻量,动作必须受控(§12.5)
>
> *Minor 级*:
> 6. **Entity projection** — P2 Projection Index 增 `idx_entity_statement`,把 mem0/entity-store 的 entity→memory 链接升级为 holder-aware entity→Statement 桥,服务 FACT_LOOKUP/BELIEF_OF_OTHER 的实体前置过滤(§4.1)
> 7. **复用资产更新** — 迁移路径补 mem0 Observation Date/entity link、Graphiti episode_indices/reference_time、cognee recall scope/非致命 improve stage、memU progressive sufficiency 与 Letta ToolRulesSolver(§16.2/§20)
>
> **v12 相对 v11 的修复**(详见 §17.11 v11 → v12 修复记录):
>
> *Major 级*:
> 1. **SourceAdapter + declared transformations** — Drawer 写入源必须声明 adapter/version/ingest_mode/privacy_class/declared_transformations,不再把"verbatim"当全局口号;byte-preserving 与 declared-lossy 变成可测试能力(§3.8/§6.0)
> 2. **Self-pollution guard** — `source_kind ∈ {user_input,external_doc,tool_observation,system_internal,observer_agent,replay_output}`;内部日志、检索回执、Replay 产物默认 `NO_STORE`,必须 allowlist 才能入 Drawer(§5.0/§6.0)
> 3. **Storage-enforced tenant isolation** — `tenant_isolation="storage_enforced"` 必须在底座命令边界注入 tenant/holder 过滤,未知数据面命令 fail-closed,不能只靠 service 层约定(§4)
> 4. **ScopedWorkGate + Pipeline step contract** — 长任务增加 pipeline revision、step requires/produces/capabilities、business_task_id 聚合与 holder/dataset scoped reentrant 并发闸门(§5.6)
> 5. **Projection/repair safety** — Projection rebuild 和索引修复在 shadow swap 前必须用独立真相源校验 row count/watermark/content hash,抽取短缺时拒绝替换,避免修复过程静默丢数据(§4.1/§5.6)
> 6. **Retrieval sufficiency + holder-isolated search** — RetrievalReceipt 增 `sufficiency_status`;多 holder/perspective 查询必须按 holder/group 隔离执行后合并,不得用宽泛多 holder scan 绕过边界(§13.3/§13.6.1)
>
> *Minor 级*:
> 7. **Trace retention tiers** — ExtractionAttempt/PipelineRun/RetrievalReceipt 的 prompt/response trace 默认 metadata/hash only,full_debug 必须有 TTL、脱敏和合规 profile(§5.6/§13.6.1)
> 8. **P0 验收微调** — 增加 self-pollution、source transformation metadata、tenant isolation fail-closed、repair safety dry-run 的负面用例(§16.1)
>
> **v11 相对 v10 的修复**(详见 §17.10 v10 → v11 修复记录):
>
> *Major 级*:
> 1. **Profile capability preflight** — 启动时按部署 profile 校验 transactional outbox、tenant isolation、crypto erasure、vector delete、projection rebuild 等能力,不满足即 fail-closed(§4.0)
> 2. **ExtractionAttempt 账本** — 每次抽取都记录 prompt/extractor 版本、input hash、existing-ref 短 id 映射、accepted/rejected/no-op 计数,避免无结果或部分失败静默消失(§5.1)
> 3. **RuntimeHealth + Backpressure** — 新增 READY/DEGRADED/DRAINING/UNREADY 状态、队列/lag/readiness 指标、前后台降级策略、worker lease/claim/confirm 与 restart guard(§5.6)
> 4. **PipelineRun/MaintenanceRun 账本** — Extraction/Replay/Projection/Compliance/Container rebuild 等长任务统一 run id、checkpoint、watermark、stage timing、取消和恢复语义(§5.6)
> 5. **RetrievalReceipt** — Context Pack 附带可审计检索回执:trace_id、query sanitizer、projection lag、路径/过滤/候选计数、score breakdown、abstention reason 与擦除证据计数(§13.6.1)
>
> *Minor 级*:
> 6. **检索融合与可观测细化** — §13.5 增加 EverOS 风格 vector-anchored fusion(BM25 饱和 + vector floor);§20 复用资产表补源码验证到的队列、健康检查、watermark、StageTimer、query sanitizer 等机制
> 7. **P0 边界微调** — P0 增加最小 ExtractionAttempt/PipelineRun 记录与 basic_retrieve debug receipt,但完整健康仪表盘、自动背压调度仍延后到 P1/P2(§16.1)
>
> **v10 相对 v9 的修复**(详见 §17.9 v9 → v10 修复记录):
>
> *Major 级*:
> 1. **抽取契约补齐** — Statement 产出上限、holder 归因、perceived_by 推断、confidence 初值与低置信拒收入文(§5.1)
> 2. **规范化 key 规则冻结** — `canonicalize_object / normalize_interval / scope_of` 规则表入文(§5.2)
> 3. **grounded 判定明确** — 显式确认、共同在场推定、重复确认、超时降级规则入文(§9.5)
> 4. **Replay 采样语义冻结** — 概率归一、无放回、批量大小、极端值截断、冷却期入文(§10.2)
>
> *Minor 级*:
> 5. **一致性与资源边界** — Container source_refs 版本语义、Projection Index 订阅表、ToM 双限流、holder 子图索引、pattern completion 节点上限、pending_evidence 容量入文(§4.1/§5.5/§6.4/§9.2/§11.1)
> 6. **P0 实施边界** — 负面验收用例、P0 非交付项、P0 内部子里程碑入文(§16.1)
> 7. **实施附录** — 新增术语表与实施 FAQ,降低新工程师上手成本(附录 C/D)
>
> **v9 相对 v8 的修复**(详见 §17.8 v8 → v9 修复记录):
>
> *Minor 级*:
> 1. **SupersedeGround 触发路径明确** — ConflictProbe 的 `superseding` 等级是主触发来源;CommonGround Builder 在新 Statement 达到 grounded 时落 act;Container.rebuild 只做一致性修复;Replay 不能绕过 Bus 直接修改 CommonGround(§5.2/§9.5)
>
> **v8 相对 v7 的修复**(详见 §17.7 v7 → v8 修复记录):
>
> *Major 级*:
> 1. **Projection Index 阶段边界明确** — P0 `basic_retrieve` 走主表直查;P2 才引入 Projection Index;投影索引为异步 outbox 物化,并声明 freshness SLA(§4.1/§13.4/§16.1)
> 2. **抽取重试去重语义** — 同一 DrawerRecord 重试前检查已写入 Statement,只重试失败片段,避免 LLM 非确定性导致重复写入(§5.1)
> 3. **CommonGround 过时治理** — 增加 `SupersedeGround / ExpireGround / Unground` act,解决 grounded 条目被过度保护、旧共识不衰减的问题(§9.5/§10.4)
> 4. **P0 smoke test 固化** — 以 §14.1 "Alice 宣布 Bob 不再负责 auth" 的最小变体作为 P0 验收闭环(§16.1)
>
> *Minor 级*:
> 5. **复用资产版本备注** — MemOS v2.0.x、memU Python ≥3.13、EverOS 非标准包管理的集成成本入文(§16.2/§20)
> 6. **Runtime 图标题更新** — 系统总览图从 Runtime v3 改为 Runtime v8(§2)
>
> **v7 相对 v6 的修复**(详见 §17.6 v6 → v7 修复记录):
>
> *Blocker 级*:
> 1. **补抽取失败补偿路径** — 新增 `extraction.failed/extraction.retry_scheduled/extraction.dead_lettered`;Extractor 对 `evidence.appended` 失败不再静默丢失(§5.1/§5.3/§14)
> 2. **补 outbox dispatcher checkpoint 与业务幂等** — 新增 `consumer_checkpoint`、subscriber inbox、业务幂等窗口;`commitment.fire` 等事件重复投递不重复提醒(§5.4)
> 3. **补 crypto_erasure 传播语义** — Drawer 擦除后 Statement evidence 引用保留但标记 erased;只传播到直接依赖且无独立证据的 Statement,不递归误删整条认知链(§3.8/§10.4)
>
> *Major 级*:
> 4. **热路径索引策略** — P2 不在主 Statement 表堆复合索引;新增 Retrieval 专用投影索引,按 holder/state/time/salience/vector 分通道维护(§4.1/§13.4/§16.1)
> 5. **Container 细粒度版本** — Persona/CommonGround 增加维度级 version/sequence,降低多人协作 CAS 冲突(§5.5)
> 6. **Conflict 等级化** — `direct_contradiction / partial_overlap / superseding / adjacent` 四级冲突,明确时间区间 overlap 处理(§5.2/§7.3)
> 7. **ToM 派生链限流** — `tom_inferred` Replay 降权公式化;derivation_chain 超阈值时暂停 ToM 增量推断,防止 ToM→Replay→Persona→ToM 多层环路(§3.10/§5.4/§9.2/§10.2)
> 8. **P0 增加最简 Retrieval** — P0 交付必须包含单 holder、单 intent、无 rerank 的写入→巩固→检索闭环(§13.4/§16.1)
>
> *Minor 级*:
> 9. **迁移路径细化** — memU Drawer 底座需补 per-record key/refcount;Graphiti episode-first 与 Starling statement-first 不能简单一对一映射;Letta Identity 可作为 Cognizer 基类参照(§16.2/§20)
> 10. **附录 A 评分降噪** — 将"认知层成熟度合计"改为定性成熟度,避免把 🟡 半支持与 ✅ 完整支持等同计分(附录 A)
>
> **v6 相对 v5 的修复**(详见 §17.5 v5 → v6 修复记录):
>
> *Blocker 级*:
> 1. **Drawer 合规生命周期重写** — 不再笼统要求"原档永不删",改为 `retention_mode ∈ {legal_hold,audit_retain,redacted_retain,crypto_erasure}`;FORGOTTEN 必须支持内容不可恢复,只保留 hash/审计元数据(§3.8/§6.0/§10.4)
> 2. **Bus 事务投递语义** — `Bus.write` 明确为 storage transaction + durable outbox append;事件至少一次投递,Subscriber 按 `idempotency_key` 幂等消费,避免写入成功事件丢失或事件先发后回滚(§5.0/§5.4)
>
> *Major 级*:
> 3. **状态枚举冻结为六个物理状态** — `VOLATILE / REPLAYING_CONSOLIDATING / REPLAYING_RECONSOLIDATING / CONSOLIDATED / ARCHIVED / FORGOTTEN`;不再口头保留五态(§0/§3.4)
> 4. **派生候选状态补齐** — 新增 `review_status` 表达 `PENDING_REVIEW`/`APPROVED` 等,解决 replay_derived 直入 CONSOLIDATED 与 Norm/Skill 候选待确认的冲突(§3.2/§3.10/§10.3)
> 5. **provenance 语义扩展** — 新增 `reconsolidation_derived`;severe correction 不再误标为 `tom_inferred`(§3.10/§11.2)
> 6. **Reconsolidation severe path 原子化** — 新版写入、旧版归档、supersedes 边、事件 outbox 在同一事务提交(§11.2)
> 7. **Container 更新契约** — Persona/CommonGround 默认定义为 StatementRefs 的物化视图;更新走 `Bus.rebuild_container` + `container.rebuilt` 事件,CAS 防并发覆盖(§3.6/§5.5/§10.3)
> 8. **Conflict/幂等 key 规范化** — key 包含 `holder + modality + subject + predicate + canonical_object + temporal_interval + scope`,避免不同 object/deadline/scope 被误合并(§5.2/§5.4)
>
> *Minor 级*:
> 9. **补 `commitment.withdrawn` 事件** — WITHDRAWN 终态可订阅,用于 Trigger 清理、归档释放与画像候选(§5.3/§12.2)
> 10. **Drawer 写入纳入 Bus 边界** — 端到端流程改为 `Bus.append_evidence`,统一权限、source trust、retention、审计和幂等(§5.0/§6.0/§14)
> 11. **schema/视图一致性修复** — `EpisodicView` 改为 `event_time IS NOT NULL OR type=EpisodicEvent OR EXISTS OBSERVED_BY`;修正文案中 subject/object 对 StatementRef 的不一致;补 `review_status` 字段(§3.1/§3.2/§3.5)
> 12. **路线图口径修正** — P2 不再写"物理分表",改为"逻辑分区标签 + 可选物理投影/索引"(§16.1)
>
> **v5 相对 v4 的修复**(详见 §17.4 v5 修复记录):
>
> *Blocker 级*:
> 1. **明确三层抽象** — 逻辑层(Statement schema)/分区层(逻辑分区,§6/§7)/物理层(Substrate Adapter,§4) 边界(§3 重写)
> 2. **定义 Statement 写入路径分类**(§3.10 新增) — 用户输入 / Replay 派生 / ToM 推断 三类,每类的 Bus 处理规则、是否触发再 Replay 明确,杜绝 §10.3 输出循环
>
> *Major 级*:
> 3. **重画 §3.4 状态机** — 补 4 条迁移边(CONSOLIDATED→REPLAYING、REPLAYING→ARCHIVED、REPLAYING→CONSOLIDATED 含确认路径、ARCHIVED→REPLAYING 召回归档)
> 4. **拆分 REPLAYING 子态** — `REPLAYING_CONSOLIDATING`(VOLATILE→) vs `REPLAYING_RECONSOLIDATING`(CONSOLIDATED→)
> 5. **Drawer 提升为独立子系统** — 从 §6.1 Hippocampus 内部分层中移出,与 Hippocampus/Neocortex 平级(§6.0 新增)
> 6. **§5.3 Bus 事件表补 5 个终态事件** — `statement.archived/forgotten/derived` + `commitment.fulfilled/broken/renegotiated`
> 7. **加防抖与幂等契约**(§5.4 新增) — 同 (subject, predicate) 的事件 N 秒内合并;递归深度 ≤ 3
> 8. **Retrieval 读副作用解耦**(§13.0 新增) — Retrieval 只 emit `statement.recalled`,Reconsolidation 异步决定开窗
> 9. **修正 EpisodicView 定义** — 去掉 consolidation_state 限定(§3.5)
> 10. **§12 PolicyEngine ↔ Bus 关系显式化**
>
> *Minor 级*:
> 11. **m1-m5** — Affect Buffer/Replay 边界、Working Set/Persona 边界、Statement vs Container 二分、EntityRef 类型定义、Commitment 细节(BROKEN→RENEGOTIATED 允许)
>
> **沿袭 v5 的设计本体**:
> - 三条公理 + 12 层架构 + Statement 中心数据模型
> - 7 步 Retrieval Planner + 8 标签 Context Pack
> - Commitment 状态机 + 4 类 Trigger
> - AffectVector 五维 + salience 显式公式
> - Substrate Adapter 5 profiles
> - 9 项目能力对照表 + "为什么更懂人"的认知科学解释
> - 8 篇 2026 前沿论文引用 + A-ToM (§9.6) + Episodic Knowledge Binding (§6.2) + Governing Evolving Memory 三 trade-off (§19)

---

## 0. 摘要(One Page)

**Starling v14 解决一个问题**:让 LLM Agent 像人一样,**对每个交互对象都形成一份"持续演化的他者画像 + 我对他的信念 + 我以为他相信什么"**,并且这套画像在系统层面具备类脑的"快写慢洗、优先重放、再巩固、自适应遗忘、显著性调制、前瞻触发"动力学,而不是停在"user_id 隔离 + 向量库 RAG"这种工程层抽象上。

**v11 新增的工程闭环**:9 个开源库源码显示,成熟记忆系统的失败点很少是"缺一个抽象名词",更多是队列积压、抽取失败、投影落后、租户泄露、检索污染、后台任务重启等运行时缝隙。v11 因此把 `RuntimeHealth / PipelineRun / RetrievalReceipt / ProfileCapability` 写入主契约,确保 Starling 不只是一套本体,也是一套可运行、可观测、可恢复的施工蓝图。

**v12 新增的工程防线**:进一步复审源码后可以看到,线上事故还常发生在更低层的"边界未声明":内部 agent 输出被自己记住、service 层过滤遗漏导致跨租户查询、source adapter 悄悄改写原文、索引修复从损坏视图回灌而误删真实数据、检索结果没有说明"够不够回答"。v12 因此把 `SourceAdapterContract / SelfPollutionGuard / storage-enforced tenant isolation / ScopedWorkGate / Retrieval sufficiency / TraceRetentionTier` 固化为契约。

**v13 新增的执行锚点**:第三轮源码复审显示,许多成熟库的可靠性来自"每个中间产物都有来源、时间锚、范围计划和失败策略":mem0 把 Observation Date 与 Current Date 分开;Graphiti 把抽取事实绑定 episode index/reference_time;cognee/memU 在检索中逐层扩展并做 sufficiency 判断;Letta 用 ToolRulesSolver 约束动作序列。v13 因此把 `SourceSpanRef / TemporalAnchor / RetrievalScopePlan / PipelineStepContract.failure_policy / ActionPolicyGraph / idx_entity_statement` 写入主契约。

**v14 新增的整合原则**:吸收开源库优点不是把 9 套概念并列进 Starling。任何外部机制进入设计前必须先回答:它映射到哪个 Starling 原生原语?它是否新增了第二套事实源、第二套生命周期、第二套权限边界?如果答案不清楚,只能留在 adapter metadata 或 §20 参考表,不能进入核心 schema。

**七大差异点**(在主流开源项目集体缺失之处,v4 更新):
1. **Cognizer 一等公民**:认知主体而非 user_id 字段。
2. **Statement 替代 Fact**:所有写入都是"谁,在何时,基于何证据,对谁,以何样态、何极性,持有何判断"。
3. **二阶 ToM 数据模型**:嵌套 Statement + nesting_depth + 自适应 ToM order(§9.6 A-ToM)。
4. **类脑六态状态机**:`consolidation_state ∈ {VOLATILE, REPLAYING_CONSOLIDATING, REPLAYING_RECONSOLIDATING, CONSOLIDATED, ARCHIVED, FORGOTTEN}` 贯穿全生命周期。
5. **Reconsolidation 不覆盖**:被回忆即开启可塑窗口,旧版本进 supersedes 链而非删除。
6. **真前瞻**:Trigger 类型化 + Commitment 五态机。
7. **视角化检索 + 心智摘要输出**:Retrieval Planner 9 Intent × Perspective Filter × Affect Reranker × Context Pack Builder × **Mentalizing Primitives**(7 高阶认知原语)。

**关键非目标**:不重写向量库、不做训练、不追求形式化完备。Starling 是数据模型 + 运行时调度 + 检索规划器,可挂在 mem0 / Letta / cognee / Graphiti 之上。

### 0.1 外部机制吸收原则(v14 新增)

9 个开源库提供的是经验样本,不是 Starling 的第二套架构。后续任何复用都必须满足四条收敛规则:

1. **原生原语优先**:外部概念只能映射到 `Statement / DrawerRecord / BusEvent / PipelineRun / RetrievalScopePlan / ActionPolicyGraph / Projection Index / Container` 之一。不能因为某库有 `episode/session/block/memory/tool_rule` 就在 Starling 核心层新增同名一等实体。
2. **权威事实源唯一**:事实权威只在 Statement 图;DrawerRecord 是证据源,Container/Projection/RetrievalReceipt/PipelineRun 都是物化视图或运行账本,不得反向成为事实源。
3. **生命周期唯一**:异步任务终态以 `PipelineRun.status` 为权威;抽取、投影、Replay、Compliance 的子明细只能作为 run item 或 event payload,不能各自定义互相冲突的状态机。
4. **边界不外溢**:外部库的 scope/step/action 名字只能出现在 Adapter 层 metadata;Starling 核心只使用自己的 scope、event、policy 和 state 枚举。

---

## 1. 三条公理

### 公理 I:**没有孤立的事实,只有归属于主体的陈述**

每条记忆必须是 `Statement(holder, subject, predicate, object, modality, polarity, time, evidence, confidence)`。这一条同时解决:归属、冲突、撤回、视角、二阶 ToM。

### 公理 II:**记忆系统由两套时间尺度的子系统协同 —— 海马式快、新皮层式慢(CLS)**

写入先入 Hippocampus(`VOLATILE`),经 Replay(`REPLAYING`)、模式分离/补全、再巩固(`CONSOLIDATED`),才有机会上升到 Neocortex 稳定语义/规范/技能/画像。

### 公理 III:**记忆为当前目标重构,不是录像回放(Conway SMS)**

检索不是 fan-out 工具堆,而是按 `(querier, perspective, intent, goal)` 重构出的视角化心智摘要,且具备显式 abstention。

---

## 2. 系统总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Starling Memory Runtime v14                        │
│                                                                         │
│  ┌────────────────┐                          ┌────────────────────┐    │
│  │  Cognizer Hub  │ ◄──── 视角/信念 ────►    │   ToM Engine       │    │
│  │ (主体 + 画像   │                          │  (Belief Tracker + │    │
│  │  + trust)      │                          │   Mentalizing API) │    │
│  └────────┬───────┘                          └─────────┬──────────┘    │
│           │                                            │               │
│           ▼                                            ▼               │
│  ┌──────────────────── Statement Bus(总线) ──────────────────────┐  │
│  │ (Validator + Conflict Probe + Transactional Outbox)             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│       ▲                          │                                    │
│       │ 写入                     ▼ 检索/注入                          │
│  ┌───────────────┐         ┌─────────────────────────┐                │
│  │ Hippocampus   │ ─重放─► │      Neocortex          │                │
│  │ ─────────     │ ◄补全── │ ──────────────────      │                │
│  │ • Episodes    │         │ • Semantic(holder图族)  │                │
│  │ • Working Set │         │ • Procedural(Skills)    │                │
│  │ • Affect Buf  │         │ • Norms                 │                │
│  └───────┬───────┘         │ • Personae(物化视图)    │                │
│          │                 │ • CommonGround(物化视图)│                │
│          │                 └────────────┬────────────┘                │
│       │                                  │                            │
│       ▼                                  ▼                            │
│  ┌───────────────────────────────────────────────────────────┐        │
│  │ Replay Scheduler + Reconsolidation + Prospective Loop     │        │
│  │ (优先级重放 + 可塑性再巩固 + 承诺触发 + 自适应遗忘)         │        │
│  └───────────────────────────────────────────────────────────┘        │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────┐        │
│  │ Perspective-aware Retrieval Planner                       │        │
│  │ (9 Intent → Multi-Channel → Perspective Filter →          │        │
│  │   Affect Reranker → Context Pack Builder + Abstention)    │        │
│  └───────────────────────────────────────────────────────────┘        │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────┐        │
│  │ Substrate Adapter:Vector / Graph / KV / Drawer / Git      │        │
│  │ (5 profiles:local-lite / local-graph / cloud-graphiti /   │        │
│  │   letta-bridge / cognee-bridge)                           │        │
│  └───────────────────────────────────────────────────────────┘        │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────┐        │
│  │ Runtime Governance:Health / Backpressure / Run Ledger     │        │
│  │ (Profile preflight + queue gates + checkpoints + receipts)│        │
│  └───────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
```

**13 个层级**(下文逐节展开):
1. Substrate Adapter — 底层存储抽象(§4)
2. Statement Bus — 全局陈述总线(§5)
3. Hippocampus — 快记忆(§6)
4. Neocortex — 慢记忆(§7)
5. Cognizer Hub — 主体画像与边界(§8)
6. ToM Engine — 多阶信念追踪 + Mentalizing API(§9)
7. Replay Scheduler — 优先级重放(§10)
8. **Reconsolidation Engine** — 被回忆即可塑(§11)
9. Prospective Loop — 承诺与触发器(§12)
10. Retrieval Planner — 视角感知检索 + 心智摘要(§13)
11. Runtime Governance — 健康、背压、长任务账本、检索回执(§4.0/§5.6/§13.6.1)
12. 端到端数据流(§14)
13. 评测、路线图、取舍、风险、复用对照、变更记录、致谢(§15-§21)

---

## 3. 数据模型(本体层)

> **设计原则(v6:三层抽象 + 可执行契约)**:
>
> 1. **逻辑层**(本节 §3):所有可写入的"陈述"都是 `Statement` 或其子类(灵感:cognee DataPoint Annotated 子类化);所有"容器型实体"(Persona / CommonGround / KnowledgeFrontier)继承 `Container`,装载 Statement 但本身不是 Statement。**Statement vs Container 是基础二分**。v6 明确 Container 默认是 StatementRefs 的物化视图,更新经 Bus 契约,不允许绕过事务边界直接改。
> 2. **分区层**(§6 Hippocampus / §7 Neocortex):**逻辑分区**而非物理分表 —— 用 `consolidation_state + modality + index_tags` 标签区分,同一物理表多分区共存。VOLATILE → CONSOLIDATED 是**状态字段 + 索引标签变更**,不是表迁移。
> 3. **物理层**(§4 Substrate Adapter):决定实际存储底座(Vector / Graph / KV / Drawer / KV-cache)。逻辑层与分区层不感知物理底座。
>
> **五类记忆是 Statement 上的视图**(吸收 Polis §3.3),由谓词 (modality)、时间字段、状态字段联合定义,见 §3.5。

### 3.1 Cognizer:认知主体

```python
class Cognizer(BaseEntity):
    id: UUID                                # UUID5 from (kind, external_id)
    kind: Literal["self","human","agent","group","role","external"]
    canonical_name: str                     # 规范名(v2 新增)
    aliases: list[str]                      # "老张" / "Zhang Wei" / "user_42"  (v2 新增)
    external_id: str                        # 跨系统稳定 id
    persona: PersonaRef                     # 长期画像(慢通道,见 §3.6)
    knowledge_frontier: KnowledgeFrontier   # 知识边界
    relations: list[RelationEdge]           # 与其他 Cognizer 的关系
    trust_priors: dict[CognizerId, float]   # 该主体对他人的先验信任 (v2 新增)
    permissions: AccessPolicy
    created_at: datetime
    last_seen_at: datetime
```

**关键差异**:
- `aliases / canonical_name` 解决跨数据源主体归一(吸收 Polis);
- `trust_priors` 是该主体**对他人**的信任先验(注意:不是系统对他的信任),用于在该主体作为 holder 持有"X 说 Y 这件事"时,系统可以在他的视角下评估证据可信度。
- `kind` 分类受益于 mempalace v3.3.4 corpus origin 检测 —— 自动识别"对话型语料 vs 文档型语料",区分 AI persona 名与人类名(v4 新增引用)。

**Entity:非 Cognizer 实体(v5 新增,补 m4 漏洞)**

```python
class Entity(BaseEntity):
    id: UUID                                # UUID5 from (kind, canonical_name)
    kind: Literal["concept","artifact","place","event","organization","project","other"]
    canonical_name: str
    aliases: list[str]
    type_tags: list[str]                    # 自由标签
    created_at: datetime
```

`EntityRef` 是 `Entity.id` 的引用。Statement.subject 接受 `CognizerRef | EntityRef`;Statement.object 接受 `Value | EntityRef | CognizerRef | StatementRef`。`StatementRef` 只出现在 object/derived/supersedes 等引用位,用于二阶 ToM 嵌套(§3.2),**subject 不直接引用 Statement**,避免查询键不可规范化。Entity 注册由 Cognizer Hub 的 NER 流程 + alias 归一负责(§8.1 discover 阶段),与 Cognizer 共享 alias 算法但**Entity 无 persona / KnowledgeFrontier / trust_priors**(它不是认知主体)。

### 3.2 Statement:核心原子

```python
class Statement(BaseEntity):
    id: ULID
    # —— 主体维度 —— 
    holder: CognizerRef                     # 谁持有
    holder_perspective: Perspective         # FIRST_PERSON | QUOTED | INFERRED | HEARSAY (v2 新增)
    # —— 内容维度 —— 
    subject: CognizerRef | EntityRef
    predicate: PredicateURI                 # 受控核心集 + 可扩展
    object: Value | CognizerRef | EntityRef | StatementRef  # StatementRef 仅在 object 位递归 → 二阶 ToM
    modality: Modality                      # 见 §3.3
    polarity: Literal["POS","NEG","UNKNOWN"]   # v2 新增,与 modality 正交
    confidence: float                       # 0..1
    # —— 时间维度(5 种,v2 补全) —— 
    event_time: Optional[TimeRange]         # 事件本身发生
    observed_at: datetime                   # 写入时观察到
    inferred_at: Optional[datetime]         # v2 新增:系统推断时刻
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    # —— 证据与归因 —— 
    evidence: list[EvidenceRef]             # 直接抽取必填;派生可由 derived_from/evidence_chain 追溯
    source_spans: list[SourceSpanRef]        # 直接抽取的 Drawer 片段锚;派生仅作 supporting spans
    temporal_anchor: TemporalAnchor          # 相对时间解析锚,默认来自 source_span 或 derived_chain
    derived_from: list[StatementRef]        # 推断链
    perceived_by: list[CognizerRef]         # 信息可见性(谁在场/被告知)
    supersedes: Optional[StatementRef]
    # —— 类脑动力学 —— 
    salience: float                         # 显著性
    affect: AffectVector                    # (valence, arousal, dominance, novelty, stakes)
    activation: float                       # 当前激活水平
    last_accessed: datetime
    access_count: int
    last_replayed: Optional[datetime]       # v3 新增:Replay Scheduler 上次采样
    replay_count: int = 0                   # v3 新增:已被重放次数
    consolidation_state: ConsolidationState  # v2 新增,见 §3.4
    review_status: ReviewStatus             # v6 新增,见 §3.10:派生候选/低置信抽取的审核态
    provenance: StatementProvenance          # v6 扩展,见 §3.10
    derivation_chain: list[StatementRef]     # Replay/再巩固派生链;比 derived_from 更窄
    nesting_depth: int                      # 嵌套深度(0=一阶,1=二阶,2=三阶)
    # —— 治理 —— 
    visibility: VisibilityScope
    retention_policy: RetentionPolicy
```

`evidence` 指向"哪条 DrawerRecord 可审计";`source_spans` 指向"这条 Statement 从 DrawerRecord 的哪个片段/episode/segment 抽出"。两者都要保留:一个 DrawerRecord 可包含多轮消息、多段文档或多 episode,只靠 `chunk_index` 不足以表达 Graphiti `episode_indices`、memU segment resource URL、mem0 Observation Date 这种片段级时间锚。

**证据锚适用范围(v14 收敛)**:
- `provenance=user_input` 且直接由 DrawerRecord 抽取的 Statement,必须有 `evidence ≥1`、`source_spans ≥1`、`temporal_anchor`。
- `provenance=replay_derived / tom_inferred / reconsolidation_derived` 的 Statement 可以没有直接 `source_spans`,但必须有 `derived_from` 或 `evidence_chain` 能追溯到原始 DrawerRecord;不得把摘要、Container payload 或推断结果伪装成直接原文 span。
- 派生 Statement 若聚合多个源 span,`source_spans` 仅表示"supporting spans",不表示逐字抽取位置;此时 `temporal_anchor.resolved_by` 必须为 `metadata/adapter/llm` 之一并标 `confidence`。
- 高影响派生(norm/persona_trait/commitment correction)若没有可追溯 evidence chain,只能 `review_status=PENDING_REVIEW/REVIEW_REQUESTED`,不能自动 `APPROVED`。

`evidence_chain` 是由 `derived_from` 递归展开得到的可计算闭包,不是 Statement 的新增存储字段。实现可缓存它,但缓存失效和重建必须由 Statement 主表 + SUPERSEDES/derived_from 边驱动。

```python
class SourceSpanRef(BaseModel):
    drawer_ref: DrawerRef
    chunk_index: int
    span_start: Optional[int]                # byte/char offset,由 adapter 声明单位
    span_end: Optional[int]
    segment_id: Optional[str]                # 如 resource#segment_3 / episode uuid
    source_role: Optional[Literal["user","assistant","tool","system","document"]]
    source_speaker: Optional[CognizerRef]
    observed_at: datetime                    # 该片段被观察/发生的时间,可不同于 DrawerRecord.timestamp
    source_hash: str                         # 片段级 hash,用于重抽/擦除传播

class TemporalAnchor(BaseModel):
    anchor_kind: Literal["source_span","episode","drawer_record","message","document","derived_chain","system_now"]
    anchor_time: datetime
    timezone: Optional[str]
    confidence: float
    resolved_by: Literal["metadata","adapter","llm","fallback"]
```

时间规则:
- relative time(`today/yesterday/recently/next month`) 必须按 `TemporalAnchor.anchor_time` 解析,不得使用系统当前时间兜底,除非 `anchor_kind=system_now` 且 `review_status=INFERRED_UNREVIEWED`。
- 多片段合并 Statement 若 span 的 `observed_at` 不一致,必须保留多个 `source_spans`,并把 `event_time/valid_from/valid_to` 标为区间或进入 `REVIEW_REQUESTED`。
- `source_spans` 中的 `source_speaker` 是归因字段,与 `holder` 一起构成审计面;纠错时新建 Statement,不能原地覆盖。

**`object` 可递归引用 Statement** —— 二阶 ToM 的天然承载。例:

```
S1: holder=Alice, predicate=BELIEVES, polarity=POS, object=
    S2: holder=Bob, predicate=KNOWS, polarity=POS, object=
        S3: subject=Project_X, predicate=delayed, polarity=POS
```

读作:Alice 相信 Bob 知道项目 X 延期了。

### 3.3 Modality(11 类,BDI + 规范 + 撤回)

```
BELIEVES   — A 相信(可错)
KNOWS      — A 知道(蕴含真;默认转 BELIEVES,慎用)
ASSUMES    — A 假设(置信低)
DOUBTS     — A 怀疑
DESIRES    — A 想要
INTENDS    — A 计划
COMMITS    — A 承诺(进入 Prospective Loop)
PREFERS    — A 偏好 X 胜过 Y
NORM_OUGHT — 应当
NORM_FORBID— 禁止
RECANTED   — 撤回(供 supersedes 链)
```

**polarity 与 modality 正交**(吸收 Polis):
- `BELIEVES + POS`:相信 X 成立
- `BELIEVES + NEG`:相信 X 不成立
- `DOUBTS + POS`:怀疑 X 成立
- `KNOWS + UNKNOWN`:知道某事但不知其值(如"知道有人偷了车,但不知是谁")

### 3.4 ConsolidationState 状态机(v6 冻结为六个物理状态)

> **v6 决策**:实现层不再使用抽象 `REPLAYING` 主状态。`ConsolidationState` 冻结为六个物理枚举值:`VOLATILE / REPLAYING_CONSOLIDATING / REPLAYING_RECONSOLIDATING / CONSOLIDATED / ARCHIVED / FORGOTTEN`。若产品界面需要"五类生命周期"展示,只能在 UI 层把两个 REPLAYING_* 聚合显示为 Replay,不能污染 schema/查询/事件表。

```
                          ┌─── reconsolidate confirm ───┐
                          │                             │
                          │   ┌─── recall/conflict ────┐│
                          │   │                        ││
   write   ┌──────────┐   │   │  ┌─────────────────┐   ││  ┌──────────────┐
   ────►   │ VOLATILE │── replay──►│ REPLAYING_     │── commit ──►│            │
           └──────────┘            │ CONSOLIDATING  │             │CONSOLIDATED│
                                   └─────────────────┘    ┌─────► │            │
                                                          │       └────┬─┬─────┘
                                                          │            │ │
                                ┌─── recall/conflict ◄────┘            │ │
                                │                                      │ │
                                ▼                                      │ │
                       ┌──────────────────────┐                       │ │
                       │ REPLAYING_           │── confirm ────────────┘ │
                       │ RECONSOLIDATING      │                          │
                       └──────────┬───────────┘                          │
                                  │                                      │
                                  │ contradict-severe                    │ decay
                                  │  (旧版进归档,新版另立)                │
                                  ▼                                      ▼
                                                                  ┌──────────┐
                                                                  │ ARCHIVED │◄── purge ──┐
                                                                  └────┬─────┘            │
                                                                       │                  │
                                                                       │ recall(已归档)   │
                                                                       │                  │
                                                                       └──► REPLAYING_RECONSOLIDATING
                                                                            (重新激活到再巩固通道)

                                  ┌──────────────────┐
                                  │ ARCHIVED         │── purge (合规/失效) ──► FORGOTTEN
                                  └──────────────────┘                       (Drawer 按 retention_mode 处理)
```

**状态语义(v6 完整)**:
- `VOLATILE`:刚写入海马分区,未巩固;
- `REPLAYING_CONSOLIDATING`:由 Replay Scheduler 选中(自 VOLATILE),目的是**首次巩固进新皮层语义层**;
- `REPLAYING_RECONSOLIDATING`:由 Retrieval/ConflictProbe/displayed-edit 触发(自 CONSOLIDATED 或 ARCHIVED 召回),目的是**已有版本的再巩固/修正**(Nader 2000);
- `CONSOLIDATED`:已沉到新皮层语义层,长期可查;
- `ARCHIVED`:长期未召回,从热路径移除但保留索引可被召回回到 REPLAYING_RECONSOLIDATING;
- `FORGOTTEN`:Statement 从热/冷检索路径移除;Drawer 内容按 `DrawerRetentionMode` 执行 redaction 或 crypto erasure,不再默认保留 verbatim。

**迁移表(v5 新增,完整列举)**:

| 源态 | 目标态 | 触发条件 | 关闭者(close 窗口者) |
|---|---|---|---|
| `(create)` | VOLATILE | Bus.write 完成 Validator | 即时(无窗口) |
| VOLATILE | REPLAYING_CONSOLIDATING | Replay Scheduler 采样命中 | Replay Scheduler |
| REPLAYING_CONSOLIDATING | CONSOLIDATED | Replay 巩固原子操作完成 commit | Replay Scheduler |
| REPLAYING_CONSOLIDATING | VOLATILE | Replay 决策保留(证据不足) | Replay Scheduler |
| CONSOLIDATED | REPLAYING_RECONSOLIDATING | Retrieval 召回 / ConflictProbe 标冲突 / 显式 reconsolidate API | 可塑窗口超时(默认 30min,自适应 5min-6h) |
| REPLAYING_RECONSOLIDATING | CONSOLIDATED | reconsolidate confirm(支持/轻微反对) | 可塑窗口超时 |
| REPLAYING_RECONSOLIDATING | ARCHIVED | reconsolidate contradict-severe(旧版作废,新版另立) | 可塑窗口超时 |
| CONSOLIDATED | ARCHIVED | decay 公式判定(§10.4)且不在 CommonGround | Replay Scheduler 周期触发 |
| ARCHIVED | REPLAYING_RECONSOLIDATING | 归档 stmt 被召回 / 显式 audit | 可塑窗口超时 |
| ARCHIVED | FORGOTTEN | 显式 purge(合规/法务) | 即时 |

**迁移例外**:
- `CONSOLIDATED → ARCHIVED` 的 decay 路径**不适用于 CommonGround 中条目**:已 grounded 的共识衰减极慢(§10.4 公式中 `is_grounded` 因子放大 S0)。
- 任何 Commitment 状态非 FULFILLED/WITHDRAWN 时**不允许进入 ARCHIVED**(承诺必须留在热路径直到结清)。
- ARCHIVED 召回路径:仅当原 stmt 的 `salience > θ_revive` 或 audit 显式触发,普通低 salience 召回不重新激活。

### 3.5 五类记忆作为视图(v6 修正:统一基类字段)

> **v5 修复**:v4 把 EpisodicView 限定 `consolidation_state IN (VOLATILE, REPLAYING)` 违反 Tulving 1985 —— Episodic 与 Semantic 的区分**不依赖巩固阶段**而依赖"是否绑定具体时空"。人类巩固后的自传体记忆显然仍是 Episodic。v5 修正定义。

```
EpisodicView   = WHERE event_time IS NOT NULL
                    OR type = "EpisodicEvent"
                    OR EXISTS edge(kind="OBSERVED_BY")
                 # 不限 consolidation_state — Episodic vs Semantic 由"绑时空"区分
SemanticView   = WHERE modality IN (KNOWS, BELIEVES) 
                       AND event_time IS NULL  
                       AND consolidation_state IN (CONSOLIDATED, ARCHIVED)
                       AND |evidence| ≥ N
                 # 时空脱钩 + 多证据 + 已巩固
ProceduralView = WHERE predicate IN skill_predicates AND linked Procedure
WorkingView    = WHERE activation > θ_w AND last_accessed within session
ProspectiveView= WHERE modality IN (INTENDS, COMMITS) AND valid_from > now()
```

**好处**:同一事件可以同时落在多个视图。"Alice 上周答应给我看代码"刚说完时是 Episodic + Prospective;Alice 真看了之后 Commitment 状态 → fulfilled,Episode 仍存(无论 CONSOLIDATED 还是 ARCHIVED);若反复发生类似承诺,可凝结出 Semantic 命题"Alice 习惯口头答应但需提醒"(此时同一时间锚的事件本身仍在 Episodic)。

### 3.6 子类(Statement 的特化)

```python
class EpisodicEvent(Statement):
    modality: Literal["BELIEVES"] = "BELIEVES"
    participants: list[CognizerRef]
    location: Optional[Place]
    raw_drawer_ref: DrawerRef
    boundary_score: float                  # EM-LLM 惊奇度

class Commitment(Statement):
    modality: Literal["COMMITS"] = "COMMITS"
    principal: CognizerRef
    beneficiary: CognizerRef
    trigger: Trigger                       # §12.1
    deadline: Optional[datetime]
    state: Literal["ACTIVE","FULFILLED","BROKEN","RENEGOTIATED","WITHDRAWN"]  # v2 增 RENEG

class Norm(Statement):
    modality: Literal["NORM_OUGHT", "NORM_FORBID"]
    scope: NormScope                       # group/1-1/role
    deontic_strength: float
    enforcement_history: list[EpisodicEventRef]   # v2 新增:被违反/重申的历史

class Skill(Statement):
    modality: Literal["KNOWS"] = "KNOWS"
    procedure: ProcedureSpec
    success_pattern: list[CaseRef]
    maturity: float

class Persona(Container):                  # v5: Container 基类,装载 Statement 但本身不是 Statement
    cognizer: CognizerRef
    traits: dict[str, TraitValue]          # OCEAN / 自定义
    preferences: list[StatementRef]
    competencies: list[StatementRef]
    values: list[StatementRef]
    self_model_anchor: list[StatementRef]  # 该主体对自己的陈述(v2 吸收 Polis)
    profile_anchor: list[StatementRef]     # 他人对该主体的陈述(v2 吸收 Polis)
    relationship_styles: dict[CognizerRef, FiskeMode]

class CommonGround(Container):              # v5: Container 基类
    parties: tuple[CognizerRef, ...]       # 支持 N 元(v2 扩展)
    grounded: list[StatementRef]           # 双方都知道双方都知道
    asserted_unack: list[StatementRef]     # 一方说了对方未确认
    suspected_diverge: list[StatementRef]  # 怀疑对方实际相信不同
    establishment_evidence: list[EpisodicEventRef]  # v2 新增:建立时机
```

### 3.7 关键边类型(社会图谱,v2 完整,v4 增 HyperMem hyperedge 参照)

| 边 | 含义 | 语义 |
|---|---|---|
| `BELIEVES_ABOUT` | 主体 → 关于另一主体的信念集 | Alice → Bob 的画像 |
| `TRUSTS` | 加权信任,带情境 | Alice -[trust=0.8 ctx=tech]→ Bob |
| `COMMITTED_TO` | 主体 → 承诺(指 Commitment) | Bob -[deadline=...]→ S(ship_v2) |
| `CONFLICTS_WITH` | 两 Statement 矛盾 | S1 ⨯ S2,带 conflict_type |
| `EVIDENCE_FOR / AGAINST` | 证据关系 | Episode → Statement |
| `SHARED_GROUND` | N 主体共享的共同知识 | {A,B,C} → fact F |
| `OBSERVED_BY` | Episode → 观察者集合 | E → {A,B} |
| `PERCEIVED_BY` | Statement → 感知者集合(v2 强调) | 见 §3.2 字段 |
| `NORM_OF` | Group → Norm | Team -[since=...]→ norm_X |
| `INTENT_OF` | Cognizer → 当前/历史意图 | Alice -[active]→ goal_Y |
| `MAY_OVERLAP_WITH` | 模式分离软边(v2 显式) | 高相似但保留差异 |
| `SUPERSEDES` | 版本链 | S_new -[supersedes]→ S_old |

**v4 增——hyperedge 方向参照**:EverOS HyperMem (2026 ACL) 使用加权 hyperedge $w \in [0,1]$ 表达"多事实共属同一 episode"这种 N 元关系,而非逐对各建一条边。Starling 当前边类型表是二元的(Statement-to-Statement),N 元场景(如"Alice、Bob、Carol 三人在场共识了 X")需靠 CommonGround pool 间接承受。当共现场景常态化时,可引入 hyperedge 作为 `SHARED_GROUND` 的物理实现替代。见 §13.5 + §20。

### 3.8 Drawer:不可被静默覆盖的原档(v6:合规生命周期)

> **v5 修复**:v4 把 Drawer 既描述为"Statement.evidence 指向的独立 BlobStore"(§3.8)又描述为"Hippocampus 的内部分层"(§6.1)—— 不一致。v5 把 Drawer 定位为**与 Hippocampus / Neocortex 平级的全局 BlobStore 子系统**,见 §6.0。
>
> **v6 修复**:v5 的"Drawer 永不删"与用户撤回/法务 purge/retention_policy 冲突。v6 改为:Drawer 的**审计元数据 append-only**,但 verbatim 内容是否可恢复由 `retention_mode` 决定。

任何 Statement 的 `evidence` 必须指向 Drawer 中的原始证据片段。DrawerRecord 的 id/source/hash/audit log append-only,即使 LLM 抽取错误也能追溯;但当原文包含个人数据或敏感信息时,FORGOTTEN 不能只是"检索隐藏"。v6 要求每条 DrawerRecord 声明保留模式:

| `retention_mode` | 内容策略 | 适用场景 | FORGOTTEN 后 |
|---|---|---|---|
| `legal_hold` | 保留密文和密钥,禁止 purge | 法务保全/审计冻结 | 不可删除,但所有访问需审计 |
| `audit_retain` | 保留密文,按 retention_policy 到期处理 | 普通可审计日志 | 到期后转 `crypto_erasure` |
| `redacted_retain` | 原文替换为脱敏文本,保留 hash | 用户撤回但需解释历史决策 | 仅可恢复脱敏片段 |
| `crypto_erasure` | 销毁内容密钥,保留不可逆 hash/元数据 | 删除权/敏感信息 purge | 内容不可恢复 |

多 Cognizer 可共享同一 DrawerRecord(参考 Letta Archive 模型,§16.2),但共享记录的 purge 采用"最严格访问者 wins":任一主体触发 `crypto_erasure` 时,共享记录必须拆分引用或整体加密擦除,不能继续向其他 holder 暴露原文。

```python
class DrawerRetentionMode(str, Enum):
    LEGAL_HOLD = "legal_hold"
    AUDIT_RETAIN = "audit_retain"
    REDACTED_RETAIN = "redacted_retain"
    CRYPTO_ERASURE = "crypto_erasure"

class SourceKind(str, Enum):
    USER_INPUT = "user_input"
    EXTERNAL_DOC = "external_doc"
    TOOL_OBSERVATION = "tool_observation"
    SYSTEM_INTERNAL = "system_internal"
    OBSERVER_AGENT = "observer_agent"
    REPLAY_OUTPUT = "replay_output"

class IngestPolicy(str, Enum):
    STORE = "store"
    NO_STORE = "no_store"
    STORE_METADATA_ONLY = "store_metadata_only"
    REQUIRE_REVIEW = "require_review"

class DrawerRecord:
    id: UUID
    source: SourceRef
    source_kind: SourceKind                 # user_input / external_doc / tool_observation / system_internal / observer_agent / replay_output
    ingest_policy: IngestPolicy             # STORE / NO_STORE / STORE_METADATA_ONLY / REQUIRE_REVIEW
    adapter_name: Optional[str]
    adapter_version: Optional[str]
    ingest_mode: Literal["chunked_content","whole_record","metadata_only"]
    declared_transformations: list[str]     # 空集才可声明 byte_preserving
    privacy_class: Literal["public","internal","personal","sensitive","regulated"]
    byte_preserving: bool
    content_ciphertext: Optional[bytes]     # 可为 None:crypto_erasure 后不可恢复
    redacted_content: Optional[str]         # redacted_retain 使用
    content_hash: str                       # sha256/verifiable hash,永远保留
    retention_mode: DrawerRetentionMode
    key_ref: Optional[KeyRef]               # 内容密钥引用;crypto_erasure 后销毁
    chunk_index: int
    speaker: Optional[CognizerRef]
    timestamp: datetime
    source_time_range: Optional[TimeRange]   # v13:源记录覆盖的真实时间范围,可跨多消息/episode
    segment_map: list[SourceSegment]         # v13:片段级 offset/role/speaker/observed_at
    audit_trail: list[AuditEventRef]        # append-only
```

```python
class SourceSegment(BaseModel):
    segment_id: str
    chunk_index: int
    span_start: Optional[int]
    span_end: Optional[int]
    role: Optional[Literal["user","assistant","tool","system","document"]]
    speaker: Optional[CognizerRef]
    observed_at: datetime
    content_hash: str
```

SourceAdapter 若执行分块、转录、PDF 解析、episode 合并或 multimodal segment 提取,必须输出 `segment_map`。Extractor 只能引用 `segment_map` 中存在的片段生成 `SourceSpanRef`;不能凭 LLM 自造 offset/episode id。若 adapter 无法给出片段级时间,DrawerRecord.timestamp 可作为 fallback,但所有相对时间抽取默认 `review_status=INFERRED_UNREVIEWED`。

**crypto_erasure 反向传播(v7 新增)**:
- `Statement.evidence` 引用不删除,但对应 `EvidenceRef.status` 置为 `ERASED`,并保留 `content_hash` 与 `erased_at`。
- 直接由该 DrawerRecord 抽取且**没有其他未擦除 evidence**的 Statement 进入 `FORGOTTEN`。
- 直接 `derived_from / derivation_chain` 依赖上述 Statement 且**没有独立 evidence**的派生 Statement 进入 `REVIEW_REQUESTED` 或 `FORGOTTEN`(按影响级别),默认**只传播一层**,避免一次擦除误删整条认知链。
- 有独立未擦除 evidence 的 Statement 保留,但 confidence 下调并在 Context Pack 中标注"部分证据已擦除"。
- 传播过程经 Compliance Engine 事务写入 outbox:`evidence.erased` → `statement.forgotten` / `statement.review_requested`。

**SourceAdapter 与转换声明(v12 新增)**:
借鉴 mempalace RFC 002 的 source adapter contract,Starling 不再把"原文"当作所有入口的无条件承诺。每条 DrawerRecord 必须声明来源适配器、ingest mode 与转换列表:

| 字段 | 规则 |
|---|---|
| `adapter_name/adapter_version` | 写入源的稳定名称与版本;手写/API 直写也必须使用内置 `direct_api` adapter |
| `ingest_mode` | `chunked_content` 表示源内容分块;`whole_record` 表示一条源记录完整入 Drawer;`metadata_only` 表示内容由用户/adapter 合成,不可当 verbatim 证据 |
| `declared_transformations` | 记录 `utf8_replace_invalid/newline_normalize/strip_tool_chrome/tool_result_truncate/redaction/...`;不得应用未声明转换 |
| `byte_preserving` | 仅当 `declared_transformations=[]` 且 conformance test 证明输出等于源字节时为 true |
| `privacy_class` | adapter 默认隐私级别,可被 source policy 升级;影响 retention、trace retention 与 Drawer raw access |

`Statement.evidence` 引用 `metadata_only` Drawer 时,Context Pack 必须标 `evidence_kind=metadata_only`,不得把它包装成一手原文。若 adapter 声明 `declared_lossy`,Extractor 的 confidence 初值上限默认 0.8,除非另有独立 byte-preserving evidence 支持。

### 3.9 AffectVector(v2 五维)

```python
class AffectVector:
    valence: float    # -1..+1
    arousal: float    #  0..1
    dominance: float  # -1..+1   v2 新增,VAD 三轴完整
    novelty: float    #  0..1
    stakes: float     #  0..1

# 显著性(v2 公式)
salience = (0.4 + 0.6*|valence|) 
         × (0.4 + 0.6*arousal) 
         × (0.3 + 0.7*novelty) 
         × (0.3 + 0.7*stakes) 
         × (0.6 + 0.4*surprise_decay)      # 惊奇度(EM-LLM 风格)
```

salience 在三处生效:
1. **写入打分**:VOLATILE 入队优先级;
2. **重放采样**:Replay Scheduler 权重;
3. **检索重排**:Reranker 乘子。

### 3.10 Statement 写入路径分类(v6:provenance + review_status)

> **v4 缺口**:§10.3 巩固原子操作(compress / abstract / induce_norm / forge_skill)输出新 Statement,但写入路径未定 —— 走 Bus 会触发 Replay 形成无限循环;绕 Bus 又违反"所有读写必经 Bus"硬约束。v5 显式三分类。

**所有 Statement 按生成来源分四类**,每类 Bus 处理规则不同:

| 来源 | `provenance` | 默认入态 | 默认 `review_status` | 是否 emit `statement.written` | 是否被 Replay 重新采样 |
|---|---|---|---|---|---|
| **用户输入(直接观察)** | `user_input` | VOLATILE | `APPROVED` 或低置信时 `REVIEW_REQUESTED` | ✅ | ✅(默认) |
| **Replay 派生(compress/abstract 等)** | `replay_derived` | CONSOLIDATED(正式索引或 candidate index) | `APPROVED` / `PENDING_REVIEW` | ❌ emit `statement.derived` 替代 | ❌(避免循环) |
| **ToM 推断(perspective_take 等运行时算子产出)** | `tom_inferred` | VOLATILE | `INFERRED_UNREVIEWED` | ✅ 但带 `is_inferred=True` 标记 | ✅(允许),但 Replay 优先级降权 |
| **再巩固证据修正** | `reconsolidation_derived` | CONSOLIDATED(原子替换路径) | `APPROVED` 或 `REVIEW_REQUESTED` | ❌ emit `statement.corrected` 替代 | ❌(由 Reconsolidation 事务关闭,不再重放) |

**StatementProvenance / ReviewStatus**(v6):

```python
class StatementProvenance(str, Enum):
    USER_INPUT = "user_input"
    REPLAY_DERIVED = "replay_derived"
    TOM_INFERRED = "tom_inferred"
    RECONSOLIDATION_DERIVED = "reconsolidation_derived"

class ReviewStatus(str, Enum):
    APPROVED = "approved"                   # 可进入正常检索/巩固
    PENDING_REVIEW = "pending_review"       # 派生候选,需规则/人工确认
    INFERRED_UNREVIEWED = "inferred_unreviewed"
    REVIEW_REQUESTED = "review_requested"   # 低置信/敏感/高影响 statement
    REJECTED = "rejected"                   # 保留审计,不进入热检索
```

`replay_derived` 不再无条件等于"已稳定事实"。`compress` 这类摘要可直接 `APPROVED + CONSOLIDATED`;`induce_norm / forge_skill / persona_trait` 这类高影响派生默认 `PENDING_REVIEW`,在 Neocortex 中只作为候选索引,不进入普通 Retrieval 的 FACT/NORM/SKILL 输出,直到 confirm 后转 `APPROVED`。

**Bus 处理规则**(v6,与 §5.3/§5.4 事务 outbox 对齐):

```python
def Bus.write(stmt: Statement):
    Validator.check(stmt)                # XML/Schema/隐私边界/review_status
    ConflictProbe.scan(stmt)             # 冲突探针,用 canonical_conflict_key
    
    if stmt.provenance == "replay_derived":
        partition = Neocortex
        if stmt.review_status == "PENDING_REVIEW":
            partition.upsert(stmt, state=CONSOLIDATED, index_tag="candidate")
        else:
            partition.upsert(stmt, state=CONSOLIDATED)
        outbox.append("statement.derived", stmt)  # 不发 .written,避免 Replay 重入
    elif stmt.provenance == "reconsolidation_derived":
        raise UseReconsolidationTransaction  # severe correction 必须走 §11.2 原子事务
    else:
        partition = Hippocampus
        partition.upsert(stmt, state=VOLATILE)
        outbox.append("statement.written", stmt)
```

**Replay 订阅规则**(v5):
- Replay 仅订阅 `statement.written`,**不订阅 `statement.derived`**
- Replay 不订阅 `statement.corrected`
- 因此 Replay 自身产出的 `replay_derived` Statement 与 Reconsolidation 产出的 `reconsolidation_derived` Statement 不会触发新一轮 Replay,断开 §10.3/§11.2 → §5 → §10 循环
- `tom_inferred` 虽会 emit `statement.written`,但 Replay 采样权重必须乘以 `tom_inferred_factor=0.25`;若 `len(derivation_chain) >= 3` 或 `causation_chain` 已含 ToM→Replay→Container,ToM Engine 暂停对该链路增量推断,只保留显式查询时即时 perspective_take。

---

---

## 4. Substrate Adapter:不重造底座

Starling 是中间件而非新数据库。SubstrateAdapter 抽象 5 类底层能力:

| 能力 | 接口 | 推荐底座 |
|---|---|---|
| Vector | `embed / knn / hybrid_search` | Chroma / Qdrant / Milvus / Letta passages |
| Graph | `upsert_node / upsert_edge / cypher_query` | Neo4j / FalkorDB / Graphiti |
| KV / Doc | `put / get / cas / list_by_prefix` | SQLite / Postgres jsonb / Redis |
| Cache(KV-cache) | `store_kv / concat_kv / evict` | MemOS KVCache 风格 |
| BlobStore(Drawer) | append-only,不可覆盖 | S3 / 本地 fs / Letta archival |
| Projection Index | `upsert_projection / query_projection / invalidate_projection` | SQLite/Postgres projection tables / Qdrant payload index |

**5 个开箱 profile**:
- `local-lite`: SQLite + Chroma + 本地 fs(单机开发)
- `local-graph`: SQLite + FalkorDB + Chroma(单机带图)
- `cloud-graphiti`: Postgres + Graphiti/Neo4j + Qdrant(生产首选)
- `letta-bridge`: 委派 Letta(嵌入既有 Letta 部署)
- `cognee-bridge`: 委派 cognee 存储 + 复用其 DataPoint 子类机制

**对照**:9 个开源项目都把存储绑死。Starling 把"存储绑定"作为部署选项而非架构决策。

**ProfileCapability preflight(v11 新增)**:
9 个仓库的源码对比显示,生产事故常来自"底座看似可接入,但缺一项硬能力":例如 crypto_erasure 需要 per-record key,多租户需要存储层 tenant filter,Projection rebuild 需要可追溯 watermark,向量库需要 payload delete。Starling 启动时必须执行 profile capability preflight,不允许运行时才发现能力缺口。

```python
class ProfileCapability(BaseModel):
    profile_name: str
    transactional_outbox: bool
    consumer_checkpoint: bool
    tenant_isolation: Literal["none","app_filter","storage_enforced"]
    command_boundary_filter: bool           # v12:底座命令边界注入 tenant/holder filter
    unknown_data_command_reject: bool       # v12:未知数据面命令 fail-closed
    id_operation_scope_guard: bool          # v12:get/delete by id 也必须带 tenant/holder scope
    drawer_per_record_key: bool
    drawer_refcount: bool
    crypto_erasure: bool
    vector_payload_delete: bool
    projection_rebuild_from_watermark: bool
    container_cas: bool
    distributed_lock_or_lease: bool
    stage_timing: bool
```

**启动校验规则**:
- `production` profile 必须满足 `transactional_outbox=true`、`consumer_checkpoint=true`、`tenant_isolation="storage_enforced"`、`container_cas=true`。
- `tenant_isolation="storage_enforced"` 必须满足 `command_boundary_filter=true`、`unknown_data_command_reject=true`、`id_operation_scope_guard=true`:Mongo/SQL/ES/Milvus/Vector 等底座的数据面 read/write/delete/search 必须在命令边界注入 `tenant_id/holder_scope`,未知数据面 API 默认拒绝,不能只靠业务 service 传参。
- 对 ID-based 操作(`get/delete/update by id`)不能假设 id 全局不可猜;必须转换为 `(id AND tenant/holder scope)` 查询或由底座强制 row-level security 覆盖。
- 启用 `retention_mode=crypto_erasure` 时必须满足 `drawer_per_record_key=true` 且 `crypto_erasure=true`;否则启动失败,不得自动降级为逻辑隐藏。
- 启用共享 DrawerRecord 时必须满足 `drawer_refcount=true` 或提供等价的引用拆分策略。
- 启用 Projection Index 时必须满足 `projection_rebuild_from_watermark=true` 与 `vector_payload_delete=true`;否则 Retrieval 只能使用主表直查,且 profile 标 `projection_disabled_reason`。
- 多租户部署若只能提供 `app_filter`,所有写入和检索必须 fail-closed 要求 `tenant_id/holder_scope` 显式存在;若 `tenant_isolation="none"`,只能运行单租户开发模式。
- 能力检查结果写入 `system.profile_checked` outbox 事件与 `RuntimeHealth.capability_status`,供 smoke test 与运维审计读取。

**底座命令边界隔离(v12 新增)**:
EverOS 的 Mongo/ES/Milvus tenant interceptor 说明,仅在 Repository 或 Service 层传 `tenant_id` 不足以构成生产隔离。Starling 的 `storage_enforced` 含义如下:

| 底座 | 必须强制的边界 | 失败策略 |
|---|---|---|
| SQL/Postgres | Row-level security 或 query builder finalizer 强制追加 `(tenant_id, holder_scope)` 谓词;delete/update 空 scope 禁止 | 缺 scope 或未知 mutation path → reject |
| Mongo/DocStore | command/listener/finalizer 层对 find/insert/update/delete/aggregate 注入 tenant filter;control-plane 命令白名单通过 | 未识别数据命令 → reject |
| Elasticsearch/BM25 | search/count/delete_by_query 外层 bool.filter 注入 tenant;bulk delete 与 mget 等不可安全注入操作禁用或专门实现 | 未识别 endpoint → reject |
| Vector/Milvus/Qdrant | search/query/delete payload filter 强制包含 tenant/holder;写入 payload force-set tenant,output_fields 默认不泄露 tenant 字段 | 空 delete expr 或无 payload delete 能力 → reject |

所有底座隔离器必须输出 audit counter(`tenant_scope_missing_count/unknown_data_command_count/id_scope_guard_count`)并进入 `RetrievalReceipt.filters_applied` 或 `PipelineRun.counters`;P0 可只在 SQLite adapter 上实现 final query assertion,但生产 profile 不得用该简化替代命令边界隔离。

### 4.1 热路径索引策略(v8:阶段边界 + 物化延迟)

Statement 主表是权威事实表,但 Retrieval Planner 不应在主表上堆叠所有复合索引。**P0 不实现 Projection Index**,`basic_retrieve` 直接查 SQLite Statement 主表(50 条样本规模足够)。**P2 起**必须维护专用投影索引:

| 投影 | 主键/分片 | 面向查询 | 更新来源 |
|---|---|---|---|
| `idx_holder_state_time` | `(holder, consolidation_state, valid_from, valid_to)` | FACT/HISTORY 基础过滤 | statement.written/derived/corrected/archived |
| `idx_holder_subgraph` | `(holder, consolidation_state, modality, subject)` | holder 子图快速过滤;FACT_LOOKUP/BELIEF_OF_OTHER 前置过滤 | statement.written/derived/corrected/archived/forgotten |
| `idx_entity_statement` | `(tenant_id, holder, entity_id, role, consolidation_state, statement_id)` | entity→Statement 桥;实体命中后快速拉取相关 holder 子图 | statement.written/derived/corrected/archived/forgotten + entity.linked |
| `idx_salience_hot` | `(holder, salience_bucket, last_accessed)` | 高 salience 热路径 | Replay + Retrieval soft flush |
| `idx_commitment_due` | `(beneficiary, deadline, state)` | COMMITMENT_DUE | commitment.* |
| `idx_common_ground` | `(party_hash, statement_id)` | COMMON_GROUND | container.rebuilt / grounding acts |
| `idx_vector_payload` | vector id + payload(holder,state,modality,review_status) | semantic/hybrid recall | statement.* |

主表只保留主键、外键、状态与审计必要索引;高频 Retrieval 走 projection index。这样避免在 SQLite/Postgres 主 Statement 表上同时承担 holder/time/state/salience/vector 五维复合索引压力。Graphiti/Zep 的 group/partition 思路可作为云端 profile 的分片参考,但 Starling 的 holder 子图族仍由逻辑层控制。

**物化策略**:
- Projection Index 由 outbox subscriber 异步物化,不阻塞 `Bus.write` 主事务。
- P2 默认 freshness SLA:Online 模式 < 2s,Idle/Sleep 批处理 < 30s;超过 SLA 时 Retrieval 可降级主表直查或标记结果 stale。
- `idx_holder_state_time` 是唯一允许 P1 提前引入的轻量投影;P0 仍用主表直查以减少实施面。
- 投影索引可重建:任何 projection 表都可由 Statement 主表 + outbox sequence 重放恢复,不作为权威事实源。
- v12 新增 repair safety:Projection rebuild / vector payload repair / HNSW 重建在 shadow table/index 完成后,必须用独立真相源校验 `expected_row_count`、`max_outbox_sequence`、抽样 `content_hash`/payload count。若 extraction count 低于主表/SQLite/Postgres ground truth,或刚好命中底座默认分页上限且无法交叉验证,必须拒绝 atomic swap 并 emit `projection.rebuild_failed(truncation_suspected)`。

**投影索引订阅规则(v10 新增)**:

| 投影 | 订阅事件 | 更新动作 |
|---|---|---|
| `idx_holder_state_time` | `statement.written/derived/corrected/archived/forgotten` | 写入/派生/修正时增量 upsert;archived 标记降权;forgotten 物理删除 |
| `idx_holder_subgraph` | `statement.written/derived/corrected/archived/forgotten` | 同 holder 子图维度 upsert;archived 保留但降权;forgotten 删除 |
| `idx_entity_statement` | `statement.written/derived/corrected/archived/forgotten/entity.linked` | 为 subject/object/source_span 中出现的 Entity 维护反向链接;role ∈ subject/object/evidence_span/query_entity;forgotten 删除 |
| `idx_salience_hot` | `statement.consolidated`;Replay 周期 flush | salience 或 last_accessed 变更时 upsert;低于热度阈值时移除 |
| `idx_commitment_due` | `commitment.fire/fulfilled/broken/renegotiated/withdrawn` | state/deadline 变更时 upsert;fulfilled/withdrawn 从热路径移除 |
| `idx_common_ground` | `container.rebuilt` | 按 CommonGround dimension sequence 增量重建 |
| `idx_vector_payload` | `statement.written/derived/corrected/consolidated/archived/forgotten/superseded` | 向量 payload 的 holder/state/modality/review_status 与主表同步;forgotten 删除向量 payload |

所有 projection index 都支持由 Statement 主表 + outbox sequence 完全重建。任何读路径若检测 projection lag 超过 §4.1 freshness SLA,必须降级主表或返回 stale 标记。

---

## 5. Statement Bus:全局陈述总线

所有读写必经 Bus,**不允许直接写存储**(公理 I 的硬约束)。v6 将"读写"明确扩展为三类入口:

1. `append_evidence(drawer_input)` — 创建 DrawerRecord,做 source trust、权限、retention、审计和幂等。
2. `write(stmt)` — 写 Statement/边/索引,并在同一事务中追加 outbox 事件。
3. `rebuild_container(container_ref, sources)` — 重建 Persona/CommonGround 等物化视图,用 CAS 防并发覆盖。

```
append_evidence(input) → Bus → EvidenceValidator → Drawer → outbox(evidence.appended)
write(stmt)            → Bus → Validator → ConflictProbe → partition/index → outbox(...)
rebuild_container(ref) → Bus → CAS Container materialization → outbox(container.rebuilt)
read(query)            → Bus → RetrievalPlanner → 多源融合 → Result
deliver(outbox)        → Bus → Subscribers(Replay/Reconsolidation/ToM/Prospective)
```

**事务投递语义(v7)**:
- `Bus.write / append_evidence / rebuild_container` 必须是**存储事务 + durable outbox append**。存储 commit 与 outbox append 同事务提交。
- 事件从 outbox 异步投递,语义为 **at-least-once**。所有 Subscriber 必须按 `idempotency_key` 幂等消费。
- 禁止"先 emit 后写库";禁止 Subscriber 同步阻塞写入事务。
- Outbox 事件带单调 `sequence` 与 `causation_chain`,同一 aggregate 内按 sequence 顺序投递。
- 失败重试采用指数退避;超过阈值进入 dead-letter queue,并 emit `system.delivery_failed`。
- Dispatcher 为每个 subscriber 持久化 `consumer_checkpoint(subscriber, shard, last_dispatched_sequence)`;重启后从 checkpoint+1 恢复扫描。
- Subscriber 处理成功后先写本地 inbox ACK/业务幂等记录,再更新 checkpoint;ACK 丢失导致重复投递时,按 inbox 去重并直接 ACK。

**自污染防护(v12 新增)**:
claude-mem 的 internal observer 排除和 mempalace 的 query sanitizer 都指向同一个问题:系统自己的 prompt、trace、检索回执、Replay 日志若进入普通记忆,会污染用户画像并形成自证循环。`Bus.append_evidence` 因此必须执行 source boundary:

枚举定义见 §3.8 DrawerRecord schema。

规则:
- `system_internal / observer_agent / replay_output` 默认 `NO_STORE`,只写 audit counter,不得创建普通 DrawerRecord;debug profile 可显式 allowlist 到 `STORE_METADATA_ONLY`,但不可参与 holder 画像、Replay、ToM。
- RetrievalReceipt、PipelineRun trace、Extractor raw prompt/response、worker log、health event 默认都是 `system_internal`;若用于评测,必须进入隔离 evaluation tenant 或 metadata-only Drawer。
- `tool_observation` 只有在工具输出是用户可见事实或外部世界观测时可 `STORE`;纯执行日志、stack trace、token usage 默认 `STORE_METADATA_ONLY` 或 `NO_STORE`。
- 任何从 `replay_derived`/Container rebuild 生成的摘要不得再次作为 evidence 写入 Drawer;其证据链应回指原始 DrawerRefs,防止摘要反喂摘要。
- P0 negative test 必须证明:一次 `basic_retrieve` 生成的 RetrievalReceipt 不会被下一轮 Extractor 当作用户记忆抽取。

### 5.1 Validator(写入校验)

借鉴 mem0 `filters={}` 契约 + claude-mem 严格 XML:

1. **Schema 校验**:`holder/perspective/modality/polarity/observed_at/provenance/review_status` 必填;`evidence ≥ 1`。
2. **抽取一致性**:LLM 输出包裹在 `<statement>` XML;非合规拒收,并写入抽取失败事件。
3. **隐私边界**:Cognizer 的 `knowledge_frontier` 限制其 holder 字段下能持有什么 —— 未到场不能"知道"私密信息。
4. **过度抽取策略**:宁可多建 statement 后期合并(借鉴 Polis §4.1)。

**抽取失败补偿(v7 新增)**:
`evidence.appended` 已提交而 Extractor 产出的 Statement 被 Validator 拒收时,不得静默丢弃该 DrawerRecord。Extractor 必须发布:

```python
outbox.append("extraction.failed", {
    "drawer_ref": drawer_ref,
    "extractor_version": extractor_version,
    "failure_kind": "schema_invalid" | "privacy_violation" | "low_confidence" | "parse_error",
    "raw_output_hash": sha256(raw_llm_output),
    "retry_count": retry_count,
})
```

处理规则:
- `parse_error/schema_invalid`:最多自动重试 2 次,emit `extraction.retry_scheduled`;
- `low_confidence`:创建 `review_status=REVIEW_REQUESTED` 的候选 Statement 或进入人工 review 队列;
- `privacy_violation`:不重试,进入 dead-letter 并触发 audit;
- 超过重试阈值 emit `extraction.dead_lettered`,DrawerRecord 保留 `extraction_status=FAILED`,后续 Sleep/人工 audit 可重新抽取。

**重试去重(v8 新增)**:
LLM 抽取非确定性意味着同一 DrawerRecord 重试可能产出不同候选。Extractor 在重试前必须读取 `extraction_attempt_id` 对应的已写入结果:
- 若上次候选中部分 Statement 已通过 Validator 并写入,重试只覆盖失败片段,不得重新写入已成功片段。
- 每个候选 Statement 带 `extraction_span_key = hash(drawer_ref, chunk_index, normalized_span, predicate, canonical_object)`;Bus.write 对同一 `extraction_span_key` 做幂等 upsert。
- 若重试产出与已成功 Statement 同 span 但内容不同,进入 `REVIEW_REQUESTED`,不自动 supersede。
- 一个 DrawerRecord 的最终 `extraction_status` 为 `PARTIAL_SUCCESS / SUCCESS / FAILED / DEAD_LETTERED`,用于 Sleep/人工 audit 续跑。

**ExtractionAttempt 明细(v11 新增,v14 收敛)**:
借鉴 mem0 的 memory history、mempalace sweeper 的确定性 id/cursor、memU workflow 的 step trace,Extractor 每次消费 `evidence.appended` 都必须记录一条 attempt,即使没有产生任何 Statement。无结果也是事实,不能让 DrawerRecord 看起来"从未处理"。

v14 明确:ExtractionAttempt 不是第二套任务生命周期,而是 `PipelineRun(kind="extraction")` 的 item-level 明细。调度、重试、lease、dead-letter、取消与最终终态以 PipelineRun 为权威;ExtractionAttempt 只解释单个 DrawerRecord/片段抽取为什么成功、失败、NOOP 或部分成功。

```python
class ExtractionAttempt(BaseEntity):
    id: UUID
    run_id: UUID                             # 所属 PipelineRun(kind="extraction")
    drawer_ref: DrawerRef
    attempt_no: int
    extractor_version: str
    prompt_version: str
    prompt_input_hash: str
    existing_ref_map: dict[str, StatementRef]  # 短 id -> 真实 StatementRef,防 LLM 幻觉引用长 UUID
    status: Literal["RUNNING","SUCCESS","PARTIAL_SUCCESS","FAILED","DEAD_LETTERED","NOOP"]
    accepted_statement_ids: list[StatementRef]
    rejected_fragments: list[dict]            # span_key/failure_kind/reason/raw_hash
    noop_reason: Optional[str]                # 如 no_new_memory / all_duplicate / below_confidence
    raw_output_hash: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]
```

规则:
- `PipelineRun.status` 是调度权威;ExtractionAttempt.status 是该 run 内单个 item 的处理结果。
- 一个 extraction run 的聚合规则:全部 SUCCESS/NOOP → `COMPLETED`;至少一个 SUCCESS 且至少一个 FAILED/DEAD_LETTERED → `PARTIAL_SUCCESS`;只有非关键片段失败但下游可继续 → `DEGRADED_COMPLETED`;全部失败 → `FAILED/DEAD_LETTERED`。
- `existing_ref_map` 只把检索到的候选 Statement 暴露为短 id(如 `M1/M2`),写回时由 Validator 反查,禁止 LLM 自造 UUID。
- 如果 LLM 输出 0 条 Statement,写 `status=NOOP` 与 `noop_reason`,并 emit `extraction.noop`。这与失败不同:NOOP 表示证据已处理但无可落库新陈述。
- `accepted_statement_ids` 与 `rejected_fragments` 必须可解释 `PARTIAL_SUCCESS`;重试只读 rejected fragments,不重抽 accepted 部分。
- `prompt_input_hash` 覆盖 Drawer hash、chunk/span、extractor config、existing_ref_map 与 holder context;同 hash 的重放必须幂等。
- P0 可先用 SQLite 表实现最小账本;P1 后纳入 §5.6 PipelineRun stage timing。

**Extractor 产出契约(v10 新增)**:

| 项 | 规则 |
|---|---|
| 产出上限 | 每条 DrawerRecord 默认最多产出 10 条 Statement;超过上限按 salience / stakes / explicitness 排序截断,剩余候选进入 review queue,不自动落库 |
| holder 归因 | 说话人不等于 holder。第一人称陈述 holder=说话人;`Bob 说他喜欢咖啡` 中 holder=Bob,subject=Bob;`Alice 说 Bob 喜欢咖啡` 中 holder=Alice,subject=Bob;归因失败时 holder 默认为说话人并标 `review_status=INFERRED_UNREVIEWED` |
| perceived_by 推断 | 群聊默认取发言时段内在线且可见该消息的 Cognizer;私聊取双方;文档型/离线语料默认空集,除非 metadata 明确 readers/viewers |
| confidence 初值 | first-person 明确陈述 ≥0.8;直接观察 0.7-0.9;hearsay 0.5-0.7;系统推断 ≤0.5;低于 0.3 的抽取不落库,只写 `extraction.failed(low_confidence)` 或 review queue |
| evidence 绑定 | 直接抽取 Statement 必须绑定至少 1 个 DrawerRef;派生 Statement 必须绑定 `derived_from/evidence_chain`,最终可追溯到 DrawerRef |
| source span 绑定 | 直接抽取 Statement 必须绑定 ≥1 个 `SourceSpanRef`;Extractor 只能引用 DrawerRecord.segment_map 中存在的 segment/offset。Graphiti 式多 episode 事实需记录所有 episode span,并以第一归因 episode 的 observed_at 作为默认 temporal_anchor。派生 Statement 不得伪造直接 source span |
| temporal grounding | 相对时间只按 `TemporalAnchor.anchor_time` 解析。历史导入、异步批处理、跨天 transcript 不得用系统当前时间;fallback 到 system_now 时必须低置信并标 `INFERRED_UNREVIEWED` |
| 归因不可变 | `holder/source_speaker/source_spans/perceived_by/temporal_anchor` 写入后不可 UPDATE。若后续发现 holder 或 speaker 归因错误,必须写 `statement.corrected` 新版本、建立 `supersedes`,旧版本保留审计 |
| review 默认值 | schema 合法但 holder/perceived_by/confidence 任一来自弱推断时,默认 `review_status=INFERRED_UNREVIEWED`;进入 P0 smoke test 的关键 Statement 必须 `APPROVED` 或可解释地 `INFERRED_UNREVIEWED` |

### 5.2 ConflictProbe(冲突探针)

写入前按规范化冲突 key 查询相邻 Statement。冲突按 §7.3 决策树处理。**关键**:不静默覆盖,而是建立 `CONFLICTS_WITH` 边并通过 outbox 触发 Reconsolidation(§11)。

```python
def canonical_conflict_key(stmt: Statement) -> str:
    return hash_tuple(
        stmt.holder,
        stmt.modality,
        stmt.subject,
        stmt.predicate,
        canonicalize_object(stmt.object),
        normalize_interval(stmt.valid_from, stmt.valid_to, stmt.event_time),
        scope_of(stmt),                    # Norm.scope / Commitment.beneficiary / CommonGround parties
    )
```

`object`、时间区间和 scope 必须参与 key。否则 "Bob responsible_for auth" 与 "Bob responsible_for billing"、两个不同 deadline 的承诺、不同群组的 Norm 会被误合并或误判冲突。

**规范化规则(v10 新增)**:

| 函数 | 输入 | 规则 |
|---|---|---|
| `canonicalize_object` | Value / EntityRef / CognizerRef / StatementRef | StatementRef 只取一阶展开 `(holder, subject, predicate, polarity)` 与 inner id hash,不递归展开;EntityRef/CognizerRef 取 canonical_name + id;Value 按类型标准化:数值定点、时间转 ISO、字符串 trim + normalize whitespace + lowercase |
| `normalize_interval` | `(valid_from, valid_to, event_time)` | 优先使用 explicit `valid_from/valid_to`;缺失时从 `event_time` 推断瞬时或当天区间;统一为闭开区间 `[start, end)`;`end` 缺失视作 open-ended;无法推断 start 时返回 `UNKNOWN_INTERVAL` 并降级为 `partial_overlap + REVIEW_REQUESTED` |
| `scope_of` | Statement 子类 | Norm 按 `scope.kind + sorted(members)`;Commitment 按 `(principal, beneficiary)`;CommonGround 按 sorted(parties);普通 Statement 返回 `NULL`;若 Statement 带 access_policy/project/channel,scope 需包含该边界 |

**冲突等级(v7 新增)**:

| 等级 | 判定 | 处理 |
|---|---|---|
| `direct_contradiction` | 同 holder/modality/subject/predicate/object/scope,时间区间等价或高度重叠,polarity 相反 | emit `belief.conflict`,进入 Reconsolidation |
| `partial_overlap` | canonical object 相同,时间区间有交集但不完全覆盖 | 建 `CONFLICTS_WITH` 边,降低自动仲裁置信度,Context Pack 标 CONFLICT |
| `superseding` | 新 Statement 的 valid interval 完全覆盖旧 Statement,且 evidence 更新 | 旧版 valid_to/expired_at 截断,建 `SUPERSEDES`,通常不进入冲突 |
| `adjacent` | 时间区间相邻或存在小 gap,语义兼容 | 建 TEMPORAL/ADJACENT 边,作为补充而非冲突 |

时间 overlap 使用闭开区间 `[valid_from, valid_to)`,缺失 valid_to 视作 open-ended。若 event_time/valid_from 来自 LLM 推断且置信度低,ConflictProbe 不做 direct_contradiction,最多标 `partial_overlap + REVIEW_REQUESTED`。

**CommonGround supersede 触发(v9 收口)**:
`superseding` 是 SupersedeGround 的主触发来源,但 ConflictProbe 不直接写 Container。事件流为:
1. ConflictProbe 在 Bus.write 事务内识别 `superseding`,写 `SUPERSEDES` 边并 emit `statement.superseded`。
2. CommonGround Builder 消费 `statement.superseded`;只有当新 Statement 已达到 `grounded` 条件(或同一 event batch 中存在 Acknowledge/共同在场证据)时,才对对应 CommonGround 条目执行 `SupersedeGround`。
3. `Bus.rebuild_container(kind="common_ground")` 的一致性校验可补漏:若发现 active grounded 旧条目已被 grounded 新条目完全 supersede,则补记 `SupersedeGround` 审计 act 后重建维度。
4. Replay Scheduler 只能通过 Bus 产生 `statement.derived/statement.corrected` 或 review 候选,不得直接修改 CommonGround;否则会绕过 outbox、CAS 与审计。

### 5.3 BusEvent(v6:终态事件 + evidence/container/outbox)

> **v5 修复**:v4 表中 5 个终态事件缺失(`statement.archived/.forgotten/.derived` + `commitment.fulfilled/.broken/.renegotiated`),且产生者-消费者完备性未核对。v5 补全。

| 事件 | Producer | Consumer | 触发时机 |
|---|---|---|---|
| `evidence.appended` (v6 新增) | Bus.append_evidence | Extractor / Cognizer Hub / Audit | DrawerRecord 事务提交 |
| `evidence.redacted` (v6 新增) | Compliance Engine | Retrieval index / Audit | DrawerRecord 转 redacted_retain |
| `evidence.erased` (v6 新增) | Compliance Engine / KMS | Retrieval index / Audit | DrawerRecord crypto_erasure 完成 |
| `extraction.failed` (v7 新增) | Extractor / Validator | Extractor retry / Audit / Review queue | evidence 已提交但 Statement 抽取被拒 |
| `extraction.retry_scheduled` (v7 新增) | Extractor retry policy | Extractor | parse/schema 失败进入延迟重试 |
| `extraction.dead_lettered` (v7 新增) | Extractor retry policy | Audit / Review queue | 抽取重试耗尽或 privacy_violation |
| `statement.written` | Bus(写完 Hippocampus 后) | Replay / ToM / Prospective / Affect Buffer | 用户输入 / ToM 推断进 VOLATILE 后 |
| `statement.derived` (v5 新增) | Bus(写完 Neocortex 后) | ToM / Container Builder | Replay 派生 stmt 直接进 CONSOLIDATED 或 candidate index |
| `statement.corrected` (v6 新增) | Reconsolidation transaction | ToM / Container Builder / Retrieval index | severe correction 新版和旧版原子提交 |
| `statement.recalled` | Retrieval Planner | Reconsolidation(异步开窗判定) | 检索命中 |
| `statement.consolidated` | Replay Scheduler | ToM(更新 Persona) | REPLAYING_CONSOLIDATING → CONSOLIDATED |
| `statement.superseded` | Reconsolidation transaction | ToM / Container Builder | REPLAYING_RECONSOLIDATING 产 supersedes 链 |
| `statement.archived` (v5 新增) | Replay (decay) / Reconsolidation (contradict-severe) | Retrieval index(降权) | CONSOLIDATED→ARCHIVED 或 REPLAYING_RECONSOLIDATING→ARCHIVED |
| `statement.review_requested` (v14 新增) | Validator / Compliance / Reconsolidation | Review queue / Retrieval index / Audit | 低置信、合规擦除影响或派生链缺证据时进入人工/规则复核 |
| `statement.forgotten` (v5 新增) | Compliance Engine | Retrieval index(剔除) / Audit log | ARCHIVED→FORGOTTEN(显式 purge) |
| `commitment.fire` | PolicyEngine(经 Bus) | Prospective(下发提醒) | Trigger 命中 |
| `commitment.fulfilled` (v5 新增) | Prospective(检测 fulfilled_by) | Reconsolidation(↑ confidence) / Cognizer Hub(↑ trust_priors) | Commitment.state ACTIVE→FULFILLED |
| `commitment.broken` (v5 新增) | PolicyEngine(deadline 过) | Reconsolidation(↓ confidence) / Cognizer Hub(↓ trust_priors) | Commitment.state ACTIVE→BROKEN |
| `commitment.renegotiated` (v5 新增) | Validator(检测 RECANT+重新 COMMIT) | Prospective / ToM | Commitment.state ANY→RENEGOTIATED |
| `commitment.withdrawn` (v6 新增) | Validator / Prospective | Prospective / Retrieval index / Container Builder | Commitment.state ACTIVE/BROKEN/RENEGOTIATED→WITHDRAWN |
| `container.rebuilt` (v6 新增) | Bus.rebuild_container | Working Set / Retrieval cache | Persona/CommonGround 物化视图 CAS 成功 |
| `action.policy_blocked` (v14 新增) | ActionPolicyGraph / PolicyEngine | Audit / Ops / Prospective | 外部动作违反 required-before-exit、requires-approval、max-count 或 allowlist |
| `cognizer.observed` | Bus(写入消息时) | ToM(更新可见性) | 主体上线/发声 |
| `belief.conflict` | ConflictProbe | Reconsolidation(优先重放仲裁) | 探针发现矛盾 |
| `norm.violated` | NormChecker | Affect Buffer(高 salience) / Audit | 规范违反 |
| `extraction.noop` (v11 新增) | Extractor | Audit / PipelineRun | DrawerRecord 已处理但无新 Statement |
| `runtime.health_changed` (v11 新增) | RuntimeHealth monitor | Ops / Scheduler gates | READY/DEGRADED/DRAINING/UNREADY 变更 |
| `pipeline.run_started/completed/failed/cancelled` (v11 新增) | PipelineRun ledger | Ops / Replay / Projection / Audit | 长任务生命周期;completed payload 必须携带 `COMPLETED/PARTIAL_SUCCESS/DEGRADED_COMPLETED` |
| `projection.rebuild_started/completed/failed` (v11 新增) | Projection worker | Retrieval / RuntimeHealth | 投影索引重建或水位修复 |
| `system.delivery_failed` (v6 新增) | Outbox dispatcher | Ops / Audit | Subscriber 重试超过阈值 |

**对照**:claude-mem 的 4 阶段 hook(v12.4.4 移除 SessionEnd)是 session 级,Starling 是 statement 级。

### 5.4 防抖、幂等与 outbox 消费契约(v7)

> **v4 缺口**:ToM ↔ ConflictProbe ↔ Reconsolidation 闭环无防抖 —— 同 (subject, predicate) 反复触发 `belief.conflict` → `statement.superseded` → ToM 产生新嵌套 stmt → 又冲突 → 无限循环。v5 加防抖 + 递归限制。

**契约**:
1. **同 key 合并**:同一 `canonical_conflict_key(stmt)` 在窗口 W(默认 10s)内触发的同类事件,合并为一个事件(取最后一次 payload),避免冲突反复仲裁。
2. **递归深度限制**:每个事件携带 `causation_chain: list[event_id]`,链长 ≤ 3。超过则 emit `system.runaway` 告警并停止派生。
3. **幂等键**:每事件 `idempotency_key = hash(event_type, aggregate_id, canonical_key, causation_chain_root, window_bucket)`。Bus outbox 与 Subscriber inbox 都持久化该 key;重复投递直接 ACK。
4. **Reconsolidation 窗口锁**:同一 Statement 可塑窗口期内,新触发的 `belief.conflict` 不开新窗口,只追加证据到现有窗口的 `pending_evidence` 队列;窗口 close 时统一仲裁。
5. **投递顺序**:同一 `aggregate_id` 的事件按 outbox `sequence` 顺序投递;跨 aggregate 不保证全局顺序。
6. **业务幂等窗口**:Subscriber 除投递幂等外,还必须声明业务幂等键与窗口。例如 `commitment.fire` 的业务键为 `(commitment_id, trigger_id, fire_bucket)`,默认 24 小时内不重复注入 Working Set;`statement.recalled` 默认 2 秒 query 窗口内合并。
7. **Dispatcher checkpoint**:`consumer_checkpoint` 记录 subscriber/shard 的 last acked sequence;dispatcher 重启从 checkpoint 恢复,Subscriber inbox 保存最近 N 天 idempotency_key 防重复副作用。

**实现位置**:Bus 总线层统一拦截,所有 Subscriber 不感知此机制(契约对 §9/§10/§11 透明)。

### 5.5 Container 物化视图契约(v6 新增)

Persona / CommonGround / KnowledgeFrontier 是 `Container`,不是 Statement。v6 选择保守实现:Container 只保存 StatementRefs 与派生摘要,是可重建的物化视图;权威事实仍在 Statement 图中。

```python
class Container(BaseEntity):
    id: UUID
    kind: Literal["persona","common_ground","knowledge_frontier"]
    source_refs: list[StatementRef]
    materialized_payload: dict
    version: int
    dimension_versions: dict[str, int]       # v7: traits/preferences/common_ground 等维度级版本
    dimension_sequences: dict[str, int]      # 每个维度已消费的最高 outbox sequence
    last_rebuilt_at: datetime
    build_policy: Literal["on_event","sleep","manual"]
```

更新规则:
- 只有 `Bus.rebuild_container(container_id, dimension, expected_dimension_version, source_refs)` 能写 Container。
- 使用维度级 CAS:`expected_dimension_version` 不匹配则只重试该维度,不阻塞整个 Container。
- `container.rebuilt` 事件只表示物化视图刷新,不表示新增事实。
- Retrieval 可读 Container,但若对应 `dimension_sequences[dimension]` 落后于相关 Statement outbox sequence,必须只对该维度降级直接查 Statement 图。
- CAS 冲突采用指数退避 + 合并重建:同一维度 3 次冲突后进入 Sleep 批处理,避免多人协作场景下反复抢写。

**source_refs 版本语义(v10 新增)**:
- `source_refs` 存储稳定的 `Statement.id`,不是 Statement 内容快照。
- `Bus.rebuild_container` 必须沿 `SUPERSEDES` 链检查每个 source ref;若旧 Statement 已被新版本 supersede,active 视图自动替换为最新未 FORGOTTEN 版本 id。
- 旧版本 Statement 仍保留在主表中,可通过 supersedes 链追溯,但不得出现在 Container 的 active payload 中。
- Retrieval 读取 Container 时若发现 active `source_refs` 中存在已被 supersede 的 Statement,必须对该 dimension 降级直接查 Statement 主表,并异步触发 `Bus.rebuild_container` 修复。
- 若最新版本 `review_status=PENDING_REVIEW/REJECTED`,Container active 视图保留旧 approved ref,并在 payload 中标 `stale_due_to_pending_review=true`。

### 5.6 Runtime Health、Backpressure 与 Run Ledger(v11 新增)

源码复审中,Letta 的 LoadGate / event-loop watchdog、MemOS 的 scheduler dispatcher/status tracker、claude-mem 的 queue claim-confirm / RestartGuard / ChromaSync watermark、cognee 的 dataset queue slot 都指向同一个缺口:Starling v10 定义了事件和状态,但缺少全局运行时健康与长任务治理。v11 新增 Runtime Governance,把"何时接受请求、何时降级、何时暂停后台工作、如何恢复长任务"写成契约。

**RuntimeHealth 状态机**:

| 状态 | 进入条件 | 前台读写 | 后台任务 |
|---|---|---|---|
| `READY` | 所有硬能力 preflight 通过,lag/queue 在 SLA 内 | 正常 | 正常 |
| `DEGRADED` | outbox lag、projection lag、extract queue depth、event loop lag、subscriber failure rate 任一超阈值但主表可用 | 写入继续但高成本副作用延后;检索可降级主表/跳过 rerank | 暂停 Replay/Projection 非关键批处理,保留 Compliance/Commitment |
| `DRAINING` | 进程关闭、迁移、profile 切换或管理员 drain | 拒绝新后台 run;前台读可继续;写入按策略返回 retry_after | worker 停止 claim 新任务,等待 lease 内任务完成 |
| `UNREADY` | capability preflight 失败、主表不可用、outbox 不可提交、tenant isolation 缺失 | fail-closed | 不启动 |

**健康指标与 gates**:
- `outbox_lag_sequence / outbox_lag_seconds`
- `subscriber_failure_rate` 与 dead-letter 增长率
- `extraction_queue_depth`、`replay_backlog`、`projection_lag_seconds`
- `runtime_event_loop_lag_ms` 或等价 worker heartbeat 延迟
- `foreground_inflight / background_inflight`
- `tenant_scope_missing_count`、`capability_status`
- `vector_delete_lag` 与 `erased_evidence_visible_count`

前台请求和后台任务使用不同 gate:
- 前台 `Bus.append_evidence/write/basic_retrieve` 在 `DEGRADED` 下应尽量服务,但返回 `runtime_degraded=true` 或 `projection_stale=true`。
- 后台 Replay、Projection rebuild、Container rebuild 在 `DEGRADED` 下暂停或降速;Compliance erase、commitment due、outbox delivery 属于 critical lane,除 `UNREADY` 外不得丢弃。
- 队列满时只允许丢弃可重建的 soft work(如低优先级 Replay candidate);禁止丢弃已提交的 outbox、Compliance erase、Commitment fire、ExtractionAttempt 终态。

**worker lease / claim / confirm**:
- 每个可异步处理的任务必须先 `claim(run_id, worker_id, lease_until)`;处理成功后 `confirm(run_id, checkpoint)`。
- lease 过期的 `RUNNING` 任务可被其他 worker `reclaim`,但必须按 `idempotency_key` 与 checkpoint 跳过已完成部分。
- worker shutdown 先进入 `DRAINING`,停止 claim 新任务,flush inbox/checkpoint,再释放 lease。
- `RestartGuard` 使用两个独立阈值:滑动窗口内重启次数 + 连续无成功处理次数。任一超限即暂停该 worker lane,emit `runtime.health_changed(DEGRADED)`。

**PipelineRun / MaintenanceRun 账本**:

```python
class PipelineRun(BaseEntity):
    id: UUID
    kind: Literal["extraction","replay","projection_rebuild","container_rebuild",
                  "compliance_erase","retrieval_eval","migration"]
    aggregate_id: str                       # drawer_ref / holder / projection / container / tenant
    business_task_id: Optional[str]          # v12:用户/业务可见任务 id,可聚合多个 item run
    parent_run_id: Optional[UUID]
    item_run_ids: list[UUID]
    profile_name: str
    input_hash: str
    idempotency_key: str
    pipeline_name: str
    pipeline_revision: str                  # v12:如 retrieve_rag:v3|projection_rebuild:v2
    step_contracts: list[dict]              # step_id/requires/produces/capabilities/config_hash
    status: Literal["QUEUED","RUNNING","PAUSED","COMPLETED","PARTIAL_SUCCESS",
                    "DEGRADED_COMPLETED","FAILED","CANCELLED","DEAD_LETTERED"]
    checkpoint_sequence: Optional[int]
    watermark: dict                         # 如 last_outbox_sequence / last_sqlite_id / last_drawer_cursor
    progress: dict                          # total/done/skipped/retried
    counters: dict                          # accepted/rejected/noop/conflicts/erased
    warnings: list[dict]                    # non_fatal/skip_downstream 的可审计降级原因
    stage_timings_ms: list[dict]            # hierarchical stage timer
    error_kind: Optional[str]
    retry_count: int
    lease_until: Optional[datetime]
    started_at: datetime
    updated_at: datetime
```

```python
class PipelineStepContract(BaseModel):
    step_id: str
    requires: set[str]
    produces: set[str]
    capabilities: set[str]
    config_hash: str
    failure_policy: Literal["critical","non_fatal","skip_downstream"] = "critical"
```

运行规则:
- 同一 `(kind, aggregate_id, input_hash)` 默认只能有一个 active run;并发请求返回已有 `run_id`。
- 长任务必须可从 `checkpoint_sequence/watermark` 恢复;Projection rebuild 完成前不替换 active projection,采用 shadow table + atomic swap。
- 每个 run 输出 `stage_timings_ms`,至少包含 `claim / fetch / validate / write / outbox / projection` 等阶段,用于定位慢点。
- 取消语义是 cooperative cancel:worker 在阶段边界检查 cancel flag;若任务持有 lease,取消时写 `CANCELLED` 并释放 lease。
- 失败重试先指数退避,超过阈值转 `DEAD_LETTERED`;如果 run 属于 Compliance lane,必须告警且保持 `RuntimeHealth=DEGRADED/UNREADY`,不得静默跳过。

**Pipeline step contract(v12 新增)**:
memU 的 WorkflowStep / PipelineRevision 说明,长任务账本必须能解释"这次到底跑了哪个步骤版本"。Starling 的 PipelineRun 因此增加:
- `pipeline_revision`:注册/变更 pipeline 时生成 revision token;同一 input_hash 在不同 revision 下不得复用旧结果。
- `step_contracts`:每个 step 声明 `requires/produces/capabilities/config_hash`;run start 前验证上游 produce 覆盖下游 require,profile capability 覆盖 step capabilities。
- step interceptor 可写入 `stage_timings_ms` 与 `trace_retention`,但不得修改权威 state;若 interceptor 失败,按 lane policy 决定 fail-open 还是 fail-closed。
- Pipeline mutation 只能产生新 revision,不得原地改写旧 revision;debug/实验 profile 可启用自定义 step,生产 profile 必须记录 revision 与 conformance test。
- v13 新增 `failure_policy`:
  - `critical`:失败立即终止 run,按 retry/dead-letter 处理。
  - `non_fatal`:失败写入 `warnings/counters`,继续执行仅当后续 step 的 `requires` 已满足;否则自动升级为 `critical`。
  - `skip_downstream`:失败后跳过所有直接依赖其 `produces` 的 step,run 终态为 `PARTIAL_SUCCESS` 或 `DEGRADED_COMPLETED`,不得报 `COMPLETED`。
- 非致命失败不得吞掉 Compliance erase、outbox delivery、tenant isolation、crypto erasure、commitment fire 这类 critical lane step;这些 step 的 `failure_policy` 固定为 `critical`。

**ScopedWorkGate(v12 新增)**:
cognee dataset queue slot 与 MemOS per-user/mem_cube grouping 都显示,全局 semaphore 太粗。Starling 后台任务使用 scoped gate:

```python
gate_key = (tenant_id, holder_scope, aggregate_id, lane)
```

规则:
- 同一 task/run 对同一 `gate_key` 可重入,只递增 depth;同 task 进入不同 aggregate 要消耗新 slot。
- `critical` lane(Compliance erase、outbox delivery、commitment due)使用独立 quota,不得被 Replay/Projection soft work 占满。
- `soft` lane 队列满时可丢弃或合并可重建任务,但必须增加 `dropped_soft_work_count` 并保留可从 outbox/watermark 重建的依据。
- task 结束时必须释放所有 depth;RuntimeHealth 定期扫描 leaked leases/gates,超时释放并 emit `runtime.health_changed(DEGRADED)`。
- `business_task_id` 可聚合多个 item run:业务层看到 `PARTIAL_SUCCESS` 当且仅当至少一个 item 成功且至少一个失败;所有 item NOOP 时业务状态为 `NOOP` 而非 SUCCESS。

**Trace retention tiers(v12 新增)**:
Letta ProviderTrace 的 full request/response 与 metadata-only trace 提醒,可观测性不能绕过隐私与合规。ExtractionAttempt、PipelineRun、RetrievalReceipt 均需支持:

| `trace_retention` | 内容 | 默认场景 |
|---|---|---|
| `metadata_only` | step 名、耗时、状态、hash、计数,不保存 prompt/response 正文 | production 默认 |
| `hash_only` | 只保留 input/output hash 与错误分类 | sensitive/regulated |
| `redacted_debug` | 保存脱敏后的 prompt/response,有 TTL | staging/debug |
| `full_debug` | 保存完整 prompt/response,有短 TTL、访问审计、禁止敏感 profile 默认启用 | 本地排障 |

full/debug trace 不得作为普通 Drawer evidence;若因合规擦除触发,trace 中对应 raw payload 必须同步 redaction 或 crypto erasure。

---

## 6. Drawer / Hippocampus / Neocortex:存储分层

> **v6 重写**:Drawer 仍与 Hippocampus / Neocortex 平级,但其写入必须经 `Bus.append_evidence`,其内容生命周期必须遵守 `DrawerRetentionMode`。

### 6.0 Drawer:全局证据子系统(v6 合规版)

Drawer 是 Starling 的最底层证据保底,**与 Hippocampus / Neocortex 平级**,不属于任何记忆子系统:

```
┌─────────────────────────────────────────────────────────┐
│  Drawer  ── 全局 BlobStore + Audit Metadata             │
│   • 任何 Statement.evidence 必须指向其中片段            │
│   • 写入经 Bus.append_evidence,不允许直接 append        │
│   • 元数据 append-only;内容按 retention_mode 保留/擦除 │
│   • 多 Cognizer 可共享同一 DrawerRecord(参考 Letta     │
│     Archive,§16.2)                                     │
└─────────────────────────────────────────────────────────┘
        ▲                 ▲                  ▲
        │                 │                  │
   evidence ref      evidence ref       evidence ref
        │                 │                  │
   ┌────┴────┐       ┌────┴────┐       ┌────┴────┐
   │Hippocam │       │Neocortex│       │ToM Engine│
   │ pus     │       │         │       │ (推断)   │
   └─────────┘       └─────────┘       └─────────┘
```

**物理底座**:S3 / 本地 fs / Letta archival / memU Rust blob 层(§16.2)。生产 profile 必须支持 per-record encryption key 或等价的 key shredding,否则不能声明支持 `crypto_erasure`。

**写入契约**:
```python
drawer_ref = Bus.append_evidence(
    source=source,
    content=verbatim,
    source_kind="user_input|external_doc|tool_observation|...",
    adapter_name="direct_api|filesystem|slack|...",
    ingest_mode="chunked_content|whole_record|metadata_only",
    declared_transformations=[...],
    privacy_class="personal|internal|...",
    perceived_by=[...],
    retention_mode=policy.choose(source, content, jurisdiction),
    source_trust=score_source(source),
)
```

Extractor 只能消费 `evidence.appended` 事件产生 Statement;不得绕过 Bus 直接从文件系统读写 DrawerRecord。

**Drawer 写入前置校验(v12 新增)**:
- `source_kind` 与 `ingest_policy` 先于 retention policy 计算;`NO_STORE` 不创建 DrawerRecord,只写 audit event。
- `metadata_only` Drawer 不满足"verbatim evidence"要求,只能作为辅助来源;高影响 Statement 需至少一条 `byte_preserving` 或外部可信 evidence 才能自动 `APPROVED`。
- `declared_transformations` 进入 `content_hash` 域:同一源字节在不同转换 pipeline 下 hash 不相等,避免 silently mixing 不同 normalization 版本。
- source adapter 必须提供稳定 `source_item_id/version/chunk_index`;增量重跑以 `(adapter_name, source_item_id, version, chunk_index)` 幂等,而不是以 LLM 输出文本幂等。
- adapter conformance test 必须覆盖:byte-preserving round trip、declared-lossy replay、privacy_class 默认值、metadata schema、incremental cursor、close 后不可复用。

### 6.1 Hippocampus:快记忆子系统

> 设计原则:**写得快、稀疏索引、显著性优先、模式分离**。原档保底由 §6.0 Drawer 负责,本子系统**不直接持有 verbatim 内容**,只持有引用与索引。

**内部分区**(v5 移除 Drawer 行,Drawer 在 §6.0):

```
┌─ Episodes ───── 按 EM-LLM 惊奇度切分的事件单元(指向 Drawer)
├─ Working Set ── 当前会话/任务的活跃槽位(Letta Block 风格,带 limit)
└─ Affect Buffer ─ 待巩固的高 salience 事件队列(优先级队列)
```

**逻辑分区标签**(v5 显式):分区由 `consolidation_state ∈ {VOLATILE, REPLAYING_CONSOLIDATING}` + 索引 tag 区分,**非物理表迁移**(见 §3 三层抽象)。

### 6.2 事件切分(EM-LLM 风格)

LLM 在线计算每条话语相对上一段上下文的 `surprise = -log P(next | context)`(负对数似然),跨阈值即切出 EpisodicEvent。该值同时作为 EpisodicEvent.boundary_score。

**为什么需要 EpisodicEvent + episodic_link**:Episodic Knowledge Binding (OpenReview 2026) 系统刻画了 LLM 跨时间绑定 episodes 的根本失败模式 —— LLM 擅长学习孤立事实,但无法跨时间绑定相关 episodes。这是 parametric memory 的根本缺口,也是 Starling §3.6 EpisodicEvent + §3.7 SHARED_GROUND/OBSERVED_BY/MAY_OVERLAP_WITH 边类型的设计动机。

### 6.3 模式分离:反相似偏移 + MAY_OVERLAP_WITH(v2 吸收 Polis)

新 Statement 入库前计算与 top-K 已有 Statement 的余弦距离:

```python
def pattern_separation_index(new_stmt, neighbors):
    if max_similarity(new_stmt, neighbors) > θ_sep:
        # 反相似偏移:故意让索引向量远离最近邻(模拟 DG sparse coding)
        new_stmt.index_vector = orthogonalize(
            new_stmt.embedding, 
            against=top_k_neighbors,
            strength=pattern_separation_boost
        )
        # 软边记录"可能重叠",留给后期巩固再决定
        for n in neighbors:
            graph.add_edge(new_stmt, n, kind="MAY_OVERLAP_WITH",
                           similarity=cos(new_stmt, n))
    else:
        new_stmt.index_vector = new_stmt.embedding
```

**与 mem0 的根本区别**:mem0 看到相似就 UPDATE/NOOP;Starling **默认保留差异**,因为细微差异往往是主体视角不同的来源。

### 6.4 模式补全:CA3 风格图游走(v2 工程化)

提供 partial cue,先做向量召回拿种子集,沿 `derived_from / evidence / OBSERVED_BY / SHARED_GROUND / MAY_OVERLAP_WITH` 边做带权游走(类 HippoRAG Personalized PageRank):

```python
def pattern_completion(cue, budget=20):
    seeds = vector_recall(cue, k=5)
    activation = {s: 1.0 for s in seeds}
    for step in range(budget):
        next_acts = {}
        for node, act in activation.items():
            for edge in node.edges:
                w = edge_weight(edge.kind)
                next_acts[edge.target] = next_acts.get(edge.target, 0) + act * w * decay
        activation = merge(activation, next_acts)
        if max(activation.values()) < θ_stop: break
    return as_episodic_subgraph(activation)
```

返回**情节性子图**而非孤立 Statement —— 这才是"补全后的回忆"。

**资源边界(v10 新增)**:
- 单次 pattern completion 最多访问 1000 个节点,超过即提前终止。
- 节点 activation 低于 `θ_propagate`(默认 0.05)时不再向外传播。
- 使用 `visited` 集合避免重复展开;同一节点多次被激活时取最大 activation,不做无限累加。
- 达到资源上限时返回当前 activation 最高的 K 个节点(默认 K=20)作为降级情节性子图,并标记 `completion_truncated=true`。
- P0 不实现 pattern completion;P2 实现时必须把这些边界作为单元测试约束。

### 6.5 Working Set(显式工作记忆,Letta Block 风格)

```python
class WorkingBlock:
    label: Literal["self_persona","active_persona","current_goal",
                   "interlocutor_persona","common_ground","norm_active",
                   "pending_commitments"]                       # v2 增 pending_commitments
    value: str
    limit: int                                                  # token 上限
    version: int                                                # 乐观锁
    refresh_strategy: Literal["never","per_turn","per_session","on_event"]
```

**主流开源系统中无一显式注入** `interlocutor_persona / common_ground / pending_commitments` 这三块 —— 这是 Starling 工作记忆的差异点。

**Working Set 与 Persona 的关系(v5 新增,解 m2)**:
- **Working Set** 是 prompt 时刻的**渲染快照**(每回合 / per-turn 重建),负责把"此刻 LLM 需要看到什么"渲染为 prompt block
- **Persona**(§3.6)是**持久化结构**,Working Set 中的 `self_persona` block 是 Persona.self_model_anchor + Persona.traits 的渲染
- 即:Working Set 是 view,Persona 是 model;view 跟 turn 走、limit token 数、可频繁重建,model 跟 cognizer 走、跨会话稳定、由 Replay 周期更新

### 6.6 Affect Buffer

高 salience 事件进入优先级队列等待重放。**容量满淘汰最低 salience 而非最旧**(借鉴 Anderson adaptive forgetting)。

**Buffer 与 Replay Scheduler 的关系(v5 新增,解 m1)**:
- Affect Buffer 是**入口缓冲**(数据结构,FIFO+优先级),只接收 `statement.written` 中 salience > θ_buffer 的子集
- Replay Scheduler(§10)在 Online 模式下**优先从 Buffer 取**(高 salience 优先);Idle/Sleep 模式则从 Hippocampus 全分区采样
- Buffer 满时新 stmt 替换最低 salience 的 stmt,被替换者**仍留在 Hippocampus VOLATILE**(不丢),只是不在快通道
- Buffer 不存 stmt 副本,只存引用

---

## 7. Neocortex:慢记忆子系统

> 设计原则:**抽象、可查、可推理,但更新需要"通过 Replay/Reconsolidation 才能进入"**。

### 7.1 五个子区

| 子区 | 内容 | 主要承载 | 更新通道 |
|---|---|---|---|
| **Semantic** | 语义事实图 | Statement(BELIEVES/KNOWS,CONSOLIDATED) | Replay 巩固 |
| **Procedural** | 技能/流程 | Skill | Case 集群提升(EverOS 风格) |
| **Norms** | 规范库 | Norm | 反思周期推断 |
| **Personae** | 主体长期画像 | Persona | 慢更新(每 N 次会话) |
| **CommonGround** | N 元共识池 | CommonGround | grounding act 触发 |

**v4 增——mempalace Hall detection 对照**:mempalace v3.3.0 引入 7 个 Hall (`emotions / technical / family / memory / identity / consciousness / creative`),基于内容情感/主题做存储分区。Starling 的 5 子区是按记忆类型(语义/技能/规范/画像/共识)划分,两者维度不同但可组合 —— Hall 可作为 Neocortex 子区内的二级分区策略。见 `_research/04_repos_resurvey_2026.md` §mempalace。

### 7.2 holder-aware 图族(关键差异)

Neocortex 的语义层不是单一全局图,而是**按 holder 分层的图族**:

```
GraphFamily = {
    holder=self     : { (subj,pred,obj,t,conf) ... },   # 我自己相信的
    holder=Alice    : { ... },                          # 我以为 Alice 相信的
    holder=Bob      : { ... },
    common(self,Alice)         : { ... },
    common(self,Alice,Bob)     : { ... },               # N 元共识
    ...
}
```

每子图独立维护,共享 entity 池但**不共享真值**。这避免了 mem0/cognee 把 LLM 抽出的命题写为全局事实的污染问题。

### 7.3 冲突消解决策树(v2 完整)

ConflictProbe 发现冲突时不静默覆盖,按以下决策树:

| 情况 | 处理 |
|---|---|
| 同 holder + 时间更晚 + 显式 RECANT | supersedes 链,旧版进历史信念链 |
| 同 holder + 时间更晚 + 隐式改口 | 旧版 confidence 衰减,新版按证据强度,**两版共存**直到 Reconsolidation 仲裁 |
| **不同 holder** | **直接共存**(多视角的本质,**不算冲突**) |
| 同 holder + 同时间窗 + 矛盾 | emit `belief.conflict`,Replay 加重该陈述优先级,**不立即仲裁** |
| 涉及承诺主体改口("我没这么说过") | 触发 audit 流程,evidence 链显式比对 |

### 7.4 Persona ↔ Belief 双通道(神经科学对齐)

呼应 Frith & Frith dmPFC/vmPFC 分工:
- **Persona(慢通道)**:traits / values / preferences / competencies / **self_model_anchor**(该主体对自己的陈述)/ **profile_anchor**(他人对该主体的陈述),**仅由 Replay 周期更新,单次会话不触动**;
- **Belief(快通道)**:holder=X 的 Statement,实时刷新。

**self_model_anchor vs profile_anchor 的工程意义**(v3 显式):同一个 Persona 持有两份锚点 ——
- `self_model_anchor`:该主体自己说过的关于自己的陈述(holder=X, subject=X 的子集);
- `profile_anchor`:他人对该主体的陈述(holder≠X, subject=X 的子集)。

两份锚点在 Persona 更新时分别加权,**自陈优先于他陈**(身份认同的认知规律),但若 profile_anchor 多源汇聚同一 trait 且与 self_model_anchor 冲突,则升级为 `suspected_diverge` 候选,交 ToM Engine 仲裁。

**为什么必须分离**:mem0/memU 等系统把"用户偏好喝咖啡"这种长期 trait 与"用户当前在生气"这种瞬时 belief 写到同一个 profile 里 —— 一次会话就能颠覆长期画像。Starling 的双通道在 schema 层禁止这种污染。

---

## 8. Cognizer Hub:主体注册与画像

### 8.1 Cognizer 生命周期

```
discover → 在 Drawer 中识别新 Cognizer(NER + 对话角色 + alias 归一)
seed     → 初始化空 Persona + 默认 KnowledgeFrontier + trust_priors=neutral
observe  → 每次出场触发 cognizer.observed,更新 last_seen_at
profile  → Replay 周期重写 Persona(慢通道)
archive  → 长期未活跃,降低检索权重(不删)
```

### 8.2 KnowledgeFrontier(知识边界)

```python
class KnowledgeFrontier:
    accessible_sources: list[SourceRef]    # 该主体可访问的信息源
    membership: list[GroupRef]              # 所属群组
    presence_log: list[PresenceWindow]     # 何时何地在场
    explicit_told: list[StatementRef]      # 明确告知
    explicit_not_told: list[StatementRef]  # 明确未告知(用于 surprise)
```

Retrieval Planner 用此对**该 holder 可能知道什么**做硬过滤(EnigmaToM iterative masking 风格)。

### 8.3 Relations(Fiske 四类 + 多维向量)

```python
class RelationEdge:
    a: CognizerRef
    b: CognizerRef
    fiske_weights: dict[Mode, float]       # 该关系在 Communal/Authority/Equality/Market 上的强度
    affinity: float                        # 0..1
    trust: dict[Context, float]            # 不同领域信任不同
    power_asymmetry: float                 # a 对 b 的影响力差(v2 吸收 Polis)
    interaction_history_ref: EpisodeQuery
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
```

**关系本身也是 Statement**(holder 是观察者),所以多视角自然支持:Alice 看到的 Alice-Bob 关系 ≠ Bob 看到的 Alice-Bob 关系。

Style 影响:
- **Communal**:倾向长期主动记忆共享、低形式化提醒;
- **Authority(上行/下行区分)**:下属对上司主动汇报,反之精炼;
- **Market**:对等可审计、强 grounding;
- **Equality**:轮替式 grounding 与责任。

---

## 9. ToM Engine:多阶信念追踪 + Mentalizing Primitives

> ToM Engine 是 §3 schema 之上的"运行时算法集合 + 高阶 API"。

### 9.1 二阶信念的物理实现

二阶信念在 schema 上是嵌套 Statement,**存储展平**为带 `nesting_depth` 的多条:

```
Outer: holder=self, subject=Alice, predicate=BELIEVES, 
       object=ref(Inner), nesting_depth=1
Inner: holder=Alice, subject=Bob, predicate=KNOWS,
       object=ref(Innermost), nesting_depth=2
Innermost: subject=Project_X, predicate=delayed, polarity=POS,
           nesting_depth=2  # 内容陈述
```

**约束**:默认追踪深度 ≤ 2,深度 3 仅显式触发(Kinderman 关于成人三阶 ToM 容量限制)。

### 9.2 Belief Tracker(每回合)

```
1. 抽取本回合产生的新 Statement(LLM tool-call,XML 严格)
2. 判断是否更新某主体的 belief 集
3. 与现有信念冲突 → 打 CONFLICTS_WITH 边
4. confidence 漂移:同主体反复确认 → 上调;反例 → 下调
5. 检测信念修正事件("其实我之前理解错了")→ 触发 Reconsolidation
6. perceived_by 推断:谁在场、谁可见
7. holder 归属判定(说话人 ≠ holder,如"Bob 说他喜欢...")
```

**ToM 派生链限流(v7 新增)**:
- Belief Tracker 对 `tom_inferred` 产生的 Statement 必须记录 `derivation_chain` 与 `causation_chain`。
- 若链路中已出现 `ToM → Replay → Container → ToM`,暂停自动增量推断,只在用户显式 META_BELIEF / perspective_take 查询时即时计算。
- 同一 `(holder, subject, predicate, object)` 的 ToM 推断在 10 分钟窗口内最多自动写入 1 条;其余作为 transient context,不落库。
- 当 `ToMDepthEstimator` 判定 partner order ≤ 1 时,默认不生成 nesting_depth=2 的持久 Statement,只生成查询时上下文。

**双限流语义(v10 新增)**:
- 窗口限流(本节):按 `(holder, subject, predicate, canonical_object)` 计数,只约束 `provenance=tom_inferred` 的 Statement 写入频率,与 `causation_chain` 长度无关。
- 链长限流(§5.4):按事件 `causation_chain` 长度限制,约束所有派生事件传播深度,与是否 ToM 无关。
- 超过窗口限流的 ToM 推断只作为 transient context 返回给当次查询,不落库、不 emit `statement.written`。
- 两个限流同时可能触发时,先检查 §5.4 链长,再检查本节窗口。链长保护无限递归,窗口保护抖动写入。

### 9.3 perspective_take 算子(SimToM + EnigmaToM 工程化)

```python
def perspective_take(target: CognizerRef, query: str, time: datetime) -> Context:
    visible = filter_by_frontier(drawer, target, time)        # 1. KnowledgeFrontier 遮蔽
    target_beliefs = neocortex.query(holder=target, time=time)# 2. 取 holder=target 子图
    cg = common_ground(self, target)                           # 3. 共识池
    return Context(visible, target_beliefs, cg)
```

任何对话生成、规划、协商都先 `perspective_take(other)` 取对方视角再决策。**这是现有开源系统全部缺失的能力**。

### 9.4 Mentalizing Primitives(7 个高阶认知原语,v2 吸收 Polis)

| API | 含义 | 对应脑区 |
|---|---|---|
| `what_does_X_believe(about=Y)` | X 关于 Y 的信念集 | rTPJ |
| `what_does_X_think_Y_believes(about=Z)` | 二阶 ToM | mPFC |
| `does_X_know(fact)` | X 是否知道(查 X 的 evidence + frontier) | 知识归因 |
| `predict_X_would(in_situation)` | 模拟 X 在某情境下的反应 | simulation theory |
| `find_misalignment(between=[X,Y], about=Z)` | 找 X 和 Y 对 Z 的认知差异 | 冲突检测 |
| `shared_with(members)` | N 主体的 SharedGround | common ground |
| `who_committed(to=Y)` | 关于 Y 的所有未决承诺 | prospective + 社会 |

**这 7 个 Mentalizing Primitives 把 LLM 从"每次重新模拟"中解放出来,系统负责维护可查询的认知状态**。

### 9.5 Grounding Acts(共识池更新,Clark 1996)

| Act | 触发 | 效果 |
|---|---|---|
| Assert | 一方陈述 | 进 `asserted_unack` |
| Acknowledge | 对方确认 | 升级到 `grounded` |
| Repair | 对方质疑 | 退回 `suspected_diverge` |
| Withdraw | 一方撤回 | RECANTED + 从池中移除 |
| SupersedeGround | 新共识覆盖旧共识 | 旧 grounded 标 `superseded_by`,新 Statement 进 `grounded` |
| ExpireGround | 共识过时/项目结束/retention 到期 | grounded → `expired`,不再享受 is_grounded 衰减保护 |
| Unground | 共同知识被显式否认或证据擦除 | grounded → `suspected_diverge` 或移除 |

输出层"已 grounded 不复述,未 grounded 主动 grounding"由 Working Set 中的 `common_ground` block 驱动。

**grounded 判定规则(v10 新增)**:
CommonGround 条目满足任一条件即可从 `asserted_unack` 升级为 `grounded`:
- **显式确认**:parties 中任一其他成员对该 Statement 显式回应、引用、复述或执行相关动作。
- **共同在场推定**:`perceived_by` 覆盖所有 parties,且后续 N 轮内(默认 N=3)无人 Repair / Withdraw / 显式否认。
- **重复确认**:同一 Statement 或 canonical 等价 Statement 被不同 parties 成员独立提及 ≥ M 次(默认 M=2)。
- **人工/规则确认**:高 stakes 场景允许 human review 或 policy rule 显式设为 grounded,必须保留审计 actor。

超时不自动升级:若 `asserted_unack` 超过 T 小时(默认 T=24)且无任何 Acknowledge/Repair,自动降级为 `suspected_diverge`,不得推定 grounded。

**CommonGround 过时治理(v8 新增,v9 明确触发路径)**:
`is_grounded` 只表示"曾经达成共同知识",不等于永久真。CommonGround 条目需要维护 `grounded_at / last_confirmed_at / superseded_by / expired_at`。若新 grounded Statement 在同一 scope 上 `superseding` 旧 Statement,旧条目必须 ExpireGround;若 evidence 被 crypto_erasure 且无独立证据,触发 Unground;若长期无确认且关联 Norm/Commitment 已终止,Replay 可降低 `is_grounded` 因子。

SupersedeGround 的主触发器是 §5.2 ConflictProbe 的 `superseding` 等级,落库执行者是 CommonGround Builder。Container.rebuild 只做 fallback 一致性校验与补审计,Replay 只产候选或派生 Statement,不直接改 CommonGround。

### 9.6 Adaptive ToM Order(v4 新增,AAAI 2026 A-ToM)

A-ToM (arxiv 2603.16264, AAAI 2026) 提出首个自适应 ToM agent,可实时估计 partner 的 ToM order,解决"固定 ToM order 在不同 partner/场景下适配性差"的问题。Starling 的 ToM Engine 默认追踪深度 ≤ 2(§9.1),深度 3 仅显式触发。A-ToM 的发现建议增加 `ToMDepthEstimator` 模块:

```python
class ToMDepthEstimator:
    """基于 partner 的 prior interactions 估计其 ToM order"""
    def estimate(self, partner: CognizerRef, context: Situation) -> int:
        # 0: partner 不追踪任何人的信念(零阶)
        # 1: partner 追踪我方信念(一阶)
        # 2: partner 追踪"我方以为他们相信什么"(二阶)
        ...
```

策略:当估计 partner 为一阶时,Starling 仅需维护 `nesting_depth ≤ 1` 的 statement;当估计为二阶时,允许 `nesting_depth = 2`。这同时为 §13.2 `META_BELIEF` Intent 提供深度上限指导,避免对低 ToM-order partner 做过度二阶推理。此模块排入 P4。

---

---

## 10. Replay Scheduler:优先级重放与巩固

> 这是 Starling 的"睡眠系统",对标 CLS + 海马 SWR(sharp-wave ripple)优先重放。

### 10.1 三种重放模式

| 模式 | 触发 | 任务 |
|---|---|---|
| **Online**(在线) | 每 N 个 statement.written | 即时巩固高 salience 短链 |
| **Idle**(空闲) | Agent 空转 > T 秒 / 用户离开 | 中等强度反思 |
| **Sleep**(深度) | 周期性(每会话结束 / 每日 / 显式 `/sleep`) | 完整 sweep + Persona 更新 |

### 10.2 优先级采样器(SWR 风格)

```python
def sample_weight(stmt):
    return (
        stmt.salience
        * novelty_decay(stmt.last_replayed)
        * (1 + conflict_bonus if stmt.has_conflict else 1)
        * (1 + arousal_bonus * stmt.affect.arousal)        # 高 arousal 多采(模拟杏仁核)
        * goal_relevance(stmt, current_goal)
        * provenance_factor(stmt.provenance)               # tom_inferred 默认 0.25
        / (1 + stmt.replay_count)                          # 已多次重放降权
    )
```

借鉴 prioritized experience replay(Schaul et al. 2015,LLM 端首次系统采纳)。

`provenance_factor` 默认值:
- `user_input`:1.0
- `tom_inferred`:0.25
- `replay_derived`:0(Replay 不订阅)
- `reconsolidation_derived`:0(Replay 不订阅)

**采样契约(v10 新增)**:
- 每个 Replay 窗口先计算 eligible Statement 的 `sample_weight`,截断到 `[w_min, w_max]` 后归一化为概率分布;低于 `w_min`(默认 0.01)的 Statement 跳过。
- 同一窗口内无放回采样,同一 Statement 不重复重放。
- 批量大小:Online 每批 1-3 条;Idle 每批 10-30 条;Sleep 可按分区 sweep,但每批仍按 bounded batch 提交。
- 极端值处理:超过 `w_max`(默认 p95 或配置上限)的 weight 截断,防止单条高 salience Statement 垄断采样。
- 新颖性下界:`last_replayed` 距今小于 `T_cooldown`(默认 5 分钟)的 Statement 权重置零,除非存在 `belief.conflict` 或 compliance 事件。
- 每次采样结果写 `replay_count / last_replayed / replay_batch_id`,便于调试与评测复现。

### 10.3 巩固原子操作集(v6:派生候选与物化视图)

> **v5 修复**:v4 表中"输出"列只说"产生新 Statement",未明确写入路径,造成与 §5 Bus 硬约束冲突。v5 显式注明 `provenance = replay_derived`(走 §3.10 派生路径,Bus 写 Neocortex CONSOLIDATED 不发 statement.written 不重入 Replay)。

| 动作 | 输入 | 输出 | provenance / review_status | 状态迁移 | 是否触发再 Replay |
|---|---|---|---|---|---|
| `compress` | 多条相似 EpisodicEvent | 1 条更高层语义 Statement(Drawer 指针保留) | `replay_derived / APPROVED` | 输入:VOLATILE→CONSOLIDATED;输出:CONSOLIDATED | ❌(v5 默认 non-propagate;借鉴 memU v1.5.0 #386,显式 propagate=True 时才级联) |
| `abstract` | 多 holder 的同 predicate | 1 条 Persona trait 候选 Statement + Container rebuild request | `replay_derived / PENDING_REVIEW` | 输入留态;候选入 Neocortex candidate index;Persona 经 `Bus.rebuild_container` 物化 | ❌ |
| `reconcile` | 冲突 Statement 集 | 推入 Reconsolidation Engine(§11)开启 REPLAYING_RECONSOLIDATING 窗口,由 §11 仲裁 | — | 输入:CONSOLIDATED → REPLAYING_RECONSOLIDATING | — |
| `induce_norm` | 多次 PREFERS/COMMITS 同模式 | 1 条 Norm 候选 | `replay_derived / PENDING_REVIEW` | 候选入 Neocortex candidate index;confirm 后 review_status→APPROVED | ❌ |
| `forge_skill` | 多次成功 Case 集群 | 1 条 Skill 候选(EverOS AgentSkill 风格) | `replay_derived / PENDING_REVIEW` | 同 induce_norm | ❌ |
| `decay` | 低 salience 长未召回 | confidence 衰减,达阈值 → state 迁移 | — | CONSOLIDATED → ARCHIVED(emit `statement.archived`) | — |
| `purge_compliance` | 用户撤回 / 法务事件 | state→FORGOTTEN + 传播到 derived 链 + Drawer 按 retention_mode redacted/erased | — | ARCHIVED 或 CONSOLIDATED → FORGOTTEN(emit `statement.forgotten` + evidence 事件) | — |

**关键不变量(v6)**:所有 `replay_derived` 输出**经 Bus.write 但带 provenance/review_status 标记**,Bus 把它写入 Neocortex 正式索引或 candidate index,emit `statement.derived`(非 `statement.written`),Replay Scheduler 不订阅此事件 —— 闭环断开,无重入。

巩固结果带 `derivation_chain` 指回原 Statement。原始证据按 Drawer retention_mode 保留、脱敏或加密擦除,不再用"永不删除"作为统一规则。

### 10.4 自适应遗忘公式(v2 完整)

借鉴 MemoryBank(Ebbinghaus)+ Anderson active forgetting:

```
S(t) = exp(-Δt / S0(stmt))                                # 召回强度

S0(stmt) = base
         × (1 + 0.5 × access_count)
         × (1 + salience)
        × (1 + 2 × active_grounded)                      # 未过时共识衰减极慢
         × decay_modifier_by_modality                      # COMMITS 极慢,ASSUMES 快
         × (1 + 0.3 × |affect.valence|)                   # 情感色彩条目衰减略慢

# 状态迁移
state CONSOLIDATED → ARCHIVED  if S(t) < 0.05 AND not active_grounded
state ARCHIVED     → FORGOTTEN if explicit purge OR retention_policy expired
```

**FORGOTTEN 的语义(v6)**:Statement 从所有普通检索索引中剔除;DrawerRecord 根据 retention_mode 执行:
- `legal_hold`:保留密文和密钥,但访问需审计授权;
- `audit_retain`:保留到 retention_policy 到期;
- `redacted_retain`:原文替换为脱敏文本,保留 hash;
- `crypto_erasure`:销毁 key_ref,仅保留 hash/metadata/audit trail。

因此 Starling 保留"可解释的审计轨迹",但不承诺 verbatim 永远可恢复。

`active_grounded` 只对 CommonGround 中未 `expired/superseded/ungrounded` 的条目为 1。旧共识一旦被 SupersedeGround/ExpireGround/Unground 处理,不再获得衰减保护,避免"团队曾经共识过"的过时事实永久占据热路径。

> **v4 勘误**:v3 在此处写"claude-mem 的 cynical deletion 真删,Starling 永远可审计" —— **此为范畴错误**。claude-mem "cynical deletion" 实为代码风格运动:删除 defenders(orphan cleanup/多余 liveness probe)与 tolerators(silent JSON drops/passthrough Zod schemas),用 fail-fast 与 strict boundary 替代防御性 try/catch。它是代码质量策略,不是数据删除策略。v4 删除此错误对照。(ref: claude-mem ANTI-PATTERN-TODO.md 301 issues/289 fixed, CHANGELOG v12.4.7)

### 10.5 巩固分层策略(v2 吸收 Polis §4.6)

| 层 | 策略 | 触发条件 |
|---|---|---|
| **Hippocampus 短期** | 指数衰减 + 显著性补偿 | 默认每条 |
| **Episodic 长期** | 重要性 + 关联度排序后修剪 | Replay 每轮 |
| **Semantic** | **不删**,只下调 confidence 或转 OUTDATED | Reconsolidation 失败 |
| **隐私强制** | FORGOTTEN + redaction/crypto erasure;默认传播到直接依赖且无独立证据的 derived | 用户/法务事件 |

---

## 11. Reconsolidation Engine:被回忆即可塑

> 借鉴 Nader 2000 的再巩固理论 + Anderson 的自适应遗忘。**记忆不是存档而是不断被改写的活物**。

### 11.1 触发条件(v5 修正状态名 + 异步契约)

任意 `CONSOLIDATED` 或 `ARCHIVED` Statement 一旦满足以下之一,**异步进入** `REPLAYING_RECONSOLIDATING` 可塑窗口(**工程默认 30 分钟,可按 modality 与更新频率自适应在 5min–6h 之间调整;Nader 2000 神经科学参考值约 6h**):

1. 收到 `statement.recalled` 事件(由 Retrieval Planner emit;v5:**Retrieval 不直接开窗,异步处理**,见 §13.0)
2. 被新输入的 Statement 通过 `derivation_chain` 引用
3. 收到 `belief.conflict` 事件(由 ConflictProbe emit)
4. 显式 reconsolidate API 调用(audit / 用户编辑场景)
5. 收到 `commitment.fulfilled` / `commitment.broken` 事件(影响相关 Commitment Statement 的 confidence)

**契约(v5 新增,解 Major M5/M6)**:
- Reconsolidation Engine 是 Bus Subscriber,**不被任何模块同步调用**;所有触发走异步事件
- 同一 Statement 已在窗口内时,新触发不开新窗口,只追加证据到现有窗口的 `pending_evidence` 队列(防抖 §5.4)
- 窗口 close 时统一仲裁(批处理),减少争用与重入风险

**pending_evidence 容量规则(v10 新增)**:
- 单个可塑窗口最多保留 100 条 `pending_evidence`;超过后按时间戳 FIFO 淘汰,但保留被淘汰数量与摘要 hash 供审计。
- `access_count` 或触发频率超过高频阈值的 Statement,窗口自动缩短至 5 分钟,防止高频对象长期占用队列。
- 窗口 close 时 `aggregate_evidence` 默认只处理最近 50 条高权重证据;其余作为低权重背景统计输入。
- 同一窗口被触发超过 K 次(默认 K=10)后强制 close 并仲裁,后续事件排入下一窗口或被防抖合并。
- 队列容量、强制 close 与淘汰都必须 emit audit metadata,但不需要额外用户可见事件。

### 11.2 可塑期内可发生的修改(v6:severe path 原子事务)

```python
def reconsolidate(stmt, pending_evidence):
    """窗口 close 时由 Reconsolidation Engine 异步执行"""
    aggregated = aggregate_evidence(pending_evidence)  # 多证据聚合
    
    if supports(aggregated, stmt):
        with bus.transaction() as tx:
            stmt.confidence = bayesian_update_up(stmt.confidence, aggregated.strength)
            stmt.access_count += 1
            stmt.consolidation_state = CONSOLIDATED
            tx.upsert_statement(stmt)
            tx.outbox_append("statement.consolidated", stmt)
    elif contradicts(aggregated, stmt):
        if mild:
            with bus.transaction() as tx:
                stmt.confidence = bayesian_update_down(stmt.confidence, aggregated.strength)
                stmt.consolidation_state = CONSOLIDATED
                tx.upsert_statement(stmt)
                tx.outbox_append("statement.consolidated", stmt)
        else:  # contradict-severe
            with bus.transaction() as tx:
                new_version = stmt.fork(modifications=delta_from(aggregated))
                new_version.supersedes = stmt.id
                new_version.provenance = "reconsolidation_derived"
                new_version.review_status = review_status_for(aggregated)
                new_version.consolidation_state = CONSOLIDATED

                Validator.check(new_version)
                ConflictProbe.scan(new_version)
                tx.upsert_statement(new_version)

                stmt.consolidation_state = ARCHIVED
                tx.upsert_statement(stmt)
                tx.upsert_edge(new_version.id, "SUPERSEDES", stmt.id)
                tx.outbox_append("statement.corrected", {"old": stmt, "new": new_version})
                tx.outbox_append("statement.archived", stmt)
                tx.outbox_append("statement.superseded", {"old": stmt, "new": new_version})
    
    if affect_change_detected(aggregated):
        stmt.affect = blend(stmt.affect, aggregated.affect, weight=0.3)  # 情感染色
    
    # 窗口已 close,清空 pending_evidence,移交下一个事件批次
```

severe path 的关键不变量:
- 新版、旧版归档、SUPERSEDES 边、outbox 事件必须同事务提交。
- 新版不走 `tom_inferred`、不进入 VOLATILE、不 emit `statement.written`。
- 若 `review_status_for(aggregated)=REVIEW_REQUESTED`,新版仍可作为最新修正版进入 holder 子图,但 Context Pack 必须标注 REVIEW_REQUESTED,不得作为无条件 FACT 输出。

### 11.3 关键差别(对照现有系统)

- **mem0**:UPDATE 直接覆盖,旧值消失。
- **cognee**:improve() 已实装流式 feedback_weight alpha 更新(高分 boost、低分降权,按 batch_size 流式更新),但仍为离线批量(无在线增量 reconsolidation)。v3 写"权重更新算法 TODO"已过时。(v4 勘误)
- **Letta**:Block version 历史在(GitEnabledBlockManager 真 git,非伪 git),但**不区分"是否被回忆触发"**。sleeptime 触发仍是简单 turns_counter 取模,无 salience/conflict 优先级。
- **Starling**:**只有被回忆才能改**,且改完不删旧版,这正是大脑可塑性的工程模拟。

### 11.4 多主体场景的特别处理

当 Alice 说"其实 Bob 上周已经离职了":
1. 不无脑覆盖关于 Bob 的 statement;
2. 检索所有 `subject=Bob && valid_from < 该日期` 的 statement;
3. 每条进入 REPLAYING_RECONSOLIDATING 可塑窗口;
4. 由 Reconsolidation 用新证据评估 —— 部分加 valid_to 截断,部分仍保留(如"Bob 喜欢 PG"这种与离职无关的 trait)。

---

## 12. Prospective Loop:真前瞻

> 主流开源系统全部缺失,这是 Starling 与 RMM 之外少数把"前瞻"做成 first-class 的设计。

### 12.1 Trigger 类型系统

```python
class Trigger:
    kind: Literal["time","event","state","compound"]
    spec: TriggerSpec

# 例
TimeTrigger(at=datetime(...))
TimeTrigger(every="1d at 09:00")
EventTrigger(when="cognizer:Alice.observed")
EventTrigger(when="statement.written: predicate=mentions, object=X")
StateTrigger(predicate="goal:onboarding.completed")
CompoundTrigger(all_of=[...])
CompoundTrigger(any_of=[...])
```

### 12.2 Commitment 五态机(v6:所有终态都有 Bus 事件)

```
created → ACTIVE ──fire──► reminder 注入 Working Set
              │
              ├─ user 履行 ──→ FULFILLED ──→ emit commitment.fulfilled
              ├─ deadline 过 ──→ BROKEN ──→ emit commitment.broken
              ├─ 双方协商 ────→ RENEGOTIATED ──→ emit commitment.renegotiated
              │                              (新版 supersedes 旧)
              └─ 主动撤回 ────→ WITHDRAWN ──→ emit commitment.withdrawn
```

**v6 状态机细节**:
- `created` 态由 `modality=COMMITS` 的 Statement 经 Validator 通过后 Bus 自动转为 ACTIVE
- `BROKEN → RENEGOTIATED` 允许:现实中"我后来又答应你了"很常见,旧 BROKEN 不删,新 RENEGOTIATED 经 supersedes 链关联
- `FULFILLED` / `WITHDRAWN` 是终态,不可再变;`FULFILLED/BROKEN/RENEGOTIATED/WITHDRAWN` 都必须经 outbox 事件发布
- `commitment.withdrawn` 用于清理 PolicyEngine Trigger、释放"未结清承诺不得 ARCHIVED"约束、刷新 Working Set.pending_commitments

每条 Commitment 由后台 PolicyEngine 持续监听 Trigger,命中时**经 Bus outbox 发布 `commitment.fire`**(PolicyEngine 是 Bus 的 publisher 之一,所有 Trigger 命中走 `Bus.emit("commitment.fire", ...)`,不绕过 Bus),Working Set 注入 `pending_commitments` block。

**PolicyEngine 与 Bus 的关系(v5 新增,解 Major M8)**:
```
PolicyEngine
  ├── 订阅:commitment.fulfilled / commitment.broken / commitment.renegotiated / commitment.withdrawn
  │   (用于 Trigger 清理、trust_priors 调整、Persona Replay 候选)
  └── 发布:commitment.fire(Trigger 命中后,经 Bus.emit;不直接调订阅者)
```
PolicyEngine 内部是 Trigger Index + 时间堆;**所有外发都经 Bus**,所有内入也来自 Bus。这保证 §5"所有读写必经 Bus"硬约束在 §12 也成立。

### 12.3 与 RMM 互补

- **RMM 的 prospective reflection**:为未来检索友好的摘要(被动);
- **Starling 的 Prospective Loop**:if-then 触发器 + 状态机(主动);

两者**不冲突**,合并产出"既会被动检索友好、又会主动出发"的记忆体。

### 12.4 Norm 与 Commitment 的关系

Norm 是 Group 内的默认规则;违反时 emit `norm.violated`,作为高 salience EpisodicEvent 入 Affect Buffer。Commitment 是个体对个体的具体承诺。两者通过 `induce_norm` 操作(§10.3)连接 —— 多次相似 Commitment 模式可凝结为 Norm 候选。

### 12.5 ActionPolicyGraph:前瞻动作护栏(v13 新增)

Prospective Loop 可以只提醒用户,也可能在产品化后触发工具或外部动作(发通知、开 issue、创建日历、调用业务 API)。提醒可轻量;真实动作必须先通过 `ActionPolicyGraph`。

```python
class ActionPolicyRule(BaseModel):
    kind: Literal["init","parent_child","conditional","max_count",
                  "terminal","required_before_exit","requires_approval"]
    action_name: str
    target_actions: list[str] = []
    condition: Optional[str]
    max_count: Optional[int]
    prefilled_args: dict = {}

class ActionPolicyGraph(BaseModel):
    profile_name: str
    rules: list[ActionPolicyRule]
    audit_mode: Literal["enforce","dry_run","disabled"] = "enforce"
```

规则:
- `commitment.fire` 只能把 pending reminder 注入 Working Set;若要调用外部 tool/action,必须经 `ActionPolicyGraph.allowed_next_actions(history, available_actions)`。
- `requires_approval` 命中的动作进入 human approval 队列,不得由 LLM 自行确认。
- `required_before_exit` 用于保证外部动作前后置完整,如"创建日历前必须确认时区","发送提醒后必须记录 delivery receipt"。
- `max_count` 防重复投递;它与 §5.4 business idempotency window 互补:前者限制单次 action graph,后者限制 at-least-once 事件重复。
- `terminal` 动作结束该 Prospective run;后续动作必须新建 causation_chain。
- Policy 失败默认 fail-closed,emit `action.policy_blocked`,并在 `PipelineRun.stage_timings_ms / warnings / counters` 中可见。

---

## 13. Retrieval Planner:视角感知检索 + 心智摘要

> 检索是"认知规划器",不是"工具堆"。这是公理 III 的运行时体现。

### 13.0 读副作用契约(v5 新增,解 Major M6)

> **v4 缺口**:§11.1 把"被 Retrieval 召回"列为 Reconsolidation 触发条件之一,意味着读路径产生写副作用 —— 可重入性、并发、缓存一致性全部受影响,但 §13 未提。v5 显式契约。

**Retrieval Planner 是纯读模块**(对外可见效果上):
1. **Retrieval 自身不改 Statement 状态**(不直接写 confidence、不直接开 Reconsolidation 窗口、不改 supersedes 链)
2. **Retrieval 仅 emit `statement.recalled` 事件**(异步,fire-and-forget),订阅者(Reconsolidation Engine)异步决定是否开窗
3. **同 query 重复执行幂等**:同一 (querier, perspective, intent, text, time) 在 N 秒(默认 2s)内多次调用,返回相同结果,事件去重
4. **Retrieval 内部使用的 activation/access_count 计数是 in-memory 软统计**,通过 Replay Scheduler 周期性批量 flush 到 Statement;非每次召回即写库

**异步链路(v5)**:
```
Retrieval.fetch(query)
  → 并发查 Substrate
  → emit "statement.recalled" × N (异步,Bus 防抖合并)
  → 返回 Result
  
[异步并行]
Bus → Reconsolidation Engine
  → 判定:命中是否触发 REPLAYING_RECONSOLIDATING?
    - 频繁召回(短窗口内 ≥ K 次):是
    - 与近期 belief.conflict 同 key:是
    - 单次命中且无冲突:否,只 ↑ 软 activation
  → 若是,开窗;若否,跳过
```

这保证 §13 的执行模型是**幂等+无状态**(对外),Reconsolidation 副作用是**事件驱动+异步聚合**,与 §5.4 防抖契约对齐。

### 13.1 输入与输出

```python
class Query:
    querier: CognizerRef                   # 谁在问(默认 self)
    perspective: CognizerRef               # 从谁的视角检索(默认 = querier)
    intent: QueryIntent                    # 见 §13.2
    text: str
    time: datetime                         # 检索时间锚("as_of")
    goal_context: Optional[GoalRef]
```

```python
class RetrievalScopeStep(BaseModel):
    scope: Literal["working_set","statement_main","projection_index","semantic_index",
                   "graph_index","container_view","drawer_evidence","tom_runtime"]
    adapter_scope: Optional[str]             # 外部库原生 scope,如 cognee:session/trace/graph_context,只作 metadata
    holder_scope: Optional[CognizerRef]
    group_scope: Optional[str]
    filters: dict
    max_candidates: int
    on_error: Literal["degrade","abstain","fail_closed"]

class RetrievalScopePlan(BaseModel):
    plan_id: str
    mode: Literal["basic","progressive","parallel","exhaustive"]
    steps: list[RetrievalScopeStep]
    stop_policy: Literal["after_first_sufficient","merge_all","needs_raw_gate","abstain_on_gap"]
    merge_policy: Literal["ranked_union","intersection","priority_order","rrf"]
    filter_mode: Literal["global_inherited","per_scope_explicit"]
```

Filter 规则:
- `global_inherited`:所有 scope 使用同一组 tenant/holder/review/evidence 过滤,只能追加更窄条件。
- `per_scope_explicit`:每个 scope 必须显式给出完整 tenant/holder/group filter。
- 禁止同一个 plan 同时使用全局 filter 又让部分 scope 自带不同 holder/group;这种混合形式必须拒绝,写入 `RetrievalReceipt.abstention_reason=invalid_scope_filter_mix`。
- `basic_retrieve` 的 plan 固定为 `mode=basic, steps=[statement_main], stop_policy=merge_all`。
- v14 收敛规则:Planner 只识别 Starling 逻辑 scope。`session/trace/graph_context/episode/community/vector_collection` 等外部库名词只能写入 `adapter_scope` 与 `plan_steps`,不得进入核心枚举,避免检索层随底座变化而重写。

### 13.2 9 种 QueryIntent

```python
class QueryIntent(Enum):
    FACT_LOOKUP        # 查事实
    BELIEF_OF_OTHER    # 查 X 相信什么
    META_BELIEF        # 查 X 以为 Y 知道什么(二阶,深度上限受 §9.6 ToMDepthEstimator 调制)
    HISTORY            # 查时间线
    COMMITMENT_DUE     # 查待办
    PREFERENCE         # 查偏好
    NORM_LOOKUP        # 查规范
    COMMON_GROUND      # 查共识
    ABSTAIN_CHECK      # 主动检查"是否真的不知道"
```

### 13.3 7 步规划

```
1. parse:    Query → intent + 关键 entity
2. mask:     按 perspective 的 KnowledgeFrontier 遮蔽不可见证据(EnigmaToM iterative masking)
3. plan:     按 intent 选择路径(下表)
4. fetch:    并发执行多源(向量 / 图 / KG / Drawer / Working Set / ToM API)
5. fuse:     按 holder 子图 + salience + recency 重排
6. ground:   检查 CommonGround,标"已 grounded"以便复述抑制
7. abstain:  Abstention Gate(详见 §13.7)—— 总分不足或证据不可信则输出"无可靠记忆",避免编造

# 步骤 4 fetch 完成后,**异步** emit "statement.recalled" 事件(每条命中一次,Bus 防抖合并),
# Reconsolidation Engine 异步消费判定是否开窗(§13.0 + §11.1)。Retrieval 主流程不等待。
```

**holder/group search isolation(v12 新增)**:
Graphiti 的 multi group search 与 EverOS 的 tenant command interceptor 都提醒:多主体检索不能退化为一个宽泛 `holder IN (...)` 扫描后在应用层过滤。规则:
- 当 query 涉及多个 holder、party、tenant、CommonGround group 或 perspective 时,Planner 必须为每个 holder/group 构建独立 substrate context,分别执行 fetch,再在 fuse 阶段合并。
- 每个子查询的 filters 必须包含单一 `tenant_id + holder_scope/group_scope`,并写入 `RetrievalReceipt.filters_applied`。
- 并发度按 `ScopedWorkGate(lane=retrieval)` 限制;某个 holder/group 失败只降级该 scope,不得扩大到无 scope fallback。
- merge 阶段只处理 StatementRef/score/metadata,不得重新打开未授权 Drawer raw 内容。
- P0 的 `basic_retrieve` 只支持单 holder;传入多 holder 必须拒绝或显式拆分调用,不能 silently broaden。

**渐进式 scope plan(v13 新增,v14 收敛)**:
cognee recall 的 `session/trace/graph_context/graph` 顺序、memU 的 category→item→resource sufficiency gate、Graphiti 的 edge/node/episode/community 多 scope trace 都说明,检索规划器需要显式记录"查了哪里、为什么停、为什么没查更贵路径"。Starling 因此规定:
- Progressive plan 先查 `working_set / statement_main / projection_index` 等低成本 scope;若 `sufficiency_status=SUFFICIENT` 且 stop_policy 允许,跳过 `graph_index / semantic_index / drawer_evidence`。
- Scope 被跳过必须写 `skipped_scopes` 与 `stop_reason`;不能让 Receipt 看起来像全量检索。
- Scope 失败只能按该 step 的 `on_error` 降级;不得自动扩大 holder/group 范围。
- `NEEDS_RAW` 不是直接打开 Drawer,而是触发 raw evidence gate;gate 失败则 `ABSTAINED` 或 `MISSING_INFO`。

### 13.4 Intent → Path 映射

| Intent | 主路径 | 辅助 |
|---|---|---|
| FACT_LOOKUP | Neocortex Semantic(holder=self) + Drawer 证据 | Working Set |
| BELIEF_OF_OTHER | Neocortex Semantic(holder=target) | Drawer 中 target 发言 |
| META_BELIEF | 嵌套 Statement(nesting_depth=2) | perspective_take 即时构建 |
| HISTORY | 时间索引 + supersedes 链 | Drawer time-window |
| COMMITMENT_DUE | Prospective Loop 队列 | — |
| PREFERENCE | Persona.preferences | PREFERS 类 Statement |
| NORM_LOOKUP | Norms 子区 + scope 过滤 | enforcement_history |
| COMMON_GROUND | CommonGround pool(parties=...) | — |
| ABSTAIN_CHECK | 跨子区低召回判定 + 校准置信度 | KnowledgeFrontier |

**P0 最简 Retrieval 闭环(v7 新增)**:
P0 不实现完整 7 步 Planner,但必须实现一个可演示闭环:

```python
basic_retrieve(
    holder=self,
    intent=FACT_LOOKUP,
    subject=...,
    predicate=...,
    as_of=now(),
) -> list[Statement]
```

约束:
- P0 阶段只查 Statement 主表的轻量索引 `(holder, consolidation_state, valid_from, valid_to)`;P2 后可切换为 `idx_holder_state_time`;
- 只返回 `holder=self` 且 `consolidation_state in {CONSOLIDATED, ARCHIVED}` 的 Statement;
- 过滤 `review_status in {REJECTED, PENDING_REVIEW}` 与 `EvidenceRef.status=ERASED only` 的结果;
- 不做 rerank、不做 ToM、不做 CommonGround,但返回 evidence hash/source metadata。

P0 验证目标是"Bus.append_evidence → Extractor → Bus.write → Replay compress/consolidate → basic_retrieve"可跑通,避免只冻结 schema 而没有端到端读路径。

### 13.5 Affect-aware Reranker

```python
def rerank(candidates, querier_state):
    for c in candidates:
        c.score = (
            base_relevance(c)
            * (1 + 0.3 * recency_factor(c))
            * (1 + 0.4 * c.salience)
            * (1 + 0.3 * activation_level(c))
            * affect_consistency(c.affect, querier_state.affect)  # 情感一致性 boost
            * (1 - temporal_distance_penalty(c, query_time))      # v4 增:时间距离惩罚(借鉴 cognee temporal_retriever)
        )
    return sorted(candidates, key=lambda c: -c.score)
```

**v4 增——Coarse-to-fine RRF 方向**:EverOS HyperMem (2026 ACL) 使用三级 coarse-to-fine 检索: Stage1 Topic → Stage2 Episode → Stage3 Fact,以 RRF $\sum 1/(k+\mathrm{rank}_m)$ 融合 BM25+dense,LoCoMo 92.73% 超越 MemOS 16.93 个点。Starling 当前 reranker 是单级加权乘子,可升级为 HyperMem 风格的三级 RRF 融合,尤其适合"先从大量 candidate 中筛 Topic,再精排 Episode→Fact"的大记忆体场景。进 P4 检索规划器时选配。

**v4 增——时间距离惩罚项**:cognee `temporal_retriever.py` 用 `triplet_distance_penalty`(默认 6.5)在距离查询时间窗的 triplet 上降权。Starling 已有 `recency_factor(c)`,但无显式的"事件时间距离查询锚点"的绝对值惩罚。v4 在 rerank 公式中新增 `temporal_distance_penalty` 项。

**v11 增——vector-anchored fusion**:EverOS EverCore 的 `vector_anchored_fusion` 把 BM25 原始分数先做饱和归一 `bm25_sat = raw / (raw + k)`,再与 vector score 加权求和,并用各路径最低召回分作为 missing-side floor。Starling P4 若启用 hybrid/RRF,默认采用此思想防止 BM25 raw score 压倒语义分数:

```python
score = alpha * vector_score_or_floor + (1-alpha) * bm25_saturated_or_floor
```

默认 `alpha=0.7, saturation_k=5.0`;最终 score breakdown 必须写入 §13.6.1 `RetrievalReceipt`。

### 13.6 Context Pack Builder:心智摘要(v2 吸收 Polis §6.2)

**关键差异**:Starling 输出的不是一段 RAG 文本,而是**带语用标注的"心智摘要"**:

```
[FACT]   Bob 当前负责 auth(Alice 在 4/15 群聊宣布,共识已建立)
[BELIEF] 据 Carol 所知,新方案下周一上线(置信 0.7,但 Bob 暂未确认)
[HEARSAY] 我听 Alice 说 Bob 上周休假(单一来源,可能过时)
[INFERRED] 根据 Bob 长期工作模式,他可能晚于 deadline 交付
[COMMON]  我们都知道:本季度的目标是发布 v2
[TODO]   你 3/12 答应给 Alice 看代码(还有 2 天)
[CONFLICT] 关于 X 的负责人:Alice 认为是 Bob,Carol 认为是 Dave —— 待澄清
[ABSTAIN] 关于 Y 的最新进展:无可靠记忆(Bob 上次提及在 2 月,之后无更新)
```

**8 个标签**:`FACT / BELIEF / HEARSAY / INFERRED / COMMON / TODO / CONFLICT / ABSTAIN`。

LLM 看到的不是无差别文本块,而是已经被分类、归因、置信度标注的语用结构。**这是 Starling 让 LLM"懂语境"的物理基础**。

### 13.6.1 RetrievalReceipt:检索回执(v11 新增)

Context Pack 是给 LLM 的心智摘要;RetrievalReceipt 是给系统、评测和审计的可观测回执。Graphiti 的多 scope search trace、EverOS StageTimer、memU sufficiency check、mempalace query sanitizer 都说明:没有回执,检索失败只能靠猜。

```python
class RetrievalReceipt(BaseModel):
    trace_id: str
    query_id: str
    querier: CognizerRef
    perspective: CognizerRef
    intent: QueryIntent
    runtime_health: Literal["READY","DEGRADED","DRAINING","UNREADY"]
    trace_retention: Literal["metadata_only","hash_only","redacted_debug","full_debug"]
    sanitized_query: Optional[dict]         # method/original_length/clean_length
    sufficiency_status: Literal["SUFFICIENT","MISSING_INFO","NEEDS_RAW","ABSTAINED"]
    scope_plan: Optional[RetrievalScopePlan]
    plan_steps: list[dict]                  # parse/mask/plan/fetch/fuse/ground/abstain
    skipped_scopes: list[dict]              # scope + reason + stop_policy
    stop_reason: Optional[str]
    projection_lag: dict                    # per projection: lag_seconds/sequence_delta/stale
    scopes_searched: list[str]              # Starling scope:statement_main/semantic_index/graph_index/container_view/...
    filters_applied: list[dict]             # holder/perspective/tenant/review/evidence erasure/access policy
    candidate_counts: dict                  # fetched/reranked/returned/dropped_by_mask/dropped_by_review
    score_breakdown: list[dict]             # statement_id, base/vector/bm25/salience/recency/final
    evidence_erased_count: int
    degraded_paths: list[dict]              # path + reason + fallback
    abstention_reason: Optional[str]
    emitted_events: list[str]               # statement.recalled ids or empty when suppressed
```

规则:
- 每次 Retrieval 都生成 receipt;P0 的 `basic_retrieve` 可只填 `trace_id/query_id/filters_applied/candidate_counts/evidence_erased_count`。
- 若 query 过长或疑似被系统提示污染,先执行 query sanitizer,receipt 记录清洗方法;清洗失败才走原 query。
- projection lag 超过 §4.1 SLA 时,receipt 必须记录 `degraded_paths` 与 fallback;若没有 fallback,Context Pack 加 `[ABSTAIN]` 或 stale 标记。
- `filters_applied` 必须能证明 perspective filter 与 tenant/holder scope 已执行,否则结果不得返回。
- `scope_plan` 必须能解释每个 scope 的 filter 来源、holder/group、fallback 与 stop policy;若 plan 因 `working_set/statement_main` 已足够而短路,`skipped_scopes` 必须列出未查的 `semantic_index/graph_index/drawer_evidence`。
- `score_breakdown` 只记录可审计分数与 StatementRef,不泄露被遮蔽证据正文。
- `sufficiency_status=SUFFICIENT` 表示 Context Pack 足以回答;`MISSING_INFO` 表示已检索但缺关键证据;`NEEDS_RAW` 表示摘要/Statement 不足,需要打开 Drawer raw evidence,此时必须先通过 retention/visibility 检查并在 receipt 记录 raw-evidence request;`ABSTAINED` 表示主动拒答。
- trace 默认遵守 `metadata_only/hash_only`;`redacted_debug/full_debug` 只能在 debug profile 或单次授权下启用,并受 §5.6 Trace retention tiers 约束。
- 评测体系可直接用 receipt 判断召回失败属于"没查到"、"被权限遮蔽"、"projection stale"还是"主动 abstain"。

### 13.7 Abstention(主动拒答,LongMemEval 关键失分项)

```
abstain if:
    max_score < tau_recall                # 召回分太低
    OR perspective frontier 不允许该信息
    OR 唯一证据来自已 RECANTED 链
    OR conflict 未仲裁(请求澄清而非赌一边)
```

abstain 时输出结构化"我不知道,因为 ___",而非编造或 "I'm not sure"。

---

## 14. 端到端数据流(典型场景)

### 14.1 写入路径

**场景**:Alice 在群聊里说"Bob 不再负责 auth 模块,改由 Carol 接手"。

```
Bus.append_evidence(verbatim Alice 原话,
                    perceived_by=[self,Alice,Bob,Carol,...],
                    retention_mode=audit_retain)
   ↓ outbox: evidence.appended → Extractor
   ↓ EM-LLM 切边界 → EpisodicEvent
   ↓ Pattern Separation:与现有 "Bob responsible_for auth" 高度相似 → 反相似偏移 + MAY_OVERLAP_WITH 软边
   ↓ LLM 抽取 4 条候选 Statement(XML 严格):
[
  S1: holder=self,  subject=Bob,   pred=responsible_for, obj=auth, mod=BELIEVES, pol=NEG, valid_to=NOW
  S2: holder=self,  subject=Carol, pred=responsible_for, obj=auth, mod=BELIEVES, pol=POS, valid_from=NOW
  S3: holder=self,  subject=Alice, pred=BELIEVES, obj=⟨S2⟩, nesting_depth=1   # 二阶
  S4: holder=Alice, subject=Bob,   pred=responsible_for, obj=auth, mod=BELIEVES, pol=NEG, valid_to=NOW
]
   ↓ Validator → ConflictProbe:发现旧 Statement(holder=self, Bob responsible)
   ↓ 决策树:同 holder + 时间更晚 + 隐式改口 → 旧 confidence 衰减,新版共存,触发 Reconsolidation 候选
   ↓ Bus.write × 4: Hippocampus upsert + outbox(statement.written × 4) 同事务
   ↓ Affect Scorer:salience 高(stakes 高,涉及职责变更)→ Affect Buffer 优先队列
   ↓ ToM Engine 更新:
       - CommonGround(self,Alice,Bob,Carol):S1/S2 已 grounded(都在场)
       - 若 Bob 不在场 → 不进 (self,Bob) common,只进 (self,Alice/Carol)
       - 触发 perceived_by=[Bob] 检查 → Bob 在 → 标"Bob 应已知"
   ↓ Reconsolidation Engine:旧 Bob 责任 statement 进入 REPLAYING_RECONSOLIDATING 可塑窗口(高频更新场景缩短至 5min,见 §11.1)
      新证据强 → 同事务写新版 + 旧版 ARCHIVED + supersedes + outbox(statement.corrected)
```

### 14.2 检索路径

**场景**:用户问"Bob 现在还负责 auth 吗?"

```
Query(intent=FACT_LOOKUP, perspective=user, text=...) → Planner
   ↓ parse: subject=Bob, predicate=responsible_for, object=auth
   ↓ mask: querier=user(无遮蔽,user 即 self perspective)
   ↓ plan: FACT_LOOKUP path
   ↓ fetch:
       Neocortex(holder=self).query: 命中 supersedes 链(新 Carol responsible / 旧 Bob ARCHIVED)
       Drawer time-window: 关联 Alice 4/15 原话 + 历史 Bob 持有 auth 的证据
       ToM API: shared_with([self,user]) 检查共识
   ↓ fuse: valid_to 近 + supersedes → "已变更,现 Carol 负责"
   ↓ ground: CommonGround(self,user) 不含此事 → 主动 grounding
   ↓ Reranker: 高 stakes + recency boost
   ↓ Context Pack Builder:
[FACT]    Bob 已不再负责 auth,现由 Carol 接手(Alice 4/15 群聊宣布,evidence: Drawer:abc123)
[HISTORY] Bob 此前负责该模块达 8 个月,如需历史设计讨论我可以拉出
[COMMON]  这是首次告知你,需要确认你已知悉吗?
   ↓ output(经 LLM 渲染)
```

### 14.3 二阶 ToM 路径

**场景**:用户问"Bob 知道这事吗?"

```
Query(intent=META_BELIEF, target=Bob, about=⟨Carol now responsible⟩)
   ↓ Planner → Mentalizing API: does_X_know(X=Bob, fact=⟨...⟩)
   ↓ 检查:
       1. perceived_by 含 Bob? → 检索 Episode 4/15 群聊参与者 → ✓ Bob 在
       2. explicit_told? → 检索后续是否私聊告知 → 无补充
       3. 检索 holder=Bob 近期发言:有无相关动作/提问? → Bob 之后无回应
   ↓ 综合判定:
       Bob 应已知(感知充分)
       但无主动确认 → suspected_diverge 候选
   ↓ Context Pack:
[INFERRED] Bob 当时在群里(perceived_by 命中),应该已知
[HEARSAY]  但他之后没有相关回应,如果重要可以确认
[TODO]     建议:私聊 Bob 确认 + 同步 Carol 接手计划
   ↓ output
```

### 14.4 Prospective Loop 触发路径(v3 新增)

**场景**:周一,Bob 答应"周三前给 Alice 看新方案的草稿"。周三上午 9 点,系统主动触发提醒。

```
─── 周一 14:30 写入阶段 ───
Bus.append_evidence(Bob 原话: "我周三前把草稿发给你",
                    perceived_by=[self, Bob, Alice],
                    retention_mode=audit_retain)
   ↓ outbox: evidence.appended → Extractor
   ↓ EM-LLM boundary_score 高(承诺类话语 surprise 显著)→ EpisodicEvent
   ↓ LLM 抽取(XML strict):
[
  S1: holder=Bob, modality=COMMITS, polarity=POS,
      principal=Bob, beneficiary=Alice,
      subject=Bob, predicate=will_deliver, object=draft,
      trigger=TimeTrigger(at="2026-05-06 09:00"),
      deadline="2026-05-06 23:59",
      state=ACTIVE,
      affect={valence:0.3, arousal:0.4, novelty:0.5, stakes:0.7}
  S2: holder=self, modality=BELIEVES, polarity=POS, object=⟨S1⟩  # self 知道 Bob 答应了
  S3: holder=Alice, modality=BELIEVES, polarity=POS, object=⟨S1⟩  # Alice 也知道(在场)
]
   ↓ Validator + ConflictProbe(无冲突)
   ↓ Bus.write × 3: Hippocampus upsert + outbox(statement.written)
   ↓ Prospective Loop 订阅器命中 modality=COMMITS:
       - 注册 TimeTrigger(at=周三 09:00) 到 PolicyEngine
       - 进 Working Set.pending_commitments block
   ↓ CommonGround(self, Bob, Alice).asserted_unack += S1
       (双方都听见,但还没显式 acknowledge → 未到 grounded)
   ↓ Affect Buffer 入队(stakes=0.7,salience 较高)

─── 周一晚 ~ 周二 巩固阶段 ───
Replay Scheduler(Idle 模式,优先级采样 S1 高权重)
   ↓ 不仲裁(无冲突),但加强 activation
   ↓ S1 进 CONSOLIDATED,Commitment.state 仍 ACTIVE
   ↓ Reconsolidation 监听:无新证据,跳过

─── 周三 09:00 触发阶段 ───
PolicyEngine 后台轮询 Trigger 队列
   ↓ TimeTrigger 命中 → emit commitment.fire(S1)
   ↓ Working Set.pending_commitments 注入提醒
   ↓ 系统自主决策:
       检查 holder=Bob 子图:Bob 周二是否有"已发草稿"的 statement? → 无
       检查 Drawer 周二消息:Bob 是否单方面 RENEGOTIATE? → 无
       检查 perceived_by=[self,Bob,Alice]:此时谁在线? → self 与用户在线
   ↓ Retrieval Planner(intent=COMMITMENT_DUE)生成 Context Pack:
[TODO]    Bob 答应今天前把方案草稿发给 Alice(周一约定,evidence: Drawer:xyz)
[FACT]    截至现在尚未看到草稿,Alice 也未确认收到
[COMMON]  这是 Bob 与 Alice 的共识(你也在场)
[INFERRED] 建议:可以提醒 Bob,或先问 Alice 是否已私下收到
   ↓ output: agent 主动开启对话:
     "对了,Bob 周一答应今天前给 Alice 看草稿,但我没看到他发出来。
      要不要我帮你提醒一下?"

─── 后续(假设 Bob 当天交付)───
   ↓ 检测到 Bob 发送 draft(新 EpisodicEvent → 抽取 fulfilled_by 关联)
   ↓ Prospective Loop:Commitment.state ACTIVE → FULFILLED
   ↓ trust_priors[self→Bob] 微调上(履行成功)
   ↓ CommonGround(self,Bob,Alice).grounded += S1
   ↓ Reconsolidation:S1 进 REPLAYING_RECONSOLIDATING 可塑窗口,
       结合"已履行"事实,confidence ↑,加 evidence_for 边
```

**关键差异点**:现有开源系统没有任何一个能在没有用户手动 query 的情况下"周三早上自己想起来这件事"。Starling 通过 Trigger + PolicyEngine 把"主动惦记"做成了运行时一等公民 —— 不依赖 cron job 或外部 reminder,而是从 Statement 数据本身派生触发条件。

---

## 15. 评测体系

Starling 的评测不能止于 RAG/QA 指标 —— 类脑记忆的"更像人"和社会心智的"更懂人"需要专门的评测维度。

### 15.1 类脑记忆评测

| 评测项 | 方法 / 数据集 | 核心指标 | Starling 对应机制 |
|---|---|---|---|
| 长期多会话回忆 | LongMemEval 五类问题(单跳/多跳/时间/更新/缺失) | 分类 accuracy | Statement 抽取 + holder 归属(§3.2)+ Replay 巩固(§10) |
| 时序推理 | LoCoMo 时间线 / 自建时间锚点 QA | 时间顺序正确率、valid_from/to 边界准确率 | §3.2 五种时间字段 + §13 time-aware planner |
| 模式补全质量 | 自建:给 partial cue(如"那次和 Alice 去的咖啡馆"),评估回忆完整度 | Recall@k of related episode subgraph | CA3-style PPR 图游走(§6.4) |
| 模式分离能力 | 注入高度相似但不同的两个 episode,检查是否混淆 | 混淆率(越低越好) | 写入反相似性偏移 + MAY_OVERLAP_WITH 软边(§6.3) |
| 巩固一致性 | 注入冲突信息,检验多视角保留 | 冲突保留率 + supersedes 链完整率 | 冲突决策树(§7.3)+ Reconsolidation 不覆盖(§11) |
| 自适应遗忘 | 注入大量噪声 statement,观察查询效率 | Latency vs total memory size 曲线,关键记忆保留率 | MemoryBank + Anderson 公式 + 降级不删除(§10.4) |
| 情感记忆偏置 | 配对高/低情感事件,间隔测试 | 高情感事件回忆优势比(模拟人类效应) | AffectVector.salience 调制写入强度与重放优先级(§3.9 + §10.2) |
| 再巩固保真度 | 注入需修正的旧信念,检查修正后旧版本可追溯性 | 旧版本可检索率、新版本引用率 | Reconsolidation 状态机(§11)+ supersedes 链保留历史(§7.3) |

### 15.2 社会心智评测

| 评测项 | 方法 / 数据集 | 核心指标 | Starling 对应机制 |
|---|---|---|---|
| 一阶 ToM(信念归因) | ToMBench / SocialIQA | 信念归因 accuracy | holder=other 子图(§7.2)+ KnowledgeFrontier mask(§8.2) |
| 二阶 ToM(嵌套信念) | FANToM / Hi-ToM / EnigmaToM | 嵌套信念 accuracy | 嵌套 Statement nesting_depth(§9.1) |
| 信息不对称(FANToM) | FANToM 标准集 | 不对称检测 F1 | perceived_by + presence_log(§3.2 + §8.2) |
| 多视角切换(SoMi) | SoMi-ToM 1225 题(第一/第三人称双视角) | viewer-conditioned QA accuracy | perspective_take 算子(§9.3)+ holder-aware 检索(§7.2) |
| 共同知识建立 | 自建:多主体对话中追踪 SharedGround | common ground inference F1 | CommonGround pool(§3.6)+ explicit grounding acts(§9.5) |
| 承诺履行 | 自建:对话中含承诺,检验 N 步后触发 | Commitment detection + reminder timeliness | Prospective Loop + Trigger 类型系统(§12) |
| 信念修正传播 | 注入"其实...是错的"修正,看关联信念是否联动更新 | 旧信念使用率(应趋零) + 旧版本可追溯性 | Reconsolidation 多主体处理(§11.4)+ supersedes 链 |
| 视角泄露防护 | 自建:检查是否向未在场者泄露信息 | 视角泄露率(应趋零) | EnigmaToM 风格 iterative masking + perspective filter(§13.3 step 2) |
| 二阶 ToM 主动提示 | 自建:"你应该提醒 Bob,他可能还不知道..." | 主动提示 precision/recall | META_BELIEF QueryIntent(§13.2)+ suspected_diverge 标记(§3.6 CommonGround) |
| 自适应 ToM order | A-ToM 复现 / 自建跨 partner 协作集 | partner ToM order 估计 accuracy + 协调收益 | ToMDepthEstimator 模块(§9.6)+ nesting_depth 动态上限 |

### 15.3 主观评测

- **Persona 稳定性**:Starling 加持的 agent 在多轮对话中是否保持对用户的理解一致,不被单次对话颠覆长期画像。度量:注入前后 Persona Statement 的 drift 距离。
- **"懂我"主观评分**:7-point Likert,覆盖(记得我的偏好 / 知道我和别人的关系 / 不会把别人的话当成我的 / 会主动惦记我的承诺 / 说错了能追溯)。
- **可解释性**:当 agent 输出错误信念时,用户能否追溯到具体 Statement + evidence(Drawer 指针)。度量:错误定位时间。
- **过度自信拒绝率**:Abstention 判定在实际对话中的 precision/recall(该拒时有没有拒、不该拒时有没有乱拒)。

### 15.4 评测执行策略

- **Phase 0-1**:单元测试覆盖 schema 正确性 + 50 条对话样本的手工标注回归集。
- **Phase 2-3**:LongMemEval 子集 + ToMBench / FANToM 标准集 + 自建承诺履行集(100 条)。
- **Phase 4+**:LoCoMo 全量 + SoMi-ToM 1225 题 + 自建二阶 ToM 主动提示集 + 用户主观评测(A/B 对照,Starling vs 纯 RAG baseline)。

---

## 16. 路线图

### 16.1 六阶段交付

| 阶段 | 时间 | 目标 | 核心交付 | 验证方式 |
|---|---|---|---|---|
| **P0 Spike** | 2 周 | 可执行契约冻结 + 最小闭环 | Statement + Cognizer + 六态 ConsolidationState + StatementProvenance + ReviewStatus + DrawerRetentionMode 的 Pydantic 实现与 JSON-Schema 导出;SQLite 单底座 CRUD;outbox 表;`ProfileCapability` preflight;最小 `PipelineRun/ExtractionAttempt` 账本;`SourceKind/IngestPolicy` 与 source adapter metadata;`SourceSpanRef/TemporalAnchor` 字段但只实现 direct_api/单片段;一阶 Statement 抽取 prompt(XML strict);`basic_retrieve(holder=self, intent=FACT_LOOKUP)` 主表直查 + 最小 `RetrievalReceipt` | 单元测试 + 50 条手工标注对话样本回归 + outbox 投递/幂等测试 + §14.1 最小变体 smoke test: Alice 宣布 Bob 不再负责 auth,检索返回 Carol 接手,并能查看 extraction attempt、pipeline run 与 retrieval receipt |
| **P1 社会心智 Schema** | 4 周 | 多主体认知层上线 | Cognizer Hub(注册 + 别名归一 + 关系类型);holder 子图族;KnowledgeFrontier 计算;冲突检测 + CONFLICTS_WITH 边;perspective_take 算子 v1 | ToMBench 一阶 ToM + FANToM 信息不对称 |
| **P2 类脑动力学 v1** | 6 周 | CLS 双系统 + 巩固回路 | Hippocampus/Neocortex 逻辑分区标签 + Projection Index;Replay Scheduler(周期采样 + 聚类 + 三动作);模式分离/补全(反相似偏移 + PPR 图游走);Reconsolidation 原子事务(不覆盖) | LongMemEval 时间 + 更新两类显著提升;模式分离混淆率 < 15%;主表查询不承担五维复合索引 |
| **P3 前瞻 + 情感** | 4 周 | 承诺记忆 + 情感调制 | Commitment 状态机 + 4 类 Trigger(time/event/state/compound);Prospective Loop 调度器;AffectVector 五维 + salience 公式;优先级重放权重 | 自建承诺履行集(100 条):detection > 80%,timeliness < 3 turns |
| **P4 检索规划器 + 二阶 ToM** | 4 周 | 智能检索 + 深度社会推理 | Retrieval Planner 完整 7 步 + 9 种 QueryIntent;perspective filter(iterative masking);Abstention 判定;Context Pack Builder 8 标签;二阶 ToM(nesting_depth=2)全链路;**ToMDepthEstimator(§9.6 A-ToM 风格)** | ToMBench / FANToM / SoMi-ToM 全量;二阶 ToM 主动提示 precision > 70%;ToMDepth 估计 accuracy > 60% |
| **P5 产品化 + 多底座** | 4 周 | 可对外交付 | Substrate Adapter 5 profiles(local-lite/graph/cloud-graphiti/letta-bridge/cognee-bridge);mem0 / Letta / cognee / Graphiti / **EverOS HyperMem(coarse-to-fine RRF 选配)** 迁移脚本;评测体系全量跑通;API 文档 + 接入指南 | 用户主观评测 A/B 对照;5 种迁移路径的集成测试 |
| **P6 持续演进** | 持续 | 多主体协作 + 形式化扩展 | 群聊 SharedGround 维护;Multi-agent 信任传播;PDDL 形式化 belief base(可选高阶);神经-符号混合实验 | 研究导向,无硬性交付节点 |

**P0 负面验收用例(v10 新增)**:
- 隐私拒收:DrawerRecord 含隐私越界内容 → Validator 拒收 → emit `extraction.failed(privacy_violation)` → 不重试,进入 dead-letter / audit。
- 冲突共存:注入两条不同 holder 的矛盾 Statement → 两条共存 → 检索/Context Pack 标 CONFLICT,不得静默挑边覆盖。
- 证据擦除:触发 `crypto_erasure` 后 → `basic_retrieve` 仍可返回 Statement 元数据,但 evidence 标注"部分证据已擦除"且 verbatim 不可恢复。
- 幂等写入:同一 DrawerRecord 重复抽取 → `extraction_span_key` 去重 → 不产生重复 Statement。
- 运行回执:一次成功写入和一次 no-op 抽取都必须产生 `ExtractionAttempt`;一次 `basic_retrieve` 必须返回最小 `RetrievalReceipt`。
- Profile preflight:故意关闭 `transactional_outbox` 或 `tenant_isolation` 时,系统进入 `UNREADY`,不得继续运行 P0 smoke test。
- 自污染防护:把一次 RetrievalReceipt / PipelineRun trace 作为输入重放 → `source_kind=system_internal` 默认 `NO_STORE`,不得产生用户画像 Statement。
- Source adapter metadata:同一内容分别以 `byte_preserving` 与 `metadata_only` 写入 → 后者不得让高影响 Statement 自动 `APPROVED`,receipt/context 必须标 evidence_kind。
- 租户隔离 fail-closed:SQLite adapter 的测试 final query 缺少 `tenant_id/holder_scope` assertion 时拒绝执行;生产 profile 模拟 `app_filter` 不得通过 `storage_enforced` preflight。
- Projection repair safety dry-run:构造 rebuild 抽取条数低于主表 ground truth → `projection.rebuild_failed(truncation_suspected)`,active projection 不被替换。
- 时间锚负例:导入 2023-06-01 的历史 DrawerRecord,文本含 "last week" → Statement.valid_from 落在 2023-05 周期,不得使用当前系统日期;若无 segment observed_at,必须低置信/待审。
- 归因不可变:写入后尝试原地修改 holder/source_speaker/perceived_by → Validator 拒绝;正确路径是 `statement.corrected + supersedes`。

**P0 非交付项(v10 新增)**:
- Projection Index(P2;P0 只主表直查)
- `idx_entity_statement` 实体投影(P2;P0 只在 Statement 中保留 EntityRef 字段)
- 完整 Retrieval Planner(P4;P0 只交付 `basic_retrieve`)
- 完整 RetrievalScopePlan runtime(P4;P0 receipt 可记录固定 `statement_main` plan)
- ToM 推断(P1 引入一阶 schema,P4 引入二阶运行时)
- Replay Scheduler(P2;P0 可做手动 compress 验证,不做周期采样)
- 完整 RuntimeHealth 仪表盘与自动背压调度(P1/P2;P0 只实现 capability preflight、最小 run ledger 表和 receipt 字段)
- 完整 SourceAdapter 插件系统(P2/P5;P0 只实现内置 `direct_api` adapter metadata 与 conformance stub)
- 外部库原生数据结构直连核心表(永不交付;只能经 Adapter 映射为 Starling 原生原语)
- Reconsolidation Engine(P2;P0 Statement 不因召回进入可塑窗口)
- Prospective Loop(P3;P0 不要求 Commitment 触发调度)
- ActionPolicyGraph(P3/P4;只有 Prospective 触发外部动作时才启用)
- CommonGround pool(P1 引入基础,P3 完整 grounding acts)
- Affect Buffer(P3;P0 写入 salience 字段但不参与采样)

**P0 内部依赖顺序(v10 新增)**:

| 子里程碑 | 内容 | 依赖 |
|---|---|---|
| M0.1 Schema | Pydantic 实现 + JSON-Schema 导出,含 `SourceSpanRef/TemporalAnchor` 最小字段 | 无 |
| M0.2 持久化 | SQLite CRUD + outbox 表 + consumer_checkpoint + 最小 `PipelineRun` 表;`ExtractionAttempt` 作为 extraction run item 表 | M0.1 |
| M0.3 写入路径 | `Bus.append_evidence` + Drawer + retention_mode/source_kind/ingest_policy 审计 | M0.2 |
| M0.4 抽取 | Extractor + Validator + `extraction_span_key` + 单片段 temporal grounding | M0.3 |
| M0.5 冲突 | ConflictProbe + `canonical_conflict_key` + `SUPERSEDES` 边 | M0.4 |
| M0.6 检索 | `basic_retrieve` + 主表过滤 + evidence 返回 + 最小 `RetrievalReceipt(sufficiency_status)` | M0.5 |
| M0.7 验收 | smoke test + 50 条回归集 + 幂等/负面用例测试 | M0.6 |

### 16.2 迁移路径

**从 mem0 迁入**:
- `filters={user_id, agent_id, run_id, actor_id}` → Cognizer.id 四维隔离(v4 勘误:mem0 v1.0.0 新增 `actor_id` 作为第 4 维查询字段,写入三维但查询可按 actor 切片 —— 这是 holder 思想的雏形,actor ≈ holder)
- Observation Date / Current Date 分离 → Starling `TemporalAnchor`:历史消息中的相对时间必须按观察日期解析,不能按导入/系统当前日期解析
- `linked_memory_ids` 与 entity collection → Starling `idx_entity_statement`:实体反向链接作为检索桥,但必须带 holder/tenant/state,不能做全局 entity scan
- ADD/UPDATE/DELETE/NOOP → Statement.modality + supersedes 链
- 既有向量库保留为 Substrate.vector,新增 holder 字段索引
- `_add_to_vector_store` 的批处理历史与 hash 去重 → Starling `ExtractionAttempt` 与 accepted/rejected/noop 计数;existing memory 在 prompt 中映射为短 id,避免 LLM 幻觉长 UUID
- UPDATE 时保留 `actor_id` → Starling 归因不可变:holder/source_speaker/perceived_by 纠错必须经 corrected/supersedes,不能原地覆盖
- 注意:mem0 v1.0.0 移除 `version` / `output_format` 参数,统一返回 `{"results": [...]}`,top-level entity params 抛错拒绝 —— 迁移脚本需适配 breaking change

**从 Letta 迁入**:
- Block.label → Working Set label 集
- GitEnabledBlockManager(真 git CLI + GCS/S3 对象存储) → Statement.supersedes 链的物理底座候选(v4 勘误:Letta 2025 后已使用真 git 而非数据库模拟)
- Identity ORM(`identifier_key + identity_type + properties`) → Cognizer 的直接设计参照;Starling 可继承其 identifier/properties 模型,再加 `aliases / canonical_name / trust_priors / knowledge_frontier`
- LoadGate / event-loop watchdog → `RuntimeHealth` 的前后台 admission gate、readiness degraded/recover 语义
- Letta identity 间 block sharing → Starling CommonGround/WorkingBlock 的权限与共享参考,不必从零实现共享主体模型
- ToolRulesSolver 的 Init/Child/Parent/Conditional/MaxCount/Terminal/RequiredBeforeExit/RequiresApproval → Starling `ActionPolicyGraph`,用于 Prospective Loop 触发真实外部动作前的 allowlist、强制前置步骤和 human approval
- Archive(可跨 agent 共享的 ArchivalPassage 池) → Drawer 的多 agent 共享原档池参照
- sleeptime agent(v4:已迭代到 `sleeptime_multi_agent_v4.py` + `voice_sleeptime_agent.py`) → Replay Scheduler Sleep 模式
- shared_blocks → CommonGround pool

**从 cognee 迁入**:
- DataPoint 子类机制 → Statement 子类化底座(直接继承)
- `run_custom_pipeline` 的 `pipeline_name/use_pipeline_cache/incremental_loading/run_in_background` 与 dataset queue slot → Starling `PipelineRun` 的 run id、input_hash、checkpoint 与 per-holder/profile 并发闸门
- 多用户 access-control capability 检查 → `ProfileCapability.tenant_isolation` fail-closed 预检
- dataset queue 的同 task + same dataset reentrant slot → Starling `ScopedWorkGate(tenant, holder_scope, aggregate_id, lane)`,避免全局锁阻塞不同 holder,也避免同 aggregate 并发写坏投影
- recall 的 `session/trace/graph_context/graph` 多源顺序与 auto fallthrough → Starling `RetrievalScopePlan`:低成本 session 命中可短路 graph,但 Receipt 必须记录 skipped scopes 与 stop_reason
- forget() 三级 + 权限 → Starling 降级而非删除
- improve() feedback_weight alpha(已实装,四阶段流水线:apply_feedback_weights → persist_session_QA → enrichment → sync_to_session_cache) → Replay 的 reconcile/abstract/induce_norm 三动作 + Reconsolidation 反馈闭环(v4 勘误:v3 写"算法 TODO"已过时)
- improve 中 feedback/session/trace/sync 多处 non-fatal stage → Starling PipelineStepContract.failure_policy 的工程来源;非核心增强失败只降级 run,不应吞掉主链路事实
- TEMPORAL 边 → 实际外包给 graphiti 的 valid_at/invalid_at(非 cognee 自实现,v4 勘误)

**从 MemOS 迁入/复用**:
- MemCube / TreeTextMemory / scheduler 模块 / KVCache 是认知层参考资产,不作为 P0/P1 的强依赖
- 若做 MemOS adapter,必须以当前 v2.0.x API 为准重新验收字段、调用方式与生命周期;本文对 MemCube/TreeTextMemory/9 scheduler 的描述只代表可复用能力,不保证旧版本接口稳定
- MemCube activation 可映射为 Hippocampus/Working Set 的短期活化载体;TreeTextMemory 可作为 Replay `compress` 输入组织方式参考
- SchedulerDispatcher / TaskStatusTracker / Redis stream grouping → `PipelineRun.progress/counters`、按 `(holder, profile, task_kind)` 分流与业务 task 聚合状态
- TaskStatusTracker 的 internal item id 与 business task id 分离 → Starling `PipelineRun.business_task_id/parent_run_id/item_run_ids` 聚合状态
- AutoDroppingQueue 提醒:Starling 只允许丢弃可重建 soft work,不得丢 committed outbox / compliance / commitment 事件
- Adapter profile 需固定 MemOS 版本并提供迁移测试,避免 scheduler 命名或配置漂移影响 Starling 主契约

**从 memU 迁入/复用**:
- Rust core + blob 层可作为 Drawer 物理底座候选,但生产 profile 需先补 per-record encryption key、key shredding、shared DrawerRecord refcount
- memU v1.5.1 要求 Python >=3.13;若宿主系统仍在 3.11/3.12,应优先通过服务边界或 Rust FFI 接入,不要把 Python binding 作为 P0/P1 阻塞依赖
- WorkflowStep 的 `requires/produces/capabilities` 与 PipelineRevision → Starling 长任务 step 校验、profile capability preflight 与 run revision token
- Workflow interceptor strict/non-strict + step error hook → Starling `failure_policy=critical/non_fatal/skip_downstream`;非致命失败必须记录 warning 且受 downstream requires 约束
- pre-retrieval decision / sufficiency check → Retrieval Planner 的 `needs_retrieval` 与 receipt 中的 `plan_steps/degraded_paths`
- sufficiency check 的 ENOUGH/MORE → Starling `RetrievalReceipt.sufficiency_status`,其中 `NEEDS_RAW` 受 Drawer retention/visibility gate 约束
- route_category→sufficiency→recall_items→sufficiency→recall_resources → Starling `RetrievalScopePlan` 的 progressive widening 与 stop_after_sufficient
- Category summary 增量维护 → Replay `compress`/Container rebuild 的参考,但不能直接承担 holder-aware ToM 图族
- non-propagate 开关 → Starling `replay_derived` 默认不再触发 Replay 的工程依据

**从 Graphiti / Zep 迁入**:
- Graphiti 字段是 `valid_at / invalid_at / expired_at`(三时间,非两时间,v4 勘误):`valid_at`(事实生效)、`invalid_at`(事实停止)、`expired_at`(被新事实推翻)。Starling 使用 `valid_from / valid_to` 映射到 `valid_at / invalid_at`,并复用 `expired_at` 机制作为 supersedes 链的时间戳底座
- SagaNode(v4 新增引用):Graphiti 的增量摘要节点(`last_summarized_at`,只读取新 episode 续写摘要) → Starling Replay Scheduler `compress` 动作的参考实现
- Search 多 scope 并发(edge/node/episode/community) + trace attributes → `RetrievalReceipt.scopes_searched/candidate_counts/score_breakdown`
- `episode_indices` + per-edge `reference_time` → Starling `SourceSpanRef/TemporalAnchor`:跨 episode 抽取必须绑定具体 source episode,并用该 episode 的 valid_at 解析相对时间
- 增加 holder 维度(Starling 把全局图族化,Graphiti 本身无 holder)
- Graphiti 是 episode-first:Episode 是一等输入,edge/triplet 是 episode 的产物;Starling 是 statement-first:EpisodicEvent 是 Statement 子类。迁移时不能简单一对一映射,应保留 Graphiti Episode 为 Drawer/EpisodicEvent evidence,再把 edge/triplet 映射为 holder-aware Statement。
- `handle_multiple_group_ids` 式每 group 隔离执行 + merge → Starling 多 holder/perspective retrieval 必须拆分 substrate context,不得宽泛 `holder IN (...)` 后置过滤
- MinHash + Shannon entropy + Jaccard ≥ 0.9 实体名去重 → Starling Cognizer alias 归一(§3.1)的算法候选
- `resolve_edge_contradictions`(新边设旧边 `expired_at`,节点就地不删) → 与 Starling supersedes 链同型,可复用 cypher

**从 mempalace 迁入/复用**:
- Drawer/Closet 二层索引与 query sanitizer → Starling Drawer + Projection Index + `RetrievalReceipt.sanitized_query`
- deterministic sweeper cursor 与边界重试(`< cursor` 而非 `<= cursor`) → PipelineRun watermark、Drawer 增量 ingest 与 crash-safe replay 语义
- repair guard(SQLite ground truth vs vector/HNSW index count) → Projection rebuild / vector payload repair 的 `truncation_suspected` 安全阈
- Source Adapter RFC 的 `declared_transformations / supported_modes / privacy_class / conformance tests` → Starling Drawer source adapter metadata 与 byte-preserving/declared-lossy 证据语义
- KG triples `valid_from/valid_to/source_file` → Statement valid interval 与 evidence/source mapping 的迁移来源
- mine lock / palace lock → `ScopedWorkGate` 和 per-aggregate non-blocking lock 的工程参考

**从 EverOS 迁入/复用**:
- StageTimer/request_id → `PipelineRun.stage_timings_ms` 与 `RetrievalReceipt.plan_steps`
- Mongo/ES/Milvus tenant command interceptor → `ProfileCapability.command_boundary_filter / unknown_data_command_reject / id_operation_scope_guard`
- participant filtering 只信 `role=user`,不靠 sender_id keyword → Extractor 的 `perceived_by/participants` 应由结构化 role/channel metadata 推断,不靠名字黑名单
- delete API 的三态过滤语义 → Starling 删除/擦除 API 必须区分 "filter absent"、"match NULL/empty"、"match all sentinel",避免误删或误跳过
- vector_anchored_fusion → §13.5 hybrid ranking 默认策略候选
- agentic/memory/biz/infra 四层拆分 → Starling 继续坚持 Bus/PolicyEngine/RetrievalPlanner/SubstrateAdapter 分层,不让业务 API 直接绕过底座隔离器

### 16.3 共存策略

Starling 不要求替换现有系统。任何开源系统都可以作为 SubstrateAdapter 后端,Starling 在其上增加 `holder + Statement + ToM + Replay + Prospective` 这一层认知中间件:
- **已用 mem0**:保留 mem0,Starling 提供二阶 ToM + 承诺触发
- **已用 Letta**:保留 Letta,Starling 把 sleeptime + shared blocks 升级为 Replay + CommonGround
- **已用 Graphiti/Zep**:保留 Graphiti,Starling 加 holder 维度与共识池

---

## 17. 版本变更记录

### 17.1 v1 → v2 主要变更

| 变更 | v1 | v2 | 理由 |
|---|---|---|---|
| **公理** | 3 条(归属+双系统+目标重构) | 3 条,措辞强化 | 不变 |
| **Statement 状态机** | 隐含的生命周期 | **显式 5 态 ConsolidationState** | 可工程实现的状态迁移 |
| **Retrieval Planner** | 9 Intents + 6 步 | 9 Intents + **7 步**(新增 Abstention Gate) | 明确"该不该回答"应在"怎么回答"之前 |
| **Context Pack Builder** | 6 标签(FACT/BELIEF/HEARSAY/INFERRED/COMMON/TODO) | **8 标签**(+CONFLICT / ABSTAIN) | 冲突显式标注 + 拒答显式信号 |
| **Prospective Loop** | 3 种 Trigger(time/event/state) | **4 种 Trigger**(+compound) | 复合条件(AND/OR/NOT)是真实场景需求 |
| **Commitment 状态机** | PENDING→ACTIVE→FULFILLED/EXPIRED | + **RENEGOTIATED** 状态 | 承诺可被协商修改,不是二元完成/过期 |
| **AffectVector** | 5 维,无显式公式 | 5 维 + **salience 计算公式**(valence × novelty × stakes 的加权积) | 公式化才能工程实现优先级重放 |
| **Reconsolidation** | 提到概念 | **独立 §11 完整状态机 + 不覆盖只追加** | 这是 2025 研究确认的核心差异点 |
| **Norm 字段** | 仅 deontic_strength | + **enforcement_history**(规范被违反/重申的历史) | 支持规范演化追踪(独立于 Reconsolidation) |
| **评测** | 5+5+5 维,简表 | 8+9+4 维,含评测执行策略 | 覆盖再巩固保真度、视角泄露防护等 v2 新增能力 |
| **路线图** | 4 阶段(v0-v3) | **6 阶段(P0-P6)** | 增加 P5 产品化 + P6 持续演进,更接近真实交付节奏 |
| **与 Polis 关系** | §16 对比表 | §18 取舍 + §20 复用对照(更详细) | 吸收 Polis §10-§11 + Appendix B |
| **设计取舍表** | 无 | **9 项显式取舍 + 理由** | 来自 Polis §10,给审查者明确的 tradeoff 上下文 |
| **风险与开放问题** | 无独立章节 | **7 项风险 + 缓解策略** | 来自 Polis §11,诚实披露 |

### 17.2 v2 → v3 修复(本版本)

> 本节由资深架构师审查 v2 后产出。**设计本体未变**,纠正交叉引用、参数不一致、字段缺失等可施工性缺陷。

| # | 类别 | 修复内容 | 影响位置 |
|---|---|---|---|
| 1 | **交叉引用** | §15 评测表 9 处章节号错位全部修正(根因:v2 把 Reconsolidation 提为独立 §11 后,后续章节整体后移一位但评测表沿用旧编号) | §15.1 + §15.2 |
| 2 | 参数一致性 | 可塑窗口默认值统一:工程默认 30 分钟、自适应区间 5min–6h(6h 为 Nader 2000 神经科学参考值) | §11.1 + §11.2 + §19 |
| 3 | Schema 完备 | Statement 补 `replay_count / last_replayed` 字段(§10.2 采样器需要) | §3.2 |
| 4 | Changelog 准确 | 修正 v1→v2 changelog 中"Reconsolidation: enforcement_history"误归 —— enforcement_history 是 Norm 子类字段,与 Reconsolidation 无关;两项独立列出 | §17.1 |
| 5 | Persona 完备 | §7.4 补 self_model_anchor / profile_anchor 双锚点的工程意义(自陈优先于他陈;冲突升级 suspected_diverge) | §7.4 |
| 6 | 状态图例外 | §3.4 状态图补 CommonGround 与未结清 Commitment 不允许进入 ARCHIVED 的例外标注 | §3.4 |
| 7 | 措辞精度 | §6.2 "对数似然反向" → "negative log-likelihood, surprise = -log P(next given context)" | §6.2 |
| 8 | 术语统一 | "Mentalizing Primitives" 统一表述(取代 API/原语混用) | §0 + §9.4 + §15.2 |
| 9 | 去重 | §13.7 改为引用 §13.3 step 7,abstain 完整语义集中在 §13.7 | §13.3 + §13.7 |
| 10 | 边界明确 | §10.3 reconcile 行明确写"推入 Reconsolidation Engine(§11)开启可塑窗口" | §10.3 |
| 11 | 案例补全 | 新增 §14.4 Prospective Loop 触发端到端流程示例 | §14.4 |
| 12 | 自夸去重 | 删除 §11.4 末尾"8 个开源系统全无"等正文重复表态(集中到附录 A 对照表) | §11.4 |

### 17.3 v3 → v4 修复(本版本)

> 本节基于 9 仓库源码重审(`_research/04_repos_resurvey_2026.md`) + 2026 前沿论文检索(`_research/05_frontier_2026.md`)。**设计本体未变**,纠正过时描述、缺失引用和一处事实错误。

| # | 类别 | 修复内容 | 影响位置 |
|---|---|---|---|
| 1 | **事实修正** | graphiti 时间字段从"valid_from/valid_to 双时间"修正为"valid_at/invalid_at/expired_at 三时间";新增 SagaNode 增量摘要节点引用 | §16.2 |
| 2 | **重大遗漏** | 补全 EverOS HyperMem(2026 ACL):三级 hypergraph + coarse-to-fine RRF + hyperedge | §3.7, §13.5, §20 |
| 3 | **维度补正** | mem0 actor_id 作为第 4 维查询维度(Cognizer 四维隔离,非三维) | §16.2 |
| 4 | **过时纠正** | cognee improve() feedback_weight alpha 已实装(非 TODO);TEMPORAL 外包给 graphiti | §11.3, §16.2 |
| 5 | **过时纠正** | Letta GitEnabledBlockManager 真 git(非伪 git);新增 Identity ORM + Archive 引用 | §16.2, §20 |
| 6 | **范畴错误删除** | claude-mem cynical deletion 实为代码风格运动(非数据删除),删除 §10.4 错误对照 | §10.4 |
| 7 | **新机制吸收** | mempalace Hall detection(7 hall) + corpus origin 检测;MemOS TreeTextMemory + 9 个 scheduler 模块;memU Rust core + non-propagate 开关 | §3.1, §7.1, §10.3, §20 |
| 8 | **新文献纳入** | 8 篇 2026 前沿论文入 §21;A-ToM 入 §9.6 新子节(原 v4 草稿误置 §12.3,本节修正);Governing Evolving Memory 三 trade-off 入 §19 | §9.6, §19, §21 |
| 9 | **reranker 增强** | §13.5 新增 coarse-to-fine RRF 方向 + temporal_distance_penalty 项 | §13.5 |
| 10 | **对照表刷新** | §20 复用资产表 + 附录 A 能力差异表全面更新为 2026 状态 | §20, 附录 A |

### 17.4 v4 → v5 修复(本版本)

> 本节基于资深架构师对 v4 的重审(`_research/06_v4_arch_review.md`)。**数据模型(Statement schema、社会心智本体、ToM API)保持与 v4 一致;运行时层(状态机、Bus 契约、分层抽象)经实质重写**。

| # | 严重度 | 修复内容 | 影响位置 |
|---|---|---|---|
| B1 | **Blocker** | 确立三层抽象(逻辑/分区/物理),解 v4 "视图 vs 物理分层"自相矛盾;声明 Statement vs Container 二分 | §3 设计原则、§3.6、§6 |
| B2 | **Blocker** | Statement 写入路径分类(`provenance ∈ {user_input, replay_derived, tom_inferred}`),解 §10.3 输出循环 —— Replay 派生 stmt 走 Bus 但跳过 statement.written 改 emit `statement.derived`,Replay 不订阅此事件,断开循环 | §3.10 新增、§5.3、§10.3 |
| M1 | **Major** | §3.4 状态机重画,补 4 条迁移边(CONSOLIDATED→REPLAYING、REPLAYING→ARCHIVED、REPLAYING→CONSOLIDATED 确认路径、ARCHIVED→REPLAYING 召回归档),完整迁移表 10 条 | §3.4 |
| M2 | **Major** | REPLAYING 拆为 `REPLAYING_CONSOLIDATING`(VOLATILE→)与 `REPLAYING_RECONSOLIDATING`(CONSOLIDATED/ARCHIVED→)两子态,语义清晰、close 责任明确 | §3.4 + §10 + §11 |
| M3 | **Major** | Drawer 提升为独立子系统(§6.0 新增),从 Hippocampus 内部分层中移出,生命周期独立于 Statement(FORGOTTEN 后 Drawer 仍在) | §6.0 新增、§6.1、§3.8 |
| M4 | **Major** | §5.3 Bus 事件表补 5 个终态事件:`statement.archived/.forgotten/.derived` + `commitment.fulfilled/.broken/.renegotiated`,完整 producer/consumer 列 | §5.3 |
| M5 | **Major** | §5.4 防抖与幂等契约:同 key N 秒合并、递归深度 ≤ 3、idempotency key 去重、Reconsolidation 窗口锁追加证据;解 ToM↔ConflictProbe↔Reconsolidation 闭环失控 | §5.4 新增 |
| M6 | **Major** | Retrieval 读副作用解耦(§13.0 新增):Retrieval 仅 emit `statement.recalled`,Reconsolidation 异步消费决定开窗;读路径幂等无状态 | §13.0 新增、§11.1 |
| M7 | **Major** | EpisodicView 定义修正(去掉 `consolidation_state IN (VOLATILE, REPLAYING)` 限定),符合 Tulving 1985 — Episodic 由"绑时空"区分,不由巩固阶段区分 | §3.5 |
| M8 | **Major** | PolicyEngine ↔ Bus 关系显式化:PolicyEngine 是 Bus publisher 之一,所有 Trigger 命中走 `Bus.emit("commitment.fire", ...)`,不绕过 Bus | §12.2 |
| m1 | Minor | Affect Buffer vs Replay 边界:Buffer 是入口缓冲(数据结构),Replay 在 Online 模式优先从 Buffer 取 | §6.6 |
| m2 | Minor | Working Set vs Persona 边界:Working Set 是 prompt 渲染快照(turn-level),Persona 是持久化结构(cross-session) | §6.5 |
| m3 | Minor | Persona / CommonGround 改继承 `Container`(非 BaseEntity),与 §3 "Statement vs Container" 二分对齐 | §3.6 |
| m4 | Minor | Entity 类型显式定义(`kind ∈ {concept, artifact, place, event, organization, project, other}`),EntityRef 即 Entity.id 引用 | §3.1 |
| m5 | Minor | Commitment `created` 态由 Validator 通过后 Bus 自动转 ACTIVE;BROKEN→RENEGOTIATED 允许("我后来又答应你了") | §12.2 |

### 17.5 v5 → v6 修复(本版本)

> 本节基于两轮架构审查对 v5 的合并意见。v6 不新增认知能力面,专注把 P0/P1 实施会卡住的契约冻结。

| # | 严重度 | 修复内容 | 影响位置 |
|---|---|---|---|
| B1 | **Blocker** | Drawer 合规生命周期重写:`legal_hold / audit_retain / redacted_retain / crypto_erasure`;FORGOTTEN 不再默认保留 verbatim,支持 redaction 和 key shredding | §3.8、§6.0、§10.4 |
| B2 | **Blocker** | Bus 写入语义改为 storage transaction + durable outbox append;Subscriber at-least-once 投递 + idempotency_key 幂等消费 | §5.0、§5.3、§5.4 |
| M1 | **Major** | ConsolidationState 冻结为六个物理状态,不再在 schema 层使用抽象 REPLAYING | §0、§3.4 |
| M2 | **Major** | Statement schema 补 `review_status/provenance/derivation_chain`;新增 ReviewStatus 枚举,表达派生候选和低置信审核 | §3.2、§3.10 |
| M3 | **Major** | StatementProvenance 从三类扩为四类,新增 `reconsolidation_derived`;severe correction 不再误标 `tom_inferred` | §3.10、§11.2 |
| M4 | **Major** | Reconsolidation severe path 原子化:新版、旧版归档、SUPERSEDES 边、outbox 事件同事务提交 | §11.2 |
| M5 | **Major** | Container 更新契约明确:Persona/CommonGround 是 StatementRefs 物化视图,经 `Bus.rebuild_container` + CAS 更新 | §3.6、§5.5、§10.3 |
| M6 | **Major** | ConflictProbe 与幂等 key 规范化,包含 holder/modality/subject/predicate/object/time/scope | §5.2、§5.4 |
| m1 | Minor | 补 `commitment.withdrawn` 事件,WITHDRAWN 终态可订阅并清理 Trigger/Working Set | §5.3、§12.2 |
| m2 | Minor | Drawer 写入从 `Drawer.append` 改为 `Bus.append_evidence`,纳入权限、source trust、retention、审计和 outbox | §5.0、§6.0、§14 |
| m3 | Minor | EpisodicView 不再引用 Base Statement 没有的 participants 字段;改为 event_time/type/OBSERVED_BY 边 | §3.5 |
| m4 | Minor | 修正 `subject/object` StatementRef 口径:subject 不接 StatementRef,object 承担二阶嵌套 | §3.1、§3.2 |
| m5 | Minor | 路线图 P2 从"物理分表"改为"逻辑分区标签 + 可选物理投影/索引" | §16.1 |

### 17.6 v6 → v7 修复(本版本)

> 本节基于 Hermes Agent(deepseek-v4-pro) 对 v6 的外部架构评审。v7 主要补 P0/P1 实施的运行时闭环和性能边界。

| # | 严重度 | 修复内容 | 影响位置 |
|---|---|---|---|
| B1 | **Blocker** | 抽取失败补偿:新增 `extraction.failed/retry_scheduled/dead_lettered`,DrawerRecord 不因 Validator 拒收而静默失去抽取机会 | §5.1、§5.3、§14 |
| B2 | **Blocker** | Outbox checkpoint 与业务幂等:新增 consumer checkpoint、Subscriber inbox、业务幂等窗口,避免 ACK 丢失导致重复提醒 | §5.4 |
| B3 | **Blocker** | crypto_erasure 传播语义:EvidenceRef 标 ERASED,仅传播到直接依赖且无独立 evidence 的 Statement,默认不递归清空派生链 | §3.8、§10.4 |
| M1 | **Major** | 热路径 Projection Index:主 Statement 表不承担 holder/time/state/salience/vector 五维复合索引压力 | §4.1、§13.4、§16.1 |
| M2 | **Major** | Container 维度级版本与 sequence,降低 Persona/CommonGround 整体 CAS 冲突 | §5.5 |
| M3 | **Major** | ConflictProbe 四级冲突:`direct_contradiction / partial_overlap / superseding / adjacent`,明确时间 overlap 语义 | §5.2、§7.3 |
| M4 | **Major** | ToM 派生链限流:tom_inferred Replay 权重因子 0.25,ToM→Replay→Container→ToM 链路暂停自动增量推断 | §3.10、§9.2、§10.2 |
| M5 | **Major** | P0 增加 basic_retrieve,要求写入→巩固→检索 smoke test | §13.4、§16.1 |
| m1 | Minor | memU Drawer 底座需补 per-record key/refcount 后才能支持 crypto_erasure 与共享记录 | §16.2、§20 |
| m2 | Minor | Graphiti episode-first 与 Starling statement-first 差异显式化,迁移时保留 Episode 为 evidence | §16.2 |
| m3 | Minor | Letta Identity ORM 作为 Cognizer 设计参照,复用 identifier/properties/block sharing 思路 | §16.2 |
| m4 | Minor | 附录 A 从"成熟度合计"改为定性成熟度,避免 🟡 与 ✅ 等价计分 | 附录 A |

### 17.7 v7 → v8 修复(本版本)

> 本节基于 Hermes Agent(deepseek-v4-pro) 对 v7 的外部架构评审。v8 不改变核心本体,只补 P0 实施前的阶段边界、重试去重与长期治理细节。

| # | 严重度 | 修复内容 | 影响位置 |
|---|---|---|---|
| M1 | Major | Projection Index 阶段边界明确:P0 `basic_retrieve` 走主 Statement 表直查;P2 才引入投影索引;投影由 outbox 异步物化并声明新鲜度 SLA | §4.1、§13.4、§16.1 |
| M2 | Major | 抽取重试去重语义:同一 DrawerRecord 重试前读取已成功片段,只重试失败片段;以 `extraction_span_key` 幂等 upsert | §5.1 |
| M3 | Major | CommonGround 过时治理:新增 `SupersedeGround / ExpireGround / Unground`,遗忘公式从 `is_grounded` 改为 `active_grounded` | §9.5、§10.4 |
| m1 | Minor | P0 smoke test 指定 §14.1 最小变体:Alice 宣布 Bob 不再负责 auth,检索返回 Carol 接手 | §16.1 |
| m2 | Minor | 系统总览图标题从 Runtime v3 更新为 Runtime v8 | §2 |
| m3 | Minor | 复用资产版本边界入文:MemOS adapter 以 v2.0.x 当前 API 为准;memU Python >=3.13;EverOS 非标准包管理只作算法参考 | §16.2、§20 |

### 17.8 v8 → v9 修复(本版本)

> 本节基于 Hermes Agent(deepseek-v4-pro) 对 v8 的外部架构评审。v9 只补一个实施级职责边界,不改变 P0 就绪结论。

| # | 严重度 | 修复内容 | 影响位置 |
|---|---|---|---|
| m1 | Minor | SupersedeGround 主触发器明确为 ConflictProbe 的 `superseding` 等级;CommonGround Builder 消费 `statement.superseded` 后落 act;Container.rebuild 只做 fallback 一致性校验;Replay 不直接改 CommonGround | §5.2、§9.5 |

### 17.9 v9 → v10 修复(本版本)

> 本节基于 Hermes Agent(claude-opus-4-7) 对 v9/v8 的外部架构评审。v10 不新增架构能力,只把 P0/P1 实施会现场决策的规则写成契约。

| # | 严重度 | 修复内容 | 影响位置 |
|---|---|---|---|
| M1 | Major | Extractor 抽取契约补齐:产出上限、holder 归因、perceived_by 推断、confidence 初值、低置信拒收 | §5.1 |
| M2 | Major | `canonical_conflict_key` 三个规范化函数补规则表:`canonicalize_object / normalize_interval / scope_of` | §5.2 |
| M3 | Major | CommonGround grounded 判定规则补齐:显式确认、共同在场推定、重复确认、人工确认、超时降级 | §9.5 |
| M4 | Major | Replay Scheduler 采样语义补齐:weight 归一、无放回、批量大小、极端值截断、冷却期 | §10.2 |
| m1 | Minor | Container source_refs 版本语义、Projection Index 订阅更新表、ToM 双限流交互入文 | §4.1、§5.5、§9.2 |
| m2 | Minor | holder 子图索引、模式补全资源边界、Reconsolidation pending_evidence 容量规则入文 | §4.1、§6.4、§11.1 |
| m3 | Minor | P0 负面验收用例、非交付项与内部依赖顺序入文 | §16.1 |
| m4 | Minor | 新增术语表与实施 FAQ,集中解释跨章节高频概念和易误解决策 | 附录 C、附录 D |

### 17.10 v10 → v11 修复(本版本)

> 本节基于 9 个开源代码库源码级复审。v11 不改 Statement 本体、六态状态机、Replay/Reconsolidation 核心认知模型,只补线上运行时治理与可观测性。

| # | 严重度 | 修复内容 | 影响位置 |
|---|---|---|---|
| M1 | Major | ProfileCapability preflight:生产 profile 启动前校验 transactional outbox、tenant isolation、crypto erasure、vector delete、projection rebuild 等硬能力,不满足则 fail-closed | §4 |
| M2 | Major | ExtractionAttempt 账本:抽取成功、部分成功、失败、dead-letter、NOOP 都持久化,记录 prompt/input hash、existing-ref 短 id 映射与 accepted/rejected 计数 | §5.1 |
| M3 | Major | RuntimeHealth + Backpressure:新增 READY/DEGRADED/DRAINING/UNREADY、健康指标、前后台 gate、critical lane 与队列满时可丢/不可丢边界 | §5.6 |
| M4 | Major | PipelineRun/MaintenanceRun 账本:长任务统一 run id、checkpoint/watermark、worker lease、claim/confirm、stage timing、cancel/retry/dead-letter 语义 | §5.6 |
| M5 | Major | RetrievalReceipt:检索结果带 trace_id、query sanitizer、projection lag、scope/candidate/score/abstention/evidence-erased 回执,用于审计和评测归因 | §13.6.1 |
| m1 | Minor | Retrieval rerank 增 vector-anchored fusion 方向:BM25 饱和归一 + vector floor + score breakdown | §13.5 |
| m2 | Minor | BusEvent 表补 extraction.noop、runtime.health_changed、pipeline.run_*、projection.rebuild_* 事件 | §5.3 |
| m3 | Minor | P0 交付微调:增加最小 ProfileCapability preflight、PipelineRun/ExtractionAttempt 表与 basic_retrieve receipt,但完整 RuntimeHealth 仪表盘延后 | §16.1 |
| m4 | Minor | 迁移路径和复用资产表补源码验证到的 LoadGate、dataset queue slot、MemOS scheduler、EverOS StageTimer、mempalace sanitizer/repair guard、claude-mem RestartGuard/watermark、Graphiti search trace | §16.2、§20 |

### 17.11 v11 → v12 修复

> 本节基于对 9 个开源代码库的第二轮源码级复审。v12 不改 Statement 本体、六态状态机、Replay/Reconsolidation 核心认知模型,只补边界契约:什么能入库、什么必须隔离、底座如何强制 scope、长任务如何解释版本、检索如何说明"够不够"。

| # | 严重度 | 修复内容 | 影响位置 |
|---|---|---|---|
| M1 | Major | SourceAdapter + declared transformations:DrawerRecord 增 adapter/version/ingest_mode/declared_transformations/privacy_class/byte_preserving,metadata_only 与 declared-lossy evidence 不再冒充 verbatim | §3.8、§6.0 |
| M2 | Major | Self-pollution guard:新增 SourceKind/IngestPolicy,system_internal/observer_agent/replay_output 默认 NO_STORE,防止 prompt/receipt/log/replay 摘要污染用户记忆 | §5.0、§6.0 |
| M3 | Major | Storage-enforced tenant isolation:ProfileCapability 增 command_boundary_filter、unknown_data_command_reject、id_operation_scope_guard,生产 profile 要求底座命令边界强制 tenant/holder scope | §4 |
| M4 | Major | ScopedWorkGate + Pipeline step contract:PipelineRun 增 business_task_id、pipeline_revision、step_contracts;后台任务按 `(tenant, holder_scope, aggregate_id, lane)` 可重入限流 | §5.6 |
| M5 | Major | Projection/repair safety:Projection rebuild/vector repair shadow swap 前用独立真相源校验 row count/watermark/hash,抽取短缺或疑似分页截断时拒绝替换 | §4.1、§5.6 |
| M6 | Major | Retrieval sufficiency + holder-isolated search:RetrievalReceipt 增 sufficiency_status;多 holder/perspective 检索按 holder/group 隔离执行后合并,不得宽泛扫描后置过滤 | §13.3、§13.6.1 |
| m1 | Minor | Trace retention tiers:ExtractionAttempt/PipelineRun/RetrievalReceipt 支持 metadata_only/hash_only/redacted_debug/full_debug,生产默认不存 raw prompt/response | §5.6、§13.6.1 |
| m2 | Minor | P0 验收补 self-pollution、source adapter metadata、tenant isolation fail-closed、projection repair safety dry-run | §16.1 |
| m3 | Minor | 迁移路径补 mempalace Source Adapter RFC、repair guard、mine lock、EverOS tenant interceptor/participant filter/delete 三态语义 | §16.2、§20 |

### 17.12 v12 → v13 修复(本版本)

> 本节基于对 9 个开源代码库的第三轮源码级复审。v13 仍不改核心认知本体,只补 v12 尚未表达清楚的执行边界:Statement 到底来自哪个源片段、相对时间按哪个时间锚解析、检索为什么停在某个 scope、长任务局部失败如何报告、前瞻触发真实动作时谁负责拦截。

| # | 严重度 | 修复内容 | 影响位置 |
|---|---|---|---|
| M1 | Major | SourceSpanRef + TemporalAnchor:Statement 绑定 Drawer 片段/episode/segment,相对时间按 source observed_at/reference_time 解析,避免历史导入按系统当前日期误落地 | §3.2、§3.8、§5.1 |
| M2 | Major | Attribution immutability:holder/source_speaker/source_spans/perceived_by/temporal_anchor 不可原地改写;纠错必须经 statement.corrected + supersedes | §5.1、§11.2 |
| M3 | Major | RetrievalScopePlan:完整 Planner 显式记录 scope 顺序、filter mode、短路/合并策略、skipped scopes 与 stop_reason;禁止混合 global/per-scope filter | §13.1、§13.3、§13.6.1 |
| M4 | Major | Pipeline step failure_policy:step 声明 critical/non_fatal/skip_downstream,非致命失败只有在 downstream requires 满足时可继续,并以 warning/partial success 体现 | §5.6 |
| M5 | Major | ActionPolicyGraph:Prospective Loop 触发真实外部动作前受 Init/Child/Parent/Conditional/MaxCount/Terminal/RequiredBeforeExit/RequiresApproval 规则约束 | §12.5 |
| m1 | Minor | Projection Index 增 idx_entity_statement,把 mem0 entity linked_memory_ids 思路升级为 holder-aware entity→Statement 投影 | §4.1 |
| m2 | Minor | P0 边界补 SourceSpanRef/TemporalAnchor 最小字段、时间锚负例和归因不可变负例,完整 ScopePlan/ActionPolicyGraph 延后 | §16.1 |
| m3 | Minor | 迁移路径补 mem0 Observation Date/entity link、Graphiti episode_indices/reference_time、cognee recall scopes/non-fatal improve、memU progressive sufficiency、Letta ToolRulesSolver | §16.2、§20 |

### 17.13 v13 → v14 修复(本版本)

> 本节基于对 v13 的一致性复审。v13 吸收 9 个开源库后,有少数机制已接近"并列拼装":证据锚像是强加给所有 Statement,ExtractionAttempt 与 PipelineRun 像两套生命周期,检索 scope 带外部库命名痕迹。v14 只做收敛,不新增认知能力。

| # | 严重度 | 修复内容 | 影响位置 |
|---|---|---|---|
| M1 | Major | 证据锚语义收敛:SourceSpanRef/TemporalAnchor 只对直接抽取 Statement 强制;派生 Statement 继承 evidence chain,不能伪造 source span | §3.2、§5.1、§10.3 |
| M2 | Major | Run Ledger 单一化:ExtractionAttempt 是 PipelineRun(kind=extraction) 的 item 明细;调度、重试、dead-letter、取消以 PipelineRun 为权威 | §5.1、§5.6、§16.1 |
| M3 | Major | 新增外部机制吸收原则:外部概念必须映射到 Starling 原生原语,不得新增第二套事实源/生命周期/权限边界 | §0.1、§20 |
| M4 | Major | RetrievalScopePlan scope 去外部化:核心 scope 收敛为 working_set/statement_main/projection_index/semantic_index/graph_index/container_view/drawer_evidence/tom_runtime,外部 scope 只入 adapter_scope | §13.1、§13.3 |
| m1 | Minor | BusEvent 表补 statement.review_requested 与 action.policy_blocked,并明确 pipeline.run_completed payload 覆盖 PARTIAL_SUCCESS/DEGRADED_COMPLETED | §5.3 |
| m2 | Minor | §20 改为外部机制映射表,明确 mem0/Graphiti/Letta 等结构不能直接成为 Starling 核心表 | §20 |

---

## 18. 关键设计选择与取舍

每一个设计都对应一个权衡。

| 选择 | 替代方案 | 理由 |
|---|---|---|
| **以 Statement 为核心原子,强制 holder 归属** | 以 Memory/Fact 为原子(类 mem0) | Statement 自带 holder/perspective,从 schema 层解决多主体隔离;长期收益远大于初始复杂度 |
| **嵌套 Statement 表达二阶 ToM(nesting_depth)** | 单独的 ToM 推理模块,在 Prompt 层模拟 | ToM 是数据结构问题而非模型问题;放进 schema 才能稳定查询、可审计、不依赖 LLM 随机推理 |
| **五类记忆作为逻辑视图而非物理分表** | 五张独立物理表 | 同一事件在生命周期中可能跨越多类(episode→semantic→commitment→fulfilled);视图灵活性更高,且 CLS 巩固本身就是跨表流动 |
| **默认保留差异(模式分离),不主动合并** | 默认合并去重 | 多视角必须共存;差异往往是认知线索而非噪声;合并会不可逆地丢失"谁在什么时候认为什么" |
| **后台 Replay Engine 异步巩固** | 同步抽取即巩固 | 同步拖慢写入且失去"重组"机会;睡眠期的离线重放是 CLS 的神经科学基础 |
| **Reconsolidation 不覆盖,只追加新版本** | 直接 UPDATE 旧记录 | 旧信念是认知历史;"曾经怎么想"对审计、追溯、理解信念演化至关重要 |
| **Substrate Adapter 多底座,不自己造存储** | 自建全套存储引擎 | 成熟开源系统(vector/graph/KV)的工程沉淀不应浪费;Starling 的价值在认知层 |
| **承诺与规范作为一等 Statement 子类** | 放进 metadata 或单独 KV 表 | §5.3 矩阵显示这是全行业空白;做成一等公民才能驱动运行时行为(触发、提醒、履行追踪) |
| **自然语言 belief 列表注入 LLM Context Pack** | 形式化 belief base(如 PDDL-Mind) | LLM 对自然语言的理解远好于形式逻辑;形式化作为 P6 高阶可选,不阻塞 MVP |

---

## 19. 风险与开放问题

1. **LLM 抽取成本与延迟**:Statement 抽取 + holder 归因 + Conflict 检测是高频操作。缓解:7B 级专用抽取模型 + 高价值场景升级大模型;批量抽取合并;抽取缓存(同一 Drawer 内容不重复抽取)。

2. **Replay Engine 的调度参数**:何时运行、运行多久、采样多少 —— 直接影响成本与新鲜度。缓解:P2 阶段做参数 sweep,上线后 A/B 调参;提供 conservative / balanced / aggressive 三档预设。

3. **冲突保留 vs 终端用户体验**:保留多视角是设计美德,但若 Context Pack 直接呈现"3 个互相冲突的 belief",LLM 可能困惑而非受益。缓解:Context Pack Builder 的 CONFLICT 标签 + 置信度排序 + 默认只注入最高置信度视角,冲突信息按需展开。

4. **隐私与 ToM 的张力**:系统持有"A 以为 B 不知道 X"的元数据,必须在错误视角下绝对不泄露。缓解:perspective filter 在检索管道早期执行(先于语义排序),不可跳过;敏感 Statement 支持 access_policy 字段。

5. **抽取错误传播**:错误的 holder 归因会产生连锁的错误信念。缓解:Statement 的 confidence + review_status 字段;提供 audit 工具帮助核查关键 statement;`review_status=REVIEW_REQUESTED` 标记低置信度抽取结果。

6. **规模化下的图查询性能**:嵌套 Statement + 关系边 + 模式补全会形成深图遍历。缓解:预聚合常用子图(per cognizer + per relation type);PPR 计算缓存;借 cognee 的图层分片经验;P5 做性能压测。

7. **再巩固窗口的边界控制**:Reconsolidation 允许修改已巩固记忆,但窗口太宽会导致记忆不稳定,太窄则失去修正机会。缓解:**§11.1 已统一为工程默认 30 分钟、自适应区间 5min–6h(其中 6h 为 Nader 2000 神经科学参考值)**;production 中按 modality 与更新频率(高频更新→缩短窗口防止抖动;低频更新→延长窗口提高仲裁质量)自动调整。

8. **Outbox 积压与重复投递**:v6 采用 at-least-once 投递,Subscriber 必须幂等;若 outbox dispatcher 停滞,Replay/ToM/Prospective 会延迟。缓解:outbox lag 指标、dead-letter queue、subscriber inbox 去重表、每个 aggregate 的 sequence 单调校验。

9. **合规擦除与可解释性的张力**:crypto_erasure 后 verbatim 不可恢复,错误解释能力下降。缓解:保留不可逆 content_hash、source metadata、redacted summary、decision trace;对 legal_hold/audit_retain 做最小权限访问和审计。

---

## 20. 外部机制映射表(谁启发什么,落到哪个 Starling 原语)

本表不是依赖清单,也不是核心实体清单。所有外部能力只能作为 Adapter、算法候选或运维经验进入 Starling;核心层仍只认 §0.1 的原生原语。

| 来源 | 可借鉴机制 | Starling 原生落点 |
|---|---|---|
| **mem0** | ADD/UPDATE/DELETE/NOOP 抽取契约;`filters={user_id, agent_id, run_id, actor_id}` 四维隔离(v4 勘误);Observation Date / Current Date 分离;entity collection + `linked_memory_ids`;UPDATE 保留 `actor_id` | 抽取输出从 fact 升级为 Statement(带 holder);隔离升级为 Cognizer Hub 主体管理;新增 supersedes 链;actor_id 作为 holder 反向兼容入口;Observation Date → `TemporalAnchor`;entity 链接 → `idx_entity_statement`;归因字段纠错走 corrected/supersedes 而非原地覆盖 |
| **Letta** | Blocks(工作记忆);Sleeptime 后台任务;Identity ORM(主体注册);**GitEnabledBlockManager**(真 git CLI 版本);Archive(共享原档池);LoadGate / event-loop watchdog;ToolRulesSolver(Init/Child/Parent/Conditional/MaxCount/Terminal/RequiredBeforeExit/RequiresApproval) | 工作记忆改 perspective 化(holder 标签);sleeptime 升级为 Replay Engine(reconcile/abstract/induce_norm);shared_blocks → CommonGround pool;Identity ORM → Cognizer 迁移起点;LoadGate/watchdog → RuntimeHealth readiness 与前后台 admission gate;ToolRulesSolver → Prospective `ActionPolicyGraph` |
| **cognee** | DataPoint 子类机制;TEMPORAL 时间边(外包 graphiti);**improve() feedback_weight alpha 已实装**(四阶段流水线);forget();run_custom_pipeline + dataset queue slot + access-control capability check;recall 的 session/trace/graph_context/graph 多 scope;improve 多处 non-fatal stage | 子类化建立社会心智本体(Statement→Belief/Commitment/Norm...);improve 改为 Reconsolidation 状态机(在线增量);forget 改为降级不删除;custom pipeline → PipelineRun 账本与 profile capability fail-closed;recall scope → `RetrievalScopePlan`;non-fatal stage → `PipelineStepContract.failure_policy` |
| **MemOS** | MemCube(activation memory);**TreeTextMemory**(树形文本记忆);**9 个 scheduler 真实模块**(非占位);SchedulerDispatcher/TaskStatusTracker/Redis stream grouping;KV Cache;v2.0.x 当前 API 需 adapter 重新验收 | activation 作为 Hippocampus 短期载体;OptimizedScheduler 的 `format_textual_memory_item` + `group_messages_by_user_and_mem_cube` 作为 Working Set 多用户分组参照;scheduler/status tracker → PipelineRun progress/counters 与 per-holder/profile 队列;若做 MemOS adapter,以当前 v2.0.x API 为准 |
| **EverOS** | EverCore:多层抽取本体(MemCell→Episode→Profile→Foresight);agentic/memory/biz/infra 四层架构;StageTimer/request_id/tenant context;vector_anchored_fusion;**HyperMem(2026 ACL)**:三级 hypergraph + coarse-to-fine RRF | HyperMem 的 coarse-to-fine 检索策略 + RRF 融合可替换 §13.5 简单加权 reranker;StageTimer/request_id → RetrievalReceipt 与 PipelineRun stage timing;tenant context → ProfileCapability fail-closed;EverOS 非标准 Python package 分发,仅作为算法参考/选配集成 |
| **mempalace** | Drawer(100% verbatim 原档);query sanitizer;deterministic sweeper cursor;repair guard(SQLite ground truth vs vector index);KG triples with valid_from/to;Hall/corpus origin | Drawer 不变;triples 升级为带 holder 的 Statement;query sanitizer → RetrievalReceipt.sanitized_query;deterministic cursor/repair guard → PipelineRun watermark 与 Projection rebuild 安全阈;Hall/corpus origin → Cognizer.kind/Neocortex 二级分区 |
| **memU** | **Rust core(v1.4+)**,Python binding;WorkflowStep requires/produces/capabilities/config + pipeline revision;pre-retrieval decision/sufficiency check;progressive category→item→resource recall;Category summary 增量维护;non-propagate patch;blob 存储层 | compress 动作默认 non-propagate=True;workflow step contract → PipelineRun step validation、ProfileCapability 与 step `failure_policy`;pre-retrieval/progressive sufficiency → RetrievalReceipt plan_steps 与 `RetrievalScopePlan`;Rust blob 层作为 Drawer 物理底座候选;Python binding 版本要求需纳入 adapter 成本 |
| **claude-mem** | Hook 生命周期;SQL 主 + 向量副降级;严格 XML 输出;SessionQueueProcessor claim-confirm;HealthMonitor/readiness;RestartGuard;ChromaSync watermark + granular docs reconcile;strategy selection(SQL/Chroma/Hybrid)与 metadata filter;`<private>/<system>/<internal>` tag 剥离 | Hook 接 Starling 写入端;Observation 升级为 Statement;claim-confirm/RestartGuard/watermark → RuntimeHealth、worker lease、Projection rebuild checkpoint;metadata-first filter → holder/tenant/perspective 先过滤再语义排序;tag stripping → `visibility / retention_policy / SourceKind` 实现参考 |
| **graphiti / Zep**(v4 新增独立行) | 三时间字段 `valid_at/invalid_at/expired_at`;SagaNode 增量摘要;多 scope search trace(edge/node/episode/community);MinHash/Jaccard 去重;contradiction resolver;DateFilter CNF;combined extraction 的 `episode_indices` 与 per-edge `reference_time` | 三时间复用为 Starling 四时间制(+ inferred_at);SagaNode → Replay `compress`;多 scope trace → RetrievalReceipt.scopes/candidate_counts/score_breakdown;`episode_indices/reference_time` → `SourceSpanRef/TemporalAnchor`;resolve_edge_contradictions → supersedes 链;加 holder 维度后做子图族 |

> Starling 要造的不是第 10 个开源记忆库,而是它们之上的认知层。

**v14 收敛约束**:
- `mem0 Memory / Graphiti Episode / Letta Block / cognee DataPoint / MemOS MemCube / memU WorkflowStep / claude-mem Observation` 都不得直接成为 Starling 核心表;只能映射为 DrawerRecord、Statement、Container、PipelineRun 或 Adapter metadata。
- 外部库检索 scope 不得进入 `RetrievalScopeStep.scope`;必须通过 `adapter_scope` 记录,核心 Planner 只按 Starling 逻辑 scope 执行。
- 外部库的任务状态不进入 Starling 状态枚举;异步运行统一落到 `PipelineRun.status` 与 BusEvent。
- 外部库的权限/租户过滤只可加强 `ProfileCapability/storage_enforced`,不能绕过 Bus 或 perspective filter。

---

## 21. 致谢与素材出处

本设计在以下素材之上独立成型:

- 9 个开源项目的源码深读(`_research/01_core_repos_deepdive.md` / `02_aux_repos_deepdive.md` / `04_repos_resurvey_2026.md`)
- Anthropic Claude Memory / OpenAI ChatGPT Memory 公开博客与社区讨论
- HippoRAG 2 / EM-LLM / Larimar / A-Mem / RMM / ReMemR / Graphiti / EnigmaToM / SoMi-ToM / PDDL-Mind / MMToM-QA / MOMENTS 等学术工作
- "Memory in the Age of AI Agents"(2025-12, 102 页综述)
- 神经科学与认知心理学经典:McClelland 1995(CLS) / Tulving 1985(Episodic/Semantic) / Yassa & Stark 2011(Pattern Separation) / Conway & Pleydell-Pearce 2000(SMS) / Clark 1996(Common Ground) / Fiske 1992(Relational Models) / Anderson & Hulbert 2021(Adaptive Forgetting) / Nader 2000(Reconsolidation)
- Wilf 2023 SimToM / Kim 2023 FANToM / Cross 2024 Hypothetical Minds

**v4 新增——2026 前沿论文**(详见 `_research/05_frontier_2026.md`):
- **Human-Like Lifelong Memory** (arxiv 2603.29023, ICLR 2026 MemAgent Workshop) —— CLS 架构 + CBT belief hierarchy,Starling CLS 路线的学术背书
- **Adaptive ToM for LLM-based Multi-Agent Coordination** (arxiv 2603.16264, AAAI 2026) —— 首个自适应 ToM agent,实时估计 partner ToM order,→ §9.6 ToMDepthEstimator
- **ToM4AI 2026 Proceedings** (arxiv 2603.18786) —— ToM 与 AI 交叉的系统性 curated anthology,→ §12 设计依据
- **Episodic Knowledge Binding** (OpenReview 2026) —— LLM 跨时间绑定 episodes 的根本失败,→ §6.2 episodic_link 动机说明
- **Governing Evolving Memory in LLM Agents** (arxiv 2603.11768) —— 三个 fundamental trade-offs(Fidelity-Utility / Stability-Plasticity / Privacy-Awareness),→ §19 风险框架
- **Amory: Coherent Narrative-Driven Agent Memory** (EACL 2026, aclanthology 2026.eacl-long.183) —— narrative coherence 作为 memory organization 原则,→ §6.3 + §13.5
- **Knowledge Objects for Persistent LLM Memory** (arxiv 2603.17781) —— Knowledge Objects 抽象对比 Statement,→ §3.2
- **Evaluating ToM and Internal Beliefs in LLM-Based Multi-Agent Systems** (arxiv 2603.00142) —— BDI + ToM + 符号验证三层架构,→ §5.3 + §12
- **Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Applications** (arxiv 2603.07670) —— 2026 年 agent memory 结构化综述,→ §1 领域全景引用
- **Zep: A Temporal Knowledge Graph Architecture for Agent Memory** (arxiv 2501.13956) —— Graphiti 学术背书,→ §16.2

如本文档进入实施阶段,需在第一里程碑前补充:
- 完整 schema 的 Pydantic 实现与 JSON-Schema 导出
- Validator 的 LLM 抽取 prompt(XML strict)
- Replay Scheduler 的具体采样器算法与默认权重
- Retrieval Planner 的 9 个 Intent 路径的可执行实现
- 与 mem0 / Letta / cognee / Graphiti 的 4 套 adapter 接入示例
- SourceAdapter conformance test:byte-preserving round trip、declared-lossy replay、privacy_class、metadata_only evidence 标注
- Storage-enforced tenant isolation test:by-id、bulk、vector search/delete、unknown data command 的 fail-closed 行为

---

## 附录 A:与 9 个开源项目的能力差异对照表

| 能力 | mem0 | Letta | cognee | MemOS | EverOS | memU | mempalace | claude-mem | graphiti | **Starling** |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| holder 归属 | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | 🟡 | ❌ | ❌ | ✅ |
| 二阶 ToM(nesting_depth=2) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| KnowledgeFrontier | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| CommonGround pool | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Affect 五维 + salience 公式 | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | ✅ |
| 真前瞻(Trigger + 状态机) | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 优先级重放(情感/新颖/奖励) | ❌ | 🟡 | 🟡 | 🟡 | ❌ | ❌ | ❌ | 🟡 | 🟡 | ✅ |
| 模式分离(反相似偏移) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🟡 | ✅ |
| 模式补全(PPR 图游走) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Drawer 证据保留/合规擦除 | ❌ | 🟡 | ❌ | ❌ | 🟡 | ❌ | ✅(原档) | ✅(原档) | 🟡 | ✅(retention mode) |
| Source adapter 转换声明 | ❌ | ❌ | ❌ | ❌ | 🟡 | 🟡 | ✅(RFC) | ❌ | ❌ | ✅ |
| 底座命令边界租户隔离 | 🟡 | 🟡 | 🟡 | 🟡 | ✅ | ❌ | ❌ | ❌ | 🟡 | ✅ |
| 双时间(valid_from/valid_to) | ❌ | ❌ | ✅(外包 graphiti) | ❌ | 🟡 | ❌ | ✅ | ❌ | ✅(三时间) | ✅(四时间) |
| supersedes 链(不覆盖) | ❌ | ✅(真 git) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅(expired_at) | ✅ |
| Reconsolidation 状态机 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Abstention 判定 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Retrieval Planner(7 步 + 9 Intent) | ❌ | ❌ | 🟡 | 🟡 | 🟡(HyperMem 三级) | ❌ | ❌ | ❌ | 🟡(rerank) | ✅ |
| RetrievalReceipt / sufficiency | ❌ | ❌ | ❌ | 🟡 | 🟡 | 🟡 | 🟡 | ❌ | 🟡 | ✅ |
| Persona-Belief 分通道 | ❌ | 🟡 | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | ✅ |
| Fiske 关系类型 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Commitment 状态机 + RENEGOTIATED | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| 增量摘要节点(SagaNode 类) | ❌ | ❌ | ❌ | ❌ | 🟡 | 🟡 | ❌ | 🟡 | ✅ | ✅(compress) |
| Hyperedge / N 元关系 | ❌ | ❌ | ❌ | ❌ | ✅(HyperMem) | ❌ | ❌ | ❌ | ❌ | 🟡(CommonGround) |
| **认知层成熟度(定性)** | 低 | 中低 | 中低 | 低 | 中 | 低 | 中低 | 中低 | 中低 | 高 |

说明:🟡 表示局部或相邻能力,不等同于 ✅ 完整支持;定性成熟度只用于架构比较,不作为功能打分。

---

## 附录 B:为什么这套设计能让 LLM"更懂人"

**人类记忆三个不易察觉的特点**:

1. **记忆是"我"的,而不是"事实"的**。我们不记得"咖啡 30 元",我们记得"昨天我和 Alice 在那家店,她请我喝的咖啡 30 元"。Starling 把"我的"做成 holder 字段 —— 所有记忆从写入那一刻就带着归属,不会退化为无主事实。

2. **记忆为当前目标重构,不是回放**。Conway SMS 模型的核心发现:自传体记忆是建构性的,每次检索都是一次重构。Starling 的 Retrieval Planner 用 perspective + goal 重构而非 fan-out,Context Pack Builder 的 8 种语用标签让 LLM 不只是"看到事实"而是"理解这段记忆对我意味着什么"。

3. **我对你的画像 ≠ 你对自己的认知**。社会智能的核心。Starling 的 holder 子图族 + perspective_take 算子让"我以为你的样子"和"你自己"物理分离,不会互相污染。

**LLM 当前的"懂人"瓶颈与 Starling 的对策**:

| 瓶颈 | 现象 | Starling 对策 |
|---|---|---|
| 不分主体的 fact 全局化 | 矛盾时被迫挑边或编造 | holder 强制归属 + CONFLICTS_WITH 边保留多版本 |
| 不分通道的 persona/belief 混存 | 一次会话颠覆长期画像 | Persona 与 Belief 分通道 + 更新需多证据 |
| 不区分共识与单边断言 | 反复复述已 grounded 内容,显得"机械" | CommonGround pool + grounding status 检查 |
| 不追踪信息可见性 | 泄露未在场者不该知道的信息 | KnowledgeFrontier + perspective filter(iterative masking) |
| 不处理二阶视角 | 不会礼貌提示,也不会合适隐瞒 | nesting_depth + META_BELIEF QueryIntent |
| 不会主动惦记承诺 | agent 说过就忘,用户不信任 | Prospective Loop + Trigger 类型系统 + 主动提醒 |
| 说错无法追溯 | 信任崩塌但找不到根因 | supersedes 链保留完整历史 + Drawer 证据指针 |

Starling 的 schema + 运行时,**每一项都对准上述瓶颈**。这不是 prompt 工程的精进,而是数据模型层对人类社会认知结构的对齐 —— 在 LLM 看到任何文本之前,检索系统就已经按"谁、知道什么、不知道什么、和谁共识了、承诺了什么、情绪有多强"组织好了信息。

## 附录 C:术语表(v10 新增,v13 扩展)

| 术语 | 一句话定义 | 首次定义 |
|---|---|---|
| `active_grounded` | CommonGround 中未 expired/superseded/ungrounded 的 grounded 条目,可获得遗忘保护 | §10.4 |
| `ActionPolicyGraph` | Prospective Loop 触发真实外部动作前必须通过的动作策略图,约束前置步骤、审批、次数和终止节点 | §12.5 |
| `ARCHIVED` | 低 salience 或历史版本的降级状态,默认仍可审计检索 | §3.4 |
| `Bus.write` | 写 Statement/边/索引并同事务追加 outbox 的唯一入口 | §5 |
| `canonical_conflict_key` | 冲突探针使用的规范化 key,包含 holder/modality/subject/predicate/object/time/scope | §5.2 |
| `Cognizer` | 可持有信念、画像、知识边界与信任先验的认知主体 | §3.1 |
| `CommonGround` | 多主体之间的共同知识物化视图,由 StatementRefs 重建 | §3.6 |
| `CONSOLIDATED` | 已经从快记忆巩固到稳定可检索层的 Statement 状态 | §3.4 |
| `crypto_erasure` | 销毁内容密钥使 verbatim 不可恢复,只保留 hash/审计元数据 | §3.8 |
| `declared_transformations` | source adapter 声明对源内容执行过的转换列表,用于判定 byte-preserving/declared-lossy | §3.8、§6.0 |
| `DrawerRecord` | 原始证据记录,由 `Bus.append_evidence` 创建,Statement evidence 必须引用它 | §6.0 |
| `failure_policy` | Pipeline step 的失败处理策略,分 critical/non_fatal/skip_downstream | §5.6 |
| `FORGOTTEN` | 合规删除或保留期到期后的不可热读状态,可能伴随 redaction/crypto erasure | §3.4 |
| `grounded` | 已被确认或推定为共同知识的 CommonGround 条目状态 | §9.5 |
| `holder` | Statement 的信念持有者,不一定等于说话人或 subject | §3.2 |
| `IngestPolicy` | Drawer 写入入口对 source_kind 的存储策略,如 STORE/NO_STORE/STORE_METADATA_ONLY/REQUIRE_REVIEW | §5 |
| `idx_entity_statement` | holder-aware entity→Statement 投影索引,用于实体命中后快速拉取相关 holder 子图 | §4.1 |
| `modality` | Statement 的心智样态,如 BELIEVES/KNOWS/COMMITS/PREFERS | §3.2 |
| `outbox` | 与存储事务同提交的 durable event log,按 at-least-once 投递 | §5 |
| `perspective` | 检索或生成时采用的主体视角,受 KnowledgeFrontier 遮蔽 | §7.2 |
| `PipelineRun` | Extraction/Replay/Projection/Compliance 等长任务的可恢复运行账本 | §5.6 |
| `polarity` | Statement 对 predicate/object 的肯定或否定取向 | §3.2 |
| `ProfileCapability` | 部署 profile 声明并由启动 preflight 校验的底座硬能力集合 | §4 |
| `provenance` | Statement 来源分类,如 user_input/replay_derived/tom_inferred/reconsolidation_derived | §3.10 |
| `REPLAYING_CONSOLIDATING` | VOLATILE Statement 进入巩固流程时的物理状态 | §3.4 |
| `REPLAYING_RECONSOLIDATING` | 已巩固 Statement 被召回或冲突触发后的可塑窗口状态 | §3.4 |
| `RetrievalReceipt` | 检索执行的审计回执,记录路径、过滤、候选数、分数、降级和 abstention 原因 | §13.6.1 |
| `RetrievalScopePlan` | 检索的多 scope 执行计划,显式声明 scope 顺序、filter 模式、短路/合并策略和 stop reason | §13.1 |
| `review_status` | 派生、低置信或待人工确认 Statement 的审核状态 | §3.2 |
| `RuntimeHealth` | 运行时健康状态机,控制 READY/DEGRADED/DRAINING/UNREADY 下的读写和后台调度 | §5.6 |
| `salience` | 情感、新颖性、目标相关性和 stakes 综合出的重放优先级信号 | §3.9 |
| `ScopedWorkGate` | 按 tenant/holder/aggregate/lane 限制后台任务并发的可重入工作闸门 | §5.6 |
| `SourceSegment` | DrawerRecord 内的片段级源映射,记录 offset、speaker、role、observed_at 和 hash | §3.8 |
| `SourceSpanRef` | Statement 到 DrawerRecord 片段/episode/segment 的证据锚,用于追溯抽取来源 | §3.2 |
| `SourceKind` | Drawer 输入来源分类,用于阻止 system_internal/observer_agent/replay_output 自污染 | §5 |
| `Statement` | Starling 的核心原子:谁在何时基于何证据以何样态持有什么判断 | §3.2 |
| `storage_enforced` | tenant/holder scope 在底座命令边界强制注入,而非仅应用层传参 | §4 |
| `SUPERSEDES` | 新版本 Statement 对旧版本 Statement 的非覆盖式替代边 | §7.3 |
| `sufficiency_status` | RetrievalReceipt 对检索结果是否足以回答的判定,如 SUFFICIENT/MISSING_INFO/NEEDS_RAW/ABSTAINED | §13.6.1 |
| `TemporalAnchor` | 相对时间解析锚,默认来自 source span 的 observed_at/reference_time,不得随导入时间漂移 | §3.2 |
| `trace_retention` | prompt/response/trace 的保留层级,控制 metadata/hash/debug/full_debug 的合规边界 | §5.6 |
| `VOLATILE` | 新写入、尚未巩固的快记忆状态 | §3.4 |

## 附录 D:实施 FAQ(v10 新增,v13 扩展)

| 问题 | 一句话答案 | 关联章节 |
|---|---|---|
| 为什么 Statement.object 可以引用 Statement,会无限递归吗? | 只允许 object 承担二阶嵌套,默认 `nesting_depth ≤ 2`,StatementRef 规范化也只做一阶展开。 | §3.2、§5.2、§9.1 |
| outbox at-least-once 投递,幂等性由谁保证? | Bus outbox 和 Subscriber inbox 都持久化 `idempotency_key`,业务副作用还需声明业务幂等窗口。 | §5.4 |
| Replay 派生的 Statement 为什么不会触发新一轮 Replay? | `replay_derived` 经 Bus 写入但 emit `statement.derived`,Replay 不订阅该事件。 | §3.10、§10.3 |
| CommonGround 的 grounded 条目为什么不会永远不衰减? | 遗忘保护只看 `active_grounded`;SupersedeGround/ExpireGround/Unground 会移除保护。 | §9.5、§10.4 |
| crypto_erasure 后 Statement 还能查到吗? | 可查到 Statement 元数据、hash、source metadata 与擦除标记,但 verbatim 不可恢复。 | §3.8、§10.4、§16.1 |
| 多个 Cognizer 共享 DrawerRecord,单方 purge 会影响其他人吗? | 需按 retention_mode、access_policy 与 legal_hold 判断;共享记录不能简单物理删除,生产底座需 refcount/key shredding。 | §3.8、§6.0、§16.2 |
| 为什么 Container 是物化视图而非事实源? | Persona/CommonGround 可由 StatementRefs 重建,事实权威留在 Statement 图,避免 Container CAS 冲突变成事实冲突。 | §3.6、§5.5 |
| Projection Index 落后时检索怎么办? | 超过 freshness SLA 时 Retrieval 降级主表直查或标记 stale,projection 不作为权威事实源。 | §4.1 |
| ToM 窗口限流和 causation_chain 限流哪个优先? | 先检查链长防递归,再检查 ToM 窗口防抖动写入;窗口超限只返回 transient context。 | §5.4、§9.2 |
| P0 为什么不交付完整 Replay/ToM/Prospective? | P0 目标是 schema、写入、冲突与 basic_retrieve 的可执行闭环,认知动力学按 P1-P4 分阶段上线。 | §16.1 |
| profile preflight 失败时能否自动降级继续跑? | 只有开发 profile 可显式降级;生产 profile 对 outbox、tenant isolation、crypto_erasure 等硬能力必须 fail-closed。 | §4 |
| RuntimeHealth=DEGRADED 时会丢事件吗? | 不会丢已提交 outbox/合规/承诺事件;只会暂停或丢弃可重建的低优先级 soft work。 | §5.6 |
| 为什么需要 RetrievalReceipt,Context Pack 不够吗? | Context Pack 给 LLM 使用,Receipt 给审计、评测和排障使用,二者目的不同。 | §13.6、§13.6.1 |
| PipelineRun 和 outbox checkpoint 是一回事吗? | outbox checkpoint 追踪事件投递位置,PipelineRun 追踪长任务自身的输入、进度、watermark 和阶段耗时。 | §5.4、§5.6 |
| 系统内部日志、检索回执和 Replay 摘要能被记住吗? | 默认不能;它们是 `source_kind=system_internal/replay_output`,除非 allowlist 到 metadata-only/evaluation tenant,否则 `NO_STORE`。 | §5、§6.0 |
| metadata_only Drawer 能作为事实证据吗? | 只能作为辅助来源;高影响 Statement 需要 byte-preserving 或其他可信 evidence 才能自动 APPROVED。 | §3.8、§6.0 |
| 为什么生产 profile 不能只靠应用层 tenant filter? | 因为 by-id、bulk、raw query、vector delete 等路径容易绕过 service 约定,生产必须在底座命令边界强制注入 scope 并拒绝未知数据命令。 | §4 |
| Projection rebuild 如果从损坏索引读少了怎么办? | shadow rebuild 完成后必须对独立真相源校验 row count/watermark/hash;疑似截断时拒绝 swap。 | §4.1 |
| 多 holder 检索为什么要拆分执行? | 拆分能让每个 holder/group 在独立 scope 下查询并审计过滤器,避免宽泛扫描后置过滤造成泄露。 | §13.3 |
| RetrievalReceipt 的 `NEEDS_RAW` 会直接打开 Drawer 原文吗? | 不会;它只是声明摘要不足,真正打开 raw evidence 前还要通过 retention、visibility、tenant/holder scope 检查。 | §13.6.1 |
| 为什么历史导入不能用系统当前时间解析 "today/last week"? | 因为相对时间属于源材料观察时刻,必须绑定 `TemporalAnchor.anchor_time`;缺锚时只能低置信待审。 | §3.2、§5.1 |
| 如果一个 Statement 来自多个 episode/span,时间锚取哪个? | `SourceSpanRef` 记录所有证据片段,默认 temporal anchor 取第一归因 span,其他 span 作为 supporting evidence 并保留各自 observed_at。 | §3.2、§5.1 |
| holder/source_speaker/perceived_by 抽错了能直接 UPDATE 吗? | 不能;归因字段是审计边界,纠错必须写 `statement.corrected` 新版本并建立 supersedes。 | §3.2、§5.1 |
| `RetrievalScopePlan` 为什么要记录 skipped scope? | 因为 sufficiency 短路不是全量检索,Receipt 必须解释为什么没查 graph/vector/drawer raw。 | §13.1、§13.6.1 |
| Pipeline step 标 `non_fatal` 是否表示可以忽略失败? | 不是;它只允许主 run 降级继续,必须写 warning/counter,且 downstream `requires` 不满足时仍要跳过或失败。 | §5.6 |
| Prospective Loop 什么时候需要 `ActionPolicyGraph`? | 只提醒用户可轻量处理;一旦要调用外部工具、发通知、开 issue、改日历或调用业务 API,必须经过策略图。 | §12.5 |
| `idx_entity_statement` 会不会变成全局实体扫描入口? | 不能;它的主键包含 tenant_id/holder/state,所有 entity 命中都必须在 holder-aware 子图内展开。 | §4.1、§13.3 |

— 完 —
