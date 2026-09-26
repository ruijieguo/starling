# R6.4 来源容量评测实施计划

<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

设计：[来源容量单变量设计](../specs/2026-09-26-socialmem-r64-source-capacity-design.md)。复用当前分支及原生核心，按已有自主迭代授权单代理执行，不提交或清理历史文件。

- [x] 固定k10控制、k20上下文、133题、模型/评分与费用上界，先保存中文设计。
- [x] 创建`tests/python/test_socialmem_r64_evaluate.py`，以`driver()`断言新入口存在开始，记录RED；加入输入、任务、localhost原生HTTP、失败和篡改行为测试。
- [x] 新增`scripts/run_socialmem_r64_evaluate.py`的`prepare(control, contexts, out)`、`qa(prepared, out, workers=4)`、`check(out)`，只编排现有C++和审计函数；记录GREEN。
- [x] 运行`.venv/bin/python -m pytest tests/python/test_socialmem_r64_evaluate.py -q`，保存日志与核心/程序SHA；检查fixture及真实prepare均为零外部请求。
- [x] 执行prepare，独立check后再执行266个候选答案；真实新请求上界478，禁止自动重试或覆盖输出。
- [x] 独立check原始HTTP、账本、上下文和配对统计；保存真实报告，区分历史控制消费和本轮新增消费。
- [x] 同步全部中文设计状态，保留原分数、失败封存和数据，汇报收益、可靠性与后续能力改进。

预定命令：

```sh
.venv/bin/python scripts/run_socialmem_r64_evaluate.py prepare --out build/socialmem_20260926_r64_expanded/prepare-v2
.venv/bin/python scripts/run_socialmem_r64_evaluate.py check --input build/socialmem_20260926_r64_expanded/prepare-v2
.venv/bin/python scripts/run_socialmem_r64_evaluate.py qa --input build/socialmem_20260926_r64_expanded/prepare-v2 --out build/socialmem_20260926_r64_expanded/qa --workers 4
.venv/bin/python scripts/run_socialmem_r64_evaluate.py check --input build/socialmem_20260926_r64_expanded/qa
```
