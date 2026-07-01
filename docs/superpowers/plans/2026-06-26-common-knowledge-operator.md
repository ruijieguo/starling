# Common-Knowledge Operator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Internalize a deterministic `is_common_knowledge(group, theme)` operator — common knowledge among a group = the group's latest perceived theme-event was co-witnessed by ALL members (public establishment); private tell / subset observation → not CK.

**Architecture:** New C++ core primitive in `src/tom/` reusing `PerceptionStateStore.perceived_for_theme` + the source_event_id co-witness intersection pattern from `what_does_X_think_chain`. Thin pybind11 binding + thin ToMEval server injection (gated). Validation via a constructed synthetic `CommonKnowledge` eval (public vs private establishment, direct CK question). Extraction layer is UNCHANGED (public claim already extracts as a tell to all-present; private told as a tell to one).

**Tech Stack:** C++20, SQLite (perception_state table), GoogleTest (ctest), pybind11, pytest, FastAPI server (scripts/starling_tomeval_server.py), deepseek-v4-pro via tokenkey.dev for the measure phase.

## Global Constraints

- Core logic is C++ only (`src/tom/mentalizing_common_knowledge.cpp`); bindings + server are thin forwarders; extraction is UNCHANGED.
- Reuse `perceived_for_theme` / `dim_for_theme` / the co-witness intersection — do NOT reinvent. `perceived_for_theme` and the `PerceptionStateRow` shape are immutable.
- Do NOT break existing pinned tests (canonicalize parity / perception / six-state / conflict / grounding / chain / shared_with / room-scoped perception / observation-gate). Baseline: ctest 695, pytest 715.
- TDD: write the failing test first, see it fail, implement minimally, see it pass, commit.
- Build from repo root: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --python-editable --build-dir build`. C++/binding changes need `--python-editable`. ctest: `.venv/bin/ctest --test-dir build`.
- New C++ changed lines must pass the CI clang-tidy gate (`.clang-tidy` WarningsAsErrors:'*'): brace every single-statement if/for/while body; variable names ≥3 chars (loop counters i/j/k/it exempt); use `.contains()` for set membership; explicit `!= nullptr` for pointer-in-condition; `// NOLINTNEXTLINE(check)` for unavoidable patterns (e.g. sqlite `reinterpret_cast`).
- explicit-path `git add` (never `./` or `-A`); NO `--no-verify` / `--amend`.
- Do NOT push/merge main, register roadmap, or burn API (measure) without explicit user consent. The measure phase (Task 5) is run by the controller with the user present.
- Honest framing: this is a lower-confidence bet. The compute is deterministic and the reuse is clean, but the GAIN depends on whether deepseek actually fails on complex public/private sequences. If deepseek can read the public/private distinction, this lands ≈ baseline (like the surface operators). Exit = measure, no promised lift.

---

### Task 1: C++ operator `is_common_knowledge` + ctest

**Files:**
- Modify: `include/starling/tom/mentalizing.hpp` (add `CommonKnowledgeResult` struct + declaration near `shared_with`, after line 97)
- Create: `src/tom/mentalizing_common_knowledge.cpp`
- Modify: `src/CMakeLists.txt` (add the new .cpp to the library — find where `mentalizing_chain.cpp` / `mentalizing_shared.cpp` are listed and add the new file alongside)
- Create + register: `tests/cpp/test_mentalizing_common_knowledge.cpp`
- Modify: `tests/cpp/CMakeLists.txt` (register the new test exe alongside `test_mentalizing_chain`)

**Interfaces:**
- Consumes: `store::PerceptionStateStore.perceived_for_theme(tenant, cognizer, theme, as_of) -> std::vector<PerceptionStateRow>` (each row has `.source_event_id`, `.position` (long long), `.state_value`, `.state_dim`); `.dim_for_theme(tenant, theme, as_of) -> std::string`; `schema::normalize_theme(theme)`; `cognizer::resolve_cognizer(hub, tenant, name)` via `cognizer::CognizerHub`.
- Produces: `CommonKnowledgeResult{ bool is_ck; std::string ck_value; std::string establishing_event_id; }` and `is_common_knowledge(adapter, frontier, group, theme, tenant, as_of)`.

- [ ] **Step 1: Declare the result struct + function in the header**

In `include/starling/tom/mentalizing.hpp`, after the `shared_with` declaration (line 97), add:

```cpp
// 7. Common knowledge among a group. X's current state is common knowledge among G
//    iff the LATEST theme-event any member of G perceived was co-witnessed by ALL of
//    G (a public establishment). A private tell / subset observation -> not CK. CK is
//    computed WITHIN G (group mutual belief), not the global physical state.
struct CommonKnowledgeResult {
    bool is_ck = false;                  // current state is common knowledge among G
    std::string ck_value;                // last all-co-witnessed value (== latest if is_ck)
    std::string establishing_event_id;   // source_event_id of that last public event
};
CommonKnowledgeResult is_common_knowledge(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    const std::vector<std::string>& group,
    std::string_view theme,
    std::string_view tenant,
    std::string_view as_of);
```

- [ ] **Step 2: Write the failing tests**

Create `tests/cpp/test_mentalizing_common_knowledge.cpp`. Copy the `open_migrated` + `seed_event` helpers verbatim from `tests/cpp/test_mentalizing_chain.cpp:18-58` (same fixture). Then:

```cpp
using starling::tom::mentalizing::is_common_knowledge;

// All of A/B/C enter room1 and witness A's move ball->L. No later event.
static std::unique_ptr<starling::persistence::SqliteAdapter> scene_public(const char* T) {
    auto a = open_migrated();
    seed_event(*a, T, "e1", "A", "enter", "room1", "", R"(["A"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "e2", "B", "enter", "room1", "", R"(["B"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "e3", "C", "enter", "room1", "", R"(["C"])", 3, "2026-01-01T00:00:03Z");
    seed_event(*a, T, "m1", "A", "move",  "ball",  "L", R"(["A"])", 4, "2026-01-01T00:00:04Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);
    return a;
}

TEST(IsCommonKnowledge, PublicEstablishmentIsCK) {
    auto a = scene_public("ck1");
    starling::cognizer::KnowledgeFrontier f(*a);
    auto r = is_common_knowledge(*a, f, {"A", "B", "C"}, "ball", "ck1", "2026-01-02T00:00:00Z");
    EXPECT_TRUE(r.is_ck);
    EXPECT_EQ(r.ck_value, "L");
}

TEST(IsCommonKnowledge, PrivateTellBreaksCK) {
    // Public L1 to all, then D privately tells A ball->L2 (only A learns it).
    auto a = scene_public("ck2");
    seed_event(*a, "ck2", "t1", "D", "tell", "ball", "L2", R"(["D","A"])", 5, "2026-01-01T00:00:05Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct("ck2");
    starling::cognizer::KnowledgeFrontier f(*a);
    auto r = is_common_knowledge(*a, f, {"A", "B", "C"}, "ball", "ck2", "2026-01-02T00:00:00Z");
    EXPECT_FALSE(r.is_ck);             // A's latest (L2) is not co-witnessed by B/C
    EXPECT_EQ(r.ck_value, "L");        // last all-co-witnessed value
}

TEST(IsCommonKnowledge, SubsetMoveBreaksCK) {
    // Public L1; A leaves; B moves ball->L2 (A does not see it).
    auto a = scene_public("ck3");
    seed_event(*a, "ck3", "l1", "A", "leave", "room1", "",  R"(["A"])", 5, "2026-01-01T00:00:05Z");
    seed_event(*a, "ck3", "m2", "B", "move",  "ball",  "L2", R"(["B"])", 6, "2026-01-01T00:00:06Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct("ck3");
    starling::cognizer::KnowledgeFrontier f(*a);
    auto r = is_common_knowledge(*a, f, {"A", "B", "C"}, "ball", "ck3", "2026-01-02T00:00:00Z");
    EXPECT_FALSE(r.is_ck);             // B/C's latest (L2) not witnessed by A
}

TEST(IsCommonKnowledge, NonGroupPrivateMoveDoesNotBreakGroupCK) {
    // A/B/C/D all see ball@L1; A/B/C leave; D moves ball->L2 (only D, not in queried G).
    auto a = open_migrated();
    const char* T = "ck4";
    seed_event(*a, T, "e1", "A", "enter", "room1", "", R"(["A"])", 1, "2026-01-01T00:00:01Z");
    seed_event(*a, T, "e2", "B", "enter", "room1", "", R"(["B"])", 2, "2026-01-01T00:00:02Z");
    seed_event(*a, T, "e3", "C", "enter", "room1", "", R"(["C"])", 3, "2026-01-01T00:00:03Z");
    seed_event(*a, T, "e4", "D", "enter", "room1", "", R"(["D"])", 4, "2026-01-01T00:00:04Z");
    seed_event(*a, T, "m1", "A", "move",  "ball",  "L1", R"(["A"])", 5, "2026-01-01T00:00:05Z");
    seed_event(*a, T, "l1", "A", "leave", "room1", "",   R"(["A"])", 6, "2026-01-01T00:00:06Z");
    seed_event(*a, T, "l2", "B", "leave", "room1", "",   R"(["B"])", 7, "2026-01-01T00:00:07Z");
    seed_event(*a, T, "l3", "C", "leave", "room1", "",   R"(["C"])", 8, "2026-01-01T00:00:08Z");
    seed_event(*a, T, "m2", "D", "move",  "ball",  "L2", R"(["D"])", 9, "2026-01-01T00:00:09Z");
    starling::cognizer::PerceptionReconstructor(a->connection()).reconstruct(T);
    starling::cognizer::KnowledgeFrontier f(*a);
    auto r = is_common_knowledge(*a, f, {"A", "B", "C"}, "ball", T, "2026-01-02T00:00:00Z");
    EXPECT_TRUE(r.is_ck);             // among {A,B,C}, latest co-witnessed is L1; D's L2 is outside G
    EXPECT_EQ(r.ck_value, "L1");
}

TEST(IsCommonKnowledge, SingletonGroupKnows) {
    auto a = scene_public("ck5");
    starling::cognizer::KnowledgeFrontier f(*a);
    auto r = is_common_knowledge(*a, f, {"A"}, "ball", "ck5", "2026-01-02T00:00:00Z");
    EXPECT_TRUE(r.is_ck);
    EXPECT_EQ(r.ck_value, "L");
}
```

Register in `tests/cpp/CMakeLists.txt`: copy the block that defines `test_mentalizing_chain` and duplicate it for `test_mentalizing_common_knowledge` (same `target_link_libraries` + `gtest_discover_tests`).

- [ ] **Step 3: Run the tests to verify they FAIL**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build 2>&1 | tail -5`
Expected: COMPILE ERROR (`is_common_knowledge` undefined) — that is the failing state.

- [ ] **Step 4: Implement the operator**

Create `src/tom/mentalizing_common_knowledge.cpp`:

```cpp
// is_common_knowledge: common knowledge among a group G. X's current state is CK
// among G iff the LATEST theme-event any member of G perceived was co-witnessed by
// ALL of G (public establishment). Reuses the source_event_id co-witness intersection
// of what_does_X_think_chain, scoped to the perceptions of G's members.
#include "starling/tom/mentalizing.hpp"
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/name_resolver.hpp"
#include "starling/schema/normalize_theme.hpp"
#include "starling/store/perception_state_store.hpp"

#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace starling::tom::mentalizing {

CommonKnowledgeResult is_common_knowledge(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,
    const std::vector<std::string>& group,
    std::string_view theme,
    std::string_view tenant,
    std::string_view as_of) {
    (void)frontier;  // parity with what_does_X_think_chain (reserved for access checks)
    CommonKnowledgeResult out;
    if (group.empty()) {
        return out;
    }

    auto& conn = adapter.connection();
    const std::string theme_n = schema::normalize_theme(theme);
    cognizer::CognizerHub hub(adapter);
    std::vector<std::string> group_n;
    group_n.reserve(group.size());
    for (const auto& member : group) {
        group_n.push_back(cognizer::resolve_cognizer(hub, tenant, member));
    }

    store::PerceptionStateStore perc(conn);
    const std::string dim = perc.dim_for_theme(tenant, theme_n, as_of);
    if (dim.empty()) {
        return out;  // theme never perceived
    }

    // Per-member set of perceived source_event_ids (this dim only); plus the group's
    // highest-position event (g_max) and a position/value lookup per event.
    std::vector<std::unordered_set<std::string>> member_sets;
    member_sets.reserve(group_n.size());
    std::unordered_map<std::string, std::pair<long long, std::string>> event_info;
    long long g_max_pos = -1;
    std::string g_max_event;

    for (const auto& member : group_n) {
        auto rows = perc.perceived_for_theme(tenant, member, theme_n, as_of);
        std::unordered_set<std::string> seen;
        for (const auto& row : rows) {
            if (row.state_dim != dim) {
                continue;
            }
            seen.insert(row.source_event_id);
            event_info[row.source_event_id] = {row.position, row.state_value};
            if (row.position > g_max_pos) {
                g_max_pos = row.position;
                g_max_event = row.source_event_id;
            }
        }
        member_sets.push_back(std::move(seen));
    }
    if (g_max_event.empty()) {
        return out;  // no member perceived the theme in this dim
    }

    auto co_witnessed_by_all = [&member_sets](const std::string& event_id) {
        for (const auto& seen : member_sets) {
            if (!seen.contains(event_id)) {
                return false;
            }
        }
        return true;
    };

    // is_ck: the group's latest theme-event was co-witnessed by ALL members.
    out.is_ck = co_witnessed_by_all(g_max_event);

    // ck_value / establishing: the highest-position event co-witnessed by all of G
    // (the last public establishment; == g_max when is_ck).
    long long cw_max_pos = -1;
    for (const auto& [event_id, info] : event_info) {
        if (info.first > cw_max_pos && co_witnessed_by_all(event_id)) {
            cw_max_pos = info.first;
            out.ck_value = info.second;
            out.establishing_event_id = event_id;
        }
    }
    return out;
}

}  // namespace starling::tom::mentalizing
```

Add `src/tom/mentalizing_common_knowledge.cpp` to `src/CMakeLists.txt` next to `mentalizing_chain.cpp`.

- [ ] **Step 5: Run the tests to verify they PASS + no regressions**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --python-editable --build-dir build && .venv/bin/ctest --test-dir build 2>&1 | grep -E "tests passed|tests failed" | tail -1`
Expected: `100% tests passed, 0 tests failed out of 700` (695 baseline + 5 new).

- [ ] **Step 6: Commit**

```bash
git add include/starling/tom/mentalizing.hpp src/tom/mentalizing_common_knowledge.cpp src/CMakeLists.txt tests/cpp/test_mentalizing_common_knowledge.cpp tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(tom): is_common_knowledge operator (group co-witness common knowledge)

is_common_knowledge(group, theme): X is common knowledge among G iff the
group's latest perceived theme-event was co-witnessed by ALL members
(public establishment). Private tell / subset observation -> not CK.
Reuses perceived_for_theme + the source_event_id co-witness intersection
of what_does_X_think_chain. +5 ctest.

EOF
```

---

### Task 2: Python binding

**Files:**
- Modify: `bindings/python/bind_08_tom.cpp` (add `CommonKnowledgeResult` class + `is_common_knowledge` def, after the `what_does_X_think_chain` def ~line 204)
- Create: `tests/python/test_common_knowledge_binding.py`

**Interfaces:**
- Consumes: the C++ `is_common_knowledge` from Task 1.
- Produces: `starling._core.is_common_knowledge(adapter, frontier, group, theme, tenant, as_of) -> CommonKnowledgeResult` with `.is_ck`, `.ck_value`, `.establishing_event_id`.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_common_knowledge_binding.py`. Mirror an existing perception/chain binding test for the harness (find one that builds a memory + reconstructs, e.g. `tests/python/test_chain_belief_roundtrip.py`, and reuse its memory-setup helper). The assertion:

```python
def test_is_common_knowledge_public_vs_private(ck_memory_public):
    # ck_memory_public: A/B/C all witness ball->L (public). Helper builds + reconstructs.
    core = ck_memory_public
    r = core.is_common_knowledge(core.adapter, core.frontier, ["A", "B", "C"], "ball", core.tenant, "2026-01-02T00:00:00Z")
    assert r.is_ck is True
    assert r.ck_value == "L"
```

(If no reusable Python perception-fixture exists, this test may be deferred to a ctest-only validation and the binding round-trip asserted via a minimal `_core` smoke that the symbol exists and returns the POD — match whatever the existing `what_does_X_think_chain` binding test does; do NOT invent a new fixture style.)

- [ ] **Step 2: Run to verify FAIL** — `AttributeError: ... has no attribute 'is_common_knowledge'`.

- [ ] **Step 3: Add the binding**

In `bindings/python/bind_08_tom.cpp`, after the `what_does_X_think_chain` def (line ~204):

```cpp
    py::class_<starling::tom::mentalizing::CommonKnowledgeResult>(m, "CommonKnowledgeResult")
        .def_readonly("is_ck",                 &starling::tom::mentalizing::CommonKnowledgeResult::is_ck)
        .def_readonly("ck_value",              &starling::tom::mentalizing::CommonKnowledgeResult::ck_value)
        .def_readonly("establishing_event_id", &starling::tom::mentalizing::CommonKnowledgeResult::establishing_event_id);

    m.def("is_common_knowledge",
        [](starling::persistence::SqliteAdapter& adapter,
           starling::cognizer::KnowledgeFrontier& frontier,
           const std::vector<std::string>& group, const std::string& theme,
           const std::string& tenant, const std::string& as_of) {
            py::gil_scoped_release release;
            return starling::tom::mentalizing::is_common_knowledge(
                adapter, frontier, group, theme, tenant, as_of);
        },
        py::arg("adapter"), py::arg("frontier"), py::arg("group"), py::arg("theme"),
        py::arg("tenant"), py::arg("as_of"),
        "Common knowledge among a group: is the theme's current state co-witnessed by "
        "ALL of G (public)? Returns a CommonKnowledgeResult.");
```

- [ ] **Step 4: Rebuild + run** — `... configure_build.py --build --python-editable --build-dir build && .venv/bin/python -m pytest tests/python/test_common_knowledge_binding.py -q`. Expected: PASS.

- [ ] **Step 5: Full pytest regression** — `.venv/bin/python -m pytest tests/python -q 2>&1 | tail -1`. Expected: `716 passed` (715 + 1) or the deferred-binding equivalent, 0 failed.

- [ ] **Step 6: Commit** (explicit paths; same trailer).

---

### Task 3: ToMEval server injection + competence gate

**Files:**
- Modify: `scripts/starling_tomeval_server.py` (add a CK-question parser + injection alongside `_chain_injection_for`; wire into `_starling_memory_for` before the chain; reuse the `STARLING_CHAIN_ONLY` gate)
- Modify/Create: a server test mirroring however the chain parser is unit-tested (search for an existing `_parse_chain_question` test; add `_parse_ck_question` cases there or in a sibling test file)

**Interfaces:**
- Consumes: `_core.is_common_knowledge`.
- Produces: a CK injection string for "is it common knowledge among {…} that the X is in Y" questions; silent otherwise.

- [ ] **Step 1: Write the failing parser test**

Find the existing test that exercises `_parse_chain_question` (grep `_parse_chain_question` under `tests/`). Add cases for a new `_parse_ck_question(question) -> (group: list[str], theme: str) | None`:

```python
def test_parse_ck_question():
    from scripts.starling_tomeval_server import _parse_ck_question
    g, t = _parse_ck_question("Is it common knowledge among Alice, Bob and Carol that the ball is in the box?")
    assert g == ["Alice", "Bob", "Carol"]
    assert t == "ball"
    assert _parse_ck_question("Where is the ball?") is None
```

- [ ] **Step 2: Run to verify FAIL** — `ImportError: cannot import name '_parse_ck_question'`.

- [ ] **Step 3: Implement the parser + injection + gate**

In `scripts/starling_tomeval_server.py`, near `_parse_chain_question` (~line 143), add:

```python
import re
_CK_RX = re.compile(
    r"\bcommon knowledge among\s+(.+?)\s+that\s+the\s+([A-Za-z][\w ]*?)\s+is\b", re.I)

def _parse_ck_question(question: str):
    """Return (group, theme) for a 'common knowledge among G that the X is ...' question, else None."""
    m = _CK_RX.search(question or "")
    if not m:
        return None
    raw_group = re.split(r",|\band\b", m.group(1))
    group = [g.strip() for g in raw_group if g.strip()]
    if len(group) < 2:
        return None
    if any(len(member.split()) != 1 for member in group):  # single-token names only
        return None
    return group, m.group(2).strip()

def _ck_injection_for(mem, user_content: str) -> str:
    parsed = _parse_ck_question(user_content)
    if not parsed:
        return ""
    group, theme = parsed
    try:
        frontier = _core.KnowledgeFrontier(mem._rt.adapter)
        ck = _core.is_common_knowledge(
            mem._rt.adapter, frontier, group, theme, mem._core.tenant, "9999-12-31T23:59:59Z")
    except Exception:
        print("[CK-EXC]\n" + traceback.format_exc(), file=sys.stderr, flush=True)
        return ""
    nested = ", ".join(group)
    verdict = ("IS common knowledge" if ck.is_ck else "is NOT common knowledge")
    return (
        "Starling's deterministic ToM engine computed: among {" + nested + "}, the "
        + theme + " location " + verdict
        + (" (commonly known value: " + ck.ck_value + ")." if ck.is_ck else " (some member's "
           "latest information was not co-witnessed by all).")
        + " Use this as the primary answer.")
```

Then in `_starling_memory_for` (the injection stack, ~line 388), compute the CK injection and prefer it like the chain. Order: try `chain` first, then `ck`, then the rest. With `STARLING_CHAIN_ONLY` set, return the CK injection too when it fires:

```python
        chain = _chain_injection_for(mem, user_content)
        ck = _ck_injection_for(mem, user_content)
        if os.environ.get("STARLING_CHAIN_ONLY") == "1" and not chain and not ck:
            return ""
        dump = _memory_dump(db_path, mem._core.tenant)
        extra = (chain or ck
                 or _belief_digest_for(mem, db_path, user_content)
                 or _mental_state_injection_for(mem, user_content)
                 or _faux_pas_injection_for(mem, user_content))
        return (dump + "\n\n" + extra) if extra else dump
```

- [ ] **Step 4: Run the parser test to verify PASS** — `.venv/bin/python -m pytest <the test file> -q`.

- [ ] **Step 5: Syntax + import smoke** — `.venv/bin/python -c "import ast; ast.parse(open('scripts/starling_tomeval_server.py').read()); print('OK')"`.

- [ ] **Step 6: Commit** (explicit paths; same trailer).

---

### Task 4: CommonKnowledge synthetic eval generator

**Files:**
- Create: `scripts/build_common_knowledge_corpus.py` (generates the synthetic eval; mirror `scripts/build_tombench_full_corpus.py` for the output shape ToMEval consumes)
- Create: `tests/python/test_common_knowledge_corpus.py` (gold self-consistency)

**Interfaces:**
- Produces: a parquet/jsonl with columns `story`, `question`, `answer`, `meta` (matching what ToMEval's `run_standardized_qa_task` expects — inspect `build_tombench_full_corpus.py` for the exact schema).

- [ ] **Step 1: Write the failing gold-consistency test**

Create `tests/python/test_common_knowledge_corpus.py`:

```python
def test_ck_gold_matches_construction():
    from scripts.build_common_knowledge_corpus import generate_item
    # public construction -> gold "yes"
    pub = generate_item(seed=1, public=True)
    assert pub["answer"].lower().startswith("yes")
    assert "common knowledge among" in pub["question"].lower()
    # private construction -> gold "no"
    priv = generate_item(seed=1, public=False)
    assert priv["answer"].lower().startswith("no")
```

- [ ] **Step 2: Run to verify FAIL** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the generator**

`scripts/build_common_knowledge_corpus.py` exposes `generate_item(seed, public) -> dict` and a `main()` that writes N items. Each item:
- Pick a room, an object, 3-5 agents (A,B,C[,D,E]), and 1-2 distractor objects.
- All agents enter the room. Distractor moves happen (witnessed by all — noise).
- The TARGET object's final establishment:
  - `public=True`: an agent moves the object to L with all of {A,B,C} present (co-witnessed) → gold "yes".
  - `public=False`: either (a) an agent privately tells one of {A,B,C} the object is at L (others absent/not recipients), or (b) one of {A,B,C} leaves, then the object moves to L witnessed only by the rest → gold "no".
- Question: `f"Is it common knowledge among {A}, {B} and {C} that the {object} is in {L}?"`.
- `answer`: "yes" / "no" per construction.
- `meta`: `{"public": public, "group": [A,B,C], "object": object, "location": L}`.

Use a fixed seed RNG (pass timestamps/seeds in; do NOT call unseeded random in a way that breaks reproducibility). Match the parquet/jsonl columns + `meta.ability`/`meta.lang` convention from `build_tombench_full_corpus.py` so ToMEval's loader accepts it.

- [ ] **Step 4: Run the gold test to verify PASS** + generate a small corpus (`python scripts/build_common_knowledge_corpus.py --n 20 --out /tmp/ck_smoke.jsonl`) and eyeball 3 items for story/question/gold coherence.

- [ ] **Step 5: Commit** (explicit paths; same trailer).

---

### Task 5: Measure (controller only — needs user consent, burns API)

> Run by the controller with the user present. NOT a subagent task.

- [ ] Generate the full CommonKnowledge corpus (e.g. 300-500 items, balanced public/private).
- [ ] Add ToMEval configs `cfg_starling_CK.yaml` (points at the local server, model `starling-deepseek`, `STARLING_CHAIN_ONLY=1`) + `cfg_deepseek_CK.yaml` (raw baseline). Mirror the HiToM configs.
- [ ] Run baseline + Starling-in-loop (server via C++ adapter / HTTP-1.1; baseline at max_workers ≤24, watch for tail connection stalls).
- [ ] Pair the predictions, compute overall + by-public/private delta, McNemar. Parse the boxed/yes-no answer.
- [ ] **Honest report:** state the measured delta. If ≈ baseline, deepseek can read public/private — report it as a boundary finding (like the surface operators), not a failure. Do NOT promise a lift up front.

---

## Self-Review

**Spec coverage:** operator (Task 1) ✓; binding (Task 2) ✓; server inject + gate (Task 3) ✓; eval generator (Task 4) ✓; measure (Task 5) ✓; extraction-unchanged (stated in Global Constraints + Task 3 reuses existing tell extraction) ✓; the 5 ctest scenarios from spec §7 (Task 1 Step 2) ✓.

**Placeholder scan:** Task 2 Step 1 notes a fixture fallback (acceptable — it points to the existing pattern to follow rather than inventing one); all code steps contain complete code. No TBD/TODO.

**Type consistency:** `CommonKnowledgeResult{is_ck, ck_value, establishing_event_id}` is identical across header (Task 1.1), implementation (Task 1.4), binding (Task 2.3). `is_common_knowledge(adapter, frontier, group, theme, tenant, as_of)` signature matches across all tasks. `_parse_ck_question -> (group, theme)` and `_ck_injection_for` match across Task 3.
