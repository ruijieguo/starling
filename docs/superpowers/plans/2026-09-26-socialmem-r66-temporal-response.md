# R6.6 单人物变化问题邻接回应实施计划

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> 执行方式：沿用executing-plans和test-driven-development技能，在现有隔离分支按用户自主迭代授权单代理执行。

**目标：** 验证并修复单人物变化题邻接通道关闭的问题，取得可审计的原生消融结果，再依离线门槛决定真实QA。

**架构：** C++新增版本化v10策略；Python保持binding与评测编排职责。旧八库、旧核心、旧结果全部保留，新核心独立构建和加载。

**设计：** [中文行为与评测合同](../specs/2026-09-26-socialmem-r66-temporal-response-design.md)。

## 任务1：C++通道反例与实现

文件：tests/cpp/test_source_retriever.cpp、tests/python/test_source_retriever_binding.py、src/retrieval/source_retriever.cpp、include/starling/retrieval/source_retriever.hpp。

- [x] 先添加v10通用正反例，独立构建并保存旧实现拒绝v10的RED。
- [x] 实现单人物时间变化邻接通道、主题排序和诊断字段，保持v9路径及声明合同。
- [x] 运行新旧Source系列C++测试、Python实际binding测试与必要完整原生回归，保存GREEN；测试中验证来源归属、边界、预算与回退。

## 任务2：冻结同库原生消融

文件：新增scripts/run_socialmem_r66_offline.py及tests/python/test_socialmem_r66_offline.py。接口：prepare(origin,out)、run(prepared,out)、check(out)；核心路径及SHA固定在入口中，worker独立进程加载冻结新核心。

- [x] 先写输入拒绝、清单/身份篡改、只读八库、v9等价和原生重放测试并记录RED。
- [x] 实现新核心运行时快照、计划、每题数据库副本、v9/v10上下文与零请求证明。调用既有原生校验，禁止在Python重写来源选择。
- [x] prepare→run→独立check；对完整133题报告变化量及公开锚点得失，核验194/263控制与固定数据库指纹。

## 任务3：条件QA与结论

- [x] 仅离线门槛通过时，先新增QA编排测试，再实现并验证v9/v10两臂1024配置、提示词绑定、完整分母、账本、篡改与中断合同。
- [x] 准入通过则运行已授权266新答案、最多478 HTTP并独立检查；未通过则记录零新模型请求及阻断原因，封存负结果。
- [x] 写中文评测诊断报告，同步全部设计文档，核验封存清单、源码/测试哈希及报告链接，不自动晋升产品默认。

## 执行结果

任务1—3已完成：1376项原生回归、16项binding/来源回执、12项离线工具、15项QA工具测试通过；同库消融38题上下文变化，锚点194→195/263，独立重放一致。同期真实QA v9/v10为54→52/133，主区间[-6.47, 3.74]个百分点，未达到扩展开发门槛；478次HTTP、3次裁判超时、零重试，原始结果已封存，不晋升默认。详细结论见[中文报告](../../eval/2026-09-26-socialmem-r66-temporal-response.md)。
