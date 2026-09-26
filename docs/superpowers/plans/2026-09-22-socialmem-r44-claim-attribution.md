<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.4 结构化声明归属与状态车道实施计划

> 本计划按“中文设计 → RED 测试 → C++ 实现 → 离线验证 → 真实评测”执行。Python binding 只传递策略和原生结果，核心语义全部在 C++。

**目标：** 将已校验的 `semantic_claim_json` metadata 接入来源选择，形成可审计的状态、信念归属和成员覆盖车道，并修复 consolidated source 与原始 claim engram 之间的安全回连。

**范围：** 新增实验策略 `evidence_profile_v6`；保留 v2/v3/v4/v5、旧评测目录和生产默认；不在 Python 复制 metadata 解析或角色判断。

## 任务一：文档与冻结边界

- [x] 写入中文设计 [R4.4 设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。
- [x] 写入本实施计划，定义 C++/Python 边界、字段和验收门槛。
- [x] 更新 R4.4 中文设计入口，记录真实评测结论和 consolidated source 回连边界；核对相对链接。

## 任务二：C++ RED 测试

文件：`tests/cpp/test_source_retriever.cpp`、`tests/cpp/test_evidence_answer.cpp`。

- [ ] 增加带有效 `semantic_claim_json` 的 early/late fixture；运行定向测试，预期 v6 策略被拒绝或 metadata 计数为零。
- [ ] 增加 consolidated source 与原始 claim engram 不同的 fixture；`source_turn` 五元组完全一致时必须加载 metadata。
- [ ] 增加 `source_turn` 的 speaker、turn_id、session_id、turn_index、observed_at 任一不一致、跨 tenant 或跨 holder的拒绝断言，并检查回连原因计数。
- [ ] 增加归属 fixture，断言不一致 `attributed_to` 不进入 attribution lane。
- [ ] 增加错误 `engram_ref/clause_id`、跨 tenant fixture，断言只记录拒绝原因。
- [ ] 增加 `lane_selected_rendered` 与 `selection_trace.selected_by` 一致性断言。

## 任务三：Python RED 合同

文件：`tests/python/test_socialmem_r44.py`。

- [ ] 断言 `_core` 与运行器接受 `evidence_profile_v6`。
- [ ] 断言运行器没有 metadata 解析和角色关键词表，Python 只读取原生 diagnostics。
- [ ] 运行 pytest，先确认失败原因是新策略或字段缺失。

## 任务四：C++ GREEN 实现

文件：`include/starling/retrieval/source_retriever.hpp`、`src/retrieval/source_retriever.cpp`、`scripts/run_socialmem_r43.py`（复制为 v6 运行器）、必要的 binding 注册文件。

- [ ] 在 C++ `Source` 中增加内部 claim metadata 视图和加载拒绝原因。
- [ ] 新增 tenant/holder 约束的声明回连查询，复用 `claim_evidence_error`，先按 source_turn 定位 consolidated source，再按原始 `source_span` 精确匹配声明。
- [ ] 增加 `claim_reconciliation_attempted/succeeded` 及按原因诊断字段；禁止静默跳过无法回连的声明。
- [ ] 在 v6 三条车道中使用 metadata 确定性评分，统一从成功 `take()` 的 trace 计算 rendered 计数。
- [ ] 更新策略校验、binding 和离线合同；旧策略保持原分支。

## 任务五：验证

- [ ] 运行 `cmake --build build -j2 --target test_source_retriever test_evidence_answer`。
- [ ] 运行定向 CTest、完整 CTest 和 R4.x Python 合同。
- [ ] 运行不发网络的独立离线 v6 prepare/check/replay，确认账本为零请求。
- [ ] 核对设计与实现字段一致，扫描文档中的未完成标记和 Python 重复语义。

## 任务六：真实评测与收口

- [ ] 新建独立 R4.4 目录，执行 `prepare/check` 后再发起 DashScope 请求。
- [ ] 完成检索、回答、裁判、verify、analysis 和 immutable SQLite 诊断。
- [ ] 生成中文评测报告；不满足门槛则明确 `promoted=false`。
- [ ] 更新 320 份导航、计划复选框和技术报告入口。
