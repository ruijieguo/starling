# Starling Memory 技术报告

### 面向多主体社会心智表征与类脑动力学的智能体记忆系统

**English version: [Starling_Technical_Report.md](Starling_Technical_Report.md)**

---

## 摘要

主流的智能体记忆栈,本质上是 `user_id` 隔离之上的向量检索增强(vector-RAG):它能记住"说过什么",却建模不了"谁在想什么"。Starling Memory 主张:一个能与人长期协作的智能体,需要的不是更大的检索召回,而是一份**对每个交互对象持续演化的心智模型**——他者的画像、我对他的信念、以及我以为他相信什么——并辅以一套**类脑的记忆动力学**:快写慢洗、优先重放、再巩固(不覆盖)、自适应遗忘、显著性调制、前瞻触发。

本报告介绍 Starling 的三项核心贡献。**(1) 多主体社会心智表征**:以带归属的 `Statement`(陈述)取代无主体的 `Fact`(事实)作为记忆原子,把归属、冲突、撤回、视角、嵌套信念五件事坍缩进同一种数据形状;`Cognizer`(认知主体)是一等公民而非数据库列;高阶信念以"符号嵌套 + 自适应阶数估计 + 感知接地的假信念追踪"三重表征实现任意阶心智推理。**(2) 类脑动力学**:一条贯穿全生命周期的六态巩固状态机,以互补学习系统(CLS)的快(海马)/慢(新皮层)双时间尺度协同为骨架,落实尖波涟漪(SWR)式优先重放、艾宾浩斯遗忘曲线、不覆盖的再巩固 supersedes 链与前瞻承诺状态机。**(3) 高阶信念推理表现**:在 HiToM 高阶心智基准上,把 Starling 的确定性嵌套追踪算子注入一个 14B 模型,**整体准确率 0.7925 → 0.8342(+4.2pp,配对显著),且增益单调集中于最深阶——order-3 +10.8pp、order-4 +8.3pp**;对更强的 deepseek 模型,深层阶(order-3/4)增益达 +15~17pp。

Starling 以现代 C++20 实现内核(约 2.48 万行,其中心智理论模块为单体最大模块),Python 仅作薄绑定。我们同样诚实地刻画其**能力边界**:确定性算子仅在"它比模型自由推理更准"的窄区间(深层嵌套追踪)产生净增益;在已被强模型可靠求解的浅层/扁平任务上持平或有害。一个语义路由门控把最坏情况从 −8.9pp 收敛到 −0.7pp,将系统从"时好时坏"转为"有益或中性"。

**关键词:** 智能体记忆;心智理论;高阶信念推理;互补学习系统;记忆巩固与再巩固;认知中间件。

---

## 1 引言

### 1.1 问题:向量库记得住事实,建模不了心智

过去两年,智能体记忆从"把对话塞进上下文窗口"演进为"向量检索 + 图谱 + 时序边"的成熟工程栈(mem0、Letta、cognee、Graphiti/Zep 等)。这些系统在**事实留存**上已相当好用,但它们共享一个隐含本体:记忆是一条条**无主体的事实**,以 `user_id` 等维度做隔离过滤。这个本体在面对真正的社会协作时会暴露三类结构性缺口:

- **归属塌缩**。"Bob 不再负责 auth"是谁说的?是我亲眼所见、Alice 转述、还是我推断的?扁平事实里,说话人、被谈论者、信念持有者被压成同一层,无法稳定查询。
- **视角缺失**。"我以为 Bob 还不知道这事"这类元信念,是社交得体性、协商、保密的根基;它要求系统持有"A 以为 B 相信什么"的嵌套结构,而非一句话的相似度。
- **静态性**。事实一旦写入就静止——没有巩固、没有遗忘曲线、没有"被回忆即可修订",更没有"无需用户提问即可被唤醒"的前瞻。

借用社会智能研究的话来说,当前系统多依赖**表层模式而非真正的社会推理**:它们能复述,却不能站在对方的视角上推断其心智状态并据此行动。

### 1.2 设计立场:认知中间件,不重写存储

Starling 不试图取代向量库,而是作为**认知中间件**叠加其上:它是"数据模型 + 运行时调度器 + 检索规划器"三件套,可挂在 mem0 / Letta / cognee / Graphiti 之上,为它们补上 `holder`(信念持有者)维度、`Statement` 本体、心智理论(ToM)、类脑重放与前瞻。三条**非目标**界定了它的克制:不重写向量库、不做模型训练、不追求形式逻辑的完备性。

### 1.3 贡献

1. **归属优先的记忆本体(§3.1–3.2)**:`Statement(holder, subject, predicate, object, modality, polarity, time, evidence, confidence)` 这一种形状,在 schema 层同时解决归属、冲突、撤回、视角、二阶 ToM;`Cognizer` 作为带稳定身份、有向信任、Fiske 关系图、知识边界与人格的一等主体。
2. **任意阶心智推理(§3.3–3.5)**:三套互补表征——符号嵌套(`nesting_depth`,软上限 32)、自适应阶数估计器、以及感知接地的假信念追踪(`what_does_X_think` / `what_does_X_think_chain`,共目击者求交 + 观测优先),并配公共知识(common knowledge)闭包算子。
3. **类脑记忆动力学(§4)**:六态巩固生命周期 + CLS 双时间尺度 + SWR 优先重放 + 艾宾浩斯遗忘 + 不覆盖再巩固 + 前瞻承诺机,均落到可运行的 C++ 内核与可审计的事件总线。
4. **视角化检索与心智摘要(§3.6)**:按 `(querier, perspective, intent, goal)` 四元组重构上下文;视角过滤先于语义排序(隐私硬约束);输出带 8 类语用标签的"心智摘要",并支持显式弃答(abstention)。
5. **高阶信念推理的可辩护评测与诚实边界(§5)**:在 HiToM/ToMBench 等基准上量化 Starling 对弱/强模型的增益,定位增益集中的深层嵌套区间,并坦陈泛化失败与有害区间及其成因。

---

## 2 系统总览

### 2.1 三条公理

Starling 的全部机制由三条公理生成,每条都对应一处神经科学或认知科学根据。

- **公理 I —— 没有孤立的事实,只有归属于主体的陈述。** 每条记忆都是 `Statement(holder, subject, predicate, object, modality, polarity, time, evidence, confidence)`。一种形状同时解决归属、冲突、撤回、视角与二阶 ToM。
- **公理 II —— 两套时间尺度协同(互补学习系统,CLS)。** 写入先落入海马(Hippocampus,`VOLATILE`),经重放、模式分离/补全、再巩固,才有机会上升进新皮层(Neocortex)成为稳定的语义 / 规范 / 技能 / 人格。这是 McClelland 等(1995)CLS 理论的工程化:快通道快进快出以抗灾难性遗忘,慢通道缓慢交织以沉淀结构。
- **公理 III —— 记忆为当前目标重构,不是录像回放(Conway 自我记忆系统,SMS)。** 检索返回一份视角塑形的心智摘要,并可显式弃答,而非把一堆工具的结果扇出拼接。

### 2.2 Statement Bus 脊柱与 12 个子系统

整个系统以 **Statement Bus** 为单一入口:所有读写都经它,没有旁路。Bus 内含 `Validator`(校验)→ `ConflictProbe`(冲突探针)→ `outbox`(发件箱)→ `event dispatcher`(事件分发)。围绕脊柱是 12 个子系统:

| # | 子系统 | 职责 |
|---|---|---|
| 1 | Substrate Adapter | 三档存储 profile 的物理底座抽象、能力预检(preflight)、投影索引 |
| 2 | EngramStore | verbatim 原档证据存储 + 留存策略(retention_mode) |
| 3 | Hippocampus | 快记忆(VOLATILE)、事件切分、Working Set、Affect Buffer |
| 4 | Neocortex | 慢记忆(CONSOLIDATED)、holder 子图族、五子区、Persona/CommonGround 容器 |
| 5 | Statement Bus | 写入入口、校验、冲突探针、事件分发、幂等 |
| 6 | Cognizer Hub | 主体注册、别名归一、信任、KnowledgeFrontier、关系边 |
| 7 | ToM Engine | 嵌套信念追踪、`perspective_take`、心智化原语 |
| 8 | Replay Scheduler | Online/Idle/Sleep 巩固、遗忘曲线、SWR 优先采样 |
| 9 | Reconsolidation Engine | 被回忆即可塑、仲裁、supersedes 链 |
| 10 | Prospective Loop | Trigger + Commitment 五态机 + ActionGuard |
| 11 | Retrieval Planner | 9 Intent + 7 步规划 + Context Pack 8 标签 + 弃答 |
| 12 | Runtime Governance | RuntimeHealth 四态、PipelineRun 账本、ScopedWorkGate 限流(横切) |

### 2.3 数据流:Statement 从生到老的物理路径

```
append_evidence ─► EngramStore(永久 verbatim)─► Bus emit: evidence.appended
   ─► Extractor(LLM 抽取多条 Statement)─► Bus.write(Validator+ConflictProbe)
   ─► Hippocampus(state=VOLATILE)─► Replay Scheduler(优先级采样,REPLAYING_CONSOLIDATING)
   ─► Neocortex(CONSOLIDATED, emit statement.derived)
        │                                   │
   被召回/冲突 ▼                      decay S(t)<0.05 ▼
   REPLAYING_RECONSOLIDATING(可塑窗口)    ARCHIVED ──► FORGOTTEN(按 retention_mode)
```

三条**数据流不变量**保证了类脑语义的正确性:

- **EngramStore 永远先写**,再写 Statement;`Statement.evidence` 必须能追溯回原档。这是"海马始终保留逐字原文"的工程落实,也确保抽取错误可被溯源纠正。
- **状态主要单向迁移**,唯一往回的路径是 `ARCHIVED → REPLAYING_RECONSOLIDATING`(被召回唤醒)。
- **provenance(来源)写入即冻结**;轻微纠正只改 confidence + 追加历史,不产新版;严重矛盾才 fork 新版 + supersedes 边 + 旧版归档 + 发件箱事件,四项同事务原子提交。

### 2.4 执行流:事件触发链

写入路径会按 `provenance` 分流触发不同订阅者(`user_input` 触发 Replay/ToM/Affect/Prospect;`replay_derived`/`tom_inferred` 仅触发部分)。两条关键不变量切断了自激循环:**Replay 不订阅 `statement.derived`**(否则派生→重放→再派生无限循环);**causation_chain ≤ 3**,超限即 emit `system.runaway`。检索是**纯读模块**,仅 fire-and-forget 地 emit `statement.recalled`,从不直接改状态——这条事件再异步触发再巩固开窗判定。

### 2.5 实现规模与工程纪律

Starling 的核心一律实现于 C++20 内核(`src/` + `include/starling/`),Python 仅做应用适配(签名归一、DTO 默认值、prompt 配置、只读检视)。判据是"换一种绑定语言是否需要重写该逻辑"。截至本报告:

| 指标 | 规模 |
|---|---|
| C++ 内核(src + include) | ~24,831 行 |
| 最大 C++ 模块 | **`tom/`(心智理论):3,143 行 / 22 文件** |
| 其他主要模块 | bus 2,588 · replay 1,837 · extractor 1,339 · retrieval 1,316 · cognizer 1,236 · prospective 1,099 · reconsolidation 1,054 · neocortex 581 · hippocampus 223 |
| Python 适配层 | ~6,319 行 |
| SQL 迁移(编译期内嵌) | 28 个 |
| 测试 | 143 个 C++ ctest 文件 + 160 个 pytest 文件 |
| 提交历史 | 740 commits |

一个客观信号值得指出:**心智理论是单体最大的 C++ 模块**,而非 prompt 层的薄补丁——这从工程占比上印证了"社会心智"在本系统中是一等深度关切。

---

## 3 多主体社会心智表征(支柱一)

本章是 Starling 区别于向量-RAG 记忆的核心。我们逐层展开:原子(§3.1)→ 主体(§3.2)→ 嵌套信念(§3.3)→ 共识(§3.4)→ 感知/心智态(§3.5)→ 视角检索(§3.6)→ 人格(§3.7)。

### 3.1 Statement 原子:一种形状坍缩五件事

记忆的原子是冻结的 `Statement` 结构(`python/starling/schema/statement.py`,36 字段),其设计目标是让归属、冲突、撤回、视角、二阶 ToM 共用同一形状:

- **主体维度**:`id`、`tenant_id`、`holder: CognizerRef`(谁持有此判断,必须是 Cognizer)、`holder_perspective ∈ {FIRST_PERSON, QUOTED, INFERRED, HEARSAY}`。**正是 `holder_perspective` 把"视角"坍缩进原子**:同一命题第一人称陈述、转述、推断、道听途说,是同一种形状的不同视角值。
- **内容维度**:`subject`(可为 Cognizer 或 Entity,**刻意不允许为 StatementRef**——递归只发生在 object,以保持归一化键可计算)、`predicate`、`object`(**递归槽**:可为标量、Cognizer/Entity 引用,或 `StatementRef`——后者即"关于信念的信念")、`modality`、`polarity`、`confidence` + 追加式 `confidence_history`。`modality` 与 `polarity` 正交:前者是命题态度,后者是 POS/NEG/UNKNOWN。
- **时间维度(五个不同的时间)**:`observed_at`、`event_time`、`inferred_at`、`valid_from`、`valid_to`——区分"何时观察到"与"事实何时生效/失效"。
- **证据与归属**:`evidence`、`source_spans`、`temporal_anchor`、`derived_from`、`perceived_by`(谁感知到了,信息可见性)、`supersedes`。**冲突**=两条共享 `canonical_object_hash` 但极性/holder 相异的陈述,以 `CONFLICTS_WITH` 边表达而非覆盖;**撤回**=新写一条 `modality=RECANTED` + `supersedes` 指针,旧版归档不删。
- **类脑动力学与治理**:`salience`、`affect`、`activation`、`consolidation_state`、`review_status`、`provenance`,以及承载二阶 ToM 的 `nesting_depth`(软上限 32)。

`modality` 给出 12 种命题态度:`BELIEVES, KNOWS, ASSUMES, DOUBTS, DESIRES, INTENDS, COMMITS, PREFERS, NORM_OUGHT, NORM_FORBID, RECANTED, OCCURRED`——把信念、知识、欲望、意图、承诺、偏好、规范、撤回、客观事件统一编码进同一原子。承诺(`COMMITS`)、规范(`NORM_OUGHT`)等被提升为一等命题态度,正是它们能驱动运行时行为(前瞻触发、衰减保护)的前提。

> **设计权衡**:把记忆原子定为带 `holder` 的 `Statement` 而非 `Memory`/`Fact`(类 mem0),从 schema 层一次性解决多主体隔离——长期收益远大于初始复杂度。本系统的判断是:**ToM 是数据结构问题,而非模型问题**;放进 schema 才能稳定查询、可审计、不依赖 LLM 的随机推理。

### 3.2 Cognizer:一等认知主体(对比 user_id 列)

`Cognizer`(`python/starling/schema/cognizer.py`)把 user/agent/group/role 提升为一等主体,赋予生命周期、知识边界与主体间关系:

- **稳定身份**:`id = UUID5(namespace, kind + external_id)`,而非自增列——同一物理人以不同 `kind` 出现即为不同主体。三层归一 `aliases → canonical_name → external_id`;`normalize_alias` 折叠空白、ASCII 大小写,CJK 字节透传,使"Xiao Hong"与"XiaoHong"归一到同一主体。
- **有向、分语境的信任**:`trust_priors[B]` 是"A 对 B 的先验信任",非系统对 A 的信任;初值中性 0.5,随 `commitment.fulfilled`/`broken` 升降。
- **比标签更丰富的社会图**:`RelationEdge` 携带 `fiske_weights`(Fiske 四种关系模型 `Communal/Authority/Equality/Market`,和为 1)、`affinity`、分语境 `trust`、`power_asymmetry`、有效期。关键在于**关系本身存为以观察者为 holder 的 Statement,因此每方对 A–B 关系的看法相互独立**——多视角是原生的。持久化边类型共 14 种(`BELIEVES_ABOUT, TRUSTS, COMMITTED_TO, CONFLICTS_WITH, SHARED_GROUND, OBSERVED_BY, PERCEIVED_BY, NORM_OF, MAY_OVERLAP_WITH, SUPERSEDES, DERIVED_FROM …`)。

作为反衬,`Entity`(非认知物)没有人格、知识边界、信任,只能作 subject/object,**永不能作 holder**。这条边界使"谁能持有信念"在类型层就受控。

> **对比 `user_id`**:user_id 是一个不透明的隔离键;Cognizer 是一个可寻址的主体——有跨源稳定身份、有向的分语境信任、Fiske 类型化的关系图、知识边界、人格,且**它自身可以成为另一主体信念的 subject 或嵌套 object**,这正是高阶 ToM 得以表达的前提。

### 3.3 嵌套信念与任意阶 ToM:三套互补表征

"我以为你以为 X"在 Starling 中有**三套互补表征**,报告应明确区分:

**(a) 符号嵌套(Statement 图嵌套)。** 元信念是一条 `object_kind='statement'` 的陈述,其 `object` 指向内层陈述 id,深度由 `nesting_depth` 携带。holder/subject 链逐层下钻:外层 `holder=self, subject=X, predicate=believes, object→内层`;内层 `holder=X, subject=Y, …`。深度由三道护栏约束而非认知帽:软上限 `kDefaultMaxNestingDepth=32`、`NestingCycle` 环检测、`compute_nesting_depth` 沿祖先链回溯。2026-06-17 的重构**移除了旧的"三阶认知帽",改为任意多阶**。查询用 `what_does_X_think_Y_believes` 以 `WITH RECURSIVE` 逐层解包,`level < max` 保证环安全。

值得强调的是**镜像 vs 编造**的二分:LLM 抽取器只产出扁平陈述,嵌套行由 `tom::second_order` 程序化产生。**自动路径**(镜像伙伴确实表达过的信念)不设门控——加门只会是同义反复;**显式路径**(把伙伴的 k 阶信念包成 self 的 k+1 阶)**仅当深度估计器 `estimate(partner) ≥ k+1` 才落地**,否则记 `gated_order`——这是反编造门:不臆造伙伴从未展示过的更深心智态。

**(b) 自适应阶数估计器。** `depth_estimator::estimate` 读取伙伴近 7 天的陈述,按 `nesting_depth` 直方图折算可信阶数(某深度需 ≥3 条陈述才被采信),保留浅层伙伴的 `{0,1,2}` 下限但**不再饱和于 2**,缓存 1 小时。这让系统对每个对象动态调整"建模到几阶"。

**(c) 感知接地的假信念追踪(HiToM 机制)。** 这一套不是符号的,而是重建"谁在何时感知到某主题的何种状态"。`PerceptionReconstructor` 从所有 `OCCURRED` 事件重算每主体的 `perception_state`。查询原语 `what_does_X_think` 返回 `StateBelief{state_value, is_stale}`——X **最后感知到的**状态,`is_stale = (≠ 全局最新真值)` 即 Sally-Anne 假信念信号。任意阶推广 `what_does_X_think_chain([c1..cN])` 读"c1 以为 c2 以为 … cN 以为主题在哪",答案取**链上每个观察者都共同目击过的事件**中持有者的最高位状态(**共目击者求交**),并实施**观测优先**:转述/告知(hearsay)不得覆盖第一手观测,仅为从未在场者补缺。**roadmap 上那条干净的 +6.4% 增益正源于此(c),而非符号嵌套(a)。**

### 3.4 共同基础与公共知识算子

**共识容器** `CommonGround` 持有 N 元 `parties` 与三个桶:`grounded`("双方都知道双方都知道")、`asserted_unack`("一方说了,另一方未确认")、`suspected_diverge`("怀疑对方其实另有所信")。生命周期由**七种 grounding act** 驱动:`assert_ / acknowledge / repair / withdraw / supersede_ground / expire_ground / unground`。`asserted_unack → grounded` 的**闭合**由四条规则之一触发:显式确认、共同在场推定(`perceived_by` 覆盖全员且连续 3 轮无修复/撤回)、重复确认(≥2 方独立提及)、带审计的人工确认;24 小时超时则降级为 `suspected_diverge`,绝不擅自推定为已共识。

**公共知识算子**(迭代互信念)与一阶共享不同:Anne 私下分别告诉 A、B、C 同一件事,三人都相信它(一阶共享命中),但这**不是公共知识**(A 不知道 B 知道)。`is_common_knowledge` 实现其闭包:**当且仅当群组 G 中任一成员最后感知到的主题事件被 G 全员共目击(一次公开确立)时,X 的当前状态才是 G 的公共知识**。实现为集合求交/不动点:取每成员的感知事件集,群最高位事件若被全员共目击则为真。该算子复用了 `what_does_X_think_chain` 的事件求交逻辑。

### 3.5 感知/知识追踪、BDI+K 心智态、faux-pas 检测

- **知识边界(KnowledgeFrontier)** 刻画"此主体**可能**知道什么":可见性闭包 = `(在场日志) ∪ (被明确告知 ∪ 可达来源 ∪ 群成员) EXCEPT (被明确告知"不知道")`,全部以时间为界。其上的三值知识查询 `does_X_know → {FullKnowledge, NotKnown, Unknowable}` 做出了多数记忆系统做不到的认识论区分:"已断言" vs "未断言但有可见证据路径" vs "根本无可见路径"。
- **BDI+K 心智态内化**:核心 C++ 聚合 `mental_state_of(X) → {beliefs, knowledge, desires, intentions, commitments, preferences}`。分桶**先谓词后样态**(解决"modality=BELIEVES 但 predicate=prefers"的歧义),一条陈述恰好入一桶。其设计教条值得引述:**能力落进 C++ 内核、开箱即用;评测服务/OpenClaw/未来绑定只是薄消费方,而非各自重新实现。**
- **faux-pas(社交失言)检测**:`detect_faux_pas` 扫描"角色 × 主题",以 `what_does_X_think(...).is_stale` 判定谁因离场而持有过时认知,产出失言的**结构性前提**(注意:语义敏感性不在此判定)。
- **实体/主题接地(entity/theme grounding)**:这是让上述机器真正"命中"的接缝。一次评测曾仅得 0.39——感知逻辑"凡能接地的探针 95% 正确",但"59/100 探针从未接地",根因是接地接缝处的**表层漂移**("Xiao Hong" vs "XiaoHong","cabbage" vs "the cabbage" vs "cabbages"按原始精确匹配被劈开)。修复是在字节级冻结的 `canonicalize_object` **之前**加一道确定性 `normalize_theme`(去冠词 + 保守单数化),且保证 `canonicalize_object` 不变(哈希不迁移)。端到端提升:**位置假信念精度 0.39 → ~0.78,接地率 0.41 → ~0.83**。

### 3.6 视角化检索与"心智摘要"

检索规划器按 `(querier, perspective, intent, goal)` 四元组重构上下文,而非工具堆的扇出。查询对象 `PlannerQuery` 含 `querier`(谁在问)、`perspective`(从谁视角)、`intent`、`target`。**9 种 QueryIntent**:`FACT_LOOKUP, BELIEF_OF_OTHER, META_BELIEF, HISTORY, COMMITMENT_DUE, PREFERENCE, NORM_LOOKUP, COMMON_GROUND, ABSTAIN_CHECK`。

**7 步管线**:`parse → mask → plan → fetch → fuse → ground → abstain`。一条硬不变量定义了系统的隐私立场:**视角过滤必须先于语义排序**——`mask` 步以目标的 `KnowledgeFrontier` 做 EnigmaToM 式迭代遮蔽,这是不可绕过的隐私边界;检索回执必须证明过滤已执行(`frontier_masked_count`),否则结果不得返回。视角快照由 `perspective_take(target)` 给出 = `按目标可见证据集过滤 ⊕ 目标的信念子图 ⊕ 双方共识`——任何对话/规划/协商都先调用它再决策。

输出不是无差别的 RAG 文本,而是带 **8 类语用标签的"心智摘要"**,让 LLM 理解每条记忆的认识论地位:`FACT`(既定共识)、`BELIEF`(某方观点 + 置信度)、`HEARSAY`(单一来源、可能过时)、`INFERRED`(从行为推断)、`COMMON`(全员知晓)、`TODO`(承诺 + 截止)、`CONFLICT`(各方分歧未决)、`ABSTAIN`(无可靠记忆)。重排融合相关性、新近度、显著性、激活与情感一致性。**弃答(abstention)** 按四条件触发(优先级 `frontier > recanted > conflict > score`):被遮蔽清零、仅有撤回证据、未决冲突、或最高分 < 0.25——输出结构化的"我不知道,因为___",而非编造或含糊。回执的 `sufficiency` 四值(`SUFFICIENT/MISSING_INFO/NEEDS_RAW/ABSTAINED`)让评测者能区分"没找到"vs"被权限遮蔽"vs"投影过期"vs"主动弃答"。

### 3.7 Persona 容器:稳定的他者画像

`Persona` 是**物化视图**而非陈述:权威事实留在 Statement 图,容器由 `Bus.rebuild_container` 在单版本 CAS 下重建。其**双通道**设计映射神经科学:Persona 是**慢通道**(每 N 次会话经 Replay 更新,映射 vmPFC 稳定自我/他者模型),逐 holder 信念是**快通道**(每次写入即更新,映射 dmPFC 快速社会信念更新)——单次会话绝不触碰 Persona。**多源仲裁**:`self_model_anchor`(主体自述)优先于 `profile_anchor`(他人对其陈述);二者置信度差 ≥ 0.5 即标 `suspected_diverge` 并交由 ToM Engine,而非擅自写入。并发重建以乐观 CAS 守护,版本不匹配抛 `ConcurrentRebuildError` 且不自动重试。

---

## 4 类脑动力学(支柱二)

如果说支柱一是"记什么、为谁记",支柱二就是"记忆如何随时间活着"。Starling 的动力学不是比喻,而是逐条落到公式、参数与可审计状态机的工程实现。一个统领性事实:**海马与新皮层是同一张 `statements` 表上以 `consolidation_state` 列区分的逻辑分区,而非物理表**——"在两库间搬运记忆"= 翻转一个字符串标签 + 发一条 Bus 事件。这本身就是本系统对 CLS"跨视图流动"的解读。

### 4.1 互补学习系统(CLS)

公理 II 是 CLS 的逐字工程化(McClelland 等, 1995):写入先入海马(`VOLATILE`,快通道快进快出以抗灾难性遗忘),只有经重放、模式分离/补全、再巩固后才上升进新皮层成为稳定语义。新皮层不接受直接写入,只经 Bus 在巩固后写入,持有**五子区**:语义 / 程序 / 规范 / 人格 / 共识。EngramStore 与海马/新皮层**平级**(被 `Statement.evidence` 指向),是"海马始终保留逐字原文"的工程落实;其摄取策略含**自污染防护**——`SYSTEM_INTERNAL/REPLAY_OUTPUT` 一律 `NO_STORE`,使重放产物不会被当作新证据再摄取。

### 4.2 六态巩固生命周期

`consolidation_state` 是贯穿全生命周期的一等列,六个状态(C++/Python 双侧 parity 钉测):

| 状态 | 语义 |
|---|---|
| `VOLATILE` | 刚写入海马分区,未巩固 |
| `REPLAYING_CONSOLIDATING` | 从 VOLATILE 选中,首次向新皮层巩固 |
| `REPLAYING_RECONSOLIDATING` | 从 CONSOLIDATED/ARCHIVED 召回,对既有版本再巩固 |
| `CONSOLIDATED` | 在新皮层定居,长期可查 |
| `ARCHIVED` | 久未召回,移出热路径但保留索引,仍可召回 |
| `FORGOTTEN` | 移出全部检索,EngramStore 按 retention_mode 处置 |

状态机声明了 11 条合法转移(T1–T11 + T7-P1),但**运行时不靠一个 `can_transition` 函数守护,而是靠逐边的 SQL 比较并交换(CAS)**:每个存储方法带 `WHERE consolidation_state='<from>'` 条件,非法或重复转移匹配 0 行,成为静默幂等 no-op——这天然消除并发竞态。配套兜底:振荡上限 `MAX_CONSOLIDATION_ATTEMPTS=5`(超限强制 CONSOLIDATED + 待审)、VOLATILE TTL 7 天(除非在 Affect Buffer 中)、未决承诺的衰减保护、共识条目免衰减。

### 4.3 重放调度:遗忘曲线、SWR 采样、巩固算子、三模式

**遗忘/衰减曲线(艾宾浩斯)。** 纯指数可提取性:

```
S(t) = exp(-Δt / S0)
S0 = 86400 · (1 + 0.5·access_count) · (1 + salience)
        · (1 + 2.0·active_grounded) · decay_modifier(modality) · (1 + 0.3·|valence|)
```

`decay_modifier` 按样态:**COMMITS=4.0, NORM_OUGHT=3.0, KNOWS=2.0, BELIEVES=1.0, ASSUMES=0.5**——承诺抗衰减约为假设的 8 倍。当 `S(t) < 0.05` 且非 `active_grounded` 时归档。这融合了 MemoryBank(艾宾浩斯)与 Anderson 的主动遗忘。

**尖波涟漪(SWR)优先采样**(对应海马 SWR 与优先经验回放 PER):

```
w = salience · novelty_decay(last_replayed) · (有冲突?1.5:1) · (1 + 0.4·arousal)
       · (目标相关?1.5:1) · provenance_factor / (1 + replay_count)
```

`provenance_factor`:`user_input=1.0`,`tom_inferred=0.25`,派生类=0。三道硬门在公式前生效:provenance 为 0 直接置 0(派生/再巩固陈述永不重入采样池,**断开重放循环**)、`derived_depth ≥ 3` 置 0、5 分钟冷却。神经科学上,海马 SWR 在静息期优先重激活高显著、高新颖、高预测误差的情节(Buzsáki;Mattar & Daw, 2018;Schaul 等, 2015)。

**巩固算子。** 内核 `enum ConsolidationOp { Compress, Abstract, Reinforce, Decay, Reconcile }`:压缩(聚类合并相似情节)、抽象(多 holder 同谓词 → 喂 Persona 重建)、强化、衰减(→ARCHIVED)、调和(把冲突路由给再巩固,重放本身不裁决)。**三种调度模式**对应清醒/静息/睡眠重放:Online(每 3 次写入采样 3 条,仅压缩)、Idle(采样 30 条 + gist 提案)、Sleep(全扫 200 条 + 完整 gist 写入)。

**gist 语义化(睡眠期抽象)。** 一条 NORM-gist 需 ≥3 个不同 holder 就同一 `(谓词, 对象哈希)` 断言,经 LLM 判定置信度 ≥0.6,再加**一道独立的逐成员蕴含验证 LLM**(防虚构/过度泛化的关键门),才作为惰性 norm 写入。这正是 CLS"海马细节 → 新皮层 schema"的转移:把 ≥3 条独立情节池化为一条泛化语义规范。

### 4.4 模式分离与补全

设计把二者映射到齿状回(DG)稀疏编码与 CA3 自联想:

- **模式分离(写入时,DG)**:近重复(余弦 > 0.85)时对邻居做 **Gram-Schmidt 正交化**偏移,并记一条 `MAY_OVERLAP_WITH` 软边;**默认保留细微差异而非合并去重(与 mem0 的根本区别)**——"差异往往是认知线索而非噪声;合并会不可逆地丢失'谁在何时认为什么'"。
- **模式补全(检索时,CA3)**:从 ANN 种子出发的扩散激活游走,每跳 `贡献 = 激活 · 边权 · 衰减`,**按 MAX 合并而非求和**(吸引子行为:节点激活 = 最强路径),返回一个连通的情节子图而非孤立行。

**Working Set(工作集,前额叶主动维持)** 以 2000 token 预算,按固定优先级 `待履行承诺 > 人格 > 共识 > 相关记忆 > 情感` 装配——已触发的承诺以 `⚠ DUE:` 注入。

### 4.5 再巩固:不覆盖

命题:Starling 只在**召回/冲突后**才修改记忆,且**绝不删除旧版**——这是大脑可塑性的工程模拟,对比 mem0 的破坏性 UPDATE。

- **可塑窗口(Nader, 2000)**:再巩固引擎是发件箱订阅者;召回不直接开窗,而是发事件被异步消费。四个开窗触发:`statement.recalled / references_existing / belief.conflict / reconsolidate.requested`。窗口时长自适应:默认 30 分钟,按样态 `COMMITS=360 / NORM_OUGHT=180 / KNOWS=60 / BELIEVES=30 / ASSUMES=5` 分钟,高频更新对象缩至 5 分钟,clamp 在 **5 分钟–6 小时**(6 小时上限引 Nader 2000 神经科学参考值)。
- **召回时仲裁**:窗口关闭时聚合待决证据,`strength` 落入三路径:**<0.3 支持**(置信度↑→CONSOLIDATED)、**[0.3,0.7] 轻微矛盾**(置信度↓ + 追加历史,**provenance 不变、不产新版**,避免小修正引发链膨胀)、**>0.7 严重矛盾**(走 supersedes)。
- **supersedes 链(保留而非删除)**:严重矛盾在一个 SAVEPOINT(嵌套事务,非 BEGIN)内原子提交 4 项——fork 一行新版(`supersedes_id = 旧 id`,刻意不发 `statement.written` 以防重入重放)、写一条 `supersedes` 边、把旧行**归档而非删除**、发 3 条事件。schema 层还有 `BEFORE UPDATE` 触发器对身份字段的就地改写 `RAISE(ABORT)`,强制走 supersedes 路径。

### 4.6 情感与显著性调制

`AffectVector` 五维:`valence[-1,1], arousal[0,1], dominance[-1,1], novelty[0,1], stakes[0,1]`(PAD/VAD 三元 + 两个评价旋钮)。显著性归约:

```
salience = (0.4+0.6·|valence|)·(0.4+0.6·arousal)·(0.3+0.7·novelty)·(0.3+0.7·stakes)·(0.6+0.4·surprise_decay)
```

情感在多处调制记忆:重放采样的 `(1+0.4·arousal)`(杏仁核/去甲肾上腺素对巩固的调制,McGaugh)、遗忘曲线的 `(1+0.3·|valence|)`(情绪记忆增强、闪光灯记忆)、检索重排的情感一致性(心境一致性回忆,Bower)、以及 Affect Buffer 对高显著 VOLATILE 行的 7 天 TTL 豁免(类似突触标记捕获)。

> **实现诚实性**:本报告同时给出"已接线 vs 设计保留"的真实状态。当前写入路径的 `affect_json` 默认为空,内容驱动的情感评价器尚未上线(列入 P3),因此除二阶 ToM 的显著性继承(×0.8)外,多数情感项跑在出生中性值上;`appraise_emotion`(基于 OCC/Scherer 评价理论)目前是研究/设计稿。**完全接线**的是:六态 CAS 生命周期、SWR 加权重放(显著性/唤醒/新颖/来源)、艾宾浩斯衰减与压缩/衰减算子、gist 语义化、DG 模式分离 + CA3 补全、完整的再巩固 supersedes 机器、以及无需提问即触发时间触发器的前瞻 tick 循环。

### 4.7 前瞻记忆:无需提问即被唤醒

前瞻回路让智能体在无用户查询时主动行动。**Commitment 五态机**(`ACTIVE/FULFILLED/BROKEN/RENEGOTIATED/WITHDRAWN`),全部转移以 `WHERE state='ACTIVE'` 原子守护:履行→FULFILLED;截止过期且 `broken_count<3`→BROKEN;`≥3`→自动 WITHDRAWN(慢性失败);重协商链 <3→RENEGOTIATED(+ supersedes 边 + 新 ACTIVE),≥3→阻断。BROKEN 非终态("后来又答应了")。**四类 Trigger**:time(ISO 时刻)、event(事件类型)、state(字段谓词,白名单防注入)、compound(all_of/any_of 递归,深度 ≤16)。**ActionGuard** fail-closed(`Allow/RequiresApproval/Blocked`)守护外部动作。

"无需提问"的循环具体落地:Dashboard 引擎起一个 30 秒守护线程 `starling-bg-tick → tick_all → policy.tick`,在无任何事件时仍会触发到期的 TimeTrigger(`commitment.fire`)、并破/自动撤回过期承诺——完全自发。触发的承诺以 `⚠ DUE:` 浮现在 Working Set 并经 WebSocket 推到 UI。**意图优越效应(intention-superiority)** 的工程对应:一个活跃承诺通过 `active_grounded` 标记屏蔽其相关陈述的衰减,履行后 `commitment.released` 解除保护(对应 McDaniel & Einstein 多过程框架与 Goschke & Kuhl 意图优越效应)。

### 4.8 神经科学锚点小结

| 机制 | 神经科学根据 |
|---|---|
| 快/慢双系统、六态巩固 | 互补学习系统 CLS(McClelland et al., 1995);情节/语义(Tulving, 1985) |
| SWR 优先重放 | 海马尖波涟漪(Buzsáki);优先经验回放(Mattar & Daw, 2018;Schaul et al., 2015) |
| 遗忘曲线 / 主动遗忘 | 艾宾浩斯遗忘曲线;Anderson 主动遗忘 |
| 模式分离 / 补全 | 齿状回稀疏编码 / CA3 自联想(Yassa & Stark, 2011) |
| 再巩固可塑窗口(5min–6h) | 再巩固(Nader, 2000) |
| 情感调制 | 杏仁核情绪巩固(McGaugh);心境一致回忆(Bower);PAD 维度(Mehrabian-Russell) |
| 检索按目标重构 | 自我记忆系统 SMS(Conway, 2000) |
| 前瞻记忆 | 时间/事件双过程(McDaniel & Einstein);意图优越(Goschke & Kuhl);BA10(Burgess) |
| 社会关系建模 | Fiske 关系四模型 |

---

## 5 高阶信念推理:评测(支柱三)

本章是全报告最需谨守诚实的部分。我们给出**可辩护的头条结果**、增益的**阶数分布**、以及**何处不帮/有害及其成因**。所有数字均经一手评测产物(ToMEval `metrics.json`)或仓库内提交文档核验,并明确区分 **干净/当前** 与 **已被项目自身撤回的伪迹** 数据。

### 5.1 评测设置:Starling-in-the-loop 三模式

需区分三种测量模式,切勿混为一谈:

1. **裸 LLM 心智地板**:MCQ 直送 LLM,Starling 不介入,给出"模型自己能到几分"。`max_tokens=32768`(推理模型的隐藏 CoT 计入预算,过小的上限会截成空内容而误判)。
2. **仅 Starling 机器**:嵌套由**确定性 C++**(belief_tracker → `what_does_X_think_chain`)产生,而非 LLM 推理;`--mode deterministic` 从模板问题播种信念以隔离记忆机器。
3. **Starling 端到端在环**(`scripts/starling_tomeval_server.py`):一个 OpenAI 兼容端点,外部 ToMEval 框架向它发请求。每请求:解析故事 → `remember()` 写入一次性 Starling 库(LLM 驱动抽取)→ 导出脚手架 → LLM 看着脚手架回答 MCQ。**同一个 LLM 既是 Starling 的抽取器,也是最终答题者**——因此本模式测量的是"结构化记忆是否帮到了模型"。注入按优先级:order≥2 的嵌套问走 `chain`、公共知识问走 `ck`、否则走 belief_digest/mental_state/faux_pas/memory_dump。

门控开关即安全机制:`STARLING_CHAIN_ONLY`(仅 order≥2 注入,因 order-0/1 注入实测净伤 −0.096)、`STARLING_PASSTHROUGH`(零注入纯配对基线)、`STARLING_NO_THINK_EXTRACT`(给抽取 prompt 加 `/no_think`,因思维链 `<think>` 痕迹会破坏抽取解析)、`STARLING_NO_THINK_ANSWER`(让弱模型读注入而非重推)。

测试模型:deepseek-v4-pro(主在环 LLM + 答题者)、deepseek-v4-flash、本地 Qwen3-14B(v3.4)与 Qwen3-8B(v3.2);gpt-5.5 等仅在裸 LLM 基线表出现。(注:文档里的 "o3/o4" 指 **HiToM 的 order-3/order-4**,**不是模型名**。)显著性用同 id 配对 McNemar/二项检验。

### 5.2 数据集

| 数据集 | 测量 | 阶/结构 |
|---|---|---|
| **HiToM** | 多房间、多主体、含欺骗的嵌套假信念 | **order 0–4**,每阶 240 题;order-k = "A 以为 B 以为 …(k 层)X 在哪" |
| **ToMBench** | 8 类社会认知能力族 | 一/二阶假信念 + 欲望/意图/知识/情感/非字面/暗示/说服 |
| **ToMBench 二阶子集** | Perner-Wimmer 二阶假信念 | 200 题(干净 196) |
| **FanToM** | 多方对话的信息不对称 | factual/belief/answerability(仅裸 LLM 画像) |
| **Commitment** | 承诺/截止追踪 | 100 场景,离线确定性,无 LLM |
| **LongMemEval** | 长程记忆 | 时间推理 / 知识更新子集 |
| **CK v1/v2** | 迭代互信念 / 公共知识 | v1 共同在场 gold,v2 公告制 gold |

### 5.3 主结果

**裸 LLM 心智地板(无 Starling):**

| 数据集 (N) | deepseek-v4-pro | gpt-5.5 |
|---|---|---|
| HiToM (1200) | 0.7458 | 0.7758 |
| ToMBench (5720) | 0.8271 | 0.8509 |
| FanToM (11292) | 0.8612 | 0.8841 |
| BigToM (5000) | 0.9068 | 0.9160 |
| EmoBench (800) | 0.7275 | 0.7425 |

**准入门(Starling 机器 / 端到端):**

| 轨道 | 结果 | 阈值 |
|---|---|---|
| ToMBench 一阶 (24),deepseek-v4-flash ×3 | **1.000 / 1.000 / 1.000** | ≥0.55 ✅ |
| ToMBench 二阶 — 裸 LLM 地板 | **0.990**(干净 194/196) | ≥0.70 ✅ |
| ToMBench 二阶 — Starling 机器(确定性) | **1.0000**(196/196) | ≥0.70 ✅ |
| ToMBench 二阶 — 端到端(抽取) | **1.0000**(195/195) | ≥0.70 ✅ |
| ToMBench 全量画像 (2860),deepseek-v4-pro | **0.8315**(2378/2860) | 画像 |
| Commitment (100) — 检出 / 及时性 | **1.0000 / 1.00 turns** | >0.80 / <3 ✅ |
| LongMemEval (24×3) — 时间 / 知识更新 | **1.0000 / 1.0000** | ≥0.55 ✅ |
| 感知位置假信念 (100) — 端到端精度 | **0.39 → ~0.78** | — |

ToMBench 全量按能力族:最强 **多重欲望 1.0、假信念 0.97、暗示 0.95**;最弱 **情绪调节 0.35、相异欲望 0.45、说服 0.52**——失分集中在需要细腻情感/动机推断而非追踪的能力上。

### 5.4 高阶信念故事:增益集中于最深阶

**最干净、最可辩护的结果——Qwen3-14B v3.4**(同日配对,0 fallback,0 抽取失败):

| order | 基线(整体 0.7925) | +Starling(整体 **0.8342**) | Δ |
|---|---|---|---|
| 0 | 1.000 | 1.000 | 0 |
| 1 | 0.9125 | 0.925 | +1.3 |
| 2 | 0.7292 | 0.733 | +0.4 |
| **3** | 0.6625 | **0.7708** | **+10.8** |
| **4** | 0.6583 | **0.7417** | **+8.3** |
| **整体** | 0.7925 | **0.8342** | **+4.2pp**(p≈1.9e-5) |

增益**单调集中于最深的 order-3/4**——恰是 CoT 工作记忆开始崩溃、而确定性"共目击者求交"算子发力的区间。order-0/1 持平(模型本就会),正是 `CHAIN_ONLY` 门控只在 order≥2 注入的原因。

**更强模型 deepseek-v4-pro**:修复版 Starling 0.8025 vs 归档基线 0.738 = **+6.4%**,其中 order-3 +16.7pp、order-4 +15.8pp。需要诚实标注的是:0.738 这个基线被项目自身记为"被约 64 次代理 fallback 衰竭过";对更干净的同仓库基线(0.7458/0.7508),修复版为 **+5.2~5.7pp**;但**无论选哪个基线,order-3/4 的 +14~17.5pp 增益都稳健**。因此可辩护的表述是:**整体约 +5~6.4pp,集中于 order-3/4。**

支撑这一增益的三处可泛化修复:**(1) 房间作用域感知**(`perception_reconstructor.cpp`:离场角色不再误目击他房间的移动);**(2) 观测/转述分离**(`mentalizing_chain.cpp`:第一手观测优先,转述/谎言仅补缺);**(3) `CHAIN_ONLY` 能力门控**(仅 order≥2 注入)。

> **已撤回的伪迹(不应引用)**:更早的 "+4.4" 结果被项目判定为**衰竭基线幻象**——干净的旧版(未修复)Starling vs 归档基线实为 −0.005(≈基线)。报告据此弃用该数。

### 5.5 弱模型的甜区与抽取依赖

把同一套注入用于更弱的 **Qwen3-8B v3.2**:整体 ≈ −1.4pp(p=0.24,不显著)——难故事上抽取退化 → 链误算 → 无净增益。甜区条件由此清晰:**模型须强到能可靠抽取,且仍存在嵌套 gap**;14B 满足,8B 不满足。这说明 Starling 的确定性算子是"放大器"而非"魔法":它依赖一次足够好的抽取把故事变成可追踪的感知状态。

### 5.6 诚实边界:何处不帮、何处有害,及原因

一条不等式统领全局:**确定性注入帮忙 ⟺ `det_acc(任务) > cot_acc(任务)`**——因为同一个 LLM 走两条路,只有当算子捕捉到模型自由推理会丢失的多步机械追踪(深层共目击求交)时才有净增益。这个区间很窄。

| 探针 | 结果 | 判定 |
|---|---|---|
| ToMBench 在环(300 / 全 5720) | +1.3pp(p=0.39)/ −0.05pp | 持平 |
| ToMBench 分层"优化" | 净 +4 → −1 → −9(逐层更差) | 有害 |
| **CK v1**(共同在场 gold) | +9.2pp(p=4.8e-7) | **定义性假象**:gold 即算子自身的共目击定义,注入覆盖了 deepseek 更严谨的读法 |
| **CK v2**(公告制 gold) | +0.83pp(p=0.5) | 边界:无真实 gap |
| faux-pas(ToMBench) | 算子 0/6 触发 → 惰性 | 结构错配 |
| ExploreToM 文学体 order-2 | **−19.6pp** | 文学叙述破坏抽取 |
| SocialMind 中文文学一阶 | **−8.9pp** | 同上 |
| 信息流脚手架接口 | **−8.9pp** | 有害 |

> **证据等级说明。** HiToM 逐阶结果、ToMBench/准入门各表、以及在环 ToMBench 数字,均读自已提交的评测产物(`metrics.json`);而 ExploreToM(−19.6pp)、SocialMind(−8.9pp)、脚手架(−8.9pp)的有害增量,以及 14B/8B 的 p 值,来自未提交为 `metrics.json` 的探索性 PoC 运行——本报告将其作为方向性证据列出,而非主基准。

**为何 deepseek 不需要帮助**:边界研究直接证明,deepseek 在**给定约定**下能以天花板级精度求解每一个结构化追踪任务——包括 order-5 六主体、强制再收敛的链(15/15)。HiToM 的增益本质是**在一个欠定基准上强制约定**(房间作用域 + 观测优先),而非一次算力能力的提升。残余的 HiToM 失分使用了**非标准的嵌套 gold**(deepseek 也答错;标准递归 ToM ≠ HiToM 的 gold),匹配它们等于逆向工程生成器 = eval 拟合,被明令禁止——我们止步于可泛化的天花板。

### 5.7 语义路由安全门控

既然增益区间窄而有害区间真实存在,产品化的关键是**一个永不有害的门控**。一个 LLM 路由器把任意问题/语言映射到 `{算子, 主体, 主题}` 或 `NONE`;以此门控注入,把无差别注入的最坏情况从 **−8.9pp 拉回 −0.7pp(≈中性)**。这把 Starling 从"时好时坏"转为"有益或中性",是被判定为可上线的那一块。

### 5.8 评测可复现性与告警

关键告警均已固化进代码:**fd 泄漏**(在环服务每请求须 `mem.close()` + `gc.collect()` + 删临时库,否则数千请求后 libcurl 取不到 socket → 空答,这才是早期"70% fallback"真因,而非限流);**静默抽取失败**(适配器出错则降级返回空,服务端因此回退一个可解析的 `\boxed{A}` 而非空串);**HTTP 传输**(基线经 C++ 适配器强制 HTTP/1.1 以避免 24 并发下 HTTP/2 尾部停滞);`max_tokens=32768`。多数 p 值来自一次性 PoC 脚本(未提交),已据实标注。

---

## 6 端到端实例:Alice / Bob / Carol

一个贯穿三支柱的场景。**输入**:Alice 在群聊说"Bob 不再负责 auth,现在 Carol 接手"。

**写入(§3.1 + §4.5)**。抽取出 4 条 Statement:

| ID | holder | subject | predicate | object | modality | polarity |
|---|---|---|---|---|---|---|
| S1 | self | Bob | responsible_for | auth | BELIEVES | NEG |
| S2 | self | Carol | responsible_for | auth | BELIEVES | POS |
| S3 | self | Alice | BELIEVES | ⟨S2⟩ | — | POS(二阶) |
| S4 | Alice | Bob | responsible_for | auth | BELIEVES | NEG |

事件序列:`evidence.appended → statement.written ×4 → belief.conflict → corrected + archived + superseded`。旧"Bob 负责 auth"陈述被冲突探针命中,严重矛盾路径同事务原子地写新版 + supersedes 边 + 旧版归档(不删)。高显著进 Affect Buffer;ToM 更新共识(全员在场 → Bob 标"应已知")。

**检索(§3.6)**。查询"Bob 还负责 auth 吗?"(intent=`FACT_LOOKUP`):解析 → 遮蔽(querier=user,无遮蔽)→ Neocortex 命中 supersedes 链 → EngramStore 取 Alice 原话片段 → `ToM.shared_with([self,user])` 检查共识发现未共享 → 主动 grounding。输出 Context Pack 三标签:`[FACT]` Bob 已不再负责 auth、现由 Carol 接手(附 EngramStore 证据)、`[HISTORY]` Bob 此前负责约 8 个月、`[COMMON]` 这是首次告知你、需确认知悉吗?

**元信念(§3.3c)**。查询"Bob 知道这事吗?"(intent=`META_BELIEF`):`does_X_know(Bob, ⟨Carol 现负责⟩)` 经 KnowledgeFrontier 判定——若 Bob 不在宣布现场且无可见路径,返回 `NotKnown`,据此提示"或许需要主动同步给 Bob"。这正是无主体向量库无法表达的认识论区分。

---

## 7 相关工作

**vs 主流智能体记忆栈。** Starling 把自己定位为认知中间件而非替代品:任何开源系统都可作 SubstrateAdapter 后端,Starling 在其上叠加 holder + Statement + ToM + Replay + Prospective。具体映射:**mem0** 的 `actor_id` 是 holder 的雏形,其 `{user_id, agent_id, run_id, actor_id}` 四维映射到 `Cognizer.id`;Starling 补二阶 ToM + 承诺触发 + holder 维度隔离。**Letta** 的 sleeptime → Replay、shared_blocks → CommonGround、ToolRulesSolver 8 规则 → ActionPolicyGraph,其 Identity ORM 被直接作为 Cognizer 设计参照。**Graphiti** 是 episode-first 且**无 holder 维度**(迁移必须补上),其 `valid_at/invalid_at/expired_at` 映射 Starling 的时序与 supersedes。**cognee** 的 DataPoint 子类 → Statement 子类,多用户访问控制 → ProfileCapability。核心差异:这些系统记录无主体事实,Starling 记录**带视角的、可嵌套的、有生命周期的信念**。

**vs 心智理论评测与社会推理研究。** ToM 基准(ToMBench、HiToM、FanToM 等)度量 LLM 的社会推理能力;近期工作(如以对抗样本与轨迹级对齐提升小模型社会推理的方向)指出当前模型常依赖**表层模式而非真正推理**。Starling 与这条线互补但正交:它不训练模型,而是提供一个**确定性的、可审计的记忆基底**,把"谁感知到什么、谁以为谁相信什么"显式化;评测(§5)恰恰诚实地界定了这种确定性结构在何种区间(深层嵌套)能补强一个强 CoT 模型、在何种区间冗余甚至有害。

---

## 8 设计权衡

每个设计都对应一个被放弃的替代方案。

| 选择 | 替代 | 理由 |
|---|---|---|
| Statement(强制 holder)为原子 | Memory/Fact 为原子(类 mem0) | schema 层解决多主体隔离;长期收益 > 初始复杂度 |
| 嵌套 Statement 表达高阶 ToM | prompt 层模拟 ToM 模块 | ToM 是数据结构问题非模型问题;入 schema 才能稳定查询、可审计、不靠 LLM 随机 |
| 六态状态机 | 三态(DRAFT/STABLE/TOMBSTONED) | 六态体现 CLS 巩固/再巩固生物学根据 |
| 再巩固 fork+supersedes | UPDATE 原 Statement | 保留版本链供 ToM/审计/回滚;防"我说过 X 但记忆已覆盖" |
| 默认保留差异(模式分离) | 默认合并去重 | 多视角必须共存;差异常是认知线索而非噪声 |
| 后台异步 Replay 巩固 | 同步抽取即巩固 | 同步拖慢写入且失去重组机会;睡眠期离线重放是 CLS 神经科学基础 |
| Bus 单入口 + outbox | 直接库写 + 触发器 | 事件序列化 + 跨子系统幂等 + 重启可恢复 |
| 承诺/规范为一等 Statement 子类 | 放进 metadata 或 KV | 全行业空白;一等公民才能驱动运行时行为 |
| 自然语言 belief 注入 Context Pack | 形式化 belief base(PDDL) | LLM 对自然语言理解远好于形式逻辑;形式化作 P3+ 可选 |
| C++ 内核 + 多语言绑定 | 纯 Python/Rust/Go | 延迟可预期;零开销抽象;与底层存储同栈 |

---

## 9 局限与边界

我们刻意以诚实的边界刻画收束,这既是工程纪律,也呼应了评测(§5)的诊断式精神。

- **确定性算子的价值区间窄**:仅深层嵌套追踪(HiToM order-3/4)满足 `det_acc > cot_acc`;泛化到 ToMBench/ExploreToM/SocialMind 与多种接口均 NULL 或有害。语义路由门控是目前唯一被判定可上线的"永不有害"封装。
- **强依赖一次好的抽取**:整条感知/ToM 机器以抽取产物为输入;弱模型或文学体叙述会在抽取处退化,导致链误算(§5.5–5.6)。
- **部分类脑机制已接线但暂未喂数据**:内容驱动的情感评价器、`appraise_emotion`、循环/cron 触发器、完整 `ActionPolicyGraph` 执行器列入 P3+;当前情感多跑在出生中性值(§4.6)。报告对此据实标注,不夸大。
- **LLM 抽取成本**:每条 Engram 至少一次 LLM 调用,规模化成本待估;缓解=专用小抽取模型 + 抽取去重缓存。
- **隐私 vs ToM 张力**:系统持有"A 以为 B 不知道 X"这类元数据,错误视角下绝不得泄露——故视角过滤在检索管线早期执行且不可跳过(§3.6)。
- **冲突保留 vs 体验**:保留多视角是设计选择,但直接呈现"3 个互相冲突的 belief"可能令 LLM 困惑;缓解=Context Pack 的 CONFLICT 标签 + 置信度排序 + 默认只注入最高置信视角。
- **评测显著性**:多数 p 值来自未提交的一次性脚本;FanToM 与全量 ToMBench-5720 为裸 LLM 画像,在环 ToMBench-5720 持平。

---

## 10 结论

Starling Memory 把"智能体记忆"从无主体的向量检索,重构为**带归属、可嵌套、有生命周期的多主体心智表征**,并以一套落到公式与状态机的类脑动力学让记忆随时间活着。三项贡献彼此支撑:归属优先的 `Statement` 本体使高阶信念可被稳定表达与查询;CLS 六态动力学使记忆能巩固、遗忘、被回忆即修订、并无需提问即唤醒;而在高阶信念推理上,确定性嵌套追踪算子在最深阶为模型带来稳健增益(Qwen3-14B 整体 +4.2pp、order-3 +10.8pp;deepseek order-3/4 +15~17pp)。

同样重要的是我们对边界的诚实:这种确定性结构只在它比强模型自由推理更准的窄区间产生净增益,并以一个永不有害的语义路由门控守住下界。我们相信,这种"把社会认知做成可审计的数据结构与动力学,而非 prompt 补丁"的路线,为长期人机协作的记忆系统提供了一个清晰且可证伪的方向。

---

## 参考文献(选)

- McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). *Why there are complementary learning systems in the hippocampus and neocortex.* Psychological Review.
- Tulving, E. (1985). *Memory and consciousness.* Canadian Psychology.
- Yassa, M. A., & Stark, C. E. L. (2011). *Pattern separation in the hippocampus.* Trends in Neurosciences.
- Nader, K., Schafe, G. E., & LeDoux, J. E. (2000). *Fear memories require protein synthesis in the amygdala for reconsolidation after retrieval.* Nature.
- Conway, M. A., & Pleydell-Pearce, C. W. (2000). *The construction of autobiographical memories in the self-memory system.* Psychological Review.
- Mattar, M. G., & Daw, N. D. (2018). *Prioritized memory access explains planning and hippocampal replay.* Nature Neuroscience.
- Schaul, T., Quan, J., Antonoglou, I., & Silver, D. (2015). *Prioritized Experience Replay.* arXiv:1511.05952.
- McGaugh, J. L. (2004). *The amygdala modulates the consolidation of memories of emotionally arousing experiences.* Annual Review of Neuroscience.
- Bower, G. H. (1981). *Mood and memory.* American Psychologist.
- Mehrabian, A., & Russell, J. A. (1974). *An Approach to Environmental Psychology* (PAD model).
- McDaniel, M. A., & Einstein, G. O. (2000). *Strategic and automatic processes in prospective memory retrieval: a multiprocess framework.*
- Goschke, T., & Kuhl, J. (1993). *Representation of intentions: persisting activation in memory* (intention-superiority).
- Fiske, A. P. (1992). *The four elementary forms of sociality: framework for a unified theory of social relations.* Psychological Review.
- Chen, Z., et al. (2024). *ToMBench: Benchmarking Theory of Mind in Large Language Models.* ACL.
- He, Y., et al. (2023). *HI-TOM: A Benchmark for Evaluating Higher-Order Theory of Mind Reasoning in LLMs.*
- Kim, H., et al. (2023). *FANToM: A Benchmark for Stress-testing Machine Theory of Mind in Interactions.* EMNLP.

> 报告中的内核机制可在仓库对应模块查证(如 `src/tom/`、`src/replay/`、`src/reconsolidation/`、`python/starling/schema/`),完整设计见 `docs/design/system_design.md` 与 `docs/design/subsystems_design/`,评测脚本见 `scripts/eval_*.py` 与 `scripts/starling_tomeval_server.py`。
