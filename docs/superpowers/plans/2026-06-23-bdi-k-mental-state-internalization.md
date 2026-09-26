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

# BDI+K Mental-State Internalization (SP-A) Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Internalize a cognizer's full mental state as an out-of-the-box core capability — reliably extract BDI+K (beliefs/desires/intentions/commitments/knowledge/preferences) and expose `mental_state_of(X)` as a core C++ aggregate — so any consumer surfaces "what's in X's mind" without peripheral logic.

**Architecture:** A new core C++ aggregate `mental_state_of(X)` mirrors `what_does_X_believe` (`SqliteMetaStore` + `StatementFilter`, drop the subject filter) and buckets X's statements by attitude (predicate-first for `prefers`/`knows`, else modality). The extraction prompt is enriched (additive worked examples) so non-belief modalities are actually elicited. The eval server is a thin gated consumer.

**Tech Stack:** C++20 (`src/tom/`, gtest, `SqliteMetaStore`), pybind11, Python (prompt data, pytest), FastAPI eval server.

**Spec:** `docs/superpowers/specs/2026-06-23-bdi-k-mental-state-internalization-design.md` (commit `0cc43c0`).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `include/starling/tom/mentalizing.hpp` | declare `MentalState` + `mental_state_of` | Modify |
| `src/tom/mentalizing_profile.cpp` | `mental_state_of` impl (query + bucketing) | Create |
| `CMakeLists.txt` | build source | Modify (add to `starling_core`) |
| `tests/cpp/test_mental_state.cpp` | ctest (bucketing contract) | Create |
| `tests/cpp/CMakeLists.txt` | test source | Modify |
| `bindings/python/bind_08_tom.cpp` | `MentalState` POD + `mental_state_of` `.def` | Modify |
| `python/starling/tom/primitives.py` | thin wrapper | Modify |
| `python/starling/extractor/prompts.py` | DESIRES/INTENDS/KNOWS worked examples | Modify |
| `tests/python/test_mental_state_roundtrip.py` | stub-LLM round-trip + binding smoke | Create |
| `scripts/starling_tomeval_server.py` | thin gated `mental_state_of` injection | Modify |
| `tests/python/test_tomeval_server_mentalstate.py` | server classify + format unit tests | Create |

---

## Task 0: Confirm green baseline (controller)

- [ ] **Step 1: Build + full suite**

Run (repo root `/Users/jaredguo-mini/develop/memory/starling`):
```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build
.venv/bin/ctest --test-dir build --output-on-failure | tail -3
.venv/bin/python -m pytest tests/python -q | tail -3
```
Expected: ctest 658 / pytest 649 passed (15 skipped). Confirm exact counts. If red before any change, stop and report.

---

## Task 1: `mental_state_of(X)` core aggregate (C++)

**Files:**
- Modify: `include/starling/tom/mentalizing.hpp` (declare after the existing structs, before the free functions)
- Create: `src/tom/mentalizing_profile.cpp`
- Modify: `CMakeLists.txt` (add to `starling_core`)
- Create: `tests/cpp/test_mental_state.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Reference (read first):** `src/tom/mentalizing_believe.cpp` — `what_does_X_believe` uses `store::SqliteMetaStore meta(adapter.connection())` + `store::StatementFilter f` (`f.tenant_id`, `f.holder_id`, `f.subject_kind`, `f.subject_id`, `f.as_of_iso8601`, optional `f.modality`) → `meta.query_statements(f)` returning `std::vector<retrieval::StatementRow>`. `StatementRow` (`include/starling/retrieval/statement_row.hpp`) has `.modality`, `.predicate`, `.holder_id`, etc.

- [ ] **Step 1: Verify `StatementFilter` semantics (no-subject query)**

`grep -n "struct StatementFilter" -r include src` and read it. Confirm: leaving `subject_kind`/`subject_id`/`modality` empty = no filter on those (so a `holder_id`-only query returns ALL of X's statements, any subject, any modality). Note the answer; if empty does NOT mean "no filter", adjust the impl in Step 4 to query without the subject constraint (e.g., a direct `query_statements` with only holder+as_of). Also confirm the canonical STORED modality string casing by grepping the writer: `grep -rn "modality" src/extractor/json_parser.cpp src/store/*writer*.cpp` — the episodic seed stores `'occurred'` (lowercase); confirm beliefs store `'believes'` etc. lowercase. Use the confirmed casing in Steps 2 + 4.

- [ ] **Step 2: Declare `MentalState` + `mental_state_of` in `include/starling/tom/mentalizing.hpp`**

After the `SharedFact` struct (before `// ─── Free functions ───`), add:
```cpp
// X's full mental state, grouped by propositional attitude. An out-of-the-box
// "what's in X's mind" aggregate over X's held statements (holder_id=x, observed_at<=as_of).
struct MentalState {
    std::vector<retrieval::StatementRow> beliefs;       // modality 'believes'
    std::vector<retrieval::StatementRow> knowledge;     // predicate 'knows'
    std::vector<retrieval::StatementRow> desires;       // modality 'desires'
    std::vector<retrieval::StatementRow> intentions;    // modality 'intends'
    std::vector<retrieval::StatementRow> commitments;   // modality 'commits'
    std::vector<retrieval::StatementRow> preferences;   // predicate 'prefers'
};
```
And after the `what_does_X_think_chain` declaration, add:
```cpp
// 10. X's full mental state, bucketed by attitude. Buckets a statement predicate-first
//     ('prefers'->preferences, 'knows'->knowledge), else by modality. occurred / norm_* /
//     enforces / observes are dropped (not propositional attitudes). Unknown X -> all empty.
MentalState mental_state_of(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view tenant,
    std::string_view as_of);
```

- [ ] **Step 3: Write the failing ctest — `tests/cpp/test_mental_state.cpp`**

Mirror `tests/cpp/test_mentalizing_think.cpp:22-26`'s `open_migrated()` (copy it). Add a `seed_stmt` helper that INSERTs ONE statements row (adapt the INSERT from `test_mentalizing_think.cpp:35-47` but parameterize holder/subject_kind/subject/predicate/object/modality, and set `consolidation_state='consolidated'`, `review_status='approved'` so `query_statements` returns it):
```cpp
#include "starling/tom/mentalizing.hpp"
#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <memory>
#include <string>

namespace {
std::unique_ptr<starling::persistence::SqliteAdapter> open_migrated() {
    auto a = starling::persistence::SqliteAdapter::open(":memory:");
    starling::persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}
// INSERT one consolidated+approved statement. modality/predicate are the bucket keys.
void seed_stmt(starling::persistence::SqliteAdapter& a, const char* tenant, const char* id,
               const char* holder, const char* subject_kind, const char* subject,
               const char* predicate, const char* object, const char* modality,
               const char* observed_at) {
    const std::string sql =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,evidence_json,consolidation_state,review_status,"
        "nesting_depth,created_at,updated_at) VALUES('" + std::string(id) +
        "','" + tenant + "','" + holder + "','FIRST_PERSON','" + subject_kind + "','" + subject +
        "','" + predicate + "','entity','" + object + "','h-" + std::string(id) +
        "','v1','" + modality + "','POS',0.9,'" + observed_at +
        "',0.5,'{}',0.0,'" + observed_at +
        "','user_input','[]','consolidated','approved',0,'" + observed_at + "','" + observed_at + "')";
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(a.connection().raw(), sql.c_str(), nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
}
}  // namespace

using starling::tom::mentalizing::mental_state_of;

TEST(MentalState, BucketsByAttitude) {
    auto a = open_migrated();
    const char* T = "tm";
    const char* AS = "2026-01-02T00:00:00Z";
    // X's statements: one per bucket. NOTE: use the CONFIRMED stored modality casing from
    // Task 1 Step 1 (lowercase here; fix if the writer stores otherwise).
    seed_stmt(*a, T, "s1", "Alice", "entity",   "ball",   "located_at", "box",     "believes", "2026-01-01T00:00:01Z");
    seed_stmt(*a, T, "s2", "Alice", "entity",   "keys",   "knows",      "drawer",  "believes", "2026-01-01T00:00:02Z");
    seed_stmt(*a, T, "s3", "Alice", "entity",   "weekend","prefers",    "outdoors","believes", "2026-01-01T00:00:03Z");
    seed_stmt(*a, T, "s4", "Alice", "entity",   "hiking", "located_at", "trail",   "desires",  "2026-01-01T00:00:04Z");
    seed_stmt(*a, T, "s5", "Alice", "entity",   "report", "responsible_for","report","intends","2026-01-01T00:00:05Z");
    seed_stmt(*a, T, "s6", "Alice", "entity",   "deck",   "promises",   "friday",  "commits",  "2026-01-01T00:00:06Z");
    seed_stmt(*a, T, "s7", "Bob",   "entity",   "ball",   "located_at", "basket",  "believes", "2026-01-01T00:00:07Z"); // other holder
    seed_stmt(*a, T, "s8", "Alice", "entity",   "door",   "located_at", "shut",    "occurred", "2026-01-01T00:00:08Z"); // dropped

    auto ms = mental_state_of(*a, "Alice", T, AS);
    EXPECT_EQ(ms.beliefs.size(), 1u);      // s1 (modality believes, predicate not knows/prefers)
    EXPECT_EQ(ms.knowledge.size(), 1u);    // s2 (predicate=knows, predicate-first)
    EXPECT_EQ(ms.preferences.size(), 1u);  // s3 (predicate=prefers, predicate-first over modality believes)
    EXPECT_EQ(ms.desires.size(), 1u);      // s4 (modality=desires, predicate=located_at -> by modality)
    EXPECT_EQ(ms.intentions.size(), 1u);   // s5 (modality=intends)
    EXPECT_EQ(ms.commitments.size(), 1u);  // s6 (modality=commits)
    // Bob's s7 (other holder) and Alice's occurred s8 excluded from all buckets.
    for (auto* b : {&ms.beliefs, &ms.knowledge, &ms.preferences, &ms.desires, &ms.intentions, &ms.commitments})
        for (auto& r : *b) EXPECT_EQ(r.holder_id, "Alice");
}

TEST(MentalState, UnknownCognizerEmpty) {
    auto a = open_migrated();
    auto ms = mental_state_of(*a, "Nobody", "tm", "2026-01-02T00:00:00Z");
    EXPECT_TRUE(ms.beliefs.empty() && ms.knowledge.empty() && ms.desires.empty() &&
                ms.intentions.empty() && ms.commitments.empty() && ms.preferences.empty());
}

TEST(MentalState, AsOfBound) {
    auto a = open_migrated();
    const char* T = "tb";
    seed_stmt(*a, T, "e1", "Alice", "entity", "ball", "located_at", "box", "believes", "2026-01-05T00:00:00Z");
    auto before = mental_state_of(*a, "Alice", T, "2026-01-01T00:00:00Z");
    EXPECT_TRUE(before.beliefs.empty()) << "statement after as_of must be excluded";
    auto after = mental_state_of(*a, "Alice", T, "2026-01-06T00:00:00Z");
    EXPECT_EQ(after.beliefs.size(), 1u);
}
```
NOTE — this test pins TWO contracts: (1) the **predicate-first rule** (a statement with `predicate='prefers'`/`'knows'` buckets to preferences/knowledge regardless of modality — that's why `s3` with modality=believes lands in preferences; everything else buckets by modality); (2) the **exact stored modality casing**. The seeds above use lowercase (`believes`/`desires`/`intends`/`commits`/`occurred`) per Step 1's finding. If Step 1 shows the writer stores a different casing, update BOTH the seeds here AND the string literals in the impl (Step 4) to match — that alignment is the contract.

Add `tests/cpp/test_mental_state.cpp` to the `add_executable(starling_tests ...)` list in `tests/cpp/CMakeLists.txt`.

- [ ] **Step 4: Build — verify link failure, then implement**

Build (`configure_build.py --build`); expect undefined `mental_state_of`. Then create `src/tom/mentalizing_profile.cpp`:
```cpp
// mental_state_of — X's full mental state grouped by attitude. Mirrors
// what_does_X_believe (SqliteMetaStore + StatementFilter) but drops the subject filter
// and buckets in C++. Internalized out-of-the-box capability; consumers stay thin.
#include "starling/tom/mentalizing.hpp"
#include "starling/store/sqlite_meta_store.hpp"
#include <string>
#include <vector>

namespace starling::tom::mentalizing {

MentalState mental_state_of(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view tenant,
    std::string_view as_of) {
    store::SqliteMetaStore meta(adapter.connection());
    store::StatementFilter f;
    f.tenant_id     = std::string(tenant);
    f.holder_id     = std::string(x);
    f.as_of_iso8601 = std::string(as_of);
    // No subject_kind / subject_id / modality filter -> ALL of X's held statements.
    const auto rows = meta.query_statements(f);

    MentalState out;
    for (const auto& r : rows) {
        if (r.predicate == "prefers")      out.preferences.push_back(r);   // predicate-first
        else if (r.predicate == "knows")   out.knowledge.push_back(r);
        else if (r.modality == "believes") out.beliefs.push_back(r);
        else if (r.modality == "desires")  out.desires.push_back(r);
        else if (r.modality == "intends")  out.intentions.push_back(r);
        else if (r.modality == "commits")  out.commitments.push_back(r);
        // occurred / norm_* / enforces / observes -> not a propositional attitude, dropped.
    }
    return out;
}

}  // namespace starling::tom::mentalizing
```
Use the CONFIRMED modality casing from Step 1. If `StatementFilter` empty-subject does NOT mean "no filter" (Step 1), instead query with only holder+as_of via the MetaStore's available no-subject path (grep `SqliteMetaStore` for the method). Add `src/tom/mentalizing_profile.cpp` to `starling_core` sources in the root `CMakeLists.txt` (beside `src/tom/mentalizing_believe.cpp`).

- [ ] **Step 5: Build + run the ctests**
```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build
.venv/bin/ctest --test-dir build -R MentalState --output-on-failure
```
Expected: all 3 `MentalState.*` PASS. If `BucketsByAttitude` fails, the stored modality casing differs from the seed — align the seed to the writer's actual casing (that's the contract).

- [ ] **Step 6: Confirm no regression**
```bash
.venv/bin/ctest --test-dir build -R "Mentalizing|WhatDoesXThink|Believe|Perception" --output-on-failure
```
Expected: existing tests still PASS (additive).

- [ ] **Step 7: Commit**
```bash
git add include/starling/tom/mentalizing.hpp src/tom/mentalizing_profile.cpp CMakeLists.txt tests/cpp/test_mental_state.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P3/SP-A): mental_state_of(X) — core BDI+K mental-state aggregate

Mirrors what_does_X_believe (SqliteMetaStore + StatementFilter) but drops the subject
filter and buckets X's held statements by attitude: predicate-first (prefers->preferences,
knows->knowledge), else modality (believes/desires/intends/commits). occurred/norm_*/
enforces/observes dropped. Out-of-the-box "what's in X's mind" core capability; additive
(no existing primitive touched). Three ctests pin the bucketing contract + unknown-X-empty
+ as_of bound.

EOF
)"
```

---

## Task 2: Bind + wrap `mental_state_of` for Python

**Files:**
- Modify: `bindings/python/bind_08_tom.cpp` (POD + `.def`)
- Modify: `python/starling/tom/primitives.py` (wrapper)
- Create: `tests/python/test_mental_state_roundtrip.py` (smoke now; round-trip in Task 3)

- [ ] **Step 1: Failing smoke test — create `tests/python/test_mental_state_roundtrip.py`**
```python
def test_mental_state_bound_and_callable():
    from starling import _core
    assert hasattr(_core, "mental_state_of")
    ms_cls = _core.MentalState
    for f in ("beliefs", "knowledge", "desires", "intentions", "commitments", "preferences"):
        assert hasattr(ms_cls, f)
    from starling.tom.primitives import mental_state_of  # wrapper exists
```

- [ ] **Step 2: Run → fail** (`AttributeError: ... 'mental_state_of'`).

- [ ] **Step 3: Add the pybind `.def`** in `bindings/python/bind_08_tom.cpp`. Mirror the `StateBelief` POD binding (~line 173) for the struct, and the `what_does_X_believe` `.def` (~line 117) for the function (read both first). After the `what_does_X_think_chain` `.def`, add:
```cpp
    py::class_<starling::tom::mentalizing::MentalState>(m, "MentalState")
        .def_readonly("beliefs",     &starling::tom::mentalizing::MentalState::beliefs)
        .def_readonly("knowledge",   &starling::tom::mentalizing::MentalState::knowledge)
        .def_readonly("desires",     &starling::tom::mentalizing::MentalState::desires)
        .def_readonly("intentions",  &starling::tom::mentalizing::MentalState::intentions)
        .def_readonly("commitments", &starling::tom::mentalizing::MentalState::commitments)
        .def_readonly("preferences", &starling::tom::mentalizing::MentalState::preferences);

    m.def("mental_state_of",
        [](starling::persistence::SqliteAdapter& adapter, const std::string& x,
           const std::string& tenant, const std::string& as_of) {
            starling::tom::mentalizing::MentalState out;
            { py::gil_scoped_release release;
              out = starling::tom::mentalizing::mental_state_of(adapter, x, tenant, as_of); }
            return out;
        },
        py::arg("adapter"), py::arg("x"), py::arg("tenant"), py::arg("as_of"),
        "X's full mental state grouped by attitude (beliefs/knowledge/desires/intentions/"
        "commitments/preferences).");
```
(`StatementRow` is already bound — its vectors convert automatically; confirm by grepping `StatementRow` in `bind_*.cpp`. If not bound, bind it as a read-only POD mirroring the fields used.)

- [ ] **Step 4: Add the wrapper** in `python/starling/tom/primitives.py` (after `what_does_X_believe`, mirror its style):
```python
def mental_state_of(
    adapter,
    *,
    x: str,
    tenant_id: str = "default",
    as_of: Optional[datetime] = None,
):
    """X's full mental state grouped by attitude: beliefs / knowledge / desires /
    intentions / commitments / preferences. Returns a MentalState."""
    as_of_iso = _iso_now_or_convert(as_of)
    return _core.mental_state_of(adapter, x, tenant_id, as_of_iso)
```

- [ ] **Step 5: Rebuild editable + run smoke**
```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --python-editable --build-dir build
.venv/bin/python -m pytest tests/python/test_mental_state_roundtrip.py::test_mental_state_bound_and_callable -v
```
Expected: PASS. (If `_core` stale, `cmake --install build --prefix "$(.venv/bin/python -c 'import site;print(site.getsitepackages()[0])')"`.)

- [ ] **Step 6: Commit**
```bash
git add bindings/python/bind_08_tom.cpp python/starling/tom/primitives.py tests/python/test_mental_state_roundtrip.py
git commit -m "$(cat <<'EOF'
feat(P3/SP-A): bind + wrap mental_state_of for Python

Thin MentalState POD binding (6 attitude buckets) + mental_state_of .def (GIL released
around the query) + Pythonic wrapper. No logic in the binding layer.

EOF
)"
```

---

## Task 3: Extraction enrichment + round-trip

**Files:**
- Modify: `python/starling/extractor/prompts.py` (additive worked examples)
- Modify: `tests/python/test_mental_state_roundtrip.py` (round-trip)

- [ ] **Step 1: Add the failing round-trip test** to `tests/python/test_mental_state_roundtrip.py` (use `starling.make_stub_llm` per `tests/python/test_completeness_e2e.py:34-56`; the stub returns a canned belief-pass JSON with the three non-belief attitudes):
```python
import json
import starling
from starling.tom.primitives import mental_state_of

_CANNED = json.dumps([
    {"holder": "Alice", "holder_perspective": "FIRST_PERSON", "subject": "ball",
     "predicate": "located_at", "object": "box", "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0},
    {"holder": "Alice", "holder_perspective": "FIRST_PERSON", "subject": "keys",
     "predicate": "knows", "object": "drawer", "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0},
    {"holder": "Alice", "holder_perspective": "FIRST_PERSON", "subject": "weekend",
     "predicate": "prefers", "object": "outdoors", "modality": "DESIRES", "polarity": "POS", "nesting_depth": 0},
    {"holder": "Alice", "holder_perspective": "FIRST_PERSON", "subject": "report",
     "predicate": "responsible_for", "object": "report", "modality": "INTENDS", "polarity": "POS", "nesting_depth": 0},
])

def test_roundtrip_buckets_nonbelief_attitudes(tmp_path):
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="narrator",
                               llm=starling.make_stub_llm(default_response=_CANNED))
    mem.remember("Alice: the ball is in the box; I know the keys are in the drawer; "
                 "I want to spend the weekend outdoors; I'm going to finish the report.")
    ms = mental_state_of(mem._rt.adapter, x="Alice", tenant_id=mem._core.tenant)
    assert len(ms.knowledge) >= 1     # predicate=knows
    assert len(ms.preferences) >= 1   # predicate=prefers
    assert len(ms.intentions) >= 1    # modality=INTENDS
    # belief bucket holds the plain located_at belief
    assert any(r.object_value == "box" for r in ms.beliefs)
```
(The exact stored modality/predicate casing must match Task 1's contract; if `remember` lowercases modality, the C++ buckets already match. If the test fails on a bucket, reconcile the writer's stored form with Task 1.)

- [ ] **Step 2: Run → likely fails** (the canned non-belief statements may not bucket if the writer drops/transforms them). Diagnose: print `ms` buckets. This pins that the WRITER stores DESIRES/INTENDS/knows/prefers in the form `mental_state_of` buckets. If the writer rejects a modality, that is a real finding — report it (the modality must be a valid stored value; the spec assumes the writer accepts the extraction's modality enum).

- [ ] **Step 3: Add the prompt worked examples** in `python/starling/extractor/prompts.py`. Read the file; after the existing worked examples (and consistent with the `OBJECT BREVITY` / `HOLDER vs SUBJECT` rules), add an additive examples block:
```
WORKED EXAMPLE (non-belief attitudes — capture DESIRES / INTENDS / knowledge, not just beliefs):
- "Li Hua: I want to spend the weekend outdoors" → {"holder":"Li Hua","holder_perspective":"FIRST_PERSON","subject":"weekend","predicate":"prefers","object":"outdoors","modality":"DESIRES","polarity":"POS","nesting_depth":0}
  (a WANT is modality=DESIRES; predicate is the closest available — the want's target.)
- "Mei: I'm going to finish the report tonight" → {"holder":"Mei","holder_perspective":"FIRST_PERSON","subject":"report","predicate":"responsible_for","object":"report","modality":"INTENDS","polarity":"POS","nesting_depth":0}
  (a plan/INTENT is modality=INTENDS.)
- "Tom: I know the keys are in the drawer" → {"holder":"Tom","holder_perspective":"FIRST_PERSON","subject":"keys","predicate":"knows","object":"drawer","modality":"BELIEVES","polarity":"POS","nesting_depth":0}
  (explicit knowing uses predicate=knows.)
Emit these attitudes when present — do NOT collapse every mental state to BELIEVES.
```
Match the file's exact JSON-brace convention (single vs the `{passage}`/`{conversation}` placeholder — check whether prompts.py uses `str.replace` or `.format`; if `.format`, double the literal braces). Keep belief examples untouched.

- [ ] **Step 4: Run the round-trip + extraction regression**
```bash
.venv/bin/python -m pytest tests/python/test_mental_state_roundtrip.py tests/python/test_completeness_e2e.py tests/python/test_perception_e2e.py -v
```
Expected: PASS (additive prompt; existing extraction unchanged).

- [ ] **Step 5: Commit**
```bash
git add python/starling/extractor/prompts.py tests/python/test_mental_state_roundtrip.py
git commit -m "$(cat <<'EOF'
feat(P3/SP-A): extraction enrichment — elicit DESIRES/INTENDS/knowledge, not just beliefs

Additive worked examples so the belief pass reliably captures non-belief attitudes
(modality DESIRES/INTENDS carries desires/intentions; predicate knows for knowledge).
Stub-LLM round-trip pins that remember -> mental_state_of buckets them correctly.
Belief examples untouched.

EOF
)"
```

---

## Task 4: Thin gated `mental_state_of` consumer (server)

**Files:**
- Modify: `scripts/starling_tomeval_server.py`
- Create: `tests/python/test_tomeval_server_mentalstate.py`

- [ ] **Step 1: Failing classify + format tests — create `tests/python/test_tomeval_server_mentalstate.py`**
```python
import importlib.util
_spec = importlib.util.spec_from_file_location("tomeval_server", "scripts/starling_tomeval_server.py")
srv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(srv)

def test_classify_targets_bdi_families():
    assert srv._wants_mental_state("What does Xiao Ming most likely do?")           # knowledge/intention
    assert srv._wants_mental_state("Where does Li Hua plan to spend the weekend?")  # desire/plan
    assert not srv._wants_mental_state("What emotion does the friend feel?")        # emotion -> gated off
    assert not srv._wants_mental_state("Where does Anne think the ball is?")        # belief -> existing dump

def test_format_mental_state_compact():
    class R:  # minimal StatementRow stand-in
        def __init__(s, subj, pred, obj): s.subject_id, s.predicate, s.object_value = subj, pred, obj
    class MS:
        beliefs=[R("ball","located_at","box")]; knowledge=[R("keys","knows","drawer")]
        desires=[R("weekend","prefers","outdoors")]; intentions=[]; commitments=[]; preferences=[]
    txt = srv._format_mental_state("Alice", MS())
    assert "Alice" in txt and "drawer" in txt and "outdoors" in txt
```

- [ ] **Step 2: Run → fail** (no `_wants_mental_state` / `_format_mental_state`).

- [ ] **Step 3: Implement in `scripts/starling_tomeval_server.py`** (near `_chain_injection_for`). Read the file first for `mem._rt.adapter` / `mem._core.tenant` usage:
```python
# Question families whose answer turns on a character's BDI+K mental state. Emotion /
# belief-only / non-literal are GATED OFF (mental-state dump is noise there — the ToMBench
# finding) and fall back to the existing dump.
_MENTAL_STATE_CUES = ("plan to", "want", "wants", "intend", "knows", "know that",
                      "most likely do", "decide", "prefer")
_GATE_OFF_CUES = ("emotion", "feel", "feeling", "think the", "thinks the")

def _wants_mental_state(question: str) -> bool:
    q = (question or "").lower()
    if any(c in q for c in _GATE_OFF_CUES):
        return False
    return any(c in q for c in _MENTAL_STATE_CUES)

def _format_mental_state(name: str, ms) -> str:
    def line(label, rows):
        items = [f"{r.subject_id} {r.predicate} {r.object_value}" for r in rows]
        return f"  {name} {label}: " + "; ".join(items) if items else ""
    parts = [line("believes", ms.beliefs), line("knows", ms.knowledge),
             line("wants", ms.desires), line("intends", ms.intentions),
             line("committed", ms.commitments), line("prefers", ms.preferences)]
    return "\n".join(p for p in parts if p)
```
Then add a `_mental_state_injection_for(mem, user_content)` mirroring `_chain_injection_for`: if `_wants_mental_state(user_content)`, call `_core.mental_state_of(mem._rt.adapter, name, mem._core.tenant, "9999-12-31T23:59:59Z")` for each named character found in the story, format, and return a `"[Each character's mental state my memory extracted]\n…"` block; wrap in try/except → "" on failure. Wire it into `_starling_memory_for` alongside the chain injection (append when non-empty). (Character-name discovery: reuse whatever the story/perception dump already enumerates, or the cognizers present in `mem`; keep it best-effort.)

- [ ] **Step 4: Run the unit tests**
```bash
.venv/bin/python -m pytest tests/python/test_tomeval_server_mentalstate.py -v
```
Expected: PASS.

- [ ] **Step 5: Full regression**
```bash
.venv/bin/ctest --test-dir build --output-on-failure | tail -3
.venv/bin/python -m pytest tests/python -q | tail -3
```
Expected: ctest >= 661 (658 + 3), pytest green (all additions pass). Report exact counts.

- [ ] **Step 6: Commit**
```bash
git add scripts/starling_tomeval_server.py tests/python/test_tomeval_server_mentalstate.py
git commit -m "$(cat <<'EOF'
feat(P3/SP-A): thin gated mental_state_of consumer in the in-loop server

For knowledge/desire/intention questions, inject each character's mental_state_of
(beliefs/knowledge/wants/intends/prefers) computed by the CORE primitive; gated OFF for
emotion / belief-only / non-literal (where it is noise) -> existing dump. Server only
classifies + formats; no social-cognition logic (internalize principle).

EOF
)"
```

---

## Final: whole-implementation review + measurement handoff

Dispatch a final code-reviewer over Tasks 1-4 vs the spec (focus: `mental_state_of` correctness, additivity, the server stays thin). Then STOP before push / merge / roadmap / eval re-run (need explicit consent; the eval burns API). Report ctest/pytest counts + the measurement command:
```bash
# server up (bounded-budget env), then re-run ToMBench (per-family Knowledge/Desire/Intention):
cd /Users/jaredguo-mini/develop/ToMEval && .venv/bin/python tasks/ToMBench/run.py --experiment-config cfg_starling_ToMBench.yaml
```

---

## Hard Constraints (every task)

- Core ToM logic = C++ (`src/tom/mentalizing_profile.cpp`); extraction prompt = config data; binding/wrapper/server = thin forwarding.
- Do NOT modify `canonicalize_*`, `what_does_X_think`/`_believe`/`does_X_know` bodies, `perceived_by_json`, or schema/migrations (reuse existing modality/predicate/StatementRow — no new table).
- Cognizer queries are lookup-only; holder isolation reuses P3.a1.
- TDD: failing test → red → minimal impl → green → commit, each task.
- Build from repo root: `configure_build.py --build`; after C++/binding changes add `--python-editable` (+ `cmake --install` if the editable `_core.so` is stale); ctest via `.venv/bin/ctest`.
- explicit-path `git add` (never `.`/`-A`); no `--no-verify`/`--amend`.
- Do NOT push, merge to main, register the roadmap, or re-run the API-burning eval without explicit user consent. Additive → ctest 658 / pytest 649 must not regress.
