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

# 声明范围定位与生成覆盖诊断实施计划
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **范围 Schema 对齐收口（2026-09-16）**：C++ 非空/去重约束与评测身份/预算守卫已实现；真实 16 次请求、零重试，C0 8/8，C1 因提供商拒绝数组 uniqueItems 为 6/8，按门槛停止。四来源覆盖及 QA 未执行，无新 F1。详见[本轮报告](../../eval/2026-09-16-socialmem-scope-schema.md)。


> 执行方式：确认设计后，在当前会话按 executing-plans 逐任务执行，并用 test-driven-development 保存 RED/GREEN。用户已确认本地实施；按此计划记录真实 RED/GREEN 与验证结果。无需另行选择代理执行方式。

**目标：** 在保留完整来源证明和原生校验的前提下，修复受限句首陈述的 QUESTIONED 误拒，建立原始行到解析候选的可靠诊断索引。

**架构：** C++ 内部定位器计算守卫范围，原生 parser、持久化与检索共用；Python 只转发原生导出、执行隔离重放和归档统计。生成、准入提示及 wire schema 不变。

**技术栈：** 仓库现有 C++、JSON、GoogleTest、Python binding 与 pytest；不新增依赖。

**设计：** [声明范围定位与生成覆盖诊断设计](../specs/2026-09-15-claim-scope-localization-design.md)。

## 全局约束

- 顺序为中文文档→用户确认→失败测试→C++ 实现→本地评测分析→中文文档同步。
- 仅句首、完整 object 唯一逐字锚点、符合设计限定的 FIRST_PERSON/POS/ASSERTED 可局部化；其他回退。
- 只局部化 QUESTIONED，其他守卫保留完整来源；不自动改 marker、候选正文、topic 或时间。
- 抽取 v2、准入 v1、Evidence v1、source unit、source_span/hash 及生产默认不变。
- 诊断扩展不进入模型提示/candidates、不入库，不在 Python 复制核心逻辑。
- 历史 104 份设计、原始来源、金标、回执和封存不修改；当前工作区既有改动保留。
- 无新增真实 API 调用；不执行 B、时间 QA 或 1031 题；不提交、不推送。

## 文件职责

| 文件 | 本次职责 |
|---|---|
| 新 `src/extractor/claim_scope.hpp/.cpp` | 受限范围扫描、完整 object 定位、依赖风险回退 |
| `include/starling/extractor/claim_contract.hpp` | 原生诊断类型与结果字段 |
| `src/extractor/claim_contract.cpp` | 全批/逐行控制流接入，JSON 诊断导出，保持候选序列化 |
| `include/starling/extractor/extractor.hpp`、`src/extractor/extractor.cpp` | 在准入前保存原始行诊断；receipt 输出 |
| `CMakeLists.txt` | 注册新 C++ 源文件 |
| `tests/cpp/test_claim_contract.cpp` | 语义正负例、来源坐标、索引与准入完整来源 |
| `tests/cpp/test_claim_evidence_storage.cpp` | 直接写入/持久化/检索重放及来源破坏用例 |
| `tests/python/test_claim_contract_native.py`、`test_claim_evidence_storage.py` | binding 对原生结果的传递与真实存储边界 |
| 新 `scripts/analyze_socialmem_claim_scope.py`、`tests/python/test_analyze_socialmem_claim_scope.py` | 离线重放编排、显式人工覆盖注释合并、未知与未执行统计 |
| `src/retrieval/claim_evidence.cpp`、`bindings/python/bind_06_extractor.cpp` | 默认只核对既有共享路径；若需要转发字段，仅薄转发，不增加规则 |

## 任务 1：先冻结来源与回归预期，再写行为测试

- [x] 只读核验本设计封存、S/T 最终封存与 450 个当前源码/测试哈希，记录实施前增量。新工作目录用 `build/socialmem_20260915_claim_scope_work`，不得覆盖历史封存。
- [x] 在现有 `test_claim_contract.cpp` 的 fixture 上新增 L01–L11。先仅依赖已有 `parse_claim_response`，确保 RED 来自已知误拒而非缺少新接口。

首个最小测试使用现有 `row()`，它已定义 Mina、feels、POS 和 ASSERTED：

```cpp
TEST(ClaimContract, LeadingStatementSurvivesUnrelatedQuestion) {
    auto claim = row();
    claim["object"] = "relieved about the rehearsal";
    const std::string payload =
        "Mina: I am relieved about the rehearsal. Can you bring the chairs?";
    const auto raw = Json{{"schema_version", 2},
        {"statements", Json::array({claim})}}.dump();
    const auto parsed = parse_claim_response(raw, payload, "Mina");
    ASSERT_TRUE(parsed.errors.empty());
    EXPECT_TRUE(parsed.semantic_rejections.empty());
    ASSERT_EQ(parsed.statements.size(), 1u);
    EXPECT_EQ(parsed.statements[0].object_value, claim["object"]);
}
```

- [x] 运行 `cmake --build build --target starling_tests`，再运行 `build/tests/cpp/starling_tests --gtest_filter=ClaimContract.LeadingStatementSurvivesUnrelatedQuestion`；预期当前实现以 QUESTIONED 行级拒绝而失败。保存完整日志。
- [x] 写配对负例，依次变为 `Am I relieved about the rehearsal?`、句末 `Or am I?`、`Can you confirm that?`；要求 `errors.empty()`、一个 `scope_failure` 且零候选。它们在旧实现已通过时记录为基线，不伪称 RED。
- [x] 将设计表 L02、L05–L10 各种歧义写成参数化用例：每例明确 object、marker、是否允许局部化及期望原有拒绝。对跨句条件、否定与 QUOTED，另配原本合法的表示，防止“全拒”通过测试。
- [x] 先保存 Femi 原始回执的离线定位预期：只要求已确认的句首情绪行恢复；其余行逐条列为观察，不要求它们为达到恢复率而被放行。来源引用使用冻结回执，不复制到生产提示。

## 任务 2：实现共享 C++ 定位器

新增类型在 `claim_contract.hpp` 中定义，内部定位器只消费已验证的 JSON 行：

```cpp
struct ClaimScopeResolution {
    std::string mode;              // whole_unit / leading_statement
    std::string reason;
    std::string coordinate_space;  // utterance_utf8 / source_unit_text_utf8
    std::string clause_id;
    std::optional<std::size_t> begin;
    std::optional<std::size_t> end;
};

// src/extractor/claim_scope.hpp，非语言 binding API。
ClaimScopeResolution resolve_claim_question_scope(
    std::string_view source, std::string_view coordinate_space,
    const nlohmann::json& row, const nlohmann::json& evidence,
    bool source_self_report);
```

- [x] 增加 `<optional>`，定义返回值和内部入口，注册源文件。whole_unit 默认 begin/end=null；分界扫描按 UTF-8 字节进行，不以 locale 或字符数重算坐标。
- [x] 按设计 4.2→4.3→4.4 顺序实施：资格检查、完整 object 所有出现位置、首句边界、局部主题/时间约束、后续问句形式与风险回退。不要先按 topic 选片段。
- [x] 冻结 reason 值：`no_question`、`ineligible_claim`、`unverified_speaker`、`object_not_literal`、`ambiguous_object`、`nonleading_object`、`ambiguous_boundary`、`context_dependency`、`unsupported_question_form`、`unique_leading_statement`。无问号直接回退；其余按上述检查顺序返回第一个阻塞原因，含相同风险时结果确定。
- [x] 先在 C++ 测试中断言新范围和 reason，再接入 `scope_guards`。其他守卫继续用完整 `source`；仅问号调用改用经过范围验证的 view：

```cpp
const auto question_source = resolution.mode == "leading_statement"
    ? std::string_view(source).substr(*resolution.begin,
                                     *resolution.end - *resolution.begin)
    : std::string_view(source);
present("QUESTIONED", question_source.find('?') != std::string_view::npos ||
                      question_source.find("？") != std::string_view::npos);
```

- [x] 使用 L09 对范围切片还原和整 source_span/hash 做字节断言；测试 JSON 中的 `\n` 和 `\"` 解码后不会变成错误 payload 偏移。内嵌换行阻止定位也应有明确 reason。
- [x] 运行 `build/tests/cpp/starling_tests --gtest_filter=ClaimContract.*`。修复只围绕已写失败用例推进，新增风险先补测试。

## 任务 3：原始行诊断与准入前索引

原生类型在任务 2 的同一公开头中增加：

```cpp
struct ClaimRowDiagnostic {
    std::size_t index = 0;
    std::optional<std::size_t> candidate_index;
    std::string outcome; // candidate / semantic_rejected
    std::optional<ClaimScopeResolution> scope_resolution;
};
// ClaimParseResult 新增 vector<ClaimRowDiagnostic> row_diagnostics。
// ExtractionLlmAttempt 新增相同字段；在 ParseResult 切片前移动保存。
```

- [x] 先写 R01、L11：三行中的首行与末行内容完全相同，中间行 actor 错误；期望映射为 0→0、1→null、2→1。准入 `[index=0,false]`、`[index=1,true]` 后映射仍不变。
- [x] 全批结构预检通过后才创建行诊断；actor 等校验先失败时 scope_resolution=null。保留行在 push 前记录候选索引，拒绝行记录原始索引。整批异常清空诊断，与既有 statements/rejections 一致。
- [x] `extract_llm` 在 `rec.parse = std::move(parsed)` 前保存 row_diagnostics，避免派生类型切片丢字段；准入不得重写该数组。
- [x] `claim_parse_response_json` 与 `claim_extraction_receipt` 输出版本化可选诊断。`wire_row`、`claim_candidates_json`、SemanticClaimEvidence 不包含新字段，防止抽取和准入提示改变。
- [x] Python 测试只调用 `core.claim_parse_response` 并比较 JSON 字段；字段由 C++ 生成。测试旧回执缺字段时统计器给 unknown，不在 Python 根据内容构造“等价诊断”。
- [x] 重放同一 fixture 两次，比较候选正文、索引及字节范围；对相同来源、相同 candidates 输入保存抽取 prompt、admission prompt 和 wire schema 对比，要求与补丁前逐字一致。新解析候选增多导致的实际准入请求数据变化单独记录，不误判为模板漂移。

## 任务 4：共享存储边界与完整原文准入

- [x] 在现有 `SequenceAdapter` 上先写 L12：抽取返回 L01，第二次 Fake 准入明确拒绝；确认收到的准入 prompt 包含后续问句和完整来源，最终没有写入候选。再配 retain=true 路径，验证 `prepare → extract_all → commit_all` 所需的完整写入过程。
- [x] 在 `test_claim_evidence_storage.cpp` 复用现有来源落库 fixture，为合法局部声明创建 evidence；通过真实 Bus/SqliteAdapter 写入并走 retrieval 证据检查，期望与 parser 一致。不能只调用纯解析函数代替存储测试。
- [x] 修改来源 payload/hash、clause_id、actor、租户及 ASSERTED/QUESTIONED 组合；原生直写与检索继续拒绝。检查丢失或擦除 Engram 仍不能形成可用来源链接。
- [x] 核对 `claim_evidence_error` 只调用共享 parser；若未来修改需要另一份分句函数，此任务不通过。既有 source_span 必须保持整单元而不是局部范围。
- [x] 运行聚焦 C++ 和 Python 存储/契约回归。Fake 准入只能证明编排，不证明真实模型会正确判断语义。

## 任务 5：零模型调用的覆盖分析与隔离对照

- [x] 先写 R02/R03 的分析器测试。输入为来源、回执路径及显式人工状态注释：状态标识、clause_id、预期既有谓词、匹配原始候选索引、判断理由。重复内容靠索引关联；不得通过 Python 搜索关键词自动判谓词。
- [x] 提供 `scripts/analyze_socialmem_claim_scope.py --input-manifest PATH --annotations PATH --native-stage PATH --output-dir PATH`。只读旧回执，在指定核心的独立进程调用原生解析，输出每行差异、scope reason 和覆盖阶段；禁止导入模型客户端，已有输出目录禁止覆盖。
- [x] 状态机实现为事实汇总：完整可审阅原文且人工匹配为空才是 `not_generated`；超时为 `unknown`；结构失败单列；S/T 的准入/入库/检索固定 `not_executed`。错误 manifest、候选索引越界、来源/hash 不符直接失败，不能自动修复注释。

分析器必须通过的示意断言：

```python
assert timeout_row["generation_status"] == "unknown"
assert st_row["admission_status"] == "not_executed"
assert unchanged_raw["generated_candidates_before"] == unchanged_raw["generated_candidates_after"]
assert duplicate_rows[0]["raw_index"] != duplicate_rows[1]["raw_index"]
```

- [x] 从冻结 A 源码另建 `build/socialmem_20260915_claim_scope_work/a_localized`，仅应用 L/R0 原生补丁和构建注册；记录文件差异及模块 hash。继承本地已有依赖，不引入当前树的 B/C/S 提示变更。
- [x] 按旧核验器实际记录数重放历史 A 原文和 S/T 52 条回执；超时也保留原始结果，但不将其送 parser 当空响应。旧核心结果验证旧身份，新 A+L 结果命名为派生解析。prompt/schema/原始响应哈希必须不变，解析差异逐行列示。
- [x] 对 Femi、Marcus 及 S 两条分类/目标问题生成来源证据表，标注这是针对性诊断。只有独立负例零新增误放、已确认句首反例恢复、非作用域结果无未解释差异，才完成本地验收；不能换成“更多候选”标准。

## 任务 6：完整回归、中文文档同步与封存

- [x] 构建与安装当前核心：`.venv/bin/cmake --build build`、`.venv/bin/cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling-web/.venv/lib/python3.14/site-packages`。先确认安装仍落在当前工作区 `.venv`，核对导入模块路径/hash，避免旧 `_core` 假通过。
- [x] 运行 `ctest --test-dir build --output-on-failure` 与 `.venv/bin/python -m pytest tests/python -q`。本机 HTTP 测试所需权限按实际环境处理；若未运行，报告缺口，不将跳过计通过。无修改后的重复全量测试要求。
- [x] 检查 C++ 唯一逻辑源、完整原文准入、索引不重排、UTF-8 坐标、来源复核和隔离 A+L 的实际差异。修复新发现后执行相关回归。
- [x] 更新 70 份现行设计入口、关键正文、实施计划与新增实施分析报告：清楚区分本地工程验证、历史真实结果、派生重放和未执行的 R1/B/QA。新增设计文字中文。
- [x] 冻结 source/test/module/log、独立对照、行级差异、覆盖注释和文档快照；核验历史 104 份设计、原标签/回执和旧封存哈希、所有本地文档链接、`git diff --check`。
- [x] 最终报告实际恢复的候选、回退/未解决案例及误放负例结果。不执行真实模型调用；如后续要真实复测，先另行准备可审阅的请求预览、重复次数及总预算。

## 完成条件

本计划在用户确认时所有复选框均未勾选；现根据实际执行证据逐项完成。完成必须具备按时序保存的 RED/GREEN、C++ 共享实现、存储及 binding 回归、隔离 A+L 身份和逐行差异报告。真实模型质量、生产可用性和新增 F1 不属于本次本地交付结论。

## 最终本地验收记录

已依次完成中文设计、用户确认、失败测试、C++ 实现和回归。最终 C++ 1103/1103 通过，Python 1387 通过、15 跳过；历史 A 的 140 条流程重放无未解释差异，52 条 S/T 回执仅恢复 Femi 的 1 条已知误拒。完整原文准入、来源证明及原始行诊断均经独立审查；发现的未闭合尾文问题已按 RED/GREEN 修复并完成本地复核，处理记录随最终封存保存。70 份现行设计入口已同步，104 份历史设计与旧归档哈希保持不变。

最终产物：`build/socialmem_20260915_claim_scope_final`；详细边界、剩余问题和验证记录见[实施分析](../../eval/2026-09-15-socialmem-claim-scope-implementation.md)。本轮模型调用为 0，无新增 F1；保持默认关闭，不提交、不推送。
