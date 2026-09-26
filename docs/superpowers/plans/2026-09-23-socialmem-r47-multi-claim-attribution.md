<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.7 多声明与第一人称归属实施计划

> 所有设计文档使用中文；主修复顺序为文档、RED 测试、C++ 实现、回归、离线和真实评测。Python 只做 binding、编排和结果读取。状态：本轮完成，未晋升；详见[中文诊断报告](../../eval/2026-09-23-socialmem-r47-multi-claim-attribution.md)。

## 任务一：设计与同步

- [x] 编写 `2026-09-23-socialmem-r47-multi-claim-attribution-design.md`。
- [x] 同步当前系统设计、检索子系统设计、claim contract 和中文技术报告。
- [x] 记录 R4.6 作为基线，不覆盖 R4.6 封存结果。

## 任务二：C++ RED

- [x] 同一来源多 claim 保留知识车道资格；反转写入/读取顺序用例于实评后补齐，并在旧核心验证 RED，见下方流程记录。
- [x] 第一人称关于另一关注人物的知识 claim 进入归属车道。
- [x] 无关第一人称 claim 不进入归属车道；此负例初始已通过。
- [x] 无效 sibling 不遮蔽有效 claim；跨 holder、跨 tenant、source_turn 不一致的既有边界回归通过。

## 任务三：C++ GREEN

- [x] 将 Source/ClaimView 改为 claim 集合并保留拒绝审计。
- [x] 车道判定改为 claim 集合 `any_of`，不重复占用 source 名额。
- [x] 加入多 claim 诊断字段，保持 v2-v5 和 legacy 不变。

## 任务四：验证

- [x] RED 日志证明测试确实捕获旧行为。
- [x] 定向 C++、完整 CTest、本机 HTTP CTest、Python binding 回归。
- [x] 重建并记录核心哈希。
- [x] 复用固定 R3.5 父数据库做零网络离线闭环；逐库 SHA256 核实与 R4.6 相同。

## 任务五：评估决策

- [x] 生成 R4.7 离线及真实诊断报告，比较 R4.5/R4.6/R4.7 候选 source 集合。
- [x] 离线门禁通过后，沿用既有授权完成独立真实双臂评测，547/600 HTTP、零重试。
- [x] 不以 claim 加载量、来源覆盖率或离线替身准确率代替 QA 质量；记录同 prompt 分层与同答案裁判翻转，不晋升。
- [x] 更新设计与技术报告入口、设计规格和实施计划的当前状态入口，保留历史正文口径。


## R4.7 当前验证记录

- 初始 RED 日志：`build/r47_claim_red.log`，3 项失败、1 项边界负例通过；初始 GREEN 日志为 `build/r47_claim_green.log`。
- 流程补充：反向写入顺序/无效 sibling/单人物自述 5 项是在实评后补齐。临时以封存 R4.6 源码构建，5/5 失败（`build/r47_order_red.log`），恢复 R4.7 后 5/5 通过（`build/r47_order_green.log`）；最终源码与受评封存源码 SHA256 相同。此项不描述为原始测试先行步骤。
- 最终定向 C++ 54/54（`build/r47_final_focused.log`）；最终 CTest 共 1276 项，1253 通过、23 环境跳过（`build/r47_final_ctest.log`）。本机 HTTP 30/30 覆盖跳过项；Python 71/71。早期 1271 项准确口径为 1248 通过、23 跳过。
- 离线目录：`build/socialmem_20260923_r47_multi_claim_offline`，57 题、114 终态、0 网络请求；多 claim 诊断与最终车道渲染一致，替身答案不作为分数证据。
- 真实目录：`build/socialmem_20260923_r47_multi_claim_real`，retrieval 19/57、native_answer 17/57，0 技术失败，锚点 48/104，547 次请求。相对 R4.6 +4/+2 题，无法确认稳定代码收益。
- 核心 SHA256：`bc0831fc9263aa7f6fa2c709f7fcf8bbcaffe77b853057f0d2ce7239a17594fb`；构建、安装、封存版本一致。
- R4.6 真实、R4.7 真实和离线封存最终核验通过。封存后补充分析外置于 `build/socialmem_20260923_r47_diagnostics/`，包含哈希清单，不重写原始评分与完成封存。
