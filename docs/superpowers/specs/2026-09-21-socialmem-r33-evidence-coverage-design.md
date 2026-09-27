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

# SocialMemBench R3.3 证据覆盖与跨会话检索设计

日期：2026-09-21

## 1. 背景

R3.2 已把结构化抽取的技术失败从 30 道降到 1 道，但 43 道错误题中有 26 道在来源和结构化声明两侧都没有命中金标话轮。Q8 跨会话变化题、Q7 关系题和 Q1/Q5 主体归属题尤其依赖多个 session 的原文组合。R3.2 的 `hybrid_fenced` 仍使用 C++ BM25 来源策略，hybrid 在 `k=10` 下交替放入来源和声明，常见结果是目标原文没有进入回答上下文，或者只保留变化链的一端。

同一 R3.2 数据库的零请求 C++ 回放显示，56 道技术正常题中 BM25 至少命中一个金标话轮 24 道；既有 `focused_coverage`（seed=5、dialogue radius=1）命中 42 道。这是候选覆盖诊断，不是模型 QA 结果，但足以支持下一轮先修复检索覆盖。

## 2. 目标与验收门槛

本轮只优化来源进入回答上下文的概率和跨会话组织，不修改题目、金标、抽取合同、谓词目录、admission、评分、裁判、重试或生产默认。

验收分为三层：

1. **原生行为**：全体成员问题能够确定性地扩展到允许 holder；时间变化问题在预算允许时同时保留早期和晚期话轮；hybrid 在显式 SOURCE 配额下确实达到最小来源数，并保持租户、holder、时间和字节预算边界。
2. **离线覆盖**：固定 R3.2 题目数据库的 C++ 零请求回放，`focused_coverage` 的金标话轮命中题数不低于现有 42/56，且不能降低默认 `bm25` 的逐字输出兼容性。该门槛用于防止实现回归，不把离线命中当作 QA 质量。
3. **真实评测**：独立 R3.3 目录完成 57/57 题、7/7 scope、36/36 holder；技术失败按类别单列。只有在共同技术正常题上相对 R3.2 的正确题数净增至少 5 且按网络 bootstrap 95% 区间下界大于 0 时，才考虑候选晋升；否则只记录诊断收益。

## 3. 方案

### 3.1 C++ 识别问题涉及的人物范围

`source_retriever.cpp` 继续以 C++ `focused_holders` 为唯一人物识别实现。保留现有完整姓名边界匹配；当问题没有显式姓名但包含 `each member`、`all members`、`everyone`、`all four`、`each person` 或对应中文表达时，将允许 holder 按稳定输入顺序全部纳入 coverage 队列。没有这些全体成员标记时不扩大范围，避免把普通“group”问题错误地扩展为全体证据。

人物来自 `ObserverQuery.allowed_holders`，不从题目金标、答案或 Python 数据集字段读取。来源仍先经过 tenant、holder、观察时间、保留策略、内容哈希和重复话轮过滤。

### 3.2 跨 session 早晚覆盖

`focused_coverage` 保留 seed 来源作为 BM25 相关性入口，再按人物和 session 轮转补充原文。对包含 `change`、`changed`、`shift`、`over the course`、`earlier`、`later`、`before`、`after`、`turning point`、`evolved` 或对应中文表达的问题，session 队列采用首尾交替顺序，优先覆盖最早和最晚可用话轮，再填充中间 session。非时间问题维持现有时间顺序。

该策略只保证候选来源覆盖，不把两段话自动解释成因果关系。回答提示仍要求模型区分早期状态、明确触发和后期状态；没有明确因果语句时必须降低断言强度。

### 3.3 hybrid 的 SOURCE 配额

在 `ObserverQuery` 增加 `min_source_items`，默认值为 0。C++ 校验 `0 <= min_source_items <= k`，仅对 `sources` 或 `hybrid` 有效；`statements` 模式设置非零值时拒绝。评测 R3.3 使用 `k=10`、`min_source_items=7`、`source_strategy=focused_coverage`、`source_seed_k=5`、`source_seed_max_context_bytes=4000`、`source_dialogue_radius=1`。

hybrid 选择时先填满最小 SOURCE 配额，再用既有声明排序填充剩余槽位；默认 `min_source_items=0` 的旧交替顺序逐字保持。SOURCE 行仍携带说话人、观察时间、session 和 turn index，完整 Engram/clause/turn 身份仍只写入回执，不把内部标识塞入模型上下文。若字节预算不足，实际达到的来源数和预算拒绝数必须写入诊断回执，不能伪造配额达成。

### 3.4 Python 边界

Python binding 只暴露 `ObserverQuery.min_source_items`，评测编排只把配置字段透传给 C++。Python 不实现人物识别、时间队列、来源配额、原文解析、候选补齐或语义改写。`source_strategy` 和 `min_source_items` 纳入实验配置、身份哈希和请求回执。

## 4. 数据流与失败处理

1. C++ 读取已登记来源，完成租户、holder、时间、擦除、哈希和重复话轮校验。
2. C++ 对问题做人物范围和时间问题分类，生成 focused coverage 候选及选择 trace。
3. C++ 在 hybrid 结果中先执行 SOURCE 配额，再执行声明补位；所有选择、预算拒绝和实际计数写入 `source_diagnostics`。
4. Python 只把 C++ block 发送给回答模型，并保存回答/裁判原始回执。
5. 任一来源或结构化声明不满足证据证书要求，沿用现有 C++ exclusion；没有来源时允许既有 abstain 行为，不用 Python 生成空占位事实。

## 5. 测试先行

先在 `tests/cpp/test_source_retriever.cpp` 增加 RED 用例：

- 无显式姓名但含 `each member` 的问题，`focused_coverage` 的 trace 必须把所有允许 holder 标为 coverage eligible；普通问题不能扩大到未提及人物。
- 含 `changed over the course` 的单人物问题，固定早晚 session 原文都进入来源候选；非时间问题的既有顺序保持。
- hybrid `k=10,min_source_items=7` 至少输出 7 条 `SOURCE`，并在字节不足时报告实际计数；`min_source_items=0` 的输出与历史行为一致。
- `statements` 模式非零 `min_source_items`、大于 `k` 和负数均由 C++ 拒绝；来源引用仍与输出行一一对应。

再补 `tests/python/test_source_retriever_binding.py` 的边界断言，确认 binding 只映射字段，`tests/python/test_socialmem_structured_eval_guard.py` 确认 R3.3 配置锁定策略和预算。测试通过后才修改 C++，不在 Python 写同名逻辑。

## 6. 非目标与风险

- 不修改 `claim-predicate-v3`、抽取提示、JSON parser、scope guard、admission 或持久化 schema。
- 不使用问题编号、金标答案、evidence anchors 或参考答案参与线上检索。
- 不把来源命中提升、声明数量增加或离线夹具通过解释为 F1/QA 提升。
- SOURCE 配额会减少 hybrid 中结构化声明的槽位；R3.3 必须同时报告来源/声明计数和 QA，若回答性能下降则关闭该候选策略。
- 全体成员识别可能扩大上下文，必须受 `k` 和 UTF-8 字节预算限制；任何超预算候选只能记录为拒绝。
