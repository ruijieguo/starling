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

> **R3.1 实评收口（2026-09-20）**：8192 抽取容量消除了本轮可观察的 `completion_truncated`，但出现 3 次 `schema_failure` 和 1 次 `envelope_failure`；固定 57 题结果为 6/57、技术失败 30、3/7 scope。27 题共同 `ok` 配对中两轮各正确 6 题，未证明 QA 提升；8192 不晋升默认。详见 [R3.1 评测报告](../eval/2026-09-20-socialmem-r31-extraction-capacity.md)。

> **R3.1 抽取容量诊断设计（2026-09-20）**：结构化臂的抽取上限拟由 4096 提升至 8192，来源臂保持 4096；回答、裁判、超时、重试、题目和评分协议固定。该轮只验证抽取截断是否为主要技术损失来源，不改变 C++ 解析器、谓词目录或 Python 语义。设计与计划见 [R3.1 设计](../superpowers/specs/2026-09-20-socialmem-r31-extraction-capacity-design.md)。

> **结构化覆盖诊断修正（2026-09-20）**：历史 hybrid_dialogue 17/57 只覆盖 6/7 结构化抽取 scope；另 9 题复用仅来源库。96 条记录仅 14 条有结构化证据，且全部缺会话/话轮时间元数据。本轮补齐 C++ 拒绝分类和评测覆盖门禁，零新模型请求，无新 QA 提升；下一步先补输入与回执。详见[诊断与修复报告](../eval/2026-09-20-socialmem-structured-coverage-diagnosis.md)。本条同步当前评测边界，各子系统原有语义以正文为准，历史分数不重写。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# 语义证据契约设计同步清单

> **2026-09-20 观察者 hybrid 对话策略同步**：C++ `ObserverRetriever` 允许 `mode=hybrid` 与 `focused/focused_window/focused_dialogue/focused_coverage` 组合；`mode=statements` 仍拒绝非 `bm25`，Python 只透传 `ObserverQuery` 和实验预算。固定 57 题的 `hybrid_dialogue` 已完成 17/57、技术失败 0，但默认 seed_k=10 与外层 k=10 导致邻句新增为 0；`hybrid_dialogue_expanded` 改用 seed_k=5、seed_bytes=4000、radius=2 后 15/57，57 题均新增 5 条邻句，未改善 QA，生产默认与历史归档保持不变。下一阶段转向结构化谓词覆盖诊断。
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../eval/2026-09-16-socialmem-scope-schema.md)。

> **R1/B 实测收口（2026-09-16）**：旧 Python/重放误用模块的证据已撤回，D1 已重建验证。真实 16 次探测中 D0 通过、D1 因空 scope_markers 未通过原生契约，按计划停止；四来源样本未执行，不能判定谓词覆盖或问答质量改善。核心逻辑仍在 C++，默认关闭。详见[R1/B 阶段报告](../eval/2026-09-15-socialmem-predicate-coverage-r1b.md)。


> **声明范围本地实施（2026-09-15）**：用户确认的 L/R0 已实现并完成最终本地回归：C++ 1103/1103、Python 1387 通过/15 跳过；A 的 140 条流程重放无差异，S/T 原文仅恢复 1 条已知 Femi 误拒。独立审查与封存核验已完成，详见[实施分析](../eval/2026-09-15-socialmem-claim-scope-implementation.md)。核心仅 C++，无新模型调用或 F1，默认关闭。

> **作用域与超时真实诊断（2026-09-15）**：84 次请求、零重试已完成；S0/S1 完整响应 13/14、10/14，主作用域字段错误 2/3 次；T60/T120 完整响应 8/12、11/12。52 条原文原生重放一致。S1 不晋升，话轮范围误拒与现有谓词召回仍需优化；详见[真实诊断报告](../eval/2026-09-15-socialmem-scope-latency-real.md)，生产默认关闭。

> **协议恢复 A 阶段结果（2026-09-14）**：A 已原生核验 verified / complete_with_errors；固定控制 62/64、误收 0，Q1 linked 3/3；但有 22 条技术失败，P1 低于冻结基线，Q9 无改善，质量门槛未通过。两轮获批探测 16 次服务响应，另有误调用的 8 次 DNS 失败，累计尝试 24 次。详见[A 阶段报告](../eval/2026-09-14-socialmem-protocol-recovery-a.md)；B 未执行，核心仅在 C++，默认关闭。

> **协议能力与关系覆盖进展同步（2026-09-14）**：中文设计→RED 测试→C++ 实现及本地验证已完成（C++ 1,089/1,089、Python 1,355 通过/15 跳过）。授权后真实探测 8 次、零重试，均 HTTP 200，但两种模式的抽取/准入四组均为 `nonconformant`；原生核验 `capability_blocked`，后续评测调用 0、质量为空。详见[最新探测报告](../eval/2026-09-14-socialmem-capability-probe.md)；核心仍仅在 C++，默认关闭，历轮数字保留各自证据时间。

> **最新输出协议与偏好边界结果（2026-09-13 核验）**：中文文档→失败测试→C++ 实现及评测已完成，C++ 1,062 项、Python 1,319 项通过（15 项跳过）。真实诊断 `verified / complete_with_errors`；固定候选 56/64、synthetic 契约 11/16（有效分母 15/16），P1 combined F1 为 0.7317/0.6829/0.7683，Q1/Q9 仅 full 阶段 3/3，质量门槛未通过。详见 [输出协议与偏好边界报告](../eval/2026-09-13-socialmem-protocol-boundary.md)。此前各阶段数字保留各自证据时间。

> **来源话轮阶段进展（2026-09-12）**：C++ 版本化输入及独立扩展标签已实现，完整回归及离线/真实原生核验通过；真实质量门槛未通过。此前各阶段“时间输入/扩展标签未完成”的描述为当时状态；当前交付范围与剩余限制见 [来源话轮评测报告](../eval/2026-09-12-socialmem-source-turn.md)。

> **本轮中文优化设计（2026-09-12）**：谓词/言语行为校验、SourceTurn 主题与时间元数据、结构化输出可靠性和扩展评价标签统一见 [SocialMemBench 谓词与来源上下文优化设计](../superpowers/specs/2026-09-12-socialmem-optimization-design.md)。本轮新增或修改的设计说明均使用中文；历史快照保持不可变。

本轮评测记录见 [优化评测报告](../eval/2026-09-12-socialmem-optimization.md)。

## 2026-09-23 R4.4 consolidated source 回连同步

R4.4 真实评测结束后发现，`source_documents` 的 consolidated engram id 与
`semantic_claim_json.source_span.engram_ref` 的原始逐话轮 id 不同，导致已合法的
声明 metadata 被静默跳过。修复已按“文档 → RED 测试 → C++ 实现”执行：

- C++ `ObserverRetriever` 在同一 tenant、holder、speaker 范围内，以
  `speaker、turn_id、session_id、turn_index、observed_at` 五元 `source_turn` 建立
  受限回连；原始 claim 仍必须通过 hash、source unit、时间、擦除和契约重放。
- 回连成功才增加 `claim_metadata_loaded` 和
  `claim_reconciliation_succeeded`；不一致、歧义、缺失和跨范围情况记录
  `claim_reconciliation_rejection_reasons`，不把 metadata 放进回答上下文。
- Python 只接收策略和诊断字段，不解析 `semantic_claim_json`，也不复制谓词或角色
  规则；旧策略和生产默认保持不变。

新增 C++ fixture 覆盖 consolidated/original 两个 engram 的合法回连和话轮身份不一致
时的拒绝；48 项 source/recovery/coverage/profile 回归全部通过。该工程诊断尚未证明
SocialMemBench QA 提升，是否进入下一轮真实评测须以冻结回放确认 metadata 加载率后再决定。

## 2026-09-19 结构化记忆闭环首轮同步

按已确认的[结构化记忆闭环设计](../superpowers/specs/2026-09-19-socialmem-structured-memory-closure-design.md)完成首轮 C++ 实施：`claim-predicate-v2` 是抽取提示、合同 JSON、别名归一和语义族统计的唯一来源；抽取 receipt 增加目录版本、按谓词接受/拒绝计数、失败类别、来源保留和结构化声明持久化状态；结构化检索入口先执行来源证据、tenant/holder/subject 范围和目录重放，再选择主题、截止时间及 temporal early/late 候选。Python 只暴露 C++ 类型和回执，不复制任何谓词或证据规则。

本轮新鲜验证为：C++ 专项 `StructuredMemoryClosure` 8/8 通过；Python 结构化目录、合同表面和 temporal 组合 10/10 通过。完整 C++ 回归 1200/1201 通过，唯一失败是当前沙箱禁止 loopback listener 的既有 OpenAI HTTP 测试；`remember_phases` Python 组合因当前环境未安装可选 `fastapi` 无法收集。现有专项夹具已覆盖目录扩展/别名、否认与人物归属、失败时来源保留、跨 tenant 与无效来源排除，但 temporal 正向持久化候选的闭环率尚未完成独立测量，离线门槛暂不通过。

因此本轮没有新的 DashScope 请求、没有新的 SocialMemBench 分数，也没有修改历史评测归档、裁判或参考答案。补强正向 source/temporal fixture 后，才允许按冻结的 `qwen3.8-27b` 口径进行一次结构化对照。

2026-09-12 优化实现已通过工程验证；真实诊断在 Q1 阶段发现并修复了评测器对失败 pipeline 的中断问题，修复后的最终目录已由验证器核验为 `verified`，运行状态为 `complete_with_errors`。

**状态（2026-09-12）：已实现；完整构建、全量测试、独立审查和离线诊断通过；真实诊断已完成并核验为 complete_with_errors，质量门槛未通过，默认关闭。**

核心生产逻辑统一在 C++：语言 binding 仅映射类型/配置、转发调用；评测脚本仅编排、归档与统计。主设计为 [Source-Grounded Claim Contract](../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md)。

| 文档范围 | 同步方式 |
|---|---|
| [总设计](system_design.md) | 更新 Statement、时间锚、C++ 边界、存储与检索契约。 |
| subsystems_design 下全部 12 份文档 | 更新正文职责、失败分类、直接/派生证据边界及统一状态。 |
| 两份 Starling_Technical_Report | 新扩展独立标注，原有基准数字仍为历史结果。 |
| 当前评测 overview/admission | 链接后继诊断；历史归档和分数不变。 |
| docs/design/history 下全部版本快照 | 历史证据，按已确认方案保持不可改写。 |

## 本轮修复同步（2026-09-12）

最新修复证据见 [可空主题与情绪误拒修复报告](../eval/2026-09-12-socialmem-repair.md)。

可空主题预检、情绪误拒和重复裁判统计按中文优化设计继续实施。总设计、Bus、EngramStore、Hippocampus、Retrieval、数据本体、抽取提示和质量基线专项设计已同步。其余子系统继续遵守原证据契约，无新增职责；历史快照不改写。结构化输出能力声明、完整扩展标签与来源时间输入尚未完成，上一轮“全部完成”的表述仅适用于已列出的工程改动。

## 专项设计逐份核对

| 专项设计 | 本次影响 |
|---|---|
| [2026-05-24-m0-7-acceptance-design.md](../superpowers/specs/2026-05-24-m0-7-acceptance-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-05-26-p2-a-social-mind-schema-design.md](../superpowers/specs/2026-05-26-p2-a-social-mind-schema-design.md) | 可选 SemanticClaimEvidence 与 SQL JSON 字段；旧 schema 数据兼容。 |
| [2026-05-27-p2-b-brain-dynamics-core-design.md](../superpowers/specs/2026-05-27-p2-b-brain-dynamics-core-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-05-27-p2a-v12-prompt-fallback.md](../superpowers/specs/2026-05-27-p2a-v12-prompt-fallback.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-05-30-p2-b-vector-layer-design.md](../superpowers/specs/2026-05-30-p2-b-vector-layer-design.md) | 检索候选在 C++ 中校验来源证据后才暴露链接。 |
| [2026-05-30-p2-c-prospective-affect-design.md](../superpowers/specs/2026-05-30-p2-c-prospective-affect-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-05-31-p2-d-pattern-completion-design.md](../superpowers/specs/2026-05-31-p2-d-pattern-completion-design.md) | 可选语义证据在 C++ 中先于种子激活和每跳传播校验；失效桥接节点不能继续传播，排除计数按 (tenant_id, statement_id) 去重。 |
| [2026-06-01-p2-e-application-surface-design.md](../superpowers/specs/2026-06-01-p2-e-application-surface-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-02-p2-f-admission-eval-design.md](../superpowers/specs/2026-06-02-p2-f-admission-eval-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-04-p2-g-dashboard-design.md](../superpowers/specs/2026-06-04-p2-g-dashboard-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-06-extractor-real-prompt-design.md](../superpowers/specs/2026-06-06-extractor-real-prompt-design.md) | 旧数组格式保留；仅实验补充通道启用 v2 契约。 |
| [2026-06-06-p2-h-oneclick-config-design.md](../superpowers/specs/2026-06-06-p2-h-oneclick-config-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-06-p2-j-social-scope-wiring-design.md](../superpowers/specs/2026-06-06-p2-j-social-scope-wiring-design.md) | 证据链接沿用 tenant/perspective 可见性，不能扩大 scope。 |
| [2026-06-07-build-dependency-config-design.md](../superpowers/specs/2026-06-07-build-dependency-config-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-08-dashboard-redesign-design.md](../superpowers/specs/2026-06-08-dashboard-redesign-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-12-p3-b1-localstore-substrate-design.md](../superpowers/specs/2026-06-12-p3-b1-localstore-substrate-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-15-p3-b2-openclaw-contract.md](../superpowers/specs/2026-06-15-p3-b2-openclaw-contract.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-15-p3-b2-openclaw-memory-plugin-design.md](../superpowers/specs/2026-06-15-p3-b2-openclaw-memory-plugin-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-17-arbitrary-multi-order-tom-design.md](../superpowers/specs/2026-06-17-arbitrary-multi-order-tom-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-17-episodic-event-memory-design.md](../superpowers/specs/2026-06-17-episodic-event-memory-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-18-perception-knowledge-tracking-design.md](../superpowers/specs/2026-06-18-perception-knowledge-tracking-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-19-entity-theme-grounding-resolution-design.md](../superpowers/specs/2026-06-19-entity-theme-grounding-resolution-design.md) | 实验文本对象保真、actor/holder 约束；旧主题规范化不变。 |
| [2026-06-19-extraction-completeness-design.md](../superpowers/specs/2026-06-19-extraction-completeness-design.md) | 补充抽取保留 topic/时间/归属，不从问答金标生成输入。 |
| [2026-06-19-extraction-configurability-design.md](../superpowers/specs/2026-06-19-extraction-configurability-design.md) | 新增默认关闭的契约/信封策略；C++ 统一验证，binding 仅映射。 |
| [2026-06-19-general-content-memory-design.md](../superpowers/specs/2026-06-19-general-content-memory-design.md) | 三通道 C++ 编排将通用事实保持在旧策略路径。 |
| [2026-06-22-deterministic-multiorder-belief-injection-design.md](../superpowers/specs/2026-06-22-deterministic-multiorder-belief-injection-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-23-bdi-k-mental-state-internalization-design.md](../superpowers/specs/2026-06-23-bdi-k-mental-state-internalization-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-24-faux-pas-detection-design.md](../superpowers/specs/2026-06-24-faux-pas-detection-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-06-26-common-knowledge-operator-design.md](../superpowers/specs/2026-06-26-common-knowledge-operator-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-07-01-p3-c-scale-baseline-harness-design.md](../superpowers/specs/2026-07-01-p3-c-scale-baseline-harness-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-07-01-persona-subscriber-materialization-design.md](../superpowers/specs/2026-07-01-persona-subscriber-materialization-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-07-02-embedding-batching-design.md](../superpowers/specs/2026-07-02-embedding-batching-design.md) | C++ OpenAIEmbeddingAdapter 暴露只读原子 request_count、embed_calls、batch_calls；request_count 统计实际 HTTP 尝试（含失败和重试），空批次不产生请求，未执行的分块不计数。语言 binding 只暴露属性。 |
| [2026-07-03-write-gate-core-design.md](../superpowers/specs/2026-07-03-write-gate-core-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-07-04-gist-judge-prompt-followup-design.md](../superpowers/specs/2026-07-04-gist-judge-prompt-followup-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-07-04-gist-semantic-entailment-fix-design.md](../superpowers/specs/2026-07-04-gist-semantic-entailment-fix-design.md) | 新摘要保留父链，不继承直接准入证书。 |
| [2026-07-05-converse-lock-free-generate-design.md](../superpowers/specs/2026-07-05-converse-lock-free-generate-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-07-11-session-ingestion-channel-design.md](../superpowers/specs/2026-07-11-session-ingestion-channel-design.md) | 整行/整轮 source unit 不丢说话者前缀与前置条件。 |
| [2026-07-12-metrics-timeseries-design.md](../superpowers/specs/2026-07-12-metrics-timeseries-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-07-12-remember-extraction-lock-free-design.md](../superpowers/specs/2026-07-12-remember-extraction-lock-free-design.md) | C++ 抽取与准入均在事务外；提交核验 prepared Engram。 |
| [2026-07-13-eval-quality-baseline-design.md](../superpowers/specs/2026-07-13-eval-quality-baseline-design.md) | P1 原标签保持，同时报告 base 与 combined，诊断与代表性结果分开。 |
| [2026-07-14-episodic-extraction-lock-free-design.md](../superpowers/specs/2026-07-14-episodic-extraction-lock-free-design.md) | 原适用范围不变；本次未修改对应子系统契约。 |
| [2026-07-21-cognizer-subject-kind-design.md](../superpowers/specs/2026-07-21-cognizer-subject-kind-design.md) | 五个实验谓词要求 cognizer actor；旧事实 subject 规则保留。 |
| [2026-09-11-source-grounded-claim-contract-design.md](../superpowers/specs/2026-09-11-source-grounded-claim-contract-design.md) | 本次权威设计；已统一 wire/native 字段、C++ 边界和固定候选评测口径。 |

## 实验范围与证据

64 个固定候选（32 旧 + 32 新；新组中英与正负平衡）在第一次真实调用前冻结。76 次新抽取包含 50 P1、16 synthetic 和 10 个已复核 speaker groups；准入最多 140 次。另有 96 次 synthetic judge votes、8 个 QA 回答及 24 次 QA judge votes。

前状态归档：`build/socialmem_claim_contract_before/manifest.json`。新测试先记录失败后实现。存储枚举大小写、图传播过滤、排除计数、Engram transformation 回读和跨抽取幂等身份问题均已按回归测试修复。完整构建与原生安装通过；Python 1,273 passed / 15 skipped；C++ 全量 1,024 passed / 1 skipped，跳过的本地 HTTP 测试在沙箱外补跑通过（合计 1,025 项）。

离线诊断 `build/socialmem_claim_contract_final_smoke/` 已由加强后的验证器核验 140 次原生重放、144 个数据库、76 个抽取记录、64 个固定候选、8 个回答与 120 次裁判记录。全部技术失败计数为零；Fake 模型分数不作为模型质量证据。独立审查发现并修复直接 Bus 写入绕过关系契约、查询 embedding 降级漏计与上下文缺少原生重建/链接完整性验证；全部修复已独立复审关闭。首次真实启动因缺少模型元数据 binding 在调用前失败（0 次模型请求）；补充统一原生接口转发及回归测试后，最终真实诊断位于 `build/socialmem_20260912_optimization_real_final/`，并由验证器核验 140 次原生重放、144 个数据库、76 次抽取、64 个注入候选和 120 次裁判投票。

语义拒绝与技术失败区分；Q1/Q9 诊断仍执行，质量门槛不通过则继续关闭默认策略和 1,031 题代表性全量评测。


## 前轮实测结论（修复前冻结档案）

[优化评测报告](../eval/2026-09-12-socialmem-optimization.md)和[逐项分析](../eval/2026-09-12-socialmem-claim-contract-analysis.json)是结果入口。最终目录中 76 次抽取、51 次准入调用、64 个固定候选注入、8 次回答尝试、120 次裁判投票均已归档；验证器状态为 `verified`，运行状态为 `complete_with_errors`。固定候选为 61/64；synthetic 冻结组 13/16、契约组 4/16；P1 保留基线的 combined F1 下降。

Q1 baseline/structured/linked/full 分别为 3/3、1/3、1/3、3/3；Q9 分别为 0/3、0/3、0/3、3/3。共 16 个技术失败，主要为 schema 信封失败；来源证据、embedding、检索和裁判链路无失败。来源契约和 C++ 统一实现已验证，整体质量提升和生产准入未被证明，`promotion_ready=false`，1,031 题代表性评测未运行。后续应先修复言语行为误拒、主题/原始时间上下文和 schema/传输稳定性；本轮冻结档案不改写。

## 最新修复与实测结论（2026-09-12）

[可空主题与情绪误拒修复报告](../eval/2026-09-12-socialmem-repair.md)与[逐项分析](../eval/2026-09-12-socialmem-repair-analysis.json)为最新结果入口。C++ 1,033 项测试（含本地 HTTP 补跑）和 Python 1,278 项测试通过，15 项 Python 跳过；真实诊断 `build/socialmem_20260912_repair_real/` 已核验为 `verified / complete_with_errors`，140 次原生重放、144 个数据库及来源/回答上下文完整性通过。

原生技术失败由 16 降至 8；固定对照 59/64，synthetic 契约组 8/16、冻结组 12/16，P1 combined F1 仍低于 base。Q1/Q9 的 baseline、structured、linked 均为 0/3，full 为 3/3；1 个无效裁判票。解析修复和局部信息恢复已被证明，整体准确率提升尚未证明；默认关闭，1,031 题全量未运行。

本轮范围包括可空主题的原生预检、部分情绪误拒修复、裁判一致率和有效分母。结构化输出能力声明、完整扩展标签和来源时间输入仍待后续验证和实现；中文职责/情绪与 Unicode 空白边界已完成 C++ 修复并通过真实诊断。

## 2026-09-12 JSON mode 设计同步

本轮仅增加默认关闭的 C++ `json_object_output` 请求选项，表达请求意图，不等同于服务端能力或 schema 保障。抽取开启时原文保真，普通生成不受影响，旧数组抽取应使用默认配置实例。Python 仅映射配置与编排独立实验，manifest 记录请求模式。非法原因仍为技术失败；完整能力协商与 JSON Schema 待实现。

总设计、两份技术报告、抽取器真实提示/可配置设计、自由生成设计、质量基线和两份契约权威设计同步更新。其余当前专项与 12 个子系统已逐项按上表核对：存储、检索、归属与传播契约不变，无新增职责；历史快照保留。验证与实测结果在完成后补充，不沿用前轮测试数量冒充本轮证据。

### 原生错误回执补充（2026-09-12）

独立审查复现：有效 UTF-8 原文中的中文尾随解释被严格解析拒绝后，第三方解析异常文本可能截断多字节字符，导致 JSON 回执编码失败。C++ 将底层 JSON 解析异常转换为稳定、可编码的 `envelope_failure` 诊断，不将底层 token 摘录直接写入错误信息；原始模型响应一字不改，技术失败仍计入严格分母。先补抽取和准入两条路径的中文尾随文本回执失败测试，再实现；不得使用替换式 JSON 编码清洗整个回执。

## JSON mode 本轮验证状态（2026-09-12）

C++ 1,041 项、Python 1,282 项测试通过（Python 15 项跳过），离线 140 记录/144 数据库核验通过。独立审查发现的中文尾随文本错误回执已用 C++ 修复，原文及技术失败状态保持；服务端最小探测接受参数但未严格输出裸 JSON。140 条真实诊断已完成并核验；最新中文边界结果见 JSON mode 报告。完整证据见 [中文 JSON mode 报告](../eval/2026-09-12-socialmem-json-mode.md)。完整 schema、能力协商、扩展标签与时间输入继续列为未完成。


## 中文职责/情绪与 Unicode 空白同步（2026-09-12）

确定性 `feels` 认知拒绝仅识别明确“X 负责……”责任命题；“职责/责任”出现在情绪对象中不再单独触发拒绝。主题 trim 统一识别 ASCII 空白、NBSP 与 U+3000，空主题仍 schema 失败。规则由 C++ 契约解析器唯一实现，Python 只转发。


## 中文边界真实评测结论（2026-09-12）

`build/socialmem_20260912_chinese_unicode_real/` 已核验 `verified / complete_with_errors`。固定候选 56/64，synthetic 冻结 10/16、契约 8/16，P1 combined holder/perspective/predicate-object F1 为 0.7101/0.6627/0.7456，原生技术失败 8；契约裁判两两一致率 100%。中文职责/情绪混合句误拒已消除，但固定与 P1 下降，不能宣称整体质量提升或生产就绪；Unicode 规则已由 C++ 回归覆盖，当前 cohort 未含对应固定样本。


## 来源时间与独立扩展标签（2026-09-12）

按已批准优化范围执行 [中文来源话轮设计](../superpowers/specs/2026-09-12-source-turn-evaluation-design.md)。C++ 生成并解析版本化话轮，保留原始消息时间与 UTF-8 来源位置，正文与元数据分开校验；Bus/检索重建 source_turn 防止篡改。Python 仅映射和统计，独立扩展标签不进入模型输入，不修改原 P1 金标。真实时间不推断为事件时间或 UTC；已完成 C++ 实现、全量测试、离线与真实核验；真实诊断为 verified / complete_with_errors，质量门槛未通过。普通正文冒号保留完整语义，直接写入/回读使用共享严格解析器拒绝嵌套重复键。详见 [来源话轮评测报告](../eval/2026-09-12-socialmem-source-turn.md)。

本次补充核对：两份来源话轮设计/计划、总设计、两份技术报告、全部 12 个子系统、抽取提示/可配置/会话摄取/质量基线与两份契约权威设计已同步当前职责和状态。表内其他专项设计未新增行为，继续按各自职责适用；历史快照和旧评测数值保持。本轮新增独立评价统计和原生 SourceTurn 防篡改，普通文本冒号兼容与嵌套重复键检查已纳入统一证据契约。


## 生成契约完整性同步（2026-09-12）

按 [中文生成契约设计](../superpowers/specs/2026-09-12-claim-generation-design.md)，C++ 在抽取提示中明确对象、逐字主题、原始时间限定和字段类型约束，并提供与本次来源隔离的通用中英文参考示例。模型输出校验、准入、存储/检索与默认开关保持既有约束，Python 仅绑定和评测编排；参考示例不作为当前证据。本轮 C++ 实现、完整回归、离线核验及历史响应 140/140 一致性重放已完成；真实诊断于北京时间 2026-09-13 完成核验，为 `verified / complete_with_errors`。固定候选 59/64、synthetic 契约 13/16、独立对象 12/14、主题/联合各 1/14，原生技术失败 5；主题字面匹配分数不能解释为字段缺失。P1 兼容与逐例不退步门槛仍失败，Q1/Q9 结构化及链接组仍为 0/3，默认关闭。详见 [生成契约评测报告](../eval/2026-09-12-socialmem-generation.md)。其他专项职责沿用设计同步清单，历史快照保持。

## 输出协议与偏好边界同步（2026-09-13）

按 [中文修复设计](../superpowers/specs/2026-09-13-claim-protocol-boundary-design.md) 继续已批准优化：C++ 提示强调键唯一、时间原文及同话轮引用，准入与解析共用合法原因目录，窄范围拒绝把明确偏好对象写成 feels。真情绪不因同源其他偏好句被拒；Bus/回读复用共享契约，Python 仅绑定与编排。当前已完成 RED、C++ 实现与复审修复后的完整回归（C++ 1,062 项，Python 1,319 项通过/15 项跳过）；旧响应重解析 137/140 一致，3 条偏好误标候选提前拒绝。复合/因果情绪及被动 preferred 感受保留准入，句尾标点边界有正反例覆盖。独立复审发现均已关闭，最终离线 140 条/144 数据库核验通过；真实诊断已完成并由原生验证器核验为 `verified / complete_with_errors`：140 条重放、144 个数据库；固定候选 56/64（TP 30、TN 26、误收 0、误拒 1、技术失败 7），synthetic 冻结 11/16、契约 11/16（有效分母 15/16），P1 combined F1 为 holder 0.7317、holder/perspective 0.6829、predicate/object 0.7683；扩展标签 object/topic/scope/time/joint 为 12/14、2/14、12/14、12/14、2/14（有效目标 13）；Q1/Q9 的 baseline、structured、linked 均为 0/3，full 均为 3/3；实际证据链仍受入库与证据聚合限制。原生技术失败共 10 条，主要为重复 JSON 键和准入 JSON 后追加文本；无效裁判票 0。`promotion_ready=false`，生产默认保持关闭，不运行 1,031 题全量。默认、原标签、检索与历史归档保持。

## 声明范围与覆盖诊断职责（2026-09-15）

本次同步既有 69 个现行设计入口并新增范围设计，共 70 个。L 只修复受限句首逐字声明，R0 只补原始行索引和覆盖阶段可观测性；不同时修改生成提示、关系 B 或时间策略。所有新增说明为中文。104 个历史设计快照保持原 hash；现有 S/T 报告和实施计划只追加后继指向，保留原证据时点。

详见[声明范围定位与生成覆盖诊断设计](../superpowers/specs/2026-09-15-claim-scope-localization-design.md)。

## 2026-09-16 范围字段协议对齐

本轮 C++ schema 生成与本地 wire 校验共同要求 scope_markers 非空且唯一；主范围成员关系、范围组合、来源与主体语义仍由 C++ 原生契约执行，binding 不重复判定。评测脚本冻结指定核心、来源、配置及调度，并在每次请求前复验能力和预约预算。真实端点拒绝数组 uniqueItems（两次 HTTP 400），C1 未通过能力门槛，来源样本、入库、检索、QA 均未执行；本地约束对齐不得解释为谓词召回或问答质量提升。当前实验开关继续关闭，提供商 schema profile 分离方案仍待下一轮单独设计与验证。

## 2026-09-16 能力与得分路线修订（已授权自主迭代）

能力与得分修订方案为后续目标入口。后续顺序为当前版本全量基线、按失败证据补能力、同条件复测与网络级保留验证；当前已获自主迭代授权。 具体范围、测试与验收见[统一方案](../superpowers/specs/2026-09-16-socialmem-capability-and-score-design.md)。本段描述计划，不代表已经实现或获得新分数。

最新执行顺序已按用户指令调整：先冻结当前默认 Starling 并完成全部 1031 题基线，再按真实失分执行中文文档→失败测试→C++ 改进→同条件复测，循环自主迭代，无需重复申请常规步骤授权。基线前仅补评测编排及题目允许来源范围，不预修被测能力。详见[基线优先执行计划](../superpowers/plans/2026-09-16-socialmem-baseline-first.md)。

## 2026-09-17 来源时间与响应完成状态修复

来源v1严格契约保持；显式容错只为无效字符串时间生成v2，规范元数据保留raw_observed_at和time_status=invalid，observed_at为null，声明证据也保留这些权威元数据。模型不得改写它们。OpenAI兼容非流式legacy抽取与普通生成统一将length、content_filter、refusal标为失败并保留原始响应及usage；Python不重复核心判定。详见[修复设计](../superpowers/specs/2026-09-17-baseline-recovery-design.md)。

## 2026-09-19 结构化闭环正向夹具补强

在首轮审计发现空候选夹具后，补充真实 C++ 正向路径：FakeLLM 的 v2 抽取与 admission 响应经过同一原生合同，声明写入后显式完成 consolidation，再由 BasicRetriever 取回并交给 `structured_claim_retriever` 做来源证据认证；另有两条带 Engram source hash/span 和 SourceTurn 元数据的 early/late 选择。专项 C++ 现为 9/9，相关合同/证据/抽取/记忆回归为 105/105，Python 结构化组合为 10/10，正向夹具 3/3。离线闭环门槛在专项范围通过，完整回归唯一 loopback 失败单独标注为沙箱环境限制；此状态允许一次固定 `qwen3.8-27b` 对照，但不代表 QA 已提升。

## 2026-09-20 全部现行设计同步

现行总设计、子系统设计、全部专项 specs 与两份技术报告共96份入口已经逐份添加本次覆盖修正与报告链接；修改前后哈希见 `build/socialmem_20260920_coverage_diagnosis/design-sync.json`。历史设计快照保留原样。具体变化限于 C++ 原生拒绝分类/超时诊断与 Python 评测覆盖协议，其他子系统正文职责不变。SourceTurn 抽取输入及完整 admission 归档仍待下一轮接线，不能根据现行入口的旧闭环说明推断这两项已经在57题真实评测中完成。

## R2 谓词覆盖扩展设计同步（2026-09-20）

本阶段承接结构化覆盖诊断和 SourceTurn/三通道回执修复，目标是补齐结构化合同与 legacy mental-state 之间的能力断层。C++ 原生目录版本升级为 `claim-predicate-v3`，新增 `prefers`、`promises`、`doubts`、`believes`、`responsible_for`、`requires`、`forbids` 七类规范谓词及受控别名；既有谓词、来源证据、admission 和持久化格式保持兼容。目录、别名、语义族、允许模态/极性、抽取提示和准入提示均由 C++ `PredicateCatalog` 唯一生成，Python 只绑定、编排和归档，不维护第二份语义逻辑。

本阶段严格执行中文设计文档 → C++/Python RED 测试 → C++ 实现 → 固定协议回归。测试覆盖中英文正反例、错误模态、主体与对象保真、admission 拒绝计数、`knows` 历史模态兼容、三通道证据回读和 Python binding 边界。新增结构化声明数量或离线测试通过率不等于 QA/F1 提升；只有 7/7 scope、36/36 holder 的同协议 SocialMemBench 结果和预注册统计门槛满足后，才讨论晋升。生产默认仍保持 `semantic_claim_contract=false`。

## R2.1 结构化输出协议修正（2026-09-20）

首次 `claim-predicate-v3` 固定评测中，qwen3.8-27b 在 legacy 结构化请求下出现截断、未转义 JSON 和证据范围不完整，57 题中 47 题在抽取建库阶段失败。该结果只说明协议性技术失败，不能解释为谓词扩展导致 QA 下降。下一轮由 C++ `OpenAIAdapter::extract_with_contract` 使用 `ValidationPolicy.claim_output_mode=JsonObject` 发送原生 `response_format`；C++ 继续执行 envelope、schema、scope、admission 和持久化校验，Python 仅传递配置和归档回执，不清洗模型文本。生产默认仍为 `semantic_claim_contract=false`、`claim_output_mode=Legacy`；新评测必须使用独立身份并分别报告技术完成率和 QA。

## R2.2 结构化输出末端格式提醒（2026-09-20）

针对 JSON Object 实评中出现的“整条 statement 字段嵌入 evidence”响应，C++ 抽取提示在源数据之后增加唯一的顶层字段提醒。该修改不做字段补齐或语义修复；原生合同继续拒绝误嵌套和缺少 `holder_perspective` 的响应。测试和评测方案见 `docs/superpowers/specs/2026-09-20-socialmem-structured-output-robustness-design.md`。

## R2.3 重复键与布局对照（2026-09-20）

针对第二轮真实回执中的重复 JSON key 与 evidence 误嵌套，C++ 末端提示加入唯一键约束和占位 BAD/GOOD 布局对照。该提示只改善生成协议，不放宽 `strict_json` 或声明合同。

### R2.3 实评证据收口（2026-09-20）

独立网络评测完成 57/57 题，7/57 正确、26/57 技术失败；4/7 scope 完成，holder 为 19/36。失败包括重复 `time_text`/`topic` 的 `envelope_failure`、抽取超时、抽取/回答 `completion_truncated`。两轮共同完整题目只有 17 题，不能从 15/57 与 7/57 的非配对差异推断提示因果收益。当前仍保持 C++ 严格拒绝和 Python 仅 binding/编排，生产默认 `semantic_claim_contract=false`；完整证据见 [R2.3 鲁棒性评测报告](../eval/2026-09-20-socialmem-structured-output-robustness.md)。

## R3.2 结构化信封与字段归属设计（2026-09-20）

R3.1 原始回执显示重复 `time_text`/`topic` key、statement 字段嵌入 `evidence` 和缺字段风险仍会阻断结构化 scope。R3.2 先完成中文设计，再由 C++ 提示生成末端结构模板和唯一 key 检查；`strict_json`、wire schema、scope、admission 和原始回执边界不放宽，Python 不做展平、补字段或谓词判断。设计与计划见 [R3.2 设计](../superpowers/specs/2026-09-20-socialmem-r32-schema-envelope-design.md) 和 [实施计划](../superpowers/plans/2026-09-20-socialmem-r32-schema-envelope.md)。本段不代表已完成实现或产生新 QA 分数。

## R3.2 结果与 R3.3 证据覆盖边界（2026-09-21）

R3.2 结构化信封实评完成 57/57 题，技术失败 1，正确 13/57，成功子集 13/56；技术协议显著改善但共同正常题没有证明语义 QA 提升。逐题回执显示，错误主因是目标来源话轮未进入上下文、跨 session 只有一端或人物观察与被描述主体混在一起。后继 R3.3 只改 C++ 来源检索和 hybrid SOURCE 配额，继续由 `claim_contract` 负责严格解析、目录和 admission；不在 Python 复制谓词、证据或来源选择逻辑。详见[R3.2 报告](../eval/2026-09-20-socialmem-r32-schema-envelope.md)与[R3.3 设计](../superpowers/specs/2026-09-21-socialmem-r33-evidence-coverage-design.md)。

R3.3 未修改 `claim-predicate-v3`、scope、admission 或证据合同。真实结果为 11/57、19 道技术失败，成功子集 11/38；来源配额实现和离线覆盖通过不等于合同语义质量提升，生产 `semantic_claim_contract` 开关和 Python binding 边界保持原值。

## R3.4 协议有限重试边界（2026-09-21）

R3.3 回执把重复 key 归为 `envelope_failure`、目录外谓词归为 `schema_failure`。R3.4 由 C++ policy 显式控制最多一次纠错重试，并在每个 attempt 保存实际 prompt/hash 和原始响应；strict parser、scope、admission、source proof 和持久化仍是唯一裁决。Python 只映射 `claim_protocol_retry_budget`，不实现 retry、JSON 修补或谓词目录。生产默认仍为 0 和 `semantic_claim_contract=false`。

## R3.5 字段级 schema 诊断与 holder 隔离（2026-09-21）

`ParseError` 增加可选 `field_path`，结构化 receipt 的每次错误同时保存 kind、detail、路径、prompt/hash 和原始响应。C++ retry prompt 只携带确定性错误摘要和完整源上下文，不复制模型原文；重试仍限于 envelope/schema，最多一次。C++ 同时把最后一个失败 attempt 的 kind/路径/detail 或传输错误归一到 `failure_detail`，并在持久化异常时覆盖，保证 holder 汇总无需解析 receipt 才能定位首要原因。多 holder 评测通过 C++ 原生批量管线逐 holder prepare、extract、commit，单个 holder 失败转为可审计结果并继续后续 holder。Python 仅绑定、字段映射和归档。partial scope 的 QA 与完整 holder 子集分开统计，不能当作完整 scope 或生产质量；默认开关与历史 receipt 保持不变。

## R4.5 声明回连后的车道计数边界（2026-09-23）

R4.5 的 claim metadata 仍由 C++ 合同、证据校验和 source_turn 回连唯一裁决。`state_chain_claim_selected`、`belief_attribution_claim_selected`、`member_claim_selected` 只说明已校验声明真正占用了最终来源名额，不代表答案语义已经验证；`claim_lane_fallbacks` 仅记录成员车道成功新增普通来源的回退。Python 不解析 semantic_claim_json、不维护第二份谓词或人物规则。真实 QA、来源锚点覆盖和 metadata 计数继续分开报告。


### R4.6 车道计数与排序补充（2026-09-23）

v6 的 `lane_selected` 仅由成功的 `take()` 计一次，claim 计数仅统计该车道新选入的有效 claim。共享来源只归属于首次选中它的车道，可以满足其他覆盖要求，但不重复计数也不记回退。`claim_lane_fallbacks` 仅统计成员车道成功新增普通来源的次数，不统计名额/字节预算拒绝、缺失候选和 relevance 补齐。状态与归属车道保持严格 claim 资格。成员车道按有效 claim 优先稳定分组，组内沿用相关性排序，避免仅因时间早而抢占题目相关来源。内部优先级使用资格布尔值和现有排序，不新增无标定的浮点 claim 分数。R4.5 历史分数与 R4.6 新核心结果分开记录。


R4.6 真实复评已封存：检索与原生回答均 15/57，来源锚点 48/104，546/600 次 HTTP，检索臂 1 次 512-token 截断。相对 R4.5 所有判分变化来自相同 prompt 的题目，变更 prompt 队列没有判分变化；无可归因的准确率提升，不晋升。底层 102 条 claim 全为第一人称，归属车道排除自述导致选中数为 0；同一来源多 claim 的单视图覆盖风险待下一轮 RED 验证。当前契约与详细结论见本文顶部 R4.6 中文报告入口。


## R4.7 多声明与第一人称归属设计入口（2026-09-23）

R4.6 暴露了同一来源多条 claim 覆盖和第一人称信念无法进入归属车道的问题。R4.7 先保留全部通过证据校验的 claim，再按人物边界进入 C++ 归属车道；设计见 [2026-09-23-socialmem-r47-multi-claim-attribution-design.md](../superpowers/specs/2026-09-23-socialmem-r47-multi-claim-attribution-design.md)，实施计划见 [2026-09-23-socialmem-r47-multi-claim-attribution.md](../superpowers/plans/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.7 已完成离线、真实复评和最终封存核验，详见[中文诊断报告](../eval/2026-09-23-socialmem-r47-multi-claim-attribution.md)。R4.6 原结果保留；本轮检索 19/57、原生回答 17/57，涨分尚不能归因于代码修复，不晋升。

## R5.6 原生分批声明抽取补记（2026-09-25）

新增候选能力 `ValidationPolicy.claim_batch_size`：默认0保留原行为，1至32仅用于semantic claim，当前实验为8。C++用完整payload规划互斥的全局来源单元批，每批保留全部上下文；模型只能输出目标clause，原生在语义过滤前拒绝越界行。证据的原始字节坐标、来源hash及SourceTurn身份保持，不把批号写入声明身份。Python配置仅映射该字段；general_fact派生policy清零，episodic独立。

原生 `claim_extraction_batch_plan(payload, policy)` 给出计划与请求上界；分批回执保留全局attempt编号、batch_index、target_clause_ids和 `claim_batches_complete`。全部批成功才允许该holder分批claim写入；后批失败保留全部原始回执与成本，0条分批claim落库。持久化重新验证计划、policy与候选来源，批间写异常由事务回滚；跨分批大小重放保持幂等。完整上下文重复输入增加成本，有限来源单元不等于token硬上限。

本轮本地验证已通过，真实同输入验收与扩大评测尚待完成；不把测试结果当QA增益。完整设计与当前证据见[R5.6中文设计](../superpowers/specs/2026-09-25-socialmem-r56-bounded-claim-design.md)，历史评测继续按各自冻结核心解释。

## 抽取提示 prefers 主语语义修正补记（2026-09-27）

`python/starling/extractor/prompts.py` 的 `EXTRACTION_PROMPT`（生产默认 `belief_prompt`）在 `5a945ca` 中修正了 `prefers` 谓词的主语语义：旧示例把被偏好的目标当主语（`"I want to spend the weekend outdoors"` → `subject="weekend"`, `subject_kind="entity"`），与同文件 `SUBJECT_KIND` 规则自相矛盾——偏好是态度，只能由 cognizer 持有。新版改为持有偏好的人作主语（`subject="Li Hua"`, `subject_kind="cognizer"`）。语义与 C++ `claim_contract.cpp` 中 `PredicateCatalog` 对 `prefers` 的 `mental_subjects={cognizer}` 定义一致。

该改动属于产品默认行为变更，与 R5.3 检索 sidecar 实验无关，但随同一提交合入且当时未单独记录；本条为事后补记。真实模型对比（2026-09-28）确认行为改变：旧版抽取为 `weekend/entity`，新版为 `Alice/cognizer`；旧版行为使偏好类语句无法进入人物图谱、ToM 查询与社交推理，属修复而非语义漂移。静态守卫 `tests/python/test_preference_prompt_contract.py` 已能拦下旧版示例。episodic 与 general_fact 两条通道按设计不抽取偏好，不受影响。

## claim 通道输出稳健性补记（2026-10-04）

只改了准入提示：末尾加一句，要求闭合所有括号，完整响应是以 `}]}` 结尾的单个 JSON 对象，其后没有文字。改动在 `src/extractor/claim_contract.cpp`，只涉及准入提示。抽取提示和固定参考示例逐字节不变，所以抽取提示与批计划的哈希钉点保持原值。

动机：qwen3.8-27b 在 legacy 模式下，2 个候选的准入响应 9 格里有 8 格少或多一个 `}`，被严格解析整条丢弃，两个候选都没入库。在 4 个固定候选夹具、每个 3 次的单独回放里，不加这句时 12 次里 6 次可解析，加了之后 12/12。

没有放宽任何守卫或解析：畸形外壳仍是 `envelope_failure`，NEG 缺 `NEGATED` 仍被拒。`semantic_claim_contract` 仍默认关闭。

曾试过另一项改动并撤回：在抽取提示的固定参考示例里增加一条 `prefers`/NEG 示例，希望模型对 "I do not prefer ..." 写出 `NEGATED`。它对 `negative_target_scope` 有效（qwen3.8-27b，legacy，12 次：带 `NEGATED` 的 NEG 声明 7/12 到 12/12），但在 json_object 模式下让 `preference_contrast` 的 NEG 声明全部丢了 `NEGATED`（6/6 到 0/6，新旧核心交错对照），deepseek-v3 上 NEG 声明带 `NEGATED` 也由 20/30 降到 15/30，差异不显著。净效果不明确且有回归，所以没有交付。"NEG 缺 `NEGATED`" 的拒收问题因此仍未解决，守卫保持原样。

数据与局限见[评测记录](../eval/2026-10-04-socialmem-claim-channel-fix.md)，修复前的观察见[claim 通道探针](../eval/2026-10-03-socialmem-claim-channel-probe.md)。


## NEG 与 NEGATED 提醒行补记（2026-10-05）

抽取提示末尾的格式检查块新增一行：polarity 为 NEG 时 `scope_markers` 必须含 `NEGATED`，否则该声明会被拒收。改动在 `src/extractor/claim_contract.cpp` 的 `final_format_reminder`，只涉及抽取提示；准入提示、批计划、作用域守卫、解析和读侧检查都没有改动，也不由 Python 补齐响应字段。

动机：`qwen3.8-27b` 与 `deepseek-v3` 都会写出 polarity=NEG 但 `scope_markers` 只写 `ASSERTED` 的候选，被作用域守卫按 `explicit source marker missing: NEGATED` 拒收。指导段第 6 条本来就有同一句话，新增的是位置——放到来源数据之后的格式检查块里，离模型生成答案更近。为什么位置有效，没有证据，不下结论。

判定按事先登记的规则（本机 `build/socialmem_20261004_claim_channel_fix/prereg_negated_variants.txt`，未入库）：qwen3.8-27b 预先登记的 24 条 NEG 声明里带 `NEGATED` 由 12/24 到 24/24，四个（用例，模式）分组没有一组倒退；回归检查在 `emotion_negative`、`reported_distrust` 两个天花板对照和 deepseek-v3 同传输上完成，逐格配对分别变好 4 变差 0 与变好 14 变差 2。同时登记的另一变体（把参考示例改成 `ASSERTED` 加 `[ASSERTED, NEGATED]` 的否定偏好示例）只到 18/24，未达门槛，已撤回。

数据、两处变差格的取证与局限见[评测记录](../eval/2026-10-05-socialmem-negated-reminder.md)。
