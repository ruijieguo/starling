# 形态 S 阶段 B 验收：BEAM-100K 预注册

**冻结于 2026-10-22，在任何 BEAM 题目被作答、任何检索结果被查看之前。** 本文件随代码提交；
跑后不改。设计依据 `docs/superpowers/specs/2026-10-19-form-s-source-lane-design.md` §10.1；
阶段 A 结果见 `docs/superpowers/plans/2026-10-21-form-s-source-lane-impl.md` Task 13。

## 0. 地位

这是左脑原文 lane 的**上线门槛**。BEAM-100K 此前从未在本项目使用过。**只跑一次**：判据未达成时
lane 保持关闭，**不得**在本数据上调整阈值、改判据或重跑。

## 1. 用户裁定（2026-10-22）

- 判据档位：**中等**（§6）。
- 右脑建库：**只抽取 user 话轮**，分块沿用生产的 8000 字符（§3.3）。左脑不受影响，写入全部话轮。

## 2. 数据

| 项 | 值 |
|---|---|
| 来源 | BEAM（Tavakoli et al., ICLR 2026，`mohammadtavakoli78/BEAM`）100K 档 |
| 文件 | `100K.parquet` sha256 `c0519be2…0075a78ace`；转 JSON 后 `beam100k.json` sha256 `5b413dd5…86dd3354a` |
| 规模 | 20 个会话 × 20 题 = **400 题**；10 种能力各 40 题 |
| 证据 | 355 题带 `source_chat_ids`（会话内全局话轮号，已核实连续）；abstention 40 题无证据；preference 1 题、summarization 4 题无证据 |
| 时序 | `temporal_reasoning` **40 题** |
| 场景 | 每个会话 3 批，共 90 批，**每批都有时间锚点**（形如 `March-15-2024`） |

数据产物：`build/dual_brain_20261017/spike/beam_b/`（gitignored）。

## 3. 建库（每个会话一个独立库）

### 3.1 左脑（原文 lane）

- 每批一次 `retain_source_turns`（v3）：`session_id = "beam<会话号>-b<批号>"`，`speaker` = 原 role
  （`user` / `assistant`），`audience = ["assistant", "user"]`，`provenance = "source_time"`。
- `observed_at` = 该批时间锚点日期 00:00:00Z + 批内写入序号（秒）。
- 正文去掉数据集产物后缀 `->-> x,y`（5732 话轮中 2191 个带它；题目文本中 0 个）。去后为空的话轮不写。
  记录"写入序号 → 全局话轮号"的映射，用于判定证据。
- 嵌入：DashScope `text-embedding-v4`，1024 维，经 `EmbeddingWorker` source 分支。

### 3.2 嵌入

同一个 `EmbeddingWorker` 同时嵌入原文 unit（source 分支）与右脑语句（语句分支），同一个嵌入器。
反复 tick 直到两条分支都无可做的事。

### 3.3 右脑（语句）

- **只用 user 话轮**（用户裁定）。每批的 user 话轮经生产的 `chunk_dialogue(max_chars=8000)` 切块，
  每块走生产的三相 remember（prepare → extract_all → commit_all），`holder_id = "user"`，
  `interlocutor = "assistant"`，`ExtractionConfig()` 默认提示（即生产提示）。
- 抽取模型 `deepseek-v4-pro` @ tokenkey，`thinking_type = "disabled"`（commit 4762342；网关不遵守
  `enable_thinking=false`，2026-10-22 复测），`max_tokens = 8192`，`timeout_ms = 120000`
  ——与线上抽取配置一致，只多了真正关闭推理这一项。
- 抽取在核心重试后仍失败的块：记录、不额外重试、不剔除题目。报告语句总数与失败块数。

## 4. 作答（每题两臂，同一个库）

两臂都走**生产对话路径** `memory_converse_prepare`（commit 785f7f9 起支持 `source_lane`），
`holder_id = "user"`，`message` = 题目原文，`created_at = 2099-01-01T00:00:00Z`（不做时间截断——
BEAM 的题目在所有会话之后提出），`recall_k = 10`：

| 臂 | `source_lane` |
|---|---|
| **ON** | `SourceLaneDeps(tau_source = 0.56, k_max = 200, chunk_byte_budget = 8000)` |
| **OFF** | 不设（右脑语句单独） |

`tau_source = 0.56` 取自阶段 A，**不在 BEAM 上调**。

作答：用 `ConversePrepared.prompt`（生产围栏提示原样）调 `deepseek-v4-pro`，temperature 0，
`thinking = {type: disabled}`，`max_tokens = 2048`。planner 拒答时同样生成（与生产一致）。

## 5. 度量

### 5.1 证据渲染（门槛用，只看 ON 臂）

对 ON 臂以与 `converse_prepare` **完全相同的 `PlannerQuery`** 直接调用 `RetrievalPlanner::run`，
取 `source_entries`。**一致性校验**：其 `context_pack` 必须与 `ConversePrepared.context_pack`
逐字节相同，不同则该题记为"未渲染"并单列计数。

- **M1**（355 题）：渲染出的 `source_entries` 中至少一条对应题目 `source_chat_ids`（展平后）中的
  某个话轮 → 记为"证据已渲染"。被字节预算截掉、或 planner 拒答，均不算渲染。
- **M2**（40 题）：M1 限于 `temporal_reasoning`。

### 5.2 弃答题错误作答（门槛用，只看 ON 臂）

- **M3**（40 题）：abstention 题的官方 rubric 得分 = 0 → 记为"错误作答"
  （官方代码对分数做 `int` 截断，0.5 也计为 0；即部分弃答亦算答错，口径偏保守）。

### 5.3 裁判（官方口径）

- 提示：官方 `unified_llm_judge_base_prompt` **原文**（sha256 `593373c6…6c56b7f5`，3781 字符），
  每条 rubric 单独判 1.0 / 0.5 / 0.0，题目得分 = rubric 平均。
- 裁判模型：**`deepseek-v4-pro`**（与作答同 backbone），temperature 0，thinking disabled。
  **与论文所用裁判不同**，数字不与论文表直接可比。
- 解析失败：先按 JSON 修复解析；仍失败记 0 分（保守）并计数。
- **分数截断**：除 event_ordering 外，官方代码写 `score += int(...)`，0.5 被截为 0。主报按官方代码
  （截断）；另报按 0.5 计的浮点版本。event_ordering 官方另有 Kendall tau 对齐分数——本次**不实现**，
  只报 rubric 分。

### 5.4 描述性（不参与门槛）

每种能力 ON / OFF 两臂的官方得分（截断版与浮点版），及配对差值的 bootstrap 区间（按题重采样
5000 次，种子 20261022）。

## 6. 判据（中等档，用户 2026-10-22 选定）

区间一律为 Wilson 95%。

| 编号 | 条件 | 等价于 |
|---|---|---|
| **C1** | M1 下界 ≥ **65%**（n = 355） | 实测 ≥ 249 / 355（70.1%） |
| **C2** | M2 下界 ≥ **55%**（n = 40） | 实测 ≥ 29 / 40（72.5%） |
| **C3** | M3 上界 ≤ **25%**（n = 40） | 错误作答 ≤ 4 / 40 |

**决定规则：**
- **C1 且 C3 同时成立** → lane 可以开启；
- 否则 lane 保持关闭；
- **C2 单独决定时序意图**：C2 不成立时，即便 C1、C3 成立，lane 也不对时序类意图开启。

## 7. 已知偏差（跑前写明）

1. **右脑只抽 user 话轮**：语句与原文的竞争变弱 → C1 轻微偏松；ON/OFF 对照会**高估**左脑增益。
   因此 §5.4 的对照只作描述，**不作对外 SOTA 数字**。
2. **感知过滤在 BEAM 上退化**：单主体，`audience` 恒为 {user, assistant}，过滤等于全部可见。
   本阶段**不验证**感知授权（spec §11 风险 8）。
3. **`tau_source` 来自 LongMemEval**：BEAM 是技术类长对话，分数分布可能不同，这正是本阶段要测的。
4. **`recall_k = 10`**：生产 `converse` 默认 6；本阶段与阶段 A、spec 默认保持一致。lane 开启时
   若沿用生产默认 6，渲染率可能低于本次测得值。
5. **裁判模型不同于论文**（§5.3）。

## 8. 不做的事

- 不调 `tau_source`、不改判据、不重跑；
- 不剔除任何题目（建库失败、解析失败一律按"未渲染 / 0 分"计）；
- 不看任何题目的作答或检索结果后再改本文件。

## 9. 预算

约 1e7 tokens（右脑抽取约 2-3e6 + 两臂作答约 3e6 + 逐条 rubric 裁判约 4e6），在 2026-10-21 批准的
1-2e7 内。嵌入走 DashScope，单独计。
