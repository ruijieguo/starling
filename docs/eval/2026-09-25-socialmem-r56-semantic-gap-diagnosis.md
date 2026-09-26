# R5.6语义损失诊断：传输修复之后仍缺少什么

日期：2026-09-25，状态补记于2026-09-26。依据已封存Kwame真实回执和冻结C++离线重放；这是开发样本事后诊断，不是抽取级gold标注、召回率或QA成绩。R5.6统一核心的8库重建已在首scope失败并封存，0/8完整健康。后续可靠性修正须另立实验身份，不改写该失败记录。

## 结论与优先级

输出截断已在该固定输入上得到修复，但“谓词不够丰富”不能解释当前全部损失。终态48条生成行只有15条入库，主要损失发生在已有谓词的范围、限定语与字段一致性检查。应先区分三类原因：原生范围判断过宽、模型未遵守声明合同、生成/协议纠错缺少覆盖稳定性，再根据完整开发评测定位真正影响答案的部分。

所有计数来自[独立拒收审计](../../build/socialmem_20260925_r55_work/r56-real-independent-audit.rejections.json)，身份、用量与验收见[R5.6主报告](2026-09-25-socialmem-r56-bounded-claim.md)。

扩大建库还暴露了前置阻断：Mum首次输出非法evidence嵌套字段，纠错后输出批外c8，导致全holder的belief声明不提交。两个HTTP响应均正常，末端也确实存在c0–c7白名单。问题已不只是语义拒收，还包括生成合同遵从。优先执行[R5.7严格输出兼容性诊断](../superpowers/specs/2026-09-25-socialmem-r57-strict-capability-design.md)，不盲目重跑8库或放宽写入范围。

另对Kwame首批已封存原生prompt作纯字节清点：共71940 UTF-8字节，其中SOURCE_DATA_JSON为42009字节（约58.4%），reference examples为11629字节；输入在原文和全部索引来源中重复呈现。本体生成指导要求检查全部来源，批次限制再在末端约束8个目标，可能形成生成目标选择压力。它是可通过原生目标单元隔离实验检验的假设，不能从字节占比直接推定token节省或故障根因。详见[清点证据](../../build/socialmem_20260925_r56_work/kwame-prompt-layout.json)。

## 一、局部陈述被相邻问句或条件影响

QUESTIONED缺失16行，全部使用whole_unit回退：ambiguous_boundary 9，object_not_literal 7。当前`src/extractor/claim_scope.cpp`仅对很窄的“首句陈述＋后续独立问句”定位；连续标点、未闭合尾句、对象非逐字片段等情况退回整话轮，`scope_guards`随后按整话轮是否含问号判定。CONDITIONAL的7行则直接扫描整个来源单元的if/unless等词。

| 来源/原始行 | 原文关系 | 当前拒收 | 诊断与反例要求 |
|---|---|---|---|
| c0，attempt1/wire0 | 开头`I'm so hyped for this!!`表达兴奋，之后才问能否带麦克风 | feels缺QUESTIONED | 有较强的局部陈述可保留线索；连续感叹号不能自动把后续许可问句作用到兴奋陈述。但真正的`Am I excited?`必须继续拦截 |
| c5，attempt1/wire12 | 先确认`the ramp is the Ridgeback one`，随后问结束后去哪里 | knows缺QUESTIONED | 身份确认与后续地点问句可以分别定位；仍须保留同一speaker和原始span，不能把另一人的问句当确认 |
| c21，attempt4/wire9 | 先问`was that me??`，随后陈述今天只吃三根谷物棒 | knows缺QUESTIONED | 当前仅支持首句陈述，不能覆盖“先问后陈述”；需要防止自我撤回、引用和跨句代词改变事实范围 |
| c29，attempt5/wire5 | 决定今冬购买装备；末句另说愿意帮Nadia查资料，`if you want`修饰帮助 | decided_on缺CONDITIONAL | 条件作用于帮助而非购买，是优先构造局部范围反例的样本；`I'll buy gear if you join`必须继续保留条件 |
| c15，attempt3/wire3、4 | 兴奋与读装备清单的承诺，邻句另有忘带物品/未确认的条件 | feels/promises缺CONDITIONAL | 值得逐声明定位；不能只删if检测，必须证明条件究竟限定哪项主张 |

这些是逐条语义分析线索，未把16或7整组认定为误拒。c27的`I genuinely loved it??`带修辞问号；c0的`I've heard there's a scramble ...??`含传闻和不确定性，均需要区别于普通事实陈述。

## 二、模型生成合同不一致不能靠放宽所有校验解决

| 来源 | 可复核现象 | 对改进的约束 |
|---|---|---|
| c7，attempt1/wire17 | 原文与object均含`especially if there's a scramble`，evidence却仅标ASSERTED | 本行拒收有明确合同依据。应让抽取保留CONDITIONAL，不能用“邻句污染”理由无条件放行 |
| c16，attempt4/wire1 | `cannot believe we slept up there`被生成为polarity=NEG、markers=[ASSERTED] | 字段内部矛盾应继续拒绝；还存在惊讶惯用语被错误当事实否定的模型问题。自动补NEGATED会固化错误含义 |
| c10，attempt3/wire2 | object为`edit Tomás's audio piece tonight`，topic为`editing it` | 拒收来自topic逐字包含要求，含义上可能仍保留了编辑对象；需对照检索渲染与代词消解合同，再设计等义改写的正反例，不在Python补对象 |
| c19，attempt4/wire4及c23两行 | time_text保存了today，但object未包含today | 当前合同明确要求object保留时间限定，因此拒收符合现行实现。若考虑以独立字段承载限定，必须同步检索渲染和回答证据测试，不能只删除校验 |
| c20，admission | `no more borrowing people's gear`被抽为forbids | 更接近自己的承诺/计划，不能自然推为对他人的禁止；准入拒收保护了关系精度，需从谓词选择侧改进 |

显式时间缺失的3行还要区分本声明本身有时间约束，还是邻句的today被传播过来。不能把“发生于有日期的话轮”直接当作该声明永远有效，也不能把话轮中的所有时间词复制到每个object。

## 三、协议纠错会改变内容覆盖

第1批首个8行响应因为evidence出现非法holder字段而整批失败，纠正后只有5行，且均语义拒收。c11—c14仅在无效首次响应中有生成行，纠错后消失。当前原子性正确阻止不合法候选入库，但协议完成不能证明每个目标来源都得到充分抽取。

后续可验证的方向是原生协议提示与按来源的覆盖回执：模型明确报告处理过哪些目标单元及哪些单元无可抽取声明，C++严格核验身份/集合与内容；不得用公开QA答案或gold anchors补生成，不得把“已处理”自报当作语义召回真值，也不能静默合并协议失败响应中的行。是否增加此合同，要以固定开发集成本、技术失败和真实QA净收益共同决策。

## 四、实施顺序与验收

先完成当前统一新核心的8库及133题baseline/优化臂对照，保留所有失败和固定分母。随后从实际失败题回链到上述来源，优先处理同时有清晰局部语义依据且影响最终context的能力缺口。

下一轮修改仍遵守中文设计→C++失败正反例→核心实现→binding薄映射→冻结评测。至少包含独立陈述/真实问句、陈述在问句前后、连续标点/省略号/引号、自我撤回、条件限定当前或相邻声明、否定惯用语、时间及topic改写、同一来源多声明和跨speaker隔离。验收同时观察：误放行控制、原始候选/拒收/入库链、实际context变化、fresh QA、请求/token成本。扩大catalog应只在实际存在无法表达的关系时进行，避免用更多谓词掩盖当前表达已存在却被遗漏或误拒的问题。
