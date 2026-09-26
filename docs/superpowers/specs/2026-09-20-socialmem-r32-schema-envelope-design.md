<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench R3.2 结构化声明信封与字段归属设计

日期：2026-09-20

## 1. 背景与可复核证据

R3.1 使用 DashScope `qwen3.8-27b`、固定 57 题和 `hybrid_fenced` 臂，将结构化抽取上限提高到 8192。该轮完成 57/57 题，但只有 3/7 个 scope 完成，技术失败 30 项，正确 6/57；抽取尝试中有 3 次 `schema_failure` 和 1 次 `envelope_failure`，没有观察到 `completion_truncated`。因此 R3.1 证明容量上限不再是唯一阻塞点，不能证明 QA 提升。

对 R3.1 保存的原始 completion 做逐条回放后，已确认以下协议形态风险：

1. 一个 Josh 响应在同一 `evidence` 对象中重复 `time_text` 和 `topic`，被严格 JSON 信封拒绝。
2. 一个 Josh 响应把 `subject_kind` 放入 `evidence`，造成声明顶层字段缺失或嵌套错误。
3. 一个 Luca 响应把 `holder`、`holder_perspective` 等声明字段重复放入 `evidence`。
4. Otto 的失败批次包含多条声明，需以 C++ 原生解析回执为准，不能用 Python 的宽松 JSON 解析替代。

这些现象发生在模型输出与 C++ 合同之间的边界。它们不能通过补字段、展平对象或猜测语义来修复，否则会把模型没有声明的内容伪装成可写入记忆。

## 2. 目标

本轮目标是降低结构化抽取的可识别信封和字段归属错误，并保持证据链可审计：

1. 把一条合法声明的完整字段归属以紧凑、无歧义的 C++ 原生模板放在 `SOURCE_DATA_JSON` 之后，靠近模型最终输出位置。
2. 在模板中分别列出 statement 顶层字段和 `evidence` 唯一允许字段，并给出只含占位符的合法最小骨架。
3. 明确每个对象内的 key 只能出现一次，要求先生成一个完整声明再复制结构，不得追加同名 key。
4. 继续由 C++ `strict_json`、wire schema、scope guard 和 admission 共同拒绝 malformed 或不受证据支持的响应。
5. 用独立的 57 题网络评测确认技术失败是否下降，再分别分析 QA，不把协议完成率当语义准确率。

## 3. 非目标与边界

- 不在 Python 中实现 JSON 解析、字段展平、重复 key 清洗、字段补全、谓词判断或语义重写。
- 不修改 `claim-predicate-v3` 的目录、别名、模态、极性和 scope 规则。
- 不修改答案生成、裁判、检索排序、题目、评分分母、重试策略或生产默认 `semantic_claim_contract=false`。
- 不启用 `json_schema_strict`，不依赖提供商对 `uniqueItems` 或嵌套对象的额外实现。
- 不把 `confidence: null` 改成任意数值；合法显式 null 仍由 C++ 采用既有安全默认值，缺少字段仍失败。
- 不以历史 R2.3/R3.1 的非配对分数推断本轮收益；所有新结论必须引用本轮独立目录和原始回执。

## 4. C++ 唯一实现方案

`claim_extraction_prompt` 继续由 `claim_contract.cpp` 组合目录、关系边界、生成指导和来源数据。R3.2 只新增一个私有的 `final_format_reminder` 末端片段，追加以下四类信息：

1. **对象边界**：根对象只有 `schema_version`、`statements`；每个 statement 的字段固定在顶层；`evidence` 是唯一嵌套对象。
2. **允许字段**：逐项列出 statement 字段和 evidence 字段，声明 evidence 不得出现 statement 字段。
3. **规范骨架**：使用 `HOLDER`、`CLAUSE_ID`、`PREDICATE` 等占位符展示一次性完整 key 集合，禁止复制占位符中的业务内容。
4. **末端检查**：裸 JSON、key 唯一、`holder_perspective` 必须存在、`event_time` 必须出现（无值用 null）、不输出 Markdown/解释或源元数据。

模板不得包含 SocialMemBench 题号、金标答案、固定人物、原始来源片段或可被误当成证据的具体对象。解析器的接受集合不因本轮提示变化而放宽；重复键、误嵌套、缺字段和额外字段继续原样保留并分类为技术失败。

## 5. 测试先行设计

在修改 C++ 前，新增 RED 断言：

- 末端提醒包含独立的 `STATEMENT TOP-LEVEL SHAPE`、`EVIDENCE NESTED SHAPE` 和 `CANONICAL SKELETON` 标记。
- 提醒明确列出 `holder`、`holder_perspective`、`subject_kind`、`predicate`、`object`、`modality`、`polarity`、`nesting_depth`、`confidence` 为顶层字段。
- 提醒明确列出 evidence 允许字段 `clause_id`、`actor`、`attributed_to`、`assertion_scope`、`scope_markers`、`time_text`、`topic`、`event_time`，并明确 `source_turn` 不属于模型输入字段。
- 提醒包含规范骨架且每个 key 只出现一次；占位符不含人物、题号、答案或真实来源词。
- 误嵌套 statement、重复 key、缺少 `holder_perspective` 的响应仍由原生 parser 拒绝；合法现有正例继续通过。

Python 只验证 binding 返回 C++ 提示和评测脚本没有清洗入口，不增加任何同名语义实现。

## 6. 评测协议

实现并回归通过后，在新目录执行与 R3.1 同题、同来源、同回答/裁判预算的 `hybrid_fenced` 评测。必须记录：

- 7/7 scope 与 36/36 holder 完成率；
- extraction/admission/answer 的请求数、token、超时、截断和原始回执；
- `envelope_failure`、`schema_failure`、`scope_failure`、`transport_failure`、`persistence_failure` 的分项；
- 空候选、结构化声明总数、谓词和语义族分布；
- 全题准确率、技术失败计零准确率、成功子集准确率、同题配对转移和 bootstrap 区间。

若 schema/envelope 技术失败下降但共同 `ok` 题 QA 未改善，只记录协议诊断收益，不晋升任何生产配置。只有完整覆盖、技术失败下降且预注册 QA 门槛满足时，才进入下一轮谓词或检索优化。

## 7. 文档同步

本设计完成后同步更新：

- `docs/design/system_design.md`
- `docs/design/claim_contract_sync.md`
- `docs/design/subsystems_design/07_neocortex.md`
- `docs/design/subsystems_design/08_cognizer.md`
- `docs/design/subsystems_design/13_retrieval.md`
- `docs/eval/2026-09-20-socialmem-r31-extraction-capacity.md`（追加后继指向，不改历史结果）
- `docs/eval/2026-09-20-socialmem-structured-coverage-diagnosis.md`（追加 R3.2 状态）

所有新增内容用中文撰写；历史快照和历史分数保持不变。

## 8. 实施结果（2026-09-21）

R3.2 已完成 C++ 末端结构提醒、专项回归和独立 57 题评测。评测完成 57/57 题，技术失败从 R3.1 的 30 降至 1，6/7 scope、32/36 holder；正确 13/57，成功子集 13/56。唯一失败是重复 `time_text` key，严格解析和原始回执边界保持不变。共同技术正常题没有证明语义 QA 提升，故 `semantic_claim_contract` 继续默认关闭。

逐题诊断显示下一轮重点应转向 C++ 来源覆盖、跨 session 早晚状态和 hybrid SOURCE 配额，详见[R3.2 评测报告](../../eval/2026-09-20-socialmem-r32-schema-envelope.md)及[R3.3 证据覆盖设计](2026-09-21-socialmem-r33-evidence-coverage-design.md)。
