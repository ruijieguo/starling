<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench R3.3 证据覆盖与跨会话检索实施计划

> **面向执行代理：** 实施时必须按任务逐项执行；每个任务使用复选框记录，严格遵守“中文设计 → RED 测试 → C++ 最小实现 → 回归 → 独立评测”。

**目标：** 在不改变抽取合同和评分协议的前提下，让 C++ 检索把目标人物的关键原文、跨 session 早晚状态和关系证据稳定送入 hybrid 回答上下文。

**架构：** `ObserverRetriever` 在 C++ 内完成全体成员识别、时间问题检测、focused coverage 和 SOURCE 配额；Python binding 只映射字段，评测脚本只透传配置和保存回执。

**技术栈：** C++17、nlohmann/json、GoogleTest、pybind11、pytest、现有 SocialMemBench 评测脚本。

**规范：** [R3.3 设计](../specs/2026-09-21-socialmem-r33-evidence-coverage-design.md)。

## 全局约束

- 保持 `claim-predicate-v3`、strict JSON、scope/admission、租户隔离和生产默认 `semantic_claim_contract=false`。
- 保持固定 57 题、7 个 scope、36 个 holder、qwen3.8-27b、回答/裁判预算、零重试和原始回执。
- 默认 `source_strategy=bm25`、`min_source_items=0` 的旧输出必须保持兼容。
- C++ 是检索选择和配额的唯一实现；Python 不解析来源、不补齐候选、不实现人物或时间逻辑。

## 任务 1：设计与同步文档

**文件：**

- 已创建：`docs/eval/2026-09-20-socialmem-r32-schema-envelope.md`
- 已创建：`docs/superpowers/specs/2026-09-21-socialmem-r33-evidence-coverage-design.md`
- 已创建：`docs/superpowers/plans/2026-09-21-socialmem-r33-evidence-coverage.md`
- 修改：`docs/design/system_design.md`
- 修改：`docs/design/claim_contract_sync.md`
- 修改：`docs/design/subsystems_design/07_neocortex.md`
- 修改：`docs/design/subsystems_design/08_cognizer.md`
- 修改：`docs/design/subsystems_design/13_retrieval.md`

- [x] 写入 R3.2 逐题诊断和 R3.3 方案边界。
- [x] 在五份设计入口追加 R3.3 中文状态段。
- [x] 运行 `git diff --check`，确认无占位语句和空链接。

## 任务 2：C++ RED 测试

**文件：**

- 修改：`tests/cpp/test_source_retriever.cpp`
- 测试：构建目录中的 `starling_tests`

- [x] 添加全体成员标记的 holder coverage 用例。
- [x] 添加时间问题早晚 session 选择用例。
- [x] 添加 hybrid `min_source_items=7`、默认兼容和预算不足用例。
- [x] 添加非法 `min_source_items` 组合拒绝用例。
- [x] 运行专项 C++ 测试，保存 RED/GREEN 日志到 `build/socialmem_20260921_r33_green_cpp.log`；RED 证据为接口缺失编译错误。

## 任务 3：C++ 最小实现

**文件：**

- 修改：`include/starling/retrieval/source_retriever.hpp`
- 修改：`src/retrieval/source_retriever.cpp`

- [x] 增加并校验 `ObserverQuery.min_source_items`。
- [x] 扩展 C++ `focused_holders` 的全体成员标记识别。
- [x] 为时间问题建立首尾交替的 session 队列。
- [x] hybrid 先满足来源配额，再用声明补位；默认零配额输出保持兼容。
- [x] 写入实际来源数、声明数、配额和预算拒绝诊断。
- [x] 运行同一专项测试，保存 GREEN 日志到 `build/socialmem_20260921_r33_green_cpp.log`。

## 任务 4：binding 与离线回归

**文件：**

- 修改：`bindings/python/bind_05_retrieval.cpp`
- 修改：`python/starling/eval_ladder_pipeline.py`（只透传字段）
- 修改：`scripts/run_socialmem_structured_eval.py`（只增加 R3.3 配置）
- 测试：`tests/python/test_source_retriever_binding.py`、`tests/python/test_socialmem_structured_eval_guard.py`

- [x] 安装新 `_core`，记录模块路径并验证 `ObserverQuery.min_source_items` 可见。
- [x] 运行 C++ 来源专项、Python binding/guard 专项和相关结构化回归。
- [x] 离线回放 R3.2 的 56 道技术正常题，BM25 为 24/56、focused coverage 为 45/56；未发送模型请求。
- [x] 检查 Python 只透传字段，没有新增来源解析、人物识别或答案清洗逻辑。

## 任务 5：独立 R3.3 真实评测

**目录：**

`build/socialmem_20260921_structured_eval_hybrid_fenced_predicate_v3_r33_evidence_coverage/`

- [x] 复用 R3.2 的冻结题目和来源 parent，生成新的身份、配置、scope manifest 和执行计划。
- [x] 固定 `source_strategy=focused_coverage`、`min_source_items=7`、`source_seed_k=5`、`source_seed_max_context_bytes=4000`、`source_dialogue_radius=1`，其余预算不变。
- [x] 在已授权网络环境执行 57 题，保存所有原始抽取、回答、裁判、账本和选择 trace。
- [x] 运行分析，报告 SOURCE/FACT 计数、金标话轮命中、技术失败、全题准确率、成功子集准确率和同题配对 bootstrap；结果见 R3.3 报告。

## 任务 6：结论与文档同步

- [x] 新建中文报告 `docs/eval/2026-09-21-socialmem-r33-evidence-coverage.md`。
- [x] 把 R3.3 状态追加到系统设计、Neocortex、Cognizer、Retrieval 和 claim contract 同步文档。
- [x] 真实结果未达到预注册 QA 门槛，已明确不晋升且保持生产默认。
- [x] 最后运行专项测试、相关 Python 回归、CTest 和 `git diff --check`；沙箱 loopback 失败单独记录。
