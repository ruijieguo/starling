<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench 结构化覆盖诊断实施计划

执行方式：在当前已授权工作区按任务执行；承接既有未提交改动，保存本轮修改前快照，不提交或重置其他工作。

目标：得到可信的结构化覆盖诊断，补齐原生拒绝分类并阻止仅来源快照冒充结构化评测。

设计：[结构化覆盖诊断设计](../specs/2026-09-20-socialmem-coverage-diagnosis-design.md)。

全局约束：中文文档先行；测试先于实现；核心逻辑 C++；Python 仅归档、统计与协议编排；零外部请求；旧评测和历史设计快照不改写。

## 任务 1：冻结与中文设计

- [x] 保存修改前源码到 `build/socialmem_20260920_coverage_diagnosis/before`。
- [x] 写入设计与计划，核对 57 题、7 scope、36 个预期 holder。
- [x] 同步现行总设计、契约清单、抽取/检索子系统、结构化闭环设计与评测接线设计。

## 任务 2：先测试再实现原生拒绝统计

文件：`tests/cpp/test_claim_contract.cpp`、`include/starling/extractor/{claim_contract,extractor}.hpp`、`src/extractor/{claim_contract,extractor}.cpp`。

- [x] 通过既有 `Extractor::extract_llm` 构造混合拒绝：原生拒绝 `has→owns`，admission 拒绝 `feels`，保留 `trusts`；断言字面计数 `{owns:1, feels:1}`。
- [x] 构造 admission 先合法拒绝后重复 index 的坏协议；断言没有部分语义拒绝计数。构造 admission 超时并断言 `failure_category == timeout`。
- [x] 运行 `ClaimContract` 新用例保存 RED；再实现规范谓词字段、准入计数及正确错误通道；运行 GREEN。

## 任务 3：先测试再实现 scope 门禁

文件：`tests/python/test_socialmem_structured_eval_guard.py`、`scripts/run_socialmem_structured_eval.py`。

- [x] 用实际临时文件和固定公共历史验证 source_only/缺 holder/重复 holder/失败/无版本回执均拒绝；完整成功零声明可通过。
- [x] 确認 RED 后新增 `_validate_structured_scope(scope_dir, group)` 并接入 `check_arm`；新 scope 不存在可开始，已有不完整产物必须拒绝。

## 任务 4：先测试再实现离线诊断

文件：`tests/python/test_analyze_socialmem_structured_coverage.py`、`scripts/analyze_socialmem_structured_coverage.py`。

- [x] 用真实 SQLite 小库构造 1 条结构化声明、1 条 legacy 声明；2 道题分别召回两者，断言分母与正确率分组。
- [x] 覆盖 source_only、missing scope、重复题目、QA 文件与 summary 漂移和非空 WAL 的拒绝。
- [x] 保存 RED；实现 `analyze_run(run: Path) -> dict`，读取明确 scope，原生字段只做分组和求和，输入哈希前后复核。
- [x] 对冻结 hybrid_dialogue 运行诊断，生成 `analysis.json` 与中文报告；不重新请求模型或评分。

## 任务 5：验证与同步

- [x] 相关 C++ 和 Python 回归，记录核心哈希；完整 C++ 验证按环境单列。
- [x] 核验历史输入哈希不变、文档引用有效与本轮 diff 无空白错误。
- [x] 报告实际证据、历史成绩限制、已修复项和下一轮输入元数据/回执接线优先级。

## 实际收口补充

原生新用例 3 项 RED→GREEN，相关 C++ 77/77；完整沙箱 1207 项为 1184 通过、22 跳过、1 个 loopback 失败，HTTP30 项本地复跑全部通过。Python 新门禁/分析 RED17 项；发现旧安装模块后补 binding RED1 项，显式新模块与当前虚拟环境普通导入均验证 71/71。96 份现行设计/技术入口已同步中文边界，历史目录不改写。冻结57题诊断和部分原生重放均零外部请求；历史输入哈希与本轮差异检查见证据目录最终核验。
