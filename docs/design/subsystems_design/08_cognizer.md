<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](../../superpowers/specs/2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **R3.1 实评收口（2026-09-20）**：8192 消除了 R2.3 中已观察的抽取截断，但重复键/结构边界风险仍在（3 次 schema、1 次 envelope）。R3.1 为 6/57、30 项技术失败、3/7 scope；与 R2.3 共同 `ok` 题各正确 6 题，不晋升容量或结构化合同默认。详见 [R3.1 评测报告](../../eval/2026-09-20-socialmem-r31-extraction-capacity.md)。

> **R3.1 抽取容量诊断设计（2026-09-20）**：本轮只改变结构化抽取请求容量（4096→8192），不修改 C++ 提示、JSON 合同、重复键拒绝、谓词目录或 admission；`sources` 对照保持 4096。评测将单独报告截断/超时与 QA 配对变化，生产默认继续关闭结构化合同。详见 [R3.1 设计](../../superpowers/specs/2026-09-20-socialmem-r31-extraction-capacity-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Cognizer Hub
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **语义证据契约状态（2026-09-12）**：已实现并通过完整工程验证；真实诊断已完成并核验，质量门槛未通过，默认关闭，设计见 [Source-Grounded Claim Contract](../../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md)。按已确认契约 actor、attributed_to、holder 和 perspective 的归属由证据契约校验；`FIRST_PERSON` 不得把他人状态写成 holder 自陈，`QUOTED` 必须保留报告者与被报告主体。

## 2026-09-11 语义证据契约

actor 与 subject 必须一致，第一人称 mental-state 候选的 subject 必须是 holder；QUOTED 保留被报告 actor 与来源报告者 attributed_to。该约束只用于实验的五个谓词，不修改旧世界事实的 subject 规则。C++ 负责名称处理、归属检查和证据一致性，binding 不进行二次重归属。

实现状态与评测证据统一见 [同步清单](../claim_contract_sync.md)。

## 功能定义

Cognizer Hub 是认知主体注册与画像管理子系统。它把 user / agent / group / role 提升为一等公民（Cognizer），赋予生命周期、知识边界（KnowledgeFrontier）和主体间关系（RelationEdge）三类持久状态。Entity（概念、制品、地点等普通实体）共享 alias 归一算法，但不具备 persona / frontier / trust_priors，与 Cognizer 严格二分。

## 输入

- Cognizer 注册请求（含 kind、external_id、aliases）
- KnowledgeFrontier 更新事件（来自 cognizer.observed 与 statement.written 中的 perceived_by 字段）
- RelationEdge 写入请求（含 Fiske 类型 + 情境化信任）
- 别名归一查询（NER 流程触发）

## 输出

- Cognizer ID（UUID5 from kind + external_id）
- 归一后的 canonical_name（aliases 合并结果）
- KnowledgeFrontier 当前快照（按 (target, time) 返回 visible engram set）
- RelationEdge 查询结果（含 fiske_kind、contextual_trust、power_asymmetry）
- trust_priors 调整事件（来自 commitment.fulfilled / broken 反馈）

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

完整 `perspective_take` 算子见 [perspective_take](09_tom.md)。

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

`persona` 字段的容器语义见 [Persona Container](07_neocortex.md)。

**group tenant 规则**：`kind="group"` 的 Cognizer 必须显式声明 `tenant_id`，不得从成员列表隐式推导。P1 只支持单 tenant group；跨 tenant 成员写入必须拒绝或进入 `REVIEW_REQUESTED` 分支，不得静默降级为 `"default"`。

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

上述 Python 示例为绑定层接口契约。核心实现为 C++ 抽象类，Python/JS/Rust 等绑定通过 pybind11 / NAPI / cxx 自动生成存根。

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
| **Persona Container** | Cognizer 长期画像，慢通道更新；见 [Persona Container](07_neocortex.md) |
| **perspective_take** | ToM Engine 视角切换算子，调用 KnowledgeFrontier 做硬过滤；见 [perspective_take](09_tom.md) |

- 配置：所有 Adapter 与运行时配置采用 JSON 格式，统一 schema 见主文档 §2.0


## 来源话轮实现核对（2026-09-12）

版本化来源话轮由 C++ 生成与解析，直接证据回读共用严格验证。该子系统继续消费已有证据与时间契约，不新增语言 binding 中的语义逻辑。来源观察时间不作为绝对事件时间；本轮核对与诊断统一见 [设计同步清单](../claim_contract_sync.md) 和 [来源话轮评测报告](../../eval/2026-09-12-socialmem-source-turn.md)。


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](../../superpowers/specs/2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](../../eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](../../superpowers/specs/2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已完成并由原生验证器核验为 `verified / complete_with_errors`：140 条重放、144 个数据库；固定候选 56/64（TP 30、TN 26、误收 0、误拒 1、技术失败 7），synthetic 冻结 11/16、契约 11/16（有效分母 15/16），P1 combined F1 为 holder 0.7317、holder/perspective 0.6829、predicate/object 0.7683；扩展标签 object/topic/scope/time/joint 为 12/14、2/14、12/14、12/14、2/14（有效目标 13）；Q1/Q9 的 baseline、structured、linked 均为 0/3，full 均为 3/3；实际证据链仍受入库与证据聚合限制。原生技术失败共 10 条，主要为重复 JSON 键和准入 JSON 后追加文本；无效裁判票 0。`promotion_ready=false`，生产默认保持关闭，不运行 1,031 题全量。默认、原标签、检索与历史归档保持。

## 2026-09-16 能力与得分路线修订（已授权自主迭代）

后续行为聚合与隐含立场回答需要保留多条父来源，并区分直接声明与推断。扩大词表须有来源支持及正反例；候选数量与抽取指标不能替代端到端得分。 具体范围、测试与验收见[统一方案](../../superpowers/specs/2026-09-16-socialmem-capability-and-score-design.md)。本段描述计划，不代表已经实现或获得新分数。

最新执行顺序已按用户指令调整：先冻结当前默认 Starling 并完成全部 1031 题基线，再按真实失分执行中文文档→失败测试→C++ 改进→同条件复测，循环自主迭代，无需重复申请常规步骤授权。基线前仅补评测编排及题目允许来源范围，不预修被测能力。详见[基线优先执行计划](../../superpowers/plans/2026-09-16-socialmem-baseline-first.md)。

## R2 谓词覆盖扩展设计同步（2026-09-20）

本阶段承接结构化覆盖诊断和 SourceTurn/三通道回执修复，目标是补齐结构化合同与 legacy mental-state 之间的能力断层。C++ 原生目录版本升级为 `claim-predicate-v3`，新增 `prefers`、`promises`、`doubts`、`believes`、`responsible_for`、`requires`、`forbids` 七类规范谓词及受控别名；既有谓词、来源证据、admission 和持久化格式保持兼容。目录、别名、语义族、允许模态/极性、抽取提示和准入提示均由 C++ `PredicateCatalog` 唯一生成，Python 只绑定、编排和归档，不维护第二份语义逻辑。

本阶段严格执行中文设计文档 → C++/Python RED 测试 → C++ 实现 → 固定协议回归。测试覆盖中英文正反例、错误模态、主体与对象保真、admission 拒绝计数、`knows` 历史模态兼容、三通道证据回读和 Python binding 边界。新增结构化声明数量或离线测试通过率不等于 QA/F1 提升；只有 7/7 scope、36/36 holder 的同协议 SocialMemBench 结果和预注册统计门槛满足后，才讨论晋升。生产默认仍保持 `semantic_claim_contract=false`。

## R2.1 结构化输出协议修正（2026-09-20）

首次 `claim-predicate-v3` 固定评测中，qwen3.8-27b 在 legacy 结构化请求下出现截断、未转义 JSON 和证据范围不完整，57 题中 47 题在抽取建库阶段失败。该结果只说明协议性技术失败，不能解释为谓词扩展导致 QA 下降。下一轮由 C++ `OpenAIAdapter::extract_with_contract` 使用 `ValidationPolicy.claim_output_mode=JsonObject` 发送原生 `response_format`；C++ 继续执行 envelope、schema、scope、admission 和持久化校验，Python 仅传递配置和归档回执，不清洗模型文本。生产默认仍为 `semantic_claim_contract=false`、`claim_output_mode=Legacy`；新评测必须使用独立身份并分别报告技术完成率和 QA。

## R2.2 结构化输出末端格式提醒（2026-09-20）

Cognizer 心智状态声明继续由 C++ 合同解析。针对 qwen3.8-27b 的误嵌套响应，提示末端明确 holder、subject、predicate 等字段必须为 statement 顶层字段，evidence 仅保存来源证据字段；缺字段和错误主体仍由 C++ 严格拒绝。

## R2.3 重复键与布局对照（2026-09-20）

Cognizer 声明生成的末端提醒增加唯一 key 与顶层布局对照，避免模型重复 `time_text`/`topic` 或将主体字段嵌入 evidence；语义和拒绝边界仍由 C++ 合同维护。

### R2.3 实评证据收口（2026-09-20）

独立网络评测完成 57/57 题，7/57 正确、26/57 技术失败；4/7 scope 完成，holder 为 19/36。失败包括重复 `time_text`/`topic` 的 `envelope_failure`、抽取超时、抽取/回答 `completion_truncated`。两轮共同完整题目只有 17 题，不能从 15/57 与 7/57 的非配对差异推断提示因果收益。当前仍保持 C++ 严格拒绝和 Python 仅 binding/编排，生产默认 `semantic_claim_contract=false`；完整证据见 [R2.3 鲁棒性评测报告](../../eval/2026-09-20-socialmem-structured-output-robustness.md)。

## R3.2 结构化声明字段归属（2026-09-20）

Cognizer 相关声明必须保留实际 holder、subject 和 perspective。R3.2 仅在 C++ 抽取提示末端增加无业务样本的字段归属骨架，不能将模型遗漏的主体或证据字段由 binding 猜补；严格解析失败仍记录为技术失败。

## R3.2 结果与 R3.3 关系证据范围（2026-09-21）

R3.2 的错误题表明，关系问题不能只依赖 holder 的孤立 belief：回答需要同时看到观察者、被描述者、回应和跨会话重复行为。R3.3 对没有显式人物但要求“每个成员/所有成员”的问题扩展允许 holder 范围，对含变化词的问题覆盖最早与最晚 session；这只是把原文送入 Cognizer/回答链，不自动生成关系或因果结论。

R3.3 共同正常题从 R3.2 的 9/38 变为 11/38，网络 bootstrap 95% 区间为 [-2.63, +2.63] 个百分点。Cognizer 继续要求回答绑定实际 speaker、被描述主体和 belief bearer，不从来源命中推导因果或关系结论。

人物边界、租户过滤、来源完整性和 `source_refs` 对齐仍由 C++ 完成；Python 仅透传 `ObserverQuery`。任何缺失来源都必须保留为证据不足或 abstain 信号，不能由 Cognizer 补写。

## R3.4 结构化协议失败恢复（2026-09-21）

Cognizer 只消费通过 C++ 合同的声明。针对 R3.3 已确认的重复键和目录外谓词，C++ 可在 policy 允许时重新请求一次完整源上下文；不在 Cognizer 或 Python 中猜测人物、谓词或证据。每次尝试的请求身份和原文都进入 receipt，scope/admission 仍不可绕过。

## R3.5 Holder 级故障隔离（2026-09-21）

结构化抽取不再由 Python 逐 holder 驱动。C++ `memory_ops` 接收已规范化的 holder/payload 集合，逐 holder 完成 prepare、锁外三通道抽取和独立 commit；异常转换为 holder 失败结果并保留完整 attempt，继续后续 holder。`failure_detail` 由 C++ 从失败 attempt 的 kind/路径/detail 或传输错误派生，供回执摘要使用。字段级 schema 路径只用于纠错与诊断，不改变谓词、scope 或 admission 语义。partial holder 的声明不得被 Cognizer 当成全体人物覆盖，评测和生产晋升分别报告完整与 partial 分母。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
