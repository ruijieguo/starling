# P2.f 评测准入（Admission Eval）设计

**里程碑**：P2.f（P2 收尾三里程碑之末，见 [2026-05-31-p2-completion-scope.md](../plans/2026-05-31-p2-completion-scope.md)）
**日期**：2026-06-02
**状态**：设计已 user approved，待 writing-plans
**依赖**：P2.d / P2.e 已合并 main（HEAD 4fc762f）；`starling.Memory` 门面、CommitmentEngine/PolicyEngine、既有 eval harness（`eval_tom_bench.py` / `eval_fantom.py` / `eval_p1_extractor.py`）均已落地

---

## 0. 背景与目标

roadmap P2 准入除 §16.3 的 10 条 CRITICAL（已在 P2.a–c 全绿）外，还要求评测：「ToMBench 一阶 + LongMemEval 时间/更新 + 自建承诺履行 100 条（detection >80% / timeliness <3 turns）」。P2.c 走了 tests-only，这三项 eval 尚未跑通——故 **P2 评测准入未达成**。P2.f 关闭它，P2 才真正达到「所有功能基本完备、局部待优化、支持小规模应用」的验收口径。

**目标一句话**：补齐 P2 评测准入——C1 承诺履行 eval（离线确定性、真数字）、C2 LongMemEval harness、C3 ToMBench 一阶确认、C4 P2 准入报告；统一「离线 fixture 入 CI + 真模型 gated」口径。

---

## 1. 范围与口径

**评测口径（user 选定）**：**离线优先 + 真模型 gated**。与既有 `eval_tom_bench.py` / `eval_fantom.py` 的 `--fixture-mode`（离线确定性 mock，必过阈值）+ real-mode（OpenAI，gated）双模式一致。

- **C1 承诺 eval 例外**：承诺 detection/timeliness 测的是 prospective 引擎行为（五态机 + 触发器），**确定性、不靠语义**——离线给的就是**真数字**，入 CI。
- **C2 / C3**：语义检索质量，离线 fixture-mode 是 harness smoke（mock answerer），**真阈值数字需 OpenAI，走 gated run**（不入 CI、报告里记命令 + 待填）。

**范围内（P2.f 交付）：**
- C1：`scripts/generate_commitment_corpus.py`（确定性模板，无 LLM）+ `tests/data/eval_commitment/scenarios.jsonl`（100 条）+ `scripts/eval_commitment.py`（引擎驱动 harness）+ 自测。
- C2：`scripts/eval_longmemeval.py`（fixture + real-mode，自建 pipeline）+ `tests/data/eval_longmemeval/sessions.jsonl`（~20–40 条）+ 自测。
- C3：补 `tests/data/eval_tom_bench/first_order.jsonl`（~20–40 条一阶语料）+ 确认现有 `eval_tom_bench.py --fixture-mode` 跑通。
- C4：`docs/eval/2026-06-02-p2-admission-report.md`（§16.3 + 3 eval 快照 + gated run 小节）。

**明确范围外（→P3，§16.4）：**
- FANToM 全量真跑（harness 已在 P2.a，本期不动）、SoMi-ToM。
- 二阶 ToM precision >70%、ToMDepth accuracy。
- 1000 Cognizer × 10000 Statement × 100 QPS 规模负载。
- 不改 `starling.Memory`（C2 harness 自建 pipeline，避免 P2.e churn）；无 migration。**+1 处 additive C++ 绑定**：`OpenAIEmbeddingAdapter`/`OpenAIEmbeddingConfig` pybind（实现期发现其未绑定 Python，C2 real-mode 需要；镜像 `OpenAIAdapter` 绑定，`api_key` 不暴露，无 C++ 逻辑改，ctest 仍 505）。

---

## 2. C1 承诺履行 eval（离线确定性，真数字）

测 prospective 引擎对承诺的**追踪**（检出 due/fired + timeliness）。承诺**结构化直接 seed**（COMMITS statement + trigger）——「从自然语言抽出承诺」是 extractor（真 LLM）的事，归 P1 抽取 eval，不在 C1。

**语料** `tests/data/eval_commitment/scenarios.jsonl`（100 条），由 `scripts/generate_commitment_corpus.py` **确定性模板生成**（seeded RNG，**无 LLM / 无网络**；输出提交入库，slot-plan 风格类比 `generate_eval_corpus.py` 但纯结构化）。每条：
```json
{
  "scenario_id": "cm-001",
  "statement": {"id":"c1","holder":"alice","subject":"bob","predicate":"owes",
                "object":"design doc","modality":"commits",
                "deadline":"2026-06-01T12:00:00Z","observed_at":"2026-06-01T09:00:00Z"},
  "trigger": {"kind":"time","spec_json":"{}","armed_at":"2026-06-01T09:00:00Z"},
  "ticks": ["2026-06-01T10:00:00Z","2026-06-01T11:00:00Z","2026-06-01T13:00:00Z"],
  "expected": {"should_fire": true, "fire_by_turn": 2, "final_state": "ACTIVE"}
}
```
覆盖：4 类触发（time/event/state/compound）、边界（broken 累计→auto WITHDRAWN、withdrawn、renegotiated 链、多 turn 延迟、不应 fire 的负例）。生成器保证子集分布（约 60 正例 should_fire + 40 含负例/边界）。

**harness** `scripts/eval_commitment.py`（CLI 对齐 `eval_tom_bench.py`：`--corpus`/`--report`/exit-code）：
- 每场景开临时 SQLite（`:memory:` 或 tmp），seed COMMITS statement + `commitment_triggers` 行 + `CommitmentEngine.create_from_statement`；按 `ticks` 序列调 `PolicyEngine.tick(now)`，每 tick 后 `CommitmentEngine.pending(...)` 观测 fired/状态。
- 指标：
  - **detection rate** = 与 `expected.should_fire`/`final_state` 一致的场景占比 → 阈值 **>0.80**（`DETECTION_THRESHOLD = 0.80`）。
  - **timeliness** = should_fire 场景里 arming→firing 的 turn 数中位数 → 阈值 **<3**（`TIMELINESS_THRESHOLD = 3`）。
- 输出：markdown 报告（detection / timeliness / 阈值 / 逐场景）+ stdout `PASS`/`BLOCKED` + exit code 0/1。
- **纯离线**（无 key/embedder）。

**自测** `tests/python/test_eval_commitment_harness.py`：tiny fixture 语料（in-memory 生成，约 5 条）跑 harness，断言 exit 0 + PASS verdict + 报告写出 + 指标算对（含一条负例验证 detection 计数）。

---

## 3. C2 LongMemEval harness（新建，镜像 ToMBench 模式）

`scripts/eval_longmemeval.py`：`--fixture-mode`（确定性 mock answerer，stddev/accuracy 必过，入 CI）+ real-mode（OpenAI，gated）。子集 `time-reasoning`（时间推理/排序）+ `knowledge-update`（事实更新 A→B 取最新）。

**语料** `tests/data/eval_longmemeval/sessions.jsonl`（~20–40 条，多选题确定性打分）：
```json
{"item_id":"lme-001","subset":"knowledge-update",
 "history":[{"speaker":"alice","text":"Bob owns auth.","observed_at":"2026-04-01T10:00:00Z"},
            {"speaker":"alice","text":"Carol took over auth from Bob.","observed_at":"2026-05-01T10:00:00Z"}],
 "question":"Who currently owns auth?","options":["Bob","Carol","Dana","Alice"],"answer":1}
```

**run 形态**：
- **fixture-mode**：deterministic mock answerer（`item_index` 哈希定 verdict，每子集 ~90% 正确 → 必过阈值），不需真检索。证明 harness 跑通 + 打分逻辑。入 CI。
- **real-mode**（gated）：harness **自建完整 pipeline**——`SqliteAdapter` + `OpenAIEmbeddingAdapter` + `EmbeddingWorker` + `SemanticRetriever` + `OpenAIAdapter`（**不经 `starling.Memory`**，避免写读 embedder 不一致 + 不改 P2.e）。写 history（逐 turn seed statement + embed）→ `recall(question)` 取上下文 → LLM 答 → 对 options 打分。需 `OPENAI_API_KEY`。

**指标/阈值**：每子集 accuracy（最后一轮，多轮取最后），阈值 `ACCURACY_THRESHOLD = 0.55`（沿用 ToMBench 量级）。PASS/FAIL exit code + markdown 报告（镜像 `eval_tom_bench.py` 输出）。

**自测** `tests/python/test_eval_longmemeval_harness.py`：fixture-mode 在 in-memory 小语料上跑，断言 exit 0 + PASS + 两子集都被评 + 报告写出。

---

## 4. C3 ToMBench 一阶确认 + 补语料

现有 `scripts/eval_tom_bench.py`（fixture + real 双模式 + 0.55 accuracy 阈值）+ 其自测 `test_eval_tom_bench_harness.py` 已过——**确认**而非新建。

**补缺失的一阶语料** `tests/data/eval_tom_bench/first_order.jsonl`（harness docstring 已引用、文件不存在）：~20–40 条多选题，覆盖 4 一阶能力（`unexpected-outcome` / `desire` / `persuade` / `world-knowledge`），**手写/模板、无 LLM**，schema 对齐 harness（`question_id` / `context` / `question` / `options[4]` / `answer` 0-based / `ability`）。

**确认**：`eval_tom_bench.py --corpus tests/data/eval_tom_bench/first_order.jsonl --fixture-mode` 跑通 exit 0 + PASS；real-mode gated（报告记命令）。

**测试**：一条语料 shape 校验测试（`tests/python/test_tom_bench_corpus.py`）断言文件存在、每条 4 options、answer 在 0–3、ability 在一阶集内。

---

## 5. C4 P2 准入报告

`docs/eval/2026-06-02-p2-admission-report.md`：

- **§16.3-1~10 CRITICAL**：逐条 ✅ + 落点（TC-A1-001/002、TC-A5-001/002、TC-A6-001/002、TC-A8-001、TC-A2-001/002、TC-A9-001/002/003、TC-NEW-CONFLICT-SEVERE、Projection/Vector repair guard 等，来自 P2.a–c，给测试名 + ctest 落点）。
- **C1 承诺 eval**：离线**真数字**（detection X% / timeliness Y turns / PASS），引 `scripts/eval_commitment.py` 报告。
- **C2 LongMemEval**：fixture 离线 PASS；real-mode **gated**——给运行命令 + 「数字待 gated run」待填表（time-reasoning / knowledge-update 两行）。
- **C3 ToMBench 一阶**：fixture 离线 PASS + 小语料 accuracy；real-mode gated（命令 + 待填）。
- **gated 真模型 run 小节**：跑 C2/C3 + P1 抽取 eval 的确切命令（`OPENAI_API_KEY=… python scripts/eval_*.py …`）+ 阈值表。
- **诚实结论**：「**P2 §16.3 CRITICAL 准入达成 + eval harness 就位且离线全绿 + C1 承诺履行离线真过(detection/timeliness)**；C2/C3 真模型阈值数字待 gated run。P2 结构性达标 + 离线验证完成,真模型 eval 数字 gated。」

---

## 6. 测试 + 红线

- **C1 自测**（`test_eval_commitment_harness.py`）：fixture 语料跑 harness，PASS + 指标算对（含负例）。入 CI。
- **C2 自测**（`test_eval_longmemeval_harness.py`）：fixture-mode 跑通，两子集被评。入 CI。
- **C3**：现有 `test_eval_tom_bench_harness.py` 不回归 + 新语料 shape 校验。
- **生成器确定性**：`generate_commitment_corpus.py` 重跑产同输出（seeded）——一条测试或 CI 校验。
- **语料 shape 校验**：C1/C2/C3 语料文件格式测试。
- **回归红线**：唯一 C++ 改动 = `OpenAIEmbeddingAdapter` pybind 绑定（additive，无逻辑改，**ctest 505 不动**）；无 migration（最高 0021）；单一 `starling_tests`；不改 `starling.Memory`/既有 harness 逻辑（C3 只补语料）；pytest 增 C1/C2/C3 自测,全绿。
- API key env-only（`OPENAI_API_KEY`，gated run 用，**绝不入参/log/绑形参/提交**）。

---

## 7. 实施约束（注入 writing-plans）

- worktree 隔离（`worktree-p2-f-admission-eval`），从 main HEAD 切出。
- 新脚本风格 mirror `scripts/eval_tom_bench.py`：argparse CLI、`--fixture-mode`、markdown 报告、PASS/BLOCKED + exit code、`OPENAI_API_KEY` gating（fixture-mode 跳过 key 检查）。
- 自测 mirror `tests/python/test_eval_tom_bench_harness.py`：in-memory 生成 fixture 语料、断言 exit 0 + 报告。
- C1 harness 经 `_core.CommitmentEngine` / `_core.PolicyEngine` 绑定驱动（conn-free 方法；参考 `examples/quickstart.py` 的 create→trigger→tick→pending 周期 + `tests/python/test_p2c_commitment_lifecycle.py`）；临时 DB 用 `runtime._build_local_store_sqlite_runtime` + `relax_preflight_for_m0_3`，或直接 `_core.SqliteAdapter.open(":memory:")`。
- C2 real-mode pipeline 用 `_core.OpenAIEmbeddingAdapter` + `_core.OpenAIAdapter`（确认绑定形态）；fixture-mode 不构造它们。
- 语料生成 `generate_commitment_corpus.py` 确定性（固定 seed，`Date.now`/`random` 不可用则模板枚举）；**无 LLM**。
- Co-Authored-By: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`；无 `--no-verify` / `--amend`；plan 文件 untracked 直到 close；API key env-only。
- **唯一 C++ 改动 = OpenAIEmbeddingAdapter pybind 绑定（additive）/ 无 migration / 不改 Memory**——其余纯 Python scripts + 语料 + 文档。

---

## 8. 验收

- C1：`scripts/eval_commitment.py` 在 100 条语料上跑通，detection >80% / timeliness <3 turns，exit 0 + 报告；自测绿，入 CI。
- C2：`scripts/eval_longmemeval.py --fixture-mode` 跑通 exit 0 + 两子集；real-mode pipeline 接好（gated）；自测绿。
- C3：`first_order.jsonl` 补齐，`eval_tom_bench.py --fixture-mode` 跑通；语料 shape 校验绿。
- C4：P2 准入报告落地，§16.3 全 ✅ + C1 真数字 + C2/C3 离线 PASS + gated 小节。
- 回归：M0.8 + M0.9 + P2.a–e 无回归；ctest 505 不动；pytest 增自测全绿；无 migration / 无 C++ / 不改 Memory。
- **可诚实声明**：P2 评测准入结构性达成 + 离线验证完成,真模型 eval 数字 gated。
