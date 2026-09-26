# R6.2 建库期间的候选作用域诊断

## 证据范围

只分析 R6.1 两个已封存、并由 R6.2 新核心重放通过的真实来源库。这里不读取题目答案来修订抽取，也不把诊断代替尚未完成的 133 题 baseline。统计来自原生 receipt，Python 只汇总字段；输出位于 `build/socialmem_20260926_r62_work/inherited-claim-diagnosis.json` 和 `question-scope-examples.json`。

44 次 belief 尝试保留 100 条候选，本地语义检查拒绝 137 条。拒绝是候选事件数，不能直接当作源事实数、唯一事实数或误拒率。

| 原生拒绝原因 | 次数 | 能说明的边界 |
|---|---:|---|
| 缺少 QUESTIONED | 80 | 整话轮有问句，但候选未携带疑问标记；需判断标记是否真的支配候选 |
| 缺少 CONDITIONAL | 28 | 条件标记覆盖范围和模型状态判断可能不一致，不能一律改为无条件 |
| topic 不在来源单元 | 8 | 主题补全超出当前可核验来源 |
| 缺少显式来源时间 | 7 | 抽取丢失时间约束 |
| object 丢失时间限定 | 7 | 候选内容与来源状态时点不一致 |
| object 丢失 topic | 5 | 摘要过度压缩或主题被错误提升到元数据 |
| 缺少 NEGATED | 1 | 丢失否定仍应严格拒绝 |
| actor 与 subject 不同 | 1 | 人物归属风险仍应独立处理 |

被拒绝最多的谓词是 prefers 37、believes 30、decided_on 21、feels 17。这些谓词已经存在，因此当前损失不能简单归因于“谓词种类不够”。它们还依赖候选与来源片段的对应、状态强度、人物归属和时间限定。

## 三类例子需要不同处理

Mum 的来源是 “Has anyone heard from your father today? He's being very quiet and I'm slightly worried. Just me probably!”；候选是 feels / “slightly worried about your father being very quiet today”。候选改写导致 object_not_literal，随后整话轮问句覆盖明确表达担忧的陈述。此例支持调查候选证据片段的疑问作用域，但父亲/He's 的指代仍需要完整话轮做语义核验。

同一来源集中，“Should we do something special?” 和 “maybe a party? Invite the family?” 表达建议或试探。直接把它们作为已决定的事实可能过强。新方案必须区分提议、愿望和决定，并保留 QUESTIONED/不确定性反例；不能仅为提高保留数撤销检查。

Kofi 表达 “I want to be there. March is ... very hard ... Can we look at what works for everyone ...?”，候选却是 prefers / “to be there in March”。原文同时表达参加意愿和对三月安排的困难。该候选可能把两个维度合并得过强；即使能移除无关问句影响，也不意味着应无条件保留该改写。

## baseline 后的验证顺序

1. 先按题目检查最终选中的上下文，区分未抽取、被本地拒绝、已入库未召回、已召回未渲染、答案推理或裁判变化。库内出现候选不等于答题可用。
2. 对确认的误拒设计候选级支撑片段合同。优先考虑精确来源引用和原生字节坐标核验，使改写后的 object 不必逐字匹配；完整来源继续用于 admission 和指代核验。只存在引用不等于蕴含成立。
3. 首轮只研究疑问作用域，条件、否定、引用、转述和时间约束分别保留严格反例。不要把两种作用域同时放宽而失去归因能力。
4. 中文设计先明确可接受与必须拒绝的真实/合成例子，再写 C++ RED 测试，最后实现；语言 binding 不实现独立的分句或判断算法。
5. 先做同库离线检索消融，检查上下文是否实际变化，再运行相同 cohort 的新回答与裁判。报告正确/错误转换、技术失败、token成本和网络层面的配对差值，不能用保留候选增加替代准确率收益。

当前上述优化尚未实施。R6.2 只修复最终向量健康门禁并恢复 baseline 执行，保持抽取和检索语义，以便下一轮有可比起点。

## 八库完成后的补充统计

八库已全部完成并通过独立检查。197个belief批次对应197次抽取尝试，没有真实协议纠错触发；179次准入调用均成功返回。原生本地检查拒绝451个候选事件，681个候选进入准入，准入再拒绝159个，保留522个。`semantic_rejected`同时包含本地与准入拒绝，统计必须与`semantic_rejections`明细分开，避免把610个总拒绝事件全部误算为本地检查拒绝。

本地主要原因：QUESTIONED 194、CONDITIONAL 134、object丢topic 30、topic不在来源29、缺来源时间28、object丢时间21、NEGATED 7。准入主要原因：wrong_relation 104、wrong_scope 28、missing_context 9、not_asserted 8、unsupported 7、wrong_attribution 3。现有谓词中believes、prefers、decided_on、feels分别被本地拒绝123、103、68、61次，说明候选忠实度、作用域和关系强度仍是需要逐例定位的损失来源。

这些是候选事件计数，既不是唯一事实数，也不是误拒率。数据库中的934条声明还包括其他抽取通道；不能把522条belief候选保留数与数据库声明数混作同一分母。统计程序和完整原生证据散列位于`build/socialmem_20260926_r62_work/{summarize_build_diagnostics.py,eight-scope-build-diagnosis.json}`。
