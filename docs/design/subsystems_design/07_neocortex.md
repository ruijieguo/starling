# Neocortex

## 功能定义

Neocortex 是慢记忆子系统，存储 CONSOLIDATED 状态 Statement，按 holder 分图族组织。它分五子区：Semantic / Procedural / Norms / Personae / CommonGround。其中 Personae 与 CommonGround 是 Container 物化视图（不是 Statement 子区），由 [Statement Bus](v24_05_bus.md) 的 `rebuild_container` 触发更新。

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

Neocortex 不接受直接写入。所有 CONSOLIDATED Statement 必须经 [Statement Bus](v24_05_bus.md) 落库。

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

`belief.conflict` 事件进入 [Reconsolidation Engine](v24_11_reconsolidation.md) 处理队列。

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

- **CONSOLIDATED 状态**：Statement 经 Replay 巩固后进入的终态。参见 [Statement Bus](v24_05_bus.md)。
- **holder 子图族**：Neocortex 按 holder 将语义层拆分为多个独立子图，各自维护真值，共享 entity 池。`common(A,B)` 子图表示 A 与 B 的 N 元共识池。
- **Persona vs Belief 双通道**：Persona 慢通道每 N 次会话更新一次，单次会话不触动；Belief 快通道实时刷新。两者对应神经科学 dmPFC（快速社会信念更新）与 vmPFC（稳定自我/他人模型）的分工。
- **self_model_anchor vs profile_anchor**：同一 Persona 持有两份锚点。自陈（holder=X，subject=X）优先于他陈（holder≠X，subject=X）。多源 profile_anchor 汇聚且与 self_model_anchor 冲突时，升级为 `suspected_diverge`，交 ToM Engine 仲裁。
- **Container 物化视图**：Personae 与 CommonGround 不是普通 Statement 子区，而是由 Bus.rebuild_container 触发重建的物化视图。CAS 防并发覆盖。参见 [Statement Bus](v24_05_bus.md)。
- **五子区各自更新通道**：Semantic 由 Replay 巩固写入；Procedural 由 Case 集群提升；Norms 由反思周期推断；Personae 由 rebuild_container（慢）；CommonGround 由 grounding act 触发的 rebuild_container。
- **冲突消解决策树**：不同 holder 矛盾直接共存；同 holder 同时间窗矛盾 emit `belief.conflict` 进队列；同 holder 隐式改口则旧版 confidence 衰减、两版共存待仲裁。显式仲裁由 [Reconsolidation Engine](v24_11_reconsolidation.md) 处理。
- 配置：所有 Adapter 与运行时配置采用 JSON 格式，统一 schema 见主文档 §2.0
