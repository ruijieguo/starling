<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

# SocialMemBench 回答消融实施计划

执行技能：executing-plans、test-driven-development、requesting-code-review、verification-before-completion。用户已授权自主迭代，继续在现有工作区执行，不创建分支、不提交或清理既有修改。

目标：完成99题四组合同期回答层消融，隔离表示处理与指导组合；不晋升候选。
架构：C++新增显式实验提示接口并复用既有提示，Python仅绑定、固定请求编排、核账和统计。
技术：现有C++/pybind、原生OpenAIAdapter、标准库进程池与SQLite账本。
设计：[消融设计](../specs/2026-09-18-socialmem-answer-ablation-design.md)。

全局约束：qwen3.8-27b；99开发自由题、33网络；4组、4进程、1024回答上限、120秒、0重试、792 HTTP上限；原裁判不变；SOURCE/JSON × grounded/synthesis；旧298题不参与请求统计；不得看分调参。

- [x] 保存351份父文档和4份修改前源码；核对父封存；先完成中文文档并同步全部设计。
- [x] 在tests/cpp/test_evidence_answer.cpp添加AnswerAblation用例，声明接口后运行构建得到缺少实现的RED。关键断言：两个对角提示与旧函数相同、JSON旧指导的来源块解码后原文和人物不变、SOURCE新指导包含原文及问题且不声称JSON输入、无效格式和损坏来源抛错。
- [x] 在src/retrieval/evidence_answer.cpp提取单份综合指导生成器，实现 `source_answer_ablation_prompt(question, block, representation, guidance)`；绑定在bind_05_retrieval.cpp。运行Source*/EvidenceAnswer*/SynthesisAnswer*/AnswerAblation*原生测试和真实绑定测试。
- [x] 新建tests/python/test_answer_ablation.py先RED：`select_sample`对输入顺序与correct/answer改变不敏感、每网络3题；`task_order`每题四组且轮换；`paired_effects`对全对/全错四组手算准确率和交互；重复/缺失/非终态/异常真标签应拒绝；零正常子集返回null。
- [x] 新建scripts/run_socialmem_answer_ablation.py：使用既有冻结导入、response_text、BudgetLedger及原judge协议；准备冻结99题来源与四提示，执行前比对两对角历史提示；只在完整核账后计算分数。每组预约2次、开始独占标记、写原始回执、按实际/未知上界结账。拒绝已开始或封存任务再次发送。
- [x] 新建scripts/analyze_socialmem_answer_ablation.py：固定五项配对统计和网络bootstrap；完整集合检查后一次性发布分析，报告技术共同子集、资源和候选方向条件。冻结分析代码，不依赖运行后变动的产品文件。
- [x] 完成有针对性的回归与独立审查，冻结唯一本轮目录build/socialmem_20260918_answer_ablation；运行前所有99×4提示、代码、配置、统计与文档哈希固定；日志只显示技术进度。
- [x] 完成396终态、独立重算、案例分析和全部文档同步；封存及独立复验脚本已就绪。最终完成状态以completion-seal.json、seal-verification.json和build/socialmem_ablation_checks/final-verification.json为准，不以清单代替机器核验。

测试示例（行为契约）：`assert len(select_sample(records)) == 99`；`assert len({t['arm'] for t in task_order(records) if t['item_id']=='a'}) == 4`；四组结果[0,1,1,1]对应表示效应[1,0]、指导效应[1,0]、交互-1。实际用例使用独立手工夹具，不能由被测统计器生成期望值。

原有测试不证明语义正确；本轮诊断结果不能替代完整评测。实施清单以日志、完整回执与最终复验为完成依据。
