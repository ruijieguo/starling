# P2.b 第一阶段：无向量脑动力学核心 — 设计规格

**Status**: Draft for review
**Author**: Auto Mode (Subagent-Driven Development)
**Date**: 2026-05-27
**里程碑代号**: M0.8（P2.b 第一阶段）
**Spec source**: `docs/design/system_design.md` §16.3 / `subsystems_design/07_neocortex.md` / `10_replay.md` / `11_reconsolidation.md` / `09_tom.md` §3-5 / `04_substrate.md`（Projection Index）

---

## 0. 命名与 P2.b 拆分说明

roadmap 把 P2.b（类脑动力学，6 周）定为一个里程碑，plan 文件 `p2-b-brain-dynamics.md`。Brainstorming 阶段发现 P2.b 内嵌一个**未建的 embedding/向量/图/logprobs 基础层**（模式分离、模式补全、EM-LLM 事件切分、`idx_vector_payload` 都依赖它），而代码库零向量基础设施。

经评估，向量依赖面很窄（仅 4 个特性），且系统设计上支持无向量 DEGRADED 运行（system_design.md:1777）。因此 P2.b 拆为两阶段：

- **M0.8（本 spec）= 无向量脑动力学核心**：Replay Scheduler、Reconsolidation Engine、Neocortex Persona/CommonGround Container、CommonGround Grounding Acts writer、Projection Index 6/7 SQL 投影。全部基于现有 SQLite + statement 字段，零新基础设施。
- **M0.9（后续单独 spec）= 向量基础层**：embedding adapter + 向量后端（sqlite-vec/seekdb）+ 图后端（PPR）+ LLM logprobs + 模式分离/补全 + EM-LLM 切分 + `idx_vector_payload`。

§16.3 准入硬约束中 -4/-7/-9 + -3/-6 的 SQL 投影部分由 M0.8 覆盖；只有向量投影的 repair test 落在 M0.9。

---

## 1. 目标

M0.8 新建 3 个空子系统 + 扩展 3 个现有子系统，让有代码子系统从 7/12 增到 10/12：

| 工作分块 | 子系统 | 输出 |
|---|---|---|
| **新建 10_replay** | Replay Scheduler | 3 模式（Online tick + Idle/Sleep API）+ 5 巩固操作（compress/abstract/reinforce/decay/reconcile）+ SWR 采样器 + 遗忘曲线 S(t) + 振荡防护 + VOLATILE TTL |
| **新建 11_reconsolidation** | Reconsolidation Engine | Outbox subscriber + 5 触发路径 + 可塑窗口（30min/5min-6h/per-modality/高频缩短）+ 窗口锁 + pending_evidence + 3 仲裁（supports/mild/severe）+ severe 4 项原子提交（仅原子事务，saga 推迟 P3） |
| **新建 07_neocortex** | Neocortex | Personae Container（rebuild + anchor 仲裁 + CAS）+ CommonGround Container 物化（Semantic 复用 P1；Procedural/Norms 推迟） |
| **扩展 09_tom** | CommonGround pool writer | 5 Grounding Acts（Assert/Acknowledge/Repair/Withdraw/SupersedeGround）+ grounded 状态机 + 3 判定规则 + 24h 降级 |
| **扩展 04_substrate** | Projection Index | 6/7 SQL 物化投影（outbox subscriber 异步）+ repair guard（truncation_suspected）；idx_vector_payload 推迟 M0.9 |
| **新建 bus/SubscriberPump** | 05_bus | 统一 post-write 泵，迁入 P2.a 两个 tick + M0.8 三个新 subscriber |

M0.8 关闭门槛：
1. 8 个 admission CRITICAL 全绿（见 §12.2）
2. P1 13 CRITICAL + P2.a 9 CRITICAL 不回归
3. §16.3-4/-7/-9 + -3/-6 SQL 部分满足
4. 现有 TC-NEW-CONFLICT-SEVERE 回归仍过（§16.3-9 兼容性）
5. ci_static_scan clean，pytest/ctest 全绿

---

## 2. 非目标

- **向量/图/logprobs 基础层**：embedding adapter、sqlite-vec/seekdb、PPR、LLM logprobs → M0.9
- **模式分离（反相似偏移）/ 模式补全（PPR）/ EM-LLM 事件切分**：→ M0.9
- **`idx_vector_payload`**（7 个投影中的第 7 个）：→ M0.9
- **Replay induce_norm / forge_skill / purge_compliance**：需 Norms/Procedural 子区 + 合规事件流，→ 后续
- **Neocortex Procedural / Norms 子区**：无 producer（forge_skill/induce_norm 推迟），→ 后续
- **Reconsolidation saga 补偿**：local-store cross_partition_transaction=true 走原子事务；saga 是 dist-store（P3.b）专属
- **Grounding Acts: ExpireGround / Unground / 人工确认**：需 retention/crypto_erasure 联动，→ 后续
- **Hippocampus Working Set / Affect Buffer / EpisodicEvent 切分**：Working Set 渲染是 retrieval 时的事，Affect Buffer 入队依赖 salience（已有字段但完整入队/淘汰策略）→ 评估后置（多数 Hippocampus 核心在 M0.9 向量层）
- **ToMDepthEstimator 真模型 / Prospective Loop / Commitment 五态机**：P2.c 或 P3

---

## 3. 子系统状态变化

### 3.1 M0.8 启动前（P2.a close 后）

| 子系统 | 状态 |
|---|---|
| 04_substrate | ⚠️ 部分（preflight + SQLite adapter；Projection Index 未建） |
| 05_bus | ✅ 有代码 |
| 05_governance | ⚠️ 部分 |
| 06_engramstore | ✅ 有代码 |
| 06_hippocampus | ⛔ 空（VOLATILE 缓冲在 statements 表，核心模式分离/补全 = M0.9） |
| **07_neocortex** | ⛔ 空 → M0.8 新建 |
| 08_cognizer | ✅ 有代码（P2.a） |
| 09_tom | ✅ 有代码（P2.a）；CommonGround writer = M0.8 扩展 |
| **10_replay** | ⛔ 空 → M0.8 新建 |
| **11_reconsolidation** | ⛔ 空 → M0.8 新建 |
| 12_prospective | ⛔ 空（P2.c） |
| 13_retrieval | ✅ 有代码 |

**有代码子系统数**：7/12

### 3.2 M0.8 完成后

| 变化 | 数量 |
|---|---|
| 新建子系统 | 3（07_neocortex, 10_replay, 11_reconsolidation） |
| 扩展现有子系统 | 3（04_substrate Projection Index, 05_bus SubscriberPump, 09_tom CommonGround writer） |
| 完成后有代码子系统数 | **10/12** |
| 仍为空/部分 | 06_hippocampus（向量核心 = M0.9）, 12_prospective（P2.c） |

---

## 4. 架构总览

```
┌─ 10_replay (新) ───────────────────────────────────────────┐
│  ReplayScheduler                                            │
│  • tick_online (Bus.write 后, 每 3 条 statement.written)   │
│  • run_idle() / run_sleep() 显式 API (无后台线程)          │
│  • SWR 采样器: 完整公式, goal_relevance=predicate/subject  │
│    匹配启发式 (无向量)                                     │
│  • 5 操作: compress/abstract/reinforce/decay/reconcile     │
│  • 遗忘曲线 S(t) + 振荡防护(replay_count≥5) + VOLATILE TTL │
│  输出 provenance=replay_derived, emit statement.derived    │
│  (不订阅自己输出 → 闭环断开无重入)                         │
└────────────────┬───────────────────────────────────────────┘
                 │ reconcile → emit belief.conflict
                 ▼
┌─ 11_reconsolidation (新) ──────────────────────────────────┐
│  ReconsolidationEngine (Outbox subscriber)                 │
│  • 5 触发: recalled/references_existing/belief.conflict/   │
│    显式 API/commitment.* (后者 P2.c stub)                  │
│  • 可塑窗口: 30min/5min-6h/per-modality/高频≥3hr→5min      │
│  • 窗口锁(1 stmt 1 窗口) + pending_evidence(100 FIFO,K=10) │
│  • 3 仲裁: supports / mild(confidence+history,prov 不变) / │
│    severe(4 项原子提交, 仅原子事务)                        │
│  • §16.3-9: 不碰 P1 同步 severe path                       │
└────────────────┬───────────────────────────────────────────┘
                 ▼
┌─ 07_neocortex (新) ────────────────────────────────────────┐
│  • Semantic: holder 子图 (P1 已有, 复用)                  │
│  • PersonaContainer: rebuild + self/profile anchor 仲裁 + │
│    dimension 合并 + 单 version CAS                         │
│  • CommonGroundContainer: grounded/asserted_unack/        │
│    suspected_diverge 物化                                  │
│  • Procedural/Norms 推迟                                   │
└────────────────┬───────────────────────────────────────────┘
                 ▼
┌─ 09_tom CommonGround writer (扩展) ────────────────────────┐
│  • 5 Grounding Acts: Assert/Ack/Repair/Withdraw/Supersede  │
│  • grounded 状态机 + 3 判定规则(显式/在场N=3/重复M=2)      │
│  • 24h 超时降级; 动作写 grounding_acts 审计日志            │
└────────────────┬───────────────────────────────────────────┘
                 ▼
┌─ 04_substrate Projection Index (扩展) ─────────────────────┐
│  ProjectionMaintainer (Outbox subscriber)                  │
│  • 6 SQL 物化投影增量更新                                 │
│  • rebuild + repair guard: rebuilt < ground_truth →       │
│    emit projection.rebuild_failed(truncation_suspected),  │
│    保留旧 active (§16.3-3/-6)                              │
│  • idx_vector_payload 推迟 M0.9                            │
└─────────────────────────────────────────────────────────────┘

         所有 subscriber 由 05_bus SubscriberPump 统一驱动:
  Bus::write_impl commit 后 → pump.run_post_write(conn) →
    [conflict_key_backfill, belief_tracker, reconsolidation,
     projection_maintainer, replay_online] 各 SAVEPOINT 隔离
```

---

## 5. Schema delta（5 migrations，无向量列）

### 5.1 migration 0011 — Replay Scheduler

```sql
CREATE TABLE replay_scheduler_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    online_trigger_counter INTEGER NOT NULL DEFAULT 0,
    last_online_run_at TEXT,
    last_idle_run_at TEXT,
    last_sleep_run_at TEXT,
    last_updated_at TEXT NOT NULL
);
INSERT INTO replay_scheduler_state (id, last_updated_at)
    VALUES (1, '2026-05-27T00:00:00Z');

CREATE TABLE replay_ledger (
    replay_batch_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('online','idle','sleep')),
    sampled_count INTEGER NOT NULL DEFAULT 0,
    ops_applied_json TEXT NOT NULL DEFAULT '{}',  -- {compress:N, abstract:N, ...}
    started_at TEXT NOT NULL,
    finished_at TEXT
);

ALTER TABLE statements ADD COLUMN last_replay_batch_id TEXT;  -- 采样归属(spec §1 要求)
```

> S(t) 遗忘曲线、SWR 采样权重全部从现有字段（salience/access_count/last_accessed/affect_json/modality/replay_count）即时计算，零新列。

### 5.2 migration 0012 — Reconsolidation

```sql
CREATE TABLE reconsolidation_windows (
    stmt_id TEXT PRIMARY KEY,            -- 窗口锁: 一个 stmt 同时只一个活跃窗口
    tenant_id TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    close_deadline TEXT NOT NULL,        -- opened_at + adaptive_timeout
    trigger_event_ids_json TEXT NOT NULL DEFAULT '[]',
    force_close_trigger_count INTEGER NOT NULL DEFAULT 0,
    evicted_count INTEGER NOT NULL DEFAULT 0,
    evicted_summary_hashes_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed'))
);
CREATE INDEX idx_recon_windows_deadline
    ON reconsolidation_windows(status, close_deadline);

CREATE TABLE reconsolidation_pending_evidence (
    id TEXT PRIMARY KEY,
    window_stmt_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_stmt_id TEXT,
    payload_hash TEXT NOT NULL,          -- 证据摘要 hash, 不存原 payload
    weight REAL NOT NULL DEFAULT 1.0,
    arrived_at TEXT NOT NULL
);
CREATE INDEX idx_recon_evidence_window
    ON reconsolidation_pending_evidence(window_stmt_id, arrived_at);

CREATE TABLE reconsolidation_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO reconsolidation_checkpoint (id, last_updated_at)
    VALUES (1, '2026-05-27T00:00:00Z');
```

> `confidence_history_json` 已在 statements（mild correction 追加写）。`replaying_reconsolidating` 是 consolidation_state 新枚举值，仅加 C++ `schema::to_string` + `consolidation_state_from_string`，statements.consolidation_state 无 CHECK 约束 → 零 schema 改动。

### 5.3 migration 0013 — Neocortex Persona/CommonGround Container

```sql
ALTER TABLE containers ADD COLUMN content_json TEXT NOT NULL DEFAULT '{}';
-- 物化的 Persona dimensions + self_model_anchor/profile_anchor +
-- CommonGround dimensions。CAS 用现有 containers.version 列。
```

> Personae/CommonGround Container 复用现有 `containers` 表（kind 已含 'persona'/'common_ground'），只补一个 payload 列。holder 子图（Semantic）P1 已有，零改动。

### 5.4 migration 0014 — CommonGround Grounding Acts

```sql
CREATE TABLE grounding_acts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    common_ground_id TEXT NOT NULL,
    act TEXT NOT NULL CHECK (act IN
        ('assert','acknowledge','repair','withdraw','supersede')),
    actor_cognizer_id TEXT,
    statement_id TEXT,
    occurred_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_grounding_acts_cg
    ON grounding_acts(tenant_id, common_ground_id, occurred_at);

ALTER TABLE common_ground ADD COLUMN establishment_evidence_json TEXT NOT NULL DEFAULT '[]';
```

> P2.a 的 `common_ground` 表 status 枚举（asserted_unack/grounded/suspected_diverge/expired/recanted）已覆盖 5 动作的状态机目标，M0.8 只补 writer + 动作审计日志。

### 5.5 migration 0015 — Projection Index（6 SQL 物化投影）

```sql
-- 6 个去规范化物化表, 由 outbox subscriber 异步维护
CREATE TABLE proj_holder_state_time (
    tenant_id TEXT NOT NULL, holder_id TEXT NOT NULL,
    consolidation_state TEXT NOT NULL, observed_at TEXT NOT NULL,
    stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, holder_id, stmt_id)
);
CREATE TABLE proj_holder_subgraph (
    tenant_id TEXT NOT NULL, holder_id TEXT NOT NULL,
    subject_kind TEXT NOT NULL, subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, holder_id, stmt_id)
);
CREATE TABLE proj_entity_statement (
    tenant_id TEXT NOT NULL, subject_kind TEXT NOT NULL,
    subject_id TEXT NOT NULL, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, subject_kind, subject_id, stmt_id)
);
CREATE TABLE proj_salience_hot (
    tenant_id TEXT NOT NULL, salience REAL NOT NULL,
    stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, stmt_id)
);
CREATE INDEX idx_proj_salience ON proj_salience_hot(tenant_id, salience DESC);
CREATE TABLE proj_commitment_due (
    tenant_id TEXT NOT NULL, due_at TEXT, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, stmt_id)
);
CREATE INDEX idx_proj_commitment ON proj_commitment_due(tenant_id, due_at);
CREATE TABLE proj_common_ground (
    tenant_id TEXT NOT NULL, common_ground_id TEXT NOT NULL,
    status TEXT NOT NULL, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, common_ground_id, stmt_id)
);

-- repair guard 状态 (§16.3-3/-6)
CREATE TABLE projection_rebuild_state (
    projection_name TEXT PRIMARY KEY,
    ground_truth_count INTEGER NOT NULL DEFAULT 0,
    index_count INTEGER NOT NULL DEFAULT 0,
    last_rebuilt_at TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','truncation_suspected'))
);

CREATE TABLE projection_subscriber_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO projection_subscriber_checkpoint (id, last_updated_at)
    VALUES (1, '2026-05-27T00:00:00Z');
```

> **为什么是物化表不是 SQL 索引**：repair guard 要比对 "SQLite ground truth vs index count"，在 rebuild 抽取 < ground truth 时 emit `projection.rebuild_failed(truncation_suspected)` 并保留旧 active projection 不替换。SQL 索引由 SQLite 事务内维护、不漂移，无法触发 truncation；只有异步物化表会漂移 → 才需 repair guard。

---

## 6. 子系统 1：10_replay

### 6.1 文件清单

```
include/starling/replay/
  replay_scheduler.hpp        # ReplayScheduler 类 + ReplayStats / ReplayMode
  swr_sampler.hpp             # sample_weight + eligible-set 过滤
  forgetting_curve.hpp        # compute_s_t + S0 五因子
  consolidation_ops.hpp       # 5 op + ConsolidationOp 枚举
src/replay/
  replay_scheduler.cpp        # tick_online / run_idle / run_sleep
  swr_sampler.cpp
  forgetting_curve.cpp
  consolidation_ops.cpp
```

### 6.2 ReplayScheduler

```cpp
namespace starling::replay {

enum class ReplayMode { Online, Idle, Sleep };

struct ReplayStats {
    int sampled = 0, compressed = 0, abstracted = 0,
        reinforced = 0, decayed = 0, reconciled = 0;
    std::string replay_batch_id;
};

class ReplayScheduler {
public:
    ReplayScheduler(persistence::SqliteAdapter& adapter);
    // Online: Bus.write commit 后调用 (SubscriberPump). 内部 online_trigger_counter+1,
    // 达 N=3 时跑一次采样窗口 (批 1-3), 否则立即返回.
    void tick_online(persistence::Connection& conn);
    // Idle/Sleep: 显式 API, 无后台线程.
    ReplayStats run_idle(persistence::Connection& conn);    // 批 10-30
    ReplayStats run_sleep(persistence::Connection& conn);   // 完整 sweep, bounded batch
};

}  // namespace
```

### 6.3 SWR 采样器（`swr_sampler.cpp`）

```cpp
// 完整公式 (spec 10_replay.md §核心算法 1):
double sample_weight(const StatementRow& s, const GoalContext& goal) {
    return s.salience
        * novelty_decay(s.last_replayed)
        * (s.has_conflict ? (1 + kConflictBonus) : 1.0)
        * (1 + kArousalBonus * affect_arousal(s.affect_json))
        * goal_relevance(s, goal)                  // predicate/subject 匹配 0/1 启发式 (无向量)
        * provenance_factor(s.provenance)
        / (1 + s.replay_count);
}
// provenance_factor: user_input=1.0, tom_inferred=0.25,
//                    replay_derived/reconsolidation_derived=0 (不进池)
// eligible set: 只含 statement.written 写入的 user_input + 可落库 tom_inferred;
//   last_replayed < T_cooldown=5min → 权重 0 (除非 belief.conflict/compliance);
//   derived_depth >= 3 → 不作自动派生输入.
// w_min=0.01 跳过; w_max=p95 截断; 无放回采样.
```

### 6.4 遗忘曲线（`forgetting_curve.cpp`）

```cpp
// S(t) = exp(-Δt / S0(stmt))
// S0 = base × (1+0.5×access_count) × (1+salience) × (1+2×active_grounded)
//        × decay_modifier_by_modality × (1+0.3×|affect.valence|)
// 状态迁移: S(t)<0.05 AND not active_grounded → CONSOLIDATED→ARCHIVED
// active_grounded: 仅 CommonGround 中未 expired/superseded/ungrounded 条目为 1.
```

### 6.5 5 巩固操作（`consolidation_ops.cpp`）

| op | 输入 | 输出 provenance/review | 状态迁移 |
|---|---|---|---|
| compress | 多条相似 EpisodicEvent（同 holder+predicate+canonical_object_hash） | replay_derived/APPROVED | 输入 VOLATILE→CONSOLIDATED |
| abstract | 多 holder 同 predicate | replay_derived/PENDING_REVIEW → Neocortex candidate（喂 Persona rebuild） | 候选 |
| reinforce | 高 salience 短链 | 提升 access_count/S0 | VOLATILE→CONSOLIDATED |
| decay | S(t)<0.05 且 not active_grounded | emit statement.archived | CONSOLIDATED→ARCHIVED |
| reconcile | 冲突集 | emit belief.conflict → Reconsolidation | CONSOLIDATED→REPLAYING_RECONSOLIDATING |

所有 replay_derived 输出经 Bus.write，emit `statement.derived`（非 statement.written），不重入 Replay。

**振荡防护**：replay_count≥5 → 强制 CONSOLIDATED + PENDING_REVIEW + emit statement.consolidation_forced。
**VOLATILE TTL**：写入 >7天 且不在 Affect Buffer → ARCHIVED(volatile_ttl_exceeded)。
**decay 串行**：emit statement.decay_candidate，Bus dispatcher per-stmt 串行投递，后到读到 state 已变即跳过（消除 T5/T8 竞争）。

### 6.6 错误类型

```cpp
class ReplayBatchError : public std::runtime_error { ... };  // 单批次失败, 不污染主写入
```

---

## 7. 子系统 2：11_reconsolidation

### 7.1 文件清单

```
include/starling/reconsolidation/
  reconsolidation_engine.hpp  # Engine 类 (subscriber) + TriggerPath 枚举
  plastic_window.hpp          # PlasticWindow + 自适应超时 + pending_evidence
  arbitration.hpp             # 3 仲裁结果 + aggregate_evidence
src/reconsolidation/
  reconsolidation_engine.cpp  # tick_one_batch + close_due_windows + reconsolidate
  plastic_window.cpp
  arbitration.cpp
```

### 7.2 ReconsolidationEngine

```cpp
namespace starling::reconsolidation {

class ReconsolidationEngine {  // Outbox subscriber, tick-driven
public:
    ReconsolidationEngine(persistence::SqliteAdapter& adapter);
    // 消费 last_checkpoint+1.. 的 outbox 事件 → 开/追加可塑窗口
    TrackerStats tick_one_batch(persistence::Connection& conn);
    // 仲裁所有超时窗口 (close_deadline <= now). 由 SubscriberPump 在 tick 后调用.
    int close_due_windows(persistence::Connection& conn, std::string_view now_iso);
    // 显式 API (5 触发路径之一: audit/用户编辑)
    void reconsolidate(persistence::Connection& conn, std::string_view stmt_id,
                       const Evidence& ev);
};

}  // namespace
```

**5 触发路径**（异步）：statement.recalled / statement.references_existing / belief.conflict / 显式 API / commitment.fulfilled|broken（commitment.* P2.c 才 emit，handler 留 stub）。

**窗口锁**：`reconsolidation_windows.stmt_id` PK；重复触发只追加 pending_evidence（防抖）。

**自适应超时**（§16.3-4 全实现）：默认 30min，clamp [5min, 6h]，per-modality config 覆写，高频 ≥3/hr → 强制 5min。pending_evidence 100 FIFO + K=10 强制 close。

### 7.3 3 仲裁（`arbitration.cpp`）

```cpp
// aggregate_evidence: 取最近 50 条高权重证据 + 其余作低权重背景统计
ArbitrationResult arbitrate(const PlasticWindow& w, const StatementRow& stmt);
// supports → confidence 贝叶斯上调 → CONSOLIDATED → emit statement.consolidated
// mild contradict → confidence 下调 + 追加 confidence_history, provenance 不变
//                 → CONSOLIDATED → emit statement.consolidated (不 emit corrected)
// severe contradict → 4 项原子提交 (见下)
```

**severe path 4 项原子提交**（仅原子事务，saga 推迟 P3）：
1. 新版 Statement（provenance=reconsolidation_derived, CONSOLIDATED）
2. SUPERSEDES 边（新版→旧版）
3. 旧版 ARCHIVED
4. emit statement.corrected + archived + superseded（同 outbox batch）

新版不走 tom_inferred、不进 VOLATILE、不 emit statement.written（防重入 Replay）。

**§16.3-9 兼容**：Engine 只接管 partial_overlap/adjacent/mild correction 异步语义；Bus.write 里 P1 的 direct_contradiction/superseding 同步 ConflictProbe 路径**不动**。验收：TC-NEW-CONFLICT-SEVERE 回归仍过。

### 7.4 错误类型

```cpp
class WindowLockConflict : public std::runtime_error { ... };  // 不应发生(PK 保证), 防御
class ArbitrationFailed : public std::runtime_error { ... };   // TC-A5-002 双层兜底
```

---

## 8. 子系统 3：07_neocortex

### 8.1 文件清单

```
include/starling/neocortex/
  persona_container.hpp       # PersonaContainer + dimension/anchor 类型
  common_ground_container.hpp # CommonGroundContainer 物化
src/neocortex/
  persona_container.cpp
  common_ground_container.cpp
```

### 8.2 PersonaContainer

```cpp
class PersonaContainer {
public:
    PersonaContainer(persistence::SqliteAdapter& adapter);
    // Replay abstract op 产出 + anchor 集合 → 物化 Persona. CAS on containers.version.
    void rebuild(persistence::Connection& conn, std::string_view tenant_id,
                 std::string_view holder_id, const std::vector<AnchorStatement>& sources);
private:
    // self_model_anchor (holder=X, subject=X) 优先于 profile_anchor (holder≠X, subject=X);
    // 多源 profile 与自陈冲突 severity >= DIVERGE_THRESHOLD →
    //   dimension.suspected_diverge=true + emit 给 ToM 仲裁, 暂不写该 dimension.
};
```

存储：`containers.content_json`（dimensions: traits/preferences/competencies/values + self_model_anchor/profile_anchor + relationship_styles）。CAS 用 `containers.version`，并发 rebuild 冲突 → `ConcurrentRebuildError`。

### 8.3 CommonGroundContainer

```cpp
class CommonGroundContainer {
    void rebuild(persistence::Connection& conn, std::string_view tenant_id,
                 std::string_view cg_ref, const std::vector<Statement>& sources);
    // 物化 grounded/asserted_unack/suspected_diverge dimensions 到 containers.content_json
};
```

Semantic 子区（holder 子图）P1 已有，复用 `basic_retriever` 的 holder 路由。Procedural/Norms 子区推迟。

### 8.4 错误类型

```cpp
class ConcurrentRebuildError : public std::runtime_error { ... };  // CAS version 失配
```

---

## 9. 子系统 4：09_tom CommonGround Grounding Acts writer

### 9.1 文件清单

```
include/starling/tom/common_ground_writer.hpp   # 扩展 P2.a 只读 common_ground.hpp
src/tom/common_ground_writer.cpp
```

### 9.2 CommonGroundWriter

```cpp
class CommonGroundWriter {
public:
    CommonGroundWriter(persistence::SqliteAdapter& adapter);
    std::string assert_(conn, tenant, stmt_id, parties);   // → asserted_unack, 返回 cg_id
    void acknowledge(conn, cg_id, actor);                  // 显式确认 → grounded
    void repair(conn, cg_id, actor);                       // 质疑 → suspected_diverge
    void withdraw(conn, cg_id, actor);                     // 撤回 → recanted
    void supersede_ground(conn, old_cg_id, new_stmt_id);   // 新共识覆盖旧
    // 每动作写 grounding_acts 审计日志.
    // grounded 自动判定 (在 acknowledge / tick 时评估):
    //   ① 显式确认 ② 共同在场推定(perceived_by 覆盖全 parties + 后续 N=3 轮无 Repair/Withdraw)
    //   ③ 重复确认(同 canonical 等价 stmt 被不同 parties 成员独立提及 ≥ M=2 次)
    // 超时降级: asserted_unack > T=24h 无 Ack/Repair → suspected_diverge.
};
```

ExpireGround/Unground/人工确认推迟（需 retention/crypto_erasure 联动）。

---

## 10. 子系统 5：04_substrate Projection Index

### 10.1 文件清单

```
include/starling/projection/projection_maintainer.hpp
src/projection/projection_maintainer.cpp
```

### 10.2 ProjectionMaintainer

```cpp
class ProjectionMaintainer {  // Outbox subscriber
public:
    ProjectionMaintainer(persistence::SqliteAdapter& adapter);
    // 消费 statement.written/derived/archived/consolidated → 增量更新 6 投影表
    TrackerStats tick_one_batch(persistence::Connection& conn);
    // 全量 rebuild + repair guard
    RebuildReport rebuild_projection(persistence::Connection& conn,
                                     std::string_view projection_name);
};

struct RebuildReport {
    std::string projection_name;
    int64_t ground_truth_count;
    int64_t rebuilt_count;
    bool truncation_suspected;   // rebuilt < ground_truth
};
```

**repair guard (§16.3-3/-6)**：rebuild 时先数主表 ground truth（符合该投影条件的 statement 行数），再数 rebuilt 临时表行数。若 rebuilt < ground_truth → emit `projection.rebuild_failed(truncation_suspected)`、写 `projection_rebuild_state.status='truncation_suspected'`、**保留旧 active projection 表不替换**。否则原子替换 active。

6 投影：idx_vector_payload 推迟 M0.9。

---

## 11. 05_bus SubscriberPump（统一 post-write 泵）

### 11.1 设计

```cpp
namespace starling::bus {

class SubscriberPump {
public:
    // Bus::write_impl commit 后调用一次. 按固定顺序跑所有 subscriber,
    // 每个 SAVEPOINT 隔离 — 单 subscriber 失败回滚自身, 不影响主写入或其他 subscriber.
    void run_post_write(persistence::SqliteAdapter& adapter,
                        persistence::Connection& conn,
                        cognizer::CognizerHub& hub,
                        cognizer::KnowledgeFrontier& frontier);
private:
    // 固定顺序:
    //  1. conflict_key_backfill::tick_one_batch   (P2.a, 迁入)
    //  2. belief_tracker::tick_one_batch          (P2.a, 迁入)
    //  3. reconsolidation::tick_one_batch + close_due_windows  (M0.8 新)
    //  4. projection_maintainer::tick_one_batch   (M0.8 新)
    //  5. replay_scheduler::tick_online           (M0.8 新)
};

}  // namespace
```

### 11.2 迁移影响

P2.a 的 `Bus::write_impl` commit 后直接调 `conflict_key_backfill::tick` + `belief_tracker::tick`。M0.8 改为调 `pump.run_post_write(...)`，两个旧 tick 迁进泵的步骤 1-2。**P2.a 的 belief_tracker / conflict_key_backfill 测试必须仍过**（行为不变，仅调用点改变）。

每个 subscriber 用独立 SAVEPOINT（`SAVEPOINT sub_N; ...; RELEASE` 或 `ROLLBACK TO`），失败只回滚该 subscriber 的工作。

---

## 12. 测试策略

### 12.1 §16.3 准入硬约束覆盖

| §16.3 | 要求 | 验收 |
|---|---|---|
| -3 | Projection repair safety（truncation_suspected + 不替换） | TC-PROJECTION-REPAIR |
| -4 | 可塑窗口 30min/5min-6h/per-modality/高频→5min | TC-RECONSOLIDATION-WINDOW（roll-up）|
| -6 | Projection Index repair guard | TC-PROJECTION-REPAIR |
| -7 | Replay 状态机 TC-A1/A5/A6 + TC-A8-001 | 6 CRITICAL |
| -9 | Reconsolidation 不改 P1 同步 path | TC-NEW-CONFLICT-SEVERE 回归（现有，不新增）|

### 12.2 8 个 admission CRITICAL

| ID | 子系统 | 文件 | 验证 |
|---|---|---|---|
| TC-A1-001 | replay | `tests/python/test_tc_a1_001.py` | replay_count≥5 → 强制 CONSOLIDATED+PENDING_REVIEW + emit consolidation_forced |
| TC-A1-002 | replay | `tests/python/test_tc_a1_002.py` | VOLATILE >7天 不在 Affect Buffer → ARCHIVED(volatile_ttl_exceeded) |
| TC-A5-001 | reconsolidation | `tests/python/test_tc_a5_001.py` | 可塑窗口 close_deadline 到 → 强制 close + 仲裁 |
| TC-A5-002 | reconsolidation | `tests/python/test_tc_a5_002.py` | 仲裁自身失败 → 窗口仍 close，stmt 回 CONSOLIDATED 不卡死 |
| TC-A6-001 | replay | `tests/python/test_tc_a6_001.py` | decay_candidate per-stmt 串行；后到读到 state 已变 → 跳过 |
| TC-A6-002 | replay | `tests/python/test_tc_a6_002.py` | T8 outbox 串行：同 stmt 多 decay 不并发迁移 |
| TC-A8-001 | reconsolidation | `tests/python/test_tc_a8_001.py` | 异步仲裁 severe 4 项原子提交，与同步 TC-NEW-CONFLICT-SEVERE 互补 |
| TC-PROJECTION-REPAIR | projection | `tests/python/test_tc_projection_repair.py` | rebuilt < ground_truth → truncation_suspected + 旧 active 不替换 |

### 12.3 non-CRITICAL roll-up

`test_replay_ops`（5 op 各路径）/ `test_swr_sampler`（完整公式 + provenance_factor + 截断）/ `test_forgetting_curve`（S(t) + S0 五因子）/ `test_reconsolidation_window_config`（§16.3-4 细节）/ `test_reconsolidation_arbitration`（3 路径，mild provenance 不变）/ `test_persona_anchor_arbitration`（self vs profile + suspected_diverge）/ `test_grounding_acts`（5 动作 + grounded 3 规则 + 24h 降级）/ `test_projection_incremental`（6 投影增量 + checkpoint 恢复）/ `test_subscriber_pump`（5 subscriber 顺序 + SAVEPOINT 隔离）。

### 12.4 P1/P2.a 回归保护

每次 CI：ctest 361/361 + pytest 418/13 + ci_static_scan。SubscriberPump 迁移后 belief_tracker/conflict_key_backfill 测试仍过；`replaying_reconsolidating` 枚举不破坏现有。

---

## 13. 错误与不变量

### 13.1 不变量清单

| 不变量 | 实现位置 | 检查时机 |
|---|---|---|
| Replay 输出 emit statement.derived（非 written），不重入 | consolidation_ops | 写入时 |
| replay_count≥5 → 强制 CONSOLIDATED | replay_scheduler 振荡防护 | tick |
| 一个 stmt 同时只一个活跃可塑窗口 | reconsolidation_windows.stmt_id PK | 开窗时 |
| mild correction provenance 不变 | arbitration mild 路径 | 仲裁时 |
| severe path 4 项同事务原子（缺一不可） | arbitration severe 路径 TransactionGuard | 仲裁时 |
| P1 同步 ConflictProbe severe path 不被 Reconsolidation 修改 | Engine 只接管 3 类异步语义 | 静态 + TC-NEW-CONFLICT-SEVERE 回归 |
| Projection rebuilt < ground_truth → 不替换 active | projection_maintainer repair guard | rebuild 时 |
| 每 subscriber SAVEPOINT 隔离，失败不影响主写入 | SubscriberPump | post-write |
| 所有 singleton 状态表 CHECK(id=1) | 各 migration | DB 层 |

### 13.2 错误类型汇总

| 类型 | 来源 | 触发 |
|---|---|---|
| `replay::ReplayBatchError` | replay_scheduler | 单批次失败 |
| `reconsolidation::WindowLockConflict` | reconsolidation_engine | 窗口锁冲突（防御，PK 保证不应发生） |
| `reconsolidation::ArbitrationFailed` | arbitration | 仲裁异常（TC-A5-002 双层兜底） |
| `neocortex::ConcurrentRebuildError` | persona_container | CAS version 失配 |

---

## 14. 实施顺序约束

1. **必须先于其他**：migrations 0011-0015（schema）
2. **`replaying_reconsolidating` 枚举**（C++ schema::to_string）先于 Reconsolidation 代码
3. **10_replay 与 11_reconsolidation 可部分并行**，但 reconcile op（Replay）emit belief.conflict → Reconsolidation 消费，二者集成测试需双方就绪
4. **07_neocortex Persona rebuild 依赖 Replay abstract op 输出**（candidate）→ abstract 先于 Persona 集成
5. **09_tom CommonGround writer 与 active_grounded**（Replay decay 保护）联动 → CommonGround writer 先于 decay 的 active_grounded 判定
6. **SubscriberPump 在所有 subscriber 就绪后引入**，迁移 P2.a 两个 tick（迁移后 P2.a 测试须立即回归通过）
7. **8 CRITICAL 在对应子系统完成后立即写**，不堆到最后
8. **Projection Index（04_substrate）独立**，可与其他并行

---

## 15. §16.3 P2 准入对照（M0.8 部分）

| 项 | M0.8 后状态 |
|---|---|
| §16.3-1 ProfileCapability | P2.a 已满足 ✅ |
| §16.3-2 ToMBench + FANToM | P2.a 已满足 ✅ |
| §16.3-3 Projection repair safety | ProjectionMaintainer repair guard ✅ |
| §16.3-4 可塑窗口配置 | ReconsolidationEngine 全实现 ✅ |
| §16.3-5 CONFLICTS_WITH 唯一性 | P2.a 已满足 ✅ |
| §16.3-6 Projection repair guard | 同 -3 ✅ |
| §16.3-7 Replay 状态机 | 6 CRITICAL（TC-A1/A5/A6 + TC-A8-001）✅ |
| §16.3-8 Commitment 契约 | P2.c（不在 M0.8） |
| §16.3-9 Reconsolidation 兼容性 | 不改 P1 同步 path；TC-NEW-CONFLICT-SEVERE 回归 ✅ |
| §16.3-10 评测加载 | P2.a 已满足 ✅ |

M0.8 直接覆盖 §16.3 的 -3/-4/-6/-7/-9。-8 是 P2.c。idx_vector_payload 的 repair（-3/-6 向量部分）在 M0.9。

---

## 16. 工作量与风险

### 16.1 代码量预估

| 块 | LOC |
|---|---|
| 10_replay C++ | ~1600 |
| 11_reconsolidation C++ | ~1400 |
| 07_neocortex C++ | ~700 |
| 09_tom CommonGround writer | ~500 |
| 04_substrate Projection | ~900 |
| 05_bus SubscriberPump | ~250 |
| Migrations | ~280 SQL |
| Python wrappers | ~600 |
| Tests | ~2600 |

**Production code**: ~5400；**Tests**: ~2600。约等于 P2.a 规模。

### 16.2 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| SubscriberPump 迁移 P2.a 两个 tick 引入回归 | 中 | 迁移后立即跑 P2.a belief_tracker/conflict_key_backfill 测试；行为不变只改调用点 |
| Replay reconcile → Reconsolidation 异步集成时序难测 | 中 | tick-driven 模型确定性强；测试用显式 tick + close_due_windows 顺序断言 |
| 5 subscriber 串行拖慢 Bus.write | 中 | 每 subscriber SAVEPOINT + bounded batch；perf 基准 ≤ 100ms/write |
| Persona rebuild 依赖 abstract op，abstract 质量不稳 | 低 | abstract 产 PENDING_REVIEW candidate，不直接落 Persona；rebuild 时再仲裁 |
| §16.3-4 高频检测（≥3/hr）边界 | 低 | 用 reconsolidation_windows 触发计数 + 时间窗 SQL 判定 |
| `replaying_reconsolidating` 新状态破坏现有查询 | 中 | basic_retrieve 的 consolidation_state IN ('consolidated','archived') 不含新态；新态仅 Reconsolidation 内部短暂 |

---

## 17. 元数据

- **里程碑代号**: M0.8（P2.b 第一阶段，无向量脑动力学核心）
- **roadmap 行**: P2.b（第 71-72 行）；M0.8 覆盖其非向量部分，M0.9 覆盖向量部分
- **预估周期**: ~3 周
- **分支策略**: worktree-m0-8-brain-dynamics 隔离 worktree，--no-ff 合并 main
- **依赖**: P2.a close（commit 50030d6 + 后续）
- **后继**: M0.9（向量基础层）→ 然后 P2.c（Prospective/Affect）

---

## 18. 修订记录

- **2026-05-27 v1**: 初版 spec。基于 brainstorming 阶段 8 个 scope 决策 + SubscriberPump 决策 + Section A-D 逐段确认。P2.b 拆为 M0.8（无向量核心，本 spec）+ M0.9（向量层）。
