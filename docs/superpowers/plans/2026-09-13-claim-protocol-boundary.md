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

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# 输出协议与偏好情绪边界实施计划
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。


本轮在当前工作区继续已批准修复，按 [中文设计](../specs/2026-09-13-claim-protocol-boundary-design.md) 顺序执行。核心只在 C++，Python 仅绑定及测试/评测编排。保留冻结标签、默认关闭、不全量、不提交推送。

- [x] 复现上一轮原生偏好误收与大小写时间拒绝，同步中文设计职责。
- [x] 在 `tests/cpp/test_claim_contract.cpp` 添加偏好误收/真情绪、无准入与无存储、可执行原因目录及大写时间示例用例；在 `tests/python/test_claim_evidence_storage.py` 覆盖 Bus/回读共享契约，记录 RED。
- [x] 修改 `src/extractor/claim_contract.cpp`：窄范围偏好对象检测、C++ 单一原因目录及提示映射、键唯一/原文时间/同话轮引用指导；聚焦测试 GREEN。
- [x] 完整构建安装、C++ 与 Python 全套、旧响应重解析差异及离线核验，代码复审后冻结。
- [x] 新目录真实诊断及原生核验，逐项分析并同步所有当前相关中文设计；结果为 `verified / complete_with_errors`，质量门槛未通过，生产默认保持关闭。

验证命令：

```sh
.venv/bin/cmake --build build -j 4
build/tests/cpp/starling_tests --gtest_filter='ClaimContract.*'
.venv/bin/cmake --install build --prefix .venv/lib/python3.14/site-packages
.venv/bin/ctest --test-dir build --output-on-failure -j 4
.venv/bin/python -m pytest tests/python -q
.venv/bin/python scripts/eval_socialmem_claim_contract.py smoke --previous build/socialmem_20260910_supplement_run --out build/socialmem_20260913_protocol_boundary_validated_smoke --source-turns
.venv/bin/python scripts/eval_socialmem_claim_contract.py verify build/socialmem_20260913_protocol_boundary_validated_smoke
.venv/bin/python scripts/eval_socialmem_claim_contract.py run --previous build/socialmem_20260910_supplement_run --out build/socialmem_20260913_protocol_boundary_real --json-object-output --source-turns
.venv/bin/python scripts/eval_socialmem_claim_contract.py verify build/socialmem_20260913_protocol_boundary_real
```

本地 HTTP 测试如因沙箱监听限制跳过，在沙箱外仅补跑这些测试；真实命令日志单独归档。失败不能标记为无错误完成。原始响应重解析只比较相同原文在旧/新解析器下的候选及拒绝，不伪造未发生的准入或回答。

## 声明范围后继方案（2026-09-15）

本计划保留其实施时点和勾选结果。后继[声明范围定位与覆盖诊断方案](../specs/2026-09-15-claim-scope-localization-design.md)已获用户确认并完成 L/R0 本地实现与回归，在 C++ 共享链路处理受限句首声明并提供原始行索引；无新增模型调用，不改变本计划对应历史结果。
