# SocialMemBench R5.3 来源预算与结构化声明 sidecar 设计

日期：2026-09-25

状态：已确认设计，等待 RED 测试与实现。

## 1. 背景与问题诊断

R5.2 在同一来源快照上完成了 `evidence_profile_v6` 与 `evidence_profile_v7` 的 fresh 双臂对照。legacy 策略由 v6 的 22/57 降至 v7 的 12/57，`grounded_memory_v1` 由 24/57 降至 11/57；两种策略都没有 v7 改善题，因此 v7 不晋升，默认继续使用 v6。

R5.1 的冻结上下文显示，v6 的 57/57 题为 `source_count=10, statement_count=0`，v7 的 57/57 题为 `source_count=7, statement_count=3`。根因不是结构化声明本身被拒绝，而是 C++ `ObserverRetriever` 先计算 `source_limit=7`，随后把声明追加到同一个 `k=10` 名额中。v7 的 semantic/event 车道因此挤出了三条原始来源；退化题中还出现了与题目主线弱相关的结构化声明。

本设计只解决来源集合被声明名额挤压、低相关 semantic link 抢占直接来源以及未充分回链的声明进入上下文这三个检索层问题。它不把来源召回提升直接解释为回答质量提升，也不改变谓词目录、抽取协议、评分器或生产默认策略。

## 2. 目标与非目标

目标：

1. 在 `k=10` 的 SocialMemBench 查询中，先完成来源选择，再在剩余字节预算内追加受限结构化声明；结构化声明不得减少来源名额。
2. 让低相关的 semantic link 不能压过直接词法/主题相关来源，同时保留没有直接词法命中时的 semantic 回退能力。
3. 只把能够回链到已选来源、满足当前 tenant/holder/as-of 约束且与问题相关的声明加入 prompt，并为每一条拒绝保留可审计原因。
4. 保持 Python binding 只透传 `source_strategy` 和结果，不在 Python 重复实现选择、回链、相关性或预算逻辑。
5. 先完成零模型请求的离线来源锚点与 sidecar 诊断，再决定是否使用 qwen3.8-27B 做 fresh answer/judge 对照。

非目标：

- 不修改 `evidence_profile_v6` 的默认行为，不把 v8 直接设为生产默认。
- 不增加新的谓词、语义族、抽取提示或声明持久化字段。
- 不放宽 tenant、holder、时间、擦除、source hash、source span 和 context byte 约束。
- 不把 statement 数量、来源命中或离线回放结果当作 QA/F1 提升证据。

## 3. 方案比较与选择

### 3.1 方案 A：v8 独立 sidecar（采用）

新增实验策略 `evidence_profile_v8`。`ObserverQuery.k` 在 v8 中只表示来源上限；来源选择结束后，C++ 最多追加三条结构化声明 sidecar。sidecar 不占来源名额，仍与来源共享 `max_context_bytes` 硬上限；字节不足时优先保留来源并跳过 sidecar。现有 Python 调用面不新增业务判断，只把策略字符串传给 C++。

优点是直接修复 R5.2 已确认的名额竞争，同时可以通过独立计数和拒绝原因观察声明质量。代价是 `block` 可能同时包含来源行和声明行，评测报告必须分别统计 `source_count` 与 `statement_count`。

### 3.2 方案 B：只调整 v7 排序

保留共享 `k`，降低 semantic link 的排序优先级。改动较小，但声明仍会占据最终名额，不能保证原始来源不被挤出，因此不能覆盖 R5.2 的主要退化机制。

### 3.3 方案 C：把 k 扩大到 13

通过更大的总名额同时容纳来源和声明。该方案会改变上下文长度和历史 `k` 契约，无法保证来源固定保留 10 条，也难以区分声明挤压与整体容量变化，故不采用。

## 4. C++ 架构与数据流

实现位置为 `src/retrieval/source_retriever.cpp`，查询结构仍由 `include/starling/retrieval/source_retriever.hpp` 的 `ObserverQuery` 承载；Python binding 只需接受新的策略字符串，不复制核心逻辑。

v8 的执行顺序固定为：

1. 按现有流程加载并过滤来源，执行 tenant、holder、时间、擦除、哈希和未知时间策略。
2. 加载通过 `claim_evidence_error` 校验的声明，按 statement source span 建立候选回链；未通过证据合同的声明只进入拒绝诊断。
3. 在来源候选内部计算直接相关性。直接相关性由问题主题词重叠、来源 BM25 分数和主体匹配组成；已验证 semantic link 只作为同等直接相关候选的后续排序依据。
4. 对没有直接相关候选的查询，才允许 semantic link 作为回退来源；从保留下来的 semantic anchor 派生 event 邻接来源，邻接来源不能反向挤出直接来源。
5. 以 `source_limit=q.k` 选择来源。`min_source_items` 仍作为兼容性诊断字段，但 v8 的来源上限不再由 statement 数量扣减。
6. 来源集合确定后，在剩余字节预算内从结构化声明中最多选择三条 sidecar。每条声明必须回链到已选来源，并通过声明相关性门槛；声明选择失败不改变来源集合。
7. C++ 按来源、sidecar 的固定顺序渲染 `block`，分别更新 `source_count`、`statement_count`、`source_context_bytes` 和 `statement_context_bytes`，并生成选择与拒绝诊断。

### 4.1 来源排序合同

v8 不使用未经标定的浮点阈值替代现有证据合同。排序优先级为：

1. tenant/holder/as-of 等硬过滤后的直接主体匹配；
2. 问题主题词的 `topic_score` 与词法重叠；
3. 来源 BM25 分数与时间稳定排序；
4. 在上述相关性相当时，已通过回链的 semantic link 分数；
5. semantic link 只在没有直接相关候选时作为回退。

这样，低相关 semantic link 不能在来源名额内无条件压过直接来源；同时，完全没有词法命中的问题仍可使用已认证的 semantic link。

### 4.2 sidecar 准入合同

sidecar 选择必须同时满足以下条件：

- statement 存在可解析且唯一的 `source_span`；
- span 的 `(engram_ref, clause_id)` 位于当前 tenant、holder、as-of 过滤后的来源池中；
- 对应来源已进入最终 source 集合；
- statement 的谓词、对象或主题与问题词项或对应来源文本存在相关性，或者命中当前问题识别出的状态、归属、关系车道；
- statement 通过现有 tenant、holder、review、时间和证据完整性校验；
- 追加该声明后不超过 `max_context_bytes`，且 sidecar 数量不超过 3。

不满足任一条件的声明不渲染，`statement_rejections` 按 `missing_or_invalid_source_span`、`source_span_not_in_authorized_pool`、`source_not_selected`、`low_statement_relevance`、`budget_rejected` 等原因计数。声明是否被拒绝不改变来源选择结果。

### 4.3 输出与诊断

v8 继续返回既有字段，并增加以下诊断字段：

- `source_diagnostics.evidence_profile.source_limit`：实际来源上限；
- `source_diagnostics.evidence_profile.source_quota_satisfied`：来源是否达到上限或已无可用来源；
- `source_diagnostics.evidence_profile.sidecar_limit`：固定为 3；
- `source_diagnostics.evidence_profile.sidecar_selected`：实际渲染的声明数；
- `source_diagnostics.evidence_profile.sidecar_rejections`：按原因计数；
- `source_diagnostics.evidence_profile.source_selection_order`：来源选择顺序及车道；
- `source_diagnostics.evidence_profile.sidecar_selection_order`：声明回链和相关性诊断。

`selected` 继续表示来源数，避免破坏现有评测脚本；声明数量只由 `statement_count` 表示。`context_bytes` 仍等于最终 `block` 的 UTF-8 字节数，两个分项字节数之和必须相等。

## 5. 不变量与兼容性

- `bm25`、`focused`、`focused_window`、`focused_dialogue`、`focused_coverage`、v2–v7 的行为和输出契约保持不变。
- v8 的 sidecar 只在 `mode=hybrid` 生效；`mode=sources` 只返回来源，`mode=statements` 的原有限制不放宽。
- 任何 binding 都不能自行决定声明车道、source span、相关性或预算；这些判断只有 C++ 实现。
- 来源行仍使用 `[SOURCE]`，声明行仍使用原有结构化标签；来源原文不是已认证事实，声明也不能脱离 source span 独立成立。
- tenant、holder、as-of、review、擦除、source hash、span 和 UTF-8 字节预算失败均 fail closed。
- 当 sidecar 全部被拒绝或字节不足时，v8 仍返回完整可用的来源集合，不因声明失败而整体弃答。

## 6. 测试设计

测试先于实现，在 `tests/cpp/test_source_retriever.cpp` 增加 v8 的 RED 用例：

1. `source_count` 达到 `k` 时，结构化声明仍只能追加到 sidecar，不能替换来源。
2. 低相关 semantic link 与直接词法来源同时存在时，直接来源先入选；没有直接来源时 semantic link 才回退生效。
3. 缺失 source span、跨 tenant/holder、未选中来源或低相关声明均被拒绝，并记录具体原因。
4. sidecar 超过三条或剩余字节不足时，只减少 `statement_count`，来源集合和来源字节预算不回退。
5. as-of、holder、tenant 和 source hash 约束在 v8 下与 v6 一致。
6. 结果的 `context_bytes`、分项字节数、source_refs、statement_ids 和 block 行数彼此一致，重复项被拒绝。

Python 只增加一个 binding 透传回归，确认 `source_strategy="evidence_profile_v8"` 到达 C++；不在 Python 重写任何准入或排序逻辑。

## 7. 评测与晋升门槛

实现后先运行 C++/Python 专项测试和同库离线回放，比较 v6、v7、v8 的金标来源锚点召回、来源数、sidecar 精度、拒绝原因和上下文哈希。离线门槛为：v8 来源锚点召回不低于 v6；v8 不得出现来源数因 sidecar 下降；人工抽样的 sidecar 相关性不得低于 0.8；所有硬过滤与预算审计通过。

只有离线门槛通过，才在独立输出目录追加 qwen3.8-27B fresh answer/judge。fresh 评测固定题目、来源快照、提示、模型配置、请求账本和裁判协议；报告 legacy/native 两种 policy 的共同正常子集、四格转移、network bootstrap、技术失败和成本。v8 只有在至少一臂共同正常子集净增 5 题且 network bootstrap 95% 区间下界大于 0 时才具备晋升资格，否则继续保持 v6 默认。

本轮结果仅限 57 题开发 cohort，不外推完整 SocialMemBench、保留集或生产质量。

## 8. 实施顺序

1. 本设计文档及检索/系统设计入口同步完成并自审。
2. 用户审阅本设计文档并确认。
3. 编写并运行 C++/Python RED 测试，确认测试因 v8 尚未实现而失败。
4. 在 C++ 实现 v8 最小闭环和诊断字段，保持 Python 仅 binding。
5. 运行专项回归、离线回放与完整审计。
6. 仅在离线门槛通过后进行 fresh QA/judge，并撰写中文结果报告。
