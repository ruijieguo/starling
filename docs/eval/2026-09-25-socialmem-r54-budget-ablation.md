# SocialMemBench R5.4：来源预算消融与问答复评

日期：2026-09-25。状态：中文设计、失败测试、C++实现、独立审查、真实检索、fresh QA及独立验封均已完成。legacy从18/57升至23/57，grounded_memory_v1从18/57升至25/57；两policy均达到事前扩大开发验证门槛，扩大验证尚未执行，产品默认不变。

## 1. 范围与主要结果

当前验证仍为 **57 题、7 scopes、6 networks 的开发 cohort**。它不是全量 SocialMemBench、保留集或生产验收。104 个公开金标锚点是题目—来源对，金标仅用于检索后的统计。

v9 将 v6 的来源选择顺序与独立来源预算组合，来源与声明共用严格字节预算；纯来源路径跳过不参与选择的 planner/embedding。来源锚点从健康 baseline 的 **51/104（49.04%）提高到 67/104（64.42%），增加15.38个百分点**。15题增加锚点，42题不变，没有丢失锚点；来源扩容也未替换原 source7 的任何已选来源。全部57题的实际回答上下文发生变化。

| 同核心检索组 | 每题来源 | 声明渲染总次数 | 锚点命中 | 零锚点题 | 全锚点覆盖题 | 平均上下文字节 | 嵌入请求 |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline：v6 hybrid，k=10 | 7 | 171 | 51/104 | 22 | 18 | 2,814.81 | 345 |
| source7：v6 sources，k=7 | 7 | 0 | 51/104 | 22 | 18 | 1,605.53 | 0 |
| source10：v9 sources，k=10 | 10 | 0 | 67/104 | 16 | 29 | 2,280.53 | 0 |
| sidecar：v9 hybrid，k=10 | 10 | 44 | 67/104 | 16 | 29 | 2,806.19 | 345 |

baseline/source7 的来源引用与文本逐题一致，source10/sidecar 的来源引用、文本、来源字节逐题一致。228条回执全部健康，无技术失败或降级。source10 来源更多，但去掉冗长声明后平均上下文较 baseline 缩短18.98%，最大3,274字节，远低于8,000字节上限。

sidecar 只有诊断资格，本轮不进入 QA；44次声明渲染尚无本轮人工相关性验收。source10 不产生声明，其相关性指标为“不适用”，不能记为100%。

## 2. 分 network 覆盖变化

| network | 题数 | baseline锚点 | source10锚点 | 锚点增加题数 |
|---|---:|---:|---:|---:|
| grp_0d1e2f3a | 6 | 5/12 | 5/12 | 0 |
| grp_2b3c4d5e | 10 | 3/16 | 5/16 | 1 |
| grp_3c4d5e6f | 8 | 8/14 | 8/14 | 0 |
| grp_4d5e6f7a | 9 | 16/23 | 21/23 | 5 |
| grp_9c0d1e2f | 6 | 2/12 | 6/12 | 4 |
| grp_a3b4c5d6 | 18 | 17/27 | 22/27 | 5 |

四个 network 获益，两个不变。仍缺37个锚点，16题没有命中任何金标锚点，说明仅恢复覆盖车道并增加三个来源名额，尚不能解决人物、事件、隐含意图及群体规范的检索问题。锚点是证据覆盖代理，完整命中也不保证回答推断正确。

| 题型 | 题数 | baseline锚点 | source10锚点 |
|---|---:|---:|---:|
| Q1 | 11 | 13/17 | 14/17 |
| Q2 | 4 | 1/5 | 1/5 |
| Q3 | 2 | 1/7 | 1/7 |
| Q4 | 6 | 4/9 | 5/9 |
| Q5 | 7 | 3/10 | 4/10 |
| Q6 | 3 | 0/6 | 0/6 |
| Q7 | 8 | 6/13 | 8/13 |
| Q8 | 16 | 23/37 | 34/37 |

Q8贡献11/16个新增锚点，群体规范Q6和多人观点Q3仍未改善。独立检查C++的selection_trace确认104个金标来源都进入了授权候选池，未命中的37个均“存在但未选中”，没有任何候选因字节预算被拒绝；570次渲染已用满57题各10条的来源名额。因此本批短板主要在候选选择，而不是候选缺失或字节不足。

37个漏选锚点中32个topic_relevance为零，10个subject_match=false：其中6个来自已识别聚焦人物以外，另4个所在题目未识别聚焦人物；同时已命中的67个锚点中也有35个词面分为零。零词面分不能作为无关的硬过滤，人物优先也不能排除带明确关系的第三方证言。来源可具备多种资格，但实际selected_by和车道选择计数按首次选入车道互斥记账，source10合计570条；状态角色、成员覆盖等诊断指标另算，不能混加。

事后原文与trace审阅发现三个值得单独测试的机制：

1. **人物齐全，但事件错配。** 投稿态度题已覆盖四名成员，却用Diane关于“明年展览”的话替代本次投稿态度；Luca的成员名额展示集体作品数量，缺少本人不投稿的理由。因此member_missing为空不代表多人答案证据完整。
2. **目标人物自己的新决定已选，第三方说明的原因未选。** Chidi探访态度题选中“I will come in March”，但原先安排与体检触发原因均出自Ngozi，未被选中，且support_requested=false。按问题中姓名优先本人发言不足以覆盖跨说话人原因。
3. **变化链角色齐全，但没有绑定同一决策维度。** Diane独立策展题的early/late/trigger各为1，早期锚点仍缺失；角色来自不同人物或不同决策内容。合法self-state声明与三个角色计数不能证明同主体、同事件的因果链。

Q6三个问题的成员覆盖也全部“完整”，但规范反例均未被选中，例如把“不停步”的群体断言与Bev要求咖啡休息的发言分开了。这些是选择缺口证据；公开锚点并不穷尽有效来源，不能仅由漏锚点断定某题必错。完整原文、trace、负例设计见[逐题来源诊断](../../build/socialmem_20260925_r54_work/source-diagnostics.md)。

## 3. 核心实现与有效期修复

实现顺序为中文[设计](../superpowers/specs/2026-09-25-socialmem-r54-budget-ablation-design.md)与[计划](../superpowers/plans/2026-09-25-socialmem-r54-budget-ablation.md)→失败测试→C++实现→回归→冻结检索。v9来源选择复用v6，sidecar共用v8严格回链；不使用v8的direct-priority，不进入v7/v8的semantic/event来源排序。Python仅负责binding、评测编排和统计。

失败测试另发现既有semantic planner缺少声明有效期过滤，可能召回未来生效或已过期声明。C++ semantic候选现在复用结构化路径的资格过滤，source claim metadata也对齐 `[valid_from, valid_to)`；NULL和空界无界，不从observed_at推断有效期，保持原语义DTO、cosine分数及salience/activation/provenance。父7库只读审计共299条声明，未来和过期均为0；本批质量结果不能作为该边界修复的收益证据，修复由独立反例验证。独立比较R5.3与R5.4健康baseline，57题的block、source_refs与statement_ids均逐项相同；这支持有效期修复未改变当前批次上下文。

| 验证范围 | 结果 |
|---|---:|
| v9未注册RED | 11项预期失败 |
| 有效期反例RED | 2项预期失败 |
| C++来源及planner专项GREEN | 79/79 |
| 完整C++回归 | 1,312/1,312 |
| 相关Python回归，含binding、检索与QA编排 | 140/140 |
| 其中R5.4检索编排合同 | 21/21 |
| 其中R5.4 QA编排合同 | 31/31 |

编排审查还补齐holder回执与请求数一致、显式list型空degraded_paths、57唯一题和228唯一任务校验，避免降级/零请求伪健康和重复题漏账。

新core SHA-256：`02a2a3d8c653d331c700cdf652c59fefe2b812ff99845271bd5137bebf81dd3d`。测试及评测显式加载隔离的新核心，避开旧editable绑定；独立重算当前核心、冻结核心及5个修改文件哈希一致。

## 4. 请求与恢复记录

首轮预检产生4条回执、8次嵌入，sidecar一名holder出现`embedder_unavailable`后停止，保留incomplete封存；回执不足以确定供应商底层失败原因。重试在新目录完整重建四组，共690次嵌入，零降级，不混入旧预检回执。本轮累计嵌入698次，评测启动重试一次，每次HTTP均无自动重试。

QA使用`qwen3.8-27b`，baseline/source10两臂各57题×legacy/grounded_memory_v1，500请求上限、回答512、裁判64、零重试。回答关闭thinking，裁判沿用原协议、未显式设置thinking。只比较同一新核心上fresh生成的回答，不复用R5.2存在嵌入降级混杂的旧分数。

全部228个回答任务完成终态：222正常、6次回答截断；实际228次回答+170次裁判=**398次请求**，比无失败上界404少6次，因为截断回答不进入裁判。SQLite账本逐条独立核验228条reservation，committed=398、reserved=0、charged_upper=0、remaining=102，HTTP尝试回执也为398次。检索加QA本轮累计**1,096次请求（698嵌入+398回答/裁判）**。未执行新增抽取，无供应商金额账单，不能把请求数直接换算费用。

| QA组 | 回答请求 | 裁判请求 | 正常终态 | 截断 | 总token |
|---|---:|---:|---:|---:|---:|
| legacy baseline | 57 | 44 | 57 | 0 | 112,290 |
| legacy source10 | 57 | 44 | 57 | 0 | 107,069 |
| grounded baseline | 57 | 40 | 53 | 4 | 194,808 |
| grounded source10 | 57 | 42 | 55 | 2 | 207,568 |

QA总usage为621,735 token。170条裁判响应报告reasoning_tokens合计145,619；228条回答响应未提供该字段，标为缺失而非观测零。裁判的实际completion token明显超过请求中的64，说明这个旧协议参数不能作为真实总completion或推理开销上限。source10的回答阶段token在两policy下均减少，但grounded裁判token增加，因此不能由上下文字节缩短推出总成本必然降低。

## 5. Fresh QA增益与配对统计

| 回答策略 | baseline | source10 | 全题净增 | 差值95%区间（百分点） |
|---|---:|---:|---:|---:|
| legacy | 18/57＝31.58% | 23/57＝40.35% | +5题，+8.77个百分点 | [1.41, 21.43] |
| grounded_memory_v1 | 18/57＝31.58% | 25/57＝43.86% | +7题，+12.28个百分点 | [4.65, 17.46] |

区间按6个network整组有放回重采样100,000次，seed=20260925。每次重采样按所选network实际题数计算准确率差，不把57题当作57个独立network。重算结果与封存统计逐项一致。

legacy共同正常为57题，9题由错变对、4题由对变错、44题正确性不变，净增5题。grounded共同正常为52题，baseline18/52、source10 24/52，9题改善、3题退化、40题不变，净增6题；差值为11.54个百分点，95%区间[4.76,16.22]。**两policy均满足共同正常净增≥5题、区间下界>0的事前门槛。** 这是允许扩大开发验证的信号，不是全量或保留集验收；6个network、反复使用的开发cohort及单次随机生成/裁判不支持直接宣称生产稳定性。

| 全题配对四格 | legacy | grounded |
|---|---:|---:|
| 两臂都对 | 14 | 15 |
| 仅baseline对 | 4 | 3 |
| 仅source10对 | 9 | 10 |
| 两臂都错或失败 | 30 | 29 |

grounded的6次截断涉及5个不同题目，发生在两臂同一题的截断只从共同正常分母扣除一次。source10减少2次截断，但全题+7与共同正常+6说明增益不全由技术恢复解释。六次均为HTTP200、finish_reason=length、completion_tokens=512，无自动重试，无裁判/网络失败。错误题目与原始响应完整保留。

### 5.1 增益分布及剩余能力

| 题型 | 题数 | legacy baseline→source10 | grounded baseline→source10 |
|---|---:|---:|---:|
| Q1 | 11 | 5→3 | 6→5 |
| Q2 | 4 | 2→3 | 2→3 |
| Q3 | 2 | 0→0 | 0→0 |
| Q4 | 6 | 3→4 | 3→4 |
| Q5 | 7 | 1→2 | 1→1 |
| Q6 | 3 | 1→2 | 1→2 |
| Q7 | 8 | 1→2 | 1→2 |
| Q8 | 16 | 5→7 | 4→8 |

Q8的来源锚点23→34/37与答题分数同时提高：legacy净增2题，grounded净增4题；仍分别有9题、8题未答对。Q3多人观点两policy仍0/2，与事件/成员证据错配诊断一致，但样本太少，不能概括所有多人问题。Q1来源锚点增加1个，准确率却下降，说明更高覆盖无法代替正确利用证据及稳定裁判。

锚点增加的15题，legacy正确4→7、grounded3→9；这两组均无由对变错题。其余42题锚点数不变，但legacy14→16、grounded15→16。不能把所有收益归因于公开锚点：增加的非金标来源、去掉声明、回答随机性和裁判差异也会改变结果。Q6锚点仍0/6却两policy均1→2/3，说明锚点命中与判对并不等价；非金标替代证据、模型推断或猜测、判分误差都可能影响结果，需逐题核验，不能仅由零锚点判对证明上下文充分。

按network，全题净增分别为legacy `[+2,0,+2,0,+1,0]`，grounded `[0,+1,0,+2,+1,+3]`，顺序与上文network表一致。本批没有network总分下降，但局部题目退化仍需分析。

### 5.2 裁判一致性与历史口径

本轮没有“回答prompt与答案同时相同”的重复组；因此该严格指标的0次翻转不能解释为裁判稳定。进一步按**实际judge prompt逐字相同**分组，找到1组、2条回执：legacy的`Q1_a3b4c603`两臂回答逐字相同、裁判输入也相同，baseline被判YES，source10被判NO。它贡献1题表观退化，不能归因于检索或回答能力下降；主评分不改写、不事后补判。只有一组重复，不能估计总体裁判错误率。network bootstrap条件于本次已观测标签，不包含重复生成/裁判的全部不确定性。

另一个历史对照提醒：本轮source10的57个block及source_refs，与本机R5.1降级v6的历史recall文件当前字节完全一致。本轮意义是把该来源覆盖明确实现为健康、无无用嵌入的原生路径，并在同核心健康baseline上重新测量组合收益；它不是此前从未出现过的新上下文。R5.1旧seal仅覆盖4个总览文件，不覆盖recalls；该历史检查只作本机文件内容比较，不证明旧运行全链路完整性，不将旧QA分数作为本轮baseline。

### 5.3 代表病例：哪些是证据利用，哪些仍未解决

独立代理对9题×两policy×两臂共36条正常回答逐项核对完整上下文、答案、reference及judge输入，56个所用封存文件在审阅前后哈希一致。**这是事后代理审阅，不是人工标注或新的准确率。** 原分数不改，不由选出的病例估计错误比例。

| 病例 | 可定位的变化 | 结论边界 |
|---|---|---|
| Diane独立投稿 | 新增“didn't run it past anyone first, I just knew”完整原话，两policy答案均引用，均错→对 | 直接证明新增行动证据被使用，不能单因归为删声明 |
| Nora与Bex的关系 | 新增借相机、六张可用照片、预测次周购机的互动，两policy均引用并错→对 | 具体细节支持指导关系推断，关系不是原文直接标签 |
| Emeka回家态度 | grounded引用新增未决定起点与“Yes Dad…we'll make it work”承诺端点，错→对 | 父亲直接命令仍缺；legacy仍混淆March/Christmas，时间链尚未完整 |
| Cass路线偏好 | 两policy均把Bev“平路便于聊天”的理由推给选择同路线的Cass，对→错 | 属于可定位的跨人物动机推断；单次生成不能证明唯一诱因 |
| Marcus膝盖限制 | source10准确引用新增“Not sure my knee is up to it right now”，grounded却对→错 | reference的“never states it directly”与完整历史存在冲突；保留NO，不能直接认定能力退化或认定唯一判错原因 |
| Yuki彩色摄影 | 两臂核心转变证据均保留，grounded措辞改变后对→错 | 过度概括与判分敏感性未能隔离；答案不同，不能称已证实相同输入翻转 |

持续错误的Q3也出现具体答案缺口：职业交流题的source10 legacy把Leon的融资发言同时归给Josh，grounded没有捕捉Josh自身的职业回避；展览题仍没有给出Luca本人拒绝投稿及作品尚未准备好的理由。改进方向应包括“证据属于谁”和“回答是否针对同一事件的每个人”，而非只增加来源条数。

本组病例未找到可以独立确证的“删除某条声明导致必要信息丢失”例子；这不证明删声明总是无害。完整原文和审阅边界见[病例复核](../../build/socialmem_20260925_r54_work/qa-case-review.md)与[证据JSON](../../build/socialmem_20260925_r54_work/qa-case-review.json)。

## 6. 归因与下一步

本轮检索证据支持恢复v6覆盖顺序与独立来源容量的组合，优于R5.3的v8强词面优先候选；它不证明v9语义召回更强。source10路径没有查询嵌入，但仍使用父库已有声明元数据；不能据此声称完全无需结构化记忆或嵌入能力。

本轮baseline/source10 QA测量“增加来源且去掉声明”的组合效果，不能从差值单因归因于预算或声明干扰。source7/sidecar只做检索消融，尚无它们各自的QA因果效应。门槛通过后下一步应**冻结现有v9候选并扩大开发验证**，与健康v6同核心、同来源库配对；不在扩大验证时夹带新的排序、提示或裁判修改。产品默认仍为bm25，开发对照仍为v6，扩大验证尚未执行。

后续能力迭代按证据优先级分开处理：

1. **成员×事件×阶段覆盖**：用新人物、新领域的正反例区分当前事件态度与另一场活动，要求每个被问成员的立场/理由与同一事件对应；优先攻克Q3仍0/2的问题。
2. **第三方原因和同一状态维度的变化链**：保留说话人与被描述者的区别，针对有明确指代和无关第三方建立对照；early/late/trigger不能仅靠时间和连接词填满。
3. **回答压缩与证据利用**：grounded仍存在512 token截断；改动必须在C++回答政策中单独设计和测试，与来源选择分开消融。不能仅增加token上限后归因于记忆能力提升。
4. **评分稳定性**：相同裁判输入翻转应独立校准和归档；任何裁判配置变化都单列实验，不覆盖本轮主分数。

这些后续改进尚未实现。现有C++修复已完成；下一轮仍遵守中文文档→失败测试→C++实现→固定协议复评，不按本批人名、Q编号或答案常量写规则。

## 7. 可复核证据与交付

- [完整检索封存](../../build/socialmem_20260925_r54_budget_ablation_retry1/seal.json)、[四组比较](../../build/socialmem_20260925_r54_budget_ablation_retry1/comparison.json)。
- [独立重算与哈希审计](../../build/socialmem_20260925_r54_work/retrieval-independent-audit.json)、[父库有效期审计](../../build/socialmem_20260925_r54_work/parent-validity-audit.json)。
- [C++修改验证清单](../../build/socialmem_20260925_r54_work/native_verification.json)、[全量C++日志](../../build/socialmem_20260925_r54_work/cpp-full.log)、[Python回归日志](../../build/socialmem_20260925_r54_work/python-final-green.log)。
- [失败预检封存](../../build/socialmem_20260925_r54_budget_ablation/seal.json)、[失败计数](../../build/socialmem_20260925_r54_budget_ablation/failure-summary.json)。
- [fresh QA封存](../../build/socialmem_20260925_r54_qa_fresh/seal.json)、[QA总览](../../build/socialmem_20260925_r54_qa_fresh/summary.json)、[执行计划与228个提示绑定](../../build/socialmem_20260925_r54_qa_fresh/execution-plan.json)。
- [独立QA审计](../../build/socialmem_20260925_r54_work/qa-independent-audit.json)、[重算脚本](../../build/socialmem_20260925_r54_work/analyze_qa.py)、[来源诊断数据](../../build/socialmem_20260925_r54_work/source-diagnostics.json)。
- [历史上下文内容比较及边界](../../build/socialmem_20260925_r54_work/historical-source-context-audit.json)、[QA依赖封存RED](../../build/socialmem_20260925_r54_work/qa-dependencies-red.log)、[QA编排及相关回归GREEN](../../build/socialmem_20260925_r54_work/qa-dependencies-green.log)。

独立验封检查检索1,080个文件、QA1,075个文件，228条prompt/context绑定全部正确，封存包含实际使用的Python/core依赖及统计helper。QA进程退出码0，输入前后哈希一致。共345份设计、计划和技术文档（含两份技术报告）同步中文当前入口并验链；保留历史正文、原有工作区和全部评测产物，不自动提交或清理。

本地复核命令（均不发送模型请求）：

```sh
.venv/bin/python scripts/run_socialmem_r54_qa.py --validate-only
.venv/bin/python build/socialmem_20260925_r54_work/analyze_qa.py
.venv/bin/python -m pytest tests/python/test_socialmem_r54_qa.py -q
```
