# R6.8 显式结构化来源选择实施计划

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> 执行方式：按executing-plans在当前分支顺序执行；已获自主迭代授权，不新增子代理、不提交。先中文文档、再RED测试、最后实现。

**目标：** 修复来源选择JSON请求未实际生效的边界，并完成同库133题冻结评测。已完成；R6.8结果为v9 52/133、selector 60/133，净增6.02个百分点，门槛未通过，不晋升默认策略。

**架构：** C++新增SourceSelectionV1合同与select_sources_structured入口，复用已有结构化适配器和来源选择执行器。Python只做绑定、编排和核验。

**设计：** [R6.8设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)。

## 全局约束

qwen3.8-27b固定；完整池1000行/131072字节、结果20行/8000字节。选择512、回答1024、裁判64；timeout=120000、retries=0、workers=4。选择133、条件QA478、总611 HTTP上界。保留旧来源选择API、全部原始判定和失败，不自动晋升。

## 任务一：原生合同及真实HTTP边界

修改include/starling/extractor/structured_output.hpp、src/extractor/structured_output.cpp、src/extractor/openai_adapter.cpp、include/starling/retrieval/source_selection.hpp、src/retrieval/source_selection.cpp和两个绑定文件。测试tests/cpp/test_structured_output.cpp、tests/cpp/test_source_retriever.cpp、tests/python/test_source_selection_structured.py。

- [x] 先写RED：原生新入口发送SourceSelectionV1/JsonObject，hash绑定prompt；schema拒绝21条、重复、布尔和额外字段；不支持合同不退回legacy，错合同响应不被接受。

```cpp
auto r=select_sources_structured(q.question,pool(),llm);
EXPECT_EQ(r.response.output_contract,OutputContractKind::SourceSelectionV1);
EXPECT_EQ(r.recall_json,apply_source_selection(q.question,pool(),R"({"source_ids":[1]})"));
```

- [x] 先写localhost请求体失败用例，在旧核心或缺失接口上保存预期RED，再实现共享执行器及薄绑定。

```python
assert request['response_format']=={'type':'json_object'}
assert result.response.output_contract==core.OutputContractKind.SourceSelectionV1
assert len(requests)==1
```

- [x] 独立构建build/socialmem_20260926_r68_work/cmake，运行来源/结构化/HTTP focused测试、完整C++回归及binding测试，保存日志及源文件/核心SHA。

## 任务二：冻结选择与费用审计

先tests/python/test_socialmem_r68_selection.py，后scripts/run_socialmem_r68_selection.py；使用与R6.7同一历史入口。prepare/select/check接口继续拒绝覆盖；新执行显式绑定合同身份和模式，审计检查原始回执，不在Python重新实现选择。

- [x] RED覆盖缺失/漂移合同身份、完整池/控制漂移、预算不足、异常与中断、封存篡改、真实HTTP格式开关；保留历史依赖发现隔离。
- [x] 实现prepare→select→check，冻结新核心及程序；零网络阶段逐题验证v9历史控制、提示词和数据库哈希。
- [x] 通过本地合同后最多133次真实选择，独立重放、账本对账与准入判定；保留3题超预算错误的原始证据，不修分。

## 任务三：条件QA与中文诊断

先tests/python/test_socialmem_r68_evaluate.py，后scripts/run_socialmem_r68_evaluate.py；最终docs/eval/2026-09-26-socialmem-r68-structured-selection.md。

- [x] RED验证选择门槛不通过不能启动QA、合同和任务绑定、失败计错、固定133分母和零重试。
- [x] 按准入结果执行同期QA或封存阻断结论；完成独立核验，统计网络区间、共同正常、题型/网络差异及完整选择成本。
- [x] 对比R6.7的选择输入和失败模式，只把实际相同输入差异列为协议诊断；不把历史分数变化直接归因于修复。
- [x] 全仓设计/技术文档同步中文最终状态，主设计补实质合同说明；重哈希所有阶段、八库及执行字节，保留清理报告和全部旧实验。

收尾回归补充：评测编排层规范化查询时间，ObserverRetriever 在 C++ 中校验并回传 `as_of_iso`，修复 real-mode 诊断无法核对
查询时点的问题。当前 C++ 全量回归为 1395 项（1372 项通过、23 项跳过、0 项失败）。由于收尾
修复改变了封存评测依赖的 `eval_ladder_pipeline.py`，历史封存的源代码漂移校验按设计阻断当前
工作树复用；不重写历史 seal，历史成绩与当前回归证据分开保存。

## R6.8 收尾结果

R6.8 已完成四阶段封存、独立核验和中文报告。结构化请求133/133带 `SourceSelectionV1/JsonObject` 合同，Markdown围栏失败从R6.7的3题降为0题，剩余3题因提议超过20条预算失败。同期QA共266个唯一终态、257个正常终态；selector正常127/133低于v9的130/133。选择和QA合计606次HTTP，已知tokens 3,707,685，QA有6次usage缺失。详见[中文评测报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。

## 收尾架构复审修复（2026-09-27）

代码审查发现归因阶梯 S_star 的 Python 实现重复了 holder 枚举、逐 scope planner 调用和候选融合。
已补充 C++ `observer_holders` 绑定，并让 S_star/S_star_oracle 透传 allowlist 到原生
`ObserverRetriever(mode=statements)`；Python 不再执行 holder SQL、排序或去重。新增守门测试防止该逻辑回流，
完成后重新构建 C++ 与 Python binding 并运行专项回归。
