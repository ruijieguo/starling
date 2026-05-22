# 06 — v4 架构合理性审查报告

> 产出日期:2026-05-05
> 审查对象:`04_anima_design_v4.md` (1454 行)
> 审查方法:逐层职责核对 + 状态机闭环 + 事件订阅闭环 + 模块循环依赖 + 抽象漏洞

---

## 总体评估

v4 在数据模型(Statement schema)、社会心智本体(holder/perspective/二阶 ToM)、文献整合上是扎实的;**但在运行时架构层面有 2 个 Blocker + 8 个 Major + 5 个 Minor 级问题**,直接施工会卡在第一周。

根因:v3/v4 把 §3 数据模型与 §6/§7 运行时分层当成两套独立叙述写,接口未对齐;§3.4 状态机图在 v2→v4 多次迭代中只画了部分迁移,缺关键边;Bus 事件表未做"产生者-消费者"完备性核对。

---

## Blocker(必须先修)

### B1 — "五类记忆是视图 vs 物理分层" 自相矛盾

**位置**:§3 设计原则(第 127 行) vs §6.1 / §7.1

**矛盾**:
- §3 说"五类记忆是 Statement 上的视图,不是物理分表"
- §6.1 给 Hippocampus 画 4 个物理分层(Drawer / Episodes / Working Set / Affect Buffer)
- §7.1 给 Neocortex 画 5 个物理子区(Semantic / Procedural / Norms / Personae / CommonGround)
- 两侧都有"更新通道"列,显然不是 SQL 视图

**真问题**:VOLATILE → CONSOLIDATED 是状态字段变更(纯视图)还是物理移动?未明确。
- 视图说:§6/§7 的"物理分层"图全错,误导工程
- 物理说:§3"不是物理分表"错,且物理移动需要双写事务,文档未设计

**修复方向(留给 v5)**:确立三层抽象:
1. **逻辑层**(§3 Statement schema + view definitions)
2. **运行时分区层**(§6/§7 改名为"逻辑分区",对应 partition tag/index)
3. **物理底座层**(§4 Substrate Adapter 决定实际存储)

VOLATILE → CONSOLIDATED **是状态字段 + 索引变更,不是表迁移**。Drawer 是独立 BlobStore,与 Statement 解耦。

---

### B2 — Replay 输出的新 Statement 写入路径未定义

**位置**:§10.3 巩固原子操作 + §5 Bus 硬约束

**问题**:`compress / abstract / induce_norm / forge_skill` 全部输出"新候选 Statement",但写入路径未定。三种可能,每种都坏:

1. **走 Bus → Validator → Hippocampus(VOLATILE)** :触发新一轮 `statement.written` → Replay 又看到 → 无限循环
2. **绕过 Bus 直接落 Neocortex(CONSOLIDATED)**:违反 §5"所有读写必经 Bus"的硬约束
3. **走 Bus 但加 derived_from 标记跳过 Replay**:Validator 需白名单逻辑,文档未提

**修复方向(留给 v5)**:选方案 3,显式写明:
- Replay 产出走 Bus 但带 `is_derived=True` 标记
- Validator 见此标记则**直接进 CONSOLIDATED 状态**(跳过 VOLATILE)
- 不发出 `statement.written` 而发 `statement.derived` 新事件
- Replay 自身不订阅 `statement.derived`,断开循环

---

## Major(影响正确性,实施前必修)

### M1 — §3.4 状态机图缺 4 条迁移边

**位置**:§3.4 ConsolidationState 状态图

**缺失边**(§11.1/§11.2 的核心动力学完全没体现在状态图):
- `CONSOLIDATED → REPLAYING`(被回忆/冲突触发再巩固)— 这是 §11 整章的核心,图里没画!
- `REPLAYING → CONSOLIDATED`(Reconsolidation 确认旧版)
- `REPLAYING → ARCHIVED`(Reconsolidation contradicts severe 时旧版进归档)
- `ARCHIVED → REPLAYING`(召回已归档的旧 stmt 时,根据 §11 应该可以重新激活)

**修复**:重画状态图,补全 4 条边;明确每条边的触发条件、原子操作、副作用。

---

### M2 — REPLAYING 状态的两种语义重叠

**位置**:§3.4 + §10 + §11

**问题**:同名 REPLAYING 但承载两种完全不同的意图:
- §3.4: `VOLATILE → REPLAYING`(Replay Scheduler 选中,**目的:巩固进新皮层**)
- §11.1: `CONSOLIDATED → REPLAYING`(被召回/冲突,**目的:再巩固/修改已巩固内容**)

工程后果:
- 谁负责 close 窗口?
- 谁决定下一态是 CONSOLIDATED 还是 ARCHIVED?
- 两类 REPLAYING 对应的 plastic_window_timeout 不同(默认 30min vs 自适应 5min-6h)

**修复方向(留给 v5)**:
- 拆为两个子态:`REPLAYING_CONSOLIDATING`(VOLATILE 来) vs `REPLAYING_RECONSOLIDATING`(CONSOLIDATED 来)
- 或保留单态但加 `replay_intent: "consolidate" | "reconsolidate"` 字段,close 窗口者各管各
- 推荐前者,状态图更清晰

---

### M3 — Drawer 分层错误

**位置**:§3.8 vs §6.1 vs §16.2

**矛盾**:
- §3.8: Drawer 是 Statement.evidence 指向的"verbatim 原档" → 像独立资源
- §6.1: Drawer 是 Hippocampus 的"内部分层"之一
- §10.4: "Drawer 永留" 暗示独立于 Hippocampus 生命周期
- §16.2 letta 迁移:Archive(可跨 agent 共享原档池) → Drawer 应是**全局服务**

**真物理位置**:与 Hippocampus / Neocortex 平级的全局 BlobStore;§4 Substrate 已有 BlobStore 行。

**修复**:把 Drawer 从 §6.1 内部移出,作为独立子系统(可建 §6.0 或扩 §4)。

---

### M4 — BusEvent 缺 5 个终态事件

**位置**:§5.3 + §12.2 + §3.4

**缺失事件**:
- `statement.archived`(状态机有 ARCHIVED 但无对应事件)
- `statement.forgotten`(同上,合规清理无事件可订阅)
- `commitment.fulfilled` / `commitment.broken` / `commitment.renegotiated`(§12.2 五态机所有终态都没事件)

**§14.4 例子里"Bob 履行后 trust_priors 上调"必须 emit 才能实现** —— v4 写的"PolicyEngine 检测到 fulfilled" 但没 emit 路径。

**修复**:§5.3 表补 5 行,每个状态终态都要可订阅。

---

### M5 — ToM/ConflictProbe/Reconsolidation 闭环无防抖

**位置**:§11.1 + §5 + §9

**循环**:
```
ConflictProbe 标冲突
  → emit belief.conflict
  → Reconsolidation 仲裁
  → 产 supersedes 链
  → emit statement.superseded
  → ToM 更新 CommonGround
  → ToM 可能产生新嵌套 Statement
  → ConflictProbe 又标冲突
  → ...
```

无递归深度限制 / 无幂等键。

**修复**:加 invariant —— 同一 (subject, predicate) 在 N 秒内不重复触发同类事件;重入计数器超阈值 emit `system.runaway` 告警。

---

### M6 — Retrieval 是读路径但产生写副作用

**位置**:§13 + §11.1

**问题**:
- §11.1 触发 #1:被 Retrieval 召回到 Working Set → 进入可塑窗口(写副作用)
- §13 全章设计为"读规划器"
- 每次读都可能改 confidence、改 supersedes —— 可重入性、并发、缓存一致性全部受影响

**修复方向(留给 v5)**:
- §13 Retrieval 只 emit `statement.recalled` 事件
- Reconsolidation 异步消费决定是否开窗
- §13 章节加并发与幂等说明
- 保留"读不直接改"的契约

---

### M7 — EpisodicView 定义违反 Tulving

**位置**:§3.5

**当前定义**:`EpisodicView = WHERE modality=BELIEVES AND event_time IS NOT NULL AND consolidation_state IN (VOLATILE, REPLAYING)`

**违反**:Tulving 1985 的 Episodic 与 Semantic 区分**不依赖巩固状态**而依赖"是否绑定具体时空"。人类的自传体记忆显然有"巩固后的情景记忆"。

**修复**:`EpisodicView = WHERE event_time IS NOT NULL` 即可;去掉 consolidation_state 限定。

---

### M8 — PolicyEngine 的 emit 路径未明确

**位置**:§12 + §5

**问题**:`commitment.fire` 表里写"Trigger 命中",§12 只说"PolicyEngine 监听"。PolicyEngine 是否走 Bus?Bus 硬约束"所有读写必经"是否包括内部触发?

**修复**:显式说 PolicyEngine 是 Bus 的发布者之一,所有 Trigger 命中走 `Bus.emit("commitment.fire", ...)`。同时 §12 流程图与 §5 事件表保持一致。

---

## Minor

### m1 — Affect Buffer vs Replay 优先级队列职责重叠

§6.6 Affect Buffer 是数据结构(优先级队列);§10.2 Replay 优先级采样器也是按 salience 排。
明确:Affect Buffer 是**入口缓冲**,Replay sampler **从全表(或 Buffer 优先)取候选**。补关系图。

### m2 — Working Set 8 label vs Persona schema 字段边界不清

§6.5 Working Set 中 `self_persona / interlocutor_persona` 等 label 与 §3.6 Persona schema(self_model_anchor / profile_anchor)的关系:Working Set 是 **prompt 时刻的渲染快照**,Persona 是 **持久化结构**。补一句话即可。

### m3 — Persona / CommonGround 不是 Statement 子类

§3 原则说"所有可写入都是 Statement 的子类",但 §3.6 Persona / CommonGround 继承 BaseEntity 而非 Statement。这是**容器型实体**(装 Statement 但本身不是)。在 §3 原则里加二分:`Statement(陈述) | Container(容器)`。

### m4 — EntityRef 类型未定义

§3.2 `subject: CognizerRef | EntityRef`,EntityRef 全文未定义。补:Entity 是 Cognizer 之外的"物体/概念/项目"实体,有 id/name/aliases 与 KG 节点对应。

### m5 — Commitment 状态机细节

§12.2 五态机:
- `created` 隐式态,应明确"created 由 modality=COMMITS 的 Statement 写入触发"
- BROKEN 后能否再 RENEGOTIATED? 现实场景"我后来又答应你了"。

---

## 给 v5 的修复路线

按优先级:

1. **重写 §3.4 状态机图**:补 4 条边 + 拆 REPLAYING 子态
2. **重写 §3 设计原则**:确立逻辑层/分区层/物理层三抽象,声明 Statement vs Container 二分
3. **重写 §3.5**:修正 EpisodicView 定义
4. **新增 §3.10**(或入 §3 末尾):Statement 写入路径分类(用户输入 / Replay 派生 / ToM 推断),每类的 Bus 处理规则
5. **重写 §6**:Drawer 移出 Hippocampus,Hippocampus 内部仅 Episodes/Working Set/Affect Buffer 三块
6. **新增 §6.0**(或加 §4 一节):Drawer 作为全局 BlobStore 的独立子系统
7. **重写 §10.3**:每个原子操作明确"输出 Statement 是否走 Bus + 是否触发 Replay"
8. **重写 §11**:加并发/幂等/防抖小节,与 §5 Bus 事件契约对齐
9. **重写 §5.3 BusEvent 表**:补 5 个终态事件;补每事件的 producer/consumer 完整列
10. **重写 §13.x**:加"读不改写状态"契约 + Retrieval 只 emit `statement.recalled`,异步消费
11. **§12 显式 PolicyEngine ↔ Bus 关系**
12. **§17.4 v4 → v5 changelog**

预计 v5 行数 1500-1700,主要在 §3 / §5 / §6 / §10 / §11 五节扩写。

---

## 哪些不需要改

- §1 三条公理:不变
- §2 总览:基本保留,12 层架构图微调(Drawer 移位)
- §7 Neocortex:概念正确,只需把"五个子区"措辞从"物理子区"改为"逻辑分区"
- §8 Cognizer Hub:不变
- §9 ToM Engine:不变(§9.6 A-ToM 已加好)
- §12 Prospective Loop:仅补 Bus 关系
- §13 Retrieval Planner:仅加并发契约,7 步规划不变
- §14 端到端示例:若状态名改,文字同步即可
- §15 评测:不变
- §16 路线图:不变
- §18-§21 + 附录:不变(附录 A 表 2026 状态已对)

— 完 —
