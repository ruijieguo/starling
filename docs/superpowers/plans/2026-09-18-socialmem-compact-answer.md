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

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

# 紧凑证据回答实施计划

目标：减少固定512-token预算下的回答截断，并检验对开发准确率的影响。

架构：C++新增纯提示函数复用grounded_v1；Python仅绑定、配置路由和冻结编排。设计见[原生接口与固定实验](../specs/2026-09-18-socialmem-compact-answer-design.md)。按持续授权在当前工作区顺序执行，保护既有修改，不提交或切换分支。

## 顺序任务

- [x] 验证父实验3512文件及336文档，复制父文档快照，写设计与中文状态入口。
- [x] 添加`tests/python/test_compact_answer.py`、`test_compact_answer_guard.py`和原生`SourceCompactAnswer`失败测试。使用实际binding、路由spy和配置漂移检查，保留红测日志。
- [x] 在`source_retriever.hpp/.cpp`实现`compact_source_answer_prompt(question, source_block)`，在`bind_05_retrieval.cpp`导出，运行器新增显式策略。原grounded_v1全文保留作为前缀，输出要求只附加。
- [x] 构建starling_tests/_core，同步实际import核心；运行原生来源测试、新旧Python提示与守卫、运行器回归，确认默认行为。
- [x] 新增`run_socialmem_compact_answer.py`并冻结新核心、源码与编排；原生预检733来源和152选择题提示、733旧grounded_v1提示；独立审查后运行check。
- [x] 在已授权DashScope执行733题真实run，最多1314 HTTP、零重试，等待完整终态，不按中途得分调参。
- [x] 复用配对统计并执行本轮预注册门槛；分析失败、长度遵从、tokens、题型和固定样本。核对逐题attempts/ledger、上下文/prompt、配对统计，再同步全部中文文档与封存。

验证命令：`.venv/bin/cmake --build build --target starling_tests _core -j 4`；新binding与冻结运行器测试使用不同pytest进程。真实评测只运行新目录的冻结run.py。不得将新开发得分与旧保留集拼接成全量分数。

关键断言：

```python
assert core.compact_source_answer_prompt(question, block).startswith(core.grounded_source_answer_prompt(question, block))
assert compact_prompt.count(block) == 1
assert new_mc_prompt == parent_mc_prompt
```

## 完成记录

733/733终态，248正确、731正常、2裁判超时；1314次HTTP、零重试，无抽取或embedding。45项C++、72项Python、22项本机HTTP测试通过；独立审查验证全部配对统计、733逐题账本、39库、父与候选摘要。新增回答政策与分析均已冻结，不改评分。

未通过开发晋升，保留grounded_v1的332/733＝45.29%为当前最佳；紧凑候选33.83%、0截断、观测tokens下降2.29%。已分析父74失败恢复只贡献4题，以及原正常659题净减88；完成9例固定机制复核。所有339文档同步中文结论并随本轮封存，历史归档不改写。下一轮方向见[结果报告](../../eval/2026-09-18-socialmem-compact-answer.md)，本计划不扩展为自动词数搜索。
