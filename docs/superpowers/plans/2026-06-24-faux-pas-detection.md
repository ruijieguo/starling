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

# Faux-Pas Detection (SP-B) Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Internalize a core `detect_faux_pas` operator that computes the faux-pas precondition (an ignorance asymmetry: a present cognizer doesn't know a fact a co-present cognizer knows) from `does_X_know`'s tri-value — perception-based, holder-robust — and inject it into the in-loop server.

**Architecture:** A new core C++ `detect_faux_pas` scans cast × facts, classifying each cognizer's knowledge of each fact via `does_X_know` (ignorant=Unknowable, knower=NotKnown∪FullKnowledge); emits candidates where both non-empty. A thin gated server consumer injects them for Non-Literal questions.

**Tech Stack:** C++20 (`src/tom/`, gtest, `does_X_know`/`KnowledgeFrontier`/`FactKey`), pybind11, Python (pytest), FastAPI server.

**Spec:** `docs/superpowers/specs/2026-06-24-faux-pas-detection-design.md` (commit `8e52d2e`).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `include/starling/tom/mentalizing.hpp` | declare `FauxPasCandidate` + `detect_faux_pas` | Modify |
| `src/tom/mentalizing_fauxpas.cpp` | the operator (cast × facts × does_X_know) | Create |
| `CMakeLists.txt` | build source | Modify (`starling_core`) |
| `tests/cpp/test_faux_pas.cpp` | ctest (asymmetry contract) | Create |
| `tests/cpp/CMakeLists.txt` | test source | Modify |
| `bindings/python/bind_08_tom.cpp` | `FauxPasCandidate` POD + `.def` | Modify |
| `python/starling/tom/primitives.py` | thin wrapper | Modify |
| `tests/python/test_faux_pas_roundtrip.py` | stub-LLM round-trip (viability gate) + smoke | Create |
| `scripts/starling_tomeval_server.py` | thin gated consumer | Modify |
| `tests/python/test_tomeval_server_fauxpas.py` | server classify + format | Create |

---

## Task 0: Confirm green baseline (controller)

- [ ] Run from repo root: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build && .venv/bin/ctest --test-dir build | tail -3 && .venv/bin/python -m pytest tests/python -q | tail -3`. Expected: ctest 661, pytest 653 passed. If red, stop + report.

---

## Task 1: `detect_faux_pas` core operator (C++)

**Files:** Create `src/tom/mentalizing_fauxpas.cpp` + `tests/cpp/test_faux_pas.cpp`; Modify `include/starling/tom/mentalizing.hpp`, `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`.

**Reference (READ FIRST):**
- `tests/cpp/test_mentalizing.cpp:256-319` — the does_X_know tri-state seed pattern: `make_adapter()`, `StmtSpec`+`insert_statement(db, spec)`, `insert_engram(db, id, tenant)`, `KnowledgeFrontier frontier(*a)`, and `frontier.record_explicit_told(tenant, {cognizers}, stmt_id, engram_id, time, conn)` to make an engram visible to specific cognizers. Copy these helpers into the new test file.
- `src/tom/mentalizing_know.cpp` — `does_X_know(adapter, frontier, x, FactKey, tenant, as_of)` returns `FullKnowledge` (X asserted pos) / `NotKnown` (evidence engram visible to X) / `Unknowable` (not visible). `FactKey{subject_kind, subject_id, predicate, canonical_object_hash}` (`mentalizing.hpp:17`).
- `include/starling/store/perception_state_store.hpp` — the cast source (distinct `cognizer_id`). Grep it / `SqliteMetaStore` for how to list distinct cognizers + distinct statement facts; if no helper, a raw `SELECT DISTINCT` is fine in the operator.

- [ ] **Step 1: Declare in `mentalizing.hpp`** (after `SharedFact`, and the function after `does_X_know`):
```cpp
// A faux-pas precondition: `ignorant` doesn't know `unknown_fact`, which co-present
// `who_knows` cognizers DO know. The structural setup of a faux pas (the speaker may
// then say something inappropriate). Semantic sensitivity is NOT judged here.
struct FauxPasCandidate {
    std::string ignorant;
    retrieval::StatementRow unknown_fact;
    std::vector<std::string> who_knows;
};

// Scan cast × established facts: for each fact F, classify each cast cognizer via
// does_X_know (Unknowable -> ignorant; NotKnown/FullKnowledge -> knower). Emit a
// candidate per ignorant cognizer when at least one cast cognizer knows F. Cast =
// distinct cognizers in perception_state; facts = distinct (subject_kind,subject_id,
// predicate,canonical_object_hash) over consolidated statements.
std::vector<FauxPasCandidate> detect_faux_pas(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view tenant,
    std::string_view as_of);
```

- [ ] **Step 2: Write the failing ctest** `tests/cpp/test_faux_pas.cpp`. Copy `make_adapter`, `StmtSpec`, `insert_statement`, `insert_engram` from `tests/cpp/test_mentalizing.cpp:29-145`. Build the asymmetry directly via the frontier (the cast is also derived from perception_state — seed it via direct `perception_state` inserts or reuse `test_mentalizing_think.cpp`'s `seed_event`+`PerceptionReconstructor`; simplest is to also assert the cast is read correctly):
```cpp
// ... includes: mentalizing.hpp, knowledge_frontier.hpp, perception_state_store.hpp,
// migration_runner.hpp, sqlite_adapter.hpp, sqlite_handles.hpp, gtest, sqlite3 ...
using starling::tom::mentalizing::detect_faux_pas;
using starling::tom::mentalizing::FauxPasCandidate;
using starling::cognizer::KnowledgeFrontier;

// Seed perception_state so the cast = {A,B,C}. Mirror PerceptionStateStore::upsert
// (see tests/cpp/test_mentalizing_think.cpp lines ~99-107 for a direct upsert) — one
// location row per cognizer is enough to make them appear as cast members.
static void seed_cast_member(starling::persistence::SqliteAdapter& a, const char* T,
                             const char* cog) {
    starling::store::PerceptionStateStore ps(a.connection());
    starling::store::PerceptionStateRow row;
    row.tenant_id = T; row.cognizer_id = cog; row.theme_id = "stage";
    row.state_dim = "location"; row.state_value = "room";
    row.observed_at = "2026-05-26T08:00:00Z"; row.position = 0;
    row.source_event_id = std::string("seed-") + cog;
    ps.upsert(row);
}

TEST(DetectFauxPas, IgnorantAsymmetryEmitsCandidate) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();
    const char* T = "t1";
    for (const char* c : {"A", "B", "C"}) seed_cast_member(*a, T, c);

    // Fact F: bob lost (canon_hash hash-lost), evidence engram engram-F.
    insert_engram(db, "engram-F", T);
    StmtSpec f; f.id = "f1"; f.holder_id = "narrator"; f.subject_kind = "cognizer";
    f.subject_id = "bob"; f.predicate = "lost"; f.canon_hash = "hash-lost"; f.polarity = "pos";
    f.evidence_json = R"([{"engram_ref":"engram-F","content_hash":"x"}])";
    insert_statement(db, f);

    // A and C saw F (engram-F visible) -> NotKnown (knower). B did NOT -> Unknowable (ignorant).
    KnowledgeFrontier frontier(*a);
    frontier.record_explicit_told(T, {"A", "C"}, "stmt-told", "engram-F",
                                  "2026-05-26T09:00:00Z", a->connection());

    auto cands = detect_faux_pas(*a, frontier, T, "2026-05-26T12:00:00Z");
    // Exactly one ignorant (B); who_knows includes A and C.
    ASSERT_EQ(cands.size(), 1u);
    EXPECT_EQ(cands[0].ignorant, "B");
    EXPECT_EQ(cands[0].unknown_fact.subject_id, "bob");
    EXPECT_EQ(cands[0].unknown_fact.predicate, "lost");
    std::vector<std::string> wk = cands[0].who_knows;
    EXPECT_NE(std::find(wk.begin(), wk.end(), "A"), wk.end());
    EXPECT_NE(std::find(wk.begin(), wk.end(), "C"), wk.end());
}

TEST(DetectFauxPas, NoAsymmetryWhenAllKnowOrNoneKnow) {
    auto a = make_adapter();
    sqlite3* db = a->connection().raw();
    const char* T = "t2";
    for (const char* c : {"A", "B"}) seed_cast_member(*a, T, c);
    insert_engram(db, "engram-G", T);
    StmtSpec g; g.id = "g1"; g.holder_id = "narrator"; g.subject_id = "bob";
    g.predicate = "lost"; g.canon_hash = "hash-lost2"; g.polarity = "pos";
    g.evidence_json = R"([{"engram_ref":"engram-G","content_hash":"x"}])";
    insert_statement(db, g);
    KnowledgeFrontier frontier(*a);
    frontier.record_explicit_told(T, {"A", "B"}, "stmt-told", "engram-G",
                                  "2026-05-26T09:00:00Z", a->connection());   // both know
    auto cands = detect_faux_pas(*a, frontier, T, "2026-05-26T12:00:00Z");
    EXPECT_TRUE(cands.empty()) << "no ignorant -> no candidate";
}
```
Confirm `record_explicit_told`'s exact signature from `include/starling/cognizer/knowledge_frontier.hpp` (and `PerceptionStateStore`/`PerceptionStateRow` fields from its header); adjust the seeds if they differ. Add `test_faux_pas.cpp` to `tests/cpp/CMakeLists.txt`'s `starling_tests`.

- [ ] **Step 3: Build → expect link failure. Then implement** `src/tom/mentalizing_fauxpas.cpp`:
```cpp
// detect_faux_pas — the faux-pas precondition (ignorance asymmetry) via does_X_know.
#include "starling/tom/mentalizing.hpp"
#include "starling/store/sqlite_meta_store.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include <sqlite3.h>
#include <set>
#include <string>
#include <vector>

namespace starling::tom::mentalizing {

namespace {
// Distinct cognizers present in perception_state (the cast).
std::vector<std::string> cast_of(persistence::SqliteAdapter& a, std::string_view tenant) {
    std::vector<std::string> out;
    const char* sql = "SELECT DISTINCT cognizer_id FROM perception_state WHERE tenant_id=?1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(a.connection().raw(), sql, -1, &raw, nullptr) != SQLITE_OK) return out;
    persistence::StmtHandle h{raw};
    sqlite3_bind_text(raw, 1, tenant.data(), (int)tenant.size(), SQLITE_TRANSIENT);
    while (sqlite3_step(raw) == SQLITE_ROW)
        out.emplace_back(reinterpret_cast<const char*>(sqlite3_column_text(raw, 0)));
    return out;
}
}  // namespace

std::vector<FauxPasCandidate> detect_faux_pas(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    std::string_view tenant,
    std::string_view as_of) {
    std::vector<FauxPasCandidate> out;
    const auto cast = cast_of(adapter, tenant);
    if (cast.size() < 2) return out;

    // Distinct facts: one representative StatementRow per (subject_kind,subject_id,
    // predicate,canonical_object_hash). Reuse SqliteMetaStore to fetch consolidated rows.
    store::SqliteMetaStore meta(adapter.connection());
    store::StatementFilter f;
    f.tenant_id = std::string(tenant);
    f.as_of_iso8601 = std::string(as_of);
    const auto rows = meta.query_statements(f);

    std::set<std::string> seen;
    for (const auto& r : rows) {
        const std::string key = r.subject_kind + "|" + r.subject_id + "|" + r.predicate +
                                "|" + r.canonical_object_hash;
        if (!seen.insert(key).second) continue;        // one representative per fact
        FactKey fk{r.subject_kind, r.subject_id, r.predicate, r.canonical_object_hash};
        std::vector<std::string> knowers, ignorant;
        for (const auto& x : cast) {
            const auto k = does_X_know(adapter, frontier, x, fk, tenant, as_of);
            if (k == KnowsResult::Unknowable) ignorant.push_back(x);
            else                              knowers.push_back(x);   // NotKnown / FullKnowledge
        }
        if (!ignorant.empty() && !knowers.empty())
            for (const auto& x : ignorant) out.push_back({x, r, knowers});
    }
    return out;
}

}  // namespace starling::tom::mentalizing
```
Confirm `SqliteMetaStore`/`StatementFilter`/`query_statements` usage from `src/tom/mentalizing_believe.cpp`. Add `src/tom/mentalizing_fauxpas.cpp` to `starling_core` in the root `CMakeLists.txt` (beside `mentalizing_believe.cpp`).

- [ ] **Step 4: Build + run** `.venv/bin/ctest --test-dir build -R DetectFauxPas --output-on-failure` → 2 PASS. If `record_explicit_told`/`PerceptionStateStore` signatures differ, fix the seeds to match (that alignment is the contract).
- [ ] **Step 5: Regression** `.venv/bin/ctest --test-dir build -R "Mentalizing|Knowledge|Perception" --output-on-failure` → existing pass.
- [ ] **Step 6: Commit** (explicit paths):
```bash
git add include/starling/tom/mentalizing.hpp src/tom/mentalizing_fauxpas.cpp CMakeLists.txt tests/cpp/test_faux_pas.cpp tests/cpp/CMakeLists.txt
git commit -m "feat(P3/SP-B): detect_faux_pas — ignorance-asymmetry core operator"   # full body with trailer
```

---

## Task 2: Bind + wrap `detect_faux_pas`

**Files:** Modify `bindings/python/bind_08_tom.cpp`, `python/starling/tom/primitives.py`; Create `tests/python/test_faux_pas_roundtrip.py` (smoke now).

- [ ] **Step 1: Failing smoke** — `tests/python/test_faux_pas_roundtrip.py`:
```python
def test_faux_pas_bound():
    from starling import _core
    assert hasattr(_core, "detect_faux_pas")
    c = _core.FauxPasCandidate
    for f in ("ignorant", "unknown_fact", "who_knows"):
        assert hasattr(c, f)
    from starling.tom.primitives import detect_faux_pas
```
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Bind** in `bind_08_tom.cpp` (after the `mental_state_of` `.def` from SP-A; mirror the `MentalState` POD + GIL-released `.def`):
```cpp
    py::class_<starling::tom::mentalizing::FauxPasCandidate>(m, "FauxPasCandidate")
        .def_readonly("ignorant",     &starling::tom::mentalizing::FauxPasCandidate::ignorant)
        .def_readonly("unknown_fact", &starling::tom::mentalizing::FauxPasCandidate::unknown_fact)
        .def_readonly("who_knows",    &starling::tom::mentalizing::FauxPasCandidate::who_knows);

    m.def("detect_faux_pas",
        [](starling::persistence::SqliteAdapter& adapter,
           starling::cognizer::KnowledgeFrontier& frontier,
           const std::string& tenant, const std::string& as_of) {
            std::vector<starling::tom::mentalizing::FauxPasCandidate> out;
            { py::gil_scoped_release release;
              out = starling::tom::mentalizing::detect_faux_pas(adapter, frontier, tenant, as_of); }
            return out;
        },
        py::arg("adapter"), py::arg("frontier"), py::arg("tenant"), py::arg("as_of"),
        "Faux-pas preconditions: ignorance asymmetries (ignorant + unknown_fact + who_knows).");
```
- [ ] **Step 4: Wrap** in `primitives.py` (mirror `mental_state_of`):
```python
def detect_faux_pas(
    adapter,
    frontier,
    *,
    tenant_id: str = "default",
    as_of: Optional[datetime] = None,
):
    """Faux-pas preconditions: ignorance asymmetries (a present cognizer ignorant of a
    fact a co-present cognizer knows). Returns a list of FauxPasCandidate."""
    as_of_iso = _iso_now_or_convert(as_of)
    return _core.detect_faux_pas(adapter, frontier, tenant_id, as_of_iso)
```
- [ ] **Step 5: Rebuild editable + smoke** `... configure_build.py --build --python-editable --build-dir build && .venv/bin/python -m pytest tests/python/test_faux_pas_roundtrip.py::test_faux_pas_bound -v` → PASS (cmake --install if stale).
- [ ] **Step 6: Commit** (`bindings/python/bind_08_tom.cpp python/starling/tom/primitives.py tests/python/test_faux_pas_roundtrip.py`).

---

## Task 3: Round-trip — VIABILITY GATE (does a real `remember` populate the frontier?)

**Files:** Modify `tests/python/test_faux_pas_roundtrip.py`.

This is the make-or-break integration test: the ctest proved the operator LOGIC with a hand-seeded frontier, but `detect_faux_pas` only works in production if a real `remember()` populates the `KnowledgeFrontier` (presence/told) per perceived fact. If it doesn't, every cognizer is `Unknowable` → no candidates → the operator is inert.

- [ ] **Step 1: Add the round-trip test** (stub-LLM, mirror `test_mental_state_roundtrip.py`'s `make_stub_llm`+`mem.tick()` pattern). The canned episodic JSON: A, B, C enter; B leaves; then a result fact is established (witnessed by A, C only):
```python
import json, starling
from starling.tom.primitives import detect_faux_pas

_CANNED = json.dumps([
    {"actor": "A", "action": "enter", "theme": "hall", "location": None, "participants": ["A","B","C"], "time": None},
    {"actor": "B", "action": "leave", "theme": "hall", "location": None, "participants": ["B"], "time": None},
    {"actor": "A", "action": "find", "theme": "result", "location": "lost", "participants": ["A","C"], "time": None},
])

def test_roundtrip_flags_absent_speaker(tmp_path):
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="narrator",
                               llm=starling.make_stub_llm(default_response=_CANNED))
    mem.remember("A, B and C entered the hall. B left. A and C saw the result: lost.")
    mem.tick()
    frontier = starling._core.KnowledgeFrontier(mem._rt.adapter)
    cands = detect_faux_pas(mem._rt.adapter, frontier, tenant_id=mem._core.tenant)
    igns = {c.ignorant for c in cands}
    assert "B" in igns, f"expected B ignorant; candidates={[(c.ignorant, c.unknown_fact.predicate) for c in cands]}"
```
- [ ] **Step 2: Run + interpret.** `.venv/bin/python -m pytest tests/python/test_faux_pas_roundtrip.py::test_roundtrip_flags_absent_speaker -v`
  - **PASS** → a real `remember` populates the frontier; the operator is viable end-to-end. Proceed.
  - **FAIL with empty candidates** → the reconstructor/remember does NOT populate the `KnowledgeFrontier` presence per perceived fact (so `does_X_know` is `Unknowable` for everyone). This is the spec §10-risk-2 viability finding. Investigate whether any subscriber writes presence_log on remember (`grep -rn "record_presence\|presence_log" src/`); if nothing populates it in the remember path, report **DONE_WITH_CONCERNS**: the operator is logically correct but inert in production without a frontier-population step — do NOT hack the operator. Surface to the controller for a decision (a follow-up to populate the frontier from perception, or gate the operator off).
- [ ] **Step 3: Commit** (`tests/python/test_faux_pas_roundtrip.py`) — whether PASS or documented-concern.

---

## Task 4: Thin gated server consumer

**Files:** Modify `scripts/starling_tomeval_server.py`; Create `tests/python/test_tomeval_server_fauxpas.py`.

- [ ] **Step 1: Failing tests** — `tests/python/test_tomeval_server_fauxpas.py`:
```python
import importlib.util
_spec = importlib.util.spec_from_file_location("s", "scripts/starling_tomeval_server.py")
srv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(srv)

def test_classify_faux_pas():
    assert srv._wants_faux_pas("Does anyone say something inappropriate in this story?")
    assert not srv._wants_faux_pas("Where does Anne think the ball is?")
    assert not srv._wants_faux_pas("What emotion does the friend feel?")

def test_format_faux_pas():
    class C:
        class F: subject_id, predicate, object_value = "result", "lost", "lost"
        ignorant = "B"; unknown_fact = F(); who_knows = ["A","C"]
    txt = srv._format_faux_pas([C()])
    assert "B" in txt and "lost" in txt and "A" in txt
```
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** in `scripts/starling_tomeval_server.py` (mirror SP-A's `_mental_state_injection_for`: tick, build `KnowledgeFrontier(mem._rt.adapter)`, call `_core.detect_faux_pas`, format; gate; wire into `_starling_memory_for` with precedence **chain > mental_state > faux_pas**, mutually exclusive):
```python
_FAUX_PAS_CUES = ("inappropriate", "faux pas", "say something", "said something", "不当", "失礼")

def _wants_faux_pas(question: str) -> bool:
    q = (question or "").lower()
    if any(c in q for c in _GATE_OFF_CUES):   # reuse SP-A's emotion/belief gate-off
        return False
    return any(c in q for c in _FAUX_PAS_CUES)

def _format_faux_pas(cands) -> str:
    lines = []
    for c in cands[:5]:
        f = c.unknown_fact
        lines.append(f"  {c.ignorant} does NOT know [{f.subject_id} {f.predicate} {f.object_value}] "
                     f"(was absent), but {', '.join(c.who_knows)} do.")
    return "\n".join(lines)

def _faux_pas_injection_for(mem, user_content: str) -> str:
    if not _wants_faux_pas(user_content):
        return ""
    try:
        mem.tick()
        frontier = _core.KnowledgeFrontier(mem._rt.adapter)
        cands = _core.detect_faux_pas(mem._rt.adapter, frontier, mem._core.tenant,
                                      "9999-12-31T23:59:59Z")
    except Exception:
        print("[FAUXPAS-EXC]\n" + traceback.format_exc(), file=sys.stderr, flush=True)
        return ""
    body = _format_faux_pas(cands)
    if not body:
        return ""
    return ("[Faux-pas preconditions my memory computed (an ignorant party may commit a "
            "faux pas if they speak)]\n" + body)
```
Wire: `extra = chain or _mental_state_injection_for(mem, user_content) or _faux_pas_injection_for(mem, user_content)` in `_starling_memory_for`. (Confirm `_GATE_OFF_CUES` exists from SP-A; if a faux-pas question contains a gate-off word, faux_pas cues should still win — verify the test passes, adjust `_wants_faux_pas` to not early-return on gate-off if needed.)
- [ ] **Step 4: Run unit tests** → PASS.
- [ ] **Step 5: Full regression** `.venv/bin/ctest --test-dir build | tail -3 && .venv/bin/python -m pytest tests/python -q | tail -3`. Expected ctest 663 (661+2), pytest green; `test_tomeval_server_chain.py` + `test_tomeval_server_mentalstate.py` still pass (precedence intact).
- [ ] **Step 6: Commit** (`scripts/starling_tomeval_server.py tests/python/test_tomeval_server_fauxpas.py`).

---

## Final: review + measurement handoff

Dispatch a final code-reviewer (focus: operator correctness, additivity, server thinness, the Task-3 viability finding). STOP before push / merge / roadmap / eval re-run (need consent). Report ctest/pytest counts + whether the Task-3 round-trip showed the frontier is populated (the operator's production viability). Measurement command (when consented):
```bash
# server up (bounded-budget env), then ToMBench (per-family Non-Literal):
cd /Users/jaredguo-mini/develop/ToMEval && .venv/bin/python tasks/ToMBench/run.py --experiment-config cfg_starling_ToMBench.yaml
```

---

## Hard Constraints (every task)
- Core logic = C++ (`src/tom/mentalizing_fauxpas.cpp`); binding/wrapper/server = thin forwarding.
- Do NOT modify `does_X_know`/`find_misalignment`/`what_does_X_*` bodies, `canonicalize_*`, `perceived_by_json`, or schema/migrations (reuse existing primitives/FactKey/StatementRow — no new table).
- TDD red→green→commit; build from repo root; after C++/binding changes add `--python-editable` (+ `cmake --install` if stale); ctest via `.venv/bin/ctest`.
- explicit-path `git add` (never `.`/`-A`); no `--no-verify`/`--amend`.
- Do NOT push, merge, register roadmap, or re-run the API eval without explicit consent. Additive → ctest 661 / pytest 653 must not regress.
