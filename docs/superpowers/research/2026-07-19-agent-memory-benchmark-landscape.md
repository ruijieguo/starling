> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# 智能体记忆系统评测基准全景调研报告

> 调研日期:2026-07-19 | 方法:4路并行网络调研(学术基准 / 业界框架评测 / 长上下文与通用智能体基准 / 评测方法论与2026最新动态),交叉核实

---

## 0. 一句话结论

**这个领域目前没有一张可信的"排行榜"。** 几乎每一份公开的头部分数——无论是Mem0、Zep、Letta 还是新兴的 EverMemOS、MemPalace——都在被同行、独立审计者或竞争对手指出方法论问题(标注错误、judge 偏松/偏严、评测集被暗改、写入成本未披露、嵌入模型一换结论就翻转)。**"长上下文能力"和"跨会话记忆能力"是两件不同的事**,但大量所谓"记忆基准"其实测的是前者。2026 年上半年,领域的注意力正从"回答对不对"转向更难的问题:记忆能不能正确处理**矛盾/更新**、能不能**正确遗忘**、会不会被**已过时的记忆诱导谄媚**、以及规模扩大到百万甚至千万 token 时是否还有效。

---

## 1. 核心分析框架:长上下文 ≠ 记忆

调研中反复出现、且已成为 2026 年领域共识的一条分界线:

> **"长上下文"解决的是容量(capacity)问题;"记忆"解决的是跨会话的连续性(continuity)问题。**

- **长上下文基准**(RULER、BABILong、∞Bench、LongBench、NIAH 系列):给模型一个固定的超大输入,一次前向传播内检索/推理/压缩。没有"写入"这一步,调用结束后什么都不持久化。
- **记忆系统基准**(LoCoMo、LongMemEval、BEAM……):要求系统在跨时间的多轮交互中**主动写入**存储,再在之后的轮次**读取**该存储作答。系统在第 50 轮的状态取决于它在第 1~49 轮做了什么。

一个在 NIAH/RULER 上接近满分的模型,完全可能有一个很差的记忆系统——因为它从未被要求真正创建、管理、演化任何记忆。反过来,**MemoryArena**(Stanford, ICML 2026)发现:在 LoCoMo 这类"长上下文式"记忆基准上接近饱和的智能体,放到真正跨会话互相依赖的 agentic 环境中表现很差。这是本次调研中对"两者不是一回事"最直接的实证。

PASB 论文(2026-07)给出了区分"真跨会话记忆基准"最精确的判据:必须经过**"持久化阶段 → 清空上下文 → 查询阶段"**的分离设计,否则测的都还是单次会合内的状态维护,不是记忆。

---

## 2. 学术记忆基准全景

### 2.1 三件"标准套装"

| 基准 | 发表 | 规模 | 任务类型 | 核心发现 |
|---|---|---|---|---|
| **LoCoMo** | Maharana et al., ACL 2024([arXiv:2402.17753](https://arxiv.org/abs/2402.17753)) | 10 组对话,每组最多 35 session,约 9K-16.6K tokens,约 1,540-1,986 道 QA | single-hop/multi-hop/temporal/open-domain/adversarial QA + 事件摘要 | LLM 在跨会话时序/因果理解上普遍吃力;RAG/长上下文有帮助但仍远逊人类 |
| **LongMemEval** | Wu et al., ICLR 2025([arXiv:2410.10813](https://arxiv.org/abs/2410.10813)) | 500 道问题,S 档~115K tokens/40 session,M 档~500 session/1.5M tokens | 信息抽取、多会话推理、时序推理、知识更新、拒答(abstention) | 商用聊天助手/长上下文 LLM 相对"直接读全部历史"基线平均下降约 30% 准确率 |
| **BEAM**("Beyond a Million Tokens") | Tavakoli et al., ICLR 2026([arXiv:2510.27246](https://arxiv.org/pdf/2510.27246)) | 100 组对话,100K/500K/1M/10M 四档,2,000 道验证过的探针题 | 10 类能力,新增矛盾消解、事件排序、指令遵循 | 专为打破"扩大上下文窗口就能解决"的幻觉设计;所有系统在 10M 档矛盾消解维度都表现挣扎 |

### 2.2 早期/经典基准

- **MSC**(Multi-Session Chat,Xu et al., Meta FAIR, ACL 2022,[arXiv:2107.07567](https://arxiv.org/abs/2107.07567)):人人众包对话,5 个时间分隔 session,persona 固定不变(不反映真实场景中个人信息的动态演变)。其 500-对话子集后来被 MemGPT 团队用来构造 **DMR(Deep Memory Retrieval)** 任务,成为独立的常用小基准——但该任务每个对话仅 60 条消息,轻易能塞进现代模型上下文窗口,已被 Zep 自己指出"不再是记忆系统质量的强判别指标"。
- **PerLTQA**(Du et al., ACL 2024 SIGHAN workshop,[arXiv:2402.16288](https://arxiv.org/abs/2402.16288)):受"语义记忆 vs. 情景记忆"认知心理学区分启发,30 个虚构角色,8,593 条 QA,拆分 Memory Classification/Retrieval/Fusion 三子任务。局限:问题多为 1-2 跳,无显式推理链。
- **MemoryBank**(Zhong et al., AAAI 2024,预印本 2023,[arXiv:2305.10250](https://arxiv.org/abs/2305.10250)):严格说是一套**方法**而非标准化数据集——借鉴艾宾浩斯遗忘曲线做选择性强化/淡化记忆,常作为后续基准中的 baseline 出现。
- **MemGPT / DMR**(Packer et al., 2023,[论文](https://shishirpatil.github.io/publications/memgpt-2023.pdf)):OS 分页隐喻(recall store + archival store),GPT-4 在 DMR 上从 32.1% 提到 92.5%。后续演化为生产级框架 **Letta**。
- **"RECALL"名称歧义**:并不存在一个专门叫"RECALL"的长期对话记忆基准。检索到两条不相关线索——(a) Liu et al. 2023 的反事实知识鲁棒性基准([arXiv:2311.08147](https://arxiv.org/abs/2311.08147)),与长期记忆无关;(b) 2026 年新基准 **Memora**("From Recall to Forgetting",[arXiv:2604.20006](https://arxiv.org/html/2604.20006v1))提出 **FAMA**(Forgetting-Aware Memory Accuracy)指标,专门惩罚依赖已失效记忆的行为。

### 2.3 已知的标注质量问题(重要,2026 年才被系统性坐实)

- **LoCoMo 审计**(Penfield Labs, 2026):对全部 1,540 题系统审计,发现 **6.4%(99 题)标注错误**——包括标准答案里的幻觉事实(如凭标注者内部检索加进去、对话原文根本没有的车型名)、时间推理错误("上周六"算错成周日)、24 处说话人归属错误。完美系统在此答案键下理论最高分只有约 93.6%。更关键的是**对抗测试**:为全部 1,540 题生成"故意错误但话题相邻"的答案,用论文同款 judge(gpt-4o-mini)打分,**接受率高达 62.81%**——具体事实错误能被抓出约 89%,但"找对了话题、漏了全部细节"的模糊答案有近三分之二蒙混过关,这恰好奖励了弱检索系统的典型失败模式。
- **LongMemEval**:官方维护者已在 2025 年 9 月发布过"清理历史会话以防止干扰答案判定"的更新,原始 v1 已标记 deprecated,替换为 `longmemeval-cleaned`。另有 MemTrace 论文指出该基准的 judge **反而过度严格**(惩罚本质正确但冗长的回答),与 LoCoMo 的 judge 偏松形成对照——说明 judge 偏差方向不是单一方向的系统性问题,需要具体审计。
- **GitHub 独立佐证**:`snap-research/locomo` 仓库 Issue #27 记录了具体标注错误案例(标准答案里出现的关键词在原文对话中根本不存在)。

---

## 3. 长上下文基准 vs. 通用智能体基准中的"记忆"任务

### 3.1 纯长上下文基准(单次前向,无跨会话写入)

| 基准 | 核心设定 | 关键发现 |
|---|---|---|
| **RULER**(NVIDIA, [arXiv:2404.06654](https://arxiv.org/abs/2404.06654)) | 4 类 13 个任务:多针检索/多跳追踪/聚合/QA | 几乎所有声称支持 128K/1M 的模型,在原版 NIAH 上接近满分,但在多跳追踪/聚合任务上随长度大幅掉分——真实有效上下文远小于宣称值 |
| **BABILong**(NeurIPS 2024) | bAbI 事实链嵌入 PG19 超长文本,预定义分箱 0K-10M | RAG 对推理任务**没有正面帮助**;记忆增强架构(如 ARMT)在极端长度下明显优于标准/检索增强 Transformer |
| **∞Bench/InfiniteBench**(ACL 2024) | 平均超 100K tokens,12 任务 | 首个平均长度超 100K 的基准,任务刻意设计成"简单检索片段不足以解题" |
| **LongBench v1/v2**(ACL 2024/2025) | v1: 21 任务/4,750 样本;v2: 503 道多选题,8K-2M words | v2 中人类专家 15 分钟限时仅 53.7% 准确率,最佳直接作答模型 50.1%——v2 的"长对话历史理解"任务已逼近记忆基准边缘,但机制上仍是单次前向 |
| **NIAH 及变体**(NoLiMa/MRCR) | 原始范式已"饱和"(多数模型 >98%);**NoLiMa**(ICML 2025)去字面匹配后 GPT-4o 从 99.3% 掉到 69.7% | 8-needle @ 1M 是当前最难档,Claude Opus 4.6 领先(76%),GPT-5.4(36.6%)/Gemini 3 Pro(24.5%)明显落后——凸显"1M 上下文"是容量声明而非质量声明 |

### 3.2 通用智能体基准(测规划/工具使用,记忆是隐含挑战而非专门维度)

- **AgentBench**(ICLR 2024)、**GAIA/GAIA2**(Meta, ICLR 2024/2026)、**TravelPlanner**(ICML 2024)、**WebArena** 系(含 2026 年新出的 Odysseys、WorkArena)、**τ-bench/τ²-bench**(Sierra, 客服场景多轮状态一致性)、**AppWorld**(ACL 2024 Best Resource Paper)——这些都属于**单会话内**的长时程任务执行压力测试,失败模式常涉及"状态漂移""忘记已做的事",但**不跨越"关闭会话重开"这条边界**,严格意义上不是记忆基准。
- **OSWorld 2.0**(2026,[arXiv:2606.29537](https://arxiv.org/abs/2606.29537))是这批基准里最接近"记忆是核心挑战"的一个:108 个长时程计算机使用工作流(人类中位数 1.6 小时),即使 Claude Opus 4.8 最大配置严格二元完成率也仅 20.6%,失败主因是"无法在长时程内维持任务级模型"——丢失约束、错过中途到达的信息、几乎不花时间自我纠错。但仍是单会话内评测。

### 3.3 2025-2026 新出现的"真跨会话"agentic 记忆基准

这批基准是对"agentic 基准普遍不测跨会话记忆"这一缺口的直接回应:

- **Momento**([arXiv:2606.00832](https://arxiv.org/abs/2606.00832)):智能体主要因**误判用户状态**失败——把上一会话历史当作当前可靠代理,而非需要重新验证的"陈旧信息"。
- **MemoryArena**(Stanford, ICML 2026):跨会话因果依赖,已实证"LoCoMo 饱和 ≠ agentic 记忆能力强"。
- **AMA-Bench**(UCSD, ICML 2026):专注智能体-环境交互轨迹(而非人机对话),GPT-5.2 准确率仅 72.26%;许多记忆系统表现不如简单长上下文基线,根因是有损压缩+相似度检索误差在长时程累积复合。
- **LongMemEval-V2**(UCLA, 2026,[arXiv:2605.12493](https://arxiv.org/abs/2605.12493)):不是 v1 勘误版,而是全新的"专用环境经验记忆"评测,451 题,历史轨迹最多 1.15 亿 tokens(来自 WebArena/WorkArena),最佳方法 AgentRunbook-C 72.5% vs 最强 RAG 基线 48.5%。
- **PASB**(Personal Agent Sycophancy Benchmark,2026-07,[arXiv:2607.10526](https://arxiv.org/abs/2607.10526)):**测的是"写入"本身**——真实智能体栈决定存什么,而非给定预写记忆;发现"持久性谄媚"会通过状态写入被放大固化。
- **DynamicMem**([arXiv:2606.22877](https://arxiv.org/abs/2606.22877)):单用户 15 个月轨迹,超 200 万 tokens,1,837 个演化中的属性/偏好项——刻意不靠拼接不同数据集凑长度。
- **MemoryAgentBench**(ICLR 2026,[arXiv:2507.05257](https://arxiv.org/abs/2507.05257)):基于认知科学定义 4 大能力(精确检索/测试时学习/长程理解/选择性遗忘),22 个系统 × 5 个骨干模型的迄今最全面对比。**没有系统四项全面达标**;所有方法在多跳 FactConsolidation 上最高仅 7% 准确率,而强推理模型在同等规模输入上能到 80%——说明难点不在推理,在记忆机制本身。

---

## 4. 业界厂商评测与"排行榜战争"

这是本次调研中信息密度最高、也最有决策参考价值的部分。

### 4.1 Mem0 vs. Zep:LoCoMo 分数互控事件(2025-2026,目前记录最完整的案例)

1. Mem0 论文(2025-04)报告自身 LoCoMo 约 68%,报告 Zep 分数为 **65.99% ± 0.16**。
2. Zep 反击博客《Lies, Damn Lies, & Statistics: Is Mem0 Really SOTA?》,声称正确评测下应得 **84%**,并指控 Mem0 三处实现错误(用户角色混淆、时间戳处理不当、串行而非并行检索导致延迟虚高)。
3. Mem0 CTO 反诉(GitHub issue),指控 Zep **把被排除的对抗类答案计入分子却未计入分母**,机械性抬高约 25 个百分点;10 个随机种子重跑后得 **58.44% ± 0.20**。
4. Zep 最终让步,修正为 **75.14% ± 0.17**。
5. 该 issue 已关闭,但**未见 Zep 对 Mem0 具体技术指控的公开正面回应**,双方各执一词。

独立评论(essays.bloo-mind.ai《The Benchmark Theatre》,2026-05)总结:"同一年份、同一基准,仅因'谁跑的测试'不同,分数就能相差 54 个百分点"。

### 4.2 另外两起独立坐实的"刷分"事件

- **MemPalace**(2026-04 爆火项目):宣称 LoCoMo 100%、LongMemEval "史上首个完美分数"。经审计发现 LongMemEval 的 100% 是"对着做错的题目定向打补丁"(针对特定失败案例加规则,再在同一批题目上重新打分,即"teaching to the test");LoCoMo 的 100% 源于 top_k=50 设置超过每段对话本身的 session 总数(19-32),等于把全部对话塞进上下文,记忆系统实际上什么贡献都没做。**项目在 48 小时内主动撤回**上述夸大声明,诚实分数修正为 LoCoMo(无 rerank)R@10 约 60.3%、LongMemEval 真实分数 96.6%。
- **EverMemOS**(2025-12 新闻稿宣称 LoCoMo 92.32%):一位用户完整跑通开源代码/Docker 栈后只得到 **38.38%**;独立审计还指出,GPT-4.1-mini 搭配特定 answer prompt 在**全上下文(无任何记忆系统)**下就能拿到 92.62%,**超过** EverMemOS 本身报告的 92.32%——说明分数很大程度由"回答 prompt"而非"记忆系统"驱动。

### 4.3 Letta 的自我颠覆式发现

Letta(MemGPT 团队)发布《Is a Filesystem All You Need?》:用最朴素的"普通文件系统 + grep"(无专用记忆机制)搭配 GPT-4o-mini,在 LoCoMo 上取得 **74.0%**,**超过 Mem0 报告的最佳图变体(68.5%)约 5.5 分**。Letta 自己的结论是:"当前的记忆基准可能并不很有意义",记忆能力更多取决于 agent 如何管理上下文,而非具体检索机制——这是本领域最具讽刺性也最值得重视的发现之一。Letta 随后把 Leaderboard 从纯检索基准转向整体任务式评测(如 Terminal-Bench),旧版 Leaderboard 仓库已归档。

### 4.4 各厂商/项目现状速览

| 项目 | 评测基准 | 关键信息 |
|---|---|---|
| **Mem0** | 自建 harness + LoCoMo/LongMemEval/BEAM | 2026-04 新算法称 LoCoMo 92.5、LongMemEval 94.4;但独立复测(memnode.dev)仅 66.9%,另有学术论文测得 F1 仅 34.20(远低于自报);Mem0 自己在文档里承认"小基准可被激进策略硬刷,不代表真正可规模化的记忆系统" |
| **Zep/Graphiti** | DMR + LongMemEval + LoCoMo | 时序知识图谱架构;LongMemEval 官方 90.2% vs 独立复测 71.2%;开放域问答仍是其公认弱项(79.2%) |
| **Letta** | 自建 Leaderboard → Context-Bench(2026-03) | 已从纯记忆检索转向整体任务式评测;Filesystem 套件 GPT-5.2-codex 93% 领先 |
| **LangChain/LangMem** | 无官方基准,依赖第三方 | 第三方测得 LoCoMo 58.10%,p95 延迟高达 59.82 秒/次,更适合非交互式批处理场景 |
| **LlamaIndex** | 无 | 本次调研中唯一完全没有对外发布可验证评测数据的主流项目 |
| **Cognee** | 早期 LoCoMo → 2026 转向 BEAM | 主动放弃展示自身 LoCoMo 头条分数,可视为对该基准局限性的行业默认认可信号 |
| **OpenAI ChatGPT Memory** | 官方内部三代对比("Dreaming V3", 2026-06) | 时序敏感准确率从 9.4% 提升到 75.1%;但数字全部来自 OpenAI 自己,未经独立审计;另有同行评审研究发现 96% 的记忆是系统单方面创建,非用户明确指示 |
| **Anthropic Claude Memory** | 无公开量化基准 | 内部宣称"针对长期运行 agent 做过基准优化"但未公开具体数字;第三方评测(Mem0 对 Opus 4.7)发现即便任务全在 4K tokens 内,5 步链条内即无法保持约束一致性 |
| **Google Gemini Personal Context** | 无学术基准评测 | 第三方综合对比将其定位为"最佳上下文窗口"而非"最佳持久记忆",与本调研反复出现的"长上下文≠记忆"共识一致 |

---

## 5. 评测方法论的八个核心维度

### 5.1 检索准确性指标本身的局限

Recall@k/Precision@k 是二元相关性假设、不考虑排序位置,已被 2026 年新论文《ANN Search: Recall What Matters》正面挑战——提出 Semantic Recall(语义相关性由 judge 判定)与 Tolerant Recall(距离容忍)两种替代,但作者承认两者都无法同时做到"无需 judge"和"无需超参数"。另有研究发现:在传统 Recall 指标上获胜的检索算法,往往不是任务层面表现最好的算法。

### 5.2 多跳推理(multi-hop across sessions)

几乎所有主流基准都覆盖,始终是各系统最薄弱环节之一。AMA-Bench 发现许多记忆系统的多跳表现反而不如简单长上下文基线,因为有损压缩+相似度检索误差会在长时程任务中累积复合。

### 5.3 时序推理

标注错误高发区(如上文 LoCoMo 审计中的日期计算错误)。BEAM 新增 Event Ordering 维度专门测这个。

### 5.4 矛盾/更新处理(belief revision)——2026 年爆发式增长的子领域

这是本次调研发现的**最活跃的新兴方向**,细分出多个专门基准:

- **BeliefShift**:2,400 条人工标注跨会话交互轨迹,提出 BRA/DCS/CRR/ESI 四个新指标区分"理性修正"与"无证据支撑的偏见漂移"。**七个模型家族中,高达 42% 的跨会话矛盾未被解决**。
- **STALE**(2026-05,[arXiv:2605.06527](https://arxiv.org/abs/2605.06527)):专测**隐式冲突**(后续观察在无显式否定的情况下使早期记忆失效,需常识推理才能检测)。400 个专家验证场景,三个探测维度(状态判过时/拒绝虚假预设/下游行为更新)。**即便最好的模型总体准确率也只有 55.2%**;三条结论——识别过时不代表会应用更新、极易被预设过时信息的查询误导、需要级联失效的传播型冲突尤其难处理。后续 StateAuditor(2026-08)针对"更新了但行为未跟进"的 gap 提出反向验证方法,取得 +5.0 分改善。
- **MemConflict**(中国人民大学,[arXiv:2605.20926](https://arxiv.org/pdf/2605.20926)):区分动态/静态/条件三类冲突,发现"答案正确性"与"检索/排序质量"经常脱节。
- **Nous**(belief-based memory,[arXiv:2606.22030](https://arxiv.org/abs/2606.22030)):受控消融发现贝叶斯信念更新相对"last-write-wins"策略几乎无额外收益——**因为现有对话记忆基准很少包含真正的矛盾**,这本身是对基准构造真实性的批评。
- **MemSyco-Bench**(2026-07,[arXiv:2607.01071](https://arxiv.org/abs/2607.01071)):评测"记忆诱导的谄媚"——检索到的历史记忆是否不当压过客观证据,使智能体顺从用户过去的信念而非当前任务的客观要求。方法论转变:从"检索是否成功"转向"检索后记忆如何被使用"。

### 5.5 遗忘曲线/长期保留

- **Memora**提出的 FAMA 指标专门惩罚"依赖已失效记忆"的行为,揭示标准准确率指标看不到的性能差距(模型可能"记住了"某事实,但那个事实已经过时)。
- **MemGym**([arXiv:2605.20833](https://arxiv.org/html/2605.20833)):四层干扰项分级 + 10K-1M token 可组合规模。
- **TraceRetain**([arXiv:2606.29178](https://arxiv.org/html/2606.29178v1)):关键发现——有边界的记忆保留策略在"干净"饱和基准上不比缓存启发式方法更好,**只有在流数据含噪声时才显现优势**(受控 75% 合成干扰项压力测试下,无边界记忆 precision@5 从 20.2% 骤降到 12.4%)。

### 5.6 拒答/abstention 能力

- **AbstentionBench**([arXiv:2506.09038](https://arxiv.org/html/2506.09038v1)):最反直觉发现——面对不可回答问题时,**推理模型的弃权表现系统性地差于其底层指令微调基线**。根源在训练激励:大多数基准把"正确回答"记 1 分、"弃权"记 0 分(与"错误回答"同分),预期得分永远是猜测更高,幻觉是某种意义上"理性的应试行为"。
- **Synthius-Mem**提出尖锐论断:**没有对抗性类别的记忆基准会产生误导性排名**——幻觉出合理措辞答案的系统可能比正确拒答的系统看起来表现更好,仅因错误答案恰好与标准答案共享一些 token。

### 5.7 效率维度(延迟/token/存储成本)

- Mem0 五维评测框架(准确率、召回/精确率、延迟、token/计算成本、时序/多跳)提出复合指标 **MemScore**。
- **写入路径(ingestion)延迟才是真正瓶颈**:RealMem 基准显示,记忆写入延迟在所有系统上都持续超过检索速度。
- **MemDelta**(2026,[arXiv:2606.29914](https://arxiv.org/pdf/2606.29914),**本次调研中方法论冲击力最大的论文**)发现:Mem0 需要 1,000+ 次 LLM 调用、约 120 分钟/实例、$0.50+ 成本,但在匹配的 88 个实例上准确率(72.7%)并未显著优于成本极低的云端 RAG(73.9%,p=1.0)——高昂的写入成本未必换来相应的准确率收益。

### 5.8 LLM-as-judge 本身的偏差与可靠性

- 系统综述(2020-2026 共 27 篇研究)指出该范式已成 AI 评测主导实践,但可靠性、公平性尚未被充分审视。**仅调换回答呈现顺序就能使判决结果偏移 20-35%**。
- **Benchmark Illusion 论文**(Eddie Yang & Dashun Wang, 2026-02,[arXiv:2602.11898](https://arxiv.org/abs/2602.11898)):即便在 MMLU-Pro/GPQA 这类主流推理基准上,聚合准确率相当的 LLM 在具体题目层面判断可能高达 16-66% 不一致;更换标注/评判模型可使处理效应估计值改变超过 80%,部分情况下甚至反转符号。**这直接冲击了记忆评测领域普遍依赖单一 LLM judge 打分的做法**。
- 记忆评测领域的直接证据:LoCoMo 的 judge 偏松(接受 62.81% 故意错误答案),而 MemTrace 论文发现自己的 judge 反而偏严——说明偏差方向因具体实现而异,不能一概而论。

### 5.9 补充维度:操作级幻觉定位 + 记忆投毒安全

- **HaluMem**(MemTensor,[arXiv:2511.03506](https://arxiv.org/abs/2511.03506)):首个"操作级"记忆幻觉基准,把工作流拆成抽取/更新/QA 三阶段做细粒度溯源。**触目发现**:更新准确率在 Medium 设置下低于 26%,Long 设置下趋近于 0%;结论是幻觉是"普遍存在的上游问题",在抽取和更新阶段持续产生并累积。
- **OWASP 2026 Agentic AI Top 10** 新增 **ASI06:Memory and Context Poisoning**——攻击载荷只需一次成功写入即可,攻击与效果在时间上解耦(今天写入,几个月后才触发错误行为)。已知攻击成功率数据:MINJA 达 98.2% 注入成功率;PoisonedRAG 仅注入 5 条文本即可达 91-99% 攻击成功率。

---

## 6. 2026 年最新动态精选

### 6.1 规模/生产可行性导向的新基准

- **STATE-Bench**(微软,2026-05,[GitHub](https://github.com/microsoft/STATE-Bench)):彻底跳出"简单回忆",转向真实企业**有状态任务执行**——450 个任务,工具调用真实修改数据库(退款、订票),用 pass^5(5 次运行全部成功才算通过)。GPT-5.1 无记忆情况下可靠完成不到一半任务,旅行领域 pass^5 仅约 30%。
- **BEAM** 见 §2.1。

### 6.2 会议/Workshop 动态

- **ICLR 2026 Workshop on Memory for LLM-Based Agentic Systems(MemAgents)**:明确定位为"记忆层专属论坛"。
- **PALM Workshop @ NeurIPS 2026**(投稿截止 2026-08-24):议题清单——超越短上下文回忆的评估方式、时间推理、记忆更新与删除测试、矛盾处理、不确定性下的弃权、真实世界记忆能力评估,与本报告 §5 梳理的维度高度重合,可视为学术界共识的旁证。
- 另有 NeurIPS 2026 TTCL(Test-Time Continual Learning)、COLM 2026 Lifelong Agents、NORA 2026 等 workshop。

### 6.3 综述类文章

- **"Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers"**(2026-03,[arXiv:2603.07670](https://arxiv.org/pdf/2603.07670)):把记忆形式化为 write-manage-read 循环,提出三维分类法(时间跨度/表征基质/控制策略)。
- **"Anatomy of Agentic Memory"**(2026-02,[arXiv:2602.19320](https://arxiv.org/abs/2602.19320)):核心批评——benchmark saturation(基准饱和)、metric misalignment(F1 vs. 语义正确性错位)、judge 对 prompt 高度敏感、backbone 依赖、系统级成本常被忽视。核心论点:**"RAG 是一种检索策略,而非记忆系统——agent 记忆需要 admission、evolution、consolidation、forgetting、typed storage、context-aware retrieval,而 RAG 只解决了最后一项。"**
- **"Contextual Agentic Memory is a Memo, Not True Memory"**([arXiv:2604.27707](https://arxiv.org/pdf/2604.27707)):提出"Frozen Novice Problem"——纯靠上下文工程运行的智能体,生成模型权重跨会话保持不变,无论外部存储积累多少经验都不是"学习"而只是"查表"。提出 Compositional Generalization over Time(CGT)评测协议以区分二者。

---

## 7. 对建设记忆系统的实践启示

1. **不要相信任何单一厂商自报的 LoCoMo/LongMemEval 分数**,尤其没有标准差、没有独立复现、没有披露 embedding 模型/judge 模型/prompt 版本的数字。至少要看:是否报告了 ingestion 方法、judge 配置、多次运行的标准差。
2. **准确率单独看没有意义**,必须同时看写入延迟、token 成本——MemDelta 证明"高精度"可能来自 1,000+ 次 LLM 调用的暴力写入,不代表架构优越。
3. **矛盾处理/信念更新是当前最薄弱、也是评测最活跃的维度**(STALE 55.2%、BeliefShift 42% 未解决矛盾)。如果构建记忆系统涉及用户信息随时间演变(地址变更、偏好变化等),这是最值得投入专门评测的地方,而非通用 QA 准确率。
4. **警惕"记忆诱导谄媚"**(MemSyco-Bench、PASB):检索到的历史记忆可能不当地压过当前客观证据/任务要求,这是纯准确率指标测不出来的失效模式。
5. **规模曲线比单点分数更有信息量**:同一系统在 100K→10M token 规模下的分数衰减曲线(如 BEAM 报告的 Mem0 从 64.1→48.6),比任何单一规模下的绝对分数更能说明真实的生产可行性。
6. **Letta 的"文件系统+grep"胜过专用记忆工具**这一发现值得认真对待——在评测/选型记忆系统时,应把"什么都不做的简单基线"(全文件历史+grep/全上下文)作为强制对照组,而不只是与其他记忆产品比较。

---

## 8. 完整来源索引

来源分散于四份子调研,总计逾百篇 arXiv 论文与厂商博客。以下为高价值来源精选(按主题分组,完整清单见调研过程中各子代理输出):

**学术基准**:[LoCoMo](https://arxiv.org/abs/2402.17753) · [LongMemEval](https://arxiv.org/abs/2410.10813) · [LongMemEval-V2](https://arxiv.org/abs/2605.12493) · [MSC](https://arxiv.org/abs/2107.07567) · [PerLTQA](https://arxiv.org/abs/2402.16288) · [MemoryBank](https://arxiv.org/abs/2305.10250) · [BEAM](https://arxiv.org/pdf/2510.27246) · [MemoryAgentBench](https://arxiv.org/abs/2507.05257) · [MemoryArena](https://arxiv.org/pdf/2602.16313) · [PersonaMem](https://arxiv.org/abs/2504.14225) · [PrefEval](https://arxiv.org/html/2502.09597) · [REALTALK](https://arxiv.org/abs/2502.13270)

**长上下文/智能体基准**:[RULER](https://arxiv.org/abs/2404.06654) · [BABILong](https://proceedings.neurips.cc/paper_files/paper/2024/file/c0d62e70dbc659cc9bd44cbcf1cb652f-Paper-Datasets_and_Benchmarks_Track.pdf) · [LongBench v2](https://arxiv.org/abs/2412.15204) · [NoLiMa](https://arxiv.org/abs/2502.05167) · [GAIA2](https://arxiv.org/abs/2509.17158) · [OSWorld 2.0](https://arxiv.org/abs/2606.29537) · [τ²-bench](https://github.com/sierra-research/tau2-bench)

**矛盾/更新/谄媚专项**:[STALE](https://arxiv.org/html/2605.06527v1) · [BeliefShift](https://arxiv.org/html/2603.23848) · [MemConflict](https://arxiv.org/pdf/2605.20926) · [MemSyco-Bench](https://arxiv.org/abs/2607.01071) · [Nous](https://arxiv.org/abs/2606.22030)

**方法论批评**:[MemDelta](https://arxiv.org/pdf/2606.29914) · [Benchmark Illusion](https://arxiv.org/abs/2602.11898) · [Penfield Labs LoCoMo audit](https://penfieldlabs.substack.com/p/we-audited-locomo-64-of-the-answer) · [Anatomy of Agentic Memory](https://arxiv.org/abs/2602.19320) · [AbstentionBench](https://arxiv.org/html/2506.09038v1) · [HaluMem](https://arxiv.org/abs/2511.03506)

**厂商争议**:[Zep "Lies, Damn Lies, & Statistics"](https://blog.getzep.com/lies-damn-lies-statistics-is-mem0-really-sota-in-agent-memory/) · [Letta "Is a Filesystem All You Need?"](https://www.letta.com/blog/benchmarking-ai-agent-memory/) · [Mem0 research](https://mem0.ai/research) · [Zep research](https://www.getzep.com/research/)
