<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

# SocialMemBench R6.0 真实探测与八库重建设计

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **执行后更正（2026-09-26）**：实际为候选单臂两完整scope探测2/2，随后八库重建3/8；并未执行本文预定三holder旧/新交错。该偏差不能追认为预注册方案；本文以下保留原设计，实际证据与准入缺口见[R6.0诊断](../../eval/2026-09-26-socialmem-r60-build-diagnosis.md)。133题仍无baseline。

## 目标

验证 `target_units_statement_first_v1` 是否能减少 R5.9 Tomas 一类的声明字段错层，同时保持语义准入、来源绑定、费用账本和失败回执合同不变。探测只回答协议健康和有来源声明保留两个前置问题；它不能单独证明 SocialMemBench QA 提升。

## 固定身份

- 候选 core 使用 R6.0 C++/binding 的新 SHA；R5.9 frozen core `ead8046e4a28d257f3429d865523c1af1f6275fd0cb1ba98d8fa8023894d6fef` 只作为历史对照，不覆盖、不改标。
- 提取模型固定为 DashScope `qwen3.8-27b`，embedding 固定为现有 R5.9 配置；endpoint、temperature、thinking、输出 token 上限和 HTTP retry 继承已审计的 R5.9 配置。
- 来源、holder、批次、target clause id 和 admission 契约来自已封存的 R5.9 cohort；运行目录必须全新创建，禁止续跑 `build/socialmem_20260926_r59_expanded`。
- 候选目标 profile 必须为 `target_units_statement_first_v1`；旧 profile `target_units_v1` 仅允许出现在历史 R5.9/R5.8 产物和旧核心的 provenance 中。

## 交错探测

第一阶段只执行 Tomas、Mum、Kwame 三个完整 holder。每个 holder 的全部 source units 和全部 batch 按固定顺序完成 belief 抽取、一次协议纠错（如需）、native schema、admission、commit 和账本结算。旧/新 profile 使用隔离 frozen runtime 和不同输出根；不复用旧 raw answer，也不只请求曾失败的 batch。

每个 terminal 同时记录：

1. HTTP 状态、finish reason、raw completion、raw HTTP、token usage、native attempt 数和 retry 数；
2. schema failure、admission rejection、semantic rejection、保留 claim 数及来源 clause id；
3. `semantic_claim_json`、source hash、batch plan/profile/prompt hash 与账本 reservation 的完整性；
4. 是否有至少一个带有效来源的 admitted claim。合法空数组是技术健康但不满足晋级门槛的语义结果。

候选晋级门槛为：三名 holder 的全部 batch 均完成固定终态，HTTP/账本/回执可审计，没有未解释的 schema 或 persistence failure，并且至少一个 holder 保留有来源 admitted claim。任一门槛失败就保存阴性结果，停止八库重建，单独分析布局是否足够。

## 八库 fresh 重建与评分

探测通过后，用同一个候选 core 和新 R6.0 runtime 从全新目录顺序重建 8 个 scope。任何 scope 失败都停止后续 scope，并保留原始回执、账本和 failure audit；不把部分完成标成完整 build。只有 8/8 healthy、所有 scope 有来源审计且数据库冻结后，才运行 266 检索请求和 532 fresh QA 请求。

评分阶段固定使用既定 133 题、两检索臂和两回答政策。结果按“来源缺失、语义遗漏、检索选择、回答错误、judge 不稳定、协议/账本失败”分层统计，并与 R5.9 的 1/8 技术失败和 R5.4 57 题历史结果分开。没有 8/8 build 就只能报告技术终态和暂无 baseline 分数。

## 失败处理

- 字段仍错层：保留原始 response 和费用，确认严格 parser 拒绝，不在 Python 搬字段；仅在独立后续设计中考虑更明确的纠错路径。
- 协议健康但 admitted claim 为零：标记“技术成功、语义未晋级”，不强行补写 claim、不修改分母。
- 账本、raw HTTP 或 native receipt 不完整：按未知消费保守计费，停止该 scope，不能重试到成功为止。
- provider 网络/凭据错误：记录 endpoint、HTTP/curl/执行确定性和请求计数；不将外部故障归因于声明布局。

## 证据与文档

真实请求前保存候选 core、源码清单、配置、prompt/profile 及测试日志 SHA。真实阶段结束后更新本文件、R6.0 声明布局设计、R6.0 实施计划和相关中文状态入口；所有报告标明 provider、模型、语料哈希、运行根和证据级别。
