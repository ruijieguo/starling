<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.1 人物—话题—时间链检索设计

日期：2026-09-22。状态：R4.1 设计阶段，尚未改变生产默认，也尚未开始新的真实请求。

## 1. 依据与目标

R4.0 两臂均为 19/57。Q7 原话锚点由 2/13 提升到 7/13，Q8 却由 26/37 降到 13/37；`Q8_r3b8c9d0` 中 Cass 的目标发言被第三方会话句挤出，`Q8_v4s3c2` 中“Preet 与实体唱片收藏的关系”误触发互动车道。R4.0 证明了来源数量和日期数量不足以代表人物在话题上的变化链。

R4.1 只修正确定性来源选择：在最终来源配额内优先保留目标人物对问题话题的早期、触发和后期证据；只有问题明确包含至少两名授权人物且使用人际互动词时才启用互动配额。回答提示、抽取、谓词合同和生产默认保持不变，便于把新收益归因于来源集合。

## 2. 选择与不选择

采用 `evidence_profile_v3`，不修改 `evidence_profile_v2` 的历史实现和 R4.0 封存目录。v3 是 v2 的 C++ 确定性改进，不调用 LLM，不读取题号、答案、公开锚点或 query_type，不新增 HTTP 请求。

不在本轮扩大 `k`、提高回答 token、增加规划请求或修改谓词目录。R4.0 的三次原生回答截断说明增加回答预算会改变成本和可比性；本轮先验证上下文选择是否能找回已存在的关键原话。

## 3. C++ 选择契约

### 3.1 目标人物、话题和候选分数

继续使用 `allowed_holders` 和问题中的完整姓名边界识别。问题词经过现有确定性分词；姓名词不作为话题词。每条来源保留已有 BM25 分数，并计算可审计的 `topic_overlap`（问题非姓名词与来源词的去重交集）和 `subject_match`（speaker 是目标人物）。最终排序优先：目标人物匹配、话题重合、BM25、有效时间。

### 3.2 人物关系与实体关系

`human_relation=true` 的必要条件是：问题至少命中两个授权人物，并包含 `relationship`、`between`、`respond`、`work together`、`关系`、`回应` 或 `合作` 等人际词。单人物问题即使包含 `relationship`，也视为人物与主题实体的关系，不启用互动车道。诊断同时输出 `relation_mode`，区分 `human`、`entity_or_self` 和 `none`。

### 3.3 时间链

时间问题按有效时间和 session 分组，但每个 session 首选目标人物自己的最高 `subject_match + topic_overlap` 来源。只有该 session 没有目标人物来源时，才允许相关第三方来源作为补充。早期、晚期和中间车道都从这个“主体优先”的会话代表集合中取值，再以相关性补足；不把第三方覆盖数算作目标人物的主体覆盖。

时间未知来源仍可进入普通相关性，但不能进入时间代表集合或声称覆盖时间两端。诊断新增 `subject_sessions`、`third_party_sessions`、`topic_overlap` 和 `subject_match`，并把 `gaps` 分为 `missing_subject_early`、`missing_subject_late` 与普通来源缺口。

### 3.4 互动邻句

只有 `human_relation=true` 时才构建互动队列。邻句严格服从 session、连续 turn_index 和 `source_dialogue_radius`；第三方句保留真实 speaker，并单独记入 `third_party_interaction`。单人物实体关系问题不因邻句而挤出主体时间证据。

### 3.5 最终配额和保真

沿用 R4.0 的最终 source limit、整行 UTF-8 字节预算和单次展示排序。v3 选择结果后不从未入选池补行，`selection_trace.rendered` 必须与 `source_refs` 完全一致。权限、租户、截止时间、擦除、哈希和 holder 隔离仍在选择之前执行。

## 4. 评测设计

R4.1 使用与 R4.0 相同的 57 题、父数据库、qwen3.8-27b、裁判、超时、零重试和 600 HTTP 上限。双臂仍为：`retrieval`（v3 + legacy）与 `native_answer`（同一上下文 + grounded_memory_v1）；两臂共用一次新检索。R4.0 结果只作为历史比较，不覆盖或重跑。

继续条件不变：相对 R3.5 共同正常题净增至少 5，网络 bootstrap 95% 区间下界大于 0，且没有新的技术退化。R4.0 已未达门槛，R4.1 不预设一定提升；若主体覆盖改善但得分无提升，结论仍为检索选择不足以解决答案能力。

## 5. 验收与回滚

先保存 SourceProfileV3 RED，再实现 GREEN。验收包括：Cass 多 session 主体早晚保留、Preet 实体关系不启用互动、两人关系仍保留邻句、第三方归属、未知时间、整行预算、租户/holder/擦除、降级回执和确定性 trace。失败时只关闭 `evidence_profile_v3` 并恢复 v2；不修改生产 `semantic_claim_contract=false` 与 `claim_protocol_retry_budget=0`。

所有实现位于 C++；Python 只传递策略名、冻结配置、运行双臂和统计。新结果写入独立 `build/socialmem_20260922_r41_subject_topic_timeline`，并另写中文评测报告。
