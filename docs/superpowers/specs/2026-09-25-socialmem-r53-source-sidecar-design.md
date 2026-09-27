<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.3 来源预算与结构化声明 sidecar 设计

日期：2026-09-25

状态：已完成设计→RED→C++ 实现→两次真实检索及分析；最终锚点 v6 51/104、v8 45/104，门槛未通过，QA 未启动，不晋升。

## 1. 背景与问题诊断

R5.2 在同一来源快照上完成了 `evidence_profile_v6` 与 `evidence_profile_v7` 的 fresh 双臂对照。legacy 策略由 v6 的 22/57 降至 v7 的 12/57，`grounded_memory_v1` 由 24/57 降至 11/57；两种策略都没有 v7 改善题，因此 v7 不晋升，开发对照继续使用 v6，产品默认仍为 bm25。

R5.1 的冻结上下文显示，v6 的 57/57 题为 `source_count=10, statement_count=0`，v7 的 57/57 题为 `source_count=7, statement_count=3`。已确认的名额压缩机制是 C++ `ObserverRetriever` 先计算 `source_limit=7`，随后把声明追加到同一个 `k=10` 名额中。这一历史构成同时受到嵌入健康差异影响：本轮核查 v6 的 345 次嵌入尝试全部降级，v7 没有该降级。健康 v6 也为 7 来源+3 声明，所以不能单因归因于 v7；退化题中还出现了与题目主线弱相关的结构化声明。

本设计只解决来源集合被声明名额挤压、低相关 semantic link 抢占直接来源以及未充分回链的声明进入上下文这三个检索层问题。它不把来源召回提升直接解释为回答质量提升，也不改变谓词目录、抽取协议、评分器或生产默认策略。

## 2. 目标与非目标

目标：

1. 在 `k=10` 的 SocialMemBench 查询中，先完成来源选择，再在剩余字节预算内追加受限结构化声明；结构化声明不得减少来源名额。
2. 让低相关的 semantic link 不能压过直接词法/主题相关来源，同时保留没有直接词法命中时的 semantic 回退能力。
3. 只把能够回链到已选来源、满足当前 tenant/holder/as-of 约束且与问题相关的声明加入 prompt，并为每一条拒绝保留可审计原因。
4. 保持 Python binding 只透传 `source_strategy` 和结果，不在 Python 重复实现选择、回链、相关性或预算逻辑。
5. 先完成来源锚点与 sidecar 检索诊断（真实查询嵌入单列请求成本），再决定是否使用 qwen3.8-27B 做 fresh answer/judge 对照。

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
3. 完整问题的来源 BM25 分数；
4. 在上述相关性相当时，已通过回链的 semantic link 分数，最后按稳定时间键排序；
5. semantic link 只在没有直接相关候选时作为回退。

这样，低相关 semantic link 不能在来源名额内无条件压过直接来源；同时，完全没有词法命中的问题仍可使用已认证的 semantic link。

### 4.2 sidecar 准入合同

sidecar 选择必须同时满足以下条件：

- statement 存在可解析且唯一的 `source_span`；
- span 的 `(engram_ref, clause_id)` 位于当前 tenant、holder、as-of 过滤后的来源池中；
- 对应来源已进入最终 source 集合；
- statement 的对象/主题与去除功能词和关注人名后的问题内容词有交集；仅姓名、谓词或和自身来源重叠不能准入；
- statement 通过现有 tenant、holder、review、时间和证据完整性校验；
- 追加该声明后不超过 `max_context_bytes`，且 sidecar 数量不超过 3。

不满足任一条件的声明不渲染，`sidecar_rejections` 按 `missing_or_invalid_source_span`、`source_span_not_in_authorized_pool`、`source_not_selected`、`low_statement_relevance`、`budget_rejected` 等原因计数。声明是否被拒绝不改变来源选择结果。已在 RetrievalPlanner 因 malformed_claim/source hash/span 等证据错误被过滤的声明，记录在 receipts.candidate_counts.dropped_by_claim_evidence 与 evidence_profile.claim_rejection_reasons，不重复进入 sidecar_selection_order；sidecar_rejections 只覆盖到达此阶段的候选。source_span.clause_id 与顶层 clause_id 冲突时，v8 严格拒绝回链，不能使用同话轮元数据替代 span 一致性。

### 4.3 输出与诊断

v8 继续返回既有字段，并增加以下诊断字段：

- `source_diagnostics.evidence_profile.source_limit`：实际来源上限；
- `source_diagnostics.evidence_profile.source_limit_satisfied`：来源数是否达到 k；
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

只有离线门槛通过，才在独立输出目录追加 qwen3.8-27B fresh answer/judge。fresh 评测固定题目、来源快照、提示、模型配置、请求账本和裁判协议；报告 legacy/native 两种 policy 的共同正常子集、四格转移、network bootstrap、技术失败和成本。v8 只有在至少一臂共同正常子集净增 5 题且 network bootstrap 95% 区间下界大于 0 时才具备晋升资格，否则继续使用 v6 开发对照；产品默认保持 bm25。

本轮结果仅限 57 题开发 cohort，不外推完整 SocialMemBench、保留集或生产质量。

## 7.1 可执行细化（书面确认后）

- 直接相关候选定义为去除问题功能词及关注人名后，主题 BM25 大于 0 的来源。先选直接相关候选；组内按主体匹配、主题分、完整问题 BM25、有效 semantic link 分、时间稳定键排序。低相关声明车道不能越过此阶段。仅在无直接相关候选时先选一个有效 semantic anchor，再从已选 anchor 的连续邻域补来源，最后复用有证据约束的 v6 车道补齐剩余名额。
- 声明相关性必须来自对象/主题与问题内容词的交集；仅和自己的来源文本重叠、仅有匹配谓词或姓名，均不能单独准入。该条件是可复现词法过滤，不是语义正确率认证。
- 字节分项包含各行前置换行，来源先渲染；因此两个分项之和严格等于最终 block 字节数。保留旧 source_quota_satisfied 的 min_source_items 含义；另增 source_limit_satisfied 表示 source_count==k，候选不足不伪称配额满足。
- sources 模式仍检索声明用于语义回链，但 statement_count 必须为 0；hybrid 与 sources 的来源集合必须一致。
- R5.1 保存了真实向量库，没有保存查询向量。回执审计进一步发现其 v6 的 345 次嵌入尝试全部降级，v7 无该降级；R5.2 历史 QA 分数保留，但策略差值归因受此混杂限制。不能用 Stub 查询真实向量库来宣称质量。无网络回放只能验证纯来源/降级控制；真实同库语义复评需要按既有 DashScope 授权获取查询嵌入，并单列 embedding 请求数。本轮三组为 v6 hybrid、v8 hybrid、v8 sources，每组 57 题、345 次嵌入，最多 1035 次、零重试；v8 sources 直接验证 sidecar 对来源集合/字节没有影响，任何降级不得标为健康语义比较。先检索、后审计、再决定 answer/judge，绝不把 embedding 请求写成零请求。
- 抽样相关性 0.8 门槛必须提供逐条语义审阅证据；词法准入率不能代替该指标。无 sidecar 时标记无法评估，不能将空分母记为 100%。
- 本轮 QA 若通过离线门槛，只新跑 v6/v8 双臂、两种 policy；v7 保留历史诊断，避免三臂超过 R5.2 的 500 次请求预算。57 题开发门槛仅决定是否扩大验证，不自动晋升产品默认。

## 8. 实施顺序

1. 本设计文档及检索/系统设计入口同步完成并自审。
2. 用户审阅本设计文档并确认。
3. 编写并运行 C++/Python RED 测试，确认测试因 v8 尚未实现而失败。
4. 在 C++ 实现 v8 最小闭环和诊断字段，保持 Python 仅 binding。
5. 运行专项回归、离线回放与完整审计。
6. 仅在离线门槛通过后进行 fresh QA/judge，并撰写中文结果报告。

## 9. 实施审查与复核边界

首轮三组检索已完成 171 条健康回执、1035 次嵌入。健康 v6 实际为 7 来源+3 声明，v8 为 10 来源+0–3 声明；此前“v6 一定有 10 来源”的结论只适用于嵌入全部降级的 R5.1 上下文。首轮锚点 v6 51/104、v8 44/104，来源控制组零差异，因锚点门槛失败未运行 QA。

随后代码审查复现邻居本身有 semantic link 时被事件车道排除的问题。v8 只先选一个语义锚点，所以不能沿用 v7“已关联即已选”的假设。按既定邻接合同补充 RED 后，v8 改为只排除已选邻居，v7 行为保持。本轮另建 `_verified` 输出目录补跑相同三组，额外最多 1035 次查询嵌入、零重试；累计上限 2070 次，不包含 answer/judge。首轮冻结核心和回执保留，最终结论只引用对应核心。

sidecar 的代理逐条审阅用于定位误召回，必须明确标注评审主体，不能写成用户人工标注或自动替代原人工 0.8 门槛。

## 10. 最终结果

最终冻结核心 `dbfd87c635d2ea4cd188cbba29e5569f6a8668191a9145d7cda7ab58cb733509`：完整 C++ 1304/1304、来源专项60/60、相关Python87/87。最终三组171/171健康，来源控制零差异；锚点v6 51/104、v8 45/104，未通过门槛。两轮合计2070次嵌入、回答/裁判各0。68次sidecar逐条代理审阅18次有实质帮助、67次有来源支持，非人工标注，不能替代人工0.8门槛。详见[完整诊断与后续方案](../../eval/2026-09-25-socialmem-r53-source-sidecar.md)。
