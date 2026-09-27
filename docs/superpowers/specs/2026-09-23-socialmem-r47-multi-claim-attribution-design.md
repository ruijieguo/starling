<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.7 多声明保留与第一人称归属车道设计

日期：2026-09-23。状态：C++ 实现、RED/GREEN、离线与真实双臂评测、补充顺序回归、封存核验全部完成；仅针对实验策略 `evidence_profile_v6`。检索臂 19/57、原生回答臂 17/57；涨分受生成/裁判波动影响，未证明稳定质量提升，不晋升生产。结论见[中文评测诊断报告](../../eval/2026-09-23-socialmem-r47-multi-claim-attribution.md)。

## 1. 证据诊断

R4.6 的 7 个 scope 共加载 102 条有效 claim，分布在 90 个来源话轮；11 个来源话轮关联多条 claim。修复前 `load_claim_views` 以来源键为索引、每个键只保存一条 evidence，因此后读声明会覆盖先读声明。R4.6 的 26 道信念归属题中，底层 claim 全为第一人称且 `attributed_to=null`，归属车道选中数为 0。

这两个问题属于 C++ 核心数据模型和选路规则，不能由 Python binding 或回答提示词补偿。R4.6 两臂均为 15/57，不能把本轮修复预先视为准确率收益。

## 2. 目标与边界

目标：

1. 一个授权来源可关联多条通过 `claim_evidence_error` 的 claim；任意合格 claim 可以满足对应车道，但来源仍只占一个上下文名额。
2. 无效 claim 不能覆盖同一来源的有效 claim；有效 claim 的入库顺序、SQLite 行顺序不改变最终车道选择。
3. 第一人称知识/信念允许进入归属车道，但必须满足人物边界：来源 speaker 是实际 holder/actor，且问题只关注该人物，或 claim 的 topic/object 明确提到另一位关注人物。
4. 第三方转述继续要求 `attributed_to` 与来源 holder 一致，并保留真实 actor；跨 tenant、holder、source_turn、时间、哈希、擦除边界不变。

非目标：

- 不在 Python 复制 predicate、人物、归属或 claim 校验逻辑。
- 不把所有第一人称 `believes/knows` 自动视作“关于另一人物的归属证据”。
- 不把 claim 文本注入回答上下文；上下文仍渲染原始 source 行。
- 先完成固定数据库的离线行为验证；通过后沿用用户授权执行独立真实双臂评测，限制 600 HTTP、零重试。

## 3. C++ 数据模型

`Source` 从单一 `claim` 扩展为 `claims: vector<Json>`，`claim_loaded` 表示集合非空，仅用于兼容诊断和普通成员优先级。`load_claim_views` 的值改为包含多个 `evidence` 的集合：

- 每条 claim 单独执行 `parse_claim_evidence`、`claim_evidence_error`、source span 回连和 tenant/holder 校验；
- 通过校验的 claim 追加到来源集合，`claim_metadata_loaded` 仍按 claim 条数递增；
- 被拒绝的 claim 只累计拒绝原因；只有来源没有任何有效 claim 时才保留 `claim_rejection`；
- 选择排序对 claim 集合做 `any_of`，不会改变来源名额、字节预算、去重和最终渲染。

使用稳定排序和 claim 的规范字段（predicate、semantic_family、actor、attributed_to、topic、object、source_turn）作为资格判定；不使用指针地址、SQLite 行号或写入顺序作为业务优先级。

## 4. 第一人称归属车道

对每个来源的每条有效 claim：

- **第三方转述**：`attributed_to` 非空，且与 source holder 相同；claim actor 可以是被描述人物，但必须经过既有证据合同。
- **第一人称自述**：`attributed_to` 为空、`actor == source speaker`、perspective 为 `FIRST_PERSON`，并且：
  - 关注人物只有 source speaker；或
  - claim 的 `topic` 或 statement object 中通过现有人物边界匹配明确提到另一位关注人物。
- 其他组合不进入归属车道，继续作为普通 source；不通过代词、同意、邻句或关系词猜测人物归属。

一条来源只在首次被车道 `take()` 成功时计数；多条 claim 只影响资格，不重复占用来源名额或重复计数。归属车道按现有相关性、时间和 source id 稳定排序。

## 5. 诊断字段

保留并明确：

- `claim_metadata_loaded`：通过校验的 claim 条数；
- `belief_attribution_claim_selected`：最终由归属车道新选入的来源中至少含一条合格 claim 的来源数；
- `claim_lane_fallbacks`：只统计成员车道成功新增普通来源；不统计 claim sibling、重复来源、预算拒绝或无候选；
- 新增 `claims_per_source_max` 和 `claims_per_source_multi_source_count`，用于核对多声明保留，不作为质量分数。

## 6. 测试顺序与验收

严格执行“中文设计 → C++ RED → C++ 实现 → 回归 → 离线评测”：

1. RED：同一 source 写入 `knows` 与 `prefers`，反转写入顺序仍必须进入知识车道；第一人称关于另一关注人物的 `knows` 必须进入归属车道；无关 self claim 不得进入；无效 sibling 不得覆盖有效 claim；跨 tenant/holder/source_turn 仍拒绝。
2. GREEN：定向 source retriever、完整 CTest、Python binding 回归；检查多 claim 诊断和 `lane_selected_rendered` 一致。
3. 离线冻结库：零网络、57 题 source diagnostics，比较 claim 条数、归属选中数和 prompt 变化；不以离线替身回答作为准确率。
4. 只有离线行为与合同稳定后，才设计独立 R4.7 真实双臂评测；未获得新鲜 QA 证据前不晋升生产。

## 7. 最终验收与保留问题

- 主修复遵循设计 → 初始 RED → C++ 实现。反向写入顺序、SQLite 反向读取和单人物自述共 5 项为实评后补验：旧 R4.6 核心均失败，恢复当前核心后全部通过；补验未改变生产代码。
- 最终定向 C++ 54/54；完整 CTest 1276 项中 1253 通过、23 沙箱跳过，相关 HTTP 另行 30/30 通过；Python 71/71。
- 离线 57 recalls、114 terminals、0 请求；真实两臂共 114 个正常终态、547/600 HTTP，0 重试。所有封存核验通过。
- 单源最多 3 条 claim；归属车道新选入含合格 claim 的来源累计 16、涉及 13 题。source 名额、整行字节与最终渲染计数保持一致。
- 相比 R4.6 的 +4/+2 题不能全归因于修复：检索臂 +4 全部来自同 prompt 子集；3 个同答案同裁判 prompt 跨轮翻转。来源锚点 48/104，未晋升。
- 状态车道 family 和 actor 的集合判断仍分开；跨 sibling 拼接资格是待构造 RED 的静态风险，不把本轮集合修复等同于完整角色/时序推理。下一轮按报告的诊断优先级单独设计。
