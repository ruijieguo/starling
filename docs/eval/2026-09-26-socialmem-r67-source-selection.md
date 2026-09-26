# SocialMemBench R6.7：C++ 原生语义证据选择

## 结论

已完成中文设计、失败测试、C++实现、完整来源准备、133次真实选择、同期QA与独立核验。固定133题开发集上，v9正确50/133（37.59%），selector正确56/133（42.11%），净变化+4.51个百分点。按网络聚类bootstrap的95%区间为[-4.58, 17.17]个百分点。

预设扩展开发门槛未通过；不自动晋升默认策略。结果仅覆盖同八库、六个网络的133题开发集，不是完整SocialMemBench或保留集成绩。

这轮观察到小幅准确率增加，但尚未实现稳定的大幅提升：增益4.51个百分点低于5个百分点门槛，区间跨零，候选正常率93.98%低于95%且低于控制97.74%。共同正常123题净增6题为正，但其网络区间仍为[-5.16, 19.35]个百分点。多个条件同时未通过，不能仅修复4道格式失败就推定方案合格。

## 实验边界与核心实现

新增独立C++模块source_selection：收集授权、时间与保留策略过滤后的完整来源池；模型只提议来源编号；C++严格验证编号、归属、数量及UTF-8预算并渲染原始来源。池上限1000行/131072字节，要求eligible_sources与实际来源数完全一致，超限显式失败。最终最多20条/8000字节，保持真实speaker、会话、时间及原文。纯回放接口不替代授权入口。

该实验增加一次读取完整授权来源池的模型选择调用，评估的是增加查询时计算后的策略整体效果；没有把Python变成另一套检索实现，也没有证明结构化声明或谓词能力已等效补齐。Python只承担binding、冻结、编排、审计和统计。默认检索策略保持原有状态。

两臂均用qwen3.8-27b、grounded_memory_v1和1024回答预算，回答thinking关闭；裁判64预算、provider默认thinking，120秒超时、零重试、并发4。候选另有每题最多一次512预算的选择调用。两臂回答政策函数相同，但候选证据包不再携带v9的词面通道coverage提示，因此效果归属于整个候选检索策略。

新选择核心SHA：`2531b82ed5ef169931877b49bb85d5b9dbdceb7197466a128d23085366afef42`。回答工厂及HTTP审计沿用R6.2核心`949484630a9c83d93fb0582c9b37ff6a228e3f39bc80fe020b1384441e0c9bfb`，分别在独立进程使用。这不是整个新核心的端到端生产验证。

## 来源选择结果

|指标|v9|selector|
|---|---:|---:|
|完整来源池|133/133|133/133|
|可用上下文|133/133|129/133|
|公开锚点命中|194/263|205/263|

133题v9的source_refs与block全部复现历史k20。候选改变全部133题上下文；共新增259条、移除2297条来源，锚点新增46、丢失35，净增11。每题完整池42–300条，中位数194；最终上下文来源中位数3条，字节中位数823、最大5341。公开锚点是事后诊断与预设准入指标，不进入选择提示词或答案。

129道选择正常题的同题锚点为187→205/254；完整133题仍保留4道失败，主统计不删除它们。总体锚点改善主要来自Q2、Q5、Q6、Q7；Q8变化题81→71/101，提示时间变化题仍有覆盖损失；其中部分由技术失败导致，剩余差异需与真实QA联合解释。

|题型|题数|锚点 v9→selector|锚点总数|
|---|---:|---:|---:|
|Q1|25|38→37|45|
|Q2|10|7→15|18|
|Q3|1|4→4|4|
|Q4|10|10→12|14|
|Q5|12|13→17|20|
|Q6|8|3→7|14|
|Q7|24|32→37|41|
|Q8|40|81→71|101|
|Q9|3|6→5|6|

## 输出合同与事件机制诊断

4道选择失败均保留原始响应并直接计错，没有补选或补答。3题带Markdown围栏，2题超过20个编号，其中1题同时发生，两类合计4题。两道仅围栏失败不能在本轮事后改成成功；另外两道分别提议24、26个编号。

已确认请求配置边界：OpenAIAdapter::generate调用complete(prompt,false)，不会使用配置json_object_output=true启用response_format。因此本轮选择是提示词约束下的自由生成，不能把围栏输出解释成服务端违反JSON mode。下一轮需要验证真实HTTP请求体的结构化输出配置，不能只检查配置对象。

|失败题|围栏|原始提议数量|正式处理|
|---|---|---:|---|
|Q7_c5d6e7f8|有|7|失败、空候选上下文、零回答请求|
|Q8_d7e8f9a001|有|8|失败、空候选上下文、零回答请求|
|Q8_cf13s6c4|无|24|失败、空候选上下文、零回答请求|
|Q1_b6c7d8e9|有|26|失败、空候选上下文、零回答请求|

**Dan饮酒事件（Q8_cf13s2c3）**：v9判定错误，候选判定正确；候选终态为ok。
候选补齐Rory描述饮酒量、Dan的“Historical Hangover”反思，以及后续调整pub nights方式的原始来源。该机制修复有真实来源证据；最终答题判定仍以上述原始裁判结果为准。

候选原始回答：

> **Cause of the Shift**
> Dan’s shift in approach was caused by a severe hangover following a pub night in Session 2. In that session, Rory reported that Dan had consumed "three 🍺 plus the wine 🍷 plus a round of chasers" (Source 3). The following day, Dan explicitly linked his new perspective to this experience, stating: "I am also not doing that again for some time. The Historical Hangover... the kind where you genuinely revise your view of a thing you previously enjoyed" (Source 5).
>
> **Signals of Genuine Change**
> The evidence indicates this was a sustained behavioral change rather than a temporary reaction, supported by actions and statements in both sessions:
>
> 1.  **Behavioral Consistency Across Time:** One week after the incident (Session 3), Dan declined an invitation to another pub event, citing a "commitment" and offering to "send a card" instead (Source 6). This demonstrates he did not immediately return to previous habits despite the short interval.
> 2.  **Explicit Acknowledgment of Adjustment:** In Session 3, Dan directly confirmed a change in his methodology, stating: "Significantly improved. I have also made some minor adjustments to my approach to pub nights" (Source 8).
> 3.  **Shift in Social Judgment:** Dan’s attitude toward others' drinking habits changed from potential judgment to self-awareness. He noted regarding Marcus: "After last week I am in no position to judge," indicating that the negative experience altered his internal standards and social comparisons (Source 7).

**Marcus表格协作（Q8_cf13s6c4）**：v9判定错误，候选判定错误；候选终态为technical_failure。
原始24条提议已经包含Tom对表格事件的前文、Marcus的省略回应和后续支持行为，但超过20条合同后整体被拒绝。正式结果没有渲染这些来源、没有回答调用。它说明语义定位与可执行的预算计划是两个独立问题，不能把原始提议存在等同于QA成功。

## 同期真实QA

|指标|v9控制|selector候选|
|---|---:|---:|
|正确|50/133|56/133|
|正常|130/133|125/133|
|回答截断|0|0|
|QA阶段HTTP|239|230|
|QA阶段已知tokens|755,806|371,908|

共同正常123题，正确49→55，净变化+6题。此诊断不替代完整133分母；主bootstrap固定seed=20260925、100000次网络聚类重采样，仅六个网络。

配对四格：都对33，仅v9对17，仅候选对23，都错60。

|题型|题数|正确 v9→selector|正常 v9→selector|
|---|---:|---:|---:|
|Q1|25|10→13|25→24|
|Q2|10|5→9|10→10|
|Q3|1|0→0|1→1|
|Q4|10|8→9|10→10|
|Q5|12|4→4|11→12|
|Q6|8|5→3|8→8|
|Q7|24|5→5|24→23|
|Q8|40|11→12|38→34|
|Q9|3|2→1|3→3|

分层为探索性分析，未作多重比较校正。所有上下文均改变；逐题相同裁判输入共0组，其中0组原始标签翻转。保留原判，不以重判替换不利结果。

|网络|题数|正确 v9→selector|净增|
|---|---:|---:|---:|
|grp_7a8b9c0d|5|1→2|+1|
|grp_a5b6c7d8|34|12→11|−1|
|grp_b1c2d3e4|32|14→11|−3|
|grp_c2d3e4f5|27|9→15|+6|
|grp_d7e8f9a0|19|8→11|+3|
|grp_e6f7a8b9|16|6→6|0|

收益具有明显网络差异：去掉grp_c2d3e4f5后，其余106题双方都对41题，净变化为0。这是事后敏感性分析，不替换完整分母，也不代表该网络应该被排除；它解释了为何总体点估计为正、网络聚类区间仍跨零。

## 能力短板与逐题证据

1. **特定事件的语义定位有效，但尚未稳定泛化。** Q2从5/10升至9/10。Q2_b1c2d3e401中，v9把第一次尝试Arch Cafe的安排当成问题所指决策，错误声称没有异议者；候选选出同一次投票中的Greg反对意见及Marcus的最终决定，正确识别Greg。Dan案例也从错误归因于糟糕的问答活动，改为有原话支持的宿醉与行为调整。两例有来源与答案共同变化的机制证据，不能代替全体题目的因果验证。
2. **群体规范与例外仍容易退化为词面主题匹配。** Q6锚点总数3→7/14，但正确5→3/8。Q6_a5b6c7d8只保留三条“急救包”讨论，遗漏Kwame多次忘带必要装备并借用应急外套的来源；Q6_b5c6d7e8只保留Priya两条活动后发照片的消息，遗漏Kwame承认先前未经询问就录制播客的反例。后一题双方都未命中公开锚点，v9原先选对不能证明它理解了规范；候选的局部上下文确实缺少反例所需证据。
3. **压缩可能保留概述而丢掉直接行为证据。** Q8_cf13s7c1中，候选保留Jess“我在努力改变”的概述和Aisha对她迅速承诺的评价，却删掉Jess本人“I'm in. dates?”的直接承诺。回答随后用另一场公园活动的报名解释旅行态度变化，出现事件混接。三个来源并不天然构成完整事件链，应验证前态、触发、行为及他人回应的角色覆盖。
4. **锚点齐全也不保证回答覆盖关键推理。** Q5_cf13s6c2锚点1→2，候选上下文已经包含Jess的“you say that every week”和“the hospital bit”，回答却只解释重复性，遗漏对特定医院话题回避模式的识别，原判由对变错。候选89道全锚点题中有88道正常，其中仅42道判对、46道正常但判错；剩余错误需要进一步区分实际证据完整性、答案遗漏及裁判口径，不能统一归因于检索。
5. **评分存在参考答案覆盖有限带来的盲区。** Q9_d7e8f9a001候选明确回答Callum偏好白天，并引用实际来源中的“arriving early suits me well”和“daytime look … in good light”。原始裁判回执质疑这些引文未出现在参考答案、可能是编造；本轮来源核对确认它们真实存在。候选同时丢失了参考答案使用的“Portugal daytime sessions”强化证据。因此可确认裁判对来源真实性的质疑缺少依据，但不能把整题直接改判为正确。保留原始NO，仅将该案例纳入以后独立、预注册的评分可靠性审计。

本轮并未补齐结构化谓词、人物状态或事件关系的全部表达能力。实验绕过部分声明召回瓶颈，在原始来源池上增加模型选择；结果表明事件定位值得继续，但群体例外、事件角色完整性、答案推理覆盖仍是主要短板。

## 历史对照波动

对R6.6与本轮v9逐题核对，133/133题的上下文哈希、回答提示词及执行配置哈希均相同，历史正确54/133、本轮50/133。共同正常129题为53→49；只有3组完全相同的裁判输入，均未翻转，因此这次历史差异不能简单归因于已证实的“相同输入裁判翻转”，还包含重新生成答案和技术健康变化。比较收益使用本轮同期50→56，不把历史54或其他轮次的最好结果混为同一基线。

## 健康、费用与判定

选择阶段133/133 HTTP，已知与总tokens均为2,552,030，usage完整；选择调用中位延迟6.402秒。QA实际469/478 HTTP，已知tokens 1,127,714，缺usage 7次，总tokens为未知（null）。

两阶段合计HTTP 602/611，已知tokens 3,679,744；合计总tokens为未知（null）。4道选择失败省去8次回答/裁判调用，使本轮实际可调用上界降至603。零重试、零新增embedding，无未结算预约。缺usage没有按零消费处理。

候选包含额外的完整来源池读取和选择模型开销，两臂并非相同的总推理预算。不能只比较QA阶段tokens来宣称候选更便宜。

候选完整链路已知tokens为2,552,030 + 371,908 = **2,923,938**，控制为**755,806**，已知用量账面比值约3.87。两臂分别缺4次和3次QA用量，这个比值不是精确总费用比；没有价格信息，也不换算货币。候选回答请求的中位延迟4.913秒低于控制6.898秒，但每题还增加选择调用（中位6.402秒），不能把两个中位数相加当作端到端中位延迟，也不能据此宣称整体更快。

7次QA超时为控制3次裁判超时、候选3次裁判与1次回答超时；加上4次选择合同失败，共11个技术失败终态。没有回答截断。裁判虽配置max_tokens=64，其provider默认thinking响应报告的completion用量最高仍达6,024；本报告采用原始usage，64不是含推理的总token费用上界。未做额外探测或重试来改写本轮成本和评分。

预设主门槛同时要求：增益至少5个百分点、网络区间下界大于0、共同正常净增为正、两臂正常率至少95%且候选不下降。通过也只允许扩大开发验证，不自动改变默认策略。
- v9错误原因计数：`{"judge response not ok: transport_error:Timeout was reached": 3}`。
- selector错误原因计数：`{"judge response not ok: transport_error:Timeout was reached": 3, "source selection failed; retained in fixed denominator without retry": 4, "answer response not ok: transport_error:Timeout was reached": 1}`。

## 下一轮优化顺序

1. 先修复C++结构化选择调用边界，增加真实HTTP请求体断言，确认JSON输出合同在实际调用路径生效；继续保留未知编号、错误归属和篡改拒绝。
2. 将“来源提议”与“可执行预算计划”分开设计：由模型给出优先顺序及必要事件角色，C++在20条/8000字节内形成明确回执。超限必须可诊断，不能按公开锚点挑选或偷偷回退；保留本轮严格策略作控制。
3. 对变化和群体模式问题优先补前态、触发、后态及反例覆盖，验证3条中位来源是否造成过度压缩。避免为了凑20条而无条件加入无关对话。
4. 修复合同后继续同期评测；再扩大到未参与开发的题目/网络，并独立衡量成本和长来源池能力。现有1000行/131072字节上限不能自动推广到更长记忆。

下一轮仍按“中文设计→通用失败用例→C++实现→冻结评测”执行。优先将结构化请求与可执行预算合同修复作为独立实验；事件角色及反例选择另作可区分的消融，避免同时修改选择、回答和评分导致收益无法归因。对Q6反例丢失、Q8事件混接、Q5已有证据却答漏构造不同人物与文本的通用测试，不将公开锚点或标准答案加入生产规则。当前133题已被多轮用于开发和准入，后续保留集须在方案冻结后评测；健康恢复和开发集涨分都不自动构成晋升。

## 工程证据与复现

先有中文设计与RED，再有C++实现。13项新增原生反例包含在1389项完整C++回归中；另有12项binding、14项选择编排、16项QA编排测试通过。真实库准备/重放、localhost原生HTTP、预算耗尽、缺usage、截断、篡改和中断均有回执。

付费请求前修复了历史依赖枚举、旧Runtime生命周期兼容、预约回执字段、中断账本初始化和历史策略表污染问题。前两版准备快照仅用于零请求诊断，真实评测使用selection-prepare-v3；所有旧回执保留，未覆盖或重跑模型任务。

- [设计](../superpowers/specs/2026-09-26-socialmem-r67-source-selection-design.md)；[实施计划](../superpowers/plans/2026-09-26-socialmem-r67-source-selection.md)。
- [QA诊断](../../build/socialmem_20260926_r67_work/diagnosis.json)；[来源诊断](../../build/socialmem_20260926_r67_work/selection-diagnosis.json)；[格式诊断](../../build/socialmem_20260926_r67_work/selection-format-diagnosis.json)。
- [历史控制波动](../../build/socialmem_20260926_r67_work/historical-control-variation.json)；[收尾验封](../../build/socialmem_20260926_r67_work/finalization-check.json)。
- [验证清单](../../build/socialmem_20260926_r67_work/validation-manifest.json)。

- selection-prepare-v3 seal：`a71cf8193399475a117e9b1a8b8ccd06b3e2b2b3e981762a12f9a6b0d161c73a`。
- selection seal：`902c388e33e12922603cb852b554964b6bcab72650ce803cbd14141fecc56306`。
- qa-prepare seal：`a29f9a1bb0682acf5719bfa6d792211621d143e666615cee3a66a07ae4db198e`。
- qa seal：`f8e037e72a53e012c3813bc4e126bf10e3e6fc62a8d365b31a2b80d7cb3fb26f`。

零请求复核命令：

```sh
.venv/bin/python -B scripts/run_socialmem_r67_selection.py check --out build/socialmem_20260926_r67_expanded/selection
.venv/bin/python -B scripts/run_socialmem_r67_evaluate.py check --input build/socialmem_20260926_r67_expanded/qa
```
