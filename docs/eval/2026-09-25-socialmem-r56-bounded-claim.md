# SocialMemBench R5.6：分批抽取与扩大评测恢复

日期：2026-09-25。当前阶段：中文设计→失败测试→C++实现→独立合同/质量审查及最终回归已完成；Kwame同输入真实验收通过。统一新核心的8库重建在第1个scope因模型协议失败停止，失败终态通过独立进程check；尚无新增133题的检索或QA准确率。

## 当前已证实的结果

| 范围 | 结果 | 可得结论 |
|---|---|---|
| R5.4旧开发57题 | legacy 18/57→23/57；grounded 18/57→25/57 | 来源扩展且移除声明的组合方案在旧开发范围有增益，不能归因单因素或称保留集分数 |
| R5.5新增开发133题建库 | 1/8 scope健康；第2个因Kwame的8192-token响应截断停止 | 输出容量是已观测的可靠性瓶颈；没有完整baseline、检索或QA结果 |
| 同输入16384单次预检 | 1次本地HTTP尝试，curl56/HTTP0，无正文，74938ms | 容量充分性未知；远端执行和用量未知，无自动重试 |
| R5.6同输入8192分批验收 | 5批完成、15条声明实际入库，10次HTTP，219586 tokens，无截断 | 此固定输入的抽取/提交可靠性通过；不代表全量可靠性、完整语义召回或QA提分 |
| R5.6统一8库重建 | 第1个scope为partial，Mum格式纠错后仍引用批外c8；后7库未执行 | 传输和输出容量正常，生成合同遵从仍不足；0个scope达到完整门槛，检索/QA未执行 |

R5.5首轮51次chat和24次native嵌入计数合计75个观测请求；548805已观测chat tokens，不含缺失embedding usage。容量预检另计1次HTTP尝试，用量未知。不能把账本141保守单位或missing usage=0当作实际API消费。

## 改进设计

[C++分批设计](../superpowers/specs/2026-09-25-socialmem-r56-bounded-claim-design.md)与[实施计划](../superpowers/plans/2026-09-25-socialmem-r56-bounded-claim.md)规定：仅对semantic claim开启目标单元分批，默认0保留旧行为，实验8。每批仍读取全部原文，只负责指定全局clause；每条证据继续使用原payload/span/SourceTurn，不切割或重编号来源。

分批规划、目标校验、协议重试、解析、准入审核、完成性判定和原子写入全在C++。Python只承担配置映射、编排、预算和证据归档。全部批次完成才能写入该holder的分批claim；失败保留所有已执行回执，未到达批次零请求。general_fact和episodic沿现有独立通道语义，不把claim原子性夸大为三通道全部成功。

该方案减少单次负责来源数量，但不能保证生成token或网络耗时上限；完整上下文重复输入会增加token成本。请求预算由原生planner计算，当前每批最多2次抽取及1次admission，不再沿用旧9/holder常量。Kwame为5批、belief最多15请求。

## 验证边界与后续

首轮真实验收按[同输入预检设计](../superpowers/specs/2026-09-25-socialmem-r56-kwame-probe-design.md)只运行Kwame的belief及admission，在新库验证prepare→extract→commit，最多15次HTTP尝试，无embedding、retrieval或QA。通过仅证明此输入可靠性与写入边界，不证明语义全召回或评测提分。

随后才以统一新核心/配置重建全部8库，按固定133题运行双臂266检索及532fresh QA，并保持R5.5预注册主要终点。旧57题与新增133题分开，298题保留集不进入本轮。尚未执行的阶段不得写成已完成。

## 已完成的实现与最终回归

核心冻结SHA-256为`4c5a7c39ae708a13d10065a0816a5c97a994929479cb0898f504c21e12b422f9`。先有10项原生RED；后续测试又复现后批语义拒收漏报、原始技术失败被持久化类别覆盖。最终质量审查用独立C++驱动复现可见范围/有效时间等中间字段变更绕过校验，以及坏来源分类回归。新增16项检查有14项RED、2项控制通过，随后改为完整ExtractedStatement结构比较，并由原生planner重放确认规划前的来源错误；原驱动独立GREEN关闭两项问题。

最终全量CTest共1343项，1320通过、23因沙箱限制跳过；相关30项HTTP回环测试在允许本机监听的环境全部通过。相关Python及probe合计135/135通过；包括真实冻结新核心与FakeLLM的5批完整执行、后半段c24声明入库、后批失败0claim以及稳定SQLite快照。FakeLLM无真实HTTP/usage，因此入口正确保留technical_failure，未冒充真实模型验收通过。

证据：[CTest](../../build/socialmem_20260925_r55_work/r56-final-ctest.log)、[HTTP](../../build/socialmem_20260925_r55_work/r56-final-http.log)、[Python](../../build/socialmem_20260925_r55_work/r56-final-python.log)、[独立修前](../../build/socialmem_20260925_r55_work/r56-quality-repro.log)、[独立修后](../../build/socialmem_20260925_r55_work/r56-quality-repro-green.log)。

## 已冻结的同输入验收

prepare seal `61c54858f86b79e04f2d88103828621ac40ab3ebae213f1a498423a900b067a9`，独立check通过、prepare/check外部请求0。新核心未分批prompt逐字保持旧输入，原生计划33单元/5批/15请求上界；构建、安装、最终测试日志与Python batching测试已随源码/配置归档。真实run已终态并通过正式离线check，只运行belief及admission和原生提交；未触发8库建库、检索或QA。

零API的全cohort原生规划也已完成：65 holders、1322来源单元、197批，belief上界591，三通道上界851；每holder1至7批。该数由同一新C++planner生成，仅是抽取调用上界，不含embedding或QA，不是实际消费。见[原生规划清单](../../build/socialmem_20260925_r55_work/r56-cohort-native-plan.json)。

## 真实分批验收结果与诊断

终态为`kwame_probe_passed`，run seal为`30f33e4437f09eaf7b080b7bd630c11afb4f2e10b0767e6e083d95f170f716a7`。原始输入12133字节及33个来源单元保持不变；6次抽取、4次admission合计10次HTTP，均响应成功、finish_reason=stop，用量完整，远端执行状态无unknown。原生分批完成、完整性检查及提交通过，封存数据库有1个engram、15条声明、17条extraction_attempt记录；后者是持久化审计记录数，不能当HTTP数。

| 批次（0起） | 来源范围 | HTTP次数 | 抽取输出tokens | 终态wire行 | 确定性拒收 | 准入候选 | 最终入库 |
|---|---|---:|---|---:|---:|---:|---:|
| 0 | c0—c7 | 2 | 3822 | 19 | 15 | 4 | 3 |
| 1 | c8—c15 | 2 | 1421，重试876 | 5 | 5 | 0 | 0 |
| 2 | c16—c23 | 2 | 2911 | 14 | 8 | 6 | 5 |
| 3 | c24—c31 | 2 | 1652 | 8 | 3 | 5 | 5 |
| 4 | c32 | 2 | 433 | 2 | 0 | 2 | 2 |

第1批首次响应出现不允许的`statements[0].evidence.holder`字段，原生按协议拒绝该响应，并在预先允许的一次协议纠错内重新抽取；这不是网络重试。首次无效响应的8行不计入终态48行，却完整计入请求和token成本。重试5行均被确定性语义规则拒绝，因此此批完成但没有声明；合法空结果是技术完成，不能写成语义覆盖完整。

终态48行中，31行被确定性规则拒收，剩余17行进入admission，其中2行因`wrong_relation`被拒绝（c4的promises、c20的forbids），最终15行落库。31与2按不同阶段的行/候选索引统计、彼此互斥，不是按唯一事实去重。确定性拒收原因：QUESTIONED标记缺失16，CONDITIONAL缺失7，显式来源时间缺失3，object丢失时间限定3，NEGATED缺失1，object丢失topic1。原生`semantic_rejected`总计33包含上述两个阶段，不能再与admission重复相加。

15条实存声明关联12个不同来源单元；c16—c32后半段有12条/10个来源，c24—c32尾段7条/6个来源，最末c32有2条。由此可确认本次没有因早期输出截断丢弃全部后半段，但12/33不能解释为语义召回率：来源单元并不等于应抽取事实，且缺少抽取级真值。

独立审计进一步确认终态wire触及28/33个来源单元；c11—c14与c18没有终态输出。c11—c14曾在第1批协议失败的8行响应中出现，纠错后消失。因此协议纠错的内容稳定性也是独立问题，不能只检查JSON最终合法与否。这里只记录候选存在性变化，不把无效首次响应当成正确事实或把33个来源单元当作33条应抽取真值。

这次验收还暴露出下一轮诊断方向：c0先说`I'm so hyped for this!!`，随后同一话轮包含许可问句。模型抽出的`feels: hyped for this`被整话轮QUESTIONED要求拒绝，native scope_resolution为`whole_unit / ambiguous_boundary`。这是一条可复现的“混合话轮影响局部声明范围”线索；其他31条拒收不能据此全部判为误拒。后续应先以原始wire及来源构造局部范围正反例，区分陈述、真实问句、条件与否定，再改C++限定范围解析；不直接取消语义门槛。本轮统一建库和评测保留当前语义规则，避免在对照过程中改协议。

逐条证据、合理拒收控制与后续验收矩阵见[语义能力短板诊断](2026-09-25-socialmem-r56-semantic-gap-diagnosis.md)。当前结果提示范围判断、合同字段一致性及协议纠错覆盖均需改进，不能把全部损失归因于谓词目录不足。

成本为输入208221、输出11365、合计219586 tokens；10个原生响应延迟合计214441ms。完整上下文在各批重复输入，输入占约94.8%，说明分批解决单次输出压力的同时带来显著输入成本。此处没有货币价格换算，也没有用量缺失；旧16384探测的未知用量仍单列。账本15上界实际结算10，reserved=0、剩余5；未使用余量不会自动触发额外请求。

证据：[真实终态](../../build/socialmem_20260925_r56_kwame/run/terminal.json)、[原始回执](../../build/socialmem_20260925_r56_kwame/run/native-receipt.json)、[逐批统计](../../build/socialmem_20260925_r56_work/kwame-diagnostic.json)。

独立审计通过：[审计报告](../../build/socialmem_20260925_r55_work/r56-real-independent-audit.md)核对全部14个run封存文件、10个互异provider响应ID、原始HTTP正文/usage、SQLite逐claim证据与成本。冻结核心+FakeLLM按实际prompt hash离线回放10条原始响应，6次attempt、5个终态以及所有协议错误、语义拒收、范围诊断、准入拒收、retained逐字段相同；新增HTTP为0。审计前后prepare/run封印与frozen.db哈希不变。后续源码前进时，历史结果以此封存源码/runtime及清单追溯，不将历史官方check的live源码漂移当成旧结果被破坏，也不把历史结果冒充新HEAD验证。

## 扩大评测恢复进度

已先写[统一8库重建设计](../superpowers/specs/2026-09-25-socialmem-r56-expanded-rebuild-design.md)及[实施计划](../superpowers/plans/2026-09-25-socialmem-r56-expanded-rebuild.md)，再写失败测试，随后实现新入口prepare/build/check，并补齐baseline helper的claim_batch_size薄映射。当前runtime依据原生planner按851总上界预约抽取。旧R5.5每holder9/合计585不适用，旧健康库不混入新实验。

新增入口测试52/52、binding回归4/4、baseline回归19/19通过；实际新核心+FakeLLM的非空集成完成来源保留、2批抽取/准入、2条提交及生命周期，DB与retained/SourceTurn对照通过，外部请求0。还覆盖失败快照与账本、预算耗尽、缺usage、假终态、重新封印后篡改summary等反例。历史baseline smoke与live core不能混装在同一测试进程，初次混跑正确触发frozen模块拒绝；随后以独立进程验证，3个本机HTTP测试在允许loopback环境通过。未削弱模块身份门禁。

合同审查修复了SourceTurn可选raw_observed_at/time_status字段漏比较的问题；固定1322话轮实际invalid time为0，因此这是配置边界回归，不是本cohort必现故障。最终合同和质量审查均通过，质量审查另用原生2声明/2个Stub向量及真实Kwame的15声明验证成功路径，所有本地复核0API。正式prepare及独立进程check通过，seal为`4aca92fe8eca1615fd7fe65a66d7cf28048f4ac789aa676367acc5ac4bda1577`。后续评测[接入设计](../superpowers/specs/2026-09-25-socialmem-r56-expanded-evaluation-design.md)及[计划](../superpowers/plans/2026-09-25-socialmem-r56-expanded-evaluation.md)已先写，独立入口正在先测试后实现；真实检索/QA受当前失败build门槛阻断。

执行前证据清单：[launch evidence](../../build/socialmem_20260925_r56_work/expanded-launch-evidence.json)；真实运行日志：[build log](../../build/socialmem_20260925_r56_work/expanded-real-build.log)。预算851是整队列保守抽取上界，不是实际消费。

## 扩大重建失败终态

build seal为`6dcbd5a82172728cb2ae84f2b4811e94ced0c3552bd8598e4252130ab1fe762c`。首个scope `ae45ef45d7ff23aade9a9a29`有4个holders、原定8批：Dad、Imogen、Kofi完成分批；Mum第0批首次响应把object/predicate/subject等顶层字段重复放入evidence，原生报`schema_failure`。允许的一次协议纠错中，模型修复了字段层级，但3个输出行中的第3行引用c8，超出本批明确列出的c0—c7，原生报`batch_scope_failure`，Mum剩余批次未执行，分批声明不提交。原始提示末端已含完整target allowlist和禁止重编号/越界的约束，因此不能将问题归因为入口漏传batch size或缺少目标列表。

该scope按既有独立通道语义继续完成本scope的general_fact/episodic及embedding，随后健康门槛拒绝并停止后7个scope。冻结DB有30条statements、30个vectors、4个source documents，均为失败诊断快照，不是健康对照库。原生belief原子性仅约束分批claim，不承诺独立legacy通道一并回滚。

本次实际观测23次chat请求、191907个chat tokens，所有chat usage完整，本地请求数及远端chat执行均已知；另有3次原生embedding计数，其token/原始HTTP明细未由当前binding提供。账本按本scope抽取上界40收费，加实际嵌入3为43，reserved=0、remaining=11957；43不是实际请求数，实际观测请求为26。未消费余量不自动触发重试。

独立进程重算check通过并确认artifact_state=incomplete，见[终态验证](../../build/socialmem_20260925_r56_work/expanded-build-verification.log)与[完整summary](../../build/socialmem_20260925_r56_expanded/build/summary.json)。CLI按incomplete返回1是任务未达成状态，验证函数本身通过，不应把两者混淆。

独立审计已逐条核实原始HTTP、回执与SQLite内容：17条语义claim（Dad7、Imogen4、Kofi6）及13条旧通道声明。Mum失败belief没有语义写入，其2条general_fact来自独立通道。517个build文件、506个prepare文件及409个当前源码文件审计前后不变。见[独立审计报告](../../build/socialmem_20260925_r56_work/expanded-real-audit.md)；本次审计新增API为0。

生成协议可靠性诊断已取得新结果：R5.7在固定qwen3.8-27b下真实调用2个严格准入fixture，均HTTP200/stop；正向却生成根数组，违反根对象schema。原生nonconformant后停止，抽取探测未调用；成本494tokens，独立审计通过。服务端接受请求但没有保证该合同，不能据此断言整个模型不支持strict。详见[R5.7实测报告](2026-09-25-socialmem-r57-strict-capability.md)。

基于实际合同不符合，下一项[R5.8 C++目标单元提示实验](../superpowers/specs/2026-09-26-socialmem-r58-target-units-design.md)已完成：保留完整上下文，只索引当前批可引用来源，默认false保持旧提示用于同核心配对。候选ead804通过1354项CTest、相关Python与独立baseline各19项；配对入口52项和合同/质量审查通过。六任务真实运行B3/3技术通过、A2/3，37HTTP/595505tokens，无未知消费，达到下一轮八库技术门槛；但Kwame B为12条/9来源，A为15条/11来源，不能据此称语义或QA改善。R5.9统一新核心八库设计已先写，尚未重新建库。详见[R5.8诊断报告](2026-09-26-socialmem-r58-target-units.md)。

新增133题准确率仍未产生。8库技术门槛通过后再进行266检索和532 fresh QA，延续既定主要终点及预算，不按锚点得分筛选是否运行QA。

## 独立检索与QA入口验收补记（2026-09-26）

`run_socialmem_r56_evaluate.py`已实现并通过合同及质量审查：固定133题、266检索终态、532 fresh QA终态及1336/956预算；从冻结题目、原生上下文和原始回答重建answer/judge提示，重新封印自报hash不能绕过。真实incomplete build在provider构造前拒绝，本轮实际检索/QA仍为0。

测试先有45项通过，审查又发现阶段初始化、写盘或结算异常后不能只读check的问题。按RED→修复补齐失败审计，完整57项通过；最后“已有execution-plan但尚无终态且账本缺失”反例确认不能误报零消费，最小修正后相关3项通过，未重跑完整58项。失败报告区分有效终态、部分回执、缺失/未开始任务、无效证据与未决预约；账本或开始状态不可知时保留unknown，不生成分数或放行QA。

最终源码、测试及质量结论归档于`build/socialmem_20260925_r56_work/evaluator-reviewed-source/`。完整日志为`evaluate-green-stage-audit-final.log`，最后差量为`evaluate-plan-ledger-green.log`。均为本地技术用例；后续R5.8修改核心时，此结果继续绑定R5.6的`4c5a7c39`，不能宣称验证了后来的HEAD。
