# Entity & Theme Grounding Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve extracted cognizer names and theme surfaces to canonical identities at the extraction write path (and symmetrically at the query input), so downstream exact-match grounding stops splitting on surface drift ("Xiao Hong"/"XiaoHong", "the cabbage"/"cabbages").

**Architecture:** A new deterministic `normalize_theme()` (lowercase + leading-article strip + conservative singularization) runs on theme `object_value` **before** the unchanged `canonicalize_object()` (so the hash + stored object_value are on the normalized surface; parity preserved). Cognizer surfaces are resolved to a canonical display name via a thin `resolve_or_register` wrapper over the existing (dormant) `CognizerHub` (`lookup_by_alias` → `register_cognizer` on miss → catch `AliasCollision`), reusing the `cognizers` table; it returns the verbatim first-seen `canonical_name` and registers a space-folded alias so internal-space drift resolves. Both run at 2 write sites + inside the query primitives; downstream SQL exact-joins are untouched.

**Tech Stack:** C++20 (`src/schema/`, `src/cognizer/`, `src/extractor/`, `src/tom/`), GoogleTest, pybind11, pytest. Spec: `docs/superpowers/specs/2026-06-19-entity-theme-grounding-resolution-design.md` (commit `bc5c513`).

**Build/test (repo root `/Users/jaredguo-mini/develop/memory/starling`):**
- Build: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`
- Single C++ test: `.venv/bin/ctest --test-dir build -R <Name> --output-on-failure`
- Full ctest (baseline **638**): `.venv/bin/ctest --test-dir build`
- Editable rebuild before pytest: add `--python-editable`
- pytest (baseline **624**): `.venv/bin/python -m pytest <file> -v`

**Hard constraints (every task):** core logic C++ (`normalize_theme` in `src/schema/`, the cognizer resolver in `src/cognizer/`); Python only binds/forwards + the eval script. **Do NOT modify `canonicalize_object`/`canonicalize_string`** (`src/schema/canonicalize.cpp`) — `normalize_theme` runs on the input *before* it; `tests/python/test_canonicalize_parity.py` must stay green. `normalize_theme` applies **only to entity/string theme object_values** (M8: not int/float/bool/datetime/cognizer/statement kinds). Cognizer resolution stores the verbatim **`canonical_name`** (NOT the UUID5 id) — single-surface name → canonical==surface (idempotent), so existing belief/ToM/B pins stay green (S5). Resolution is **best-effort** (never fail `remember`); the `CognizerHub` writes participate in the caller's open transaction (it manages none of its own). No new migration (reuses `cognizers`, migration 0008). Do not break belief / multi-order-ToM / six-state / conflict / A-episodic / B-perception pins. `perceived_by_json` immutable. TDD red→green→commit; explicit-path `git add` (never `.`/`-A`); no `--no-verify`/`--amend`; rebuild editable after C++/binding changes.

---

## File Structure

| File | Responsibility | Phase |
|------|----------------|-------|
| `include/starling/schema/normalize_theme.hpp` + `src/schema/normalize_theme.cpp` | deterministic theme normalization (lowercase + article-strip + conservative singularize) | 1 |
| `include/starling/cognizer/name_resolver.hpp` + `src/cognizer/name_resolver.cpp` | `fold_internal_spaces`, `resolve_or_register_cognizer` (write), `resolve_cognizer` (query) over `CognizerHub` | 2 |
| `src/extractor/json_parser.cpp` (modify ~:97,:116) | belief write: resolve `subject_id`; `normalize_theme` before canonicalize (str-kind) | 1, 2 |
| `src/extractor/episodic_extractor.cpp` (modify ~:141,:145,:182) | episodic write: resolve `actor` + each participant; `normalize_theme` theme before canonicalize | 1, 2 |
| `src/tom/mentalizing_think.cpp` (modify ~:20) | query: resolve `x`/`observer`, `normalize_theme(theme)` at top | 1, 2 |
| `CMakeLists.txt` (modify) | add `src/schema/normalize_theme.cpp` + `src/cognizer/name_resolver.cpp` to `starling_core` | 1, 2 |
| `tests/cpp/test_normalize_theme.cpp` ; `tests/cpp/test_name_resolver.cpp` ; `tests/cpp/CMakeLists.txt` | unit tests | 1, 2 |
| `tests/python/test_grounding_resolution_e2e.py` | round-trip (drifted name + plural theme → write → query hits) | 2 |
| `scripts/eval_perception_starling.py` (modify) | grounding-rate metric + name-drift/incompleteness decomposition | 3 |

**G1 is resolved (no Task 0 needed):** the Explore confirmed `CognizerHub` exposes `lookup_by_alias(tenant, alias) -> optional<id>` and `register_cognizer(CognizerRegistration) -> Cognizer` (id = UUID5(kind, external_id); throws `AliasCollision{existing_id, alias}` when a normalized alias maps to a different id) + `get(id, tenant) -> optional<Cognizer>` (`.canonical_name` is the verbatim first-seen surface). The resolver composes these (Task 2.1). It is constructed `CognizerHub(SqliteAdapter&)` and writes on the caller's connection (no own transaction).

---

## Phase 1 — Theme normalization

### Task 1.1: `normalize_theme`

**Files:**
- Create: `include/starling/schema/normalize_theme.hpp`, `src/schema/normalize_theme.cpp`
- Modify: `CMakeLists.txt` (add `src/schema/normalize_theme.cpp` to the `target_sources(starling_core PRIVATE …)` block near `src/schema/canonicalize.cpp` ~line 66)
- Test: `tests/cpp/test_normalize_theme.cpp` (+ add to `tests/cpp/CMakeLists.txt` `add_executable(starling_tests …)` near the canonicalize test ~line 30)

- [ ] **Step 1: Write the failing test** — `tests/cpp/test_normalize_theme.cpp`:

```cpp
#include "starling/schema/normalize_theme.hpp"
#include <gtest/gtest.h>
using starling::schema::normalize_theme;

TEST(NormalizeTheme, StripsArticleAndSingularizes) {
    EXPECT_EQ(normalize_theme("the cabbage"), "cabbage");
    EXPECT_EQ(normalize_theme("a backpack"), "backpack");
    EXPECT_EQ(normalize_theme("an apple"), "apple");
    EXPECT_EQ(normalize_theme("cabbages"), "cabbage");      // -s
    EXPECT_EQ(normalize_theme("the cabbages"), "cabbage");  // article + -s
    EXPECT_EQ(normalize_theme("boxes"), "box");             // -es after x
    EXPECT_EQ(normalize_theme("tomatoes"), "tomato");       // -es after o
    EXPECT_EQ(normalize_theme("crayons"), "crayon");
    EXPECT_EQ(normalize_theme("leaves"), "leaf");           // irregular
    EXPECT_EQ(normalize_theme("  Handbag  "), "handbag");   // trim + lowercase
}

TEST(NormalizeTheme, ConservativeFalsePositiveGuards) {
    EXPECT_EQ(normalize_theme("bus"), "bus");       // -us, not a plural
    EXPECT_EQ(normalize_theme("glass"), "glass");   // -ss
    EXPECT_EQ(normalize_theme("boss"), "boss");     // -ss
    EXPECT_EQ(normalize_theme("series"), "series"); // -is stoplist
    EXPECT_EQ(normalize_theme("ball"), "ball");     // no trailing s, unchanged
}
```

Add `test_normalize_theme.cpp` to `tests/cpp/CMakeLists.txt`'s `add_executable(starling_tests …)` list.

- [ ] **Step 2: Run → FAIL** (build error, no such header).

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`

- [ ] **Step 3: Header** — `include/starling/schema/normalize_theme.hpp`:

```cpp
#pragma once
#include <string>
#include <string_view>
namespace starling::schema {
// Deterministic theme-surface normalization for grounding. Runs BEFORE
// canonicalize_object (which is unchanged). Lowercases, strips a leading article
// (the/a/an), and conservatively singularizes. Applied ONLY to entity/string
// theme object_values (NOT numbers/datetimes/refs). Idempotent.
std::string normalize_theme(std::string_view surface);
}  // namespace starling::schema
```

- [ ] **Step 4: Impl** — `src/schema/normalize_theme.cpp`:

```cpp
#include "starling/schema/normalize_theme.hpp"
#include <array>
#include <cctype>
#include <utility>
namespace starling::schema {
namespace {
std::string to_lower(std::string_view s) {
    std::string o; o.reserve(s.size());
    for (unsigned char c : s) o.push_back(static_cast<char>(std::tolower(c)));
    return o;
}
bool ends_with(const std::string& s, std::string_view suf) {
    return s.size() >= suf.size() && s.compare(s.size() - suf.size(), suf.size(), suf) == 0;
}
// irregular plural → singular (lowercase keys)
constexpr std::array<std::pair<std::string_view, std::string_view>, 6> kIrregular = {{
    {"leaves", "leaf"}, {"knives", "knife"}, {"lives", "life"},
    {"wolves", "wolf"}, {"shelves", "shelf"}, {"children", "child"},
}};
// -s endings that are NOT plurals → leave unchanged
bool is_singular_s(const std::string& s) {
    return ends_with(s, "ss") || ends_with(s, "us") || ends_with(s, "is") ||
           s == "bus" || s == "lens" || s == "series" || s == "species" || s == "news";
}
std::string singularize(const std::string& w) {
    for (const auto& [pl, sg] : kIrregular) if (w == pl) return std::string(sg);
    if (w.size() > 3 && ends_with(w, "ies")) return w.substr(0, w.size() - 3) + "y";
    if (w.size() > 3 && ends_with(w, "es")) {
        const std::string stem = w.substr(0, w.size() - 2);
        if (ends_with(stem, "s") || ends_with(stem, "x") || ends_with(stem, "z") ||
            ends_with(stem, "ch") || ends_with(stem, "sh") || ends_with(stem, "o"))
            return stem;
    }
    if (w.size() > 1 && ends_with(w, "s") && !is_singular_s(w)) return w.substr(0, w.size() - 1);
    return w;
}
}  // namespace

std::string normalize_theme(std::string_view surface) {
    std::string s = to_lower(surface);
    while (!s.empty() && std::isspace(static_cast<unsigned char>(s.front()))) s.erase(s.begin());
    while (!s.empty() && std::isspace(static_cast<unsigned char>(s.back()))) s.pop_back();
    for (std::string_view art : {"the ", "a ", "an "}) {
        if (s.size() > art.size() && s.compare(0, art.size(), art) == 0) {
            s = s.substr(art.size());
            while (!s.empty() && std::isspace(static_cast<unsigned char>(s.front()))) s.erase(s.begin());
            break;
        }
    }
    return singularize(s);
}
}  // namespace starling::schema
```

Add `src/schema/normalize_theme.cpp` to `starling_core` in `CMakeLists.txt`.

- [ ] **Step 5: Run → PASS** (`ctest -R NormalizeTheme`), then full ctest 638 stays green.

- [ ] **Step 6: Commit**

```bash
git add include/starling/schema/normalize_theme.hpp src/schema/normalize_theme.cpp CMakeLists.txt tests/cpp/test_normalize_theme.cpp tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(schema): normalize_theme — deterministic theme surface normalization

Lowercase + leading-article strip + conservative singularization (suffix rules
+ irregular map + non-plural stoplist). Runs before the unchanged
canonicalize_object so grounding stops splitting on articles/plurals.

EOF
```

### Task 1.2: wire `normalize_theme` into write + query (str/entity themes only — M8)

**Files:** Modify `src/extractor/json_parser.cpp` (~:99,:116), `src/extractor/episodic_extractor.cpp` (~:144,:145), `src/tom/mentalizing_think.cpp` (~:20). Test: extend `tests/cpp/test_normalize_theme.cpp` or rely on the Phase-2 round-trip; add a focused write-normalization assertion if a stub-LLM C++ path exists.

- [ ] **Step 1: belief write** — in `json_parser.cpp`, `#include "starling/schema/normalize_theme.hpp"`; the object is `object_kind="str"` (hardcoded :110), so normalize it before canonicalize. Replace the canonicalize block (~:116):

```cpp
            s.object_value = schema::normalize_theme(s.object_value);  // M8: str-kind theme
            const schema::CanonicalResult cr =
                schema::canonicalize_object(schema::CanonicalInput{std::string(s.object_value)});
            s.canonical_object_hash = cr.sha256_hex;
```

- [ ] **Step 2: episodic write** — in `episodic_extractor.cpp`, `#include` the header; `object_kind="entity"` here. Normalize `theme` before it's used for both `object_value` and the hash (and the `episodic_events` row, which `events_for_theme` matches on `s.object_value`). Replace (~:144):

```cpp
        stmt.object_value       = schema::normalize_theme(theme);
        const schema::CanonicalResult cr =
            schema::canonicalize_object(schema::CanonicalInput{stmt.object_value});
        stmt.canonical_object_hash = cr.sha256_hex;
```

(Use `stmt.object_value` for the canonicalize input so the hash, the stored object_value, and the `EpisodicEventStore` row all see the identical normalized theme.)

- [ ] **Step 3: query** — in `mentalizing_think.cpp` `what_does_X_think`, `#include` the header; normalize `theme` once at the top (params are `string_view`, so make a `std::string` local and use it for every store call):

```cpp
    auto& conn = adapter.connection();
    const std::string theme_n = schema::normalize_theme(theme);   // match the write side
    store::PerceptionStateStore ps(conn);
    StateBelief out;
    const std::string dim = ps.dim_for_theme(tenant, theme_n, as_of);
    if (dim.empty()) return out;
    // ... replace every `theme` arg below with `theme_n`:
    // ps.last_known(tenant, x, theme_n, dim, as_of), ps.perceived_for_theme(tenant, x, theme_n, as_of),
    // ps.perceived_for_theme(tenant, observer, theme_n, as_of), ps.latest_actual(tenant, theme_n, dim, as_of)
```

- [ ] **Step 4: Build + rebuild editable + run** — `… --build --python-editable …`; full ctest 638 green; full pytest 624 green (the location-FB B tests still pass — their themes like "ball"/"basket" are unaffected by normalize_theme, single-token no-plural).

- [ ] **Step 5: Commit**

```bash
git add src/extractor/json_parser.cpp src/extractor/episodic_extractor.cpp src/tom/mentalizing_think.cpp
git commit -F - <<'EOF'
feat(grounding): apply normalize_theme at write + query (themes only)

object_value normalized before the unchanged canonicalize_object at both write
sites (belief str-kind + episodic entity-kind) and inside what_does_X_think, so
plural/article theme surfaces ground. canonicalize parity untouched.

EOF
```

---

## Phase 2 — Cognizer resolution

### Task 2.1: `name_resolver` over `CognizerHub`

**Files:**
- Create: `include/starling/cognizer/name_resolver.hpp`, `src/cognizer/name_resolver.cpp`
- Modify: `CMakeLists.txt` (add to `starling_core` near `src/cognizer/cognizer_hub.cpp` ~line 111)
- Test: `tests/cpp/test_name_resolver.cpp` (+ `tests/cpp/CMakeLists.txt`)

- [ ] **Step 1: grep the exact `CognizerRegistration` fields + `Cognizer.canonical_name`** in `include/starling/cognizer/cognizer.hpp` (the resolver constructs a `CognizerRegistration` and reads `Cognizer.canonical_name` / `Cognizer.id`). Confirm field names (`kind`, `external_id`, `canonical_name`, `aliases`, `tenant_id`) before writing the impl.

- [ ] **Step 2: Write the failing test** — `tests/cpp/test_name_resolver.cpp` (open a migrated in-memory adapter like `tests/cpp/test_cognizer_hub_register.cpp` does):

```cpp
#include "starling/cognizer/name_resolver.hpp"
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling::cognizer;

TEST(NameResolver, ResolvesInternalSpaceAndCaseDrift) {
    auto adapter = /* open migrated :memory: — mirror test_cognizer_hub_register.cpp */;
    CognizerHub hub(*adapter);
    const char* T = "default";
    // first surface registers; canonical = first-seen verbatim
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "Xiao Hong"), "Xiao Hong");
    // drifted surfaces resolve to the canonical first-seen surface
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "XiaoHong"), "Xiao Hong");
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "xiao hong"), "Xiao Hong");
    // distinct name → distinct
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "Li Lei"), "Li Lei");
    // single-surface idempotent (canonical == surface) — pins-green guarantee
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "Sally"), "Sally");
    EXPECT_EQ(resolve_or_register_cognizer(hub, T, "Sally"), "Sally");
    // query-only resolve: known → canonical, unknown → passthrough (no register)
    EXPECT_EQ(resolve_cognizer(hub, T, "XIAOHONG"), "Xiao Hong");
    EXPECT_EQ(resolve_cognizer(hub, T, "Unknown Person"), "Unknown Person");
}
```

- [ ] **Step 3: Header** — `include/starling/cognizer/name_resolver.hpp`:

```cpp
#pragma once
#include "starling/cognizer/cognizer_hub.hpp"
#include <string>
#include <string_view>
namespace starling::cognizer {
// Remove ALL internal ASCII whitespace + lowercase (stronger than normalize_alias,
// which keeps a single internal space). Used to register a space-folded alias so
// "Xiao Hong" and "XiaoHong" resolve to one entity.
std::string fold_internal_spaces(std::string_view s);
// Write-side: resolve surface to its canonical display name (first-seen surface),
// registering a new entity (kind=human) on miss. Best-effort: returns the raw
// surface on any error. Reuses CognizerHub (cognizers table).
std::string resolve_or_register_cognizer(CognizerHub& hub, std::string_view tenant,
                                         std::string_view surface);
// Query-side: resolve to canonical name if known; passthrough (no register) on miss.
std::string resolve_cognizer(CognizerHub& hub, std::string_view tenant,
                             std::string_view surface);
}  // namespace starling::cognizer
```

- [ ] **Step 4: Impl** — `src/cognizer/name_resolver.cpp` (uses the verified `CognizerHub` API: `lookup_by_alias`, `register_cognizer`, `get`, `AliasCollision`):

```cpp
#include "starling/cognizer/name_resolver.hpp"
#include "starling/cognizer/cognizer.hpp"   // CognizerRegistration, Cognizer, AliasCollision
#include <cctype>
namespace starling::cognizer {

std::string fold_internal_spaces(std::string_view s) {
    std::string o; o.reserve(s.size());
    for (unsigned char c : s) {
        if (std::isspace(c)) continue;                       // drop all whitespace
        o.push_back(static_cast<char>(std::tolower(c)));     // ASCII lower; non-ASCII passes
    }
    return o;
}

namespace {
// Try existing entity by raw surface then by space-folded surface. Returns canonical_name or "".
std::string try_resolve(CognizerHub& hub, std::string_view tenant, std::string_view surface) {
    if (auto id = hub.lookup_by_alias(tenant, surface))
        if (auto cog = hub.get(*id, tenant)) return cog->canonical_name;
    const std::string folded = fold_internal_spaces(surface);
    if (folded != std::string(surface))
        if (auto id = hub.lookup_by_alias(tenant, folded))
            if (auto cog = hub.get(*id, tenant)) return cog->canonical_name;
    return std::string();
}
}  // namespace

std::string resolve_or_register_cognizer(CognizerHub& hub, std::string_view tenant,
                                         std::string_view surface) {
    if (surface.empty()) return std::string(surface);
    if (auto hit = try_resolve(hub, tenant, surface); !hit.empty()) return hit;
    // register new; alias set = {surface, space-folded surface} so future variants resolve.
    CognizerRegistration reg;
    reg.kind          = "human";
    reg.tenant_id     = std::string(tenant);
    reg.external_id   = std::string(surface);
    reg.canonical_name = std::string(surface);
    reg.aliases       = {std::string(surface)};
    const std::string folded = fold_internal_spaces(surface);
    if (folded != std::string(surface)) reg.aliases.push_back(folded);
    try {
        return hub.register_cognizer(reg).canonical_name;   // == surface
    } catch (const AliasCollision& e) {
        if (auto cog = hub.get(e.existing_id, tenant)) return cog->canonical_name;
        return std::string(surface);
    } catch (const std::exception&) {
        return std::string(surface);                        // best-effort
    }
}

std::string resolve_cognizer(CognizerHub& hub, std::string_view tenant,
                             std::string_view surface) {
    if (surface.empty()) return std::string(surface);
    if (auto hit = try_resolve(hub, tenant, surface); !hit.empty()) return hit;
    return std::string(surface);   // unknown → passthrough, no register
}
}  // namespace starling::cognizer
```

Add `src/cognizer/name_resolver.cpp` to `starling_core`. (Confirm `CognizerRegistration` has a `tenant_id` field in Step 1; if the kind is an enum not a string, adapt `reg.kind`.)

- [ ] **Step 5: Run → PASS** (`ctest -R NameResolver`), full ctest 638 green. **Step 6: Commit** (explicit paths: header, cpp, CMakeLists, test).

### Task 2.2: wire resolution into write + query

**Files:** Modify `src/extractor/episodic_extractor.cpp` (actor + each participant), `src/extractor/json_parser.cpp` (subject — but note: json_parser has no adapter/tenant in scope; resolution there happens in `Extractor::run` where the connection + tenant exist — grep `extractor.cpp` for where `subject_id`/holder are finalized, ~:245, and resolve there), `src/tom/mentalizing_think.cpp` (x + observer).

- [ ] **Step 1: episodic write (the load-bearing one for B)** — in `episodic_extractor.cpp`, construct a `CognizerHub hub(adapter_)` once (the extractor holds `conn_`; CognizerHub needs the `SqliteAdapter&` — grep how the extractor reaches the adapter, or thread it; it writes inside the existing `TransactionGuard`). Resolve `actor` and **each participant** before use:

```cpp
        actor = cognizer::resolve_or_register_cognizer(hub, tenant, actor);   // after line ~109
        // ... and resolve each participant in the participants loop (lines ~131-133):
        for (const auto& p : el["participants"]) {
            if (p.is_string())
                participants.push_back(cognizer::resolve_or_register_cognizer(hub, tenant, p.get<std::string>()));
        }
```

Best-effort: the resolver already catches errors and returns the raw surface, so it never breaks `remember`.

- [ ] **Step 2: belief write** — in `Extractor::run` (grep `src/extractor/extractor.cpp` for where the parsed `ExtractedStatement.subject_id` is finalized before `writer.write`, ~:245 area where holder_id is set), resolve `s.subject_id` via a `CognizerHub` built on the run's adapter, inside the write transaction.

- [ ] **Step 3: query** — in `mentalizing_think.cpp`, build `CognizerHub hub(adapter)` and resolve `x` + `observer` (query-side `resolve_cognizer`, no register) at the top, alongside the `normalize_theme` from Task 1.2:

```cpp
    cognizer::CognizerHub hub(adapter);
    const std::string x_n = cognizer::resolve_cognizer(hub, tenant, x);
    const std::string obs_n = observer.empty() ? std::string() : cognizer::resolve_cognizer(hub, tenant, observer);
    // use x_n / obs_n (and theme_n) in every store call
```

- [ ] **Step 4: Build + editable + full ctest 638 / pytest 624 green** (single-surface idempotency keeps the existing belief/ToM/B fixtures — which use names like "Sally"/"Anne" — unchanged). **Step 5: Commit** (explicit paths).

### Task 2.3: round-trip e2e (G2 — write→query symmetry)

**Files:** `tests/python/test_grounding_resolution_e2e.py`.

- [ ] **Step 1: Test** — a stub-LLM narrative whose episodic JSON uses a DRIFTED name across events + a PLURAL theme; assert `what_does_X_think` grounds when queried with a DIFFERENT surface of the same name + the singular theme:

```python
import json, starling
from starling.tom import what_does_X_think

_CANNED = json.dumps([
    {"actor":"Xiao Hong","action":"put","theme":"the cabbages","location":"basket","participants":["Xiao Hong","Li Lei"],"time":None},
    {"actor":"Xiao Hong","action":"leave","theme":"room","location":None,"participants":["Xiao Hong"],"time":None},
    {"actor":"Li Lei","action":"move","theme":"cabbages","location":"box","participants":["Li Lei"],"time":None},
])

def test_drifted_name_and_plural_theme_ground(tmp_path):
    mem = starling.Memory.open(str(tmp_path/"m.db"), agent="narrator",
                               llm=starling.make_stub_llm(default_response=_CANNED))
    mem.remember("...")
    frontier = starling._core.KnowledgeFrontier(mem._rt.adapter)
    # query with a DRIFTED surface ("XiaoHong") + the SINGULAR theme ("cabbage")
    b = what_does_X_think(mem._rt.adapter, frontier, x="XiaoHong", theme="cabbage", tenant_id=mem._core.tenant)
    assert b.has_belief and b.state_value == "basket"   # Xiao Hong left before the move → stale basket
```

- [ ] **Step 2: rebuild editable, run → PASS**; full pytest 624 + ctest 638 green. **Step 3: Commit.**

---

## Phase 3 — Grounding-recall measurement

### Task 3.1: grounding-rate metric + name-drift/incompleteness decomposition (M5)

**Files:** Modify `scripts/eval_perception_starling.py` (`run_probe`, the main loop, `write_report`, and the fixture self-test call site).

- [ ] **Step 1:** thread a third return value through `run_probe`: `(correct, grounded, detail)` where `grounded = belief.has_belief`. On a `no belief` miss, run the **decomposition query** — does any `OCCURRED` event for the *normalized* theme exist? — via the connection in scope:

```python
    # in run_probe, on the `no belief` path, classify the miss:
    from starling.schema import normalize_theme  # bind it (Task 3 may add the binding) OR inline the SQL theme
    import sqlite3
    # query whether an OCCURRED event exists for the normalized theme (any cognizer)
    raw = adapter.connection().raw_path if hasattr(adapter, ...) else None  # grep how to reach the sqlite conn
    # SQL: SELECT 1 FROM episodic_events e JOIN statements s ON s.id=e.statement_id
    #      AND s.tenant_id=e.tenant_id WHERE e.tenant_id=? AND s.object_value=? AND s.modality='occurred' LIMIT 1
    # event_exists True  → name-drift / resolution-addressable
    # event_exists False → extraction-incompleteness (next spec)
```

Grep the cleanest way to run that SQL from the eval (the adapter/connection accessor, or add a small bound `events_for_theme`/`has_occurred_event` helper — `EpisodicEventStore::events_for_theme` is C++-only today, so either bind it or issue raw SQL on a `sqlite3.connect(db)` to the same file).

- [ ] **Step 2:** accumulate `grounded` + `name_drift` + `incompleteness` counters in the main loop and in `run_fixture_self_test` (update BOTH `run_probe` call sites). Extend `write_report` to emit `grounding-rate` and the decomposition rows. Keep `precision` as-is.

- [ ] **Step 3:** the metric is deterministic-self-testable (the fixture path exercises it without API). Do NOT run the 100-probe real eval in this task — document the on-demand command (the funded tokenkey.dev creds from `~/.zshrc`: `eval "$(grep -E '^export (DEEPSEEK_API_KEY|DEEPSEEK_BASE_URL)=' ~/.zshrc)" && OPENAI_API_KEY="$DEEPSEEK_API_KEY" OPENAI_BASE_URL="$DEEPSEEK_BASE_URL/v1" .venv/bin/python scripts/eval_perception_starling.py --corpus tests/data/eval_tom_bench/full.jsonl --model deepseek-v4-pro`). **No fixed lift is promised** (G3) — the real run, when funded, measures it. Commit (explicit paths).

---

## Self-Review

**1. Spec coverage** (spec §1–8 → task):
- §3.1 cognizer resolution (CognizerHub reuse / G1) → Task 2.1 (`resolve_or_register`/`resolve` over the verified API) + 2.2 wiring (incl. participants — G4). ✓
- §3.2 theme normalization before canonicalize, M8 entity/str-only → Task 1.1 + 1.2. ✓
- §3.3 touch-point table → 1.2 (theme: 2 write + query) + 2.2 (cognizer: subject/actor/participants + x/observer). ✓
- §5 parity (canonicalize unchanged) → Task 1.x never edits canonicalize; the parity test is in the regression gate. ✓
- §6 best-effort → resolver catches all errors → raw surface; episodic resolution inside the existing TransactionGuard. ✓
- §7 two-track testing → deterministic units (1.1, 2.1) + round-trip (2.3) + grounding-recall (3.1); G3 no-fixed-target. ✓ §8 constraints → header. ✓

**2. Placeholder scan:** Phase 1 + Task 2.1 carry full code. The remaining lookups are explicit greps with the reason named: `CognizerRegistration` fields (2.1 Step 1), how the extractor reaches the `SqliteAdapter&` for the Hub (2.2 Step 1), where `Extractor::run` finalizes subject_id (2.2 Step 2), and the eval's connection accessor + theme-existence SQL (3.1). Each names exactly what to find. The `test_cognizer_hub_register.cpp` / `test_canonicalize` references are concrete existing files to mirror for seeding.

**3. Type consistency:** `normalize_theme(std::string_view)->std::string` identical across header/impl/write-sites/query. `resolve_or_register_cognizer`/`resolve_cognizer`/`fold_internal_spaces` signatures identical across header/impl/tests/wiring. The resolver returns `canonical_name` (a display string, NOT the UUID id) everywhere — so stored `subject_id` stays a name, single-surface idempotent (S5). `what_does_X_think` uses `theme_n`/`x_n`/`obs_n` locals consistently. No new migration / no schema type. ✓

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-19-entity-theme-grounding-resolution.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks.

**2. Inline Execution** — execute in this session via executing-plans, batched with checkpoints.

**Which approach?**
