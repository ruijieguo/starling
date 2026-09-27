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

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

# SocialMemBench 结构化记忆闭环设计

状态：已确认并完成首轮实现，结构化闭环离线门槛已通过；完整回归仍有一个当前沙箱无法创建 loopback listener 的既有 HTTP 测试。本文是方案 A 的设计基线；本轮已按“文档 → RED 测试 → C++ 实现”执行，Python 绑定只负责参数归一和结果转发。专项 C++ 9 项测试和 Python 10 项可运行组合测试通过，可进入一次固定模型对照。

## 1. 背景与目标

上一轮 `focused_coverage` 已完成来源选择优化，但 99 道开发自由题只从 40/99 提升到 43/99，网络 bootstrap 95% 区间为 `[-5.05%, +12.12%]`，没有达到预注册晋级门槛。来源覆盖能够补回两个已知漏召回事实，却没有形成稳定的问答收益，因此下一阶段不再围绕同一批题搜索来源窗口，而是补齐结构化记忆闭环。

当前代码已经具备以下基础能力：

1. `memory_ops` 在 C++ 中提供 `remember_prepare → remember_extract_all → remember_commit_all` 三相管线。
2. `claim_contract` 能解析并校验结构化声明、来源片段和范围标记。
3. `claim_evidence` 能在检索阶段重放来源哈希、租户、片段和合同约束。
4. `temporal_evidence` 能从带会话顺序的候选中选择早期/晚期证据。

主要缺口是：结构化谓词目录过窄、抽取提示与校验目录缺少单一来源、声明统计不能完整区分失败阶段，以及没有独立夹具证明“抽取—持久化—证据检索—回答上下文”的闭环。本文目标是在不读取 SocialMemBench 题号、参考答案或公开锚点的前提下，完成可审计的最小闭环，并为后续真实评测提供可归因的实验接口。

## 2. 非目标和边界

- 不把 SocialMemBench 题目、参考答案、锚点词或题号写入谓词目录、解析规则、测试夹具或运行时分支。
- 不在 Python 中复制谓词语义、范围判断、证据校验、时间选择或冲突规则。
- 不修改裁判、参考答案、历史评测归档和已封存的 `focused_coverage` 结果。
- 不把原始来源召回的成功、合成夹具的成功或结构化声明数量直接宣称为端到端 QA 提升。
- 不在离线闭环测试通过前发起新的 DashScope 请求。
- 不改变现有来源证据的哈希和 span 定义；旧版本声明仍可被只读校验和检索。

## 3. 方案选择

本阶段采用“版本化谓词目录 + 原生结构化闭环”。目录是 C++ 的单一事实来源，负责生成抽取提示、结构化 schema、别名归一和语义 admission 规则。持久化继续复用现有三相管线；检索复用租户、来源认证和时间顺序约束，把通过证据校验的声明写入回答上下文。

方案 A 的取舍如下：

- 相对于开放谓词注册表，第一阶段的语义边界更严格，能明确区分“未支持关系”和“解析错误”。
- 相对于来源兜底的双通路，结构化收益可独立测量，失败时仍保留原始 engram，不会把回答模型的自由综合误算为记忆能力。
- 目录可以按通用关系族扩展，但每次扩展都必须有独立夹具、原生合同测试和失败统计，不按基准题目逐题添加谓词。

初始目录按以下关系族组织，具体谓词名称、别名、模态和时间能力由 C++ 目录固定并在实现计划中逐项落表：

| 关系族 | 语义范围 | 典型约束 |
|---|---|---|
| 身份与归属 | 人物身份、称谓、成员或归属 | holder、subject、subject_kind 必须一致 |
| 拥有与社会关系 | 拥有、认识、信任、家庭/协作关系 | 关系对象不可被误判为情绪对象 |
| 偏好与情绪 | 喜欢、厌恶、感受、态度 | 偏好和情绪分离，否定必须显式记录 |
| 计划与决定 | 计划、决定、意图、承诺 | `INTENDS` 与 `BELIEVES` 的模态不可混用 |
| 知识与不确定性 | 知道、相信、不确定、询问 | 不确定性不能被提升为事实 |
| 位置、工作与事件 | 位置、工作状态、事件状态 | 支持可选时间区间和来源时间 |
| 否认与纠正 | 否认、修正、被报道内容 | 归属、引用者和极性必须可重放 |

目录初始版本只允许已经定义过字段的声明形式；没有足够规则的关系暂时进入“未支持”统计，不用宽松字符串比较放行。

## 4. 数据模型与接口

### 4.1 C++ 谓词目录

在 `include/starling/extractor/claim_contract.hpp` 增加目录描述类型，核心字段包括：

- `catalog_version`：目录版本，随合同一起写入抽取 receipt。
- `name` 和 `aliases`：规范谓词名及输入别名；归一化只在 C++ 完成。
- `allowed_modalities`、`allowed_polarities`：允许的模态和极性集合。
- `supports_event_time`、`supports_topic`：是否允许事件时间和主题字段。
- `subject_kinds`、`object_kinds`：主体和对象的类型约束。
- `semantic_family`：用于统计和诊断的关系族，不参与答案生成。

目录提供以下原生入口：

```cpp
struct PredicateSpec;
struct PredicateCatalog {
    std::string version;
    std::vector<PredicateSpec> predicates;
};

PredicateCatalog claim_predicate_catalog();
const PredicateSpec* find_claim_predicate(std::string_view name);
std::string canonical_claim_predicate(std::string_view name);
bool is_claim_predicate(std::string_view name);
```

现有 `claim_contract_catalog()` 保留为兼容的 JSON 视图，由同一目录生成，不允许再维护第二份谓词列表。`claim_extraction_prompt()` 和结构化输出 schema 也必须从该目录派生。

### 4.2 声明合同

继续使用当前 `schema_version` 兼容路径；新增字段采用向后兼容方式写入：

- `predicate_catalog_version`：本次抽取所用目录版本。
- `semantic_family`：规范化后的关系族。
- `evidence`：现有 clause、actor、attribution、scope、topic、time 字段。
- `source_span`、`source_time`、`source_turn`：由 C++ 根据原始 payload 补全，模型不能伪造。

旧声明没有 `predicate_catalog_version` 时按旧合同重放；新目录不放宽旧声明的来源哈希、租户或 span 校验。

### 4.3 记忆三相边界

保持现有接口和顺序：

1. `remember_prepare` 只负责写入幂等 engram 并返回权威时间戳。
2. `remember_extract_all` 在锁外调用 LLM，完成 JSON 解析、合同校验、语义拒绝分类，不写数据库。
3. `remember_commit_all` 在短事务中写入声明、来源映射、抽取 receipt 和必要投影；任一通道的持久化失败按既有事务语义回滚。

`RememberOutcome` 和 `claim_extraction_receipt` 需要提供以下可重放统计：

- `accepted_by_predicate`、`rejected_by_predicate`；
- `envelope_failure`、`schema_failure`、`scope_failure`、`semantic_rejection`、`persistence_failure`；
- `source_preserved`、`structured_claims_persisted`；
- `catalog_version` 和请求/响应证据标识。

抽取失败时，已接受的原始 engram 必须保留，结果明确为“source_preserved=true、structured_claims_persisted=false”；不得返回伪造的成功声明。

### 4.4 结构化检索

在 `retrieval` 中增加纯 C++ 的结构化候选选择入口，至少支持租户、holder/subject、谓词、主题、截至时间和候选上限。入口必须先调用现有 `claim_evidence_error`，再按目录重放合同；无效来源、跨租户行、未知谓词和缺失时间顺序分别计数。

时间变化继续使用 `TemporalEvidenceRequest`。早期/晚期选择结果和不足原因写入检索 receipt；当证据不足时，`context_pack` 必须保留 `[ABSTAIN]` 或等价的不确定性标签，不能把单条声明扩展成未经证据支持的变化结论。

`context_pack` 只渲染通过权限、来源和合同校验的声明，并保留 holder、谓词、对象、极性、模态、时间状态和来源引用。原始文本继续使用现有不可信数据围栏和二阶提示注入防护。

## 5. 失败分类与可观测性

所有失败类别必须由 C++ 产生稳定键，并出现在抽取或检索 receipt 中：

| 阶段 | 稳定类别 | 处理 |
|---|---|---|
| LLM 调用 | `transport_failure`、`timeout` | 保留来源，结构化抽取失败；不重试隐藏成本 |
| JSON 外层 | `envelope_failure` | 拒绝整批声明，保留原始响应摘要和校验错误 |
| 字段合同 | `schema_failure` | 按行记录，不能写入不完整声明 |
| 范围/归属 | `scope_failure` | 拒绝错误 holder、引用者、否定或问题范围 |
| 语义 admission | `semantic_rejection` | 按谓词和关系族统计，不伪装成解析失败 |
| 持久化 | `persistence_failure` | 事务回滚声明，原始 engram 保留并标记降级 |
| 检索证据 | `invalid_evidence`、`cross_tenant`、`unknown_predicate` | 候选排除并计数 |
| 时间证据 | `missing_order`、`insufficient_temporal_evidence` | 返回不足原因，允许回答模型谨慎 abstain |

receipt 中不能只记录“抽取为空”；必须能区分模型没有声明、声明被合同拒绝、声明因证据无效被检索排除和数据库写入失败。

## 6. 独立夹具与测试设计

测试数据使用与 SocialMemBench 无关的合成姓名、会话和事实，固定在 C++ 原生夹具中。至少覆盖：

1. 多人物对话中的显式 holder 归属；
2. 否认、纠正、引用和问题范围；
3. 同一主题的早期/晚期状态变化；
4. 多成员、多会话和缺失会话顺序；
5. 来源 span、哈希、source_time 和 source_turn 的完整回放；
6. 跨租户隔离、逻辑删除和幂等写入；
7. 未知谓词、模态冲突、对象类型错误和时间证据不足；
8. `prepare/extract_all/commit_all` 与单体 `remember` 的字段级等价性。

测试顺序严格为：先写失败用例并确认 RED，再实现；Python 测试只调用绑定的 C++ 接口，不能在 Python 中补充谓词判断或证据选择。

离线验收门槛：

- C++ 合同、来源证据、租户边界和事务回滚测试 100% 通过；
- 独立夹具中有效声明至少 95% 能完成“抽取—入库—检索”闭环；
- 多人物归属、否认/纠正、时间早晚选择和来源引用不允许出现静默错误；
- Python 组合测试只验证绑定转发、结果结构和异常映射；
- 现有回归测试不新增失败，旧合同和旧声明仍可读。

## 7. 真实评测门槛

只有离线门槛全部通过后，才允许使用已授权的 DashScope `qwen3.8-27b`。真实评测保持上一轮冻结口径：同一语料、同一回答与裁判协议、零重试、完整终态后再查看成绩，并单独记录 HTTP、tokens、抽取失败、声明接受数、证据排除数和 QA 标签。

结构化闭环实验与来源覆盖实验必须有独立运行目录、请求账本、源码/依赖哈希和 seal。主晋级条件仍为：相对同期 baseline 净增至少 5 道题，且网络 bootstrap 95% 区间下界大于 0；否则只保留诊断结论，不做生产或泛化宣称。

## 8. 实施顺序与回滚

实施顺序固定为：

1. 本设计文档和相关评测文档同步；
2. 编写原生失败测试并确认 RED；
3. 实现 C++ 目录、合同、receipt、持久化和检索闭环；
4. 运行 C++ 原生测试和 Python 组合测试；
5. 生成独立夹具报告并自审证据链；
6. 通过离线门槛后执行一次冻结的真实对照；
7. 分析提升与失败类型，决定下一轮消融或回滚。

回滚只撤销本阶段新增的目录版本和检索入口；旧 `semantic_claim_json`、来源 engram、旧绑定函数和已封存评测目录不得删除或重写。任何未通过门槛的实现保持在诊断状态，不修改默认策略。

## 8.1 SourceTurn 证据闭环同步（2026-09-20）

为使真实评测输入与来源持久化输入等价，抽取编排统一调用 C++ SourceTurn renderer，并由 C++ 导出三个抽取通道的完整回执；Python 只传递白名单字段和归档 JSON。此项已通过 RED/GREEN 与本地回归，但尚未产生新的真实 QA 结果；完整 baseline 需在新接线下单独重建。

## 9. 验收结论格式

每轮报告必须分别列出：

- 设计/实现状态和工作区证据；
- 合同测试、来源证据测试、事务测试和绑定测试；
- 独立夹具闭环率及各失败类别；
- 真实评测的完整分母、技术失败、tokens 和置信区间；
- 与 baseline 的逐题变化、共同正常子集和已知限制；
- 是否达到晋级门槛，以及下一轮唯一待验证假设。

任何“能力补齐”“准确率提升”“修复完成”结论都必须对应新鲜、可重放的原生或真实评测证据。

## 10. 首轮实施状态（2026-09-19）

已落地的 C++ 核心包括：`claim-predicate-v2` 版本化目录（10 个规范谓词及别名）、由目录派生的抽取提示/合同 JSON/schema、抽取失败分类与来源保留回执，以及按租户、holder、subject、predicate、topic、截止时间和时间证据选择结构化候选的原生接口。Python 绑定仅映射这些 C++ 类型和结果。

本轮新鲜验证结果：`StructuredMemoryClosure` C++ 专项 9/9 通过；其中包含一条真实 C++ 抽取→持久化→consolidation→BasicRetriever→结构化证据检索正向路径，以及两条带真实 Engram span/hash 的 early/late SourceTurn 选择；Python 结构化目录、合同表面和时间证据组合 10/10 通过。相关合同/证据/抽取/记忆回归 105/105 通过。完整 C++ 回归为 1200/1201 通过，唯一失败是沙箱不允许 loopback listener 的既有 HTTP 测试；`remember_phases` Python 测试在当前环境因未安装可选 `fastapi` 无法收集。RED 日志保存在 `build/structured_memory_closure/red.log`。

当前离线门槛状态为“通过（闭环专项范围）”：有效正向夹具 3/3 完成抽取/来源认证/检索选择，目录归一、失败时保留来源、跨租户/无效来源排除和 binding 转发均通过。完整回归的 loopback 失败属于环境限制，已单独记录，不能归因于本轮实现。该门槛只允许启动一次固定 `qwen3.8-27b` 对照，仍不等同于 SocialMemBench QA 已提升。
