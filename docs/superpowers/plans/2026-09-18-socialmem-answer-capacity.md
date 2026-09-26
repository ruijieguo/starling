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

# SocialMemBench回答容量实施计划

按设计规划、测试驱动和逐项验证执行；沿用已授权的自主迭代，不追加确认流程。目标是检验grounded_v1的输出容量，不修改核心语义。技术为父冻结C++/Python binding、Python实验编排与统计。设计见[单变量契约](../specs/2026-09-18-socialmem-answer-capacity-design.md)。

## 固定条件

733开发题、33网络、39范围；qwen3.8-27b、focused_window/k30/8000字节；唯一配置变化answer_max_tokens 512→1024；核心与全部冻结代码逐字相同。最多1314 HTTP、零重试，裁判及失败计零规则不变。新目录`build/socialmem_20260918_answer_capacity_v2/`，不使用保留集。

## 顺序任务

- [x] 核验grounded父3512文件、紧凑父3519文件和339文档，复制到`build/socialmem_capacity_checks/parent-documentation/`，写中文设计与全局状态。
- [x] 在`tests/python/test_answer_capacity_guard.py`先写配置漂移、父代码复制保真、缺题/重复/自由题提示漂移失败用例；在`test_analyze_socialmem_answer_capacity.py`写事前门槛边界用例。
- [x] 运行新测试保存RED，确认失败来自新编排/分析入口缺失；不修改父C++核心。
- [x] 新建`scripts/run_socialmem_answer_capacity.py`，接口`validate_config(parent,candidate)`、`copy_frozen_code(parent,work,identity)`、`validate_code_delta(parent,candidate)`、`verify_preflight_rows(records,parent,rows)`和prepare/check/run。只从父frozen复制，配置只改1024，全部733提示相同；新建统计脚本复用配对算法，只应用本轮门槛。
- [x] 运行守卫/配对统计测试至GREEN；本机HTTP通过实际冻结核心验证角色参数（回答1024、裁判64、抽取4096及thinking隔离）。
- [x] 冻结新目录、分析脚本和测试；预检733原生来源/prompt及39库，独立审查后执行check，保存零提供商请求证据。
- [x] 在授权DashScope执行单候选run，等待733终态；只报告技术进度，不按中途分数调参。
- [x] 分析完整分数、网络区间、分层、失败恢复、token与固定样本；独立核账；同步342中文文档，封存及重验新旧归档。

验证命令：

```sh
.venv/bin/python -m pytest -q tests/python/test_answer_capacity_guard.py tests/python/test_analyze_socialmem_answer_capacity.py
.venv/bin/python scripts/run_socialmem_answer_capacity.py prepare --work build/socialmem_20260918_answer_capacity_v2
.venv/bin/python build/socialmem_20260918_answer_capacity_v2/run.py check --work build/socialmem_20260918_answer_capacity_v2
.venv/bin/python build/socialmem_20260918_answer_capacity_v2/run.py run --work build/socialmem_20260918_answer_capacity_v2
.venv/bin/python scripts/analyze_socialmem_answer_capacity.py --work build/socialmem_20260918_answer_capacity_v2
```

关键接口契约：

```python
candidate = {**parent, 'answer_max_tokens': 1024}
validate_config(parent, candidate)
assert candidate['core_sha256'] == parent['core_sha256']
# 验证器必须拒绝下列情况，而不是静默容忍：
# candidate['judge_max_tokens'] = 1024
# candidate['answer_policy'] = 'grounded_compact_v1'
# 自由题row['prompt']与父不同、重复或缺失item_id
```

晋升五项同时成立：净增≥8题、差值区间下界>0、自由题净增>0、截断≤15、观测tokens≤3,803,932。失败则保留grounded_v1/512，不追加候选搜索。Python仅编排，不加入检索/生成核心逻辑。

## 最终执行记录

真实目录`build/socialmem_20260918_answer_capacity_v2/`已完成733/733，进程退出0。候选345/733、父332/733；网络区间下界为-0.70个百分点，`promoted_on_development=false`。失败20题（回答3、裁判17）全部计零；1311 HTTP、零重试；回答截断3题；观测tokens3,185,355。独立核账已逐项确认所有来源/prompt/refs、39数据库、started/receipt/ledger和请求attempt一致，无封存阻断。

已完成固定样本诊断、容量统计和342份中文文档结果同步；归档身份及文件校验以`build/socialmem_20260918_answer_capacity_v2/seal-verification.json`和`build/socialmem_capacity_checks/final-verification.json`为准。失败门槛不触发更多上限搜索；grounded_v1/512保留为通过门槛的推荐开发配置，1024点估计更高但未晋升。
