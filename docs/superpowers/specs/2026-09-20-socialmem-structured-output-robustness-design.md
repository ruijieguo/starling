<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench 结构化输出鲁棒性设计

日期：2026-09-20

## 1. 证据与问题定义

`build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_json_object` 使用
`qwen3.8-27b`、DashScope、`response_format={"type":"json_object"}` 完成了 57/57 题的调度，
但只有 `grp_4d5e6f7a` 的 9 个 holder 完成结构化抽取。其余 6 个 scope 各有一个 holder 的
模型响应触发 C++ `schema_failure`，scope 随后终止，最终为 3/57、48 个技术失败。

逐字回读原始响应确认，失败响应并非传输空响应或截断，而是把本应位于声明顶层的
`holder`、`subject`、`predicate`、`object`、`modality`、`polarity` 等字段整体放入
`evidence` 对象；其中 `confidence: null` 位于外层。另有一条还省略了
`holder_perspective`。这是一种可识别的 wire-shape 误嵌套，不能由 Python 清洗，也不能把
模型未提供的语义字段猜出来。

## 2. 目标与非目标

目标：

1. 由 C++ 唯一生成一个短的最终输出格式提醒，明确声明字段必须位于 statement 顶层，
   `evidence` 只能包含证据字段；提醒放在源数据之后，减少长提示末端的格式漂移。
2. 在 C++ 本地回环测试中锁定该提醒的字节内容、目录字段和安全边界，Python 只透传提示和
   评测配置。
3. 保留严格解析：真实模型输出若仍误嵌套、缺字段、越权字段或语义证据不完整，必须原样
   记录并计为技术/协议失败；本阶段不自动把误嵌套响应转换为成功声明。
4. 将失败回执细分为 `schema_failure`、`scope_failure`、传输失败和持久化失败，便于下一轮
   判断提示修复是否真正降低技术失败。

非目标：

- 不在 C++ 之外实现解析、正则清洗、字段补齐或谓词判断。
- 不把 `confidence: null` 改成模型没有给出的数值；现有 C++ 合同仍按 0.7 的安全默认值
  处理合法的显式 `null`，但这不放宽缺失顶层字段。
- 不启用已被历史能力探测证明不稳定的 `json_schema_strict`，不删减服务端 schema 字段，
  不自动切换输出模式或重试不同协议。
- 不修改答案、裁判、检索排序、SocialMemBench 题目和评分分母。

## 3. C++ 数据流与边界

`claim_extraction_prompt` 仍由 C++ `PredicateCatalog`、关系边界和示例生成。实现新增一个
原生 `final_output_format_reminder()`（或等价的私有常量），在 `SOURCE_DATA_JSON` 后追加：

```text
FINAL FORMAT CHECK:
- Return one bare JSON object with exactly schema_version and statements.
- In every statement, holder, holder_perspective, subject, subject_kind, predicate, object,
  modality, polarity, nesting_depth and confidence are TOP-LEVEL fields.
- The evidence field is a separate nested object containing only clause_id, actor,
  attributed_to, assertion_scope, scope_markers, time_text, topic and event_time.
- Never put statement fields inside evidence. Never omit holder_perspective.
- Do not emit Markdown, prose, source metadata or extra keys.
```

该文本不携带评测人物、答案或标签。`parse_claim_response` 继续是唯一 wire/schema/scope
入口，`OpenAIAdapter` 继续保存原始 completion 和 HTTP 回执。提示改变不会改变解析器的
接受集合：只有符合既有合同的响应才进入 admission、写入和检索。

## 4. 测试设计（先 RED，后实现）

新增 C++ 用例 `tests/cpp/test_structured_output_prompt.cpp`：

- 当前提示在 `SOURCE_DATA_JSON` 之后包含唯一的 `FINAL FORMAT CHECK`；提醒明确出现
  `TOP-LEVEL`、`Never put statement fields inside evidence` 和 `holder_perspective`。
- 提示不包含 SocialMemBench 题号、金标答案或固定评测人物。
- 合法已有正例仍可由 `parse_claim_response` 接受。
- 误嵌套样例（statement 字段全部放入 evidence）仍返回 `schema_failure`，不得被测试暗中
  归一化；缺少 `holder_perspective` 的样例也必须失败。

新增 Python 用例只核验 binding 返回的提示包含同一原生提醒，且评测 runner 仍仅传递
`claim_output_mode`，不出现字段修复函数或 Python 谓词逻辑。

## 5. 评测与验收

实现后依次运行 C++/Python RED→GREEN、结构化合同和 SourceTurn 回归，再用独立目录进行
同题 57 题 `hybrid_fenced` 评测。报告必须同时给出：scope/holder 完成率、失败类别、空
候选率、谓词分布、结构化声明数、技术失败计零的 QA 准确率和成功分母准确率。只有技术失败
显著下降且 QA 置信区间达到既有事前门槛，才讨论晋升；否则只记录协议鲁棒性诊断。

## 6. 设计同步范围

本设计同步更新现行中文入口：

- `docs/design/system_design.md`
- `docs/design/claim_contract_sync.md`
- `docs/design/subsystems_design/07_neocortex.md`
- `docs/design/subsystems_design/08_cognizer.md`
- `docs/design/subsystems_design/13_retrieval.md`
- `docs/superpowers/specs/2026-09-20-socialmem-predicate-coverage-expansion-design.md`
- `docs/eval/2026-09-20-socialmem-structured-coverage-diagnosis.md`

历史评测封存只保留原值，不改写为本轮结果。

## 7. R2.3 重复键与布局对照修正（2026-09-20）

末端提醒后的第二轮真实评测仍有三份失败 scope 回执：两份原始 JSON 含重复 `time_text`/`topic` 键，触发 C++ `envelope_failure`；另一份继续把 statement 字段置于 `evidence`，触发 `schema_failure`。因此本轮新增两个纯提示约束：每个 JSON key 在同一对象内只能出现一次；追加极短的 BAD/GOOD 布局对照，明确 `confidence` 与 statement 字段在外层、证据字段在内层。

对照只使用占位字符串，不提供人物、题目或答案，不改变 C++ 解析接受集合。重复键和误嵌套继续保留原始文本并拒绝，任何模型输出修复都必须发生在模型侧生成阶段，而不是 Python 或 C++ 解析器的隐式清洗。
