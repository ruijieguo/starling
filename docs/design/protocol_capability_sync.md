<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../tests/README.md)和[中文设计](../superpowers/specs/2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../superpowers/specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../superpowers/specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../superpowers/specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../superpowers/specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../superpowers/specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../superpowers/specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# 协议能力与关系覆盖设计同步清单
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

A 阶段真实诊断已完成并原生核验：固定控制 62/64，Q1 linked 3/3；22 条技术失败、P1 退步和 Q9 证据缺失使质量门槛失败。B 尚未执行。下方历史章节保留各自时点；最新结果以[A 阶段报告](../eval/2026-09-14-socialmem-protocol-recovery-a.md)为准。

当前登记 69 份设计/技术报告/专项规范（含本清单、恢复设计及新增作用域/超时设计），实施步骤另见[本轮计划](../superpowers/plans/2026-09-14-protocol-recovery.md)。`docs/design/history/` 全部版本按已确认约束保留原文与哈希。

| 当前文档 | 本轮职责或核对结论 |
|---|---|
| [2026-09-15-scope-generation-and-timeout-design.md](../superpowers/specs/2026-09-15-scope-generation-and-timeout-design.md) | 本地实现及验证完成：C++ 作用域提示、原生截止配置、冻结配对预览；真实 S/T 未运行。 |
| [2026-09-14-protocol-recovery-design.md](../superpowers/specs/2026-09-14-protocol-recovery-design.md) | 共同提示与模型配置已实现；A 真实诊断完成但质量门槛未通过，B 未执行；历史授权与发送偏差单列。 |
| [Starling_Technical_Report.md](../Starling_Technical_Report.md) | 同步当前实现与外部评测阻断、生产默认、历史证据层级、C++ 唯一核心边界；旧质量数字保持各轮含义。 |
| [Starling_Technical_Report.zh-CN.md](../Starling_Technical_Report.zh-CN.md) | 同步当前实现与外部评测阻断、生产默认、历史证据层级、C++ 唯一核心边界；旧质量数字保持各轮含义。 |
| [claim_contract_sync.md](claim_contract_sync.md) | 同步当前实现与外部评测阻断、生产默认、历史证据层级、C++ 唯一核心边界；旧质量数字保持各轮含义。 |
| [04_substrate.md](subsystems_design/04_substrate.md) | 保留来源及失败证据、原生存取检查和旧数据兼容；模型不能生成来源证书。 |
| [05_bus.md](subsystems_design/05_bus.md) | 保留来源及失败证据、原生存取检查和旧数据兼容；模型不能生成来源证书。 |
| [05_governance.md](subsystems_design/05_governance.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [06_engramstore.md](subsystems_design/06_engramstore.md) | 保留来源及失败证据、原生存取检查和旧数据兼容；模型不能生成来源证书。 |
| [06_hippocampus.md](subsystems_design/06_hippocampus.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [07_neocortex.md](subsystems_design/07_neocortex.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [08_cognizer.md](subsystems_design/08_cognizer.md) | 行为归纳与时间解释保持派生父链；主体、转述与知识边界不因补充谓词扩展而放宽。 |
| [09_tom.md](subsystems_design/09_tom.md) | 行为归纳与时间解释保持派生父链；主体、转述与知识边界不因补充谓词扩展而放宽。 |
| [10_replay.md](subsystems_design/10_replay.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [11_reconsolidation.md](subsystems_design/11_reconsolidation.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [12_prospective.md](subsystems_design/12_prospective.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [13_retrieval.md](subsystems_design/13_retrieval.md) | 权限/来源先过滤，时间证据视图默认关闭；保留 tenant/id 与派生证据边界。 |
| [system_design.md](system_design.md) | 同步当前实现与外部评测阻断、生产默认、历史证据层级、C++ 唯一核心边界；旧质量数字保持各轮含义。 |
| [2026-07-19-starling-eval-impl-spec.md](../eval/2026-07-19-starling-eval-impl-spec.md) | 能力探测与 cohort 分开计数；v1/v2 归档分别核验；原分母和晋升门槛保持。 |
| [2026-05-24-m0-7-acceptance-design.md](../superpowers/specs/2026-05-24-m0-7-acceptance-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-05-26-p2-a-social-mind-schema-design.md](../superpowers/specs/2026-05-26-p2-a-social-mind-schema-design.md) | 保留来源及失败证据、原生存取检查和旧数据兼容；模型不能生成来源证书。 |
| [2026-05-27-p2-b-brain-dynamics-core-design.md](../superpowers/specs/2026-05-27-p2-b-brain-dynamics-core-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-05-27-p2a-v12-prompt-fallback.md](../superpowers/specs/2026-05-27-p2a-v12-prompt-fallback.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-05-30-p2-b-vector-layer-design.md](../superpowers/specs/2026-05-30-p2-b-vector-layer-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-05-30-p2-c-prospective-affect-design.md](../superpowers/specs/2026-05-30-p2-c-prospective-affect-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-05-31-p2-d-pattern-completion-design.md](../superpowers/specs/2026-05-31-p2-d-pattern-completion-design.md) | 权限/来源先过滤，时间证据视图默认关闭；保留 tenant/id 与派生证据边界。 |
| [2026-06-01-p2-e-application-surface-design.md](../superpowers/specs/2026-06-01-p2-e-application-surface-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-02-p2-f-admission-eval-design.md](../superpowers/specs/2026-06-02-p2-f-admission-eval-design.md) | 能力探测与 cohort 分开计数；v1/v2 归档分别核验；原分母和晋升门槛保持。 |
| [2026-06-04-p2-g-dashboard-design.md](../superpowers/specs/2026-06-04-p2-g-dashboard-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-06-extractor-real-prompt-design.md](../superpowers/specs/2026-06-06-extractor-real-prompt-design.md) | 两种原生请求契约、合法目录、未决/路由/否定边界；Python 不复制判定。 |
| [2026-06-06-p2-h-oneclick-config-design.md](../superpowers/specs/2026-06-06-p2-h-oneclick-config-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-06-p2-j-social-scope-wiring-design.md](../superpowers/specs/2026-06-06-p2-j-social-scope-wiring-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-07-build-dependency-config-design.md](../superpowers/specs/2026-06-07-build-dependency-config-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-08-dashboard-redesign-design.md](../superpowers/specs/2026-06-08-dashboard-redesign-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-12-p3-b1-localstore-substrate-design.md](../superpowers/specs/2026-06-12-p3-b1-localstore-substrate-design.md) | 保留来源及失败证据、原生存取检查和旧数据兼容；模型不能生成来源证书。 |
| [2026-06-15-p3-b2-openclaw-contract.md](../superpowers/specs/2026-06-15-p3-b2-openclaw-contract.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-15-p3-b2-openclaw-memory-plugin-design.md](../superpowers/specs/2026-06-15-p3-b2-openclaw-memory-plugin-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-17-arbitrary-multi-order-tom-design.md](../superpowers/specs/2026-06-17-arbitrary-multi-order-tom-design.md) | 行为归纳与时间解释保持派生父链；主体、转述与知识边界不因补充谓词扩展而放宽。 |
| [2026-06-17-episodic-event-memory-design.md](../superpowers/specs/2026-06-17-episodic-event-memory-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-18-perception-knowledge-tracking-design.md](../superpowers/specs/2026-06-18-perception-knowledge-tracking-design.md) | 行为归纳与时间解释保持派生父链；主体、转述与知识边界不因补充谓词扩展而放宽。 |
| [2026-06-19-entity-theme-grounding-resolution-design.md](../superpowers/specs/2026-06-19-entity-theme-grounding-resolution-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-19-extraction-completeness-design.md](../superpowers/specs/2026-06-19-extraction-completeness-design.md) | 两种原生请求契约、合法目录、未决/路由/否定边界；Python 不复制判定。 |
| [2026-06-19-extraction-configurability-design.md](../superpowers/specs/2026-06-19-extraction-configurability-design.md) | 两种原生请求契约、合法目录、未决/路由/否定边界；Python 不复制判定。 |
| [2026-06-19-general-content-memory-design.md](../superpowers/specs/2026-06-19-general-content-memory-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-22-deterministic-multiorder-belief-injection-design.md](../superpowers/specs/2026-06-22-deterministic-multiorder-belief-injection-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-23-bdi-k-mental-state-internalization-design.md](../superpowers/specs/2026-06-23-bdi-k-mental-state-internalization-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-24-faux-pas-detection-design.md](../superpowers/specs/2026-06-24-faux-pas-detection-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-06-26-common-knowledge-operator-design.md](../superpowers/specs/2026-06-26-common-knowledge-operator-design.md) | 行为归纳与时间解释保持派生父链；主体、转述与知识边界不因补充谓词扩展而放宽。 |
| [2026-07-01-p3-c-scale-baseline-harness-design.md](../superpowers/specs/2026-07-01-p3-c-scale-baseline-harness-design.md) | 能力探测与 cohort 分开计数；v1/v2 归档分别核验；原分母和晋升门槛保持。 |
| [2026-07-01-persona-subscriber-materialization-design.md](../superpowers/specs/2026-07-01-persona-subscriber-materialization-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-07-02-embedding-batching-design.md](../superpowers/specs/2026-07-02-embedding-batching-design.md) | 网络/推理在事务外；语言绑定只转发；共享传输增加显式策略，原用途保持兼容。 |
| [2026-07-03-write-gate-core-design.md](../superpowers/specs/2026-07-03-write-gate-core-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-07-04-gist-judge-prompt-followup-design.md](../superpowers/specs/2026-07-04-gist-judge-prompt-followup-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-07-04-gist-semantic-entailment-fix-design.md](../superpowers/specs/2026-07-04-gist-semantic-entailment-fix-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-07-05-converse-lock-free-generate-design.md](../superpowers/specs/2026-07-05-converse-lock-free-generate-design.md) | 网络/推理在事务外；语言绑定只转发；共享传输增加显式策略，原用途保持兼容。 |
| [2026-07-11-session-ingestion-channel-design.md](../superpowers/specs/2026-07-11-session-ingestion-channel-design.md) | 网络/推理在事务外；语言绑定只转发；共享传输增加显式策略，原用途保持兼容。 |
| [2026-07-12-metrics-timeseries-design.md](../superpowers/specs/2026-07-12-metrics-timeseries-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-07-12-remember-extraction-lock-free-design.md](../superpowers/specs/2026-07-12-remember-extraction-lock-free-design.md) | 两种原生请求契约、合法目录、未决/路由/否定边界；Python 不复制判定。 |
| [2026-07-13-eval-quality-baseline-design.md](../superpowers/specs/2026-07-13-eval-quality-baseline-design.md) | 能力探测与 cohort 分开计数；v1/v2 归档分别核验；原分母和晋升门槛保持。 |
| [2026-07-14-episodic-extraction-lock-free-design.md](../superpowers/specs/2026-07-14-episodic-extraction-lock-free-design.md) | 两种原生请求契约、合法目录、未决/路由/否定边界；Python 不复制判定。 |
| [2026-07-21-cognizer-subject-kind-design.md](../superpowers/specs/2026-07-21-cognizer-subject-kind-design.md) | 行为归纳与时间解释保持派生父链；主体、转述与知识边界不因补充谓词扩展而放宽。 |
| [2026-09-11-source-grounded-claim-contract-design.md](../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md) | 两种原生请求契约、合法目录、未决/路由/否定边界；Python 不复制判定。 |
| [2026-09-12-claim-generation-design.md](../superpowers/specs/2026-09-12-claim-generation-design.md) | 两种原生请求契约、合法目录、未决/路由/否定边界；Python 不复制判定。 |
| [2026-09-12-socialmem-optimization-design.md](../superpowers/specs/2026-09-12-socialmem-optimization-design.md) | 逐份核对：本轮不新增本子系统生产职责；继续遵守 C++ 唯一核心、证据边界和默认关闭，详细影响统一见本轮两份设计。 |
| [2026-09-12-source-turn-evaluation-design.md](../superpowers/specs/2026-09-12-source-turn-evaluation-design.md) | 能力探测与 cohort 分开计数；v1/v2 归档分别核验；原分母和晋升门槛保持。 |
| [2026-09-13-claim-protocol-boundary-design.md](../superpowers/specs/2026-09-13-claim-protocol-boundary-design.md) | 两种原生请求契约、合法目录、未决/路由/否定边界；Python 不复制判定。 |
| [2026-09-13-relation-evidence-coverage-design.md](../superpowers/specs/2026-09-13-relation-evidence-coverage-design.md) | 全题结构矩阵、关系边界、派生立场与原生时间视图的本轮权威设计。 |
| [2026-09-13-structured-output-capability-design.md](../superpowers/specs/2026-09-13-structured-output-capability-design.md) | 原生协议能力、探测、schema、缓存、失败证据与重试策略的本轮权威设计。 |

## 文档校验和已发现偏差

两份技术报告残留的“真实诊断运行中”已改为前轮最终核验结果。当前文档中 99 个已核实的旧路径引用已修复（重复目录、旧 v24 文件名和迁移后的历史主设计路径）；另将一处被误解析为链接的说明括号改为中文括号；不改历史快照。

本轮目录包括协议能力设计、关系与证据设计、实施计划、1,031 题机器矩阵及其说明、原始失败诊断。结构矩阵是设计资产，不是生产分类器或覆盖正确率。

## 阶段状态

| 阶段 | 状态 |
|---|---|
| 既有文档与结构矩阵 | 已获确认并同步既有实现结果；S/T 本地实现结果单列，真实待运行 |
| 2026-09-15 离线复核与 S/T 设计 | 原文与示例原生核验完成；69 份现行入口同步，本地实现与验证完成，S/T 真实尚未运行 |
| 新 RED 测试及 C++ 实现 | A/B/C 既有实现与本轮共同修复完成；保留各阶段 RED/GREEN 日志 |
| 能力探测与真实评测 | A 两轮获批探测各 8 次 conformant，另有 8 次意外 DNS 失败；A 140 条诊断 verified / complete_with_errors，质量门槛失败；B 和时间 QA 未执行 |
| 2026-09-14 完整工程回归（历史证据） | C++ 1,090/1,090，Python 1,362 passed / 15 skipped；A/B 各 34/34 聚焦测试 |
| 生产晋升与 1,031 题全量 | 未达条件，默认关闭 |

## 设计阶段历史核验

`build/protocol_capability_document_validation.json` 记录实现前的文档阶段检查：66 份当前设计/技术报告/规范和 1 份新清单，636 个本地链接全部可解析；当时 905 个受保护源码、测试及历史快照文件内容未变。彼时原生模块、430 个归档源码文件和原标签与上一轮 manifest 一致。上述源码不变结论只属于实现前的历史阶段。

矩阵的 1,031 个组合身份、问题/消息哈希、来源锚点及题型统计均与本地 Parquet 一致；4 组跨网络重复 QA ID、3 处锚点元数据差异有记录。10 条技术失败的原文哈希与归档逐项一致。以上为文档和只读证据核验，模型调用 0，不是新增工程测试或评测成绩。

## 实现阶段核验

最终源码、模块、测试及 schema 冻结在 `build/socialmem_20260913_coverage_final`，447 项源码/测试与归档一致；104 份历史设计快照哈希无变化。现行设计、清单、计划和报告的链接检查记录于 `build/protocol_coverage_document_validation.json`。原标签、三份 A/B 离线归档及其哈希已重新核验。

2026-09-14 真实探测后再次核对上述源码、最终模块、测试日志、历史设计及三份离线归档，哈希均未变化。当前 70 份文档的 513 个本地链接有效；结果见 `build/socialmem_20260914_capability_analysis/validation.json`。能力报告与阻断归档分别保存 A 的冻结身份，未改写历史本地验证结果。

## 协议恢复实现阶段核验（2026-09-14）

本轮最终封存位于 `build/socialmem_20260914_protocol_recovery_final`，包含源码/测试、核心、schema、日志及独立阶段索引。相对旧最终源码清单只变动 8 个文件；旧封存、原标签、104 份历史设计均未改写。三版本各自 140 条原文重放零差异；A/B 共同补丁的新增/删除行哈希一致，跨核心能力报告全部拒绝。误加载 editable 模块的两份初次离线目录已标记无效，不计入阶段验证。文档、历史及档案核验详见新封存 `validation.json`。此阶段新外部模型调用 0，无 Qwen 能力或质量观测。

## A 阶段真实结果封存

运行归档为 `build/socialmem_20260914_protocol_recovery_a_real`，分析与文档封存为 `build/socialmem_20260914_protocol_recovery_a_analysis`。140 条原生重放、144 数据库、源与回执完整性核验通过；当前产品源码 447 项、A 源码 433 项以及历史设计继续冻结。本轮没有新增产品实现或测试；现行设计入口同步真实结论和后续建议。

## 作用域与超时设计阶段核验（2026-09-15）

本轮只完成离线调查和新中文设计：61 条有响应抽取原文、六份参考示例经冻结 A 原生接口核验，重现七条主作用域成员缺失；超时分布不支持仅归因于长来源。新增设计为 S 提示改进和 T 截止时间对照，两项独立，不改变既有解析失败粒度。69 份现行设计入口已同步待确认状态；本轮源码、测试、模块、104 份历史设计及旧运行/分析封存保持不变，外部请求 0。核验与文档快照见 `build/socialmem_20260915_scope_latency_design`；此前完整回归数字不作为本轮新测试。

## 作用域与超时本地交付核验

本轮完成 C++ 提示改进与原生配置驱动的薄实验编排，具体新验证见[实现报告](../eval/2026-09-15-socialmem-scope-latency-implementation.md)。原设计阶段文档/证据封存保持，新增源码/测试与两套本机请求预览另存于 `build/socialmem_20260915_scope_latency_final`；之前章节保留各自时点，真实质量仍以 A 旧报告为准。

## S/T 真实诊断核验（2026-09-15）

本次用户已明确授权并完成84次请求。32次协议探测通过，52次抽取中42次完整、10次超时；52条原文按冻结核心重放一致。S1提示未改善本组可靠性，T120恢复部分响应但语义/范围/覆盖仍有缺口。现行69入口已同步，详见[真实诊断报告](../eval/2026-09-15-socialmem-scope-latency-real.md)。历史各章节与归档保留原时点，不用新诊断覆盖A成绩。

## 声明范围与覆盖诊断职责（2026-09-15）

L/R0 保持抽取 wire v2、准入 v1 与提示逐字不变；诊断扩展不进入 candidates。原生模块身份会因 parser 改动变化，历史能力报告只支持其原核心，不能为 A+L 或开发树新核心提供真实执行资格。本次确认范围为本地验证，无能力探测或外部请求。

详见[声明范围定位与生成覆盖诊断设计](../superpowers/specs/2026-09-15-claim-scope-localization-design.md)。

## 2026-09-16 范围字段协议对齐

本轮 C++ schema 生成与本地 wire 校验共同要求 scope_markers 非空且唯一；主范围成员关系、范围组合、来源与主体语义仍由 C++ 原生契约执行，binding 不重复判定。评测脚本冻结指定核心、来源、配置及调度，并在每次请求前复验能力和预约预算。真实端点拒绝数组 uniqueItems（两次 HTTP 400），C1 未通过能力门槛，来源样本、入库、检索、QA 均未执行；本地约束对齐不得解释为谓词召回或问答质量提升。当前实验开关继续关闭，提供商 schema profile 分离方案仍待下一轮单独设计与验证。

## 2026-09-16 能力与得分路线修订（已授权自主迭代）

provider wire schema 与完整本地契约拟分离并绑定各自身份；协议修复在当前版本基线完成后实施。已结束实验仍遵守原停止规则；新开发评测不因少量语义错答阻止其余已授权题目执行，生产晋升另设严格门槛。 具体范围、测试与验收见[统一方案](../superpowers/specs/2026-09-16-socialmem-capability-and-score-design.md)。本段描述计划，不代表已经实现或获得新分数。

最新执行顺序已按用户指令调整：先冻结当前默认 Starling 并完成全部 1031 题基线，再按真实失分执行中文文档→失败测试→C++ 改进→同条件复测，循环自主迭代，无需重复申请常规步骤授权。基线前仅补评测编排及题目允许来源范围，不预修被测能力。详见[基线优先执行计划](../superpowers/plans/2026-09-16-socialmem-baseline-first.md)。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 当前只完成行为与离线验证，真实复评尚未封存，不提前宣称质量提升。
