<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **R3.1 实评收口（2026-09-20）**：抽取上限提升至 8192 后未观察到截断，但严格 C++ 合同仍拒绝 3 次 schema 和 1 次 envelope 响应；57 题完成 6 题、30 题技术失败，不能宣称语义抽取或 QA 提升。当前仅保留为诊断配置，生产默认不变。详见 [R3.1 评测报告](../../eval/2026-09-20-socialmem-r31-extraction-capacity.md)。

> **R3.1 抽取容量诊断设计（2026-09-20）**：C++ 抽取和解析职责不变；评测编排仅为五个结构化 arm 传递 8192 抽取上限，`sources` 仍为 4096，回答/裁判和失败协议不变。真实评测尚待执行，不能把容量变化预先宣称为谓词或 QA 提升。详见 [R3.1 设计](../../superpowers/specs/2026-09-20-socialmem-r31-extraction-capacity-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# Neocortex
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **语义证据契约状态（2026-09-12）**：已实现并通过完整工程验证；真实诊断已完成并核验，质量门槛未通过，默认关闭，设计见 [Source-Grounded Claim Contract](../../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md)。Neocortex 不新增事实表；按已确认契约 Statement 携带的 SemanticClaimEvidence 随慢通道巩固与 Container 物化复制，派生 Statement 仍必须通过 derived_from 追溯。

## 2026-09-11 语义证据契约

Container 保存 Statement 引用，原始证据仍由主表和 Engram 支持。巩固原 Statement 不修改 semantic_claim_json；新摘要或抽象是新命题，只能保留 tenant 范围内的父链，不能继承父命题的直接准入证书。本文的“复制证据”仅指保留未变命题的引用，不表示摘要获得直接来源资格。

实现状态与评测证据统一见 [同步清单](../claim_contract_sync.md)。

## 功能定义

Neocortex 是慢记忆子系统，存储 CONSOLIDATED 状态 Statement，按 holder 分图族组织。它分五子区：Semantic / Procedural / Norms / Personae / CommonGround。其中 Personae 与 CommonGround 是 Container 物化视图（不是 Statement 子区），由 [Statement Bus](05_bus.md) 的 `rebuild_container` 触发更新。

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

Neocortex 不接受直接写入。所有 CONSOLIDATED Statement 必须经 [Statement Bus](05_bus.md) 落库。

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

`belief.conflict` 事件进入 [Reconsolidation Engine](11_reconsolidation.md) 处理队列。

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

- **CONSOLIDATED 状态**：Statement 经 Replay 巩固后进入的终态。参见 [Statement Bus](05_bus.md)。
- **holder 子图族**：Neocortex 按 holder 将语义层拆分为多个独立子图，各自维护真值，共享 entity 池。`common(A,B)` 子图表示 A 与 B 的 N 元共识池。
- **Persona vs Belief 双通道**：Persona 慢通道每 N 次会话更新一次，单次会话不触动；Belief 快通道实时刷新。两者对应神经科学 dmPFC（快速社会信念更新）与 vmPFC（稳定自我/他人模型）的分工。
- **self_model_anchor vs profile_anchor**：同一 Persona 持有两份锚点。自陈（holder=X，subject=X）优先于他陈（holder≠X，subject=X）。多源 profile_anchor 汇聚且与 self_model_anchor 冲突时，升级为 `suspected_diverge`，交 ToM Engine 仲裁。
- **Container 物化视图**：Personae 与 CommonGround 不是普通 Statement 子区，而是由 Bus.rebuild_container 触发重建的物化视图。CAS 防并发覆盖。参见 [Statement Bus](05_bus.md)。
- **五子区各自更新通道**：Semantic 由 Replay 巩固写入；Procedural 由 Case 集群提升；Norms 由反思周期推断；Personae 由 rebuild_container（慢）；CommonGround 由 grounding act 触发的 rebuild_container。
- **冲突消解决策树**：不同 holder 矛盾直接共存；同 holder 同时间窗矛盾 emit `belief.conflict` 进队列；同 holder 隐式改口则旧版 confidence 衰减、两版共存待仲裁。显式仲裁由 [Reconsolidation Engine](11_reconsolidation.md) 处理。
- 配置：所有 Adapter 与运行时配置采用 JSON 格式，统一 schema 见主文档 §2.0


## 来源话轮实现核对（2026-09-12）

版本化来源话轮由 C++ 生成与解析，直接证据回读共用严格验证。该子系统继续消费已有证据与时间契约，不新增语言 binding 中的语义逻辑。来源观察时间不作为绝对事件时间；本轮核对与诊断统一见 [设计同步清单](../claim_contract_sync.md) 和 [来源话轮评测报告](../../eval/2026-09-12-socialmem-source-turn.md)。


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](../../superpowers/specs/2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](../../eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](../../superpowers/specs/2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已完成并由原生验证器核验为 `verified / complete_with_errors`：140 条重放、144 个数据库；固定候选 56/64（TP 30、TN 26、误收 0、误拒 1、技术失败 7），synthetic 冻结 11/16、契约 11/16（有效分母 15/16），P1 combined F1 为 holder 0.7317、holder/perspective 0.6829、predicate/object 0.7683；扩展标签 object/topic/scope/time/joint 为 12/14、2/14、12/14、12/14、2/14（有效目标 13）；Q1/Q9 的 baseline、structured、linked 均为 0/3，full 均为 3/3；实际证据链仍受入库与证据聚合限制。原生技术失败共 10 条，主要为重复 JSON 键和准入 JSON 后追加文本；无效裁判票 0。`promotion_ready=false`，生产默认保持关闭，不运行 1,031 题全量。默认、原标签、检索与历史归档保持。

## R2 谓词覆盖扩展设计同步（2026-09-20）

本阶段承接结构化覆盖诊断和 SourceTurn/三通道回执修复，目标是补齐结构化合同与 legacy mental-state 之间的能力断层。C++ 原生目录版本升级为 `claim-predicate-v3`，新增 `prefers`、`promises`、`doubts`、`believes`、`responsible_for`、`requires`、`forbids` 七类规范谓词及受控别名；既有谓词、来源证据、admission 和持久化格式保持兼容。目录、别名、语义族、允许模态/极性、抽取提示和准入提示均由 C++ `PredicateCatalog` 唯一生成，Python 只绑定、编排和归档，不维护第二份语义逻辑。

本阶段严格执行中文设计文档 → C++/Python RED 测试 → C++ 实现 → 固定协议回归。测试覆盖中英文正反例、错误模态、主体与对象保真、admission 拒绝计数、`knows` 历史模态兼容、三通道证据回读和 Python binding 边界。新增结构化声明数量或离线测试通过率不等于 QA/F1 提升；只有 7/7 scope、36/36 holder 的同协议 SocialMemBench 结果和预注册统计门槛满足后，才讨论晋升。生产默认仍保持 `semantic_claim_contract=false`。

## R2.1 结构化输出协议修正（2026-09-20）

首次 `claim-predicate-v3` 固定评测中，qwen3.8-27b 在 legacy 结构化请求下出现截断、未转义 JSON 和证据范围不完整，57 题中 47 题在抽取建库阶段失败。该结果只说明协议性技术失败，不能解释为谓词扩展导致 QA 下降。下一轮由 C++ `OpenAIAdapter::extract_with_contract` 使用 `ValidationPolicy.claim_output_mode=JsonObject` 发送原生 `response_format`；C++ 继续执行 envelope、schema、scope、admission 和持久化校验，Python 仅传递配置和归档回执，不清洗模型文本。生产默认仍为 `semantic_claim_contract=false`、`claim_output_mode=Legacy`；新评测必须使用独立身份并分别报告技术完成率和 QA。

## R2.2 结构化输出末端格式提醒（2026-09-20）

Neocortex 的结构化抽取提示由 C++ 在不可信来源数据之后追加顶层字段格式检查，避免模型将 statement 字段误放入 evidence。此处只约束 wire shape，不放宽声明合同；不符合格式的响应仍进入原生失败回执，不经 Python 清洗。

## R2.3 重复键与布局对照（2026-09-20）

Neocortex 抽取提示现在额外要求同一 JSON 对象不得重复 key，并以占位 BAD/GOOD 对照强化 statement/evidence 层级；重复键和错误层级仍由 C++ 原生解析拒绝。

### R2.3 实评证据收口（2026-09-20）

独立网络评测完成 57/57 题，7/57 正确、26/57 技术失败；4/7 scope 完成，holder 为 19/36。失败包括重复 `time_text`/`topic` 的 `envelope_failure`、抽取超时、抽取/回答 `completion_truncated`。两轮共同完整题目只有 17 题，不能从 15/57 与 7/57 的非配对差异推断提示因果收益。当前仍保持 C++ 严格拒绝和 Python 仅 binding/编排，生产默认 `semantic_claim_contract=false`；完整证据见 [R2.3 鲁棒性评测报告](../../eval/2026-09-20-socialmem-structured-output-robustness.md)。

## R3.2 结构化抽取信封（2026-09-20）

结构化抽取的末端格式由 C++ `claim_contract.cpp` 唯一生成：statement 的关系字段固定在顶层，`evidence` 只承载来源字段；重复 key、误嵌套、缺字段和额外字段继续由原生合同拒绝。R3.2 当前处于设计阶段，尚未改变谓词目录、写入或生产默认。

## R3.2 语义诊断与 R3.3 证据覆盖（2026-09-21）

R3.2 已验证结构化协议边界，但成功子集仅 23.21%。错误题逐条关联显示，主要短板是 Neocortex 的来源证据覆盖：26 道错误题的来源和声明均未命中金标话轮，Q8 跨 session 变化、Q7 关系和 Q1/Q5 主体归属最明显。Neocortex 不把统一摄入时间当作事件时间，也不把单条声明扩展成未验证的历史模式。

R3.3 的来源 coverage、早晚 session 组织和 hybrid SOURCE 配额仍全部在 C++ retrieval core 中实现；结构化声明的解析、谓词目录和证据证书继续由 `claim_contract` 唯一维护。评测中的来源命中只作为检索诊断，不能替代事实语义验证或生产质量门槛。

R3.3 实跑完成 57 题、19 题技术失败，5/7 scope 和 23/36 holder 完成；正常题中来源配额 38/38 达成。来源覆盖改善没有达到问答晋升门槛，后续先修复抽取协议和 scope 稳定性。

## R3.4 抽取协议纠错重试（2026-09-21）

R3.3 的重复 key 与目录外谓词失败只说明输出协议不稳定。R3.4 在 C++ Neocortex 抽取边界增加可配置且最多一次的 `envelope_failure/schema_failure` 重试；原始响应不修补，语义拒绝不重试，Python 只传递 policy。真实质量仍需独立 57 题同协议复测，不能由重试次数或声明数量代替 QA。

## R3.5 Holder 级失败证据（2026-09-21）

R3.5 将失败影响从 scope 降到 holder：C++ 负责批量 holder 的独立抽取和提交，协议、传输或持久化失败只结束当前 holder，后续 holder 继续。`ParseError.field_path` 和字段级纠错摘要进入每个 attempt receipt；C++ 另外生成 holder 级 `failure_detail`，失败 holder 也必须保留三通道回执，禁止用空声明冒充成功。partial scope 只作为带失败标记的诊断输入，Cognizer 不从缺失 holder 补写关系或心理状态。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
