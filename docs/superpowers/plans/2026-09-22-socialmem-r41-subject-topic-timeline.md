<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.1 人物—话题—时间链实施计划

设计：[R4.1 中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)。用户已授权继续迭代；顺序固定为中文文档、RED 测试、C++ 实现、离线验证和真实双臂评测。

## 任务一：文档和冻结边界

- [x] 新建 R4.1 中文设计与实施计划。
- [x] 在 320 份设计入口追加 R4.1 导航，记录 R4.0 封存结果不变。
- [x] 新实验目录继承 R3.5 父快照，不修改 R4.0 封存目录。

## 任务二：C++ RED 测试

- [x] 新增 `SourceProfileV3`：主体优先时间链、实体关系不触发互动、双人物关系保留互动、第三方归属和诊断字段。
- [x] 先运行并保存 RED；补充未知时间、权限、擦除、UTF-8 和确定性回归。

## 任务三：C++ 实现

- [x] 增加 `evidence_profile_v3` 策略校验与主体/话题分数。
- [x] 改为主体优先 session 代表和严格 human relation 判定；保持 v2、生产默认与 binding 接口不变。
- [x] 运行 SourceProfileV3、全部 Source*、EvidenceAnswer 和完整 CTest。

## 任务四：R4.1 评测和报告

- [ ] 新建双臂 driver 目录，prepare/check/recall/run/analyze/verify 全部通过后再发送请求。
- [ ] 执行真实 57×2 回答、裁判与查询 embedding，记录账本、原始回执、覆盖和 token。
- [ ] 编写 `docs/eval/2026-09-22-socialmem-r41-subject-topic-timeline.md`，报告是否超过 R4.0/R3.5 及所有失败。
- [ ] 同步 320 份设计入口、验收清单和封存哈希；不晋升未达门槛结果。
