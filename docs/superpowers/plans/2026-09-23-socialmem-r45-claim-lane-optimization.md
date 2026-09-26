<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.5 声明车道选路优化实施计划

> 先完成中文设计，再写 RED 测试，最后实现 C++。Python 只做 binding、编排和结果读取。

## 任务一：设计和证据边界

- [x] 记录 R4.5 的新鲜检索/回答结果、metadata 回连计数和未晋升结论。
- [x] 写入中文设计文档 `2026-09-23-socialmem-r45-claim-lane-optimization-design.md`。
- [x] 复核 `system_design.md`、`13_retrieval.md`、技术报告和 claim contract 入口的字段说明。

## 任务二：C++ RED 测试

- [x] 有效 claim fixture 断言三类 claim 车道计数和 `claim_lane_fallbacks` 字段。
- [x] source limit、预算不足和重复 source 下，claim 计数只在 `take()` 成功时增加。
- [x] source_turn 不一致、跨 holder 和跨 tenant 的声明不进入 claim 车道。
- [x] 断言 `lane_selected_rendered` 与 `selection_trace.selected_by` 一致。

## 任务三：C++ 实现

- [x] 在 `profile_sources` 中加入仅 v6 生效的 claim 资格优先级和配额；成员同组保留相关性次序。
- [x] 新增三类 claim 选中计数与 fallback 计数；旧策略字段和行为保持不变。
- [x] 保留现有 tenant/holder/source_turn/时间/哈希/擦除/字节预算校验。

## 任务四：验证

- [x] 定向 CTest 与完整 CTest。
- [x] Python R4.4/R4.5 合同回归。
- [x] 独立离线冻结验证，确认零网络和诊断闭环。

## 任务五：真实复评和报告

- [x] 新建独立 R4.6 目录，不覆盖 R4.4/R4.5 封存目录。
- [x] 运行检索、回答、裁判、verify、analyze，记录核心 SHA、模型、端点、请求账本和 bootstrap 设置。
- [x] 更新中文评测报告、计划复选框和当前设计入口；明确是否晋升。


## R4.6 本轮核验记录

- 新增 7 个真实入库 claim 行为测试，先观察 6 项预期失败，再完成 C++ 最小修复。RED 日志 `build/r46_claim_lanes_red.log`；GREEN 日志 `build/r46_claim_lanes_green.log`。
- 定向 C++ 44/44；完整 CTest 1266 项，1243 通过、23 环境跳过；重装新核心后 Python 71/71。
- 独立离线目录 `build/socialmem_20260923_r46_claim_lanes_offline`：57 recalls、114 terminals、0 网络请求、封存核验通过；57 题 lane_selected 与最终渲染计数一致。离线替身答案不作为准确率。
- 核心 SHA256：`b86cbac787d697e2847e6bb64074292b4d4e1269f4583e6a527006b7ecaf0261`。

- 补跑本机 HTTP 相关 CTest 30/30，覆盖默认沙箱跳过项；只使用 localhost，没有增加 DashScope 请求。

- R4.6 真实闭环：两臂均 15/57，546/600 HTTP，检索臂 1 次截断，其余技术正常；所有判分变化发生在相同 prompt 题目，无可归因质量提升，不晋升。见 [中文报告](../../eval/2026-09-23-socialmem-r46-claim-lanes.md)。
