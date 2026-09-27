<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.8：原生分批目标单元提示设计

## 执行条件与证据

本设计承接R5.7兼容性诊断。2026-09-26补记：原生实现、全量回归及合同/质量审查已完成；六任务真实配对完成，B三个任务全部技术通过，满足进入八库重建的门槛。Kwame B实际12条/9来源，A为15条/11来源，不能声称语义或QA改善；详见R5.8中文诊断报告。R5.7两个真实HTTP均为200/stop，但正向fixture在要求根对象的严格schema下生成根数组，原生判定nonconformant；共494tokens后按原计划停止。这不是服务端明确拒绝模式，也不是schema关键字拒绝；它直接表明当前组合不足以作为输出结构的可靠保证。基于此实测，选择本方案作为下一项有界实验。既有用户自主优化授权覆盖文档、测试、实现和开发验收。

R5.6的Mum来源15个单元分两批，首批先生成非法evidence字段，一次纠错后又引用下一批c8；完整提示含c0–c14索引，而末端要求只能引用c0–c7。Kwame首批71940字节中SOURCE_DATA_JSON占42009字节，包含完整原文和全部索引单元；生成指导同时要求检查每个来源单元。本方案检验“完整上下文与可生成目标未明确分离”的假设，不将上述字节统计当作根因已证实。

## 原生合同

在C++ `ValidationPolicy`增加布尔`claim_batch_target_units=false`。只有semantic_claim_contract=true且claim_batch_size>0时可设true；由C++ validate统一检查。默认false时原提示、原schema、原解析与重试行为逐字/逐字段保持；这是同一新核心内配对对照的前提。

true时原生生成新的目标提示：

1. 原生解析完整payload生成相同的来源单元清单，沿用原全局clause_id、speaker、UTF-8来源span与SourceTurn元数据，不切片或重编号payload。
2. 完整原文作为不可引用的上下文呈现，帮助代词、因果和前后状态解释；可输出证据的索引列表只包含当前计划的目标单元。
3. 当前holder、batch_index、target_clause_ids及本批索引同属一个原生生成的数据段。开头说明只检查目标单元的候选，末端再列目标与原格式检查；提示不得同时要求为非目标单元生成声明。
4. 谓词目录、关系边界、字段语义与固定示例沿用当前合同，不增删谓词、不调整范围/时间/实体校验、不改变admission prompt。JSON Object、8192 tokens、thinking=false、一次schema协议纠错和HTTP retry0保持。
5. 协议纠错也重建同一目标提示，并附原生错误摘要，不复制或修补失败响应、不从失败响应捞行。批外引用仍全批失败且不增加重试。

提示组装及目标校验放在`src/extractor/claim_contract.cpp`，由`src/extractor/extractor.cpp`的抽取与完整性重放调用同一函数，避免第二份规则。可共享原提示的静态合同片段，但必须用字节回归证明false分支完全兼容；不通过字符串替换从成品提示里删除来源。

分批plan与receipt显式记录启用的提示profile（true为`target_units_v1`），纳入原生policy快照及完整性检查。默认false保持旧plan/receipt字段形状；true的结果不能在false policy下提交。改写profile、目标列表、原始payload、prompt或其他快照均在提交前拒绝，保留真实消费审计。

`memory_ops.cpp`切换到独立general_fact通道时同时清零batch size和新开关，防止语义补充通道配置污染旧通道。Python只新增字段及对原生policy的薄映射；不能在binding或评测脚本重新实现来源拆分、目标提示或语义判断。

## 先测试后实现

涉及文件：`include/starling/extractor/{statement_validator,claim_contract}.hpp`，`src/extractor/{statement_validator,claim_contract,extractor}.cpp`，`src/memory/memory_ops.cpp`，`bindings/python/bind_06_extractor.cpp`，`python/starling/extractor/config.py`，`scripts/run_socialmem_baseline.py`。修改前先新增`tests/cpp/test_claim_batch_target_units.cpp`及`tests/python/test_claim_batch_target_units.py`，在CMake测试注册中登记。

RED矩阵必须覆盖：

- 默认false逐字复现R5.6抽取/纠错提示，plan与请求次数保持；非法开关组合在provider前失败。
- 三批非零起始索引只列本批来源；完整原文仍可见，中文UTF-8与SourceTurn元数据逐字段不变；空来源仍一批空目标。
- 首次和纠错均不暴露其他单元的可引用索引；未知或重复目标参数拒绝，不把全局c8重编号为c0。
- 批外响应、非法evidence字段、截断、admission失败、后批失败继续零semantic belief claim提交并记录所有费用；独立general_fact/episodic通道的合法写入按原合同保留和单列核验，不能要求整库零声明。
- true/false policy、profile、plan、prompt及已解析声明篡改在persist前拒绝；合法跨批多声明正常持久化。
- 同一多通道记忆流程general_fact不继承新开关；Python只映射，原生异常透传。

完成针对性C++/Python及必要全量回归、独立合同与质量审查后冻结新core；旧R5.6所有库、输入、回执、核心及结果保持历史身份，不混用新旧核心。

## 真实小规模验收与停止条件

真实运行另用独立编排入口，在同一新core比较false（完整索引）与true（目标索引）。输入固定为已封存Mum 15单元和Kwame 33单元，payload字节、holder、模型、schema、生成容量与批大小一致。Mum每臂2次、Kwame每臂1次，共6个holder终态；最大请求预算54（Mum 4×6，Kwame 2×15），无自动重跑。

固定次序为Mum重复1：false→true；重复2：true→false；Kwame：false→true。对照只允许原生回放确认的终末抽取schema/envelope/batch_scope失败作为观测保留并进入配对候选，要求全部HTTP/usage及次数已知；admission同名协议失败及其他scope/source错误不在继续范围。候选首次技术失败即停止后续计划，报告尚未执行项，不补次数。传输未知、预算超限或身份漂移立即停止全部调用。

候选3个计划终态必须全部完整、HTTP/usage已知、无截断、越界或持久化失败，并各保留至少1条原生admitted claim，才允许设计下一轮8库重建。避免把生成空数组的技术成功当作本次能力恢复。还报告每臂协议纠错次数、候选/拒收/准入/保留数量、来源覆盖和token成本；小样本成功不宣称总体可靠性提高，不将保留条数直接解释为召回率。

下一轮8库及133题QA须用该候选的统一新核心和显式新配置重新冻结。评测继续沿用grounded主要终点、固定分母与网络区间，不因协议fixture通过或候选更多便宣称提分，产品默认保持不推广。
