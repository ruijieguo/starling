# P2 准入报告（Admission Report）— 2026-06-02

> P2 评测准入快照。口径：离线优先 + 真模型 gated。

## 1. §16.3 CRITICAL 准入（10 条，P2.a–c 已全绿）

| # | 准入项 | CRITICAL 测试 | 落点 | 状态 |
|---|---|---|---|---|
| 1 | P1 全部 13 CRITICAL 用例绿灯，无豁免 | TC-NEW-PREFLIGHT → `Preflight.*`; TC-NEW-OUTBOX-IDEMP → `OutboxDispatcher.*`; TC-NEW-CONFLICT-SEVERE → `BusWriteConflict.*` + `ArbitrationSevere.*`; TC-Q2/Q3/NEG → `FinalQueryAssertion.*` + `ConflictProbeScan.*` | P1 出货门槛（§15.3.1），已通过 | ✅ |
| 2 | P2 ToMBench 一阶 ToM 基准跑通，FANToM 信息不对称对照集准备完毕 | `eval_tom_bench.py --fixture-mode`（fixture self-test）+ FANToM harness（P2.a 已落地） | P2.a eval harness，已就位 | ✅ |
| 3 | Replay Scheduler 上线前通过 Projection repair safety 测试：truncation_suspected 告警触发且 active projection 不被替换 | `ProjectionRepairGuard.TruncationKeepsOldActive`; `VectorRepairGuard.TruncationSuspectedKeepsActive` | P2.b Projection/Vector repair guard | ✅ |
| 4 | Reconsolidation Engine 上线前，再巩固窗口参数有 per-modality 覆写配置，高频更新对象自动缩短至 5 min | `ReconsolidationEngine.TickBeliefConflictOpensWindow`; `ReconsolidationEngine.CommitmentFulfilledIsSkipped` | P2.b ReconsolidationEngine | ✅ |
| 5 | P2 ConflictProbe 上线后，CONFLICTS_WITH 边写入必须通过 canonical_conflict_key 唯一性校验，防止同一冲突对多次记录 | `ConflictKey.SameInputProducesSameKey`; `ConflictProbeIndices.BothNewIndicesPresent` | P2.b ConflictProbe 唯一性索引 | ✅ |
| 6 | Projection Index 首次 rebuild 前，repair guard（SQLite ground truth vs index count）验证，truncation_suspected 告警可触发 | `ProjectionRepairGuard.HealthyRebuildReplacesActive`; `ProjectionRepairGuard.TruncationKeepsOldActive`; `VectorRepairGuard.HealthyRebuildReplaces` | P2.b Projection/Vector repair guard | ✅ |
| 7 | 状态机契约（Replay 路径）：TC-A1-001（replay_count 上限→CONSOLIDATED）、TC-A1-002（VOLATILE TTL）、TC-A5-001/002（fallback timeout/双层兜底）、TC-A6-001/002（T5/T8 outbox 串行）、TC-A8-001（severe 异步仲裁） | `ReplayScheduler.OscillationGuard_HighReplayCount_Forced`; `ReplayScheduler.SweepVolatileTTL_OldArchived_RecentUnchanged`; `ReplayScheduler.RunDecay_ArchivesOldConsolidated`; `OutboxDispatcher.PerAggregateOrderingHonoredOnRetry`; `ArbitrationSevere.FourItemAtomicCommit` | P2.b Replay Scheduler | ✅ |
| 8 | Commitment 契约：TC-A2-001（三次 BROKEN auto WITHDRAWN）、TC-A2-002（RENEGOTIATED 链长=3）、TC-A9-001（active_holding 反向保护）、TC-A9-002（release 释放）、TC-A9-003（dispatcher boot replay） | `CommitmentEngine.ThreeBrokenAutoWithdrawn`; `CommitmentEngine.RenegotiationChainCappedAtThree`; `CommitmentProtectionDecay.ActiveHoldingPreventsArchive`; `CommitmentProtectionDecay.TerminalReleasesProtection`; `CommitmentProtectionDecay.ProtectionDurableAcrossNewInstance` | P2.c Prospective Loop | ✅ |
| 9 | Reconsolidation 兼容性：P2.b 上线不得修改 P1 ConflictProbe 同步路径；TC-NEW-CONFLICT-SEVERE 在 P2 仍须通过；TC-A8-001 异步仲裁版本作为补集 | `BusWriteConflict.PartialOverlapWritesConflictsWithEdgeAndBeliefEvent`; `ArbitrationSevere.FourItemAtomicCommit`; `ArbitrationSevere.NewVersionNoStatementWritten` | P2.b Reconsolidation 兼容守护 | ✅ |
| 10 | 评测加载：接入 ToMBench 一阶 ToM 子集 + FANToM 信息不对称对照集，取代 §15.3.3 手工标注成为权威质量指标 | `eval_tom_bench.py`（24 条一阶语料）+ FANToM harness（1k 采样）；均已入 CI fixture self-test | P2.a eval harness（§15.1） | ✅ |

## 2. C1 承诺履行 eval（离线确定性，真数字）

命令：`python scripts/eval_commitment.py --corpus tests/data/eval_commitment/scenarios.jsonl`

结果：detection rate **1.0000**（阈值 >0.80 ✅）/ timeliness **1.00** turns（阈值 <3 ✅）/ 100 scenarios / **PASS**。

分布：30 fulfill + 25 deadline_break + 20 renegotiate + 15 withdraw + 10 active_pending。

注：chronic auto-WITHDRAWN（broken_count≥3）经探针确认**不可由公共 API 路径触达**（on_deadline_expired 的 ACTIVE 源态守护 + renegotiation 链长上限），故承诺语料用 renegotiate 类替代；C++ `CommitmentEngine.ThreeBrokenAutoWithdrawn` 经 raw-SQL 强置 ACTIVE 覆盖该内部路径。

## 3. C2 LongMemEval（fixture 离线 PASS；真模型 gated 已跑）

fixture-mode：`python scripts/eval_longmemeval.py --corpus tests/data/eval_longmemeval/sessions.jsonl --fixture-mode` → **PASS**。

real-mode（gated，2026-06-03 跑）：chat=`deepseek-v4-flash`@DeepSeek 官网 + embedding=`text-embedding-v3`@DashScope（dim 1024）；OpenAIEmbeddingAdapter→EmbeddingWorker→SemanticRetriever 真向量检索 + DeepSeek 答题；3 轮 24 条。

| 子集 | fixture | real（gated，last-acc） |
|---|---|---|
| time-reasoning | 0.9167 PASS | **1.0000 PASS** |
| knowledge-update | 0.9167 PASS | **1.0000 PASS** |

## 4. C3 ToMBench 一阶（fixture 离线 PASS；真模型 gated 已跑）

fixture-mode：`python scripts/eval_tom_bench.py --corpus tests/data/eval_tom_bench/first_order.jsonl --fixture-mode` → **PASS**（accuracy **0.7500** ≥ 0.55，24 条一阶语料；round 1/2/3 一致）。

real-mode（gated，2026-06-03 跑）：`--model deepseek-v4-flash`@DeepSeek 官网，3 轮 24 条 → accuracy **1.0000 / 1.0000 / 1.0000**（≥ 0.55）**PASS**。

## 5. Gated 真模型 run（需 key，不入 CI；2026-06-03 实跑）

C2/C3 已用 DeepSeek 官网（chat）+ DashScope（embedding）双 provider 实跑（数字见 §3/§4）：

```
# C2 LongMemEval — chat=deepseek-v4-flash@DeepSeek + emb=text-embedding-v3@DashScope
OPENAI_BASE_URL=https://api.deepseek.com/v1 OPENAI_API_KEY=$DEEPSEEK_API_KEY \
  CHAT_MODEL=deepseek-v4-flash EMBEDDING_MODEL=text-embedding-v3 EMBEDDING_DIM=1024 \
  DASHSCOPE_API_KEY=… DASHSCOPE_BASE_URL=… \
  python scripts/eval_longmemeval.py --corpus tests/data/eval_longmemeval/sessions.jsonl --rounds 3 --report build/lme_real.md

# C3 ToMBench — chat=deepseek-v4-flash@DeepSeek
OPENAI_BASE_URL=https://api.deepseek.com/v1 OPENAI_API_KEY=$DEEPSEEK_API_KEY \
  python scripts/eval_tom_bench.py --corpus tests/data/eval_tom_bench/first_order.jsonl --rounds 3 --model deepseek-v4-flash --report build/tom_real.md

# P1 extractor（可选；P1 期 eval，非 P2 准入门槛。2026-06-03 已补跑，结果见 §5.1）
OPENAI_BASE_URL=https://api.deepseek.com/v1 OPENAI_API_KEY=$DEEPSEEK_API_KEY \
  python scripts/eval_p1_extractor.py --corpus tests/data/eval_p1_corpus.jsonl --rounds 3 --model deepseek-v4-flash --report build/p1_real.md
```

注：DeepSeek 无 embeddings 端点，故 C2 向量检索经 DashScope `text-embedding-v3`（dim 1024），chat 经 DeepSeek `deepseek-v4-flash`。harness 的 `max_tokens` 由 4 提至 512，使推理型模型（deepseek-v4-*）有空间产出可见答案（解析器取首个 0–3 数字，多余/推理文本无害）。P1 extractor 的 payload 原无 `max_tokens`，补跑时显式加 4096，给推理 + JSON 数组留余量。key 仅经环境变量注入，不入参/log/语料/报告。

### 5.1 P1 extractor 补跑结果（deepseek-v4-flash，3 轮 50 条；P1 期 eval，非 P2 准入门槛）

| field | round 1 | round 2 | round 3 | 阈值 | last ≥ 阈值 |
|---|---|---|---|---|---|
| holder | 0.865 | 0.869 | 0.851 | 0.85 | ✅ PASS |
| holder_perspective | 0.823 | 0.786 | 0.794 | 0.80 | ❌ FAIL（差 0.006）|
| predicate | 0.908 | 0.910 | 0.894 | 0.75 | ✅ PASS |
| object | 0.908 | 0.910 | 0.894 | 0.70 | ✅ PASS |
| nesting_depth_1 | 0.526 | 0.762 | 0.600 | 0.60 | ✅ PASS |

5 个字段中 **4 个达阈**；`holder_perspective` 末轮 0.794 微差阈值 0.80（round 1 曾 0.823 达阈，rounds 2/3 回落至 0.786/0.794）。抽取 prompt 为 gpt-5.5 重度调优，deepseek-v4-flash 在 perspective 细则（FIRST_PERSON/QUOTED/HEARSAY/INFERRED）上略逊。整体 harness exit=1（因末轮单字段未达阈）。**此为 P1 期质量指标，不构成 P2 准入门槛**——P2 准入门槛为 §16.3 十条 + C1/C2/C3，均已达阈。

## 6. 结论

P2 §16.3 CRITICAL 准入达成；eval harness 就位且离线全绿（C1/C2/C3 fixture 自测入 CI）；
**C1 承诺履行离线真过**（detection 1.0000 / timeliness 1.00 turns，均达阈）；
**C2 LongMemEval 真模型过**（time-reasoning 1.0000 / knowledge-update 1.0000，均 ≥ 0.55）；
**C3 ToMBench 一阶真模型过**（1.0000 ≥ 0.55，3 轮一致）。
**P2 准入达成：结构性（§16.3 十条）+ 离线（C1/C2/C3 fixture）+ 真模型 gated（C1 离线真 / C2 / C3）三层 eval 数字全部达阈。**

（附：P1 期 extractor eval 以 deepseek-v4-flash 补跑，5 字段 4 达阈，holder_perspective 末轮 0.794 微差 0.80；详见 §5.1。该指标属 P1 期，不构成 P2 准入门槛。）

---

## 6. P3.a2 二阶 ToM 准入(2026-06-12 增设)

P3 准入硬约束之一:**二阶 ToM precision > 0.70**。harness 扩展
`scripts/eval_tom_bench.py --order second`(二阶子集
false-belief / second-order / higher-order,阈 0.70;一阶记录跳过)。

- fixture 离线:**PASS**(确定性 mock,入 CI:`test_eval_tom_bench_harness.py::test_second_order_subset_with_higher_threshold`)。
- 真模型 gated(待跑,命令):
  ```bash
  OPENAI_API_KEY=… OPENAI_BASE_URL=https://api.deepseek.com/v1 \
    .venv/bin/python scripts/eval_tom_bench.py \
    --corpus <tombench-second-order.jsonl> --order second \
    --model deepseek-v4-flash --rounds 3 --max-items 24 \
    --report build/eval_tom_bench_second.md
  ```
  真模型数字回填本节后,P3.a2 准入关闭。
