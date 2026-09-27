<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.6：统一新核心重建扩大开发集

日期：2026-09-25。沿用用户已批准的自主迭代、DashScope请求和R5.5扩大评测范围。先中文文档、失败测试、实现、独立审查，再真实运行。核心算法仍全部在C++。

## 证据与决策

Kwame固定输入的R5.6真实验收已终态：33来源单元、5批完成，15条声明入库，10次HTTP、219586 tokens、无截断；离线check通过。其语义拒收与admission拒收不能当作全来源召回率。本方案执行已列入R5.6计划的后续步骤，恢复新增133题的完整结构化对照。

选择全部8库以统一新核心和配置重新构建。复用旧健康库会混用抽取协议；重试旧失败库不能形成同配置对照，因此不采用。保留R5.5全部历史产物，恢复阶段使用全新目录，失败不覆盖、不自动重试。

## 当前实现边界

新增独立入口 `scripts/run_socialmem_r56_expanded.py`，先交付prepare/build/check三阶段。复用R5.5纯统计、分组、源数据校验、健康验证、快照归档和账本读取函数；不得调用其绑定旧核心的prepare/check，也不得用替换字符串或修改模块全局常量的方式绕过旧协议。检索和QA保持R5.5合同，在8库健康后接入，尚未实现时命令必须明确不支持。

`scripts/run_socialmem_baseline.py::_build_extraction_config`仅增加claim_batch_size映射，默认0，不实现分批逻辑。新的冻结runtime必须包含这一最新helper，不能继承旧快照中的缺映射脚本。

## 输入与冻结

固定父输入为R5.5封存prepare（seal `66b13d7e22b0794903467d9ea89f21b91379118d43866b4504b49fd9bd0178d0`）；完整验证其文件集合/hash，历史校验不要求旧源码等于当前源码。另要求R5.6 Kwame run成功及其完整封存，固定run seal `30f33e4437f09eaf7b080b7bd630c11afb4f2e10b0767e6e083d95f170f716a7`、其prepare seal `61c54858f86b79e04f2d88103828621ac40ab3ebae213f1a498423a900b067a9`，绑定其core、配置及原始审计证据。父输入仅提供固定corpus/split/old-sample/sample/groups和历史参数，不提供新运行时或旧数据库。

新核心固定 `4c5a7c39ae708a13d10065a0816a5c97a994929479cb0898f504c21e12b422f9`。冻结当前Python runtime、原生.so、baseline和实际所需脚本、C++/include/bindings/migrations/cmake源码、构建缓存、全部新增测试与验证证据。执行前后检查当前依赖/冻结依赖集合及hash、输入配置和加载模块路径；拒绝editable混入。历史probe允许当前源码前进，以其封印及新核心一致性核验，不让本轮新增helper映射破坏历史证据的可读性。

prepare/check必须零provider请求。按原生retain_source_turns保留每holder完整来源，用同一core的claim_extraction_batch_plan生成并重算每holder计划。`preserve_invalid_time=true`沿用固定数据策略，payload/hash/全局clause/span保持原生原样。冻结65 holder计划、1322 source units、197批及每scope预算；不得在Python分割文本或重新实现planner。check重算时只用临时数据库，不修改封存文件。

## 固定配置与预算

沿用R5.5参数，仅改变core和claim_batch_size=8及阶段标识。qwen3.8-27b、抽取8192、thinking=false、json_object、code-fence兼容、协议重试1、HTTP retry0、120000ms；general_fact/episodic不分批。保留holder isolation、retain_sources、sleep生命周期及原始时间参数，embedding模型qwen3.7-text-embedding、1024维、batch10。

每holder抽取上界为原生planner的belief_request_upper_bound加4（general_fact最多3、episodic最多1）。此队列合计belief591、三通道851。保守账本每scope预约其holder计划之和，沿既有helper按上界收费；实际HTTP与usage另从原始回执统计。建库持久预算仍12000，嵌入按已有保守预约和实际native计数结算，不自动加额。不得沿用旧9/holder或585总额。

## 真实执行与技术门槛

先prepare/check独立进程通过，再按固定顺序串行重建8个全新scope。每scope调用冻结baseline的原生导入/抽取/sleep/embedding流程。每个成功或失败scope都保存原始回执、失败类别、账本与稳定数据库快照；禁止把live SQLite主文件直接封存，失败采用SQLite backup。每scope完成后打印进度。整个build失败立即阻止后续scope，不自动续跑。

完整健康除R5.5门槛外，逐holder要求belief的原生claim_batch_plan与预冻结计划相等，claim_batches_complete=true，完整性无错误，实际attempt按批有序且目标身份一致。协议重试与语义拒收可合法存在；不能以semantic_rejection本身判技术失败。被调用的全部三通道响应必须HTTP正常、finish_reason=stop且回执完整，真实usage缺失必须单列，不能当0消费。实际HTTP不得超过本holder原生上界。general_fact/episodic不得带批次计划。

声明、向量、source documents/turns和holder必须与真实数据库一致，零声明、holder不全、缺向量、技术响应失败都不形成完整对照。只以无WAL/SHM且已封存的frozen.db进行immutable读取。成功summary重算851保守抽取费用和实际embedding结算；失败保留费用、unknown、已完成scope与未执行阶段，不输出QA分数。check不得仅信任summary：重算每scope计划、健康、原始回执、usage与账本，并验证完整封印及来源链。

来源检查须用原生计划的完整payload/hash以及SourceTurn元数据，不能只比较speaker/text/turn_id而漏过observed_at/session_id/turn_index漂移；已入库claim来源身份须与相应原生receipt及engram匹配。沿用R5.5事件通道诊断边界：传输正常而episodic.ok=false仍只能记为“空结果或未解析”，不宣称三通道语义解析全部成功，不用Python补parser。若embed_seeded异常发生在预约后，保留原始预约及native已知计数，能够证明结束且在上界内时结算；不能确定执行数时显式上界收费及unknown，进程崩溃遗留reservation不得静默重放。

## 测试与后续评测

失败测试至少覆盖：默认0/显式8映射；原生固定cohort预算851；错配置/错core/错父封印/源码漂移；拒覆盖；prepare零provider；计划或目标篡改/缺批/后批失败；真实新core+FakeLLM经helper产生多批回执；不同scope保守预约；成功/失败稳定快照；usage缺失与技术失败不能冒充成功；重新封印后伪造summary/费用仍被拒绝。沿用旧测试所需legacy默认行为。

8库成功后才执行同库v6 hybrid k10与v9 sources k10的266检索和532 fresh QA；检索预算1336、QA956。grounded全133题为主要终点，净增至少7且network bootstrap 95%CI下界>0、共同正常同向、每臂至少127正常；legacy次要。不得以锚点增益决定是否QA，不使用298题保留集。新增133题与旧57题分开报告。同步所有中文设计入口与两技术报告。
