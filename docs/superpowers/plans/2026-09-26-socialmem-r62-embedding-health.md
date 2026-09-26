# R6.2 最终向量健康实施计划

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

目标：修复重试已恢复却被误判为失败的问题，取得可审计的八库评测输入。

设计：[中文设计](../specs/2026-09-26-socialmem-r62-embedding-health-design.md)。按已授权范围单代理执行；不提交或清理历史工作区。

- [x] 只读核验第二库 189/189 向量及历史费用，保存诊断。
- [x] 在 `tests/cpp/test_embedding_worker.cpp` 和 Python 管线/运行器测试中先加入恢复、耗尽、损坏、租户和只读反例，记录 RED。
- [x] 在 embedding worker C++ 中实现健康快照及文件检查，binding 仅透传；Python 门禁改用 final_health，保留 failed。
- [x] 隔离构建，运行聚焦 C++、Python 测试和必要完整回归，保存命令与输出。
- [x] 测试并实现封存审计程序执行和版本化恢复，核验旧库在新核心下完整原生回放等价。
- [x] 通过恢复 fixture 后执行新阶段；完整八库才运行检索和问答。
- [x] 同步所有设计文档的当前状态块和中文报告，区分历史结果、机制验证与真实分数。
