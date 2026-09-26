# SocialMemBench 结构化覆盖诊断与修复报告

日期：2026-09-20。范围：冻结的 `hybrid_dialogue` 开发实验，57 题、6 网络、7 scope；历史模型为 DashScope `qwen3.8-27b`。本轮仅做离线诊断、工程修复和本地测试，新增外部请求 0，没有新 QA 成绩。

## 结论

当前低分不能单独归因于谓词目录不够丰富。已确认的损失同时存在于**评测覆盖、输入元数据、候选生成、合同拒绝和证据归档**。因此应先补齐输入和证据链，再分别验证谓词与 admission 改进。

历史 17/57（29.82%）的标签和分母保留，但必须补充限定：只有 6/7 scope 执行了结构化抽取；另一个 scope 的 9 题使用仅来源快照。这不是 7 个 scope 全部执行结构化管线的 baseline，也不能作为“结构化能力已经提升”的证据。

## 1. 真实覆盖与存储分母

| 网络 / scope | 题数 | 正确 | 抽取 holder / 预期 | 结构化声明 / 全部记录 | 原生概要拒绝数 |
|---|---:|---:|---:|---:|---:|
| grp_0d1e2f3a / all_history | 5 | 2 | 4/4 | 1/1 | 0 |
| grp_0d1e2f3a / sessions_1_2 | 1 | 1 | 4/4 | 0/0 | 0 |
| grp_2b3c4d5e / all_history | 10 | 0 | 5/5 | 2/2 | 6 |
| grp_3c4d5e6f / all_history | 8 | 3 | 5/5 | 2/41 | 19 |
| grp_4d5e6f7a / all_history | 9 | 2 | **0/5** | **0/0** | 未执行 |
| grp_9c0d1e2f / all_history | 6 | 2 | 4/4 | 3/24 | 4 |
| grp_a3b4c5d6 / all_history | 18 | 7 | 9/9 | 6/28 | 22 |
| 合计 | 57 | 17 | **31/36** | **14/96** | **51** |

423 个来源话轮为按 scope 相加，包含同网络不同范围的重复话轮；36 个 holder 也为按 scope 计数。它们不是去重后的人物或语料总量。

14 条结构化声明的谓词为：`feels=10`、`decided_on=3`、`uncertain_about=1`。持久化语义族分别为 affect、plan_decision、uncertainty。目录有 10 个规范谓词，但本批只有 3 类出现；这只是已持久化分布，不能据此证明其余 7 类在来源里本应存在，亦不能称为 30% 语义召回率。其余 82 条记录来自 legacy 等路径，不具备本报告要求的结构化声明证据。

缺失 scope 的 `scope.json` 明确写有 `ingestion_mode=source_only`、`extraction=[]`、`extraction_request_count=0`。其 `hybrid_fenced` 父记录已经标注 `reused_from=sources`，后续 dialogue 候选继续继承。因此问题发生在结构化实验快照复用，而非新模型没有生成声明。

## 2. 输入元数据损失

14/14 条结构化声明的 `source_turn` 均缺 `session_id`、`turn_id` 和 `observed_at`。代码定位在 `scripts/eval_ladder.py::make_real_extract_fn`：按 speaker 分组后只保留 text，拼接普通 `speaker: text`。另一方面，来源保存路径已通过 C++ `retain_source_turns` 保存原始元数据，两条路径的输入不等价。

影响是结构化声明无法直接进入需要会话顺序的 early/late 对照；召回展示的 `source_time=2026-06-01` 是统一摄入时间，不能替代每条来源的真实会话时间。C++ 已支持 `claim_source_turn_payload`，故后续应修复评测输入接线，复用现有原生校验，不在 Python 增加时间推断或分句规则。

## 3. 可恢复的候选与拒绝证据

数据库共 137 行 extraction_attempt，47 行有非空 `raw_output`。这些记录可能按 statement span 写入，**137 不是模型请求次数**。本轮从中识别并用该实验冻结 `_core` 重放了 22 份 v2 形式响应：16 份为空候选，6 份非空，共 16 条原始候选；原生解析保留 4 条，拒绝 12 条，批级解析错误 0。

| 可恢复部分的原生拒绝原因 | 条数 |
|---|---:|
| 来源包含条件但缺 CONDITIONAL 标记 | 4 |
| topic 不在被引用来源单元 | 2 |
| object 丢失 topic | 2 |
| 来源包含问句但缺 QUESTIONED 标记 | 2 |
| object 丢失显式时间限定 | 1 |
| NEG 关系又在 object 重复否定 | 1 |

该重放只覆盖有原文的响应，存在保存机制导致的选择偏差；不能把 12/16 外推到全部生成候选。51 条拒绝概要包含原生守卫和模型 admission，旧概要没有分开记录。admission 原始决策缺失，4 条过原生检查后的最终处理也不在本次重放中重判。未保存原文的响应保持未知。

条件/问句错误既可能是生成漏标，也可能涉及同话轮不同句子的范围过宽；本报告只确认拒绝触发点，不把所有拒绝都定为误拒。先使用独立正反例定位范围，再考虑调整，不能全局关闭 scope 守卫。

## 4. 检索与 QA 的关系

14 条存储结构化声明均至少被召回一次，按题累计 79 次引用；这表示现有少量声明能进入检索，不代表答案所需证据已经齐全。

| 实际进入上下文的声明类别 | 题数 | 正确 | 正确率 |
|---|---:|---:|---:|
| 至少 1 条结构化声明 | 40 | 12 | 30.00% |
| 仅 legacy 声明 | 7 | 2 | 28.57% |
| 没有声明，仅来源 | 10 | 3 | 30.00% |

以上分组按 `statement_ids` 关联同 scope 数据库得到，不从文本标签猜测。分组是事后描述，题目难度和网络不同，不具备因果可比性。仅有来源的 10 题中，9 题来自未执行抽取的 scope，1 题来自完整但空的抽取 scope，二者原因不同。

特别是 grp_2b3c4d5e 的 10 题，两个结构化声明被累计召回 20 次，仍为 0/10。反复召回少量通用声明不会自动补齐题目所需的人物态度、关系和跨轮变化证据。

## 5. 已执行的修复

遵循中文设计 → RED 测试 → 实现：

1. **C++ 拒绝计数**：确定性拒绝保存规范谓词；admission 完整校验后按谓词计数；receipt 同时暴露 admission 阶段计数。别名 `has` 在诊断中统一为 `owns`，Python 不维护谓词表。坏 admission 协议不留下部分计数。
2. **C++ 超时归类**：admission 失败使用 admission 响应的错误信息；修复原先读取成功 extraction 响应而把超时误记为 transport_failure 的错误。
3. **评测门禁**：构造提供商前，结构化 arm 拒绝 source_only、缺 holder、重复 holder、失败/无目录版本回执及部分运行目录。完整成功但声明为空仍合法。
4. **离线分析器**：只读固定 scope，严格关联逐题回执与 summary，拒绝缺失/重复题目、缺失 statement ID 和未 checkpoint 的 WAL；记录并复核输入 SHA-256。

这些修复改善诊断可信度，不改变抽取语义、谓词目录、提示、答案或评分，也没有新准确率增益。

## 6. 验证与产物

修改前的 3 个 C++ 新用例均明确 RED：通用拒绝桶、缺 admission 分类字段、admission 超时错误归类。修复后相关 C++ 77/77 通过。Python 诊断/门禁 RED 为 17 项，修复后通过；随后模块身份审计发现常规导入仍加载虚拟环境旧 `_core`，新增 binding 断言在旧模块明确 RED。显式加载新构建模块后，全部相关 Python 71/71 通过；新模块安装到当前虚拟环境后，常规导入再次验证同一组 71 项。早先旧模块的 49 项结果不作为本轮实现验收证据。

完整 C++ 沙箱回归为 1207 项：1184 通过、22 跳过、1 个既有 loopback listener 失败；随后允许本地回环监听，相关 HTTP 套件 30/30 通过，覆盖全部 22 个跳过和 1 个失败。原始沙箱结果仍单列保存。

新构建与当前虚拟环境 `_core` 均为 `12473f953c8b73743017ea65a5a24d859ea052af3c40ade48c6b6c471bc4235c`。历史冻结模块保持原哈希，部分原生重放仍使用历史模块。

- 设计：[结构化覆盖诊断设计](../superpowers/specs/2026-09-20-socialmem-coverage-diagnosis-design.md)
- 实施计划：[执行记录](../superpowers/plans/2026-09-20-socialmem-coverage-diagnosis.md)
- 结构化覆盖：[analysis.json](../../build/socialmem_20260920_coverage_diagnosis/analysis.json)
- 部分原生重放：[partial-native-replay.json](../../build/socialmem_20260920_coverage_diagnosis/partial-native-replay.json)
- 最终核验（83 份历史输入不变、新旧模块身份、合同无漂移）：[final-verification.json](../../build/socialmem_20260920_coverage_diagnosis/final-verification.json)
- 部分重放复现脚本：[replay_available.py](../../build/socialmem_20260920_coverage_diagnosis/replay_available.py)
- RED/GREEN、修改前快照与回归日志：[证据目录](../../build/socialmem_20260920_coverage_diagnosis)

复现主诊断：`.venv/bin/python scripts/analyze_socialmem_structured_coverage.py --run build/socialmem_20260919_structured_eval_dialogue_v3 --output /tmp/socialmem-coverage-new.json`。输出路径须不存在。原生重放模块哈希为 `55b001c53551a711e1428f82ba6a8a557d75baf7a81286b52d6ab632d5b5de6c`，与历史实验一致。

## 7. 下一轮优化顺序

1. **输入与回执闭环**：评测抽取输入接入 C++ SourceTurn renderer，逐 holder 保存完整 extraction/admission 原生回执。先用独立中英文夹具验证多会话、坏时间、换行与 holder 归属，再对 7/7 scope、36/36 holder 建立完整 baseline。
2. **生成覆盖**：在有完整回执的基础上区分模型为空、结构错误、范围拒绝、admission 拒绝与写入失败。当前 16 份可见空候选是值得验证的生成缺口，不应靠增加召回 k 补救。
3. **谓词表达**：审计 `semantic_claim_contract` 替换原 belief 路径后，偏好、观点和责任等基础关系是否有实际可用的独立承载路径。当前提示要求“保留在既有路径”，但评测只有该结构化 belief 通道以及 general_fact/episodic，不能假定后两者已完整替代基础心智状态抽取。按通用来源证据设计正反例，再选择保留基础关系或扩目录；不按题号/答案定制。
4. **单变量评测**：输入/回执修复、谓词扩展、范围规则分别冻结候选，保持 qwen3.8-27b、同题目/裁判和零重试。恢复完整 baseline 后再比较准确率，达到既有门槛前不晋升。focused dialogue 参数方向保持关闭。

## 8. SourceTurn 输入与三通道回执修复（2026-09-20）

本阶段已按“中文设计 → RED 测试 → C++ 实现 → 验证”完成输入和证据链修复，尚未追加 DashScope 请求，也没有产生新的 QA/F1 分数。

- `eval_ladder.make_real_extract_fn` 现在按 holder 分组后调用 C++ `claim_source_turn_payload`，保留 `speaker`、`session_id`、`turn_id`、`turn_index` 和 `observed_at`；数据集答案/锚点字段仍在 Python 白名单映射处被排除。
- C++ 为 episodic 通道保存 prompt、输入哈希和完整原始响应，并新增 `memory_remember_bundle_receipt`，统一导出 belief、general-fact、episodic 三通道。belief/general-fact 继续由 `claim_extraction_receipt` 生成 extraction/admission attempt 级证据。
- 每个 scope 额外写入 `extraction.receipts.json`，以 holder 为键保存三通道回执；它是诊断归档，不改变逐题评分字段。

新增验证：SourceTurn/回执专项 Python 4 项、相关评测编排和合同组合测试共 73 项通过；对应 C++ 专项 81 项通过；本地 loopback HTTP 回归 30/30 通过。完整 C++ 测试为 1208 项，其中 1185 通过、22 项因沙箱禁止监听而跳过、1 项同类环境失败；在允许回环后已补跑 30 项。全量 Python 1871 项中 1796 项通过、23 项跳过、52 项失败，失败集中在既有 `_core` 与 Python facade `RememberResult` 字段漂移、冻结模块导入污染和 loopback 权限，SourceTurn/receipt 相关组合测试未失败。

本修复只提高 baseline 的输入等价性和失败可归因性，不能把结构化声明数量、回执覆盖或离线夹具通过率当作问答准确率提升。下一步是用新接线在不复用 `source_only` 快照的前提下重新建立 7/7 scope、36/36 holder 的完整结构化 baseline，然后才单独评估谓词目录和 admission 规则。

## 9. R3.2 结构化信封评测与语义诊断（2026-09-21）

R3.2 在固定 57 题、qwen3.8-27b、`hybrid_fenced` 下完成 57/57 题，技术失败 1，正确 13/57，成功子集 13/56，完成 6/7 scope、32/36 holder。技术失败从 R3.1 的 30 降至 1，说明 C++ 末端字段骨架有效降低了误嵌套和重复键风险；共同技术正常题的正确数没有提升，因此不能把协议收益解释为 QA 提升。

逐题按 `gold_statements[].turn_id` 与实际 `source_refs`/`semantic_claim_json.source_turn` 关联：43 道错误中 26 道来源和声明均未命中金标话轮，6 道仅声明命中，5 道仅来源命中，6 道两侧命中后仍有主体、时间或关系推理错误。下一轮不再增加抽取容量，改做 C++ `focused_coverage`、跨 session 早晚覆盖和 hybrid 来源配额。完整报告见[ R3.2 结构化信封评测与语义诊断报告](2026-09-20-socialmem-r32-schema-envelope.md)，设计见[ R3.3 证据覆盖设计](../superpowers/specs/2026-09-21-socialmem-r33-evidence-coverage-design.md)。

- 设计：[SourceTurn 与三通道回执设计](../superpowers/specs/2026-09-20-socialmem-source-turn-receipt-design.md)
- 计划：[SourceTurn 与三通道回执实施计划](../superpowers/plans/2026-09-20-socialmem-source-turn-receipt.md)
- 实施记录：[实现与验证报告](2026-09-20-socialmem-source-turn-receipt-implementation.md)

## R2 谓词覆盖扩展设计同步（2026-09-20）

本阶段承接结构化覆盖诊断和 SourceTurn/三通道回执修复，目标是补齐结构化合同与 legacy mental-state 之间的能力断层。C++ 原生目录版本升级为 `claim-predicate-v3`，新增 `prefers`、`promises`、`doubts`、`believes`、`responsible_for`、`requires`、`forbids` 七类规范谓词及受控别名；既有谓词、来源证据、admission 和持久化格式保持兼容。目录、别名、语义族、允许模态/极性、抽取提示和准入提示均由 C++ `PredicateCatalog` 唯一生成，Python 只绑定、编排和归档，不维护第二份语义逻辑。

本阶段严格执行中文设计文档 → C++/Python RED 测试 → C++ 实现 → 固定协议回归。测试覆盖中英文正反例、错误模态、主体与对象保真、admission 拒绝计数、`knows` 历史模态兼容、三通道证据回读和 Python binding 边界。新增结构化声明数量或离线测试通过率不等于 QA/F1 提升；只有 7/7 scope、36/36 holder 的同协议 SocialMemBench 结果和预注册统计门槛满足后，才讨论晋升。生产默认仍保持 `semantic_claim_contract=false`。


## 9. JSON Object 实评暴露的误嵌套问题与下一轮方案（2026-09-20）

独立目录 `build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_json_object` 已完成 57 题真实调度：3/57 正确、48/57 技术失败，失败集中在六个 scope 各一个 holder 的 `schema_failure`。原始 completion 逐字复核显示，模型把 `holder`、`subject`、`predicate`、`object`、`modality`、`polarity` 等 statement 字段嵌入 `evidence`，并出现一条缺少 `holder_perspective`；不是 JSON 传输或 SQLite 写入失败。

下一轮专项先在中文设计中定义 C++ 末端格式提醒，再写 RED 测试，最后实现。提醒位于 `SOURCE_DATA_JSON` 之后，明确 statement 顶层字段与 evidence 字段边界；`parse_claim_response` 继续拒绝误嵌套、缺字段和额外字段，Python 不清洗模型文本。新评测需独立冻结目录，并同时报告 scope/holder 完成率、协议失败类别、谓词分布和 QA/F1；本轮 3/57 不能解释为谓词扩展造成的质量下降。

设计与计划：

- [结构化输出鲁棒性设计](../superpowers/specs/2026-09-20-socialmem-structured-output-robustness-design.md)
- [结构化输出鲁棒性计划](../superpowers/plans/2026-09-20-socialmem-structured-output-robustness.md)

## 10. 第二轮格式提醒后的剩余失败（2026-09-20）

`build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_format_reminder` 完成 57 题：15/57 正确、16/57 技术失败、41/57 成功技术分母、成功子集 15/41。相对上一轮 JSON Object 目录的 3/57 正确、48/57 技术失败，协议完成率明显改善；失败集中在两个 scope 各一个 holder，原始回执分别包含重复 `time_text`/`topic` 键（`envelope_failure`）和 evidence 误嵌套（`schema_failure`）。

下一轮 R2.3 先增加 C++ 末端唯一 key 与占位 BAD/GOOD 布局对照的 RED 测试，再实现和评测；不放宽解析器、不在 Python 清洗。设计与计划见结构化输出鲁棒性文档。

## 11. R2.3 独立网络重跑收口（2026-09-20）

R2.3 的独立目录 `build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_layout_r23_net` 已完成 57/57 题：7/57 正确、26/57 技术失败、31/57 成功技术分母、成功子集 7/31（22.58%）。4/7 scope 完成结构化抽取，holder 完成率为 19/36。当前失败为一个重复 key 的 `envelope_failure`、一个抽取超时、一个抽取 `completion_truncated`，以及一题回答 `completion_truncated`；没有写入、SQLite/WAL 或 Python 清洗失败。

本轮仍保留一条重复 `time_text`/`topic` 原始回执，说明 R2.3 末端提醒没有消除重复 key 风险；本轮没有复现上一轮的 evidence 误嵌套，但上一轮与本轮成功 scope 集合不同。两轮共同拥有完整 `ok` 逐题回执的 17 题中，上一轮 7 正确、本轮 6 正确，不能把整体 15/57→7/57 变化归因于 R2.3。完整失败分类、holder 覆盖、声明谓词分布和交集诊断见 [R2.3 鲁棒性评测报告](2026-09-20-socialmem-structured-output-robustness.md) 与 [离线诊断 JSON](../../build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_layout_r23_net/analysis_r23_selected.json)。

R2.3 达成了 C++ 实现、严格拒绝和回归测试要求，但未达到技术失败显著下降及 QA 置信区间改善门槛；生产默认继续关闭 `semantic_claim_contract`。下一步先建立无服务超时/截断干扰的完整 7/7 scope 基线，再单变量评估提示或谓词改动。

## R3.2 结构化信封后继方案（2026-09-20）

在 R3.1 截断已消除但 schema/envelope 仍失败的证据上，下一轮把变量收窄为 C++ 末端结构模板：逐项固定 statement 顶层字段、evidence 允许字段和唯一 key 约束。parser 继续严格拒绝，Python 不清洗；本段是设计状态，不代表新请求或 QA 提升。设计与计划见 [R3.2 设计](../superpowers/specs/2026-09-20-socialmem-r32-schema-envelope-design.md) 和 [实施计划](../superpowers/plans/2026-09-20-socialmem-r32-schema-envelope.md)。
