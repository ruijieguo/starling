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

# Replay Scheduler

## 功能定义

Replay Scheduler 负责将 VOLATILE Statement 巩固到 CONSOLIDATED，并对长期记忆执行衰减、抽象、规则归纳、技能锻造。触发模式分三种：Online（在线）、Idle（空闲）、Sleep（深度）。它只经事件总线 emit `statement.decay_candidate`，不直接修改 state，与 [Reconsolidation Engine](v23_11_reconsolidation.md) 严格分工。

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
| `reconcile` | 冲突 Statement 集 | 推入 [Reconsolidation Engine](v23_11_reconsolidation.md) | 输入：CONSOLIDATED → REPLAYING_RECONSOLIDATING | — |
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

上述 Python 示例为绑定层接口契约。核心实现为 C++ 抽象类，Python/JS/Rust 等绑定通过 pybind11 / NAPI / cxx 自动生成存根。

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
所有 Replay 巩固输出的固定 provenance 标签。Bus 写入后 emit `statement.derived`（非 `statement.written`），Replay Scheduler 不订阅该事件。参见 [Statement Bus](v23_05_bus.md)。

**Replay 循环断开机制**
Replay Scheduler 只订阅 `statement.written`，不订阅 `statement.derived`，从源头断开巩固输出触发再采样的可能。

**decay 路由经事件总线**
Replay 不直接修改 state，而是 emit `statement.decay_candidate`，由 Bus dispatcher per-stmt 串行投递。后到事件读到 state 已变则跳过，消除并发 decay 的竞争条件（T5/T8 race）。

**振荡防护（MAX_CONSOLIDATION_ATTEMPTS=5）**
`replay_count` 达到上限时强制迁移至 CONSOLIDATED + PENDING_REVIEW，并 emit `statement.consolidation_forced`，防止 VOLATILE/REPLAYING 无限循环。

- 配置：所有 Adapter 与运行时配置采用 JSON 格式，统一 schema 见主文档 §2.0

**参见**：

- [Statement Bus](v23_05_bus.md) — 事件写入与 replay_derived 路由
- [Affect Buffer](v23_06_hippocampus.md) — VOLATILE TTL 兜底判断、Idle 优先级影响
- [Reconsolidation Engine](v23_11_reconsolidation.md) — reconcile 操作的接收方与冲突仲裁


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
