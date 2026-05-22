# Anima Memory:多主体社会心智 + 类脑动力学的智能体记忆系统设计方案

> 项目代号 **Anima** —— 取自拉丁语「灵魂 / 心」,强调记忆不仅是信息存储,而是承载主体性、关系性与时间性的"心智实体"。
>
> 文档定位:从零起草的独立设计方案。读者:(1) 准备实现该系统的工程团队;(2) 关注"多主体社会心智 + 类脑记忆"双命题的研究伙伴。
>
> 输入素材:
> - `_research/01_core_repos_deepdive.md` —— EverOS / Letta / cognee / MemOS 源码深读
> - `_research/02_aux_repos_deepdive.md` —— memU / mem0 / mempalace / claude-mem 源码深读
> - `_research/03_frontier_2025_supplement.md` —— 2025 学术 + 工业落地补充
> - 同目录 `_synthesis/` 三份文档作为对照(本方案不复用其结构)

---

## 0. 摘要(One Page)

**Anima 解决一个问题**:让 LLM Agent 像人一样,**对每个交互对象都形成一份"持续演化的他者画像 + 我对他的信念 + 我以为他相信什么"**,并且这套画像在系统层面具备类脑的"快写慢洗、优先重放、自适应遗忘、显著性调制、前瞻触发"动力学,而不是停在"user_id 隔离 + 向量库 RAG"这种工程层抽象上。

**与现有 8 个开源项目相比的差异点**(基于 `01/02_repos_deepdive`):
1. **Cognizer 一等公民**:每个交互对象不是 user_id 字段,而是带"知识边界 / 关系标签 / 性格特质 / 当前情绪"的认知主体。**8 个项目无一具备**。
2. **Statement 替代 Fact**:所有写入都是"谁,在何时,基于何证据,对谁,以何样态,持有何判断"。原生承载冲突、归属、撤回。**只有 mempalace 在 KG 层接近,但无 holder 维度**。
3. **二阶 ToM 数据模型**:`Belief(holder=A, content=Belief(holder=B, content=...))` 可递归。**全行业空白**。
4. **Affect-Salience 调制**:每条记忆带 `valence / arousal / novelty / stake` 四维显著性,作为巩固优先级与检索权重的乘子。**仅 mempalace AAAK 有字段无运行时**。
5. **真前瞻记忆**:`Commitment(trigger=条件, action=动作, principal=承诺人, beneficiary=受益人, deadline=...)` 作为带触发器的运行时实体。**只有 EverOS Foresight 字段存在但无触发器,RMM 是"未来友好摘要"不是 if-then**。
6. **快慢双系统 + 优先级重放**:Hippocampus(快、稀疏、原档) ↔ Neocortex(慢、密集、抽象),由 ReplayScheduler 按 `salience × novelty × stakes × recency` 采样巩固。**Letta sleeptime 是计数触发,无优先级**。
7. **Perspective-Filter 检索**:检索时按"目标 Cognizer 的知识边界"动态遮蔽,产出该主体视角下的记忆切片(借鉴 EnigmaToM iterative masking)。**全行业空白**。

**关键非目标**:
- 不重写向量库、不重做 RAG;底层存储抽象为 SubstrateAdapter,可挂在 mem0 / Letta / cognee / Graphiti 之上。
- 不做训练;Anima 是数据模型 + 运行时调度 + 检索规划器,LLM 是组件而非主体。
- 不追求 100% 形式化(那是 PDDL-Mind 路线);采用"轻量结构 + LLM 抽取"的神经-符号混合,与 EnigmaToM 同档。

---

## 1. 三条公理

整套设计建立在三条公理上,后续所有 schema 与机制都从这里推导。

### 公理 I:**没有孤立的事实,只有归属于主体的陈述**

> "Bob 喜欢 PostgreSQL"在 Anima 中**不存在**。它必然是 `Statement(holder, subject, predicate, object, modality, time, evidence, confidence)`。

这一公理同时解决三件事:
- **归属**:每条信息可追溯到"谁说的、谁观察到的"。
- **冲突**:同一 (subject, predicate) 在不同 holder 下可有不同 value,系统不再被迫挑选"全局真理"。
- **撤回与版本**:holder 改变信念,只需追加一条新 Statement 并标 supersedes,而非修改既有事实。

**对照**:Graphiti / cognee / mem0 全部把 LLM 抽出的命题写为全局事实。Anima 是把"who-said-what"的归属嵌进 schema 而非 metadata。

### 公理 II:**记忆系统由两套时间尺度的子系统协同 —— 海马式快、新皮层式慢**

任何写入都先进入 Hippocampus 快速缓冲(原档 + 稀疏索引 + 显著性标签),经优先级重放、模式分离、再巩固后,才有机会被提升为 Neocortex 的稳定语义/规范/技能/画像。

这一公理是 CLS(McClelland 1995)的工程化:
- 抗灾难性遗忘:慢系统更新慢,快系统快进快出。
- 抗 LLM 抽取错误:Hippocampus 永远保留原档(借鉴 mempalace Drawer);抽取错了可以重放重做。
- 抗"既成事实污染":未通过巩固阈值的陈述不进入语义层。

### 公理 III:**记忆的目的是为当前目标服务的重构,而非录像回放**

(借鉴 Conway SMS 模型)Anima 的检索不返回"最相似的 N 条原文",而返回"为当前目标 + 当前 perspective 重构出的视角化切片"。这要求:
- 检索是 query planner 而非 fan-out 工具堆;
- 检索默认 perspective-filter:同一查询从 Alice 视角与从 Bob 视角应得到不同结果;
- 检索带 abstention:当证据不足时输出"不知道",而非编造。

---

## 2. 系统总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                       Anima Memory Runtime                           │
│                                                                      │
│  ┌────────────────┐                          ┌──────────────────┐   │
│  │  Cognizer Hub  │ ◄──── 视角/信念 ─────►   │   ToM Engine     │   │
│  │ (主体注册/画像)│                          │ (多阶信念追踪)   │   │
│  └────────┬───────┘                          └─────────┬────────┘   │
│           │                                            │            │
│           ▼                                            ▼            │
│  ┌────────────────────── Statement Bus ──────────────────────────┐ │
│  │  (所有读写的统一总线;载体=带 holder 的 Statement)              │ │
│  └──────────────────────────────────────────────────────────────┘ │
│       ▲                          │                                  │
│       │ 写入                     ▼ 检索/注入                        │
│  ┌────┴──────────┐         ┌─────────────────────────┐              │
│  │ Hippocampus   │ ─重放─► │      Neocortex          │              │
│  │ ─────────     │         │ ──────────────────      │              │
│  │ • Drawer      │ ◄─补全─ │ • Semantic (KG)         │              │
│  │   (verbatim)  │         │ • Procedural (Skills)   │              │
│  │ • Episodes    │         │ • Norms (规范库)        │              │
│  │ • Working Mem │         │ • Personae (画像)       │              │
│  │ • Affect Tag  │         │ • CommonGround (共识池) │              │
│  └────┬──────────┘         └────────────┬────────────┘              │
│       │                                  │                          │
│       ▼                                  ▼                          │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │  Replay Scheduler  +  Prospective Loop                  │       │
│  │  (优先级重放 + 承诺触发 + 反思 + 自适应遗忘)             │       │
│  └─────────────────────────────────────────────────────────┘       │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │  Perspective-aware Retrieval Planner                    │       │
│  │  (按 (querier, target, goal) 规划检索路径)              │       │
│  └─────────────────────────────────────────────────────────┘       │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │  Substrate Adapter:Vector / Graph / KV / Doc / Git      │       │
│  │  (可挂 mem0 / Letta / cognee / Graphiti / Chroma 任一)  │       │
│  └─────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

**九个层级**(下文 §3-§11 逐节展开):
1. Substrate Adapter — 底层存储抽象
2. Statement Bus — 全局陈述总线
3. Hippocampus — 快记忆(原档 + 情节 + 工作 + 情感缓冲)
4. Neocortex — 慢记忆(语义/程序/规范/画像/共识)
5. Cognizer Hub — 主体画像与边界
6. ToM Engine — 多阶信念追踪
7. Replay Scheduler — 优先级重放与巩固
8. Prospective Loop — 承诺与触发器
9. Retrieval Planner — 视角感知检索

---

## 3. 数据模型(本体层)

> 设计原则:**所有可写入的内容都是 Statement 的子类**(灵感:cognee DataPoint Annotated 子类化机制)。

### 3.1 基础类型

```python
# 借鉴 cognee DataPoint 的 Annotated 扩展机制
from typing import Annotated, Literal, Optional
from datetime import datetime

class Cognizer(BaseEntity):
    """认知主体 —— 一切陈述的归属者与对象"""
    id: UUID  # UUID5 from (kind, external_id)
    kind: Literal["self", "human", "agent", "group", "role"]
    external_id: str          # 跨系统稳定 id
    display_name: str
    persona: Annotated[Persona, _Embeddable]   # 长期画像(慢通道)
    knowledge_frontier: KnowledgeFrontier      # 知识边界(谁知道什么)
    relations: list[RelationEdge]              # 与其他 Cognizer 的关系
    created_at: datetime
    last_seen_at: datetime

class Statement(BaseEntity):
    """所有记忆的最小单元 —— 不存在脱离 holder 的事实"""
    id: UUID
    holder: CognizerRef                  # 谁持有这条陈述
    subject: CognizerRef | EntityRef     # 关于谁/什么
    predicate: str                       # 谓词(开放词表 + 受控核心集)
    object: Value | StatementRef         # 值,或递归引用另一条 Statement(二阶)
    modality: Modality                   # 见 §3.2
    confidence: float                    # 0-1
    affect: AffectTag                    # 见 §3.3
    evidence: list[EvidenceRef]          # 指向 Drawer 原档片段
    perceived_by: list[CognizerRef]      # 谁感知到了(信息可见性)
    happened_at: Optional[datetime]      # 事件发生时间
    observed_at: datetime                # 观察/写入时间
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]         # 借鉴 mempalace KG
    supersedes: Optional[StatementRef]   # 版本链
    derived_from: list[StatementRef]     # 由哪些陈述推导
    tier: Literal["hippocampus", "neocortex"]  # 当前所在子系统
    salience_score: float                # 重放优先级(由 affect + novelty + stakes 计算)
```

**关键差异**(对照 8 个开源系统):
- `holder` 字段是新增的强制维度,**这是公理 I 的硬体现**。
- `object: Value | StatementRef` 让二阶/N 阶 ToM 在 schema 层就具备表达力(Belief about Belief)。
- `perceived_by` 是借鉴 MOMENTS/FANToM 的"信息可见性"维度 —— 8 个开源系统全部缺失。
- `tier` 显式标记快慢通道,而非靠"两个表"隐式分离。

### 3.2 Modality(样态)

借鉴 epistemic logic + BDI(Belief-Desire-Intention),不追求形式化完备但覆盖 90% 自然语言场景:

```
BELIEVES       — A 相信 X(可错)
KNOWS          — A 知道 X(蕴含真,慎用,默认转 BELIEVES)
ASSUMES        — A 假设 X(置信度低)
DESIRES        — A 想要 X
INTENDS        — A 计划做 X
COMMITS        — A 承诺做 X(进入 Prospective Loop)
PREFERS        — A 偏好 X 胜过 Y
NORM_OUGHT     — 在某情境 X 应当成立(规范)
NORM_FORBID    — 在某情境 X 不得成立
DOUBTS         — A 怀疑 X
RECANTED       — A 撤回 X(用于版本链)
```

**对照**:mem0 只有 ADD/UPDATE/DELETE/NOOP 4 个动作,无 modality;EverOS Foresight 暗含 INTENDS 但混在事件预测里;**没有任何开源系统把 BDI + 规范 + 承诺**作为一等枚举。

### 3.3 Affect 与 Salience

```python
class AffectTag:
    valence: float    # -1..+1   情感效价(正/负)
    arousal: float    #  0..1    唤起度(强/弱)
    novelty: float    #  0..1    新颖度(与已有记忆距离)
    stakes: float     #  0..1    利害(对 holder 目标的影响)
    surprise: float   #  0..1    惊奇度(EM-LLM 风格,贝叶斯)

# 显著性 = 情感乘子 × 新颖 × 利害 × 惊奇
salience = (0.5 + 0.5*|valence|) * (0.5 + arousal) * (0.3 + novelty) * (0.3 + stakes) * (0.5 + surprise)
```

salience 既是 ReplayScheduler 的采样权重,也是 Retrieval 的重排乘子。这把"情感与重要性"做成**可计算字段而非自然语言注释**(对照 mempalace AAAK 有字段无算法)。

### 3.4 子类(Statement 的特化)

利用 Annotated 子类化(cognee 风格),声明式扩展本体而不重写基类:

```python
class EpisodicEvent(Statement):
    modality: Literal[BELIEVES] = BELIEVES   # 默认
    participants: list[CognizerRef]
    location: Optional[Place]
    raw_drawer_ref: DrawerRef                # 必须指向原档(强制 verbatim)
    boundary_score: float                    # EM-LLM 惊奇度切边界

class Commitment(Statement):
    modality: Literal[COMMITS] = COMMITS
    principal: CognizerRef       # 承诺人
    beneficiary: CognizerRef     # 受益人
    trigger: Trigger             # 触发条件(时间/事件/状态)
    deadline: Optional[datetime]
    status: Literal["pending", "fired", "fulfilled", "broken", "withdrawn"]

class Norm(Statement):
    modality: Literal[NORM_OUGHT, NORM_FORBID]
    scope: NormScope             # group / 1-1 / role
    deontic_strength: float      # 强建议 vs 硬禁

class Skill(Statement):
    modality: Literal[KNOWS] = KNOWS
    procedure: ProcedureSpec     # 步骤化
    success_pattern: list[CaseRef]   # 借鉴 EverOS AgentCase
    maturity: float

class Persona(BaseEntity):
    """Cognizer 的长期稳定画像 —— 慢通道,与 Belief 严格分开"""
    traits: dict[str, TraitValue]    # OCEAN / 自定义
    preferences: list[StatementRef]  # 指向 PREFERS 类陈述
    competencies: list[StatementRef] # 能力画像
    values: list[StatementRef]       # 价值观/底线
    relationship_styles: dict[CognizerRef, FiskeMode]  # Fiske 四元(Communal/Authority/Equality/Market)

class CommonGround(BaseEntity):
    """两个 Cognizer 之间的共识池 —— Clark 共同知识"""
    parties: tuple[CognizerRef, CognizerRef]
    grounded: list[StatementRef]     # 双方都知道双方都知道的
    asserted_unack: list[StatementRef]   # 一方说了对方未确认
    suspected_diverge: list[StatementRef] # 怀疑对方实际相信不同
```

**关键设计**:
- `Persona`(慢)与 Cognizer 当前 belief(快)严格分开,呼应神经科学 dmPFC/vmPFC 分工。
- `CommonGround` 是 8 个开源系统全部缺失的维度 —— 对话生成时"已 grounded 的不复述"的硬基础。
- `RelationEdge.style` 用 Fiske 四类标签,作为对话风格与记忆策略的乘子。

### 3.5 Drawer:不可被覆盖的原档(借鉴 mempalace)

任何 Statement 的 `evidence` 必须指向 Drawer 中的 verbatim 片段。Drawer 是物理上不可改写的(append-only),即使 LLM 抽取错误,原档永远在。

```python
class DrawerRecord:
    id: UUID
    source: SourceRef            # 对话/邮件/文档
    content: str                 # 100% verbatim
    chunk_index: int
    speaker: Optional[CognizerRef]
    timestamp: datetime
    immutable: True              # append-only
```

这是 Hippocampus 的"最底层证据带",对应大脑的"原始感觉痕迹"假设。

---

---

## 4. Substrate Adapter:不重造底座

Anima 是中间件而非新数据库。SubstrateAdapter 抽象出 5 类底层能力,可挂在任意现成系统:

| 能力 | 接口 | 推荐底座 |
|---|---|---|
| Vector | `embed / knn / hybrid_search` | Chroma / Qdrant / Milvus / Letta passages |
| Graph | `upsert_node / upsert_edge / cypher_query` | Neo4j / FalkorDB / Graphiti |
| KV / Doc | `put / get / cas / list_by_prefix` | SQLite / Postgres jsonb / Redis |
| Cache(KV-cache) | `store_kv / concat_kv / evict` | MemOS KVCache 风格 |
| BlobStore(Drawer) | append-only,不可覆盖 | S3 / 本地 fs / Letta archival |

实现层面提供 5 个**默认 profile**,开箱即用:
- `local-lite`: SQLite + Chroma + 本地 fs(单机开发)
- `local-graph`: SQLite + FalkorDB + Chroma(单机带图)
- `cloud-graphiti`: Postgres + Graphiti/Neo4j + Qdrant(生产首选)
- `letta-bridge`: 全部委派给 Letta(嵌入既有 Letta 部署)
- `cognee-bridge`: 委派 cognee 的存储层 + 复用其 DataPoint 子类机制

**对照**:`01_core_repos_deepdive` 显示,8 个项目都把存储抽象绑死。Anima 把"存储绑定"作为部署选项而非架构决策。

---

## 5. Statement Bus:全局陈述总线

所有写入/读出都经过 Bus,**不允许直接写存储**。这是公理 I 的硬约束。

```
write(stmt: Statement)        → Bus → Validator → Hippocampus → 异步 Replay
read(query: Query)            → Bus → RetrievalPlanner → 多源融合 → Result
emit(event: BusEvent)         → Bus → Subscribers(Replay/Prospective/ToM)
```

### 5.1 Validator(写入校验)

借鉴 mem0 `filters={}` 契约 + claude-mem 严格 XML 输出契约:

1. **Schema 校验**:`holder` 非空、`predicate` 在受控集合或显式扩展、`evidence` 至少 1 条 DrawerRef。
2. **抽取一致性**:LLM 抽取产出必须包裹在 `<statement>` XML;非合规直接拒收(避免 memU 式自由文本污染)。
3. **冲突探针**:写入前查询同 (holder, subject, predicate) 是否已有,触发 §7.3 冲突消解策略。
4. **隐私边界**:Cognizer 的 `knowledge_frontier` 限制其 holder 字段下能持有什么 —— 未到场就不能"知道"私密信息。

### 5.2 BusEvent 类型

| 事件 | 触发器 | 订阅者 |
|---|---|---|
| `statement.written` | 写入 Hippocampus 后 | Replay / ToM / Prospective |
| `statement.consolidated` | 通过 Replay 提升到 Neocortex | ToM(更新画像) |
| `statement.superseded` | 新版覆盖旧版 | ToM(更新 CommonGround) |
| `commitment.fire` | Trigger 命中 | Prospective(下发提醒) |
| `cognizer.observed` | 主体上线/发声 | ToM(更新可见性) |
| `belief.conflict` | 探针发现矛盾 | Replay(优先重放仲裁) |

**对照**:claude-mem 的 5 阶段 hook 是 session 级,Anima 是 statement 级 —— 粒度更细,可被多组件复用。

---

## 6. Hippocampus:快记忆子系统

> 设计原则:**写得快、原档不丢、稀疏索引、显著性优先**。

### 6.1 内部分层

```
┌─ Drawer ─────── verbatim 原档(append-only,immutable)
│
├─ Episodes ───── 按 EM-LLM 惊奇度切分的事件单元(指向 Drawer)
│
├─ Working Set ── 当前会话/任务的活跃槽位(Letta Block 风格,带 limit)
│
└─ Affect Buffer ─ 待巩固的高 salience 事件队列(优先级队列)
```

### 6.2 事件切分(借鉴 EM-LLM)

不按固定 token 窗口切对话,而是 LLM 在线计算每条话语的 `surprise`(下一句对上一段的预测对数似然反向),当跨过阈值时切出一个 EpisodicEvent。

切完做**模式分离**(借鉴 DG/CA3 的 pattern separation):
- 检查与最近 K 个 Episode 的字段相似度;
- 若高度相似但关键差异字段不同(时间戳/参与者/任务),**强制写入差异性 metadata** 避免后续混淆。

### 6.3 Working Set(显式工作记忆)

Letta Block 是工作记忆的成熟工程模式,Anima 直接采纳并扩展:

```python
class WorkingBlock:
    label: Literal["self_persona", "active_persona", "current_goal",
                   "interlocutor_persona", "common_ground", "norm_active"]
    value: str
    limit: int                     # token 上限
    version: int                   # 乐观锁(Letta 同款)
    refresh_strategy: Literal["never", "per_turn", "per_session", "on_event"]
```

新增 `interlocutor_persona`(当前对话对象画像)与 `common_ground`(已确认共识),**8 个开源系统中无一显式注入这两块**。

### 6.4 Affect Buffer

高 salience 事件进入优先级队列等待重放,FIFO 容量与 salience 双指标:
- 容量满:淘汰最低 salience(不是最旧 —— 借鉴 Anderson adaptive forgetting);
- 重放调度器(§9)定期采样并提升到 Neocortex。

---

## 7. Neocortex:慢记忆子系统

> 设计原则:**抽象、可查、可推理,但更新需要"通过 Replay 才能进入"**。

### 7.1 五个子区

| 子区 | 内容 | 主要承载 | 更新通道 |
|---|---|---|---|
| **Semantic** | 语义事实图 | Statement(BELIEVES/KNOWS) | Replay 巩固 |
| **Procedural** | 技能/流程 | Skill | Case 集群提升(EverOS 风格) |
| **Norms** | 规范库 | Norm | 反思周期推断 |
| **Personae** | 主体长期画像 | Persona | 慢更新(每 N 次会话) |
| **CommonGround** | 二元共识池 | CommonGround | grounding act 触发 |

### 7.2 语义图的"holder-aware"实现

Neocortex 的图层不是单一全局图,而是**按 holder 分层的图族**:

```
GraphFamily = {
    holder=self : { (subj, pred, obj, t, conf) ... },   # 我自己相信的
    holder=Alice: { ... },                              # 我以为 Alice 相信的
    holder=Bob  : { ... },
    common(self,Alice): { ... },                        # 我和 Alice 的共识
    ...
}
```

每个子图独立维护,共享 entity 池但不共享真值。这避免了 mem0/cognee 把 LLM 抽出的命题写为全局事实的污染问题。

### 7.3 冲突消解策略

写入探针发现 (holder, subject, predicate) 冲突时,**不静默覆盖**,而是按以下决策树:

1. **同 holder + 时间更晚 + 显式 RECANT**:supersedes 关系标记,旧版进入"历史信念链"。
2. **同 holder + 时间更晚 + 隐式改口**:置信度衰减旧版,新版 confidence 视证据强度,**两版共存**直到 Replay 仲裁。
3. **不同 holder**:**直接共存**,不作为冲突 —— 这正是多视角的本质。
4. **同 holder + 同时间窗 + 矛盾**:emit `belief.conflict`,Replay 调度器加重该陈述的重放优先级。

**对照**:8 个开源系统全部把冲突当 UPDATE 处理(mem0 最典型),丢失多视角与历史。

---

## 8. Cognizer Hub:主体注册与画像

### 8.1 Cognizer 生命周期

```
discover  → 在 Drawer 中识别新 Cognizer(NER + 对话角色)
seed      → 初始化空 Persona + 默认 KnowledgeFrontier
observe   → 每次出场触发 cognizer.observed,更新 last_seen_at
profile   → Replay 周期重写 Persona
archive   → 长期未活跃,降低检索权重(不删)
```

### 8.2 KnowledgeFrontier(知识边界)

每个 Cognizer 有一份"该主体能知道什么"的边界描述:

```python
class KnowledgeFrontier:
    accessible_sources: list[SourceRef]    # 该主体可访问的信息源
    membership: list[GroupRef]              # 所属群组
    presence_log: list[PresenceWindow]     # 何时何地在场
    explicit_told: list[StatementRef]      # 明确告知的内容
    explicit_not_told: list[StatementRef]  # 明确未告知(用于 surprise)
```

检索 Planner 用此对**该 holder 可能知道什么**做硬过滤(EnigmaToM iterative masking 风格)。

### 8.3 Relations(Fiske 四类)

```python
class RelationEdge:
    from_: CognizerRef
    to:    CognizerRef
    style: Literal["communal", "authority_up", "authority_down",
                   "equality", "market"]   # Fiske 1992
    closeness: float           # 0..1
    trust: float               # 0..1(可有向)
    history_depth: int         # 互动次数
    last_interaction: datetime
```

Style 影响:
- **Communal**:倾向长期主动记忆共享、低形式化提醒;
- **Authority**:区分上行/下行信息流(下属对上司主动汇报,反之精炼);
- **Market**:对等可审计、强 grounding;
- **Equality**:轮替式 grounding 与责任。

---

## 9. ToM Engine:多阶信念追踪

> ToM Engine 是 §3 schema 之上的"运行时算法集合"。

### 9.1 二阶信念的物理实现

二阶信念 `Alice 以为 Bob 知道 X` 在 schema 上是:

```
Statement(
    holder=self,
    subject=Alice,
    predicate=BELIEVES,
    object=Statement(
        holder=Alice,
        subject=Bob,
        predicate=KNOWS,
        object=X
    )
)
```

存储上展平为带 `nesting_depth` 字段的两条 Statement(嵌套深度索引)。检索时按需展开。**约束:默认追踪深度 ≤ 2,深度 3 仅在显式触发时构建**(避免组合爆炸,呼应 Kinderman 关于成人三阶 ToM 容量限制)。

### 9.2 信念抽取 pipeline

```
Drawer 原档
   ↓ ① LLM 提取候选 Statement(XML 严格输出)
Validator
   ↓ ② perceived_by 推断(谁在场、谁可见)
   ↓ ③ holder 归属判定(说话人 ≠ holder,如"Bob 说他喜欢...")
   ↓ ④ modality 标注(BELIEVES vs KNOWS vs ASSUMES)
   ↓ ⑤ 若涉及他人心理状态 → 嵌套 Statement(二阶)
Hippocampus
```

### 9.3 perspective_take 算子

借鉴 SimToM + EnigmaToM iterative masking,作为 Engine 的核心算子:

```python
def perspective_take(target: CognizerRef, query: str, time: datetime) -> Context:
    # 1. 用 KnowledgeFrontier 过滤:只保留 target 可见的 Drawer 片段
    visible = filter_by_frontier(drawer, target, time)
    # 2. 检索 holder=target 的 Statement 子图
    target_beliefs = neocortex.query(holder=target, time=time)
    # 3. 共识池
    cg = common_ground(self, target)
    # 4. 组装 perspective context
    return Context(visible, target_beliefs, cg)
```

任何对话生成、规划、协商都可以用 `perspective_take(other)` 先取得对方视角再决策,这是 8 个开源系统全部缺失的能力。

### 9.4 Grounding Acts(共识池更新)

借鉴 Clark 1996,显式建模 4 类:

| Act | 触发 | 效果 |
|---|---|---|
| Assert | 一方陈述 | 进 `asserted_unack` |
| Acknowledge | 对方确认 | 升级到 `grounded` |
| Repair | 对方质疑 | 退回 `suspected_diverge` |
| Withdraw | 一方撤回 | RECANTED + 从池中移除 |

输出策略层的"已 grounded 不复述,未 grounded 主动 grounding"由 Working Set 中的 `common_ground` block 驱动。

---

## 10. Replay Scheduler:优先级重放与巩固

> 这是 Anima 的"睡眠系统",对标 CLS + 海马重放。

### 10.1 三种重放模式

| 模式 | 触发 | 任务 |
|---|---|---|
| **Online**(在线) | 每 N 个 statement.written | 即时巩固高 salience 短链 |
| **Idle**(空闲) | Agent 空转 > T 秒 | 中等强度反思 |
| **Sleep**(深度) | 周期性(每会话结束 / 每日) | 完整 sweep + Persona 更新 |

### 10.2 优先级采样器

```
sample_weight(stmt) = stmt.salience_score
                    × novelty_decay(time_since_last_replay)
                    × (1 + conflict_bonus if has_conflict else 1)
                    × goal_relevance(stmt, current_goal)
```

借鉴 prioritized experience replay(Schaul et al. 2015 强化学习经验,LLM 端首次系统采纳)。

### 10.3 巩固动作(原子操作集)

| 动作 | 输入 | 输出 |
|---|---|---|
| `compress` | 多条相似 EpisodicEvent | 1 条更高层语义 Statement(Drawer 指针保留) |
| `abstract` | 多 holder 的同 predicate | 1 条 Persona trait 更新 |
| `reconcile` | 冲突 Statement 集 | supersedes 链 + 历史信念归档 |
| `induce_norm` | 多次 PREFERS/COMMITS | 1 条 Norm 候选,人工/规则确认入库 |
| `forge_skill` | 多次成功 Case 集群 | 1 条 Skill 候选(EverOS AgentSkill 风格) |
| `decay` | 低 salience 长未召回 | confidence 衰减,达阈值则归档 |

巩固结果带 `derived_from` 指回原 Statement,**不删除**原始证据(借鉴 mempalace verbatim 哲学)。

### 10.4 自适应遗忘公式

借鉴 MemoryBank(Ebbinghaus)+ Anderson active forgetting:

```
S(t) = exp(-Δt / S0(stmt))     # 召回强度
S0(stmt) = base
         × (1 + 0.5 × access_count)
         × (1 + salience_score)
         × (1 + 2 × is_grounded)     # 共识池中条目衰减更慢
         × decay_modifier_by_modality  # COMMITS 衰减极慢,ASSUMES 衰减快

forget if S(t) < 0.05 and 不在 CommonGround 且 confidence < 0.3
```

被 forget 的条目不删 Drawer,只**降级**(从 Neocortex 撤出,Hippocampus 标 archived)。

---

## 11. Prospective Loop:真前瞻

> 8 个开源系统全部缺失,这是 Anima 与 RMM 之外少数把"前瞻"做成 first-class 的设计。

### 11.1 Trigger 类型

```python
class Trigger:
    kind: Literal["time", "event", "state", "compound"]
    spec: TriggerSpec   # 见下

# 例子
TimeTrigger(at=datetime(...))
TimeTrigger(every="1d at 09:00")
EventTrigger(when="cognizer:Alice.observed")
EventTrigger(when="statement.written: predicate=mentions, object=X")
StateTrigger(predicate="goal:onboarding.completed")
CompoundTrigger(all_of=[..., ...])
CompoundTrigger(any_of=[..., ...])
```

### 11.2 Commitment 生命周期

```
created → pending → fired → fulfilled / broken / withdrawn
                       ↓
                  reminder 入对话
```

每条 Commitment 由后台 PolicyEngine 持续监听对应 Trigger,命中则 emit `commitment.fire`,Working Set 注入提醒,LLM 在下一轮系统提示中可见"待办"。

### 11.3 与 RMM(prospective reflection)互补

RMM 的 prospective reflection 是"为未来检索友好的摘要",Anima 的 Prospective Loop 是"if-then 触发器"。两者**不冲突**:RMM 用于"未来如果用户问起,我能找到";Anima Loop 用于"未来某时该主动做什么"。两类合并产出"既会被动检索友好、又会主动出发"的记忆体。

---

---

## 12. Retrieval Planner:视角感知检索

> 检索不是"工具堆",是"认知规划器"。这是 §1 公理 III 的运行时体现。

### 12.1 输入与输出

```python
class Query:
    querier: CognizerRef       # 谁在问(默认 self)
    perspective: CognizerRef   # 从谁的视角检索(默认 = querier)
    intent: QueryIntent        # 见下
    text: str
    time: datetime             # 检索时间锚(支持 "as_of")
    goal_context: Optional[GoalRef]

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

### 12.2 7 步规划

```
1. parse:  解析 Query → intent + 关键 entity
2. mask:   按 perspective 的 KnowledgeFrontier 遮蔽不可见证据
3. plan:   按 intent 选择路径(下表)
4. fetch:  并发执行多源(向量 / 图 / KG / Drawer / Working Set)
5. fuse:   按 holder 子图 + salience + recency 重排
6. ground: 检查 CommonGround,标记"已 grounded"以便复述抑制
7. abstain check:if 总分 < 阈值 → 输出"无可靠记忆"而非编造
```

### 12.3 Intent → Path 映射

| Intent | 主路径 | 辅助 |
|---|---|---|
| FACT_LOOKUP | Neocortex Semantic(holder=self) + Drawer 证据 | Working Set |
| BELIEF_OF_OTHER | Neocortex Semantic(holder=target) | Drawer 中 target 的发言 |
| META_BELIEF | 嵌套 Statement 索引(nesting_depth=2) | perspective_take 即时构建 |
| HISTORY | 时间索引 + supersedes 链 | Drawer time-window |
| COMMITMENT_DUE | Prospective Loop 队列 | — |
| PREFERENCE | Persona.preferences | PREFERS 类 Statement |
| NORM_LOOKUP | Norms 子区 + scope 过滤 | — |
| COMMON_GROUND | CommonGround pool(parties=...) | — |
| ABSTAIN_CHECK | 跨子区低召回判定 + 校准置信度 | — |

### 12.4 Abstention(主动拒答)

LongMemEval 显示这是 SOTA 系统最大的失分项。Anima 把 abstention 做成显式判定:

```
abstain if:
   max_score < tau_recall      # 召回分太低
   OR perspective frontier 不允许该信息
   OR 唯一证据来自已 RECANTED 链
   OR conflict 未仲裁(请求澄清而非赌一边)
```

abstain 时输出结构化"我不知道,因为 ___",而非编造或 "I'm not sure"。

---

## 13. 端到端数据流(典型场景)

### 13.1 写入路径(Alice 在群聊里说"Bob 不再负责 auth 模块,改由 Carol 接手")

```
Drawer.append(verbatim Alice 原话, perceived_by=[self, Alice, Bob, Carol, ...])
                                  ↑ 谁在群里 = 都被标 perceived_by
   ↓ EM-LLM 切边界 → EpisodicEvent
   ↓ LLM 抽取候选 Statement(XML 严格)
   ↓
[
  Statement(holder=self, subject=Bob,   pred=responsible_for, obj=auth, mod=BELIEVES, valid_to=NOW),
  Statement(holder=self, subject=Carol, pred=responsible_for, obj=auth, mod=BELIEVES, valid_from=NOW),
  Statement(holder=self, subject=Alice, pred=BELIEVES, obj=⟨Carol now responsible⟩),  # 二阶
  Statement(holder=Alice,subject=Bob,   pred=responsible_for, obj=auth, mod=BELIEVES, valid_to=NOW),  # Alice 的视图
]
   ↓ Validator(冲突探针):发现旧 Statement(Bob responsible),触发 reconcile,supersedes 链
   ↓ Hippocampus.write
   ↓ emit statement.written ×4
   ↓ Replay 评估 salience → high(stakes 高)→ Affect Buffer 优先队列
   ↓ ToM Engine 更新 CommonGround(self, Alice/Bob/Carol):本陈述已 grounded
   ↓ 若 Bob 不在场 → 不进 (self,Bob) common ground,只进 (self,Alice/Carol)
```

### 13.2 检索路径(用户问"Bob 现在还负责 auth 吗?")

```
Query(intent=FACT_LOOKUP, text=...) → Planner
   ↓ mask: querier=user 视角(自身,无遮蔽)
   ↓ plan: FACT_LOOKUP path
   ↓ fetch:
       Neocortex(holder=self).query(subj=Bob, pred=responsible_for): 命中 supersedes 链
       Drawer time-window: 关联 Alice 群聊原话 + 历史 Bob 拥有 auth 的对话
   ↓ fuse:
       valid_to 近且有 supersedes → 输出"已变更,现 Carol 负责"
       同时携带历史链:"Bob 此前负责,2026-04-15 Alice 通知变更"
       证据指针:Drawer:abc123
   ↓ ground: CommonGround(self,user) 检查 → 用户尚未确认 → 主动 grounding
   ↓ output:
     "不是。Alice 在 4/15 群聊宣布 auth 由 Carol 接手 [evidence]。
      Bob 之前负责该模块,如有需要我可以拉出当时的设计讨论。"
```

### 13.3 二阶 ToM 路径(用户问"Bob 知道这事吗?")

```
Query(intent=META_BELIEF, target=Bob, about=⟨Carol now responsible⟩)
   ↓ Planner.plan:
       1. 检查 perceived_by: Bob 是否在场?
       2. 检查 explicit_told: 是否事后被 @ 或私聊告知?
       3. 检索 holder=Bob 的近期发言:有无相关动作 / 提问?
   ↓ 综合:
       perceived_by 含 Bob → Bob 应已知道
       OR perceived_by 不含 Bob 且无 explicit_told → Bob 可能不知,需提示
   ↓ output:"Bob 当时在群里(perceived_by 命中),应该已知。
              不过他之后没有相关回应,如果重要可以确认一下。"
```

---

## 14. 评测指标与对标

### 14.1 五维度记忆能力(沿用 LongMemEval 拆分)

| 维度 | Anima 设计应得分点 | 对应机制 |
|---|---|---|
| 单/多会话事实抽取 | Statement 抽取 + holder 归属 | §9.2 |
| 多会话整合 | Replay 巩固 + holder 子图 | §10 |
| 时序推理 | valid_from/to + supersedes + time-aware planner | §3 + §12 |
| 知识更新 | 冲突消解 + supersedes 链 | §7.3 |
| Abstention | 显式 abstain 判定 | §12.4 |

### 14.2 ToM 能力(对标 ToMBench / FANToM / SoMi-ToM / EnigmaToM)

| 能力 | Anima 设计 |
|---|---|
| 一阶 false belief | holder=other 子图 + KnowledgeFrontier mask |
| 二阶 false belief | 嵌套 Statement(nesting_depth=2) |
| 信息不对称(FANToM) | perceived_by + presence_log |
| Perspective-taking | perspective_take 算子(§9.3) |
| 多视角(SoMi) | holder-aware 检索默认行为 |

### 14.3 新评测维度(Anima 提出的延伸)

| 维度 | 测试方法 | 暂未有公开 benchmark |
|---|---|---|
| **承诺履行率** | 注入 Commitment,N 步后检查是否触发 | ✓ 自建 |
| **冲突保持率** | 注入冲突陈述,检查 supersedes 链是否完整 | ✓ |
| **共识区分** | 同一事实在不同 (self, other) 共识池中区分 | ✓ |
| **二阶 ToM 召回** | "Bob 以为 Alice 知道 X" 类问题 | ✓ |
| **Persona 漂移监控** | Persona 变更不应被一次会话颠覆 | ✓ |

---

## 15. 路线图与迁移

### 15.1 4 阶段交付

| 阶段 | 时间 | 内容 | 验证 |
|---|---|---|---|
| **v0 Spike** | 2 周 | 数据模型 + Statement Bus + SQLite 单底座 + 一阶 Statement 抽取 | 单元测试 + 50 条对话样本 |
| **v1 MVP** | 6 周 | Hippocampus + Neocortex 分层 + Replay 基础 + Cognizer Hub + 一阶 ToM | LongMemEval 子集 |
| **v2 ToM** | 6 周 | 二阶 ToM + perspective_take + CommonGround + Abstention | ToMBench / FANToM / SoMi-ToM |
| **v3 完整** | 8 周 | Affect 调制 + Prospective Loop + 优先级重放 + Substrate Adapter 5 profiles | LoCoMo / 自建承诺履行 |

### 15.2 与现有系统的迁移路径

**从 mem0 迁入**:
- mem0 的 `filters={user_id, agent_id, run_id}` 直接映射 Cognizer.id;
- ADD/UPDATE/DELETE/NOOP → Statement.modality + supersedes 链;
- 既有向量库继续作为 Substrate.vector,只需新增 holder 字段索引。

**从 Letta 迁入**:
- Block.label 直接映射 Working Set 的 label 集;
- BlockHistory + version 直接复用为 Statement.supersedes 链;
- sleeptime agent 接管 Replay Scheduler 的 Sleep 模式;
- shared_blocks → CommonGround pool。

**从 cognee 迁入**:
- DataPoint 子类机制是 Anima Statement 子类化的天然底座,直接继承;
- forget() 三级 + 权限 → Anima 降级而非删除;
- improve() 实装为 Replay 的 reconcile/abstract/induce_norm 三个动作。

**从 Graphiti / Zep 迁入**:
- valid_from / valid_to 双时间区间直接复用;
- 增加 holder 维度(Anima 把全局图族化);
- Episode 中心架构与 Anima EpisodicEvent 一一对应。

### 15.3 与 8 个开源项目共存策略

Anima 不要求替换。**任何一个开源系统都可以作为 SubstrateAdapter 后端**,Anima 只在它们之上加 `holder + Statement + ToM + Replay + Prospective` 这一层认知中间件。这意味着团队可以:
- 已用 mem0:保留 mem0,Anima 在 mem0 之上提供"二阶 ToM + 承诺触发"。
- 已用 Letta:保留 Letta,Anima 把 Letta 的 sleeptime + shared blocks 升级为 Replay + CommonGround。
- 已用 Graphiti/Zep:保留 Graphiti,Anima 给 Graphiti 加 holder 维度与共识池。

---

## 16. 与已有 Polis 提案(`_synthesis/03_design_proposal.md`)的关系

> 用户要求"重新独立设计",故本文件未复用 Polis 结构。这里给出**独立设计完成后**的差异说明,供阅读对照。

| 维度 | Polis(03_design_proposal) | Anima(本文) |
|---|---|---|
| 公理数 | 2(Statement 归属 + CLS 双系统) | 3(增"为目标重构非回放") |
| 核心数据类型 | Statement + Cognizer | Statement + Cognizer + **CommonGround + KnowledgeFrontier + Affect 计算字段** |
| 二阶 ToM | 提到但未详 | **嵌套 Statement + nesting_depth + 算子化 perspective_take**(§9) |
| 前瞻 | Prospective Loop 一节 | **Trigger 类型化 + Commitment 状态机 + 与 RMM 互补**(§11) |
| Affect | Hippocampus 内 Affect 缓冲 | **AffectTag 五维 + salience 计算公式 + 优先级重放权重**(§3.3,§10) |
| 检索 | 简略 | **Retrieval Planner 7 步 + 9 种 Intent 路径 + Abstention 判定**(§12) |
| 自适应遗忘 | 提及 | **MemoryBank + Anderson 公式 + modality 修饰 + 不删除只降级**(§10.4) |
| 与 8 项目关系 | 中间件 | 中间件 + **5 个 SubstrateAdapter profile + 4 种迁移路径**(§4,§15) |
| 评测 | 部分 | **5 维 LongMemEval + 5 维 ToM + 5 维 Anima 新指标**(§14) |
| 字数与结构 | 690 行偏研究稿 | 工程交付稿,数据流端到端示例三例 |

简言之,Anima 把 Polis 的"概念蓝图"做成了"可被工程团队直接接手的设计文档",并补齐了 Polis 缺的:**二阶 ToM 的物理实现、前瞻的 Trigger 类型系统、Affect 的可计算公式、Retrieval 的 Planner 化、Abstention 的判定、迁移路径**。

---

## 附录 A:与 8 个开源项目的能力差异对照表(精炼版)

| 能力 | mem0 | Letta | cognee | MemOS | EverOS | memU | mempalace | claude-mem | **Anima** |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| holder 归属 | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | 🟡 | ❌ | ✅ |
| 二阶 ToM | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| KnowledgeFrontier | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| CommonGround pool | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Affect 五维计算 | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ | 🟡 | ❌ | ✅ |
| 真前瞻(Trigger) | ❌ | ❌ | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ | ✅ |
| 优先级重放 | ❌ | 🟡 | 🟡 | 🟡 | ❌ | ❌ | ❌ | 🟡 | ✅ |
| 模式分离/补全 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Verbatim Drawer | ❌ | 🟡 | ❌ | ❌ | 🟡 | ❌ | ✅ | ✅ | ✅ |
| 双时间(valid_from/to) | ❌ | ❌ | ✅ | ❌ | 🟡 | ❌ | ✅ | ❌ | ✅ |
| supersedes 链 | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Abstention 判定 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Retrieval Planner | ❌ | ❌ | 🟡 | 🟡 | 🟡 | ❌ | ❌ | ❌ | ✅ |
| Persona-Belief 分通道 | ❌ | 🟡 | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ | ✅ |
| Fiske 关系类型 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **认知层成熟度合计** | 0 | 4🟡 | 3🟡✅ | 2🟡 | 5🟡 | 0 | 3🟡✅ | 2🟡✅ | **15✅** |

---

## 附录 B:为什么这套设计能让 LLM"更懂人"

**人类记忆三个不易察觉的特点**:

1. **记忆是"我"的,而不是"事实"的**。我们不记得"咖啡 30 元",我们记得"昨天我和 Alice 在那家店,她请我喝的咖啡 30 元"。Anima 把"我的"做成 holder 字段。

2. **记忆为当前目标重构,不是回放**。Conway SMS 模型核心。Anima 的 Retrieval Planner 用 perspective + goal 重构而非 fan-out。

3. **我对你的画像 ≠ 你对自己的认知**。社会智能的核心。Anima 的 holder 子图族 + perspective_take 算子让"我以为你的样子"和"你自己"分离。

**LLM 当前的"懂人"瓶颈**:

- 不分主体的 fact 全局化 → 矛盾时被迫挑边或编造;
- 不分通道的 persona 与 belief 混存 → 一次会话颠覆长期画像;
- 不区分共识与单边断言 → 反复复述已 grounded 的内容,显得"机械";
- 不追踪信息可见性 → 会泄露未在场者不该知道的;
- 不处理二阶视角 → 不会做礼貌的提示("Bob 应该知道,不过你要不要确认下"),也不会做合适的隐瞒。

Anima 的 schema + 运行时,**每一项都对准上述瓶颈**。这就是它"更懂人"的物理基础 —— 不是 prompt 工程的精进,而是数据模型层对人类社会认知结构的对齐。

---

## 附录 C:致谢与素材出处

本设计在以下素材之上独立成型:
- 8 个开源项目的源码深读(`_research/01-02`)
- Anthropic Claude / OpenAI ChatGPT memory 公开博客
- HippoRAG / EM-LLM / Larimar / A-Mem / RMM / Graphiti / EnigmaToM / SoMi-ToM 等学术工作
- 神经科学与认知心理学经典:McClelland 1995 / Tulving 1985 / Yassa & Stark 2011 / Conway & Pleydell-Pearce 2000 / Clark 1996 / Fiske 1992 / Anderson & Hulbert 2021
- Wilf 2023 SimToM / Kim 2023 FANToM / Cross 2024 Hypothetical Minds

如本文档进入实施阶段,需在第一里程碑前补充:
- 完整 schema 的 Pydantic 实现与 JSON-schema 导出
- Validator 的 LLM 抽取 prompt(XML strict)
- Replay Scheduler 的具体采样器算法与默认权重
- Retrieval Planner 的 9 个 Intent 路径的可执行实现
- 与 mem0 / Letta / cognee / Graphiti 的 4 套 adapter 接入示例

— 完 —


