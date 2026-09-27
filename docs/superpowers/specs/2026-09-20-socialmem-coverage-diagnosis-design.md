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

# SocialMemBench 结构化覆盖诊断与评测完整性设计

状态：承接已批准方案 A 和连续自主迭代授权。实施顺序为中文文档、RED 测试、实现、离线评测。本轮零外部请求。

## 目标与已确认问题

固定 57 题的历史 hybrid 对照有 7 个 scope。其中 `80c2bb913025e73cc364c724` 的 `scope.json` 明确为 `source_only`，抽取记录为空，覆盖 9 题。其余 6 个 scope 共 31 个 holder 抽取概要，96 条数据库记录只有 14 条携带 `semantic_claim_json`；不能把所有记录都计为结构化声明。现有 51 条拒绝概要统一使用 `__semantic_rejection__`，不支持按谓词定位。14 条声明均未携带 session_id/turn_id/observed_at；评测抽取入口仅传 speaker/text，来源保留通道的元数据没有传入抽取。

本轮先修复可观测性和评测完整性，再决定谓词或 admission 变更。三个选择中，直接扩表无法解释当前损失，直接放宽 admission 有误收风险；选择先建立真实分母、原生拒绝分类和完整 scope 门禁。历史 QA 标签保持原样，补充解释其有效范围。

## 离线诊断合同

新增 `scripts/analyze_socialmem_structured_coverage.py`。仅读取 summary 明确列出的 scope 和逐题终态，检查重复题号、缺失 scope、逐题摘要与文件一致性；多余目录不扩大分母。SQLite 以只读、immutable 方式打开，非空 WAL 拒绝；输入逐文件记录 SHA-256，读取后复核。统计使用存储字段和 C++ 生成的计数，不在 Python 重建谓词、准入或来源语义。

按 scope 输出：预期/实际 holder、来源话轮数、全部记录数、结构化声明数、谓词与持久化语义族、时间元数据缺失、原生 failure_category、拒绝概要和原始抽取输出可用性。按题把 statement_ids 与同 scope 数据库关联，分别统计携带结构化声明、仅 legacy 声明和仅来源的问答正确率。这是相关性描述，不是因果、答案要点召回率或新 QA 成绩。没有金标声明清单时，不输出语义召回率。没有准入回执时，拒绝原因明细必须为未知。

## 原生可观测性修复

在 C++ `ClaimSemanticRejection` 中增加规范谓词，在 `ClaimAdmissionResult` 中增加按规范谓词拒绝计数。只有完整 admission 决策通过原有校验后才提交计数；坏协议不能留下部分语义拒绝。`ExtractionLlmAttempt` 持有 admission 计数，`finalize_claim_result` 汇总确定性拒绝和 admission 拒绝，不再使用通用桶。规范化继续调用唯一 C++ 目录。

失败归类在 admission 调用失败时读取 admission 响应的错误信息，避免把准入超时错记为普通 transport_failure。receipt 序列化增加原生生成的分阶段拒绝计数；不改变候选准入、目录版本、模型提示或默认策略。

## 评测完整性门禁

`run_socialmem_structured_eval.check_arm` 在构造提供商之前检查已存在的运行 scope。结构化 arm 必须有与该 scope 公共历史人物清单一一对应的抽取结果、明确目录版本、来源保留和无抽取失败；`source_only` 快照一律拒绝。尚未运行的 scope 可以不存在；已有不完整运行产物不能伪装成新 scope。零声明且有完整成功抽取是合法结果，不要求强造声明。

该门禁属于 Python 评测协议编排；产品抽取、谓词归一、语义判断继续全部在 C++。不修改或刷新历史运行 manifest，不覆盖其旧 driver。

## 测试与验收

先验证以下 RED：原生确定性/准入拒绝按谓词分开且别名归一；准入坏协议无部分计数；准入超时分类正确；结构化运行拒绝 source_only、缺 holder、重复 holder、失败/无版本回执；完整成功零声明可通过；离线报告区分 legacy 与结构化声明、缺失抽取与空抽取，按声明 ID 关联 QA，拒绝摘要不一致与非空 WAL。

完成后运行相关 C++/Python 回归，诊断固定 57 题，保存结果及哈希。上一轮完整 C++ 为 1204 项：1181 通过、22 跳过、1 个 loopback listener 环境失败；本轮验证独立报告。

## 后续唯一优先假设

优先补齐结构化抽取输入的 SourceTurn 元数据及每个 holder 的完整原生回执，再建立 7/7 scope、36/36 holder 的真实 baseline。确认传输/解析/准入损失后，才分别评测谓词扩展和范围规则；所有新候选保持 qwen3.8-27b、同题目/裁判、零重试、独立冻结目录。当前不追加 focused dialogue 参数实验。
