<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench 结构化输出鲁棒性实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 C++ 末端格式提醒降低 qwen3.8-27b 结构化声明的误嵌套技术失败，同时保持严格解析和完整原始证据。

**Architecture:** `claim_contract.cpp` 生成提示和目录；解析器继续拒绝不符合合同的模型响应。Python 只调用 binding、透传配置和归档失败分类，不清洗或补齐字段。

**Tech Stack:** C++17、nlohmann/json、GoogleTest、pybind11、pytest、现有 DashScope SocialMemBench runner。

**Spec:** `docs/superpowers/specs/2026-09-20-socialmem-structured-output-robustness-design.md`

## Global Constraints

- 核心语义、格式提醒和拒绝边界必须在 C++；Python 不维护第二份解析逻辑。
- 不改变 `claim-predicate-v3`、答案/裁判协议、题目、评分分母或生产默认 `semantic_claim_contract=false`。
- 真实请求只使用用户已授权的 DashScope/qwen3.8-27b，独立实验目录和账本。
- 顺序固定为中文设计 → RED 测试 → C++ 实现 → 回归 → 独立评测 → 中文报告。

### Task 1: 设计同步与源码快照

**Files:**
- Create: `docs/superpowers/specs/2026-09-20-socialmem-structured-output-robustness-design.md`
- Modify: 当前中文设计入口及 `docs/eval/2026-09-20-socialmem-structured-coverage-diagnosis.md`
- Create: `build/socialmem_20260920_structured_output_robustness/before/`

- [x] 保存 `claim_contract.cpp`、相关测试和当前 `_core` SHA-256，记录 JSON Object 实评 3/57、48 技术失败和六条原始误嵌套响应摘要。
- [x] 检查新增设计无 TODO/TBD/占位，且明确拒绝误嵌套、不做 Python 清洗。
- [x] 在现行入口追加同一中文摘要；历史文档和历史数字保持不变。

### Task 2: 先写 C++ RED 测试

**Files:**
- Create: `tests/cpp/test_structured_output_prompt.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

- [x] 写提示末端提醒断言、敏感数据排除断言和误嵌套严格拒绝断言。
- [x] 构建并运行专项测试，确认 RED 原因是提醒缺失或测试目标未接入，而非测试导入错误。

### Task 3: 先写 Python RED 测试

**Files:**
- Create: `tests/python/test_structured_output_prompt.py`

- [x] 通过 `_core.claim_extraction_prompt` 断言 binding 暴露原生提醒；扫描评测脚本确认没有
  `repair_nested`、`flatten_evidence` 等 Python 清洗入口。
- [x] 运行该测试并保存 RED 日志。

### Task 4: C++ 最小实现

**Files:**
- Modify: `src/extractor/claim_contract.cpp`
- Modify: `tests/cpp/test_structured_output_prompt.cpp`

- [x] 新增私有末端提醒并在源数据之后追加；不把任何样本标签写入提示。
- [x] 保持 `parse_claim_response` 严格拒绝误嵌套和缺字段；只改善提示，不改变接受集合。
- [x] 运行专项 C++ 测试 GREEN，再运行结构化合同相关回归。

### Task 5: Python/binding 回归

**Files:**
- Modify: `tests/python/test_structured_output_prompt.py`（如需补充断言）
- Create: `build/socialmem_20260920_structured_output_robustness/`

- [x] 重建并安装当前 `_core`，运行专项 Python 测试、结构化评测 guard、SourceTurn/receipt 和谓词覆盖测试。
- [x] 记录 C++/Python 测试计数、模块路径与 SHA-256；不把旧模块结果冒充当前结果。

### Task 6: 独立真实评测与分析

**Files:**
- Create: `build/socialmem_20260920_structured_eval_hybrid_fenced_predicate_v3_format_reminder/`
- Create: `docs/eval/2026-09-20-socialmem-structured-output-robustness.md`

- [x] 从同一冻结 source parent 准备独立实验并执行 `check`。
- [x] 在已授权网络环境执行 57 题 `hybrid_fenced`；保存原始回执、请求账本、失败分类和 summary。
- [x] 用 C++/Python 分析器计算 scope/holder 完成率、误嵌套残留、schema/scope/admission/传输/写入失败、谓词计数、QA/F1 和 bootstrap。
- [x] 对比历史目录与 JSON Object 诊断，明确哪些差异只代表协议完成率，不能把失败计零准确率当作语义提升。

### Task 7: 设计文档收口

- [x] 将最终模块 hash、测试、请求数、技术完成率和 QA 结果同步到现行中文入口。
- [x] 未满足事前 QA 门槛，已明确保持生产默认关闭。
- [x] 运行 `git diff --check` 和适用完整回归，保存日志路径。

### Task 8: R2.3 重复键与布局对照

**Files:**
- Modify: `docs/superpowers/specs/2026-09-20-socialmem-structured-output-robustness-design.md`
- Modify: `src/extractor/claim_contract.cpp`
- Modify: `tests/cpp/test_structured_output_prompt.cpp`
- Modify: `tests/python/test_structured_output_prompt.py`
- Create: `build/socialmem_20260920_structured_output_layout/`

- [x] 先增加 RED 断言：末端提醒包含“每个 JSON key 只能出现一次”、`BAD:` 和 `GOOD:`，且占位对照不含评测人物。
- [x] 在 C++ 末端提醒中增加重复键约束和最小布局对照，不修改解析器。
- [x] 运行 C++/Python GREEN 与相关回归，再进行独立 57 题评测。
- [x] 只有原始回执显示重复键/误嵌套下降时，才把协议改进记为诊断收益；QA 仍单独统计。
