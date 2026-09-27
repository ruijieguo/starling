<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

# R6.2 恢复后的检索与问答评测

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

沿用 R6.1 的 133 题、8 scope、两个检索臂与两个回答政策，产生 266 个上下文、532 个新答案。基础模型固定 qwen3.8-27b；题目、裁判规则、预算及并发约束保持。Python 只编排与统计，检索、提示和答案证据逻辑由 C++ 执行。

新增身份必须绑定 R6.2 隔离核心和 revalidated_recovery build seal。两个复用库必须通过 R6.1 封存 checker、候选核心完整原生回放和最终向量健康检查。余下六库使用同一候选核心新建。任何库不健康都禁止构造检索/回答 provider。

建库费用按 inherited_cost 和 new_cost 分开；评测阶段的检索、答案和裁判均 fresh。不得把复用库说成 fresh-from-zero baseline，也不得把 133 题开发分数称为 SocialMemBench 全量分数。恢复并不构成语义质量提升；能力优化仍需要 baseline 与相同 cohort 的改进后配对比较。

复用既有检索、QA 和独立 check 实现，新增版本入口、正向完整建库门禁及负向反例；使用原生 localhost fixture 验证，再执行真实请求。保留旧版本的固定 SHA 与错误结果。
