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

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# 结构化输出能力与请求失败证据设计
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

**状态（2026-09-14）：中文设计、RED 测试、C++ 实现与本地验证已完成；C++ 1,089/1,089、Python 1,355 通过（15 跳过）。用户授权后真实探测 8 次、零重试；四组契约均为 nonconformant，阶段 A 原生核验 capability_blocked；没有后续评测调用或新质量分数。**

本设计与[关系覆盖及时间证据设计](2026-09-13-relation-evidence-coverage-design.md)共同细化已确认优化方案，执行顺序见[实施计划](../plans/2026-09-13-protocol-capability-and-coverage.md)。核心只在 C++，Python 仅转发类型、调用以及归档统计。

## 设计前证据（历史）

最近真实归档 `build/socialmem_20260913_protocol_boundary_real` 为 `verified / complete_with_errors`，manifest SHA-256 为 `47b71aa9538aa0bcb1f1a30882a4a68f719878464b93fb0d53bef8af685781d9`。140 条记录含 10 条技术失败：2 条抽取重复 JSON 键、8 条准入围栏后追加说明，其中 7 条属于固定候选。逐条索引见[原始失败诊断](../../eval/2026-09-13-socialmem-next-design-evidence.json)。现有验收策略允许完整单围栏，失败原因是重复键或围栏外说明，并非所有围栏一律失败。

设计时 `OpenAIAdapter::extract()` 只提供 `json_object_output` 请求提示。它不识别抽取/准入契约种类，未暴露 HTTP 尝试详情、完成原因或服务能力证据。`Extractor::extract_llm()` 的补充通道已是一次抽取、至多一次准入，不做语义或内容重试。

共享 `http_post_json` 对超时、接收失败、部分响应及 429/5xx 有重试；流式路径只检查是否已向回调交付正文。请求发出但未收到正文仍可能已在服务端执行。因此“首字节前失败”只能表明未交付输出，不能证明请求未执行或不会重复计费。本设计收紧的是实验结构化请求的显式策略，不能无声改写其他适配器的兼容策略。

## 方案取舍

| 方案 | 收益 | 限制与决策 |
|---|---|---|
| 继续增加提示或清洗错误响应 | 改动小 | 前者已有反复失败，后者改写原始证据；不作为协议可靠性方案。 |
| 原生契约请求、显式能力探测、严格本地校验 | 可区分请求被接受与实际输出符合契约，保留证据 | 采用；不能承诺服务商一定支持严格 schema。 |
| 直接更换模型或提供商 | 可能降低格式错误 | 同时改变模型语义和成本，无法隔离本轮收益；能力不支持时另立对照，不自动切换。 |

## C++ 请求接口

新增 `include/starling/extractor/structured_output.hpp` 与 `src/extractor/structured_output.cpp`，负责类型、契约描述、能力证据与缓存。`claim_contract.cpp` 保持语义解析、来源校验与准入唯一入口。接口草案如下，名字与含义为实现约束：

```cpp
enum class OutputContractKind { Legacy, ClaimExtractionV2, ClaimAdmissionV1 };
enum class OutputMode { Legacy, JsonObject, JsonSchemaStrict };
enum class CapabilityState { Unknown, ObservedConformant, Unsupported, Nonconformant };
struct StructuredOutputRequest {
    OutputContractKind contract;
    OutputMode mode;
};
// LLMAdapter 新增虚方法，保留现有 extract/generate/generate_stream 签名。
virtual LLMResponse extract_with_contract(std::string_view prompt,
    std::string_view prompt_input_hash, const StructuredOutputRequest& request);
```

默认实现只在 `Legacy` 请求下转发旧 `extract()`；其他模式返回结构化的“不支持”失败，绝不静默忽略约束。`OpenAIAdapter` 实现新方法，Fake 适配器记录请求种类并支持固定响应重放。旧自定义适配器继续可编译，选择新模式前必须实现对应接口。

补充抽取由 Extractor 传 `ClaimExtractionV2`，准入传 `ClaimAdmissionV1`；不靠解析提示文本选择 schema。`generate()`、`generate_stream()` 和旧数组抽取保留现有请求方式。新输出模式由 C++ 配置显式选择，默认 `Legacy`；既有 `json_object_output` 只在旧接口使用，若与新模式冲突则在调用前报配置错误。

## 线协议与原生目录

`JsonObject` 请求候选为 `response_format: {"type":"json_object"}`；`JsonSchemaStrict` 请求候选为 `response_format: {"type":"json_schema","json_schema":{"name":...,"strict":true,"schema":...}}`。这些是兼容接口设计中的待探测请求，不能据此声明当前 DashScope 模型支持。

抽取 schema 覆盖 v2 根对象与全部 Statement/evidence 字段，准入 schema 覆盖 v1 decisions/index/retain/reason。所有对象禁止额外字段；严格模式把可选字段显式表示为可空的必填字段（包括 `confidence`、`topic`、`attributed_to`、`event_time` 以及 event_time 的 `end`）。抽取不允许模型生成 source_span、source_turn、哈希或观察时间；它们由原生来源重建。

为兼容严格 schema 的必填可空字段，`confidence:null` 明确等同于省略 confidence，原生默认仍为 0.7；需先补缺省/null/数值/非法类型的正反例。既有非空值及原始证据原样归档。schema 将类型/枚举目录与原生预检共享，不能在 Python 定义第二份目录。现有宽接受、窄语义拒绝的边界不得被服务 schema 偷换：FIRST_PERSON/QUOTED/INFERRED/HEARSAY、cognizer/entity 及现有 modality/polarity 枚举保留原生预检的范围，关系矩阵继续在本地判断。

本地仍执行键唯一、类型、枚举、索引覆盖、`retain`/`reason` 一致、谓词矩阵、来源归属、范围和时间检查。服务端 schema 不承担蕴含判断；不能假定它能防止重复 JSON 键、跨话轮引用或语义错误。严格模式失败与 JSON mode 失败均不清洗、不补键、不改写成空成功。

## 显式能力探测与缓存

能力探测是单独 C++ API `probe_structured_output(request)`，只在调用方明确执行时发请求，构造适配器与普通调用不自动探测。首次检查固定不超过 8 个请求：2 种模式 × 2 种契约 × 2 个通用案例。每组含一个正常案例、一个正文要求违反 schema 的案例；使用与生产相同 schema 哈希和 C++ 校验，案例与评测题目、人物、答案及标签隔离。探测 `max_retries=0`，全部响应与代价单独归档。

| 观察 | 能力状态 | 后续行为 |
|---|---|---|
| 尚无结果或临时网络/认证失败 | Unknown | 不缓存为不支持；严格模式停止在前置检查，报告具体错误。 |
| 端点对指定格式参数明确返回不支持 | Unsupported | 缓存模式/契约级失败证据；不能把任意 400 都解释为不支持。 |
| 参数被接受但原文不符合对应契约 | Nonconformant | 留存失败原文，严格模式不能进入 cohort。 |
| 同组两个探测均通过 | ObservedConformant | 仅表示观测样本通过；每个业务响应仍校验。 |

缓存归适配器实例所有，不跨凭证、租户或实例共享。实例配置不可变；键包含完整 base_url、model、mode、契约版本、schema SHA 和探测版本；凭证不入键、日志或绑定。单调时钟 TTL 10 分钟，显式清除可用；相同键并发只允许一次探测，网络请求在锁外，其他请求等待同一有界结果。认证、超时等临时错误不缓存。配置或 schema 变化创建新键。运行开始时能力证据有效即可；长评测中不因 TTL 过期自动追加探测，实际响应违约仍逐条记失败。

本轮不自动降级。严格探测失败时输出 `capability_blocked`，记录零 cohort 调用与缺失质量分母，不能报告 `complete` 或复制历史分数。调用者明确选择 JSON mode 的另一次实验必须用独立目录、独立模式标记；不把它说成严格 schema 实验。

## 传输重试与回执

共享网络层新增 `RetryPolicy { LegacyCompatible, ConnectOnly }`，以及 `ExecutionCertainty { NotConnected, ResponseReceived, Unknown }`。原入口默认 `LegacyCompatible` 以保持旧用途；实验结构化请求强制 `ConnectOnly`。两种策略共用一份 C++ 网络循环。`HttpResult::attempts` 是 `HttpAttemptEvidence` 列表，各项包含 `execution_certainty`；已有 `attempt_count` 必须等于列表的实际尝试数。

`ConnectOnly` 只在域名/代理解析失败、连接建立失败，且尚无目标 HTTP 响应或正文时重试；上限保持配置的 `max_retries`，总尝试不超过 `1 + max_retries`。TLS/代理路径若无法排除请求已发送，一律归未知、不重试。超时、发送/接收失败、GOT_NOTHING、PARTIAL_FILE、HTTP 429/5xx、格式失败和语义拒绝均不在此策略自动重试。证书失败不重试。任何已交付流式字节禁止重放；保留共享层既有流式行为并补上真实保证的说明，不宣称“未交付字节”等于“未执行”。

HTTP 回执记录每次真实尝试的序号、HTTP 状态、curl 错误、响应正文字节数、是否交付流式字节、耗时、重试策略与服务端执行确定性（未连接/已收到响应/未知）。不通过上传字节计数或 request_size 推断“未处理”。部分正文保存在受控失败证据中；Authorization、请求头和凭证不归档。非有限 timeout 或负重试次数在请求前拒绝。

LLM 回执追加完成原因、拒答标志、请求模式/契约/schema SHA、能力证据 ID、HTTP 尝试列表和原始 completion 文本。`length` 截断、拒答、外层响应损坏、HTTP 错误、契约格式错误、语义拒绝分别记账；`raw_xml` 成功字段兼容，失败原文使用新增字段保留，不偷偷改变旧调用者的假设。有效 completion 的原文不经过 reasoning-trace 清洗。

错误主类保持现有统计口径；追加 `stage` 与细分原因，避免把 7 个固定技术失败改算正确拒绝。回执使用新版本；历史 v1 归档由其冻结核心/验证器重放，新版本校验新增请求与尝试证据，不能伪造旧档案不存在的字段。

## 测试与评测

先增加 RED：旧适配器兼容、两种契约不混用、原生 schema/null 边界、正常与违约探测、缓存键/TTL/并发、能力失败不启动 cohort、拒答/截断保留原文、无正文但服务器已读 POST 不重试、部分正文不重试、连接失败有界重试、负配置拒绝、Python 只转发及归档篡改被发现。测试使用本地 HTTP 服务和 Fake，不依赖真实提供商。

工程 GREEN 后冻结源码、模块、schema、输入、标签、能力证据与实际 HTTP 调用数。协议阶段保持上一轮语义定义，不同时修改 `uncertain_about`；语义阶段使用同一可用输出模式另跑独立目录，这样两阶段可区分，历史重放只证明解析兼容。

每阶段继续 50 P1、16 synthetic、10 来源组、64 固定候选，最多 76 抽取/140 准入、8 回答、120 裁判；能力探测另计，不混入 140 记录。指标保留严格分母、有效分母、首次成功率、最终成功率、传输尝试数、格式失败、语义误收误拒及重复裁判一致率。条件未满足时不扩大到 1,031 题，不更改生产默认。

## 文档依据与限制

2026-09-13 按 AGENTS.md 用 Context7 查阅 Alibaba Cloud Model Studio 与 Everything curl。阿里云普通索引返回无关视频模型文档，不能作为 deepseek-v3 schema 支持依据；两个查询的 `--research` 均被当前 CLI 以 `unknown option '--research'` 拒绝，未继续追加命令。curl 索引的[传输重试说明](https://everything.curl.dev/print.html)说明重试是一种配置策略，未提供服务端“恰好执行一次”保证。此处重试策略是保守的本地设计，不冒称官方给出了所有边界保证。

2026-09-14 已用阶段 A 冻结模块执行上述探测：两种输出模式、两个契约共 8 个案例均收到 HTTP 200，全部因围栏或额外说明未满足契约，分类为 Nonconformant。服务未明确拒绝参数，不能改称 Unsupported。能力检测不能代替语义评测。

## A2/A3 实现与聚焦验证（2026-09-13）

原生 typed request、共用 schema/enum 目录、nullable confidence、显式双案例探测、实例 single-flight/10 分钟单调 TTL、ConnectOnly 请求与失败原文回执已实现。Python 只暴露原生类型、调用及 JSON 序列化。`validate_capability_evidence_json()` 在 C++ 核对证据 ID、当前 schema、原始 HTTP/completion、实际尝试数与分类；外部报告不写入新实例缓存。

普通业务响应通过原有本地 claim parser；探测额外核验完整严格 schema。探测观测仅覆盖固定通用案例，不能推断服务对所有输入的严格保证。JSON object 模式也使用同一完整 schema 作为探测合格条件，因此缺失严格 schema 的可空必填字段时仍报告 Nonconformant，而不据此清洗响应或自动回退。

RED 日志为 `build/a2_binding_red.log`、`build/a2_confidence_red.log`、`build/a2_a3_native_red.log`、`build/a3_archive_validator_red.log`。原生 HTTP/claim/schema 聚焦 55/55 通过，binding 7/7 通过；另补 Fake 失败 completion 保留的 RED/GREEN，4/4 schema/Fake 聚焦通过。完整构建及安装已通过；A4 集成后的全套回归及真实服务结果由独立评测阶段记录，此处没有新质量分数。

最新真实探测与能力阻断详见[2026-09-14 报告](../../eval/2026-09-14-socialmem-capability-probe.md)。八条实际请求与审阅预览一致；外部报告不导入实例缓存。历史回执核验不刷新 TTL，也不追加探测。

## 声明范围与覆盖诊断职责（2026-09-15）

后继 L/R0 的诊断输出不属于模型 wire schema，schema 和提示须逐字回归。即使 schema 不变，新 parser 模块仍须新身份；只做本地重放无需能力探测，未来真实调用不能复用旧核心能力报告。已实施，本地验证结果见实施分析。

详见[声明范围定位与生成覆盖诊断设计](2026-09-15-claim-scope-localization-design.md)。

## 2026-09-16 范围字段协议对齐

本轮 C++ schema 生成与本地 wire 校验共同要求 scope_markers 非空且唯一；主范围成员关系、范围组合、来源与主体语义仍由 C++ 原生契约执行，binding 不重复判定。评测脚本冻结指定核心、来源、配置及调度，并在每次请求前复验能力和预约预算。真实端点拒绝数组 uniqueItems（两次 HTTP 400），C1 未通过能力门槛，来源样本、入库、检索、QA 均未执行；本地约束对齐不得解释为谓词召回或问答质量提升。当前实验开关继续关闭，提供商 schema profile 分离方案仍待下一轮单独设计与验证。

## 2026-09-16 能力与得分路线修订（已授权自主迭代）

后续计划引入显式 C++ provider profile 和 wire/local 双 schema 身份；完整本地校验不因提供商子集受限而放松。一次冻结实验可以预先列出独立兼容候选，禁止运行时隐式降级，协议可用后连续进入真实写入/召回/回答。 具体范围、测试与验收见[统一方案](2026-09-16-socialmem-capability-and-score-design.md)。本段描述计划，不代表已经实现或获得新分数。

最新执行顺序已按用户指令调整：先冻结当前默认 Starling 并完成全部 1031 题基线，再按真实失分执行中文文档→失败测试→C++ 改进→同条件复测，循环自主迭代，无需重复申请常规步骤授权。基线前仅补评测编排及题目允许来源范围，不预修被测能力。详见[基线优先执行计划](../plans/2026-09-16-socialmem-baseline-first.md)。
