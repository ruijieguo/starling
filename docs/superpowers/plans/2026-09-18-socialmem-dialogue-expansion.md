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

# SocialMemBench 连续对话扩展实施计划

执行技能：executing-plans、test-driven-development、requesting-code-review及verification-before-completion。依据[中文设计](../specs/2026-09-18-socialmem-dialogue-expansion-design.md)，在现有已授权工作区继续；不提交/清理既有修改，以独立build目录隔离实验。

目标：在C++保留旧检索种子、补齐同会话连续话轮，并完成固定733题真实对照。新字段source_seed_k/source_seed_max_context_bytes/source_dialogue_radius；Python仅绑定和透传。唯一评测参数30/8000/2→总60/16000，grounded_v1/1024，1314请求上限。全部全局约束以设计为准。

- [x] 验证上一轮3924封存文件，快照345旧文档及6份待改源码；先写中文设计、计划及报告入口。
- [x] 在tests/cpp/test_source_retriever.cpp写SourceDialogue失败用例。代表场景：Alice在turn=10给出种子，Bob在9质疑、Carol在11确认，8和12为二层；seed_k=1、radius=2、k=5时返回8..12；删除9后不能沿此方向加入8。运行`.venv/bin/cmake --build build --target starling_tests -j 4`，保存缺失字段/行为RED。
- [x] 在source_retriever.hpp/.cpp实现新字段、策略校验和先种子后邻接选择；半径0保留原种子，旧策略路径不变。执行`build/tests/cpp/starling_tests --gtest_filter='Source*:EvidenceAnswer*'`确认原生回归。
- [x] 先写tests/python/test_dialogue_expansion.py，加载build核心并通过recall_observer_block验证实际第三方话轮；再在bind_05_retrieval.cpp暴露字段、eval_ladder_pipeline.py和run_socialmem_baseline.py透传。构建_core，运行新用例及baseline隔离回归，保存RED/GREEN。
- [x] 先写test_dialogue_expansion_guard.py和test_analyze_socialmem_dialogue_expansion.py：严格配置白名单、完整题集、父种子逐项保留及预算、分析依赖完整、失败时不发布报告、封存后只读、五项门槛边界。补充整目录发布失败与完整结果只读用例，禁止逐文件混合发布。再实现scripts/run_socialmem_dialogue_expansion.py和scripts/analyze_socialmem_dialogue_expansion.py，复用已有预算/统计基础；分开代码父和成绩父。
- [x] 新核心离线复现733父上下文/引用/提示，预检新来源且父种子不丢失；冻结348文档和执行/分析依赖。独立审查无阻断后启动唯一真实候选，监控只看技术状态，等733终态和进程退出。
- [x] 冻结分析、固定案例和独立核账后同步348份中文文档、封存及独立复验。主验收净增>=37、区间下界>0、自由题净增、截断<=15、tokens<=6,370,710；如实保留未达标结论。

产物：build/socialmem_20260918_dialogue_expansion/；日志和前态快照：build/socialmem_dialogue_checks/。代码修改从最小失败用例开始，旧归档和原评分不改。封存必须递归收录旧文档及before快照，未知请求按保守上界处理，不能只收顶层日志。

终态结果：376/733、净增31、+4.23个百分点；原门槛未全过，未晋升。31项Python新测试含整目录发布失败注入；封存辅助10项含已知零请求/未知上界和嵌套快照。统计由独立标准库脚本重算，未导入冻结统计函数。封存与最终复验机器回执是完成凭据，不以清单勾选代替验证。
