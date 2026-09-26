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

# Neocortex

## 功能定义

Neocortex 是慢记忆子系统，存储 CONSOLIDATED 状态 Statement，按 holder 分图族组织。它分五子区：Semantic / Procedural / Norms / Personae / CommonGround。其中 Personae 与 CommonGround 是 Container 物化视图（不是 Statement 子区），由 [Statement Bus](v23_05_bus.md) 的 `rebuild_container` 触发更新。

---

## 输入

- Bus 路由的 CONSOLIDATED Statement（来自 statement.derived 事件）
- holder 子图查询请求（来自 Retrieval Planner）
- Container rebuild 请求（Persona / CommonGround / KnowledgeFrontier 物化触发）
- decay 候选事件（statement.decay_candidate）

## 输出

- CONSOLIDATED 分区持久化结果
- holder 子图族（按 holder=self / holder=Alice / common(self,Alice) 等分层返回）
- Container 物化视图（Persona / CommonGround / KnowledgeFrontier 当前快照）
- ARCHIVED 迁移事件（statement.archived）
- 冲突消解决策（emit belief.conflict 进 Reconsolidation）

---

## 主要流程

### 1. Replay 巩固入口

```
Replay Scheduler
  → 生成 provenance=replay_derived 的 Statement
  → Bus.write(stmt, state=CONSOLIDATED)
  → 若该写入使条目进入 CONSOLIDATED，则 emit statement.consolidated
  → 若该轮产生新的派生内容，则 emit statement.derived
  → Statement 落入 Neocortex 对应子区
      ├─ BELIEVES / KNOWS  → Semantic 子图（按 holder 路由）
      ├─ Skill 提升        → Procedural
      └─ Norm 推断         → Norms
```

Neocortex 不接受直接写入。所有 CONSOLIDATED Statement 必须经 [Statement Bus](v23_05_bus.md) 落库。

### 2. holder 子图查询

检索时不走全局图，而是按 holder 分图族定向查询：

```
query(predicate, holder=self)          → 我自己相信的
query(predicate, holder="Alice")       → 我以为 Alice 相信的
query(predicate, holder=common(self, Alice))  → 自-Alice 共识池
query(predicate, holder=common(self, Alice, Bob))  → N 元共识
```

每子图独立维护真值，共享 entity 池。不同 holder 的同一命题在各自子图中存储，互不污染。

### 3. Container 物化

Bus.rebuild_container 触发时，重建以下三类 Container：

```
rebuild_container(PersonaRef, sources)
  → 汇聚 self_model_anchor + profile_anchor
  → Persona dimension 按权重合并
  → CAS 防并发覆盖写入 Personae 子区

rebuild_container(CommonGroundRef, sources)
  → 汇聚 grounding act 触发的共识陈述
  → 更新 grounded / asserted_unack / suspected_diverge
  → 写入 CommonGround 子区

rebuild_container(KnowledgeFrontierRef, sources)
  → 推断当前知识边界
  → 写入 Semantic 子区附属索引
```

### 4. 冲突消解决策树

ConflictProbe 在 Bus 写入时探测冲突，Neocortex 按以下决策树处理结果：

| 情况 | 处理 |
|---|---|
| 不同 holder 命题矛盾 | 直接共存（多视角，不算冲突） |
| 同 holder + 同时间窗 + 矛盾 | emit `belief.conflict`，Replay 加重优先级，不立即仲裁 |
| 同 holder + 时间更晚 + 隐式改口 | 旧版 confidence 衰减，新旧两版共存，待 Reconsolidation 仲裁 |
| 同 holder + 时间更晚 + 显式 RECANT | supersedes 链，旧版进历史信念链 |
| 涉及承诺主体改口 | 触发 audit 流程，evidence 链显式比对 |

`belief.conflict` 事件进入 [Reconsolidation Engine](v23_11_reconsolidation.md) 处理队列。

---

## 核心算法

### 1. holder-aware 图族命名规则与查询路由

```python
def graph_key(holder: HolderSpec) -> str:
    if isinstance(holder, SingleHolder):
        return f"holder:{holder.id}"
    if isinstance(holder, CommonHolder):
        # 规范化排序，保证 common(A,B) == common(B,A)
        ids = sorted(h.id for h in holder.members)
        return "common:" + ":".join(ids)
    raise ValueError(f"unknown holder type: {holder}")

def route_query(predicate, holder):
    key = graph_key(holder)
    graph = graph_family[key]      # 不存在则返回空图
    return graph.match(predicate)
```

图族索引结构：`Dict[str, SubGraph]`，key 为上述规范化字符串，SubGraph 内部为 `(subj, pred, obj, t, conf)` 元组集合。

### 2. Persona 慢通道 vs Belief 快通道

| 通道 | 载体 | 更新频率 | 触发 |
|---|---|---|---|
| 慢通道（Persona） | Persona Container | 每 N 次会话一次 | Replay 周期 |
| 快通道（Belief） | holder=X 的 Statement | 实时，每次写入 | Bus.write |

单次会话不触动 Persona。Belief 与 Persona 出现矛盾时：

```
Belief 快通道（Statement, CONSOLIDATED）
  ↔ 与 Persona 慢通道（dimension value）比对
      ├─ 一致         → 无操作
      ├─ 局部偏差     → Persona 候选队列（待下一轮 Replay 周期确认）
      └─ 持续冲突     → 升 suspected_diverge，交 ToM Engine 仲裁
```

### 3. self_model_anchor vs profile_anchor 多源仲裁

```python
def update_persona_dimension(persona: Persona, dim: str, candidates: list[AnchorCandidate]):
    self_anchors    = [c for c in candidates if c.anchor_type == "self_model_anchor"]
    profile_anchors = [c for c in candidates if c.anchor_type == "profile_anchor"]

    # 自陈优先
    if self_anchors:
        primary = weighted_merge(self_anchors)
    else:
        primary = weighted_merge(profile_anchors)

    # 多源 profile 与自陈冲突检测
    if self_anchors and profile_anchors:
        conflict = detect_trait_conflict(
            weighted_merge(self_anchors),
            weighted_merge(profile_anchors),
        )
        if conflict.severity >= DIVERGE_THRESHOLD:
            persona.dimensions[dim].suspected_diverge = True
            emit_to_tom_engine(persona.holder, dim, conflict)
            return   # 暂不写入，等 ToM 仲裁

    persona.dimensions[dim].value = primary.value
    persona.dimensions[dim].confidence = primary.confidence
```

### 4. Container 物化视图 CAS 策略

```python
def rebuild_container(ref: ContainerRef, sources: list[Statement]):
    current = store.load(ref)

    if current.priority <= P2:
        # P1：整体 rebuild，单 version CAS
        new_container = build_from_sources(sources)
        ok = store.cas(ref, expected_version=current.version, new=new_container)
        if not ok:
            raise ConcurrentRebuildError(ref)

    else:
        # P3：dimension-level CAS，粒度更细
        for dim, value in build_dimensions(sources).items():
            store.cas_dimension(ref, dim, expected=current.dimensions[dim], new=value)
```

---

## 数据结构

### 五子区总览

| 子区 | 主要承载类型 | 更新通道 | Container？ |
|---|---|---|---|
| Semantic | Statement（BELIEVES / KNOWS，CONSOLIDATED） | Replay 巩固 | 否 |
| Procedural | Skill | Case 集群提升（EverOS 风格） | 否 |
| Norms | Norm | 反思周期推断 | 否 |
| Personae | Persona | 慢更新（每 N 次会话），rebuild_container | 是 |
| CommonGround | CommonGround | grounding act 触发，rebuild_container | 是 |

### holder 子图族索引

```python
@dataclass
class SubGraph:
    key: str                         # "holder:self" / "common:Alice:self" 等
    triples: set[Triple]             # (subj, pred, obj, t, conf)
    entity_pool_ref: EntityPoolRef   # 共享 entity 池（只读引用）

@dataclass
class GraphFamily:
    graphs: Dict[str, SubGraph]      # key = graph_key(holder)

    def get_or_empty(self, holder: HolderSpec) -> SubGraph:
        return self.graphs.get(graph_key(holder), SubGraph.empty())
```

### Persona dimension keys

```python
@dataclass
class PersonaDimensions:
    traits:              dict[str, DimensionValue]   # 性格特质
    preferences:         dict[str, DimensionValue]   # 偏好
    competencies:        dict[str, DimensionValue]   # 技能/能力
    values:              dict[str, DimensionValue]   # 价值观
    self_model_anchor:   list[AnchorStatement]       # 主体自陈集合
    profile_anchor:      list[AnchorStatement]       # 他人对该主体陈述集合
    relationship_styles: dict[str, DimensionValue]   # 关系风格（对不同 holder）

@dataclass
class DimensionValue:
    value:             Any
    confidence:        float
    suspected_diverge: bool = False
    last_updated_at:   datetime = None

@dataclass
class AnchorStatement:
    stmt_id:     str
    anchor_type: Literal["self_model_anchor", "profile_anchor"]
    source_holder: str                # 谁说的
    subject_holder: str               # 说的是谁
    content:     str
    confidence:  float
    valid_from:  datetime
    valid_to:    datetime | None
```

### CommonGround dimension keys

```python
@dataclass
class CommonGroundDimensions:
    grounded:             list[GroundedFact]       # 双方已确认共识
    asserted_unack:       list[AssertedFact]       # 一方陈述，他方未明确确认
    suspected_diverge:    list[DivergenceCandidate] # 疑似分歧，待 ToM 仲裁
    establishment_evidence: list[EvidenceRef]      # 共识建立的证据链

@dataclass
class GroundedFact:
    content:      str
    holders:      list[str]          # 参与共识的 holder 列表
    grounded_at:  datetime
    evidence_ids: list[str]

@dataclass
class DivergenceCandidate:
    content:       str
    holder_a:      str
    holder_b:      str
    conflict_type: str               # trait_mismatch / belief_mismatch 等
    detected_at:   datetime
```

---

上述 Python 示例为绑定层接口契约。核心实现为 C++ 抽象类，Python/JS/Rust 等绑定通过 pybind11 / NAPI / cxx 自动生成存根。

## 相关概念

- **CONSOLIDATED 状态**：Statement 经 Replay 巩固后进入的终态。参见 [Statement Bus](v23_05_bus.md)。
- **holder 子图族**：Neocortex 按 holder 将语义层拆分为多个独立子图，各自维护真值，共享 entity 池。`common(A,B)` 子图表示 A 与 B 的 N 元共识池。
- **Persona vs Belief 双通道**：Persona 慢通道每 N 次会话更新一次，单次会话不触动；Belief 快通道实时刷新。两者对应神经科学 dmPFC（快速社会信念更新）与 vmPFC（稳定自我/他人模型）的分工。
- **self_model_anchor vs profile_anchor**：同一 Persona 持有两份锚点。自陈（holder=X，subject=X）优先于他陈（holder≠X，subject=X）。多源 profile_anchor 汇聚且与 self_model_anchor 冲突时，升级为 `suspected_diverge`，交 ToM Engine 仲裁。
- **Container 物化视图**：Personae 与 CommonGround 不是普通 Statement 子区，而是由 Bus.rebuild_container 触发重建的物化视图。CAS 防并发覆盖。参见 [Statement Bus](v23_05_bus.md)。
- **五子区各自更新通道**：Semantic 由 Replay 巩固写入；Procedural 由 Case 集群提升；Norms 由反思周期推断；Personae 由 rebuild_container（慢）；CommonGround 由 grounding act 触发的 rebuild_container。
- **冲突消解决策树**：不同 holder 矛盾直接共存；同 holder 同时间窗矛盾 emit `belief.conflict` 进队列；同 holder 隐式改口则旧版 confidence 衰减、两版共存待仲裁。显式仲裁由 [Reconsolidation Engine](v23_11_reconsolidation.md) 处理。
- 配置：所有 Adapter 与运行时配置采用 JSON 格式，统一 schema 见主文档 §2.0


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
