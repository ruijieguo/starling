<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

# SocialMemBench R4.0 实施计划

采用 executing-plans 在当前工作区逐项执行；不清理已有修改，不提交混合历史工作。方案已获用户确认。

目标：C++ 完成最终预算内的证据覆盖和混合证据回答边界，双臂评测区分召回与回答效果。

设计：[R4.0 中文契约](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。技术：C++20、SQLite、现有 pybind11；不引入新依赖。

## 任务一：原生来源选择

- [x] 在 tests/cpp/test_source_retriever.cpp 新建 SourceProfile 夹具，使用 ObserverQuery.source_strategy=evidence_profile_v2，经真实 SQLite 来源写入/读取验证末期保留、主题排序、互动邻句、权限、时间和整行预算。
- [x] 运行 `cmake --build build -j 4`，随后 `build/tests/cpp/starling_tests --gtest_filter='SourceProfile.*'`，保存缺失策略的 RED。
- [x] 在 src/retrieval/source_retriever.cpp 增加 profile 选择，仅新策略在 statement 候选已知后选择最终来源份额；旧策略保持。计算并核对最终 trace。
- [x] 运行 SourceProfile 与全部 Source* 回归，核对来源引用与 block 对齐。

## 任务二：原生混合证据回答

- [x] tests/python/test_socialmem_r40.py 先验证新增原生函数缺失，保存 RED；新增 C++ 回归覆盖混合行、错误引用、Unicode 和来源保真。
- [x] include/starling/retrieval/evidence_answer.hpp、src/retrieval/evidence_answer.cpp 新增 grounded_memory_answer_packet/prompt，复用已有 SOURCE parser 与 grounded 规则。
- [x] bindings/python/bind_05_retrieval.cpp 只注册函数；scripts/run_socialmem_baseline.py 增加政策路由和模式校验。pytest 验证 MC 旧提示、非法配置及真实 binding 输出。

## 任务三：固定双臂实验

- [x] tests/python/test_socialmem_r40.py 添加预算、完整任务集、重复任务、配置漂移与配对统计 RED。
- [x] 新增 scripts/run_socialmem_r40.py，复用既有 frozen imports、native adapters、账本、评分协议；prepare 冻结代码/父快照，recall 查询一次保存两臂输入，run 执行两臂，analyze 验证账本并配对统计。
- [x] 父 SHA 与 57/7 范围严格检查；600 HTTP 上限，禁止重试和覆盖。只向已授权 DashScope 发送数据。
- [x] 真实结果按所有题计零统计，按网络重采样；记录代码、模型、提示、语料、数据库、账本和 raw response 身份。

## 任务四：验证与交付

- [x] 相关原生/binding/runner 测试通过后运行完整 CTest；git diff --check。
- [x] 执行独立 R4.0 双臂评测，审计 114 终态、来源同一性、44 道自由题/13 选择题各臂分母、实际 HTTP 和冻结身份。
- [x] 编写 docs/eval/2026-09-22-socialmem-r40-evidence-profile.md，列出前后结果、技术失败、覆盖与语义短板，明确 partial 父不能晋升。
- [x] 更新本计划状态与全部中文设计导航，保存同步清单和评测封存清单。所有未通过门槛的候选保持实验状态。

完成记录（2026-09-22）：两臂均 19/57，114 个终态与 544 次实际 HTTP 审计通过。原生回答 3 次截断；未达开发继续门槛，不晋升生产。详见 [评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。
