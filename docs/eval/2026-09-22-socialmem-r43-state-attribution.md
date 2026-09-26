# SocialMemBench R4.3 事件状态与信念归属评测报告

日期：2026-09-22。评测目录：`build/socialmem_20260922_r43_state_attribution_real_net`。状态：开发诊断，未晋升生产。

## 1. 结论

R4.3 在固定 57 题、7 个 scope、6 个 network、两臂配对协议下完成 114 个终态。检索臂为 **17/57（29.82%）**，原生回答臂为 **19/57（33.33%）**。相对 R4.2，两臂都是 0 净变化；原生回答臂有 3 题新正确、3 题退步，检索臂有 4 题新正确、4 题退步。相对 R3.5，检索臂为 16→17（+1），原生回答臂为 16→19（+3，+5.26 个百分点）；网络 bootstrap 95% 区间分别为 `[-5.66,+7.79]` 和 `[+1.67,+9.76]` 个百分点。R4.3 不满足“相对 R3.5 至少净增 5 题且检索臂区间下界大于 0”的晋升条件，`promoted=false`。

技术链路完整：57/57 检索为 `ok`，114/114 回答与裁判终态为 `ok`，无 degraded retrieval、无回答失败、无裁判失败。实际 HTTP 请求为 547/600：query embedding 345、answer 114、judge 88；账本 committed=547、reserved=0、charged_upper=0，剩余 53 次。首次失败目录因沙箱 DNS 受限而全部 degraded，未重试；本报告只使用独立网络目录的结果。

## 2. 分层结果

| 维度 | 检索臂 | 原生回答臂 |
|---|---:|---:|
| 全部 57 题 | 17/57（29.82%） | 19/57（33.33%） |
| 选择题 13 题 | 8/13（61.54%） | 8/13（61.54%） |
| 短答 8 题 | 2/8（25.00%） | 1/8（12.50%） |
| 长答 36 题 | 7/36（19.44%） | 10/36（27.78%） |

按 query type，Q4 最稳定（两臂 5/6），Q3 仍为 0/2，Q5 为 2/7，Q8 为检索 3/16、原生 4/16。R4.3 的提升集中在少数题，不能外推为普遍能力。

## 3. 证据覆盖与车道诊断

精确来源锚点按 `(speaker_display_name, turn_id)` 匹配。R3.5 为 53/104，R4.3 为 51/104；声明出处并集为 R3.5 60/104、R4.3 58/104。来源命中没有提升，说明状态车道的当前实现没有稳定增加可用证据。

R4.3 诊断中状态车道请求 26 题，其中 17 题仍有角色缺口；归属车道请求 26 题，其中 6 题有缺口；全体成员车道请求 6 题，均记录了成员覆盖结果。代码审计显示 v5 主要使用来源文本词法（如 `prefer`、`because`、`know`），没有把已存储的 `semantic_claim_json` 的 predicate、semantic_family、actor、attributed_to 和 source_turn 作为选择依据；设计中关于“使用结构化 claim metadata”的承诺尚未兑现。另有 24 题的 `lane_selected` 计数与最终 `selection_trace.rendered/selected_by` 不完全一致，诊断字段不能直接作为选择事实使用。

## 4. 能力短板

1. 变化题仍缺少可审计的“早期状态—触发/回应—后期状态”结构。Q8 变化题只有 3/16 或 4/16 正确，表明有来源不等于形成状态链。
2. 信念归属仍可能把真实 speaker、信念持有者和被谈论人物混在一起。关键词命中只能发现候选，不能证明归属。
3. 全体成员题虽然输出缺口，但成员覆盖没有与结构化声明的 actor/predicate 对齐，难以区分 stated preference、observed behavior 和 unknown。
4. 输出压缩解决了本轮技术失败，但没有带来总分提升。R4.3 无截断、无超时，却仍与 R4.2 持平，下一轮应优先修复证据选择语义，而不是继续增加回答容量。

## 5. 下一轮方案

先中文设计，再 RED 测试，最后 C++ 实现。新增实验策略 `evidence_profile_v6`：

- 在 C++ 来源加载阶段按 `engram_ref/clause_id` 回连同库中的结构化声明；
- 用 predicate、semantic_family、actor、attributed_to、source_turn、topic 形成确定性角色评分；
- 状态车道优先选择 actor 与 focused holder 一致且 topic 相容的早/晚声明，再选择有 response/decision/change 语义的中间声明；
- 归属车道要求结构化 `attributed_to`、真实 source_turn speaker 和被谈论人物关系一致；
- 成员车道逐 holder 区分声明、来源和缺口，并在 diagnostics 中统一 rendered 事实；
- 保留 v5/v4/v1 回滚路径，不修改生产默认。

只有在新轮次相对 R3.5 达到事前晋升门槛后，才讨论生产默认变更。

## 6. 证据索引

- 评测分析：[analysis.json](../../build/socialmem_20260922_r43_state_attribution_real_net/analysis.json)
- 诊断：[diagnostics.json](../../build/socialmem_r43_checks/diagnostics.json)
- 配对与车道复核：[paired_and_roles.json](../../build/socialmem_r43_checks/paired_and_roles.json)
- 运行器：[run_socialmem_r43.py](../../scripts/run_socialmem_r43.py)
