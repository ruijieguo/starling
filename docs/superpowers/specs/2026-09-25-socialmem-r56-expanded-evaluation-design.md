<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.6：扩大开发集的检索与fresh QA接入

日期：2026-09-25。执行前提为[R5.6统一8库重建](2026-09-25-socialmem-r56-expanded-rebuild-design.md)完整健康。沿用R5.5已批准统计合同，不扩样、不改模型或问题提示、不改变判断门槛。文档先于测试和实现。

## 接入方式与职责

新增独立 `scripts/run_socialmem_r56_evaluate.py`，提供retrieve/qa/check；复用现有R5.4逐题检索、回答任务和原生适配器，以及R5.5样本统计/配对分析函数，不复制核心算法，不修改运行中的建库依赖或历史runner的全局常量。它调用R5.6 build的check完成新核心、输入、DB、账本和健康验证；旧R5.5绑定旧核心的check不能用于新结果。

可复用的明确边界为R5.4的query_one/validate_row（显式传入新core hash）/healthy_embedding/build_task/run_task，以及R5.5的retrieval_comparison/compare_scores和仅处理输入rows的统计函数。不能复用R5.4的validate_record_groups/compare_rows/validate_inputs/_frozen_modules：这些函数含旧57题、四臂、anchor gate或旧core限制。新入口自行实现阶段身份及完整验收，不通过修改旧模块常量绕过限制。

进入retrieve前必须8/8完整健康，且133题、65 holders、8 scopes与固定cohort一致。partial、诊断库、失败seal、缺向量、少holder或旧core都拒绝，并且在构造provider适配器之前失败。来源锚点得分无论高低均不作为QA门槛。

## 冻结与生命周期

评测目录独立保存当前评测入口/测试及其实际依赖快照、配置、样本、分组、父seal和原始回执。绑定R5.6完整build seal、8库hash、新核心`4c5a7c39ae708a13d10065a0816a5c97a994929479cb0898f504c21e12b422f9`和build所绑定的prepare runtime。代码与数据身份在阶段前后重验；输出存在立即拒绝，不覆盖、不静默重试。

原生runtime统一从build的prepare冻结目录加载，与builder.check加载路径一致；不得在同一进程再次从另一份同内容.so加载，亦不得放宽editable隔离。逐题检索使用原库副本，原8库查询前后hash完全相同；check读原库时沿用无WAL/SHM且immutable方式。prepare/check类检查零provider请求。

## 检索合同

双臂为baseline=`evidence_profile_v6/hybrid/k10`、source10=`evidence_profile_v9/sources/k10`，上下文上限8000 UTF-8 bytes、min_source_items=7、radius=1；其余冻结参数一致。复用`ablation.query_one`与显式传入新core hash的`validate_row`，不调用旧core常量绑定的总体验证。每臂133条终态，共266，严格核对item/group/holder/DB/core/策略/实际context及receipt身份。

持久预算1336。每题baseline预约对应历史holders数，source10预约0并使用StubEmbeddingAdapter；实际native计数结算，异常上界扣账并保存unknown。所有holder embedding正常、degraded_paths显式空列表、所有266终态健康才允许QA。缺失或失败保留完整失败状态，不删题重算成绩；不自动重跑。

冻结的OpenAIEmbeddingAdapter仅暴露request_count/embed_calls/batch_calls及检索逐holder健康回执，没有原始HTTP正文或usage。因此embedding按原生实际计数结算，并明确`raw_http_available=false`、token用量未知；不能将未知token计为0。正常向量及回执证明逻辑调用成功，逐次HTTP细节与远端attempt证据仍不可用，不把这些概念混为一谈。此边界沿用R5.5，不为补观测修改运行中的C++/binding。下述raw HTTP逐条消费审计主要用于能够提供完整证据的QA answer/judge。

## QA及统计合同

双臂×legacy/grounded_memory_v1×133题=532个fresh终态，预算956。沿用qwen3.8-27b，answer512且thinking=false，judge64且不新设thinking参数，HTTP retry0、120000ms，并发最多4；回答提示和裁判文本由已有原生路径与helpers产生。每个任务绑定item/arm/policy/prompt/context哈希及输入检索回执；每个生成与judge响应保留原始正文、HTTP、usage。不同阶段既有结果不能代替fresh答案。

回答失败、judge失败、无效选项和技术失败均生成终态并按固定分母计零。真实请求数、保守扣账、unknown和缺失usage分列；原生token缺失默认0不得解释为零消费。正常终态比例与终态文件完整率分列。同一实际judge prompt字节和相同配置下的裁判翻转单列。

grounded全133题source10准确率减baseline为主要终点；legacy次要。复用R5.5的100000次network cluster bootstrap、seed20260925、95%CI及题型/网络分解。继续扩大标准为全题净增至少7、CI下界>0、共同正常同向、每臂正常至少127/133。不得因legacy更好换主要终点；不能把新增133题与旧57题相加成fresh190题，更不能称为保留集结果。产品默认不自动推广。

## check与失败测试

check必须重算固定任务集合、逐题策略/输入/上下文/回答提示绑定、账本全部预约与结算、DB/core身份、统计和缺失用量，不仅验证可被重新封印的summary。stage seal与父seal闭环，任何阶段结束后独立进程check不修改封存内容。失败检索/异常必须可审计；QA包含失败题时仍可形成完整实验终态，但不满足健康比例不得宣称成功推广。

回答prompt必须由冻结record+输入recall重新调用build_task/answer_prompt生成，再按字节比较；judge_prompt必须由冻结题目/gold与原始answer调用既有audit._judge_prompt重建。单纯比较自报prompt/hash/binding不足以验收，须拒绝“prompt与hash一同修改后重新seal”。成本从每条raw HTTP响应重算usage、已知小计、缺失及远端unknown，并与ledger逐reservation绑定；旧run_task/summary的默认tokens=0和只在exception写budget_unknown不能替代新消费审计。以上均只在新编排入口处理，不改C++语义或冻结builder依赖。

先失败测试覆盖：旧/partial build在provider前拒绝，重复/缺失item与holder拒绝，策略/core/DB/context篡改，source10零embedding，1336/956固定预算，异常终态计零、拒覆盖、judge/answer hash绑定，修改summary后重新seal仍失败，固定133题统计门槛和低锚点不阻断QA。真实核心+Stub/FakeLLM只证明编排，缺真实HTTP证据不能冒充真实模型成功。运行真实阶段前完成独立合同/质量审查。
