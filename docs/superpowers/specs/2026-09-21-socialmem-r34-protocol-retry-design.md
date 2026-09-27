<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench R3.4 结构化抽取协议有限重试设计

日期：2026-09-21

## 1. 诊断依据

R3.3 的 57 道题全部启动，但两个 scope 在 C++ 结构化抽取阶段失败，分别造成 1 道和 18 道题不能进入回答。固定回执显示：Josh 的模型响应含重复 `time_text` 键，被严格 envelope 校验拒绝；Margot 的响应使用目录外谓词 `believes`，被 schema 校验拒绝。两类失败都发生在模型输出协议层，不能归因于来源检索或 QA。

## 2. 目标与边界

本轮只提高结构化抽取的协议可用性，目标是让一次可纠正的 envelope/schema 错误有第二次合法输出机会。严格 parser、谓词目录、scope guard、admission、证据持久化、回答/裁判协议、题目和生产默认均保持不变。重复键不被修补，目录外谓词不被改名，原始响应必须保留。

## 3. 原生方案

在 C++ `ValidationPolicy` 增加 `claim_protocol_retry_budget`，默认值为 0，并约束为 0 或 1。`semantic_claim_contract` 路径第一次解析产生 `envelope_failure` 或 `schema_failure` 时，在预算尚未用尽的情况下重新调用同一个结构化合同接口。第二次 prompt 由 C++ 重新生成完整源文本，并追加不含模型原文的纠错提示，要求严格遵守唯一 key、规范谓词目录和顶层字段布局。

以下情况不触发该重试：传输失败或 provider refusal（由 adapter 的既有证据与预算处理）、`scope_failure` 语义拒绝、admission 失败、持久化失败以及任何已经成功解析的空声明。这样不会把语义不确定性伪装成协议修复，也不会重复写库。

每个 `ExtractionLlmAttempt` 保存实际 prompt、prompt hash、原始响应、解析错误和 `terminal` 状态；回执同时保留顶层首轮 prompt 以兼容既有归档。重试仍在 `prepare → extract → commit` 的锁外抽取阶段执行，commit 只重放最终尝试序列。R3.4 每个 holder 最多增加一次结构化抽取请求，现有 scope 预留上限仍覆盖该预算。

Python `ExtractionConfig` 只承载整数并映射到 C++ policy；评测脚本只锁定 R3.4 配置，不判断错误类别、不重写 JSON、不实现重试循环。

## 4. RED 测试与验收

先新增 C++ 测试：默认预算为 0 时重复键仍失败；预算为 1 时重复键首轮失败、第二轮合法响应成功；目录外谓词同样可在第二轮合法响应后成功；连续两次协议失败后不再请求；scope 语义拒绝不重试；每次尝试的 prompt/hash 与原始响应进入回执。再新增 Python binding/评测门禁测试，确认字段只透传、默认值不变、R3.4 实验预算和身份配置锁定。

真实评测使用独立目录、qwen3.8-27B、固定 57 题、同一回答/裁判协议和 `claim_protocol_retry_budget=1`。先验收 7/7 scope、36/36 holder 和技术失败分类，再在共同技术正常题上计算配对 QA；只有净增至少 5 题且网络 bootstrap 95% 区间下界大于 0 才考虑晋升，否则保留为诊断结果。

## 5. 风险与回滚

有限重试会增加少量抽取请求和成本；所有请求通过现有预算账本预约并在回执中核账。若技术完成率没有改善、语义错误增加或预算边界不清晰，关闭 R3.4 配置即可回到默认 0；生产 `semantic_claim_contract=false` 始终不受影响。
