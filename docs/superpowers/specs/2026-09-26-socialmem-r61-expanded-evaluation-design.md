# SocialMemBench R6.1：统一候选核心的检索与回答评测

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

## 固定问题和执行门禁

继续用户已授权的133题开发baseline。R6.1八库必须先全部健康并通过独立重算：同一candidate core、同一来源/cohort、65 holder、1322来源单元，所有数据库均冻结且无WAL侧文件。3/8历史结果、两holder探测或人工摘要都不能启动本阶段。

固定两个检索臂：baseline使用evidence_profile_v6、hybrid、k=10；source10使用evidence_profile_v9、sources、k=10。固定legacy和grounded_memory_v1两个回答政策。共266条检索上下文、532条fresh答案，继续既有评分合同；回答和judge基础模型为qwen3.8-27b。请求额度保留既有1336 retrieval、956 QA上界，均不是美元金额。embedding仅已有binding计数；没有token明细时保持未知。

## 实现边界

既有 `run_socialmem_r59_evaluate.py` 保留默认R5.9身份和所有校验。仅将seal、identity、failure三个版本标签提取为常量。新 `run_socialmem_r61_evaluate.py` 加载独立共享引擎实例，注入R6.1 builder、固定candidate SHA、专属版本标签和源码清单；不复制千行评分/账本/回答绑定逻辑，不在Python新增语义、检索或回答清理实现。

阶段runtime只使用build的唯一冻结包；C++回答清理binding、原生提示回放、raw HTTP与raw completion对应、来源引用以及judge输入均需保留现有验证。prepare/build和retrieve/QA分阶段封存；任何完整性或上游失败按既有失败统计和费用合同保留，不能修改分母掩盖失败。

## 文档之后的测试

先新增入口/身份RED及错误build在provider前拒绝的用例。复用历史evaluator的通用测试函数，但显式切换新driver与由R6.1实际C++构建的八库localhost fixture；历史R5.9 SHA/profile断言保留，新增R6.1专属正向断言，不能只让旧profile意外挡住所有负例。

测试必须包括：八库数量及core/profile门禁、readonly独立check、266上下文/532答案清单、费用账本整数类型及连接释放、并行provider环境隔离、模型回答和HTTP联合篡改、source/context/judge输入篡改、失败封存和消费未知。完整localhost fixture应实际经过C++检索和回答，再对其原始响应独立重算；不能把fixture结果当真实分数。

## 报告与后续能力改进

首次完成的133题结果称baseline，按检索臂和回答政策报告正确数、题数、技术失败和消费。与旧57题只并列，不计算直接提升百分比。诊断分为来源/抽取保留/检索选择/回答/评分不稳定。下一轮作用域细化等能力改动保持同一分母并以真实新答案重评；只有对齐prompt、上下文和评分后才归因于实现。

本设计是后续实施合同，尚不代表新八库或真实检索/QA已经完成。
