# Starling 在 LoCoMo / LongMemEval / BEAM 上的评测方案

**日期**:2026-07-19
**状态**:设计草案(待评审)
**配套调研**:`docs/superpowers/research/2026-07-19-agent-memory-benchmark-landscape.md`

---

## 0. 一句话摘要

在**一套可比、可审计、带统计显著性**的共享 harness 里,把 Starling 放到 LoCoMo / LongMemEval / BEAM 三个基准上评测。评测的目标**不是**去刷一个"Starling 92.x% SOTA"的头条数字——调研已坐实这类数字在本领域普遍不可信——而是回答两个 Starling 特有的问题:(1)归属优先 + 类脑动力学的认知中间件,在这三个通用记忆基准上**是否至少不劣于**纯检索基线;(2)Starling 的差异化能力(知识更新/矛盾、视角化弃答、时序、跨会话推理)在基准的**对应子集**上是否产生可测的净增益。方案沿用技术报告 §5 的科学纪律:诚实刻画有益区间与边界,不逆向工程基准生成器。

---

## 1. 定位:先想清楚"Starling 在这三个基准上应该被测出什么"

Starling 的技术报告(§2.2、§7)把自身明确定位为**认知中间件**,叠加在 mem0/Letta/Graphiti 这类向量记忆栈之上,补的是"归属维度、心智理论、类脑重放与前瞻"这一认知层。这个定位直接决定了评测重点:

- **LoCoMo/LongMemEval/BEAM 大部分题是"无主体事实检索"**(single-hop 事实回忆),这块能力主要由底层向量栈 + backbone 模型决定,Starling 的表征创新在这里**理论上不产生增益**——正如 Letta 的著名发现:纯文件系统 + grep 就能在 LoCoMo 上拿 74%,超过多数专用记忆工具。**在这些子集上,Starling 的目标是"不劣化",而非"领先"。**
- **Starling 的主战场是三个基准里的少数几类子集**:知识更新(knowledge-update)、时序推理(temporal)、多会话/多跳推理(multi-session/multi-hop)、拒答(abstention)。这几类恰好对应 Starling 的核心机制——不覆盖再巩固保全信念历史(§4.4)、感知接地的时序状态重建(§3.3b)、视角遮蔽与认识论诚实弃答(§3.5)。**净增益若存在,必然集中在这里**,与 §5.2"增益单调集中于最深推理阶"的形态一致。

> **方法论第一原则(承接技术报告 §5.3)**:确定性/结构化记忆带来净增益,当且仅当它在该子集上比 backbone 的自由推理 + 朴素检索更准。因此评测必须**按子集分层报告**,绝不只报一个聚合准确率——聚合数字会同时掩盖"主战场的增益"和"陪跑子集的中性",让结论不可解读。

---

## 2. 三基准选型、规格与子集映射

| 基准 | 规模 | 我们用的子集 | 映射到 Starling 的能力 | 期望 |
|---|---|---|---|---|
| **LongMemEval**(ICLR 2025) | 500 题,S 档 ~115K tok | 全 5 类(信息抽取/多会话推理/时序/知识更新/拒答) | 知识更新↔再巩固不覆盖;时序↔感知接地状态重建;拒答↔认识论诚实弃答 | **主基准**。knowledge-update / abstention / temporal 三类是净增益的最可能来源 |
| **LoCoMo**(ACL 2024) | 10 组对话,~1,540 题 | 非对抗四类(single/multi-hop/temporal/open-domain);Category 5 对抗类**排除**(无 gold,双方社区惯例) | multi-hop↔跨会话陈述图遍历;temporal↔状态重建 | **对照基准**。single-hop 只求不劣化;用其审计问题(见 §5)校准 judge |
| **BEAM**(ICLR 2026) | 100 组对话,128K–10M tok,2000 题 | 先跑 128K/500K/1M 三档;10M 档作为**规模压力**留后 | contradiction-resolution↔矛盾共存;knowledge-update↔再巩固;event-ordering/temporal↔时序 | **规模与压力基准**。验证 Starling 在"上下文塞不下"时检索架构是否成立;矛盾消解子集是差异化亮点的最佳舞台 |

**为什么必须三个都做,而不是只挑一个刷高分**:
- LoCoMo 已被独立审计证实**上下文塞得下(16–26K tok)+ 6.4% 标注错误 + judge 接受 62.81% 的错误答案**,单独用它得出的任何"SOTA"都不可信。它的价值在于**对照**(和全行业数字对齐)和**judge 校准**(它的对抗审计数据是现成的)。
- LongMemEval 的五类能力划分和 Starling 的机制**几乎一一对应**,是最能测出差异化的基准,定为主基准。注意用官方 2025-09 清洗版(`longmemeval-cleaned`),原始 v1 已 deprecated。
- BEAM 的 10M 档是唯一"物理上塞不进任何上下文窗口"的规模,能证伪"Starling 只是把东西塞进上下文"的质疑;其 contradiction-resolution 子集是全行业公认最难、也是 Starling 表征最有话说的地方。

**现状复用**:仓库已有 `tests/data/eval_longmemeval/sessions.jsonl`(9.6KB 小样本)+ `scripts/eval_longmemeval.py`(fixture/real 双模)。本方案的 LongMemEval 部分是**把这个 harness 从冒烟扩到全量 + 去 gate**,而非从零重写。LoCoMo/BEAM 需新建数据加载与题型适配,但可完全复用现有 harness 的 real-mode 管线骨架(SqliteAdapter + OpenAIEmbeddingAdapter + EmbeddingWorker + SemanticRetriever + chat-completion)。

---

## 3. 统一评测协议(可比性的地基)

调研中最一致的结论:**跨系统、跨论文的记忆基准数字不可直接比较**,因为 backbone、ingestion、embedding、answer-prompt、judge 全都在变,且几乎没人披露。Starling 的评测从第一天起就锁死这些变量,并**强制披露**。

### 3.1 固定并披露的七要素(每次运行随报告落盘)

沿用 Penfield Labs 审计建议的六条 + Starling 的 backbone 一条:

1. **Backbone 模型**:answerer 与 extractor **必须是同一模型**(沿用技术报告 §5.1 的"同模型在环"范式,度量的是记忆结构对该模型的边际贡献,而非换了个更强求解器)。默认 backbone 固定为一个中档模型(如 `deepseek-v4-flash` 或等价),另跑一个强模型(如 `deepseek-v4-pro`)看增益是否随 backbone 变强而收窄——这正是 §5.2 观察到的形态。
2. **Ingestion 方式**:**渐进式**逐 session 写入(经真实 Extractor → 陈述总线 → 巩固),**不是**一次性灌入。这对 Starling 尤其关键:再巩固、遗忘曲线、重放只在渐进摄入下才被触发,一次性灌入等于阉割掉 §4 的全部动力学。
3. **Embedding 模型 + 维度**:固定(如 DashScope `text-embedding-v3`, 1024 dim),记录在报告里。
4. **Answer-prompt**:模板固定并全文落盘(现有 harness 的 `_build_answer_prompt` 已是好起点);调研反复证明 answer-prompt 的细节能摆动准确率两位数,所以它必须是被冻结、被披露的常量。
5. **Judge 模型 + prompt**:固定,且**经 §5 的对抗验证**后才可用。
6. **运行次数 + 统计量**:每题至少 N=3 轮(现有 harness 默认 rounds=3),报告**中位数 + 分项的 95% 置信区间**(Wilson score,小样本子集尤其需要),不报单次点估计。
7. **corpus_hash**:复用 `eval_quality_baseline.py::corpus_hash`,同内容同 hash,保证"这次和上次跑的是同一批题"。

### 3.2 报告分层(强制)

每个基准的报告**必须**按子集/题型分层,每层给出:准确率(judge)、检索指标(Recall@k / NDCG@k,LongMemEval 原生支持)、以及 §7 的效率三元组(延迟、token、写入路径成本)。**禁止只报聚合准确率。**

---

## 4. Starling 接入设计:三模式对照 + 消融

沿用技术报告 §5.1 的三模式范式,把它从 HiToM 扩展到这三个记忆基准:

### 4.1 三种被测配置(每个基准都跑三条)

- **A. 纯检索基线(baseline)**:backbone + 朴素向量检索(SemanticRetriever top-k),**不经** Starling 的陈述本体/巩固/视角层。这是"没有 Starling"的对照,等价于一个 mem0-lite。
- **B. Starling 中间件(full)**:backbone + 完整 Starling(陈述抽取 → 总线 → 巩固/再巩固/遗忘/重放 → 视角化检索 + 心智摘要 + 认识论弃答)。这是主被测系统。
- **C. 纯机器算子(det-only,仅适用子集)**:对时序/状态类题,用 §3.3b 的确定性感知接地算子直接作答,隔离"记忆机制本身"vs"backbone 推理"。仅在算子有定义的题型上跑(时序、知识更新),其余题型 N/A。

**核心读数是 B − A 的分项差值**(净增益),不是 B 的绝对值。B > A 且集中在主战场子集 = 达到设计目标;B ≈ A 在 single-hop 上 = 符合预期(不劣化);B < A 任何地方 = 需要归因(抽取退化?视角遮蔽误剔证据?)。

### 4.2 消融(定位增益来源)

在配置 B 上做加法消融,每次只关一个机制,看哪个子集掉分,以此把增益**归因到具体机制**而非笼统归给"Starling":
- 关掉再巩固不覆盖(退化为 last-write-wins)→ 预期 knowledge-update / contradiction 掉分。
- 关掉感知接地时序重建 → 预期 temporal 掉分。
- 关掉认识论弃答(强制作答)→ 预期 abstention 掉分(且暴露"宁可编造"的失败)。
- 关掉视角遮蔽 → 检验它是否在误剔本该可见的证据(这是 B < A 的头号嫌疑)。

### 4.3 弃答(abstention)的记分——Starling 的关键差异化

调研强调:**没有对抗/弃答类别的记忆基准会产生误导性排名**——会编造合理措辞的系统看起来比正确拒答的系统更高分。Starling 的 §3.5 认识论诚实弃答正是为此设计。记分必须区分:
- 可回答题答对 / 答错;
- 不可回答题**正确弃答**(Starling 输出结构化"我不知道,因为…")/ **错误编造**。

LongMemEval 有 30 条 abstention 题、BEAM 有 abstention 子集,原生支持。**弃答正确率单列上报**,不混入总准确率——这是 Starling 相对纯检索基线最可能拉开差距、也最能体现产品价值的一维。

---

## 5. Judge 可信度:先审 judge,再信分数

调研中最硬的发现之一:LoCoMo 官方同款 judge(gpt-4o-mini)对"故意错误但话题相邻"的答案**接受率 62.81%**。这意味着**任何小于该阈值的分差在统计上不可解读**。Starling 评测不能重蹈覆辙。

**上线前必做的 judge 对抗验证**(一次性,产出一个可复用的 judge 质量报告):
1. 对每个基准的 gold 集,程序化生成"话题相邻但事实错误"的干扰答案(复现 Penfield 的对抗集构造)。
2. 用选定 judge + prompt 打分,测其**假阳性率**(接受错误答案的比例)和假阴性率(拒绝正确答案,如 MemTrace 发现的 judge 过严)。
3. **只有 judge 假阳性率足够低时,其分数才可解读**;并把"不可解读阈值"写进报告——所有小于此阈值的 B−A 差值标注为"统计不可区分"。
4. **双 judge 交叉**:主 judge + 一个不同家族的副 judge,分歧题人工复核(承接 §7 的人在回路分工)。

**gold 审计**:LoCoMo 已知 6.4% 标注错误。跑之前先跑一遍 `dial481/locomo-audit` 已公开的勘误清单,把已知错题剔除或修正,报告"理论最高分上限"(LoCoMo ≈ 93.6%),避免把标注错误算成 Starling 的失败(尤其 temporal 题的日期运算——正确的系统反而会被错误 gold 扣分,而这恰是 Starling 的强项子集)。

---

## 6. 分阶段实施

### Phase 0 — 协议与 judge 地基(阻塞后续全部)
- [ ] 冻结 §3.1 七要素,写成 `eval/protocol.yaml`(backbone、embedding、prompt 模板、judge、rounds)。
- [ ] 完成 §5 的 judge 对抗验证,产出 judge 质量报告 + 不可解读阈值。
- [ ] gold 审计:LoCoMo 套用公开勘误;LongMemEval 用 cleaned 版。

### Phase 1 — LongMemEval 全量(主基准,复用现有 harness)
- [ ] 把 `scripts/eval_longmemeval.py` 从当前小样本冒烟扩到官方 500 题全量(S 档先行)。
- [ ] real-mode 去 gate:现在是 `OPENAI_API_KEY` gated 且"NOT exercised this milestone",本阶段正式行使,接三配置(A/B/C)。
- [ ] 渐进式 ingestion:逐 session 经 Extractor → 总线写入(不是现有 harness 里"每 turn 一条 said 陈述"的扁平灌入——那阉割了动力学)。
- [ ] 按 5 类子集 + abstention 分层报告,出 B−A 差值 + Wilson CI。
- [ ] 阈值升级:现有 `ACCURACY_THRESHOLD=0.55` 是过门槛,不是评测目标;评测报告用**相对基线的净增益**而非绝对门槛。

### Phase 2 — LoCoMo 对照
- [ ] 新建 LoCoMo 数据加载(注意技术报告调研提到的 category-ID 白皮书↔源码不一致坑,以源码映射为准)。
- [ ] 复用 Phase 1 的三配置管线;排除 Category 5。
- [ ] 重点看:single-hop 是否不劣化;multi-hop/temporal 是否有增益;和全行业公开数字对齐(标注为"仅供定位,不可直接比较")。

### Phase 3 — BEAM 规模与压力
- [ ] 接 BEAM 128K/500K/1M 三档(10M 留后,先确认管线在 1M 稳定)。
- [ ] 重点子集:contradiction-resolution(§3.1 矛盾共存 + §4.4 再巩固的最佳舞台)、knowledge-update、event-ordering。
- [ ] 出**规模退化曲线**(准确率 vs token 规模)——这本身是 BEAM 要测的东西,也验证 Starling 检索架构在塞不下时是否成立。

### Phase 4 — 效率与消融
- [ ] 补齐 §7 效率三元组(尤其写入路径成本——调研指出这是最常被隐瞒的 confound,可占 agent 总执行时间 80%+)。
- [ ] 跑 §4.2 消融,把增益归因到具体机制。
- [ ] 汇总成一份诚实报告(见 §9)。

---

## 7. 效率维度(不可省略)

调研共识:**只报准确率是误导性的**。每个基准每个配置都要报:
- **检索延迟**(p50/p95)——现有 real-mode 已跑 SemanticRetriever,可直接计量。
- **写入路径成本**——ingestion 的 LLM 调用次数、总 token、wall-clock。调研的 MemDelta 论文实测 Mem0 写入需 1000+ 次 LLM 调用、~120 分钟/实例、$0.50+,而准确率并不显著优于成本极低的 RAG。Starling 的巩固/重放/再巩固都在写入侧,**这一维必须诚实计量**,否则"认知中间件"的成本收益无法评估。
- **每题检索 token**——对齐调研里 Mem0(~1764/query)vs full-context(~26031/query)的口径。

一个"准确率 +2pp 但写入成本 10×"的结果,在生产语境下可能是负收益——报告必须让这个权衡可见。

---

## 8. 反作弊与诚实纪律(承接技术报告 §5 的方法论)

调研记录了 MemPalace"对着错题定向打补丁"刷到 100% 后 48 小时撤回、EverMemOS 宣称 92% 实测 38% 等多起事故。Starling 评测显式规避:

- **不 teaching-to-test**:任何机制改动必须是对 Starling 设计原则的忠实贯彻(如 §5.2 的房间作用域感知),不得针对具体失败题加规则。改完先在**留出集**验证泛化,再在全量报分。
- **不挑子集报头条**:报告默认展示全部子集分层 + 聚合,不允许只摘 knowledge-update 的高分做标题。
- **报 stddev/CI**:禁止单次点估计。
- **标注证据等级**:主基准结果 vs 探索性结果分开标注(沿用技术报告 §5.4 的"证据等级说明")。
- **B<A 不隐藏**:任何 Starling 劣于纯基线的子集如实上报并归因,这本身是有价值的边界刻画(§5.3 精神)。

---

## 9. 交付物

1. `eval/protocol.yaml` — 冻结的七要素协议。
2. `eval/judge_quality_report.md` — judge 对抗验证结果 + 不可解读阈值。
3. 三份基准报告(LongMemEval / LoCoMo / BEAM),每份含:子集分层准确率 + Wilson CI、B−A 净增益、检索指标、效率三元组、消融归因。
4. 一份**总评报告**,回答 §0 的两个问题:Starling 在通用检索子集上是否不劣化?差异化能力在对应子集上是否有可测净增益、集中在哪、边界在哪?
5. git-committed 基线 JSON(复用 `eval_quality_baseline.py` 机制),纳入质量回归门禁。

---

## 10. 与现有设施的衔接(不重复造轮子)

| 需求 | 现有可复用 | 需新建/改造 |
|---|---|---|
| LongMemEval harness | `scripts/eval_longmemeval.py`(fixture/real 双模、three-config 骨架已在) | 扩到全量 500 题、去 gate、渐进 ingestion、子集分层 |
| 质量回归编排 | `scripts/eval_quality_baseline.py`(median-of-N、corpus_hash、per-metric 容差) | 把 recall(longmemeval)从 "follow-up" 转正,纳入 LoCoMo/BEAM 维 |
| real-mode 管线 | SqliteAdapter + OpenAIEmbeddingAdapter + EmbeddingWorker + SemanticRetriever + chat(已在 `_real_answer`) | 抽成三配置可切换的公共模块 |
| ToM 能力(非本三基准,但相关) | ToMBench/HiToM/FanToM harness 已全 | 保持,作为 Starling 差异化的另一战场,与本方案并行 |
| 展示 | `dashboard/web/src/routes/eval/+page.svelte` | 接三基准报告的可视化 |

**关键提醒**:现有 real-mode 的 ingestion 是"每 turn 灌一条 `said` 扁平陈述"(见 `eval_longmemeval.py:102-114`),这对冒烟够用,但对真实评测**必须替换为经 Extractor 的渐进摄入**——否则 §4 的类脑动力学(再巩固、遗忘、重放、共识晋升)全部不被触发,评测的就不是 Starling 而是一个扁平向量库,B 会退化成 A,结论失真。这是 Phase 1 的头号技术任务。

---

## 附:开放问题(需评审拍板)

1. **Backbone 选型**:默认中档模型选哪个?本机 Clash TUN 对 LLM 网络有已知抖动(见 memory),真机跑全量 500×3 轮 ×3 配置需要一个稳定 provider 窗口——是否需要先做网络可靠性预案(裸 curl 供应商对比)?
2. **BEAM 10M 档**:硬件/成本上是否本阶段就做,还是确认 1M 稳定后作为独立里程碑?
3. **judge 选型**:主/副 judge 用哪两个家族?是否复用 answerer backbone 会引入 self-enhancement bias(调研点名的偏差)?建议 judge ≠ answerer。
4. **人在回路预算**:双 judge 分歧题 + abstention 题的人工复核,谁来做、抽样多大?
