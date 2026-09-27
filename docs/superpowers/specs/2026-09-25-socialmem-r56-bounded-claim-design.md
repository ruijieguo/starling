<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.6：C++ 分批声明抽取设计

日期：2026-09-25。状态：设计先行，延续用户对自主优化和DashScope的授权；不提交代码，不自动更改产品默认策略。

## 问题与证据

R5.5固定新增开发133题的建库在Kwame处发生8192-token输出截断。单次16384容量预检又遇curl56传输失败，75秒无响应正文；远端执行与用量未知，不能据此推断16384不足。停止提高额度与自动重试。R5.5尚无检索或QA成绩，R5.4旧57题分数仅保留为开发证据。

目前C++一次抽取整个holder，声明包含充分的归因与来源字段，输出随话轮/声明密度增长。简单截取响应、缩减谓词或丢掉后半来源会损害能力。采用可选的目标来源单元分批：每次只负责有限个来源单元，同时保留完整上下文。

## 唯一核心实现

在原生ValidationPolicy新增claim_batch_size，默认0完全沿用现有路径；允许1至32，仅semantic_claim_contract=true时启用。实验预注册为8。规划、提示生成、目标资格校验、解析、admission、协议重试、结果合并与持久化均由C++负责。Python仅传配置、调用原生接口、预留预算、保存/分析回执；不能拆payload、重编号cN或复制parser。

原生planner对完整payload生成一次source_units，按原顺序分批，输出每批index、target_clause_ids及belief请求上界。保留全局clause_id、原始字节span、source_payload_hash及SourceTurn身份。空source保留一个空目标批，只有空候选可合格。每批prompt仍包括完整source与全量units，在独立协议指令中限制仅目标clause可输出；无需匹配题目、答案或gold锚点。默认0时旧prompt与请求行为保持一致。

每批最多claim_protocol_retry_budget+1次抽取及一次admission；只有envelope/schema协议错误可按现有预算重试。越界引用属于目标范围错误，整批失败且不admit、不静默过滤；在语义过滤前检查全部wire rows，包括本会被语义拒收的行。每批合法空数组或全部语义拒收可成功。传输/截断/admission失败不重试，停止后续批。

输出对象规模仍由来源密度决定；8个单元并不是token或声明数硬上限，单个长单元仍可能失败。该设计降低单次生成体量，但不能保证消除网络故障；完整上下文会增加重复输入token开销。

## 全批完成与写入边界

ExtractionLlmAttempt.attempt保持holder内全局递增，另记batch_index、target_clause_ids；每批本地协议重试状态独立。ExtractionLlmResult记录batch_size与确定性计划。原有平铺attempts保留每次抽取/admission原始回执，不能合成一次虚假模型响应。

仅当计划的每批恰有一个合格terminal且全部来源单元覆盖无遗漏/重复时，才允许该holder的任何分批claim写入。任一批失败，早先合格批保留诊断候选但不落库；原始来源照常保留，非claim通道沿既有独立语义运行。persist必须重新验证policy、计划、全局attempt编号、batch归属、终态与来源证明，防止漏批/篡改/只写首批。既有单事务保障批次中途异常回滚全部声明。

持久化完整性复核须比较原生解析/准入重放后的完整ExtractedStatement结构，不能只比较模型wire字段；object_kind、canonical_object_hash、scope_parties、perceived_by、时间、provenance等实际落库字段也必须一致。采用原生结构比较，避免在不同语言或多个位置维护字段子集。

failure_category不能由第一批成功掩盖后批失败；accepted_by_predicate在未完整时不得报告可提交声明，已提取候选可从逐批回执检查。失败attempt与先前成功attempt的成本都保留，账本总量以真实响应为依据。general_fact派生policy必须显式清零batch_size，episodic不使用本能力。

## 预算与评测

B批belief上界为B×(claim_protocol_retry_budget+2)，当前重试预算1即3B；general_fact最多3请求，episodic最多1请求，完整holder上界3B+4。由C++planner给出belief上界，Python只加既有其它通道边界。不能继续按旧9/holder计账。

先离线测试与C++构建，随后单独冻结新核心和失败Kwame输入做有界真实验收。固定batch_size=8、抽取8192 token、thinking=false、HTTP retry0；超时仍120000ms，不改变answer512/judge64协议。单holder最多19个抽取/审核/其它通道请求（若只测belief则15），不隐式恢复旧失败目录；独立预检不算QA成绩。

通过后另冻结统一新核心/配置的8库全新建库。新增133题双臂v6 hybrid k10、v9 sources k10，同库、同核心、同QA协议；沿R5.5主要终点与技术门槛，不按锚点增益筛选QA。旧57题、新增开发133题、298保留集严格分开。历史旧核心和封存结果不覆盖，当前源码变更后历史验证以冻结证据身份为准，不冒充当前HEAD健康。

## 验收矩阵

先RED后实现：默认0兼容；配置上下界与general_fact隔离；全局cN/UTF-8/SourceTurn跨度不变；批目标穷尽且互斥；完整上下文含跨批代词前件；后批正常及合法空输出；范围越界在语义拒收前失败；每批协议恢复与全局attempt编号；后批传输/截断/admission失败、未到达批零请求；全批成功均落库；任一失败零分批claim落库；持久化时缺批/改policy/改计划拒收；重复运行幂等；逐回执及持久账本成本一致。Python仅验证配置映射和端到端调用原生能力。
