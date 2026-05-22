# Cognizer Hub

## 功能定义

Cognizer Hub 是认知主体注册与画像管理子系统。它把 user / agent / group / role 提升为一等公民（Cognizer），赋予生命周期、知识边界（KnowledgeFrontier）和主体间关系（RelationEdge）三类持久状态。Entity（概念、制品、地点等普通实体）共享 alias 归一算法，但不具备 persona / frontier / trust_priors，与 Cognizer 严格二分。

## 主要流程

### 1. Cognizer 生命周期（五阶段）

```
discover → seed → observe → profile → archive
```

| 阶段 | 动作 |
|---|---|
| discover | EngramStore NER + 对话角色检测 + alias 归一，识别新主体 |
| seed | 初始化空 Persona、默认 KnowledgeFrontier、trust_priors=neutral |
| observe | 每次出场触发 `cognizer.observed`，刷新 `last_seen_at` |
| profile | Replay 周期重写 Persona（慢通道） |
| archive | 长期未活跃后降低检索权重，**不删除** |

### 2. KnowledgeFrontier 维护（五类信息）

KnowledgeFrontier 记录"该主体可能知道什么"，包含以下五类：

| 字段 | 含义 |
|---|---|
| `accessible_sources` | 该主体可访问的信息源列表 |
| `membership` | 所属群组（影响群组级信息可见性） |
| `presence_log` | 何时何地在场（PresenceWindow 序列） |
| `explicit_told` | 明确被告知的陈述（StatementRef 列表） |
| `explicit_not_told` | 明确未被告知的陈述（用于 surprise 推断） |

frontier 由 observe / profile 阶段持续写入；seed 阶段以空集初始化。

### 3. Retrieval 硬过滤（perspective filter）

检索时，Retrieval Planner 调用 `filter_by_frontier(engram_store, target, time)`，以 `(target, time)` 为参数对全部 engram 做 EnigmaToM iterative masking，只返回该主体在指定时间点前可见的 engram 子集。此步骤是硬过滤，不可跳过。

完整 `perspective_take` 算子见 [perspective_take](v19_09_tom.md)。

### 4. RelationEdge 计算（Fiske 四类关系）

关系本身作为 Statement 存储，holder 为观察者，因此多视角天然支持：Alice 视角下的 Alice-Bob 关系与 Bob 视角下的 Alice-Bob 关系相互独立。

Fiske 四类关系对生成风格的影响：

| 关系模式 | 风格影响 |
|---|---|
| Communal（共同体） | 长期主动记忆共享，低形式化提醒 |
| Authority（权威，上行/下行区分） | 下属对上司主动汇报；反之精炼输出 |
| Market（市场） | 对等可审计，强 grounding |
| Equality（平等） | 轮替式 grounding 与责任分配 |

`power_asymmetry` 捕捉 a 对 b 的影响力差；`trust` 按领域（Context）分别维护，不同领域信任度可不同。

## 核心算法

### 1. Cognizer 去重与归并

新 Cognizer 写入前，系统按以下三层做归一：

- `aliases`：同一主体的多个自然语言称呼（"老张" / "Zhang Wei" / "user_42"）
- `canonical_name`：归一后的规范名，写入后作为主键参与冲突检测
- `external_id`：跨系统稳定标识符，与 `kind` 组合构成 UUID5 主键

alias 归一算法与 Entity 注册共享，但 Entity 无 persona / frontier / trust_priors。

### 2. KnowledgeFrontier iterative masking

检索时按 `(target, time)` 过滤 visible engram set：

```python
def perspective_take(target: CognizerRef, query: str, time: datetime) -> Context:
    visible = filter_by_frontier(engram_store, target, time)   # KnowledgeFrontier 遮蔽
    target_beliefs = neocortex.query(holder=target, time=time) # holder=target 子图
    cg = common_ground(self, target)                           # 共识池
    return Context(visible, target_beliefs, cg)
```

masking 逻辑遍历 `presence_log`、`membership`、`accessible_sources`、`explicit_told` 四路正向信息，再从 `explicit_not_told` 中移除对应 engram，形成最终可见集。

### 3. trust_priors 方向性

`trust_priors: dict[CognizerId, float]` 记录**该主体对他人**的先验信任，方向为 Cognizer A → B（A 信任 B 的程度），而非系统对 A 的信任度。

- 当 A 作为 holder 持有"B 说 X 这件事"时，系统在 A 的视角下使用 `A.trust_priors[B]` 评估证据可信度。
- `commitment.fulfilled` 事件触发 trust_priors 上调；`commitment.broken` 触发下调（具体公式见 §8.3）。
- 初始化为 neutral（0.5），由 seed 阶段写入。

### 4. Fiske 四类关系的判定与多维向量化

RelationEdge 以 `fiske_weights: dict[Mode, float]` 存储四类关系强度，允许一段关系同时带有多种模式（如师生关系兼具 Authority 与 Communal 成分）。判定流程：

1. 从 interaction_history_ref 引用的 Episode 中抽取行为特征。
2. 按 Fiske 四模式打分，归一化为权重向量。
3. 结合 `affinity`（0..1）与 `trust[Context]` 形成完整关系向量。
4. `valid_from` / `valid_to` 支持关系的时间有效性约束。

## 数据结构

### Cognizer

```python
class Cognizer(BaseEntity):
    id: UUID                                # UUID5 from (kind, external_id)
    tenant_id: str = "default"              # 单租户固定为 default；多租户写入后不可变
    kind: Literal["self","human","agent","group","role","external"]
    canonical_name: str                     # 规范名
    aliases: list[str]                      # 多语言/多系统称呼
    external_id: str                        # 跨系统稳定 id
    persona: PersonaRef                     # 长期画像（慢通道，见 §3.6）
    knowledge_frontier: KnowledgeFrontier   # 知识边界
    relations: list[RelationEdge]           # 与其他 Cognizer 的关系
    trust_priors: dict[CognizerId, float]   # 该主体对他人的先验信任
    permissions: AccessPolicy
    created_at: datetime
    last_seen_at: datetime
```

`persona` 字段的容器语义见 [Persona Container](v19_07_neocortex.md)。

**group tenant 规则**：`kind="group"` 的 Cognizer 必须显式声明 `tenant_id`，不得从成员列表隐式推导。P0 只支持单 tenant group；跨 tenant 成员写入必须拒绝或进入 `REVIEW_REQUESTED` 分支，不得静默降级为 `"default"`。

### Entity（非 Cognizer 实体）

```python
class Entity(BaseEntity):
    id: UUID                                # UUID5 from (kind, canonical_name)
    kind: Literal["concept","artifact","place","event","organization","project","other"]
    canonical_name: str
    aliases: list[str]
    type_tags: list[str]
    created_at: datetime
```

Entity 无 `persona` / `knowledge_frontier` / `trust_priors`，不是认知主体。注册由 Cognizer Hub NER 流程 + alias 归一负责（§8.1 discover 阶段）。

### KnowledgeFrontier

```python
class KnowledgeFrontier:
    accessible_sources: list[SourceRef]     # 可访问信息源
    membership: list[GroupRef]              # 所属群组
    presence_log: list[PresenceWindow]      # 在场记录（何时何地）
    explicit_told: list[StatementRef]       # 明确被告知的陈述
    explicit_not_told: list[StatementRef]   # 明确未被告知（用于 surprise）
```

Container 类型，是可重建的 StatementRef 物化视图，不直接是 Statement。

### RelationEdge

```python
class RelationEdge:
    a: CognizerRef
    b: CognizerRef
    fiske_weights: dict[Mode, float]        # Communal/Authority/Equality/Market 强度
    affinity: float                         # 0..1
    trust: dict[Context, float]             # 领域级信任
    power_asymmetry: float                  # a 对 b 的影响力差
    interaction_history_ref: EpisodeQuery
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
```

关系本身作为 Statement 存储，holder 为观察者，多视角下自然独立。

## 相关概念

| 术语 | 说明 |
|---|---|
| **Cognizer vs Entity** | Cognizer 是一等公民（有 persona / frontier / trust_priors）；Entity 是普通实体（无上述三项） |
| **Cognizer.kind 枚举** | `self` / `human` / `agent` / `group` / `role` / `external` |
| **KnowledgeFrontier** | 记录"该主体可能知道什么"的五维知识边界 |
| **iterative masking** | 检索时以 `(target, time)` 对 engram set 做逐层遮蔽，只暴露目标主体可见子集 |
| **trust_priors 方向性** | A.trust_priors[B] 表示 A 对 B 的先验信任，而非系统对 A/B 的评价 |
| **Fiske 四类关系** | Communal / Authority / Equality / Market，多维权重向量，可混合 |
| **aliases / canonical_name / external_id** | 三层归一：自然语言别名 → 规范名 → 跨系统稳定 ID |
| **Persona Container** | Cognizer 长期画像，慢通道更新；见 [Persona Container](v19_07_neocortex.md) |
| **perspective_take** | ToM Engine 视角切换算子，调用 KnowledgeFrontier 做硬过滤；见 [perspective_take](v19_09_tom.md) |
