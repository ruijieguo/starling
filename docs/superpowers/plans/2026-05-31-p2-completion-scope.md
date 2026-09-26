<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

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

# P2 收尾范围清单（P2 Completion Scope）
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **目标**：把当前状态推到 P2 的真正验收口径——**「所有功能基本完备、局部待优化、支持小规模应用」**。
> 本文件是**范围清单 + 拆分原则**,不直接执行;每个收尾里程碑落地前再生成对应 spec/plan(与 P2.a/b/c 同流程)。

**关联**:[2026-05-23-roadmap.md](2026-05-23-roadmap.md)(总路线图)。本清单只覆盖「补齐 P2」,P3「大规模应用」不在范围。

---

## 现状一句话

P2.a / P2.b(M0.8+M0.9)/ P2.c 三个子阶段的**里程碑已全部合并 main 且测试全绿**(ctest 486 / pytest 487 passed + 13 skipped)。但相对**完整 P2**,仍有三类缺口:

1. **P2.b 漏掉的模式补全(PPR)** —— roadmap P2.b 出货项明列「模式分离 + PPR」,M0.9 只落地了模式分离,PPR/CA3 联想补全被推迟。
2. **没有可被 agent 使用的应用接口层** —— Python 侧只有 `from starling import _core` + `Runtime`(preflight/health)+ `BusFacade`,**没有 `Memory` 门面、没有 Working Set 渲染、没有可运行示例**。这是「支持小规模应用」最大的硬缺口。
3. **P2 评测准入未跑** —— roadmap P2 准入要求「ToMBench 一阶 + LongMemEval 时间/更新 + 自建承诺履行 100 条」;P2.c 走了 tests-only,承诺履行 eval 与 LongMemEval 尚未建/未跑。

**范围原则(YAGNI)**:只补「P2 完整 + 小规模可用」所需。分布式底座、seekdb、二阶 ToM、完整 Retrieval Planner、外部动作执行、规模化优化**全部明确留给 P3**(见文末「不在本次范围」)。

---

## 收尾里程碑总览

| 里程碑 | 目标 | 关闭的缺口 | 估算(human / CC) |
|---|---|---|---|
| **P2.d 模式补全** | PPR/CA3 联想补全 + 接入检索 | ① P2.b 功能缺口 | ~1 周 / ~1–2 session |
| **P2.e 应用接口层** | `Memory` 门面 + Working Set 渲染 + 可运行示例 | ② 支持小规模应用 | ~1.5 周 / ~2 session |
| **P2.f 评测准入** | 承诺履行 100 条 + LongMemEval + ToMBench 确认 | ③ P2 admission | ~1 周 / ~1–2 session |

> 命名延续 P2 子阶段字母序(a/b/c → d/e/f),不与既有里程碑冲突。

---

## P2.d —— 模式补全（Pattern Completion / PPR）

**为什么属于 P2**:roadmap P2.b 出货项明列「模式分离(反相似偏移 + PPR)」。M0.9 只落地了**模式分离**(`PatternSeparator` + `MAY_OVERLAP_WITH` 边),**PPR/CA3 联想补全**(给部分线索→召回共现记忆)被推迟。这是 P2.b 范围内的功能缺口,不是 P3。

**范围**:
- `PatternCompletor`:给定部分线索(cue statements / 当前上下文),在 statement 图上做 **Personalized PageRank**(种子 = cue 命中的 statements;边 = `MAY_OVERLAP_WITH` + 语义近邻 + `statement_edges` 关联),返回共现补全集。
- 接入 `Retrieval`:新增 `pattern_completion` recall 模式(与 `vector_recall` / `basic_retrieve` 并列),privacy-first(复用既有视角过滤)。
- 配置:阻尼系数、walk 深度上限、top-k。

**不做(→P3)**:EM-LLM 事件切分、`segment_map`/`span_start`/`span_end`(P3.c)、dimension-level Container CAS。

**验收**:给定 cue 集能召回共现 statements;单测 + 一条 runtime E2E;不回归 M0.9 `vector_recall`。

**依赖**:M0.9 向量层(已完成)、`statement_edges`(已完成)。

**估算**:~5–7 task。

---

## P2.e —— 应用接口层（Application Surface）

**为什么属于 P2**:P2 验收口径就是「**支持小规模应用**」。当前 Python 侧只有 `from starling import _core` + `Runtime`(preflight/health 监督器)+ `starling.bus.append_evidence.BusFacade`,**没有一个小应用开发者能直接拿来用的门面**,也没有把记忆喂进 prompt 的 Working Set 渲染,更没有可运行示例。这是「支持小规模应用」最大的硬缺口。

**范围**:
- **B1 公开门面 `starling.Memory`**:`open(path)` / `remember(...)` / `recall(query, perspective, goal)` / `tick()` / `close()`。薄封装 `_core` + `Runtime` + `BusFacade` + `SemanticRetriever`,方法 conn-free,preflight 内建。
- **B2 Working Set 渲染 `render_working_set(agent, interlocutor, goal) -> ContextBlock`**:persona 摘要 + common ground + top-k 检索(basic + semantic + pattern-completion) + `pending_commitments` + 当前 affect,输出 prompt-ready 上下文块。**注意是最小版**,非 P3.a 的 7 步 Retrieval Planner / 8 标签 Context Pack。
- **B3 `commitment.fire` → reminder 注入端到端**:PolicyEngine fire 的 commitment 出现在 `render_working_set` 的 `pending_commitments` 区(reminder 注入路径,**不接外部 tool 执行**——那是 P3)。
- **B4 可运行示例 `examples/quickstart.py`**:打开记忆 → 写若干关于某人的 statement → 跑一轮对话(recall + working set)→ 演示一个 commitment 到期触发提醒。兼作 README quickstart 与冒烟测试。

**不做(→P3)**:完整 Retrieval Planner(7 步 / 9 QueryIntent)、Context Pack 8 标签、二阶 ToM、外部 tool 执行、ActionPolicyGraph。

**验收**:pytest 覆盖 `Memory` 门面 + working set;`examples/quickstart.py` 可跑通并断言关键输出;README quickstart 指向它。

**依赖**:可与 P2.d 并行起手(B2 先接 basic+semantic,pattern-completion 后补)。

**估算**:~7–9 task。

---

## P2.f —— 评测准入（P2 Admission Eval）

**为什么属于 P2**:roadmap P2 准入除 §16.3 的 10 条 CRITICAL(已过)外,还要求评测——「ToMBench 一阶 + LongMemEval 时间/更新 + 自建承诺履行 100 条(detection >80% / timeliness <3 turns)」。P2.c 走了 tests-only,承诺履行 eval 与 LongMemEval 尚未建/未跑。

**范围**:
- **C1 承诺履行 eval**:`scripts/eval_commitment.py` + 100 条自建语料(扩展现有 `generate_eval_corpus.py`);指标 detection rate >80%、timeliness <3 turns;对接 `CommitmentEngine` + `PolicyEngine`。
- **C2 LongMemEval 时间/更新子集**:`scripts/eval_longmemeval.py`(time-reasoning + knowledge-update 两子集),跑通达阈。
- **C3 ToMBench 一阶确认**:现有 `scripts/eval_tom_bench.py` 跑一阶子集,记录通过阈值(**确认**而非新建)。
- **C4 P2 准入报告**:一份 §16.3 全 10 条 + 三项 eval 的 P2 验收快照(markdown,落 `docs/`)。

**不做(→P3)**:FANToM / SoMi-ToM 全量、二阶 ToM precision >70%、1000 Cognizer × 10000 Statement × 100 QPS 规模负载(均为 P3 准入 §16.4)。

**验收**:三个 eval 脚本可跑且达 roadmap 阈值;P2 准入报告落地。

**依赖**:P2.e(承诺履行 eval 用到 working set / 提醒注入路径)。建议 P2.d、P2.e 之后跑。

**估算**:~5–7 task。

---

## 明确不在本次范围（→ P3「大规模应用」,§16.4 准入）

| 项 | 归属 |
|---|---|
| dist-store(Postgres+pgvector+AGE)多租户底座、cloud-store 三形态 | P3.b |
| seekdb 单引擎向量后端(`VectorIndex` adapter seam 已留,暴力够小规模) | P3 优化 |
| EM-LLM 事件切分 + LLM logprobs + `segment_map`/`span` | P3.c |
| 完整 Retrieval Planner(7 步 / 9 QueryIntent)+ Context Pack 8 标签 | P3.a |
| 二阶 ToM(`nesting_depth=2`)+ `ToMDepthEstimator` | P3.a |
| ActionPolicyGraph 8 规则 + 外部 tool 执行 | P3.c |
| 规模化优化(ScopedWorkGate / 自动背压 / fan-out latency budget) | P3.c |
| 跨档迁移工具 + mem0/Letta/cognee/Graphiti/memU 迁移脚本 | P3.b |
| FANToM / SoMi-ToM 全量评测、规模负载测试 | P3 准入 |

**一句话**:以上都属于 P3「大规模应用」,不是「小规模应用基本完备」的阻塞项。当前 local-store SQLite 单租户 + 暴力向量,在小规模下够用。

---

## 建议执行顺序

```
P2.d 模式补全  ┐
               ├─(并行起手)→ P2.e 收尾(B3/B4)→ P2.f 评测准入 → 诚实声明「P2 完整 + 小规模可用」
P2.e B1/B2     ┘
```

三个收尾里程碑各走 **brainstorm → spec → writing-plans → subagent-driven-development**,与 P2.a/b/c 同流程同约束(worktree 隔离、Co-Authored-By trailer、`cmake --install` 刷新、单一 `starling_tests`、migrations glob)。

**总量**:3 里程碑 ≈ human ~3.5 周 / CC 数个 session。完成后方可诚实声明 P2 达到「所有功能基本完备、局部待优化、支持小规模应用」。
