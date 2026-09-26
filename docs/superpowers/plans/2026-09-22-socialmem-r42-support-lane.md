<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.2 支持性第三方证据实施计划

设计：[R4.2 中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)。继续遵循中文文档、RED 测试、C++ 实现、离线验证、真实评测顺序。

## 任务一：文档

- [x] 编写 R4.2 中文设计与计划。
- [x] 同步 320 份设计入口并记录 R4.1 封存结果。

## 任务二：测试

- [x] 新增 `SourceProfileV4` 支持车道、认知触发、纯时间禁用和关系回归测试。
- [x] 保存 RED，随后运行相关 Source*/EvidenceAnswer 回归。

## 任务三：实现

- [x] 在 C++ 增加 `evidence_profile_v4` 校验和 support lane；v2/v3、binding 和生产默认保持不变。
- [x] 运行完整 CTest、R4.0/R4.1/R4.2 Python 合同和离线冻结流程。

## 任务四：评测

- [x] 创建独立 R4.2 driver/目录，prepare/check 后执行真实检索和双臂回答。
- [x] 封存 114 终态、账本、coverage、token、失败和配对 bootstrap 结果。
- [x] 编写中文 R4.2 评测报告；未达门槛，保持实验状态并给出下一轮短板。

## 任务五：封存后复核

- [x] 重新运行 `python scripts/run_socialmem_r42.py verify --work build/socialmem_20260922_r42_support_lane_real`，确认 114 个任务、57 次检索和账本无未决请求。
- [x] 以 immutable SQLite 独立计算精确来源命中、结构化声明回指、网络分层、技术失败和 token 使用，输出 `build/socialmem_r42_checks/diagnostics.json`。
- [x] 更新本设计、320 份中文设计入口和 R4.2 评测报告；生产默认与历史封存目录保持不变。
