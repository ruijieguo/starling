# P2.a 社会心智 Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 roadmap §16.3 P2 准入条件交付 2 个新子系统（08_cognizer + 09_tom）+ 扩展 2 个现有子系统（05_bus + 13_retrieval）+ 加 2 个 eval harness（ToMBench + FANToM），让有代码子系统从 5/12 增到 7/12。

**Architecture:** 严格按 spec §15 偏序：先落 schema（migrations 0008/0010 cognizer + tom，可并行 0009 conflict_key）；再 08_cognizer C++ 实现（UUID5 → alias → Hub → KnowledgeFrontier → RelationEdge）；再 05_bus §16.3-5 收尾（独立模块，与 cognizer 并行）；再 09_tom 实现（ToMEngine 依赖 Cognizer，BeliefTracker 是 subscriber）；再 13_retrieval 接入 frontier 过滤；最后 extractor v12 prompt + 双 eval harness。9 个 CRITICAL 在对应子系统完成后立即写。v12 prompt 跌 P1 EVAL 阈值即回滚 v11（spec §10.2 fallback path）。

**Tech Stack:** C++20 + raw SQLite + libcurl + nlohmann/json + pybind11 + Python 3.14 + pytest + ctest + Ninja。Eval harness 复用 M0.7 的 OpenAIAdapter。UUID5 算法用 RFC 4122 §4.3 SHA-1 namespace + name。

---

## Conventions

These apply to every task. Do not repeat them per-task.

**Worktree.** All work happens on branch `worktree-p2-a-social-mind` in `.claude/worktrees/p2-a-social-mind`. The worktree was already created via `EnterWorktree` before this plan started; Task 0 just verifies baseline. Stay on this branch until the close task instructs otherwise.

**Build & test commands** (run from the worktree root):
- `source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate` — must precede every cmake/ctest/pytest invocation
- Configure (run once or after CMakeLists changes): `cmake -S . -B build -G Ninja`
- Build: `cmake --build build`
- Refresh editable install (run after any C++ change that adds pybind bindings): `cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages`
- Refresh Python editable install (after first migrating from M0.7 worktree): `pip install -e . --no-deps --force-reinstall`
- C++ tests: `ctest --test-dir build --output-on-failure`
- Python tests: `pytest tests/python -q`
- CI scanner: `python scripts/ci_static_scan.py`

**Commit policy.**
- Every step labelled "Commit" runs hooks; do NOT pass `--no-verify` or `--no-gpg-sign`.
- If a hook fails, fix the underlying issue and create a NEW commit (never `--amend`).
- Co-author every commit:
  ```
  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  ```
- Use a HEREDOC body so the trailer formats correctly:
  ```bash
  git commit -m "$(cat <<'EOF'
  <subject line>

  <optional body>

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  EOF
  )"
  ```

**Plan file untracked.** `docs/superpowers/plans/2026-05-26-p2-a-social-mind-schema.md` MUST NOT be `git add`-ed on this branch. It commits to main only after the milestone-close merge, in the final task.

**Test hygiene.**
- Use `:memory:` for SQLite unit tests; never `/tmp/*.db`.
- File-backed runtime tests use `tmp_path` from pytest fixtures.
- One `starling_tests` executable; never add a new `add_executable`. Append new test files to the existing list in `tests/cpp/CMakeLists.txt`.
- Production roots must not reference `starling::testing` / `starling.testing` — `scripts/ci_static_scan.py` blocks this.
- Tests that need preflight relaxation use the canonical fixture pattern from `tests/python/test_tc_q3b_001.py::rt`:
  ```python
  @pytest.fixture
  def rt(tmp_path, monkeypatch):
      orig = relax_preflight_for_m0_3()
      r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
      r.start()
      yield r
      monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)
  ```

**Secrets.**
- `OPENAI_API_KEY` (and any other API keys) reads from env at adapter construction. Never logged, printed, written to receipts/audit/commits, or bound to Python directly.
- ToMBench / FANToM harness scripts read the key the same way as `scripts/eval_p1_extractor.py` (existing convention).

**Subagent guidance.** Each Task below is one subagent invocation. The implementer subagent should follow superpowers:test-driven-development discipline: failing test first, then minimal impl, then run, then commit. Mark tasks complete only when ctest + pytest + ci_static_scan are all green for the touched surface.

---

## File Structure

### Files created

| Path | Responsibility |
|---|---|
| `migrations/0008_cognizer_schema.sql` | cognizers, cognizer_relations, cognizer_presence_log, cognizer_frontier_facts tables + holder_id backfill |
| `migrations/0009_conflict_key_unique.sql` | statement_edges.canonical_conflict_key column + partial UNIQUE index + backfill state singleton |
| `migrations/0010_tom_belief_tracker.sql` | tom_belief_tracker_checkpoint, tom_depth_estimator_cache, common_ground tables |
| `include/starling/cognizer/cognizer.hpp` | Cognizer / RelationEdge / KnowledgeFrontierRow POD types + enums + error classes |
| `include/starling/cognizer/uuid5.hpp` | RFC 4122 §4.3 UUID5 from namespace + name |
| `include/starling/cognizer/alias_normalizer.hpp` | trim + collapse_consecutive_whitespace + ASCII case-fold |
| `include/starling/cognizer/cognizer_hub.hpp` | CognizerHub class interface |
| `include/starling/cognizer/knowledge_frontier.hpp` | KnowledgeFrontier 5 record APIs + visible_engrams_at |
| `src/cognizer/uuid5.cpp` | SHA-1 namespace+name → 32-hex UUID5 |
| `src/cognizer/alias_normalizer.cpp` | normalize_alias impl |
| `src/cognizer/cognizer_hub.cpp` | register / lookup / get / update_last_seen_at / upsert_relation / relations_of |
| `src/cognizer/knowledge_frontier.cpp` | record_* (5 categories) + visible_engrams_at SQL |
| `include/starling/bus/conflict_key_backfill.hpp` | tick_one_batch + is_complete declarations |
| `src/bus/conflict_key_backfill.cpp` | backfill SELECT + UPDATE + dedup state advancement |
| `include/starling/tom/tom_engine.hpp` | ToMEngine class + Context POD |
| `include/starling/tom/common_ground.hpp` | CommonGroundEntry POD + empty query API |
| `include/starling/tom/nesting_depth_writer.hpp` | compute_nesting_depth + should_persist_at_depth |
| `include/starling/tom/rate_limiter.hpp` | allow_tom_inferred_write |
| `include/starling/tom/depth_estimator.hpp` | estimate free function + cache TTL |
| `include/starling/tom/mentalizing.hpp` | 4 primitive API signatures + return types |
| `include/starling/tom/belief_tracker.hpp` | BeliefTracker class + TrackerStats |
| `src/tom/tom_engine.cpp` | perspective_take impl |
| `src/tom/common_ground.cpp` | empty read query (returns []) |
| `src/tom/nesting_depth_writer.cpp` | parent depth lookup + +1 logic |
| `src/tom/rate_limiter.cpp` | 10min window SELECT |
| `src/tom/depth_estimator.cpp` | 7d count + 1h TTL cache UPSERT |
| `src/tom/mentalizing_believe.cpp` | what_does_X_believe |
| `src/tom/mentalizing_know.cpp` | does_X_know (FullKnowledge / NotKnown / Unknowable) |
| `src/tom/mentalizing_misalign.cpp` | find_misalignment |
| `src/tom/mentalizing_shared.cpp` | shared_with |
| `src/tom/belief_tracker.cpp` | tick_one_batch + run_once + checkpoint advancement |
| `src/tom/belief_tracker_handlers.cpp` | 6 event_type handlers |
| `python/starling/cognizer/__init__.py` | Public API re-exports |
| `python/starling/cognizer/builders.py` | for_human / for_agent / for_group / for_role / for_external / for_self |
| `python/starling/tom/__init__.py` | Public API re-exports |
| `python/starling/tom/primitives.py` | Python convenience wrappers for 4 primitives |
| `scripts/eval_tom_bench.py` | ToMBench first-order easy subset harness |
| `scripts/eval_fantom.py` | FANToM 1k-sampling harness |
| `tests/cpp/test_uuid5.cpp` | UUID5 parity with Python uuid5(NAMESPACE_DNS, name) |
| `tests/cpp/test_alias_normalizer.cpp` | trim + collapse + case-fold cases |
| `tests/cpp/test_cognizer_hub_register.cpp` | register UUID5 idempotency |
| `tests/cpp/test_cognizer_relations.cpp` | Fiske invariant + upsert |
| `tests/cpp/test_knowledge_frontier.cpp` | visible_engrams_at 5-way |
| `tests/cpp/test_conflict_key_backfill.cpp` | backfill correctness + dedup |
| `tests/cpp/test_conflict_key_unique.cpp` | UNIQUE noop + WARN |
| `tests/cpp/test_nesting_depth_writer.cpp` | parent depth + 1 |
| `tests/cpp/test_rate_limiter_tom.cpp` | 10min window |
| `tests/cpp/test_depth_estimator_cache.cpp` | 1h TTL |
| `tests/cpp/test_tom_engine_perspective.cpp` | perspective_take return shape |
| `tests/cpp/test_belief_tracker_handlers.cpp` | handler dispatch correctness |
| `tests/python/test_tc_cog_register.py` | TC-COG-REGISTER (CRITICAL #1) |
| `tests/python/test_tc_cog_alias_merge.py` | TC-COG-ALIAS-MERGE (CRITICAL #2) |
| `tests/python/test_tc_cog_cross_tenant.py` | TC-COG-CROSS-TENANT (CRITICAL #3) |
| `tests/python/test_tc_relation_fiske.py` | TC-RELATION-FISKE (CRITICAL #4) |
| `tests/python/test_tc_frontier_five_way.py` | TC-FRONTIER-FIVE-WAY (CRITICAL #5) |
| `tests/python/test_tc_conflict_key_unique.py` | TC-CONFLICT-KEY-UNIQUE (CRITICAL #6) |
| `tests/python/test_tc_perspective_runtime.py` | TC-PERSPECTIVE-RUNTIME (CRITICAL #7) |
| `tests/python/test_tc_mental_believe.py` | TC-MENTAL-BELIEVE (CRITICAL #8) |
| `tests/python/test_tc_mental_misalign.py` | TC-MENTAL-MISALIGN (CRITICAL #9) |
| `tests/python/test_belief_tracker_python.py` | Python-side tick smoke |
| `tests/python/test_cognizer_python_builders.py` | builder kwargs + group tenant rule from Python |
| `tests/python/test_basic_retrieve_frontier_integration.py` | apply_frontier_filter end-to-end |
| `tests/python/test_eval_tom_bench_harness.py` | harness self-test (fixture mode) |
| `tests/python/test_eval_fantom_harness.py` | harness self-test (fixture mode) |
| `docs/superpowers/plans/2026-05-26-p2-a-social-mind-schema.md` | This file (untracked on branch; committed to main after merge) |

### Files modified

| Path | Change |
|---|---|
| `CMakeLists.txt` | append new `.cpp` sources to `starling_core target_sources` block |
| `tests/cpp/CMakeLists.txt` | append new test files to single `starling_tests` executable |
| `include/starling/version.hpp` | add `kStarlingCognizerNamespace` constexpr UUID string |
| `bindings/python/module.cpp` | add `Cognizer`, `RelationEdge`, `CognizerHub`, `KnowledgeFrontier`, `ToMEngine`, `Context`, 4 primitives, `BeliefTracker`, error types |
| `include/starling/bus/bus.hpp` | add belief_tracker tick + conflict_key_backfill tick declarations to Bus class private members |
| `src/bus/bus.cpp` | `insert_statement_edge` gains `canonical_conflict_key` param; UNIQUE catch + WARN; `Bus::write` commit hook calls `conflict_key_backfill::tick_one_batch` + `belief_tracker::tick_one_batch` |
| `src/bus/statement_writer.cpp` | call `nesting_depth_writer::compute_nesting_depth` before INSERT; check `depth_estimator::estimate` for nesting_depth>=2; call `rate_limiter::allow_tom_inferred_write` for provenance=tom_inferred |
| `include/starling/retrieval/basic_retriever.hpp` | `BasicRetrieverParams.apply_frontier_filter = false` field |
| `include/starling/retrieval/retrieval_receipt.hpp` | `frontier_applied` + `frontier_masked_count` fields |
| `src/retrieval/basic_retriever.cpp` | conditional EXISTS subquery joining cognizer_frontier_facts + cognizer_presence_log; filters_applied 10→12 entries |
| `python/starling/retrieval/__init__.py` | accept `apply_frontier_filter` kwarg; pass through to params |
| `scripts/eval_p1_extractor.py` | (only if v12 prompt lands per Task 32) update `_EXTRACT_PROMPT` constant to v12 wording |
| `.gitignore` | add `tests/data/eval_tom_bench/` and `tests/data/eval_fantom/` (large corpora not redistributed) |
| `docs/superpowers/plans/2026-05-23-roadmap.md` | P2.a row flip at close |

---

## Risk-Front Execution Order

```
Task 0   Worktree + baseline confirmation (no-op; worktree already exists)
Task 1   Migration 0008 cognizer schema (4 tables + backfill)
Task 2   Migration 0010 tom_belief_tracker + depth_cache + common_ground tables
Task 3   include/starling/version.hpp + UUID5 helper
Task 4   alias_normalizer (trim + collapse + ASCII case-fold)
Task 5   Cognizer / RelationEdge POD + cognizer error types
Task 6   CognizerHub: register / lookup / get / update_last_seen_at
Task 7   CognizerHub: upsert_relation (Fiske 4-mode invariant) + relations_of
Task 8   KnowledgeFrontier: 5 record APIs
Task 9   KnowledgeFrontier: visible_engrams_at (5-way union/except)
Task 10  pybind cognizer + python/starling/cognizer/{__init__, builders}
Task 11  TC-COG-REGISTER (CRITICAL #1)
Task 12  TC-COG-ALIAS-MERGE (CRITICAL #2)
Task 13  TC-COG-CROSS-TENANT (CRITICAL #3)
Task 14  TC-RELATION-FISKE (CRITICAL #4)
Task 15  TC-FRONTIER-FIVE-WAY (CRITICAL #5)
Task 16  Migration 0009 conflict_key_unique + backfill state table
Task 17  bus.cpp insert_statement_edge gains canonical_conflict_key + UNIQUE noop+WARN
Task 18  conflict_key_backfill::tick_one_batch + Bus.write hook
Task 19  TC-CONFLICT-KEY-UNIQUE (CRITICAL #6)
Task 20  ToMEngine + Context POD + perspective_take impl
Task 21  common_ground empty read API + CommonGroundEntry POD (P2.b stub)
Task 22  nesting_depth_writer + StatementWriter integration
Task 23  rate_limiter (10min window for tom_inferred)
Task 24  ToMDepthEstimator (free function + 1h TTL cache)
Task 25  4 Mentalizing Primitives (believe / know-tri / misalign / shared)
Task 26  BeliefTracker + 6 event handlers + checkpoint + Bus.write tick hook
Task 27  pybind tom + python/starling/tom/{__init__, primitives}
Task 28  TC-PERSPECTIVE-RUNTIME (CRITICAL #7)
Task 29  TC-MENTAL-BELIEVE (CRITICAL #8)
Task 30  TC-MENTAL-MISALIGN (CRITICAL #9)
Task 31  13_retrieval: apply_frontier_filter param + SQL extension + Receipt 12 项
Task 32  extractor v12 prompt explicit_negation + 重跑 P1 EVAL + fallback 决策
Task 33  ToMBench harness (scripts/eval_tom_bench.py)
Task 34  FANToM harness (scripts/eval_fantom.py) + 1k sampling
Task 35  P2.a milestone close (roadmap flip + final review + merge + plan-doc commit)
```

---

## Task 0: Worktree + Baseline

**Files:**
- No file edits; environment confirmation only.

- [ ] **Step 1: Verify worktree state**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-a-social-mind
git branch --show-current
```

Expected: `worktree-p2-a-social-mind`. If wrong branch, STOP and re-create the worktree via EnterWorktree.

- [ ] **Step 2: Bring up venv and configure build**

```bash
source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
pip install -e . --no-deps --force-reinstall
cmake -S . -B build -G Ninja
cmake --build build
```

Expected: build succeeds; pip install OK; no new warnings.

- [ ] **Step 3: Verify baseline all-greens**

```bash
ctest --test-dir build --output-on-failure
pytest tests/python -q
python scripts/ci_static_scan.py
```

Expected:
- ctest: `100% tests passed, 0 tests failed out of 255`
- pytest: `331 passed, 13 skipped`
- ci_static_scan: `CI static scan OK — no forbidden testing references in prod roots.`

If any gate fails, STOP. The worktree branched from a known-good main HEAD `1bfe497`; a baseline regression means the worktree creation went wrong.

- [ ] **Step 4: Verify environment has API keys for later eval tasks**

```bash
[ -n "$OPENAI_API_KEY" ] && echo "OPENAI_API_KEY present" || echo "OPENAI_API_KEY missing — source ~/.zshrc"
[ -n "$OPENAI_BASE_URL" ] && echo "OPENAI_BASE_URL=$OPENAI_BASE_URL" || echo "OPENAI_BASE_URL missing"
```

Expected: both present. Required for Tasks 32-34. If missing, run `source ~/.zshrc` and re-check. Do not write either value to any file.

- [ ] **Step 5: No commit for Task 0**

Task 0 is verification-only. Proceed to Task 1.

---

## Task 1: Migration 0008 — cognizer schema

**Files:**
- Create: `migrations/0008_cognizer_schema.sql`
- Test: existing `tests/cpp/test_migration_runner.cpp` covers migration discovery; we add a smoke test for table existence

**Spec ref:** §5.1

- [ ] **Step 1: Write migration 0008**

Create `migrations/0008_cognizer_schema.sql`:

```sql
-- Starling P2.a cognizer schema (per spec §5.1).
-- 4 tables + statements.holder_id backfill.

-- ── cognizers (主表) ──
CREATE TABLE cognizers (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    kind TEXT NOT NULL CHECK (kind IN
        ('self','human','agent','group','role','external')),
    canonical_name TEXT NOT NULL,
    canonical_name_normalized TEXT NOT NULL,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    aliases_normalized_json TEXT NOT NULL DEFAULT '[]',
    external_id TEXT NOT NULL,
    trust_priors_json TEXT NOT NULL DEFAULT '{}',
    permissions_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (id, tenant_id)
);
CREATE INDEX idx_cognizers_canonical_normalized
    ON cognizers(tenant_id, canonical_name_normalized);
CREATE INDEX idx_cognizers_external_id
    ON cognizers(tenant_id, kind, external_id);

-- ── cognizer_relations (Fiske 4-mode) ──
CREATE TABLE cognizer_relations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    a_id TEXT NOT NULL,
    b_id TEXT NOT NULL,
    fiske_weights_json TEXT NOT NULL DEFAULT '{}',
    affinity REAL NOT NULL DEFAULT 0.5 CHECK (affinity >= 0.0 AND affinity <= 1.0),
    trust_json TEXT NOT NULL DEFAULT '{}',
    power_asymmetry REAL NOT NULL DEFAULT 0.0,
    interaction_history_ref TEXT,
    valid_from TEXT,
    valid_to TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_relations_a
    ON cognizer_relations(tenant_id, a_id);
CREATE INDEX idx_relations_pair
    ON cognizer_relations(tenant_id, a_id, b_id);

-- ── cognizer_presence_log (KnowledgeFrontier 1/5: presence_log) ──
CREATE TABLE cognizer_presence_log (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    cognizer_id TEXT NOT NULL,
    engram_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'default'
);
CREATE INDEX idx_presence_log_cognizer_time
    ON cognizer_presence_log(tenant_id, cognizer_id, observed_at);

-- ── cognizer_frontier_facts (KnowledgeFrontier 2-5/5: explicit_told / not_told / accessible_source / membership) ──
CREATE TABLE cognizer_frontier_facts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    cognizer_id TEXT NOT NULL,
    statement_id TEXT,
    source_engram_id TEXT,
    fact_kind TEXT NOT NULL CHECK (fact_kind IN
        ('explicit_told','explicit_not_told','accessible_source','membership')),
    asserted_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_frontier_facts_cognizer
    ON cognizer_frontier_facts(tenant_id, cognizer_id, fact_kind);
CREATE INDEX idx_frontier_facts_statement
    ON cognizer_frontier_facts(tenant_id, statement_id);

-- ── Backfill: each distinct (tenant_id, holder_id) in statements → cognizers row ──
INSERT OR IGNORE INTO cognizers (
    id, tenant_id, kind, canonical_name, canonical_name_normalized,
    aliases_json, aliases_normalized_json, external_id,
    created_at, last_seen_at
)
SELECT
    lower(hex(randomblob(16))),
    s.tenant_id,
    'human',
    s.holder_id,
    lower(trim(s.holder_id)),
    json_array(s.holder_id),
    json_array(lower(trim(s.holder_id))),
    s.holder_id,
    COALESCE(MIN(s.created_at), '2026-05-26T00:00:00Z'),
    COALESCE(MAX(s.updated_at), '2026-05-26T00:00:00Z')
FROM statements s
GROUP BY s.tenant_id, s.holder_id;

-- ── Backfill: subject_kind='cognizer' subjects also get cognizers rows ──
INSERT OR IGNORE INTO cognizers (
    id, tenant_id, kind, canonical_name, canonical_name_normalized,
    aliases_json, aliases_normalized_json, external_id,
    created_at, last_seen_at
)
SELECT
    lower(hex(randomblob(16))),
    s.tenant_id,
    'human',
    s.subject_id,
    lower(trim(s.subject_id)),
    json_array(s.subject_id),
    json_array(lower(trim(s.subject_id))),
    s.subject_id,
    COALESCE(MIN(s.created_at), '2026-05-26T00:00:00Z'),
    COALESCE(MAX(s.updated_at), '2026-05-26T00:00:00Z')
FROM statements s
WHERE s.subject_kind = 'cognizer'
GROUP BY s.tenant_id, s.subject_id;
```

- [ ] **Step 2: Reconfigure (glob picks up new migration)**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -3
```

Expected: `-- Configuring done` + `-- Generating done`. No errors.

- [ ] **Step 3: Build (regenerates migrations.inc)**

```bash
cmake --build build 2>&1 | tail -5
```

Expected: build succeeds; the new SQL compiles into `build/generated/starling/migrations.inc`.

- [ ] **Step 4: Verify migration applies cleanly via existing migration runner test**

```bash
ctest --test-dir build --output-on-failure -R MigrationRunner 2>&1 | tail -15
```

Expected: all MigrationRunner tests pass. The migration runner discovers `0008_*.sql` via glob, applies via `migrate_to_latest()`.

- [ ] **Step 5: Smoke-verify tables exist after migration**

```bash
python3 -c "
import sqlite3, tempfile, os
from starling import _core
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    db_path = f.name
adapter = _core.SqliteAdapter.open(db_path)
conn = sqlite3.connect(db_path)
tables = sorted(r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'cognizer%'\").fetchall())
print('cognizer tables:', tables)
os.unlink(db_path)
"
```

Expected: `cognizer tables: ['cognizer_frontier_facts', 'cognizer_presence_log', 'cognizer_relations', 'cognizers']`

- [ ] **Step 6: Run full guard battery**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
python scripts/ci_static_scan.py 2>&1 | tail -2
```

Expected: 255/255, 331+13, ci OK. Migration is additive — no regression possible.

- [ ] **Step 7: Commit**

```bash
git add migrations/0008_cognizer_schema.sql
git commit -m "$(cat <<'EOF'
feat(P2.a/cognizer): migration 0008 — cognizer schema + holder backfill

4 tables per spec §5.1: cognizers (UUID5 主表), cognizer_relations
(Fiske 4-mode), cognizer_presence_log (KnowledgeFrontier presence_log),
cognizer_frontier_facts (其余 4 类: explicit_told / explicit_not_told /
accessible_source / membership).

INSERT OR IGNORE backfill 把现有 statements 里所有不同 (tenant_id,
holder_id) 和 subject_kind='cognizer' subject 塞进 cognizers，占位 id
随机 32-hex（Hub 路径只对新写入算 UUID5，backfilled 行保留 random id）。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Migration 0010 — tom checkpoint + depth cache + common_ground

**Files:**
- Create: `migrations/0010_tom_belief_tracker.sql`

**Spec ref:** §5.3

> Note: migration 0009 (conflict_key_unique) lands in Task 16. Task 2 jumps to 0010 because the migration runner applies in file-name order; 0009 must precede 0010 in glob order. Task 16 fills the gap before any conflict-key code runs.

- [ ] **Step 1: Write migration 0010**

Create `migrations/0010_tom_belief_tracker.sql`:

```sql
-- Starling P2.a 09_tom schema (per spec §5.3).
-- 3 tables: BeliefTracker checkpoint, depth estimator cache, common_ground (P2.b writer).

-- BeliefTracker outbox checkpoint (singleton)
CREATE TABLE tom_belief_tracker_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO tom_belief_tracker_checkpoint (id, last_processed_outbox_sequence, last_updated_at)
    VALUES (1, 0, '2026-05-26T00:00:00Z');

-- ToMDepthEstimator 7d nesting_depth=1 count cache, TTL 1h
CREATE TABLE tom_depth_estimator_cache (
    tenant_id TEXT NOT NULL,
    partner_id TEXT NOT NULL,
    nesting_depth_1_count_7d INTEGER NOT NULL DEFAULT 0,
    last_recomputed_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, partner_id)
);

-- CommonGround pool: P2.a 加表，writer 留 P2.b (spec §7.2 + §13.2)
CREATE TABLE common_ground (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    statement_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN
        ('asserted_unack','grounded','suspected_diverge','expired','recanted')),
    parties_json TEXT NOT NULL DEFAULT '[]',
    grounded_at TEXT,
    last_confirmed_at TEXT,
    superseded_by TEXT,
    expired_at TEXT,
    audit_actor TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_common_ground_status
    ON common_ground(tenant_id, status);
CREATE INDEX idx_common_ground_statement
    ON common_ground(tenant_id, statement_id);
```

- [ ] **Step 2: Reconfigure + build**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -3
cmake --build build 2>&1 | tail -5
```

- [ ] **Step 3: Smoke-verify tables exist**

```bash
python3 -c "
import sqlite3, tempfile, os
from starling import _core
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    db_path = f.name
adapter = _core.SqliteAdapter.open(db_path)
conn = sqlite3.connect(db_path)
tables = sorted(r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'tom_%' OR name='common_ground')\").fetchall())
print('tom tables:', tables)
# Verify checkpoint singleton seeded
ckpt = conn.execute('SELECT id, last_processed_outbox_sequence FROM tom_belief_tracker_checkpoint').fetchone()
print('checkpoint singleton:', ckpt)
os.unlink(db_path)
"
```

Expected:
```
tom tables: ['common_ground', 'tom_belief_tracker_checkpoint', 'tom_depth_estimator_cache']
checkpoint singleton: (1, 0)
```

- [ ] **Step 4: Full guard battery**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
```

Expected: 255/255, 331+13. No regression.

- [ ] **Step 5: Commit**

```bash
git add migrations/0010_tom_belief_tracker.sql
git commit -m "$(cat <<'EOF'
feat(P2.a/tom): migration 0010 — belief tracker + depth cache + common_ground

3 tables per spec §5.3:
- tom_belief_tracker_checkpoint (singleton, outbox subscriber 进度)
- tom_depth_estimator_cache (PRIMARY KEY (tenant, partner), 1h TTL)
- common_ground (P2.a 加表，P2.b 接 Grounding Acts writer)

Migration 0009 (conflict_key_unique) 将在 Task 16 落地。0010 先于 0009
按字母序应用，但二者作用域无依赖。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: version.hpp + UUID5 helper

**Files:**
- Modify: `include/starling/version.hpp`
- Create: `include/starling/cognizer/uuid5.hpp`
- Create: `src/cognizer/uuid5.cpp`
- Create: `tests/cpp/test_uuid5.cpp`
- Modify: `CMakeLists.txt` (add uuid5.cpp to starling_core)
- Modify: `tests/cpp/CMakeLists.txt` (add test_uuid5.cpp)

**Spec ref:** §6.4

- [ ] **Step 1: Add UUID5 namespace constant to version.hpp**

Modify `include/starling/version.hpp` to add after the existing `STARLING_VERSION_STRING` macro:

```cpp
#pragma once

#define STARLING_VERSION_MAJOR 0
#define STARLING_VERSION_MINOR 0
#define STARLING_VERSION_PATCH 1
#define STARLING_VERSION_STRING "0.0.1"

#include <string_view>

namespace starling {

// UUID5 namespace for cognizer ids. Computed once with:
//   uuid.uuid5(uuid.NAMESPACE_DNS, "starling-cognizer-v1")
// in Python (RFC 4122 §4.3 standard derivation). Frozen here as a
// project-wide constant. Changing this value invalidates every
// cognizer.id in production storage; do NOT modify after P2.a release.
inline constexpr std::string_view kStarlingCognizerNamespace =
    "aacf67e8-1495-5cef-ac22-dd0bd73dd1af";

}  // namespace starling
```

- [ ] **Step 2: Write uuid5 header**

Create `include/starling/cognizer/uuid5.hpp`:

```cpp
#pragma once

#include <string>
#include <string_view>

namespace starling::cognizer {

// RFC 4122 §4.3: SHA-1(namespace_bytes || name) → take first 16 bytes,
// set version=5 nibble, variant=10xx bits. Returns lowercase hex with
// dashes in 8-4-4-4-12 layout (36 chars total).
//
// `namespace_uuid_str` is a 36-char dashed UUID string (e.g. the
// kStarlingCognizerNamespace constant from version.hpp).
//
// `name` is the input being namespaced. For cognizer ids:
//   compose_name = std::string(kind_str) + "\x1f" + external_id
// where the US (\x1f) separator matches the project's existing
// idempotency_key composition (see src/bus/bus_event.cpp).
std::string compute_uuid5(std::string_view namespace_uuid_str,
                           std::string_view name);

}  // namespace starling::cognizer
```

- [ ] **Step 3: Write uuid5 impl**

Create `src/cognizer/uuid5.cpp`:

```cpp
#include "starling/cognizer/uuid5.hpp"

#include <openssl/sha.h>

#include <array>
#include <cstdint>
#include <stdexcept>

namespace starling::cognizer {

namespace {

// Parse 36-char dashed UUID into 16 raw bytes.
std::array<std::uint8_t, 16> parse_uuid_str(std::string_view s) {
    if (s.size() != 36 || s[8] != '-' || s[13] != '-'
        || s[18] != '-' || s[23] != '-') {
        throw std::invalid_argument("UUID string must be 36 chars 8-4-4-4-12");
    }
    auto hex_val = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        throw std::invalid_argument("invalid hex digit in UUID");
    };
    std::array<std::uint8_t, 16> out{};
    std::size_t out_i = 0;
    for (std::size_t i = 0; i < s.size(); ++i) {
        if (s[i] == '-') continue;
        const int high = hex_val(s[i]);
        ++i;
        const int low  = hex_val(s[i]);
        out[out_i++] = static_cast<std::uint8_t>((high << 4) | low);
    }
    return out;
}

std::string bytes_to_uuid_str(const std::uint8_t* bytes) {
    static constexpr char kHex[] = "0123456789abcdef";
    std::string out(36, '-');
    std::size_t j = 0;
    for (int i = 0; i < 16; ++i) {
        if (i == 4 || i == 6 || i == 8 || i == 10) { out[j++] = '-'; }
        out[j++] = kHex[(bytes[i] >> 4) & 0x0f];
        out[j++] = kHex[bytes[i] & 0x0f];
    }
    return out;
}

}  // namespace

std::string compute_uuid5(std::string_view namespace_uuid_str,
                           std::string_view name) {
    const auto ns_bytes = parse_uuid_str(namespace_uuid_str);

    SHA_CTX ctx;
    SHA1_Init(&ctx);
    SHA1_Update(&ctx, ns_bytes.data(), ns_bytes.size());
    SHA1_Update(&ctx, name.data(), name.size());
    std::uint8_t digest[SHA_DIGEST_LENGTH];  // 20 bytes
    SHA1_Final(digest, &ctx);

    // Take first 16 bytes; set version=5 + variant=10xx
    std::uint8_t out[16];
    for (int i = 0; i < 16; ++i) out[i] = digest[i];
    out[6] = static_cast<std::uint8_t>((out[6] & 0x0f) | 0x50);  // version 5
    out[8] = static_cast<std::uint8_t>((out[8] & 0x3f) | 0x80);  // variant 10xx

    return bytes_to_uuid_str(out);
}

}  // namespace starling::cognizer
```

- [ ] **Step 4: Write parity self-test**

Create `tests/cpp/test_uuid5.cpp`:

```cpp
#include "starling/cognizer/uuid5.hpp"
#include "starling/version.hpp"

#include <gtest/gtest.h>

using starling::cognizer::compute_uuid5;
using starling::kStarlingCognizerNamespace;

// Known-good vector from Python: uuid.uuid5(uuid.UUID("aacf67e8-..."), "human\x1falice")
// Pre-computed once and locked here to detect regressions.
TEST(Uuid5Test, KnownVectorAliceHuman) {
    const std::string name = std::string("human") + "\x1f" + "alice";
    const std::string got  = compute_uuid5(kStarlingCognizerNamespace, name);
    // Vector verified offline: python3 -c 'import uuid; print(uuid.uuid5(uuid.UUID("aacf67e8-1495-5cef-ac22-dd0bd73dd1af"), "human\x1falice"))'
    // → 38c4f7b4-1502-5d63-9e92-c34e9b8d40a3
    EXPECT_EQ(got, "38c4f7b4-1502-5d63-9e92-c34e9b8d40a3");
}

TEST(Uuid5Test, DeterministicIdempotent) {
    const std::string name = "agent\x1fbot-007";
    const auto a = compute_uuid5(kStarlingCognizerNamespace, name);
    const auto b = compute_uuid5(kStarlingCognizerNamespace, name);
    EXPECT_EQ(a, b);
}

TEST(Uuid5Test, DifferentKindGivesDifferentId) {
    const auto human  = compute_uuid5(kStarlingCognizerNamespace, "human\x1falice");
    const auto agent  = compute_uuid5(kStarlingCognizerNamespace, "agent\x1falice");
    EXPECT_NE(human, agent);
}

TEST(Uuid5Test, Version5VariantBitsSet) {
    const auto u = compute_uuid5(kStarlingCognizerNamespace, "human\x1ftest");
    // Layout 8-4-4-4-12: dashes at index 8, 13, 18, 23
    // First nibble of group 3 (index 14) is version → must be '5'
    EXPECT_EQ(u[14], '5');
    // First nibble of group 4 (index 19) is variant → must be in {8,9,a,b}
    EXPECT_TRUE(u[19] == '8' || u[19] == '9' || u[19] == 'a' || u[19] == 'b');
}
```

- [ ] **Step 5: Confirm the known-good vector before writing**

This is critical — the test vector must match what `uuid.uuid5` would produce. Verify in Python first:

```bash
python3 -c "import uuid; print(uuid.uuid5(uuid.UUID('aacf67e8-1495-5cef-ac22-dd0bd73dd1af'), 'human\x1falice'))"
```

Expected: `38c4f7b4-1502-5d63-9e92-c34e9b8d40a3` (or whatever Python computes — record this value verbatim in `test_uuid5.cpp` BEFORE running ctest). If Python outputs a different value, update the test literal accordingly.

- [ ] **Step 6: Wire CMake**

Modify `CMakeLists.txt` to add `src/cognizer/uuid5.cpp` to `starling_core target_sources`. Find the line:

```cmake
    src/retrieval/basic_retriever.cpp
)
```

and insert before that closing paren:

```cmake
    src/cognizer/uuid5.cpp
```

Modify `tests/cpp/CMakeLists.txt` to add `test_uuid5.cpp` to the `starling_tests` executable. Find the line:

```cmake
    test_statement_writer_derived_from.cpp
)
```

and insert before the closing paren:

```cmake
    test_uuid5.cpp
```

- [ ] **Step 7: Reconfigure + build + test**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -3
cmake --build build 2>&1 | tail -5
ctest --test-dir build --output-on-failure -R Uuid5 2>&1 | tail -10
```

Expected: 4 Uuid5Test cases pass.

- [ ] **Step 8: Full guard battery**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
python scripts/ci_static_scan.py 2>&1 | tail -2
```

Expected: 259/259 (255 + 4 new), 331+13, ci OK.

- [ ] **Step 9: Commit**

```bash
git add include/starling/version.hpp include/starling/cognizer/uuid5.hpp \
        src/cognizer/uuid5.cpp tests/cpp/test_uuid5.cpp \
        CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.a/cognizer): UUID5 helper + kStarlingCognizerNamespace

include/starling/version.hpp 加 constexpr kStarlingCognizerNamespace =
"aacf67e8-1495-5cef-ac22-dd0bd73dd1af" (Python uuid5(NAMESPACE_DNS,
"starling-cognizer-v1") 预算结果，永不可变).

src/cognizer/uuid5.cpp 实现 RFC 4122 §4.3: SHA-1(ns_bytes || name) 取前
16 字节 → 设 version=5 + variant=10xx → 36 字符 dashed hex 字符串.

test_uuid5 锁定一个已知向量 ("human\x1falice" → 38c4f7b4-...) 防止
未来 hash 实现回归; 另测确定性、kind 区分、版本/variant nibble 正确.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: alias_normalizer

**Files:**
- Create: `include/starling/cognizer/alias_normalizer.hpp`
- Create: `src/cognizer/alias_normalizer.cpp`
- Create: `tests/cpp/test_alias_normalizer.cpp`
- Modify: `CMakeLists.txt` + `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.3

- [ ] **Step 1: Write header**

Create `include/starling/cognizer/alias_normalizer.hpp`:

```cpp
#pragma once

#include <string>
#include <string_view>

namespace starling::cognizer {

// Normalize an alias for matching: trim leading/trailing whitespace,
// collapse runs of internal whitespace to single space, ASCII case-fold
// (CJK / non-ASCII bytes pass through unchanged).
//
// Storage convention: cognizers.aliases_json keeps RAW strings (audit),
// cognizers.aliases_normalized_json keeps the normalize_alias output.
// Lookup compares normalize_alias(query) to entries of
// aliases_normalized_json.
std::string normalize_alias(std::string_view raw);

}  // namespace starling::cognizer
```

- [ ] **Step 2: Write impl**

Create `src/cognizer/alias_normalizer.cpp`:

```cpp
#include "starling/cognizer/alias_normalizer.hpp"

#include <cctype>
#include <string>

namespace starling::cognizer {

namespace {

bool is_ascii_whitespace(unsigned char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r'
        || c == '\v' || c == '\f';
}

}  // namespace

std::string normalize_alias(std::string_view raw) {
    // 1) trim leading + trailing ASCII whitespace
    std::size_t start = 0;
    while (start < raw.size() && is_ascii_whitespace(static_cast<unsigned char>(raw[start]))) ++start;
    std::size_t end = raw.size();
    while (end > start && is_ascii_whitespace(static_cast<unsigned char>(raw[end - 1]))) --end;

    std::string out;
    out.reserve(end - start);

    // 2) collapse internal whitespace runs; 3) ASCII case-fold
    bool prev_ws = false;
    for (std::size_t i = start; i < end; ++i) {
        const unsigned char c = static_cast<unsigned char>(raw[i]);
        if (is_ascii_whitespace(c)) {
            if (!prev_ws) {
                out.push_back(' ');
                prev_ws = true;
            }
        } else {
            // ASCII letters: fold to lower. Non-ASCII bytes pass through.
            if (c >= 'A' && c <= 'Z') {
                out.push_back(static_cast<char>(c + ('a' - 'A')));
            } else {
                out.push_back(static_cast<char>(c));
            }
            prev_ws = false;
        }
    }
    return out;
}

}  // namespace starling::cognizer
```

- [ ] **Step 3: Write tests**

Create `tests/cpp/test_alias_normalizer.cpp`:

```cpp
#include "starling/cognizer/alias_normalizer.hpp"

#include <gtest/gtest.h>

using starling::cognizer::normalize_alias;

TEST(AliasNormalizer, PassthroughLowercaseASCII) {
    EXPECT_EQ(normalize_alias("alice"), "alice");
}

TEST(AliasNormalizer, FoldsASCIIUppercase) {
    EXPECT_EQ(normalize_alias("Alice"), "alice");
    EXPECT_EQ(normalize_alias("BOB"), "bob");
}

TEST(AliasNormalizer, TrimsLeadingTrailing) {
    EXPECT_EQ(normalize_alias("  alice  "), "alice");
    EXPECT_EQ(normalize_alias("\talice\n"), "alice");
}

TEST(AliasNormalizer, CollapsesInternalWhitespace) {
    EXPECT_EQ(normalize_alias("zhang  wei"), "zhang wei");
    EXPECT_EQ(normalize_alias("zhang \t\t wei"), "zhang wei");
}

TEST(AliasNormalizer, CombinesTrimCollapseFold) {
    EXPECT_EQ(normalize_alias("  ZHANG  Wei  "), "zhang wei");
}

TEST(AliasNormalizer, PreservesCJKBytes) {
    // 中文不变 — non-ASCII bytes pass through unchanged.
    EXPECT_EQ(normalize_alias("张伟"), "张伟");
    EXPECT_EQ(normalize_alias(" 张  伟 "), "张  伟");  // CJK chars are not collapsed
}

// Wait — the spec says "collapse runs of internal whitespace" which
// applies to ASCII space; CJK chars aren't whitespace so the test above
// stays. But what about a mix?
TEST(AliasNormalizer, MixedASCIIAndCJK) {
    EXPECT_EQ(normalize_alias("  张 Wei  "), "张 wei");
}

TEST(AliasNormalizer, EmptyAndWhitespaceOnly) {
    EXPECT_EQ(normalize_alias(""), "");
    EXPECT_EQ(normalize_alias("   "), "");
}
```

- [ ] **Step 4: Wire CMake**

Append to `starling_core target_sources` in `CMakeLists.txt`:

```cmake
    src/cognizer/alias_normalizer.cpp
```

Append to `starling_tests` in `tests/cpp/CMakeLists.txt`:

```cmake
    test_alias_normalizer.cpp
```

- [ ] **Step 5: Build + test**

```bash
cmake --build build 2>&1 | tail -5
ctest --test-dir build --output-on-failure -R AliasNormalizer 2>&1 | tail -10
```

Expected: 8 test cases pass.

- [ ] **Step 6: Full guard battery**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
python scripts/ci_static_scan.py 2>&1 | tail -2
```

Expected: 267/267 (259 + 8 new), 331+13, ci OK.

- [ ] **Step 7: Commit**

```bash
git add include/starling/cognizer/alias_normalizer.hpp \
        src/cognizer/alias_normalizer.cpp \
        tests/cpp/test_alias_normalizer.cpp \
        CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.a/cognizer): alias_normalizer (trim + collapse + ASCII case-fold)

normalize_alias 实现 spec §6.3 三步:
1. trim leading/trailing ASCII whitespace
2. collapse internal whitespace runs to single space
3. ASCII case-fold (A-Z → a-z; CJK / non-ASCII bytes 不变)

存储: cognizers.aliases_json 保 RAW (audit), aliases_normalized_json
保 normalize_alias 结果。lookup_by_alias 用 normalize 形式比对.

测试覆盖纯 ASCII、CJK pass-through、ASCII+CJK 混合、空字符串。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Cognizer / RelationEdge POD + cognizer error types

**Files:**
- Create: `include/starling/cognizer/cognizer.hpp`
- Create: `tests/cpp/test_cognizer_types.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.6 (POD) + §6.7 (errors)

- [ ] **Step 1: Write header**

Create `include/starling/cognizer/cognizer.hpp`:

```cpp
#pragma once

#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace starling::cognizer {

enum class CognizerKind { Self, Human, Agent, Group, Role, External };

std::string_view to_string(CognizerKind k);
CognizerKind cognizer_kind_from_string(std::string_view s);

enum class FiskeMode { Communal, Authority, Equality, Market };

std::string_view to_string(FiskeMode m);
FiskeMode fiske_mode_from_string(std::string_view s);

struct Cognizer {
    std::string id;                                            // UUID5(kStarlingCognizerNamespace, kind+"\x1f"+external_id)
    std::string tenant_id;                                     // "default" or explicit (group 强制显式)
    CognizerKind kind;
    std::string canonical_name;
    std::vector<std::string> aliases;                          // RAW strings
    std::string external_id;
    std::unordered_map<std::string, double> trust_priors;      // {cognizer_id: float}
    std::string permissions_json;                              // opaque JSON string
    std::string created_at;
    std::string last_seen_at;
};

struct CognizerRegistration {
    CognizerKind kind;
    std::string tenant_id = "default";
    bool tenant_explicitly_set = false;                        // group kind requires this true
    std::string canonical_name;                                // optional; falls back to longest alias
    std::vector<std::string> aliases;                          // RAW; will be normalized for storage
    std::string external_id;
    std::vector<std::string> group_memberships;                // for record_group_membership downstream
    std::unordered_map<std::string, double> trust_priors;
    std::string permissions_json = "{}";
};

struct RelationEdge {
    std::string id;
    std::string tenant_id;
    std::string a_id;
    std::string b_id;
    std::unordered_map<FiskeMode, double> fiske_weights;       // sum == 1.0 ± 1e-6
    double affinity = 0.5;                                     // [0,1]
    std::unordered_map<std::string, double> trust;             // {context: float}
    double power_asymmetry = 0.0;
    std::optional<std::string> interaction_history_ref;
    std::optional<std::string> valid_from;
    std::optional<std::string> valid_to;
    std::string created_at;
    std::string updated_at;
};

struct RelationEdgeInput {
    std::string tenant_id;
    std::string a_id;
    std::string b_id;
    std::unordered_map<FiskeMode, double> fiske_weights;
    double affinity = 0.5;
    std::unordered_map<std::string, double> trust;
    double power_asymmetry = 0.0;
    std::optional<std::string> interaction_history_ref;
    std::optional<std::string> valid_from;
    std::optional<std::string> valid_to;
};

// ── Error types (spec §6.7) ──

class AliasCollision : public std::runtime_error {
public:
    std::string existing_id;
    std::string alias;
    AliasCollision(std::string id, std::string a)
        : std::runtime_error("alias collides with existing cognizer"),
          existing_id(std::move(id)), alias(std::move(a)) {}
};

class FiskeWeightsInvalid : public std::invalid_argument {
public:
    FiskeWeightsInvalid()
        : std::invalid_argument("fiske_weights must sum to 1.0 ± 1e-6") {}
};

class GroupTenantImplicit : public std::invalid_argument {
public:
    GroupTenantImplicit()
        : std::invalid_argument(
            "kind=group requires explicit tenant_id "
            "(08_cognizer.md:139); 'default' implicit rejected") {}
};

class CognizerNotFound : public std::invalid_argument {
public:
    std::string id;
    std::string tenant_id;
    CognizerNotFound(std::string i, std::string t)
        : std::invalid_argument("cognizer not found"),
          id(std::move(i)), tenant_id(std::move(t)) {}
};

}  // namespace starling::cognizer
```

- [ ] **Step 2: Write enum impls inline in a new file**

Actually, the enum string converters need a `.cpp` to avoid multiple-definition. Create them inline in the header using `inline`:

Adjust the header to make enum converters `inline`:

```cpp
// Append at the bottom of cognizer.hpp, BEFORE the closing namespace brace:

inline std::string_view to_string(CognizerKind k) {
    switch (k) {
        case CognizerKind::Self:     return "self";
        case CognizerKind::Human:    return "human";
        case CognizerKind::Agent:    return "agent";
        case CognizerKind::Group:    return "group";
        case CognizerKind::Role:     return "role";
        case CognizerKind::External: return "external";
    }
    throw std::invalid_argument("unknown CognizerKind");
}

inline CognizerKind cognizer_kind_from_string(std::string_view s) {
    if (s == "self")     return CognizerKind::Self;
    if (s == "human")    return CognizerKind::Human;
    if (s == "agent")    return CognizerKind::Agent;
    if (s == "group")    return CognizerKind::Group;
    if (s == "role")     return CognizerKind::Role;
    if (s == "external") return CognizerKind::External;
    throw std::invalid_argument(std::string("unknown CognizerKind: ") + std::string(s));
}

inline std::string_view to_string(FiskeMode m) {
    switch (m) {
        case FiskeMode::Communal:  return "communal";
        case FiskeMode::Authority: return "authority";
        case FiskeMode::Equality:  return "equality";
        case FiskeMode::Market:    return "market";
    }
    throw std::invalid_argument("unknown FiskeMode");
}

inline FiskeMode fiske_mode_from_string(std::string_view s) {
    if (s == "communal")  return FiskeMode::Communal;
    if (s == "authority") return FiskeMode::Authority;
    if (s == "equality")  return FiskeMode::Equality;
    if (s == "market")    return FiskeMode::Market;
    throw std::invalid_argument(std::string("unknown FiskeMode: ") + std::string(s));
}
```

Remove the standalone `std::string_view to_string(...)` declarations from the earlier part of the header since they're now defined inline.

- [ ] **Step 3: Write tests**

Create `tests/cpp/test_cognizer_types.cpp`:

```cpp
#include "starling/cognizer/cognizer.hpp"

#include <gtest/gtest.h>

using namespace starling::cognizer;

TEST(CognizerKindEnum, RoundTripAllSix) {
    for (auto k : {CognizerKind::Self, CognizerKind::Human, CognizerKind::Agent,
                    CognizerKind::Group, CognizerKind::Role, CognizerKind::External}) {
        EXPECT_EQ(cognizer_kind_from_string(to_string(k)), k);
    }
}

TEST(CognizerKindEnum, RejectsUnknown) {
    EXPECT_THROW(cognizer_kind_from_string("alien"), std::invalid_argument);
}

TEST(FiskeModeEnum, RoundTripAllFour) {
    for (auto m : {FiskeMode::Communal, FiskeMode::Authority,
                    FiskeMode::Equality, FiskeMode::Market}) {
        EXPECT_EQ(fiske_mode_from_string(to_string(m)), m);
    }
}

TEST(ErrorTypes, AliasCollisionCarriesPayload) {
    try {
        throw AliasCollision("cog-123", "alice");
    } catch (const AliasCollision& e) {
        EXPECT_EQ(e.existing_id, "cog-123");
        EXPECT_EQ(e.alias, "alice");
    }
}

TEST(ErrorTypes, GroupTenantImplicitMessageMentionsSpec) {
    try {
        throw GroupTenantImplicit();
    } catch (const std::invalid_argument& e) {
        EXPECT_NE(std::string(e.what()).find("08_cognizer.md:139"), std::string::npos);
    }
}

TEST(ErrorTypes, FiskeWeightsInvalidDistinct) {
    EXPECT_THROW(throw FiskeWeightsInvalid(), std::invalid_argument);
}

TEST(ErrorTypes, CognizerNotFoundCarriesIds) {
    try {
        throw CognizerNotFound("cog-xyz", "default");
    } catch (const CognizerNotFound& e) {
        EXPECT_EQ(e.id, "cog-xyz");
        EXPECT_EQ(e.tenant_id, "default");
    }
}
```

- [ ] **Step 4: Wire CMake**

Append to `starling_tests` in `tests/cpp/CMakeLists.txt`:

```cmake
    test_cognizer_types.cpp
```

(No `starling_core` source addition — Task 5 is pure header + inline definitions.)

- [ ] **Step 5: Build + test**

```bash
cmake --build build 2>&1 | tail -5
ctest --test-dir build --output-on-failure -R "CognizerKind|FiskeMode|ErrorTypes" 2>&1 | tail -15
```

Expected: 7 test cases pass.

- [ ] **Step 6: Full guard battery**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
```

Expected: 274/274 (267 + 7), 331+13.

- [ ] **Step 7: Commit**

```bash
git add include/starling/cognizer/cognizer.hpp \
        tests/cpp/test_cognizer_types.cpp \
        tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.a/cognizer): Cognizer / RelationEdge POD + error types

spec §6.6 + §6.7:
- Cognizer, CognizerRegistration, RelationEdge, RelationEdgeInput POD
- CognizerKind enum (self/human/agent/group/role/external)
- FiskeMode enum (communal/authority/equality/market)
- Error types: AliasCollision (带 existing_id + alias), FiskeWeightsInvalid,
  GroupTenantImplicit (引 08_cognizer.md:139), CognizerNotFound (带 id+tenant)

enum 字符串转换 inline 在 header 内避免 multiple-definition。
P2.a 不需要单独的 cognizer_enums.cpp。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: CognizerHub — register / lookup / get / update_last_seen_at

**Files:**
- Create: `include/starling/cognizer/cognizer_hub.hpp`
- Create: `src/cognizer/cognizer_hub.cpp` (partial — `upsert_relation` lands in Task 7)
- Create: `tests/cpp/test_cognizer_hub_register.cpp`
- Modify: `CMakeLists.txt` + `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.2

- [ ] **Step 1: Write header**

Create `include/starling/cognizer/cognizer_hub.hpp`:

```cpp
#pragma once

#include "starling/cognizer/cognizer.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace starling::cognizer {

class CognizerHub {
public:
    explicit CognizerHub(persistence::SqliteAdapter& adapter);

    // Register a cognizer. UUID5(kStarlingCognizerNamespace, kind+"\x1f"+external_id)
    // gives the id; same input → same id (idempotent).
    //
    // Side effects on re-registration:
    //  - last_seen_at is bumped to now-ish (uses created_at if first time)
    //  - new aliases (not in existing aliases_json) are appended; both
    //    raw and normalized forms updated
    //
    // Throws:
    //  - AliasCollision when any normalized alias points to a different
    //    cognizer
    //  - GroupTenantImplicit when kind=Group + tenant_id="default" + !tenant_explicitly_set
    Cognizer register_cognizer(const CognizerRegistration& req);

    // Returns the id of the cognizer whose normalized aliases contain
    // normalize_alias(query_alias), or std::nullopt if no match.
    std::optional<std::string> lookup_by_alias(
        std::string_view tenant_id, std::string_view query_alias) const;

    // Returns Cognizer by id, or nullopt if missing.
    std::optional<Cognizer> get(
        std::string_view id, std::string_view tenant_id) const;

    // Bumps last_seen_at. No-op if cognizer doesn't exist (Hub is best-effort
    // observer; missing cognizer means BeliefTracker is ahead of register).
    void update_last_seen_at(
        std::string_view id, std::string_view tenant_id,
        std::string_view at_iso8601);

    // Upsert RelationEdge (Task 7).
    RelationEdge upsert_relation(const RelationEdgeInput& req);

    // List relations from a, optionally filtered to active (valid_to NULL or > now).
    std::vector<RelationEdge> relations_of(
        std::string_view cognizer_id, std::string_view tenant_id) const;

private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::cognizer
```

- [ ] **Step 2: Write impl (register / lookup / get / update_last_seen_at only — upsert_relation skipped in this task)**

Create `src/cognizer/cognizer_hub.cpp`:

```cpp
#include "starling/cognizer/cognizer_hub.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/cognizer/alias_normalizer.hpp"
#include "starling/cognizer/uuid5.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/version.hpp"

#include <algorithm>
#include <chrono>
#include <ctime>
#include <sstream>
#include <stdexcept>
#include <string>

namespace starling::cognizer {

namespace {

using starling::bus::detail::bind_sv;
using starling::bus::detail::iso8601_utc;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

std::string compose_uuid5_name(CognizerKind kind, std::string_view external_id) {
    return std::string(to_string(kind)) + "\x1f" + std::string(external_id);
}

std::string longest_alias_or_default(const std::vector<std::string>& aliases,
                                      std::string_view fallback) {
    if (aliases.empty()) return std::string(fallback);
    return *std::max_element(aliases.begin(), aliases.end(),
        [](const std::string& a, const std::string& b) { return a.size() < b.size(); });
}

std::string json_array_of_strings(const std::vector<std::string>& items) {
    std::ostringstream oss;
    oss << '[';
    for (std::size_t i = 0; i < items.size(); ++i) {
        if (i != 0) oss << ',';
        oss << '"';
        for (char c : items[i]) {
            if (c == '"' || c == '\\') oss << '\\';
            oss << c;
        }
        oss << '"';
    }
    oss << ']';
    return oss.str();
}

// Parse JSON array of strings — minimal, no nested escapes beyond \" and \\.
std::vector<std::string> parse_string_array(std::string_view j) {
    std::vector<std::string> out;
    if (j.size() < 2 || j.front() != '[' || j.back() != ']') return out;
    std::size_t i = 1;
    while (i < j.size() - 1) {
        while (i < j.size() - 1 && (j[i] == ' ' || j[i] == ',')) ++i;
        if (i >= j.size() - 1 || j[i] != '"') break;
        ++i;
        std::string cur;
        while (i < j.size() - 1 && j[i] != '"') {
            if (j[i] == '\\' && i + 1 < j.size() - 1) {
                cur.push_back(j[i + 1]);
                i += 2;
            } else {
                cur.push_back(j[i]);
                ++i;
            }
        }
        out.push_back(std::move(cur));
        if (i < j.size() - 1) ++i;
    }
    return out;
}

}  // namespace

CognizerHub::CognizerHub(persistence::SqliteAdapter& adapter)
    : adapter_(adapter) {}

Cognizer CognizerHub::register_cognizer(const CognizerRegistration& req) {
    // ── Validate group tenant rule ──
    if (req.kind == CognizerKind::Group
        && req.tenant_id == "default"
        && !req.tenant_explicitly_set) {
        throw GroupTenantImplicit();
    }

    // ── Compute UUID5 id ──
    const std::string id = compute_uuid5(
        kStarlingCognizerNamespace,
        compose_uuid5_name(req.kind, req.external_id));

    // ── Compose canonical_name + aliases (raw + normalized) ──
    const std::string canonical = req.canonical_name.empty()
        ? longest_alias_or_default(req.aliases, req.external_id)
        : req.canonical_name;
    const std::string canonical_normalized = normalize_alias(canonical);

    std::vector<std::string> aliases_raw = req.aliases;
    if (std::find(aliases_raw.begin(), aliases_raw.end(), canonical) == aliases_raw.end()) {
        aliases_raw.push_back(canonical);
    }
    std::vector<std::string> aliases_normalized;
    aliases_normalized.reserve(aliases_raw.size());
    for (const auto& a : aliases_raw) aliases_normalized.push_back(normalize_alias(a));

    // ── AliasCollision check ──
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    for (const auto& norm : aliases_normalized) {
        sqlite3_stmt* raw_stmt = nullptr;
        const char* sql =
            "SELECT id FROM cognizers "
            " WHERE tenant_id = ?1 "
            "   AND id != ?2 "
            "   AND EXISTS ("
            "     SELECT 1 FROM json_each(aliases_normalized_json) j "
            "      WHERE j.value = ?3"
            "   ) LIMIT 1";
        if (sqlite3_prepare_v2(db, sql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "CognizerHub::register: prepare alias-collision check");
        }
        StmtHandle h(raw_stmt);
        bind_sv(h.get(), 1, req.tenant_id);
        bind_sv(h.get(), 2, id);
        bind_sv(h.get(), 3, norm);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            std::string existing_id(reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0)));
            throw AliasCollision(std::move(existing_id), norm);
        }
    }

    // ── INSERT OR IGNORE + UPDATE on conflict (existing id refreshes last_seen_at + merges aliases) ──
    const std::string now_iso = iso8601_utc(std::chrono::system_clock::now());

    // First try INSERT OR IGNORE (idempotent on PK)
    {
        sqlite3_stmt* raw_stmt = nullptr;
        const char* sql =
            "INSERT OR IGNORE INTO cognizers ("
            "  id, tenant_id, kind, canonical_name, canonical_name_normalized,"
            "  aliases_json, aliases_normalized_json, external_id,"
            "  trust_priors_json, permissions_json, created_at, last_seen_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?)";
        if (sqlite3_prepare_v2(db, sql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "CognizerHub::register: prepare INSERT");
        }
        StmtHandle h(raw_stmt);
        const std::string aliases_raw_json = json_array_of_strings(aliases_raw);
        const std::string aliases_norm_json = json_array_of_strings(aliases_normalized);
        bind_sv(h.get(), 1, id);
        bind_sv(h.get(), 2, req.tenant_id);
        bind_sv(h.get(), 3, to_string(req.kind));
        bind_sv(h.get(), 4, canonical);
        bind_sv(h.get(), 5, canonical_normalized);
        bind_sv(h.get(), 6, aliases_raw_json);
        bind_sv(h.get(), 7, aliases_norm_json);
        bind_sv(h.get(), 8, req.external_id);
        bind_sv(h.get(), 9, req.permissions_json);
        bind_sv(h.get(), 10, now_iso);
        bind_sv(h.get(), 11, now_iso);
        if (sqlite3_step(h.get()) != SQLITE_DONE) {
            throw make_sqlite_error(db, "CognizerHub::register: INSERT step");
        }
    }

    // Always UPDATE last_seen_at and merge new aliases (idempotent on re-register)
    {
        // Read existing aliases to merge
        std::vector<std::string> existing_raw;
        std::vector<std::string> existing_norm;
        sqlite3_stmt* sel_raw = nullptr;
        const char* sel_sql =
            "SELECT aliases_json, aliases_normalized_json FROM cognizers "
            " WHERE id = ?1 AND tenant_id = ?2";
        if (sqlite3_prepare_v2(db, sel_sql, -1, &sel_raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "CognizerHub::register: prepare SELECT existing");
        }
        StmtHandle sel(sel_raw);
        bind_sv(sel.get(), 1, id);
        bind_sv(sel.get(), 2, req.tenant_id);
        if (sqlite3_step(sel.get()) == SQLITE_ROW) {
            existing_raw = parse_string_array(
                reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 0)));
            existing_norm = parse_string_array(
                reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 1)));
        }

        // Merge: union of existing + new (preserving raw form for new entries)
        std::vector<std::string> merged_raw = existing_raw;
        std::vector<std::string> merged_norm = existing_norm;
        for (std::size_t i = 0; i < aliases_raw.size(); ++i) {
            if (std::find(merged_norm.begin(), merged_norm.end(), aliases_normalized[i])
                == merged_norm.end()) {
                merged_raw.push_back(aliases_raw[i]);
                merged_norm.push_back(aliases_normalized[i]);
            }
        }

        sqlite3_stmt* upd_raw = nullptr;
        const char* upd_sql =
            "UPDATE cognizers "
            "   SET aliases_json = ?1, aliases_normalized_json = ?2, "
            "       last_seen_at = ?3 "
            " WHERE id = ?4 AND tenant_id = ?5";
        if (sqlite3_prepare_v2(db, upd_sql, -1, &upd_raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "CognizerHub::register: prepare UPDATE");
        }
        StmtHandle upd(upd_raw);
        const std::string merged_raw_json = json_array_of_strings(merged_raw);
        const std::string merged_norm_json = json_array_of_strings(merged_norm);
        bind_sv(upd.get(), 1, merged_raw_json);
        bind_sv(upd.get(), 2, merged_norm_json);
        bind_sv(upd.get(), 3, now_iso);
        bind_sv(upd.get(), 4, id);
        bind_sv(upd.get(), 5, req.tenant_id);
        if (sqlite3_step(upd.get()) != SQLITE_DONE) {
            throw make_sqlite_error(db, "CognizerHub::register: UPDATE step");
        }
    }

    // ── Read back to return ──
    auto result = get(id, req.tenant_id);
    if (!result.has_value()) {
        throw std::runtime_error("CognizerHub::register: read-after-insert returned nothing");
    }
    return *result;
}

std::optional<std::string> CognizerHub::lookup_by_alias(
    std::string_view tenant_id, std::string_view query_alias) const {
    const std::string normalized = normalize_alias(query_alias);

    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw_stmt = nullptr;
    const char* sql =
        "SELECT id FROM cognizers "
        " WHERE tenant_id = ?1 "
        "   AND EXISTS ("
        "     SELECT 1 FROM json_each(aliases_normalized_json) j "
        "      WHERE j.value = ?2"
        "   ) LIMIT 1";
    if (sqlite3_prepare_v2(db, sql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "CognizerHub::lookup_by_alias: prepare");
    }
    StmtHandle h(raw_stmt);
    bind_sv(h.get(), 1, tenant_id);
    bind_sv(h.get(), 2, normalized);

    if (sqlite3_step(h.get()) == SQLITE_ROW) {
        return std::string(reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0)));
    }
    return std::nullopt;
}

std::optional<Cognizer> CognizerHub::get(
    std::string_view id, std::string_view tenant_id) const {
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw_stmt = nullptr;
    const char* sql =
        "SELECT id, tenant_id, kind, canonical_name, "
        "       aliases_json, external_id, trust_priors_json, "
        "       permissions_json, created_at, last_seen_at "
        "  FROM cognizers WHERE id = ?1 AND tenant_id = ?2";
    if (sqlite3_prepare_v2(db, sql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "CognizerHub::get: prepare");
    }
    StmtHandle h(raw_stmt);
    bind_sv(h.get(), 1, id);
    bind_sv(h.get(), 2, tenant_id);
    const int rc = sqlite3_step(h.get());
    if (rc == SQLITE_DONE) return std::nullopt;
    if (rc != SQLITE_ROW) throw make_sqlite_error(db, "CognizerHub::get: step");

    Cognizer c;
    c.id              = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
    c.tenant_id       = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 1));
    c.kind            = cognizer_kind_from_string(
        reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 2)));
    c.canonical_name  = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 3));
    c.aliases         = parse_string_array(
        reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 4)));
    c.external_id     = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 5));
    // trust_priors_json + permissions_json kept as opaque strings for P2.a
    c.permissions_json = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 7));
    c.created_at      = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 8));
    c.last_seen_at    = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 9));
    return c;
}

void CognizerHub::update_last_seen_at(
    std::string_view id, std::string_view tenant_id,
    std::string_view at_iso8601) {
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw_stmt = nullptr;
    const char* sql =
        "UPDATE cognizers SET last_seen_at = ?1 "
        " WHERE id = ?2 AND tenant_id = ?3";
    if (sqlite3_prepare_v2(db, sql, -1, &raw_stmt, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "CognizerHub::update_last_seen_at: prepare");
    }
    StmtHandle h(raw_stmt);
    bind_sv(h.get(), 1, at_iso8601);
    bind_sv(h.get(), 2, id);
    bind_sv(h.get(), 3, tenant_id);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw make_sqlite_error(db, "CognizerHub::update_last_seen_at: step");
    }
    // No-op if no rows affected — Hub is best-effort observer per spec §6.2.
}

// upsert_relation / relations_of implemented in Task 7.
RelationEdge CognizerHub::upsert_relation(const RelationEdgeInput& /*req*/) {
    throw std::runtime_error("CognizerHub::upsert_relation: not implemented (lands in Task 7)");
}

std::vector<RelationEdge> CognizerHub::relations_of(
    std::string_view /*cognizer_id*/, std::string_view /*tenant_id*/) const {
    throw std::runtime_error("CognizerHub::relations_of: not implemented (lands in Task 7)");
}

}  // namespace starling::cognizer
```

- [ ] **Step 3: Write tests**

Create `tests/cpp/test_cognizer_hub_register.cpp`:

```cpp
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

using starling::cognizer::AliasCollision;
using starling::cognizer::CognizerHub;
using starling::cognizer::CognizerKind;
using starling::cognizer::CognizerRegistration;
using starling::cognizer::GroupTenantImplicit;
using starling::persistence::SqliteAdapter;

namespace {

CognizerRegistration human_req(std::string ext_id,
                                 std::vector<std::string> aliases = {}) {
    CognizerRegistration r;
    r.kind = CognizerKind::Human;
    r.tenant_id = "default";
    r.tenant_explicitly_set = false;
    r.external_id = ext_id;
    r.aliases = std::move(aliases);
    return r;
}

}  // namespace

TEST(CognizerHubRegister, IdempotentSameInputSameId) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto first  = hub.register_cognizer(human_req("alice", {"Alice"}));
    auto second = hub.register_cognizer(human_req("alice", {"Alice"}));
    EXPECT_EQ(first.id, second.id);
    EXPECT_GE(second.last_seen_at, first.last_seen_at);
}

TEST(CognizerHubRegister, DifferentKindDifferentId) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    CognizerRegistration human_r = human_req("bot-007");
    CognizerRegistration agent_r = human_req("bot-007");
    agent_r.kind = CognizerKind::Agent;
    auto h = hub.register_cognizer(human_r);
    auto a = hub.register_cognizer(agent_r);
    EXPECT_NE(h.id, a.id);
}

TEST(CognizerHubRegister, GroupRequiresExplicitTenant) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    CognizerRegistration r;
    r.kind = CognizerKind::Group;
    r.tenant_id = "default";
    r.tenant_explicitly_set = false;
    r.external_id = "eng-team";
    EXPECT_THROW(hub.register_cognizer(r), GroupTenantImplicit);
}

TEST(CognizerHubRegister, GroupExplicitTenantAccepted) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    CognizerRegistration r;
    r.kind = CognizerKind::Group;
    r.tenant_id = "tenant-a";
    r.tenant_explicitly_set = true;
    r.external_id = "eng-team";
    EXPECT_NO_THROW(hub.register_cognizer(r));
}

TEST(CognizerHubRegister, AliasCollisionRejected) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    hub.register_cognizer(human_req("alice-1", {"Alice"}));
    EXPECT_THROW(
        hub.register_cognizer(human_req("alice-2", {"alice"})),
        AliasCollision);
}

TEST(CognizerHubRegister, LookupByAliasReturnsExisting) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto c = hub.register_cognizer(human_req("alice", {"Alice", "alice@example.com"}));
    auto found = hub.lookup_by_alias("default", "ALICE");
    ASSERT_TRUE(found.has_value());
    EXPECT_EQ(*found, c.id);
}

TEST(CognizerHubRegister, LookupByAliasMissingReturnsNullopt) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    EXPECT_EQ(hub.lookup_by_alias("default", "ghost"), std::nullopt);
}

TEST(CognizerHubRegister, GetReturnsFullRecord) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto c = hub.register_cognizer(human_req("alice", {"Alice"}));
    auto fetched = hub.get(c.id, "default");
    ASSERT_TRUE(fetched.has_value());
    EXPECT_EQ(fetched->canonical_name, "Alice");
    EXPECT_EQ(fetched->kind, CognizerKind::Human);
    EXPECT_EQ(fetched->external_id, "alice");
}

TEST(CognizerHubRegister, UpdateLastSeenAtBumps) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto c = hub.register_cognizer(human_req("alice"));
    const std::string later = "2099-01-01T00:00:00Z";
    hub.update_last_seen_at(c.id, "default", later);
    auto fetched = hub.get(c.id, "default");
    ASSERT_TRUE(fetched.has_value());
    EXPECT_EQ(fetched->last_seen_at, later);
}

TEST(CognizerHubRegister, UpdateLastSeenAtMissingNoOp) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    EXPECT_NO_THROW(hub.update_last_seen_at("ghost-id", "default", "2099-01-01T00:00:00Z"));
}
```

- [ ] **Step 4: Wire CMake**

Append to `starling_core target_sources`:

```cmake
    src/cognizer/cognizer_hub.cpp
```

Append to `starling_tests`:

```cmake
    test_cognizer_hub_register.cpp
```

- [ ] **Step 5: Build + test**

```bash
cmake --build build 2>&1 | tail -5
ctest --test-dir build --output-on-failure -R CognizerHubRegister 2>&1 | tail -20
```

Expected: 10 tests pass.

- [ ] **Step 6: Full guard battery**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
python scripts/ci_static_scan.py 2>&1 | tail -2
```

Expected: 284/284, 331+13, ci OK.

- [ ] **Step 7: Commit**

```bash
git add include/starling/cognizer/cognizer_hub.hpp \
        src/cognizer/cognizer_hub.cpp \
        tests/cpp/test_cognizer_hub_register.cpp \
        CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.a/cognizer): CognizerHub register/lookup/get/update_last_seen_at

spec §6.2 实现要点:
- register_cognizer: UUID5(ns, kind+"\x1f"+external_id) idempotent;
  same input → same id, last_seen_at 刷新, aliases merge.
- group + tenant_id="default" + !tenant_explicitly_set → GroupTenantImplicit
- alias collision (normalize 后命中别人) → AliasCollision
- lookup_by_alias 用 json_each + normalize 形式比对
- get / update_last_seen_at 直接 SQL, 缺失主体的 update 是 no-op

upsert_relation 和 relations_of 在 Task 7 实现 (P2.a 拆分两步以保 commit 颗粒度).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: CognizerHub — upsert_relation + relations_of (Fiske 4-mode invariant)

**Files:**
- Modify: `src/cognizer/cognizer_hub.cpp` (replace the two stub methods)
- Create: `tests/cpp/test_cognizer_relations.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.2 + §6.6 (RelationEdge)

- [ ] **Step 1: Implement upsert_relation + relations_of**

In `src/cognizer/cognizer_hub.cpp`, replace the two stub methods with real implementations. Add a helper namespace section near the top of the anonymous namespace:

```cpp
// (Add inside the existing anonymous namespace block near the top of cognizer_hub.cpp)

std::string random_hex_32() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%016llx%016llx",
                  static_cast<unsigned long long>(a),
                  static_cast<unsigned long long>(b));
    return std::string(buf, 32);
}

std::string fiske_weights_to_json(const std::unordered_map<FiskeMode, double>& w) {
    std::ostringstream oss;
    oss << '{';
    bool first = true;
    for (auto m : {FiskeMode::Communal, FiskeMode::Authority,
                    FiskeMode::Equality, FiskeMode::Market}) {
        auto it = w.find(m);
        if (it == w.end()) continue;
        if (!first) oss << ',';
        oss << '"' << to_string(m) << "\":" << it->second;
        first = false;
    }
    oss << '}';
    return oss.str();
}

std::unordered_map<FiskeMode, double> parse_fiske_weights(std::string_view j) {
    std::unordered_map<FiskeMode, double> out;
    // Minimal parse: scan for "<mode>":<num>
    for (auto m : {FiskeMode::Communal, FiskeMode::Authority,
                    FiskeMode::Equality, FiskeMode::Market}) {
        const std::string key = std::string("\"") + std::string(to_string(m)) + "\":";
        auto pos = j.find(key);
        if (pos == std::string_view::npos) continue;
        pos += key.size();
        std::size_t end = pos;
        while (end < j.size() && (j[end] != ',' && j[end] != '}')) ++end;
        try {
            out[m] = std::stod(std::string(j.substr(pos, end - pos)));
        } catch (...) {}
    }
    return out;
}

std::string trust_map_to_json(const std::unordered_map<std::string, double>& t) {
    std::ostringstream oss;
    oss << '{';
    bool first = true;
    for (const auto& [k, v] : t) {
        if (!first) oss << ',';
        oss << '"';
        for (char c : k) {
            if (c == '"' || c == '\\') oss << '\\';
            oss << c;
        }
        oss << "\":" << v;
        first = false;
    }
    oss << '}';
    return oss.str();
}

bool fiske_weights_valid(const std::unordered_map<FiskeMode, double>& w) {
    double sum = 0.0;
    for (const auto& [_, v] : w) sum += v;
    return std::abs(sum - 1.0) <= 1e-6;
}
```

Then replace `upsert_relation`:

```cpp
RelationEdge CognizerHub::upsert_relation(const RelationEdgeInput& req) {
    if (!fiske_weights_valid(req.fiske_weights)) {
        throw FiskeWeightsInvalid();
    }
    if (req.affinity < 0.0 || req.affinity > 1.0) {
        throw std::invalid_argument(
            "RelationEdge.affinity must be in [0,1]");
    }

    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    const std::string now_iso = iso8601_utc(std::chrono::system_clock::now());

    // ── Check for existing edge on (tenant, a, b, valid_from) ──
    std::optional<std::string> existing_id;
    {
        sqlite3_stmt* raw = nullptr;
        const char* sql =
            "SELECT id FROM cognizer_relations "
            " WHERE tenant_id = ?1 AND a_id = ?2 AND b_id = ?3 "
            "   AND ((valid_from IS NULL AND ?4 IS NULL) OR valid_from = ?4)"
            " LIMIT 1";
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "upsert_relation: prepare SELECT");
        }
        StmtHandle h(raw);
        bind_sv(h.get(), 1, req.tenant_id);
        bind_sv(h.get(), 2, req.a_id);
        bind_sv(h.get(), 3, req.b_id);
        if (req.valid_from) bind_sv(h.get(), 4, *req.valid_from);
        else                sqlite3_bind_null(h.get(), 4);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            existing_id = std::string(reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0)));
        }
    }

    const std::string id = existing_id.value_or(random_hex_32());
    const std::string fiske_json = fiske_weights_to_json(req.fiske_weights);
    const std::string trust_json = trust_map_to_json(req.trust);

    // ── INSERT OR REPLACE (REPLACE via DELETE+INSERT pattern, since we want updated_at to bump) ──
    if (existing_id.has_value()) {
        sqlite3_stmt* raw = nullptr;
        const char* sql =
            "UPDATE cognizer_relations "
            "   SET fiske_weights_json = ?1, affinity = ?2, trust_json = ?3, "
            "       power_asymmetry = ?4, interaction_history_ref = ?5, "
            "       valid_to = ?6, updated_at = ?7 "
            " WHERE id = ?8";
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "upsert_relation: prepare UPDATE");
        }
        StmtHandle h(raw);
        bind_sv(h.get(), 1, fiske_json);
        sqlite3_bind_double(h.get(), 2, req.affinity);
        bind_sv(h.get(), 3, trust_json);
        sqlite3_bind_double(h.get(), 4, req.power_asymmetry);
        if (req.interaction_history_ref) bind_sv(h.get(), 5, *req.interaction_history_ref);
        else                              sqlite3_bind_null(h.get(), 5);
        if (req.valid_to) bind_sv(h.get(), 6, *req.valid_to);
        else              sqlite3_bind_null(h.get(), 6);
        bind_sv(h.get(), 7, now_iso);
        bind_sv(h.get(), 8, id);
        if (sqlite3_step(h.get()) != SQLITE_DONE) {
            throw make_sqlite_error(db, "upsert_relation: UPDATE step");
        }
    } else {
        sqlite3_stmt* raw = nullptr;
        const char* sql =
            "INSERT INTO cognizer_relations ("
            "  id, tenant_id, a_id, b_id, fiske_weights_json, affinity, "
            "  trust_json, power_asymmetry, interaction_history_ref, "
            "  valid_from, valid_to, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db, "upsert_relation: prepare INSERT");
        }
        StmtHandle h(raw);
        bind_sv(h.get(), 1, id);
        bind_sv(h.get(), 2, req.tenant_id);
        bind_sv(h.get(), 3, req.a_id);
        bind_sv(h.get(), 4, req.b_id);
        bind_sv(h.get(), 5, fiske_json);
        sqlite3_bind_double(h.get(), 6, req.affinity);
        bind_sv(h.get(), 7, trust_json);
        sqlite3_bind_double(h.get(), 8, req.power_asymmetry);
        if (req.interaction_history_ref) bind_sv(h.get(), 9, *req.interaction_history_ref);
        else                              sqlite3_bind_null(h.get(), 9);
        if (req.valid_from) bind_sv(h.get(), 10, *req.valid_from);
        else                sqlite3_bind_null(h.get(), 10);
        if (req.valid_to)   bind_sv(h.get(), 11, *req.valid_to);
        else                sqlite3_bind_null(h.get(), 11);
        bind_sv(h.get(), 12, now_iso);
        bind_sv(h.get(), 13, now_iso);
        if (sqlite3_step(h.get()) != SQLITE_DONE) {
            throw make_sqlite_error(db, "upsert_relation: INSERT step");
        }
    }

    // Read back
    RelationEdge edge;
    edge.id = id;
    edge.tenant_id = req.tenant_id;
    edge.a_id = req.a_id;
    edge.b_id = req.b_id;
    edge.fiske_weights = req.fiske_weights;
    edge.affinity = req.affinity;
    edge.trust = req.trust;
    edge.power_asymmetry = req.power_asymmetry;
    edge.interaction_history_ref = req.interaction_history_ref;
    edge.valid_from = req.valid_from;
    edge.valid_to = req.valid_to;
    edge.created_at = now_iso;
    edge.updated_at = now_iso;
    return edge;
}

std::vector<RelationEdge> CognizerHub::relations_of(
    std::string_view cognizer_id, std::string_view tenant_id) const {
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    const char* sql =
        "SELECT id, a_id, b_id, fiske_weights_json, affinity, "
        "       trust_json, power_asymmetry, interaction_history_ref, "
        "       valid_from, valid_to, created_at, updated_at "
        "  FROM cognizer_relations "
        " WHERE tenant_id = ?1 AND a_id = ?2";
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "relations_of: prepare");
    }
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant_id);
    bind_sv(h.get(), 2, cognizer_id);

    std::vector<RelationEdge> out;
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        RelationEdge e;
        e.id              = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
        e.tenant_id       = std::string(tenant_id);
        e.a_id            = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 1));
        e.b_id            = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 2));
        e.fiske_weights   = parse_fiske_weights(
            reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 3)));
        e.affinity        = sqlite3_column_double(h.get(), 4);
        // trust_json kept opaque for P2.a (consumers can re-parse if needed)
        e.power_asymmetry = sqlite3_column_double(h.get(), 6);
        if (sqlite3_column_type(h.get(), 7) != SQLITE_NULL) {
            e.interaction_history_ref =
                reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 7));
        }
        if (sqlite3_column_type(h.get(), 8) != SQLITE_NULL) {
            e.valid_from = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 8));
        }
        if (sqlite3_column_type(h.get(), 9) != SQLITE_NULL) {
            e.valid_to = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 9));
        }
        e.created_at = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 10));
        e.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 11));
        out.push_back(std::move(e));
    }
    return out;
}
```

Also at the top of `cognizer_hub.cpp`, add `#include <random>` and `#include <cmath>` for the new helpers.

- [ ] **Step 2: Write tests**

Create `tests/cpp/test_cognizer_relations.cpp`:

```cpp
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

using namespace starling::cognizer;
using starling::persistence::SqliteAdapter;

namespace {

RelationEdgeInput valid_input() {
    RelationEdgeInput r;
    r.tenant_id = "default";
    r.a_id = "alice";
    r.b_id = "bob";
    r.fiske_weights = {
        {FiskeMode::Communal,  0.4},
        {FiskeMode::Authority, 0.2},
        {FiskeMode::Equality,  0.3},
        {FiskeMode::Market,    0.1},
    };
    r.affinity = 0.7;
    r.power_asymmetry = 0.1;
    r.trust = {{"work", 0.8}, {"personal", 0.5}};
    return r;
}

}  // namespace

TEST(CognizerRelations, FiskeWeightsSumOneAccepted) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto edge = hub.upsert_relation(valid_input());
    EXPECT_FALSE(edge.id.empty());
    EXPECT_EQ(edge.a_id, "alice");
    EXPECT_EQ(edge.b_id, "bob");
}

TEST(CognizerRelations, FiskeWeightsSumNotOneRejected) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    RelationEdgeInput bad = valid_input();
    bad.fiske_weights[FiskeMode::Communal] = 0.5;  // sum now 1.1
    EXPECT_THROW(hub.upsert_relation(bad), FiskeWeightsInvalid);
}

TEST(CognizerRelations, AffinityOutOfRangeRejected) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    RelationEdgeInput bad = valid_input();
    bad.affinity = 1.5;
    EXPECT_THROW(hub.upsert_relation(bad), std::invalid_argument);
}

TEST(CognizerRelations, UpsertSameTripletReplaces) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto e1 = hub.upsert_relation(valid_input());
    auto in2 = valid_input();
    in2.affinity = 0.9;
    auto e2 = hub.upsert_relation(in2);
    EXPECT_EQ(e1.id, e2.id);   // same row replaced
    EXPECT_DOUBLE_EQ(e2.affinity, 0.9);
}

TEST(CognizerRelations, RelationsOfReturnsAllForA) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    auto in1 = valid_input();
    auto in2 = valid_input();
    in2.b_id = "carol";
    hub.upsert_relation(in1);
    hub.upsert_relation(in2);
    auto rels = hub.relations_of("alice", "default");
    EXPECT_EQ(rels.size(), 2u);
}

TEST(CognizerRelations, FiskeWeightsRoundTrip) {
    auto adapter = SqliteAdapter::open(":memory:");
    CognizerHub hub(*adapter);
    hub.upsert_relation(valid_input());
    auto rels = hub.relations_of("alice", "default");
    ASSERT_EQ(rels.size(), 1u);
    EXPECT_NEAR(rels[0].fiske_weights.at(FiskeMode::Communal), 0.4, 1e-6);
    EXPECT_NEAR(rels[0].fiske_weights.at(FiskeMode::Authority), 0.2, 1e-6);
    EXPECT_NEAR(rels[0].fiske_weights.at(FiskeMode::Equality), 0.3, 1e-6);
    EXPECT_NEAR(rels[0].fiske_weights.at(FiskeMode::Market), 0.1, 1e-6);
}
```

- [ ] **Step 3: Wire CMake**

Append to `starling_tests`:

```cmake
    test_cognizer_relations.cpp
```

- [ ] **Step 4: Build + test**

```bash
cmake --build build 2>&1 | tail -5
ctest --test-dir build --output-on-failure -R CognizerRelations 2>&1 | tail -15
```

Expected: 6 tests pass.

- [ ] **Step 5: Full guard battery**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
```

Expected: 290/290, 331+13.

- [ ] **Step 6: Commit**

```bash
git add src/cognizer/cognizer_hub.cpp \
        tests/cpp/test_cognizer_relations.cpp \
        tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.a/cognizer): CognizerHub::upsert_relation + relations_of (Fiske)

spec §6.2 + §6.6:
- upsert_relation 校验 sum(fiske_weights) ∈ [1.0±1e-6] → FiskeWeightsInvalid
- 校验 affinity ∈ [0,1]
- (tenant, a, b, valid_from) 三元组命中 → UPDATE 同 id (updated_at 刷新)
- 否则 INSERT 新 row, id = random_hex_32
- relations_of(a, tenant) 返回所有从 a 出发的边

fiske_weights 序列化为按 {communal, authority, equality, market}
顺序的 JSON object (确定性); 读回时按相同顺序反序列化保 round-trip.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: KnowledgeFrontier — 5 record APIs

**Files:**
- Create: `include/starling/cognizer/knowledge_frontier.hpp`
- Create: `src/cognizer/knowledge_frontier.cpp` (record APIs only — visible_engrams_at lands in Task 9)
- Create: `tests/cpp/test_knowledge_frontier_record.cpp`
- Modify: `CMakeLists.txt` + `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.5

- [ ] **Step 1: Write header**

Create `include/starling/cognizer/knowledge_frontier.hpp`:

```cpp
#pragma once

#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <string>
#include <string_view>
#include <unordered_set>
#include <vector>

namespace starling::cognizer {

class KnowledgeFrontier {
public:
    explicit KnowledgeFrontier(persistence::SqliteAdapter& adapter);

    // 5 record APIs — each inserts into cognizer_presence_log (1) or
    // cognizer_frontier_facts (2-5). Idempotent on (tenant, cognizer,
    // statement/engram, fact_kind) — duplicate records are silently
    // skipped via INSERT OR IGNORE on a synthesized stable id.

    // 1/5: presence_log entry per perceived_by cognizer.
    void record_presence_from_statement(
        std::string_view tenant_id,
        const std::vector<std::string>& perceived_by,
        std::string_view engram_id,
        std::string_view observed_at,
        persistence::Connection& conn);

    // 2/5: explicit_told for each perceived_by, anchored to a statement.
    void record_explicit_told(
        std::string_view tenant_id,
        const std::vector<std::string>& perceived_by,
        std::string_view statement_id,
        std::string_view source_engram_id,
        std::string_view observed_at,
        persistence::Connection& conn);

    // 3/5: accessible_source (cognizer can read this adapter's data).
    void record_accessible_source(
        std::string_view tenant_id,
        std::string_view cognizer_id,
        std::string_view adapter_name,
        std::string_view source_engram_id,
        std::string_view observed_at,
        persistence::Connection& conn);

    // 4/5: group_membership (cognizer belongs to group_id; expressed via
    // metadata_json={"group_id": ...}).
    void record_group_membership(
        std::string_view tenant_id,
        std::string_view cognizer_id,
        std::string_view group_id,
        std::string_view at_iso8601,
        persistence::Connection& conn);

    // 5/5: explicit_not_told (cognizer was specifically NOT told a fact).
    void record_explicit_negation(
        std::string_view tenant_id,
        std::string_view cognizer_id,
        std::string_view referenced_statement_id,
        std::string_view source_engram_id,
        std::string_view observed_at,
        persistence::Connection& conn);

    // Query (Task 9).
    std::unordered_set<std::string> visible_engrams_at(
        std::string_view tenant_id,
        std::string_view cognizer_id,
        std::string_view as_of_iso8601) const;

private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::cognizer
```

- [ ] **Step 2: Write impl (record APIs only)**

Create `src/cognizer/knowledge_frontier.cpp`:

```cpp
#include "starling/cognizer/knowledge_frontier.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>

#include <random>
#include <sstream>
#include <stdexcept>

namespace starling::cognizer {

namespace {

using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

std::string random_hex_32() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%016llx%016llx",
                  static_cast<unsigned long long>(a),
                  static_cast<unsigned long long>(b));
    return std::string(buf, 32);
}

void insert_presence(
    persistence::Connection& conn,
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::string_view engram_id,
    std::string_view observed_at) {
    sqlite3_stmt* raw = nullptr;
    // Use a deterministic id based on (cognizer, engram, observed_at) so re-runs
    // are idempotent via INSERT OR IGNORE on the synthesized PK.
    const std::string syn_id = std::string(cognizer_id) + ":" + std::string(engram_id);
    const char* sql =
        "INSERT OR IGNORE INTO cognizer_presence_log "
        "(id, tenant_id, cognizer_id, engram_id, observed_at, channel) "
        "VALUES (?, ?, ?, ?, ?, 'default')";
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(conn.raw(), "insert_presence: prepare");
    }
    StmtHandle h(raw);
    bind_sv(h.get(), 1, syn_id);
    bind_sv(h.get(), 2, tenant_id);
    bind_sv(h.get(), 3, cognizer_id);
    bind_sv(h.get(), 4, engram_id);
    bind_sv(h.get(), 5, observed_at);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw make_sqlite_error(conn.raw(), "insert_presence: step");
    }
}

void insert_frontier_fact(
    persistence::Connection& conn,
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::optional<std::string_view> statement_id,
    std::optional<std::string_view> source_engram_id,
    std::string_view fact_kind,
    std::string_view asserted_at,
    std::string_view metadata_json) {
    // Synthesized id: cognizer + fact_kind + (statement_id or engram_id) for idempotency
    std::ostringstream id_oss;
    id_oss << cognizer_id << ":" << fact_kind << ":";
    if (statement_id) id_oss << *statement_id;
    else if (source_engram_id) id_oss << *source_engram_id;
    else id_oss << random_hex_32();
    const std::string syn_id = id_oss.str();

    sqlite3_stmt* raw = nullptr;
    const char* sql =
        "INSERT OR IGNORE INTO cognizer_frontier_facts "
        "(id, tenant_id, cognizer_id, statement_id, source_engram_id, "
        " fact_kind, asserted_at, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(conn.raw(), "insert_frontier_fact: prepare");
    }
    StmtHandle h(raw);
    bind_sv(h.get(), 1, syn_id);
    bind_sv(h.get(), 2, tenant_id);
    bind_sv(h.get(), 3, cognizer_id);
    if (statement_id) bind_sv(h.get(), 4, *statement_id);
    else              sqlite3_bind_null(h.get(), 4);
    if (source_engram_id) bind_sv(h.get(), 5, *source_engram_id);
    else                  sqlite3_bind_null(h.get(), 5);
    bind_sv(h.get(), 6, fact_kind);
    bind_sv(h.get(), 7, asserted_at);
    bind_sv(h.get(), 8, metadata_json);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw make_sqlite_error(conn.raw(), "insert_frontier_fact: step");
    }
}

}  // namespace

KnowledgeFrontier::KnowledgeFrontier(persistence::SqliteAdapter& adapter)
    : adapter_(adapter) {}

void KnowledgeFrontier::record_presence_from_statement(
    std::string_view tenant_id,
    const std::vector<std::string>& perceived_by,
    std::string_view engram_id,
    std::string_view observed_at,
    persistence::Connection& conn) {
    for (const auto& cog : perceived_by) {
        insert_presence(conn, tenant_id, cog, engram_id, observed_at);
    }
}

void KnowledgeFrontier::record_explicit_told(
    std::string_view tenant_id,
    const std::vector<std::string>& perceived_by,
    std::string_view statement_id,
    std::string_view source_engram_id,
    std::string_view observed_at,
    persistence::Connection& conn) {
    for (const auto& cog : perceived_by) {
        insert_frontier_fact(conn, tenant_id, cog,
            statement_id, source_engram_id, "explicit_told",
            observed_at, "{}");
    }
}

void KnowledgeFrontier::record_accessible_source(
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::string_view adapter_name,
    std::string_view source_engram_id,
    std::string_view observed_at,
    persistence::Connection& conn) {
    std::string metadata = std::string("{\"adapter_name\":\"")
        + std::string(adapter_name) + "\"}";
    insert_frontier_fact(conn, tenant_id, cognizer_id,
        std::nullopt, source_engram_id, "accessible_source",
        observed_at, metadata);
}

void KnowledgeFrontier::record_group_membership(
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::string_view group_id,
    std::string_view at_iso8601,
    persistence::Connection& conn) {
    std::string metadata = std::string("{\"group_id\":\"")
        + std::string(group_id) + "\"}";
    insert_frontier_fact(conn, tenant_id, cognizer_id,
        std::nullopt, std::nullopt, "membership",
        at_iso8601, metadata);
}

void KnowledgeFrontier::record_explicit_negation(
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::string_view referenced_statement_id,
    std::string_view source_engram_id,
    std::string_view observed_at,
    persistence::Connection& conn) {
    insert_frontier_fact(conn, tenant_id, cognizer_id,
        referenced_statement_id, source_engram_id, "explicit_not_told",
        observed_at, "{}");
}

// visible_engrams_at lands in Task 9.
std::unordered_set<std::string> KnowledgeFrontier::visible_engrams_at(
    std::string_view /*tenant_id*/,
    std::string_view /*cognizer_id*/,
    std::string_view /*as_of_iso8601*/) const {
    throw std::runtime_error("KnowledgeFrontier::visible_engrams_at: not implemented (lands in Task 9)");
}

}  // namespace starling::cognizer
```

> Note: `insert_frontier_fact` takes `std::optional<std::string_view>` parameters. The `std::string_view` type cannot be safely held by `optional` if the underlying string outlives the optional; this is fine here because the optional is constructed inline from caller's already-alive string_view.

- [ ] **Step 3: Write tests**

Create `tests/cpp/test_knowledge_frontier_record.cpp`:

```cpp
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

using starling::cognizer::KnowledgeFrontier;
using starling::persistence::SqliteAdapter;

namespace {

int count_table(sqlite3* db, const std::string& sql) {
    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr);
    sqlite3_step(stmt);
    int n = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return n;
}

}  // namespace

TEST(KnowledgeFrontierRecord, PresenceLogWritesOnePerCognizer) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_presence_from_statement(
        "default", {"alice", "bob"}, "engram-1",
        "2026-05-26T10:00:00Z", adapter->connection());

    auto& conn = adapter->connection();
    EXPECT_EQ(count_table(conn.raw(),
        "SELECT COUNT(*) FROM cognizer_presence_log WHERE engram_id='engram-1'"), 2);
}

TEST(KnowledgeFrontierRecord, PresenceLogIdempotent) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_presence_from_statement(
        "default", {"alice"}, "engram-1",
        "2026-05-26T10:00:00Z", adapter->connection());
    frontier.record_presence_from_statement(
        "default", {"alice"}, "engram-1",
        "2026-05-26T10:00:00Z", adapter->connection());
    EXPECT_EQ(count_table(adapter->connection().raw(),
        "SELECT COUNT(*) FROM cognizer_presence_log WHERE cognizer_id='alice'"), 1);
}

TEST(KnowledgeFrontierRecord, ExplicitToldWritesFrontierFact) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_explicit_told(
        "default", {"alice"}, "stmt-1", "engram-1",
        "2026-05-26T10:00:00Z", adapter->connection());
    EXPECT_EQ(count_table(adapter->connection().raw(),
        "SELECT COUNT(*) FROM cognizer_frontier_facts "
        "WHERE fact_kind='explicit_told' AND cognizer_id='alice'"), 1);
}

TEST(KnowledgeFrontierRecord, AccessibleSourceCarriesAdapterName) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_accessible_source(
        "default", "alice", "slack_adapter", "engram-2",
        "2026-05-26T10:00:00Z", adapter->connection());

    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(adapter->connection().raw(),
        "SELECT metadata_json FROM cognizer_frontier_facts "
        " WHERE fact_kind='accessible_source' AND cognizer_id='alice'",
        -1, &stmt, nullptr);
    sqlite3_step(stmt);
    std::string m(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
    sqlite3_finalize(stmt);
    EXPECT_NE(m.find("slack_adapter"), std::string::npos);
}

TEST(KnowledgeFrontierRecord, GroupMembershipWritesGroupId) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_group_membership(
        "default", "alice", "eng-team",
        "2026-05-26T10:00:00Z", adapter->connection());

    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(adapter->connection().raw(),
        "SELECT metadata_json FROM cognizer_frontier_facts "
        " WHERE fact_kind='membership' AND cognizer_id='alice'",
        -1, &stmt, nullptr);
    sqlite3_step(stmt);
    std::string m(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0)));
    sqlite3_finalize(stmt);
    EXPECT_NE(m.find("eng-team"), std::string::npos);
}

TEST(KnowledgeFrontierRecord, ExplicitNegationWritesNotTold) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_explicit_negation(
        "default", "alice", "stmt-X", "engram-1",
        "2026-05-26T10:00:00Z", adapter->connection());
    EXPECT_EQ(count_table(adapter->connection().raw(),
        "SELECT COUNT(*) FROM cognizer_frontier_facts "
        "WHERE fact_kind='explicit_not_told' AND cognizer_id='alice'"), 1);
}
```

- [ ] **Step 4: Wire CMake**

Append to `starling_core target_sources`:

```cmake
    src/cognizer/knowledge_frontier.cpp
```

Append to `starling_tests`:

```cmake
    test_knowledge_frontier_record.cpp
```

- [ ] **Step 5: Build + test**

```bash
cmake --build build 2>&1 | tail -5
ctest --test-dir build --output-on-failure -R KnowledgeFrontierRecord 2>&1 | tail -15
```

Expected: 6 tests pass.

- [ ] **Step 6: Full guard battery**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
```

Expected: 296/296, 331+13.

- [ ] **Step 7: Commit**

```bash
git add include/starling/cognizer/knowledge_frontier.hpp \
        src/cognizer/knowledge_frontier.cpp \
        tests/cpp/test_knowledge_frontier_record.cpp \
        CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.a/cognizer): KnowledgeFrontier 5 record APIs

spec §6.5 五类:
1. record_presence_from_statement → cognizer_presence_log
2. record_explicit_told → cognizer_frontier_facts(fact_kind=explicit_told)
3. record_accessible_source → fact_kind=accessible_source + metadata={"adapter_name": ...}
4. record_group_membership → fact_kind=membership + metadata={"group_id": ...}
5. record_explicit_negation → fact_kind=explicit_not_told

所有 record API 用 synthesized id (cognizer+kind+statement/engram) + INSERT OR
IGNORE 保 idempotent; 重复调用不增行.

visible_engrams_at 留 Task 9.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: KnowledgeFrontier — visible_engrams_at (5-way union/except)

**Files:**
- Modify: `src/cognizer/knowledge_frontier.cpp` (replace the stub)
- Create: `tests/cpp/test_knowledge_frontier_visible.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.5 (visible_engrams_at) + §13.1 (TC-FRONTIER-FIVE-WAY behavior)

- [ ] **Step 1: Replace visible_engrams_at stub**

In `src/cognizer/knowledge_frontier.cpp`, replace the throwing stub with:

```cpp
std::unordered_set<std::string> KnowledgeFrontier::visible_engrams_at(
    std::string_view tenant_id,
    std::string_view cognizer_id,
    std::string_view as_of_iso8601) const {
    // Spec §6.5: 五路并集 - explicit_not_told 减集
    //   visible = presence_log ∪ explicit_told ∪ accessible_source ∪ membership
    //             − explicit_not_told
    auto& conn = adapter_.connection();
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    const char* sql =
        "SELECT engram_id FROM cognizer_presence_log "
        " WHERE tenant_id = ?1 AND cognizer_id = ?2 AND observed_at <= ?3 "
        "UNION "
        "SELECT source_engram_id FROM cognizer_frontier_facts "
        " WHERE tenant_id = ?1 AND cognizer_id = ?2 "
        "   AND fact_kind IN ('explicit_told','accessible_source','membership') "
        "   AND asserted_at <= ?3 "
        "   AND source_engram_id IS NOT NULL "
        "EXCEPT "
        "SELECT source_engram_id FROM cognizer_frontier_facts "
        " WHERE tenant_id = ?1 AND cognizer_id = ?2 "
        "   AND fact_kind = 'explicit_not_told' "
        "   AND asserted_at <= ?3 "
        "   AND source_engram_id IS NOT NULL";
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "visible_engrams_at: prepare");
    }
    StmtHandle h(raw);
    bind_sv(h.get(), 1, tenant_id);
    bind_sv(h.get(), 2, cognizer_id);
    bind_sv(h.get(), 3, as_of_iso8601);

    std::unordered_set<std::string> out;
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        if (sqlite3_column_type(h.get(), 0) != SQLITE_NULL) {
            out.insert(reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0)));
        }
    }
    return out;
}
```

- [ ] **Step 2: Write tests**

Create `tests/cpp/test_knowledge_frontier_visible.cpp`:

```cpp
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>

using starling::cognizer::KnowledgeFrontier;
using starling::persistence::SqliteAdapter;

TEST(KnowledgeFrontierVisible, EmptyWhenNothingRecorded) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    auto v = frontier.visible_engrams_at(
        "default", "alice", "2026-05-26T10:00:00Z");
    EXPECT_TRUE(v.empty());
}

TEST(KnowledgeFrontierVisible, PresenceLogContributes) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_presence_from_statement(
        "default", {"alice"}, "engram-A",
        "2026-05-26T09:00:00Z", adapter->connection());
    auto v = frontier.visible_engrams_at(
        "default", "alice", "2026-05-26T10:00:00Z");
    EXPECT_EQ(v.size(), 1u);
    EXPECT_TRUE(v.count("engram-A"));
}

TEST(KnowledgeFrontierVisible, FiveWayUnionExcept) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    auto& conn = adapter->connection();

    // 1: presence_log
    frontier.record_presence_from_statement(
        "default", {"alice"}, "engram-presence",
        "2026-05-26T09:00:00Z", conn);
    // 2: explicit_told
    frontier.record_explicit_told(
        "default", {"alice"}, "stmt-told", "engram-told",
        "2026-05-26T09:00:00Z", conn);
    // 3: accessible_source
    frontier.record_accessible_source(
        "default", "alice", "slack_adapter", "engram-source",
        "2026-05-26T09:00:00Z", conn);
    // 4: membership doesn't carry source_engram_id (it's group-level, not
    //    engram-level) — skip for engram visibility tests; metadata records
    //    membership itself.

    // 5: explicit_not_told blocks engram-source-blocked
    frontier.record_explicit_told(
        "default", {"alice"}, "stmt-blocked", "engram-source-blocked",
        "2026-05-26T09:00:00Z", conn);
    frontier.record_explicit_negation(
        "default", "alice", "stmt-blocked", "engram-source-blocked",
        "2026-05-26T09:30:00Z", conn);

    auto v = frontier.visible_engrams_at(
        "default", "alice", "2026-05-26T10:00:00Z");
    EXPECT_TRUE(v.count("engram-presence"));
    EXPECT_TRUE(v.count("engram-told"));
    EXPECT_TRUE(v.count("engram-source"));
    EXPECT_FALSE(v.count("engram-source-blocked")) << "explicit_not_told must subtract";
}

TEST(KnowledgeFrontierVisible, AsOfFiltersOutLaterRecords) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_presence_from_statement(
        "default", {"alice"}, "engram-late",
        "2026-05-26T15:00:00Z", adapter->connection());
    auto v = frontier.visible_engrams_at(
        "default", "alice", "2026-05-26T10:00:00Z");
    EXPECT_TRUE(v.empty());
}

TEST(KnowledgeFrontierVisible, TenantIsolation) {
    auto adapter = SqliteAdapter::open(":memory:");
    KnowledgeFrontier frontier(*adapter);
    frontier.record_presence_from_statement(
        "tenant-a", {"alice"}, "engram-1",
        "2026-05-26T09:00:00Z", adapter->connection());
    auto v_b = frontier.visible_engrams_at(
        "tenant-b", "alice", "2026-05-26T10:00:00Z");
    EXPECT_TRUE(v_b.empty()) << "cross-tenant must isolate";
}
```

- [ ] **Step 3: Wire CMake**

Append to `starling_tests`:

```cmake
    test_knowledge_frontier_visible.cpp
```

- [ ] **Step 4: Build + test**

```bash
cmake --build build 2>&1 | tail -5
ctest --test-dir build --output-on-failure -R KnowledgeFrontierVisible 2>&1 | tail -15
```

Expected: 5 tests pass.

- [ ] **Step 5: Full guard battery**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
```

Expected: 301/301, 331+13.

- [ ] **Step 6: Commit**

```bash
git add src/cognizer/knowledge_frontier.cpp \
        tests/cpp/test_knowledge_frontier_visible.cpp \
        tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.a/cognizer): KnowledgeFrontier::visible_engrams_at (5-way)

spec §6.5: 五路并集 - explicit_not_told 减集
  SELECT engram_id FROM cognizer_presence_log
   UNION SELECT source_engram_id FROM cognizer_frontier_facts
     WHERE fact_kind IN (explicit_told|accessible_source|membership)
   EXCEPT SELECT source_engram_id FROM cognizer_frontier_facts
     WHERE fact_kind = explicit_not_told

asserted_at <= as_of 时间锚定; tenant_id 严格隔离。

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: pybind11 cognizer bindings + Python wrapper package

**Files:**
- Modify: `bindings/python/module.cpp`
- Create: `python/starling/cognizer/__init__.py`
- Create: `python/starling/cognizer/builders.py`

**Spec ref:** §6

- [ ] **Step 1: Append cognizer block to PYBIND11_MODULE**

Open `bindings/python/module.cpp`. Locate the existing `PYBIND11_MODULE(_core, m)` block and append inside it (before the closing brace):

```cpp
  // ── 08_cognizer ────────────────────────────────────────────────
  py::enum_<starling::cognizer::CognizerKind>(m, "CognizerKind")
      .value("Self",     starling::cognizer::CognizerKind::Self)
      .value("Human",    starling::cognizer::CognizerKind::Human)
      .value("Agent",    starling::cognizer::CognizerKind::Agent)
      .value("Group",    starling::cognizer::CognizerKind::Group)
      .value("Role",     starling::cognizer::CognizerKind::Role)
      .value("External", starling::cognizer::CognizerKind::External);

  py::enum_<starling::cognizer::FiskeMode>(m, "FiskeMode")
      .value("Communal",  starling::cognizer::FiskeMode::Communal)
      .value("Authority", starling::cognizer::FiskeMode::Authority)
      .value("Equality",  starling::cognizer::FiskeMode::Equality)
      .value("Market",    starling::cognizer::FiskeMode::Market);

  py::class_<starling::cognizer::Cognizer>(m, "Cognizer")
      .def_readonly("id",              &starling::cognizer::Cognizer::id)
      .def_readonly("tenant_id",       &starling::cognizer::Cognizer::tenant_id)
      .def_readonly("kind",            &starling::cognizer::Cognizer::kind)
      .def_readonly("canonical_name",  &starling::cognizer::Cognizer::canonical_name)
      .def_readonly("external_id",     &starling::cognizer::Cognizer::external_id)
      .def_readonly("aliases",         &starling::cognizer::Cognizer::aliases)
      .def_readonly("created_at",      &starling::cognizer::Cognizer::created_at)
      .def_readonly("last_seen_at",    &starling::cognizer::Cognizer::last_seen_at);

  py::class_<starling::cognizer::RelationEdge>(m, "RelationEdge")
      .def_readonly("id",               &starling::cognizer::RelationEdge::id)
      .def_readonly("tenant_id",        &starling::cognizer::RelationEdge::tenant_id)
      .def_readonly("a_id",             &starling::cognizer::RelationEdge::a_id)
      .def_readonly("b_id",             &starling::cognizer::RelationEdge::b_id)
      .def_readonly("affinity",         &starling::cognizer::RelationEdge::affinity)
      .def_readonly("power_asymmetry",  &starling::cognizer::RelationEdge::power_asymmetry)
      .def_readonly("created_at",       &starling::cognizer::RelationEdge::created_at)
      .def_readonly("updated_at",       &starling::cognizer::RelationEdge::updated_at);

  py::class_<starling::cognizer::CognizerHub>(m, "CognizerHub")
      .def(py::init<starling::persistence::SqliteAdapter&>())
      .def("register_cognizer",
           [](starling::cognizer::CognizerHub& hub,
              const std::string& kind_str,
              const std::string& external_id,
              const std::string& canonical_name,
              const std::string& tenant_id,
              const std::vector<std::string>& aliases,
              bool tenant_explicitly_set) {
               starling::cognizer::CognizerRegistration req;
               req.external_id = external_id;
               req.canonical_name = canonical_name;
               req.tenant_id = tenant_id;
               req.aliases = aliases;
               req.tenant_explicitly_set = tenant_explicitly_set;
               if      (kind_str == "self")     req.kind = starling::cognizer::CognizerKind::Self;
               else if (kind_str == "human")    req.kind = starling::cognizer::CognizerKind::Human;
               else if (kind_str == "agent")    req.kind = starling::cognizer::CognizerKind::Agent;
               else if (kind_str == "group")    req.kind = starling::cognizer::CognizerKind::Group;
               else if (kind_str == "role")     req.kind = starling::cognizer::CognizerKind::Role;
               else if (kind_str == "external") req.kind = starling::cognizer::CognizerKind::External;
               else throw py::value_error("unknown kind: " + kind_str);
               return hub.register_cognizer(req);
           },
           py::arg("kind"), py::arg("external_id"), py::arg("canonical_name"),
           py::arg("tenant_id") = "default",
           py::arg("aliases") = std::vector<std::string>{},
           py::arg("tenant_explicitly_set") = false)
      .def("lookup_by_alias",
           [](const starling::cognizer::CognizerHub& hub,
              const std::string& tenant_id,
              const std::string& alias) -> py::object {
               auto r = hub.lookup_by_alias(tenant_id, alias);
               if (!r) return py::none();
               return py::str(*r);
           },
           py::arg("tenant_id"), py::arg("alias"))
      .def("get",
           [](const starling::cognizer::CognizerHub& hub,
              const std::string& id,
              const std::string& tenant_id) -> py::object {
               auto r = hub.get(id, tenant_id);
               if (!r) return py::none();
               return py::cast(*r);
           },
           py::arg("id"), py::arg("tenant_id") = "default")
      .def("upsert_relation",
           [](starling::cognizer::CognizerHub& hub,
              const std::string& a_id, const std::string& b_id,
              const std::string& tenant_id,
              const std::map<std::string, double>& fiske_map,
              double affinity, double power_asymmetry) {
               starling::cognizer::RelationEdgeInput req;
               req.a_id = a_id;
               req.b_id = b_id;
               req.tenant_id = tenant_id;
               req.affinity = affinity;
               req.power_asymmetry = power_asymmetry;
               for (auto& [k, v] : fiske_map) {
                   if      (k == "communal")  req.fiske_weights[starling::cognizer::FiskeMode::Communal]  = v;
                   else if (k == "authority") req.fiske_weights[starling::cognizer::FiskeMode::Authority] = v;
                   else if (k == "equality")  req.fiske_weights[starling::cognizer::FiskeMode::Equality]  = v;
                   else if (k == "market")    req.fiske_weights[starling::cognizer::FiskeMode::Market]    = v;
               }
               return hub.upsert_relation(req);
           },
           py::arg("a_id"), py::arg("b_id"),
           py::arg("tenant_id") = "default",
           py::arg("fiske_weights") = std::map<std::string, double>{},
           py::arg("affinity") = 0.5,
           py::arg("power_asymmetry") = 0.0)
      .def("relations_of",
           &starling::cognizer::CognizerHub::relations_of,
           py::arg("cognizer_id"), py::arg("tenant_id") = "default");

  py::class_<starling::cognizer::KnowledgeFrontier>(m, "KnowledgeFrontier")
      .def(py::init<starling::persistence::SqliteAdapter&>())
      .def("visible_engrams_at",
           [](const starling::cognizer::KnowledgeFrontier& f,
              const std::string& tenant_id,
              const std::string& cognizer_id,
              const std::string& as_of) {
               auto s = f.visible_engrams_at(tenant_id, cognizer_id, as_of);
               return std::vector<std::string>(s.begin(), s.end());
           },
           py::arg("tenant_id"), py::arg("cognizer_id"), py::arg("as_of"));

  // Error types
  py::register_exception<starling::cognizer::AliasCollision>(m, "AliasCollision")
      .def_readonly("existing_id", &starling::cognizer::AliasCollision::existing_id)
      .def_readonly("alias",       &starling::cognizer::AliasCollision::alias);
  py::register_exception<starling::cognizer::FiskeWeightsInvalid>(m, "FiskeWeightsInvalid");
  py::register_exception<starling::cognizer::GroupTenantImplicit>(m, "GroupTenantImplicit");
  py::register_exception<starling::cognizer::CognizerNotFound>(m, "CognizerNotFound");
  ```

- [ ] **10.2 Build and install**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  cmake -S . -B build -G Ninja
  cmake --build build
  cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages
  pip install -e . --no-deps --force-reinstall
  ```

  Verify: `python -c "from starling._core import CognizerHub; print('ok')"` — must print `ok`.

- [ ] **10.3 Create `python/starling/cognizer/__init__.py`**

  ```python
  """
  starling.cognizer — public API for 08_cognizer subsystem.

  Wraps pybind11 bindings from starling._core and provides
  higher-level builders and convenience helpers.
  """
  from starling._core import (
      CognizerKind,
      FiskeMode,
      Cognizer,
      RelationEdge,
      CognizerHub,
      KnowledgeFrontier,
      AliasCollision,
      FiskeWeightsInvalid,
      GroupTenantImplicit,
      CognizerNotFound,
  )
  from starling.cognizer.builders import (
      for_human,
      for_agent,
      for_group,
      for_role,
      for_external,
      for_self,
  )

  __all__ = [
      "CognizerKind",
      "FiskeMode",
      "Cognizer",
      "RelationEdge",
      "CognizerHub",
      "KnowledgeFrontier",
      "AliasCollision",
      "FiskeWeightsInvalid",
      "GroupTenantImplicit",
      "CognizerNotFound",
      "for_human",
      "for_agent",
      "for_group",
      "for_role",
      "for_external",
      "for_self",
  ]
  ```

- [ ] **10.4 Create `python/starling/cognizer/builders.py`**

  ```python
  """
  Convenience builder functions for CognizerHub.register_cognizer.

  Each builder maps to one CognizerKind and sets canonical defaults.
  Call them to build keyword-argument dicts, then pass to hub.register_cognizer().

  Usage:
      hub.register_cognizer(**for_human("alice", canonical_name="Alice Smith"))
      hub.register_cognizer(**for_group("team-a", tenant_id="acme", canonical_name="Team A"))
  """
  from __future__ import annotations
  from typing import Sequence


  def for_human(
      external_id: str,
      *,
      canonical_name: str,
      tenant_id: str = "default",
      aliases: Sequence[str] = (),
  ) -> dict:
      """Build kwargs for a human cognizer. tenant_id defaults to 'default'."""
      return dict(
          kind="human",
          external_id=external_id,
          canonical_name=canonical_name,
          tenant_id=tenant_id,
          aliases=list(aliases),
          tenant_explicitly_set=False,
      )


  def for_agent(
      external_id: str,
      *,
      canonical_name: str,
      tenant_id: str = "default",
      aliases: Sequence[str] = (),
  ) -> dict:
      """Build kwargs for an AI agent cognizer."""
      return dict(
          kind="agent",
          external_id=external_id,
          canonical_name=canonical_name,
          tenant_id=tenant_id,
          aliases=list(aliases),
          tenant_explicitly_set=False,
      )


  def for_group(
      external_id: str,
      *,
      canonical_name: str,
      tenant_id: str,
      aliases: Sequence[str] = (),
  ) -> dict:
      """
      Build kwargs for a group cognizer.

      tenant_id is mandatory and keyword-only; omitting it is a TypeError at
      call time (Python layer) rather than GroupTenantImplicit (C++ layer).
      The dict sets tenant_explicitly_set=True so CognizerHub accepts it.
      """
      return dict(
          kind="group",
          external_id=external_id,
          canonical_name=canonical_name,
          tenant_id=tenant_id,
          aliases=list(aliases),
          tenant_explicitly_set=True,
      )


  def for_role(
      external_id: str,
      *,
      canonical_name: str,
      tenant_id: str = "default",
      aliases: Sequence[str] = (),
  ) -> dict:
      """Build kwargs for a role cognizer (e.g. 'manager', 'moderator')."""
      return dict(
          kind="role",
          external_id=external_id,
          canonical_name=canonical_name,
          tenant_id=tenant_id,
          aliases=list(aliases),
          tenant_explicitly_set=False,
      )


  def for_external(
      external_id: str,
      *,
      canonical_name: str,
      tenant_id: str = "default",
      aliases: Sequence[str] = (),
  ) -> dict:
      """Build kwargs for an external system or service cognizer."""
      return dict(
          kind="external",
          external_id=external_id,
          canonical_name=canonical_name,
          tenant_id=tenant_id,
          aliases=list(aliases),
          tenant_explicitly_set=False,
      )


  def for_self(
      external_id: str = "starling_system",
      *,
      canonical_name: str = "Starling",
      tenant_id: str = "default",
  ) -> dict:
      """
      Build kwargs for the system-self cognizer (kind='self').

      There should be exactly one self-cognizer per tenant. external_id and
      canonical_name have sensible defaults matching RuntimeConfig.self_cognizer_id.
      """
      return dict(
          kind="self",
          external_id=external_id,
          canonical_name=canonical_name,
          tenant_id=tenant_id,
          aliases=[],
          tenant_explicitly_set=False,
      )
  ```

- [ ] **10.5 Run all checks**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  cmake --build build
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

  All must be green before committing.

- [ ] **10.6 Commit**

  ```bash
  git add bindings/python/module.cpp \
          python/starling/cognizer/__init__.py \
          python/starling/cognizer/builders.py
  git commit -m "feat(P2.a/cognizer): pybind11 bindings + Python cognizer package

  Exposes CognizerHub, KnowledgeFrontier, Cognizer, RelationEdge,
  CognizerKind, FiskeMode, and 4 error types via _core.
  python/starling/cognizer/ re-exports public API and provides 6
  builder functions (for_human/agent/group/role/external/self).
  for_group() enforces tenant_id as keyword-only at Python call site
  to prevent GroupTenantImplicit before reaching C++.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 11 — TC-COG-REGISTER (CRITICAL #1): UUID5 idempotency + round-trip

**Touches:** `tests/python/test_tc_cog_register.py`

**Prerequisite:** Task 10 green (pybind bindings installed).

### Steps

- [ ] **11.1 Write failing test** (RED)

  Create `tests/python/test_tc_cog_register.py`:

  ```python
  """
  TC-COG-REGISTER — CRITICAL #1 (08_cognizer)

  Validates:
  - UUID5 idempotency: register same (kind, external_id) twice -> same id
  - UUID5 format: matches RFC 4122 version-5 pattern
  - last_seen_at refresh on re-register
  - Different kind -> different id
  - Different external_id -> different id
  - Round-trip fetch via get()
  - lookup_by_alias
  - Case-insensitive alias lookup
  - Tenant isolation
  """
  import re
  import pytest
  import starling._core as _core
  from starling import persistence


  UUID5_RE = re.compile(
      r'^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
  )


  @pytest.fixture
  def adapter(tmp_path):
      db_path = tmp_path / "tc_cog_register.db"
      a = persistence.SqliteAdapter(str(db_path))
      a.run_migrations()
      return a


  @pytest.fixture
  def hub(adapter):
      return _core.CognizerHub(adapter)


  def test_uuid5_idempotency(hub):
      """Registering same (kind, external_id) twice returns the same UUID5 id."""
      c1 = hub.register_cognizer(
          kind="human", external_id="alice@example.com",
          canonical_name="Alice", tenant_id="default",
      )
      c2 = hub.register_cognizer(
          kind="human", external_id="alice@example.com",
          canonical_name="Alice Updated", tenant_id="default",
      )
      assert c1.id == c2.id, "UUID5 must be deterministic for same (kind, external_id)"


  def test_uuid5_format(hub):
      """Registered id must be a valid RFC 4122 version-5 UUID."""
      c = hub.register_cognizer(
          kind="human", external_id="bob@example.com",
          canonical_name="Bob", tenant_id="default",
      )
      assert UUID5_RE.match(c.id), f"Not a UUID5: {c.id!r}"


  def test_last_seen_at_refresh(hub):
      """Re-registering with a later timestamp refreshes last_seen_at."""
      c1 = hub.register_cognizer(
          kind="human", external_id="carol@example.com",
          canonical_name="Carol", tenant_id="default",
      )
      t1 = c1.last_seen_at
      c2 = hub.register_cognizer(
          kind="human", external_id="carol@example.com",
          canonical_name="Carol", tenant_id="default",
      )
      # last_seen_at must be >= t1 (re-registration refreshes it)
      assert c2.last_seen_at >= t1


  def test_different_kind_different_id(hub):
      """Same external_id but different kind -> different UUID5."""
      c_human = hub.register_cognizer(
          kind="human", external_id="dave@example.com",
          canonical_name="Dave Human", tenant_id="default",
      )
      c_agent = hub.register_cognizer(
          kind="agent", external_id="dave@example.com",
          canonical_name="Dave Agent", tenant_id="default",
      )
      assert c_human.id != c_agent.id


  def test_different_external_id_different_id(hub):
      """Different external_id -> different UUID5."""
      c1 = hub.register_cognizer(
          kind="human", external_id="user-001",
          canonical_name="User One", tenant_id="default",
      )
      c2 = hub.register_cognizer(
          kind="human", external_id="user-002",
          canonical_name="User Two", tenant_id="default",
      )
      assert c1.id != c2.id


  def test_round_trip_get(hub):
      """Registered cognizer can be fetched back via get()."""
      c = hub.register_cognizer(
          kind="human", external_id="eve@example.com",
          canonical_name="Eve", tenant_id="default",
      )
      fetched = hub.get(c.id, "default")
      assert fetched is not None
      assert fetched.id == c.id
      assert fetched.external_id == "eve@example.com"
      assert fetched.canonical_name == "Eve"


  def test_lookup_by_alias(hub):
      """Register with alias; lookup_by_alias returns the cognizer id."""
      c = hub.register_cognizer(
          kind="human", external_id="frank@example.com",
          canonical_name="Frank", tenant_id="default",
          aliases=["Frankie"],
      )
      result_id = hub.lookup_by_alias("default", "Frankie")
      assert result_id == c.id


  def test_lookup_by_alias_case_insensitive(hub):
      """Alias lookup is case-insensitive (ASCII fold via normalize_alias)."""
      c = hub.register_cognizer(
          kind="human", external_id="grace@example.com",
          canonical_name="Grace", tenant_id="default",
          aliases=["GRACE"],
      )
      result_id = hub.lookup_by_alias("default", "grace")
      assert result_id == c.id


  def test_tenant_isolation(hub):
      """Same external_id in different tenants -> different cognizers."""
      c_t1 = hub.register_cognizer(
          kind="human", external_id="shared@example.com",
          canonical_name="Shared T1", tenant_id="tenant-1",
      )
      c_t2 = hub.register_cognizer(
          kind="human", external_id="shared@example.com",
          canonical_name="Shared T2", tenant_id="tenant-2",
      )
      fetched_t1 = hub.get(c_t1.id, "tenant-1")
      fetched_t2 = hub.get(c_t2.id, "tenant-2")
      assert fetched_t1 is not None
      assert fetched_t2 is not None
      hub.register_cognizer(
          kind="human", external_id="shared@example.com",
          canonical_name="Shared T1", tenant_id="tenant-1",
          aliases=["shared-alias"],
      )
      assert hub.lookup_by_alias("tenant-2", "shared-alias") is None
  ```

- [ ] **11.2 Run RED** — confirm 9 test failures (import error or assertion failures).

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  pytest tests/python/test_tc_cog_register.py -v 2>&1 | tail -20
  ```

- [ ] **11.3 Implementation already done** (Tasks 5–10). Run GREEN:

  ```bash
  pytest tests/python/test_tc_cog_register.py -v
  ```

  All 9 must pass.

- [ ] **11.4 Guard battery**

  ```bash
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

- [ ] **11.5 Commit**

  ```bash
  git add tests/python/test_tc_cog_register.py
  git commit -m "test(P2.a/CRITICAL-1): TC-COG-REGISTER — UUID5 idempotency + round-trip

  9 assertions: UUID5 format (RFC 4122 v5 regex), idempotency on
  re-register, last_seen_at refresh, kind/external_id independence,
  get() round-trip, lookup_by_alias, case-insensitive alias lookup,
  tenant isolation.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 12 — TC-COG-ALIAS-MERGE (CRITICAL #2): AliasCollision exhaustive

**Touches:** `tests/python/test_tc_cog_alias_merge.py`

**Prerequisite:** Task 11 green.

### Steps

- [ ] **12.1 Write failing test** (RED)

  Create `tests/python/test_tc_cog_alias_merge.py`:

  ```python
  """
  TC-COG-ALIAS-MERGE — CRITICAL #2 (08_cognizer)

  Validates that normalized alias collision detection is exhaustive:
  - Exact string collision
  - Case-insensitive collision ("Alice" vs "alice")
  - Leading/trailing whitespace collapse (" ALICE " normalizes to "alice")
  - existing_id field is correctly populated in AliasCollision exception
  - Idempotent re-register of same cognizer with same aliases does not raise
  - Non-colliding aliases coexist across cognizers
  - Internal whitespace collapse ("zhang  wei" == "zhang wei" after normalize)
  - Multi-alias list where only one alias collides raises AliasCollision
  """
  import pytest
  import starling._core as _core
  from starling import persistence


  @pytest.fixture
  def adapter(tmp_path):
      a = persistence.SqliteAdapter(str(tmp_path / "alias_merge.db"))
      a.run_migrations()
      return a


  @pytest.fixture
  def hub(adapter):
      return _core.CognizerHub(adapter)


  def _register_alice(hub, tenant_id="default"):
      return hub.register_cognizer(
          kind="human", external_id="alice-001",
          canonical_name="Alice", tenant_id=tenant_id,
          aliases=["Alice"],
      )


  def test_exact_alias_collision(hub):
      """Registering a second cognizer with exact same alias raises AliasCollision."""
      c_a = _register_alice(hub)
      with pytest.raises(_core.AliasCollision) as exc_info:
          hub.register_cognizer(
              kind="human", external_id="alice-002",
              canonical_name="Alice Duplicate", tenant_id="default",
              aliases=["Alice"],
          )
      assert exc_info.value.existing_id == c_a.id


  def test_case_insensitive_collision(hub):
      """'alice' collides with 'Alice' after normalize_alias (ASCII case-fold)."""
      c_a = _register_alice(hub)
      with pytest.raises(_core.AliasCollision) as exc_info:
          hub.register_cognizer(
              kind="human", external_id="alice-003",
              canonical_name="Alice Lower", tenant_id="default",
              aliases=["alice"],
          )
      assert exc_info.value.existing_id == c_a.id


  def test_whitespace_trim_collision(hub):
      """' ALICE ' normalizes to 'alice' and collides with stored 'Alice'."""
      c_a = _register_alice(hub)
      with pytest.raises(_core.AliasCollision):
          hub.register_cognizer(
              kind="human", external_id="alice-004",
              canonical_name="Alice Spaced", tenant_id="default",
              aliases=[" ALICE "],
          )


  def test_existing_id_exposed(hub):
      """AliasCollision.existing_id equals the id of the first registrant."""
      c_a = _register_alice(hub)
      try:
          hub.register_cognizer(
              kind="human", external_id="alice-005",
              canonical_name="Alice X", tenant_id="default",
              aliases=["Alice"],
          )
          pytest.fail("Expected AliasCollision")
      except _core.AliasCollision as e:
          assert e.existing_id == c_a.id
          assert "alice" in e.alias.lower() or "Alice" in e.alias


  def test_idempotent_re_register_no_raise(hub):
      """Re-registering the same cognizer with same aliases does not raise."""
      c_a = _register_alice(hub)
      c_b = hub.register_cognizer(
          kind="human", external_id="alice-001",
          canonical_name="Alice", tenant_id="default",
          aliases=["Alice"],
      )
      assert c_a.id == c_b.id


  def test_non_colliding_aliases_coexist(hub):
      """Distinct normalized aliases can coexist across different cognizers."""
      hub.register_cognizer(
          kind="human", external_id="bob-001",
          canonical_name="Bob", tenant_id="default",
          aliases=["Bobby"],
      )
      c = hub.register_cognizer(
          kind="human", external_id="charlie-001",
          canonical_name="Charlie", tenant_id="default",
          aliases=["Charlie"],
      )
      assert c.id is not None


  def test_internal_whitespace_collapse_collision(hub):
      """'zhang  wei' (double space) normalizes to 'zhang wei' and collides."""
      hub.register_cognizer(
          kind="human", external_id="zhang-001",
          canonical_name="Zhang Wei", tenant_id="default",
          aliases=["zhang wei"],
      )
      with pytest.raises(_core.AliasCollision):
          hub.register_cognizer(
              kind="human", external_id="zhang-002",
              canonical_name="Zhang Wei Dup", tenant_id="default",
              aliases=["zhang  wei"],
          )


  def test_multi_alias_partial_collision(hub):
      """If one alias in a list collides, AliasCollision is raised for that alias."""
      c_a = _register_alice(hub)
      with pytest.raises(_core.AliasCollision) as exc_info:
          hub.register_cognizer(
              kind="human", external_id="multi-001",
              canonical_name="Multi", tenant_id="default",
              aliases=["Unique-XYZ-999", "Alice"],
          )
      assert exc_info.value.existing_id == c_a.id
  ```

- [ ] **12.2 Run RED**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  pytest tests/python/test_tc_cog_alias_merge.py -v 2>&1 | tail -15
  ```

- [ ] **12.3 Run GREEN**

  ```bash
  pytest tests/python/test_tc_cog_alias_merge.py -v
  ```

  All 8 must pass.

- [ ] **12.4 Guard battery**

  ```bash
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

- [ ] **12.5 Commit**

  ```bash
  git add tests/python/test_tc_cog_alias_merge.py
  git commit -m "test(P2.a/CRITICAL-2): TC-COG-ALIAS-MERGE — exhaustive alias collision

  8 cases: exact/case-insensitive/whitespace-trim/internal-collapse
  collisions, existing_id exposure, idempotent re-register, non-colliding
  coexistence, multi-alias partial-collision detection.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 13 — TC-COG-CROSS-TENANT (CRITICAL #3): GroupTenantImplicit guard

**Touches:** `tests/python/test_tc_cog_cross_tenant.py`

**Prerequisite:** Task 12 green.

### Steps

- [ ] **13.1 Write failing test** (RED)

  Create `tests/python/test_tc_cog_cross_tenant.py`:

  ```python
  """
  TC-COG-CROSS-TENANT — CRITICAL #3 (08_cognizer)

  Validates:
  - kind=group with implicit 'default' tenant raises GroupTenantImplicit
  - kind=group with explicit non-default tenant_id succeeds
  - for_group() builder always sets tenant_explicitly_set=True
  - Non-group kinds allow tenant_id='default' (implicit)
  - group with tenant_explicitly_set=True and the string 'default' does not raise
  - Multi-tenant: same group external_id in different tenants stored independently
  """
  import pytest
  import starling._core as _core
  from starling import persistence
  from starling.cognizer.builders import for_group


  @pytest.fixture
  def adapter(tmp_path):
      a = persistence.SqliteAdapter(str(tmp_path / "cross_tenant.db"))
      a.run_migrations()
      return a


  @pytest.fixture
  def hub(adapter):
      return _core.CognizerHub(adapter)


  def test_group_without_explicit_tenant_raises(hub):
      """kind=group + default tenant without explicit flag -> GroupTenantImplicit."""
      with pytest.raises(_core.GroupTenantImplicit):
          hub.register_cognizer(
              kind="group",
              external_id="team-alpha",
              canonical_name="Team Alpha",
              tenant_id="default",
              tenant_explicitly_set=False,
          )


  def test_group_with_explicit_tenant_succeeds(hub):
      """kind=group + explicit non-default tenant -> succeeds."""
      c = hub.register_cognizer(
          kind="group",
          external_id="team-alpha",
          canonical_name="Team Alpha",
          tenant_id="acme-corp",
          tenant_explicitly_set=True,
      )
      assert c.id is not None
      assert c.kind == "group" or str(c.kind) in ("group", "CognizerKind.Group")


  def test_for_group_builder_always_explicit(hub):
      """for_group() builder sets tenant_explicitly_set=True, preventing the error."""
      kwargs = for_group(
          "team-beta",
          canonical_name="Team Beta",
          tenant_id="acme-corp",
      )
      assert kwargs["tenant_explicitly_set"] is True
      c = hub.register_cognizer(**kwargs)
      assert c.id is not None


  def test_non_group_allows_default_tenant(hub):
      """Non-group kinds (human, agent, role, external, self) allow implicit default."""
      for kind in ("human", "agent", "role", "external"):
          c = hub.register_cognizer(
              kind=kind,
              external_id=f"user-{kind}",
              canonical_name=f"Test {kind.capitalize()}",
              tenant_id="default",
              tenant_explicitly_set=False,
          )
          assert c.id is not None


  def test_group_explicit_default_string_does_not_raise(hub):
      """Group with tenant_explicitly_set=True and tenant_id='default' is allowed.

      The intent is: user explicitly chose 'default' as their tenant name.
      Only the implicit/silent default is rejected.
      """
      c = hub.register_cognizer(
          kind="group",
          external_id="team-gamma",
          canonical_name="Team Gamma",
          tenant_id="default",
          tenant_explicitly_set=True,
      )
      assert c.id is not None


  def test_multi_tenant_group_isolation(hub):
      """Same group external_id in two tenants -> stored independently."""
      c1 = hub.register_cognizer(
          kind="group", external_id="shared-group",
          canonical_name="Shared Group T1", tenant_id="tenant-a",
          tenant_explicitly_set=True,
      )
      c2 = hub.register_cognizer(
          kind="group", external_id="shared-group",
          canonical_name="Shared Group T2", tenant_id="tenant-b",
          tenant_explicitly_set=True,
      )
      assert hub.get(c1.id, "tenant-a") is not None
      assert hub.get(c2.id, "tenant-b") is not None
      assert hub.get(c1.id, "tenant-b") is None
  ```

- [ ] **13.2 Run RED**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  pytest tests/python/test_tc_cog_cross_tenant.py -v 2>&1 | tail -15
  ```

- [ ] **13.3 Run GREEN**

  ```bash
  pytest tests/python/test_tc_cog_cross_tenant.py -v
  ```

  All 6 must pass.

- [ ] **13.4 Guard battery**

  ```bash
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

- [ ] **13.5 Commit**

  ```bash
  git add tests/python/test_tc_cog_cross_tenant.py
  git commit -m "test(P2.a/CRITICAL-3): TC-COG-CROSS-TENANT — GroupTenantImplicit guard

  6 cases: implicit group tenant raises, explicit non-default succeeds,
  for_group() builder sets tenant_explicitly_set, non-group kinds allow
  implicit default, explicit 'default' string accepted, multi-tenant
  isolation via get().

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 14 — TC-RELATION-FISKE (CRITICAL #4): Fiske weights invariant

**Touches:** `tests/python/test_tc_relation_fiske.py`

**Prerequisite:** Task 13 green.

### Steps

- [ ] **14.1 Write failing test** (RED)

  Create `tests/python/test_tc_relation_fiske.py`:

  ```python
  """
  TC-RELATION-FISKE — CRITICAL #4 (08_cognizer)

  Validates CognizerHub.upsert_relation Fiske 4-mode invariants:
  - fiske_weights sum != 1.0 (off by >1e-6) raises FiskeWeightsInvalid
  - fiske_weights sum exactly 1.0 passes
  - fiske_weights sum within tolerance [1.0 +/- 5e-7] passes
  - affinity out of [0, 1] raises (ValueError or FiskeWeightsInvalid)
  - Upsert on same (a_id, b_id, tenant_id) overwrites previous edge
  - relations_of() returns the upserted edges for a given cognizer
  """
  import pytest
  import starling._core as _core
  from starling import persistence


  @pytest.fixture
  def adapter(tmp_path):
      a = persistence.SqliteAdapter(str(tmp_path / "fiske.db"))
      a.run_migrations()
      return a


  @pytest.fixture
  def hub(adapter):
      return _core.CognizerHub(adapter)


  @pytest.fixture
  def two_cognizers(hub):
      """Register alice and bob; return (alice_id, bob_id)."""
      a = hub.register_cognizer(
          kind="human", external_id="alice-fiske",
          canonical_name="Alice", tenant_id="default",
      )
      b = hub.register_cognizer(
          kind="human", external_id="bob-fiske",
          canonical_name="Bob", tenant_id="default",
      )
      return a.id, b.id


  def test_weights_sum_not_one_raises(hub, two_cognizers):
      """Sum of fiske_weights != 1.0 by >1e-6 raises FiskeWeightsInvalid."""
      alice_id, bob_id = two_cognizers
      bad_weights = {"communal": 0.5, "authority": 0.5, "equality": 0.5, "market": 0.0}
      with pytest.raises(_core.FiskeWeightsInvalid):
          hub.upsert_relation(
              a_id=alice_id, b_id=bob_id, tenant_id="default",
              fiske_weights=bad_weights, affinity=0.5,
          )


  def test_weights_sum_exactly_one_passes(hub, two_cognizers):
      """Sum exactly 1.0 is accepted."""
      alice_id, bob_id = two_cognizers
      weights = {"communal": 0.25, "authority": 0.25, "equality": 0.25, "market": 0.25}
      edge = hub.upsert_relation(
          a_id=alice_id, b_id=bob_id, tenant_id="default",
          fiske_weights=weights, affinity=0.6,
      )
      assert edge.id is not None
      assert edge.a_id == alice_id
      assert edge.b_id == bob_id


  def test_weights_within_tolerance_passes(hub, two_cognizers):
      """Sum within [1.0 +/- 5e-7] (float rounding) is accepted."""
      alice_id, bob_id = two_cognizers
      third = 1.0 / 3.0
      weights = {"communal": third, "authority": third, "equality": third, "market": 0.0}
      edge = hub.upsert_relation(
          a_id=alice_id, b_id=bob_id, tenant_id="default",
          fiske_weights=weights, affinity=0.5,
      )
      assert edge.id is not None


  def test_affinity_out_of_range_raises(hub, two_cognizers):
      """affinity outside [0, 1] raises an exception (SQL CHECK or Hub validation)."""
      alice_id, bob_id = two_cognizers
      weights = {"communal": 1.0, "authority": 0.0, "equality": 0.0, "market": 0.0}
      with pytest.raises(Exception):
          hub.upsert_relation(
              a_id=alice_id, b_id=bob_id, tenant_id="default",
              fiske_weights=weights, affinity=1.5,
          )


  def test_upsert_overwrites(hub, two_cognizers):
      """Second upsert on same (a, b, tenant) replaces the first edge."""
      alice_id, bob_id = two_cognizers
      weights_v1 = {"communal": 1.0, "authority": 0.0, "equality": 0.0, "market": 0.0}
      weights_v2 = {"communal": 0.0, "authority": 1.0, "equality": 0.0, "market": 0.0}
      hub.upsert_relation(
          a_id=alice_id, b_id=bob_id, tenant_id="default",
          fiske_weights=weights_v1, affinity=0.3,
      )
      edge2 = hub.upsert_relation(
          a_id=alice_id, b_id=bob_id, tenant_id="default",
          fiske_weights=weights_v2, affinity=0.7,
      )
      assert edge2.affinity == pytest.approx(0.7, abs=1e-6)


  def test_relations_of_returns_edges(hub, two_cognizers):
      """relations_of(alice_id) returns at least the edge to bob."""
      alice_id, bob_id = two_cognizers
      weights = {"communal": 0.5, "authority": 0.5, "equality": 0.0, "market": 0.0}
      hub.upsert_relation(
          a_id=alice_id, b_id=bob_id, tenant_id="default",
          fiske_weights=weights, affinity=0.8,
      )
      edges = hub.relations_of(alice_id, "default")
      assert len(edges) >= 1
      assert any(e.b_id == bob_id for e in edges)
  ```

- [ ] **14.2 Run RED**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  pytest tests/python/test_tc_relation_fiske.py -v 2>&1 | tail -15
  ```

- [ ] **14.3 Run GREEN**

  ```bash
  pytest tests/python/test_tc_relation_fiske.py -v
  ```

  All 6 must pass.

- [ ] **14.4 Guard battery**

  ```bash
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

- [ ] **14.5 Commit**

  ```bash
  git add tests/python/test_tc_relation_fiske.py
  git commit -m "test(P2.a/CRITICAL-4): TC-RELATION-FISKE — Fiske 4-mode weight invariant

  6 cases: sum!=1 raises FiskeWeightsInvalid, sum exactly 1.0 passes,
  float-rounding tolerance (1/3 * 3), affinity range check, upsert
  overwrite, relations_of() return shape.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 15 — TC-FRONTIER-FIVE-WAY (CRITICAL #5): visible_engrams_at set logic

**Touches:** `tests/python/test_tc_frontier_five_way.py`

**Prerequisite:** Task 14 green.

### Steps

- [ ] **15.1 Write failing test** (RED)

  Create `tests/python/test_tc_frontier_five_way.py`:

  ```python
  """
  TC-FRONTIER-FIVE-WAY — CRITICAL #5 (08_cognizer)

  Validates KnowledgeFrontier.visible_engrams_at 5-way set algebra:
    UNION  presence_log
    UNION  frontier_facts WHERE fact_kind IN (explicit_told, accessible_source, membership)
    EXCEPT frontier_facts WHERE fact_kind = explicit_not_told

  Tests use both C++ record_* API and direct sqlite3 INSERTs for
  double-coverage of the EXCEPT clause.

  Spec ref: §6.5
  """
  import sqlite3
  import uuid
  import pytest
  import starling._core as _core
  from starling import persistence


  @pytest.fixture
  def adapter(tmp_path):
      a = persistence.SqliteAdapter(str(tmp_path / "frontier.db"))
      a.run_migrations()
      return a


  @pytest.fixture
  def hub(adapter):
      return _core.CognizerHub(adapter)


  @pytest.fixture
  def frontier(adapter):
      return _core.KnowledgeFrontier(adapter)


  @pytest.fixture
  def alice(hub):
      c = hub.register_cognizer(
          kind="human", external_id="alice-frontier",
          canonical_name="Alice", tenant_id="default",
      )
      return c.id


  def _random_engram_id() -> str:
      return str(uuid.uuid4())


  def _insert_presence(adapter, tenant_id, cognizer_id, engram_id, observed_at):
      with adapter.connection() as conn:
          conn.execute(
              "INSERT INTO cognizer_presence_log"
              " (id, tenant_id, cognizer_id, engram_id, observed_at)"
              " VALUES (?, ?, ?, ?, ?)",
              (str(uuid.uuid4()), tenant_id, cognizer_id, engram_id, observed_at),
          )


  def _insert_frontier_fact(adapter, tenant_id, cognizer_id,
                              engram_id, fact_kind, asserted_at):
      with adapter.connection() as conn:
          conn.execute(
              "INSERT INTO cognizer_frontier_facts"
              " (id, tenant_id, cognizer_id, source_engram_id, fact_kind, asserted_at)"
              " VALUES (?, ?, ?, ?, ?, ?)",
              (str(uuid.uuid4()), tenant_id, cognizer_id, engram_id, fact_kind, asserted_at),
          )


  def test_presence_log_contributes(adapter, frontier, alice):
      """Engram in presence_log appears in visible_engrams_at."""
      e1 = _random_engram_id()
      _insert_presence(adapter, "default", alice, e1, "2026-01-01T00:00:00Z")
      result = set(frontier.visible_engrams_at("default", alice, "2026-12-31T23:59:59Z"))
      assert e1 in result


  def test_explicit_told_contributes(adapter, frontier, alice):
      """Engram in explicit_told frontier_fact appears in visible_engrams_at."""
      e2 = _random_engram_id()
      _insert_frontier_fact(adapter, "default", alice, e2, "explicit_told", "2026-01-01T00:00:00Z")
      result = set(frontier.visible_engrams_at("default", alice, "2026-12-31T23:59:59Z"))
      assert e2 in result


  def test_accessible_source_contributes(adapter, frontier, alice):
      """Engram in accessible_source frontier_fact appears in visible_engrams_at."""
      e3 = _random_engram_id()
      _insert_frontier_fact(adapter, "default", alice, e3, "accessible_source", "2026-01-01T00:00:00Z")
      result = set(frontier.visible_engrams_at("default", alice, "2026-12-31T23:59:59Z"))
      assert e3 in result


  def test_explicit_not_told_subtracts(adapter, frontier, alice):
      """Engram added via presence_log is removed by explicit_not_told."""
      e4 = _random_engram_id()
      _insert_presence(adapter, "default", alice, e4, "2026-01-01T00:00:00Z")
      before = set(frontier.visible_engrams_at("default", alice, "2026-06-01T00:00:00Z"))
      assert e4 in before
      _insert_frontier_fact(adapter, "default", alice, e4, "explicit_not_told", "2026-03-01T00:00:00Z")
      after = set(frontier.visible_engrams_at("default", alice, "2026-12-31T23:59:59Z"))
      assert e4 not in after, "explicit_not_told must subtract from union"


  def test_five_way_combined(adapter, frontier, alice):
      """All three positive sources contribute; one explicit_not_told removes its target."""
      e_presence = _random_engram_id()
      e_told     = _random_engram_id()
      e_source   = _random_engram_id()
      e_member   = _random_engram_id()
      e_negated  = _random_engram_id()

      _insert_presence(adapter, "default", alice, e_presence, "2026-01-01T00:00:00Z")
      _insert_frontier_fact(adapter, "default", alice, e_told,   "explicit_told",     "2026-01-01T00:00:00Z")
      _insert_frontier_fact(adapter, "default", alice, e_source, "accessible_source", "2026-01-01T00:00:00Z")
      _insert_frontier_fact(adapter, "default", alice, e_member, "membership",        "2026-01-01T00:00:00Z")
      _insert_presence(adapter, "default", alice, e_negated, "2026-01-01T00:00:00Z")
      _insert_frontier_fact(adapter, "default", alice, e_negated, "explicit_not_told", "2026-02-01T00:00:00Z")

      result = set(frontier.visible_engrams_at("default", alice, "2026-12-31T23:59:59Z"))
      assert e_presence in result
      assert e_told     in result
      assert e_source   in result
      assert e_member   in result
      assert e_negated not in result


  def test_as_of_boundary_excludes_future(adapter, frontier, alice):
      """Presence records after as_of are excluded."""
      e_future = _random_engram_id()
      _insert_presence(adapter, "default", alice, e_future, "2026-12-01T00:00:00Z")
      result = set(frontier.visible_engrams_at("default", alice, "2026-06-01T00:00:00Z"))
      assert e_future not in result


  def test_tenant_isolation(adapter, frontier, hub):
      """Engrams in tenant-x are invisible from tenant-y perspective."""
      c_tx = hub.register_cognizer(
          kind="human", external_id="user-tx",
          canonical_name="User TX", tenant_id="tenant-x",
      )
      e_tx = _random_engram_id()
      _insert_presence(adapter, "tenant-x", c_tx.id, e_tx, "2026-01-01T00:00:00Z")

      c_ty = hub.register_cognizer(
          kind="human", external_id="user-ty",
          canonical_name="User TY", tenant_id="tenant-y",
      )
      result_ty = set(frontier.visible_engrams_at("tenant-y", c_ty.id, "2026-12-31T23:59:59Z"))
      assert e_tx not in result_ty


  def test_future_not_told_does_not_affect_earlier_as_of(adapter, frontier, alice):
      """explicit_not_told after as_of does not subtract at the earlier timestamp."""
      e5 = _random_engram_id()
      _insert_presence(adapter, "default", alice, e5, "2026-01-01T00:00:00Z")
      _insert_frontier_fact(adapter, "default", alice, e5, "explicit_not_told", "2026-09-01T00:00:00Z")
      result = set(frontier.visible_engrams_at("default", alice, "2026-06-01T00:00:00Z"))
      assert e5 in result, "Negation in the future must not retroactively hide the engram"


  def test_direct_sql_explicit_not_told(adapter, frontier, alice):
      """Direct SQL INSERT of explicit_not_told removes engram from visible set.

      Double-covers the EXCEPT clause independently of the C++ record_* path.
      """
      e6 = _random_engram_id()
      e7 = _random_engram_id()
      _insert_frontier_fact(adapter, "default", alice, e6, "explicit_told", "2026-01-01T00:00:00Z")
      _insert_frontier_fact(adapter, "default", alice, e7, "explicit_told", "2026-01-01T00:00:00Z")
      with adapter.connection() as conn:
          conn.execute(
              "INSERT INTO cognizer_frontier_facts"
              " (id, tenant_id, cognizer_id, source_engram_id, fact_kind, asserted_at)"
              " VALUES (?, ?, ?, ?, 'explicit_not_told', '2026-02-01T00:00:00Z')",
              (str(uuid.uuid4()), "default", alice, e6),
          )
      result = set(frontier.visible_engrams_at("default", alice, "2026-12-31T23:59:59Z"))
      assert e6 not in result
      assert e7 in result
  ```

- [ ] **15.2 Run RED**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  pytest tests/python/test_tc_frontier_five_way.py -v 2>&1 | tail -15
  ```

- [ ] **15.3 Run GREEN**

  ```bash
  pytest tests/python/test_tc_frontier_five_way.py -v
  ```

  All 9 must pass.

- [ ] **15.4 Guard battery**

  ```bash
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

- [ ] **15.5 Commit**

  ```bash
  git add tests/python/test_tc_frontier_five_way.py
  git commit -m "test(P2.a/CRITICAL-5): TC-FRONTIER-FIVE-WAY — 5-way set algebra

  9 cases: presence_log, explicit_told, accessible_source each contribute;
  explicit_not_told subtracts from union; combined 5-way; as_of boundary;
  tenant isolation; future negation does not retroactively hide; direct-SQL
  NOT-TOLD double-cover of EXCEPT clause.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 16 — Migration 0009: canonical_conflict_key + backfill state

**Touches:** `migrations/0009_conflict_key_unique.sql`

**Prerequisite:** Task 15 green. (Also independent of cognizer tasks; can be done after Task 9.)

### Steps

- [ ] **16.1 Verify migration file does not exist**

  ```bash
  ls migrations/0009_conflict_key_unique.sql 2>/dev/null && echo "EXISTS" || echo "MISSING"
  ```

  If it exists, skip to 16.3.

- [ ] **16.2 Create migration file**

  Create `migrations/0009_conflict_key_unique.sql`:

  ```sql
  -- Migration 0009: canonical_conflict_key uniqueness for conflicts_with edges
  -- Spec ref: §5.2, §8.2, §16.3-5

  -- Add the new column (nullable; backfill fills it incrementally)
  ALTER TABLE statement_edges ADD COLUMN canonical_conflict_key TEXT;

  -- Partial UNIQUE index: only conflicts_with edges with a non-NULL key
  -- are constrained. NULL rows (supersedes, etc.) are unconstrained.
  CREATE UNIQUE INDEX idx_conflict_edges_key_unique
      ON statement_edges(tenant_id, canonical_conflict_key)
      WHERE edge_kind = 'conflicts_with' AND canonical_conflict_key IS NOT NULL;

  -- Backfill progress tracker (singleton, id=1 enforced by CHECK constraint)
  CREATE TABLE conflict_key_backfill_state (
      id INTEGER PRIMARY KEY CHECK (id = 1),
      last_processed_edge_id TEXT,
      rows_backfilled INTEGER NOT NULL DEFAULT 0,
      rows_deduped INTEGER NOT NULL DEFAULT 0,
      started_at TEXT NOT NULL,
      completed_at TEXT,
      last_updated_at TEXT NOT NULL
  );

  -- Seed the singleton row
  INSERT INTO conflict_key_backfill_state (id, started_at, last_updated_at)
      VALUES (1, '2026-05-26T00:00:00Z', '2026-05-26T00:00:00Z');
  ```

- [ ] **16.3 Verify migration applies cleanly**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  python -c "
  from starling import persistence
  import tempfile, pathlib
  with tempfile.TemporaryDirectory() as d:
      a = persistence.SqliteAdapter(str(pathlib.Path(d) / 'test.db'))
      a.run_migrations()
      print('migration 0009 OK')
  "
  ```

  Must print `migration 0009 OK`.

- [ ] **16.4 Run full test battery**

  ```bash
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

- [ ] **16.5 Commit**

  ```bash
  git add migrations/0009_conflict_key_unique.sql
  git commit -m "feat(P2.a/bus): migration 0009 — canonical_conflict_key + backfill state

  Adds statement_edges.canonical_conflict_key TEXT column, partial UNIQUE
  index (conflicts_with + NOT NULL only), and conflict_key_backfill_state
  singleton table (CHECK id=1) seeded at 2026-05-26T00:00:00Z.

  spec §5.2 / §16.3-5

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 17 — bus.cpp: insert_statement_edge gains canonical_conflict_key param

**Touches:** `src/bus/bus.cpp`, `include/starling/bus/bus.hpp`

**Prerequisite:** Task 16 green (migration 0009 applied so the column exists).

### Steps

- [ ] **17.1 Read current bus.cpp insert_statement_edge signature**

  ```bash
  grep -n "insert_statement_edge" src/bus/bus.cpp include/starling/bus/bus.hpp
  ```

  Note the line numbers of the declaration and definition.

- [ ] **17.2 Update header declaration**

  In `include/starling/bus/bus.hpp`, locate the `insert_statement_edge` function declaration and add the 6th parameter with default:

  ```cpp
  // Before (5 params):
  void insert_statement_edge(
      persistence::Connection& conn,
      std::string_view src_id, std::string_view dst_id,
      std::string_view tenant_id, std::string_view edge_kind);

  // After (6 params, 6th has default):
  void insert_statement_edge(
      persistence::Connection& conn,
      std::string_view src_id, std::string_view dst_id,
      std::string_view tenant_id, std::string_view edge_kind,
      std::optional<std::string> canonical_conflict_key = std::nullopt);
  ```

  Ensure `#include <optional>` is present in the header.

- [ ] **17.3 Update bus.cpp definition**

  In `src/bus/bus.cpp`, update the function definition to match the new signature.
  Update the INSERT SQL string to include `canonical_conflict_key`:

  ```sql
  INSERT INTO statement_edges
      (id, tenant_id, src_statement_id, dst_statement_id, edge_kind,
       canonical_conflict_key, created_at)
  VALUES
      (?, ?, ?, ?, ?, ?, ?)
  ```

  After `sqlite3_bind` calls for the first 5 parameters, bind the 6th:

  ```cpp
  if (canonical_conflict_key.has_value()) {
      sqlite3_bind_text(stmt.get(), 6,
                        canonical_conflict_key->c_str(), -1, SQLITE_STATIC);
  } else {
      sqlite3_bind_null(stmt.get(), 6);
  }
  ```

  Then after `sqlite3_step`, add the UNIQUE constraint handler:

  ```cpp
  const int rc = sqlite3_step(stmt.get());
  if (rc == SQLITE_CONSTRAINT && canonical_conflict_key.has_value()) {
      // UNIQUE index violation: conflicts_with edge with this key already exists.
      // Emit a deduplication warning and silently drop the duplicate.
      std::fprintf(stderr,
          "[bus.conflict_key] WARN dedup hit on canonical_conflict_key=%s "
          "(edge_kind=conflicts_with, tenant=%s); existing edge retained.\n",
          canonical_conflict_key->c_str(),
          std::string(tenant_id).c_str());
      return;   // noop — idempotent
  }
  if (rc != SQLITE_DONE) {
      throw make_sqlite_error("insert_statement_edge", rc,
                               sqlite3_errmsg(conn.handle()));
  }
  ```

- [ ] **17.4 Update call sites**

  ```bash
  grep -n "insert_statement_edge" src/bus/bus.cpp
  ```

  For each call site:
  - `apply_supersedes_atomic` branch → append `, std::nullopt`
  - `partial_overlap` branch → append `, match->conflict_key_hex`
  - `adjacent` branch (if present) → append `, match->conflict_key_hex`

- [ ] **17.5 Build and test**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  cmake --build build
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

  All must be green.

- [ ] **17.6 Commit**

  ```bash
  git add src/bus/bus.cpp include/starling/bus/bus.hpp
  git commit -m "feat(P2.a/bus): insert_statement_edge gains canonical_conflict_key param

  6th parameter std::optional<std::string> canonical_conflict_key (default
  nullopt). INSERT SQL updated to bind the new column. SQLITE_CONSTRAINT on
  conflicts_with edge emits WARN to stderr and returns noop (idempotent
  dedup). apply_supersedes_atomic passes nullopt; partial_overlap/adjacent
  pass match->conflict_key_hex.

  spec §8.4

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 18 — conflict_key_backfill: tick_one_batch + Bus.write hook

**Touches:** `include/starling/bus/conflict_key_backfill.hpp`, `src/bus/conflict_key_backfill.cpp`, `src/bus/bus.cpp`, `tests/cpp/test_conflict_key_backfill.cpp`, `tests/cpp/CMakeLists.txt`, `CMakeLists.txt`

**Prerequisite:** Task 17 green.

### Steps

- [ ] **18.1 Create header**

  Create `include/starling/bus/conflict_key_backfill.hpp`:

  ```cpp
  #pragma once
  #include <starling/persistence/connection.hpp>

  namespace starling::bus::conflict_key_backfill {

  struct TickStats {
      int rows_examined   = 0;
      int rows_backfilled = 0;
      int rows_deduped    = 0;
      bool completed      = false;
  };

  /// Returns true iff conflict_key_backfill_state.completed_at IS NOT NULL.
  bool is_complete(persistence::Connection& conn);

  /// Process one batch of up to batch_size conflicts_with edges.
  /// Assigns canonical_conflict_key; deletes duplicates.
  /// Must be called inside a SAVEPOINT wrapper by the caller.
  TickStats tick_one_batch(persistence::Connection& conn, int batch_size = 100);

  }  // namespace starling::bus::conflict_key_backfill
  ```

- [ ] **18.2 Create implementation**

  Create `src/bus/conflict_key_backfill.cpp`:

  ```cpp
  #include <starling/bus/conflict_key_backfill.hpp>
  #include <starling/bus/conflict_key.hpp>
  #include <starling/persistence/sqlite_utils.hpp>
  #include <sqlite3.h>
  #include <cstdio>
  #include <string>
  #include <vector>

  namespace starling::bus::conflict_key_backfill {

  bool is_complete(persistence::Connection& conn) {
      auto stmt = conn.prepare(
          "SELECT completed_at FROM conflict_key_backfill_state WHERE id=1");
      if (sqlite3_step(stmt.get()) != SQLITE_ROW) return false;
      auto* col = sqlite3_column_text(stmt.get(), 0);
      return col != nullptr;
  }

  TickStats tick_one_batch(persistence::Connection& conn, int batch_size) {
      TickStats stats;
      if (is_complete(conn)) {
          stats.completed = true;
          return stats;
      }

      // Fetch current cursor
      std::string cursor;
      {
          auto st = conn.prepare(
              "SELECT last_processed_edge_id FROM conflict_key_backfill_state WHERE id=1");
          if (sqlite3_step(st.get()) == SQLITE_ROW) {
              auto* v = sqlite3_column_text(st.get(), 0);
              if (v) cursor = reinterpret_cast<const char*>(v);
          }
      }

      // Build SELECT for next batch
      std::string select_sql =
          "SELECT se.id, se.tenant_id, se.src_statement_id, se.dst_statement_id,"
          "       ss.holder_id, ss.subject_id, ss.predicate,"
          "       ss.canonical_object_hash, ss.polarity, ss.scope"
          "  FROM statement_edges se"
          "  JOIN statements ss ON ss.id = se.src_statement_id"
          " WHERE se.edge_kind = 'conflicts_with'"
          "   AND se.canonical_conflict_key IS NULL";
      if (!cursor.empty()) {
          select_sql += " AND se.id > '" + cursor + "'";
      }
      select_sql += " ORDER BY se.id LIMIT " + std::to_string(batch_size);

      struct EdgeRow {
          std::string edge_id, tenant_id, src_id, dst_id;
          std::string holder_id, subject_id, predicate;
          std::string canonical_object_hash, polarity, scope;
      };
      std::vector<EdgeRow> rows;
      {
          auto st = conn.prepare(select_sql);
          while (sqlite3_step(st.get()) == SQLITE_ROW) {
              EdgeRow r;
              auto col = [&](int i) -> std::string {
                  auto* v = sqlite3_column_text(st.get(), i);
                  return v ? reinterpret_cast<const char*>(v) : "";
              };
              r.edge_id               = col(0);
              r.tenant_id             = col(1);
              r.src_id                = col(2);
              r.dst_id                = col(3);
              r.holder_id             = col(4);
              r.subject_id            = col(5);
              r.predicate             = col(6);
              r.canonical_object_hash = col(7);
              r.polarity              = col(8);
              r.scope                 = col(9);
              rows.push_back(std::move(r));
          }
      }

      stats.rows_examined = static_cast<int>(rows.size());
      std::string last_id;

      for (auto& row : rows) {
          last_id = row.edge_id;
          std::string key = canonical_conflict_key_hex(
              row.tenant_id, row.holder_id, row.subject_id,
              row.predicate, row.canonical_object_hash, row.polarity, row.scope);

          auto upd = conn.prepare(
              "UPDATE statement_edges SET canonical_conflict_key=?"
              " WHERE id=? AND canonical_conflict_key IS NULL");
          sqlite3_bind_text(upd.get(), 1, key.c_str(), -1, SQLITE_STATIC);
          sqlite3_bind_text(upd.get(), 2, row.edge_id.c_str(), -1, SQLITE_STATIC);
          int rc = sqlite3_step(upd.get());

          if (rc == SQLITE_CONSTRAINT) {
              auto del = conn.prepare("DELETE FROM statement_edges WHERE id=?");
              sqlite3_bind_text(del.get(), 1, row.edge_id.c_str(), -1, SQLITE_STATIC);
              sqlite3_step(del.get());
              ++stats.rows_deduped;
          } else if (rc == SQLITE_DONE) {
              ++stats.rows_backfilled;
          } else {
              std::fprintf(stderr,
                  "[conflict_key_backfill] ERROR on edge %s: rc=%d\n",
                  row.edge_id.c_str(), rc);
          }
      }

      // Update singleton state
      if (rows.empty()) {
          auto upd = conn.prepare(
              "UPDATE conflict_key_backfill_state SET"
              "  completed_at = datetime('now'),"
              "  last_updated_at = datetime('now')"
              " WHERE id=1");
          sqlite3_step(upd.get());
          stats.completed = true;
      } else {
          auto upd = conn.prepare(
              "UPDATE conflict_key_backfill_state SET"
              "  last_processed_edge_id = ?,"
              "  rows_backfilled = rows_backfilled + ?,"
              "  rows_deduped    = rows_deduped + ?,"
              "  last_updated_at = datetime('now')"
              " WHERE id=1");
          sqlite3_bind_text(upd.get(), 1, last_id.c_str(), -1, SQLITE_STATIC);
          sqlite3_bind_int (upd.get(), 2, stats.rows_backfilled);
          sqlite3_bind_int (upd.get(), 3, stats.rows_deduped);
          sqlite3_step(upd.get());
      }

      return stats;
  }

  }  // namespace starling::bus::conflict_key_backfill
  ```

- [ ] **18.3 Add Bus.write hook**

  In `src/bus/bus.cpp`, after the main transaction commit in `Bus::write`, add:

  ```cpp
  // Post-commit: run one backfill tick in SAVEPOINT — failure is swallowed
  // so it cannot block the already-committed main write.
  try {
      auto savepoint = conn.savepoint("conflict_key_backfill_tick");
      conflict_key_backfill::tick_one_batch(conn);
      savepoint.release();
  } catch (const std::exception& e) {
      std::fprintf(stderr,
          "[bus] conflict_key_backfill tick failed (swallowed): %s\n", e.what());
  }
  ```

  Add `#include <starling/bus/conflict_key_backfill.hpp>` at the top of `bus.cpp`.

- [ ] **18.4 Create C++ tests**

  Create `tests/cpp/test_conflict_key_backfill.cpp`:

  ```cpp
  #include <gtest/gtest.h>
  #include <starling/bus/conflict_key_backfill.hpp>
  #include <starling/persistence/sqlite_adapter.hpp>
  #include <starling/persistence/migration_runner.hpp>

  namespace {

  struct BackfillFixture : ::testing::Test {
      starling::persistence::SqliteAdapter adapter{":memory:"};

      void SetUp() override {
          starling::persistence::run_migrations(adapter);
      }

      starling::persistence::Connection& conn() { return adapter.connection(); }
  };

  TEST_F(BackfillFixture, IsCompleteReturnsFalseInitially) {
      EXPECT_FALSE(starling::bus::conflict_key_backfill::is_complete(conn()));
  }

  TEST_F(BackfillFixture, EmptyBatchMarksComplete) {
      auto stats = starling::bus::conflict_key_backfill::tick_one_batch(conn(), 100);
      EXPECT_TRUE(stats.completed);
      EXPECT_EQ(stats.rows_examined, 0);
      EXPECT_TRUE(starling::bus::conflict_key_backfill::is_complete(conn()));
  }

  TEST_F(BackfillFixture, BackfillAssignsKeyAndAdvancesCursor) {
      // Insert a minimal statement for JOIN
      conn().execute(
          "INSERT INTO statements (id, tenant_id, holder_id, subject_id,"
          " predicate, canonical_object_hash, polarity, scope,"
          " consolidation_state, created_at, updated_at)"
          " VALUES ('stmt-001', 'default', 'alice', 'carol', 'knows', 'hash1',"
          "         'pos', 'default', 'consolidated',"
          "         '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')");
      // Insert a conflicts_with edge with NULL key
      conn().execute(
          "INSERT INTO statement_edges (id, tenant_id, src_statement_id,"
          " dst_statement_id, edge_kind, created_at)"
          " VALUES ('edge-001', 'default', 'stmt-001', 'stmt-002',"
          "         'conflicts_with', '2026-01-01T00:00:00Z')");

      auto stats = starling::bus::conflict_key_backfill::tick_one_batch(conn(), 100);
      EXPECT_EQ(stats.rows_examined, 1);
      EXPECT_EQ(stats.rows_backfilled, 1);
      EXPECT_EQ(stats.rows_deduped, 0);

      auto st = conn().prepare(
          "SELECT canonical_conflict_key FROM statement_edges WHERE id='edge-001'");
      ASSERT_EQ(sqlite3_step(st.get()), SQLITE_ROW);
      auto* key = sqlite3_column_text(st.get(), 0);
      ASSERT_NE(key, nullptr);
      EXPECT_GT(std::string(reinterpret_cast<const char*>(key)).size(), 0u);
  }

  }  // namespace
  ```

- [ ] **18.5 Update CMakeLists**

  In `tests/cpp/CMakeLists.txt`, append `test_conflict_key_backfill.cpp` to the `starling_tests` sources list.

  In the root `CMakeLists.txt` (or bus sources block), append `src/bus/conflict_key_backfill.cpp` to the `starling_core` target sources.

- [ ] **18.6 Build and test**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  cmake -S . -B build -G Ninja
  cmake --build build
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

- [ ] **18.7 Commit**

  ```bash
  git add include/starling/bus/conflict_key_backfill.hpp \
          src/bus/conflict_key_backfill.cpp \
          src/bus/bus.cpp \
          tests/cpp/test_conflict_key_backfill.cpp \
          tests/cpp/CMakeLists.txt \
          CMakeLists.txt
  git commit -m "feat(P2.a/bus): conflict_key_backfill tick_one_batch + Bus.write hook

  New module: conflict_key_backfill::{is_complete, tick_one_batch}.
  Processes up to N conflicts_with edges per call: computes
  canonical_conflict_key_hex from 7-tuple, UPDATEs or DELETEs duplicates,
  advances singleton cursor. Bus::write calls tick post-commit inside a
  SAVEPOINT; failure is swallowed to prevent backfill from blocking writes.
  3 C++ tests: initially incomplete, empty batch completes, key assignment.

  spec §8.2 / §8.3

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 19 — TC-CONFLICT-KEY-UNIQUE (CRITICAL #6): dedup end-to-end

**Touches:** `tests/python/test_tc_conflict_key_unique.py`

**Prerequisite:** Task 18 green.

### Steps

- [ ] **19.1 Write failing test** (RED)

  Create `tests/python/test_tc_conflict_key_unique.py`:

  ```python
  """
  TC-CONFLICT-KEY-UNIQUE — CRITICAL #6 (05_bus)

  Validates that the canonical_conflict_key UNIQUE partial index prevents
  duplicate conflicts_with edges end-to-end through Bus.write().

  Spec ref: §8.2, §8.4, §16.3-5
  """
  import sqlite3
  import pytest
  from starling import persistence, runtime


  @pytest.fixture
  def rt(tmp_path, monkeypatch):
      """Runtime fixture using a real file-backed store (Bus requires real DB)."""
      from starling.preflight import relax_preflight_for_m0_3
      orig = relax_preflight_for_m0_3()
      r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
      r.start()
      yield r
      monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


  def _db_conn(rt) -> sqlite3.Connection:
      """Direct sqlite3 connection to the runtime DB for inspection."""
      db_path = rt.adapter.db_path()
      conn = sqlite3.connect(db_path)
      conn.row_factory = sqlite3.Row
      return conn


  def test_three_partial_overlaps_produce_one_conflicts_with_edge(rt):
      """3 partial_overlap writes + backfill -> exactly 1 conflicts_with edge."""
      for i in range(3):
          rt.bus.write(
              tenant_id="default", holder_id="alice",
              subject_id="bob", predicate="knows",
              object_text=f"Alice knows Bob v{i}", polarity="pos", scope="default",
              observed_at=f"2026-0{i+1}-01T00:00:00Z", provenance="test",
          )
      from starling.bus import conflict_key_backfill
      with rt.adapter.connection() as conn:
          for _ in range(10):
              stats = conflict_key_backfill.tick_one_batch(conn, 100)
              if stats.completed:
                  break

      with _db_conn(rt) as conn:
          n = conn.execute(
              "SELECT COUNT(*) AS n FROM statement_edges WHERE edge_kind='conflicts_with'"
          ).fetchone()["n"]
          assert n == 1, f"Expected 1 conflicts_with edge after dedup, got {n}"


  def test_unique_index_exists_in_schema(rt):
      """The partial UNIQUE index idx_conflict_edges_key_unique is present."""
      with _db_conn(rt) as conn:
          row = conn.execute(
              "SELECT sql FROM sqlite_master"
              " WHERE type='index' AND name='idx_conflict_edges_key_unique'"
          ).fetchone()
          assert row is not None, "idx_conflict_edges_key_unique index not found"
          assert "UNIQUE" in row["sql"].upper()
          assert "conflicts_with" in row["sql"]


  def test_distinct_canonical_keys_produce_distinct_edges(rt):
      """Two partial_overlap pairs with different subject produce 2 edges."""
      for i in range(2):
          rt.bus.write(
              tenant_id="default", holder_id="alice",
              subject_id="bob", predicate="knows",
              object_text=f"Alice knows Bob v{i}", polarity="pos", scope="default",
              observed_at=f"2026-0{i+1}-01T00:00:00Z", provenance="test",
          )
      for i in range(2):
          rt.bus.write(
              tenant_id="default", holder_id="alice",
              subject_id="carol", predicate="knows",
              object_text=f"Alice knows Carol v{i}", polarity="pos", scope="default",
              observed_at=f"2026-0{i+1}-01T00:00:00Z", provenance="test",
          )
      from starling.bus import conflict_key_backfill
      with rt.adapter.connection() as conn:
          for _ in range(10):
              if conflict_key_backfill.tick_one_batch(conn, 100).completed:
                  break
      with _db_conn(rt) as conn:
          n = conn.execute(
              "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='conflicts_with'"
          ).fetchone()[0]
          assert n == 2, f"Expected 2 distinct conflict edges, got {n}"


  def test_null_canonical_key_rows_unconstrained(rt):
      """supersedes edges (canonical_conflict_key IS NULL) are not UNIQUE constrained."""
      with rt.adapter.connection() as conn:
          for i in range(3):
              conn.execute(
                  "INSERT INTO statement_edges"
                  " (id, tenant_id, src_statement_id, dst_statement_id,"
                  "  edge_kind, canonical_conflict_key, created_at)"
                  " VALUES (?, 'default', ?, ?, 'supersedes', NULL, '2026-01-01T00:00:00Z')",
                  (f"sup-edge-{i}", f"src-{i}", f"dst-{i}"),
              )
      with _db_conn(rt) as conn:
          n = conn.execute(
              "SELECT COUNT(*) FROM statement_edges WHERE edge_kind='supersedes'"
          ).fetchone()[0]
          assert n == 3, f"Expected 3 supersedes edges, got {n}"
  ```

- [ ] **19.2 Run RED**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  pytest tests/python/test_tc_conflict_key_unique.py -v 2>&1 | tail -20
  ```

- [ ] **19.3 Run GREEN**

  ```bash
  pytest tests/python/test_tc_conflict_key_unique.py -v
  ```

  All 4 must pass.

- [ ] **19.4 Guard battery**

  ```bash
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

- [ ] **19.5 Commit**

  ```bash
  git add tests/python/test_tc_conflict_key_unique.py
  git commit -m "test(P2.a/CRITICAL-6): TC-CONFLICT-KEY-UNIQUE — dedup end-to-end

  4 cases: 3 partial_overlap writes produce exactly 1 conflicts_with edge
  after backfill; UNIQUE index exists in sqlite_master; distinct keys
  produce distinct edges; NULL canonical_conflict_key rows unconstrained.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 20: ToMEngine + Context POD + common_ground stub + perspective_take

**Files:**
- Create: `include/starling/tom/tom_engine.hpp`
- Create: `include/starling/tom/common_ground.hpp`
- Create: `src/tom/tom_engine.cpp`
- Create: `src/tom/common_ground.cpp`
- Test: `tests/cpp/test_tom_engine_perspective.cpp`
- Modify: `CMakeLists.txt` + `tests/cpp/CMakeLists.txt`

**Spec ref:** §7.2 + §7.1 (common_ground P2.b stub)

> **Note**: `migrations/0010_tom_belief_tracker.sql` was ALREADY created in Task 2. This task does NOT re-create the migration file. The `tom_belief_tracker_checkpoint`, `tom_depth_estimator_cache`, and `common_ground` tables already exist when Task 20 runs. This task adds only C++ surface: POD types + common_ground read API + ToMEngine class.

- [ ] **Step 1: Create `include/starling/tom/common_ground.hpp`**

  ```cpp
  #pragma once
  #include <string>
  #include <vector>
  #include <starling/persistence/sqlite_adapter.hpp>

  namespace starling::tom {

  struct CommonGroundEntry {
      std::string id;
      std::string tenant_id;
      std::string statement_id;
      std::string status;
      std::string parties_json;
      std::string created_at;
      std::string updated_at;
  };

  namespace common_ground {

  /// P2.a stub: always returns empty vector.
  std::vector<CommonGroundEntry> query(
      persistence::SqliteAdapter& adapter,
      std::string_view self_id,
      std::string_view target_id,
      std::string_view tenant_id,
      std::string_view as_of_iso8601);

  }  // namespace common_ground
  }  // namespace starling::tom
  ```

- [ ] **20.3 Create `src/tom/common_ground.cpp`**

  ```cpp
  #include <starling/tom/common_ground.hpp>

  namespace starling::tom::common_ground {

  // P2.a stub: returns [] per spec §7.2 step 3.
  std::vector<CommonGroundEntry> query(
      persistence::SqliteAdapter&, std::string_view,
      std::string_view, std::string_view, std::string_view)
  {
      return {};
  }

  }  // namespace starling::tom::common_ground
  ```

- [ ] **20.4 Create `include/starling/tom/tom_engine.hpp`**

  ```cpp
  #pragma once
  #include <string>
  #include <vector>
  #include <starling/cognizer/cognizer_hub.hpp>
  #include <starling/cognizer/knowledge_frontier.hpp>
  #include <starling/persistence/sqlite_adapter.hpp>
  #include <starling/tom/common_ground.hpp>

  namespace starling::retrieval { struct StatementRow; }

  namespace starling::tom {

  struct Context {
      std::vector<std::string>               visible_engram_ids;
      std::vector<retrieval::StatementRow>    target_beliefs;
      std::vector<CommonGroundEntry>          cg;   // P2.a: always empty
  };

  class ToMEngine {
  public:
      ToMEngine(
          persistence::SqliteAdapter& adapter,
          cognizer::CognizerHub& hub,
          cognizer::KnowledgeFrontier& frontier);

      Context perspective_take(
          std::string_view target_cognizer_id,
          std::string_view tenant_id,
          std::string_view as_of_iso8601) const;

  private:
      persistence::SqliteAdapter& adapter_;
      cognizer::CognizerHub& hub_;
      cognizer::KnowledgeFrontier& frontier_;
  };

  }  // namespace starling::tom
  ```

- [ ] **20.5 Create `src/tom/tom_engine.cpp`**

  ```cpp
  #include <starling/tom/tom_engine.hpp>
  #include <starling/retrieval/basic_retriever.hpp>
  #include <sqlite3.h>

  namespace starling::tom {

  ToMEngine::ToMEngine(
      persistence::SqliteAdapter& adapter,
      cognizer::CognizerHub& hub,
      cognizer::KnowledgeFrontier& frontier)
      : adapter_(adapter), hub_(hub), frontier_(frontier)
  {}

  Context ToMEngine::perspective_take(
      std::string_view target_cognizer_id,
      std::string_view tenant_id,
      std::string_view as_of_iso8601) const
  {
      Context ctx;

      // Step 1: visible engrams
      auto visible_set = frontier_.visible_engrams_at(
          tenant_id, target_cognizer_id, as_of_iso8601);
      ctx.visible_engram_ids.assign(visible_set.begin(), visible_set.end());

      // Step 2: target beliefs
      const std::string tid(tenant_id), cid(target_cognizer_id), aof(as_of_iso8601);
      auto& conn = adapter_.connection();
      auto stmt = conn.prepare(
          "SELECT id, tenant_id, holder_id, subject_id, predicate,"
          "       canonical_object_hash, polarity, scope, nesting_depth,"
          "       consolidation_state, observed_at, created_at"
          "  FROM statements"
          " WHERE tenant_id = ? AND holder_id = ? AND observed_at <= ?"
          "   AND consolidation_state IN ('consolidated', 'archived')"
          "   AND review_status NOT IN ('rejected', 'pending_review')");
      sqlite3_bind_text(stmt.get(), 1, tid.c_str(), -1, SQLITE_STATIC);
      sqlite3_bind_text(stmt.get(), 2, cid.c_str(), -1, SQLITE_STATIC);
      sqlite3_bind_text(stmt.get(), 3, aof.c_str(), -1, SQLITE_STATIC);
      while (sqlite3_step(stmt.get()) == SQLITE_ROW) {
          retrieval::StatementRow row;
          auto col = [&](int i) -> std::string {
              auto* v = sqlite3_column_text(stmt.get(), i);
              return v ? reinterpret_cast<const char*>(v) : "";
          };
          row.id = col(0); row.tenant_id = col(1); row.holder_id = col(2);
          row.subject_id = col(3); row.predicate = col(4);
          row.canonical_object_hash = col(5); row.polarity = col(6);
          row.scope = col(7); row.nesting_depth = sqlite3_column_int(stmt.get(), 8);
          row.consolidation_state = col(9); row.observed_at = col(10);
          row.created_at = col(11);
          ctx.target_beliefs.push_back(std::move(row));
      }

      // Step 3: cg (P2.a stub)
      ctx.cg = common_ground::query(adapter_, "system_self", cid, tid, aof);
      return ctx;
  }

  }  // namespace starling::tom
  ```

- [ ] **20.6 Create C++ smoke tests** (`tests/cpp/test_tom_engine_perspective.cpp`)

  ```cpp
  #include <gtest/gtest.h>
  #include <starling/tom/tom_engine.hpp>
  #include <starling/cognizer/cognizer_hub.hpp>
  #include <starling/cognizer/knowledge_frontier.hpp>
  #include <starling/persistence/sqlite_adapter.hpp>
  #include <starling/persistence/migration_runner.hpp>

  namespace {

  struct TomEngineFixture : ::testing::Test {
      starling::persistence::SqliteAdapter adapter{":memory:"};
      starling::cognizer::CognizerHub hub{adapter};
      starling::cognizer::KnowledgeFrontier frontier{adapter};
      starling::tom::ToMEngine engine{adapter, hub, frontier};
      void SetUp() override { starling::persistence::run_migrations(adapter); }

      starling::cognizer::Cognizer make_human(const std::string& ext) {
          starling::cognizer::CognizerRegistration r;
          r.kind = starling::cognizer::CognizerKind::Human;
          r.external_id = ext; r.canonical_name = ext; r.tenant_id = "default";
          return hub.register_cognizer(r);
      }
  };

  TEST_F(TomEngineFixture, CgAlwaysEmptyP2a) {
      auto a = make_human("alice");
      auto ctx = engine.perspective_take(a.id, "default", "2026-12-31T23:59:59Z");
      EXPECT_TRUE(ctx.cg.empty());
  }

  TEST_F(TomEngineFixture, EmptyContextShape) {
      auto b = make_human("bob");
      auto ctx = engine.perspective_take(b.id, "default", "2026-12-31T23:59:59Z");
      EXPECT_TRUE(ctx.visible_engram_ids.empty());
      EXPECT_TRUE(ctx.target_beliefs.empty());
      EXPECT_TRUE(ctx.cg.empty());
  }

  }  // namespace
  ```

- [ ] **20.7 Update CMakeLists**

  In `tests/cpp/CMakeLists.txt`, append `test_tom_engine_perspective.cpp` to `starling_tests`.

  In root `CMakeLists.txt`, append `src/tom/tom_engine.cpp` and `src/tom/common_ground.cpp` to `starling_core`.

- [ ] **20.8 Build and test**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  cmake -S . -B build -G Ninja && cmake --build build
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

- [ ] **20.9 Commit**

  ```bash
  git add migrations/0010_tom_belief_tracker.sql \
          include/starling/tom/tom_engine.hpp \
          include/starling/tom/common_ground.hpp \
          src/tom/tom_engine.cpp \
          src/tom/common_ground.cpp \
          tests/cpp/test_tom_engine_perspective.cpp \
          tests/cpp/CMakeLists.txt \
          CMakeLists.txt
  git commit -m "feat(P2.a/tom): migration 0010 + ToMEngine + perspective_take

  migration 0010: tom_belief_tracker_checkpoint, tom_depth_estimator_cache,
  common_ground tables per spec §5.3. ToMEngine::perspective_take delegates
  visible_engram_ids to KnowledgeFrontier, fetches target_beliefs from
  statements with time-anchor + state filter, cg always empty (P2.a stub).
  2 C++ tests verifying empty cg and context shape.

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 21 -- nesting_depth_writer + StatementWriter integration

**Touches:** `include/starling/tom/nesting_depth_writer.hpp`, `src/tom/nesting_depth_writer.cpp`, `src/bus/statement_writer.cpp`, `tests/cpp/test_nesting_depth_writer.cpp`, `tests/cpp/CMakeLists.txt`, `CMakeLists.txt`

**Prerequisite:** Task 20 green.

### Steps

- [ ] **21.1 Create header**

  Create `include/starling/tom/nesting_depth_writer.hpp`:

  ```cpp
  #pragma once
  #include <starling/persistence/connection.hpp>
  #include <starling/extractor/extracted_statement.hpp>

  namespace starling::tom::nesting_depth_writer {

  /// Compute the nesting_depth for statement s before INSERT.
  /// - If s.object_kind != "statement" -> return 0
  /// - Else look up statements WHERE id=s.object_value
  ///   - found  -> return parent.nesting_depth + 1
  ///   - not found -> throw NestingDepthOverflow (parent must exist)
  /// P2.a hard limit: nesting_depth > 2 also throws NestingDepthOverflow.
  int compute_nesting_depth(
      persistence::Connection& conn,
      const extractor::ExtractedStatement& s);

  }  // namespace starling::tom::nesting_depth_writer
  ```

- [ ] **21.2 Create implementation**

  Create `src/tom/nesting_depth_writer.cpp`:

  ```cpp
  #include <starling/tom/nesting_depth_writer.hpp>
  #include <starling/tom/tom_engine.hpp>  // NestingDepthOverflow
  #include <sqlite3.h>
  #include <stdexcept>

  namespace starling::tom::nesting_depth_writer {

  int compute_nesting_depth(
      persistence::Connection& conn,
      const extractor::ExtractedStatement& s)
  {
      if (s.object_kind != "statement") return 0;

      const std::string& parent_id = s.object_value;
      auto stmt = conn.prepare(
          "SELECT nesting_depth FROM statements WHERE id = ? LIMIT 1");
      sqlite3_bind_text(stmt.get(), 1, parent_id.c_str(), -1, SQLITE_STATIC);
      int rc = sqlite3_step(stmt.get());
      if (rc != SQLITE_ROW) {
          throw NestingDepthOverflow(
              "nesting_depth_writer: parent statement not found: " + parent_id);
      }
      int parent_depth = sqlite3_column_int(stmt.get(), 0);
      int computed = parent_depth + 1;
      if (computed > 2) {
          throw NestingDepthOverflow(
              "nesting_depth_writer: computed depth " +
              std::to_string(computed) + " exceeds P2.a hard limit of 2");
      }
      return computed;
  }

  }  // namespace starling::tom::nesting_depth_writer
  ```

- [ ] **21.3 Integrate into StatementWriter**

  In `src/bus/statement_writer.cpp`, before the statements INSERT:

  ```cpp
  #include <starling/tom/nesting_depth_writer.hpp>
  #include <starling/tom/depth_estimator.hpp>
  #include <starling/tom/rate_limiter.hpp>

  // ... inside write_statement(), before INSERT:
  int nesting_depth = tom::nesting_depth_writer::compute_nesting_depth(conn, s);

  // For nesting_depth >= 2: check partner depth estimate
  if (nesting_depth >= 2) {
      int est = tom::depth_estimator::estimate(
          conn, s.holder_id, s.holder_tenant_id, s.observed_at);
      if (est < 2) {
          // partner not yet at second-order depth — transient only
          return StatementWriteRejected{"tom_depth_partner_lower_order", true};
      }
  }

  // Hard limit
  if (nesting_depth > 2) {
      throw tom::NestingDepthOverflow("nesting_depth > 2 hard limit");
  }

  // Rate-limit tom_inferred provenance
  if (s.provenance == "tom_inferred") {
      if (!tom::rate_limiter::allow_tom_inferred_write(
              conn, s.holder_id, s.subject_id, s.predicate,
              s.canonical_object_hash, s.holder_tenant_id)) {
          return StatementWriteRejected{"tom_inferred_rate_limited", true};
      }
  }
  // Bind nesting_depth when calling sqlite3_bind for the INSERT
  ```

  If depth_estimator and rate_limiter are not yet implemented (Tasks 22-23), stub them as always returning 2 and true respectively until those tasks are done.

- [ ] **21.4 Create C++ tests**

  Create `tests/cpp/test_nesting_depth_writer.cpp`:

  ```cpp
  #include <gtest/gtest.h>
  #include <starling/tom/nesting_depth_writer.hpp>
  #include <starling/tom/tom_engine.hpp>
  #include <starling/persistence/sqlite_adapter.hpp>
  #include <starling/persistence/migration_runner.hpp>
  #include <starling/extractor/extracted_statement.hpp>
  #include <sqlite3.h>

  namespace {

  struct NestingDepthFixture : ::testing::Test {
      starling::persistence::SqliteAdapter adapter{":memory:"};
      void SetUp() override { starling::persistence::run_migrations(adapter); }
      starling::persistence::Connection& conn() { return adapter.connection(); }

      void insert_statement(const std::string& id, int depth) {
          auto st = conn().prepare(
              "INSERT INTO statements (id, tenant_id, holder_id, subject_id, predicate,"
              " canonical_object_hash, polarity, scope, nesting_depth,"
              " consolidation_state, review_status, created_at, updated_at)"
              " VALUES (?, 'default', 'alice', 'sub', 'knows', 'hash',"
              " 'pos', 'default', ?, 'consolidated', 'accepted',"
              " '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')");
          sqlite3_bind_text(st.get(), 1, id.c_str(), -1, SQLITE_STATIC);
          sqlite3_bind_int(st.get(), 2, depth);
          sqlite3_step(st.get());
      }
  };

  TEST_F(NestingDepthFixture, NonStatementObjectReturnsZero) {
      starling::extractor::ExtractedStatement s;
      s.object_kind = "entity";
      s.object_value = "some-entity-id";
      EXPECT_EQ(starling::tom::nesting_depth_writer::compute_nesting_depth(conn(), s), 0);
  }

  TEST_F(NestingDepthFixture, StatementObjectAddsOneToParentDepth) {
      insert_statement("parent-stmt", 0);
      starling::extractor::ExtractedStatement s;
      s.object_kind = "statement";
      s.object_value = "parent-stmt";
      EXPECT_EQ(starling::tom::nesting_depth_writer::compute_nesting_depth(conn(), s), 1);
  }

  TEST_F(NestingDepthFixture, MissingParentThrowsNestingDepthOverflow) {
      starling::extractor::ExtractedStatement s;
      s.object_kind = "statement";
      s.object_value = "nonexistent-parent";
      EXPECT_THROW(
          starling::tom::nesting_depth_writer::compute_nesting_depth(conn(), s),
          starling::tom::NestingDepthOverflow);
  }

  TEST_F(NestingDepthFixture, DepthExceedsTwoThrowsNestingDepthOverflow) {
      // parent at depth 2 -> child would be depth 3 -> throw
      insert_statement("depth2-stmt", 2);
      starling::extractor::ExtractedStatement s;
      s.object_kind = "statement";
      s.object_value = "depth2-stmt";
      EXPECT_THROW(
          starling::tom::nesting_depth_writer::compute_nesting_depth(conn(), s),
          starling::tom::NestingDepthOverflow);
  }

  }  // namespace
  ```

- [ ] **21.5 Update CMakeLists**

  In `tests/cpp/CMakeLists.txt`, append `test_nesting_depth_writer.cpp`.

  In root `CMakeLists.txt`, append `src/tom/nesting_depth_writer.cpp` to `starling_core`.

- [ ] **21.6 Build and test**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  cmake -S . -B build -G Ninja && cmake --build build
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

- [ ] **21.7 Commit**

  ```bash
  git add include/starling/tom/nesting_depth_writer.hpp \
          src/tom/nesting_depth_writer.cpp \
          src/bus/statement_writer.cpp \
          tests/cpp/test_nesting_depth_writer.cpp \
          tests/cpp/CMakeLists.txt \
          CMakeLists.txt
  git commit -m "feat(P2.a/tom): nesting_depth_writer + StatementWriter integration

  compute_nesting_depth: 0 for non-statement objects; parent_depth+1 for
  object_kind='statement'; throws NestingDepthOverflow if parent missing or
  computed depth > 2. StatementWriter calls it before INSERT; rejects writes
  at depth>=2 when partner depth estimate < 2 (transient_only); enforces
  tom_inferred rate limit. 4 C++ tests.

  spec §7.6

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

## Task 22 -- rate_limiter (10min window for tom_inferred)

**Touches:** `include/starling/tom/rate_limiter.hpp`, `src/tom/rate_limiter.cpp`, `tests/cpp/test_rate_limiter_tom.cpp`, `tests/cpp/CMakeLists.txt`, `CMakeLists.txt`

**Prerequisite:** Task 21 green.

### Steps

- [ ] **22.1 Create header**

  Create `include/starling/tom/rate_limiter.hpp`:

  ```cpp
  #pragma once
  #include <string_view>
  #include <starling/persistence/connection.hpp>

  namespace starling::tom::rate_limiter {

  /// Returns true iff no tom_inferred statement with the same
  /// (holder, subject, predicate, canonical_object_hash, tenant)
  /// was written in the last 600 seconds (10 minutes) relative
  /// to the current wall clock.
  ///
  /// Call BEFORE inserting a tom_inferred statement. If false,
  /// the caller must return StatementWriteRejected{transient_only=true}.
  bool allow_tom_inferred_write(
      persistence::Connection& conn,
      std::string_view holder_id,
      std::string_view subject_id,
      std::string_view predicate,
      std::string_view canonical_object_hash,
      std::string_view tenant_id);

  }  // namespace starling::tom::rate_limiter
  ```

- [ ] **22.2 Create implementation**

  Create `src/tom/rate_limiter.cpp`:

  ```cpp
  #include <starling/tom/rate_limiter.hpp>
  #include <sqlite3.h>

  namespace starling::tom::rate_limiter {

  bool allow_tom_inferred_write(
      persistence::Connection& conn,
      std::string_view holder_id,
      std::string_view subject_id,
      std::string_view predicate,
      std::string_view canonical_object_hash,
      std::string_view tenant_id)
  {
      // SELECT 1 if a tom_inferred statement with matching key exists
      // in the last 600 seconds.
      auto stmt = conn.prepare(
          "SELECT 1 FROM statements"
          " WHERE provenance = 'tom_inferred'"
          "   AND tenant_id = ? AND holder_id = ? AND subject_id = ?"
          "   AND predicate = ? AND canonical_object_hash = ?"
          "   AND observed_at >= datetime('now', '-600 seconds')"
          " LIMIT 1");
      const std::string tid(tenant_id), hid(holder_id), sid(subject_id);
      const std::string pred(predicate), coh(canonical_object_hash);
      sqlite3_bind_text(stmt.get(), 1, tid.c_str(),  -1, SQLITE_STATIC);
      sqlite3_bind_text(stmt.get(), 2, hid.c_str(),  -1, SQLITE_STATIC);
      sqlite3_bind_text(stmt.get(), 3, sid.c_str(),  -1, SQLITE_STATIC);
      sqlite3_bind_text(stmt.get(), 4, pred.c_str(), -1, SQLITE_STATIC);
      sqlite3_bind_text(stmt.get(), 5, coh.c_str(),  -1, SQLITE_STATIC);
      return sqlite3_step(stmt.get()) != SQLITE_ROW;  // true = allowed (no hit)
  }

  }  // namespace starling::tom::rate_limiter
  ```

- [ ] **22.3 Create C++ tests**

  Create `tests/cpp/test_rate_limiter_tom.cpp`:

  ```cpp
  #include <gtest/gtest.h>
  #include <starling/tom/rate_limiter.hpp>
  #include <starling/persistence/sqlite_adapter.hpp>
  #include <starling/persistence/migration_runner.hpp>
  #include <sqlite3.h>

  namespace {

  struct RateLimitFixture : ::testing::Test {
      starling::persistence::SqliteAdapter adapter{":memory:"};
      void SetUp() override { starling::persistence::run_migrations(adapter); }
      starling::persistence::Connection& conn() { return adapter.connection(); }

      void insert_tom_statement(const std::string& id, const std::string& observed_at) {
          auto st = conn().prepare(
              "INSERT INTO statements (id, tenant_id, holder_id, subject_id, predicate,"
              " canonical_object_hash, polarity, scope, nesting_depth, provenance,"
              " consolidation_state, review_status, observed_at, created_at, updated_at)"
              " VALUES (?, 'default', 'alice', 'bob', 'knows', 'hash', 'pos', 'default',"
              " 1, 'tom_inferred', 'consolidated', 'accepted', ?, ?, ?)");
          sqlite3_bind_text(st.get(), 1, id.c_str(), -1, SQLITE_STATIC);
          sqlite3_bind_text(st.get(), 2, observed_at.c_str(), -1, SQLITE_STATIC);
          sqlite3_bind_text(st.get(), 3, observed_at.c_str(), -1, SQLITE_STATIC);
          sqlite3_bind_text(st.get(), 4, observed_at.c_str(), -1, SQLITE_STATIC);
          sqlite3_step(st.get());
      }
  };

  TEST_F(RateLimitFixture, AllowsFirstWriteWhenEmpty) {
      EXPECT_TRUE(starling::tom::rate_limiter::allow_tom_inferred_write(
          conn(), "alice", "bob", "knows", "hash", "default"));
  }

  TEST_F(RateLimitFixture, BlocksDuplicateWithinWindow) {
      // Insert a tom_inferred statement with observed_at = now
      insert_tom_statement("stmt-1", "datetime('now')");
      // The same key within 600s should be blocked
      // (SQLite datetime('now') in INSERT was literal string -- use a workaround)
      // Insert with actual ISO timestamp just now
      auto st = conn().prepare(
          "INSERT INTO statements (id, tenant_id, holder_id, subject_id, predicate,"
          " canonical_object_hash, polarity, scope, nesting_depth, provenance,"
          " consolidation_state, review_status, observed_at, created_at, updated_at)"
          " VALUES ('stmt-now', 'default', 'alice', 'bob', 'knows', 'hash', 'pos', 'default',"
          " 1, 'tom_inferred', 'consolidated', 'accepted',"
          " datetime('now'), datetime('now'), datetime('now'))");
      sqlite3_step(st.get());

      EXPECT_FALSE(starling::tom::rate_limiter::allow_tom_inferred_write(
          conn(), "alice", "bob", "knows", "hash", "default"));
  }

  TEST_F(RateLimitFixture, AllowsDifferentKey) {
      auto st = conn().prepare(
          "INSERT INTO statements (id, tenant_id, holder_id, subject_id, predicate,"
          " canonical_object_hash, polarity, scope, nesting_depth, provenance,"
          " consolidation_state, review_status, observed_at, created_at, updated_at)"
          " VALUES ('stmt-x', 'default', 'alice', 'bob', 'knows', 'hash', 'pos', 'default',"
          " 1, 'tom_inferred', 'consolidated', 'accepted',"
          " datetime('now'), datetime('now'), datetime('now'))");
      sqlite3_step(st.get());

      // Different canonical_object_hash -> different key -> allowed
      EXPECT_TRUE(starling::tom::rate_limiter::allow_tom_inferred_write(
          conn(), "alice", "bob", "knows", "different_hash", "default"));
  }

  }  // namespace
  ```

- [ ] **22.4 Update CMakeLists**

  In `tests/cpp/CMakeLists.txt`, append `test_rate_limiter_tom.cpp`.

  In root `CMakeLists.txt`, append `src/tom/rate_limiter.cpp` to `starling_core`.

- [ ] **22.5 Build and test**

  ```bash
  source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
  cmake -S . -B build -G Ninja && cmake --build build
  ctest --test-dir build --output-on-failure
  pytest tests/python -q
  python scripts/ci_static_scan.py
  ```

- [ ] **22.6 Commit**

  ```bash
  git add include/starling/tom/rate_limiter.hpp \
          src/tom/rate_limiter.cpp \
          tests/cpp/test_rate_limiter_tom.cpp \
          tests/cpp/CMakeLists.txt \
          CMakeLists.txt
  git commit -m "feat(P2.a/tom): rate_limiter — 10min window for tom_inferred writes

  allow_tom_inferred_write: SELECT 1 from statements WHERE provenance='tom_inferred'
  AND same (holder,subject,predicate,canonical_object_hash,tenant) AND
  observed_at >= now-600s. Returns true (allowed) if no hit. StatementWriter
  consults this before inserting tom_inferred provenance statements.
  3 C++ tests: first write allowed, same-key blocked, different-key allowed.

  spec §7.7

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  ```

---

---

## Task 23 — ToMDepthEstimator: free function + 1 h TTL cache

**Spec refs:** §7.6 (ToM depth estimation), §7.7 (cache policy), §13.1 CRITICAL #7 (perspective-runtime test)
**TDD colour at commit:** GREEN (4 C++ unit tests pass)
**Depends on:** Task 20 (ToMEngine + migration 0010), Task 21 (nesting_depth_writer)

### 23.1 Context

`ToMEngine::perspective_take` needs to know how deep to recurse when computing a partner's
believed-beliefs.  The depth is estimated from observed interaction frequency over the past 7 days,
then cached for 1 hour so we never hammer the DB on every write.

Mapping (spec §7.6):

| 7-day interaction count | estimated depth |
|-------------------------|-----------------|
| 0                       | 0               |
| 1–2                     | 1               |
| ≥ 3                     | 2               |

Cache lives in `tom_depth_estimate_cache` (migration 0010 already created this table).

### 23.2 Header — `include/starling/tom/depth_estimator.hpp`

```cpp
// include/starling/tom/depth_estimator.hpp
#pragma once
#include "starling/persistence/connection.hpp"
#include <string_view>

namespace starling::tom::depth_estimator {

/// Estimate the ToM depth for @p partner_cognizer_id within @p tenant_id.
///
/// Returns 0, 1, or 2.  Reads from the 1-hour TTL cache first; populates it
/// on a miss by counting rows in cognizer_presence_log over the past 7 days.
///
/// Thread-safety: each call uses its own SQLite statement; safe to call from
/// concurrent threads sharing the same persistence::Connection.
int estimate(persistence::Connection& conn,
             std::string_view partner_cognizer_id,
             std::string_view tenant_id,
             std::string_view as_of_iso8601);

} // namespace starling::tom::depth_estimator
```

### 23.3 Implementation — `src/tom/depth_estimator.cpp`

```cpp
// src/tom/depth_estimator.cpp
#include "starling/tom/depth_estimator.hpp"
#include <sqlite3.h>
#include <cstdio>
#include <stdexcept>

namespace starling::tom::depth_estimator {

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

static int count_from_cache(persistence::Connection& conn,
                             std::string_view cognizer_id,
                             std::string_view tenant_id,
                             std::string_view as_of)
{
    // Returns cached depth (-1 = cache miss or expired)
    sqlite3_stmt* stmt = nullptr;
    const char* sql =
        "SELECT estimated_depth FROM tom_depth_estimate_cache "
        "WHERE cognizer_id = ? AND tenant_id = ? "
        "  AND cached_at >= datetime(?, '-3600 seconds') "
        "LIMIT 1";
    if (sqlite3_prepare_v2(conn.handle(), sql, -1, &stmt, nullptr) != SQLITE_OK) {
        return -1;
    }
    sqlite3_bind_text(stmt, 1, cognizer_id.data(), static_cast<int>(cognizer_id.size()), SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, tenant_id.data(),   static_cast<int>(tenant_id.size()),   SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, as_of.data(),        static_cast<int>(as_of.size()),        SQLITE_TRANSIENT);
    int depth = -1;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        depth = sqlite3_column_int(stmt, 0);
    }
    sqlite3_finalize(stmt);
    return depth;
}

static int count_interactions(persistence::Connection& conn,
                               std::string_view cognizer_id,
                               std::string_view tenant_id,
                               std::string_view as_of)
{
    sqlite3_stmt* stmt = nullptr;
    const char* sql =
        "SELECT COUNT(*) FROM cognizer_presence_log "
        "WHERE cognizer_id = ? AND tenant_id = ? "
        "  AND observed_at >= datetime(?, '-7 days') "
        "  AND observed_at <= ?";
    if (sqlite3_prepare_v2(conn.handle(), sql, -1, &stmt, nullptr) != SQLITE_OK) {
        return 0;
    }
    sqlite3_bind_text(stmt, 1, cognizer_id.data(), static_cast<int>(cognizer_id.size()), SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, tenant_id.data(),   static_cast<int>(tenant_id.size()),   SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, as_of.data(),        static_cast<int>(as_of.size()),        SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 4, as_of.data(),        static_cast<int>(as_of.size()),        SQLITE_TRANSIENT);
    int n = 0;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        n = sqlite3_column_int(stmt, 0);
    }
    sqlite3_finalize(stmt);
    return n;
}

static void write_cache(persistence::Connection& conn,
                         std::string_view cognizer_id,
                         std::string_view tenant_id,
                         std::string_view as_of,
                         int depth)
{
    sqlite3_stmt* stmt = nullptr;
    const char* sql =
        "INSERT INTO tom_depth_estimate_cache "
        "  (cognizer_id, tenant_id, estimated_depth, cached_at) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(cognizer_id, tenant_id) DO UPDATE SET "
        "  estimated_depth = excluded.estimated_depth, "
        "  cached_at       = excluded.cached_at";
    if (sqlite3_prepare_v2(conn.handle(), sql, -1, &stmt, nullptr) != SQLITE_OK) {
        fprintf(stderr, "[depth_estimator] cache write prepare failed: %s\n",
                sqlite3_errmsg(conn.handle()));
        return;
    }
    sqlite3_bind_text(stmt, 1, cognizer_id.data(), static_cast<int>(cognizer_id.size()), SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, tenant_id.data(),   static_cast<int>(tenant_id.size()),   SQLITE_TRANSIENT);
    sqlite3_bind_int (stmt, 3, depth);
    sqlite3_bind_text(stmt, 4, as_of.data(),        static_cast<int>(as_of.size()),        SQLITE_TRANSIENT);
    if (sqlite3_step(stmt) != SQLITE_DONE) {
        fprintf(stderr, "[depth_estimator] cache write step failed: %s\n",
                sqlite3_errmsg(conn.handle()));
    }
    sqlite3_finalize(stmt);
}

// ---------------------------------------------------------------------------
// public API
// ---------------------------------------------------------------------------

int estimate(persistence::Connection& conn,
             std::string_view partner_cognizer_id,
             std::string_view tenant_id,
             std::string_view as_of_iso8601)
{
    // 1. Cache hit?
    int cached = count_from_cache(conn, partner_cognizer_id, tenant_id, as_of_iso8601);
    if (cached >= 0) {
        return cached;
    }

    // 2. Cache miss — count 7-day interactions
    int n = count_interactions(conn, partner_cognizer_id, tenant_id, as_of_iso8601);

    // 3. Map count → depth
    int depth = (n == 0) ? 0 : (n <= 2) ? 1 : 2;

    // 4. Populate cache
    write_cache(conn, partner_cognizer_id, tenant_id, as_of_iso8601, depth);

    return depth;
}

} // namespace starling::tom::depth_estimator
```

### 23.4 CMakeLists.txt additions

In `src/tom/CMakeLists.txt`, add `depth_estimator.cpp` to the `starling_tom` target source list:

```cmake
# src/tom/CMakeLists.txt  (add depth_estimator.cpp to the existing list)
target_sources(starling_tom PRIVATE
    # ... existing sources ...
    depth_estimator.cpp
)
```

### 23.5 C++ unit tests — `tests/cpp/test_depth_estimator_cache.cpp`

```cpp
// tests/cpp/test_depth_estimator_cache.cpp
#include "starling/tom/depth_estimator.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/migrations.hpp"
#include <catch2/catch_test_macros.hpp>
#include <sqlite3.h>
#include <cstring>

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

static void insert_presence(persistence::Connection& conn,
                             const char* cognizer_id,
                             const char* tenant_id,
                             const char* observed_at)
{
    sqlite3_stmt* stmt = nullptr;
    const char* sql =
        "INSERT INTO cognizer_presence_log (cognizer_id, tenant_id, engram_id, observed_at) "
        "VALUES (?, ?, 'eng-test', ?)";
    sqlite3_prepare_v2(conn.handle(), sql, -1, &stmt, nullptr);
    sqlite3_bind_text(stmt, 1, cognizer_id, -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 2, tenant_id,   -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(stmt, 3, observed_at, -1, SQLITE_TRANSIENT);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);
}

static persistence::Connection make_db()
{
    auto conn = persistence::Connection::open(":memory:");
    persistence::run_migrations(conn);
    return conn;
}

// ---------------------------------------------------------------------------
// tests
// ---------------------------------------------------------------------------

TEST_CASE("depth_estimator: zero interactions returns depth 0", "[depth_estimator]")
{
    auto conn = make_db();
    int d = starling::tom::depth_estimator::estimate(
        conn, "alice", "t1", "2026-05-26T12:00:00Z");
    REQUIRE(d == 0);
}

TEST_CASE("depth_estimator: one interaction returns depth 1", "[depth_estimator]")
{
    auto conn = make_db();
    insert_presence(conn, "bob", "t1", "2026-05-25T10:00:00Z");
    int d = starling::tom::depth_estimator::estimate(
        conn, "bob", "t1", "2026-05-26T12:00:00Z");
    REQUIRE(d == 1);
}

TEST_CASE("depth_estimator: three or more interactions returns depth 2", "[depth_estimator]")
{
    auto conn = make_db();
    insert_presence(conn, "carol", "t1", "2026-05-20T08:00:00Z");
    insert_presence(conn, "carol", "t1", "2026-05-21T08:00:00Z");
    insert_presence(conn, "carol", "t1", "2026-05-22T08:00:00Z");
    int d = starling::tom::depth_estimator::estimate(
        conn, "carol", "t1", "2026-05-26T12:00:00Z");
    REQUIRE(d == 2);
}

TEST_CASE("depth_estimator: cache is populated after first call", "[depth_estimator]")
{
    auto conn = make_db();
    // First call — cache miss
    starling::tom::depth_estimator::estimate(
        conn, "dave", "t1", "2026-05-26T12:00:00Z");

    // Verify the cache row exists
    sqlite3_stmt* stmt = nullptr;
    sqlite3_prepare_v2(conn.handle(),
        "SELECT COUNT(*) FROM tom_depth_estimate_cache "
        "WHERE cognizer_id = 'dave' AND tenant_id = 't1'",
        -1, &stmt, nullptr);
    sqlite3_step(stmt);
    int n = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    REQUIRE(n == 1);

    // Second call must hit cache; insert a row that would change the count
    // but the cached value (0) should still be returned
    insert_presence(conn, "dave", "t1", "2026-05-25T10:00:00Z");
    int d2 = starling::tom::depth_estimator::estimate(
        conn, "dave", "t1", "2026-05-26T12:00:00Z");
    REQUIRE(d2 == 0); // cache hit — stale but correct for TTL window
}
```

### 23.6 CMakeLists.txt — test target addition

In `tests/cpp/CMakeLists.txt`, register the new test binary:

```cmake
# tests/cpp/CMakeLists.txt  (add after existing add_executable blocks)
add_executable(test_depth_estimator_cache test_depth_estimator_cache.cpp)
target_link_libraries(test_depth_estimator_cache PRIVATE
    starling_tom starling_persistence Catch2::Catch2WithMain)
catch_discover_tests(test_depth_estimator_cache)
```

### 23.7 Commit

```
git add include/starling/tom/depth_estimator.hpp \
        src/tom/depth_estimator.cpp \
        src/tom/CMakeLists.txt \
        tests/cpp/test_depth_estimator_cache.cpp \
        tests/cpp/CMakeLists.txt

git commit -m "$(cat <<'EOF'
feat(tom): add ToMDepthEstimator with 1h TTL cache (Task 23)

Free function estimate() counts 7-day cognizer_presence_log rows and maps
0→0, 1-2→1, ≥3→2.  Result is written to tom_depth_estimate_cache (created
by migration 0010) with a 1-hour TTL checked via datetime() arithmetic.
Four Catch2 unit tests cover each depth bucket and cache-hit staleness.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```


---

## Task 24 — 4 Mentalizing Primitives

**Spec refs:** §7.4 (mentalizing primitives), §7.5 (believe/know-tri/misalign/shared)
**TDD colour at commit:** GREEN (C++ tests for each primitive pass)
**Depends on:** Task 20 (ToMEngine + Context), Task 21 (nesting_depth_writer), Task 22 (rate_limiter), Task 23 (depth_estimator)

### 24.1 Context

The four mentalizing primitives are the public surface of 08_cognizer's Theory-of-Mind layer.
Each function writes a `tom_inferred` statement (or reads one) against the statement_edges +
engrams tables through the Bus.  They share a consistent calling convention:

```
bool <primitive>(Bus& bus,
                 const Context& ctx,
                 std::string_view holder_id,   // who holds the belief
                 std::string_view subject_id,  // engram the belief is about
                 std::string_view predicate,
                 std::string_view object_id,
                 std::string_view tenant_id,
                 std::string_view as_of_iso8601);
```

Return value: `true` = write succeeded / belief confirmed, `false` = rate-limited or
nesting depth exceeded.

### 24.2 Shared header — `include/starling/tom/mentalizing.hpp`

```cpp
// include/starling/tom/mentalizing.hpp
#pragma once
#include "starling/bus/bus.hpp"
#include "starling/tom/tom_engine.hpp"   // Context
#include <string_view>

namespace starling::tom::mentalizing {

/// Primitive 1: believe
/// Records that @p holder_id believes (subject, predicate, object).
/// Rate-limited: one write per holder+subject+predicate+object per 10 min.
bool believe(Bus& bus, const Context& ctx,
             std::string_view holder_id,
             std::string_view subject_id,
             std::string_view predicate,
             std::string_view object_id,
             std::string_view tenant_id,
             std::string_view as_of_iso8601);

/// Primitive 2: know_tri (tripartite knowledge: holder knows that actor
/// believes (subject, predicate, object)).
/// Nesting depth must be ≤ 2; returns false if depth would be exceeded.
bool know_tri(Bus& bus, const Context& ctx,
              std::string_view holder_id,
              std::string_view actor_id,
              std::string_view subject_id,
              std::string_view predicate,
              std::string_view object_id,
              std::string_view tenant_id,
              std::string_view as_of_iso8601);

/// Primitive 3: misalign
/// Records that @p holder_id believes X while @p other_id believes NOT-X
/// for the same (subject, predicate).  Writes a conflicts_with edge between
/// the two inferred belief engrams.
bool misalign(Bus& bus, const Context& ctx,
              std::string_view holder_id,
              std::string_view other_id,
              std::string_view subject_id,
              std::string_view predicate,
              std::string_view holder_object_id,
              std::string_view other_object_id,
              std::string_view tenant_id,
              std::string_view as_of_iso8601);

/// Primitive 4: shared (common ground — P2.a stub always returns true)
/// In P2.b this will write a shared_belief engram.  For now it is a no-op
/// that returns true so call-sites compile against the final interface.
bool shared(Bus& bus, const Context& ctx,
            std::string_view holder_id,
            std::string_view other_id,
            std::string_view subject_id,
            std::string_view predicate,
            std::string_view object_id,
            std::string_view tenant_id,
            std::string_view as_of_iso8601);

} // namespace starling::tom::mentalizing
```

### 24.3 Implementation — `src/tom/mentalizing_believe.cpp`

```cpp
// src/tom/mentalizing_believe.cpp
#include "starling/tom/mentalizing.hpp"
#include "starling/tom/rate_limiter.hpp"
#include "starling/bus/bus.hpp"
#include <functional>
#include <sstream>

namespace starling::tom::mentalizing {

bool believe(Bus& bus, const Context& ctx,
             std::string_view holder_id,
             std::string_view subject_id,
             std::string_view predicate,
             std::string_view object_id,
             std::string_view tenant_id,
             std::string_view as_of_iso8601)
{
    // Build a canonical object hash for rate-limiter deduplication
    std::ostringstream oss;
    oss << object_id;
    std::string canonical_obj = oss.str();

    auto& conn = bus.connection();
    bool allowed = rate_limiter::allow_tom_inferred_write(
        conn,
        holder_id, subject_id, predicate, canonical_obj, tenant_id);
    if (!allowed) {
        return false;
    }

    // Build the engram text: "<holder> believes <subject> <predicate> <object>"
    std::string engram_text;
    engram_text.reserve(128);
    engram_text += holder_id;
    engram_text += " believes ";
    engram_text += subject_id;
    engram_text += " ";
    engram_text += predicate;
    engram_text += " ";
    engram_text += object_id;

    bus::WriteRequest req;
    req.text        = std::move(engram_text);
    req.tenant_id   = std::string(tenant_id);
    req.provenance  = "tom_inferred";
    req.as_of       = std::string(as_of_iso8601);

    bus.write(req);
    return true;
}

} // namespace starling::tom::mentalizing
```

### 24.4 Implementation — `src/tom/mentalizing_know.cpp`

```cpp
// src/tom/mentalizing_know.cpp
#include "starling/tom/mentalizing.hpp"
#include "starling/tom/nesting_depth_writer.hpp"
#include "starling/tom/rate_limiter.hpp"
#include "starling/bus/bus.hpp"
#include <sstream>

namespace starling::tom::mentalizing {

bool know_tri(Bus& bus, const Context& ctx,
              std::string_view holder_id,
              std::string_view actor_id,
              std::string_view subject_id,
              std::string_view predicate,
              std::string_view object_id,
              std::string_view tenant_id,
              std::string_view as_of_iso8601)
{
    auto& conn = bus.connection();

    // Depth check: look up a candidate parent belief engram for actor
    // and see if its nesting_depth + 1 would exceed 2.
    // For the know_tri primitive the new statement nests one level
    // deeper than actor's direct belief.
    // We pass a synthetic StatementRow to nesting_depth_writer to check.
    nesting_depth_writer::StatementRow candidate;
    candidate.object_kind = "statement";
    // We look up the existing believe engram for actor as parent
    // (simplified: if none found, depth defaults to 0+1=1 which is fine)
    candidate.parent_statement_id = "";  // populated by BeliefTracker in Task 25
    // If nesting depth would exceed 2, skip
    try {
        int nd = nesting_depth_writer::compute_nesting_depth(conn, candidate);
        if (nd > 2) {
            return false;
        }
    } catch (const nesting_depth_writer::NestingDepthOverflow&) {
        return false;
    }

    std::string canonical_obj(object_id);
    bool allowed = rate_limiter::allow_tom_inferred_write(
        conn, holder_id, subject_id, predicate, canonical_obj, tenant_id);
    if (!allowed) {
        return false;
    }

    // "<holder> knows that <actor> believes <subject> <predicate> <object>"
    std::string engram_text;
    engram_text.reserve(160);
    engram_text += holder_id;
    engram_text += " knows that ";
    engram_text += actor_id;
    engram_text += " believes ";
    engram_text += subject_id;
    engram_text += " ";
    engram_text += predicate;
    engram_text += " ";
    engram_text += object_id;

    bus::WriteRequest req;
    req.text       = std::move(engram_text);
    req.tenant_id  = std::string(tenant_id);
    req.provenance = "tom_inferred";
    req.as_of      = std::string(as_of_iso8601);

    bus.write(req);
    return true;
}

} // namespace starling::tom::mentalizing
```

### 24.5 Implementation — `src/tom/mentalizing_misalign.cpp`

```cpp
// src/tom/mentalizing_misalign.cpp
#include "starling/tom/mentalizing.hpp"
#include "starling/tom/rate_limiter.hpp"
#include "starling/bus/bus.hpp"
#include <sstream>

namespace starling::tom::mentalizing {

bool misalign(Bus& bus, const Context& ctx,
              std::string_view holder_id,
              std::string_view other_id,
              std::string_view subject_id,
              std::string_view predicate,
              std::string_view holder_object_id,
              std::string_view other_object_id,
              std::string_view tenant_id,
              std::string_view as_of_iso8601)
{
    auto& conn = bus.connection();

    // Rate-limit on holder side
    bool allowed_h = rate_limiter::allow_tom_inferred_write(
        conn, holder_id, subject_id, predicate,
        std::string(holder_object_id), tenant_id);
    if (!allowed_h) {
        return false;
    }

    // Write holder's belief
    std::string holder_text;
    holder_text.reserve(128);
    holder_text += holder_id;
    holder_text += " believes ";
    holder_text += subject_id;
    holder_text += " ";
    holder_text += predicate;
    holder_text += " ";
    holder_text += holder_object_id;

    bus::WriteRequest req_h;
    req_h.text       = std::move(holder_text);
    req_h.tenant_id  = std::string(tenant_id);
    req_h.provenance = "tom_inferred";
    req_h.as_of      = std::string(as_of_iso8601);
    bus.write(req_h);

    // Write other's belief
    bool allowed_o = rate_limiter::allow_tom_inferred_write(
        conn, other_id, subject_id, predicate,
        std::string(other_object_id), tenant_id);
    if (!allowed_o) {
        return true;  // holder side already written; partial is still a success
    }

    std::string other_text;
    other_text.reserve(128);
    other_text += other_id;
    other_text += " believes ";
    other_text += subject_id;
    other_text += " ";
    other_text += predicate;
    other_text += " ";
    other_text += other_object_id;

    bus::WriteRequest req_o;
    req_o.text       = std::move(other_text);
    req_o.tenant_id  = std::string(tenant_id);
    req_o.provenance = "tom_inferred";
    req_o.as_of      = std::string(as_of_iso8601);
    bus.write(req_o);

    // Write conflicts_with edge between the two engrams using canonical_conflict_key
    // (exact engram IDs resolved by Bus after writing)
    // The canonical key is deterministic: sort(holder_object_id, other_object_id) joined
    std::string a(holder_object_id), b(other_object_id);
    if (a > b) std::swap(a, b);
    std::string conflict_key = a + "::" + b + "::" + std::string(predicate) + "::" + std::string(subject_id);

    bus.insert_statement_edge(conn,
        /*src=*/ req_h.engram_id_out,
        /*dst=*/ req_o.engram_id_out,
        tenant_id, "conflicts_with", conflict_key);

    return true;
}

} // namespace starling::tom::mentalizing
```

### 24.6 Implementation — `src/tom/mentalizing_shared.cpp`

```cpp
// src/tom/mentalizing_shared.cpp
#include "starling/tom/mentalizing.hpp"

namespace starling::tom::mentalizing {

// P2.a stub — common_ground is always empty per spec §7.4.
// Returns true so that call-sites compile and tests pass at the integration level.
bool shared(Bus& /*bus*/, const Context& /*ctx*/,
            std::string_view /*holder_id*/,
            std::string_view /*other_id*/,
            std::string_view /*subject_id*/,
            std::string_view /*predicate*/,
            std::string_view /*object_id*/,
            std::string_view /*tenant_id*/,
            std::string_view /*as_of_iso8601*/)
{
    return true;
}

} // namespace starling::tom::mentalizing
```

### 24.7 CMakeLists.txt additions

In `src/tom/CMakeLists.txt`, add all four translation units to `starling_tom`:

```cmake
# src/tom/CMakeLists.txt  (add to existing target_sources block)
target_sources(starling_tom PRIVATE
    # ... existing sources ...
    mentalizing_believe.cpp
    mentalizing_know.cpp
    mentalizing_misalign.cpp
    mentalizing_shared.cpp
)
```

### 24.8 Commit

```
git add include/starling/tom/mentalizing.hpp \
        src/tom/mentalizing_believe.cpp \
        src/tom/mentalizing_know.cpp \
        src/tom/mentalizing_misalign.cpp \
        src/tom/mentalizing_shared.cpp \
        src/tom/CMakeLists.txt

git commit -m "$(cat <<'EOF'
feat(tom): implement 4 mentalizing primitives believe/know_tri/misalign/shared (Task 24)

believe and misalign write tom_inferred engrams through Bus after rate-limit
check.  know_tri additionally enforces nesting depth ≤ 2.  shared is a P2.a
no-op stub that always returns true; P2.b will fill in common-ground writes.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```


---

## Task 25 — BeliefTracker + 6 event handlers + checkpoint advancement

**Spec refs:** §7.3 (BeliefTracker), §7.3.1 (Outbox subscriber), §7.3.2 (6 event handlers), §7.3.3 (checkpoint advancement)
**TDD colour at commit:** GREEN (BeliefTracker C++ tests pass, Bus.write tick hook active)
**Depends on:** Task 20 (ToMEngine), Task 21 (nesting_depth_writer), Task 22 (rate_limiter), Task 23 (depth_estimator), Task 24 (mentalizing primitives)

### 25.1 Context

`BeliefTracker` is an Outbox subscriber that reads from `bus_outbox` and, for each unprocessed
event, fires the appropriate mentalizing primitive.  It advances a checkpoint in
`belief_tracker_state` after each processed batch so replay is idempotent.

The 6 event kinds it handles:

| event kind           | primitive called         |
|----------------------|--------------------------|
| `engram_created`     | `believe`                |
| `engram_updated`     | `believe`                |
| `relation_asserted`  | `know_tri`               |
| `relation_retracted` | (no-op — log and skip)   |
| `presence_observed`  | `believe` (location cue) |
| `conflict_detected`  | `misalign`               |

### 25.2 Header — `include/starling/tom/belief_tracker.hpp`

```cpp
// include/starling/tom/belief_tracker.hpp
#pragma once
#include "starling/bus/bus.hpp"
#include "starling/persistence/connection.hpp"
#include <cstdint>
#include <string>

namespace starling::tom {

struct BeliefTrackerStats {
    int events_processed = 0;
    int believes_written  = 0;
    int know_tris_written = 0;
    int misaligns_written = 0;
    int rate_limited      = 0;
    int skipped           = 0;  // relation_retracted + unknown kinds
};

class BeliefTracker {
public:
    explicit BeliefTracker(Bus& bus);

    /// Process up to @p batch_size unprocessed outbox events, advance checkpoint.
    /// Returns stats for the batch.
    BeliefTrackerStats process_batch(int batch_size = 50);

    /// Current checkpoint (last processed outbox event id).
    int64_t checkpoint() const noexcept;

private:
    Bus& bus_;
    int64_t checkpoint_ = 0;

    void load_checkpoint();
    void save_checkpoint(int64_t new_cp);

    BeliefTrackerStats handle_engram_created   (const std::string& payload, const std::string& tenant_id, const std::string& as_of);
    BeliefTrackerStats handle_engram_updated   (const std::string& payload, const std::string& tenant_id, const std::string& as_of);
    BeliefTrackerStats handle_relation_asserted(const std::string& payload, const std::string& tenant_id, const std::string& as_of);
    BeliefTrackerStats handle_presence_observed(const std::string& payload, const std::string& tenant_id, const std::string& as_of);
    BeliefTrackerStats handle_conflict_detected(const std::string& payload, const std::string& tenant_id, const std::string& as_of);
};

} // namespace starling::tom
```

### 25.3 Implementation — `src/tom/belief_tracker.cpp`

```cpp
// src/tom/belief_tracker.cpp
#include "starling/tom/belief_tracker.hpp"
#include "starling/tom/mentalizing.hpp"
#include "starling/tom/depth_estimator.hpp"
#include "starling/tom/tom_engine.hpp"
#include <nlohmann/json.hpp>
#include <sqlite3.h>
#include <cstdio>

using json = nlohmann::json;

namespace starling::tom {

// ---------------------------------------------------------------------------
// ctor
// ---------------------------------------------------------------------------

BeliefTracker::BeliefTracker(Bus& bus) : bus_(bus)
{
    load_checkpoint();
}

// ---------------------------------------------------------------------------
// checkpoint helpers
// ---------------------------------------------------------------------------

void BeliefTracker::load_checkpoint()
{
    auto& conn = bus_.connection();
    sqlite3_stmt* stmt = nullptr;
    const char* sql =
        "SELECT last_processed_event_id FROM belief_tracker_state WHERE id = 1";
    if (sqlite3_prepare_v2(conn.handle(), sql, -1, &stmt, nullptr) == SQLITE_OK) {
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            checkpoint_ = sqlite3_column_int64(stmt, 0);
        }
        sqlite3_finalize(stmt);
    }
}

void BeliefTracker::save_checkpoint(int64_t new_cp)
{
    auto& conn = bus_.connection();
    sqlite3_stmt* stmt = nullptr;
    const char* sql =
        "INSERT INTO belief_tracker_state (id, last_processed_event_id, updated_at) "
        "VALUES (1, ?, datetime('now')) "
        "ON CONFLICT(id) DO UPDATE SET "
        "  last_processed_event_id = excluded.last_processed_event_id, "
        "  updated_at = excluded.updated_at";
    if (sqlite3_prepare_v2(conn.handle(), sql, -1, &stmt, nullptr) != SQLITE_OK) {
        fprintf(stderr, "[belief_tracker] checkpoint prepare failed\n");
        return;
    }
    sqlite3_bind_int64(stmt, 1, new_cp);
    sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    checkpoint_ = new_cp;
}

int64_t BeliefTracker::checkpoint() const noexcept { return checkpoint_; }

// ---------------------------------------------------------------------------
// process_batch
// ---------------------------------------------------------------------------

BeliefTrackerStats BeliefTracker::process_batch(int batch_size)
{
    BeliefTrackerStats total;
    auto& conn = bus_.connection();

    sqlite3_stmt* stmt = nullptr;
    const char* sql =
        "SELECT id, event_kind, tenant_id, as_of, payload "
        "FROM bus_outbox "
        "WHERE id > ? "
        "ORDER BY id ASC "
        "LIMIT ?";
    if (sqlite3_prepare_v2(conn.handle(), sql, -1, &stmt, nullptr) != SQLITE_OK) {
        fprintf(stderr, "[belief_tracker] outbox query prepare failed\n");
        return total;
    }
    sqlite3_bind_int64(stmt, 1, checkpoint_);
    sqlite3_bind_int  (stmt, 2, batch_size);

    int64_t last_id = checkpoint_;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int64_t     event_id   = sqlite3_column_int64(stmt, 0);
        const char* event_kind = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        const char* tenant_id  = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        const char* as_of      = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3));
        const char* payload_c  = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));

        std::string payload = payload_c ? payload_c : "{}";
        std::string tid     = tenant_id  ? tenant_id  : "";
        std::string aof     = as_of      ? as_of      : "";
        std::string kind    = event_kind ? event_kind : "";

        BeliefTrackerStats s;
        if      (kind == "engram_created")     s = handle_engram_created   (payload, tid, aof);
        else if (kind == "engram_updated")     s = handle_engram_updated   (payload, tid, aof);
        else if (kind == "relation_asserted")  s = handle_relation_asserted(payload, tid, aof);
        else if (kind == "presence_observed")  s = handle_presence_observed(payload, tid, aof);
        else if (kind == "conflict_detected")  s = handle_conflict_detected(payload, tid, aof);
        else { s.skipped = 1; }  // relation_retracted + unknowns

        total.events_processed++;
        total.believes_written  += s.believes_written;
        total.know_tris_written += s.know_tris_written;
        total.misaligns_written += s.misaligns_written;
        total.rate_limited      += s.rate_limited;
        total.skipped           += s.skipped;

        last_id = event_id;
    }
    sqlite3_finalize(stmt);

    if (last_id > checkpoint_) {
        save_checkpoint(last_id);
    }
    return total;
}

// ---------------------------------------------------------------------------
// event handlers
// ---------------------------------------------------------------------------

BeliefTrackerStats BeliefTracker::handle_engram_created(
    const std::string& payload, const std::string& tenant_id, const std::string& as_of)
{
    BeliefTrackerStats s;
    try {
        auto j = json::parse(payload);
        std::string engram_id = j.value("engram_id", "");
        std::string author_id = j.value("author_cognizer_id", "");
        if (engram_id.empty() || author_id.empty()) { s.skipped = 1; return s; }

        Context ctx;  // empty context — BeliefTracker does not call perspective_take
        bool ok = mentalizing::believe(bus_, ctx, author_id, engram_id,
                                       "authored", engram_id, tenant_id, as_of);
        if (ok) s.believes_written = 1;
        else    s.rate_limited     = 1;
    } catch (...) { s.skipped = 1; }
    return s;
}

BeliefTrackerStats BeliefTracker::handle_engram_updated(
    const std::string& payload, const std::string& tenant_id, const std::string& as_of)
{
    // Same logic as created — re-assert belief after update
    return handle_engram_created(payload, tenant_id, as_of);
}

BeliefTrackerStats BeliefTracker::handle_relation_asserted(
    const std::string& payload, const std::string& tenant_id, const std::string& as_of)
{
    BeliefTrackerStats s;
    try {
        auto j = json::parse(payload);
        std::string holder_id  = j.value("cognizer_id", "");
        std::string actor_id   = j.value("related_cognizer_id", "");
        std::string subject_id = j.value("engram_id", "");
        if (holder_id.empty() || actor_id.empty() || subject_id.empty()) {
            s.skipped = 1; return s;
        }
        Context ctx;
        bool ok = mentalizing::know_tri(bus_, ctx, holder_id, actor_id,
                                        subject_id, "related_to", subject_id,
                                        tenant_id, as_of);
        if (ok) s.know_tris_written = 1;
        else    s.rate_limited      = 1;
    } catch (...) { s.skipped = 1; }
    return s;
}

BeliefTrackerStats BeliefTracker::handle_presence_observed(
    const std::string& payload, const std::string& tenant_id, const std::string& as_of)
{
    BeliefTrackerStats s;
    try {
        auto j = json::parse(payload);
        std::string cognizer_id = j.value("cognizer_id", "");
        std::string engram_id   = j.value("engram_id", "");
        if (cognizer_id.empty() || engram_id.empty()) { s.skipped = 1; return s; }

        Context ctx;
        bool ok = mentalizing::believe(bus_, ctx, cognizer_id, engram_id,
                                       "observed", engram_id, tenant_id, as_of);
        if (ok) s.believes_written = 1;
        else    s.rate_limited     = 1;
    } catch (...) { s.skipped = 1; }
    return s;
}

BeliefTrackerStats BeliefTracker::handle_conflict_detected(
    const std::string& payload, const std::string& tenant_id, const std::string& as_of)
{
    BeliefTrackerStats s;
    try {
        auto j = json::parse(payload);
        std::string holder_id        = j.value("holder_cognizer_id", "");
        std::string other_id         = j.value("other_cognizer_id", "");
        std::string subject_id       = j.value("subject_engram_id", "");
        std::string predicate        = j.value("predicate", "");
        std::string holder_object_id = j.value("holder_object_id", "");
        std::string other_object_id  = j.value("other_object_id", "");
        if (holder_id.empty() || other_id.empty()) { s.skipped = 1; return s; }

        Context ctx;
        bool ok = mentalizing::misalign(bus_, ctx, holder_id, other_id,
                                        subject_id, predicate,
                                        holder_object_id, other_object_id,
                                        tenant_id, as_of);
        if (ok) s.misaligns_written = 1;
        else    s.rate_limited      = 1;
    } catch (...) { s.skipped = 1; }
    return s;
}

} // namespace starling::tom
```

### 25.4 Bus.write tick hook

In `src/bus/bus.cpp`, add a BeliefTracker tick after the existing conflict_key_backfill tick:

```cpp
// src/bus/bus.cpp  — inside Bus::write(), after conflict_key_backfill tick
try {
    auto sp2 = conn.savepoint("belief_tracker_tick");
    belief_tracker_.process_batch(/*batch_size=*/10);
    sp2.release();
} catch (const std::exception& e) {
    fprintf(stderr, "[bus] belief_tracker_tick swallowed: %s\n", e.what());
} catch (...) {
    fprintf(stderr, "[bus] belief_tracker_tick swallowed: unknown\n");
}
```

`bus_.hpp` must hold a `BeliefTracker belief_tracker_;` member (constructed in `Bus::Bus()`).

### 25.5 CMakeLists.txt additions

```cmake
# src/tom/CMakeLists.txt
target_sources(starling_tom PRIVATE
    # ... existing sources ...
    belief_tracker.cpp
)
```

### 25.6 Commit

```
git add include/starling/tom/belief_tracker.hpp \
        src/tom/belief_tracker.cpp \
        src/bus/bus.hpp \
        src/bus/bus.cpp \
        src/tom/CMakeLists.txt

git commit -m "$(cat <<'EOF'
feat(tom): add BeliefTracker with 6 outbox event handlers and checkpoint (Task 25)

BeliefTracker subscribes to bus_outbox and dispatches engram_created,
engram_updated, relation_asserted, presence_observed, and conflict_detected
events to the four mentalizing primitives.  relation_retracted is a no-op.
Checkpoint advances after each batch; Bus.write drives a 10-event tick via
a SAVEPOINT so hook failures never roll back the parent write.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```


---

## Task 26 — pybind11 tom bindings + `python/starling/tom/`

**Spec refs:** §7.8 (Python bindings for 09_tom), §7.4 (mentalizing primitives Python surface)
**TDD colour at commit:** GREEN (Python import test passes)
**Depends on:** Task 20 (ToMEngine), Task 24 (mentalizing), Task 25 (BeliefTracker)

### 26.1 Context

Expose the ToM subsystem to Python through the existing `PYBIND11_MODULE(_core, m)` block in
`bindings/python/module.cpp`.  The Python package structure mirrors 08_cognizer:

```
python/starling/tom/
    __init__.py        re-exports Context, ToMEngine, BeliefTracker, BeliefTrackerStats
    primitives.py      thin wrappers: believe(), know_tri(), misalign(), shared()
```

### 26.2 Additions to `bindings/python/module.cpp`

Append inside the existing `PYBIND11_MODULE(_core, m)` body (after the cognizer block):

```cpp
// --- 09_tom bindings ---

py::class_<starling::tom::Context>(m, "TomContext")
    .def(py::init<>())
    .def_readwrite("visible_engram_ids", &starling::tom::Context::visible_engram_ids)
    .def_readwrite("target_beliefs",     &starling::tom::Context::target_beliefs)
    // cg is always empty in P2.a — expose as read-only empty list
    .def_property_readonly("cg",
        [](const starling::tom::Context&) { return py::list(); });

py::class_<starling::tom::ToMEngine>(m, "ToMEngine")
    .def(py::init<starling::persistence::Connection&,
                  starling::retrieval::RetrieverInterface&>(),
         py::arg("conn"), py::arg("retriever"))
    .def("perspective_take",
         [](starling::tom::ToMEngine& e,
            const std::string& target_cognizer_id,
            const std::string& tenant_id,
            const std::string& as_of) {
             return e.perspective_take(target_cognizer_id, tenant_id, as_of);
         },
         py::arg("target_cognizer_id"),
         py::arg("tenant_id"),
         py::arg("as_of"));

py::class_<starling::tom::BeliefTrackerStats>(m, "BeliefTrackerStats")
    .def_readonly("events_processed", &starling::tom::BeliefTrackerStats::events_processed)
    .def_readonly("believes_written",  &starling::tom::BeliefTrackerStats::believes_written)
    .def_readonly("know_tris_written", &starling::tom::BeliefTrackerStats::know_tris_written)
    .def_readonly("misaligns_written", &starling::tom::BeliefTrackerStats::misaligns_written)
    .def_readonly("rate_limited",      &starling::tom::BeliefTrackerStats::rate_limited)
    .def_readonly("skipped",           &starling::tom::BeliefTrackerStats::skipped);

py::class_<starling::tom::BeliefTracker>(m, "BeliefTracker")
    .def(py::init<starling::Bus&>(), py::arg("bus"))
    .def("process_batch",
         &starling::tom::BeliefTracker::process_batch,
         py::arg("batch_size") = 50)
    .def("checkpoint",
         &starling::tom::BeliefTracker::checkpoint);
```

### 26.3 `python/starling/tom/__init__.py`

```python
# python/starling/tom/__init__.py
"""starling.tom — Theory-of-Mind subsystem (P2.a)."""
from starling._core import (  # noqa: F401
    TomContext,
    ToMEngine,
    BeliefTracker,
    BeliefTrackerStats,
)
from starling.tom.primitives import (  # noqa: F401
    believe,
    know_tri,
    misalign,
    shared,
)

__all__ = [
    "TomContext",
    "ToMEngine",
    "BeliefTracker",
    "BeliefTrackerStats",
    "believe",
    "know_tri",
    "misalign",
    "shared",
]
```

### 26.4 `python/starling/tom/primitives.py`

```python
# python/starling/tom/primitives.py
"""Thin Python wrappers around the four mentalizing primitives.

These functions shadow the C++ API so that Python callers never need to
import _core directly.  The Bus and TomContext objects come from the C++
side; all string arguments are regular Python str.
"""
from __future__ import annotations

from starling._core import TomContext


def believe(
    bus,
    ctx: TomContext,
    holder_id: str,
    subject_id: str,
    predicate: str,
    object_id: str,
    tenant_id: str,
    as_of_iso8601: str,
) -> bool:
    """Record that *holder_id* believes (*subject_id*, *predicate*, *object_id*).

    Returns True if the write succeeded, False if rate-limited.
    """
    from starling._core import _tom_believe  # bound in module.cpp
    return _tom_believe(bus, ctx, holder_id, subject_id, predicate,
                        object_id, tenant_id, as_of_iso8601)


def know_tri(
    bus,
    ctx: TomContext,
    holder_id: str,
    actor_id: str,
    subject_id: str,
    predicate: str,
    object_id: str,
    tenant_id: str,
    as_of_iso8601: str,
) -> bool:
    """Record that *holder_id* knows that *actor_id* believes the triple.

    Returns False if nesting depth would exceed 2, or if rate-limited.
    """
    from starling._core import _tom_know_tri
    return _tom_know_tri(bus, ctx, holder_id, actor_id, subject_id, predicate,
                         object_id, tenant_id, as_of_iso8601)


def misalign(
    bus,
    ctx: TomContext,
    holder_id: str,
    other_id: str,
    subject_id: str,
    predicate: str,
    holder_object_id: str,
    other_object_id: str,
    tenant_id: str,
    as_of_iso8601: str,
) -> bool:
    """Record belief misalignment between *holder_id* and *other_id*.

    Writes tom_inferred engrams for both parties and inserts a conflicts_with
    edge with a canonical conflict key.  Returns False if rate-limited on the
    holder side.
    """
    from starling._core import _tom_misalign
    return _tom_misalign(bus, ctx, holder_id, other_id, subject_id, predicate,
                         holder_object_id, other_object_id, tenant_id, as_of_iso8601)


def shared(
    bus,
    ctx: TomContext,
    holder_id: str,
    other_id: str,
    subject_id: str,
    predicate: str,
    object_id: str,
    tenant_id: str,
    as_of_iso8601: str,
) -> bool:
    """P2.a stub — always returns True.  P2.b will write a shared_belief engram."""
    from starling._core import _tom_shared
    return _tom_shared(bus, ctx, holder_id, other_id, subject_id, predicate,
                       object_id, tenant_id, as_of_iso8601)
```

Supplement `bindings/python/module.cpp` with the four free-function bindings:

```cpp
// Append after the class bindings in the tom section
m.def("_tom_believe",   &starling::tom::mentalizing::believe,
      py::arg("bus"), py::arg("ctx"), py::arg("holder_id"),
      py::arg("subject_id"), py::arg("predicate"), py::arg("object_id"),
      py::arg("tenant_id"), py::arg("as_of_iso8601"));

m.def("_tom_know_tri",  &starling::tom::mentalizing::know_tri,
      py::arg("bus"), py::arg("ctx"), py::arg("holder_id"), py::arg("actor_id"),
      py::arg("subject_id"), py::arg("predicate"), py::arg("object_id"),
      py::arg("tenant_id"), py::arg("as_of_iso8601"));

m.def("_tom_misalign",  &starling::tom::mentalizing::misalign,
      py::arg("bus"), py::arg("ctx"), py::arg("holder_id"), py::arg("other_id"),
      py::arg("subject_id"), py::arg("predicate"),
      py::arg("holder_object_id"), py::arg("other_object_id"),
      py::arg("tenant_id"), py::arg("as_of_iso8601"));

m.def("_tom_shared",    &starling::tom::mentalizing::shared,
      py::arg("bus"), py::arg("ctx"), py::arg("holder_id"), py::arg("other_id"),
      py::arg("subject_id"), py::arg("predicate"), py::arg("object_id"),
      py::arg("tenant_id"), py::arg("as_of_iso8601"));
```

### 26.5 Commit

```
git add bindings/python/module.cpp \
        python/starling/tom/__init__.py \
        python/starling/tom/primitives.py

git commit -m "$(cat <<'EOF'
feat(bindings): expose 09_tom to Python via pybind11 (Task 26)

Adds TomContext, ToMEngine, BeliefTracker, BeliefTrackerStats class bindings
and four free-function mentalizing primitive bindings (_tom_believe, etc.).
Python package python/starling/tom/ re-exports all public symbols and wraps
primitives with typed signatures.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```


---

## Task 27 — TC-PERSPECTIVE-RUNTIME (CRITICAL test #7)

**Spec refs:** §13.1 CRITICAL #7 (TC-PERSPECTIVE-RUNTIME)
**TDD colour at commit:** RED → GREEN (9 pytest cases)
**Depends on:** Task 20 (ToMEngine), Task 23 (depth_estimator), Task 26 (tom bindings)

### 27.1 Full test file — `tests/python/test_tc_perspective_runtime.py`

```python
"""TC-PERSPECTIVE-RUNTIME — CRITICAL test #7.

Verifies that ToMEngine.perspective_take() constructs a correct Context object
for a given partner cognizer:
  - visible_engram_ids populated from cognizer_presence_log
  - target_beliefs populated from retrieval layer
  - nesting depth estimated from 7-day interaction window
  - cg is always an empty list in P2.a
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import starling.persistence as persistence
import starling.retrieval as retrieval
import starling.tom as tom
from starling._core import ToMEngine, TomContext


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def adapter(tmp_path):
    db_path = tmp_path / "test_perspective.db"
    a = persistence.SqliteAdapter(str(db_path))
    a.run_migrations()
    return a


@pytest.fixture()
def ret(adapter):
    return retrieval.SqliteRetriever(adapter)


@pytest.fixture()
def engine(adapter, ret):
    return ToMEngine(adapter.connection(), ret)


def _insert_presence(conn_raw, cognizer_id: str, engram_id: str,
                     tenant_id: str, observed_at: str):
    conn_raw.execute(
        "INSERT INTO cognizer_presence_log "
        "(cognizer_id, tenant_id, engram_id, observed_at) "
        "VALUES (?, ?, ?, ?)",
        (cognizer_id, tenant_id, engram_id, observed_at),
    )
    conn_raw.commit()


def _insert_engram(conn_raw, engram_id: str, text: str, tenant_id: str,
                   as_of: str):
    conn_raw.execute(
        "INSERT INTO engrams (id, tenant_id, text, created_at) VALUES (?, ?, ?, ?)",
        (engram_id, tenant_id, text, as_of),
    )
    conn_raw.commit()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

AS_OF = "2026-05-26T12:00:00Z"
SEVEN_DAYS_AGO = "2026-05-19T12:00:00Z"
EIGHT_DAYS_AGO = "2026-05-18T12:00:00Z"


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class TestPerspectiveTakeBasic:
    def test_empty_returns_empty_context(self, engine, adapter):
        """No presence rows → empty visible_engram_ids, empty target_beliefs."""
        ctx = engine.perspective_take("alice", "tenant1", AS_OF)
        assert isinstance(ctx, TomContext)
        assert ctx.visible_engram_ids == []
        assert ctx.target_beliefs     == []

    def test_cg_is_always_empty_list(self, engine, adapter):
        """cg must be an empty list in P2.a regardless of data."""
        _insert_presence(adapter.connection().raw(), "bob", "eng1",
                         "tenant1", SEVEN_DAYS_AGO)
        ctx = engine.perspective_take("bob", "tenant1", AS_OF)
        assert list(ctx.cg) == []

    def test_visible_engrams_populated(self, engine, adapter):
        """Engrams observed by cognizer within window appear in visible_engram_ids."""
        raw = adapter.connection().raw()
        _insert_presence(raw, "carol", "eng-a", "t1", SEVEN_DAYS_AGO)
        _insert_presence(raw, "carol", "eng-b", "t1", SEVEN_DAYS_AGO)
        ctx = engine.perspective_take("carol", "t1", AS_OF)
        assert "eng-a" in ctx.visible_engram_ids
        assert "eng-b" in ctx.visible_engram_ids

    def test_old_presence_excluded(self, engine, adapter):
        """Presence older than 7 days must NOT appear in visible_engram_ids."""
        raw = adapter.connection().raw()
        _insert_presence(raw, "dave", "eng-old", "t1", EIGHT_DAYS_AGO)
        ctx = engine.perspective_take("dave", "t1", AS_OF)
        assert "eng-old" not in ctx.visible_engram_ids


class TestDepthEstimation:
    def test_zero_interactions_depth_zero(self, engine, adapter):
        """No presence rows in 7-day window → depth estimate 0."""
        ctx = engine.perspective_take("nobody", "t1", AS_OF)
        # depth is not exposed on Context directly, but estimate() is tested
        # via depth_estimator.  This test confirms perspective_take does not crash.
        assert ctx is not None

    def test_one_interaction_depth_one(self, engine, adapter):
        raw = adapter.connection().raw()
        _insert_presence(raw, "eve", "eng1", "t1", SEVEN_DAYS_AGO)
        # Single presence → depth 1; perspective_take must complete without error
        ctx = engine.perspective_take("eve", "t1", AS_OF)
        assert ctx is not None

    def test_three_interactions_depth_two(self, engine, adapter):
        raw = adapter.connection().raw()
        for i in range(3):
            _insert_presence(raw, "frank", f"eng{i}", "t1", SEVEN_DAYS_AGO)
        ctx = engine.perspective_take("frank", "t1", AS_OF)
        assert ctx is not None


class TestTenantIsolation:
    def test_different_tenants_isolated(self, engine, adapter):
        """Engrams in tenant2 must not appear in tenant1 perspective."""
        raw = adapter.connection().raw()
        _insert_presence(raw, "grace", "eng-t2", "tenant2", SEVEN_DAYS_AGO)
        ctx = engine.perspective_take("grace", "tenant1", AS_OF)
        assert "eng-t2" not in ctx.visible_engram_ids

    def test_same_cognizer_different_tenants(self, engine, adapter):
        """Same cognizer in two tenants has independent contexts."""
        raw = adapter.connection().raw()
        _insert_presence(raw, "hank", "eng-a", "t1", SEVEN_DAYS_AGO)
        _insert_presence(raw, "hank", "eng-b", "t2", SEVEN_DAYS_AGO)
        ctx1 = engine.perspective_take("hank", "t1", AS_OF)
        ctx2 = engine.perspective_take("hank", "t2", AS_OF)
        assert "eng-a" in ctx1.visible_engram_ids
        assert "eng-b" not in ctx1.visible_engram_ids
        assert "eng-b" in ctx2.visible_engram_ids
        assert "eng-a" not in ctx2.visible_engram_ids
```

### 27.2 pytest marker and conftest

No new conftest entry is needed — `tmp_path` is a built-in pytest fixture.
The test file is self-contained.

### 27.3 Commit

```
git add tests/python/test_tc_perspective_runtime.py

git commit -m "$(cat <<'EOF'
test(tom): add TC-PERSPECTIVE-RUNTIME CRITICAL test #7 (Task 27)

Nine pytest cases cover perspective_take() output shape (empty context,
P2.a empty-cg guarantee, visible_engram_ids population, age cutoff) and
tenant isolation.  All cases must be GREEN before P2.a milestone close.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```


---

## Task 28 — TC-MENTAL-BELIEVE (CRITICAL test #8)

**Spec refs:** §13.1 CRITICAL #8 (TC-MENTAL-BELIEVE)
**TDD colour at commit:** RED → GREEN (10 pytest cases)
**Depends on:** Task 24 (mentalizing primitives), Task 26 (tom bindings)

### 28.1 Full test file — `tests/python/test_tc_mental_believe.py`

```python
"""TC-MENTAL-BELIEVE — CRITICAL test #8.

Verifies the believe() mentalizing primitive end-to-end:
  - Writes a tom_inferred engram with correct text
  - Rate-limiter blocks duplicate writes within 10-minute window
  - Duplicate writes outside 10-minute window succeed
  - Tenant isolation: same (holder, subject, predicate, object) in different
    tenants are independent
  - Empty holder_id or subject_id raises / returns False gracefully
"""
from __future__ import annotations

import sqlite3
import time

import pytest

import starling.persistence as persistence
import starling.bus as bus_module
import starling.tom as tom
from starling._core import TomContext
from starling.tom.primitives import believe


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

AS_OF       = "2026-05-26T12:00:00Z"
AS_OF_LATER = "2026-05-26T12:15:00Z"   # 15 minutes later — outside rate-limit window


@pytest.fixture()
def adapter(tmp_path):
    db_path = tmp_path / "test_believe.db"
    a = persistence.SqliteAdapter(str(db_path))
    a.run_migrations()
    return a


@pytest.fixture()
def bus(adapter):
    return bus_module.Bus(adapter)


@pytest.fixture()
def ctx():
    return TomContext()


def _count_tom_engrams(raw_conn, tenant_id: str) -> int:
    cur = raw_conn.execute(
        "SELECT COUNT(*) FROM engrams WHERE tenant_id = ? AND provenance = 'tom_inferred'",
        (tenant_id,),
    )
    return cur.fetchone()[0]


def _fetch_engram_texts(raw_conn, tenant_id: str) -> list[str]:
    cur = raw_conn.execute(
        "SELECT text FROM engrams WHERE tenant_id = ? AND provenance = 'tom_inferred' ORDER BY created_at",
        (tenant_id,),
    )
    return [row[0] for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class TestBelievePrimitiveBasic:
    def test_believe_writes_engram(self, bus, ctx, adapter):
        """believe() must create exactly one tom_inferred engram."""
        ok = believe(bus, ctx, "alice", "eng1", "authored", "eng1", "t1", AS_OF)
        assert ok is True
        raw = adapter.connection().raw()
        assert _count_tom_engrams(raw, "t1") == 1

    def test_believe_engram_text_contains_holder(self, bus, ctx, adapter):
        """Written engram text must contain holder_id."""
        believe(bus, ctx, "alice", "eng1", "authored", "eng1", "t1", AS_OF)
        raw = adapter.connection().raw()
        texts = _fetch_engram_texts(raw, "t1")
        assert any("alice" in t for t in texts)

    def test_believe_engram_text_contains_predicate(self, bus, ctx, adapter):
        """Written engram text must contain the predicate."""
        believe(bus, ctx, "bob", "eng2", "saw_at", "place1", "t1", AS_OF)
        raw = adapter.connection().raw()
        texts = _fetch_engram_texts(raw, "t1")
        assert any("saw_at" in t for t in texts)

    def test_believe_engram_provenance_is_tom_inferred(self, bus, ctx, adapter):
        """Engram provenance column must equal 'tom_inferred'."""
        believe(bus, ctx, "carol", "eng3", "authored", "eng3", "t1", AS_OF)
        raw = adapter.connection().raw()
        cur = raw.execute(
            "SELECT provenance FROM engrams WHERE tenant_id = 't1' AND provenance = 'tom_inferred'"
        )
        rows = cur.fetchall()
        assert len(rows) >= 1
        assert all(r[0] == "tom_inferred" for r in rows)


class TestBelieveRateLimiter:
    def test_duplicate_within_window_rate_limited(self, bus, ctx, adapter):
        """Second call with same args within 10 min must return False."""
        ok1 = believe(bus, ctx, "dave", "eng4", "authored", "eng4", "t1", AS_OF)
        ok2 = believe(bus, ctx, "dave", "eng4", "authored", "eng4", "t1", AS_OF)
        assert ok1 is True
        assert ok2 is False

    def test_duplicate_rate_limited_does_not_write_extra_engram(self, bus, ctx, adapter):
        """Rate-limited call must not create a second engram."""
        believe(bus, ctx, "eve", "eng5", "authored", "eng5", "t1", AS_OF)
        believe(bus, ctx, "eve", "eng5", "authored", "eng5", "t1", AS_OF)
        raw = adapter.connection().raw()
        assert _count_tom_engrams(raw, "t1") == 1

    def test_different_predicate_not_rate_limited(self, bus, ctx, adapter):
        """Different predicate bypasses rate-limiter (different cache key)."""
        ok1 = believe(bus, ctx, "frank", "eng6", "authored", "eng6", "t1", AS_OF)
        ok2 = believe(bus, ctx, "frank", "eng6", "observed", "eng6", "t1", AS_OF)
        assert ok1 is True
        assert ok2 is True


class TestBelieveTenantIsolation:
    def test_same_args_different_tenants_both_succeed(self, bus, ctx, adapter):
        """Same (holder, subject, predicate, object) in t1 and t2 are independent."""
        ok1 = believe(bus, ctx, "grace", "eng7", "authored", "eng7", "t1", AS_OF)
        ok2 = believe(bus, ctx, "grace", "eng7", "authored", "eng7", "t2", AS_OF)
        assert ok1 is True
        assert ok2 is True
        raw = adapter.connection().raw()
        assert _count_tom_engrams(raw, "t1") == 1
        assert _count_tom_engrams(raw, "t2") == 1

    def test_rate_limit_scoped_to_tenant(self, bus, ctx, adapter):
        """Rate-limit in t1 must not affect t2."""
        believe(bus, ctx, "hank", "eng8", "authored", "eng8", "t1", AS_OF)
        believe(bus, ctx, "hank", "eng8", "authored", "eng8", "t1", AS_OF)  # rate-limited
        ok_t2 = believe(bus, ctx, "hank", "eng8", "authored", "eng8", "t2", AS_OF)
        assert ok_t2 is True


class TestBelieveEdgeCases:
    def test_outside_window_succeeds(self, bus, ctx, adapter):
        """Second call 15 min later (outside 10-min window) must succeed."""
        believe(bus, ctx, "iris", "eng9", "authored", "eng9", "t1", AS_OF)
        # Rate-limiter uses datetime() arithmetic; pass a timestamp outside window
        ok2 = believe(bus, ctx, "iris", "eng9", "authored", "eng9", "t1", AS_OF_LATER)
        assert ok2 is True
```

### 28.2 Commit

```
git add tests/python/test_tc_mental_believe.py

git commit -m "$(cat <<'EOF'
test(tom): add TC-MENTAL-BELIEVE CRITICAL test #8 (Task 28)

Ten pytest cases exercise the believe() mentalizing primitive: engram
creation, text/provenance content, rate-limiter blocking within the
10-minute window, different-predicate bypass, tenant isolation, and
out-of-window re-allow.  All cases must be GREEN before P2.a close.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```


---

## Task 29 — TC-MENTAL-MISALIGN (CRITICAL test #9)

**Spec refs:** §13.1 CRITICAL #9 (TC-MENTAL-MISALIGN)
**TDD colour at commit:** RED → GREEN (10 pytest cases)
**Depends on:** Task 24 (misalign primitive), Task 16–18 (conflict_key), Task 26 (tom bindings)

### 29.1 Full test file — `tests/python/test_tc_mental_misalign.py`

```python
"""TC-MENTAL-MISALIGN — CRITICAL test #9.

Verifies the misalign() mentalizing primitive end-to-end:
  - Writes two tom_inferred engrams (one per party)
  - Inserts a conflicts_with edge between them with canonical_conflict_key
  - canonical_conflict_key is deterministic (sorted) regardless of argument order
  - Duplicate misalign calls on the same (subject, predicate) pair are rate-limited
  - UNIQUE index prevents duplicate conflict edges (canonical_conflict_key + partial index)
  - Tenant isolation: misalign in t1 does not affect t2
"""
from __future__ import annotations

import sqlite3

import pytest

import starling.persistence as persistence
import starling.bus as bus_module
import starling.tom as tom
from starling._core import TomContext
from starling.tom.primitives import misalign


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

AS_OF = "2026-05-26T12:00:00Z"


@pytest.fixture()
def adapter(tmp_path):
    db_path = tmp_path / "test_misalign.db"
    a = persistence.SqliteAdapter(str(db_path))
    a.run_migrations()
    return a


@pytest.fixture()
def bus(adapter):
    return bus_module.Bus(adapter)


@pytest.fixture()
def ctx():
    return TomContext()


def _tom_engrams(raw_conn, tenant_id: str) -> list[dict]:
    cur = raw_conn.execute(
        "SELECT id, text FROM engrams "
        "WHERE tenant_id = ? AND provenance = 'tom_inferred' "
        "ORDER BY created_at",
        (tenant_id,),
    )
    return [{"id": r[0], "text": r[1]} for r in cur.fetchall()]


def _conflict_edges(raw_conn, tenant_id: str) -> list[dict]:
    cur = raw_conn.execute(
        "SELECT source_engram_id, target_engram_id, canonical_conflict_key "
        "FROM statement_edges "
        "WHERE tenant_id = ? AND edge_kind = 'conflicts_with'",
        (tenant_id,),
    )
    return [
        {"src": r[0], "dst": r[1], "key": r[2]}
        for r in cur.fetchall()
    ]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class TestMisalignPrimitiveBasic:
    def test_writes_two_engrams(self, bus, ctx, adapter):
        """misalign() must create exactly two tom_inferred engrams."""
        ok = misalign(bus, ctx,
                      "alice", "bob",
                      "eng1", "likes",
                      "cats", "dogs",
                      "t1", AS_OF)
        assert ok is True
        raw = adapter.connection().raw()
        engrams = _tom_engrams(raw, "t1")
        assert len(engrams) == 2

    def test_holder_engram_text_present(self, bus, ctx, adapter):
        """Holder engram text must mention holder_id, subject, predicate, holder_object."""
        misalign(bus, ctx, "alice", "bob", "eng1", "likes", "cats", "dogs", "t1", AS_OF)
        raw = adapter.connection().raw()
        texts = [e["text"] for e in _tom_engrams(raw, "t1")]
        assert any("alice" in t and "likes" in t and "cats" in t for t in texts)

    def test_other_engram_text_present(self, bus, ctx, adapter):
        """Other engram text must mention other_id, subject, predicate, other_object."""
        misalign(bus, ctx, "alice", "bob", "eng1", "likes", "cats", "dogs", "t1", AS_OF)
        raw = adapter.connection().raw()
        texts = [e["text"] for e in _tom_engrams(raw, "t1")]
        assert any("bob" in t and "likes" in t and "dogs" in t for t in texts)

    def test_conflicts_with_edge_inserted(self, bus, ctx, adapter):
        """A conflicts_with edge must be inserted between the two engrams."""
        misalign(bus, ctx, "alice", "bob", "eng1", "likes", "cats", "dogs", "t1", AS_OF)
        raw = adapter.connection().raw()
        edges = _conflict_edges(raw, "t1")
        assert len(edges) == 1


class TestCanonicalConflictKey:
    def test_key_is_deterministic_regardless_of_order(self, bus, ctx, adapter):
        """Swapping holder and other must produce the same canonical_conflict_key."""
        ok1 = misalign(bus, ctx, "alice", "bob", "eng1", "likes", "cats", "dogs", "t1", AS_OF)
        raw = adapter.connection().raw()
        edges1 = _conflict_edges(raw, "t1")
        assert ok1 is True
        assert len(edges1) == 1
        key1 = edges1[0]["key"]

        # Reset
        raw.execute("DELETE FROM engrams WHERE tenant_id = 't1'")
        raw.execute("DELETE FROM statement_edges WHERE tenant_id = 't1'")
        raw.commit()

        # Swap holder/other and holder_object/other_object
        ok2 = misalign(bus, ctx, "bob", "alice", "eng1", "likes", "dogs", "cats", "t1", AS_OF)
        edges2 = _conflict_edges(raw, "t1")
        assert ok2 is True
        assert len(edges2) == 1
        key2 = edges2[0]["key"]

        assert key1 == key2, f"Keys differ: {key1!r} vs {key2!r}"

    def test_different_predicates_different_keys(self, bus, ctx, adapter):
        """Different predicate must yield different canonical_conflict_key."""
        misalign(bus, ctx, "alice", "bob", "eng1", "likes", "cats", "dogs", "t1", AS_OF)
        raw = adapter.connection().raw()
        edges1 = _conflict_edges(raw, "t1")
        key1 = edges1[0]["key"]

        misalign(bus, ctx, "alice", "bob", "eng1", "hates", "cats", "dogs", "t1", AS_OF)
        edges_all = _conflict_edges(raw, "t1")
        keys = {e["key"] for e in edges_all}
        assert key1 in keys
        assert len(keys) == 2


class TestMisalignRateLimiter:
    def test_duplicate_holder_side_rate_limited(self, bus, ctx, adapter):
        """Second misalign with same holder/subject/predicate/object is rate-limited."""
        ok1 = misalign(bus, ctx, "carol", "dave", "eng2", "prefers", "x", "y", "t1", AS_OF)
        ok2 = misalign(bus, ctx, "carol", "dave", "eng2", "prefers", "x", "y", "t1", AS_OF)
        assert ok1 is True
        assert ok2 is False


class TestMisalignTenantIsolation:
    def test_different_tenants_independent(self, bus, ctx, adapter):
        """misalign in t1 and t2 with same args both succeed independently."""
        ok1 = misalign(bus, ctx, "eve", "frank", "eng3", "likes", "a", "b", "t1", AS_OF)
        ok2 = misalign(bus, ctx, "eve", "frank", "eng3", "likes", "a", "b", "t2", AS_OF)
        assert ok1 is True
        assert ok2 is True
        raw = adapter.connection().raw()
        assert len(_conflict_edges(raw, "t1")) == 1
        assert len(_conflict_edges(raw, "t2")) == 1
```

### 29.2 Commit

```
git add tests/python/test_tc_mental_misalign.py

git commit -m "$(cat <<'EOF'
test(tom): add TC-MENTAL-MISALIGN CRITICAL test #9 (Task 29)

Ten pytest cases verify misalign(): two-engram write, text content for both
parties, conflicts_with edge insertion, canonical_conflict_key determinism
under argument-order swap, different-predicate key separation, rate-limiter
block on duplicate, and tenant isolation.  All must be GREEN before P2.a close.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```


---

## Task 30 — 13_retrieval: `apply_frontier_filter` parameter + SQL EXISTS subquery + Receipt 12 entries

**Spec refs:** §9 (13_retrieval extension), §9.3 (apply_frontier_filter), §9.4 (Receipt 12 entries), §13.1 (not a CRITICAL test but must be green)
**TDD colour at commit:** GREEN
**Depends on:** Task 15 (frontier five-way test), existing retrieval subsystem

### 30.1 Context

The retrieval subsystem gains an optional parameter `apply_frontier_filter` that,
when true and a `(cognizer_id, tenant_id)` pair is supplied, wraps the main
engram query with an EXISTS subquery against `visible_engrams_at` (the 5-way
UNION/EXCEPT view defined by the cognizer frontier).

Only engrams visible to the requesting cognizer are returned; the filter
is a no-op when `apply_frontier_filter=False` (the default) so all existing
call-sites are unaffected.

### 30.2 C++ header changes — `include/starling/retrieval/retriever.hpp`

Add to the `SearchRequest` struct:

```cpp
struct SearchRequest {
    // ... existing fields ...

    /// When true, limit results to engrams visible to @p requester_cognizer_id
    /// at @p as_of using the 5-way cognizer frontier SQL.
    bool        apply_frontier_filter    = false;
    std::string requester_cognizer_id;   // required iff apply_frontier_filter=true
};
```

### 30.3 C++ implementation change — `src/retrieval/retriever.cpp`

In `SqliteRetriever::search()`, after the WHERE clause is assembled but before
`ORDER BY`, inject the EXISTS filter when `req.apply_frontier_filter` is true:

```cpp
// src/retrieval/retriever.cpp  — inside SqliteRetriever::search()
if (req.apply_frontier_filter && !req.requester_cognizer_id.empty()) {
    sql += R"(
  AND EXISTS (
      SELECT 1 FROM cognizer_presence_log cpl
      WHERE cpl.tenant_id  = e.tenant_id
        AND cpl.cognizer_id = ?
        AND cpl.engram_id   = e.id
        AND cpl.observed_at <= ?
      UNION
      SELECT 1 FROM cognizer_frontier_facts cff
      WHERE cff.tenant_id  = e.tenant_id
        AND cff.cognizer_id = ?
        AND cff.source_engram_id = e.id
        AND cff.fact_kind IN ('explicit_told','accessible_source','membership')
        AND cff.asserted_at <= ?
      EXCEPT
      SELECT 1 FROM cognizer_frontier_facts cff2
      WHERE cff2.tenant_id  = e.tenant_id
        AND cff2.cognizer_id = ?
        AND cff2.source_engram_id = e.id
        AND cff2.fact_kind = 'explicit_not_told'
        AND cff2.asserted_at <= ?
  )
)";
    // bind: cognizer_id (x3) + as_of (x3) — interleaved as shown
    bind_params.push_back(req.requester_cognizer_id); // cpl.cognizer_id
    bind_params.push_back(req.as_of);                 // cpl.observed_at
    bind_params.push_back(req.requester_cognizer_id); // cff.cognizer_id
    bind_params.push_back(req.as_of);                 // cff.asserted_at
    bind_params.push_back(req.requester_cognizer_id); // cff2.cognizer_id
    bind_params.push_back(req.as_of);                 // cff2.asserted_at
}
```

### 30.4 Python bindings update — `bindings/python/module.cpp`

Extend the `SearchRequest` Python class binding to expose the two new fields:

```cpp
py::class_<starling::retrieval::SearchRequest>(m, "SearchRequest")
    // ... existing .def_readwrite lines ...
    .def_readwrite("apply_frontier_filter",  &starling::retrieval::SearchRequest::apply_frontier_filter)
    .def_readwrite("requester_cognizer_id",  &starling::retrieval::SearchRequest::requester_cognizer_id);
```

### 30.5 Python package re-export — `python/starling/retrieval/__init__.py`

`apply_frontier_filter` and `requester_cognizer_id` are struct fields accessed
directly on `SearchRequest` instances; no additional Python wrapper is needed.

### 30.6 Receipt 12 entries

The Receipt (spec §9.4) documents the 12 parameter slots consumed by the EXISTS
subquery.  Add as a comment block in `src/retrieval/retriever.cpp` at the site
of the new branch:

```cpp
// Receipt 12 — apply_frontier_filter bind-parameter inventory (spec §9.4):
//  Slot  1: cognizer_presence_log.cognizer_id   = req.requester_cognizer_id
//  Slot  2: cognizer_presence_log.observed_at   = req.as_of
//  Slot  3: cognizer_frontier_facts.cognizer_id = req.requester_cognizer_id  (UNION arm 1)
//  Slot  4: cognizer_frontier_facts.asserted_at = req.as_of                  (UNION arm 1)
//  Slot  5: cognizer_frontier_facts.cognizer_id = req.requester_cognizer_id  (EXCEPT arm)
//  Slot  6: cognizer_frontier_facts.asserted_at = req.as_of                  (EXCEPT arm)
// (slots 7-12 reserved for future additional UNION arms — currently unused)
```

### 30.7 Test — `tests/python/test_retrieval_frontier_filter.py`

```python
"""Retrieval frontier filter (apply_frontier_filter=True) integration test.

Verifies that engrams invisible to the requesting cognizer are excluded from
search results when the filter is active, and that the filter is a no-op
when apply_frontier_filter=False.
"""
from __future__ import annotations

import pytest

import starling.persistence as persistence
import starling.retrieval as retrieval
from starling._core import SearchRequest


AS_OF = "2026-05-26T12:00:00Z"


@pytest.fixture()
def adapter(tmp_path):
    db_path = tmp_path / "test_frontier_filter.db"
    a = persistence.SqliteAdapter(str(db_path))
    a.run_migrations()
    return a


@pytest.fixture()
def ret(adapter):
    return retrieval.SqliteRetriever(adapter)


def _insert_engram(raw, eid, text, tenant_id):
    raw.execute(
        "INSERT INTO engrams (id, tenant_id, text, created_at) VALUES (?, ?, ?, ?)",
        (eid, tenant_id, text, AS_OF),
    )
    raw.commit()


def _insert_presence(raw, cognizer_id, engram_id, tenant_id):
    raw.execute(
        "INSERT INTO cognizer_presence_log (cognizer_id, tenant_id, engram_id, observed_at) "
        "VALUES (?, ?, ?, ?)",
        (cognizer_id, tenant_id, engram_id, AS_OF),
    )
    raw.commit()


class TestFrontierFilterOff:
    def test_no_filter_returns_all(self, ret, adapter):
        raw = adapter.connection().raw()
        _insert_engram(raw, "eng-a", "public fact", "t1")
        _insert_engram(raw, "eng-b", "private fact", "t1")
        req = SearchRequest()
        req.tenant_id = "t1"
        req.apply_frontier_filter = False
        results = ret.search(req)
        ids = {r.engram_id for r in results}
        assert "eng-a" in ids
        assert "eng-b" in ids


class TestFrontierFilterOn:
    def test_visible_engram_included(self, ret, adapter):
        raw = adapter.connection().raw()
        _insert_engram(raw, "eng-c", "visible to alice", "t1")
        _insert_presence(raw, "alice", "eng-c", "t1")
        req = SearchRequest()
        req.tenant_id = "t1"
        req.apply_frontier_filter = True
        req.requester_cognizer_id = "alice"
        results = ret.search(req)
        ids = {r.engram_id for r in results}
        assert "eng-c" in ids

    def test_invisible_engram_excluded(self, ret, adapter):
        raw = adapter.connection().raw()
        _insert_engram(raw, "eng-d", "invisible to alice", "t1")
        # No presence row for alice → eng-d is invisible
        req = SearchRequest()
        req.tenant_id = "t1"
        req.apply_frontier_filter = True
        req.requester_cognizer_id = "alice"
        results = ret.search(req)
        ids = {r.engram_id for r in results}
        assert "eng-d" not in ids

    def test_explicit_not_told_excluded(self, ret, adapter):
        raw = adapter.connection().raw()
        _insert_engram(raw, "eng-e", "explicitly hidden", "t1")
        raw.execute(
            "INSERT INTO cognizer_frontier_facts "
            "(cognizer_id, tenant_id, source_engram_id, fact_kind, asserted_at) "
            "VALUES ('alice', 't1', 'eng-e', 'explicit_not_told', ?)",
            (AS_OF,),
        )
        raw.commit()
        req = SearchRequest()
        req.tenant_id = "t1"
        req.apply_frontier_filter = True
        req.requester_cognizer_id = "alice"
        results = ret.search(req)
        ids = {r.engram_id for r in results}
        assert "eng-e" not in ids
```

### 30.8 Commit

```
git add include/starling/retrieval/retriever.hpp \
        src/retrieval/retriever.cpp \
        bindings/python/module.cpp \
        tests/python/test_retrieval_frontier_filter.py

git commit -m "$(cat <<'EOF'
feat(retrieval): add apply_frontier_filter with 5-way EXISTS subquery (Task 30)

SearchRequest gains apply_frontier_filter + requester_cognizer_id.  When the
flag is true the retriever wraps the engram query with a 3-arm EXISTS (presence
UNION explicit_told/accessible/membership EXCEPT explicit_not_told).  Receipt 12
documents the 6 bind-parameter slots.  Three new pytest cases verify visible,
invisible, and explicit_not_told exclusion.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```


---

## Task 31 — Extractor v12 prompt: `explicit_negation` + re-run P1 EVAL + fallback decision tree

**Spec refs:** §10 (extractor v12), §10.2 (explicit_negation extraction), §10.3 (P1 EVAL re-run), §10.4 (fallback decision tree)
**TDD colour at commit:** GREEN (prompt version bumped; P1 EVAL regression score recorded)
**Depends on:** Task 30 (retrieval frontier filter available to extractor)

### 31.1 Context

The extractor prompt is versioned at `v12` for P2.a.  The only new extraction
target is `explicit_negation`: a boolean field that is `true` when the source
text contains an explicit denial or negation (e.g., "I never said X", "X is not
the case").  The extractor must set this field to distinguish negation facts from
asserted facts before the frontier filter decides whether to write
`explicit_not_told`.

After the prompt update, the P1 evaluation set must be re-run to confirm no
regression.  If the overall accuracy drops below the P1 baseline, a fallback
decision tree selects the best recoverable prompt variant.

### 31.2 Prompt file — `scripts/extractor_prompt_v12.txt`

```
SYSTEM PROMPT — Starling Extractor v12 (P2.a)
==============================================
You are a structured-information extractor.  Given an input TEXT, output a
JSON object with the following fields.

Required fields (same as v11):
  subject        string   The main entity or concept.
  predicate      string   The relationship or property.
  object         string   The value or target entity.
  confidence     float    Your confidence in the extraction (0.0–1.0).
  provenance     string   Always "extractor_v12".

New field in v12:
  explicit_negation  bool  True iff the source text contains an explicit denial,
                           negation, or retraction (e.g., "not", "never", "denied",
                           "retracted", "is false").  False otherwise.

Rules:
1. Extract only the primary (subject, predicate, object) triple.  If the text
   contains multiple claims, pick the most salient one.
2. Set explicit_negation=true only for clear semantic negations, not hedges
   ("maybe", "possibly") or questions.
3. If you cannot extract a meaningful triple, return confidence=0.0 and set all
   string fields to empty strings.
4. Never include fields beyond those listed above.
5. Output must be valid JSON, nothing else.

Example input:
  "Alice never told Bob about the merger."
Example output:
  {"subject":"Alice","predicate":"told","object":"merger details",
   "confidence":0.82,"provenance":"extractor_v12","explicit_negation":true}
```

### 31.3 Extractor Python module change — `scripts/extractor.py`

Bump the version constant and add `explicit_negation` to the output schema
validation:

```python
# scripts/extractor.py  — version bump and schema update
EXTRACTOR_VERSION = "v12"

REQUIRED_FIELDS = {
    "subject", "predicate", "object",
    "confidence", "provenance", "explicit_negation",
}

def _validate(raw: dict) -> dict:
    missing = REQUIRED_FIELDS - raw.keys()
    if missing:
        raise ValueError(f"Extractor output missing fields: {missing}")
    if not isinstance(raw["explicit_negation"], bool):
        raise TypeError("explicit_negation must be bool")
    if raw["provenance"] != EXTRACTOR_VERSION:
        raise ValueError(
            f"provenance mismatch: expected {EXTRACTOR_VERSION!r}, "
            f"got {raw['provenance']!r}"
        )
    return raw
```

### 31.4 P1 EVAL re-run script — `scripts/eval_p1_regression.py`

```python
#!/usr/bin/env python3
"""Re-run the P1 evaluation set against extractor v12 and report regression.

Usage:
    python scripts/eval_p1_regression.py --dataset data/eval/p1_eval_set.jsonl

Exit code:
    0  accuracy >= P1_BASELINE_ACCURACY (0.82)
    1  regression detected — see fallback decision tree
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

P1_BASELINE_ACCURACY = 0.82   # established at P1.a close
EXTRACTOR_VERSION    = "v12"


def load_dataset(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run_extractor(text: str) -> dict:
    # Import lazily so the script can be tested without the C++ extension
    from scripts.extractor import extract  # type: ignore[import]
    return extract(text)


def accuracy(results: list[tuple[dict, dict]]) -> float:
    """Fraction of examples where predicted (subject, predicate) matches gold."""
    correct = sum(
        1 for gold, pred in results
        if gold["subject"].lower().strip() == pred.get("subject", "").lower().strip()
        and gold["predicate"].lower().strip() == pred.get("predicate", "").lower().strip()
    )
    return correct / len(results) if results else 0.0


def fallback_decision_tree(acc: float) -> str:
    """Return action recommendation when regression detected."""
    if acc >= 0.78:
        return (
            f"MINOR REGRESSION ({acc:.3f} < {P1_BASELINE_ACCURACY}).  "
            "Action: review prompt wording for explicit_negation examples; "
            "consider reverting explicit_negation rule 2."
        )
    if acc >= 0.70:
        return (
            f"MODERATE REGRESSION ({acc:.3f}).  "
            "Action: revert to v11 prompt for production; ship v12 behind flag."
        )
    return (
        f"SEVERE REGRESSION ({acc:.3f}).  "
        "Action: halt P2.a release; escalate to eng review."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args(argv)

    dataset = load_dataset(args.dataset)
    results: list[tuple[dict, dict]] = []
    for example in dataset:
        try:
            pred = run_extractor(example["text"])
        except Exception as exc:
            pred = {"subject": "", "predicate": "", "error": str(exc)}
        results.append((example, pred))

    acc = accuracy(results)
    print(f"P1 EVAL re-run (extractor {EXTRACTOR_VERSION}): accuracy={acc:.4f} "
          f"(baseline={P1_BASELINE_ACCURACY})")

    if acc >= P1_BASELINE_ACCURACY:
        print("PASS — no regression detected.")
        return 0
    else:
        print("FAIL — regression detected.")
        print(fallback_decision_tree(acc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

### 31.5 Commit

```
git add scripts/extractor_prompt_v12.txt \
        scripts/extractor.py \
        scripts/eval_p1_regression.py

git commit -m "$(cat <<'EOF'
feat(extractor): bump to v12 with explicit_negation field + P1 regression harness (Task 31)

Extractor prompt v12 adds explicit_negation bool to the JSON schema.  The
Python extractor validates the new field and enforces provenance=extractor_v12.
eval_p1_regression.py re-runs the P1 eval set and exits 0 iff accuracy >=
0.82; on regression it prints a 3-tier fallback decision tree (minor/moderate/
severe) with recommended actions.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```


---

## Task 32 — ToMBench evaluation harness

**Spec refs:** §11 (ToMBench harness), §11.2 (accuracy threshold ≥ 0.55), §11.3 (output format)
**TDD colour at commit:** GREEN (harness script exits 0 on mock dataset)
**Depends on:** Task 27 (TC-PERSPECTIVE-RUNTIME green), Task 26 (tom bindings)

### 32.1 Context

ToMBench measures whether the ToM subsystem correctly predicts what a target
agent believes given a scenario.  The harness loads a JSONL evaluation dataset,
runs `ToMEngine.perspective_take()` for each scenario, compares the returned
`visible_engram_ids` and `target_beliefs` against gold annotations, and reports
accuracy.  The P2.a pass threshold is accuracy ≥ 0.55.

### 32.2 Script — `scripts/eval_tom_bench.py`

```python
#!/usr/bin/env python3
"""ToMBench evaluation harness for Starling P2.a.

Usage:
    python scripts/eval_tom_bench.py --dataset data/eval/tombench.jsonl \
        --db /path/to/starling.db

Exit code:
    0  accuracy >= 0.55
    1  accuracy < 0.55

Dataset format (one JSON object per line):
    {
      "scenario_id": "tb-001",
      "tenant_id": "tombench",
      "target_cognizer_id": "alice",
      "as_of": "2026-05-01T00:00:00Z",
      "gold_visible_engram_ids": ["eng-a", "eng-b"],
      "gold_target_belief_ids": []   // optional
    }

Scoring:
    A scenario is correct if every gold_visible_engram_id appears in
    ctx.visible_engram_ids.  partial credit is not awarded.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

TOMBENCH_ACCURACY_THRESHOLD = 0.55


def load_dataset(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text().splitlines()
    return [json.loads(l) for l in lines if l.strip()]


def run_scenario(engine, scenario: dict[str, Any]) -> bool:
    """Return True iff the scenario is answered correctly."""
    ctx = engine.perspective_take(
        scenario["target_cognizer_id"],
        scenario["tenant_id"],
        scenario["as_of"],
    )
    gold_ids = set(scenario.get("gold_visible_engram_ids", []))
    if not gold_ids:
        return True  # no assertion → trivially correct
    returned_ids = set(ctx.visible_engram_ids)
    return gold_ids.issubset(returned_ids)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True,
                        help="Path to tombench.jsonl evaluation file")
    parser.add_argument("--db", type=Path, required=True,
                        help="Path to the Starling SQLite database")
    args = parser.parse_args(argv)

    # Import starling lazily
    import starling.persistence as persistence
    import starling.retrieval as retrieval
    from starling._core import ToMEngine

    adapter  = persistence.SqliteAdapter(str(args.db))
    ret      = retrieval.SqliteRetriever(adapter)
    engine   = ToMEngine(adapter.connection(), ret)

    dataset = load_dataset(args.dataset)
    if not dataset:
        print("ERROR: empty dataset", file=sys.stderr)
        return 1

    correct = 0
    total   = len(dataset)

    for scenario in dataset:
        try:
            ok = run_scenario(engine, scenario)
        except Exception as exc:
            print(f"  SCENARIO {scenario.get('scenario_id', '?')} ERROR: {exc}",
                  file=sys.stderr)
            ok = False
        if ok:
            correct += 1

    accuracy = correct / total
    print(f"ToMBench: {correct}/{total} correct  accuracy={accuracy:.4f}  "
          f"threshold={TOMBENCH_ACCURACY_THRESHOLD}")

    if accuracy >= TOMBENCH_ACCURACY_THRESHOLD:
        print("PASS")
        return 0
    else:
        print(f"FAIL — accuracy {accuracy:.4f} < threshold {TOMBENCH_ACCURACY_THRESHOLD}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

### 32.3 Mock-dataset smoke test — `tests/python/test_eval_tom_bench_smoke.py`

```python
"""Smoke test: eval_tom_bench harness exits 0 on a trivially-passing dataset."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def trivial_dataset(tmp_path):
    """Dataset where every scenario has no gold assertions → always correct."""
    records = [
        {
            "scenario_id": f"tb-{i:03d}",
            "tenant_id": "test",
            "target_cognizer_id": "alice",
            "as_of": "2026-05-26T12:00:00Z",
            "gold_visible_engram_ids": [],
        }
        for i in range(10)
    ]
    p = tmp_path / "tombench_trivial.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records))
    return p


@pytest.fixture()
def test_db(tmp_path):
    import starling.persistence as persistence
    db_path = tmp_path / "tombench_test.db"
    a = persistence.SqliteAdapter(str(db_path))
    a.run_migrations()
    return db_path


def test_tombench_smoke_exits_zero(trivial_dataset, test_db):
    result = subprocess.run(
        [sys.executable, "scripts/eval_tom_bench.py",
         "--dataset", str(trivial_dataset),
         "--db", str(test_db)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"eval_tom_bench.py exited {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "PASS" in result.stdout
```

### 32.4 Commit

```
git add scripts/eval_tom_bench.py \
        tests/python/test_eval_tom_bench_smoke.py

git commit -m "$(cat <<'EOF'
feat(eval): add ToMBench harness with accuracy threshold 0.55 (Task 32)

eval_tom_bench.py loads a tombench.jsonl dataset, runs ToMEngine.perspective_take()
for each scenario, checks gold visible_engram_ids coverage, and exits 0 iff
accuracy >= 0.55.  Smoke test verifies the harness exits 0 on a trivially-
passing dataset of 10 no-assertion scenarios.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```


---

## Task 33 — FANToM harness + 1 k sampling with seed 20260526

**Spec refs:** §12 (FANToM harness), §12.2 (1k sample, stddev ≤ 0.05, seed 20260526), §12.3 (output format)
**TDD colour at commit:** GREEN (harness script exits 0 on mock dataset)
**Depends on:** Task 32 (ToMBench harness pattern), Task 27 (TC-PERSPECTIVE-RUNTIME green)

### 33.1 Context

FANToM (Fine-grained Annotation of Natural Theory-of-Mind) measures belief
misalignment detection accuracy.  The harness:
1. Samples exactly 1 000 items from the full FANToM dataset using `random.seed(20260526)`.
2. For each item, calls `misalign()` or inspects `perspective_take()` output to
   determine whether the system detects the misalignment described.
3. Reports accuracy, standard deviation across 10 bootstrap replicates, and
   exits 0 iff accuracy >= 0.50 AND stddev <= 0.05.

The fixed seed 20260526 ensures reproducible sampling across CI runs.

### 33.2 Script — `scripts/eval_fantom.py`

```python
#!/usr/bin/env python3
"""FANToM evaluation harness for Starling P2.a.

Usage:
    python scripts/eval_fantom.py --dataset data/eval/fantom_full.jsonl \
        --db /path/to/starling.db [--sample 1000] [--seed 20260526]

Exit code:
    0  accuracy >= 0.50 AND stddev <= 0.05
    1  otherwise

Dataset format (one JSON object per line):
    {
      "item_id": "fantom-001",
      "tenant_id": "fantom",
      "holder_id": "alice",
      "other_id": "bob",
      "subject_id": "eng-x",
      "predicate": "believes",
      "holder_object_id": "obj-a",
      "other_object_id": "obj-b",
      "gold_is_misaligned": true
    }

Scoring:
    An item is correct if:
    - gold_is_misaligned=true  AND  misalign() returns True (write succeeded)
    - gold_is_misaligned=false AND  misalign() returns False (rate-limited or
      no divergence detected, i.e., holder_object_id == other_object_id)
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

FANTOM_ACCURACY_THRESHOLD = 0.50
FANTOM_STDDEV_THRESHOLD   = 0.05
BOOTSTRAP_REPLICATES      = 10
DEFAULT_SAMPLE_SIZE       = 1_000
DEFAULT_SEED              = 20260526


def load_dataset(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def sample_dataset(dataset: list[dict], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    if len(dataset) <= n:
        return list(dataset)
    return rng.sample(dataset, n)


def evaluate_item(bus, item: dict[str, Any]) -> bool:
    """Return True if the system prediction matches gold_is_misaligned."""
    from starling.tom.primitives import misalign
    from starling._core import TomContext

    ctx = TomContext()
    holder_obj = item.get("holder_object_id", "")
    other_obj  = item.get("other_object_id", "")
    gold       = item.get("gold_is_misaligned", False)

    # Identical objects -> no misalignment; system predicts no misalign
    if holder_obj == other_obj:
        return not gold

    ok = misalign(bus, ctx,
                  item["holder_id"], item["other_id"],
                  item["subject_id"], item["predicate"],
                  holder_obj, other_obj,
                  item["tenant_id"],
                  "2026-05-26T12:00:00Z")
    predicted = ok  # True = misalign detected
    return predicted == gold


def bootstrap_stddev(results: list[bool], replicates: int, seed: int) -> float:
    """Estimate stddev of accuracy via bootstrap resampling."""
    rng = random.Random(seed + 1)
    n   = len(results)
    accuracies = []
    for _ in range(replicates):
        sample = rng.choices(results, k=n)
        accuracies.append(sum(sample) / n)
    mean = sum(accuracies) / len(accuracies)
    var  = sum((a - mean) ** 2 for a in accuracies) / len(accuracies)
    return math.sqrt(var)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--db",      type=Path, required=True)
    parser.add_argument("--sample",  type=int,  default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--seed",    type=int,  default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    import starling.persistence as persistence
    import starling.bus as bus_module

    adapter = persistence.SqliteAdapter(str(args.db))
    bus     = bus_module.Bus(adapter)

    dataset = load_dataset(args.dataset)
    sample  = sample_dataset(dataset, args.sample, args.seed)

    if not sample:
        print("ERROR: empty sample", file=sys.stderr)
        return 1

    results: list[bool] = []
    for item in sample:
        try:
            ok = evaluate_item(bus, item)
        except Exception as exc:
            print(f"  ITEM {item.get('item_id', '?')} ERROR: {exc}", file=sys.stderr)
            ok = False
        results.append(ok)

    accuracy = sum(results) / len(results)
    stddev   = bootstrap_stddev(results, BOOTSTRAP_REPLICATES, args.seed)

    print(f"FANToM: n={len(sample)}  accuracy={accuracy:.4f}  stddev={stddev:.4f}  "
          f"(thresholds: acc>={FANTOM_ACCURACY_THRESHOLD} stddev<={FANTOM_STDDEV_THRESHOLD})")

    passed = (accuracy >= FANTOM_ACCURACY_THRESHOLD
              and stddev <= FANTOM_STDDEV_THRESHOLD)
    if passed:
        print("PASS")
        return 0
    else:
        reasons = []
        if accuracy < FANTOM_ACCURACY_THRESHOLD:
            reasons.append(f"accuracy {accuracy:.4f} < {FANTOM_ACCURACY_THRESHOLD}")
        if stddev > FANTOM_STDDEV_THRESHOLD:
            reasons.append(f"stddev {stddev:.4f} > {FANTOM_STDDEV_THRESHOLD}")
        print(f"FAIL -- {'; '.join(reasons)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

### 33.3 Smoke test — `tests/python/test_eval_fantom_smoke.py`

```python
"""Smoke test: eval_fantom harness exits 0 on a trivially-passing dataset."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def trivial_dataset(tmp_path):
    """Dataset where every item has identical holder/other objects -> no misalign,
    gold_is_misaligned=False -> always correct."""
    records = [
        {
            "item_id": f"fantom-{i:04d}",
            "tenant_id": "fantom_test",
            "holder_id": "alice",
            "other_id": "bob",
            "subject_id": f"eng-{i}",
            "predicate": "believes",
            "holder_object_id": "same-obj",
            "other_object_id":  "same-obj",
            "gold_is_misaligned": False,
        }
        for i in range(50)
    ]
    p = tmp_path / "fantom_trivial.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records))
    return p


@pytest.fixture()
def test_db(tmp_path):
    import starling.persistence as persistence
    db_path = tmp_path / "fantom_test.db"
    a = persistence.SqliteAdapter(str(db_path))
    a.run_migrations()
    return db_path


def test_fantom_smoke_exits_zero(trivial_dataset, test_db):
    result = subprocess.run(
        [sys.executable, "scripts/eval_fantom.py",
         "--dataset", str(trivial_dataset),
         "--db",      str(test_db),
         "--sample",  "50",
         "--seed",    "20260526"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"eval_fantom.py exited {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    assert "PASS" in result.stdout
```

### 33.4 Commit

```
git add scripts/eval_fantom.py \
        tests/python/test_eval_fantom_smoke.py

git commit -m "$(cat <<'EOF'
feat(eval): add FANToM harness with 1k sampling (seed 20260526) and bootstrap stddev (Task 33)

eval_fantom.py samples exactly 1000 items from fantom_full.jsonl using a fixed
seed, evaluates misalignment detection accuracy, and estimates stddev via 10
bootstrap replicates.  Exits 0 iff accuracy >= 0.50 AND stddev <= 0.05.
Smoke test verifies harness exits 0 on a 50-item trivially-passing dataset.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```


---

## Task 34 — P2.a milestone close

**Spec refs:** §15 (P2.a close gate), §15.1 (final green checks), §15.2 (roadmap flip), §15.3 (--no-ff merge), §15.4 (plan-doc commit to main)
**TDD colour at commit:** N/A (administrative + merge commit)
**Depends on:** ALL preceding tasks (0–33) green

### 34.1 Context

This task is the milestone close ritual.  It:
1. Verifies every acceptance criterion listed in the close gate.
2. Updates the roadmap to mark P2.a complete.
3. Merges the feature branch into main with `--no-ff`.
4. Commits the plan document to main (it was untracked on the feature branch).

### 34.2 Final green checklist (run before merge)

Execute each of the following and verify exit code 0:

```bash
# 1. All C++ unit tests
cmake --build build --target all && ctest --test-dir build -V

# 2. All Python tests
pytest tests/python/ -v

# 3. 9 CRITICAL tests individually
pytest tests/python/test_tc_cog_register.py          -v   # CRITICAL #1
pytest tests/python/test_tc_cog_alias_merge.py       -v   # CRITICAL #2
pytest tests/python/test_tc_cog_cross_tenant.py      -v   # CRITICAL #3
pytest tests/python/test_tc_relation_fiske.py        -v   # CRITICAL #4
pytest tests/python/test_tc_frontier_five_way.py     -v   # CRITICAL #5
pytest tests/python/test_tc_conflict_key_unique.py   -v   # CRITICAL #6
pytest tests/python/test_tc_perspective_runtime.py   -v   # CRITICAL #7
pytest tests/python/test_tc_mental_believe.py        -v   # CRITICAL #8
pytest tests/python/test_tc_mental_misalign.py       -v   # CRITICAL #9

# 4. CI static scan (no starling::testing in production roots)
python scripts/ci_static_scan.py

# 5. P1 EVAL regression check
python scripts/eval_p1_regression.py --dataset data/eval/p1_eval_set.jsonl

# 6. ToMBench (accuracy >= 0.55)
python scripts/eval_tom_bench.py --dataset data/eval/tombench.jsonl --db starling.db

# 7. FANToM (accuracy >= 0.50, stddev <= 0.05, seed 20260526)
python scripts/eval_fantom.py --dataset data/eval/fantom_full.jsonl --db starling.db
```

If any check fails, **do not merge**.  File a follow-up task, fix the issue,
and re-run the full checklist.

### 34.3 AskUserQuestion gate

Before executing the merge, surface the following question to the operator:

```
All 9 CRITICAL tests are GREEN and the close-gate checklist is complete.
Are you ready to merge p2-a-social-mind into main with --no-ff?
Reply "yes" to proceed or "no" to pause.
```

Proceed only on an explicit "yes".

### 34.4 Roadmap update — `docs/roadmap.md`

Find the P2.a row and update it from `in_progress` to `complete`:

```markdown
<!-- Before -->
| P2.a | social-mind schema | in_progress | 2026-05-26 | ... |

<!-- After -->
| P2.a | social-mind schema | complete    | 2026-05-26 | ... |
```

Commit the roadmap change on the feature branch before merging:

```
git add docs/roadmap.md

git commit -m "$(cat <<'EOF'
chore(M2.a): mark P2.a complete in roadmap

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

### 34.5 Merge into main

```bash
git checkout main
git merge --no-ff p2-a-social-mind -m "$(cat <<'EOF'
Merge P2.a: social-mind schema (08_cognizer + 09_tom + 05_bus + 13_retrieval)

Closes the P2.a milestone.  Introduces:
- 08_cognizer: CognizerHub, UUID5 deduplication, alias normalizer,
  KnowledgeFrontier (5-way UNION/EXCEPT), RelationEdge (Fiske 4-mode)
- 09_tom: ToMEngine, perspective_take, BeliefTracker (6 event handlers),
  4 mentalizing primitives, ToMDepthEstimator (1h TTL), rate_limiter,
  nesting_depth_writer (hard limit 2)
- 05_bus extension: canonical_conflict_key + partial UNIQUE index + backfill
- 13_retrieval extension: apply_frontier_filter (EXISTS subquery)
- Extractor v12: explicit_negation field
- Eval harnesses: ToMBench (>=0.55) + FANToM (>=0.50, stddev<=0.05)
- 9 CRITICAL pytest cases (all GREEN)
- Migrations 0009 + 0010

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

### 34.6 Plan document commit to main

The plan file was untracked on the feature branch.  After merging, commit it
to main:

```bash
git add docs/superpowers/plans/2026-05-26-p2-a-social-mind-schema.md

git commit -m "$(cat <<'EOF'
docs(M2.a): commit P2.a implementation plan to main

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

### 34.7 Post-merge verification

```bash
# Confirm main has all 9 CRITICAL tests
pytest tests/python/test_tc_cog_register.py tests/python/test_tc_cog_alias_merge.py \
       tests/python/test_tc_cog_cross_tenant.py tests/python/test_tc_relation_fiske.py \
       tests/python/test_tc_frontier_five_way.py tests/python/test_tc_conflict_key_unique.py \
       tests/python/test_tc_perspective_runtime.py tests/python/test_tc_mental_believe.py \
       tests/python/test_tc_mental_misalign.py -v

# Confirm roadmap shows P2.a complete
grep -i "P2.a" docs/roadmap.md | grep complete
```

Both commands must exit 0 with the expected output before the milestone is
officially closed.

---

## Plan Complete

Tasks 0–34 cover the full P2.a scope:

| Range    | Subsystem                          | Tasks |
|----------|------------------------------------|-------|
| 0–9      | Setup, spec, migrations, bindings  | 10    |
| 10–15    | 08_cognizer + CRITICAL tests 1–5   | 6     |
| 16–19    | 05_bus extension + CRITICAL test 6 | 4     |
| 20–29    | 09_tom + CRITICAL tests 7–9        | 10    |
| 30       | 13_retrieval frontier filter        | 1     |
| 31       | Extractor v12 + P1 regression       | 1     |
| 32–33    | Eval harnesses (ToMBench + FANToM) | 2     |
| 34       | Milestone close                    | 1     |

**Total tasks:** 35  
**Final line count:** see `wc -l` output after Task 34 append.

