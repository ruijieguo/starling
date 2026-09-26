<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench R3.1 抽取容量诊断设计

日期：2026-09-20
状态：已实施，结果不晋升
适用范围：Starling 当前工作区的固定 57 题结构化评测

## 1. 背景与问题

R2.3 在同一冻结来源快照上完成了 57 题网络评测，但出现抽取超时、抽取 `completion_truncated`、回答 `completion_truncated` 和重复 JSON 键。回答上限为 512、裁判上限为 64，本轮不再同时改变多个容量或协议变量。R3.1 只验证一个可证伪问题：结构化抽取上限从 4096 提升到 8192，是否能减少抽取输出截断并提高 scope/holder 完成度。

本轮不把抽取容量变化解释为谓词能力增强。若抽取截断下降但 QA 不升，只能说明容量是技术瓶颈；若技术失败下降且同一题配对正确率改善，才可进入下一轮语义/谓词诊断。

## 2. 设计决策

### 2.1 单变量变更

| 配置 | `sources` 对照臂 | 结构化臂（其余五臂） |
|---|---:|---:|
| `extract_max_tokens` | 4096 | 8192 |
| `answer_max_tokens` | 512 | 512 |
| `judge_max_tokens` | 64 | 64 |
| `timeout_ms` | 120000 | 120000 |
| `max_retries` | 0 | 0 |
| 题目、来源、评分 | 固定 | 固定 |

结构化臂包括 `statements`、`statements_fenced`、`hybrid_fenced`、`hybrid_dialogue` 和 `hybrid_dialogue_expanded`。`sources` 仍使用 4096，便于确认观察到的变化来自结构化抽取容量，而不是整个运行器的默认漂移。

### 2.2 责任边界

Python 只修改评测臂配置并将容量传递到已有 native adapter。抽取提示、JSON 解析、重复键拒绝、谓词目录、admission、写入和检索仍由 C++ 实现；不在 Python 中截断、展平、补字段或修复模型输出。C++ binding 不新增逻辑，本轮不重建核心库，除非回归证明配置传递需要重新构建。

### 2.3 评测与证据

建立独立的 R3.1 目录，重新执行 `prepare`、`check` 和固定 57 题网络运行。归档配置、冻结文件、请求账本、逐题回执和分析 JSON。报告同时给出：

1. 抽取 `completion_truncated`、抽取超时、`envelope_failure`、`schema_failure` 和其他技术失败的题数；
2. 7/7 scope、36/36 holder 完成率及结构化声明/谓词分布；
3. 主评分与成功技术子集评分；
4. 与 R2.3 逐题 `item_id` 交集的配对转移；
5. 抽取容量变化对 QA 的证据边界，不把成功声明数量当作 F1 或生产质量。

R3.1 只有在技术失败下降、配对结果可解释且没有新协议违规时，才允许进入下一轮候选；不自动改变生产默认 `semantic_claim_contract=false`。

## 3. 风险与停止条件

- 若 `extract_max_tokens=8192` 导致请求预算、服务超时或响应大小越界，停止网络运行并保留离线门禁证据。
- 若出现写入失败、数据库/WAL 失败或 binding 配置漂移，先修复并重新执行本轮，不能用不完整目录做 QA 结论。
- 若仍有抽取截断，下一轮应分析 prompt/输出密度或分 holder 分片，不同时修改谓词和解析器。
- 若技术失败下降但 QA 没有配对改善，R3.1 只标记为可靠性修复，不晋升结构化能力。

## 4. 验收标准

验收必须有新鲜命令证据：中文设计与计划存在且入口同步；RED 测试在实现前因 4096 配置失败；最小实现后相关 Python 回归通过；独立 R3.1 目录通过 `prepare`/`check` 并完成或明确记录停止原因；评测报告给出 R2.3 对照和技术失败分解。任何“通过”“完成”结论都不得只依据历史日志。
