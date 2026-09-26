<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

# SocialMemBench 单次综合回答实施计划

执行技能：executing-plans、test-driven-development、requesting-code-review、verification-before-completion。按已有自主授权在当前工作区执行，不提交或清理历史修改。设计：[单次综合回答](../specs/2026-09-18-socialmem-synthesis-answer-design.md)。

目标：在固定来源下改善范围、时序、关系解释与逐人覆盖，完成一轮733题配对评测。架构：C++复用来源解析器，生成无损JSON证据包和单次综合提示；Python只绑定和路由。全局约束：qwen3.8-27b、synthesis_v1/1024、focused_dialogue/60/16000、733题、1314请求、零重试、39库不变，完整终态前不看分。

- [x] 核验父3927文件和348文档；保存5份修改前源码；固定12例诊断，先写中文设计和报告入口。
- [x] 在tests/cpp/test_evidence_answer.cpp增加SynthesisAnswer用例，再运行`.venv/bin/cmake --build build --target starling_tests -j 4`保存RED。代表断言：解析`synthesis_source_answer_packet("谁改主意？", block)`后，source_id为1和2，speaker保持Lina和Noah，未知observed_at仍null，text保留完整中文且semantic_verified=false；畸形SOURCE和空白问题抛invalid_argument。
- [x] 在include/starling/retrieval/evidence_answer.hpp声明两个新函数；src/retrieval/evidence_answer.cpp复用sources(block)实现packet（schema_version、question、sources、semantic_verified）与prompt。运行`build/tests/cpp/starling_tests --gtest_filter='Source*:EvidenceAnswer*:SynthesisAnswer*'`保存GREEN。
- [x] tests/python/test_synthesis_answer.py先RED：真实build核心与本地库，回答和裁判适配器仅返回固定文本，assert结果包含两阶段且无evidence；选择题提示同原版。再在bind_05_retrieval.cpp暴露两个函数，run_socialmem_baseline.py只新增synthesis_v1校验及自由题原生路由；构建_core，再运行Python新用例和baseline回归。
- [x] 守卫与统计先RED：固定配置/代码集合、完整题集、block/refs/旧提示逐字一致、152选择题提示相同、581新包所有元数据与原文一致、所有分析依赖冻结、禁止sealed重跑、统计发布失败不留下部分结果。然后新增scripts/run_socialmem_synthesis_answer.py与scripts/analyze_socialmem_synthesis_answer.py，复用已测试账本和bootstrap实现，分析用analysis-results整目录一次发布。
- [x] 离线prepare冻结唯一build/socialmem_20260918_synthesis_answer，独立审查预检，确认733来源不变、581包保真、152选择题不变、预算1314后运行唯一候选。监控仅检查技术状态，等待733终态及退出0。
- [x] 运行冻结分析，固定九例与技术失败分解，独立核账所有回执/started/ledger/HTTP/真实提示。同步351文档，封存348旧文档及5before源码，封存后独立重验。五项门槛：净增≥37、网络区间下界>0、自由题净增、截断≤15、tokens≤6,060,610；不得事后放宽。

产物：build/socialmem_synthesis_checks/（诊断、快照、RED/GREEN、核验），build/socialmem_20260918_synthesis_answer/（唯一真实候选）。原始父归档只读。模板测试不证明LLM理解了时间/范围/社会语义；准确率以真实单次开发评测为准。

终态结果：309/733、净增-67、-9.14个百分点；未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。新增统计前动态账本核验与空子集处理，来源/提示/调用次数独立重算；封存与最终复验机器回执是完成凭据，不以清单勾选代替验证。
