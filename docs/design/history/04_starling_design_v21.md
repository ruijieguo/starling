# Starling Memory:多主体社会心智 + 类脑动力学的智能体记忆系统设计方案

> **本版**为 P1 编码起点。文档由主文档（本文件，§0 摘要、§1 公理、§2 总览、§3 数据本体、§14 端到端场景、§15 路线图、§16 取舍与风险）+ 11 个子系统文档（位于 `v21_subsystems/` 目录）组成。历史变更记录见 [附录 H](#附录-h)。

---

## 目录

- [§0 摘要](#0-摘要one-page)
- [§1 三条公理](#1-三条公理)
- [§2 系统总览](#2-系统总览)
  - [§2.1 子系统拓扑（谁是谁的邻居）](#21-子系统拓扑谁是谁的邻居)
  - [§2.2 数据流（Statement 从生到老的物理路径）](#22-数据流statement-从生到老的物理路径)
  - [§2.3 执行流（事件总线触发链）](#23-执行流事件总线触发链)
  - [§2.4 子系统索引](#24-子系统索引)
- [§3 数据本体](#3-数据本体)
  - [§3.1 本体总图（ER + UML 双视图）](#31-本体总图er--uml-双视图)
  - [§3.2 Cognizer 与 Entity](#32-cognizer-与-entity)
  - [§3.3 Statement 核心原子](#33-statement-核心原子)
  - [§3.4 Modality](#34-modality)
  - [§3.5 ConsolidationState 状态机](#35-consolidationstate-状态机)
  - [§3.6 五类视图与 Statement 子类](#36-五类视图与-statement-子类)
  - [§3.7 Container（Persona / CommonGround / KnowledgeFrontier）](#37-containerpersona--commonground--knowledgefrontier)
  - [§3.8 EngramStore 与证据](#38-engramstore-与证据)
  - [§3.9 AffectVector](#39-affectvector)
  - [§3.10 BusEvent 信封](#310-busevent-信封)
  - [§3.11 Provenance 与 ReviewStatus](#311-provenance-与-reviewstatus)
  - [§3.12 关键边类型（社会图谱）](#312-关键边类型社会图谱)
- [§14 端到端场景流程](#14-端到端场景流程)
- [§15 路线图](#15-路线图)
- [§16 取舍与风险](#16-取舍与风险)
- [附录 A 术语速查](#附录-a-术语速查)
- [附录 H 历史变更记录](#附录-h-历史变更记录)

---

## 0. 摘要（One Page）

Starling Memory 解决一个问题：让 LLM Agent 像人一样，对每个交互对象都形成一份「持续演化的他者画像 + 我对他的信念 + 我以为他相信什么」，并在系统层面具备类脑的「快写慢洗、优先重放、再巩固、自适应遗忘、显著性调制、前瞻触发」动力学。

它不是 user_id 隔离 + 向量库 RAG 的工程层抽象，而是数据模型 + 运行时调度 + 检索规划器三件套，可挂在 mem0 / Letta / cognee / Graphiti 之上。

**七大差异点**（在主流开源项目集体缺失之处）：

1. **Cognizer 一等公民**：认知主体而非 user_id 字段。
2. **Statement 替代 Fact**：所有写入都是「谁，在何时，基于何证据，对谁，以何样态、何极性，持有何判断」。
3. **二阶 ToM 数据模型**：嵌套 Statement + nesting_depth + 自适应 ToM order。
4. **类脑六态状态机**：`consolidation_state ∈ {VOLATILE, REPLAYING_CONSOLIDATING, REPLAYING_RECONSOLIDATING, CONSOLIDATED, ARCHIVED, FORGOTTEN}` 贯穿全生命周期。
5. **Reconsolidation 不覆盖**：被回忆即开启可塑窗口，旧版本进 supersedes 链而非删除。
6. **真前瞻**：Trigger 类型化 + Commitment 五态机。
7. **视角化检索 + 心智摘要**：9 Intent × Perspective Filter × Affect Reranker × Context Pack Builder × 7 Mentalizing Primitives。

**关键非目标**：不重写向量库、不做训练、不追求形式化完备。

### 0.1 外部机制吸收原则

外部库提供经验样本，不是 Starling 的第二套架构。任何复用须满足四条收敛规则：

1. **原生原语优先**：外部概念只能映射到 `Statement / Engram / BusEvent / PipelineRun / RetrievalScopePlan / ActionPolicyGraph / Projection Index / Container` 之一。不能因为某库有 `episode/session/block/memory/tool_rule` 就在 Starling 核心层新增同名一等实体。
2. **权威事实源唯一**：事实权威只在 Statement 图。Engram 是证据源，Container/Projection/RetrievalReceipt/PipelineRun 都是物化视图或运行账本，不得反向成为事实源。
3. **生命周期唯一**：异步任务终态以 `PipelineRun.status` 为权威。抽取、投影、Replay、Compliance 的子明细只能作为 run item 或 event payload，不能各自定义互相冲突的状态机。
4. **边界不外溢**：外部库的 scope/step/action 名字只能出现在 Adapter 层 metadata。Starling 核心只使用自己的 scope、event、policy 和 state 枚举。

### 0.2 简单性优先原则

复杂机制必须有明确触发条件。默认实现遵循：

| 领域 | 简单默认 | 升级触发 |
|---|---|---|
| 写入 | `Bus.append_evidence` + `Bus.write` + outbox | 多 worker / 跨进程 / 重放恢复需求出现后启用完整 PipelineRun lease/checkpoint |
| 证据锚 | `engram_ref + chunk_index + observed_at + source_hash` | 多 episode、PDF 分段、转录、多模态或 offset 级擦除需求出现后启用 `segment_map / span_start / span_end` |
| 检索 | 固定 `basic_retrieve(statement_main)` | 多 scope 成本差异、sufficiency 短路或 engram raw gate 需求出现后启用完整 RetrievalScopePlan |
| 投影 | 主 Statement 表 + 必要索引 | 主表查询无法满足 SLA 或数据量超过 P2 阈值后启用 Projection Index |
| Container | 整体 rebuild + 单 version CAS | 多维度高频更新导致 CAS 冲突后启用 dimension-level versions |
| 动作 | reminder-only + allowlist / approval / idempotency | 真实外部动作链需要前后置顺序 / 条件分支后启用 ActionPolicyGraph |
| Pipeline | 单 run 状态 + counters / watermark | 多 step 依赖、可选分支、非致命阶段失败需求出现后启用 PipelineStepContract |

文档中标为 P3、P3、P3 的机制不得被 P1 实现团队提前做成通用框架。P1 只证明核心闭环可跑通。

---

## 1. 三条公理

### 公理 I：没有孤立的事实，只有归属于主体的陈述

每条记忆必须是 `Statement(holder, subject, predicate, object, modality, polarity, time, evidence, confidence)`。这一条同时解决：归属、冲突、撤回、视角、二阶 ToM。

### 公理 II：记忆系统由两套时间尺度的子系统协同（CLS）

写入先入 Hippocampus（`VOLATILE`），经 Replay（`REPLAYING_CONSOLIDATING`）、模式分离 / 补全、再巩固（`CONSOLIDATED`），才有机会上升到 Neocortex 稳定语义 / 规范 / 技能 / 画像。

### 公理 III：记忆为当前目标重构，不是录像回放（Conway SMS）

检索不是 fan-out 工具堆，而是按 `(querier, perspective, intent, goal)` 重构出的视角化心智摘要，且具备显式 abstention。

---

## 2. 系统总览

总览分三张图，每张回答一个不同问题：拓扑（谁连谁）、数据流（Statement 怎么走）、执行流（事件怎么触发）。

### 2.1 子系统拓扑（谁是谁的邻居）

```
                     ┌─────────────────────────────────────────────────┐
                     │              Application Layer                   │
                     │     (Agent runtime / Conversation loop)          │
                     └───┬───────────────────────────────────────┬─────┘
                         │ append_evidence / write              │ retrieve
                         ▼                                       ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │                       Statement Bus                                │
   │  ┌──────────┐  ┌──────────────┐  ┌────────┐  ┌──────────────────┐ │
   │  │Validator │→ │ConflictProbe │→ │ outbox │→ │ event dispatcher │ │
   │  └──────────┘  └──────────────┘  └────────┘  └──────────────────┘ │
   └───┬─────────────┬──────────────┬──────────────┬───────────────┬──┘
       │             │              │              │               │
       ▼             ▼              ▼              ▼               ▼
   ┌────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────┐
   │EngramStor│ │Hippocamp │  │ Neocortex  │  │Cognizer  │  │ ToM      │
   │ (verbatim)│ │us VOLATIL│  │ CONSOLIDAT │  │ Hub      │  │ Engine   │
   │          │ │ Working  │  │ holder 子图│  │ Persona  │  │ 嵌套     │
   │          │ │  Set /   │  │ 族 / 五子区 │  │ KFrontier│  │ Stmt /   │
   │          │ │ Affect   │  │            │  │ trust    │  │ perspect │
   │          │ │ Buffer   │  │            │  │          │  │ ive_take │
   └────┬─────┘ └────┬─────┘  └─────┬──────┘  └─────┬────┘  └────┬─────┘
        │            │              │               │            │
        │            ▼              ▼               │            │
        │      ┌──────────────────────────┐         │            │
        │      │ Replay Scheduler         │         │            │
        │      │ Online / Idle / Sleep    │         │            │
        │      │ Reconsolidation Engine   │         │            │
        │      │ 可塑窗口 / supersedes    │         │            │
        │      │ Prospective Loop         │         │            │
        │      │ Trigger / Commitment 5态 │         │            │
        │      └────────────┬─────────────┘         │            │
        │                   │                       │            │
        ▼                   ▼                       ▼            ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │                Retrieval Planner                                  │
   │  9 Intent → Perspective Filter → fan-out → fuse →                 │
   │  Affect Reranker → ground → Context Pack (8 标签) → Abstention   │
   └────────────────────────────┬─────────────────────────────────────┘
                                │ Context Pack
                                ▼
                        Application Layer
   ┌──────────────────────────────────────────────────────────────────┐
   │  Substrate Adapter（三档 profile：local-store / dist-store / cloud-store） │
   │   - local-store: SQLite + LanceDB + Kuzu（嵌入式，P1）              │
   │   - dist-store: Postgres 18 + pgvector + Apache AGE（P2）          │
   │   - cloud-store: 单云原生 / 混合托管 / 跨云 SaaS 三形态（P3）         │
   │  + Runtime Governance（READY/DEGRADED/DRAINING/UNREADY,           │
   │    PipelineRun, ScopedWorkGate, critical lane）                  │
   └──────────────────────────────────────────────────────────────────┘
```

**邻接关系要点**：

- **Statement Bus 是单入口**。所有写入和事件都经它，没有旁路。
- **EngramStore / Hippocampus / Neocortex 平级**。EngramStore 不是 Hippocampus 的内部分层，是与 Hippocampus / Neocortex 平级的全局证据子系统，被 Statement.evidence 指向。
- **Replay Scheduler / Reconsolidation / Prospective 共享 Hippocampus 与 Neocortex**。它们读两侧、写两侧，但只通过 Bus 写。
- **Cognizer Hub 与 ToM Engine 横跨 Hippocampus 与 Neocortex**。Cognizer 持有 Persona Container 物化在 Neocortex，knowledge_frontier 用于 Retrieval Planner 硬过滤。ToM Engine 的 perspective_take 同时读 EngramStore / Neocortex / CommonGround。
- **Substrate Adapter 在最底**。所有持久化经它路由到 SQLite / Postgres / Vector Store / 图引擎。
- **Runtime Governance 横切**。它不在主链路上，但每个子系统启动需经 ProfileCapability preflight，运行时受 ScopedWorkGate 限流。

### 2.2 数据流（Statement 从生到老的物理路径）

```
                    ┌────────────────────┐
                    │  Application       │
                    │  append_evidence() │
                    └──────────┬─────────┘
                               │ raw text + metadata
                               ▼
                    ┌────────────────────┐
                    │   EngramStore      │  ← 永久 verbatim（按 retention_mode）
                    │   write Engram     │
                    └──────────┬─────────┘
                               │ EngramRef
                               ▼
                    ┌────────────────────┐
                    │   Bus emit         │
                    │   evidence.appended│
                    └──────────┬─────────┘
                               │
                               ▼
                    ┌────────────────────┐
                    │   Extractor        │  ← LLM 抽取多条 Statement
                    │   (LLM call)       │
                    └──────────┬─────────┘
                               │ Statement[]
                               ▼
                    ┌────────────────────┐
                    │  Bus.write(stmt)   │
                    │  Validator +       │
                    │  ConflictProbe     │
                    └──────────┬─────────┘
                               │ stmt 通过
                               ▼
                    ┌────────────────────┐
                    │  Hippocampus       │  ← state=VOLATILE
                    │  (logical part.)   │     index_tag=hippocampus
                    └──────────┬─────────┘
                               │ statement.written → Replay 订阅
                               ▼
                    ┌────────────────────┐
                    │  Replay Scheduler  │  ← 优先级采样
                    │  (Online/Idle/Slep)│     state=REPLAYING_CONSOLIDATING
                    └──────────┬─────────┘
                               │ 巩固原子操作（compress / abstract / ...）
                               ▼
                    ┌────────────────────┐
                    │  Neocortex         │  ← state=CONSOLIDATED
                    │  (logical part.)   │     index_tag=neocortex
                    │  holder 子图族     │     emit statement.derived
                    │  + Container 物化  │     （不是 statement.written）
                    └──────┬───────┬─────┘
                           │       │
              recall/      │       │ decay 公式 S(t)<0.05
              conflict/    │       │ 且 not active_grounded
              derived_from │       │
                           ▼       ▼
              ┌──────────────┐ ┌──────────────┐
              │REPLAYING_    │ │  ARCHIVED    │
              │RECONSOLIDATIN│ │              │
              │     G        │ │              │
              │ (可塑窗口     │ │  ┌─────────┐ │
              │  30 min)     │ │  │ recall  │ │
              └──┬─────┬─────┘ │  │ + audit │ │
                 │     │       │  └────┬────┘ │
       confirm   │     │       │       │      │
       (mild/    │     │ severe│       │      │
       support)  │     │ contra│       │      │
                 │     │ dict  │       │      │
                 ▼     │       │       │      │
        confidence     │       │       │      │
        ↑/↓ + history  │       │       └──────┘
        provenance 不变│       │  purge (合规)
                       ▼       │
              新版 fork +      ▼
              SUPERSEDES   ┌──────────┐
              旧版 ARCHIVE │FORGOTTEN │
              （4 项原子   │EngramStore│
                提交 / saga）│按         │
                           │retention  │
                           │_mode 处理 │
                           └──────────┘
```

**数据流不变量**：

- **EngramStore 永远先写**，再写 Statement。Statement.evidence 必须能追溯回 EngramStore；evidence 与 derived_from 至少其一非空。
- **Statement state 单向迁移为主**，唯一往回的路径是 `ARCHIVED → REPLAYING_RECONSOLIDATING`（被召回）。
- **provenance 写入即冻结**。后续 confidence 调整、state 迁移、access_count 累加都不改 provenance。
- **mild correction 不产新版**。轻微反对修改原 Statement 的 confidence + 追加 confidence_history，provenance 不变。
- **severe contradict 必产新版**。新版 + supersedes 边 + 旧版 ARCHIVED + outbox 事件四项同事务（local-store 走原子事务，dist-store 走 saga 补偿）。

### 2.3 执行流（事件总线触发链）

```
   ┌─────────────────────┐
   │  evidence.appended  │── Extractor ──┐
   └─────────────────────┘               │
                                         ▼
   ┌─────────────────────────────────────────────────┐
   │              Bus.write(stmt)                     │
   │              (Validator + ConflictProbe)         │
   └────┬─────────────┬─────────────┬─────────┬──────┘
        │             │             │         │
        │ user_input  │ replay_     │ tom_    │ reconsolidation_
        │             │ derived     │ inferred│ derived
        ▼             ▼             ▼         ▼
   statement.    statement.    statement.  raise
   written       derived       written     UseReconsolidation
                                           Transaction
        │             │             │
        ├─► Replay    ├─► ToM       ├─► Replay (×0.25 权重)
        ├─► ToM       ├─► Container ├─► ToM
        ├─► Affect    │   Builder   ├─► (causation 链 ≤3)
        │   Buffer    └─► Retrieval │
        └─► Prospect      cache     │
                                    │
   (不订阅 statement.derived)        │
   (不订阅 statement.corrected)      │

   检索路径：
   ┌────────────────────┐
   │  Application       │
   │  retrieve(query)   │
   └─────────┬──────────┘
             ▼
   ┌────────────────────┐
   │ Retrieval Planner  │── basic_retrieve / 7 步 ──┐
   └─────────┬──────────┘                            │
             │                                       │
             ▼ Context Pack                          │
   ┌────────────────────┐                            │
   │  Application       │                            │
   └────────────────────┘                            │
                                                     ▼
                                       statement.recalled
                                       (fire-and-forget)
                                                     │
                                                     ▼
                                          Reconsolidation
                                          异步开窗判定

   Reconsolidation 五条触发路径：
   ──────────────────────────────────────────────────────
   1. statement.recalled                  ← Retrieval emit
   2. statement.references_existing       ← Bus.write 检测 derived_from
   3. belief.conflict                     ← ConflictProbe emit
   4. reconsolidate.requested             ← 显式 API
   5. commitment.fulfilled / .broken      ← PolicyEngine emit
   ──────────────────────────────────────────────────────
   全部进入同一 stmt_id 的 pending_evidence 队列
   窗口 close 时（默认 30min）统一仲裁

   Prospective 触发链：
   ┌──────────────┐
   │ TimeTrigger  │
   │ EventTrigger │
   │ StateTrigger │
   │ Compound     │
   └──────┬───────┘
          ▼ 命中
   commitment.fire (经 Bus.emit)
          │
          ▼
   Working Set 注入 pending_commitments
          │
   履行检测                    deadline 过
          │                          │
          ▼                          ▼
   commitment.fulfilled       commitment.broken
   trust_priors ↑             trust_priors ↓
   commitment.released        ├─ 累计 ≥3 → auto_withdrawn
   (decay 解除保护)           └─ 进 RENEGOTIATED（链长 ≤3）
```

**执行流不变量**：

- **Replay 不订阅 `statement.derived`**。这是断开 Replay→派生→Replay 循环的关键不变量。同理 Replay 不订阅 `statement.corrected`。
- **Retrieval 是纯读模块**。对外只通过 emit `statement.recalled` fire-and-forget 间接影响 state，不直接修改。
- **decay 经事件总线**。Replay decay 不直接改 state，emit `statement.decay_candidate`，由 outbox dispatcher 对同 stmt_id 顺序串行处理（消除 T5/T8 race）。
- **Commitment 反向保护**。ACTIVE 时 emit `commitment.active_holding`，decay scheduler in-memory set 持有相关 stmt_id；终态时 emit `commitment.released` 释放保护。
- **causation_chain ≤ 3**。超过 emit `system.runaway`，断开自动派生。
- **PolicyEngine 是 Bus publisher**。所有 Trigger 命中走 `Bus.emit("commitment.fire", ...)`，不绕过 Bus。

### 2.4 子系统索引

13 个子系统，每个独立文档。文档分两组：

**核心数据子系统**（4 个）：

| # | 子系统 | 文档 | 职责 |
|---|---|---|---|
| 1 | Substrate Adapter | [v21_04_substrate.md](v21_subsystems/v21_04_substrate.md) | 三档 profile 的物理底座抽象，三层隔离 |
| 2 | EngramStore | [v21_06_engramstore.md](v21_subsystems/v21_06_engramstore.md) | verbatim 原档，retention_mode 生命周期 |
| 3 | Hippocampus | [v21_06_hippocampus.md](v21_subsystems/v21_06_hippocampus.md) | 快记忆（VOLATILE）、事件切分、Working Set、Affect Buffer |
| 4 | Neocortex | [v21_07_neocortex.md](v21_subsystems/v21_07_neocortex.md) | 慢记忆（CONSOLIDATED）、holder 子图族、五子区 |

**核心运行时子系统**（7 个）：

| # | 子系统 | 文档 | 职责 |
|---|---|---|---|
| 5 | Statement Bus | [v21_05_bus.md](v21_subsystems/v21_05_bus.md) | 写入入口、Validator、ConflictProbe、事件分发、幂等 |
| 6 | Cognizer Hub | [v21_08_cognizer.md](v21_subsystems/v21_08_cognizer.md) | 主体注册、KnowledgeFrontier、RelationEdge |
| 7 | ToM Engine | [v21_09_tom.md](v21_subsystems/v21_09_tom.md) | 二阶信念追踪、perspective_take、7 Mentalizing Primitives |
| 8 | Replay Scheduler | [v21_10_replay.md](v21_subsystems/v21_10_replay.md) | Online/Idle/Sleep 巩固，自适应遗忘 |
| 9 | Reconsolidation Engine | [v21_11_reconsolidation.md](v21_subsystems/v21_11_reconsolidation.md) | 被回忆即可塑，supersedes 链 |
| 10 | Prospective Loop | [v21_12_prospective.md](v21_subsystems/v21_12_prospective.md) | Trigger + Commitment 5 态 + ActionGuard（含 PolicyEngine 触发引擎） |
| 11 | Retrieval Planner | [v21_13_retrieval.md](v21_subsystems/v21_13_retrieval.md) | 9 Intent + 7 步规划 + Context Pack 8 标签 |

**横切子系统**（1 个）：

| # | 子系统 | 文档 | 职责 |
|---|---|---|---|
| 12 | Runtime Governance | [v21_05_governance.md](v21_subsystems/v21_05_governance.md) | RuntimeHealth 4 态、PipelineRun 账本、ScopedWorkGate 限流 |

**P1 编码必读顺序**：

1. 主文档 §3 数据本体（schema 与边）
2. v21_04_substrate.md（preflight 与索引）
3. v21_05_bus.md（写入路径与事件表）
4. v21_06_engramstore.md（证据底座）
5. v21_06_hippocampus.md（VOLATILE 入口）
6. v21_13_retrieval.md（basic_retrieve P1 闭环）
7. 主文档 §14 端到端场景流程
8. 主文档 §15 路线图（M0.0 到 M0.7）

P2+ 才需要读：v21_05_governance.md、v21_07_neocortex.md（CONSOLIDATED 落地）、v21_08_cognizer.md、v21_09_tom.md、v21_10_replay.md、v21_11_reconsolidation.md、v21_12_prospective.md。

---

## 3. 数据本体

本节冻结 P1 编码所需的全部数据结构。Statement 是核心原子，承载「谁、在何时、基于何证据、对谁、以何样态与极性、持有何判断」；Container 是 Persona / CommonGround / KnowledgeFrontier 的物化视图，由 Bus 重建；Engram 是不可静默覆盖的证据底座，被 Statement.evidence 指向；BusEvent 是跨子系统的事件信封，envelope 字段固定。本节是 schema 的权威来源，子系统文档中的字段须与此对齐。

### 3.1 本体总图

本体分两个视图：UML 类图说明继承与组合关系；ER 图说明持久化字段与索引边界。

#### 3.1.1 UML 类图

```
            ┌────────────────────────────────┐
            │           BaseEntity            │
            │  id        : UUID/ULID          │
            │  created_at: datetime           │
            └────────────────┬────────────────┘
                             │ 继承
        ┌──────────────┬─────┴──────┬────────────────┐
        │              │            │                │
        ▼              ▼            ▼                ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐    ┌──────────┐
  │ Cognizer │  │  Entity  │  │ Statement│    │ Container│
  │ 认知主体 │  │ 非认知物 │  │ 核心原子 │    │ 物化视图 │
  └────┬─────┘  └────┬─────┘  └────┬─────┘    └────┬─────┘
       │             │             │                │ 继承
       │             │             │      ┌─────────┼────────────┐
       │             │             │      ▼         ▼            ▼
       │             │             │  ┌───────┐ ┌──────────┐ ┌──────────┐
       │             │             │  │Persona│ │CommonGr. │ │KnowledgeF│
       │             │             │  └───┬───┘ └────┬─────┘ └────┬─────┘
       │             │             │      │          │            │
       │             │             │      │ cognizer │ parties    │ cognizer
       │             │             │      ▼          ▼            ▼
       │             │             │      └──────────┴────────────┘
       │             │             │                 │
       │             │     ┌───────┴──────┐          │
       │             │     │ 继承          │          │
       │             │     ▼   ▼   ▼   ▼              │
       │             │  Episo Comm Norm Skill          │
       │             │  dic   itme                     │
       │             │  Event nt                       │
       │             │                                 │
       │ holder      │ subject/object                  │
       │ ◄───────────┴─────────────────────────────────┘
       │             ▲
       │             │ subject/object
       │             └────────────────────────────┐
       │                                          │
       │ Statement.object 可递归引用 Statement   │
       │ (二阶 ToM 嵌套)                          │
       │                                          │
       └──────────────────────────────────────────┘

  Statement.evidence    ───►  Engram (聚合，0..N)
  Statement.source_spans───►  SourceSpanRef (value object)
  Statement.affect      ───►  AffectVector (value object)
  Statement.temporal_anchor──►TemporalAnchor (value object)

  BusEvent (独立，非 BaseEntity 后代)
     primary_id 指向 Statement.id / Container.id / Engram.id / run_id
```

继承与组合的硬约束：

- `Statement.subject` 接受 `CognizerRef | EntityRef`；不接受 `StatementRef`，避免主键不可规范化。
- `Statement.object` 接受 `Value | CognizerRef | EntityRef | StatementRef`；只在 object 位允许递归引用 Statement，构成二阶/三阶 ToM 嵌套。
- `Statement.holder` 强引用 Cognizer；Entity 不能作为 holder。
- `Container.cognizer`（Persona / KnowledgeFrontier）与 `Container.parties`（CommonGround）只接受 CognizerRef。
- `BusEvent` 不继承 BaseEntity；它是事件信封，生命周期由 outbox 管理，不参与 Statement / Engram 的版本链。
- `AffectVector` / `TemporalAnchor` / `SourceSpanRef` 是 value object，不独立持久化，随 Statement 一起序列化。

#### 3.1.2 ER 图（持久化关系）

```
  ┌─────────────────────────────────────────────────────────────┐
  │ cognizers                                                    │
  │  PK id (UUID5)                                              │
  │  tenant_id, kind, canonical_name, aliases[], external_id    │
  │  persona_ref, knowledge_frontier_ref, trust_priors          │
  │  permissions, created_at, last_seen_at                      │
  └──────────────────┬──────────────────────────────────────────┘
                     │ 1
                     │
                     │ N
  ┌──────────────────┴──────────────────────────────────────────┐
  │ statements                                                   │
  │  PK id (ULID)                                               │
  │  tenant_id, holder_id ──► cognizers.id                      │
  │  subject_kind, subject_id (poly: cognizer|entity)           │
  │  predicate (URI)                                            │
  │  object_value (JSON scalar) | object_ref_kind, object_ref_id│
  │  modality, polarity, confidence, confidence_history[]       │
  │  event_time, observed_at, inferred_at, valid_from, valid_to │
  │  evidence_ids[] ──► engrams.id                              │
  │  source_spans[] (embedded JSON)                             │
  │  temporal_anchor (embedded JSON, P1 可空)                   │
  │  derived_from[], derived_depth, perceived_by[], supersedes  │
  │  salience, affect (embedded), activation                    │
  │  last_accessed, access_count, last_replayed, replay_count   │
  │  consolidation_state, review_status, provenance             │
  │  nesting_depth, visibility, retention_policy                │
  │  canonical_object_hash, canonical_object_hash_version       │
  │                                                              │
  │  INDEX idx_statement_id_tenant (id, tenant_id)  -- P1 必备 │
  └──────────────────┬──────────────────────────────────────────┘
                     │ N
                     │ many-to-many via statement_edges
                     │ M
  ┌──────────────────┴──────────────────────────────────────────┐
  │ statement_edges                                              │
  │  PK (source_id, target_id, edge_kind)                       │
  │  edge_kind ∈ {supersedes, derived_from, may_overlap_with,   │
  │              believes_about, conflicts_with, evidence_for,  │
  │              evidence_against, observed_by, perceived_by}   │
  │  metadata (JSON)                                            │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │ entities                                                     │
  │  PK id (UUID5 from kind, canonical_name)                    │
  │  kind, canonical_name, aliases[], type_tags[]               │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │ engrams                                                      │
  │  PK id (UUID)                                               │
  │  source, source_kind, ingest_policy                         │
  │  adapter_name, adapter_version, ingest_mode                 │
  │  declared_transformations[], privacy_class, byte_preserving │
  │  content_ciphertext (nullable), redacted_content (nullable) │
  │  content_hash, retention_mode, key_ref (nullable)           │
  │  chunk_index, speaker_id, timestamp, source_time_range      │
  │  segment_map[] (embedded JSON, P3)                         │
  │  audit_trail[] (append-only)                                │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │ containers                                                   │
  │  PK id (UUID)                                               │
  │  kind ∈ {persona, common_ground, knowledge_frontier}        │
  │  source_refs[] ──► statements.id                            │
  │  materialized_payload (JSON)                                │
  │  version (整体 CAS, P1)                                   │
  │  dimension_versions (JSON, P3)                             │
  │  dimension_sequences (JSON, P3)                            │
  │  last_rebuilt_at, build_policy                              │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │ bus_events (outbox + 已派发表)                              │
  │  PK event_id                                                │
  │  event_type, primary_id, aggregate_id                       │
  │  outbox_sequence (单调递增)                                  │
  │  causation_chain[] (event_id 列表，长度 ≤3)                  │
  │  idempotency_key, payload (JSON), created_at                │
  │  INDEX (aggregate_id, outbox_sequence)                      │
  │  INDEX (event_type, created_at)                             │
  └─────────────────────────────────────────────────────────────┘
```

关系基数：

- `cognizers 1 : N statements`（holder 维度）
- `cognizers 1 : 1 persona Container`（cognizer 与 Persona 一一对应）
- `cognizers 1 : 1 knowledge_frontier Container`
- `engrams 1 : N statements`（一条 Engram 可被多条 Statement 引用为 evidence）
- `statements N : M statements`（通过 statement_edges 表达 supersedes / derived_from / 等边）

索引层次：

- **P1 主表必备**：`idx_statement_id_tenant(id, tenant_id)`，承接 `derived_from` 点查、SUPERSEDES 旧版定位、evidence erasure 传播；缺该索引则降级为全表扫描，Validator 拒绝启动。
- **P3 Projection Index**：7 类专用投影（idx_holder_state_time / idx_holder_subgraph / idx_entity_statement / idx_salience_hot / idx_commitment_due / idx_common_ground / idx_vector_payload），由 outbox subscriber 异步物化，详见 v21_04_substrate.md。

### 3.2 Cognizer 与 Entity

#### Cognizer：认知主体

```python
class Cognizer(BaseEntity):
    id: UUID                                # UUID5 from (kind, external_id)
    tenant_id: str = "default"              # 单租户固定 default；多租户写入后不可变
    kind: Literal["self","human","agent","group","role","external"]
    canonical_name: str                     # 规范名
    aliases: list[str]                      # "老张" / "Zhang Wei" / "user_42"
    external_id: str                        # 跨系统稳定 id
    persona: PersonaRef                     # 长期画像 Container
    knowledge_frontier: KnowledgeFrontierRef
    relations: list[RelationEdge]
    trust_priors: dict[CognizerId, float]   # 该主体对他人的先验信任
    permissions: AccessPolicy
    created_at: datetime
    last_seen_at: datetime
```

字段语义：

- `id` 由 `kind + external_id` 做 UUID5，跨数据源稳定；同一物理人在不同 kind 下产生不同 id。
- `tenant_id` 写入后不可变；任何 UPDATE 路径必须 fail-closed。
- `kind` 六值：`self`（系统宿主自身）/ `human`（用户）/ `agent`（其他 AI agent）/ `group`（群体）/ `role`（角色化主体）/ `external`（外部观察者）。
- `aliases` 与 `canonical_name` 解决跨数据源主体归一，由 Cognizer Hub NER 流程维护。
- `trust_priors` 是方向性的：`trust_priors[B]` 表示 **A 对 B** 的先验信任，不是 B 对 A 的信任，也不是系统对 A 的信任。

**group tenant 规则**：

- `kind="group"` 必须显式声明 `tenant_id`，不得从成员列表隐式推导。
- P1 单 tenant group 默认 `tenant_id="default"`；若发现跨 tenant 成员，写入必须拒绝或进入 `REVIEW_REQUESTED` 分支，不得静默降级为 default。
- P2+ 启用跨 tenant group 时，group 自身必须声明 `tenant_id="cross_tenant"` 或显式协议 tenant；以该 group 为 holder 的 Statement 默认 `review_status=REVIEW_REQUESTED`，直到策略或人工确认归属。

#### Entity：非认知主体

```python
class Entity(BaseEntity):
    id: UUID                                # UUID5 from (kind, canonical_name)
    kind: Literal["concept","artifact","place","event","organization","project","other"]
    canonical_name: str
    aliases: list[str]
    type_tags: list[str]
    created_at: datetime
```

Entity 是事物，不是认知主体：**没有 persona、没有 knowledge_frontier、没有 trust_priors**。它只承担 Statement 的 subject / object 角色，不能作为 holder。Entity 注册由 Cognizer Hub 的 NER + alias 归一负责，与 Cognizer 共享 alias 算法。

#### Ref 类型

| Ref | 指向 | 允许出现的字段位 |
|---|---|---|
| `CognizerRef` | `Cognizer.id` | `Statement.holder` / `Statement.subject` / `Statement.object` / `Container.cognizer` / `Container.parties` |
| `EntityRef` | `Entity.id` | `Statement.subject` / `Statement.object` |
| `StatementRef` | `Statement.id` | `Statement.object` / `Statement.derived_from[]` / `Statement.supersedes` / `Statement.perceived_by[]`（不允许出现在 `subject`） |
| `EngramRef` | `Engram.id` | `Statement.evidence[]` / `SourceSpanRef.engram_ref` |
| `PersonaRef` / `KnowledgeFrontierRef` | `Container.id` | `Cognizer.persona` / `Cognizer.knowledge_frontier` |

`subject` 不允许 `StatementRef` 的原因：subject 参与 `canonical_object_hash` 与 holder 子图索引的规范化键，若允许递归则键不可稳定。二阶 ToM 嵌套只在 object 位发生。

### 3.3 Statement 核心原子

```python
class Statement(BaseEntity):
    id: ULID
    # 主体维度
    tenant_id: str                          # 由 holder.tenant_id 派生，写入后不可变
    holder: CognizerRef                     # 谁持有
    holder_perspective: Perspective         # FIRST_PERSON | QUOTED | INFERRED | HEARSAY
    # 内容维度
    subject: CognizerRef | EntityRef
    predicate: PredicateURI                 # 受控核心集 + 可扩展
    object: Value | CognizerRef | EntityRef | StatementRef
    modality: Modality                      # 见 §3.4
    polarity: Literal["POS","NEG","UNKNOWN"]
    confidence: float                       # 0..1
    confidence_history: list[ConfidenceEvent] = []
    # 时间维度（5 种）
    event_time: Optional[TimeRange]         # 事件本身发生
    observed_at: datetime                   # 写入时观察到
    inferred_at: Optional[datetime]         # 系统推断时刻
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    # 证据归因
    evidence: list[EvidenceRef]             # 直接抽取必填；派生由 derived_from 追溯
    source_spans: list[SourceSpanRef]       # 直接抽取的 Engram 片段锚；派生作 supporting
    temporal_anchor: Optional[TemporalAnchor]
    derived_from: list[StatementRef]        # 直接前驱；派生 Statement 必填
    derived_depth: int = 0                  # 派生链深度缓存；根因 0
    perceived_by: list[CognizerRef]         # 信息可见性
    supersedes: Optional[StatementRef]
    # 类脑动力学
    salience: float
    affect: AffectVector
    activation: float
    last_accessed: datetime
    access_count: int
    last_replayed: Optional[datetime]
    replay_count: int = 0
    consolidation_state: ConsolidationState
    review_status: ReviewStatus
    provenance: StatementProvenance
    nesting_depth: int                      # 0=一阶, 1=二阶, 2=三阶
    # 治理
    visibility: VisibilityScope
    retention_policy: RetentionPolicy
    canonical_object_hash: str              # 写入时计算，ConflictProbe 主表索引使用
    canonical_object_hash_version: str = "v1"
```

字段逐项说明：

- `tenant_id` 由 `holder.tenant_id` 派生，写入后不可变；跨 tenant 派生规则见 §3.11。
- `holder_perspective` 四值：`FIRST_PERSON`（holder 第一人称陈述）/ `QUOTED`（直接引用）/ `INFERRED`（系统推断 holder 持有此判断）/ `HEARSAY`（道听途说）。
- `predicate` 是受控 URI；核心集由 Cognizer Hub 定义，扩展须经 Validator 注册，不允许 LLM 自造谓词。
- `modality + polarity` 正交：modality 表样态（信念/愿望/承诺/规范），polarity 表正反（POS/NEG/UNKNOWN）。
- `confidence` 0..1；初值由 Extractor 给出，受 adapter `declared_lossy` 影响。
- `confidence_history` append-only：mild correction 修改原 Statement 的 confidence 时追加 `ConfidenceEvent(old_value, ts, evidence_hash)`，provenance 不变。
- 5 类时间：`event_time` 事件本身；`observed_at` 写入时刻；`inferred_at` 系统推断时刻；`valid_from / valid_to` 事实有效期。
- `evidence` 与 `derived_from` 至少其一非空（Validator 校验）。
- `source_spans` 指向 Engram 内的片段位置；P1 最小只要 `engram_ref + chunk_index + observed_at + source_hash`。
- `temporal_anchor` P1 可空，序列化时按 `source_spans[0].observed_at` 推导；P3 多源时持久化。
- `derived_from` 是唯一持久化派生前驱；只记直接前驱，递归闭包由查询展开。
- `derived_depth` 写入规则：`derived_from=[]` 时为 0；否则为 `max(parent.derived_depth)+1`；与 derived_from 同事务原子写入。SUPERSEDES 版本链不计入派生深度。
- `nesting_depth` 默认 0；二阶 ToM 嵌套（object 是 Statement）时 +1。
- `canonical_object_hash` 在写入时由 `canonicalize_object(object, version=canonical_object_hash_version)` 计算，供 ConflictProbe 索引使用；版本升级 maintenance 超 14 天 emit `projection.upgrade_overdue`。

**Value 类型枚举与标准化**：

`Statement.object` 中的 `Value` 只允许简单标量。复杂结构必须拆成多条 Statement，或先注册为 Entity 后用 `EntityRef` 引用。

| Value 子类型 | 标准化规则 |
|---|---|
| `bool` | 序列化为 `"true"` / `"false"` |
| `int` | 十进制字符串，不带分组符 |
| `float` | 定点 6 位小数；需要更高精度时声明 `high_precision` profile |
| `str` | Unicode NFC；trim；连续空白折叠为单空格；有大小写语义文本执行 lowercase；不改变 CJK 字符 |
| `datetime` | 转 UTC ISO-8601，秒级精度 |
| `list` / `dict` | P1 拒收；列表拆为多条 Statement，结构对象建 Entity 承载 |

若 Value 类型不在上表，Validator 拒收并 emit `extraction.failed(schema_invalid)`；不得 JSON dump 兜底。

**证据锚分级规则**：

| provenance | evidence 要求 | source_spans 要求 | derived_from 要求 |
|---|---|---|---|
| `user_input` | ≥1 条 EngramRef，必填 | ≥1，必填（P1 chunk 级即可） | 可为空 |
| `tom_inferred` | 可为空 | 不强制；若有只作 supporting | ≥1，除非只返 transient context |
| `replay_derived` | 可为空 | 不强制；不得伪造直接 span | ≥1 |
| `reconsolidation_derived` | 可为空 | 不强制 | ≥1，必须指向被修正旧版 Statement |

总校验：`evidence` 与 `derived_from` 至少其一非空，且与 provenance 的允许组合一致；派生 Statement 不得把摘要、Container payload 或推断结果伪装成直接原文 span。高影响派生（norm / persona_trait / commitment correction）若没有可追溯 evidence chain，只能 `review_status=PENDING_REVIEW/REVIEW_REQUESTED`，不能自动 APPROVED。

**SourceSpanRef 与 TemporalAnchor**：

```python
class SourceSpanRef(BaseModel):
    engram_ref: EngramRef
    chunk_index: int
    span_start: Optional[int] = None         # P3；P1 可空
    span_end: Optional[int] = None
    segment_id: Optional[str] = None         # P3；如 resource#segment_3 / episode uuid
    source_role: Optional[Literal["user","assistant","tool","system","document"]]
    source_speaker: Optional[CognizerRef]
    observed_at: datetime                    # 该片段被观察/发生的时间
    source_hash: str                         # 片段级 hash，用于重抽/擦除传播

class TemporalAnchor(BaseModel):
    anchor_kind: Literal["source_span","episode","engram_record","message",
                         "document","derived_chain","system_now"]
    anchor_time: datetime
    timezone: Optional[str]
    confidence: float
    resolved_by: Literal["metadata","adapter","llm","fallback"]
```

时间规则：

- relative time（today / yesterday / recently / next month）须按 `TemporalAnchor.anchor_time` 解析，不得用系统当前时间兜底，除非 `anchor_kind=system_now` 且 `review_status=INFERRED_UNREVIEWED`。
- 多片段合并 Statement 若 span 的 `observed_at` 不一致，须保留多个 `source_spans`，并把 `event_time/valid_from/valid_to` 标为区间或进 `REVIEW_REQUESTED`。
- P1 最小实现只要求 `engram_ref/chunk_index/observed_at/source_hash`；`span_start/span_end/segment_id/segment_map` 在 P3 引入。

**二阶 ToM 嵌套示例**：

```
S1: holder=Alice, predicate=BELIEVES, polarity=POS, object=
    S2: holder=Bob, predicate=KNOWS, polarity=POS, object=
        S3: subject=Project_X, predicate=delayed, polarity=POS
```

读作：Alice 相信 Bob 知道项目 X 延期了。`nesting_depth` 在 S1 上为 2，S2 上为 1，S3 上为 0。

### 3.4 Modality

11 类样态：

```
BELIEVES   -- A 相信（可错）
KNOWS      -- A 知道（蕴含真；默认转 BELIEVES，慎用）
ASSUMES    -- A 假设（置信低）
DOUBTS     -- A 怀疑
DESIRES    -- A 想要
INTENDS    -- A 计划
COMMITS    -- A 承诺（进入 Prospective Loop）
PREFERS    -- A 偏好 X 胜过 Y
NORM_OUGHT -- 应当
NORM_FORBID-- 禁止
RECANTED   -- 撤回（供 supersedes 链）
```

polarity 与 modality 正交，三值 `POS / NEG / UNKNOWN`。组合示例：

| modality + polarity | 语义 |
|---|---|
| `BELIEVES + POS` | 相信 X 成立 |
| `BELIEVES + NEG` | 相信 X 不成立 |
| `DOUBTS + POS` | 怀疑 X 成立 |
| `KNOWS + UNKNOWN` | 知道某事但不知其值（如「知道有人偷了车，但不知是谁」） |
| `COMMITS + POS` | 承诺做 X |
| `NORM_FORBID + POS` | 禁止 X |
| `RECANTED + POS` | 撤回先前对 X 的肯定主张 |

`KNOWS` 默认转 `BELIEVES` 落库；只有当上游具备真值闭包（如形式验证、外部权威源）时才保留 `KNOWS`。运行时算子优先按 `BELIEVES` 处理，避免「知道蕴含真」与系统认知边界冲突。

### 3.5 ConsolidationState 状态机

实现层冻结为六个物理状态：`VOLATILE / REPLAYING_CONSOLIDATING / REPLAYING_RECONSOLIDATING / CONSOLIDATED / ARCHIVED / FORGOTTEN`。若 UI 需要五类生命周期展示，只能在展示层聚合两个 REPLAYING_*，不得污染 schema / 查询 / 事件表。

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
                       ┌──────────────────────┐                        │ │
                       │ REPLAYING_           │── confirm ─────────────┘ │
                       │ RECONSOLIDATING      │                          │
                       └──────────┬───────────┘                          │
                                  │                                      │
                                  │ contradict-severe                    │ decay
                                  │  (旧版进归档，新版另立)              │
                                  ▼                                      ▼
                                                                  ┌──────────┐
                                                                  │ ARCHIVED │◄── purge ──┐
                                                                  └────┬─────┘            │
                                                                       │                  │
                                                                       │ recall (已归档)  │
                                                                       │                  │
                                                                       └──► REPLAYING_RECONSOLIDATING
                                                                            (重新激活到再巩固通道)

                                  ┌──────────────────┐
                                  │ ARCHIVED         │── purge (合规/失效) ──► FORGOTTEN
                                  └──────────────────┘                       (EngramStore 按 retention_mode 处理)
```

状态语义：

- `VOLATILE`：刚写入海马分区，未巩固。
- `REPLAYING_CONSOLIDATING`：Replay Scheduler 选中（自 VOLATILE），首次巩固进新皮层语义层。
- `REPLAYING_RECONSOLIDATING`：Retrieval / ConflictProbe / 显式 edit 触发（自 CONSOLIDATED 或 ARCHIVED 召回），已有版本的再巩固/修正。
- `CONSOLIDATED`：已沉到新皮层语义层，长期可查。
- `ARCHIVED`：长期未召回，从热路径移除但保留索引可被召回回到 REPLAYING_RECONSOLIDATING。
- `FORGOTTEN`：Statement 从冷热检索路径全部移除；EngramStore 内容按 `retention_mode` 执行 redaction 或 crypto erasure。

**迁移表（11 条边，完整列举）**：

| # | 源态 | 目标态 | 触发条件 | 关闭者（close 窗口者） |
|---|---|---|---|---|
| T1 | `(create)` | VOLATILE | Bus.write 完成 Validator | 即时（无窗口） |
| T2 | VOLATILE | REPLAYING_CONSOLIDATING | Replay Scheduler 采样命中 | Replay Scheduler |
| T3 | REPLAYING_CONSOLIDATING | CONSOLIDATED | Replay 巩固原子操作 commit | Replay Scheduler |
| T4 | REPLAYING_CONSOLIDATING | VOLATILE | Replay 决策保留（证据不足） | Replay Scheduler |
| T5 | CONSOLIDATED | REPLAYING_RECONSOLIDATING | Retrieval 召回 / ConflictProbe 标冲突 / 显式 API | 可塑窗口超时（默认 30min，自适应 5min-6h） |
| T6 | REPLAYING_RECONSOLIDATING | CONSOLIDATED | reconsolidate confirm（支持/轻微反对） | 可塑窗口超时 |
| T7 | REPLAYING_RECONSOLIDATING | ARCHIVED | reconsolidate contradict-severe（旧版作废，新版另立） | 可塑窗口超时 |
| T8 | CONSOLIDATED | ARCHIVED | decay 公式判定（S(t)<0.05）且不在 active_grounded | Replay Scheduler 周期触发 |
| T9 | ARCHIVED | REPLAYING_RECONSOLIDATING | 归档 stmt 被召回 + salience>θ_revive 或 audit | 可塑窗口超时 |
| T10 | ARCHIVED | FORGOTTEN | 显式 purge（合规/法务） | 即时 |
| T11 | CONSOLIDATED / ARCHIVED | FORGOTTEN | `purge_compliance` 路径 | 即时 |

**不变量与 fallback**：

- **振荡上限**：同 Statement `replay_count >= MAX_CONSOLIDATION_ATTEMPTS`（默认 5）时，Replay Scheduler 不再选中其退回 VOLATILE，强制转 CONSOLIDATED 且 `review_status=PENDING_REVIEW`，emit `statement.consolidation_forced(reason="max_attempts")`。防单条高 salience 但证据不足的 Statement 永久占用 Replay 采样预算。
- **VOLATILE TTL**：进入 VOLATILE 超 `T_max_volatile`（默认 7 天）且不在 Affect Buffer，定时清理任务自动 decay 至 ARCHIVED，emit `statement.archived(reason="volatile_ttl_exceeded")`。兜底从未被 Replay 选中的低 salience 长尾。
- **REPLAYING_CONSOLIDATING fallback timeout**：进入该状态后超 `T_replay_consolidating_timeout` 自动回退 VOLATILE，emit `statement.replay_timeout`。RuntimeHealth=READY 时默认 1 小时，DEGRADED/DRAINING 时默认 4 小时。
- **未结清 Commitment 保护**：`commitment.active_holding` 事件 Consumer（decay scheduler）在 in-memory set 中持有相关 stmt_id，decay 候选选取时 O(1) 排除。terminal 态时 emit `commitment.released` 从 set 移除。
- **T5/T8 并发互斥**：CONSOLIDATED Statement 同时被 Retrieval 召回（T5）与 Replay decay（T8）触发时，decay 不再同步写库，改 emit `statement.decay_candidate` 经事件总线；outbox dispatcher 对同 stmt_id 顺序串行处理。后到事件读到 state 已变即幂等跳过。

**迁移例外**：

- `CONSOLIDATED → ARCHIVED` decay 路径**不适用于 CommonGround 中条目**：已 grounded 共识衰减极慢，decay 公式中 `is_grounded` 因子放大 S0。
- 任何 Commitment 状态非 FULFILLED/WITHDRAWN 时**不允许进入 ARCHIVED**（承诺必须留在热路径直到结清）。
- ARCHIVED 召回路径：仅当原 stmt 的 `salience > θ_revive` 或 audit 显式触发，普通低 salience 召回不重新激活。

### 3.6 五类视图与 Statement 子类

#### 五类视图（基于 modality + time）

五类记忆是 Statement 上的纯查询视图，不是物理分表。同一 Statement 可同时落在多个视图。

```
EpisodicView   = WHERE event_time IS NOT NULL
                    OR type = "EpisodicEvent"
                    OR EXISTS edge(kind="OBSERVED_BY")
                 # 不限 consolidation_state；Episodic vs Semantic 由「绑时空」区分
SemanticView   = WHERE modality IN (KNOWS, BELIEVES)
                       AND event_time IS NULL
                       AND consolidation_state IN (CONSOLIDATED, ARCHIVED)
                       AND |evidence| >= N
                 # 时空脱钩 + 多证据 + 已巩固
ProceduralView = WHERE type = "Skill"
                       AND consolidation_state = CONSOLIDATED
                       AND linked ProcedureSpec
NormativeView  = WHERE modality IN (NORM_OUGHT, NORM_FORBID)
IntentionalView= WHERE modality IN (DESIRES, INTENDS, COMMITS)
                       AND valid_from > now()    # ProspectiveLoop 子视图
WorkingView    = WHERE activation > θ_w
                       AND last_accessed within session
```

视图组合举例：「Alice 上周答应给我看代码」刚说完时是 Episodic + Intentional；Alice 真看了之后 Commitment 状态 → fulfilled，Episode 仍存（无论 CONSOLIDATED 还是 ARCHIVED）；若反复发生类似承诺，可凝结出 Semantic 命题「Alice 习惯口头答应但需提醒」，原 Episode 不灭。

#### Statement 子类

```python
class EpisodicEvent(Statement):
    modality: Literal["BELIEVES"] = "BELIEVES"
    participants: list[CognizerRef]
    location: Optional[Place]
    raw_engram_ref: EngramRef
    boundary_score: float                  # EM-LLM 惊奇度

class Commitment(Statement):
    modality: Literal["COMMITS"] = "COMMITS"
    principal: CognizerRef                 # 承诺者
    beneficiary: CognizerRef               # 受益人
    trigger: Trigger                       # 触发规约，见 v21_12_prospective.md
    deadline: Optional[datetime]
    state: Literal["ACTIVE","FULFILLED","BROKEN","RENEGOTIATED","WITHDRAWN"]

class Norm(Statement):
    modality: Literal["NORM_OUGHT", "NORM_FORBID"]
    scope: NormScope                       # group / 1-1 / role
    deontic_strength: float
    enforcement_history: list[EpisodicEventRef]

class Skill(Statement):
    modality: Literal["KNOWS"] = "KNOWS"
    procedure: ProcedureSpec
    success_pattern: list[CaseRef]
    maturity: float                        # 熟练度 0..1
```

子类只是 Statement 的特化，不脱离基类字段；持久化时与基础 Statement 同表，type 列区分。子类特有字段（participants / trigger / deontic_strength / procedure 等）作为可空列或独立扩展表，由 Substrate Adapter 决定布局。

### 3.7 Container（Persona / CommonGround / KnowledgeFrontier）

Container 基类是物化视图，**不是 Statement**。它装载 StatementRefs 与派生 payload，由 `Bus.rebuild_container` 重建，权威事实仍在 Statement 图中。

```python
class Container(BaseEntity):
    id: UUID
    kind: Literal["persona","common_ground","knowledge_frontier"]
    source_refs: list[StatementRef]
    materialized_payload: dict
    version: int                            # 整体 CAS（P1）
    dimension_versions: dict[str, int] = {} # P3
    dimension_sequences: dict[str, int] = {} # P3；每维度已消费的最高 outbox sequence
    last_rebuilt_at: datetime
    build_policy: Literal["on_event","sleep","manual"]
```

#### Persona

```python
class Persona(Container):
    cognizer: CognizerRef
    traits: dict[str, TraitValue]           # OCEAN / 自定义
    preferences: list[StatementRef]
    competencies: list[StatementRef]
    values: list[StatementRef]
    self_model_anchor: list[StatementRef]   # 该主体对自己的陈述
    profile_anchor: list[StatementRef]      # 他人对该主体的陈述
    relationship_styles: dict[CognizerRef, FiskeMode]
```

#### CommonGround

```python
class CommonGround(Container):
    parties: tuple[CognizerRef, ...]        # 支持 N 元
    grounded: list[StatementRef]            # 双方都知道双方都知道
    asserted_unack: list[StatementRef]      # 一方说了对方未确认
    suspected_diverge: list[StatementRef]   # 怀疑对方实际相信不同
    establishment_evidence: list[EpisodicEventRef]
```

#### KnowledgeFrontier

```python
class KnowledgeFrontier(Container):
    cognizer: CognizerRef
    accessible_sources: list[SourceRef]     # 该主体可访问的信息源
    membership: list[GroupRef]              # 所属群体
    presence_log: list[EpisodicEventRef]    # 在场/缺席记录
    explicit_told: list[StatementRef]       # 显式被告知
    explicit_not_told: list[StatementRef]   # 显式未被告知
```

#### dimension key 表

| Container 类型 | 合法 dimension keys |
|---|---|
| `Persona` | `traits / preferences / competencies / values / self_model_anchor / profile_anchor / relationship_styles` |
| `CommonGround` | `grounded / asserted_unack / suspected_diverge / establishment_evidence` |
| `KnowledgeFrontier` | `accessible_sources / membership / presence_log / explicit_told / explicit_not_told` |

`Bus.rebuild_container(container_id, dimension, expected_version, source_refs)` 的 `dimension` 参数必须属于上表合法 key。未声明 dimension 必须拒绝写入并 emit `container.dimension_invalid`。P1 用整体 rebuild + 单 `version` CAS；P3 启用 `dimension_versions` 细粒度 CAS，`expected_version` 表示对应 dimension version。

Container 不是事实源：Retrieval 可读 Container，但若整体 version 或 P3 对应 `dimension_sequences[dimension]` 落后于相关 Statement outbox sequence，必须对该 dimension 降级直接查 Statement 主表，并异步触发修复。

### 3.8 EngramStore 与证据

任何 Statement 的 `evidence` 必须指向 EngramStore 中的原始证据片段。Engram 的 id / source / hash / audit log append-only，即使 LLM 抽取错误也能追溯；但当原文包含个人数据或敏感信息时，FORGOTTEN 不能只是「检索隐藏」，须按 `retention_mode` 执行内容侧处理。

#### EngramRetentionMode 四值

| `retention_mode` | 内容策略 | 适用场景 | FORGOTTEN 后行为 |
|---|---|---|---|
| `legal_hold` | 保留密文与密钥，禁止 purge | 法务保全 / 审计冻结 | 不可删除，但所有访问需审计 |
| `audit_retain` | 保留密文，按 retention_policy 到期处理 | 普通可审计日志 | 到期后转 `crypto_erasure` |
| `redacted_retain` | 原文替换为脱敏文本，保留 hash | 用户撤回但需解释历史决策 | 仅可恢复脱敏片段 |
| `crypto_erasure` | 销毁内容密钥，保留不可逆 hash / 元数据 | 删除权 / 敏感信息 purge | 内容不可恢复 |

#### SourceKind 枚举

```
user_input         -- 用户直接输入
external_doc       -- 外部文档（PDF / 网页 / 邮件 / 转录）
tool_observation   -- 工具调用产生的外部世界观测
system_internal    -- 系统自身 prompt/trace/health 事件
observer_agent     -- 观察者 agent 输出（自己的 agent run）
replay_output      -- Replay/Reconsolidation 派生输出
```

#### IngestPolicy 枚举

```
STORE                  -- 写完整 Engram
NO_STORE               -- 不写 Engram，只写 audit counter
STORE_METADATA_ONLY    -- 写 metadata，不写 verbatim
REQUIRE_REVIEW         -- 默认 NO_STORE，待显式 allowlist 提升
```

`system_internal / observer_agent / replay_output` 默认 `NO_STORE`，防止 RetrievalReceipt、PipelineRun trace、Extractor raw prompt 等污染用户画像。`tool_observation` 默认 `STORE_METADATA_ONLY`，仅当工具输出是用户可见事实或外部世界观测时升级为 `STORE`。

#### Engram 完整 schema

```python
class Engram:
    id: UUID
    source: SourceRef
    source_kind: SourceKind
    ingest_policy: IngestPolicy
    adapter_name: Optional[str]
    adapter_version: Optional[str]
    ingest_mode: Literal["chunked_content","whole_record","metadata_only"]
    declared_transformations: list[str]     # 空集才可声明 byte_preserving
    privacy_class: Literal["public","internal","personal","sensitive","regulated"]
    byte_preserving: bool
    content_ciphertext: Optional[bytes]     # 可为 None：crypto_erasure 后不可恢复
    redacted_content: Optional[str]         # redacted_retain 使用
    content_hash: str                       # sha256/verifiable hash，永远保留
    retention_mode: EngramRetentionMode
    key_ref: Optional[KeyRef]               # 内容密钥引用；crypto_erasure 后销毁
    chunk_index: int
    speaker: Optional[CognizerRef]
    timestamp: datetime
    source_time_range: Optional[TimeRange]   # 源记录覆盖的真实时间范围
    segment_map: list[SourceSegment] = []    # P3；P1 可空
    audit_trail: list[AuditEventRef]         # append-only
```

#### SourceSegment（P3）

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

SourceAdapter 若执行分块、转录、PDF 解析、episode 合并或 multimodal segment 提取，必须输出 `segment_map`。P1 `direct_api` adapter 可不输出 `segment_map`，Extractor 以 `(engram_ref, chunk_index, Engram.timestamp/content_hash)` 构造最小 `SourceSpanRef`。引用 `segment_id/span_start/span_end` 的 Statement 须在 `segment_map` 中找到对应片段；不能由 LLM 自造 offset / episode id。

#### crypto_erasure 反向传播

- `Statement.evidence` 引用不删除，但对应 `EvidenceRef.status` 置为 `ERASED`，保留 `content_hash` 与 `erased_at`。
- 直接由该 Engram 抽取且**没有其他未擦除 evidence**的 Statement 进入 `FORGOTTEN`。
- 直接 `derived_from` 依赖上述 Statement 且**没有独立 evidence**的派生 Statement 进入 `REVIEW_REQUESTED` 或 `FORGOTTEN`（按影响级别）。默认**只传播一层**，避免一次擦除误删整条认知链。
- 有独立未擦除 evidence 的 Statement 保留，但 confidence 下调并在 Context Pack 中标注「部分证据已擦除」。
- 传播过程经 Compliance Engine 事务写入 outbox：`evidence.erased` → `statement.forgotten` / `statement.review_requested`。

多 Cognizer 可共享同一 Engram，共享记录的 purge 采用「最严格访问者 wins」：任一主体触发 `crypto_erasure` 时，共享记录必须拆分引用或整体加密擦除，不能继续向其他 holder 暴露原文。

### 3.9 AffectVector

```python
class AffectVector(BaseModel):
    valence: float    # -1..+1   情感效价
    arousal: float    #  0..1    唤起度
    dominance: float  # -1..+1   主导感（VAD 三轴）
    novelty: float    #  0..1    新奇度
    stakes: float     #  0..1    利害度
```

salience 计算公式：

```
salience = (0.4 + 0.6 * |valence|)
         × (0.4 + 0.6 * arousal)
         × (0.3 + 0.7 * novelty)
         × (0.3 + 0.7 * stakes)
         × (0.6 + 0.4 * surprise_decay)    # EM-LLM 风格惊奇度
```

salience 在三处生效：

1. **写入打分**：VOLATILE 入队优先级（高 salience 优先消费）。
2. **重放采样**：Replay Scheduler 权重（高 salience 优先采样）。
3. **检索重排**：Reranker 乘子（高 salience Statement 排序前置）。

AffectVector 是 value object，随 Statement 持久化为嵌入 JSON 字段，不独立成表。

### 3.10 BusEvent 信封

BusEvent 是 outbox 事件信封，独立于 BaseEntity 体系。所有跨子系统通信经此投递。

```python
class BusEvent(BaseModel):
    event_id: UUID
    event_type: str                          # 见下方枚举
    primary_id: str                          # 业务幂等键主标识
    aggregate_id: str                        # 同 aggregate 顺序投递
    outbox_sequence: int                     # 单调递增
    causation_chain: list[UUID]              # 长度 ≤3
    idempotency_key: str                     # 重复投递去重
    payload: dict
    created_at: datetime
    version: str = "v1"
```

**primary_id 规则表**：

| 事件族 | primary_id | aggregate_id |
|---|---|---|
| `statement.*` | `stmt_id` | `stmt_id` |
| `belief.conflict` | `canonical_conflict_key` | `conflict_window_id` 或 `canonical_conflict_key` |
| `statement.superseded/corrected` | `new_stmt_id` | `supersedes_root_id` |
| `container.*` | `container_id` | `container_id:dimension` |
| `evidence.*` | `engram_ref` | `engram_ref` |
| `pipeline.*` | `run_id` | `run_id` |
| `commitment.*` | `commitment_id` | `commitment_id` |

`belief.conflict` 可能早于某些相关 `statement.*` 事件到达 subscriber；消费冲突事件时必须按 stmt_id 补查主表，以主表事务状态为准，不能只相信事件到达顺序。

**完整事件枚举（按 P 阶段分组）**：

P1 事件（必须上线）：

| 事件 | Producer | Consumer |
|---|---|---|
| `evidence.appended` | Bus.append_evidence | Extractor / Cognizer Hub / Audit |
| `evidence.redacted` | Compliance Engine | Retrieval index / Audit |
| `evidence.erased` | Compliance Engine / KMS | Retrieval index / Audit |
| `extraction.failed` | Extractor / Validator | Extractor retry / Audit / Review queue |
| `extraction.retry_scheduled` | Extractor retry policy | Extractor |
| `extraction.dead_lettered` | Extractor retry policy | Audit / Review queue |
| `extraction.noop` | Extractor | Audit / PipelineRun |
| `statement.written` | Bus（写完 Hippocampus 后） | Replay / ToM / Prospective / Affect Buffer |
| `statement.derived` | Bus（写完 Neocortex 后） | ToM / Container Builder |
| `runtime.health_changed` | RuntimeHealth monitor | Ops / Scheduler gates |
| `pipeline.run_started` | PipelineRun ledger | Ops / Replay / Projection / Audit |
| `pipeline.run_completed` | PipelineRun ledger | Ops / Replay / Projection / Audit |
| `pipeline.run_failed` | PipelineRun ledger | Ops / Replay / Projection / Audit |
| `pipeline.run_cancelled` | PipelineRun ledger | Ops / Replay / Projection / Audit |
| `system.delivery_failed` | Outbox dispatcher | Ops / Audit |
| `system.runaway` | Bus | Ops + Audit |
| `projection.upgrade_overdue` | maintenance rebuild monitor | Ops |

P2 事件：

| 事件 | Producer | Consumer |
|---|---|---|
| `cognizer.observed` | Bus（写入消息时） | ToM（更新可见性） |
| `statement.review_requested` | Validator / Compliance / Reconsolidation | Review queue / Retrieval index / Audit |

P2 事件：

| 事件 | Producer | Consumer |
|---|---|---|
| `statement.recalled` | Retrieval Planner | Reconsolidation（异步开窗判定） |
| `statement.consolidated` | Replay Scheduler / Reconsolidation Engine | ToM（更新 Persona） |
| `statement.archived` | Replay (decay) / Reconsolidation (severe) | Retrieval index（降权） |
| `statement.corrected` | Reconsolidation transaction | ToM / Container Builder / Retrieval index |
| `statement.superseded` | Reconsolidation transaction | ToM / Container Builder |
| `statement.references_existing` | Bus.write 检测 derived_from 含 CONSOLIDATED/ARCHIVED | Reconsolidation Engine |
| `statement.decay_candidate` | Replay decay | Bus dispatcher（per-stmt 串行） |
| `statement.consolidation_forced` | Replay Scheduler | Audit |
| `statement.replay_timeout` | RuntimeHealth monitor | Audit |
| `belief.conflict` | ConflictProbe | Reconsolidation（优先重放仲裁） |
| `container.rebuilt` | Bus.rebuild_container | Working Set / Retrieval cache |
| `container.dimension_invalid` | Bus.rebuild_container | Audit / Ops |
| `projection.rebuild_started` | Projection worker | Retrieval / RuntimeHealth |
| `projection.rebuild_completed` | Projection worker | Retrieval / RuntimeHealth |
| `projection.rebuild_failed` | Projection worker | Retrieval / RuntimeHealth |

> `statement.consolidated` 是生命周期信号，不是内容源事件。Replay Scheduler 与 Reconsolidation Engine 都可能发出它；`statement.derived` 才表示新内容被派生或重写。

P3 事件：

| 事件 | Producer | Consumer |
|---|---|---|
| `commitment.fire` | PolicyEngine（经 Bus） | Prospective（下发提醒） |
| `commitment.fulfilled` | Prospective（检测 fulfilled_by） | Reconsolidation / Cognizer Hub（↑ trust_priors） |
| `commitment.broken` | PolicyEngine（deadline 过） | Reconsolidation / Cognizer Hub（↓ trust_priors） |
| `commitment.renegotiated` | Validator（检测 RECANT + 重新 COMMIT） | Prospective / ToM |
| `commitment.withdrawn` | Validator / Prospective | Prospective / Retrieval index / Container Builder |
| `commitment.active_holding` | PolicyEngine 转 ACTIVE 时 | decay scheduler |
| `commitment.released` | PolicyEngine 转 FULFILLED/WITHDRAWN 时 | decay scheduler |
| `norm.violated` | NormChecker | Affect Buffer（高 salience） / Audit |

P3 事件：

| 事件 | Producer | Consumer |
|---|---|---|
| `action.policy_blocked` | ActionPolicyGraph / PolicyEngine | Audit / Ops / Prospective |

**idempotency_key 公式**：

```
idempotency_key = hash(
    event_type,
    aggregate_id,
    canonical_key,
    causation_chain_root,
    window_bucket
)
```

Bus outbox 与 Subscriber inbox 都持久化该 key，重复投递直接 ACK。

**window_bucket 默认值表**：

| 事件 | window_bucket |
|---|---|
| `commitment.fire` | 24h |
| `belief.conflict` | 10s |
| `statement.references_existing` | 10s |
| `statement.recalled` | 2s |
| 其他（默认一次性业务键） | 不分桶，使用 `(event_type, primary_id, target_state/dimension_version/outbox_sequence)` |

**causation_chain 深度上限**：3。超过即拒绝派生事件并 emit `system.runaway`，payload 含 `[chain_root, depth, source_event_id]`。

### 3.11 Provenance 与 ReviewStatus

所有 Statement 按生成来源分四类，Bus 处理规则不同：

| provenance | 默认入态 | 默认 review_status | emit 事件 | 是否被 Replay 重新采样 |
|---|---|---|---|---|
| `user_input` | VOLATILE | APPROVED 或低置信时 REVIEW_REQUESTED | `statement.written` | 是（默认） |
| `replay_derived` | CONSOLIDATED（正式或 candidate index） | APPROVED / PENDING_REVIEW | `statement.derived`（不发 written） | 否（避免循环） |
| `tom_inferred` | VOLATILE | INFERRED_UNREVIEWED | `statement.written`（×0.25 Replay 权重） | 是（降权） |
| `reconsolidation_derived` | CONSOLIDATED（原子替换路径） | APPROVED 或 REVIEW_REQUESTED | `statement.corrected`（不发 written） | 否（事务关闭） |

```python
class StatementProvenance(str, Enum):
    USER_INPUT = "user_input"
    REPLAY_DERIVED = "replay_derived"
    TOM_INFERRED = "tom_inferred"
    RECONSOLIDATION_DERIVED = "reconsolidation_derived"

class ReviewStatus(str, Enum):
    APPROVED = "approved"                   # 可进入正常检索 / 巩固
    PENDING_REVIEW = "pending_review"       # 派生候选，待规则 / 人工确认
    INFERRED_UNREVIEWED = "inferred_unreviewed"  # ToM 推断未复核
    REVIEW_REQUESTED = "review_requested"   # 低置信 / 敏感 / 高影响
    REJECTED = "rejected"                   # 保留审计，不进入热检索
```

`replay_derived` 不无条件等于「已稳定事实」。`compress` 类摘要可直接 APPROVED + CONSOLIDATED；`induce_norm / forge_skill / persona_trait` 类高影响派生默认 PENDING_REVIEW，在 Neocortex 中只作候选索引，不进入普通 Retrieval 的 FACT/NORM/SKILL 输出，直到 confirm 后转 APPROVED。

**provenance 不变量**：

- Statement 的 `provenance` 在 `Bus.write` 首次提交时确定，写入后不可变。
- 后续 confidence 调整、review_status 提升/降级、access_count 累加、consolidation_state 迁移、evidence erasure 标记，均不改原 Statement 的 provenance。
- 只有产生新 Statement（fork + `SUPERSEDES`）时才出现新 provenance：Replay compress/abstract 产物为 `replay_derived`；Reconsolidation severe path 新版为 `reconsolidation_derived`；ToM 自动持久化推断为 `tom_inferred`；人工 review 提升不产生新 Statement，原 provenance 保留。

**Replay 订阅规则**：

- Replay 仅订阅 `statement.written`，**不订阅 `statement.derived`**。
- Replay 不订阅 `statement.corrected`。
- 因此 Replay 自身产出的 `replay_derived` 与 Reconsolidation 产出的 `reconsolidation_derived` 不会触发新一轮 Replay，断开派生 → Replay → Container 循环。
- `tom_inferred` 虽 emit `statement.written`，但 Replay 采样权重乘以 `tom_inferred_factor=0.25`；按 `derived_from` 递归展开的派生链深度 ≥3，或 `causation_chain` 已含 ToM→Replay→Container 时，ToM Engine 暂停对该链路增量推断，只保留显式查询时即时 perspective_take。

### 3.12 关键边类型（社会图谱）

边在持久化层是 `statement_edges` 表（多对多），含 `source_id / target_id / edge_kind / metadata`。

| 边 | 含义 | 语义 |
|---|---|---|
| `BELIEVES_ABOUT` | 主体 → 关于另一主体的信念集 | Alice → 对 Bob 的画像锚 |
| `TRUSTS` | 加权信任，带情境 | Alice -[trust=0.8, ctx=tech]→ Bob |
| `COMMITTED_TO` | 主体 → 承诺（指 Commitment） | Bob -[deadline=...]→ S(ship_v2) |
| `CONFLICTS_WITH` | 两 Statement 矛盾 | S1 ⨯ S2，带 conflict_type |
| `EVIDENCE_FOR` | 证据支持 Statement | Episode → Statement |
| `EVIDENCE_AGAINST` | 证据反对 Statement | Episode → Statement |
| `SHARED_GROUND` | N 主体共享的共同知识 | {A, B, C} → fact F |
| `OBSERVED_BY` | Episode → 观察者集合 | E → {A, B} |
| `PERCEIVED_BY` | Statement → 感知者集合 | 与 `Statement.perceived_by` 字段对偶 |
| `NORM_OF` | Group → Norm | Team -[since=...]→ norm_X |
| `INTENT_OF` | Cognizer → 当前 / 历史意图 | Alice -[active]→ goal_Y |
| `MAY_OVERLAP_WITH` | 模式分离软边 | 高相似但保留差异；防止 ConflictProbe 假阳性 |
| `SUPERSEDES` | 版本链 | S_new -[supersedes]→ S_old |
| `derived_from` | 派生前驱 | S_child -[derived_from]→ S_parent；只记直接前驱 |

边的写入规则：

- 所有边变更经 `Bus.write` 原子提交，与 Statement 主表同事务。
- `SUPERSEDES` 形成版本链；版本链长度 `≤3` 时允许自动 RENEGOTIATED Commitment 迁移，超出长度拒绝。
- `derived_from` 只记直接前驱（深度 1）；递归闭包由查询展开，不持久化。
- `MAY_OVERLAP_WITH` 是软边，由模式分离阶段（Replay）写入，标记两条高相似但被保留差异的 Statement；ConflictProbe 看到 `MAY_OVERLAP_WITH` 时不再标 `CONFLICTS_WITH`。
- `BELIEVES_ABOUT` / `SHARED_GROUND` 由 Container Builder 在 `rebuild_container` 内同步刷新；外部不得直接写。

边的索引：

- `(source_id, edge_kind)` 与 `(target_id, edge_kind)` 双向索引，支撑 holder 子图扇出与反向溯源。
- `edge_kind = supersedes` 单独维护 `supersedes_root_id` 索引，加速版本链遍历。
- `edge_kind = derived_from` 维护 `derived_depth` 缓存的反向验证：从 root 沿 `derived_from` 边重算深度时，与 Statement 主表 `derived_depth` 字段一致；不一致即标 `projection.rebuild_failed(derived_depth_mismatch)`。

---
## 14. 端到端场景流程

本节用 5 个典型场景展示子系统如何协同。每个场景含：（1）输入事件，（2）ASCII 时序图，（3）经过的子系统与事件列表，（4）输出。

---

### 14.1 场景 A：写入路径（Alice 宣布 Bob 不再负责 auth）

**输入：** Alice 在群聊中说"Bob 不再负责 auth，现在 Carol 接手"。

```
App   Bus   EngramStore   Extractor   Validator   ConflictProbe   Hippocampus   ToM   Reconsolidation
 │     │        │             │           │             │              │          │          │
 │─append_evidence──────────────────────────────────────────────────────────────────────────►
 │     │    put Engram                                                                        │
 │     │─►evidence.appended──────────────────────────────────────────────────────────────────│
 │     │        │         extract(LLM call)                                                   │
 │     │        │◄────── 4 条 Statement（含 2 条二阶 ToM 嵌套）                                │
 │     │        │             │                                                               │
 │     │◄── Bus.write × 4 ───┘                                                               │
 │     │─►Validator.check───────────────►                                                    │
 │     │        │           ◄─── 通过 ───┘                                                   │
 │     │─►ConflictProbe.scan──────────────────────────────►                                  │
 │     │        │                       ◄─── 命中：旧 stmt "Bob 负责 auth" 冲突 ──────────────│
 │     │─► Hippocampus VOLATILE upsert──────────────────────────────────────────────────►    │
 │     │─► outbox: statement.written × 4                                                     │
 │     │        │                                              Affect Buffer 入队（高 salience）
 │     │        │                                              ToM 更新 CommonGround          │
 │     │        │                                              belief.conflict ──────────────►│
 │     │        │                                                                          开窗（旧 stmt）
 │     │        │                                                                          severe contradict
 │     │        │                                                                          → 新版写入
 │     │        │                                                                          → 旧版 ARCHIVED
 │     │        │                                                                          → SUPERSEDES 边
 │     │        │                                                                          → outbox: corrected / archived / superseded
```

**抽取结果（4 条 Statement）：**

| ID | holder | subject | pred | obj | mod | pol |
|----|--------|---------|------|-----|-----|-----|
| S1 | self | Bob | responsible\_for | auth | BELIEVES | NEG |
| S2 | self | Carol | responsible\_for | auth | BELIEVES | POS |
| S3 | self | Alice | BELIEVES | ⟨S2⟩ | — | POS（二阶） |
| S4 | Alice | Bob | responsible\_for | auth | BELIEVES | NEG |

**经过子系统（按序）：**

1. Bus.append\_evidence → EngramStore
2. Extractor（LLM call，XML strict）
3. Bus.write × 4
4. Validator → ConflictProbe
5. Hippocampus VOLATILE upsert
6. Affect Buffer 入队
7. ToM Engine：CommonGround 更新（perceived\_by 全员在场 → Bob 标"应已知"）
8. Reconsolidation Engine：旧 stmt 开可塑窗口，severe contradict 路径

**事件顺序：**

```
evidence.appended
  → statement.written × 4
  → belief.conflict
  → statement.corrected + statement.archived + statement.superseded
```

**输出：** 4 条 VOLATILE Statement；旧"Bob 负责 auth"Statement 状态轨迹：ACTIVE → ARCHIVED，新版写入并附 SUPERSEDES 边。

---

### 14.2 场景 B：检索路径（"Bob 还负责 auth 吗？"）

**输入：** 用户 query "Bob 还负责 auth 吗？"，intent=FACT\_LOOKUP。

```
App   Retrieval Planner   Neocortex   EngramStore   ToM   Bus
 │           │                │            │          │     │
 │─query────►│                                              │
 │           │ parse: subject=Bob, pred=responsible_for, obj=auth
 │           │ mask: querier=user（无遮蔽）
 │           │ plan: FACT_LOOKUP 路径
 │           │─► Neocortex(holder=self).query ────────────►│
 │           │        ◄─── 命中 supersedes 链 ──────────────│
 │           │─► EngramStore time-window ──────────────────►│
 │           │        ◄─── Alice 原话片段引用 ───────────────│
 │           │─► ToM.shared_with([self,user]) 检查共识 ─────►│
 │           │        ◄─── CommonGround 无此事 → 主动 grounding
 │           │ fuse + rerank（valid_to 近 + supersedes → 已变更）
 │           │ Context Pack Builder
 │◄──── Context Pack ─────────────────────────────────────────
 │           │─► emit statement.recalled × N（fire-and-forget）►│
 │           │                                           → Reconsolidation 异步判定窗口
```

**Context Pack 内容：**

```
[FACT]    Bob 已不再负责 auth，现由 Carol 接手（Alice 群聊宣布，evidence: EngramStore:abc123）
[HISTORY] Bob 此前负责该模块约 8 个月，如需历史设计讨论可拉取
[COMMON]  这是首次告知你，需要确认你已知悉吗？
```

**经过子系统：** Retrieval Planner → Neocortex → EngramStore → ToM（perspective\_take） → Context Pack Builder → Bus emit

**事件：** statement.recalled × N（每条召回 Statement 一条）

**输出：** Context Pack 3 标签，[FACT] 含 EngramStore 证据片段引用。

---

### 14.3 场景 C：二阶 ToM（"Bob 知道这事吗？"）

**输入：** query intent=META\_BELIEF，target=Bob，about=⟨Carol 现负责 auth⟩。

```
App   Retrieval Planner   ToM(Mentalizing)   KnowledgeFrontier   Neocortex   Bus
 │           │                   │                  │                │          │
 │─query────►│                                                                  │
 │           │ parse: META_BELIEF, target=Bob
 │           │─► does_X_know(X=Bob, fact=⟨Carol responsible⟩) ────►│
 │           │                   │ 检查 perceived_by 含 Bob？
 │           │                   │─► Episode 4/15 群聊参与者 ────────────────►│
 │           │                   │        ◄─── Bob 在场 ✓ ────────────────────│
 │           │                   │ 检查 explicit_told？
 │           │                   │─► 检索后续私聊 ────────────────────────────►│
 │           │                   │        ◄─── 无补充 ───────────────────────│
 │           │                   │ 检索 holder=Bob 近期发言
 │           │                   │─► Neocortex(holder=Bob).query ─────────────►│
 │           │                   │        ◄─── Bob 之后无相关回应 ────────────│
 │           │                   │ 判定：应已知（感知充分）但无主动确认
 │           │                   │ → suspected_diverge 候选
 │◄────── Context Pack ──────────────────────────────────────────────────────────
```

**Context Pack 内容：**

```
[INFERRED] Bob 当时在群里（perceived_by 命中），应该已知
[HEARSAY]  但他之后没有相关回应，必要时可主动确认
[TODO]     建议：私聊 Bob 确认 + 同步 Carol 接手计划
```

**经过子系统：** Retrieval Planner → ToM.does\_X\_know → KnowledgeFrontier 过滤 → Neocortex(holder=Bob) → CommonGround 检查

**事件：** statement.recalled × N

**输出：** [INFERRED] Bob 应已知（perceived\_by 命中）+ [HEARSAY] 无主动确认 → suspected\_diverge 候选标记。

---

### 14.4 场景 D：Replay 巩固（Idle 模式）

**输入：** agent 空转触发 Idle 模式，Replay Scheduler 采样 VOLATILE Statement。

```
Replay Scheduler   Hippocampus   Validator   ConflictProbe   Neocortex   Bus
        │              │              │             │             │          │
  Idle trigger                                                               │
        │─► 优先级采样 10-30 条 VOLATILE ──────────────────────────────────►│
        │─► 巩固原子操作（compress / abstract）                               │
        │─► Bus.write(replay_derived) ─────────────────────────────────────►│
        │              │          Validator.check ────────────────────────►  │
        │              │          ConflictProbe.scan ──────────────────────► │
        │              │                             Neocortex CONSOLIDATED upsert
        │              │◄── emit statement.derived ────────────────────────  │
        │   （Replay Scheduler 不订阅 statement.derived，循环断开）
```

**经过子系统：** Replay Scheduler → 优先级采样 → 巩固原子操作 → Bus.write → Validator → ConflictProbe → Neocortex CONSOLIDATED upsert

**事件：** statement.derived × N（不发 statement.written）

**输出：** N 条 CONSOLIDATED Statement；原 VOLATILE Statement 进入下一轮采样，或在 Sleep 模式触发 decay。

---

### 14.5 场景 E：Prospective 触发（承诺提醒）

**输入：** 周二 Bob 承诺"周四前完成 X"，Commitment(state=ACTIVE，trigger=TimeTrigger(at=Thu 09:00))。

#### 阶段 1：写入

```
Bus.append_evidence(Bob 原话，perceived_by=[self, Bob, Alice])
  → evidence.appended → Extractor
  → EM-LLM boundary_score 高（承诺类话语 surprise 显著）→ EpisodicEvent
  → LLM 抽取（XML strict）：
      S1: holder=Bob, modality=COMMITS, pol=POS,
          predicate=will_deliver, object=draft,
          trigger=TimeTrigger(at=Thu 09:00), deadline=Thu 23:59,
          state=ACTIVE, affect={stakes:0.7}
      S2: holder=self,  modality=BELIEVES, pol=POS, object=⟨S1⟩
      S3: holder=Alice, modality=BELIEVES, pol=POS, object=⟨S1⟩
  → Validator + ConflictProbe（无冲突）
  → Bus.write × 3 → Hippocampus VOLATILE upsert
  → Prospective Loop 订阅器命中 modality=COMMITS：
      注册 TimeTrigger(at=Thu 09:00) 到 PolicyEngine
      写入 Working Set.pending_commitments
  → CommonGround(self, Bob, Alice).asserted_unack += S1
  → Affect Buffer 入队（stakes=0.7）
```

#### 阶段 2：巩固（Idle 模式）

```
Replay Scheduler（Idle）：S1 高权重优先采样
  → 无冲突，不仲裁，加强 activation
  → S1 升入 CONSOLIDATED，Commitment.state 仍 ACTIVE
  → Reconsolidation：无新证据，跳过
```

#### 阶段 3：周四 09:00 触发

```
PolicyEngine 后台轮询 Trigger 队列
  → TimeTrigger 命中 → emit commitment.fire(S1)
  → Working Set.pending_commitments 注入提醒
  → 系统自主检查：
      holder=Bob 子图：无"已发草稿"statement
      EngramStore：无 Bob 单方面 RENEGOTIATE
      perceived_by：self 与用户在线
  → Retrieval Planner(intent=COMMITMENT_DUE) → Context Pack：
      [TODO]    Bob 答应今天前把方案草稿发给 Alice（周二约定，evidence: EngramStore:xyz）
      [FACT]    截至现在尚未看到草稿，Alice 也未确认收到
      [COMMON]  这是 Bob 与 Alice 的共识（你也在场）
      [INFERRED] 建议：可以提醒 Bob，或先问 Alice 是否已私下收到
  → agent 主动开启对话（无用户 query 触发）
```

#### 后续：Bob 当天交付

```
新 EpisodicEvent 检测到 Bob 发出 draft → 抽取 fulfilled_by 关联
  → Prospective Loop：Commitment.state ACTIVE → FULFILLED
  → emit commitment.fulfilled → trust_priors[self→Bob] 微调上
  → CommonGround(self, Bob, Alice).grounded += S1
  → emit commitment.released → decay scheduler 移除保护
  → Reconsolidation：S1 进可塑窗口，结合"已履行"事实，confidence ↑，加 evidence_for 边
```

**事件顺序（完整）：**

```
statement.written × 3
  → commitment.fire（Thu 09:00）
  → commitment.fulfilled（Bob 交付后）
  → commitment.released
  → statement.derived（Reconsolidation 输出）
```

**输出：** 系统在无用户 query 的情况下于周四早上主动想起承诺。PolicyEngine 将 TimeTrigger 作为运行时一等公民，触发条件从 Statement 数据本身派生，不依赖外部 cron job 或 reminder 服务。

---
## 15. 路线图

三阶段分层，按"最小可测试 → 小规模可用 → 大规模优化"递进。每阶段以可量化验收指标为准入/出口，不以功能清单为判据。

| 阶段 | 定位 | 周数 | 状态 |
|---|---|---|---|
| **P1** | 最小系统，主要功能完备可测试 | 6 周 | 编码起点 |
| **P2** | 所有功能基本完备，局部待优化，支持小规模应用 | 14 周 | 接续 P1 |
| **P3** | 所有功能完备，系统完成主要优化，支持大规模应用 | 12 周 | 接续 P2 |
| P3+ | 持续演进，无硬性交付节点 | 不定 | 研究方向 |

总工期（不含 P3+）：P1（6 周）+ P2（14 周）+ P3（12 周）= 32 周 ≈ 8 个月。P2 与 P3 内部子阶段可并行展开，压缩至 6-7 个月内。

阶段依赖链：P1 → P2 → P3。P2 依赖 P1 的 holder 子图数据与冻结契约；P3 依赖 P2 的 Replay + Reconsolidation 写路径稳定，与 AffectVector salience 字段、完整 Retrieval Planner 接口。

### 15.1 阶段交付

**P1（6 周 baseline，单/双人熟练 Python）**

定位：最小系统，主要功能可测试。Schema + 写入闭环 + LLM 抽取 + 冲突探针 + basic_retrieve。

| 内容 | 验收方式 |
|---|---|
| Statement + Cognizer + 六态 ConsolidationState + StatementProvenance + ReviewStatus + EngramRetentionMode Pydantic 实现；SQLite 单底座 CRUD；outbox 表；ProfileCapability preflight（含 cross_partition_transaction）；最小 PipelineRun 账本 + ExtractionAttempt item 明细；SourceKind/IngestPolicy 与 source adapter metadata；chunk 级 SourceSpanRef（engram_ref/chunk_index/observed_at/source_hash）与序列化推导的 TemporalAnchor；一阶 Statement 抽取 prompt（XML strict + holder_perspective 规则）；basic_retrieve(holder=self, intent=FACT_LOOKUP) 主表直查 + 最小 RetrievalReceipt | 单元测试 + 50 条手工标注对话样本回归 + outbox 投递/幂等测试 + §14.1 最小变体 smoke test（Alice 宣布 Bob 不再负责 auth，testing helper 将 Statement 标为 CONSOLIDATED 后检索返回 Carol 接手，能查看 extraction attempt、pipeline run 与 retrieval receipt）；35 用例（12 CRITICAL） |

**P2（14 周，小规模应用）**

定位：所有功能基本完备，局部待优化。在 P1 契约之上叠加社会心智、类脑动力学、前瞻三个能力层。P2 内部分三个子阶段，可部分并行：

| 子阶段 | 周数 | 核心交付 | 验收方式 |
|---|---|---|---|
| P2.a 社会心智 Schema | 4 周 | Cognizer Hub（注册 + 别名归一 + 关系类型）；holder 子图族；KnowledgeFrontier 计算；ConflictProbe + CONFLICTS_WITH 边；perspective_take 算子一阶版；ToM 一阶 Schema | ToMBench 一阶 ToM + FANToM 信息不对称 |
| P2.b 类脑动力学 | 6 周 | Hippocampus/Neocortex 逻辑分区标签 + Projection Index；Replay Scheduler（周期采样 + 聚类 + 三动作：reinforce/abstract/compress）；模式分离/补全（反相似偏移 + PPR 图游走）；Reconsolidation 原子事务（不覆盖）；CommonGround pool 基础 | LongMemEval 时间 + 更新两类得分提升；模式分离混淆率 < 15%；主表查询不承担五维复合索引 |
| P2.c 前瞻与情感 | 4 周 | Commitment 五态机 + 4 类 Trigger（time/event/state/compound）；Prospective Loop 调度器；AffectVector 五维 + salience 公式；优先级重放权重；ActionGuard 最小子集（allowed_actions + requires_approval + idempotency_window） | 自建承诺履行集 100 条：detection > 80%，timeliness < 3 turns |

**P3（12 周，大规模应用）**

定位：所有功能完备，主要优化完成。在 P2 之上叠加完整检索规划、二阶 ToM、多底座产品化。P3 内部分三个子阶段：

| 子阶段 | 周数 | 核心交付 | 验收方式 |
|---|---|---|---|
| P3.a 检索规划 + 二阶 ToM | 4 周 | Retrieval Planner 完整 7 步 + 9 种 QueryIntent；perspective filter（iterative masking）；Abstention 判定；Context Pack Builder 8 标签；二阶 ToM（nesting_depth=2）全链路；ToMDepthEstimator（A-ToM 风格）；CommonGround 完整 grounding acts；Affect Buffer 参与采样 | ToMBench / FANToM / SoMi-ToM 全量；二阶 ToM 主动提示 precision > 70%；ToMDepth 估计 accuracy > 60% |
| P3.b 多底座产品化 | 4 周 | Substrate Adapter 三档 profile 全量交付：local-store（SQLite+LanceDB+Kuzu）已在 P1 落地；dist-store（Postgres+pgvector+AGE）已在 P2 落地；P3.b 交付 cloud-store 三形态（单云原生 AWS/GCP/Azure、混合托管、跨云 SaaS）；P1↔P2↔P3 跨档迁移工具；mem0 / Letta / cognee / Graphiti / memU 迁移脚本；评测体系全量跑通；API 文档 + 接入指南 | 用户主观评测 A/B 对照；跨档迁移 + 5 种外部系统迁移集成测试 |
| P3.c 规模化优化 | 4 周 | 完整 ScopedWorkGate / RestartGuard / stage_timing；RuntimeHealth 完整仪表盘与自动背压调度；完整 SourceAdapter 插件系统；dimension-level Container CAS；segment_map / span_start / span_end；ActionPolicyGraph 8 规则完整版；PipelineStepContract 通用 step graph；Retrieval 多源 fan-out latency budget | P3 规模化负载测试：1000 Cognizer × 10000 Statement × 100 QPS 检索 |

### 15.2 P1 内部里程碑 M0.0 - M0.7

| 里程碑 | 估算 | 交付 |
|---|---|---|
| M0.0 ProfileCapability skeleton | 3 天 | ProfileCapability + final query assertion + testing helper marker + CI 静态扫描 |
| M0.1 Schema | 3-5 天 | 30+ 字段 + 16+ enum + Container key + canonicalize_object 规则 |
| M0.2 SQLite + outbox | 7-10 天 | at-least-once dispatcher + idempotency + dead-letter + PipelineRun + ExtractionAttempt + idx_statement_id_tenant |
| M0.3 Bus.append_evidence | 3 天 | EngramStore + retention_mode + ingest_policy + 自污染防护 |
| M0.4 LLM Extractor | 7 天 | XML strict + existing_ref_map + extraction_span_key + retry/PARTIAL_SUCCESS + holder_perspective 规则 |
| M0.5 ConflictProbe | 7 天 | canonicalize_object + normalize_interval + scope_of + hash version 双查协议 + 两个 idx |
| M0.6 basic_retrieve | 3 天 | 主表查询 + RetrievalReceipt + sufficiency_status |
| M0.7 验收 | 10-14 天 | 35 用例（12 CRITICAL）+ 50 条手工标注 + 2 E2E + 1 eval |

**并行性**：M0.4 与 M0.5 共享 canonicalize_object，需先完成 M0.5 核心函数再启动 M0.4。M0.4 的 existing_ref_map 需要 M0.6 的 holder-aware 检索给 LLM 列已有候选；M0.4 第一版可用 stub 替代，M0.6 完成后回填。

**内部依赖顺序**：

| 子里程碑 | 内容 | 依赖 |
|---|---|---|
| M0.1 Schema | Pydantic 实现 + JSON-Schema 导出，含 tenant_id、derived_depth、canonical_object_hash_version、chunk 级 SourceSpanRef 与 P1 推导式 TemporalAnchor 序列化 | 无 |
| M0.2 持久化 | SQLite CRUD + outbox 表 + consumer_checkpoint + idx_statement_id_tenant + 最小 PipelineRun 表；ExtractionAttempt 作为 extraction run item 表；不实现 step graph | M0.1 |
| M0.3 写入路径 | Bus.append_evidence + EngramStore + retention_mode/source_kind/ingest_policy 审计 | M0.2 |
| M0.4 抽取 | Extractor + Validator + extraction_span_key(normalized_span=chunk_index) + 单片段 temporal grounding | M0.3 |
| M0.5 冲突 | ConflictProbe + canonical_conflict_key + canonical_object_hash/canonical_object_hash_version 主表列 + SUPERSEDES 边 | M0.4 |
| M0.6 检索 | basic_retrieve + 主表过滤 + evidence 返回 + 最小 RetrievalReceipt(sufficiency_status) | M0.5 |
| M0.7 验收 | smoke test + 50 条回归集 + 幂等/负面用例测试 | M0.6 |

总和：M0.0（3）+ M0.1（5）+ M0.2（10）+ M0.3（3）+ M0.4（7）+ M0.5（7）+ M0.6（3）+ M0.7（14）= 52 天 ≈ 7 周。考虑 Lane B/C 部分并行（M0.4 + M0.5），收口至 6 周 baseline。

### 15.3 P1 验收用例

35 条用例（16 现有 + 19 新增），其中 12 CRITICAL：

**状态机契约（5 CRITICAL）**
- TC-A1-001 / TC-A1-002：振荡上限 + TTL
- TC-A5-001：fallback timeout
- TC-A6-001 / TC-A6-002：T5/T8 并发互斥（severe path 双路径）

**Commitment 契约（3 CRITICAL）**
- TC-A2-001 / TC-A2-002：BROKEN 计数 + 链长
- TC-A9-001 / TC-A9-002：active_holding 保护

**Reconsolidation 契约（3 CRITICAL + 1）**
- TC-A3-001：derived_from 防抖
- TC-Q1-001：references_existing 闭环
- TC-A8-001 / TC-A8-002：severe path 双路径
- TC-Q3a-001：mild provenance 不变（非 CRITICAL）

**Extractor 契约（4 CRITICAL）**
- TC-Q2-001 / TC-Q2-002 / TC-Q2-003 / TC-Q2-004：holder_perspective 四种 perspective

**ConflictProbe 契约（1）**
- TC-Q3b-001：二阶 Statement object 区分

**默认值与事件表（3）**
- TC-A4-001：system.runaway
- TC-A7-001 / TC-A7-002：默认值 baseline

12 CRITICAL 用例为 P1 出货门槛，缺一不可。详细列表见 v21_subsystems/07_v16_eng_review_test_plan.md。

**新增 critical failure mode 测试**

- TC-A5-002：fallback 任务自身失败（双层兜底）
- TC-A9-003：dispatcher 启动 boot replay commitment.active_holding/released 事件，重建 in-memory set

**负面验收用例**

- 隐私拒收：Engram 含隐私越界内容 → Validator 拒收 → emit `extraction.failed(privacy_violation)` → 不重试，进入 dead-letter / audit。
- 冲突共存：注入两条不同 holder 的矛盾 Statement → 两条共存 → 检索/Context Pack 标 CONFLICT，不得静默挑边覆盖。
- 证据擦除：触发 `crypto_erasure` 后 → `basic_retrieve` 仍可返回 Statement 元数据，但 evidence 标注"部分证据已擦除"且 verbatim 不可恢复。
- 幂等写入：同一 Engram 重复抽取 → `extraction_span_key` 去重 → 不产生重复 Statement。
- 运行回执：成功写入与 no-op 抽取都必须产生 ExtractionAttempt；basic_retrieve 必须返回最小 RetrievalReceipt。
- Profile preflight：关闭 `transactional_outbox` 或 `tenant_isolation` → 系统进入 UNREADY，不得继续运行。
- 自污染防护：RetrievalReceipt / PipelineRun trace 作为输入重放 → `source_kind=system_internal` 默认 NO_STORE，不得产生用户画像 Statement。
- 归因不可变：写入后尝试原地修改 holder/source_speaker/perceived_by → Validator 拒绝；正确路径是 `statement.corrected + supersedes`。
- `tenant_id` 不可变：尝试原地 UPDATE Statement.tenant_id → 拒绝，只能新建跨 tenant review 候选。
- `provenance` 不可变：review 提升、confidence 调整、testing consolidate 不得修改原 Statement.provenance；fork/supersedes 新版本才可有新 provenance。
- 跨 tenant 派生：Statement A(tenant=t1) 派生 Statement B(holder.tenant=t2) 时，若无 org_default/system 前驱或显式协议 → Validator 拒绝；若有显式协议 → REVIEW_REQUESTED。
- chunk 级幂等：同一 chunk 内同 (predicate, canonical_object) 重复抽取，第一条接受，第二条标 REVIEW_REQUESTED，不自动覆盖。
- 时间锚负例：导入历史 Engram 含"last week" → valid_from 落在原始观察周期，不得使用系统当前日期；若无 segment observed_at，必须低置信/待审。
- 租户隔离 fail-closed：SQLite adapter 测试 final query 缺少 tenant_id/holder_scope assertion 时拒绝执行；生产 profile 模拟 app_filter 不得通过 storage_enforced preflight。
- Source adapter metadata：同一内容分别以 byte_preserving 与 metadata_only 写入 → 后者不得让高影响 Statement 自动 APPROVED，receipt/context 必须标 evidence_kind。

**P1 testing helper 约定**

- `testing.mark_consolidated(stmt_id)`：VOLATILE → CONSOLIDATED，写审计记录，production profile 禁用。
- `testing.mark_evidence_erased(engram_ref)`：标为 crypto_erasure，用于 basic_retrieve 擦除负例，不实现完整合规传播。
- 所有 helper 文件级必须声明 `__starling_testing_only__ = True`，位于 `starling.testing.*` 命名空间。production 启动 preflight 发现该标记即 fail-closed；CI 静态扫描禁止 production entrypoint 引用 testing 命名空间。module marker 是运行时防线，不是唯一保证；不能通过 runtime flag 覆盖。

**P1 非交付项（明确说明）**

P1 不交付：Projection Index（P2）；idx_entity_statement 实体投影（P2）；完整 Retrieval Planner（P3）；完整 RetrievalScopePlan runtime（P3）；ToM 推断（P2 一阶 schema，P3 二阶运行时）；Replay Scheduler（P2，P1 只用 testing helper 模拟）；完整 RuntimeHealth 仪表盘（P2）；完整 SourceAdapter 插件系统（P2）；细粒度 segment_map/span_start/span_end（P2）；Reconsolidation Engine（P2）；Prospective Loop（P3）；完整 ActionPolicyGraph（P3 高阶）；CommonGround pool（P2 基础，P3 完整）；Affect Buffer（P3，P1 写入 salience 字段但不参与采样）。

### 15.4 迁移路径

**mem0 → Starling**

mem0 以 `{user_id, agent_id, run_id, actor_id}` 四维过滤为隔离手段，actor 是 holder 思想的雏形（v1.0.0 新增 actor_id，actor ≈ holder）。迁移时：filters 四维映射 Cognizer.id；Observation Date / Current Date 分离映射 TemporalAnchor（历史消息相对时间按观察日期解析，不按导入/系统当前日期）；`linked_memory_ids` 与 entity collection 映射 idx_entity_statement（必须带 holder/tenant/state，不能做全局 entity scan）；ADD/UPDATE/DELETE/NOOP 映射 Statement.modality + supersedes 链；`_add_to_vector_store` 的 hash 去重映射 ExtractionAttempt accepted/rejected/noop 计数；existing memory 在 prompt 中映射为短 id，避免 LLM 幻觉长 UUID；UPDATE 时 actor_id 保留对应 Starling 归因不可变（holder/source_speaker/perceived_by 纠错必须经 corrected/supersedes）。注意 mem0 v1.0.0 移除 `version`/`output_format` 参数，统一返回 `{"results": [...]}` ，top-level entity params 抛错拒绝，迁移脚本需适配该 breaking change。

**Letta → Starling**

Letta 已用真实 git CLI + GCS/S3 对象存储实现 Block 版本管理（已迭代到 sleeptime_multi_agent_v4.py + voice_sleeptime_agent.py）。迁移时：Block.label → Working Set label 集；GitEnabledBlockManager → Statement.supersedes 链物理底座候选；Identity ORM（identifier_key + identity_type + properties）→ Cognizer 直接设计参照（Starling 可继承 identifier/properties 模型，再加 aliases/canonical_name/trust_priors/knowledge_frontier）；LoadGate / event-loop watchdog → RuntimeHealth 前后台 admission gate、readiness degraded/recover 语义；Letta identity 间 block sharing → Starling CommonGround/WorkingBlock 权限与共享参考；ToolRulesSolver 8 类规则（Init/Child/Parent/Conditional/MaxCount/Terminal/RequiredBeforeExit/RequiresApproval）→ ActionPolicyGraph，用于 Prospective Loop 触发真实外部动作前的 allowlist、强制前置步骤和 human approval；Archive（可跨 agent 共享的 ArchivalPassage 池）→ EngramStore 的多 agent 共享原档池参照；sleeptime agent → Replay Scheduler Sleep 模式；shared_blocks → CommonGround pool。

**cognee → Starling**

cognee DataPoint 子类机制直接对应 Statement 子类化底座（可直接继承）。迁移时：`run_custom_pipeline` 的 pipeline_name/use_pipeline_cache/incremental_loading/run_in_background 与 dataset queue slot → Starling PipelineRun 的 run id、input_hash、checkpoint 与 per-holder/profile 并发闸门；多用户 access-control capability 检查 → ProfileCapability.tenant_isolation fail-closed 预检；dataset queue 的同 task + same dataset reentrant slot → ScopedWorkGate(tenant, holder_scope, aggregate_id, lane)，避免全局锁阻塞不同 holder；recall 多源顺序（session/trace/graph_context/graph）→ RetrievalScopePlan，低成本 session 命中可短路 graph，但 Receipt 必须记录 skipped scopes 与 stop_reason；forget() 三级 + 权限 → Starling 降级而非删除；improve() feedback_weight alpha（已实装四阶段流水线：apply_feedback_weights → persist_session_QA → enrichment → sync_to_session_cache）→ Replay 的 reconcile/abstract/induce_norm 三动作 + Reconsolidation 反馈闭环；improve 中非致命 stage 失败 → PipelineStepContract.failure_policy 的工程来源；TEMPORAL 边 → 实际外包给 graphiti 的 valid_at/invalid_at（非 cognee 自实现）。

**Graphiti → Starling**

Graphiti 时间字段三元组：`valid_at`（事实生效）/ `invalid_at`（事实停止）/ `expired_at`（被新事实推翻）。Starling 用 valid_from/valid_to 映射前两者，复用 expired_at 机制作为 supersedes 链时间戳底座。Graphiti 是 episode-first（Episode 是一等输入，edge/triplet 是 Episode 产物）；Starling 是 statement-first（EpisodicEvent 是 Statement 子类）。迁移时不能简单一对一映射：保留 Graphiti Episode 为 EngramStore/EpisodicEvent evidence，再把 edge/triplet 映射为 holder-aware Statement。SagaNode（增量摘要节点，只读取新 episode 续写摘要）→ Replay Scheduler compress 动作参考实现；`resolve_edge_contradictions`（新边设旧边 expired_at，节点就地不删）与 Starling supersedes 链同型，可复用 Cypher；MinHash + Shannon entropy + Jaccard ≥ 0.9 实体名去重 → Cognizer alias 归一算法候选；`handle_multiple_group_ids` 式每 group 隔离执行 + merge → Starling 多 holder/perspective retrieval 必须拆分 substrate context，不得宽泛 `holder IN (...)` 后置过滤；Search 多 scope 并发（edge/node/episode/community）+ trace attributes → RetrievalReceipt.scopes_searched/candidate_counts/score_breakdown。迁移时必须补 holder 维度，Graphiti 本身无 holder。

**memU → Starling**

memU Rust core + blob 层可作为 EngramStore 物理底座候选，但需先补 per-record encryption key、key shredding、shared Engram refcount。memU 要求 Python ≥ 3.13；宿主系统在 3.11/3.12 时应通过服务边界或 Rust FFI 接入，不做 P1 阻塞依赖。WorkflowStep `requires/produces/capabilities` 与 PipelineRevision → Starling 长任务 step 校验 + ProfileCapability preflight + run revision token；Workflow interceptor strict/non-strict + step error hook → failure_policy(critical/non_fatal/skip_downstream)，非致命失败必须记录 warning 且受 downstream requires 约束；pre-retrieval decision / sufficiency check → Retrieval Planner 的 needs_retrieval 与 receipt 中的 plan_steps/degraded_paths；sufficiency check 的 ENOUGH/MORE → RetrievalReceipt.sufficiency_status，其中 NEEDS_RAW 受 EngramStore retention/visibility gate 约束；route_category→sufficiency→recall_items→sufficiency→recall_resources → RetrievalScopePlan 的 progressive widening 与 stop_after_sufficient；non-propagate 开关 → replay_derived 默认不再触发 Replay 的工程依据。

### 15.5 共存策略

Starling 不要求替换现有系统。任何开源系统都可以作为 SubstrateAdapter 后端，Starling 在其上增加 holder + Statement + ToM + Replay + Prospective 这一层认知中间件。

- 已用 mem0：保留 mem0，Starling 提供二阶 ToM + 承诺触发 + holder 维度隔离。
- 已用 Letta：保留 Letta，Starling 把 sleeptime + shared blocks 升级为 Replay + CommonGround，不需重写 agent loop。
- 已用 Graphiti/Zep：保留 Graphiti 时序图，Starling 加 holder 维度、KnowledgeFrontier 计算与共识池，不重复建 episode 存储。
- 已用 cognee：保留 cognee 图层，Starling 补 holder 归因 + Commitment 状态机 + perspective_take，cognee 的 multi-user access-control 直接映射 ProfileCapability。
- 已用 memU：保留 memU Rust core 作为 EngramStore blob 底座，Starling 在上层加 Statement schema + outbox + Bus 路由，避免重复实现 blob 存储。

在所有共存模式下，外部库原生数据结构不得直连 Starling 核心表，只能经 Adapter 映射为 Starling 原生原语。Adapter profile 需固定外部库版本并提供迁移测试，避免外部库命名或配置漂移影响 Starling 主契约。

---

## 16. 取舍与风险

取舍与风险两节分开记录。§16.1 记录已做出的设计选择及其被放弃的替代方案，每条均有可追溯的理由。§16.2 记录尚未解决的工程风险与开放问题，部分有缓解方案，部分在后续阶段研究。§16.3–§16.4 记录准入条件与未来演进方向。§16.5 汇总所有明确延后的交付项及延后原因，供排期时参考。

设计选择的评判标准：长期可维护性 > 初始实现复杂度；数据结构层的正确性 > Prompt 工程补丁；可审计性 > 运行时性能（P1 阶段）。凡是通过 schema 约束可以解决的问题，不引入运行时模型推理；凡是通过物理隔离可以解决的问题，不依赖业务逻辑过滤。



每个设计对应一个权衡。

| 选择 | 替代方案 | 理由 |
|---|---|---|
| Statement 为核心原子强制 holder 归属 | Memory/Fact 为原子（类 mem0） | Statement 自带 holder/perspective，从 schema 层解决多主体隔离；长期收益远大于初始复杂度 |
| 嵌套 Statement 表达二阶 ToM（nesting_depth） | 单独的 ToM 推理模块在 Prompt 层模拟 | ToM 是数据结构问题而非模型问题；放进 schema 才能稳定查询、可审计、不依赖 LLM 随机推理 |
| 五类记忆作为逻辑视图非物理分表 | 五张独立物理表 | 同一事件在生命周期中可能跨多类（episode→semantic→commitment→fulfilled）；视图灵活性更高，CLS 巩固本身就是跨表流动 |
| 默认保留差异（模式分离），不主动合并 | 默认合并去重 | 多视角必须共存；差异往往是认知线索而非噪声；合并会不可逆地丢失"谁在什么时候认为什么" |
| 六态状态机 | 三态（DRAFT/STABLE/TOMBSTONED） | 六态体现 CLS 巩固/再巩固生物学根据；SQLite enum 多三个值的 schema 税可接受 |
| Reconsolidation 不覆盖（fork + supersedes） | UPDATE 原 Statement | 保留版本链供 ToM 推断、审计、回滚；防"我说过 X 但记忆已覆盖"问题 |
| 后台 Replay Engine 异步巩固 | 同步抽取即巩固 | 同步拖慢写入且失去"重组"机会；睡眠期离线重放是 CLS 的神经科学基础 |
| Bus 单入口 + outbox | 直接库写 + 触发器 | 事件序列化保证 + 跨子系统幂等 + 重启可恢复 |
| EngramStore 独立子系统 | Hippocampus 内部分层 | 跨 Cognizer 共享原档；retention_mode 独立于 Statement 生命周期 |
| Container 物化视图 | Persona/CommonGround 直接 Statement | 高频读 + 低频写 + 多维度结构；CAS 重建避免锁竞争 |
| Substrate Adapter 多底座，不自造存储 | 自建全套存储引擎 | 成熟开源系统（vector/graph/KV）的工程沉淀不应浪费；Starling 的价值在认知层 |
| 承诺与规范作为一等 Statement 子类 | 放进 metadata 或单独 KV 表 | 全行业空白；做成一等公民才能驱动运行时行为（触发、提醒、履行追踪） |
| 自然语言 belief 列表注入 LLM Context Pack | 形式化 belief base（如 PDDL-Mind） | LLM 对自然语言的理解远好于形式逻辑；形式化作为 P3+ 高阶可选，不阻塞 MVP |

### 16.2 风险与开放问题

1. **LLM 抽取成本**：高频 Statement 抽取 + holder 归因 + ConflictProbe 是主路径，每条 Engram 至少 1 次 LLM 调用，规模化成本未估。缓解：7B 级专用抽取模型 + 高价值场景升级大模型；批量抽取合并；同一 EngramStore 内容不重复抽取的缓存（extraction_span_key 去重）。

2. **Replay 参数调优**：Online/Idle/Sleep 三模式的切换阈值、批量大小直接影响成本与新鲜度。缓解：P2 阶段做参数 sweep，上线后 A/B 调参；提供 conservative / balanced / aggressive 三档预设。

3. **冲突保留 vs 用户体验**：保留多视角是设计选择，但 Context Pack 直接呈现"3 个互相冲突的 belief"时 LLM 可能困惑而非受益。缓解：Context Pack Builder 的 CONFLICT 标签 + 置信度排序 + 默认只注入最高置信度视角，冲突信息按需展开。

4. **隐私 vs ToM 张力**：系统持有"A 以为 B 不知道 X"的元数据，错误视角下绝对不得泄露。缓解：perspective filter 在检索管道早期执行（先于语义排序），不可跳过；敏感 Statement 支持 access_policy 字段。

5. **抽取错误传播**：错误的 holder 归因会产生连锁的错误信念。缓解：Statement 的 confidence + review_status 字段；audit 工具帮助核查关键 Statement；review_status=REVIEW_REQUESTED 标记低置信度抽取结果。

6. **规模化图查询性能**：嵌套 Statement + 关系边 + PPR 游走会形成深图遍历。缓解：预聚合常用子图（per cognizer + per relation type）；PPR 计算缓存；借 cognee 图层分片经验；P3 做性能压测。

7. **再巩固窗口边界**：窗口太宽记忆不稳定，太窄失去修正机会。缓解：工程默认 30 分钟，自适应区间 5 min–6 h（6 h 为 Nader 2000 神经科学参考值）；高频更新对象自动缩短至 5 min 防抖，低频更新延长窗口提高仲裁质量；按 modality 与更新频率自动调整。

8. **Outbox 积压**：at-least-once + 幂等是设计选择，outbox dispatcher 停滞会延迟 Replay/ToM/Prospective。缓解：outbox lag 指标、dead-letter queue、subscriber inbox 去重表、每个 aggregate 的 sequence 单调校验。P1 必备。

9. **crypto_erasure 与可解释性张力**：verbatim 不可恢复后错误溯源能力下降。缓解：保留不可逆 content_hash、source metadata、redacted summary、decision trace；legal_hold/audit_retain 做最小权限访问和审计。

10. **评测单薄**：50 条手工标注对 LLM 抽取统计无功效；FANToM/ToMBench 推到 P2；P1 阶段数据质量信号来源有限，12 CRITICAL 用例是唯一强门槛。

11. **embedding 策略真空**：P1 用主表 LIKE 查询，样本量 50→5000 条即失效；向量检索策略未定，P2 引入 Projection Index 前无法规模化。

12. **hash version 升级期**：maintenance rebuild 未完成前的双查/保守协议复杂度不低；rebuild 期间 ConflictProbe 需两套 hash 共存查询，升级窗口必须有回滚预案。

13. **failure mode 集缺**：LLM 不可用、SQLite WAL 锁、outbox dispatcher hang 等降级路径未在 P1 测试集中列出；P2 需补齐 LLM 降级模式（batch fallback、timeout、partial extraction 三级）。

### 16.3 P2 准入条件

P2 开始前必须满足：

1. P1 全部 12 CRITICAL 用例绿灯，无豁免。
2. P2 ToMBench 一阶 ToM 基准跑通，FANToM 信息不对称对照集准备完毕。
3. Replay Scheduler 启用前需通过 Projection repair safety 测试：构造 rebuild 抽取条数低于主表 ground truth 的场景，验证系统 emit `projection.rebuild_failed(truncation_suspected)` 且 active projection 不被替换。
4. Reconsolidation Engine 上线前，再巩固窗口参数（默认 30 分钟，区间 5 min–6 h）必须有 per-modality 覆写配置，高频更新对象（≥ 3 次/小时）自动缩短至 5 min。
5. P2 ConflictProbe 上线后，CONFLICTS_WITH 边写入必须通过 canonical_conflict_key 唯一性校验，防止同一冲突对多次记录。
6. Projection Index 首次 rebuild 前，必须通过 repair guard（SQLite ground truth vs index count）验证，确认 truncation_suspected 告警机制可触发。

### 16.4 P3+ 持续演进（无硬性交付节点）

P3+ 研究方向：群聊 SharedGround 维护；Multi-agent 信任传播；PDDL 形式化 belief base（可选高阶）；神经-符号混合实验。P3+ 不设出货门槛，P3 结束后按研究进度迭代。

依赖：P3+ 的群聊 SharedGround 需要 P2 CommonGround pool 作为基础；PDDL 形式化 belief base 需要 P3 Context Pack Builder 稳定后才有足够结构化输入；Multi-agent 信任传播需要 P2 KnowledgeFrontier + P3 ToMDepthEstimator 联合驱动。

### 16.5 未交付项（明确延后）

下表汇总所有在 P1–P3 阶段明确不交付的功能项。延后原因以工程必要性和阶段依赖为准，不以"可选"标签代替具体理由。

| 项 | 推迟到 | 原因 |
|---|---|---|
| Retrieval Planner 完整 7 步 + 9 种 Intent | P3 | P1 只交付 basic_retrieve |
| 完整 RetrievalScopePlan runtime | P3 | P1 receipt 只记录固定 statement_main 字段，不构建 plan 对象 |
| ToM 推断运行时 | P2（一阶 schema）/ P3（二阶运行时） | 分阶段引入 |
| Replay Scheduler | P2 | P1 只用 testing helper 模拟巩固完成 |
| Projection Index + idx_entity_statement | P2 | P1 主表直查，不承担五维复合索引 |
| Reconsolidation Engine | P2 | P1 Statement 不因召回进入可塑窗口 |
| Prospective Loop | P3 | P1 不要求 Commitment 触发调度 |
| CommonGround pool | P2（基础）/ P3（完整 grounding acts） | 分阶段 |
| Affect Buffer 参与采样 | P3 | P1 写入 salience 字段但不参与采样 |
| 完整 ActionPolicyGraph 8 规则 | P3 高阶 | P3 仅 ActionGuard 最小子集 |
| 模式补全 CA3 风格 | P2 | 计算重 |
| dimension-level Container CAS | P3 | P1 整体 rebuild 够用 |
| segment_map / span_start / span_end | P2 | 多模态/PDF 分段才需要 |
| ToMDepthEstimator（A-ToM） | P3 | 需 partner 历史数据 |
| 完整 ScopedWorkGate / RestartGuard / stage_timing | P2+ | P1 单线程不需要 |
| RuntimeHealth 完整仪表盘与自动背压调度 | P2 | P1 只实现 capability preflight + 最小 run ledger |
| 完整 SourceAdapter 插件系统 | P2 | P1 只实现内置 direct_api adapter metadata + conformance stub |
| 外部库原生数据结构直连核心表 | 永不交付 | 只能经 Adapter 映射为 Starling 原生原语 |
| Retrieval P3 多源 fan-out latency budget | P3 | 实际负载成点才能估准默认值 |
| PipelineStepContract/requires/produces/failure_policy 通用 step graph | P3 | P1 只记录 pipeline_name/version/status/counters |

---
## 附录 A 术语速查

按字母顺序排列。每个术语 1-3 句定义。

### A-C

- active_grounded：CommonGround 中未 expired/superseded/ungrounded 的条目；§10.4 衰减公式中放大 S0。
- ActionGuard：前瞻动作护栏，三件套 allowed_actions / requires_approval / idempotency_window。P1 阶段替代完整 ActionPolicyGraph。
- ActionPolicyGraph：8 规则完整动作策略（P3 高阶）。含 Init/Child/Parent/Conditional/MaxCount/Terminal/RequiredBeforeExit/RequiresApproval。
- aggregate_id：BusEvent 信封字段，同一 aggregate 按 outbox sequence 顺序投递。
- aliases：Cognizer 跨数据源主体归一的别名集合。canonical_name 是首选展示名。
- APPROVED：review_status 之一，可进入正常检索/巩固。
- ARCHIVED：consolidation_state 之一，长期未召回从热路径移除但保留索引。CommonGround 条目与未结清 Commitment 不允许进入此态。
- canonical_object_hash：写入时计算的对象哈希，供 ConflictProbe 索引。仅支持五种 Value 类型。
- canonical_object_hash_version：哈希版本字段，升级期 ConflictProbe 同版本比较。跨版本降级 review 而非直接拒收。
- canonicalize_object：Value 标准化函数（bool/int/float/str/datetime/StatementRef）。list/dict 拒收。
- causation_chain：BusEvent 因果链，深度 ≤ 3。Subscriber 调 Bus 必须显式传 causation_parent。
- chunk_index：SourceSpanRef 字段，Engram 内片段索引。P1 阶段即 normalized_span。
- Cognizer：认知主体一等公民，区分于 Entity。持有信念、画像、知识边界与信任先验。
- commitment.active_holding：Commitment ACTIVE 时反向 emit 的保护事件。防止关联 Statement 在承诺存续期被遗忘。
- CONSOLIDATED：consolidation_state 之一，已沉到 Neocortex 长期语义。
- ConflictProbe：冲突探针。四级冲突：direct_contradiction / partial_overlap / superseding / adjacent。
- Container：物化视图基类（Persona / CommonGround / KnowledgeFrontier），非 Statement。经 Bus.rebuild_container + CAS 更新。
- content_hash：Engram 字段，sha256 永远保留即使 crypto_erasure 后。
- crypto_erasure：retention_mode 之一，销毁内容密钥保留不可逆 hash。传播仅到直接依赖且无独立 evidence 的 Statement。
- cross_partition_transaction：ProfileCapability 字段，声明跨 Hippocampus/Neocortex/Outbox 原子事务能力。severe path 双路径之一。

### D-G

- decay：Replay 周期性衰减，公式 S(t) = exp(-Δt / S0)。active_grounded 条目放大 S0 获得遗忘保护。
- DEGRADED：RuntimeHealth 四态之一，暂停非关键 Replay/Projection。读写继续，后台调度限速。
- derived_depth：Statement 字段，派生链深度 O(1) 缓存。SUPERSEDES 边不累计深度。
- derived_from：Statement 字段，直接前驱列表。唯一派生链字段，derivation_chain 已删除。
- dimension_versions：Container P3 字段，dimension-level CAS。P1 用整体 rebuild + 单 version CAS。
- DRAINING：RuntimeHealth 之一，停止 claim 新任务。已持有任务继续完成。
- Engram：EngramStore 中的 verbatim 原档记录。Statement FORGOTTEN 后 EngramStore 仍保留。
- EngramRef：Engram.id 引用。
- EngramStore：与 Hippocampus/Neocortex 平级的全局证据子系统。生命周期独立于 Statement。
- evidence：Statement 字段，指向 EngramRef 列表。直接抽取 Statement 必须有此字段。
- evidence_chain：可计算闭包，由 derived_from 递归展开。非持久化字段。
- FIRST_PERSON：holder_perspective 之一，agent 自陈。
- FORGOTTEN：consolidation_state 之一，从检索路径移除。可伴随 redaction 或 crypto_erasure。
- grounded：CommonGround 状态，双方都知道双方都知道。可经显式确认、共同在场推定、重复确认等途径达成。
- group tenant：Cognizer kind=group 必须显式声明 tenant_id。

### H-N

- HEARSAY：holder_perspective 之一，转述不可追溯。Extractor 填值规则：无明确说话人时使用此值。
- Hippocampus：快记忆子系统，承担 VOLATILE Statement。
- holder：Statement 字段，认知主体引用。不一定等于说话人或 subject。
- holder_perspective：FIRST_PERSON / QUOTED / INFERRED / HEARSAY 四值。Extractor 基于源文本上下文填写，不可随意默认 FIRST_PERSON。
- idempotency_key：幂等键，公式 hash(event_type, aggregate_id, canonical_key, causation_chain_root, window_bucket)。
- INFERRED：holder_perspective 之一，LLM 推断。填写后进入 INFERRED_UNREVIEWED 审核状态。
- INFERRED_UNREVIEWED：review_status 之一。LLM 推断产出的 Statement 默认初始状态。
- KnowledgeFrontier：Cognizer 知识边界 Container。检索时用于遮蔽超出视角范围的信息。
- legal_hold：retention_mode 之一，保留密文禁止 purge。优先级高于 crypto_erasure。
- Mentalizing Primitives：7 个高阶认知原语 API。封装 ToM 推理，供上层调用。
- modality：Statement 字段，11 类（BELIEVES / KNOWS / ASSUMES / DOUBTS / DESIRES / INTENDS / COMMITS / PREFERS / NORM_OUGHT / NORM_FORBID / RECANTED）。
- Neocortex：慢记忆子系统，承担 CONSOLIDATED Statement。
- nesting_depth：Statement 嵌套深度（0=一阶，1=二阶，2=三阶）。object 字段通过 StatementRef 承担嵌套，subject 不接 StatementRef。

### O-R

- outbox：事务性 outbox 模式，写入与 outbox append 同事务。at-least-once 投递，消费端幂等消费。
- outbox_sequence：BusEvent 字段，按 aggregate 顺序投递。
- perceived_by：Statement 字段，信息可见性。检索时按主体视角过滤。
- PENDING_REVIEW：review_status 之一，待人工或自动流程审核。
- perspective_take：ToM 算子，按 (target, time) 重构 Context。
- PipelineRun：长任务账本。统一 Extraction/Replay/Projection/Compliance 等长任务，支持 checkpoint/watermark/worker lease。
- PolicyEngine：Prospective Loop 的 Trigger 监听器。是 Bus publisher 之一，所有 Trigger 命中走 Bus.emit。
- polarity：与 modality 正交，三值 POS / NEG / UNKNOWN。
- primary_id：BusEvent 信封字段。一次性业务幂等键默认从此字段推导。
- ProfileCapability：Substrate 能力声明，preflight 时校验。生产 profile 不满足则 fail-closed。
- Projection Index：P3 物化视图索引。P1 走主 Statement 表直查。
- provenance：Statement 字段，写入即冻结，四值 user_input / replay_derived / tom_inferred / reconsolidation_derived。后续任何变更不改此字段。
- QUOTED：holder_perspective 之一，直接引语或明确转述。
- READY：RuntimeHealth 之一，正常运行。
- Reconsolidation：被回忆即可塑机制。severe path 原子化，新版/旧版归档/SUPERSEDES 边/outbox 事件同事务提交。
- REJECTED：review_status 之一，审核拒绝，不进入检索路径。
- replay_derived：provenance 之一，Replay 巩固产出。不触发 statement.written，改 emit statement.derived，断开循环。
- REPLAYING_CONSOLIDATING：state 之一，从 VOLATILE 进入首次巩固。有振荡上限与 fallback timeout。
- REPLAYING_RECONSOLIDATING：state 之一，从 CONSOLIDATED/ARCHIVED 进入再巩固。可塑窗口内追加证据。
- REVIEW_REQUESTED：review_status 之一，已发出人工审核请求。
- review_status：APPROVED / PENDING_REVIEW / INFERRED_UNREVIEWED / REVIEW_REQUESTED / REJECTED 五值。
- RetrievalReceipt：检索回执，证明 perspective filter 与 tenant scope 已执行。含 sufficiency_status 与 abstention 原因。

### S-Z

- salience：显著性，五维计算。驱动 Replay 采样权重。
- ScopedWorkGate：并发限流，按 (tenant, holder_scope, aggregate_id, lane) 可重入。
- self_model_anchor：Persona dimension，主体自陈。冲突时优先于 profile_anchor。
- profile_anchor：Persona dimension，他人对主体陈述。与 self_model_anchor 分歧触发 suspected_diverge。
- SourceKind：EngramStore 输入来源分类。system_internal/observer_agent/replay_output 默认 NO_STORE，防止自污染。
- SourceSpanRef：片段锚。绑定 Statement 到 EngramStore 具体片段/episode/segment。
- SUPERSEDES：版本链边。新版本对旧版本的非覆盖式替代，不累计 derived_depth。
- statement.references_existing：派生引用闭环事件。§11.1 触发路径 2 的入口。
- statement.decay_candidate：decay 候选事件，per-stmt 顺序串行。防止 T5/T8 并发竞态。
- Statement：核心原子。谁在何时基于何证据以何样态持有什么判断。
- StatementRef：Statement.id 引用，用于嵌套二阶 ToM。object 字段承担嵌套，subject 不接 StatementRef。
- sufficiency_status：RetrievalReceipt 字段，SUFFICIENT / MISSING_INFO / NEEDS_RAW / ABSTAINED 四值。
- TemporalAnchor：时间锚。默认由 SourceSpanRef.observed_at 推导，不得随导入时间漂移。P3 才持久化独立字段。
- tenant_id：Statement/Cognizer 字段，写入后不可变。底座命令边界强制注入，非应用层传参。
- tom_inferred：provenance 之一，ToM 推断。Replay 权重因子 0.25，防止 ToM→Replay→Container→ToM 链路失控。
- trace_retention：prompt/response/trace 的保留层级，metadata/hash/debug/full_debug 四档。生产默认不存 raw。
- trust_priors：Cognizer 对他人的先验信任（注意方向性）。
- UNREADY：RuntimeHealth 之一，preflight 失败 fail-closed。
- VOLATILE：state 之一，刚写入未巩固。振荡上限与 TTL 兜底由 v17 冻结。
- window_bucket：幂等键中的时间桶粒度。

---

## 附录 H 历史变更记录

本节按版本时间倒序列出每版主要修改。完整设计推导可参考各版本源文件。

| 版本跨度 | 主题 |
|---|---|
| v18 → v19 | 事件语义收口：区分 lifecycle `statement.consolidated` 与内容派生 `statement.derived` |
| v17 → v18 | 结构拆分，单文件 → 主文档 + 11 子系统 |
| v16 → v17 | 编码起点，14 项契约决定写入 |
| v15.1 → v16 | Value 类型冻结，hash 版本化 |
| v15 → v15.1 | 派生链收敛，provenance 冻结 |
| v14 → v15 | 简单性优先原则 |
| v13 → v14 | 外部机制吸收原则 |
| v12 → v13 | 执行锚点写入 |
| v11 → v12 | 工程防线 |
| v10 → v11 | 工程闭环 |
| v9 → v10 | 负面用例 + 术语表 |
| v8 → v9 | evidence chain 重构 |
| v7 → v8 | 热路径索引策略 |
| v6 → v7 | 防抖与幂等契约 |
| v5 → v6 | 六态冻结 + 合规生命周期 |
| v4 → v5 | 15 项架构问题修复 |
| v3 → v4 | 6 态状态机 + 前沿论文整合 |
| v2 → v3 | Replay Scheduler + Prospective Loop |
| v1 → v2 | AffectVector + trust_priors + polarity |

### v18 → v19（本版）

编码前事件语义收口。`statement.consolidated` 明确为生命周期信号，表示 Statement 最终稳定在 `CONSOLIDATED`；Replay Scheduler 与 Reconsolidation Engine 都可作为 producer。`statement.derived` 明确为内容派生信号，仅表示 Replay 产出新的派生 Statement，不再承担生命周期含义。

同步更新主文档、Statement Bus、Neocortex、Replay Scheduler 与 Reconsolidation Engine 的事件表和流程描述。v18 及其子系统文档保持不变，v19 是本轮审阅后的编码前候选版本。

### v17 → v18

结构性重构。从单文件 spec 拆为主文档 + 11 子系统文档。

主文档保留：摘要、公理、系统总览（三张分层图：拓扑/数据流/执行流）、数据本体、端到端场景、路线图、取舍与风险、术语表。

子系统拆出：Substrate / Bus / Governance / EngramStore / Hippocampus / Neocortex / Cognizer / ToM / Replay / Reconsolidation / Prospective / Retrieval 共 11 个。

正文移除所有版本闲聊（"v6 新增"、"v15 修复"等表述），不影响合约语义。

### v16 → v17

Section 1+2 plan-eng-review 14 项契约决定 + cross-model tension 3 项策略决定全部写入。

Major 级（影响 P1 编码契约边界）：
- VOLATILE↔REPLAYING_CONSOLIDATING 振荡上限 + TTL 兜底
- Commitment BROKEN 计数 + RENEGOTIATED 链长上限
- derived_from 防抖路径在 §5.4 显式列出
- REPLAYING_CONSOLIDATING fallback timeout（对称 RECONSOLIDATING）
- T5/T8 并发互斥：decay 路由经事件总线，per-stmt 顺序串行
- severe path 双路径：ProfileCapability cross_partition_transaction + saga
- Commitment 反向保护事件 active_holding/released
- 默认值冻结 + system.runaway 入 §5.3 主表
- statement.references_existing 闭环 §11.1 触发路径 2
- holder_perspective Extractor 填值规则
- mild correction provenance 不变 + confidence_history
- canonicalize_object 对 StatementRef 补 modality + inner_object_hash
- 文档级修复：DRY/术语/阶段标注/3 张 ASCII 图
- canonical_object_hash 升级 maintenance 超期告警

策略级：保持六态机不变；P1 时间表调整 2 周→6 周；v17 是 P1 编码起点。

### v15.1 → v16

Value 类型与 canonical 化冻结；canonical_object_hash 版本化；跨 tenant 派生例外规则；派生深度 O(1) 缓存；BusEvent 默认业务键；testing helper fail-closed 识别。

### v15 → v15.1

证据约束按 provenance 分级；派生链语义单一化（删 derivation_chain）；provenance 写入即冻结；tenant_id 入主体与陈述 schema；P1 TemporalAnchor 简化。

### v14 → v15

简单性优先原则（§0.2）：ActionPolicyGraph / PipelineStepContract / RetrievalScopePlan / Projection Index / dimension-level Container CAS 都有价值，但只有触发条件出现后才升级。P1 以主表、固定路径、单状态机为主。

### v13 → v14

外部机制吸收原则（§0.1）：四条收敛规则确保外部库经验不污染核心 schema。外部概念必须映射到 Starling 原生原语，不得引入第二套事实源/生命周期/权限边界。ExtractionAttempt 并入 PipelineRun（kind=extraction），Run Ledger 单一化。

### v12 → v13

执行锚点：SourceSpanRef / TemporalAnchor / RetrievalScopePlan / PipelineStepContract.failure_policy / ActionPolicyGraph / idx_entity_statement 写入主契约。归因不可变原则：holder/source_speaker/source_spans/perceived_by/temporal_anchor 不可原地改写，纠错必须经 statement.corrected + supersedes。

### v11 → v12

工程防线：SourceAdapterContract / SelfPollutionGuard / storage-enforced tenant isolation / ScopedWorkGate / Retrieval sufficiency / TraceRetentionTier。system_internal/observer_agent/replay_output 默认 NO_STORE，防止 prompt/receipt/log/replay 摘要污染用户记忆。

### v10 → v11

工程闭环：RuntimeHealth / PipelineRun / RetrievalReceipt / ProfileCapability 写入主契约。READY/DEGRADED/DRAINING/UNREADY 四态控制读写与后台调度。ProfileCapability preflight 校验 transactional outbox、tenant isolation、crypto erasure 等硬能力，不满足则 fail-closed。

### v9 → v10

负面验收用例集；术语表（附录 C）；实施 FAQ（附录 D）。补齐 Extractor 抽取契约、canonicalize_object 规范化函数、CommonGround grounded 判定规则、Replay 采样语义。

### v8 → v9

EngramRef 与 evidence chain 重构。SupersedeGround 主触发器明确为 ConflictProbe 的 superseding 等级；Replay 不直接改 CommonGround。

### v7 → v8

热路径索引策略：阶段边界 + 物化延迟。Projection Index P1 走主表直查，P2 才引入投影；抽取重试以 extraction_span_key 幂等 upsert。

### v6 → v7

防抖与幂等契约：causation_chain ≤ 3、idempotency_key 公式、Reconsolidation 窗口锁追加证据。新增 Outbox checkpoint 与业务幂等。

### v5 → v6

ConsolidationState 冻结为六态；EngramStore retention_mode 合规生命周期（legal_hold / audit_retain / redacted_retain / crypto_erasure）；Statement provenance + review_status 四分类；severe path 原子事务。

### v4 → v5

15 个 v4 架构问题全部修复：三层抽象（逻辑/分区/物理）；EngramStore 提升为独立子系统；REPLAYING 拆为 CONSOLIDATING/RECONSOLIDATING 两子态；状态机补 4 条迁移边；终态事件补全；EpisodicView 定义修正（由"绑时空"区分而非巩固阶段）；Persona/CommonGround 改继承 Container；Entity 类型显式定义（kind 七值）。

### v3 → v4

Statement 6 态状态机；Reconsolidation 章节独立；2026 ICLR/AAAI/EACL 前沿论文整合（含 EverOS HyperMem 三级 hypergraph）。

### v2 → v3

Replay Scheduler 三模式；Prospective Loop 完整章节；Working Set 7 label（+CONFLICT / ABSTAIN）。12 项可施工性缺陷修复，设计本体不变。

### v1 → v2

VAD 三轴 AffectVector；trust_priors 加入 Cognizer；polarity 与 modality 正交；canonical_name + aliases 主体归一；EngramStore 独立 BlobStore；模式分离 MAY_OVERLAP_WITH 软边；CommonGround N 元扩展。Statement 显式 5 态 ConsolidationState；Retrieval 新增 Abstention Gate；路线图从 4 阶段扩为 6 阶段（P1-P3+）。

---

## 术语索引（按子系统）

| 子系统 | 核心术语 |
|---|---|
| Bus | outbox / outbox_sequence / causation_chain / idempotency_key / primary_id / aggregate_id |
| Cognizer | aliases / trust_priors / group tenant / KnowledgeFrontier |
| EngramStore | Engram / EngramRef / content_hash / crypto_erasure / legal_hold / SourceKind |
| Hippocampus | VOLATILE / REPLAYING_CONSOLIDATING |
| Neocortex | CONSOLIDATED / ARCHIVED / FORGOTTEN / REPLAYING_RECONSOLIDATING |
| Replay | decay / salience / replay_derived / statement.decay_candidate |
| Reconsolidation | Reconsolidation / REPLAYING_RECONSOLIDATING / window_bucket |
| Retrieval | RetrievalReceipt / sufficiency_status / perspective_take / profile_anchor |
| Statement | modality / polarity / provenance / review_status / holder / holder_perspective / nesting_depth / derived_from / derived_depth / evidence / SourceSpanRef / TemporalAnchor / tenant_id |
| Substrate | ProfileCapability / RuntimeHealth / ScopedWorkGate / PipelineRun / cross_partition_transaction |
| ToM | Mentalizing Primitives / StatementRef / perspective_take / tom_inferred |
| Prospective | ActionGuard / ActionPolicyGraph / PolicyEngine / commitment.active_holding |
