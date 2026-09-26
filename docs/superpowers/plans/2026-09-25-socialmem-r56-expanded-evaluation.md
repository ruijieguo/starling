<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

# SocialMemBench R5.6扩大检索与QA实施计划

> 执行技能：superpowers:subagent-driven-development。文档→RED→实现→GREEN→合同审查→质量审查→真实运行。不修改运行中建库的已冻结依赖，不自动提交。

目标：在统一新核心的8个健康库上完成266检索和532 fresh QA，并按固定133题分母分析组合方案的提升。

架构：新增独立编排入口，复用原生检索/提示以及既有逐题执行和统计函数；只新增R5.6阶段身份、冻结、账本与check。详细边界见[合同](../specs/2026-09-25-socialmem-r56-expanded-evaluation-design.md)。

## 任务1：可离线验证的评测入口

- [x] 先新增`tests/python/test_socialmem_r56_evaluate.py`，围绕retrieve/qa/check写RED：不健康build在provider构造前失败，拒覆盖，缺/重item，策略与context/DB/core不一致，source10零嵌入，异常计零与账本上界，重新封印假summary，133题主要终点、net_gain=6不达标而net_gain=7还须满足CI与正常率。
- [x] 新增`scripts/run_socialmem_r56_evaluate.py`，显式复用R56 builder的check与冻结runtime；实现独立seal/来源链、retrieve及qa、只读check。具体模型、预算、scope/holder/任务集合不得从CLI任意改写。
- [x] 针对真实新核心的本地Stub/Fake边界补验，不允许在Python实现新检索/提示算法。执行`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/python/test_socialmem_r56_evaluate.py`，所有RED/GREEN写`build/socialmem_20260925_r56_work/`。
- [x] 先合同审查、后质量审查，发现漏洞回到失败测试；审查期间不发真实API。

## 任务2：真实配对评测与诊断

- [ ] builder.check确认8库完整技术健康；如不通过，保留检索/QA零请求状态并诊断实际建库故障，不用部分库得分代替baseline。
- [ ] 在新目录运行retrieve，预算1336、并发最多4，封存266终态；独立check确认全部技术健康且原库hash不变。锚点只输出诊断。
- [ ] 在新目录运行qa，预算956、并发最多4，fresh生成532终态；独立check重算ledger、任务绑定、统计和裁判翻转。
- [ ] 按固定133题全分母报告grounded主要终点、legacy次要、网络与题型分解、共同正常和失败计零、成本及用量未知；与旧57题分开。
- [ ] 更新R56报告、此计划及所有中文设计/技术报告状态入口。真实结果未出之前禁止写成提分已证实。

入口验收补记（2026-09-26）：完整57项通过，最后新增“已有execution-plan但无账本/首条终态”的费用未知反例后相关3项通过；未重复完整58项。合同及质量审查通过，阶段异常保存有效/部分/缺失/无效回执、未决预约与unknown，不生成成绩。最终入口`940bdffb…`及测试`22d9a8cf…`已归档`build/socialmem_20260925_r56_work/evaluator-reviewed-source/`。真实8库健康条件仍未满足，因此任务2的检索与QA不执行；之后R5.8核心前进时该验证属于R5.6冻结核心历史证据。
