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

# 作用域生成与截止时间对照实施计划
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。


> 在当前会话使用 subagent-driven-development 执行独立工作包，使用 test-driven-development 保留 RED/GREEN。用户已确认本地实施；不提交、不推送。现行工作区继续保留既有改动，实验按冻结源码另建副本。

**目标：** 补足原生生成示例的复合作用域覆盖，并提供身份可核对、次数有上限的独立截止时间诊断入口。

**架构：** C++ 负责提示、协议、来源解析和传输；Python 只配置、调度、归档及统计。S0 使用冻结 A，S1 从 A 仅加入共同 S 提示补丁；T60/T120 使用同一冻结 A。

**技术栈：** 现有 C++、pybind11、GoogleTest、pytest，无新增依赖。

**设计：** [已确认设计](../specs/2026-09-15-scope-generation-and-timeout-design.md)。

## 全局约束

- 先文档、再测试用例、最后实现；全部新增设计说明中文。
- 核心仅 C++；Python 不复制作用域、schema、来源校验、HTTP 或重试规则。
- 保留 schema 与解析行为，结构错误整批拒绝、既有语义按行拒绝。
- 保留默认 60000 ms、deepseek-v3、semantic_claim_contract=false、Legacy 和 temporal_evidence=None。
- 不改冻结 A/B、旧回执、原标签及 104 份历史设计；不运行 1,031 题；不提交/推送。
- 本轮只运行本机/Fake 测试和离线预览；具体真实 S/T 载荷完成后按明确获准范围执行，候选上限 84 次、零重试。

## 任务 1：S 提示及原生覆盖

文件：修改 `tests/cpp/test_claim_contract.cpp`、`src/extractor/claim_contract.cpp`；复用 `tests/cpp/test_structured_output.cpp` 的真实示例 schema 覆盖。

- [x] 从 `REFERENCE_EXAMPLES_JSON` 读取真实提示，新增中英复合案例覆盖测试：QUOTED、NEG、CONDITIONAL/REPORTED/NEGATED 并存；逐个解析并验证 source_units、主体与来源证据。缺少两语种案例先 RED。
- [x] 对案例删除必要标记、重复主标记、改 actor 和 attributed_to；确认结构/语义拒绝粒度。真实 parser 行为测试使用非评测来源，不复制金标。
- [x] C++ `generation_guidance` 明确非空、唯一、主作用域成员和兼容性；`generation_examples()` 保留六例并加两例。
- [x] 构建后运行 ClaimContract、StructuredOutput 聚焦测试，记录提示字节变化；不修改 parser 或 schema。

示例测试的关键行为：
```cpp
auto parsed = parse_claim_response(example.at("response").dump(),
    example.at("source").get<std::string>(), example.at("source_holder").get<std::string>());
EXPECT_TRUE(parsed.errors.empty());
EXPECT_TRUE(parsed.semantic_rejections.empty());
ASSERT_EQ(parsed.statements.size(), 1u);
```

## 任务 2：S/T 薄实验编排

文件：新增 `scripts/eval_socialmem_scope_latency.py`（配置与单臂 worker）、`scripts/run_socialmem_scope_latency.py`（进程隔离、冻结预览与配对调度），新增对应 Python 测试。既有探测 helper 只复用，不改历史报告格式。

接口职责：单臂 worker 从指定 stage 的原生模块构造 config/adapter，输出报告、配置清单和原生回执；supervisor 为每个动作在独立进程调用 worker，统一检查两臂有效期并按冻结配对顺序执行。S 不在一个 Python 进程加载两个核心。

- [x] 先写测试并记录 RED：新入口尚不存在；随后参数传递/身份漂移/次序和预算的行为测试应依次通过。
- [x] 用原生 Config 配置 timeout/model/max_tokens=4096/temperature=0/max_retries=0，保留真实构造值、核心/schema/配置/报告/请求哈希，不存凭证。两 timeout 独立探测；任何 probe 前先只读核对两臂实际模块/配置以及 worker、supervisor、探测 helper 源码身份，漂移时零发送。
- [x] 本机延迟 HTTP 验证短截止失败、长截止成功且各一次；原生回执保存执行确定性、attempt_count、原文、耗时，未知输出/token 为 null。
- [x] S 七个失败目标及七个同轨迹最近字节合法对照；T 按设计 12 来源。交替每条两臂先后顺序。配置漂移、失败能力、报告过期均在抽取前拒绝；完整日程启动后不刷新。
- [x] 各臂最多 8 探测，S 抽取 28/T 抽取 24；每个动作单次，失败不补跑。先生成捕获自本机 HTTP 的完整请求预览及清单，再允许明确的 real 模式。
- [x] 针对行为运行新 Python 测试，报告 RED/GREEN、改动文件及已知限制。

边界测试采用实际本机服务，例如：
```python
assert short_response.ok is False
assert short_receipt["attempt_count"] == 1
assert long_response.ok is True
assert long_receipt["attempt_count"] == 1
```
断言键以既有原生 `structured_metadata_json()` 的实际布局为准，不由 Python 重新判断技术错误。

## 任务 3：全回归及冻结对照

- [x] 完整构建/安装，C++ 全套和 Python 全套；新问题才扩大或重复检查。
- [x] 从冻结 A 复制 S1 的 433 源码及原构建支持，仅应用任务 1 的共同提示 diff；添加聚焦测试并登记支持差异，使用本地依赖构建/安装。
- [x] 使用 `.venv/bin/python -S` 和模块实际路径/hash 断言，重放 A 的 140 条原文；要求入库/证据/失败结果零差异。
- [x] 为 S0/S1/T60/T120 生成本地预览；验证 S 两臂仅提示变化，T 两臂仅 timeout 变化；两臂 HTTP method/path 一致，并用方法/路径漂移反例先验证 RED。保存模块、源码、schema、来源和预览哈希。
- [x] 对实现做任务审查及最终审查，修复影响正确性的发现并执行相关回归。

## 任务 4：中文同步与交付封存

- [x] 69 份现行设计入口同步本地完成/真实未执行；实施报告列清历史 A 结果、本轮工程验证和真实待验证项。
- [x] 核验旧设计封存、A 运行/分析、本地旧封存、历史文档及标签；记录本轮源码差异，验证所有现行链接与 `git diff --check`。
- [x] 封存日志、源码、模块、请求清单、报告与中文文档；最终给出真实 S/T 的具体请求范围和预算，待明确授权后执行。

## 本地执行结果

各项本地工作、任务审查、完整回归、独立 S1 原文重放、原生本机请求预览和归档检查已完成。真实 S/T 未运行；候选 84 次须按具体发送批准执行。日志及限制见[实现报告](../../eval/2026-09-15-socialmem-scope-latency-implementation.md)。

## 后续真实执行记录

用户随后明确授权原候选 S/T，已完成 84 次真实请求、零重试及52条原生重放。原本地步骤保留其时点；新结果见[真实诊断报告](../../eval/2026-09-15-socialmem-scope-latency-real.md)。S1 未达晋升条件，T120 只保留诊断选项；下一轮设计/编码或真实发送不由本次剩余预算自动授权（本次预算已用完）。

## 声明范围后继方案（2026-09-15）

本计划保留其实施时点和勾选结果。后继[声明范围定位与覆盖诊断方案](../specs/2026-09-15-claim-scope-localization-design.md)已获用户确认并完成 L/R0 本地实现与回归，在 C++ 共享链路处理受限句首声明并提供原始行索引；无新增模型调用，不改变本计划对应历史结果。
