<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.2 主体时间链与支持性第三方证据设计

日期：2026-09-22。状态：R4.2 实现和真实评测已封存；生产默认未改变。结果见 [R4.2 中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。

## 1. 诊断依据

R4.1 的 `evidence_profile_v3` 将精确原话覆盖提高到 55/104，但检索臂降至 17/57。失败样本显示：部分题目需要主体自己的前后状态，部分题目还需要他人观察、先前认知或群体背景。把第三方全部排除会损失“Luca 已经知道 Raj 的矛盾”“Nora 早已知道 Priya 偏好”等证据；把第三方无条件加入又重现 R4.0 的日期和邻句噪声。

R4.2 只在 C++ 来源选择中加入受限 `support` 车道，保留 v3 的主体优先时间链。回答提示、谓词目录、抽取合同、Python binding、生产默认和 R4.1/R4.0 封存目录均不修改。

## 2. 支持车道触发

增加 `evidence_profile_v4`。问题词仍由现有确定性分词和姓名边界得到；不读取题号、答案、公开锚点或 query_type。

`support_requested` 在问题包含 `already knew`、`knew`、`aware`、`understand`、`what does ... reveal/show`、`what explains`、`why`、`之前知道`、`说明`、`揭示`、`为何` 等认知或解释线索时为真。时间变化问题本身不触发 support；只有同时出现解释/认知线索才触发。

主体时间题（例如 Cass 如何逐渐改变做法）support 名额为零；非时间主体题以及“主体+他人认知”题最多取一个 support 来源。support 来源必须是非目标 speaker、通过原有权限/时间/完整性过滤、与问题话题有词项重合或明确提及目标人物；没有合格来源时留下 `support_missing` 缺口。

## 3. C++ 选择契约

- v4 复用 v3 的 `subject_match`、`topic_overlap`、主体优先 session 代表、实体/人际关系区分和最终 source limit。
- 增加 `support_requested`、`support_limit`、`support_selected`、`support_missing` 和 trace 的 `selected_by=support`。
- 选择顺序为相关性主体种子、时间车道、严格人际互动车道、support 车道、行为车道、相关性补足。support 不得改变 `subject_sessions` 的计算，也不把第三方 session 计入主体时间覆盖。
- v3 策略保持逐字行为；v4 仅新增 support 车道。source_refs、整行 UTF-8 字节预算、degraded_paths 和 rendered 对齐约束保持不变。

## 4. 验证与评测

先保存 `SourceProfileV4` RED：单人物偏好题在非时间模式保留一条第三方支持、带“已经知道”的时间题保留主体和一条支持句、纯时间变化题 support=0、双人物关系仍保留互动。再实现 GREEN，运行相关 C++、Python、完整 CTest 和冻结目录离线合同。

真实评测沿用 57 题、qwen3.8-27b、R3.5 父快照、600 HTTP、零重试、两臂共用一次检索；新目录为 `build/socialmem_20260922_r42_support_lane_real`。继续门槛仍是相对 R3.5 净增至少 5 且 bootstrap 区间下界大于 0；R4.1 失败不构成放宽门槛的理由。

## 5. 回滚

若支持车道降低完整回答质量或增加技术失败，关闭 v4、保留 v3/v2 代码和封存结果；不修改生产 `semantic_claim_contract=false`、`claim_protocol_retry_budget=0`。所有核心逻辑仍在 C++，Python 只传递策略名和编排评测。

## 6. R4.2 实评结论（2026-09-22）

R4.2 的 57 题真实双臂评测已经完成并通过终态核验。检索臂为 17/57，原生回答臂为 19/57；两臂相对彼此净增 2 题，网络 bootstrap 95% 区间为 [-3.64, +9.80] 个百分点，未达到继续门槛。原生回答臂有 2 次回答截断和 2 次裁判超时，检索臂无技术失败。实际请求 545/600，账本无未决请求。

精确 `(speaker, turn_id)` 来源命中为 R3.5 的 53/104、R4.2 的 52/104；结构化声明出处并集为 60/104、57/104。支持车道在认知/解释问题上按设计最多选一条第三方来源，但未解决事件的前态—触发—后态链、他人信念归属和“所有成员”逐人覆盖。`Q6_n2a7b8c9` 明确留下 `no_selected_utterance:Chidi`，`Q8_r3b8c9d0` 已命中全部原话却因回答截断失败。生产默认保持关闭，R4.2 不晋升；完整证据见评测报告及 `build/socialmem_r42_checks/diagnostics.json`。

下一轮候选为 R4.3 事件状态与信念归属车道，先建立中文设计和 RED 测试，再决定是否编码；不得把本节诊断直接当作实现效果。
