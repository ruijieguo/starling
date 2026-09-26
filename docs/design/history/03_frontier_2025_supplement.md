<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# 2025-2026 前沿调研补充(主报告员手工汇总)

> 两个 web 调研 agent 因权限失败,本文由主报告员用 WebSearch 直接收集要点,作为 02_frontier_research.md 的增量补充。
> 引用以搜索结果为准,使用前应再核对 arxiv id 与页面。

## A. 类脑记忆 / Agent Memory 新工作

### A1. **Memory in the Age of AI Agents: A Survey**(2025-12,102 页)
- GitHub paper list:`Shichun-Liu/Agent-Memory-Paper-List`
- 提出三分:**token-level / parametric / latent memory**(对应 mempalace 风格 verbatim、Larimar 风格外置矩阵、KV/激活复用三类)
- 强调研究前沿:**memory automation、RL 整合、multimodal、multi-agent、trustworthiness**
- **设计启示**:三分类法可作为新系统"存储层"的顶层划分 —— Polis 既有的 Hippocampus/Neocortex 应在每一层内显式标记是 token-level / parametric / latent 中的哪一种。

### A2. **A-Mem: Agentic Memory(NeurIPS 2025 poster)**
- Zettelkasten 路线;新条目写入触发既有条目的"演化更新"。
- **设计启示**:写入即"链接构建"。新系统必须把"信念/陈述"也设计成可演化、可触发邻居更新的活节点,而非死记录。

### A3. **Reflective Memory Management(RMM, ACL 2025)**
- 提出 **prospective reflection**:在 utterance / turn / session 三层动态摘要,作为面向未来检索的记忆库;并用 RL 做 retrospective refinement。
- **设计启示**:这是迄今学术界最接近"前瞻记忆"的工作之一(命名上),但其本质仍是"预先组织信息便于将来检索",**不是承诺/触发条件式的真前瞻**。新系统应把"`when X happens, do Y`"作为 first-class data,与 RMM 的"未来友好摘要"叠加使用。

### A4. **ReMemR: Revisitable Memory(arxiv 2509.23040, 2024)**
- 把检索嵌入"更新"循环,允许 agent 主动 callback 历史记忆做非线性推理;多级奖励信号。
- **设计启示**:Polis 的"反思循环"应允许检索→改写→再检索的多轮闭环,���不是"巩固一次完事"。

### A5. **Graphiti / Zep(arxiv 2501.13956, 2025)**
- 时间知识图引擎:实时增量、episode 中心、追踪事实有效期。
- 报告称多会话推理较 MemGPT +18%,延迟低 90%。
- **设计启示**:Graphiti 是**与 Polis 设计哲学最接近的工业产品**(temporal-first + entity-first)。但 Graphiti 仍是"全局事实图",**没有"信念归属"维度** —— Polis 在这一点上仍是空白补位。

---

## B. ToM / 社会认知新工作

### B1. **MMToM-QA**(多模态 ToM QA)
- 把 ToM 任务带入视频/图像 + 文本场景,验证 LLM 对"agent 看到了什么、知道了���么"的多模态推理。

### B2. **MOMENTS(EMNLP 2025)**
- 多模态视频 QA,**7 项 ToM 能力**:Intentions / Desires / Beliefs / Knowledge / Percepts / Non-literal Communication / Emotions。
- **设计启示**:这 7 项与新系统的 BDI 本体直接对应;**Percepts(感知)**是 8 个开源仓库都没有的维度 —— 应作为新系统的"信息可见性"字段。

### B3. **SoMi-ToM(NeurIPS 2025)**
- 多视角具身 ToM,1225 道题,带第一人称/第三人称双视角。
- **设计启示**:验证了"per-perspective 检索"的研究价值,Polis 的 ToM Engine 可以直接对接其评测。

### B4. **EnigmaToM(ACL 2025 Findings)**
- 神经-符号方法:Neural Knowledge Base + iterative masking 做"perspective-taking"。
- 显式支持二阶 false belief。
- **设计启示**:**iterative masking** 是 SimToM 的工程���级版 —— 检索时按目标主体的"知识边界"动态遮蔽信息。Polis 的检索规划器应原生支持"perspective filter"。

### B5. **PDDL-Mind**
- 用 PDDL 做 belief state 形式化,LLM 做翻译;在 MMToM-QA / MuMa-ToM / FANToM 上 +5%。
- **设计启示**:**形式化 belief state** 在受限领域可行;Polis 的 Statement schema 是"轻量形式化",PDDL-Mind 验证了这条路径的工程价值。

### B6. **"Think Twice" perspective-taking**(2024-2025)
- 显式 perspective-taking prompting 提升 false-belief 任务准确率。
- **设计启示**:作为生成端默认的 ToM prompting 模板。

### B7. **多 agent ToM 综述**(2025-07,nlper.com)
- 系统综述递归心智状态推理与嵌套信念。
- 2024 后单 agent ToM 有 Hypothetical Minds 之外更多的工作,可作为 Polis ToM Engine 的对标。

---

## C. 工业落地

### C1. ChatGPT Memory(2024 GA → 2025 升级)
- 2025 年扩展为 **persistent memory + reference past chats**,不局限于"saved memory bullets"。
- 体系包含:结构化用户记忆 + 跨会话持续性 + 时间感知。
- 公开细节稀少,主流推断:**LLM 周期性总结对话 → 写入用户级 store → 按相关性注入新会话 system prompt**;每用户 memory bullets 有上限。
- **未公开的关键细节**:冲突更新策略、置信度模型、跨账户/跨设备同步细节。

### C2. Anthropic Claude Memory(2025)
- Claude 在 2025 推出原生 memory feature(详见 anthropic.com/news);与 Projects 互补。
- 公开机制:用户可见可编辑;按 project 隔离。
- 待核实:是否有自动总结循环。

### C3. LangChain LangMem + LangGraph 1.0(2025)
- `BaseStore` 多 namespace;`create_manage_memory_tool` / `create_search_memory_tool` 把记忆操作做成"tool"。
- LangGraph 1.0 把 memory 嵌进决策"hot path"。
- MongoDB Store 作为长期持久层。
- **设计启示**:把"记忆操作"暴露为 LLM 可调用 tool 是产品级共识;Polis 应原生提供 `recall / remember / forget / improve / perspective_take` 等 tool。

### C4. Graphiti / Zep
- 见 A5。这是**工业上"时间知识图 + entity-first"**的代表。

---

## D. 中文学术圈
- 本轮搜索未充分覆盖。已知较强的:清华(MemoryBank、PerLTQA)、复旦(persona)、IAAR-上海(MemOS)、北邮(`Memory in the Age of AI Agents` 综述合著之一,据 2025-03 Medium 报道)。
- 待补充。

---

## E. 关键空白与新系统机会

调研后,**新系统真正能"立起来"的命题**仍是以下三个,与 02_frontier_research 评估一致并被 2025 工作进一步确认:

1. **多主体认知 actor + 信念归属**:Graphiti / Zep 做了 entity 与时间,但**没有"holder of belief"维度**;EnigmaToM / SoMi-ToM 在评测层面承认了 perspective 的重要,但**评测 ≠ 数据模型**。Polis 是把"二阶 ToM"提升为"一等数据模型 + 一等检索维度"的最早工程提案。

2. **真前瞻记忆(承诺 + 触发条件)**:RMM 的 prospective reflection 仍是"为未来友好的摘要",**不是 if-then commitment 数据**。**整个开源 + 商业领域,无人把"承诺/约定/触发"作为带触发器的运行时一等公民**。这是新系统最易拿下的商业差异点。

3. **CLS 风格的"快慢双系统 + 优先级重放"**:HippoRAG / Graphiti / Letta sleeptime 各自踩到一角,但**优先级重放(高情绪/高新颖/高奖励)**与 **Affect 显著性调制**只在 mempalace 的 AAAK 中以字段形式存在,无运行时算法。

→ 设计文档将围绕这三件事展开。

---

## 引用

- Memory in the Age of AI Agents (2025-12 survey) — `github.com/Shichun-Liu/Agent-Memory-Paper-List`
- A-Mem — NeurIPS 2025 Poster page
- RMM — ACL 2025 Long Paper, aclanthology
- ReMemR — arxiv 2509.23040
- Graphiti — arxiv 2501.13956
- MMToM-QA — researchgate 384216501
- MOMENTS — aclanthology 2025.findings-emnlp.1230
- SoMi-ToM — NeurIPS 2025 Poster 121816
- EnigmaToM — aclanthology 2025.findings-acl.699
- PDDL-Mind — arxiv 2604.17819(疑误,实际编号待核)
- "Think Twice" — researchgate 384208511
- ChatGPT Memory — community.openai.com 多个帖子
- LangMem — langchain-ai.github.io/langmem


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
