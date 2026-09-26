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

完整 `perspective_take` 算子见 [perspective_take](v18_09_tom.md)。

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

`persona` 字段的容器语义见 [Persona Container](v18_07_neocortex.md)。

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
| **Persona Container** | Cognizer 长期画像，慢通道更新；见 [Persona Container](v18_07_neocortex.md) |
| **perspective_take** | ToM Engine 视角切换算子，调用 KnowledgeFrontier 做硬过滤；见 [perspective_take](v18_09_tom.md) |


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
