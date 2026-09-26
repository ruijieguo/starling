<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

# SocialMemBench 人物与会话覆盖实施计划

执行技能：executing-plans、test-driven-development、requesting-code-review、verification-before-completion。依用户已授权范围在当前工作区执行，不提交、不切分支。

目标：C++增加显式focused_coverage策略，完成同预算99题两组同期对照并分析。
架构：复用过滤与旧种子，人物/会话覆盖使用一半剩余预算，随后邻句扩展；Python仅调用原生接口、冻结编排与统计。
设计：[完整设计](../specs/2026-09-19-socialmem-source-coverage-design.md)。

全局约束：qwen3.8-27b、99开发自由题、4进程、60条/16000字节、seed30/8000字节、radius2、grounded_v1、1024回答、120秒、零重试、396 HTTP上限；原裁判不变。

- [x] 只读原生定位两处漏召回，保存父文档与源码，先完成中文设计并同步全部文档。
- [x] 在tests/cpp/test_source_retriever.cpp增加SourceCoverage独立夹具，先运行得到非法策略RED；用无词项且无邻接本人事实断言新策略补回，同时`old_seed_refs ⊆ candidate_refs`。覆盖多人轮转、会话轮转、整行字节、权限/时间/哈希、无姓名精确回退和trace。
- [x] 在src/retrieval/source_retriever.cpp扩展策略验证及dialogue_sources，保留旧策略逐字行为；覆盖队列使用`map<speaker, session queues>`和双层轮转，take记录新增阶段与预算拒绝。运行Source*原生测试。
- [x] 新建tests/python/test_source_coverage.py，真实绑定子进程检查新策略，并先RED覆盖配对完整集合、非法终态、重复/缺失回执、预算与冻结拒绝。新增scripts/run_socialmem_source_coverage.py及scripts/analyze_socialmem_source_coverage.py；复用已审查的回答执行、原裁判重放、BudgetLedger和bootstrap基础能力，不复制语义业务逻辑。
- [x] 对99题重放旧策略及候选，断言旧block/refs一致、种子保留、来源范围与预算；保存比较与trace，独立审查通过后冻结唯一实验目录build/socialmem_20260919_source_coverage。
- [x] 冻结后完成198终态，日志仅技术进度；核账退出0再分析配对成绩，按事前条件决定是否值得扩大开发验证。不得根据中间分数改参数或重发。
- [x] 完成中文结果及全部设计文档同步；封存和独立复验脚本就绪。完成状态以completion-seal.json、seal-verification.json和final-verification.json为准，不以此清单代替机器回执。

关键统计夹具：两个网络、四道题，旧[1,0,1,0]和新[1,1,0,1]应净增1、新对2、回退1；技术失败即使correct=true也应拒绝，空共同正常子集返回null。期望值由手工给出，不由被测实现生成。
