<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench R3.5 Holder 级故障隔离与字段诊断设计

日期：2026-09-21

## 1. 诊断依据

R3.4 在固定 57 道 SocialMemBench 题上完成 57/57 次启动，9 题技术失败，正确 12/57；技术正常子集为 12/48。协议重试把 R3.3 的 19 个技术失败降到 9 个，但共同技术正常题从 8/30 降到 6/30，不能证明回答质量提升。

失败仍然存在批级放大：Josh 的两次 envelope 失败和 Yusuf 的 schema 失败使所属 scope 无法生成可回答快照。R3.4 的 Yusuf 回执只能确认进入 belief 结构化通道，不能恢复具体字段、错误路径和完整失败 attempt。当前多 holder 遍历在 Python `eval_ladder.py`，某个 holder 的异常会中断后续 holder，违反“单个 holder 失败不阻断后续 holder”的诊断目标，也把核心管线语义放在 binding 侧。

## 2. 目标与非目标

目标：

1. 由 C++ 保存每次结构化 attempt 的确定性错误类别、字段路径、prompt/hash、原始响应和终态；scope 失败也必须可回放。
2. 由 C++ 执行多 holder 的 prepare → extract → commit 编排。单个 holder 的协议、传输或持久化失败转换为该 holder 的可审计结果，后续 holder 继续执行。
3. 对 `schema_failure` 和 `envelope_failure` 的最多一次重试提示加入确定性的错误摘要和字段路径；不复制模型原文，不修补 JSON，不改写谓词或语义结论。
4. 评测允许生成带 `holder_failures` 的 partial scope，并把完整 holder、partial holder、技术失败和 QA 分母分开报告。

非目标：

- 不增加谓词目录，不改变 scope、admission、source proof、tenant 隔离、答案或裁判协议。
- 不改变生产默认：`semantic_claim_contract=false`、`claim_protocol_retry_budget=0`，既有单 holder API 和历史归档保持兼容。
- 不在 Python 实现重试、解析、错误分类、holder 状态机或提交边界；Python 只做数据字段映射、binding 调用和归档。
- 不把 partial scope 的可回答结果当作 7/7 scope、36/36 holder 的生产质量证据。

## 3. C++ 原生接口与数据流

### 3.1 字段级错误模型

`ParseError` 增加可选 `field_path` 字段，保持既有 kind/detail/byte_offset 字段和初始化兼容。结构化 parser 为已知错误提供稳定路径，例如 `statements[0].holder`、`statements[0].predicate`、`statements[0].evidence.time_text`；无法确定时使用空字符串，不猜测路径。receipt 的 `errors` 同时输出 `kind`、`detail`、`field_path`、`byte_offset`。C++ 从最后一个失败 attempt 派生稳定的 `failure_detail`：优先 admission/解析错误（包含 kind、路径和 detail），其次传输错误；持久化失败覆盖该字段。该摘要只用于 holder 汇总和诊断，不参与重试判定或语义改写。

C++ 新增带错误摘要的 retry prompt 构造函数。提示只包含结构化的 kind/path/detail 列表和固定纠错指令，完整源上下文由 C++ 重新生成；原始响应不进入下一次请求。重试条件仍只限 `envelope_failure` 或 `schema_failure`，预算仍受 `claim_protocol_retry_budget` 的 0/1 上限约束。

### 3.2 Holder 批量管线

在 `memory_ops` 增加原生 DTO：

- `RememberParams`：`holder_id` 与已经由 C++ `claim_source_turn_payload` 生成的 payload；它复用既有单 holder 输入结构。
- `RememberOutcome`：holder、`outcome`、`extraction_failed`、`failure_category`、`failure_detail`、statement ids、结构化统计和完整三通道 receipt。

增加 `remember_holders(...)` 原生函数，执行以下阶段：

1. 按稳定输入顺序逐个调用 `remember_prepare`，记录 prepare 失败并继续。
2. 对可抽取 holder 在事务外调用三通道 `remember_extract_all`。每个 holder 拥有独立的 `RememberLlmBundle` 和 attempt 序列；异常转换为该 holder 的失败结果，不抛出中止整个批次。
3. 对每个 holder 独立调用 `remember_commit_all`。提交失败只回滚该 holder 的短事务并记录失败；后续 holder 仍执行。
4. 返回所有 holder 结果。没有可用 holder 或出现输入身份冲突时，才返回批级错误；该错误不伪造任何 holder 成功结果。

单 holder 旧 API 继续调用原有三相路径，避免影响生产调用者。批量 API 不使用跨 holder 的长事务，确保网络抽取期间不持有写锁；holder 间的数据库提交不共享回滚边界。

### 3.3 Receipt 与 partial scope

`memory_remember_bundle_receipt` 和 `claim_extraction_receipt` 继续由 C++ 生成。失败 holder 也必须有三通道 receipt；若失败发生在 prepare 之前，receipt 明确 `stage=prepare` 且 attempts 为空。每个 channel 的每个 attempt 保留实际 prompt、hash、raw response、错误数组、admission 回执和 terminal 标志。

Python 仅将 `RememberHolderResult` 转为 JSON 归档。scope 元数据新增 `holder_failures`、`holder_complete` 和 `scope_state=complete|partial`。存在 `frozen.db` 且所有输入 holder 都有结果时，partial scope 可以继续回答题目；缺失 holder 不会被伪装为成功。诊断报告必须同时给出全题、完整 holder 子集和 partial holder 子集，晋升门槛仍要求 7/7 scope 与 36/36 holder。

## 4. 评测配置与统计

R3.5 使用独立 arm 和目录，固定 `qwen3.8-27b`、57 题、同一来源快照、回答 512、裁判 64、HTTP 上限 1200，`claim_protocol_retry_budget=1`。R3.4/R3.3 目录不覆盖。

预注册输出：

- scope 完成数、partial scope 数、holder 完成数和失败类别；
- 每个失败 attempt 的 kind/path/prompt hash/raw response hash；
- 全题 QA、技术正常 QA、完整 holder QA、partial holder QA；
- 与 R3.4 的逐题配对、网络 bootstrap 95% 区间和实际请求账本。

只有技术失败下降且共同技术正常题配对净增至少 5 题、网络 bootstrap 区间下界大于 0，并满足 7/7 scope、36/36 holder，才讨论晋升。否则只保留诊断结果，生产默认不变。

## 5. 测试与验收顺序

严格执行中文设计 → RED 测试 → C++ 实现 → binding/评测门禁 → 离线回放 → 独立真实评测：

1. C++ RED：字段路径输出、字段级 retry prompt、重复 key/未知谓词一次重试、预算上限、失败 receipt 完整性、两个 holder 中第一个失败而第二个成功。
2. Python RED：R3.5 arm 只透传配置；runner 调用单一原生批量 API；partial scope 归档和门禁不会把失败 holder 伪装为成功。
3. C++ GREEN 后运行专项 CTest、相关 Python pytest 和完整 CTest；既有 loopback listener 沙箱失败单独列出。
4. 对固定 FakeLLM/SQLite 夹具执行零请求回放，检查 holder 顺序、attempt/hash、失败通道和 frozen snapshot。
5. 真实评测后独立生成中文报告，完整记录限制，不以技术可用性代替 QA 提升。

## 6. 风险与回滚

批量接口会改变评测抽取的调用编排，并可能让 partial scope 获得更多可回答题目；这会增加统计解释复杂度，因此必须分层报告。失败 holder 的 source evidence 可以已经持久化，但其 statement 不得进入结构化检索。若出现跨 holder 污染、租户越界、提交边界破坏或 receipt 不完整，关闭 R3.5 arm 即回到 R3.4；生产默认和历史数据不迁移、不重写。
