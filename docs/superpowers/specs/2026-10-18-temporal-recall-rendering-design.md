# 召回渲染带时间：把 observed_at 与会话标识送进回答模型

日期 2026-10-18。状态：草案 v1，待第三方评审；承接并取代 `2026-10-17-dual-brain-general-memory-design.md` 的 P1。

## 为什么有这份文档

双脑设计 v2 的 P1（Engram 投影的 chunk 层）立项依据是“通用记忆的瓶颈在检索与原文通道”。本轮用 LongMemEval-S 做了一个不改核心的探针（仅评测侧，脚本与日志在本机 `build/dual_brain_20261017/`，未入库），数据否决了该前提，并指出一个更小、有确证数据的改动：**回答模型看不到日期**。

## 证据（全部来自同一探针；单一 backbone deepseek-v4-pro、单次采样、judge 与回答同模型）

探针设计：每题一个库（话轮原文逐条嵌入），同一次 top-k 检索，用不同渲染分别作答；另设 FULL（整段历史）与 ORACLE（仅证据会话）两个无检索参照。官方 LongMemEval judge 模板（按题型），跑前固定。

| 渲染 | 一行的样子 |
|---|---|
| R0 | `- said: <原文>`（现 S_rag 在评测里的渲染，无日期无说话人）|
| R1 | `- <role>: <原文>` |
| R2 | `- [2023-04-10 Mon 17:50 \| session 3] <role>: <原文>` |

**探索集**（分层 120 题）：检索 recall@20 = 97.1%（167/172 个证据话轮）；R2 89% / FULL 88% / ORACLE 91%；预注册 H2（时序+知识更新合并 R2−R0 ≥ +5pp 且 CI 下界 > 0）因样本小（35 题）判不成立。

**确认集**（171 题，与探索集不相交，跑前预注册）：

| 对比 | 完整案例 n=161 | 保守（失败行记错）n=171 |
|---|---|---|
| R2 − R0 | **+14.9pp** [+8.7, +21.7] | **+18.1pp** [+11.1, +25.1] |
| 其中 temporal-reasoning | **+25.2pp** [+16.5, +35.0]（60%→85%）| +29.2pp [+20.4, +38.1] |
| 其中 knowledge-update | −3.4pp [−10.3, +3.4]（91–95%，无差异）| 同 |
| R1 − R0（只加说话人）| −1.9pp [−6.2, +1.9] | −1.8pp [−5.8, +2.3] |
| R2 − FULL | −4.3pp [−9.9, +0.6] | −5.8pp [−11.1, −0.6] |
| ORACLE − R2 | +8.1pp [+3.1, +13.7] | +9.4pp [+4.1, +14.6] |

结论：**日期（及会话号）是时序题的决定性信息；说话人标签无效；知识更新题不依赖它。**

### 不能夸大的地方

- **排序混杂（已核对代码）**：探针中 R0/R1/R2 三种渲染都把命中话轮**按时间顺序**排列（`spike_lib.to_hits_text` 按话轮序号排），而不是按检索分数。所以 R2−R0 的差只来自日期文字，这一点成立；但“生产应按什么序渲染”和“时间序本身贡献多少”探针都没测过，生产路径按 `final_score` 排。E1 的 R2c 臂专门拆这一项。

- 14 条失败（推理预算耗尽，空回答）全部出现在 temporal-reasoning 的 R0/R1，即无日期的臂。已按两种口径报告，结论一致。它本身也是信号：没有日期时推理模型会“想不出来”。
- R2 渲染同时带了日期与会话号，**未拆开消融**哪一项起作用。
- 评测里每个话轮自带真实 `observed_at`；**生产摄入不具备**（见下“硬约束”）。
- 单一 backbone；FULL 与 R2 之间仍有 5.8pp 差距，时序题上 R2 与 ORACLE 仍差约 11pp。

### 对 v2 前提的修正

“检索不是瓶颈”只在 k=20 成立。生产聊天默认 `recall_k=6`，同批 50 题重测：

| k | 证据话轮召回 | 全证据题占比 |
|---|---|---|
| 3 | 70.6% (60/85) | 63.6% |
| 6（生产默认）| 84.7% (72/85) | 80.0% |
| 10 | 88.2% | 83.6% |
| 20 | 97.6% (83/85) | 96.4% |

所以召回深度仍是一个独立的、可调的因素，但它的修复是调参与评测，不是新建索引层。v2 的 chunk 投影层依旧没有立项依据。

## 范围

做：
1. 让召回上下文里的每条记忆行带上**事件发生的时间**（及来源会话标识）。
2. 让生产摄入能带上真实时间（见硬约束）。
3. 拆分消融，确认哪一项起作用；并在真实 Starling 检索路径上验证收益可迁移。

不做：chunk 投影层、FTS5、开放谓词事实层、`episode_gist`、第二套检索器、对右脑任何子系统的改动。多会话聚合缺口（R2 比 FULL 低约 15pp，探索集里归因到 2/20 题的证据补全）另立诊断，不在此文档内承诺机制。

## 现状（已核对代码）

- `render_line`（`src/retrieval/context_pack.cpp`）只输出 `[LABEL] subject predicate object (conf X, holder H)`，不含任何时间。仅当声明合同开启（`semantic_claim_json` 非空）时才附 `source_time` / `event_time` 等字段，默认关闭。
- `StatementRow` 已有 `observed_at`、`valid_from`、`valid_to`（`include/starling/retrieval/statement_row.hpp`），数据已在，只是没渲染。
- Working Set 的 `relevant_memories` 区同样渲染无时间的行。
- 聊天 prompt（`converse_prepare`）不含“当前日期”。评测官方模板的每个 prompt 都含 `Current Date: {question_date}`，R0/R2 两臂都有，所以本探针的 +25pp **不是**当前日期缺失造成的，而是相对日期缺失造成的。生产的 prompt 两者都缺，两者都需要补。
- 摄入：`Extractor` 把语句 `observed_at` 取为 engram 的 `created_at`（`extractor.cpp:706`）；Dashboard 摄入线程对历史转录传 `now=None`（`engine.py` 约 891 行），即**写入时刻**，不是对话真实发生时刻。

## 硬约束：时间必须是真实的

渲染一个错误的日期比不渲染更糟：回答模型会据此做错误的日期运算，并且显得有依据。因此：

- 渲染用 `event_time_start`（若有），否则 `observed_at`；只有当该值可信时才渲染。
- “可信”的定义：来自来源话轮自带的时间（`claim_source_turn_payload` 合同的 `observed_at`）或调用方显式传入的 `now`。若 `observed_at` 只是写入时刻回退值，**不渲染日期**，并在回执里记 `time_basis=ingest_time_unrendered`，让上游可见。
- 需要一个明确的“可信度”标记随语句保存（见方案）。否则无法区分。

## 方案

### 渲染（C++，`context_pack`）

`render_line` 在 `[LABEL]` 之后、`subject` 之前加入时间前缀，格式沿用探针中验证有效的形式：

`[FACT] [2023-04-10 Mon 17:50] Bob responsible_for auth (conf 0.93, holder Alice)`

- 时间字段由新的 `RenderOptions{ render_time, time_zone_policy }` 控制，默认值见“开关与兼容”。
- 会话标识：仅当来源语句的 `source_spans`/`semantic_claim_json.source_turn` 带有 `session_id` 时渲染，格式 `session s`。无则省略，不伪造。
- 所有格式化在 C++；Python 只透传 `RenderOptions`（遵守 C++/Python 边界裁定）。
- 渲染顺序：右脑 8 标签行的排序语义不变（仍按 final_score），时间只是行内字段，不改变排序。**不**强制按时间重排；是否对 HISTORY intent 按时间序渲染，留给消融（探针里命中是按时间序渲染的，这是一个未拆开的混杂因素，见消融）。

### 当前日期

`converse_prepare` 的 prompt 加入 `Current Date: <created_at 日期>`（取自 `ConverseParams.created_at_iso8601`，即 `as_of`，已有，非 wall clock），格式与官方模板一致。没有它，相对时间（“上周”“三个月前”）无法算。

### 摄入端时间

- 为语句增加一个可信度来源标记，记录 `observed_at` 是 `source_turn`（话轮自带）/ `caller_supplied`（调用方显式传入）/ `ingest_time`（写入时刻回退）。做法倾向于不新增 `statements` 列：复用现有 `temporal_anchor_json`（设计文档 §3.3 已有 `TemporalAnchor{anchor_kind, resolved_by}`，P1 即可空，序列化时按 `source_spans[0].observed_at` 推导）。需 Codex 评审确认这是否合适，或是否需要迁移。
- Dashboard 转录摄入：已核对，Claude Code transcript 的行带 `timestamp`（本机抽样 24/31 行），`ingest_filter.clean_turns` 只读 `type` 与 `message`，时间戳被丢；`engine.py` 摄入循环以 `now=None` 调 `remember`，即写入时刻。需让清洗后的每个话轮保留时间。**但有一个未解决的结构问题**：`chunk_dialogue` 把多个话轮合并成一个 chunk 再 `remember`，一个 chunk 跨多个时间点，而 `remember` 只接受一个 `created_at`，语句的 `observed_at` 因此只能取一个值。可选做法（待评审）：(a) 按时间边界切 chunk，使一个 chunk 内的话轮同日；(b) chunk 内给每个话轮带行内时间前缀，让抽取模型自己解析事件日期（走 `semantic_claim_contract` 的 `source_turn` 通道，已有 `observed_at` 字段）；(c) 取 chunk 首个话轮时间并接受粒度损失。三者对 E2 的效果不同，不预先选定。

### 开关与兼容

- `RenderOptions.render_time` 默认 **关**，保持所有现有测试与历史评测回放的字节级行为；通过 `PlannerQuery`/`ConverseParams` 与 Dashboard 配置开启。
- 默认是否翻开由评测结果决定（见验收），不在本设计里预设。
- 现有 pinning 测试涉及渲染文本：`test_context_pack.cpp`、`test_retrieval_planner.cpp`、`test_recall_fence.cpp`、`test_evidence_answer.cpp` 及若干 Python 评测测试。默认关闭保证它们不动；新增测试覆盖开启路径。

## 评测与验收

沿用既有纪律（同 backbone、预注册、开发/保留切分、判据在跑前固定）。

### E1 拆分消融（评测侧，复用探针）

在确认集 171 题上增加三臂，只改渲染、不动检索：
- `R2a` = 只日期：`- [2023-04-10 Mon 17:50] <role>: <原文>`
- `R2b` = 只会话号：`- [session 3] <role>: <原文>`
- `R2c` = R2 但**不按时间序**渲染（保持检索分数序），拆开“排序”混杂因素。

预注册：若 `R2a ≈ R2`（|差| < 3pp 且 CI 含 0）则会话号可省；若 `R2c` 比 R2 低 ≥ 5pp 且 CI 排除 0，则时间序渲染也是必要成分，需写入渲染规则。

### E2 可迁移性（真实 Starling 路径）

在生产路径 `RetrievalPlanner + Context Pack` 上验证：用 `remember` 灌入带真实时间的话轮（`created_at` = 话轮时间），`converse`/`query` 开启 `render_time` 前后各跑一遍。这一项回答“评测臂的收益能否迁移到生产”，探针本身**不回答**这一点：探针里的 R0/R2 都是平铺的 `said` 行，不经三元组抽取，三元组化后 `object` 经抽取可能丢失日期相关细节。

预注册判据（时序题，确认集同一批题）：开启后相对关闭 ≥ +5pp 且 CI 下界 > 0 才算迁移成功；否则如实记为“收益未迁移”，并回到抽取层分析，不得改判据。

### E3 召回深度

在 `recall_k ∈ {6, 10, 20}` 上对 E2 重复，量化召回深度与渲染的交互。生产默认 6 时证据召回仅 84.7%，这是独立的、可调的损失。

### 守护

- 全量 ctest 与 pytest 全绿；新增渲染单元测试（含时间缺失、不可信时间不渲染、UTC 与时区、非法时间字符串、会话号缺失）。
- SocialMemBench 1031 题来源路径读数（0.7825）不得下降（该路径不走 `render_line`，应不受影响；以实测为准）。
- 渲染增加的上下文字节数必报（探针中约 +9.7%）。
- 弃答与 `[ABSTAIN]` 行为不变。

## 风险与待评审点

1. **时间可信度**是本设计最危险的地方：错误日期比无日期更糟。可信度标记放在哪、默认如何处理旧数据（全是 `ingest_time`）、旧库迁移是否需要，须评审。
2. **探针与生产路径的差异**：探针渲染的是原文行，生产渲染的是三元组行；三元组 `object` 常是短名词，加上日期是否同样有效是 E2 要回答的，不能默认成立。如果 E2 不成立，说明时序题需要的是“带日期的原文”，则又回到“生产路径要有原文通道”的问题，届时需重新评估，**不预先承诺**。
3. **单一 backbone / 单次采样 / 同模型 judge**：收益是否随 backbone 变化未知。
4. **FULL 仍高于 R2**：渲染不是全部；剩余缺口（尤其时序、多会话聚合）未被本设计解决。
5. **相对时间的歧义**：话轮里的“昨天”“下周”要靠话轮日期解析；日期渲染使其可算，但抽取层是否保留了这类词需在 E2 检查。
6. **隐私**：日期不是新增敏感信息，但渲染在 perspective mask 之后，行为不变。

## 路线

| 阶段 | 内容 |
|---|---|
| E1（评测侧，约 0.5 周）| 拆分消融三臂，确认集 171 题，沿用探针 |
| E2（约 1.5 周）| 生产路径：`RenderOptions`、`render_line` 改动、`Current Date`、摄入时间保真（Dashboard 转录保留时间戳）、可信度标记；E2 评测 |
| E3（约 0.5 周）| 召回深度扫描 `recall_k` |
| 之后 | 阶段 B：换到 headroom 更大的基准（MemoryAgentBench 冲突消解、BEAM），沿用本设计的渲染为默认配置 |

## 待实施前确认

1. 时间可信度标记的落点（复用 `temporal_anchor_json` 还是新增列）。
2. E2 的数据来源：用探针的 171 题灌入生产 `remember`（每题约 490 个话轮，三通道抽取成本高）还是用较小子集；需评估成本。
3. 是否对 HISTORY intent 默认时间序渲染（由 E1 的 R2c 决定）。
