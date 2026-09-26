# R6.7 原生语义证据选择实施计划

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> 执行方式：使用executing-plans在现有隔离分支顺序执行；不新增子代理。逐项保存RED、GREEN和阶段核验，用户已授权自主执行。

**目标：** 检验完整授权来源池上的模型编号选择能否补回关键事件证据，并提升固定133题准确率。

**架构：** C++负责池完整性、提示词、单次调用、编号验证和整行渲染；Python负责冻结、调度、费用审计及统计。复用v9作控制与原有回答工厂。

**技术：** 现有C++20、nlohmann JSON、pybind11、原生LLMAdapter及评测账本，不增加依赖。

**设计：** [R6.7设计](../specs/2026-09-26-socialmem-r67-source-selection-design.md)。

## 全局约束

中文文档先行；先失败测试再实现；qwen3.8-27b固定；1000行/131072字节来源池，20行/8000字节输出；选择512、回答1024、裁判64；零重试，单请求超时120000ms。选择133、QA478、总611 HTTP上界。原始回执、未知费用及失败完整保留。不得改写旧封存脚本或产物。

## 任务一：来源选择核心

文件：新增include/starling/retrieval/source_selection.hpp、src/retrieval/source_selection.cpp；修改source_retriever.cpp的eligible_sources计数、CMakeLists.txt与bindings/python/bind_05_retrieval.cpp；在tests/cpp/test_source_retriever.cpp追加SourceSelection用例以复用真实SQLite夹具。

接口：collect_selection_pool(observer,q)、source_selection_prompt(question,pool,k,bytes)、apply_source_selection(question,pool,raw,k,bytes)、select_sources(question,pool,llm,k,bytes)；返回类型及错误合同以设计为准。

- [x] 写C++测试并保存预期RED：选取逆序编号仍输出原时序，未授权来源不存在，未知编号与不完整池不能调用LLM。

```cpp
auto pool=collect_selection_pool(observer,q);
auto result=Json::parse(apply_source_selection(q.question,pool,R"({"source_ids":[2,1]})",20,8000));
EXPECT_EQ(result["source_count"],2);
EXPECT_THROW(apply_source_selection(q.question,pool,R"({"source_ids":[999]})",20,8000),std::invalid_argument);
```

- [x] 完成C++模块、薄绑定和构建登记，不修改原回答提示词；格式失败返回原始响应和错误，不回退。
- [x] 运行Source*与完整starling_tests，保留日志；绑定验证同一个原生函数行为，检查v9回归。

## 任务二：可验封来源准备和单次选择

文件：先新增tests/python/test_socialmem_r67_selection.py，再新增scripts/run_socialmem_r67_selection.py。接口prepare(origin,out)、select(prepared,out,workers=4)、check(out)。独立worker只载新核心，历史核验只载旧核心。

- [x] 测试先行覆盖重复输出拒绝、池缺失与历史控制漂移拒绝、提示词哈希绑定、started先写、账本不足零调用、响应截断/缺usage保留、封存后篡改拒绝。

```python
assert plan['selection_http_budget'] == 133
assert plan['max_retries'] == 0
assert summary['control_mismatches'] == 0
assert summary['new_embedding_requests'] == 0
```

- [x] 实现冻结程序、逐题DB副本、原生池与v9查询、完整清单和双核心身份；不把答案或锚点传给选择API。
- [x] 用本机HTTP服务验证选择调用、原始响应和费用闭环；localhost测试在允许本机监听的环境运行。
- [x] 零请求准备并独立验封，通过后最多133次真实选择；按冻结响应C++重放验证来源原文，输出准入结论。

## 任务三：条件QA与分析

文件：先新增tests/python/test_socialmem_r67_evaluate.py，再新增scripts/run_socialmem_r67_evaluate.py；报告docs/eval/2026-09-26-socialmem-r67-source-selection.md。

- [x] 先验证来源阶段失败或验封异常不能启动QA；两臂任务绑定、完整分母、选择失败计错、总预算和配置继承。
- [x] 实现prepare、qa、check，复用原生回答工厂与既有配对统计；原始评分不重判。
- [x] 准入通过后完成最多478次同期QA，独立核验账本/终态/来源/提示词，报告净变化与区间。
- [x] 核对Dan与Marcus前文是否补回，并检查新增来源是否产生新干扰；任何来源收益不得代替QA收益。
- [x] 同步全仓设计与技术文档的中文状态；重哈希产物，计划勾选只反映已完成工作，不自动晋升或提交。

## 完成回执

本计划已完成。真实来源选择133次HTTP，QA469次HTTP，两阶段合计602/611；独立验封通过。133题正确50→56（+4.51个百分点，网络95%区间[-4.58,17.17]），正常130→125，未达到预设扩展开发门槛。13项新C++反例、1389项完整C++回归、12项绑定、14项选择编排、16项QA编排测试通过。所有原始失败保留，未自动晋升或提交。

新增执行中诊断已写入[最终报告](../../eval/2026-09-26-socialmem-r67-source-selection.md)：generate路径未启用JSON模式、超量计划拒绝、群体反例丢失、事件混接及参考答案裁判盲区。本轮严格失败合同不事后修正；后续变更另行先文档、再测试、最后实现。
