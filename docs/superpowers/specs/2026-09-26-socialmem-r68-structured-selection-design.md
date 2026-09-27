<!-- regression-boundary-20260927:start -->
> **回归验收边界（2026-09-27）**：日常回归与固定历史评测回放分开执行；默认跳过项须显式报告，历史封存、SHA 和失败断言保持有效。部分无有效提升产物已退役，旧文中的回放链接不保证仍可用。当前执行规则见[测试说明](../../../tests/README.md)和[中文设计](2026-09-27-python-regression-boundary-design.md)；这不产生新的准确率结论，产品核心仍由 C++ 实现。
<!-- regression-boundary-20260927:end -->

# R6.8：显式结构化来源选择合同

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

## 依据与范围

已先完成本机清理：删除4041个未封存编译中间文件，目录占用减少612.48 MiB，175908个保留文件及207个身份/封存清单核验一致。R6.7正式产物完整保留并重验通过。

R6.7同期v9→selector正确50→56/133，增益4.51个百分点，网络95%区间[-4.58,17.17]，正常130→125；未晋升。三个来源计划带围栏、两个超过20条，其中一道重叠，合计四次选择合同失败。根因之一为选择器使用generate，而OpenAIAdapter::generate固定调用complete(prompt,false)，配置json_object_output没有生效。

本轮仅修复真实调用合同，不改来源选择提示词、池排序、20条/8000字节预算或回答政策。已按中文设计、失败用例、C++实现、冻结评测顺序完成；R6.8真实选择和同期QA已封存。来源选择133/133次带结构化合同，3题因超过20条预算失败；同期v9为52/133、selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常率低于v9，门槛未通过。完整逐题诊断见[中文评测报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。

## 方案与接口

选择复用已有LLMAdapter::extract_with_contract与OpenAIAdapter结构化HTTP路径，新增OutputContractKind::SourceSelectionV1及原生select_sources_structured(question,pool,llm,k=20,max_context_bytes=8000)。旧select_sources保持R6.7自由生成行为，以支持历史回放与明确控制。两条入口复用同一个内部执行器，来源验证、预算及渲染不得复制到Python或另一套C++实现。

另外两种方案不采用：全局改变generate会影响普通问答的输出行为；Python剥除围栏只掩盖实际请求配置缺陷，且破坏原生核心单一实现原则。

新入口发送StructuredOutputRequest{SourceSelectionV1,JsonObject}，输入哈希绑定完整提示词。实际HTTP体必须含response_format.type=json_object，单次调用无隐式能力探测或退回自由生成；评测max_retries=0。响应带output_mode、output_contract、schema_sha256，完整raw_completion及HTTP回执保留。运行时必须核对响应合同身份，拒绝模式、schema或raw字段漂移。空池/非法池保持零调用；不支持结构化合同的适配器明确失败。

SourceSelectionV1的静态schema为唯一必需顶层键source_ids，值为最多20项的正整数去重数组，禁止额外字段。C++泛型schema验证补齐maxItems检查。池内编号存在性、动态k和整行UTF-8字节预算仍由apply_source_selection负责；静态schema和JSON mode不承诺语义正确，也不能防止模型提出24个编号。围栏、超量、未知编号、重复或类型错误仍直接失败，不补选、不截断、不回退。

已有显式能力探测API支持新合同的空列表夹具及反格式夹具，其证据必须能独立重放；本轮真实选择不自动执行这些探测。普通generate与已有claim合同行为保持回归覆盖。

## 测试与实测合同

先新增C++反例：显式合同及提示词哈希、原始响应保留、未知/错合同拒绝、无结构化支持拒绝而不调用legacy、空池零调用、超量与字节边界、SourceSelectionV1静态schema和maxItems。新增Python薄绑定/localhost测试，通过真实C++OpenAIAdapter捕获请求体，断言response_format，测试供应商不支持、围栏、截断、拒绝及用量缺失，验证不重试；同时确认普通generate仍是自由输出。

冻结同八库、六网络、133题；R6.8 selection-prepare seal为`24ae3280d34cd27edc7dc5f9e50d4726a27a987a23385ea2bb6ed9c4f14abb02`，选择seal为`0cb3d9ed55d7dd3ee16e5972dca5fa1d1edd07c7ca23beafd7509f86b2efc1ac`，QA seal为`9dcc08c22487b3d0d8b4081f1fa14746ff5ea5df212862df8c49f1a66612e89a`。新核心独立构建；回答/HTTP审计仍在独立进程用R6.2核心949484630a9c83d93fb0582c9b37ff6a228e3f39bc80fe020b1384441e0c9bfb。Python仅编排、冻结、核验和统计。历史程序和数据库只读。

来源选择最多133次HTTP，qwen3.8-27b、512输出、thinking=false、120秒、零重试、并发4。QA准入为完整可验封133终态、正常≥127、锚点≥194/263、v9历史来源控制零差异、候选上下文确有改变。条件QA两臂v9/structured selector均fresh，回答1024且thinking=false，裁判64且provider默认thinking；最多478次HTTP，总上界611。选择失败候选直接计错，零回答/裁判调用；所有失败保留在133分母，不重判或补答。

主要结果仍为同期候选减v9；R6.7仅作历史参照，不能把跨轮差异归因于JSON开关。R6.8逐题比较两轮选择提示词/来源池哈希与合同失败数：输入133/133相同，Markdown围栏由3题降为0题，剩余3题均为超20条预算。费用包括完整池选择；QA有6次缺usage，未知总tokens保留null。门槛仍为增益≥5个百分点、六网络聚类bootstrap 95%下界>0、共同正常净增>0、双方正常≥95%且候选不下降，不自动晋升；本轮门槛未通过，后续先修复预算规划和启动幂等再复评。

## 文档同步与后续

全部设计/技术文档已同步中文最终状态，主设计保留显式结构化入口和失败合同；最终报告分别列出工程修复、协议健康、QA收益、成本和并发启动事件。群体反例、事件角色及回答遗漏留待可区分消融，本轮未同时改动这些策略，也未改变裁判规则。

## 收尾架构复审修复（2026-09-27）

收尾代码审查发现归因阶梯的旧 S_star 分支曾在 Python 中枚举 `holder_id`、逐 holder 调用
`RetrievalPlanner`，并在 Python 排序合并候选。这违反语言绑定只做透传的边界，也可能使评测路径与生产
`ObserverRetriever` 的融合实现漂移。现已在 C++ 增加 `observer_holders` 原生租户范围查询；S_star 与
S_star_oracle 仅将原生返回的 holder allowlist 传给 C++ `ObserverRetriever(mode=statements)`，候选融合、去重、
预算和渲染全部由 C++ 完成。Python 保留评测阶段的台阶编排与结果解析，不再执行检索 SQL 或候选排序。
守门测试固定检查该分支使用原生接口且不重新出现 holder SQL/候选排序。

评测编排层先将查询时间规范化为 UTC，再由 ObserverRetriever 在 C++ 中校验并在原生结果回传 `as_of_iso`，使 real-mode 诊断能够证明
查询时点已按 UTC 规范化并传入 C++。当前收尾构建的 C++ 全量回归为 1395 项（1372 项通过、
23 项跳过、0 项失败）。R6.8 封存结果继续绑定评测当时的 Python 源码哈希；本次收尾改写
`eval_ladder_pipeline.py` 后，旧封存程序对当前工作树报告源码漂移并拒绝复用，这是封存边界
的预期行为，不能通过重写 seal 或历史结果消除差异。
