# P2 收尾范围清单（P2 Completion Scope）

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
