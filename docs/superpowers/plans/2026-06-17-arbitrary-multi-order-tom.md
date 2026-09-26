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

# Arbitrary Multi-Order Theory-of-Mind Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** ✅ IMPLEMENTED 2026-06-17 — all 6 phases landed (commits `c530c80`..`a4884b2` on main); ctest 599/599, pytest 614 passed/13 skipped; final review APPROVED. The `- [ ]` checkboxes below record the original task breakdown.

**Goal:** Lift Starling's hard 3rd-order ToM cap so nested-belief representation, production, and recall support arbitrary depth, bounded only by a cycle guard + configurable soft ceilings.

**Architecture:** Replace the hard `nesting_depth > 2` throw with a write-time ancestor-walk (cycle detection + soft ceiling `max_nesting_depth`, default 32); decouple the production limiter's `causation_chain_len` from `nesting_depth`; generalize the depth estimator and the explicit production path to arbitrary order while the auto path mirrors observed beliefs ungated; make recall fully unwrap the N-deep chain via a bounded recursive CTE. Zero schema migration (`nesting_depth` is already an unbounded `INTEGER`).

**Tech Stack:** C++20 core (`src/tom`, `include/starling/tom`), SQLite (WAL), pybind11 bindings, GoogleTest (ctest), pytest. Spec: `docs/superpowers/specs/2026-06-17-arbitrary-multi-order-tom-design.md` (commit 4ebfb8c).

---

## File Structure

| File | Responsibility | Phase |
|------|----------------|-------|
| `include/starling/tom/nesting_depth_writer.hpp` | `NestingCycle` type, updated `NestingDepthOverflow`, `compute_nesting_depth` signature (+`max_depth`) | 1 |
| `src/tom/nesting_depth_writer.cpp` | ancestor-walk: cycle detection + soft ceiling + depth | 1 |
| `tests/cpp/test_nesting_depth_writer.cpp` | depth 3/4/5 accepted, soft-cap overflow, cycle rejected | 1 |
| `src/tom/second_order.cpp` | decouple `causation_chain_len`; auto path ungated mirroring (drop `skip_nested_source`); explicit `persist_meta_belief` depth-N | 2, 4 |
| `include/starling/tom/depth_estimator.hpp` + `src/tom/depth_estimator.cpp` | `count_to_depth` → arbitrary monotone order | 3 |
| `include/starling/tom/mentalizing.hpp` + `src/tom/mentalizing_more.cpp` | `what_does_X_think_Y_believes` recursive CTE + `.chain` | 5 |
| `tests/cpp/test_tom_second_order.cpp` | estimator order ≥3, explicit depth-N gate, auto deep mirror | 3, 4 |
| `tests/cpp/test_mentalizing*.cpp` | recursive recall returns all levels | 5 |
| `tests/python/test_tom2_e2e.py` | 3-deep multi-holder chain end-to-end | 5 |
| `include/starling/tom/limiting.hpp` + config path | `max_nesting_depth` / `max_cascade_depth` runtime config | 6 |
| `docs/design/subsystems_design/09_tom.md` | cognitive-cap → arbitrary-order + guards revision | 6 |

**Phase ordering:** 1 (representation guard) is the foundation and must land first; 2 (decouple) + 3 (estimator) pave the way; 4 (production) depends on 1–3; 5 (recall) depends on 1 (needs deep rows to recall) and is exercised by the e2e after 4; 6 (config + spec doc) closes out. Each phase exits independently green and mergeable.

**Build / test commands (run from repo root `/Users/jaredguo-mini/develop/memory/starling`):**
- Configure + build C++: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`
- Run a C++ test: `ctest --test-dir build -R <TestName> --output-on-failure`
- Full ctest: `ctest --test-dir build --output-on-failure`
- Rebuild editable `_core` after C++/binding changes (REQUIRED before pytest): `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build --python-editable`
- Run pytest: `.venv/bin/python -m pytest tests/python/<file> -v`

**Standing constraints (every task):** core logic C++ only (Python = binding forwarding); new/changed bindings issuing recursive SQL use `gil_scoped_release`; subscriber code uses SAVEPOINT not BEGIN IMMEDIATE; explicit-path `git add` (never `.`/`-A`); no `--no-verify`/`--amend`. Each phase must not break ctest 589 / pytest 609 except the spec §7 assertions intentionally changed here.

---

## Phase 1 — Representation guard (cycle + soft ceiling) — FULL DETAIL

Replaces the hard `nesting_depth > 2` throw. `compute_nesting_depth` becomes an
ancestor walk that computes depth, detects a pre-existing cycle, and enforces a
configurable soft ceiling. Cycles are structurally impossible on the append-only
write path (a fresh id cannot be its own ancestor), so the `NestingCycle` check is
a defensive guard against corrupted/cyclic data and the primitive that also bounds
the walk; the soft ceiling is the operative depth guard.

### Task 1.1: `NestingCycle` type + updated overflow + signature

**Files:**
- Modify: `include/starling/tom/nesting_depth_writer.hpp`

- [ ] **Step 1: Write the failing test** (in `tests/cpp/test_nesting_depth_writer.cpp`, add near the top after includes)

```cpp
TEST(NestingDepthWriter, NestingCycleTypeCarriesId) {
    starling::tom::NestingCycle e("stmt-42");
    EXPECT_EQ(e.cycle_id, "stmt-42");
    EXPECT_NE(std::string(e.what()).find("cycle"), std::string::npos);
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`
Expected: FAIL — compile error, `NestingCycle` undeclared.

- [ ] **Step 3: Implement** — replace `include/starling/tom/nesting_depth_writer.hpp` lines 8-24 with:

```cpp
class NestingDepthOverflow : public std::runtime_error {
public:
    int computed_depth;
    explicit NestingDepthOverflow(int d)
        : std::runtime_error(
              "nesting_depth exceeds configured max_nesting_depth (runaway guard)"),
          computed_depth(d) {}
};

class NestingCycle : public std::runtime_error {
public:
    std::string cycle_id;  // the statement id revisited while walking ancestors
    explicit NestingCycle(std::string id)
        : std::runtime_error("nested-belief object_value chain contains a cycle"),
          cycle_id(std::move(id)) {}
};

namespace nesting_depth_writer {
    // Default soft ceiling on nesting depth (Phase 6 wires this to runtime config).
    // 0 ⇒ unbounded (the cycle guard still applies).
    inline constexpr int kDefaultMaxNestingDepth = 32;

    // Returns 0 if object_kind != "statement". Otherwise walks the object_value
    // ancestor chain to a flat (non-statement) leaf, returning the chain length
    // (== parent.nesting_depth + 1). Throws NestingCycle if an id repeats on the
    // walk; throws NestingDepthOverflow if the chain length exceeds max_depth
    // (when max_depth > 0); throws std::runtime_error if a parent is missing.
    int compute_nesting_depth(
        persistence::Connection& conn,
        const extractor::ExtractedStatement& s,
        int max_depth = kDefaultMaxNestingDepth);
}
```
(add `#include <string>` to the header includes.)

- [ ] **Step 4: Run to verify it passes**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build && ctest --test-dir build -R NestingDepthWriter --output-on-failure`
Expected: `NestingCycleTypeCarriesId` PASSES; pre-existing `NestingDepthWriter` tests still compile (some will fail until Task 1.3 — that is expected and fixed there).

- [ ] **Step 5: Commit**

```bash
git add include/starling/tom/nesting_depth_writer.hpp tests/cpp/test_nesting_depth_writer.cpp
git commit -F - <<'EOF'
feat(tom): NestingCycle type + soft-ceiling signature for nesting_depth_writer

EOF
```

### Task 1.2: ancestor-walk computes depth + detects cycle + soft ceiling

**Files:**
- Modify: `src/tom/nesting_depth_writer.cpp`
- Test: `tests/cpp/test_nesting_depth_writer.cpp`

- [ ] **Step 1: Write the failing tests** — REPLACE the existing depth-3 overflow test block (`tests/cpp/test_nesting_depth_writer.cpp:146-165`, the `NestingDepthOverflow`/`computed_depth == 3` case) with:

```cpp
TEST(NestingDepthWriter, AcceptsDepthThreeFourFiveUnderDefaultCeiling) {
    auto a = open_fresh();             // existing helper in this file
    sqlite3* db = a->raw_handle();     // existing helper pattern; match file's accessor
    seed_chain(db, 5);                 // helper below: flat leaf L0 then nested L1..L5
    // a fresh statement pointing at the depth-4 row computes depth 5, accepted (<32)
    auto s = make_nested_stmt("L4");   // helper: ExtractedStatement object_kind=statement, object_value="L4"
    EXPECT_EQ(starling::tom::nesting_depth_writer::compute_nesting_depth(*conn(a), s), 5);
}

TEST(NestingDepthWriter, SoftCeilingOverflowThrows) {
    auto a = open_fresh();
    sqlite3* db = a->raw_handle();
    seed_chain(db, 3);
    auto s = make_nested_stmt("L2");   // would compute depth 3
    EXPECT_THROW(
        starling::tom::nesting_depth_writer::compute_nesting_depth(*conn(a), s, /*max_depth=*/2),
        starling::tom::NestingDepthOverflow);
}

TEST(NestingDepthWriter, CycleInExistingChainThrows) {
    auto a = open_fresh();
    sqlite3* db = a->raw_handle();
    // seed two statement-rows whose object_value point at each other (corrupt cycle)
    seed_cyclic_pair(db, "C1", "C2");  // C1.object_value=C2, C2.object_value=C1
    auto s = make_nested_stmt("C1");
    EXPECT_THROW(
        starling::tom::nesting_depth_writer::compute_nesting_depth(*conn(a), s),
        starling::tom::NestingCycle);
}
```

> NOTE for the implementer: reuse this test file's existing fixtures/helpers
> (`open_fresh`, the connection accessor, the seed helpers). If `seed_chain`,
> `make_nested_stmt`, `seed_cyclic_pair` don't exist, add them next to the
> existing seeders, mirroring the `INSERT INTO statements(...)` column list used
> elsewhere in this file (38-field row; `object_kind='statement'`,
> `object_value=<parent id>` for nested, `object_kind='str'` for the flat leaf).

- [ ] **Step 2: Run to verify they fail**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build && ctest --test-dir build -R NestingDepthWriter --output-on-failure`
Expected: FAIL — `AcceptsDepthThreeFourFive` throws `NestingDepthOverflow` under the old `>2` code; cycle test loops or mis-throws.

- [ ] **Step 3: Implement** — replace the body of `compute_nesting_depth` in `src/tom/nesting_depth_writer.cpp` (lines 11-46) with the ancestor walk:

```cpp
int compute_nesting_depth(
        persistence::Connection& conn,
        const extractor::ExtractedStatement& s,
        int max_depth) {
    if (s.object_kind != "statement") {
        return 0;
    }
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "SELECT object_kind, object_value FROM statements "
            "WHERE id = ? AND tenant_id = ?",
            -1, &raw, nullptr) != SQLITE_OK) {
        throw std::runtime_error(
            std::string("nesting_depth_writer: prepare failed: ") +
            sqlite3_errmsg(db));
    }
    persistence::StmtHandle h(raw);

    std::unordered_set<std::string> seen;
    std::string cur = s.object_value;
    int depth = 0;
    while (true) {
        depth += 1;
        if (max_depth > 0 && depth > max_depth) {
            throw NestingDepthOverflow(depth);
        }
        if (!seen.insert(cur).second) {
            throw NestingCycle(cur);
        }
        sqlite3_reset(h.get());
        sqlite3_clear_bindings(h.get());
        sqlite3_bind_text(h.get(), 1, cur.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(h.get(), 2, s.holder_tenant_id.c_str(), -1, SQLITE_TRANSIENT);
        const int rc = sqlite3_step(h.get());
        if (rc == SQLITE_DONE) {
            throw std::runtime_error(
                "nesting_depth_writer: parent statement not found in tenant " +
                s.holder_tenant_id + ": " + cur);
        }
        if (rc != SQLITE_ROW) {
            throw std::runtime_error(
                std::string("nesting_depth_writer: step failed: ") +
                sqlite3_errmsg(db));
        }
        const auto* okind = sqlite3_column_text(h.get(), 0);
        const std::string parent_kind =
            okind ? reinterpret_cast<const char*>(okind) : "";
        if (parent_kind != "statement") {
            break;  // reached a flat leaf; depth is the chain length
        }
        const auto* oval = sqlite3_column_text(h.get(), 1);
        cur = oval ? reinterpret_cast<const char*>(oval) : "";
    }
    return depth;
}
```
(add `#include <unordered_set>` to the .cpp includes.)

- [ ] **Step 4: Run to verify they pass**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build && ctest --test-dir build -R NestingDepthWriter --output-on-failure`
Expected: all `NestingDepthWriter` tests PASS.

- [ ] **Step 5: Regression — full ctest**

Run: `ctest --test-dir build --output-on-failure`
Expected: all pass EXCEPT any `test_tom_second_order` case that still expects depth-2-only behavior — those are updated in Phase 4. If a non-Phase-4 test regresses, stop and investigate (likely a fixture sharing the old `>2` assumption).

- [ ] **Step 6: Commit**

```bash
git add src/tom/nesting_depth_writer.cpp tests/cpp/test_nesting_depth_writer.cpp
git commit -F - <<'EOF'
feat(tom): nesting_depth_writer ancestor-walk — arbitrary depth + cycle guard + soft ceiling

Replaces the hard nesting_depth>2 throw (P2.a cognitive cap) with a walk that
computes depth, rejects cyclic chains (NestingCycle), and enforces the
configurable soft ceiling (default 32; 0=unbounded). Foundation for arbitrary
multi-order ToM. See docs/superpowers/specs/2026-06-17-arbitrary-multi-order-tom-design.md.

EOF
```

---

## Phase 2 — Production-gate decoupling (cap #2)

**Goal:** stop the ToM production limiter from capping nesting via the misused
`causation_chain_len = src.nesting_depth`. The limiter
(`should_persist_tom_statement`) and its direct tests are unchanged; only the ToM
caller stops feeding nesting_depth.

### Task 2.1: feed `causation_chain_len = 0` from the ToM gate

**Files:**
- Modify: `src/tom/second_order.cpp:125`
- Test: `tests/cpp/test_tom_second_order.cpp`

- [ ] **Step 1 (test):** add a test seeding a partner depth-2 statement and asserting the auto/explicit path is no longer rejected with `reason="gated_limiting"` purely due to nesting depth (it may still be gated for other reasons; assert specifically that a depth-3 production is reachable). Mirror the existing `test_tom_second_order.cpp` seed helpers.
- [ ] **Step 2:** run → FAIL (today `causation_chain_len = src.nesting_depth` gates at chain-len ≥ 3 once Phase 1 lets depth grow).
- [ ] **Step 3 (implement):** in `src/tom/second_order.cpp` change line 125 from
  `gate.causation_chain_len = src.nesting_depth;` to
  `gate.causation_chain_len = 0;  // decoupled from nesting_depth (spec §4.B); nesting is guarded by nesting_depth_writer; derived_depth remains the cascade guard`
- [ ] **Step 4:** run → PASS; full ctest green (limiter's own direct tests at `test_tom_second_order.cpp:139-143` unchanged and still pass).
- [ ] **Step 5 (commit):** `git add src/tom/second_order.cpp tests/cpp/test_tom_second_order.cpp` + trailer.

---

## Phase 3 — Estimator generalization (arbitrary monotone order)

**Goal:** `count_to_depth` returns the partner's demonstrated order without the
`→ 2` saturation, monotone in demonstrated nesting, preserving `{0,1,2}` for
shallow partners.

### Task 3.1: generalize `count_to_depth`

**Files:**
- Modify: `src/tom/depth_estimator.cpp:54-58` (and the SQL at `:118-125` to read the partner's max demonstrated `nesting_depth`, not only depth-1 counts)
- Modify: `include/starling/tom/depth_estimator.hpp:8` (doc comment: returns any non-negative int)
- Test: `tests/cpp/test_tom_second_order.cpp` (or a dedicated `test_depth_estimator.cpp`)

- [ ] **Step 1 (test):** seed a partner with several depth-2 statements (demonstrating 3rd-order) → `estimate(partner) >= 3`; a partner with only depth-1 statements → `>= 2`; preserve current `{0,1,2}` outputs for the existing shallow cases (keep those assertions). Add an assertion that a partner with depth-3 statements estimates `>= 4`.
- [ ] **Step 2:** run → FAIL (saturates at 2).
- [ ] **Step 3 (implement):** replace `count_to_depth` saturation. Concrete rule (monotone, preserves shallow behavior): estimate = `max_demonstrated_nesting_depth + 1`, but only crediting a depth `d` when the partner has `>= kMinCountForDepth` (reuse the existing threshold, currently 3 for the top tier) statements at that depth over the 7-day window; fall back to the current `{0,1,2}` mapping for depths 0-1 so existing tests hold. Widen the query to `SELECT nesting_depth, COUNT(*) ... GROUP BY nesting_depth` and fold to the highest qualifying order.
- [ ] **Step 4:** run → PASS; full ctest green.
- [ ] **Step 5 (commit):** explicit add + trailer.

---

## Phase 4 — Production generalization (auto mirror + explicit depth-N)

**Goal:** auto path mirrors observed partner beliefs at any depth (ungated by the
estimator — grounded); explicit `persist_meta_belief` fabricates depth-N gated by
`estimate(partner) < target_order`. The self-holder skip (`second_order.cpp:193`)
stays — it prevents self-cascade.

### Task 4.1: auto path — drop `skip_nested_source`, ungated mirroring

**Files:**
- Modify: `src/tom/second_order.cpp` (remove the `skip_nested_source` guard at ~`:190`; keep `:193` self-skip)
- Test: `tests/cpp/test_tom_second_order.cpp`

- [ ] **Step 1 (test):** seed a partner's depth-1 statement (`partner believes [X believes Y]`); run the auto path; assert it produces self's depth-2 belief (`reason` not `skip_nested_source`), `nesting_depth == 2`, `provenance == tom_inferred`, with NO estimator gate (passes regardless of `estimate(partner)`). Add a depth-2 source → self depth-3 case.
- [ ] **Step 2:** run → FAIL (today `skip_nested_source` blocks nested sources).
- [ ] **Step 3 (implement):** remove the `if (src.nesting_depth > 0) { out.reason = "skip_nested_source"; return out; }` guard. Keep the self-holder skip and the `user_input`/already-modeled guards. The produced statement's depth auto-derives via `compute_nesting_depth` (Phase 1) from the source depth.
- [ ] **Step 4:** run → PASS; full ctest green.
- [ ] **Step 5 (commit):** explicit add + trailer.

### Task 4.2: explicit `persist_meta_belief` — depth-N, order-gated

**Files:**
- Modify: `src/tom/second_order.cpp:213` (the `estimate(partner) < 2` gate)
- Test: `tests/cpp/test_tom_second_order.cpp` (update `:155-170` order-gate cases)

- [ ] **Step 1 (test):** wrapping a partner's depth-2 row into self depth-3 is gated unless `estimate(partner) >= 3`; depth-1 → depth-2 gated unless `>= 2` (the existing `:166-170` case generalizes). Update the old `== 2`-specific assertions.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3 (implement):** replace the `estimate(partner) < 2 → gated_order` check with `estimate(partner) < target_order → gated_order`, where `target_order = src.nesting_depth + 1` (the order being fabricated). Remove the depth-2 special case so any depth-k source wraps to depth-(k+1).
- [ ] **Step 4:** run → PASS; full ctest green.
- [ ] **Step 5 (commit):** explicit add + trailer.

---

## Phase 5 — Recursive recall (full N-deep chain)

**Goal:** `what_does_X_think_Y_believes` returns the complete nested chain via a
bounded recursive CTE; `.inner` preserved (immediate inner), new `.chain` of all
levels. Binding updated (GIL released around the recursive query).

### Task 5.1: recursive CTE in `what_does_X_think_Y_believes`

**Files:**
- Modify: `include/starling/tom/mentalizing.hpp` (result struct: add `chain` vector of `{level, holder_id, subject_id, predicate, object_kind, object_value}`; keep `inner`)
- Modify: `src/tom/mentalizing_more.cpp:48-100` (replace single self-JOIN with `WITH RECURSIVE`, `max_unwrap` param defaulting to `nesting_depth_writer::kDefaultMaxNestingDepth`)
- Test: `tests/cpp/test_mentalizing_more.cpp` (or the file holding the existing test)

- [ ] **Step 1 (test):** seed a depth-2 outer (`self believes P believes [Q believes R]`); call `what_does_X_think_Y_believes(self, P)`; assert `.inner.id` is the depth-1 row (backward-compat) AND `.chain` has 3 levels ending at the depth-0 leaf `R`; assert `max_unwrap=1` truncates `.chain` to the immediate inner.
- [ ] **Step 2:** run → FAIL (today returns only one JOIN level).
- [ ] **Step 3 (implement):** recursive CTE anchored on `holder=X AND subject=Y AND nesting_depth>=1`, recursing `next.id = cur.object_value WHERE cur.object_kind='statement'`, with a `level < max_unwrap` bound (cycle-safe). Populate `.inner` from level 1 and `.chain` from all levels. Keep O(depth) — `id` is the PK.
- [ ] **Step 4:** run → PASS; full ctest green.
- [ ] **Step 5 (commit):** explicit add + trailer.

### Task 5.2: binding + Python e2e for a 3-deep chain

**Files:**
- Modify: `bindings/python/<mentalizing binding>.cpp` (expose `.chain`; `gil_scoped_release` around the call)
- Test: `tests/python/test_tom2_e2e.py`

- [ ] **Step 1 (test):** extend `test_tom2_e2e.py` — programmatically seed a 3-deep multi-holder chain, `belief_tracker_tick`, `mem.tick()`, then assert recursive recall returns all 3 levels and the leaf object_value.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3 (implement):** expose `.chain` in the binding; rebuild editable (`--python-editable`).
- [ ] **Step 4:** run → PASS; `.venv/bin/python -m pytest tests/python/test_tom2_e2e.py -v`.
- [ ] **Step 5 (commit):** explicit add (binding + test) + trailer.

---

## Phase 6 — Config wiring + spec-doc revision

### Task 6.1: `max_nesting_depth` / `max_cascade_depth` runtime config

**Files:**
- Modify: caller `src/bus/statement_writer.cpp:335` to pass the configured `max_nesting_depth` into `compute_nesting_depth`; resolve Starling's existing config source (the limiter `constexpr` in `limiting.hpp` is the current pattern — move `kDerivedDepthMax` → `max_cascade_depth` config, default 8).
- Test: a C++ test setting a low `max_nesting_depth` via config and asserting the soft cap fires.

- [ ] Steps: TDD as above — config plumbed, defaults 32/8, fallback to defaults when unset; rebuild; full ctest + pytest green.

### Task 6.2: revise `docs/design/subsystems_design/09_tom.md`

**Files:**
- Modify: `09_tom.md:120` (default depth ≤ 2 → arbitrary, bounded by cycle + `max_nesting_depth` + `max_cascade_depth`), `:194/:273` (field doc), `:90-95`/`:289` (Adaptive ToM Order: over-reasoning = fabrication is estimator-gated; mirroring observed beliefs is ungated and unbounded by order).

- [ ] Steps: edit the doc; no code; commit (docs-only).

---

## Self-Review

**Spec coverage:** §3 guards → Phase 1 (cycle + soft cap) + Phase 6 (cascade config); §4.A → Phase 1; §4.B decouple → Phase 2; §4.C recursive recall → Phase 5; §4.D estimator + auto path → Phase 3 + 4.1; §4.E explicit depth-N → Phase 4.2; §4.F config → Phase 6.1; §7 tests → embedded per phase; §8 spec doc → Phase 6.2. No gaps.

**Type consistency:** `NestingCycle{cycle_id}` (1.1) used in 1.2 and the recall cycle-safety (5.1); `compute_nesting_depth(conn, s, max_depth=kDefaultMaxNestingDepth)` signature consistent across 1.2 / 6.1; `.chain` introduced in 5.1, consumed in 5.2; `target_order` (4.2) = `src.nesting_depth + 1`; config keys `max_nesting_depth` / `max_cascade_depth` consistent (1.x default constant → 6.1 config).

**Placeholder scan:** Phase 1 carries exact C++. Phases 2–6 are task-level with the exact lines/changes and concrete rules; the one soft spot — test fixture helper names (`seed_chain` etc.) in 1.2 — is flagged with an explicit instruction to reuse/extend this file's existing seeders against the documented 38-field row, not a "TODO".
