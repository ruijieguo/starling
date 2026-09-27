<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.5 声明车道选路优化设计

日期：2026-09-23。状态：已完成实现与 R4.6 真实复评，不晋升生产；只针对实验策略 `evidence_profile_v6`，不改变生产默认和已封存评测。

## 1. 诊断结论

R4.5 外网检索阶段确认 consolidated source 与原始 claim engram 的安全回连已经生效：57 题均为 `ok`，`claim_reconciliation_attempted=1142`、`claim_reconciliation_succeeded=1142`、`claim_metadata_rejected=0`。完整两臂评测使用 547/600 次 HTTP 请求，检索臂 14/57，原生回答臂 18/57；相对父 R3.5 分别为 -2 和 +2 题，paired 检索与回答差异为 +4 题，bootstrap 区间为 [1.89, 11.63] 个百分点。该结果仍是 57 题开发诊断，不晋升生产。

当前短板不是 metadata 无法读取，而是 metadata 没有稳定地影响最终选路：

1. `profile_sources` 先无条件用第一条排序候选占用 `relevance` 名额，再尝试状态、归属、成员车道；claim 车道因此经常在上下文预算或 source limit 下失去名额。
2. `state_chain_claim_selected`、`belief_attribution_claim_selected`、`member_claim_selected` 没有输出，无法区分“车道选中了普通 source”还是“车道选中了已校验 claim source”。
3. R4.5 source anchor 命中为 48/104，父 R3.5 为 53/104；metadata 加载量增加没有直接转化为答案质量，必须先让选路行为可审计，再评估排序收益。

## 2. 目标和非目标

目标：

- 只在 C++ 的 `evidence_profile_v6` 分支中，让已通过 `claim_evidence_error` 且完成 source_turn 回连的声明影响候选排序和车道配额。
- 对状态链、信念归属、成员覆盖分别记录 claim 选中计数，并由最终 `selection_trace` 重新核对 rendered 计数。
- 保持 tenant、holder、source_turn 五元组、时间、哈希、擦除和上下文字节预算的安全边界。

非目标：

- 不在 Python 复制 predicate、semantic_family、actor 或 attributed_to 规则。
- 不修改 v2/v3/v4/v5、legacy、生产默认和已封存 R4.4/R4.5 目录。
- 不新增 LLM 请求，不把 claim metadata 原文直接注入回答上下文。
- 不把 metadata 加载量或来源覆盖率当作答案准确率提升的替代指标。

## 3. 方案

### 3.1 候选方案

1. **继续扩大关键词表**：改动小，但无法保证 actor、attributed_to 与 source speaker 一致，也不能解释选路事实。
2. **Python 读取诊断后重排**：能够快速试验，但会复制核心语义并破坏 C++/binding 边界。
3. **C++ claim-aware 排序与配额（采用）**：在现有 `Source` 内部视图上计算确定性车道资格优先级，先为被问题触发的 claim 车道保留名额，再用 relevance 补齐；Python 只读取诊断和 prompt。

### 3.2 排序与配额

仅当 `source_strategy == "evidence_profile_v6"` 时启用：

1. 计算候选的内部车道资格（布尔优先级，不引入无标定的浮点加权分数）。基础条件是 `claim_loaded=true`；状态链还要求 actor 等于 source speaker，归属车道还要求 belief/knowledge/uncertainty 族或对应 predicate，成员车道还要求 claim source speaker 等于该成员。
2. 对问题触发的车道，在 `relevance` 之前先按确定性顺序取候选：状态链最多 3 条，归属最多 2 条，每个成员最多 1 条。已有的 source limit、UTF-8 字节预算和去重规则继续由 `take()` 统一执行。
3. 状态和归属车道只接收合格 claim；不足部分记录缺口，由后续普通来源车道补齐。成员车道先尝试该成员的有效 claim，再尝试该成员普通来源；回退不能把未经校验的 claim 当作 metadata 候选。
4. 对没有触发车道的问题保持原 v6 排序，只补充计数，避免无关题改变上下文。
5. 成员车道稳定划分有效 claim 与普通来源，同组保留现有 topic overlap、BM25 score、时间和 source id 排序；状态链仍按早晚时间取端点。归属车道保持候选相关性次序。同一输入可复现。

### 3.3 诊断字段

在现有 `evidence_profile` 中新增：

- `state_chain_claim_selected`
- `belief_attribution_claim_selected`
- `member_claim_selected`
- `claim_lane_fallbacks`

前三项只在 `take()` 成功且 `claim_loaded=true` 时递增。v6 的 `lane_selected` 每次成功只由 `take()` 递增一次；共享来源可以满足多个覆盖要求，但只归属首次选中它的车道。`claim_lane_fallbacks` 精确定义为成员车道成功新增普通来源的次数：已经被其他车道选中的来源、无可用来源、source limit 或字节预算拒绝、relevance 补齐都不计回退。状态和归属车道严格使用 claim，因此不增加此字段。`lane_selected_rendered` 仍从最终 `selection_trace.selected_by` 重新计算；任何预算拒绝、重复 source 或未回连 claim 都不能计入成功。

## 4. 数据流与边界

`ObserverRetriever::run` 先完成 tenant/holder/时间/完整性过滤，再由 `load_claim_views` 建立 source 与 claim 的安全索引。`profile_sources` 只接收这个内部视图，计算车道资格优先级并调用现有 `take()`。最终上下文仍渲染原始 source 行和已有 statement 行；metadata 只影响排序和诊断。Python binding 不新增语义代码。

回连失败、字段缺失、歧义、跨 tenant/holder 或 source_turn 不一致时，候选可作为普通 source 保留，但不得进入 claim lane，且必须保留现有拒绝原因计数。

## 5. 测试与验收

按“文档 → RED 测试 → C++ 实现 → 回归 → 真实评测”执行：

- C++ RED：构造有效 claim fixture，断言三类 claim 计数和 claim-aware 选路字段当前缺失；构造 source limit/预算不足、跨 holder、source_turn 不一致 fixture，断言 claim 不计入车道。
- C++ GREEN：定向 `SourceProfile`、`SourceRecovery`、`SourceCoverage` 回归；完整 CTest。
- Python 合同：确认策略透传、binding 无第二份语义规则，运行既有 R4.4 合同。
- 离线验证：冻结输入无网络，检查 `claim_metadata_loaded`、三类 claim 计数、拒绝原因和 `lane_selected_rendered` 一致性。
- 真实复评：新建独立目录，固定 57 题、两臂共用一次检索、qwen3.8-27b、零重试、600 HTTP。只有技术失败不增加且 paired 结果满足既定统计门槛时才讨论晋升，否则保留为开发诊断。


## 6. R4.6 补充行为验证（2026-09-23）

有效 claim 必须经过原生解析、remember 和 Bus 写入再回连；测试涵盖归属独占名额、成员相关性排序、共享 claim 不重复计数、普通成员来源回退、source limit、UTF-8 整行预算、tenant/holder 隔离。历史 R4.5 结果来自车道优先级改动前的封存核心；R4.6 才评估当前选路优化。

## 7. R4.6 验收结论

行为验收与完整冻结评测已完成；两臂均 15/57，546 次 HTTP。相对 R4.5 所有分数变化出现在相同 prompt 的题目，变更 prompt 队列净变化为 0；没有证明本优化提高准确率。保留实验分支和正确性修复，不提升为生产默认。详见 [中文评测报告](../../eval/2026-09-23-socialmem-r46-claim-lanes.md)。
