<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench 结构化谓词覆盖扩展设计

日期：2026-09-20

## 1. 背景与问题

当前 `hybrid_fenced` 完整结构化结果为 18/57，7/7 scope、36/36 holder、技术失败 0。C++ 结构化合同的规范目录只有 10 个谓词，提示明确要求模型把偏好、承诺、怀疑、责任和规范类状态留在“既有路径”；但在 `semantic_claim_contract` 评测路径中，legacy belief 抽取并没有与结构化声明形成同等的 holder、准入、证据和持久化闭环。结果是模型在大量有明确社会心理状态的来源上返回空候选，或只能退化到 general_fact/episodic，丢失心智状态的模态和主体。

本设计只解决**结构化声明能够表达并保留哪些原生心智谓词**。它不从来源关键词自动生成声明，不修改题目、答案或裁判，不把声明数量当作问答准确率，也不改变生产默认策略。

## 2. 目标与非目标

目标：

1. 由 C++ 唯一维护一份扩展谓词目录、别名、语义族、允许模态和极性。
2. 让结构化合同覆盖当前 legacy mental-state prompt 已承诺的七类能力：偏好、承诺、怀疑、信念、责任、要求、禁止。
3. 解析、准入、写入、回读和检索使用同一目录；Python 只调用 binding、传递配置和归档。
4. 保留现有五类结构化声明的行为，非法模态、主体或范围仍确定性拒绝。
5. 通过固定的中英文正反例证明新增谓词不会把行为、访问、偶然转交或一般事实误收为心智关系。

非目标：

- 不新增 Python 谓词词表、正则分句、自动候选补写或答案定向规则。
- 不把 general_fact 的 `has_property/related_to` 等世界事实改成心智声明。
- 不扩展二阶信念、推理事实、自动主体归因或政策实体主体；这些另有契约。
- 不改变 `semantic_claim_contract` 的默认关闭状态，不刷新既有评测目录，不在本阶段发起 DashScope 请求。
- 不声称本地 RED/GREEN、声明数、召回次数或离线夹具通过率等于 QA/F1 提升。

## 3. 原生目录与语义边界

目录版本由 `claim-predicate-v3` 递增。既有条目保持名称和别名，新条目如下：

| 规范谓词 | 别名 | 语义族 | 允许模态 | 允许极性 | 边界 |
|---|---|---|---|---|---|
| `prefers` | `wants`, `desires` | preference | `DESIRES`, `PREFERS` | POS/NEG | 只表示来源明确的偏好或想要；行为选择、第三方猜测和一般喜好推断不自动成立。 |
| `promises` | `commits_to` | commitment | `COMMITS` | POS/NEG | 需要来源中的明确承诺/保证/答应；普通计划或操作转交不自动升级为承诺。 |
| `doubts` | `questions` | epistemic_doubt | `DOUBTS` | POS/NEG | 表示主体对命题/对象的怀疑；问句、未知或未决行动不能直接改写为怀疑。 |
| `believes` | `thinks`, `assumes` | belief | `BELIEVES`, `ASSUMES` | POS/NEG | 保留明确的相信/认为/假定命题；不把模型或系统推断写成来源声明。 |
| `responsible_for` | `owns_area` | responsibility | `BELIEVES` | POS/NEG | 表示主体被明确赋予责任范围；一次访问、帮忙或偶然处理事件不等于责任。 |
| `requires` | `necessitates` | norm_requirement | `NORM_OUGHT` | POS/NEG | 只表示来源明确的规则、要求或必要条件；“请转给某人确认”不是要求关系。 |
| `forbids` | `prohibits` | norm_prohibition | `NORM_FORBID` | POS/NEG | 只表示来源明确禁止或不允许；个人不喜欢不等于规范禁止。 |

这七项的 subject_kind 仍限定为 `cognizer`，因为本阶段目标是 SocialMemBench 的人物心智状态闭环。政策实体、抽象规则作为主体的扩展留在单独的 policy-as-holder 设计，不通过放宽本合同偷偷引入。

既有目录保持：

- `feels`、`trusts`、`uncertain_about`、`indifferent_to`、`owns`、`located_at`、`works_at`、`member_of` 保持 `BELIEVES`；
- `knows` 同时接受历史 `BELIEVES` 和语义正确的 `KNOWS`，以兼容已有回执；
- `decided_on` 继续只接受 `INTENDS`；
- `uncertain_about` 继续只接受 POS。

目录中不允许把 `prefers` 别名映射到 `feels`，也不允许把 `promises` 映射到 `decided_on`；二者的证据和检索语义不同。对象必须保留来源中的目标、动作、范围和时间限定，解析器不做改写。

## 4. C++ 责任边界与数据流

1. `claim_contract.cpp` 生成目录 JSON、抽取提示、准入提示和通用参考例；所有模态、别名和语义族均从同一 C++ `PredicateCatalog` 渲染。
2. `parse_claim_response` 通过目录查找规范谓词，按 `PredicateSpec.allowed_modalities/allowed_polarities` 校验；不再在解析器和 `statement_validator.cpp` 各维护一套硬编码模态规则。
3. `statement_validator.cpp` 对结构化声明只调用目录规范检查主体、模态、极性和证据存在性；legacy 路径仍使用原有 `predicate_registry.hpp`，二者不共享 Python 实现。
4. admission 继续只保留完整、按原 index 顺序的决策。新增谓词的拒绝原因仍由原生目录提供，receipt 按规范谓词统计。
5. Bus、SQLite、回读和检索只处理已有 `ExtractedStatement` 与 `semantic_claim_json`，不新增第二份序列化格式。semantic_family 和 predicate_catalog_version 写入原有 evidence。
6. Python binding 暴露原生目录和已有抽取 API；评测脚本只读取目录版本、回执和存储字段，不复制谓词判定。

## 5. 提示与准入约束

抽取提示必须：

- 明确模型逐个检查偏好、承诺、怀疑、信念、责任、规则要求和禁止；
- 强调“明确来源才抽取”，行为、访问、偶然转交、沉默和问题不自动升级；
- 要求 `prefers` 使用 `DESIRES/PREFERS`，`promises` 使用 `COMMITS`，`doubts` 使用 `DOUBTS`，`believes` 使用 `BELIEVES/ASSUMES`，规范关系使用 `NORM_OUGHT/NORM_FORBID`；
- 保持 subject、holder、reported attribution、scope_markers、topic、time_text 和 object 的原文证据；
- 继续允许空 statements；不得为了覆盖率制造候选。

准入提示必须复用同一目录和边界说明，逐候选检查关系是否被误写、主体和模态是否匹配、对象是否丢失限定。准入不修复或改写候选。

## 6. 测试设计（先 RED，后实现）

C++ 新增 `tests/cpp/test_predicate_coverage_expansion.cpp`：

- 目录包含七个新增规范名、别名归一、版本为 v3，既有目录仍在；
- 通用英文和中文正例分别解析为规范谓词，保存原 object/topic/time；
- 每个新增谓词的非法模态被拒绝，`prefers` 不接受 `feels` 语义，`promises` 不接受无条件转交；
- `knows/BELIEVES` 历史兼容和 `knows/KNOWS` 新模态均保留；
- 混合候选的 admission 只保留支持决策，拒绝计数按规范谓词归档；
- 通过 `Extractor::persist` 后，新增谓词的 semantic_family、catalog_version 和 source proof 可回读；
- prompt 不包含 SocialMemBench 人物、地点、题目或答案，不出现 Python 维护的第二份目录。

Python 新增 `tests/python/test_predicate_coverage_expansion.py`：

- binding 返回的目录与 C++ JSON 一致，版本和新增谓词可见；
- `ExtractionConfig` 默认仍关闭结构化合同，Python 不导出谓词集合；
- 评测归档只传递目录版本/receipt，不在 Python 判断偏好、承诺或责任。

每个新增测试先运行并保存预期失败；只有 RED 原因是能力缺失而不是测试错误时才写实现。旧测试和结构化回归必须保持。

## 7. 评测方案与验收条件

实现后按以下顺序验证：

1. 新 C++/Python RED→GREEN；
2. 相关 C++、binding、结构化回执和检索回归；
3. 固定 57 题离线重放，确认旧响应解析结果未发生非预期变化；
4. 在同一 qwen3.8-27b、同题目/裁判、零重试、SourceTurn 完整输入协议下，建立一个新 `hybrid_fenced` 评测目录。新目录必须 7/7 scope、36/36 holder、每 holder 有三通道回执，不能复用 `source_only`；
5. 对比空候选率、原生拒绝率、admission 拒绝率、谓词分布、结构化声明数和 18/57 baseline；逐题 QA 与网络 bootstrap 单独报告；
6. 只有当 QA 净增和置信区间满足既定事前门槛，才考虑晋升；否则只报告能力和诊断变化。

## 8. 风险与回滚

- 新谓词可能增加误收：由独立正反例、admission 以及旧控制样本监控；若出现已有正反例误收、legacy 回归或目录/提示漂移，回滚目录版本和对应实现。
- 新模态可能使旧回执被拒：`knows` 明确保留 BELIEVES 兼容；其他改变只接受新候选，不重写历史数据库。
- 评测分数可能不升：声明覆盖提升不等于答案提升，保留空候选、拒绝、检索和 QA 分层结论。
- 任何 Python 新增谓词判断均视为架构违规，测试必须失败。

## 9. 受影响设计文档

本设计实施时同步更新当前中文设计入口：

- `docs/design/system_design.md`
- `docs/design/claim_contract_sync.md`
- `docs/design/subsystems_design/07_neocortex.md`
- `docs/design/subsystems_design/08_cognizer.md`
- `docs/design/subsystems_design/13_retrieval.md`
- `docs/superpowers/specs/2026-09-15-predicate-coverage-r1b-design.md`
- `docs/eval/2026-09-20-socialmem-structured-coverage-diagnosis.md`

历史设计快照和既有评测封存保持原样。

## 10. 首次 v3 评测后的输出协议修正（2026-09-20）

首次 v3 固定评测使用 `qwen3.8-27b`、legacy 结构化请求加代码围栏兼容。57 题均产生终态，但只有 10 题完成回答，47 题在抽取建库阶段失败。失败回执中已复核到三类可重复的技术原因：完成被截断、模型返回未转义的 JSON 字符串、候选证据的范围标记或对象限定不完整。它们发生在原生解析/写入边界，不能把这些题的 2/57 表面结果当作 QA 下降，也不能用 Python 清洗原文掩盖。

下一轮固定协议将把结构化抽取和准入请求的 `ValidationPolicy.claim_output_mode` 设置为原生 `JsonObject`。请求模式由 C++ `OpenAIAdapter::extract_with_contract` 产生 `response_format={"type":"json_object"}`；C++ 仍执行完整 envelope/schema/scope/admission 校验，保留代码围栏兼容作为服务端偶尔忽略参数时的诊断信息。Python 只传递 `claim_output_mode` 配置并归档输出模式、schema 哈希和能力回执，不解析、修复或删除模型文本。

该修正只降低协议性技术失败，不预设语义召回或 QA 提升。首次 v3 目录、请求账本和失败回执保持封存；新运行必须使用新的配置身份和独立目录，完成后分别报告技术完成率、谓词分布、结构化声明、QA/F1 和网络 bootstrap。若 qwen3.8-27b 的 `JsonObject` 实际仍返回围栏或非 JSON，原生回执应记录为协议不合格并停止把它当质量证据。

## 11. R2.2 结构化输出误嵌套诊断与提示修正（2026-09-20）

JSON Object 固定实评发现 qwen3.8-27b 在六个 scope 中各有一个 holder 将 statement 字段整体放入 `evidence`，导致 48/57 题技术失败。后续专项设计见 `docs/superpowers/specs/2026-09-20-socialmem-structured-output-robustness-design.md`：C++ 在源数据之后追加短格式提醒，解析器仍严格拒绝误嵌套，不做 Python 字段清洗或语义补写。评测必须分开报告协议完成率和 QA/F1。

## 12. R2.3 结构化输出重复键修正（2026-09-20）

第二轮 `claim-predicate-v3` JSON Object 评测将技术失败降至 16/57，但剩余回执暴露重复 JSON key 和 evidence 误嵌套。下一轮只在 C++ 生成提示末端增加唯一 key 与占位 BAD/GOOD 布局对照，解析器继续严格拒绝坏响应；不把协议完成率直接写成谓词或 QA 提升。

### R2.3 实评证据收口（2026-09-20）

独立网络评测完成 57/57 题，7/57 正确、26/57 技术失败；4/7 scope 完成，holder 为 19/36。失败包括重复 `time_text`/`topic` 的 `envelope_failure`、抽取超时、抽取/回答 `completion_truncated`。两轮共同完整题目只有 17 题，不能从 15/57 与 7/57 的非配对差异推断提示因果收益。当前仍保持 C++ 严格拒绝和 Python 仅 binding/编排，生产默认 `semantic_claim_contract=false`；完整证据见 [R2.3 鲁棒性评测报告](../../eval/2026-09-20-socialmem-structured-output-robustness.md)。
