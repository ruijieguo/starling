<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# P2.f 评测准入（Admission Eval）设计
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

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
- 无 `--no-verify` / `--amend`；plan 文件 untracked 直到 close；API key env-only。
- **唯一 C++ 改动 = OpenAIEmbeddingAdapter pybind 绑定（additive）/ 无 migration / 不改 Memory**——其余纯 Python scripts + 语料 + 文档。

---

## 8. 验收

- C1：`scripts/eval_commitment.py` 在 100 条语料上跑通，detection >80% / timeliness <3 turns，exit 0 + 报告；自测绿，入 CI。
- C2：`scripts/eval_longmemeval.py --fixture-mode` 跑通 exit 0 + 两子集；real-mode pipeline 接好（gated）；自测绿。
- C3：`first_order.jsonl` 补齐，`eval_tom_bench.py --fixture-mode` 跑通；语料 shape 校验绿。
- C4：P2 准入报告落地，§16.3 全 ✅ + C1 真数字 + C2/C3 离线 PASS + gated 小节。
- 回归：M0.8 + M0.9 + P2.a–e 无回归；ctest 505 不动；pytest 增自测全绿；无 migration / 无 C++ / 不改 Memory。
- **可诚实声明**：P2 评测准入结构性达成 + 离线验证完成,真模型 eval 数字 gated。
