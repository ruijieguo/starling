# Anima Memory v3:多主体社会心智 + 类脑动力学的智能体记忆系统设计方案

> **版本说明**:本文为 v3,基于 v2(`04_anima_design_v2.md`)经资深架构师审查后修正所有交叉引用错误、参数不一致、字段缺失等问题。设计本体未变,可读性与可施工性显著提升。
>
> **v3 相对 v2 的修复**(详见 §17.2 v3 修复记录):
> 1. **修复 §15 评测表的 9 处章节交叉引用错位**(根因:v2 把 Reconsolidation 提为独立 §11 后,后续章节整体后移一位但评测表未同步)
> 2. 统一可塑窗口默认值(§11.1 与 §19 风险 #7)
> 3. Statement schema 补 `replay_count / last_replayed` 字段(§10.2 采样器需要)
> 4. §17 changelog 修正 enforcement_history 误归 Reconsolidation 的错误
> 5. §7.4 双通道补 self_model_anchor / profile_anchor 说明
> 6. §3.4 状态图补 CommonGround 例外标注
> 7. §6.2 "对数似然反向" → "负对数似然"
> 8. 统一术语:Mentalizing Primitives(API/原语命名一致)
> 9. §13.7 与 §13.3 abstain 合并去重
> 10. §10.3 reconcile 明确导向 §11(消除"两套机制"歧义)
> 11. 新增 §14.4 Prospective Loop 触发端到端流程示例
> 12. 删除 §11.4 等处的重复自夸(集中到附录 A)
>
> **沿袭 v2 的设计本体**(详见 §17.1 v1→v2 变更):
> - 三条公理 + 12 层架构 + Statement 中心数据模型
> - Reconsolidation 作为独立第一性章节(§11)
> - 7 步 Retrieval Planner + 8 标签 Context Pack
> - Commitment 状态机 + 4 类 Trigger
> - AffectVector 五维 + salience 显式公式
> - Substrate Adapter 5 profiles
> - 与 8 项目能力对照表 + "为什么更懂人"的认知科学解释

---

## 0. 摘要(One Page)

**Anima v2 解决一个问题**:让 LLM Agent 像人一样,**对每个交互对象都形成一份"持续演化的他者画像 + 我对他的信念 + 我以为他相信什么"**,并且这套画像在系统层面具备类脑的"快写慢洗、优先重放、再巩固、自适应遗忘、显著性调制、前瞻触发"动力学,而不是停在"user_id 隔离 + 向量库 RAG"这种工程层抽象上。

**七大差异点**(在 8 个开源项目集体缺失之处):
1. **Cognizer 一等公民**:认知主体而非 user_id 字段。
2. **Statement 替代 Fact**:所有写入都是"谁,在何时,基于何证据,对谁,以何样态、何极性,持有何判断"。
3. **二阶 ToM 数据模型**:嵌套 Statement + nesting_depth。
4. **类脑五维状态机**:`consolidation_state ∈ {VOLATILE, REPLAYING, CONSOLIDATED, ARCHIVED, FORGOTTEN}` 贯穿全生命周期。
5. **Reconsolidation 不覆盖**:被回忆即开启可塑窗口,旧版本进 supersedes 链而非删除。
6. **真前瞻**:Trigger 类型化 + Commitment 五态机。
7. **视角化检索 + 心智摘要输出**:Retrieval Planner 9 Intent × Perspective Filter × Affect Reranker × Context Pack Builder × **Mentalizing Primitives**(7 高阶认知原语)。

**关键非目标**:不重写向量库、不做训练、不追求形式化完备。Anima 是数据模型 + 运行时调度 + 检索规划器,可挂在 mem0 / Letta / cognee / Graphiti 之上。

---

## 1. 三条公理

### 公理 I:**没有孤立的事实,只有归属于主体的陈述**

每条记忆必须是 `Statement(holder, subject, predicate, object, modality, polarity, time, evidence, confidence)`。这一条同时解决:归属、冲突、撤回、视角、二阶 ToM。

### 公理 II:**记忆系统由两套时���尺度的子系统协同 —— 海马式快、新皮层式慢(CLS)**

写入先入 Hippocampus(`VOLATILE`),经 Replay(`REPLAYING`)、模式分离/补全、再巩固(`CONSOLIDATED`),才有机会上升到 Neocortex 稳定语义/规范/技能/画像。

### 公理 III:**记忆为当前目标重构,不是录像回放(Conway SMS)**

检索不是 fan-out 工具堆,而是按 `(querier, perspective, intent, goal)` 重构出的视角化心智摘要,且具备显式 abstention。

---

## 2. 系统总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Anima Memory Runtime v2                            │
│                                                                         │
│  ┌────────────────┐                          ┌────────────────────┐    │
│  │  Cognizer Hub  │ ◄──── 视角/信念 ────►    │   ToM Engine       │    │
│  │ (主体 + 画像   │                          │  (Belief Tracker + │    │
│  │  + trust)      │                          │   Mentalizing API) │    │
│  └────────┬───────┘                          └─────────┬──────────┘    │
│           │                                            │               │
│           ▼                                            ▼               │
│  ┌──────────────────── Statement Bus(总线) ──────────────────────┐  │
│  │ (Validator + Conflict Probe + Reconsolidation Trigger)         │  │
│  └────────────────────────────────────────────────────────────────┘  │
│       ▲                          │                                    │
│       │ 写入                     ▼ 检索/注入                          │
│  ┌────┴──────────┐         ┌─────────────────────────┐                │
│  │ Hippocampus   │ ─重放─► │      Neocortex          │                │
│  │ ─────────     │         │ ──────────────────      │                │
│  │ • Drawer      │ ◄─补全─ │ • Semantic (KG, holder子图族) │          │
│  │   (verbatim)  │         │ • Procedural (Skills)   │                │
│  │ • Episodes    │         │ • Norms (规范库)        │                │
│  │ • Working Set │         │ • Personae (画像)       │                │
│  │ • Affect Buf  │         │ • CommonGround (共识池) │                │
│  └────┬──────────┘         └────────────┬────────────┘                │
│       │                                  │                            │
│       ▼                                  ▼                            │
│  ┌───────────────────────────────────────────────────────────┐        │
│  │ Replay Scheduler + Reconsolidation + Prospective Loop     │        │
│  │ (优先级重放 + 可塑性再巩固 + 承诺触发 + 自适应遗忘)         │        │
│  └───────────────────────────────────────────────────────────┘        │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────┐        │
│  │ Perspective-aware Retrieval Planner                       │        │
│  │ (9 Intent → Multi-Channel → Perspective Filter →          │        │
│  │   Affect Reranker → Context Pack Builder + Abstention)    │        │
│  └───────────────────────────────────────────────────────────┘        │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────┐        │
│  │ Substrate Adapter:Vector / Graph / KV / Drawer / Git      │        │
│  │ (5 profiles:local-lite / local-graph / cloud-graphiti /   │        │
│  │   letta-bridge / cognee-bridge)                           │        │
│  └───────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
```

**12 个层级**(下文逐节展开):
1. Substrate Adapter — 底层存储抽象(§4)
2. Statement Bus — 全局陈述总线(§5)
3. Hippocampus — 快记忆(§6)
4. Neocortex — 慢记忆(§7)
5. Cognizer Hub — 主体画像与边界(§8)
6. ToM Engine — 多阶信念追踪 + Mentalizing API(§9)
7. Replay Scheduler — 优先级重放(§10)
8. **Reconsolidation Engine** — 被回忆即可塑(§11,v2 新增独立章)
9. Prospective Loop — 承诺与触发器(§12)
10. Retrieval Planner — 视角感知检索 + 心智摘要(§13)
11. 端到端数据流(§14)
12. 评测、路线图、取舍、风险、复用对照、变更记录、致谢(§15-§21)

---

## 3. 数据模型(本体层)

> **设计原则**:所有可写入都是 `Statement` 的子类(灵感:cognee DataPoint Annotated 子类化)。**五类记忆是 Statement 上的视图,不是物理分表**(吸收 Polis §3.3)。

### 3.1 Cognizer:认知主体

```python
class Cognizer(BaseEntity):
    id: UUID                                # UUID5 from (kind, external_id)
    kind: Literal["self","human","agent","group","role","external"]
    canonical_name: str                     # 规范名(v2 新增)
    aliases: list[str]                      # "老张" / "Zhang Wei" / "user_42"  (v2 新增)
    external_id: str                        # 跨系统稳定 id
    persona: PersonaRef                     # 长期画像(慢通道,见 §3.6)
    knowledge_frontier: KnowledgeFrontier   # 知识边界
    relations: list[RelationEdge]           # 与其他 Cognizer 的关系
    trust_priors: dict[CognizerId, float]   # 该主体对他人的先验信任 (v2 新增)
    permissions: AccessPolicy
    created_at: datetime
    last_seen_at: datetime
```

**关键差异**:
- `aliases / canonical_name` 解决跨数据源主体归一(吸收 Polis);
- `trust_priors` 是该主体**对他人**的信任先验(注意:不是系统对他的信任),用于在该主体作为 holder 持有"X 说 Y 这件事"时,系统可以在他的视角下评估证据可信度。

### 3.2 Statement:核心原子(v2 完整版)

```python
class Statement(BaseEntity):
    id: ULID
    # —— 主体维度 —— 
    holder: CognizerRef                     # 谁持有
    holder_perspective: Perspective         # FIRST_PERSON | QUOTED | INFERRED | HEARSAY (v2 新增)
    # —— 内容维度 —— 
    subject: CognizerRef | EntityRef
    predicate: PredicateURI                 # 受控核心集 + 可扩展
    object: Value | StatementRef            # 可递归 → 二阶 ToM
    modality: Modality                      # 见 §3.3
    polarity: Literal["POS","NEG","UNKNOWN"]   # v2 新增,与 modality 正交
    confidence: float                       # 0..1
    # —— 时间维度(5 种,v2 补全) —— 
    event_time: Optional[TimeRange]         # 事件本身发生
    observed_at: datetime                   # 写入时观察到
    inferred_at: Optional[datetime]         # v2 新增:系统推断时刻
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    # —— 证据与归因 —— 
    evidence: list[EvidenceRef]             # 必须 ≥1 条 DrawerRef
    derived_from: list[StatementRef]        # 推断链
    perceived_by: list[CognizerRef]         # 信息可见性(谁在场/被告知)
    supersedes: Optional[StatementRef]
    # —— 类脑动力学 —— 
    salience: float                         # 显著性
    affect: AffectVector                    # (valence, arousal, dominance, novelty, stakes)
    activation: float                       # 当前激活水平
    last_accessed: datetime
    access_count: int
    last_replayed: Optional[datetime]       # v3 新增:Replay Scheduler 上次采样
    replay_count: int = 0                   # v3 新增:已被重放次数
    consolidation_state: ConsolidationState  # v2 新增,见 §3.4
    nesting_depth: int                      # 嵌套深度(0=一阶,1=二阶,2=三阶)
    # —— 治理 —— 
    visibility: VisibilityScope
    retention_policy: RetentionPolicy
```

**`object` 可递归引用 Statement** —— 二阶 ToM 的天然承载。例:

```
S1: holder=Alice, predicate=BELIEVES, polarity=POS, object=
    S2: holder=Bob, predicate=KNOWS, polarity=POS, object=
        S3: subject=Project_X, predicate=delayed, polarity=POS
```

读作:Alice 相信 Bob 知道项目 X 延期了。

### 3.3 Modality(11 类,BDI + 规范 + 撤回)

```
BELIEVES   — A 相信(可错)
KNOWS      — A 知道(蕴含真;默认转 BELIEVES,慎用)
ASSUMES    — A 假设(置信低)
DOUBTS     — A 怀疑
DESIRES    — A 想要
INTENDS    — A 计划
COMMITS    — A 承诺(进入 Prospective Loop)
PREFERS    — A 偏好 X 胜过 Y
NORM_OUGHT — 应当
NORM_FORBID— 禁止
RECANTED   — 撤回(供 supersedes 链)
```

**polarity 与 modality 正交**(吸收 Polis):
- `BELIEVES + POS`:相信 X 成立
- `BELIEVES + NEG`:相信 X 不成立
- `DOUBTS + POS`:怀疑 X 成立
- `KNOWS + UNKNOWN`:知道某事但不知其值(如"知道有人偷了车,但不知是谁")

### 3.4 ConsolidationState 状态机(v2 显式)

```
                ┌──── reconsolidate ◄────┐
                │                        │
   write   ┌────▼───────┐           ┌────┴──────────┐
   ─────►  │  VOLATILE  │── replay──►│  REPLAYING   │
           └────────────┘           └────┬──────────┘
                                         │
                                         │ commit
                                         ▼
                                  ┌──────────────┐
                                  │ CONSOLIDATED │
                                  └────┬─────┬───┘
                                  decay│     │recall
                                       ▼     │
                                  ┌─────────┐│
                                  │ ARCHIVED│◄┘
                                  └────┬────┘
                                       │ purge (合规/失效)
                                       ▼
                                  ┌──────────┐
                                  │ FORGOTTEN│  (软删,Drawer 永留)
                                  └──────────┘
```

**状态语义**:
- `VOLATILE`:刚写入海马,未巩固;
- `REPLAYING`:被 Replay Scheduler 选中或被检索召回(可塑窗口);
- `CONSOLIDATED`:已沉到新皮层语义层;
- `ARCHIVED`:长期未召回,从热路径移除但保留;
- `FORGOTTEN`:逻辑删,Drawer 原档**永不删**。

**迁移例外**(v3 显式):
- `CONSOLIDATED → ARCHIVED` 的 decay 路径**不适用于 CommonGround 中条目**:已 grounded 的共识衰减极慢(§10.4 公式中 `is_grounded` 因子放大 S0),实际很难达到归档阈值。
- 任何 Commitment 状态非 FULFILLED/WITHDRAWN 时**不允许进入 ARCHIVED**(承诺必须留在热路径直到结清)。

### 3.5 五类记忆作为视图(v2 改:不分表)

```
EpisodicView   = WHERE modality=BELIEVES AND event_time IS NOT NULL
                       AND consolidation_state IN (VOLATILE, REPLAYING)
SemanticView   = WHERE modality IN (KNOWS,BELIEVES) 
                       AND consolidation_state = CONSOLIDATED 
                       AND |evidence| ≥ N
ProceduralView = WHERE predicate IN skill_predicates 
                       AND linked Procedure
WorkingView    = WHERE activation > θ_w AND last_accessed within session
ProspectiveView= WHERE modality IN (INTENDS, COMMITS) 
                       AND valid_from > now()
```

**好处**:同一事件可以同时落在多个视图。"Alice 上周答应给我看代码"刚说完时是 Episodic + Prospective;Alice 真看了之后 Commitment 状态 → fulfilled,但 Episode 仍存。

### 3.6 子类(Statement 的特化)

```python
class EpisodicEvent(Statement):
    modality: Literal[BELIEVES] = BELIEVES
    participants: list[CognizerRef]
    location: Optional[Place]
    raw_drawer_ref: DrawerRef
    boundary_score: float                  # EM-LLM 惊奇度

class Commitment(Statement):
    modality: Literal[COMMITS] = COMMITS
    principal: CognizerRef
    beneficiary: CognizerRef
    trigger: Trigger                       # §12.1
    deadline: Optional[datetime]
    state: Literal["ACTIVE","FULFILLED","BROKEN","RENEGOTIATED","WITHDRAWN"]  # v2 增 RENEG

class Norm(Statement):
    modality: Literal[NORM_OUGHT, NORM_FORBID]
    scope: NormScope                       # group/1-1/role
    deontic_strength: float
    enforcement_history: list[EpisodicEventRef]   # v2 新增:被违反/重申的历史

class Skill(Statement):
    modality: Literal[KNOWS] = KNOWS
    procedure: ProcedureSpec
    success_pattern: list[CaseRef]
    maturity: float

class Persona(BaseEntity):
    cognizer: CognizerRef
    traits: dict[str, TraitValue]          # OCEAN / 自定义
    preferences: list[StatementRef]
    competencies: list[StatementRef]
    values: list[StatementRef]
    self_model_anchor: list[StatementRef]  # 该主体对自己的陈述(v2 吸收 Polis)
    profile_anchor: list[StatementRef]     # 他人对该主体的陈述(v2 吸收 Polis)
    relationship_styles: dict[CognizerRef, FiskeMode]

class CommonGround(BaseEntity):
    parties: tuple[CognizerRef, ...]       # 支持 N 元(v2 扩展)
    grounded: list[StatementRef]           # 双方都知道双方都知道
    asserted_unack: list[StatementRef]     # 一方说了对方未确认
    suspected_diverge: list[StatementRef]  # 怀疑对方实际相信不同
    establishment_evidence: list[EpisodicEventRef]  # v2 新增:建立时机
```

### 3.7 关键边类型(社会图谱,v2 完整)

| 边 | 含义 | 语义 |
|---|---|---|
| `BELIEVES_ABOUT` | 主体 → 关于另一主体的信念集 | Alice → Bob 的画像 |
| `TRUSTS` | 加权信任,带情境 | Alice -[trust=0.8 ctx=tech]→ Bob |
| `COMMITTED_TO` | 主体 → 承诺(指 Commitment) | Bob -[deadline=...]→ S(ship_v2) |
| `CONFLICTS_WITH` | 两 Statement 矛盾 | S1 ⨯ S2,带 conflict_type |
| `EVIDENCE_FOR / AGAINST` | 证据关系 | Episode → Statement |
| `SHARED_GROUND` | N 主体共享的共同知识 | {A,B,C} → fact F |
| `OBSERVED_BY` | Episode → 观察者集合 | E → {A,B} |
| `PERCEIVED_BY` | Statement → 感知者集合(v2 强调) | 见 §3.2 字段 |
| `NORM_OF` | Group → Norm | Team -[since=...]→ norm_X |
| `INTENT_OF` | Cognizer → 当前/历史意图 | Alice -[active]→ goal_Y |
| `MAY_OVERLAP_WITH` | 模式分离软边(v2 显式) | 高相似但保留差异 |
| `SUPERSEDES` | 版本链 | S_new -[supersedes]→ S_old |

### 3.8 Drawer:不可被覆盖的原档

任何 Statement 的 `evidence` 必须指向 Drawer 中的 verbatim 片段。Drawer 物理上 append-only,即使 LLM 抽取错误,原档永远在(借鉴 mempalace)。

```python
class DrawerRecord:
    id: UUID
    source: SourceRef
    content: str                           # 100% verbatim
    chunk_index: int
    speaker: Optional[CognizerRef]
    timestamp: datetime
    immutable: True                        # append-only
```

### 3.9 AffectVector(v2 五维)

```python
class AffectVector:
    valence: float    # -1..+1
    arousal: float    #  0..1
    dominance: float  # -1..+1   v2 新增,VAD 三轴完整
    novelty: float    #  0..1
    stakes: float     #  0..1

# 显著性(v2 公式)
salience = (0.4 + 0.6*|valence|) 
         × (0.4 + 0.6*arousal) 
         × (0.3 + 0.7*novelty) 
         × (0.3 + 0.7*stakes) 
         × (0.6 + 0.4*surprise_decay)      # 惊奇度(EM-LLM 风格)
```

salience 在三处生效:
1. **写入打分**:VOLATILE 入队优先级;
2. **重放采样**:Replay Scheduler 权重;
3. **检索重排**:Reranker 乘子。

---

---

## 4. Substrate Adapter:不重造底座

Anima 是中间件而非新数据库。SubstrateAdapter 抽象 5 类底层能力:

| 能力 | 接口 | 推荐底座 |
|---|---|---|
| Vector | `embed / knn / hybrid_search` | Chroma / Qdrant / Milvus / Letta passages |
| Graph | `upsert_node / upsert_edge / cypher_query` | Neo4j / FalkorDB / Graphiti |
| KV / Doc | `put / get / cas / list_by_prefix` | SQLite / Postgres jsonb / Redis |
| Cache(KV-cache) | `store_kv / concat_kv / evict` | MemOS KVCache 风格 |
| BlobStore(Drawer) | append-only,不可覆盖 | S3 / 本地 fs / Letta archival |

**5 个开箱 profile**:
- `local-lite`: SQLite + Chroma + 本地 fs(单机开发)
- `local-graph`: SQLite + FalkorDB + Chroma(单机带图)
- `cloud-graphiti`: Postgres + Graphiti/Neo4j + Qdrant(生产首选)
- `letta-bridge`: 委派 Letta(嵌入既有 Letta 部署)
- `cognee-bridge`: 委派 cognee 存储 + 复用其 DataPoint 子类机制

**对照**:8 个开源项目都把存储绑死。Anima 把"存储绑定"作为部署选项而非架构决策。

---

## 5. Statement Bus:全局陈述总线

所有读写必经 Bus,**不允许直接写存储**(公理 I 的硬约束)。

```
write(stmt)        → Bus → Validator → ConflictProbe → Hippocampus → emit
read(query)        → Bus → RetrievalPlanner → 多源融合 → Result
emit(event)        → Bus → Subscribers(Replay/Reconsolidation/ToM/Prospective)
```

### 5.1 Validator(写入校验)

借鉴 mem0 `filters={}` 契约 + claude-mem 严格 XML:

1. **Schema 校验**:`holder/perspective/modality/polarity/observed_at` 必填;`evidence ≥ 1`。
2. **抽取一致性**:LLM 输出包裹在 `<statement>` XML;非合规拒收。
3. **隐私边界**:Cognizer 的 `knowledge_frontier` 限制其 holder 字段下能持有什么 —— 未到场不能"知道"私密信息。
4. **过度抽取策略**:宁可多建 statement 后期合并(借鉴 Polis §4.1)。

### 5.2 ConflictProbe(冲突探针)

写入前查 (holder, subject, predicate, polarity)。冲突按 §7.3 决策树处理。**关键**:不静默覆盖,而是建立 `CONFLICTS_WITH` 边并触发 Reconsolidation(§11)。

### 5.3 BusEvent

| 事件 | 触发 | 订阅 |
|---|---|---|
| `statement.written` | 写入 Hippocampus 后 | Replay / ToM / Prospective |
| `statement.recalled` | 检索命中 | Reconsolidation(开启可塑窗口) |
| `statement.consolidated` | 通过 Replay 提升 | ToM(更新 Persona) |
| `statement.superseded` | 新版覆盖旧版 | ToM(更新 CommonGround) |
| `commitment.fire` | Trigger 命中 | Prospective(下发提醒) |
| `cognizer.observed` | 主体上线/发声 | ToM(更新可见性) |
| `belief.conflict` | 探针发现矛盾 | Reconsolidation(优先重放仲裁) |
| `norm.violated` | 规范违反 | Affect Buffer(高 salience) |

**对照**:claude-mem 的 5 阶段 hook 是 session 级,Anima 是 statement 级。

---

## 6. Hippocampus:快记忆子系统

> 设计原则:**写得快、原档不丢、稀疏索引、显著性优先、模式分离**。

### 6.1 内部分层

```
┌─ Drawer ─────── verbatim 原档(append-only,immutable)
├─ Episodes ───── 按 EM-LLM 惊奇度切分的事件单元(指向 Drawer)
├─ Working Set ── 当前会话/任务的活跃槽位(Letta Block 风格,带 limit)
└─ Affect Buffer ─ 待巩固的高 salience 事件队列(优先级队列)
```

### 6.2 事件切分(EM-LLM 风格)

LLM 在线计算每条话语相对上一段上下文的 `surprise = -log P(next | context)`(负对数似然),跨阈值即切出 EpisodicEvent。该值同时作为 EpisodicEvent.boundary_score。

### 6.3 模式分离:反相似偏移 + MAY_OVERLAP_WITH(v2 吸收 Polis)

新 Statement 入库前计算与 top-K 已有 Statement 的余弦距离:

```python
def pattern_separation_index(new_stmt, neighbors):
    if max_similarity(new_stmt, neighbors) > θ_sep:
        # 反相似偏移:故意让索引向量远离最近邻(模拟 DG sparse coding)
        new_stmt.index_vector = orthogonalize(
            new_stmt.embedding, 
            against=top_k_neighbors,
            strength=pattern_separation_boost
        )
        # 软边记录"可能重叠",留给后期巩固再决定
        for n in neighbors:
            graph.add_edge(new_stmt, n, kind="MAY_OVERLAP_WITH",
                           similarity=cos(new_stmt, n))
    else:
        new_stmt.index_vector = new_stmt.embedding
```

**与 mem0 的根本区别**:mem0 看到相似就 UPDATE/NOOP;Anima **默认保留差异**,因为细微差异往往是主体视角不同的来源。

### 6.4 模式补全:CA3 风格图游走(v2 工程化)

提供 partial cue,先做向量召回拿种子集,沿 `derived_from / evidence / OBSERVED_BY / SHARED_GROUND / MAY_OVERLAP_WITH` 边做带权游走(类 HippoRAG Personalized PageRank):

```python
def pattern_completion(cue, budget=20):
    seeds = vector_recall(cue, k=5)
    activation = {s: 1.0 for s in seeds}
    for step in range(budget):
        next_acts = {}
        for node, act in activation.items():
            for edge in node.edges:
                w = edge_weight(edge.kind)
                next_acts[edge.target] = next_acts.get(edge.target, 0) + act * w * decay
        activation = merge(activation, next_acts)
        if max(activation.values()) < θ_stop: break
    return as_episodic_subgraph(activation)
```

返回**情节性子图**而非孤立 Statement —— 这才是"补全后的回忆"。

### 6.5 Working Set(显式工作记忆,Letta Block 风格)

```python
class WorkingBlock:
    label: Literal["self_persona","active_persona","current_goal",
                   "interlocutor_persona","common_ground","norm_active",
                   "pending_commitments"]                       # v2 增 pending_commitments
    value: str
    limit: int                                                  # token 上限
    version: int                                                # 乐观锁
    refresh_strategy: Literal["never","per_turn","per_session","on_event"]
```

**8 个开源系统中无一显式注入** `interlocutor_persona / common_ground / pending_commitments` 这三块 —— 这是 Anima 工作记忆的差异点。

### 6.6 Affect Buffer

高 salience 事件进入优先级队列等待重放。**容量满淘汰最低 salience 而非最旧**(借鉴 Anderson adaptive forgetting)。

---

## 7. Neocortex:慢记忆子系统

> 设计原则:**抽象、可查、可推理,但更新需要"通过 Replay/Reconsolidation 才能进入"**。

### 7.1 五个子区

| 子区 | 内容 | 主要承载 | 更新通道 |
|---|---|---|---|
| **Semantic** | 语义事实图 | Statement(BELIEVES/KNOWS,CONSOLIDATED) | Replay 巩固 |
| **Procedural** | 技能/流程 | Skill | Case 集群提升(EverOS 风格) |
| **Norms** | 规范库 | Norm | 反思周期推断 |
| **Personae** | 主体长期画像 | Persona | 慢更新(每 N 次会话) |
| **CommonGround** | N 元共识池 | CommonGround | grounding act 触发 |

### 7.2 holder-aware 图族(关键差异)

Neocortex 的语义层不是单一全局图,而是**按 holder 分层的图族**:

```
GraphFamily = {
    holder=self     : { (subj,pred,obj,t,conf) ... },   # 我自己相信的
    holder=Alice    : { ... },                          # 我以为 Alice 相信的
    holder=Bob      : { ... },
    common(self,Alice)         : { ... },
    common(self,Alice,Bob)     : { ... },               # N 元共识
    ...
}
```

每子图独立维护,共享 entity 池但**不共享真值**。这避免了 mem0/cognee 把 LLM 抽出的命题写为全局事实的污染问题。

### 7.3 冲突消解决策树(v2 完整)

ConflictProbe 发现冲突时不静默覆盖,按以下决策树:

| 情况 | 处理 |
|---|---|
| 同 holder + 时间更晚 + 显式 RECANT | supersedes 链,旧版进历史信念链 |
| 同 holder + 时间更晚 + 隐式改口 | 旧版 confidence 衰减,新版按证据强度,**两版共存**直到 Reconsolidation 仲裁 |
| **不同 holder** | **直接共存**(多视角的本质,**不算冲突**) |
| 同 holder + 同时间窗 + 矛盾 | emit `belief.conflict`,Replay 加重该陈述优先级,**不立即仲裁** |
| 涉及承诺主体改口("我没这么说过") | 触发 audit 流程,evidence 链显式比对 |

### 7.4 Persona ↔ Belief 双通道(神经科学对齐)

呼应 Frith & Frith dmPFC/vmPFC 分工:
- **Persona(慢通道)**:traits / values / preferences / competencies / **self_model_anchor**(该主体对自己的陈述)/ **profile_anchor**(他人对该主体的陈述),**仅由 Replay 周期更新,单次会话不触动**;
- **Belief(快通道)**:holder=X 的 Statement,实时刷新。

**self_model_anchor vs profile_anchor 的工程意义**(v3 显式):同一个 Persona 持有两份锚点 ——
- `self_model_anchor`:该主体自己说过的关于自己的陈述(holder=X, subject=X 的子集);
- `profile_anchor`:他人对该主体的陈述(holder≠X, subject=X 的子集)。

两份锚点在 Persona 更新时分别加权,**自陈优先于他陈**(身份认同的认知规律),但若 profile_anchor 多源汇聚同一 trait 且与 self_model_anchor 冲突,则升级为 `suspected_diverge` 候选,交 ToM Engine 仲裁。

**为什么必须分离**:8 个开源系统(尤其 mem0/memU)把"用户偏好喝咖啡"这种长期 trait 与"用户当前在生气"这种瞬时 belief 写到同一个 profile 里 —— 一次会话就能颠覆长期画像。Anima 的双通道在 schema 层禁止这种污染。

---

## 8. Cognizer Hub:主体注册与画像

### 8.1 Cognizer 生命周期

```
discover → 在 Drawer 中识别新 Cognizer(NER + 对话角色 + alias 归一)
seed     → 初始化空 Persona + 默认 KnowledgeFrontier + trust_priors=neutral
observe  → 每次出场触发 cognizer.observed,更新 last_seen_at
profile  → Replay 周期重写 Persona(慢通道)
archive  → 长期未活跃,降低检索权重(不删)
```

### 8.2 KnowledgeFrontier(知识边界)

```python
class KnowledgeFrontier:
    accessible_sources: list[SourceRef]    # 该主体可访问的信息源
    membership: list[GroupRef]              # 所属群组
    presence_log: list[PresenceWindow]     # 何时何地在场
    explicit_told: list[StatementRef]      # 明确告知
    explicit_not_told: list[StatementRef]  # 明确未告知(用于 surprise)
```

Retrieval Planner 用此对**该 holder 可能知道什么**做硬过滤(EnigmaToM iterative masking 风格)。

### 8.3 Relations(Fiske 四类 + 多维向量)

```python
class RelationEdge:
    a: CognizerRef
    b: CognizerRef
    fiske_weights: dict[Mode, float]       # 该关系在 Communal/Authority/Equality/Market 上的强度
    affinity: float                        # 0..1
    trust: dict[Context, float]            # 不同领域信任不同
    power_asymmetry: float                 # a 对 b 的影响力差(v2 吸收 Polis)
    interaction_history_ref: EpisodeQuery
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
```

**关系本身也是 Statement**(holder 是观察者),所以多视角自然支持:Alice 看到的 Alice-Bob 关系 ≠ Bob 看到的 Alice-Bob 关系。

Style 影响:
- **Communal**:倾向长期主动记忆共享、低形式化提醒;
- **Authority(上行/下行区分)**:下属对上司主动汇报,反之精炼;
- **Market**:对等可审计、强 grounding;
- **Equality**:轮替式 grounding 与责任。

---

## 9. ToM Engine:多阶信念追踪 + Mentalizing Primitives

> ToM Engine 是 §3 schema 之上的"运行时算法集合 + 高阶 API"。

### 9.1 二阶信念的物理实现

二阶信念在 schema 上是嵌套 Statement,**存储展平**为带 `nesting_depth` 的多条:

```
Outer: holder=self, subject=Alice, predicate=BELIEVES, 
       object=ref(Inner), nesting_depth=1
Inner: holder=Alice, subject=Bob, predicate=KNOWS,
       object=ref(Innermost), nesting_depth=2
Innermost: subject=Project_X, predicate=delayed, polarity=POS,
           nesting_depth=2  # 内容陈述
```

**约束**:默认追踪深度 ≤ 2,深度 3 仅显式触发(Kinderman 关于成人三阶 ToM 容量限制)。

### 9.2 Belief Tracker(每回合)

```
1. 抽取本回合产生的新 Statement(LLM tool-call,XML 严格)
2. 判断是否更新某主体的 belief 集
3. 与现有信念冲突 → 打 CONFLICTS_WITH 边
4. confidence 漂移:同主体反复确认 → 上调;反例 → 下调
5. 检测信念修正事件("其实我之前理解错了")→ 触发 Reconsolidation
6. perceived_by 推断:谁在场、谁可见
7. holder 归属判定(说话人 ≠ holder,如"Bob 说他喜欢...")
```

### 9.3 perspective_take 算子(SimToM + EnigmaToM 工程化)

```python
def perspective_take(target: CognizerRef, query: str, time: datetime) -> Context:
    visible = filter_by_frontier(drawer, target, time)        # 1. KnowledgeFrontier 遮蔽
    target_beliefs = neocortex.query(holder=target, time=time)# 2. 取 holder=target 子图
    cg = common_ground(self, target)                           # 3. 共识池
    return Context(visible, target_beliefs, cg)
```

任何对话生成、规划、协商都先 `perspective_take(other)` 取对方视角再决策。**这是 8 个开源系统全部缺失的能力**。

### 9.4 Mentalizing Primitives(7 个高阶认知原语,v2 吸收 Polis)

| API | 含义 | 对应脑区 |
|---|---|---|
| `what_does_X_believe(about=Y)` | X 关于 Y 的信念集 | rTPJ |
| `what_does_X_think_Y_believes(about=Z)` | 二阶 ToM | mPFC |
| `does_X_know(fact)` | X 是否知道(查 X 的 evidence + frontier) | 知识归因 |
| `predict_X_would(in_situation)` | 模拟 X 在某情境下的反应 | simulation theory |
| `find_misalignment(between=[X,Y], about=Z)` | 找 X 和 Y 对 Z 的认知差异 | 冲突检测 |
| `shared_with(members)` | N 主体的 SharedGround | common ground |
| `who_committed(to=Y)` | 关于 Y 的所有未决承诺 | prospective + 社会 |

**这 7 个 Mentalizing Primitives 把 LLM 从"每次重新模拟"中解放出来,系统负责维护可查询的认知状态**。

### 9.5 Grounding Acts(共识池更新,Clark 1996)

| Act | 触发 | 效果 |
|---|---|---|
| Assert | 一方陈述 | 进 `asserted_unack` |
| Acknowledge | 对方确认 | 升级到 `grounded` |
| Repair | 对方质疑 | 退回 `suspected_diverge` |
| Withdraw | 一方撤回 | RECANTED + 从池中移除 |

输出层"已 grounded 不复述,未 grounded 主动 grounding"由 Working Set 中的 `common_ground` block 驱动。

---

---

## 10. Replay Scheduler:优先级重放与巩固

> 这是 Anima 的"睡眠系统",对标 CLS + 海马 SWR(sharp-wave ripple)优先重放。

### 10.1 三种重放模式

| 模式 | 触发 | 任务 |
|---|---|---|
| **Online**(在线) | 每 N 个 statement.written | 即时巩固高 salience 短链 |
| **Idle**(空闲) | Agent 空转 > T 秒 / 用户离开 | 中等强度反思 |
| **Sleep**(深度) | 周期性(每会话结束 / 每日 / 显式 `/sleep`) | 完整 sweep + Persona 更新 |

### 10.2 优先级采样器(SWR 风格)

```python
def sample_weight(stmt):
    return (
        stmt.salience
        * novelty_decay(stmt.last_replayed)
        * (1 + conflict_bonus if stmt.has_conflict else 1)
        * (1 + arousal_bonus * stmt.affect.arousal)        # 高 arousal 多采(模拟杏仁核)
        * goal_relevance(stmt, current_goal)
        / (1 + stmt.replay_count)                          # 已多次重放降权
    )
```

借鉴 prioritized experience replay(Schaul et al. 2015,LLM 端首次系统采纳)。

### 10.3 巩固原子操作集

| 动作 | 输入 | 输出 |
|---|---|---|
| `compress` | 多条相似 EpisodicEvent | 1 条更高层语义 Statement(Drawer 指针保留) |
| `abstract` | 多 holder 的同 predicate | 1 条 Persona trait 更新候选 |
| `reconcile` | 冲突 Statement 集 | **不直接仲裁;将冲突 Statement 集合推入 Reconsolidation Engine(§11)开启可塑窗口,由其结合新证据决定 supersedes 链或共存** |
| `induce_norm` | 多次 PREFERS/COMMITS 同模式 | 1 条 Norm 候选,人工/规则确认入库 |
| `forge_skill` | 多次成功 Case 集群 | 1 条 Skill 候选(EverOS AgentSkill 风格) |
| `decay` | 低 salience 长未召回 | confidence 衰减,达阈值 → ARCHIVED |
| `purge_compliance` | 用户撤回 / 法务事件 | FORGOTTEN + 传播到 derived 链(Drawer 仍留) |

巩固结果带 `derived_from` 指回原 Statement,**不删除原始证据**。

### 10.4 自适应遗忘公式(v2 完整)

借鉴 MemoryBank(Ebbinghaus)+ Anderson active forgetting:

```
S(t) = exp(-Δt / S0(stmt))                                # 召回强度

S0(stmt) = base
         × (1 + 0.5 × access_count)
         × (1 + salience)
         × (1 + 2 × is_grounded)                          # 共识池中条目衰减极慢
         × decay_modifier_by_modality                      # COMMITS 极慢,ASSUMES 快
         × (1 + 0.3 × |affect.valence|)                   # 情感色彩条目衰减略慢

# 状态迁移
state CONSOLIDATED → ARCHIVED  if S(t) < 0.05 AND not in CommonGround
state ARCHIVED     → FORGOTTEN if explicit purge OR retention_policy expired
```

**被 forget 不删 Drawer**,只逻辑下降。**这是与现有系统的本质差异**:claude-mem 的 cynical deletion 真删,Anima 永远可审计。

### 10.5 巩固分层策略(v2 吸收 Polis §4.6)

| 层 | 策略 | 触发条件 |
|---|---|---|
| **Hippocampus 短期** | 指数衰减 + 显著性补偿 | 默认每条 |
| **Episodic 长期** | 重要性 + 关联度排序后修剪 | Replay 每轮 |
| **Semantic** | **不删**,只下调 confidence 或转 OUTDATED | Reconsolidation 失败 |
| **隐私强制** | 硬删传播到所有 derived | 用户/法务事件 |

---

## 11. Reconsolidation Engine:被回忆即可塑(v2 独立章)

> 借鉴 Nader 2000 的再巩固理论 + Anderson 的自适应遗忘。**记忆不是存档而是不断被改写的活物**。

### 11.1 触发条件

任意 CONSOLIDATED Statement 一旦满足以下之一,进入短暂 `REPLAYING` 可塑窗口(**工程默认 30 分钟,可按 modality 与更新频率自适应在 5min–6h 之间调整;Nader 2000 神经科学参考值约 6h**):

1. 被 Retrieval Planner 召回到 Working Set;
2. 被新输入的 Statement 通过 `derived_from` 引用;
3. 被 ConflictProbe 标为冲突候选;
4. 显式 reconsolidate API 调用(audit / 用户编辑场景)。

### 11.2 可塑期内可发生的修改

```python
def reconsolidate(stmt, new_evidence_or_input):
    if supports(new_evidence, stmt):
        stmt.confidence = bayesian_update_up(stmt.confidence, new_evidence.strength)
        stmt.access_count += 1
    elif contradicts(new_evidence, stmt):
        if mild:
            stmt.confidence = bayesian_update_down(stmt.confidence, new_evidence.strength)
        else:
            new_version = stmt.fork(modifications=delta_from(new_evidence))
            new_version.supersedes = stmt.id
            stmt.consolidation_state = ARCHIVED               # 不删
    if affect_change_detected(new_input):
        stmt.affect = blend(stmt.affect, new_input.affect, weight=0.3)  # 情感染色
    schedule_close_plastic_window(stmt, timeout=window_default)  # 30min default,见 §11.1
```

### 11.3 关键差别(对照现有系统)

- **mem0**:UPDATE 直接覆盖,旧值消失。
- **cognee**:improve 框架但权重更新算法 TODO。
- **Letta**:Block version 历史在,但**不区分"是否被回忆触发"**。
- **Anima**:**只有被回忆才能改**,且改完不删旧版,这正是大脑可塑性的工程模拟。

### 11.4 多主体场景的特别处理

当 Alice 说"其实 Bob 上周已经离职了":
1. 不无脑覆盖关于 Bob 的 statement;
2. 检索所有 `subject=Bob && valid_from < 该日期` 的 statement;
3. 每条进入 REPLAYING 可塑窗口;
4. 由 Reconsolidation 用新证据评估 —— 部分加 valid_to 截断,部分仍保留(如"Bob 喜欢 PG"这种与离职无关的 trait)。

---

## 12. Prospective Loop:真前瞻

> 8 个开源系统全部缺失,这是 Anima 与 RMM 之外少数把"前瞻"做成 first-class 的设计。

### 12.1 Trigger 类型系统

```python
class Trigger:
    kind: Literal["time","event","state","compound"]
    spec: TriggerSpec

# 例
TimeTrigger(at=datetime(...))
TimeTrigger(every="1d at 09:00")
EventTrigger(when="cognizer:Alice.observed")
EventTrigger(when="statement.written: predicate=mentions, object=X")
StateTrigger(predicate="goal:onboarding.completed")
CompoundTrigger(all_of=[...])
CompoundTrigger(any_of=[...])
```

### 12.2 Commitment 五态机(v2 增 RENEGOTIATED)

```
created → ACTIVE ──fire──► reminder 注入 Working Set
              │
              ├─ user 履行 ──→ FULFILLED
              ├─ deadline 过 ──→ BROKEN ──→ trust 调降
              ├─ 双方协商 ────→ RENEGOTIATED(新版 supersedes 旧)
              └─ 主动撤回 ────→ WITHDRAWN
```

每条 Commitment 由后台 PolicyEngine 持续监听 Trigger,命中即 emit `commitment.fire`,Working Set 注入 `pending_commitments` block。

### 12.3 与 RMM 互补

- **RMM 的 prospective reflection**:为未来检索友好的摘要(被动);
- **Anima 的 Prospective Loop**:if-then 触发器 + 状态机(主动);

两者**不冲突**,合并产出"既会被动检索友好、又会主动出发"的记忆体。

### 12.4 Norm 与 Commitment 的关系

Norm 是 Group 内的默认规则;违反时 emit `norm.violated`,作为高 salience EpisodicEvent 入 Affect Buffer。Commitment 是个体对个体的具体承诺。两者通过 `induce_norm` 操作(§10.3)连接 —— 多次相似 Commitment 模式可凝结为 Norm 候选。

---

## 13. Retrieval Planner:视角感知检索 + 心智摘要

> 检索是"认知规划器",不是"工具堆"。这是公理 III 的运行时体现。

### 13.1 输入与输出

```python
class Query:
    querier: CognizerRef                   # 谁在问(默认 self)
    perspective: CognizerRef               # 从谁的视角检索(默认 = querier)
    intent: QueryIntent                    # 见 §13.2
    text: str
    time: datetime                         # 检索时间锚("as_of")
    goal_context: Optional[GoalRef]
```

### 13.2 9 种 QueryIntent

```python
class QueryIntent(Enum):
    FACT_LOOKUP        # 查事实
    BELIEF_OF_OTHER    # 查 X 相信什么
    META_BELIEF        # 查 X 以为 Y 知道什么(二阶)
    HISTORY            # 查时间线
    COMMITMENT_DUE     # 查待办
    PREFERENCE         # 查偏好
    NORM_LOOKUP        # 查规范
    COMMON_GROUND      # 查共识
    ABSTAIN_CHECK      # 主动检查"是否真的不知道"
```

### 13.3 7 步规划

```
1. parse:    Query → intent + 关键 entity
2. mask:     按 perspective 的 KnowledgeFrontier 遮蔽不可见证据(EnigmaToM iterative masking)
3. plan:     按 intent 选择路径(下表)
4. fetch:    并发执行多源(向量 / 图 / KG / Drawer / Working Set / ToM API)
5. fuse:     按 holder 子图 + salience + recency 重排
6. ground:   检查 CommonGround,标"已 grounded"以便复述抑制
7. abstain:  Abstention Gate(详见 §13.7)—— 总分不足或证据不可信则输出"无可靠记忆",避免编造
```

### 13.4 Intent → Path 映射

| Intent | 主路径 | 辅助 |
|---|---|---|
| FACT_LOOKUP | Neocortex Semantic(holder=self) + Drawer 证据 | Working Set |
| BELIEF_OF_OTHER | Neocortex Semantic(holder=target) | Drawer 中 target 发言 |
| META_BELIEF | 嵌套 Statement(nesting_depth=2) | perspective_take 即时构建 |
| HISTORY | 时间索引 + supersedes 链 | Drawer time-window |
| COMMITMENT_DUE | Prospective Loop 队列 | — |
| PREFERENCE | Persona.preferences | PREFERS 类 Statement |
| NORM_LOOKUP | Norms 子区 + scope 过滤 | enforcement_history |
| COMMON_GROUND | CommonGround pool(parties=...) | — |
| ABSTAIN_CHECK | 跨子区低召回判定 + 校准置信度 | KnowledgeFrontier |

### 13.5 Affect-aware Reranker

```python
def rerank(candidates, querier_state):
    for c in candidates:
        c.score = (
            base_relevance(c)
            * (1 + 0.3 * recency_factor(c))
            * (1 + 0.4 * c.salience)
            * (1 + 0.3 * activation_level(c))
            * affect_consistency(c.affect, querier_state.affect)  # 情感一致性 boost
        )
    return sorted(candidates, key=lambda c: -c.score)
```

### 13.6 Context Pack Builder:心智摘要(v2 吸收 Polis §6.2)

**关键差异**:Anima 输出的不是一段 RAG 文本,而是**带语用标注的"心智摘要"**:

```
[FACT]   Bob 当前负责 auth(Alice 在 4/15 群聊宣布,共识已建立)
[BELIEF] 据 Carol 所知,新方案下周一上线(置信 0.7,但 Bob 暂未确认)
[HEARSAY] 我听 Alice 说 Bob 上周休假(单一来源,可能过时)
[INFERRED] 根据 Bob 长期工作模式,他可能晚于 deadline 交付
[COMMON]  我们都知道:本季度的目标是发布 v2
[TODO]   你 3/12 答应给 Alice 看代码(还有 2 天)
[CONFLICT] 关于 X 的负责人:Alice 认为是 Bob,Carol 认为是 Dave —— 待澄清
[ABSTAIN] 关于 Y 的最新进展:无可靠记忆(Bob 上次提及在 2 月,之后无更新)
```

**8 个标签**:`FACT / BELIEF / HEARSAY / INFERRED / COMMON / TODO / CONFLICT / ABSTAIN`。

LLM 看到的不是无差别文本块,而是已经被分类、归因、置信度标注的语用结构。**这是 Anima 让 LLM"懂语境"的物理基础**。

### 13.7 Abstention(主动拒答,LongMemEval 关键失分项)

```
abstain if:
    max_score < tau_recall                # 召回分太低
    OR perspective frontier 不允许该信息
    OR 唯一证据来自已 RECANTED 链
    OR conflict 未仲裁(请求澄清而非赌一边)
```

abstain 时输出结构化"我不知道,因为 ___",而非编造或 "I'm not sure"。

---

## 14. 端到端数据流(典型场景)

### 14.1 写入路径

**场景**:Alice 在群聊里说"Bob 不再负责 auth 模块,改由 Carol 接手"。

```
Drawer.append(verbatim Alice 原话, perceived_by=[self,Alice,Bob,Carol,...])
   ↓ EM-LLM 切边界 → EpisodicEvent
   ↓ Pattern Separation:与现有 "Bob responsible_for auth" 高度相似 → 反相似偏移 + MAY_OVERLAP_WITH 软边
   ↓ LLM 抽取 4 条候选 Statement(XML 严格):
[
  S1: holder=self,  subject=Bob,   pred=responsible_for, obj=auth, mod=BELIEVES, pol=NEG, valid_to=NOW
  S2: holder=self,  subject=Carol, pred=responsible_for, obj=auth, mod=BELIEVES, pol=POS, valid_from=NOW
  S3: holder=self,  subject=Alice, pred=BELIEVES, obj=⟨S2⟩, nesting_depth=1   # 二阶
  S4: holder=Alice, subject=Bob,   pred=responsible_for, obj=auth, mod=BELIEVES, pol=NEG, valid_to=NOW
]
   ↓ Validator → ConflictProbe:发现旧 Statement(holder=self, Bob responsible)
   ↓ 决策树:同 holder + 时间更晚 + 隐式改口 → 旧 confidence 衰减,新版共存,触发 Reconsolidation 候选
   ↓ Hippocampus.write × 4(VOLATILE)
   ↓ emit statement.written × 4
   ↓ Affect Scorer:salience 高(stakes 高,涉及职责变更)→ Affect Buffer 优先队列
   ↓ ToM Engine 更新:
       - CommonGround(self,Alice,Bob,Carol):S1/S2 已 grounded(都在场)
       - 若 Bob 不在场 → 不进 (self,Bob) common,只进 (self,Alice/Carol)
       - 触发 perceived_by=[Bob] 检查 → Bob 在 → 标"Bob 应已知"
   ↓ Reconsolidation Engine:旧 Bob 责任 statement 进入 REPLAYING 可塑窗口 5min
       新证据强 → 旧版 supersedes → ARCHIVED(不删)
```

### 14.2 检索路径

**场景**:用户问"Bob 现在还负责 auth 吗?"

```
Query(intent=FACT_LOOKUP, perspective=user, text=...) → Planner
   ↓ parse: subject=Bob, predicate=responsible_for, object=auth
   ↓ mask: querier=user(无遮蔽,user 即 self perspective)
   ↓ plan: FACT_LOOKUP path
   ↓ fetch:
       Neocortex(holder=self).query: 命中 supersedes 链(新 Carro responsible / 旧 Bob ARCHIVED)
       Drawer time-window: 关联 Alice 4/15 原话 + 历史 Bob 持有 auth 的证据
       ToM API: shared_with([self,user]) 检查共识
   ↓ fuse: valid_to 近 + supersedes → "已变更,现 Carol 负责"
   ↓ ground: CommonGround(self,user) 不含此事 → 主动 grounding
   ↓ Reranker: 高 stakes + recency boost
   ↓ Context Pack Builder:
[FACT]    Bob 已不再负责 auth,现由 Carol 接手(Alice 4/15 群聊宣布,evidence: Drawer:abc123)
[HISTORY] Bob 此前负责该模块达 8 个月,如需历史设计讨论我可以拉出
[COMMON]  这是首次告知你,需要确认你已知悉吗?
   ↓ output(经 LLM 渲染)
```

### 14.3 二阶 ToM 路径

**场景**:用户问"Bob 知道这事吗?"

```
Query(intent=META_BELIEF, target=Bob, about=⟨Carol now responsible⟩)
   ↓ Planner → Mentalizing API: does_X_know(X=Bob, fact=⟨...⟩)
   ↓ 检查:
       1. perceived_by 含 Bob? → 检索 Episode 4/15 群聊参与者 → ✓ Bob 在
       2. explicit_told? → 检索后续是否私聊告知 → 无补充
       3. 检索 holder=Bob 近期发言:有无相关动作/提问? → Bob 之后无回应
   ↓ 综合判定:
       Bob 应已知(感知充分)
       但��主动确认 → suspected_diverge 候选
   ↓ Context Pack:
[INFERRED] Bob 当时在群里(perceived_by 命中),应该已知
[HEARSAY]  但他之后没有相关回应,如果重要可以确认
[TODO]     建议:私聊 Bob 确认 + 同步 Carol 接手计划
   ↓ output
```

### 14.4 Prospective Loop 触发路径(v3 新增)

**场景**:周一,Bob 答应"周三前给 Alice 看新方案的草稿"。周三上午 9 点,系统主动触发提醒。

```
─── 周一 14:30 写入阶段 ───
Drawer.append(Bob 原话: "我周三前把草稿发给你", 
              perceived_by=[self, Bob, Alice])
   ↓ EM-LLM boundary_score 高(承诺类话语 surprise 显著)→ EpisodicEvent
   ↓ LLM 抽取(XML strict):
[
  S1: holder=Bob, modality=COMMITS, polarity=POS,
      principal=Bob, beneficiary=Alice,
      subject=Bob, predicate=will_deliver, object=draft,
      trigger=TimeTrigger(at="2026-05-06 09:00"),
      deadline="2026-05-06 23:59",
      state=ACTIVE,
      affect={valence:0.3, arousal:0.4, novelty:0.5, stakes:0.7}
  S2: holder=self, modality=BELIEVES, polarity=POS, object=⟨S1⟩  # self 知道 Bob 答应了
  S3: holder=Alice, modality=BELIEVES, polarity=POS, object=⟨S1⟩  # Alice 也知道(在场)
]
   ↓ Validator + ConflictProbe(无冲突)
   ↓ Hippocampus.write × 3,VOLATILE
   ↓ emit statement.written
   ↓ Prospective Loop 订阅器命中 modality=COMMITS:
       - 注册 TimeTrigger(at=周三 09:00) 到 PolicyEngine
       - 进 Working Set.pending_commitments block
   ↓ CommonGround(self, Bob, Alice).asserted_unack += S1
       (双方都听见,但还没显式 acknowledge → 未到 grounded)
   ↓ Affect Buffer 入队(stakes=0.7,salience 较高)

─── 周一晚 ~ 周二 巩固阶段 ───
Replay Scheduler(Idle 模式,优先级采样 S1 高权重)
   ↓ 不仲裁(��冲突),但加强 activation
   ↓ S1 进 CONSOLIDATED,Commitment.state 仍 ACTIVE
   ↓ Reconsolidation 监听:无新证据,跳过

─── 周三 09:00 触发阶段 ───
PolicyEngine 后台轮询 Trigger 队列
   ↓ TimeTrigger 命中 → emit commitment.fire(S1)
   ↓ Working Set.pending_commitments 注入提醒
   ↓ 系统自主决策:
       检查 holder=Bob 子图:Bob 周二是否有"已发草稿"的 statement? → 无
       检查 Drawer 周二消息:Bob 是否单方面 RENEGOTIATE? → 无
       检查 perceived_by=[self,Bob,Alice]:此时谁在线? → self 与用户在线
   ↓ Retrieval Planner(intent=COMMITMENT_DUE)生成 Context Pack:
[TODO]    Bob 答应今天前把方案草稿发给 Alice(周一约定,evidence: Drawer:xyz)
[FACT]    截至现在尚未看到草稿,Alice 也未确认收到
[COMMON]  这是 Bob 与 Alice 的共识(你也在场)
[INFERRED] 建议:可以提醒 Bob,或先问 Alice 是否已私下收到
   ↓ output: agent 主动开启对话:
     "对了,Bob 周一答应今天前给 Alice 看草稿,但我没看到他发出来。
      要不要我帮你提醒一下?"

─── 后续(假设 Bob 当天交付)───
   ↓ 检测到 Bob 发送 draft(新 EpisodicEvent → 抽取 fulfilled_by 关联)
   ↓ Prospective Loop:Commitment.state ACTIVE → FULFILLED
   ↓ trust_priors[self→Bob] 微调上(履行成功)
   ↓ CommonGround(self,Bob,Alice).grounded += S1
   ↓ Reconsolidation:S1 进 REPLAYING 可塑窗口,
       结合"已履行"事实,confidence ↑,加 evidence_for 边
```

**关键差异点**:8 个开源系统没有任何一个能在没有用户手动 query 的情况下"周三早上自己想起来这件事"。Anima 通过 Trigger + PolicyEngine 把"主动惦记"做成了运行时一等公民 —— 不依赖 cron job 或外部 reminder,而是从 Statement 数据本身派生触发条件。

---

## 15. 评测体系

Anima 的评测不能止于 RAG/QA 指标 —— 类脑记忆的"更像人"和社会心智的"更懂人"需要专门的评测维度。

### 15.1 类脑记忆评测

| 评测项 | 方法 / 数据集 | 核心指标 | Anima 对应机制 |
|---|---|---|---|
| 长期多会话回忆 | LongMemEval 五类问题(单跳/多跳/时间/更新/缺失) | 分类 accuracy | Statement 抽取 + holder 归属(§3.2)+ Replay 巩固(§10) |
| 时序推理 | LoCoMo 时间线 / 自建时间锚点 QA | 时间顺序正确率、valid_from/to 边界准确率 | §3.2 五种时间字段 + §13 time-aware planner |
| 模式补全质量 | 自建:给 partial cue(如"那次和 Alice 去的咖啡馆"),评估回忆完整度 | Recall@k of related episode subgraph | CA3-style PPR 图游走(§6.4) |
| 模式分离能力 | 注入高度相似但不同的两个 episode,检查是否混淆 | 混淆率(越低越好) | 写入反相似性偏移 + MAY_OVERLAP_WITH 软边(§6.3) |
| 巩固一致性 | 注入冲突信息,检验多视角保留 | 冲突保留率 + supersedes 链完整率 | 冲突决策树(§7.3)+ Reconsolidation 不覆盖(§11) |
| 自适应遗忘 | 注入大量噪声 statement,观察查询效率 | Latency vs total memory size 曲线,关键记忆保留率 | MemoryBank + Anderson 公式 + 降级不删除(§10.4) |
| 情感记忆偏置 | 配对高/低情感事件,间隔测试 | 高情感事件回忆优势比(模拟人类效应) | AffectVector.salience 调制写入强度与重放优先级(§3.9 + §10.2) |
| 再巩固保真度 | 注入需修正的旧信念,检查修正后旧版本可追溯性 | 旧版本可检索率、新版本引用率 | Reconsolidation 状态机(§11)+ supersedes 链保留历史(§7.3) |

### 15.2 社会心智评测

| 评测项 | 方法 / 数据集 | 核心指标 | Anima 对应机制 |
|---|---|---|---|
| 一阶 ToM(信念归因) | ToMBench / SocialIQA | 信念归因 accuracy | holder=other 子图(§7.2)+ KnowledgeFrontier mask(§8.2) |
| 二阶 ToM(嵌套信念) | FANToM / Hi-ToM / EnigmaToM | 嵌套信念 accuracy | 嵌套 Statement nesting_depth(§9.1) |
| 信息不对称(FANToM) | FANToM 标准集 | 不对称检测 F1 | perceived_by + presence_log(§3.2 + §8.2) |
| 多视角切换(SoMi) | SoMi-ToM 1225 题(第一/第三人称双视角) | viewer-conditioned QA accuracy | perspective_take 算子(§9.3)+ holder-aware 检索(§7.2) |
| 共同知识建立 | 自建:多主体对话中追踪 SharedGround | common ground inference F1 | CommonGround pool(§3.6)+ explicit grounding acts(§9.5) |
| 承诺履行 | 自建:对话中含承诺,检验 N 步后触发 | Commitment detection + reminder timeliness | Prospective Loop + Trigger 类型系统(§12) |
| 信念修正传播 | 注入"其实...是错的"修正,看关联信念是否联动更新 | 旧信念使用率(应趋零) + 旧版本可追溯性 | Reconsolidation 多主体处理(§11.4)+ supersedes 链 |
| 视角泄露防护 | 自建:检查是否向未在场者泄露信息 | 视角泄露率(应趋零) | EnigmaToM 风格 iterative masking + perspective filter(§13.3 step 2) |
| 二阶 ToM 主动提示 | 自建:"你应该提醒 Bob,他可能还不知道..." | 主动提示 precision/recall | META_BELIEF QueryIntent(§13.2)+ suspected_diverge 标记(§3.6 CommonGround) |

### 15.3 主观评测

- **Persona 稳定性**:Anima 加持的 agent 在多轮对话中是否保持对用户的理解一致,不被单次对话颠覆长期画像。度量:注入前后 Persona Statement 的 drift 距离。
- **"懂我"主观评分**:7-point Likert,覆盖(记得我的偏好 / 知道我和别人的关系 / 不会把别人的话当成我的 / 会主动惦记我的承诺 / 说错了能追溯)。
- **可解释性**:当 agent 输出错误信念时,用户能否追溯到具体 Statement + evidence(Drawer 指针)。度量:错误定位时间。
- **过度自信拒绝率**:Abstention 判定在实际对话中的 precision/recall(该拒时有没有拒、不该拒时有没有乱拒)。

### 15.4 评测执行策略

- **Phase 0-1**:单元测试覆盖 schema 正确性 + 50 条对话样本的手工标注回归集。
- **Phase 2-3**:LongMemEval 子集 + ToMBench / FANToM 标准集 + 自建承诺履行集(100 条)。
- **Phase 4+**:LoCoMo 全量 + SoMi-ToM 1225 题 + 自建二阶 ToM 主动提示集 + 用户主观评测(A/B 对照,Anima vs 纯 RAG baseline)。

---

## 16. 路线图

### 16.1 六阶段交付

| 阶段 | 时间 | 目标 | 核心交付 | 验证方式 |
|---|---|---|---|---|
| **P0 Spike** | 2 周 | 数据模型冻结 | Statement + Cognizer + ConsolidationState 的 Pydantic 实现与 JSON-Schema 导出;SQLite 单底座 CRUD;一阶 Statement 抽取 prompt(XML strict) | 单元测试 + 50 条手工标注对话样本回归 |
| **P1 社会心智 Schema** | 4 周 | 多主体认知层上线 | Cognizer Hub(注册 + 别名归一 + 关系类型);holder 子图族;KnowledgeFrontier 计算;冲突检测 + CONFLICTS_WITH 边;perspective_take 算子 v1 | ToMBench 一阶 ToM + FANToM 信息不对称 |
| **P2 类脑动力学 v1** | 6 周 | CLS 双系统 + 巩固回路 | Hippocampus/Neocortex 物理分表;Replay Scheduler(周期采样 + 聚类 + 三动作);模式分离/补全(反相似偏移 + PPR 图游走);Reconsolidation 状态机(不覆盖) | LongMemEval 时间 + 更新两类显著提升;模式分离混淆率 < 15% |
| **P3 前瞻 + 情感** | 4 周 | 承诺记忆 + 情感调制 | Commitment 状态机 + 4 类 Trigger(time/event/state/compound);Prospective Loop 调度器;AffectVector 五维 + salience 公式;优先级重放权重 | 自建承诺履行集(100 条):detection > 80%,timeliness < 3 turns |
| **P4 检索规划器 + 二阶 ToM** | 4 周 | 智能检索 + 深度社会推理 | Retrieval Planner 完整 7 步 + 9 种 QueryIntent;perspective filter(iterative masking);Abstention 判定;Context Pack Builder 8 标签;二阶 ToM(nesting_depth=2)全链路 | ToMBench / FANToM / SoMi-ToM 全量;二阶 ToM 主动提示 precision > 70% |
| **P5 产品化 + 多底座** | 4 周 | 可对外交付 | Substrate Adapter 5 profiles(local-lite/graph/cloud-graphiti/letta-bridge/cognee-bridge);mem0 / Letta / cognee / Graphiti 迁移脚本;评测体系全量跑通;API 文档 + 接入指南 | 用户主观评测 A/B 对照;4 种迁移路径的集成测试 |
| **P6 持续演进** | 持续 | 多主体协作 + 形式化扩展 | 群聊 SharedGround 维护;Multi-agent 信任传播;PDDL 形式化 belief base(可选高阶);神经-符号混合实验 | 研究导向,无硬性交付节点 |

### 16.2 迁移路径

**从 mem0 迁入**:
- `filters={user_id, agent_id, run_id}` → Cognizer.id 三维隔离
- ADD/UPDATE/DELETE/NOOP → Statement.modality + supersedes 链
- 既有向量库保留为 Substrate.vector,新增 holder 字段索引

**从 Letta 迁入**:
- Block.label → Working Set label 集
- BlockHistory + version → Statement.supersedes 链
- sleeptime agent → Replay Scheduler Sleep 模式
- shared_blocks → CommonGround pool

**从 cognee 迁入**:
- DataPoint 子类机制 → Statement 子类化底座(直接继承)
- forget() 三级 + 权限 → Anima 降级而非删除
- improve() → Replay 的 reconcile/abstract/induce_norm 三动作
- TEMPORAL 边 → valid_from/valid_to 双时间区间

**从 Graphiti / Zep 迁入**:
- valid_from/valid_to 双时间区间直接复用
- 增加 holder 维度(Anima 把全局图族化)
- Episode 中心架构 → Anima EpisodicEvent 一一对应

### 16.3 共存策略

Anima 不要求替换现有系统。任何开源系统都可以作为 SubstrateAdapter 后端,Anima 在其上增加 `holder + Statement + ToM + Replay + Prospective` 这一层认知中间件:
- **已用 mem0**:保留 mem0,Anima 提供二阶 ToM + 承诺触发
- **已用 Letta**:保留 Letta,Anima 把 sleeptime + shared blocks 升级为 Replay + CommonGround
- **已用 Graphiti/Zep**:保留 Graphiti,Anima 加 holder 维度与共识池

---

## 17. 版本变更记录

### 17.1 v1 → v2 主要变更

| 变更 | v1 | v2 | 理由 |
|---|---|---|---|
| **公理** | 3 条(归属+双系统+目标重构) | 3 条,措辞强化 | 不变 |
| **Statement 状态机** | 隐含的生命周期 | **显式 5 态 ConsolidationState** | 可工程实现的状态迁移 |
| **Retrieval Planner** | 9 Intents + 6 步 | 9 Intents + **7 步**(新增 Abstention Gate) | 明确"该不该回答"应在"怎么回答"之前 |
| **Context Pack Builder** | 6 标签(FACT/BELIEF/HEARSAY/INFERRED/COMMON/TODO) | **8 标签**(+CONFLICT / ABSTAIN) | 冲突显式标注 + 拒答显式信号 |
| **Prospective Loop** | 3 种 Trigger(time/event/state) | **4 种 Trigger**(+compound) | 复合条件(AND/OR/NOT)是真实场景需求 |
| **Commitment 状态机** | PENDING→ACTIVE→FULFILLED/EXPIRED | + **RENEGOTIATED** 状态 | 承诺可被协商修改,不是二元完成/过期 |
| **AffectVector** | 5 维,无显式公式 | 5 维 + **salience 计算公式**(valence × novelty × stakes 的加权积) | 公式化才能工程实现优先级重放 |
| **Reconsolidation** | 提到概念 | **独立 §11 完整状态机 + 不覆盖只追加** | 这是 2025 研究确认的核心差异点 |
| **Norm 字段** | 仅 deontic_strength | + **enforcement_history**(规范被违反/重申的历史) | 支持规范演化追踪(独立于 Reconsolidation) |
| **评测** | 5+5+5 维,简表 | 8+9+4 维,含评测执行策略 | 覆盖再巩固保真度、视角泄露防护等 v2 新增能力 |
| **路线图** | 4 阶段(v0-v3) | **6 阶段(P0-P6)** | 增加 P5 产品化 + P6 持续演进,更接近真实交付节奏 |
| **与 Polis 关系** | §16 对比表 | §18 取舍 + §20 复用对照(更详细) | 吸收 Polis §10-§11 + Appendix B |
| **设计取舍表** | 无 | **9 项显式取舍 + 理由** | 来自 Polis §10,给审查者明确的 tradeoff 上下文 |
| **风险与开放问题** | 无独立章节 | **7 项风险 + 缓解策略** | 来自 Polis §11,诚实披露 |

### 17.2 v2 → v3 修复(本版本)

> 本节由资深架构师审查 v2 后产出。**设计本体未变**,纠正交叉引用、参数不一致、字段缺失等可施工性缺陷。

| # | 类别 | 修复内容 | 影响位置 |
|---|---|---|---|
| 1 | **交叉引用** | §15 评测表 9 处章节号错位全部修正(根因:v2 把 Reconsolidation 提为独立 §11 后,后续章节整体后移一位但评测表沿用旧编号) | §15.1 + §15.2 |
| 2 | 参数一致性 | 可塑窗口默认值统一:工程默认 30 分钟、自适应区间 5min–6h(6h 为 Nader 2000 神经科学参考值) | §11.1 + §11.2 + §19 |
| 3 | Schema 完备 | Statement 补 `replay_count / last_replayed` 字段(§10.2 采样器需要) | §3.2 |
| 4 | Changelog 准确 | 修正 v1→v2 changelog 中"Reconsolidation: enforcement_history"误归 —— enforcement_history 是 Norm 子类字段,与 Reconsolidation 无关;两项独立列出 | §17.1 |
| 5 | Persona 完备 | §7.4 补 self_model_anchor / profile_anchor 双锚点的工程意义(自陈优先于他陈;冲突升级 suspected_diverge) | §7.4 |
| 6 | 状态图例外 | §3.4 状态图补 CommonGround 与未结清 Commitment 不允许进入 ARCHIVED 的例外标注 | §3.4 |
| 7 | 措辞精度 | §6.2 "对数似然反向" → "negative log-likelihood, surprise = -log P(next \| context)" | §6.2 |
| 8 | 术语统一 | "Mentalizing Primitives" 统一表述(取代 API/原语混用) | §0 + §9.4 + §15.2 |
| 9 | 去重 | §13.7 改为引用 §13.3 step 7,abstain 完整���义集中在 §13.7 | §13.3 + §13.7 |
| 10 | 边界明确 | §10.3 reconcile 行明确写"推入 Reconsolidation Engine(§11)开启可塑窗口" | §10.3 |
| 11 | 案例补全 | 新增 §14.4 Prospective Loop 触发端到端流程示例 | §14.4 |
| 12 | 自夸去重 | 删除 §11.4 末尾"8 个开源系统全无"等正文重复表态(集中到附录 A 对照表) | §11.4 |

---

## 18. 关键设计选择与取舍

每一个设计都对应一个权衡。

| 选择 | 替代方案 | 理由 |
|---|---|---|
| **以 Statement 为核心原子,强制 holder 归属** | 以 Memory/Fact 为原子(类 mem0) | Statement 自带 holder/perspective,从 schema 层解决多主体隔离;长期收益远大于初始复杂度 |
| **嵌套 Statement 表达二阶 ToM(nesting_depth)** | 单独的 ToM 推理模块,在 Prompt 层模拟 | ToM 是数据结构问题而非模型问题;放进 schema 才能稳定查询、可审计、不依赖 LLM 随机推理 |
| **五类记忆作为逻辑视图而非物理分表** | 五张独立物理表 | 同一事件在生命周期中可能跨越多类(episode→semantic→commitment→fulfilled);视图灵活性更高,且 CLS 巩固本身就是跨表流动 |
| **默认保留差异(模式分离),不主动合并** | 默认合并去重 | 多视角必须共存;差异往往是认知线索而非噪声;合并会不可逆地丢失"谁在什么时候认为什么" |
| **后台 Replay Engine 异步巩固** | 同步抽取即巩固 | 同步拖慢写入且失去"重组"机会;睡眠期的离线重放是 CLS 的神经科学基础 |
| **Reconsolidation 不覆盖,只追加新版本** | 直接 UPDATE 旧记录 | 旧信念是认知历史;"曾经怎么想"对审计、追溯、理解信念演化至关重要 |
| **Substrate Adapter 多底座,不自己造存储** | 自建全套存储引擎 | 成熟开源系统(vector/graph/KV)的工程沉淀不应浪费;Anima 的价值在认知层 |
| **承诺与规范作为一等 Statement 子类** | 放进 metadata 或单独 KV 表 | §5.3 矩阵显示这是全行业空白;做成一等公民才能驱动运行时行为(触发、提醒、履行追踪) |
| **自然语言 belief 列表注入 LLM Context Pack** | 形式化 belief base(如 PDDL-Mind) | LLM 对自然语言的理解远好于形式逻辑;形式化作为 P6 高阶可选,不阻塞 MVP |

---

## 19. 风险与开放问题

1. **LLM 抽取成本与延迟**:Statement 抽取 + holder 归因 + Conflict 检测是高频操作。缓解:7B 级专用抽取模型 + 高价值场景升级大模型;批量抽取合并;抽取缓存(同一 Drawer 内容不重复抽取)。

2. **Replay Engine 的调度参数**:何时运行、运行多久、采样多少 —— 直接影响成本与新鲜度。缓解:P2 阶段做参数 sweep,上线后 A/B 调参;提供 conservative / balanced / aggressive 三档预设。

3. **冲突保留 vs 终端用户体验**:保留多视角是设计美德,但若 Context Pack 直接呈现"3 个互相冲突的 belief",LLM 可能困惑而非受益。缓解:Context Pack Builder 的 CONFLICT 标签 + 置信度排序 + 默认只注入最高置信度视角,冲突信息按需展开。

4. **隐私与 ToM 的张力**:系统持有"A 以为 B 不知道 X"的元数据,必须在错误视角下绝对不泄露。缓解:perspective filter 在检索管道早期执行(先于语义排序),不可跳过;敏感 Statement 支持 access_policy 字段。

5. **抽取错误传播**:错误的 holder 归因会产生连锁的错误信念。缓解:Statement 的 confidence + review_status 字段;提供 audit 工具帮助核查关键 statement;REVIEW_REQUESTED 状态标记低置信度抽取结果。

6. **规模化下的图查询性能**:嵌套 Statement + 关系边 + 模式补全会形成深图遍历。缓解:预聚合常用子图(per cognizer + per relation type);PPR 计算缓存;借 cognee 的图层分片经验;P5 做性能压测。

7. **再巩固窗口的边界控制**:Reconsolidation 允许修改已巩固记忆,但窗口太宽会导致记忆不稳定,太窄则失去修正机会。缓解:**§11.1 已统一为工程默认 30 分钟、自适应区间 5min–6h(其中 6h 为 Nader 2000 神经科学参考值)**;production 中按 modality 与更新频率(高频更新→缩短窗口防止抖动;低频更新→延长窗口提高仲裁质量)自动调整。

---

## 20. 复用资产对照(谁干什么,Anima 加了什么)

| 来源 | 被 Anima 复用的能力 | Anima 在其上加了什么 |
|---|---|---|
| **mem0** | ADD/UPDATE/DELETE/NOOP 抽取契约;`filters={user_id, agent_id, run_id}` 隔离 | 抽取输出从 fact 升级为 Statement(带 holder);隔离升级为 Cognizer Hub 主体管理;新增 supersedes 链 |
| **Letta** | Blocks(工作记忆);Sleeptime 后台任务;Git history 版本 | 工作记忆改 perspective 化(holder 标签);sleeptime 升级为 Replay Engine(reconcile/abstract/induce_norm);shared_blocks → CommonGround pool |
| **cognee** | DataPoint 子类机制;TEMPORAL 时间边;improve()/forget() | 子类化建立社会心智本体(Statement→Belief/Commitment/Norm...);improve 改为 Reconsolidation 状态机;forget 改为降级不删除 |
| **MemOS** | MemCube(activation memory);Memory-Brain 概念 | activation 作为 Hippocampus 短期载体;引入 Neurogenesis 模块(模式分离+补全) |
| **EverOS** | 多层抽取本体(MemCell→Episode→Profile→Foresight) | Foresight 升级为 Commitment 状态机 + Trigger 类型系统 + Prospective Loop |
| **mempalace** | Drawer(100% verbatim 原档);AAAK 有损摘要(含 emotions/weight/flags);KG triples with valid_from/to | Drawer 不变;triples 升级为带 holder 的 Statement;emotions 升级为 AffectVector 五维;KG 增加 perspective 维度 |
| **memU** | Category summary 增量维护;PROMPT_BLOCK 模块化 | 增量摘要改为 Replay Engine 的聚类抽象输出;XML 输出契约复用 |
| **claude-mem** | 5 阶段 Hook 生命周期;SQL 主 + 向量副降级;严格 XML 输出契约 | Hook 接 Anima 的写入端(抽取→冲突检测→Replay 调度);Observation 升级为 Statement;摘要压缩衔接 ConsolidationState 流转 |

> Anima 要造的不是第 9 个开源记忆库,而是它们之上的认知层。

---

## 21. 致谢与素材出处

本设计在以下素材之上独立成型:

- 8 个开源项目的源码深读(`_research/01_core_repos_deepdive.md` / `02_aux_repos_deepdive.md`)
- Anthropic Claude Memory / OpenAI ChatGPT Memory 公开博客与社区讨论
- HippoRAG 2 / EM-LLM / Larimar / A-Mem / RMM / ReMemR / Graphiti / EnigmaToM / SoMi-ToM / PDDL-Mind / MMToM-QA / MOMENTS 等学术工作
- "Memory in the Age of AI Agents"(2025-12, 102 页综述)
- 神经科学与认知心理学经典:McClelland 1995(CLS) / Tulving 1985(Episodic/Semantic) / Yassa & Stark 2011(Pattern Separation) / Conway & Pleydell-Pearce 2000(SMS) / Clark 1996(Common Ground) / Fiske 1992(Relational Models) / Anderson & Hulbert 2021(Adaptive Forgetting) / Nader 2000(Reconsolidation)
- Wilf 2023 SimToM / Kim 2023 FANToM / Cross 2024 Hypothetical Minds

如本文档进入实施阶段,需在第一里程碑前补充:
- 完整 schema 的 Pydantic 实现与 JSON-Schema 导出
- Validator 的 LLM 抽取 prompt(XML strict)
- Replay Scheduler 的具体采样器算法与默认权重
- Retrieval Planner 的 9 个 Intent 路径的可执行实现
- 与 mem0 / Letta / cognee / Graphiti 的 4 套 adapter 接入示例

---

## 附录 A:与 8 个开源项目的能力差异对照表

| 能力 | mem0 | Letta | cognee | MemOS | EverOS | memU | mempalace | claude-mem | **Anima** |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| holder 归属 | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | 🟡 | ❌ | ✅ |
| 二阶 ToM(nesting_depth=2) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| KnowledgeFrontier | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| CommonGround pool | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Affect 五维 + salience 公式 | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ | 🟡 | ❌ | ✅ |
| 真前瞻(Trigger + 状态机) | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ | ✅ |
| 优先级重放(情感/新颖/奖励) | ❌ | 🟡 | 🟡 | 🟡 | ❌ | ❌ | ❌ | 🟡 | ✅ |
| 模式分离(反相似偏移) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| 模式补全(PPR 图游走) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Verbatim Drawer(原档不可变) | ❌ | 🟡 | ❌ | ❌ | 🟡 | ❌ | ✅ | ✅ | ✅ |
| 双时间(valid_from/valid_to) | ❌ | ❌ | ✅ | ❌ | 🟡 | ❌ | ✅ | ❌ | ✅ |
| supersedes 链(不覆盖) | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Reconsolidation 状态机 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Abstention 判定 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Retrieval Planner(7 步 + 9 Intent) | ❌ | ❌ | 🟡 | 🟡 | 🟡 | ❌ | ❌ | ❌ | ✅ |
| Persona-Belief 分通道 | ❌ | 🟡 | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ | ✅ |
| Fiske 关系类型 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Commitment 状态机 + RENEGOTIATED | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **认知层成熟度合计** | 0 | 4🟡 | 3🟡✅ | 2🟡 | 5🟡 | 0 | 3🟡✅ | 2🟡✅ | **18✅** |

---

## 附录 B:为什么这套设计能让 LLM"更懂人"

**人类记忆三个不易察觉的特点**:

1. **记忆是"我"的,而不是"事实"的**。我们不记得"咖啡 30 元",我们记得"昨天我和 Alice 在那家店,她请我喝的咖啡 30 元"。Anima 把"我的"做成 holder 字段 —— 所有记忆从写入那一刻就带着归属,不会退化为无主事实。

2. **记忆为当前目标重构,不是回放**。Conway SMS 模型的核心发现:自传体记忆是建构性的,每次检索都是一次重构。Anima 的 Retrieval Planner 用 perspective + goal 重构而非 fan-out,Context Pack Builder 的 8 种语用标签让 LLM 不只是"看到事实"而是"理解这段记忆对我意味着什么"。

3. **我对你的画像 ≠ 你对自己的认知**。社会智能的核心。Anima 的 holder 子图族 + perspective_take 算子让"我以为你的样子"和"你自己"物理分离,不会互相污染。

**LLM 当前的"懂人"瓶颈与 Anima 的对策**:

| 瓶颈 | 现象 | Anima 对策 |
|---|---|---|
| 不分主体的 fact 全局化 | 矛盾时被迫挑边或编造 | holder 强制归属 + CONFLICTS_WITH 边保留多版本 |
| 不分通道的 persona/belief 混存 | 一次会话颠覆长期画像 | Persona 与 Belief 分通道 + 更新需多证据 |
| 不区分共识与单边断言 | 反复复述已 grounded 内容,显得"机械" | CommonGround pool + grounding status 检查 |
| 不追踪信息可见性 | 泄露未在场者不该知道的信息 | KnowledgeFrontier + perspective filter(iterative masking) |
| 不处理二阶视角 | 不会礼貌提示,也不会合适隐瞒 | nesting_depth + META_BELIEF QueryIntent |
| 不会主动惦记承诺 | agent 说过就忘,用户不信任 | Prospective Loop + Trigger 类型系统 + 主动提醒 |
| 说错无法追溯 | 信任崩塌但找不到根因 | supersedes 链保留完整历史 + Drawer 证据指针 |

Anima 的 schema + 运行时,**每一项都对准上述瓶颈**。这不是 prompt 工程的精进,而是数据模型层对人类社会认知结构的对齐 —— 在 LLM 看到任何文本之前,检索系统就已经按"谁、知道什么、不知道什么、和谁共识了、承诺了什么、情绪有多强"组织好了信息。

— 完 —
