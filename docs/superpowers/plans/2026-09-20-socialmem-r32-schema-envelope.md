<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench R3.2 结构化信封实施计划

> **面向执行代理：** 实施时必须按任务逐项执行；每个任务使用复选框记录，且严格遵守“中文设计 → RED 测试 → C++ 最小实现 → 回归 → 独立评测”的顺序。

**目标：** 通过 C++ 末端结构模板降低 qwen3.8-27b 结构化声明的重复 key、误嵌套和字段遗漏，同时保持严格拒绝与原始回执。

**架构：** 抽取提示、字段目录、解析、scope guard 和 admission 全部由 C++ 提供唯一实现。Python 只调用 binding、传递配置、保存回执和计算统计；任何不合约的模型文本都不能在 Python 中修复。

**技术栈：** C++17、nlohmann/json、GoogleTest、pybind11、pytest、现有 DashScope SocialMemBench 评测脚本。

**设计依据：** `docs/superpowers/specs/2026-09-20-socialmem-r32-schema-envelope-design.md`。

## 全局约束

- 保持 `claim-predicate-v3`、原有 scope/admission 规则和 `semantic_claim_contract=false` 生产默认。
- 不修改题目、答案、裁判、检索、评分分母、重试次数和 qwen3.8-27b 评测预算。
- C++ 是结构化协议和语义逻辑唯一实现；Python 不增加同名 parser、谓词或清洗逻辑。
- 每个真实实验使用新的 Starling-local 目录、manifest、请求账本和原始 completion。

## 任务 1：保存设计与同步清单

**文件：**

- 已创建：`docs/superpowers/specs/2026-09-20-socialmem-r32-schema-envelope-design.md`
- 已创建：`docs/superpowers/plans/2026-09-20-socialmem-r32-schema-envelope.md`
- 修改：`docs/design/system_design.md`
- 修改：`docs/design/claim_contract_sync.md`
- 修改：`docs/design/subsystems_design/07_neocortex.md`
- 修改：`docs/design/subsystems_design/08_cognizer.md`
- 修改：`docs/design/subsystems_design/13_retrieval.md`
- 修改：`docs/eval/2026-09-20-socialmem-r31-extraction-capacity.md`
- 修改：`docs/eval/2026-09-20-socialmem-structured-coverage-diagnosis.md`

- [x] 写入 R3.1 证据、R3.2 假设、非目标、验收指标和文档同步范围。
- [ ] 在上述入口追加 R3.2 状态段，标注“仅设计完成，尚未产生新模型分数”。
- [ ] 检查所有新增文档为中文、无 TODO/TBD/占位语句，运行 `git diff --check`。

## 任务 2：C++ RED 测试

**文件：**

- 修改：`tests/cpp/test_structured_output_prompt.cpp`
- 测试目标：构建目录中的 `starling_tests`

- [ ] 添加一个最小测试，要求提示在 `SOURCE_DATA_JSON` 后包含 `STATEMENT TOP-LEVEL SHAPE`、`EVIDENCE NESTED SHAPE` 和 `CANONICAL SKELETON`。
- [ ] 添加字段归属断言：`holder`、`holder_perspective`、`subject_kind`、`predicate`、`object`、`modality`、`polarity`、`nesting_depth`、`confidence` 只在顶层骨架出现；evidence 只列证据字段。
- [ ] 添加骨架安全断言：提醒包含 `event_time` 和“一次”唯一 key 约束，且不含真实人物、题号或答案词。
- [ ] 运行 `.venv/bin/cmake --build build --target starling_tests -j2` 与 `.venv/bin/ctest --test-dir build -R '^StructuredOutputPrompt\\.' --output-on-failure`，确认新增断言因当前提示缺少标记而失败；保存 RED 日志到 `build/socialmem_20260920_r32_red_cpp.log`。

## 任务 3：C++ 最小实现

**文件：**

- 修改：`src/extractor/claim_contract.cpp`

- [ ] 在现有 `final_format_reminder` 末端追加短的结构模板，固定根、statement 和 evidence 的字段归属；只使用占位符。
- [ ] 明确每个 object 内 key 只能出现一次，并要求 `event_time` 显式为 null 或合法对象。
- [ ] 不改 `strict_json`、`parse_claim_response`、scope guard、admission 或 Python binding。
- [ ] 重新构建 `starling_tests`，运行同一专项测试，确认 GREEN；保存 `build/socialmem_20260920_r32_green_cpp.log`。

## 任务 4：binding 与回归

**文件：**

- 修改：`tests/python/test_structured_output_prompt.py`（只补 binding 边界断言）
- 不修改：`scripts/` 中的语义解析和清洗逻辑

- [ ] 安装新构建 `_core` 到 `.venv/lib/python3.14/site-packages`，记录模块路径和 SHA-256。
- [ ] 运行专项 Python 测试、结构化合同测试、SourceTurn/receipt 测试和谓词覆盖测试。
- [ ] 运行 `.venv/bin/ctest --test-dir build --output-on-failure`；若存在 loopback 或旧 facade 环境失败，单列其环境原因，不将其归因于本轮提示。
- [ ] 检查 Python 评测脚本不包含 `flatten_evidence`、`repair_nested`、`json.loads` 后重写候选等清洗路径。

## 任务 5：独立 SocialMemBench 评测

**目录：**

- 创建：`build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_r32_schema_envelope/`

- [ ] 复用 R3.1 的冻结题目、来源 parent、模型和预算，生成新身份、config、scope manifest 和执行计划。
- [ ] 在已授权网络环境完成 57 题 `hybrid_fenced`；只使用 DashScope `qwen3.8-27b`，零重试，保存 extraction/admission/answer 原始回执和 ledger。
- [ ] 运行现有分析器并补充 R3.2 统计：scope/holder、失败类别、误嵌套/重复 key 证据、空候选、谓词分布、全题与成功子集 QA、同题配对和 bootstrap。
- [ ] 若技术完成率不足 7/7 scope 或存在回执缺口，禁止宣称完整 baseline，保留失败目录供下一轮诊断。

## 任务 6：中文评测报告与结论

**文件：**

- 创建：`docs/eval/2026-09-20-socialmem-r32-schema-envelope.md`
- 修改：上述设计同步入口

- [ ] 报告 R3.1/R3.2 的同题配对、技术失败变化和错误样例；区分协议收益与 QA 收益。
- [ ] 给出是否晋升的结论；未满足预注册门槛时明确保持生产默认关闭。
- [ ] 写入实验目录、manifest、core hash、请求数、测试命令和 `git diff --check` 结果。
- [ ] 最后运行验证命令并只根据当前输出汇报完成状态。

## 实施收口（2026-09-21）

R3.2 已完成上述顺序：中文设计、C++ RED/GREEN、合同与相关回归、独立 DashScope 评测和逐题诊断。最终报告为[ R3.2 结构化信封评测与语义诊断报告](../../eval/2026-09-20-socialmem-r32-schema-envelope.md)。技术协议收益已确认，语义 QA 未达到晋升门槛；后继工作进入[R3.3 证据覆盖计划](2026-09-21-socialmem-r33-evidence-coverage.md)。
