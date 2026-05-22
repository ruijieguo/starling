# Replay Scheduler

## 功能定义

Replay Scheduler 负责将 VOLATILE Statement 巩固到 CONSOLIDATED，并对长期记忆执行衰减、抽象、规则归纳、技能锻造。触发模式分三种：Online（在线）、Idle（空闲）、Sleep（深度）。它只经事件总线 emit `statement.decay_candidate`，不直接修改 state，与 [Reconsolidation Engine](v20_11_reconsolidation.md) 严格分工。

---

## 输入

- statement.written 事件流（Online 模式触发器）
- 空转信号（Idle 模式触发器，agent 无对话 ≥ 120s）
- Sleep 信号（每会话结束 / 每日 / 显式 /sleep）
- Affect Buffer 优先级队列（高 salience 候选）
- statement.decay_candidate 事件（per-stmt 顺序串行处理）

## 输出

- 巩固原子操作产出（compress / abstract / reconcile / induce_norm / forge_skill 产物 Statement，provenance=replay_derived，emit statement.derived 而非 statement.written）
- decay 决策（emit statement.archived 当 S(t)<0.05 且 not active_grounded）
- 振荡防护事件（statement.consolidation_forced 当 replay_count ≥ MAX_CONSOLIDATION_ATTEMPTS）
- VOLATILE TTL 兜底（statement.archived(volatile_ttl_exceeded)）

---

## 主要流程

### 1. Online 模式

```
每 N=3 条 statement.written
  → Online 采样窗口（批量 1-3 条）
  → 优先级采样器筛选高 salience 短链
  → 执行巩固原子操作
  → VOLATILE → CONSOLIDATED
  → emit statement.consolidated
```

适用场景：会话进行中即时巩固，防止短链过期丢失。

### 2. Idle 模式

```
Agent 空转 > T=120s 或用户离开
  → Idle 采样窗口（批量 10-30 条）
  → 中等强度反思：abstract / induce_norm 等操作优先
  → 巩固候选写 Neocortex candidate index
```

### 3. Sleep 模式

```
每会话结束 / 每日 / 显式 /sleep
  → 完整 sweep（分区 bounded batch 提交）
  → abstract → Persona Container rebuild（Bus.rebuild_container）
  → forge_skill / induce_norm 候选统一提交
  → purge_compliance 传播到 derived 链
```

### 4. 巩固原子操作流程

```
candidate Statement（eligible set 中）
  → 优先级采样器输出排序列表
  → 选择原子操作（见下表）
  → Bus.write(provenance=replay_derived, review_status=...)
      → 若该条目进入 CONSOLIDATED，则同时 emit statement.consolidated（生命周期信号）
      → emit statement.derived（非 statement.written）
      → Replay Scheduler 不订阅 statement.derived
          ← 闭环断开，无重入
```

原子操作集：

| 操作 | 输入 | 输出 provenance / review_status | 状态迁移 | 触发再 Replay |
|---|---|---|---|---|
| `compress` | 多条相似 EpisodicEvent | `replay_derived / APPROVED` | 输入 VOLATILE→CONSOLIDATED；输出 CONSOLIDATED | 否（propagate=True 时级联） |
| `abstract` | 多 holder 同 predicate | `replay_derived / PENDING_REVIEW` | 候选入 Neocortex candidate index；Persona 经 Bus.rebuild_container 物化 | 否 |
| `reconcile` | 冲突 Statement 集 | 推入 [Reconsolidation Engine](v20_11_reconsolidation.md) | 输入：CONSOLIDATED → REPLAYING_RECONSOLIDATING | — |
| `induce_norm` | 多次 PREFERS/COMMITS 同模式 | `replay_derived / PENDING_REVIEW` | 候选入 Neocortex candidate index | 否 |
| `forge_skill` | 多次成功 Case 集群 | `replay_derived / PENDING_REVIEW` | 同 induce_norm | 否 |
| `decay` | 低 salience 长未召回 | — | CONSOLIDATED → ARCHIVED（emit `statement.archived`） | — |
| `purge_compliance` | 用户撤回 / 法务事件 | — | CONSOLIDATED / ARCHIVED → FORGOTTEN（emit `statement.forgotten`）；传播到无独立证据的直接 derived 链 | — |

所有 `replay_derived` 输出经 Bus.write 写入 Neocortex 正式索引或 candidate index，emit `statement.derived`，不 emit `statement.written`，不重入 Replay。

### 5. decay 流程

```
Replay 识别低 S(t) Statement
  → emit statement.decay_candidate
  → Bus dispatcher per-stmt 顺序串行投递
      → 后到事件读到 state 已变 → 跳过（消除 T5/T8 竞争）
  → S(t) < 0.05 AND not active_grounded
      → CONSOLIDATED → ARCHIVED
      → emit statement.archived
```

串行投递保证：同一 stmt_id 的 decay 事件不并发执行，避免多次 state 迁移覆盖。

### 6. 振荡防护

```
stmt.replay_count ≥ MAX_CONSOLIDATION_ATTEMPTS=5
  → 强制 consolidation_state = CONSOLIDATED
  → review_status = PENDING_REVIEW
  → emit statement.consolidation_forced
```

防止同一 Statement 在 VOLATILE / REPLAYING 之间反复振荡。

### 7. VOLATILE TTL 兜底

```
consolidation_state = VOLATILE
  AND 写入距今 > T_max_volatile=7 天
  AND not in Affect Buffer
    → 自动迁移 → ARCHIVED
```

不依赖 Replay 调度，由 TTL 后台任务兜底清理。

---

## 核心算法

### 1. 优先级采样器（SWR 风格）

借鉴 Prioritized Experience Replay（Schaul et al. 2015），完整公式：

```python
def sample_weight(stmt):
    return (
        stmt.salience
        * novelty_decay(stmt.last_replayed)
        * (1 + conflict_bonus if stmt.has_conflict else 1)
        * (1 + arousal_bonus * stmt.affect.arousal)
        * goal_relevance(stmt, current_goal)
        * provenance_factor(stmt.provenance)
        / (1 + stmt.replay_count)
    )
```

**provenance_factor 取值表**：

| provenance | factor |
|---|---|
| `user_input` | 1.0 |
| `tom_inferred` | 0.25 |
| `replay_derived` | 0（不进采样池） |
| `reconsolidation_derived` | 0（不进采样池） |

**Eligible set 过滤规则**：

- 只含经 `statement.written` 写入的 `user_input` 与可落库 `tom_inferred` Statement。
- `replay_derived` / `reconsolidation_derived` 不进入候选，不以权重 0 参与抽样。
- `last_replayed` 距今 < `T_cooldown=5 分钟` → 权重置零，除非存在 `belief.conflict` 或 compliance 事件。
- `derived_depth >= 3` → 不作自动派生输入，只允许显式 audit/review 路径处理。

**批量与截断契约**：

- 批量大小：Online 1-3 条，Idle 10-30 条，Sleep 按分区 sweep 但每批仍 bounded。
- 低于 `w_min`（默认 0.01）的 Statement 跳过。
- 超过 `w_max`（默认 p95 或配置上限）的 weight 截断，防止单条高 salience Statement 垄断采样。
- 同一窗口内无放回采样，同一 Statement 不重复重放。
- 每次采样结果写 `replay_count / last_replayed / replay_batch_id`。

### 2. 自适应遗忘公式

借鉴 MemoryBank（Ebbinghaus）+ Anderson active forgetting：

```
S(t) = exp(-Δt / S0(stmt))

S0(stmt) = base
         × (1 + 0.5 × access_count)
         × (1 + salience)
         × (1 + 2 × active_grounded)
         × decay_modifier_by_modality
         × (1 + 0.3 × |affect.valence|)
```

**各因子含义**：

| 因子 | 作用 |
|---|---|
| `access_count` | 被检索越多衰减越慢 |
| `salience` | 显著性高的条目衰减慢 |
| `active_grounded` | 未过时共识保护，置 1 则衰减极慢 |
| `decay_modifier_by_modality` | COMMITS 极慢，ASSUMES 快 |
| `\|affect.valence\|` | 情感色彩越强衰减略慢 |

**状态迁移触发**：

```
S(t) < 0.05 AND not active_grounded  →  CONSOLIDATED → ARCHIVED
ARCHIVED + (explicit purge OR retention_policy expired)  →  FORGOTTEN
```

**active_grounded 判定**：仅对 CommonGround 中未 `expired / superseded / ungrounded` 的条目为 1。旧共识经 SupersedeGround / ExpireGround / Unground 处理后立即失去保护。

**FORGOTTEN 后 Engram 处置**（按 retention_mode）：

| retention_mode | 处置 |
|---|---|
| `legal_hold` | 保留密文与密钥，访问需审计授权 |
| `audit_retain` | 保留到 retention_policy 到期 |
| `redacted_retain` | 原文替换为脱敏文本，保留 hash |
| `crypto_erasure` | 销毁 key_ref，仅保留 hash / metadata / audit trail |

### 3. 巩固分层策略

| 层 | 策略 | 触发条件 |
|---|---|---|
| Hippocampus 短期 | 指数衰减 + 显著性补偿 | 默认每条 |
| Episodic 长期 | 关联度排序后修剪 | Replay 每轮 |
| Semantic | 不删，只下调 confidence 或转 OUTDATED | Reconsolidation 失败 |
| 隐私强制 | FORGOTTEN + redaction/crypto erasure；默认传播到无独立证据的直接 derived | 用户/法务事件 |

---

## 数据结构

### ReplayMode 枚举

```python
from enum import Enum

class ReplayMode(Enum):
    ONLINE = "online"    # 每 N=3 条 statement.written 触发，批 1-3 条
    IDLE   = "idle"      # Agent 空转 > T=120s 触发，批 10-30 条
    SLEEP  = "sleep"     # 会话结束 / 每日 / /sleep 触发，完整 sweep
```

### ConsolidationOp 枚举

```python
class ConsolidationOp(Enum):
    COMPRESS         = "compress"
    ABSTRACT         = "abstract"
    RECONCILE        = "reconcile"
    INDUCE_NORM      = "induce_norm"
    FORGE_SKILL      = "forge_skill"
    DECAY            = "decay"
    PURGE_COMPLIANCE = "purge_compliance"
```

### ConsolidationAtom（原子操作元数据）

```python
class ConsolidationAtom:
    op: ConsolidationOp
    input_stmt_ids: list[UUID]              # 输入 Statement（可多条）
    output_stmt_id: Optional[UUID]          # 派生输出（compress/abstract/induce_norm/forge_skill）
    provenance: Literal[
        "replay_derived",                   # 所有 Replay 产出固定取此值
    ]
    review_status: Literal[
        "APPROVED",                         # compress 直接落库
        "PENDING_REVIEW",                   # abstract / induce_norm / forge_skill 候选
    ]
    triggers_replay: bool = False           # 默认不触发再 Replay；propagate=True 时例外
    replay_batch_id: UUID                   # 所属 Replay 批次
```

### statement.decay_candidate 事件

```python
class DecayCandidateEvent:
    event_type: Literal["statement.decay_candidate"]
    stmt_id: UUID
    current_s: float                        # 当前召回强度 S(t)
    active_grounded: bool
    consolidation_state: str
    emitted_at: datetime
    # Bus dispatcher 按 stmt_id 串行投递，后到事件读到 state 已变即跳过
```

### statement.consolidation_forced 事件

```python
class ConsolidationForcedEvent:
    event_type: Literal["statement.consolidation_forced"]
    stmt_id: UUID
    replay_count: int                       # 触发时等于 MAX_CONSOLIDATION_ATTEMPTS=5
    forced_state: Literal["CONSOLIDATED"]
    review_status: Literal["PENDING_REVIEW"]
    emitted_at: datetime
```

### ReplaySamplerConfig（参数常量）

```python
class ReplaySamplerConfig:
    N_online_trigger: int    = 3            # Online 模式触发阈值
    T_idle_seconds: int      = 120          # Idle 模式空转超时
    T_cooldown_minutes: int  = 5            # 同一 Statement 最短重放间隔
    w_min: float             = 0.01         # 最低采样权重下界
    w_max_percentile: int    = 95           # 极端权重截断分位数
    batch_online: tuple      = (1, 3)
    batch_idle: tuple        = (10, 30)
    MAX_CONSOLIDATION_ATTEMPTS: int = 5     # 振荡防护阈值
    T_max_volatile_days: int = 7            # VOLATILE TTL 兜底
    derived_depth_max: int   = 3            # 超过此深度不再自动派生
```

---

## 相关概念

**Online / Idle / Sleep 三种重放模式**
三种触发时机各异的 Replay 窗口，分别对应会话内即时巩固、空转反思、深度 sweep。

**SWR（Sharp-Wave Ripple）风格优先级采样**
对标海马 SWR 重放机制，用加权随机采样替代轮询，高 salience 与高 arousal Statement 优先巩固。详见核心算法 §1。

**自适应遗忘公式**
基于 Ebbinghaus 遗忘曲线扩展，S0 受 access_count / salience / active_grounded / modality / valence 联合调节。详见核心算法 §2。

**active_grounded**
CommonGround 中未 `expired / superseded / ungrounded` 的条目标志位，置 1 时 S0 大幅增大，Statement 衰减极慢。旧共识失效后立即清零。

**replay_derived provenance**
所有 Replay 巩固输出的固定 provenance 标签。Bus 写入后 emit `statement.derived`（非 `statement.written`），Replay Scheduler 不订阅该事件。参见 [Statement Bus](v20_05_bus.md)。

**Replay 循环断开机制**
Replay Scheduler 只订阅 `statement.written`，不订阅 `statement.derived`，从源头断开巩固输出触发再采样的可能。

**decay 路由经事件总线**
Replay 不直接修改 state，而是 emit `statement.decay_candidate`，由 Bus dispatcher per-stmt 串行投递。后到事件读到 state 已变则跳过，消除并发 decay 的竞争条件（T5/T8 race）。

**振荡防护（MAX_CONSOLIDATION_ATTEMPTS=5）**
`replay_count` 达到上限时强制迁移至 CONSOLIDATED + PENDING_REVIEW，并 emit `statement.consolidation_forced`，防止 VOLATILE/REPLAYING 无限循环。

**参见**：

- [Statement Bus](v20_05_bus.md) — 事件写入与 replay_derived 路由
- [Affect Buffer](v20_06_hippocampus.md) — VOLATILE TTL 兜底判断、Idle 优先级影响
- [Reconsolidation Engine](v20_11_reconsolidation.md) — reconcile 操作的接收方与冲突仲裁
