<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

# SocialMemBench 结构化记忆闭环实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 C++ 核心中建立版本化谓词目录、可重放抽取回执和结构化证据检索闭环，并用独立合成夹具验证人物归属、否认/纠正、时间变化、多成员与来源引用。

**Architecture:** `claim_contract` 维护唯一的谓词目录，并由它生成 JSON 视图、抽取提示和语义约束。`memory_ops` 保持 `prepare → extract_all → commit_all` 三相边界，`claim_evidence` 负责来源与租户认证，新增的纯 C++ 结构化选择器负责按 holder、subject、predicate、topic 和截止时间筛选候选，`context_pack` 只渲染通过校验的声明。Python 绑定只映射 C++ 类型和回执，不复制语义规则。

**Tech Stack:** C++20、SQLite、nlohmann/json、GoogleTest、pybind11、pytest、现有 FakeLLMAdapter。

**Spec:** `docs/superpowers/specs/2026-09-19-socialmem-structured-memory-closure-design.md`

## Global Constraints

- 所有核心语义、谓词归一、范围判断、证据校验、时间选择和失败分类必须在 C++ 中实现。
- Python 只做参数归一、绑定转发、结果结构检查和评测编排。
- 不读取 SocialMemBench 题号、参考答案、公开锚点或开发题文本来生成目录、规则或夹具。
- 不修改裁判、参考答案、历史评测归档和已封存 `focused_coverage` 结果。
- 在离线闭环门槛通过前不发送新的 DashScope 请求；真实模型固定为已授权的 `qwen3.8-27b`。
- 共享工作区保持现有脏 `main`，不切分支、不清理无关修改、不提交历史混杂内容；每个任务用 `git diff --check`、测试输出和文件哈希作为检查点。
- 旧 `semantic_claim_json`、来源 engram、旧绑定函数和旧评测目录必须保持可读；新增字段必须向后兼容。

## 文件地图

- 修改 `include/starling/extractor/claim_contract.hpp`、`src/extractor/claim_contract.cpp`：新增 `PredicateSpec`/`PredicateCatalog`、规范化入口、目录版本和由目录派生的 JSON/prompt/schema 视图。
- 修改 `include/starling/extractor/extractor.hpp`、`src/extractor/extractor.cpp`、`src/memory/memory_ops.cpp`：扩展原生抽取/持久化回执的失败计数和来源保留状态。
- 新增 `include/starling/retrieval/structured_claim_retriever.hpp`、`src/retrieval/structured_claim_retriever.cpp`：实现纯 C++ 的结构化候选选择与 receipt。
- 修改 `include/starling/retrieval/context_pack.hpp`、`src/retrieval/context_pack.cpp`：渲染结构化声明的目录版本、关系族、证据引用和不足标记。
- 修改 `bindings/python/bind_06_extractor.cpp`、`bindings/python/bind_05_retrieval.cpp`、`bindings/python/bind_13_memory_ops.cpp`：只暴露 C++ 类型、函数和回执字段。
- 新增 `tests/cpp/test_structured_memory_closure.cpp`：独立合成夹具和 C++ 原生闭环测试。
- 新增 `tests/python/test_structured_memory_closure.py`：绑定转发、回执结构和异常映射测试。
- 修改 `tests/cpp/CMakeLists.txt`：加入新的 C++ 测试源文件。
- 修改 `docs/design/system_design.md`、`docs/design/subsystems_design/13_retrieval.md`、`docs/design/claim_contract_sync.md`：同步 C++ 单一语义源、目录版本、失败回执和闭环状态；不覆盖历史报告。
- 新增 `build/structured_memory_closure/`：保存 RED、离线测试、独立夹具报告和哈希清单；不写入模型密钥。

---

### Task 1: 建立 RED 夹具和测试入口

**Files:**
- Create: `tests/cpp/test_structured_memory_closure.cpp`
- Create: `tests/python/test_structured_memory_closure.py`
- Modify: `tests/cpp/CMakeLists.txt`

**Interfaces:**
- Consumes: 当前 `claim_source_turn_payload`、`parse_claim_response`、`memory_remember_prepare/extract_all/commit_all`、`TemporalEvidenceRequest`。
- Produces: 失败测试名称和合成 fixture；后续实现必须使这些测试通过。

- [ ] **Step 1: 写 C++ 失败测试**

在新测试文件顶部定义 `ClosureFixture`（包含 `std::shared_ptr<persistence::SqliteAdapter> db`、`std::vector<retrieval::StatementRow> candidates`、`retrieval::StructuredClaimRequest request`），以及 `make_closure_fixture()`、`make_tampered_closure_fixture()`、`make_remember_params()`、`failed_fake_llm()` 和 `make_failed_extraction_result()`。`make_closure_fixture()` 创建 `:memory:` SQLite 数据库并迁移到最新 schema，写入两个租户、三个会话和两个带合法 `semantic_claim_json/source_spans_json` 的候选；`make_tampered_closure_fixture()` 只篡改一条来源 payload；`make_failed_extraction_result()` 返回唯一 attempt 的 `LLMResponse.ok=true`、`raw_xml="{invalid"`、`parsed=false` 且错误类别为 `envelope_failure`；`make_remember_params()` 固定 tenant=`default`、holder=`Nora`、adapter=`closure-test`、source_prefix=`closure-`、created_at=`2026-09-19T10:00:00Z`。夹具内容只使用 Nora、Owen、ferry operator 和 community garden。

在新测试文件中加入以下测试名称和最小断言：

```cpp
TEST(StructuredMemoryClosure, CatalogExposesVersionedRelationFamilies) {
    const auto catalog = extractor::claim_predicate_catalog();
    EXPECT_FALSE(catalog.version.empty());
    EXPECT_NE(std::find_if(catalog.predicates.begin(), catalog.predicates.end(),
                           [](const auto& p) { return p.name == "owns"; }),
              catalog.predicates.end());
}

TEST(StructuredMemoryClosure, AliasNormalizesInNativeCore) {
    EXPECT_EQ(extractor::canonical_claim_predicate("has"), "owns");
}

TEST(StructuredMemoryClosure, MultiHolderAndNegationRoundTripKeepsActor) {
    const std::string payload = "Nora: I do not trust the ferry operator.\nOwen: I trust Nora.";
    const std::string raw = R"({"schema_version":2,"statements":[{"holder":"Nora","holder_perspective":"FIRST_PERSON","subject":"Nora","subject_kind":"cognizer","predicate":"trusts","object":"ferry operator","modality":"BELIEVES","polarity":"NEG","nesting_depth":0,"confidence":null,"evidence":{"clause_id":"c0","actor":"Nora","attributed_to":null,"assertion_scope":"NEGATED","scope_markers":["NEGATED"],"topic":"ferry operator","time_text":"","event_time":null}}]})";
    const auto parsed = extractor::parse_claim_response(raw, payload, "Nora");
    ASSERT_EQ(parsed.statements.size(), 1u);
    EXPECT_EQ(parsed.statements.front().subject_id, "Nora");
    EXPECT_EQ(parsed.statements.front().polarity, schema::Polarity::NEG);
}

TEST(StructuredMemoryClosure, TemporalFixtureSelectsEarlyAndLateClaims) {
    const auto fixture = make_closure_fixture();
    const auto view = retrieval::select_structured_claims(
        fixture.db->connection(), fixture.candidates, fixture.request);
    ASSERT_TRUE(view.sufficient);
    ASSERT_TRUE(view.early.has_value());
    ASSERT_TRUE(view.late.has_value());
    EXPECT_NE(view.early->statement_id, view.late->statement_id);
}

TEST(StructuredMemoryClosure, InvalidSourceAndCrossTenantClaimsAreExcluded) {
    const auto fixture = make_tampered_closure_fixture();
    const auto view = retrieval::select_structured_claims(
        fixture.db->connection(), fixture.candidates, fixture.request);
    EXPECT_EQ(view.excluded_invalid_evidence, 1u);
    EXPECT_EQ(view.excluded_scope, 1u);
}

TEST(StructuredMemoryClosure, FailedExtractionPreservesEngramAndReceiptClassifiesFailure) {
    auto database = make_closure_fixture().db;
    auto params = make_remember_params("Nora: invalid model output");
    const auto prepared = memoryops::remember_prepare(*database, params);
    const auto result = memoryops::remember_commit(
        *database, failed_fake_llm(), params, prepared,
        make_failed_extraction_result(), extractor::ValidationPolicy{});
    EXPECT_TRUE(result.source_preserved);
    EXPECT_FALSE(result.structured_claims_persisted);
    EXPECT_EQ(result.failure_category, "envelope_failure");
}
```

测试夹具使用 `Nora`、`Owen`、`ferry operator`、`community garden` 等与基准无关的内容；不得引用 SocialMemBench 文本。测试先按本计划声明的 C++ 接口编写，缺失接口导致的编译错误就是 RED 证据。

- [ ] **Step 2: 写 Python 绑定 RED 测试**

```python
def test_native_catalog_and_receipt_are_exposed():
    catalog = _core.claim_predicate_catalog()
    assert catalog.version
    assert any(spec.name == "owns" for spec in catalog.predicates)

def test_binding_forwards_native_failure_receipt(tmp_path):
    rt = runtime._build_local_store_sqlite_runtime(tmp_path / "closure.db")
    rt.start()
    llm = _core.FakeLLMAdapter()
    llm.set_default_response("{invalid", True, "")
    prepared = _core.memory_remember_prepare(
        rt.adapter, "default", "Nora", "", "closure-test", "closure-",
        "2026-09-19T10:00:00Z", b"Nora: invalid model output")
    extracted = _core.memory_extract_llm(
        rt.adapter, llm, "{convo}", "Nora", b"Nora: invalid model output")
    result = _core.memory_remember_commit(
        rt.adapter, llm, "default", "Nora", "", prepared, extracted)
    assert result["source_preserved"] is True
    assert result["structured_claims_persisted"] is False
    assert result["failure_category"] == "envelope_failure"
    del rt
```

该测试只访问 C++ 绑定，不在 Python 定义谓词列表或判断 holder/极性。

- [ ] **Step 3: 注册 C++ 测试目标**

在 `tests/cpp/CMakeLists.txt` 的 `starling_tests` 源列表中加入 `test_structured_memory_closure.cpp`，然后生成构建文件。

- [ ] **Step 4: 运行 RED**

运行：

```bash
cmake --build build --target starling_tests -j2
ctest --test-dir build -R 'StructuredMemoryClosure' --output-on-failure
pytest -q tests/python/test_structured_memory_closure.py
```

预期：C++ 因新目录/选择器/回执接口未定义而编译失败，Python 因绑定符号不存在而失败；保存完整输出到 `build/structured_memory_closure/red.log`。在 RED 之前不得修改实现文件。

---

### Task 2: 实现版本化 C++ 谓词目录和合同派生视图

**Files:**
- Modify: `include/starling/extractor/claim_contract.hpp`
- Modify: `src/extractor/claim_contract.cpp`
- Modify: `include/starling/extractor/structured_output.hpp`
- Modify: `src/extractor/structured_output.cpp`
- Test: `tests/cpp/test_structured_memory_closure.cpp`

**Interfaces:**
- Consumes: Task 1 的目录 RED 测试。
- Produces: `PredicateSpec`, `PredicateCatalog`, `claim_predicate_catalog()`, `find_claim_predicate()`, `canonical_claim_predicate()`；`claim_contract_catalog()`、`claim_extraction_prompt()` 和结构化 schema 从同一目录派生。

- [ ] **Step 1: 定义原生类型**

在头文件中加入明确字段，不让绑定层保存第二份规则：

```cpp
struct PredicateSpec {
    std::string name;
    std::vector<std::string> aliases;
    std::string semantic_family;
    std::vector<std::string> allowed_modalities;
    std::vector<std::string> allowed_polarities;
    std::vector<std::string> subject_kinds;
    std::vector<std::string> object_kinds;
    bool supports_event_time = false;
    bool supports_topic = true;
};

struct PredicateCatalog {
    std::string version;
    std::vector<PredicateSpec> predicates;
};
```

- [ ] **Step 2: 以 C++ 静态目录覆盖初始关系族**

实现规范谓词和别名归一。初始目录至少包含 `feels`、`trusts`、`decided_on`、`uncertain_about`、`indifferent_to`、`owns`、`knows`、`located_at`、`works_at`、`member_of`；每一项明确关系族、模态、极性、对象类型和时间能力。对没有明确语义规则的输入返回空规范名，并保持拒绝，不用宽松字符串匹配。

- [ ] **Step 3: 从目录生成 JSON/prompt/schema**

移除 `claim_contract_catalog()` 中独立维护的谓词数组；由目录生成谓词、别名、关系族和合同版本。抽取 prompt 只输出目录中的规范名称，schema 的 enum 与目录一致。旧五谓词合同的 JSON 读取路径继续兼容。

- [ ] **Step 4: 运行目录测试**

运行：

```bash
cmake --build build --target starling_tests -j2
ctest --test-dir build -R 'StructuredMemoryClosure.Catalog|StructuredMemoryClosure.Alias' --output-on-failure
```

预期：Task 1 的目录和别名测试通过；现有 `test_claim_contract`、`test_structured_output` 不新增失败。

---

### Task 3: 实现抽取 receipt、失败分类和三相状态

**Files:**
- Modify: `include/starling/extractor/extractor.hpp`
- Modify: `src/extractor/extractor.cpp`
- Modify: `include/starling/memory/memory_ops.hpp`
- Modify: `src/memory/memory_ops.cpp`
- Modify: `src/extractor/claim_contract.cpp`
- Test: `tests/cpp/test_structured_memory_closure.cpp`

**Interfaces:**
- Consumes: Task 2 的目录版本和当前 `ExtractionLlmResult`/`RememberOutcome` 三相管线。
- Produces: 原生失败分类、`source_preserved`、`structured_claims_persisted`、按谓词统计和 receipt 版本；失败时保留已写入 engram。

- [ ] **Step 1: 扩展状态结构**

为 `ExtractionLlmResult` 增加 C++ 字段：

```cpp
std::string catalog_version;
std::string failure_category;
std::map<std::string, std::size_t> accepted_by_predicate;
std::map<std::string, std::size_t> rejected_by_predicate;
bool source_preserved = false;
bool structured_claims_persisted = false;
```

为 `RememberOutcome` 增加同名状态和 `failure_category`，默认成功路径保持现有字段含义。

- [ ] **Step 2: 将错误映射固定在 C++**

在抽取解析、admission、持久化和证据阶段统一映射：LLM/HTTP → `transport_failure` 或 `timeout`；JSON → `envelope_failure`；字段 → `schema_failure`；范围/归属 → `scope_failure`；admission → `semantic_rejection`；事务 → `persistence_failure`。未知异常只允许映射为 `persistence_failure` 并保留原始异常摘要。

- [ ] **Step 3: 生成可重放 receipt**

扩展 `claim_extraction_receipt()`：加入 `catalog_version`、`failure_category`、来源保留状态、结构化写入状态、接受/拒绝按谓词计数；不删除当前 attempts、prompt hash、原始响应和错误数组。

- [ ] **Step 4: 写失败测试并验证**

使用 FakeLLM 返回非法 JSON、合法空声明、合法声明但 admission 拒绝三种结果，分别断言：原始 engram 存在；结构化声明状态准确；receipt 类别稳定；`remember` 与分相调用字段一致。

运行：

```bash
ctest --test-dir build -R 'ClaimContract|Extractor|Remember|StructuredMemoryClosure' --output-on-failure
```

---

### Task 4: 实现纯 C++ 结构化声明检索和 Context Pack 输出

**Files:**
- Create: `include/starling/retrieval/structured_claim_retriever.hpp`
- Create: `src/retrieval/structured_claim_retriever.cpp`
- Modify: `CMakeLists.txt`
- Modify: `include/starling/retrieval/context_pack.hpp`
- Modify: `src/retrieval/context_pack.cpp`
- Test: `tests/cpp/test_structured_memory_closure.cpp`

**Interfaces:**
- Consumes: `StatementRow`, `claim_evidence_error()`, Task 2 的谓词目录和现有 `TemporalEvidenceView`。
- Produces: 以下纯 C++ 接口：

```cpp
struct StructuredClaimRequest {
    std::string tenant_id;
    std::string holder_id;
    std::string subject_id;
    std::string predicate;
    std::string topic;
    std::string as_of_iso8601;
    int limit = 10;
    std::optional<TemporalEvidenceRequest> temporal;
};

struct StructuredClaimView {
    std::vector<StatementRow> selected;
    std::string receipt_json;
    bool sufficient = false;
    std::string insufficiency_reason;
    std::optional<TemporalEvidenceRef> early;
    std::optional<TemporalEvidenceRef> late;
    std::size_t input_candidates = 0;
    std::size_t excluded_scope = 0;
    std::size_t excluded_invalid_evidence = 0;
    std::size_t excluded_unknown_predicate = 0;
    std::size_t excluded_missing_order = 0;
};

StructuredClaimView select_structured_claims(
    persistence::Connection& conn,
    const std::vector<StatementRow>& candidates,
    const StructuredClaimRequest& request);
std::string structured_claim_view_json(const StructuredClaimView& view);
```

- [ ] **Step 1: 先实现输入边界**

缺少 tenant/subject、非法 limit、非法截止时间和未知谓词必须在 C++ 返回稳定不足原因；不得进入排序。

- [ ] **Step 2: 认证后筛选**

对每个候选先调用 `claim_evidence_error`，再检查 tenant、holder/subject、目录谓词、topic 和 `observed_at <= as_of`。每个排除原因独立计数；候选不得跨租户泄露。

- [ ] **Step 3: 时间和上下文输出**

对带 `source_turn` 的候选复用 `select_temporal_evidence`；不足时返回 `insufficiency_reason`，由 `render_pack` 输出 `[ABSTAIN]`。结构化行必须保留 holder、predicate、object、polarity、modality、catalog version、scope、source span 和时间状态。

- [ ] **Step 4: 运行检索测试**

```bash
cmake --build build --target starling_tests -j2
ctest --test-dir build -R 'StructuredMemoryClosure|TemporalEvidence|ClaimEvidenceStorage' --output-on-failure
```

---

### Task 5: 增加最小 Python 绑定并验证核心边界

**Files:**
- Modify: `bindings/python/bind_06_extractor.cpp`
- Modify: `bindings/python/bind_05_retrieval.cpp`
- Modify: `bindings/python/bind_13_memory_ops.cpp`
- Test: `tests/python/test_structured_memory_closure.py`

**Interfaces:**
- Consumes: Task 2–4 的 C++ 类型和函数。
- Produces: `PredicateSpec`/`PredicateCatalog` 只读属性、结构化检索请求/结果只读属性、`RememberOutcome` 新状态只读属性、`claim_extraction_receipt` JSON 字符串。

- [ ] **Step 1: 只读绑定目录和回执字段**

绑定层只暴露 `name`、`aliases`、`semantic_family`、允许集合、目录版本和结果字段；不添加 Python 谓词常量、别名表或选择器实现。

- [ ] **Step 2: 绑定结构化选择器**

提供一个释放 GIL 的薄转发函数，直接调用 `select_structured_claims`；异常保持 `ValueError`/`RuntimeError` 的既有映射。

- [ ] **Step 3: 运行 Python 组合测试**

```bash
pytest -q tests/python/test_structured_memory_closure.py \
  tests/python/test_claim_contract_surface.py \
  tests/python/test_temporal_evidence.py \
  tests/python/test_remember_phases_binding.py
```

预期：Python 只验证绑定字段、状态和异常，不验证核心语义算法。

---

### Task 6: 同步中文设计文档并完成离线闭环验收

**Files:**
- Modify: `docs/design/system_design.md`
- Modify: `docs/design/subsystems_design/13_retrieval.md`
- Modify: `docs/design/claim_contract_sync.md`
- Modify: `docs/superpowers/specs/2026-09-19-socialmem-structured-memory-closure-design.md`
- Create: `build/structured_memory_closure/offline-report.json`

**Interfaces:**
- Consumes: Task 1–5 的代码、测试和 receipt。
- Produces: 中文设计同步、独立夹具闭环率、失败类别统计、哈希和真实评测准入结论。

- [ ] **Step 1: 更新主设计文档**

在系统设计中说明：C++ `PredicateCatalog` 是唯一语义源；Python 不复制谓词；三相记忆的来源保留语义；结构化检索先认证证据后排序；目录版本和 receipt 字段属于可观测契约。历史评测段落只追加当前状态，不改旧数字。

- [ ] **Step 2: 运行专项 C++ 和 Python 测试**

```bash
cmake --build build --target starling_tests -j2
ctest --test-dir build --output-on-failure
pytest -q tests/python
```

记录完整测试命令、退出码、通过数、跳过数和已知沙箱限制；loopback listener 若仍受沙箱限制，按既有流程在允许环境单独复验，不把未运行误报为通过。

- [ ] **Step 3: 生成独立夹具报告**

用合成夹具统计有效声明总数、完成持久化数、证据检索数、正确 holder 数、时间早晚选择数、来源引用数和每类失败数。闭环率必须按有效声明分母计算，目标至少 95%；任一静默归属错误都阻断真实评测。

- [ ] **Step 4: 离线门槛判定**

只有以下条件全部满足，才把 `offline-report.json` 标为 `eligible_for_real_eval=true`：C++ 合同/来源/租户/事务测试 100% 通过；独立夹具闭环率 ≥95%；Python 组合测试通过；旧合同回归无新增失败。否则只记录诊断，不发送 DashScope 请求。

- [ ] **Step 5: 保存证据**

保存 `git diff --check`、测试输出、报告和受影响文件 SHA-256 到 `build/structured_memory_closure/manifest.json`。不执行提交，不覆盖既有 `build/socialmem_*` 归档。

---

### Task 7: 通过离线门槛后执行一次冻结真实评测并分析

**Files:**
- Create: `build/socialmem_20260919_structured_memory/`
- Modify: `docs/eval/2026-09-19-socialmem-structured-memory-closure.md`
- Modify: `docs/design/subsystems_design/13_retrieval.md`

**Interfaces:**
- Consumes: Task 6 的 `eligible_for_real_eval=true`、冻结源码/依赖哈希和已授权 DashScope 配置。
- Produces: 一次完整终态的 baseline/结构化闭环对照、技术失败与 token 账本、逐题变化、bootstrap 区间和晋级结论。

- [x] **Step 1: 冻结请求边界**

固定 `qwen3.8-27b`、原回答/裁判协议、零重试、同一语料和独立运行目录；每题写预约和终态账本，未知请求按上界计入，完整终态前不查看成绩。

- [ ] **Step 2: 运行一次对照**

只在离线门槛通过后执行；记录回答、裁判、抽取 receipt、结构化候选 receipt、tokens、HTTP 和源码哈希。失败计零，不自动追加请求。

- [ ] **Step 3: 分析结果**

报告 99 题开发诊断集的准确率、逐题新对/回退、33 网络 bootstrap 5000 次区间、技术失败、共同正常子集、抽取失败类别和证据排除数。结果不外推到 733 题或生产。

- [ ] **Step 4: 应用晋级门槛**

### 首轮执行记录（2026-09-19）

- [x] 文档、RED 测试和 C++ 实现已完成；Python 仅保留 binding。
- [x] `.venv/bin/ctest --test-dir build -R 'StructuredMemoryClosure' --output-on-failure`：9/9 通过，包含正向持久化后检索路径。
- [x] Python 结构化组合（临时注入构建扩展，`test_remember_phases_binding.py` 除外）：10/10 通过。
- [x] 完整 C++ 回归：1200/1201 通过；失败项为沙箱 loopback listener 限制，未归因于本轮改动。
- [x] 离线审计报告和 manifest 已写入 `build/structured_memory_closure/`。
- [x] 补强正向 temporal/source 持久化夹具并重新验收离线门槛：有效正向夹具 3/3 通过。
- [ ] 执行一次固定 `qwen3.8-27b` 对照并记录完整终态；当前尚未发送本轮对照请求。

只有净增至少 5 题且网络 bootstrap 95% 区间下界大于 0 才列为扩大开发集验证方向；否则保留诊断状态，提出下一轮唯一待验证假设，不追加本轮请求。

---

## 验收命令索引

```bash
git diff --check
cmake --build build --target starling_tests -j2
ctest --test-dir build -R 'StructuredMemoryClosure|ClaimContract|ClaimEvidenceStorage|TemporalEvidence|Extractor|Remember' --output-on-failure
pytest -q tests/python/test_structured_memory_closure.py tests/python/test_claim_contract_surface.py tests/python/test_temporal_evidence.py tests/python/test_remember_phases_binding.py
```

计划完成后，执行阶段必须按 Task 1→Task 7 顺序推进；任何测试失败先定位并更新 C++ 核心或夹具，不能在 Python 添加重复语义规则，也不能跳过 RED 直接实现。
