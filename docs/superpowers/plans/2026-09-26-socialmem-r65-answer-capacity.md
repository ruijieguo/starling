# R6.5 回答输出容量实施计划

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> 执行方式：使用executing-plans技能在现有隔离分支逐项执行；沿用用户自主迭代授权，不另行请求批准。

**目标：** 固定k20及主回答策略，对133题实施同期512/1024配对实验并分析可靠性、准确率和成本。

**架构：** 新Python评测入口复用冻结C++提示词、适配器和原始回执审计；两臂配置仅answer_max_tokens不同。不更改已有封存协议，不新增核心语义实现。

**技术：** C++原生核心、Python评测编排、SQLite请求账本、pytest、本机HTTP夹具。

**设计：** [完整中文合同](../specs/2026-09-26-socialmem-r65-answer-capacity-design.md)。

## 全局约束

完整133题、266新答案、HTTP上界478；qwen3.8-27b；grounded_memory_v1；k20/8000字节；固定八库与核心；零重试和零新embedding。先文档再测试最后实现；保留所有失败和原始用量；不修改工作区既有未提交代码。全部设计文档状态同步中文。

## 任务1：输入配对与配置合同

文件：新增scripts/run_socialmem_r65_evaluate.py及tests/python/test_socialmem_r65_evaluate.py。

接口：prepare(origin,out)、check(out)、make_tasks(checked,rows,runner,modules)、arm_config(checked,arm)。输入为R6.4 prepare-v2；输出为封存准备目录及两个容量臂。

- [x] 写RED测试：既有目录拒绝；固定seal篡改拒绝；每题两臂同prompt/context；每臂133题，首臂计数67/66；gold变更不影响回答prompt；两臂配置差异仅answer_max_tokens。
- [x] 运行`.venv/bin/python -m pytest tests/python/test_socialmem_r65_evaluate.py -q`，保存缺失入口的预期失败。
- [x] 实现prepare、依赖归档、固定输入检查和可复算任务次序；保留原始R6.4来源目录，复制133条上下文而不继承历史答案。

## 任务2：同期原生执行与审计

接口：qa(prepared,out,workers=4)、summarize(out,data,partial=False)、make_adapters(data,arm)。复用e.execute_qa持久化原始响应和started，补充每条答案的配置SHA并在独立check校验。

- [x] 写本机HTTP测试：将工厂endpoint指向localhost，实际捕获133个512、133个1024及212个64请求；每对messages相同；模型与thinking合同不变。
- [x] 增加无usage响应反例，完整分母和分臂费用；重封存答案、prompt、配置SHA、started、账本、摘要反例；注入中断并检查incomplete及拒绝重用输出。
- [x] 实现两臂独立原生适配器池、共享分scope账本，逐任务绑定配置；实现配对统计、正常率门槛和原始用量核算。
- [x] 本机测试在允许监听localhost的环境运行，保存GREEN日志；不把夹具分数当真实结果。

## 任务3：真实执行与诊断封存

- [x] 同步全部设计文档状态，冻结源码后执行prepare并在独立进程check；启动前重核验文件SHA。
- [x] 执行`qa --input build/socialmem_20260926_r65_expanded/prepare --out build/socialmem_20260926_r65_expanded/qa --workers 4`，独立check完成后才引用分数。
- [x] 新增docs/eval/2026-09-26-socialmem-r65-answer-capacity.md：完整分母、四格、网络置信区间、截断/超时、分层、案例和费用，明确历史与同期差异。
- [x] 同步全部设计文档最终中文状态，重哈希封存清单并验证报告链接，保存validation-manifest和finalization-check。保留独立分支及未提交结果。
