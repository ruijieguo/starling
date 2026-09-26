<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.9 主题排序实施计划

设计见[中文设计](../specs/2026-09-24-socialmem-r49-topic-ranking-design.md)。执行中文文档 → RED → C++ → 回归 → 冻结消融 → 真实复评；核心不放入 Python。

- [x] 写中文设计，固定功能词表、A/B 消融和最终候选 B。
- [x] 同步 335 个当前设计、规格、计划及技术报告入口。
- [x] A 的 4 项测试先 RED：3 项预期失败、1 项控制通过；实现后 65 项定向 GREEN。
- [x] A 零网络 57 recalls、114 terminals 闭环封存；相对 R4.8 改变 41 题 source/block，锚点 67/104 不变（2 题得、2 题失）。
- [x] B 的 4 项测试在 A 上 RED：2 项预期失败、2 项控制通过；实现后 69 项定向 GREEN。
- [x] 最终 CTest 1291 项（1268 通过、23 沙箱跳过）、HTTP 补跑 30/30、Python 65/65；构建、安装、真实封存核心哈希一致。
- [x] B 零网络闭环封存；相对 A 单独改变 6 题 source/block，锚点无变化。相对 R4.8 改变 41 题 source/block，锚点 67/104，完整得失保存在外置诊断中。
- [x] 根据事前条件执行独立真实评测：检索 17/57、原生 16/57，两臂较 R4.8 各净 −1；114/114 正常、547/600 HTTP、零重试。
- [x] 完成 prompt 分层归因、1 条相同裁判输入翻转审计及代表题原文对照，保留原始分数。
- [x] 完成中文报告、335 个设计入口状态同步和五个实验只读封存核验；未达门槛不晋升。

## 当前证据

- A：`build/socialmem_20260924_r49a_topic_offline`；B：`build/socialmem_20260924_r49b_topic_member_offline`。
- 真实：`build/socialmem_20260924_r49_topic_member_real`。57/57 检索正常，41 题 source/block 改变、statement 全不变；锚点 48→51/104（4 题得、1 题失）。检索 17/57（29.82%）、原生 16/57（28.07%），未证明准确率提升；Q6 来源锚点仍 0/6，但两臂均从 1/3 增至 2/3。
- 最终核心 SHA256：`bc3d34327ef7ae2edaf298a7960ad805453f4ed857873caac852a387eb9d613f`。
- 诊断：`build/socialmem_20260924_r49_diagnostics/`；Q6 六个锚点全部 topic_relevance=0，提示词汇匹配限制，不按基准词扩充词表。
- 完整结果、配对区间、答案与裁判波动边界、后续语义/事件能力方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。该后续方向尚未实现，不计入本轮成绩。
