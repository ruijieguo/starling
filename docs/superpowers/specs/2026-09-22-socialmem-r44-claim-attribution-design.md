<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.4 结构化声明归属与状态车道设计

日期：2026-09-22。状态：设计已确认；R4.4 真实评测已完成，当前进入 consolidated source 与原始 claim 回连修复阶段；不修改生产默认。

## 1. 问题与目标

R4.3 的 `evidence_profile_v5` 能记录状态链、信念归属和全体成员缺口，但选择逻辑主要依赖来源文本关键词。R4.3 真实评测为检索臂 17/57、原生回答臂 19/57；相对 R4.2 两臂均为 0 净变化。评测显示来源命中和技术稳定性没有转化为答案质量，且设计承诺的 `semantic_claim_json` metadata 尚未进入 v5 选择器。

R4.4 的目标是在 C++ 核心中把已经通过声明证据校验的结构化 metadata 接入来源选择：`predicate`、`semantic_family`、`actor`、`attributed_to`、`topic`、`source_turn` 和 `source_span` 必须与真实来源行关联后才能参与状态、归属和成员车道。Python 只传策略和调用原生接口，不复制语义规则。

非目标：不新增 LLM 请求、不从问题或答案制造声明、不修改 v4/v5 和任何已封存目录、不把 metadata 命中当作 QA 提升、不改变生产默认。

## 2. 方案选择

候选方案有三种：

1. 继续扩展关键词表。改动小，但无法解决 speaker/actor/attributed_to 混淆，也不能验证出处完整性。
2. 在 Python 侧读取 SQLite 声明后重新排序。能快速试验，但违反核心逻辑集中在 C++ 的边界，且会产生 binding 与核心双份语义。
3. **在 C++ 来源选择器中做声明回连与角色评分（采用）**。读取同一 tenant 的已校验 statement，按 `source_span.engram_ref`、`clause_id` 回连来源，使用确定性 metadata 评分；Python 只接收诊断和提示结果。该方案能复用现有 claim evidence 校验，并保持旧策略分支不变。

## 3. C++ 数据流

1. `ObserverRetriever::run` 读取已通过 tenant、holder、时间、擦除和 hash 检查的 source turn。
2. 对每一条 source，按 `engram_ref/clause_id` 查询同 tenant、同 holder 的 `statements`；只接受 `claim_evidence_error` 为空且 `source_span` 与来源一致的声明。
3. 将声明 metadata 放入内部 `Source` 角色视图，不把完整 JSON 无条件放入回答上下文。上下文仍只渲染原始 source 行和已有 statement 行。
4. `evidence_profile_v6` 使用 metadata 与 source 的联合评分：
   - `state_chain`：`actor == focused_holder`、topic 与问题重合、`semantic_family` 属于 preference/plan/affect/uncertainty/behavior 的声明优先；按 `source_turn.observed_at/session_id/turn_index` 形成 early、trigger_or_response、late；
   - `attribution`：保留真实 source speaker；只有 `attributed_to`、actor 和 topic 能解释“谁知道/相信谁的什么”的声明进入归属车道；缺任何关键字段则进入 `belief_attribution_missing`；
   - `member`：每个 focused holder 最多一条声明或来源；声明缺失时保留来源，来源也缺失时记录 `member_missing`；
   - 其他来源仍受 source limit、UTF-8 字节预算、holder/tenant 隔离和 `selection_trace.rendered` 约束。
5. `lane_selected` 只在 `take()` 成功时增加；最终诊断从 `selection_trace.selected_by` 重新计算并输出 `lane_selected_rendered`，禁止计数与渲染集合分离。

### 3.1 consolidated source 与原始 claim 的安全回连

评测冻结库允许按 holder 将多轮来源合并为一个 consolidated engram。此时
`source_documents.engram_ref` 可能指向 consolidated engram，而声明中的
`semantic_claim_json.source_span.engram_ref` 仍指向产生该声明的原始逐话轮 engram。
因此，单纯用两个 engram id 拼接键会把合法声明静默丢弃。回连规则调整为：

1. 先以 source document 的 `source_turn`（`speaker`、`turn_id`、`session_id`、
   `turn_index`、`observed_at`）定位 consolidated payload 中的权威话轮。
2. 在同一 tenant、同一 holder、同一 source speaker 范围内，允许声明的原始
   `source_span.engram_ref` 与 consolidated `engram_ref` 不同；原始 engram 仍须
   通过 `claim_evidence_error` 的 hash、租户、擦除状态、source unit、时间和契约校验。
3. `clause_id`、source speaker 和完整 `source_turn` 必须一致；任一字段不一致、
   跨 tenant 或跨 holder 均拒绝，并记录可审计的 `claim_reconciliation_*` 原因。
4. 回连只扩展“已授权 source 行到已校验 claim”的索引关系，不把未经校验的
   声明文本放入回答上下文，也不改变旧策略和 Python binding 的语义。

诊断至少包含 `claim_metadata_loaded`、`claim_metadata_rejected`、
`claim_reconciliation_attempted`、`claim_reconciliation_succeeded` 和按原因计数的
`claim_reconciliation_rejection_reasons`。这组字段用于确认优化确实生效，不作为答案
质量提升的替代指标。

## 4. 接口与兼容性

新增实验策略名 `evidence_profile_v6`，新增 `claim_metadata_loaded`、`claim_metadata_rejected`、`state_chain_claim_selected`、`belief_attribution_claim_selected`、`member_claim_selected`、`lane_selected_rendered` 字段。v2/v3/v4/v5 和 legacy 行为保持原有分支。`compact_grounded_memory_answer_prompt` 继续复用，不新增 Python 语义函数。

声明回连失败按原因分类为 `claim_missing`、`claim_unavailable`、`claim_mismatch`，不会把不完整 metadata 当作已验证事实；来源仍可作为普通 source 候选，但不能获得 metadata 角色分数。

## 5. 测试顺序

先写 RED 测试，再实现：

- C++ fixture 用真实 `semantic_claim_json` 与 `source_span` 建立 early/late、belief attribution、member 三类声明；另建 consolidated source 与原始 claim engram 不同的回连 fixture；
- v6 能报告 metadata 加载数、拒绝原因和 `lane_selected_rendered`；
- 错误 `engram_ref`、错误 `clause_id`、跨 tenant、`source_turn` 任一字段不一致、`attributed_to` 与 source speaker 不一致的声明不能进入角色车道；
- source limit、上下文字节预算、旧策略输出和未知时间行为回归不变；
- Python 合同只检查 v6 策略透传、binding 接口和没有第二份语义词表；
- 运行定向 C++/Python 测试后，再运行完整 CTest 与离线冻结验证。

## 6. 评测门槛与回滚

真实评测使用独立目录、固定 57 题、两臂共用一次检索、qwen3.8-27b、零重试、600 HTTP。只有相对 R3.5 共同正常题净增至少 5、网络 bootstrap 95% 区间下界大于 0、技术失败不增加且 metadata 拒绝原因可审计时，才讨论晋升。否则保留 v6 开发诊断，生产继续使用既有安全策略。
