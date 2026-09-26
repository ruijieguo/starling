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

# 协议能力与关系覆盖实施计划
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。


> 执行者逐项使用 `superpowers:executing-plans`，在当前会话内执行并检查每个交付阶段。所有测试先记录 RED，再实现 GREEN。详细设计已获用户确认，本地实现与验证已完成；2026-09-14 获授权的真实探测已完成，后续实验因能力门槛未通过停止。

**目标：** 使服务协议能力和请求失败可核验，修复现有未决选择/操作路由的语义边界，再验证跨时段证据选择。

**架构：** C++ 保存唯一请求/schema/能力/重试/关系/时间选择实现。Python 只映射配置、转发接口、记录归档和计算评价统计。三个阶段分别冻结源码与结果，避免同时变更多个未知条件。

**技术栈：** 既有 C++20、libcurl、nlohmann/json、SQLite、pybind11、GoogleTest、pytest；无需增加运行时依赖。

**设计依据：** [协议能力](../specs/2026-09-13-structured-output-capability-design.md)、[关系与时间证据](../specs/2026-09-13-relation-evidence-coverage-design.md)、[全题矩阵](../../eval/2026-09-13-socialmem-coverage-matrix.json)。

## 全局约束

- 详细设计已确认；进入测试和实现，承接当前未提交工作区，不覆盖既有改动。
- 所有新设计说明为中文。核心不得在不同 binding 重复实现，评测脚本不得清洗原始 completion。
- `semantic_claim_contract`、新输出模式和时间视图保持默认关闭；原标签、历史归档与 `docs/design/history/` 不改写。
- 不提交、不推送；全量 1,031 题只在原门槛全部通过后再决定。
- 现有 140 条协议的固定候选/回答/裁判分母不变；新增独立控制和能力探测另计。

## 阶段 0：设计与证据冻结

- [x] 核对 10 条真实技术失败的阶段及原文，定位 P1 额外 4 条操作性路由声明。
- [x] 完成 1,031 题结构矩阵，分别标出题型假设、两题来源复核、4 组跨网络重复 QA ID 和 3 处锚点元数据差异。
- [x] 完成两份中文设计和本实施计划；对当前设计及技术报告逐份登记职责。
- [x] 文档链接、全题组合身份/来源哈希和失败原文索引核验通过；源码、测试、历史快照和旧原生模块保持一致。
- [x] 用户已确认详细设计，进入以下测试步骤。

## 阶段 A1：传输证据与受限重试

**文件：** `include/starling/net/http_post_json.hpp`、`src/net/http_post_json.cpp`、`tests/cpp/test_http_post_json.cpp`。

**输入/输出：** 在共享网络入口新增 `RetryPolicy { LegacyCompatible, ConnectOnly }`；原重载保持兼容。`HttpResult` 追加实际尝试列表、响应字节与执行确定性，结构化调用强制 ConnectOnly。

- [x] 先扩展本地 HTTP 测试服务：读完请求后立即关闭且不发正文；发送部分正文后关闭；返回 429/503；连接拒绝；所有响应均记录真实连接次数。
- [x] 在旧核心运行 RED；核心断言是“服务器已读 POST 后 ConnectOnly 不重试”“部分响应保留”“每次尝试不超过配置上限”，而不是断言某个私有函数被调用。

```cpp
// 计划中的端到端断言，服务 fixture 在测试文件内实现。
EXPECT_EQ(result.attempt_count, 1);   // 已读请求、无响应正文。
EXPECT_FALSE(result.ok);
EXPECT_EQ(server.requests_read(), 1);
EXPECT_EQ(result.attempts.front().execution_certainty, ExecutionCertainty::Unknown);
```

- [x] 实现共享策略：ConnectOnly 仅限解析/连接失败；超时、读写、部分响应、HTTP 错误不自动重试；配置负值/非有限时限在调用前拒绝。
- [x] 运行新测试及既有 JSON/stream/embedding 适配器测试，验证旧策略与流式已交付字节边界保持。

## 阶段 A2：原生请求契约与 schema

**新增：** `include/starling/extractor/structured_output.hpp`、`src/extractor/structured_output.cpp`、`tests/cpp/test_structured_output.cpp`。

**修改：** `include/starling/extractor/llm_adapter.hpp`、`openai_adapter.hpp`、`fake_llm_adapter.hpp`，对应 `src/extractor/` 文件，`claim_contract.hpp/cpp`、`extractor.cpp`、`CMakeLists.txt`、`tests/cpp/CMakeLists.txt`。

**接口：** 使用设计中 `StructuredOutputRequest`、`OutputContractKind`、`OutputMode` 与 `extract_with_contract()`，schema JSON 由 `structured_output_schema(OutputContractKind)` 提供；不从提示推断请求类型。

- [x] RED：仅实现旧 extract 的适配器仍能执行 Legacy，新模式报不支持；准入/抽取正确发送不同 schema；自由生成不带 response_format；模式冲突请求为零。
- [x] RED：confidence 缺省/null/数值为正例，字符串/越界为反例；额外字段、重复键、决策索引重复和 reason/retain 矛盾仍失败。

```cpp
const auto response = legacy_adapter.extract_with_contract("x", "hash",
    {OutputContractKind::ClaimAdmissionV1, OutputMode::JsonSchemaStrict});
EXPECT_FALSE(response.ok);
EXPECT_EQ(legacy_adapter.calls(), 0);
```

- [x] 从 C++ 共用目录输出 schema 与提示枚举；原生预检接受 confidence:null 为缺省值，其余语义矩阵不变。
- [x] 适配器保留原始 completion，返回模式、契约、schema SHA、finish_reason/拒答和传输证据。拒答、截断和损坏外层响应分别失败，失败原文不写入旧成功字段。
- [x] 原生 Extractor 显式传两种契约，补充通道仍只允许一次内容尝试；编译及聚焦回归通过。

## 阶段 A3：能力探测、缓存与薄绑定

**文件：** `structured_output.hpp/cpp`、`openai_adapter.hpp/cpp`、`bindings/python/bind_06_extractor.cpp`、`tests/cpp/test_structured_output.cpp`、`tests/python/test_openai_adapter_binding.py`。

**接口：** `probe_structured_output(request)` 返回 `CapabilityEvidence`；其中包含状态、探测版本、schema SHA、探测响应、调用数、观察时间和证据 ID。`clear_structured_output_capabilities()` 显式清缓存。时钟作为原生可注入依赖，生产为单调时钟，测试无需等待 TTL。

- [x] RED：接受参数但违规输出为 Nonconformant；明确不支持为 Unsupported；普通 400/401/超时不缓存为 Unsupported；两案例通过也只标 ObservedConformant。
- [x] RED：并发同键只产生同组两次探测；不同模式/契约/schema 不复用；10 分钟过期/显式清除失效；原始凭证不出现在能力回执中。
- [x] 实现适配器实例缓存及锁外调用；构造和普通请求无自动探测；运行中 TTL 过期不追加隐藏探测。
- [x] Python binding 仅暴露上述类型与方法；集成断言 C++ 和 Python 返回相同模式/原因/原文，无独立语义代码。

## 阶段 A4：归档、原生核验与协议实验

**文件：** `scripts/eval_socialmem_claim_contract.py`、`scripts/verify_socialmem_claim_contract.py`、`scripts/eval_socialmem_extraction.py`、`tests/python/test_eval_socialmem_claim_contract.py`；新增 `scripts/probe_socialmem_output_capability.py`（只调用原生探测并保存回执）。

- [x] RED：能力不满足时 cohort 抽取/准入/回答/裁判计数全为零，状态 `capability_blocked`，质量指标为空而非零分。
- [x] RED：修改能力证据、schema SHA、请求契约或尝试数使 verify 失败；固定注入的真实外部准入元数据与 Fake 重放分开保存。
- [x] 增加计划中的 `--output-mode` 与 `--capability-report` 参数；旧命令继续可用。归档新核心/源码/schema/能力证据，v1 旧档使用冻结验证器，新版回执使用新验证器。
- [x] 完整构建安装、C++ 全套、Python 全套；对本轮 140 条历史原始响应作离线兼容重放，记录新增 null 接受边界，不能据此生成新准入分数。
- [x] 新旧模式及 B 阶段独立离线 smoke 已完成并核验；本地能力 fixture 每次 8 请求、零重试。
- [x] 2026-09-14 获用户手动授权后完成阶段 A 真实探测：8 请求、零重试、8 次 HTTP 200，四组均 Nonconformant；原文及证据经 C++ 核验。
- [x] 严格能力不满足时执行停止分支：`build/socialmem_20260913_capability_real` 已封存并由 A 冻结验证器核验为 `verified / capability_blocked`；抽取/准入/回答/裁判均 0、quality=null。不自动换模型或降级。
- [ ] 140 条协议诊断仅在探测符合且回归通过时运行；本次前置条件未满足，未执行。

## 阶段 B：已有关系边界修复与语义实验

**文件：** `src/extractor/claim_contract.cpp`、`tests/cpp/test_claim_contract.cpp`、`tests/python/test_relation_boundary_storage.py`（复用既有原生证据存取路径）；新增 `tests/data/eval_socialmem_relation_boundary_v2.json` 为独立来源用例，不并入原 64 候选。

- [x] 先写中英正反例：未决定单动作/仅可能/不知事实/疑问；操作转交/明确选定转交方案；关系否定/对象否定；同话轮其他语句不能污染当前候选。
- [x] RED 覆盖实际抽取提示、模型准入 prompt 合约和 Bus/持久化回读；Fake 只证明原生调用与字段正确，不能证明真实模型理解。
- [x] 修改 C++ 共享定义与提示；若增加候选局部规则，先保证明确决定与复合句的正例通过。只修既有五谓词，新增谓词仍需来源复核证明必要性。
- [x] 完整工程验证、旧响应重解析与离线 smoke；冻结本阶段源码和提示。
- [ ] 与阶段 A 使用相同已验证输出模式，在新目录 `build/socialmem_20260913_relation_boundary_real` 再运行同规模 140 条真实诊断。本地测试已完成；本次 A 真实能力门槛未通过，B cohort 不启动，不能隐式降级。
- [ ] 分开分析 P1 操作路由增量、固定否定/归属正例、未决定病例、误收误拒、首次格式成功率和 Q1/Q9 actor 入库；同步中文报告。

## 阶段 C：只读时间证据视图

**新增：** `include/starling/retrieval/temporal_evidence.hpp`、`src/retrieval/temporal_evidence.cpp`、`tests/cpp/test_temporal_evidence.cpp`。

**修改：** `bindings/python/bind_05_retrieval.cpp`、`src/retrieval/retrieval_planner.cpp`、`include/starling/retrieval/retrieval_planner.hpp`、`src/retrieval/context_pack.cpp`、`include/starling/retrieval/retrieval_receipt.hpp`，及对应构建列表与 Python binding 集成测试。

**接口：** `TemporalEvidenceRequest`、带 score 的 `TemporalEvidenceCandidate` 与 `select_temporal_evidence()` 按关系设计定义，Planner 请求追加可选时间视图请求，缺省关闭；`TemporalEvidenceView` 包含早/晚 Statement 引用、选中引用列表、顺序依据、歧义/不足及排除计数，不包含新事实。

- [x] RED：同主体同主题早晚保留、截止后排除、跨 tenant/actor 排除、source_turn 缺省/顺序重复失败、预算不足、相反状态并存、来源被篡改、同 id 不同 tenant 不混淆。

```cpp
ASSERT_TRUE(view.early && view.late);
EXPECT_EQ(view.early->statement_id, early_id);
EXPECT_EQ(view.late->statement_id, late_id);
EXPECT_LE(view.selected.size(), request.limit);
EXPECT_TRUE(view.excluded_after_cutoff > 0);
```

- [x] 实现 C++ 视图与 Context Pack/receipt 输出，绑定仅转发；既有相关性及权限过滤先执行，视图选取在最终 top-k 截断前完成，沿用有界候选预算。
- [x] 完整 C++/Python 回归及本地时间视图来源篡改/截断前选择测试通过。
- [ ] 只有目标人物补充声明稳定入库后才进行独立时间视图 QA 比较。先从 B 的归档库建立校验副本，源库哈希不变；同候选库、两个问题、旧/新视图各一次回答、各 3 票，共最多 4 回答/12 票，单列预算，不混入 B 的 120 票。
- [ ] 报告早晚来源是否共同进入上下文、截止违规数、派生解释父链和答题效果；不能把选出两条来源当作语义覆盖达标。

## 最终验证与交付

以下为现有工程验证命令，新增 CLI 参数须在 A4 实现后使用：

```sh
.venv/bin/cmake --build build -j 4
.venv/bin/cmake --install build --prefix .venv/lib/python3.14/site-packages
.venv/bin/ctest --test-dir build --output-on-failure -j 4
.venv/bin/python -m pytest tests/python -q
git diff --check
```

所有新增测试先有 RED 日志，再有 GREEN 日志；本地 HTTP 测试受监听限制时仅在沙箱外补跑对应项。各阶段全套通过后不反复重跑无关测试，文档更正只做文档一致性验证。

- [x] 同步总设计、两份技术报告、全部 12 子系统与专项设计登记；保留历轮数字的证据时间。
- [x] 核对报告、447 项源码/测试、原生模块、schema、原标签与本地能力证据；69 份现行文档/清单/计划/报告的链接有效，104 份历史快照未变。上述为 2026-09-13 工程检查；2026-09-14 新增真实能力证据与报告，同步现行设计入口并另行核验文档。
- [x] 报告生产门槛，不自动启用默认或运行 1,031 题。任何能力阻断、技术失败或质量退步明确列出，不冒充整个优化完成。

## 本轮交付状态

本地全部实现与验证完成；真实 A/B cohort、真实时间问答及其质量分析保持未完成。最终验证为 C++ 1,089/1,089、Python 1,355 passed / 15 skipped。A/B 原生模块及源码各自冻结，历史 140 原文在协议与最终解析阶段均零结果差异。2026-09-14 真实探测已执行并核验：四组 Nonconformant，阶段 A capability_blocked，后续 cohort 调用 0。当前停止源于能力门槛，详见[最新报告](../../eval/2026-09-14-socialmem-capability-probe.md)。A4 复用 `eval_socialmem_extraction.py` 的既有适配器构造入口，不在该脚本另造 schema 或能力逻辑。

## 2026-09-14 后续方案待确认

原计划已执行能力不符合时停止的分支。后续调查发现提示示例与严格 schema 的 confidence 字段不一致，并取得官方分模型支持文档；建议进入[协议恢复设计](../specs/2026-09-14-protocol-recovery-design.md)。该方案包含新的模型选择、A/B 每核心独立探测和明确发送范围，尚未获确认，不据此继续真实请求或修改实现。

## 声明范围后继方案（2026-09-15）

本计划保留其实施时点和勾选结果。后继[声明范围定位与覆盖诊断方案](../specs/2026-09-15-claim-scope-localization-design.md)已获用户确认并完成 L/R0 本地实现与回归，在 C++ 共享链路处理受限句首声明并提供原始行索引；无新增模型调用，不改变本计划对应历史结果。
