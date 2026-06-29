# Faux-Pas Detection (SP-B) Implementation Plan

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
