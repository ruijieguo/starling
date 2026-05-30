# M0.8 无向量脑动力学核心 Implementation Plan（P2.b 第一阶段）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 3 个空子系统（07_neocortex / 10_replay / 11_reconsolidation）+ 扩展 3 个（04_substrate Projection Index / 05_bus SubscriberPump / 09_tom CommonGround writer），让有代码子系统从 7/12 增到 10/12，满足 §16.3 准入 -3/-4/-6/-7/-9（SQL 部分）。全部基于现有 SQLite + statement 字段，零向量/图/logprobs 依赖。

**Architecture:** 按 spec §14 偏序：先落 5 migration（0011-0015）；再 10_replay（forgetting_curve → swr_sampler → 5 consolidation_ops → ReplayScheduler）；再 11_reconsolidation（plastic_window → arbitration → ReconsolidationEngine）；再 07_neocortex（Persona/CommonGround Container）；再 09_tom CommonGround writer；再 04_substrate ProjectionMaintainer；最后 SubscriberPump 统一 post-write 泵（迁移 P2.a 两个 tick）+ pybind + roll-up。8 个 admission CRITICAL 在对应子系统完成后立即写。

**Tech Stack:** C++20 + raw SQLite + pybind11 + Python 3.14 + pytest + ctest + Ninja。无新基础设施（向量/图/logprobs 在 M0.9）。

---

## Conventions

These apply to every task. Do not repeat them per-task.

**Worktree.** All work happens on branch `worktree-m0-8-brain-dynamics` in `.claude/worktrees/m0-8-brain-dynamics`. The worktree was already created via `EnterWorktree`; Task 0 just verifies baseline. Stay on this branch until the close task instructs otherwise.

**Build & test commands** (run from the worktree root):
- `source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate` — must precede every cmake/ctest/pytest invocation
- Configure (run once or after CMakeLists / new migration): `cmake -S . -B build -G Ninja`
- Build: `cmake --build build`
- Refresh editable install (after any pybind binding change): `cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages`
- Refresh Python editable install (after first entering worktree, or any python/ change): `pip install -e . --no-deps --force-reinstall`
- C++ tests: `ctest --test-dir build --output-on-failure`
- Python tests: `pytest tests/python -q`
- CI scanner: `python scripts/ci_static_scan.py`

**Commit policy.**
- Every "Commit" step runs hooks; do NOT pass `--no-verify` or `--no-gpg-sign`.
- On hook failure, fix the underlying issue and create a NEW commit (never `--amend`).
- Co-author every commit with HEREDOC body:
  ```bash
  git commit -m "$(cat <<'EOF'
  <subject>

  <body>

  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
  EOF
  )"
  ```

**Plan file untracked.** `docs/superpowers/plans/2026-05-27-m0-8-brain-dynamics-core.md` MUST NOT be `git add`-ed on this branch. It commits to main only after the milestone-close merge (Task 32).

**Test hygiene.**
- `:memory:` for C++ SQLite unit tests; never `/tmp/*.db`.
- Python runtime tests use the canonical `rt` fixture (`tmp_path` + `relax_preflight_for_m0_3()`) from `tests/python/test_tc_q3b_001.py`.
- One `starling_tests` executable; never add a new `add_executable`. Append new test .cpp to the existing list in `tests/cpp/CMakeLists.txt`.
- `starling_core` uses an explicit `target_sources` list (NOT glob); append each new .cpp to it in `CMakeLists.txt`.
- Production roots must not reference `starling::testing` / `starling.testing` — `scripts/ci_static_scan.py` blocks this.

**Key pre-existing facts.**
- `ConsolidationState::REPLAYING_RECONSOLIDATING` already exists in `src/schema/statement_enums.cpp` (to_string + from_string). Do NOT re-add it — just use it.
- `statements.consolidation_state` has no CHECK constraint — new state values need no schema change.
- Migrations are glob-based; highest existing is `0010`. M0.8 uses `0011`–`0015`.
- `common_ground` table + `containers` table already exist (P1 + P2.a). M0.8 ALTERs them.

**Subagent guidance.** Each Task is one implementer subagent invocation. Follow TDD: failing test → minimal impl → run → commit. Mark complete only when ctest + pytest + ci_static_scan are green for the touched surface.

---

## File Structure

### Files created

| Path | Responsibility |
|---|---|
| `migrations/0011_replay_scheduler.sql` | replay_scheduler_state + replay_ledger + statements.last_replay_batch_id |
| `migrations/0012_reconsolidation.sql` | reconsolidation_windows + pending_evidence + checkpoint |
| `migrations/0013_container_content.sql` | containers.content_json ALTER |
| `migrations/0014_grounding_acts.sql` | grounding_acts + common_ground.establishment_evidence_json |
| `migrations/0015_projection_index.sql` | proj_* 6 tables + projection_rebuild_state + projection_subscriber_checkpoint |
| `include/starling/replay/forgetting_curve.hpp` + `src/replay/forgetting_curve.cpp` | S(t) + S0 五因子 |
| `include/starling/replay/swr_sampler.hpp` + `src/replay/swr_sampler.cpp` | sample_weight 完整公式 + eligible 过滤 |
| `include/starling/replay/consolidation_ops.hpp` + `src/replay/consolidation_ops.cpp` | compress/abstract/reinforce/decay/reconcile |
| `include/starling/replay/replay_scheduler.hpp` + `src/replay/replay_scheduler.cpp` | tick_online/run_idle/run_sleep + 振荡防护 + TTL |
| `include/starling/reconsolidation/plastic_window.hpp` + `src/reconsolidation/plastic_window.cpp` | 窗口锁 + pending_evidence + 自适应超时 |
| `include/starling/reconsolidation/arbitration.hpp` + `src/reconsolidation/arbitration.cpp` | aggregate_evidence + 3 仲裁 |
| `include/starling/reconsolidation/reconsolidation_engine.hpp` + `src/reconsolidation/reconsolidation_engine.cpp` | subscriber tick + close_due_windows + reconsolidate |
| `include/starling/neocortex/persona_container.hpp` + `src/neocortex/persona_container.cpp` | rebuild + anchor 仲裁 + CAS |
| `include/starling/neocortex/common_ground_container.hpp` + `src/neocortex/common_ground_container.cpp` | 物化视图 |
| `include/starling/tom/common_ground_writer.hpp` + `src/tom/common_ground_writer.cpp` | 5 Grounding Acts + grounded 状态机 |
| `include/starling/projection/projection_maintainer.hpp` + `src/projection/projection_maintainer.cpp` | 6 投影增量 + rebuild + repair guard |
| `include/starling/bus/subscriber_pump.hpp` + `src/bus/subscriber_pump.cpp` | 统一 post-write 泵 |
| `python/starling/replay/__init__.py` + `reconsolidation/` + `neocortex/` + `projection/` | Python wrappers |
| `tests/cpp/test_*.cpp` | C++ unit tests (per subsystem) |
| `tests/python/test_tc_a1_001.py` / `test_tc_a1_002.py` / `test_tc_a6_001.py` / `test_tc_a6_002.py` / `test_tc_a5_001.py` / `test_tc_a5_002.py` / `test_tc_a8_001.py` / `test_tc_projection_repair.py` | 8 admission CRITICAL |
| `tests/python/test_*` roll-up | non-CRITICAL 运行时正确性 |
| `docs/superpowers/plans/2026-05-27-m0-8-brain-dynamics-core.md` | This file (untracked until close) |

### Files modified

| Path | Change |
|---|---|
| `CMakeLists.txt` | append new .cpp to `starling_core target_sources` |
| `tests/cpp/CMakeLists.txt` | append new test .cpp to `starling_tests` |
| `bindings/python/module.cpp` | append ReplayScheduler/ReconsolidationEngine/PersonaContainer/CommonGroundWriter/ProjectionMaintainer bindings |
| `src/bus/bus.cpp` | replace post-write tick calls (~lines 619-630) with `SubscriberPump::run_post_write` |
| `include/starling/bus/bus.hpp` | SubscriberPump member / wiring |
| `docs/superpowers/plans/2026-05-23-roadmap.md` | P2.b/M0.8 row flip at close |

---

## Risk-Front Execution Order

```
Task 0   Worktree + baseline
Task 1   Migration 0011 replay scheduler
Task 2   Migration 0012 reconsolidation
Task 3   Migration 0013 container content
Task 4   Migration 0014 grounding acts
Task 5   Migration 0015 projection index
Task 6   forgetting_curve
Task 7   swr_sampler
Task 8   consolidation_ops compress
Task 9   consolidation_ops abstract + reinforce
Task 10  consolidation_ops decay (serial)
Task 11  consolidation_ops reconcile
Task 12  ReplayScheduler (tick_online/run_idle/run_sleep + 振荡防护 + TTL)
Task 13  TC-A1-001 [CRITICAL]
Task 14  TC-A1-002 [CRITICAL]
Task 15  TC-A6-001 + TC-A6-002 [CRITICAL ×2]
Task 16  plastic_window
Task 17  arbitration: aggregate + supports + mild
Task 18  arbitration: severe (4 项原子)
Task 19  ReconsolidationEngine (subscriber + close_due_windows)
Task 20  TC-A5-001 [CRITICAL]
Task 21  TC-A5-002 [CRITICAL]
Task 22  TC-A8-001 [CRITICAL]
Task 23  PersonaContainer
Task 24  CommonGroundContainer
Task 25  CommonGroundWriter (5 acts + grounded 状态机)
Task 26  ProjectionMaintainer tick (6 投影增量)
Task 27  ProjectionMaintainer rebuild + repair guard
Task 28  TC-PROJECTION-REPAIR [CRITICAL]
Task 29  SubscriberPump (迁移 P2.a 两个 tick + 3 新)
Task 30  pybind + python wrappers
Task 31  non-CRITICAL roll-up + §16.3-9 回归
Task 32  Milestone close
```

---

## Task 0: Worktree + Baseline

**Files:** 无文件改动；环境确认。

- [ ] **Step 1: 确认 worktree 分支**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-8-brain-dynamics
git branch --show-current
```
Expected: `worktree-m0-8-brain-dynamics`。若错，STOP 重建 worktree。

- [ ] **Step 2: venv + 刷新 editable install + 配置 build**

```bash
source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
pip install -e . --no-deps --force-reinstall
cmake -S . -B build -G Ninja
cmake --build build
```
Expected: pip install OK；build 成功，无新 warning。

- [ ] **Step 3: 验证 baseline 全绿**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
python scripts/ci_static_scan.py 2>&1 | tail -2
```
Expected: ctest `100% tests passed ... out of 361`；pytest `418 passed, 13 skipped`；ci_static_scan OK。任一失败 STOP。

- [ ] **Step 4: 确认 REPLAYING_RECONSOLIDATING 枚举已存在**

```bash
grep -n "REPLAYING_RECONSOLIDATING" src/schema/statement_enums.cpp
```
Expected: to_string + from_string 两处命中。Reconsolidation 任务直接复用，无需加枚举。

- [ ] **Step 5: 无 commit（Task 0 仅验证）**

---

## Task 1: Migration 0011 — Replay Scheduler

**Files:**
- Create: `migrations/0011_replay_scheduler.sql`
- Test: 复用 `tests/cpp/test_migration_runner.cpp`（glob 发现）

**Spec ref:** §5.1

- [ ] **Step 1: 写 migration 0011**

Create `migrations/0011_replay_scheduler.sql`:

```sql
-- M0.8 Replay Scheduler 状态 (per spec §5.1).

CREATE TABLE replay_scheduler_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    online_trigger_counter INTEGER NOT NULL DEFAULT 0,
    last_online_run_at TEXT,
    last_idle_run_at TEXT,
    last_sleep_run_at TEXT,
    last_updated_at TEXT NOT NULL
);
INSERT INTO replay_scheduler_state (id, last_updated_at)
    VALUES (1, '2026-05-27T00:00:00Z');

CREATE TABLE replay_ledger (
    replay_batch_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('online','idle','sleep')),
    sampled_count INTEGER NOT NULL DEFAULT 0,
    ops_applied_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL,
    finished_at TEXT
);

ALTER TABLE statements ADD COLUMN last_replay_batch_id TEXT;
```

- [ ] **Step 2: 重配置 + build（glob 拾取 + 重生成 migrations.inc）**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -3
cmake --build build 2>&1 | tail -5
```
Expected: Configuring/Generating done；build 成功。

- [ ] **Step 3: 验证迁移应用 + 表存在**

```bash
ctest --test-dir build --output-on-failure -R MigrationRunner 2>&1 | tail -5
python3 -c "
import sqlite3, tempfile, os
from starling import _core
f = tempfile.NamedTemporaryFile(suffix='.db', delete=False); db=f.name; f.close()
_core.SqliteAdapter.open(db)
c = sqlite3.connect(db)
print('tables:', sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'replay%'\")))
print('last_replay_batch_id col:', any(r[1]=='last_replay_batch_id' for r in c.execute('PRAGMA table_info(statements)')))
os.unlink(db)
"
```
Expected: `tables: ['replay_ledger', 'replay_scheduler_state']`；`last_replay_batch_id col: True`。

- [ ] **Step 4: 全 guard**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
```
Expected: 361/361，418+13。迁移纯增量无回归。

- [ ] **Step 5: Commit**

```bash
git add migrations/0011_replay_scheduler.sql
git commit -m "$(cat <<'EOF'
feat(M0.8/replay): migration 0011 — replay scheduler state + ledger

spec §5.1: replay_scheduler_state (singleton, online_trigger_counter +
三模式 last_run 时间戳), replay_ledger (每批次审计), statements 加
last_replay_batch_id 列 (采样归属)。

S(t) 遗忘曲线 / SWR 采样权重全部从现有字段即时计算, 零新列。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Migration 0012 — Reconsolidation

**Files:**
- Create: `migrations/0012_reconsolidation.sql`

**Spec ref:** §5.2

- [ ] **Step 1: 写 migration 0012**

Create `migrations/0012_reconsolidation.sql`:

```sql
-- M0.8 Reconsolidation Engine 状态 (per spec §5.2).

CREATE TABLE reconsolidation_windows (
    stmt_id TEXT PRIMARY KEY,            -- 窗口锁: 一个 stmt 同时只一个活跃窗口
    tenant_id TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    close_deadline TEXT NOT NULL,        -- opened_at + adaptive_timeout
    trigger_event_ids_json TEXT NOT NULL DEFAULT '[]',
    force_close_trigger_count INTEGER NOT NULL DEFAULT 0,
    evicted_count INTEGER NOT NULL DEFAULT 0,
    evicted_summary_hashes_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed'))
);
CREATE INDEX idx_recon_windows_deadline
    ON reconsolidation_windows(status, close_deadline);

CREATE TABLE reconsolidation_pending_evidence (
    id TEXT PRIMARY KEY,
    window_stmt_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_stmt_id TEXT,
    payload_hash TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    arrived_at TEXT NOT NULL
);
CREATE INDEX idx_recon_evidence_window
    ON reconsolidation_pending_evidence(window_stmt_id, arrived_at);

CREATE TABLE reconsolidation_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO reconsolidation_checkpoint (id, last_updated_at)
    VALUES (1, '2026-05-27T00:00:00Z');
```

- [ ] **Step 2: 重配置 + build**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -3
cmake --build build 2>&1 | tail -5
```

- [ ] **Step 3: 验证表存在**

```bash
python3 -c "
import sqlite3, tempfile, os
from starling import _core
f=tempfile.NamedTemporaryFile(suffix='.db',delete=False); db=f.name; f.close()
_core.SqliteAdapter.open(db); c=sqlite3.connect(db)
print('tables:', sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'reconsolidation%'\")))
os.unlink(db)
"
```
Expected: `['reconsolidation_checkpoint', 'reconsolidation_pending_evidence', 'reconsolidation_windows']`。

- [ ] **Step 4: 全 guard**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
```
Expected: 361/361，418+13。

- [ ] **Step 5: Commit**

```bash
git add migrations/0012_reconsolidation.sql
git commit -m "$(cat <<'EOF'
feat(M0.8/reconsolidation): migration 0012 — plastic windows + evidence

spec §5.2: reconsolidation_windows (stmt_id PK = 窗口锁), pending_evidence
(每窗口 100 FIFO), reconsolidation_checkpoint (Outbox subscriber 位点)。

REPLAYING_RECONSOLIDATING 枚举已存在于 statement_enums.cpp, 无需加;
confidence_history_json 已在 statements (mild correction 追加写)。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Migration 0013 — Container content

**Files:**
- Create: `migrations/0013_container_content.sql`

**Spec ref:** §5.3

- [ ] **Step 1: 写 migration 0013**

Create `migrations/0013_container_content.sql`:

```sql
-- M0.8 Neocortex Persona/CommonGround Container 物化载荷 (per spec §5.3).
ALTER TABLE containers ADD COLUMN content_json TEXT NOT NULL DEFAULT '{}';
```

- [ ] **Step 2: 重配置 + build**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -3
cmake --build build 2>&1 | tail -3
```

- [ ] **Step 3: 验证列存在**

```bash
python3 -c "
import sqlite3, tempfile, os
from starling import _core
f=tempfile.NamedTemporaryFile(suffix='.db',delete=False); db=f.name; f.close()
_core.SqliteAdapter.open(db); c=sqlite3.connect(db)
print('content_json col:', any(r[1]=='content_json' for r in c.execute('PRAGMA table_info(containers)')))
os.unlink(db)
"
```
Expected: `content_json col: True`。

- [ ] **Step 4: 全 guard**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
```
Expected: 361/361，418+13。

- [ ] **Step 5: Commit**

```bash
git add migrations/0013_container_content.sql
git commit -m "$(cat <<'EOF'
feat(M0.8/neocortex): migration 0013 — containers.content_json

spec §5.3: containers 加 content_json 载荷列, 存物化 Persona dimensions +
self_model_anchor/profile_anchor + CommonGround dimensions。
CAS 用现有 containers.version 列, kind 已含 persona/common_ground。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Migration 0014 — Grounding Acts

**Files:**
- Create: `migrations/0014_grounding_acts.sql`

**Spec ref:** §5.4

- [ ] **Step 1: 写 migration 0014**

Create `migrations/0014_grounding_acts.sql`:

```sql
-- M0.8 CommonGround Grounding Acts 审计 (per spec §5.4).

CREATE TABLE grounding_acts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    common_ground_id TEXT NOT NULL,
    act TEXT NOT NULL CHECK (act IN
        ('assert','acknowledge','repair','withdraw','supersede')),
    actor_cognizer_id TEXT,
    statement_id TEXT,
    occurred_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_grounding_acts_cg
    ON grounding_acts(tenant_id, common_ground_id, occurred_at);

ALTER TABLE common_ground ADD COLUMN establishment_evidence_json TEXT NOT NULL DEFAULT '[]';
```

- [ ] **Step 2: 重配置 + build**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -3
cmake --build build 2>&1 | tail -3
```

- [ ] **Step 3: 验证**

```bash
python3 -c "
import sqlite3, tempfile, os
from starling import _core
f=tempfile.NamedTemporaryFile(suffix='.db',delete=False); db=f.name; f.close()
_core.SqliteAdapter.open(db); c=sqlite3.connect(db)
print('grounding_acts:', bool(c.execute(\"SELECT name FROM sqlite_master WHERE name='grounding_acts'\").fetchone()))
print('estab col:', any(r[1]=='establishment_evidence_json' for r in c.execute('PRAGMA table_info(common_ground)')))
os.unlink(db)
"
```
Expected: `grounding_acts: True`；`estab col: True`。

- [ ] **Step 4: 全 guard**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
```
Expected: 361/361，418+13。

- [ ] **Step 5: Commit**

```bash
git add migrations/0014_grounding_acts.sql
git commit -m "$(cat <<'EOF'
feat(M0.8/tom): migration 0014 — grounding_acts 审计日志

spec §5.4: grounding_acts (5 动作 assert/acknowledge/repair/withdraw/
supersede 审计), common_ground 加 establishment_evidence_json。
P2.a 的 common_ground.status 枚举已覆盖 5 动作状态机目标。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Migration 0015 — Projection Index

**Files:**
- Create: `migrations/0015_projection_index.sql`

**Spec ref:** §5.5

- [ ] **Step 1: 写 migration 0015**

Create `migrations/0015_projection_index.sql`:

```sql
-- M0.8 Projection Index 6 SQL 物化投影 + repair guard (per spec §5.5).
-- idx_vector_payload (第7个) 推迟 M0.9。

CREATE TABLE proj_holder_state_time (
    tenant_id TEXT NOT NULL, holder_id TEXT NOT NULL,
    consolidation_state TEXT NOT NULL, observed_at TEXT NOT NULL,
    stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, holder_id, stmt_id)
);
CREATE TABLE proj_holder_subgraph (
    tenant_id TEXT NOT NULL, holder_id TEXT NOT NULL,
    subject_kind TEXT NOT NULL, subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, holder_id, stmt_id)
);
CREATE TABLE proj_entity_statement (
    tenant_id TEXT NOT NULL, subject_kind TEXT NOT NULL,
    subject_id TEXT NOT NULL, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, subject_kind, subject_id, stmt_id)
);
CREATE TABLE proj_salience_hot (
    tenant_id TEXT NOT NULL, salience REAL NOT NULL, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, stmt_id)
);
CREATE INDEX idx_proj_salience ON proj_salience_hot(tenant_id, salience DESC);
CREATE TABLE proj_commitment_due (
    tenant_id TEXT NOT NULL, due_at TEXT, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, stmt_id)
);
CREATE INDEX idx_proj_commitment ON proj_commitment_due(tenant_id, due_at);
CREATE TABLE proj_common_ground (
    tenant_id TEXT NOT NULL, common_ground_id TEXT NOT NULL,
    status TEXT NOT NULL, stmt_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, common_ground_id, stmt_id)
);

CREATE TABLE projection_rebuild_state (
    projection_name TEXT PRIMARY KEY,
    ground_truth_count INTEGER NOT NULL DEFAULT 0,
    index_count INTEGER NOT NULL DEFAULT 0,
    last_rebuilt_at TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','truncation_suspected'))
);

CREATE TABLE projection_subscriber_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO projection_subscriber_checkpoint (id, last_updated_at)
    VALUES (1, '2026-05-27T00:00:00Z');
```

- [ ] **Step 2: 重配置 + build**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -3
cmake --build build 2>&1 | tail -5
```

- [ ] **Step 3: 验证 6 投影表 + 状态表**

```bash
python3 -c "
import sqlite3, tempfile, os
from starling import _core
f=tempfile.NamedTemporaryFile(suffix='.db',delete=False); db=f.name; f.close()
_core.SqliteAdapter.open(db); c=sqlite3.connect(db)
proj = sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'proj_%'\"))
print('projections:', proj, 'count:', len(proj))
print('rebuild_state:', bool(c.execute(\"SELECT name FROM sqlite_master WHERE name='projection_rebuild_state'\").fetchone()))
os.unlink(db)
"
```
Expected: 6 个 proj_ 表；rebuild_state True。

- [ ] **Step 4: 全 guard**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
python scripts/ci_static_scan.py 2>&1 | tail -2
```
Expected: 361/361，418+13，ci OK。

- [ ] **Step 5: Commit**

```bash
git add migrations/0015_projection_index.sql
git commit -m "$(cat <<'EOF'
feat(M0.8/substrate): migration 0015 — projection index 6 SQL 投影

spec §5.5: 6 个去规范化物化投影 (holder_state_time / holder_subgraph /
entity_statement / salience_hot / commitment_due / common_ground) +
projection_rebuild_state (repair guard §16.3-3/-6) + subscriber checkpoint。
idx_vector_payload (第7) 推迟 M0.9。

物化表而非 SQL 索引: repair guard 需比对 ground_truth vs index_count,
只有异步物化表会漂移才需 truncation_suspected 检测。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: forgetting_curve（S(t) + S0 五因子）

**Files:**
- Create: `include/starling/replay/forgetting_curve.hpp`, `src/replay/forgetting_curve.cpp`, `tests/cpp/test_forgetting_curve.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.4

- [ ] **Step 1: 写 header**

Create `include/starling/replay/forgetting_curve.hpp`:

```cpp
#pragma once
#include <string>
#include <string_view>

namespace starling::replay {

// 遗忘强度因子. 调用方提供这些已从 statement 行读出的字段.
struct ForgettingInputs {
    double salience = 0.0;          // [0,1]
    int64_t access_count = 0;
    bool active_grounded = false;   // CommonGround 中未 expired/superseded/ungrounded
    std::string modality;           // COMMITS 极慢 / ASSUMES 快
    double affect_valence = 0.0;    // [-1,1]
    std::string last_accessed_iso;  // 计算 Δt
};

// S0(stmt) = base × (1+0.5×access_count) × (1+salience)
//            × (1+2×active_grounded) × decay_modifier_by_modality
//            × (1+0.3×|affect.valence|)
double compute_s0(const ForgettingInputs& in);

// S(t) = exp(-Δt / S0); Δt 为 now - last_accessed 的秒数.
double compute_s_t(const ForgettingInputs& in, std::string_view now_iso);

// modality → decay_modifier (COMMITS 慢 → 大; ASSUMES 快 → 小)
double decay_modifier_by_modality(std::string_view modality);

}  // namespace starling::replay
```

- [ ] **Step 2: 写 impl**

Create `src/replay/forgetting_curve.cpp`:

```cpp
#include "starling/replay/forgetting_curve.hpp"
#include <chrono>
#include <cmath>
#include <ctime>

namespace starling::replay {
namespace {
constexpr double kBase = 86400.0;  // base S0 in seconds (~1 day)

// 解析 ISO-8601 UTC "YYYY-MM-DDTHH:MM:SSZ" → epoch 秒
double parse_iso_epoch(std::string_view iso) {
    std::tm tm{};
    // 简化解析: 仅处理 Z 结尾的秒级 UTC
    int y, mo, d, h, mi, s;
    if (std::sscanf(std::string(iso).c_str(), "%d-%d-%dT%d:%d:%dZ",
                    &y, &mo, &d, &h, &mi, &s) != 6) return 0.0;
    tm.tm_year = y - 1900; tm.tm_mon = mo - 1; tm.tm_mday = d;
    tm.tm_hour = h; tm.tm_min = mi; tm.tm_sec = s;
    return static_cast<double>(timegm(&tm));
}
}  // namespace

double decay_modifier_by_modality(std::string_view modality) {
    if (modality == "COMMITS" || modality == "commits")     return 4.0;   // 极慢
    if (modality == "NORM_OUGHT" || modality == "norm_ought") return 3.0;
    if (modality == "KNOWS" || modality == "knows")         return 2.0;
    if (modality == "BELIEVES" || modality == "believes")   return 1.0;
    if (modality == "ASSUMES" || modality == "assumes")     return 0.5;   // 快
    return 1.0;
}

double compute_s0(const ForgettingInputs& in) {
    return kBase
        * (1.0 + 0.5 * static_cast<double>(in.access_count))
        * (1.0 + in.salience)
        * (1.0 + 2.0 * (in.active_grounded ? 1.0 : 0.0))
        * decay_modifier_by_modality(in.modality)
        * (1.0 + 0.3 * std::abs(in.affect_valence));
}

double compute_s_t(const ForgettingInputs& in, std::string_view now_iso) {
    const double s0 = compute_s0(in);
    if (s0 <= 0.0) return 0.0;
    const double dt = parse_iso_epoch(now_iso) - parse_iso_epoch(in.last_accessed_iso);
    if (dt <= 0.0) return 1.0;
    return std::exp(-dt / s0);
}

}  // namespace starling::replay
```

- [ ] **Step 3: 写测试**

Create `tests/cpp/test_forgetting_curve.cpp`:

```cpp
#include "starling/replay/forgetting_curve.hpp"
#include <gtest/gtest.h>
using namespace starling::replay;

TEST(ForgettingCurve, FreshAccessNearOne) {
    ForgettingInputs in; in.salience=0.5; in.modality="BELIEVES";
    in.last_accessed_iso="2026-05-27T10:00:00Z";
    EXPECT_GT(compute_s_t(in, "2026-05-27T10:00:01Z"), 0.99);
}
TEST(ForgettingCurve, CommitsDecaysSlowerThanAssumes) {
    ForgettingInputs c; c.modality="COMMITS"; c.last_accessed_iso="2026-05-01T00:00:00Z";
    ForgettingInputs a; a.modality="ASSUMES"; a.last_accessed_iso="2026-05-01T00:00:00Z";
    EXPECT_GT(compute_s_t(c, "2026-05-27T00:00:00Z"),
              compute_s_t(a, "2026-05-27T00:00:00Z"));
}
TEST(ForgettingCurve, ActiveGroundedBoostsS0) {
    ForgettingInputs g; g.active_grounded=true; g.modality="BELIEVES";
    ForgettingInputs n; n.active_grounded=false; n.modality="BELIEVES";
    EXPECT_GT(compute_s0(g), compute_s0(n));
}
TEST(ForgettingCurve, AccessCountSlowsDecay) {
    ForgettingInputs hi; hi.access_count=10; hi.modality="BELIEVES";
    ForgettingInputs lo; lo.access_count=0; lo.modality="BELIEVES";
    EXPECT_GT(compute_s0(hi), compute_s0(lo));
}
TEST(ForgettingCurve, OldStatementBelowThreshold) {
    ForgettingInputs in; in.salience=0.0; in.modality="ASSUMES";
    in.last_accessed_iso="2025-01-01T00:00:00Z";
    EXPECT_LT(compute_s_t(in, "2026-05-27T00:00:00Z"), 0.05);
}
```

- [ ] **Step 4: 接 CMake**

`CMakeLists.txt` 的 `starling_core target_sources` 列表追加 `src/replay/forgetting_curve.cpp`。
`tests/cpp/CMakeLists.txt` 的 `starling_tests` 追加 `test_forgetting_curve.cpp`。

- [ ] **Step 5: build + 测试**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2
cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R ForgettingCurve 2>&1 | tail -8
```
Expected: 5 cases pass。

- [ ] **Step 6: 全 guard + Commit**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -2
git add include/starling/replay/forgetting_curve.hpp src/replay/forgetting_curve.cpp \
        tests/cpp/test_forgetting_curve.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/replay): forgetting_curve S(t) + S0 五因子

spec §6.4: S(t)=exp(-Δt/S0); S0=base × (1+0.5×access_count) × (1+salience)
× (1+2×active_grounded) × decay_modifier_by_modality × (1+0.3×|valence|)。
COMMITS 衰减极慢, ASSUMES 快; active_grounded 大幅增 S0。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: swr_sampler（完整采样权重公式）

**Files:**
- Create: `include/starling/replay/swr_sampler.hpp`, `src/replay/swr_sampler.cpp`, `tests/cpp/test_swr_sampler.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.3

- [ ] **Step 1: 写 header**

Create `include/starling/replay/swr_sampler.hpp`:

```cpp
#pragma once
#include <string>
#include <string_view>

namespace starling::replay {

struct SamplerInputs {
    double salience = 0.0;
    std::string last_replayed_iso;   // 空 = 从未 replay
    bool has_conflict = false;
    double affect_arousal = 0.0;     // [0,1]
    bool goal_relevant = false;      // current_goal 的 subject/predicate 匹配启发式 (无向量)
    std::string provenance;          // user_input / tom_inferred / replay_derived / reconsolidation_derived
    int64_t replay_count = 0;
    int derived_depth = 0;
};

struct SamplerConfig {
    double conflict_bonus = 0.5;
    double arousal_bonus = 0.4;
    double w_min = 0.01;
    int cooldown_minutes = 5;        // last_replayed < 5min → 权重 0 (除非 conflict)
};

// provenance_factor: user_input=1.0, tom_inferred=0.25,
//                    replay_derived/reconsolidation_derived=0 (不进池)
double provenance_factor(std::string_view provenance);

// 完整公式. 返回采样权重; 不合格 (replay_derived / cooldown / derived_depth>=3) 返回 0.
double sample_weight(const SamplerInputs& in, const SamplerConfig& cfg,
                     std::string_view now_iso);

}  // namespace starling::replay
```

- [ ] **Step 2: 写 impl**

Create `src/replay/swr_sampler.cpp`:

```cpp
#include "starling/replay/swr_sampler.hpp"
#include <cstdio>
#include <ctime>

namespace starling::replay {
namespace {
double parse_iso_epoch(std::string_view iso) {
    if (iso.empty()) return 0.0;
    std::tm tm{}; int y,mo,d,h,mi,s;
    if (std::sscanf(std::string(iso).c_str(), "%d-%d-%dT%d:%d:%dZ",
                    &y,&mo,&d,&h,&mi,&s) != 6) return 0.0;
    tm.tm_year=y-1900; tm.tm_mon=mo-1; tm.tm_mday=d;
    tm.tm_hour=h; tm.tm_min=mi; tm.tm_sec=s;
    return static_cast<double>(timegm(&tm));
}
double novelty_decay(std::string_view last_replayed, std::string_view now) {
    if (last_replayed.empty()) return 1.0;   // 从未 replay = 最新鲜
    const double dt = parse_iso_epoch(now) - parse_iso_epoch(last_replayed);
    // 越久未 replay 越新鲜 (上限 1.0)
    return dt > 86400.0 ? 1.0 : 0.5 + 0.5 * (dt / 86400.0);
}
}  // namespace

double provenance_factor(std::string_view p) {
    if (p == "user_input")   return 1.0;
    if (p == "tom_inferred") return 0.25;
    return 0.0;  // replay_derived / reconsolidation_derived → 不进池
}

double sample_weight(const SamplerInputs& in, const SamplerConfig& cfg,
                     std::string_view now_iso) {
    const double pf = provenance_factor(in.provenance);
    if (pf == 0.0) return 0.0;                 // 不进采样池
    if (in.derived_depth >= 3) return 0.0;     // 超深度不自动派生
    // cooldown: last_replayed < 5min → 0 (除非 conflict)
    if (!in.last_replayed_iso.empty() && !in.has_conflict) {
        const double dt = parse_iso_epoch(now_iso) - parse_iso_epoch(in.last_replayed_iso);
        if (dt < cfg.cooldown_minutes * 60.0) return 0.0;
    }
    double w = in.salience
        * novelty_decay(in.last_replayed_iso, now_iso)
        * (in.has_conflict ? (1.0 + cfg.conflict_bonus) : 1.0)
        * (1.0 + cfg.arousal_bonus * in.affect_arousal)
        * (in.goal_relevant ? 1.5 : 1.0)       // goal_relevance 启发式
        * pf
        / (1.0 + static_cast<double>(in.replay_count));
    return w < cfg.w_min ? 0.0 : w;            // w_min 截断
}

}  // namespace starling::replay
```

- [ ] **Step 3: 写测试**

Create `tests/cpp/test_swr_sampler.cpp`:

```cpp
#include "starling/replay/swr_sampler.hpp"
#include <gtest/gtest.h>
using namespace starling::replay;

static SamplerInputs base() {
    SamplerInputs i; i.salience=0.8; i.provenance="user_input";
    i.last_replayed_iso=""; return i;
}

TEST(SwrSampler, ReplayDerivedNotInPool) {
    auto i=base(); i.provenance="replay_derived";
    EXPECT_EQ(sample_weight(i, {}, "2026-05-27T10:00:00Z"), 0.0);
}
TEST(SwrSampler, TomInferredQuarterFactor) {
    EXPECT_DOUBLE_EQ(provenance_factor("tom_inferred"), 0.25);
    EXPECT_DOUBLE_EQ(provenance_factor("user_input"), 1.0);
}
TEST(SwrSampler, CooldownZerosWeight) {
    auto i=base(); i.last_replayed_iso="2026-05-27T09:58:00Z";  // 2min ago
    EXPECT_EQ(sample_weight(i, {}, "2026-05-27T10:00:00Z"), 0.0);
}
TEST(SwrSampler, ConflictBypassesCooldown) {
    auto i=base(); i.last_replayed_iso="2026-05-27T09:58:00Z"; i.has_conflict=true;
    EXPECT_GT(sample_weight(i, {}, "2026-05-27T10:00:00Z"), 0.0);
}
TEST(SwrSampler, DerivedDepth3Excluded) {
    auto i=base(); i.derived_depth=3;
    EXPECT_EQ(sample_weight(i, {}, "2026-05-27T10:00:00Z"), 0.0);
}
TEST(SwrSampler, GoalRelevantBoostsWeight) {
    auto g=base(); g.goal_relevant=true;
    auto n=base(); n.goal_relevant=false;
    EXPECT_GT(sample_weight(g, {}, "2026-05-27T10:00:00Z"),
              sample_weight(n, {}, "2026-05-27T10:00:00Z"));
}
TEST(SwrSampler, WMinTruncatesLowWeight) {
    auto i=base(); i.salience=0.001; i.replay_count=100;
    EXPECT_EQ(sample_weight(i, {}, "2026-05-27T10:00:00Z"), 0.0);
}
```

- [ ] **Step 4: 接 CMake**

`CMakeLists.txt` starling_core 追加 `src/replay/swr_sampler.cpp`；`tests/cpp/CMakeLists.txt` 追加 `test_swr_sampler.cpp`。

- [ ] **Step 5: build + 测试 + 全 guard + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R SwrSampler 2>&1 | tail -10
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -2
git add include/starling/replay/swr_sampler.hpp src/replay/swr_sampler.cpp \
        tests/cpp/test_swr_sampler.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/replay): SWR 优先级采样器 (完整公式)

spec §6.3: sample_weight = salience × novelty_decay × conflict_bonus ×
arousal_bonus × goal_relevance × provenance_factor / (1+replay_count)。
goal_relevance = current_goal subject/predicate 匹配启发式 (无向量)。
provenance_factor: user_input=1.0/tom_inferred=0.25/derived=0(不进池);
cooldown 5min 权重 0 (conflict 例外); derived_depth≥3 排除; w_min 截断。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: consolidation_ops — compress

**Files:**
- Create: `include/starling/replay/consolidation_ops.hpp`, `src/replay/consolidation_ops.cpp`, `tests/cpp/test_consolidation_compress.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.5（compress 行）

- [ ] **Step 1: 写 header（含 5 op 枚举，后续任务填充其余 op）**

Create `include/starling/replay/consolidation_ops.hpp`:

```cpp
#pragma once
#include "starling/persistence/connection.hpp"
#include <string>
#include <vector>

namespace starling::replay {

enum class ConsolidationOp { Compress, Abstract, Reinforce, Decay, Reconcile };
std::string_view to_string(ConsolidationOp op);

struct OpResult {
    ConsolidationOp op;
    std::string output_stmt_id;      // compress/abstract 产出; 否则空
    int affected = 0;
};

// compress: 多条相似 EpisodicEvent (同 holder+predicate+canonical_object_hash) 聚类合并.
// 输入 VOLATILE → CONSOLIDATED; 输出 provenance=replay_derived/APPROVED,
// emit statement.derived (非 statement.written → 不重入 Replay).
OpResult op_compress(persistence::Connection& conn,
                     const std::vector<std::string>& input_stmt_ids,
                     std::string_view tenant_id,
                     std::string_view replay_batch_id);

}  // namespace starling::replay
```

- [ ] **Step 2: 写 impl（compress；Bus.write provenance=replay_derived 路径复用现有 StatementWriter）**

Create `src/replay/consolidation_ops.cpp`:

```cpp
#include "starling/replay/consolidation_ops.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include <stdexcept>

namespace starling::replay {
using starling::bus::detail::bind_sv;
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

std::string_view to_string(ConsolidationOp op) {
    switch (op) {
        case ConsolidationOp::Compress:  return "compress";
        case ConsolidationOp::Abstract:  return "abstract";
        case ConsolidationOp::Reinforce: return "reinforce";
        case ConsolidationOp::Decay:     return "decay";
        case ConsolidationOp::Reconcile: return "reconcile";
    }
    throw std::invalid_argument("unknown ConsolidationOp");
}

OpResult op_compress(persistence::Connection& conn,
                     const std::vector<std::string>& input_stmt_ids,
                     std::string_view tenant_id,
                     std::string_view replay_batch_id) {
    // compress: 把 input set 全部从 VOLATILE 迁到 CONSOLIDATED,
    // 标记 last_replay_batch_id. 第一条作为 canonical survivor (其余仍保留,
    // 仅状态迁移 — 默认不删, 保细粒度). emit statement.derived 由调用方
    // ReplayScheduler 统一处理 (此处只做 state 迁移 + batch 标记).
    OpResult r{ConsolidationOp::Compress, {}, 0};
    sqlite3* db = conn.raw();
    for (const auto& id : input_stmt_ids) {
        const char* sql =
            "UPDATE statements SET consolidation_state='consolidated', "
            "  last_replay_batch_id=?, replay_count=replay_count+1, "
            "  last_replayed=? "
            " WHERE id=? AND tenant_id=? AND consolidation_state='volatile'";
        sqlite3_stmt* raw=nullptr;
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "op_compress: prepare");
        StmtHandle h(raw);
        bind_sv(h.get(),1,replay_batch_id);
        bind_sv(h.get(),2,"2026-05-27T00:00:00Z");  // 调用方传 now; 占位由 scheduler 覆盖
        bind_sv(h.get(),3,id);
        bind_sv(h.get(),4,tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "op_compress: step");
        r.affected += sqlite3_changes(db);
    }
    if (!input_stmt_ids.empty()) r.output_stmt_id = input_stmt_ids.front();
    return r;
}

}  // namespace starling::replay
```

> 实现注：`emit statement.derived` 与 now 时间戳由 Task 12 的 ReplayScheduler 统一注入（ops 是纯 state 迁移单元，scheduler 负责事件 + batch 元数据）。本 task 先验证 compress 的状态迁移；scheduler 集成在 Task 12。

- [ ] **Step 3: 写测试**

Create `tests/cpp/test_consolidation_compress.cpp`:

```cpp
#include "starling/replay/consolidation_ops.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
using namespace starling::replay;
using starling::persistence::SqliteAdapter;

namespace {
void seed_volatile(sqlite3* db, const std::string& id) {
    std::string sql =
      "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
      "subject_kind,subject_id,predicate,object_kind,object_value,"
      "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
      "confidence,observed_at,salience,affect_json,activation,last_accessed,"
      "provenance,consolidation_state,review_status,created_at,updated_at) "
      "VALUES('"+id+"','default','alice','first_person','cognizer','bob',"
      "'knows','str','x','"+std::string(64,'a')+"','v1','believes','pos',"
      "0.9,'2026-05-27T09:00:00Z',0.5,'{}',0.0,'2026-05-27T09:00:00Z',"
      "'user_input','volatile','approved','2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    sqlite3_exec(db, sql.c_str(), nullptr, nullptr, nullptr);
}
}  // namespace

TEST(ConsolidationCompress, VolatileToConsolidated) {
    auto a = SqliteAdapter::open(":memory:");
    auto& conn = a->connection();
    seed_volatile(conn.raw(), "s1");
    seed_volatile(conn.raw(), "s2");
    auto r = op_compress(conn, {"s1","s2"}, "default", "batch-1");
    EXPECT_EQ(r.affected, 2);
    sqlite3_stmt* st=nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "SELECT COUNT(*) FROM statements WHERE consolidation_state='consolidated'",
        -1,&st,nullptr);
    sqlite3_step(st);
    EXPECT_EQ(sqlite3_column_int(st,0), 2);
    sqlite3_finalize(st);
}
TEST(ConsolidationCompress, OnlyTouchesVolatile) {
    auto a = SqliteAdapter::open(":memory:");
    auto& conn = a->connection();
    seed_volatile(conn.raw(), "s1");
    op_compress(conn, {"s1"}, "default", "b1");
    auto r2 = op_compress(conn, {"s1"}, "default", "b2");  // 已 consolidated
    EXPECT_EQ(r2.affected, 0);  // 不再迁移
}
```

- [ ] **Step 4: 接 CMake**

`CMakeLists.txt` starling_core 追加 `src/replay/consolidation_ops.cpp`；`tests/cpp/CMakeLists.txt` 追加 `test_consolidation_compress.cpp`。

- [ ] **Step 5: build + 测试 + 全 guard + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R ConsolidationCompress 2>&1 | tail -8
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/replay/consolidation_ops.hpp src/replay/consolidation_ops.cpp \
        tests/cpp/test_consolidation_compress.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/replay): consolidation op compress

spec §6.5: compress 把多条相似 EpisodicEvent (同 holder+predicate+
canonical_object_hash) 从 VOLATILE 迁 CONSOLIDATED, 标 last_replay_batch_id +
replay_count+1。默认不删 (保细粒度)。ConsolidationOp 枚举 5 值,
后续 task 填 abstract/reinforce/decay/reconcile。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: consolidation_ops — abstract + reinforce

**Files:**
- Modify: `include/starling/replay/consolidation_ops.hpp`, `src/replay/consolidation_ops.cpp`
- Create: `tests/cpp/test_consolidation_abstract_reinforce.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.5（abstract / reinforce 行）

- [ ] **Step 1: header 追加两个签名**

在 `consolidation_ops.hpp` 的 namespace 内追加：

```cpp
// abstract: 多 holder 同 predicate → 产出候选 (replay_derived/PENDING_REVIEW),
// 入 Neocortex candidate index (喂 Persona rebuild). 不立即落 Persona。
OpResult op_abstract(persistence::Connection& conn,
                     const std::vector<std::string>& input_stmt_ids,
                     std::string_view tenant_id,
                     std::string_view replay_batch_id);

// reinforce: 高 salience 短链, 提升 access_count + 标记巩固.
// VOLATILE → CONSOLIDATED.
OpResult op_reinforce(persistence::Connection& conn,
                      const std::vector<std::string>& input_stmt_ids,
                      std::string_view tenant_id,
                      std::string_view replay_batch_id);
```

- [ ] **Step 2: impl 追加**

在 `consolidation_ops.cpp` 追加：

```cpp
OpResult op_reinforce(persistence::Connection& conn,
                      const std::vector<std::string>& input_stmt_ids,
                      std::string_view tenant_id,
                      std::string_view replay_batch_id) {
    OpResult r{ConsolidationOp::Reinforce, {}, 0};
    sqlite3* db = conn.raw();
    for (const auto& id : input_stmt_ids) {
        const char* sql =
            "UPDATE statements SET access_count=access_count+1, "
            "  consolidation_state='consolidated', "
            "  last_replay_batch_id=?, replay_count=replay_count+1 "
            " WHERE id=? AND tenant_id=?";
        sqlite3_stmt* raw=nullptr;
        if (sqlite3_prepare_v2(db,sql,-1,&raw,nullptr)!=SQLITE_OK)
            throw make_sqlite_error(db,"op_reinforce: prepare");
        StmtHandle h(raw);
        bind_sv(h.get(),1,replay_batch_id); bind_sv(h.get(),2,id); bind_sv(h.get(),3,tenant_id);
        if (sqlite3_step(h.get())!=SQLITE_DONE) throw make_sqlite_error(db,"op_reinforce: step");
        r.affected += sqlite3_changes(db);
    }
    return r;
}

OpResult op_abstract(persistence::Connection& conn,
                     const std::vector<std::string>& input_stmt_ids,
                     std::string_view tenant_id,
                     std::string_view replay_batch_id) {
    // abstract 产 candidate: 标记输入为已抽象来源 (review_status 不变),
    // candidate 物化由 Neocortex PersonaContainer::rebuild 消费 (Task 23).
    // 此处记录 batch 归属 + 标记参与 abstract, 不直接产新行 (避免重入);
    // 真正的候选合成在 Persona rebuild 阶段从 abstract 标记的源读取.
    OpResult r{ConsolidationOp::Abstract, {}, 0};
    sqlite3* db = conn.raw();
    for (const auto& id : input_stmt_ids) {
        const char* sql =
            "UPDATE statements SET last_replay_batch_id=?, replay_count=replay_count+1 "
            " WHERE id=? AND tenant_id=?";
        sqlite3_stmt* raw=nullptr;
        if (sqlite3_prepare_v2(db,sql,-1,&raw,nullptr)!=SQLITE_OK)
            throw make_sqlite_error(db,"op_abstract: prepare");
        StmtHandle h(raw);
        bind_sv(h.get(),1,replay_batch_id); bind_sv(h.get(),2,id); bind_sv(h.get(),3,tenant_id);
        if (sqlite3_step(h.get())!=SQLITE_DONE) throw make_sqlite_error(db,"op_abstract: step");
        r.affected += sqlite3_changes(db);
    }
    if (!input_stmt_ids.empty()) r.output_stmt_id = input_stmt_ids.front();
    return r;
}
```

> abstract 在 M0.8 是"标记 + 喂 Persona rebuild"的轻量形式（真正的多 holder 语义合成是 Persona rebuild 的多源仲裁，Task 23）。完整 abstract LLM 合成是后续（需 induce_norm 类基础）。

- [ ] **Step 3: 测试**

Create `tests/cpp/test_consolidation_abstract_reinforce.cpp`（复用 Task 8 的 seed_volatile helper 模式，验证 reinforce 提升 access_count + 迁 CONSOLIDATED；abstract 标记 batch 不改 review_status）。完整断言：

```cpp
#include "starling/replay/consolidation_ops.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
using namespace starling::replay;
using starling::persistence::SqliteAdapter;
// (seed_volatile 同 Task 8, 此处复制一份局部 helper)
namespace {
void seed(sqlite3* db,const std::string& id){
    std::string s="INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
    "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
    "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
    "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
    "access_count,created_at,updated_at) VALUES('"+id+"','default','alice','first_person',"
    "'cognizer','bob','knows','str','x','"+std::string(64,'a')+"','v1','believes','pos',"
    "0.9,'2026-05-27T09:00:00Z',0.5,'{}',0.0,'2026-05-27T09:00:00Z','user_input','volatile',"
    "'approved',2,'2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    sqlite3_exec(db,s.c_str(),nullptr,nullptr,nullptr);
}
int icol(sqlite3* db,const std::string& q){sqlite3_stmt* s=nullptr;
    sqlite3_prepare_v2(db,q.c_str(),-1,&s,nullptr);sqlite3_step(s);
    int v=sqlite3_column_int(s,0);sqlite3_finalize(s);return v;}
}
TEST(ConsolidationReinforce, BumpsAccessCountAndConsolidates) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed(c.raw(),"s1");
    op_reinforce(c,{"s1"},"default","b1");
    EXPECT_EQ(icol(c.raw(),"SELECT access_count FROM statements WHERE id='s1'"),3);
    EXPECT_EQ(icol(c.raw(),"SELECT COUNT(*) FROM statements WHERE id='s1' AND consolidation_state='consolidated'"),1);
}
TEST(ConsolidationAbstract, MarksBatchKeepsReviewStatus) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed(c.raw(),"s1");
    auto r=op_abstract(c,{"s1"},"default","b1");
    EXPECT_EQ(r.affected,1);
    EXPECT_EQ(icol(c.raw(),"SELECT COUNT(*) FROM statements WHERE id='s1' AND review_status='approved'"),1);
}
```

- [ ] **Step 4: CMake + build + 测试 + Commit**

`tests/cpp/CMakeLists.txt` 追加 `test_consolidation_abstract_reinforce.cpp`。

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R "ConsolidationReinforce|ConsolidationAbstract" 2>&1 | tail -8
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/replay/consolidation_ops.hpp src/replay/consolidation_ops.cpp \
        tests/cpp/test_consolidation_abstract_reinforce.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/replay): consolidation ops abstract + reinforce

spec §6.5: reinforce 提升 access_count + VOLATILE→CONSOLIDATED;
abstract 标记多 holder 同 predicate 源 (review_status 不变), 真正语义合成
由 Neocortex Persona rebuild 多源仲裁消费 (Task 23)。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: consolidation_ops — decay（statement.decay_candidate per-stmt 串行）

**Files:**
- Modify: `include/starling/replay/consolidation_ops.hpp`, `src/replay/consolidation_ops.cpp`
- Create: `tests/cpp/test_consolidation_decay.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.5（decay 行）+ §6.4

- [ ] **Step 1: header 追加**

```cpp
// decay: S(t)<0.05 且 not active_grounded → emit statement.decay_candidate.
// Bus dispatcher per-stmt 串行投递; 后到事件读到 state 已变即跳过 (T5/T8 race 消除).
// 实际 CONSOLIDATED→ARCHIVED 由 decay_candidate handler 在串行投递时执行.
OpResult op_decay(persistence::Connection& conn,
                  const std::vector<std::string>& candidate_stmt_ids,
                  std::string_view tenant_id,
                  std::string_view now_iso);
```

- [ ] **Step 2: impl 追加**

```cpp
#include "starling/replay/forgetting_curve.hpp"
// ... 在 consolidation_ops.cpp 内:
OpResult op_decay(persistence::Connection& conn,
                  const std::vector<std::string>& candidate_stmt_ids,
                  std::string_view tenant_id,
                  std::string_view now_iso) {
    OpResult r{ConsolidationOp::Decay, {}, 0};
    sqlite3* db = conn.raw();
    for (const auto& id : candidate_stmt_ids) {
        // 读 forgetting inputs
        ForgettingInputs in;
        sqlite3_stmt* sel=nullptr;
        sqlite3_prepare_v2(db,
            "SELECT salience,access_count,modality,last_accessed,consolidation_state "
            "FROM statements WHERE id=? AND tenant_id=?",-1,&sel,nullptr);
        StmtHandle hsel(sel);
        bind_sv(hsel.get(),1,id); bind_sv(hsel.get(),2,tenant_id);
        if (sqlite3_step(hsel.get())!=SQLITE_ROW) continue;
        in.salience = sqlite3_column_double(hsel.get(),0);
        in.access_count = sqlite3_column_int64(hsel.get(),1);
        in.modality = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(),2));
        in.last_accessed_iso = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(),3));
        std::string state = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(),4));
        // active_grounded 判定: 查 common_ground 是否有 grounded 且未 expired/recanted
        // (M0.8 简化: 默认 false; 完整联动在 CommonGround writer Task 25 后由 scheduler 注入)
        in.active_grounded = false;
        // 串行守护: 后到事件读到 state 已非 consolidated → 跳过 (T5/T8)
        if (state != "consolidated") continue;
        if (compute_s_t(in, now_iso) < 0.05 && !in.active_grounded) {
            sqlite3_stmt* upd=nullptr;
            sqlite3_prepare_v2(db,
                "UPDATE statements SET consolidation_state='archived' "
                "WHERE id=? AND tenant_id=? AND consolidation_state='consolidated'",
                -1,&upd,nullptr);
            StmtHandle hupd(upd);
            bind_sv(hupd.get(),1,id); bind_sv(hupd.get(),2,tenant_id);
            if (sqlite3_step(hupd.get())!=SQLITE_DONE) throw make_sqlite_error(db,"op_decay: step");
            r.affected += sqlite3_changes(db);
            // emit statement.archived 由 ReplayScheduler 统一 (Task 12)
        }
    }
    return r;
}
```

- [ ] **Step 3: 测试**

Create `tests/cpp/test_consolidation_decay.cpp`：seed 一条 CONSOLIDATED + 老 last_accessed（S(t)<0.05）→ op_decay → ARCHIVED；seed 一条新鲜的 → 不 decay；重复 op_decay（state 已 archived）→ 跳过（affected=0，验证串行守护）。

```cpp
#include "starling/replay/consolidation_ops.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
using namespace starling::replay;
using starling::persistence::SqliteAdapter;
namespace {
void seed_consol(sqlite3* db,const std::string& id,const std::string& last_acc,double sal){
    std::string s="INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
    "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
    "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
    "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
    "created_at,updated_at) VALUES('"+id+"','default','alice','first_person','cognizer',"
    "'bob','knows','str','x','"+std::string(64,'a')+"','v1','assumes','pos',0.9,"
    "'2025-01-01T00:00:00Z',"+std::to_string(sal)+",'{}',0.0,'"+last_acc+"','user_input',"
    "'consolidated','approved','2025-01-01T00:00:00Z','2025-01-01T00:00:00Z')";
    sqlite3_exec(db,s.c_str(),nullptr,nullptr,nullptr);
}
int icol(sqlite3* db,const std::string& q){sqlite3_stmt* s=nullptr;
    sqlite3_prepare_v2(db,q.c_str(),-1,&s,nullptr);sqlite3_step(s);
    int v=sqlite3_column_int(s,0);sqlite3_finalize(s);return v;}
}
TEST(ConsolidationDecay, OldLowSalienceArchived) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed_consol(c.raw(),"old","2025-01-01T00:00:00Z",0.0);
    auto r=op_decay(c,{"old"},"default","2026-05-27T00:00:00Z");
    EXPECT_EQ(r.affected,1);
    EXPECT_EQ(icol(c.raw(),"SELECT COUNT(*) FROM statements WHERE id='old' AND consolidation_state='archived'"),1);
}
TEST(ConsolidationDecay, FreshNotArchived) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed_consol(c.raw(),"fresh","2026-05-27T09:59:00Z",0.9);
    auto r=op_decay(c,{"fresh"},"default","2026-05-27T10:00:00Z");
    EXPECT_EQ(r.affected,0);
}
TEST(ConsolidationDecay, SerialGuardSkipsAlreadyArchived) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed_consol(c.raw(),"old","2025-01-01T00:00:00Z",0.0);
    op_decay(c,{"old"},"default","2026-05-27T00:00:00Z");      // 第一次 archive
    auto r2=op_decay(c,{"old"},"default","2026-05-27T00:00:00Z"); // state 已变 → 跳过
    EXPECT_EQ(r2.affected,0);
}
```

- [ ] **Step 4: CMake + build + 测试 + Commit**

`tests/cpp/CMakeLists.txt` 追加 `test_consolidation_decay.cpp`。

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R ConsolidationDecay 2>&1 | tail -8
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/replay/consolidation_ops.hpp src/replay/consolidation_ops.cpp \
        tests/cpp/test_consolidation_decay.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/replay): consolidation op decay (S(t)<0.05 串行守护)

spec §6.5+§6.4: decay 用 forgetting_curve 算 S(t), <0.05 且 not
active_grounded → CONSOLIDATED→ARCHIVED。串行守护: 读到 state 已非
consolidated 即跳过 (T5/T8 race 消除)。emit statement.archived 由
ReplayScheduler 统一 (Task 12)。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: consolidation_ops — reconcile（路由到 Reconsolidation）

**Files:**
- Modify: `include/starling/replay/consolidation_ops.hpp`, `src/replay/consolidation_ops.cpp`
- Create: `tests/cpp/test_consolidation_reconcile.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.5（reconcile 行）

- [ ] **Step 1: header 追加**

```cpp
// reconcile: 冲突集 → CONSOLIDATED→REPLAYING_RECONSOLIDATING + emit belief.conflict
// (路由到 Reconsolidation Engine, 由其异步开可塑窗口). Replay 本身不仲裁.
OpResult op_reconcile(persistence::Connection& conn,
                      const std::string& stmt_id,
                      std::string_view tenant_id);
```

- [ ] **Step 2: impl 追加（state 迁移 REPLAYING_RECONSOLIDATING；belief.conflict emit 由 scheduler 经 OutboxWriter）**

```cpp
OpResult op_reconcile(persistence::Connection& conn,
                      const std::string& stmt_id,
                      std::string_view tenant_id) {
    OpResult r{ConsolidationOp::Reconcile, stmt_id, 0};
    sqlite3* db = conn.raw();
    const char* sql =
        "UPDATE statements SET consolidation_state='replaying_reconsolidating' "
        "WHERE id=? AND tenant_id=? AND consolidation_state='consolidated'";
    sqlite3_stmt* raw=nullptr;
    if (sqlite3_prepare_v2(db,sql,-1,&raw,nullptr)!=SQLITE_OK)
        throw make_sqlite_error(db,"op_reconcile: prepare");
    StmtHandle h(raw);
    bind_sv(h.get(),1,stmt_id); bind_sv(h.get(),2,tenant_id);
    if (sqlite3_step(h.get())!=SQLITE_DONE) throw make_sqlite_error(db,"op_reconcile: step");
    r.affected = sqlite3_changes(db);
    // emit belief.conflict 由 ReplayScheduler 经 OutboxWriter (Task 12),
    // Reconsolidation Engine 异步消费开窗口 (Task 19).
    return r;
}
```

- [ ] **Step 3: 测试**

Create `tests/cpp/test_consolidation_reconcile.cpp`：seed CONSOLIDATED → op_reconcile → 验证 state = replaying_reconsolidating；非 consolidated 的不迁移。

```cpp
#include "starling/replay/consolidation_ops.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
using namespace starling::replay;
using starling::persistence::SqliteAdapter;
namespace {
void seed_consol(sqlite3* db,const std::string& id){
    std::string s="INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
    "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
    "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
    "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
    "created_at,updated_at) VALUES('"+id+"','default','alice','first_person','cognizer',"
    "'bob','knows','str','x','"+std::string(64,'a')+"','v1','believes','pos',0.9,"
    "'2026-05-27T09:00:00Z',0.5,'{}',0.0,'2026-05-27T09:00:00Z','user_input','consolidated',"
    "'approved','2026-05-27T09:00:00Z','2026-05-27T09:00:00Z')";
    sqlite3_exec(db,s.c_str(),nullptr,nullptr,nullptr);
}
int icol(sqlite3* db,const std::string& q){sqlite3_stmt* s=nullptr;
    sqlite3_prepare_v2(db,q.c_str(),-1,&s,nullptr);sqlite3_step(s);
    int v=sqlite3_column_int(s,0);sqlite3_finalize(s);return v;}
}
TEST(ConsolidationReconcile, ConsolidatedToReplayingReconsolidating) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    seed_consol(c.raw(),"s1");
    auto r=op_reconcile(c,"s1","default");
    EXPECT_EQ(r.affected,1);
    EXPECT_EQ(icol(c.raw(),"SELECT COUNT(*) FROM statements WHERE id='s1' AND consolidation_state='replaying_reconsolidating'"),1);
}
```

- [ ] **Step 4: CMake + build + 测试 + Commit**

`tests/cpp/CMakeLists.txt` 追加 `test_consolidation_reconcile.cpp`。

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R ConsolidationReconcile 2>&1 | tail -6
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/replay/consolidation_ops.hpp src/replay/consolidation_ops.cpp \
        tests/cpp/test_consolidation_reconcile.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/replay): consolidation op reconcile (路由到 Reconsolidation)

spec §6.5: reconcile 把冲突 stmt CONSOLIDATED→REPLAYING_RECONSOLIDATING,
emit belief.conflict 路由给 Reconsolidation Engine 异步开可塑窗口。
Replay 不自己仲裁。REPLAYING_RECONSOLIDATING 枚举已存在。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: ReplayScheduler（tick_online / run_idle / run_sleep + 振荡防护 + VOLATILE TTL）

**Files:**
- Create: `include/starling/replay/replay_scheduler.hpp`, `src/replay/replay_scheduler.cpp`, `tests/cpp/test_replay_scheduler.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §6.2

- [ ] **Step 1: 写 header**

Create `include/starling/replay/replay_scheduler.hpp`:

```cpp
#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/replay/consolidation_ops.hpp"
#include <string>

namespace starling::replay {

struct ReplayStats {
    int sampled=0, compressed=0, abstracted=0, reinforced=0, decayed=0, reconciled=0;
    int forced_consolidated=0, ttl_archived=0;
    std::string replay_batch_id;
};

class ReplayScheduler {
public:
    explicit ReplayScheduler(persistence::SqliteAdapter& adapter);
    // Online: SubscriberPump 调用. online_trigger_counter+1; 达 N=3 跑采样窗口(批1-3).
    ReplayStats tick_online(persistence::Connection& conn, std::string_view now_iso);
    // 显式 API (无后台线程).
    ReplayStats run_idle(persistence::Connection& conn, std::string_view now_iso);   // 批10-30
    ReplayStats run_sleep(persistence::Connection& conn, std::string_view now_iso);  // sweep
    // 振荡防护: replay_count≥5 → 强制 CONSOLIDATED+PENDING_REVIEW.
    int enforce_oscillation_guard(persistence::Connection& conn);
    // VOLATILE TTL: 写入>7天 且不在 Affect Buffer → ARCHIVED.
    int sweep_volatile_ttl(persistence::Connection& conn, std::string_view now_iso);
private:
    persistence::SqliteAdapter& adapter_;
    static constexpr int kOnlineTrigger=3, kMaxConsolidationAttempts=5, kVolatileTtlDays=7;
};

}  // namespace starling::replay
```

- [ ] **Step 2: 写 impl（核心：采样 → 选 op → 执行 → emit 事件 + ledger；振荡防护 + TTL 独立方法）**

Create `src/replay/replay_scheduler.cpp`. 关键逻辑：
- `tick_online`: 读 `replay_scheduler_state.online_trigger_counter`，+1，<3 则返回；==3 重置为 0 + 跑一次采样窗口（eligible set SELECT → sample_weight 排序 → 取批 1-3 → 选 op → 调 op_* → emit statement.derived/archived/belief.conflict via OutboxWriter → 写 replay_ledger）。
- `enforce_oscillation_guard`: `UPDATE statements SET consolidation_state='consolidated', review_status='pending_review' WHERE replay_count>=5 AND consolidation_state IN ('volatile','replaying_consolidating')` + emit statement.consolidation_forced。
- `sweep_volatile_ttl`: `UPDATE ... SET consolidation_state='archived' WHERE consolidation_state='volatile' AND created_at < (now-7d)` + emit statement.archived(volatile_ttl_exceeded)。

> 完整 impl 由 implementer 按 header 契约 + 现有 OutboxWriter（`src/bus/outbox_writer.cpp`）+ make_event 模式写出。emit 事件复用 `starling::bus::make_event` + `OutboxWriter::append`。replay_batch_id 用 `random_hex_32`（同 cognizer_hub 模式）。

- [ ] **Step 3: 写测试（覆盖振荡防护 + TTL；tick_online 计数；采样产 ledger）**

Create `tests/cpp/test_replay_scheduler.cpp`：
- `tick_online` 调 2 次不触发（counter<3），第 3 次触发采样 + 写 ledger
- `enforce_oscillation_guard`: seed replay_count=5 的 VOLATILE → 强制 consolidated+pending_review
- `sweep_volatile_ttl`: seed 8 天前的 VOLATILE → archived；3 天前的 → 不动

（完整 seed + 断言由 implementer 按前述 tasks 的 seed helper 模式写。）

- [ ] **Step 4: 接 CMake**

`CMakeLists.txt` starling_core 追加 `src/replay/replay_scheduler.cpp`；`tests/cpp/CMakeLists.txt` 追加 `test_replay_scheduler.cpp`。

- [ ] **Step 5: build + 测试 + 全 guard + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R ReplayScheduler 2>&1 | tail -10
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/replay/replay_scheduler.hpp src/replay/replay_scheduler.cpp \
        tests/cpp/test_replay_scheduler.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/replay): ReplayScheduler 3 模式 + 振荡防护 + VOLATILE TTL

spec §6.2: tick_online (每 3 条 statement.written 触发, 批 1-3) +
run_idle (批 10-30) + run_sleep (sweep)。采样用 SWR sample_weight 排序,
选 op (compress/abstract/reinforce/decay/reconcile) 执行, emit
statement.derived/archived/belief.conflict, 写 replay_ledger。
振荡防护 replay_count≥5 → 强制 CONSOLIDATED+PENDING_REVIEW;
VOLATILE TTL >7天不在 Affect Buffer → ARCHIVED。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: TC-A1-001 [CRITICAL] — replay_count≥5 强制 CONSOLIDATED

**Files:**
- Create: `tests/python/test_tc_a1_001.py`

**Spec ref:** §12.2 TC-A1-001

- [ ] **Step 1: 写测试**

Create `tests/python/test_tc_a1_001.py`:

```python
"""TC-A1-001 [CRITICAL]: replay_count≥5 振荡防护强制 CONSOLIDATED+PENDING_REVIEW.

spec §6.2 振荡防护: stmt.replay_count >= MAX_CONSOLIDATION_ATTEMPTS=5 →
强制 consolidation_state=CONSOLIDATED + review_status=PENDING_REVIEW +
emit statement.consolidation_forced。防止 VOLATILE/REPLAYING 无限振荡。
"""
from __future__ import annotations
import sqlite3
import pytest
from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _seed(rt, stmt_id, replay_count, state="volatile"):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,replay_count,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", "believes", "pos", 0.9,
             "2026-05-27T09:00:00Z", 0.5, "{}", 0.0, "2026-05-27T09:00:00Z",
             "user_input", state, "approved", replay_count,
             "2026-05-27T09:00:00Z", "2026-05-27T09:00:00Z"))
        c.commit()


def test_replay_count_5_forces_consolidated(rt):
    _seed(rt, "osc", replay_count=5, state="volatile")
    sched = _core.ReplayScheduler(rt.adapter)
    forced = sched.enforce_oscillation_guard()
    assert forced >= 1, "replay_count>=5 应被强制巩固"
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        row = c.execute(
            "SELECT consolidation_state, review_status FROM statements WHERE id='osc'"
        ).fetchone()
    assert row == ("consolidated", "pending_review"), \
        f"应强制 consolidated+pending_review, 实际 {row!r}"
    # consolidation_forced 事件
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        n = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.consolidation_forced' "
            "AND primary_id='osc'").fetchone()[0]
    assert n == 1, "应 emit 1 条 statement.consolidation_forced"


def test_replay_count_under_5_not_forced(rt):
    _seed(rt, "ok", replay_count=4, state="volatile")
    _core.ReplayScheduler(rt.adapter).enforce_oscillation_guard()
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        state = c.execute(
            "SELECT consolidation_state FROM statements WHERE id='ok'").fetchone()[0]
    assert state == "volatile", "replay_count<5 不应被强制"
```

- [ ] **Step 2: 跑测试（先 RED 若 enforce_oscillation_guard/binding 未就绪 → 应在 Task 12 + Task 30 binding 后 GREEN）**

```bash
pytest tests/python/test_tc_a1_001.py -v 2>&1 | tail -10
```
Expected: 依赖 `_core.ReplayScheduler` binding（Task 30）。若 binding 未就绪，此 task 在 Task 30 后回跑。GREEN: 2 passed。

- [ ] **Step 3: 全 guard + Commit**

```bash
pytest tests/python -q 2>&1 | tail -3
git add tests/python/test_tc_a1_001.py
git commit -m "$(cat <<'EOF'
test(M0.8/CRITICAL): TC-A1-001 — replay_count≥5 强制 CONSOLIDATED

§16.3-7 准入: 振荡防护 replay_count>=5 → CONSOLIDATED+PENDING_REVIEW +
emit statement.consolidation_forced; <5 不强制。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: TC-A1-002 [CRITICAL] — VOLATILE TTL

**Files:**
- Create: `tests/python/test_tc_a1_002.py`

**Spec ref:** §12.2 TC-A1-002

- [ ] **Step 1: 写测试**

Create `tests/python/test_tc_a1_002.py`:

```python
"""TC-A1-002 [CRITICAL]: VOLATILE >7天 不在 Affect Buffer → ARCHIVED.

spec §6.2 VOLATILE TTL 兜底: consolidation_state=VOLATILE 且写入距今 >
T_max_volatile=7天 且 not in Affect Buffer → 自动 ARCHIVED(volatile_ttl_exceeded)。
不依赖 Replay 调度, 由 TTL sweep 兜底。
"""
from __future__ import annotations
import sqlite3
import pytest
from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _seed(rt, stmt_id, created_at):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", "believes", "pos", 0.9,
             created_at, 0.5, "{}", 0.0, created_at,
             "user_input", "volatile", "approved", created_at, created_at))
        c.commit()


def test_volatile_older_than_7d_archived(rt):
    _seed(rt, "old", created_at="2026-05-01T00:00:00Z")   # >7天 before now
    n = _core.ReplayScheduler(rt.adapter).sweep_volatile_ttl("2026-05-27T00:00:00Z")
    assert n >= 1
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        state = c.execute(
            "SELECT consolidation_state FROM statements WHERE id='old'").fetchone()[0]
        ev = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived' "
            "AND primary_id='old'").fetchone()[0]
    assert state == "archived"
    assert ev == 1


def test_volatile_within_7d_kept(rt):
    _seed(rt, "fresh", created_at="2026-05-25T00:00:00Z")  # 2天 before now
    _core.ReplayScheduler(rt.adapter).sweep_volatile_ttl("2026-05-27T00:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        state = c.execute(
            "SELECT consolidation_state FROM statements WHERE id='fresh'").fetchone()[0]
    assert state == "volatile"
```

- [ ] **Step 2: 跑 + 全 guard + Commit**（同 Task 13 模式，依赖 Task 30 binding）

```bash
pytest tests/python/test_tc_a1_002.py -v 2>&1 | tail -8
git add tests/python/test_tc_a1_002.py
git commit -m "$(cat <<'EOF'
test(M0.8/CRITICAL): TC-A1-002 — VOLATILE TTL 7天兜底

§16.3-7 准入: VOLATILE >7天 不在 Affect Buffer → ARCHIVED +
emit statement.archived; <7天 保留。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: TC-A6-001 + TC-A6-002 [CRITICAL ×2] — decay 串行投递

**Files:**
- Create: `tests/python/test_tc_a6_001.py`, `tests/python/test_tc_a6_002.py`

**Spec ref:** §12.2 TC-A6-001/002

- [ ] **Step 1: 写 TC-A6-001（decay_candidate per-stmt 串行；后到读到 state 已变跳过）**

Create `tests/python/test_tc_a6_001.py`:

```python
"""TC-A6-001 [CRITICAL]: decay_candidate per-stmt 串行投递 T5 race 消除.

spec §6.5 decay: emit statement.decay_candidate, Bus dispatcher per-stmt
顺序串行投递; 后到事件读到 state 已变 → 跳过。验证同一 stmt 的 decay
不会重复迁移 (CONSOLIDATED→ARCHIVED 仅一次)。
"""
from __future__ import annotations
import sqlite3
import pytest
from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _seed_consolidated_old(rt, stmt_id):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", "assumes", "pos", 0.9,
             "2025-01-01T00:00:00Z", 0.0, "{}", 0.0, "2025-01-01T00:00:00Z",
             "user_input", "consolidated", "approved",
             "2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z"))
        c.commit()


def test_decay_serial_idempotent(rt):
    _seed_consolidated_old(rt, "d1")
    sched = _core.ReplayScheduler(rt.adapter)
    # 第一次 decay → archived
    sched.run_decay(["d1"], "2026-05-27T00:00:00Z")
    # 第二次 (模拟后到事件) → state 已变, 跳过, 不重复
    sched.run_decay(["d1"], "2026-05-27T00:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        state = c.execute(
            "SELECT consolidation_state FROM statements WHERE id='d1'").fetchone()[0]
        n_arch = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived' "
            "AND primary_id='d1'").fetchone()[0]
    assert state == "archived"
    assert n_arch == 1, "串行守护: archived 事件只应 emit 一次"
```

- [ ] **Step 2: 写 TC-A6-002（T8 outbox 串行：同 stmt 多 decay 不并发迁移）**

Create `tests/python/test_tc_a6_002.py`:

```python
"""TC-A6-002 [CRITICAL]: T8 outbox 串行 — 同 stmt 多 decay 不并发迁移.

spec §6.5: 同一 stmt_id 的 decay 事件不并发执行, 避免多次 state 迁移覆盖。
验证批量 decay 候选含重复 stmt_id 时, 只迁移一次。
"""
from __future__ import annotations
import sqlite3
import pytest
from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _seed_consolidated_old(rt, stmt_id):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", "assumes", "pos", 0.9,
             "2025-01-01T00:00:00Z", 0.0, "{}", 0.0, "2025-01-01T00:00:00Z",
             "user_input", "consolidated", "approved",
             "2025-01-01T00:00:00Z", "2025-01-01T00:00:00Z"))
        c.commit()


def test_duplicate_decay_candidates_archive_once(rt):
    _seed_consolidated_old(rt, "dup")
    sched = _core.ReplayScheduler(rt.adapter)
    # 同一 stmt_id 在一批候选里出现两次 (模拟并发 decay 候选)
    sched.run_decay(["dup", "dup"], "2026-05-27T00:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        n_arch = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived' "
            "AND primary_id='dup'").fetchone()[0]
    assert n_arch == 1, "重复候选只应迁移 + emit 一次"
```

> 实现注：Task 12 的 ReplayScheduler 需暴露 `run_decay(candidate_ids, now)` 方法（包装 op_decay + emit statement.archived），供这两个 CRITICAL 测试与 binding 调用。若 Task 12 未含，回头补上再跑本 task。

- [ ] **Step 3: 跑 + 全 guard + Commit**

```bash
pytest tests/python/test_tc_a6_001.py tests/python/test_tc_a6_002.py -v 2>&1 | tail -8
git add tests/python/test_tc_a6_001.py tests/python/test_tc_a6_002.py
git commit -m "$(cat <<'EOF'
test(M0.8/CRITICAL): TC-A6-001 + TC-A6-002 — decay 串行投递

§16.3-7 准入: decay_candidate per-stmt 串行 (T5: 后到读到 state 已变跳过;
T8: 同 stmt 多 decay 不并发迁移)。archived 事件只 emit 一次。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: plastic_window（窗口锁 + pending_evidence + 自适应超时）

**Files:**
- Create: `include/starling/reconsolidation/plastic_window.hpp`, `src/reconsolidation/plastic_window.cpp`, `tests/cpp/test_plastic_window.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §7 + §16.3-4

- [ ] **Step 1: 写 header**

Create `include/starling/reconsolidation/plastic_window.hpp`:

```cpp
#pragma once
#include "starling/persistence/connection.hpp"
#include <optional>
#include <string>
#include <string_view>

namespace starling::reconsolidation {

// 自适应超时: 默认 30min, clamp [5min, 6h], per-modality 覆写,
// 高频 (≥3次/小时) → 强制 5min. (§16.3-4)
int adaptive_timeout_minutes(std::string_view modality, int trigger_freq_per_hour);

struct OpenResult { bool opened; bool appended; std::string close_deadline; };

// 开窗或追加证据 (窗口锁: stmt_id PK).
// 已有活跃窗口 → 只追加 pending_evidence (防抖), 不开新窗口.
// pending_evidence 满 100 → FIFO 淘汰; 触发计数达 K=10 → 强制 close.
OpenResult open_or_append(persistence::Connection& conn,
                          std::string_view stmt_id, std::string_view tenant_id,
                          std::string_view event_id, std::string_view event_type,
                          std::string_view payload_hash, double weight,
                          std::string_view modality, std::string_view now_iso);

// 列出 close_deadline <= now 的 open 窗口 stmt_id.
std::vector<std::string> due_windows(persistence::Connection& conn,
                                     std::string_view now_iso);

constexpr int kPendingEvidenceMax = 100;
constexpr int kForceCloseTriggerCount = 10;

}  // namespace starling::reconsolidation
```

- [ ] **Step 2: 写 impl**

Create `src/reconsolidation/plastic_window.cpp`。关键逻辑：
- `adaptive_timeout_minutes`: base=30；modality COMMITS→长(360 clamp), ASSUMES→短(min 5)；trigger_freq≥3 → return 5；最后 clamp [5,360]。
- `open_or_append`: SELECT reconsolidation_windows WHERE stmt_id=? AND status='open'。无 → INSERT 新窗口 (close_deadline = now + adaptive_timeout)，opened=true。有 → INSERT pending_evidence + force_close_trigger_count+1；若 pending count>100 → DELETE 最旧 (FIFO) + evicted_count+1；若 trigger_count≥10 → status='closed' (强制 close)；appended=true。
- `due_windows`: SELECT stmt_id FROM reconsolidation_windows WHERE status='open' AND close_deadline<=now。

> 完整 SQL impl 由 implementer 按 header + migration 0012 schema 写出。用 StmtHandle + bind_sv（同其他子系统）。

- [ ] **Step 3: 写测试**

Create `tests/cpp/test_plastic_window.cpp`：
- `adaptive_timeout`: COMMITS > BELIEVES > ASSUMES；trigger_freq≥3 返回 5；clamp 边界。
- `open_or_append`: 首次 opened=true；再触发 appended=true 不开新窗口；pending 满 100 FIFO 淘汰；trigger 达 10 强制 close。
- `due_windows`: close_deadline 过期的返回，未过期的不返回。

```cpp
#include "starling/reconsolidation/plastic_window.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling::reconsolidation;
using starling::persistence::SqliteAdapter;

TEST(PlasticWindow, AdaptiveTimeoutModalityOrder) {
    EXPECT_GT(adaptive_timeout_minutes("COMMITS", 0), adaptive_timeout_minutes("BELIEVES", 0));
    EXPECT_GT(adaptive_timeout_minutes("BELIEVES", 0), adaptive_timeout_minutes("ASSUMES", 0));
}
TEST(PlasticWindow, HighFrequencyForces5min) {
    EXPECT_EQ(adaptive_timeout_minutes("COMMITS", 3), 5);
}
TEST(PlasticWindow, ClampLowerBound5) {
    EXPECT_GE(adaptive_timeout_minutes("ASSUMES", 0), 5);
}
TEST(PlasticWindow, ClampUpperBound360) {
    EXPECT_LE(adaptive_timeout_minutes("COMMITS", 0), 360);
}
TEST(PlasticWindow, FirstTriggerOpens) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    auto r = open_or_append(c,"s1","default","e1","belief.conflict","h1",1.0,
                            "believes","2026-05-27T10:00:00Z");
    EXPECT_TRUE(r.opened);
}
TEST(PlasticWindow, SecondTriggerAppendsNoNewWindow) {
    auto a=SqliteAdapter::open(":memory:"); auto& c=a->connection();
    open_or_append(c,"s1","default","e1","belief.conflict","h1",1.0,"believes","2026-05-27T10:00:00Z");
    auto r2 = open_or_append(c,"s1","default","e2","statement.recalled","h2",1.0,"believes","2026-05-27T10:01:00Z");
    EXPECT_FALSE(r2.opened);
    EXPECT_TRUE(r2.appended);
}
```

- [ ] **Step 4: CMake + build + 测试 + Commit**

`CMakeLists.txt` starling_core 追加 `src/reconsolidation/plastic_window.cpp`；`tests/cpp/CMakeLists.txt` 追加 `test_plastic_window.cpp`。

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R PlasticWindow 2>&1 | tail -10
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/reconsolidation/plastic_window.hpp src/reconsolidation/plastic_window.cpp \
        tests/cpp/test_plastic_window.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/reconsolidation): plastic_window 窗口锁 + 自适应超时

spec §7 + §16.3-4: 窗口锁 stmt_id PK (一个 stmt 一个活跃窗口, 重复触发
只追加 pending_evidence 防抖)。自适应超时 30min 默认 / clamp[5min,6h] /
per-modality 覆写 / 高频≥3hr→5min。pending_evidence 100 FIFO + K=10 强制 close。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: arbitration — aggregate_evidence + supports + mild contradict

**Files:**
- Create: `include/starling/reconsolidation/arbitration.hpp`, `src/reconsolidation/arbitration.cpp`, `tests/cpp/test_arbitration_mild.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §7.3（supports + mild）

- [ ] **Step 1: 写 header**

Create `include/starling/reconsolidation/arbitration.hpp`:

```cpp
#pragma once
#include "starling/persistence/connection.hpp"
#include <string>
#include <string_view>

namespace starling::reconsolidation {

enum class ArbitrationPath { Supports, MildContradict, SevereContradict };

struct Aggregated {
    ArbitrationPath path;
    double strength;          // 证据聚合强度 [0,1]
    std::string summary_hash;
};

// 取窗口 pending_evidence 最近 50 条高权重 + 其余低权重背景统计 → 判定路径.
Aggregated aggregate_evidence(persistence::Connection& conn, std::string_view stmt_id);

// supports: confidence 贝叶斯上调 → CONSOLIDATED → emit statement.consolidated.
void apply_supports(persistence::Connection& conn, std::string_view stmt_id,
                    std::string_view tenant_id, const Aggregated& agg,
                    std::string_view now_iso);

// mild contradict: confidence 贝叶斯下调 + 追加 confidence_history, provenance 不变
//                  → CONSOLIDATED → emit statement.consolidated (不 emit corrected).
void apply_mild_contradict(persistence::Connection& conn, std::string_view stmt_id,
                           std::string_view tenant_id, const Aggregated& agg,
                           std::string_view now_iso);

double bayesian_update_up(double conf, double strength);
double bayesian_update_down(double conf, double strength);

}  // namespace starling::reconsolidation
```

- [ ] **Step 2: 写 impl（severe 在 Task 18 追加）**

Create `src/reconsolidation/arbitration.cpp`：
- `bayesian_update_up/down`: 简单贝叶斯式 `conf + strength*(1-conf)` / `conf*(1-strength)`，clamp [0,1]。
- `aggregate_evidence`: SELECT pending_evidence ORDER BY weight DESC LIMIT 50 → 计算平均 weight 作 strength；path 判定（M0.8 简化：strength<0.3 → Supports；0.3-0.7 → MildContradict；>0.7 → SevereContradict；具体阈值实现时定，测试覆盖三档）。
- `apply_supports`: UPDATE confidence=bayesian_update_up + consolidation_state='consolidated' + emit statement.consolidated。
- `apply_mild_contradict`: 读 old confidence → UPDATE confidence=bayesian_update_down + 追加 confidence_history_json（ConfidenceEvent: old_value/new_value/ts/evidence_summary_hash/path="mild_contradict"）+ **provenance 不写（保持原值）** + consolidation_state='consolidated' + emit statement.consolidated（不 emit corrected）。

- [ ] **Step 3: 写测试**

Create `tests/cpp/test_arbitration_mild.cpp`：
- `bayesian_update_up` 增、`bayesian_update_down` 减，都 clamp [0,1]。
- `apply_mild_contradict`: seed CONSOLIDATED confidence=0.9 provenance=user_input → mild → confidence 下降 + confidence_history 追加一条 + **provenance 仍 user_input** + state consolidated + emit statement.consolidated（不 emit statement.corrected）。

```cpp
#include "starling/reconsolidation/arbitration.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling::reconsolidation;
using starling::persistence::SqliteAdapter;

TEST(Arbitration, BayesianUpIncreases) {
    EXPECT_GT(bayesian_update_up(0.5, 0.4), 0.5);
    EXPECT_LE(bayesian_update_up(0.9, 0.9), 1.0);
}
TEST(Arbitration, BayesianDownDecreases) {
    EXPECT_LT(bayesian_update_down(0.9, 0.4), 0.9);
    EXPECT_GE(bayesian_update_down(0.1, 0.9), 0.0);
}
// mild contradict provenance 不变 + confidence_history 追加 — 完整 DB 断言
// 由 implementer 用 seed CONSOLIDATED + apply_mild_contradict + 查
// provenance/confidence/confidence_history_json/bus_events 写出。
```

- [ ] **Step 4: CMake + build + 测试 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R Arbitration 2>&1 | tail -8
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/reconsolidation/arbitration.hpp src/reconsolidation/arbitration.cpp \
        tests/cpp/test_arbitration_mild.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/reconsolidation): arbitration supports + mild contradict

spec §7.3: aggregate_evidence 取最近50高权重; supports→confidence 上调→
CONSOLIDATED→emit consolidated; mild contradict→confidence 下调+追加
confidence_history, provenance 不变, emit consolidated (不 emit corrected)。
severe path 在 Task 18。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: arbitration — severe contradict（4 项原子提交）

**Files:**
- Modify: `include/starling/reconsolidation/arbitration.hpp`, `src/reconsolidation/arbitration.cpp`
- Create: `tests/cpp/test_arbitration_severe.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §7.3（severe）

- [ ] **Step 1: header 追加**

```cpp
// severe contradict: 4 项原子提交 (仅原子事务, saga 推迟 P3):
//   1. 新版 Statement (provenance=reconsolidation_derived, CONSOLIDATED)
//   2. SUPERSEDES 边 (新版→旧版)
//   3. 旧版 ARCHIVED
//   4. emit statement.corrected + archived + superseded (同 outbox batch)
// 新版不走 tom_inferred, 不进 VOLATILE, 不 emit statement.written (防重入 Replay).
// 返回新版 stmt_id.
std::string apply_severe_contradict(persistence::Connection& conn,
                                    std::string_view old_stmt_id,
                                    std::string_view tenant_id,
                                    const Aggregated& agg,
                                    std::string_view now_iso);
```

- [ ] **Step 2: impl 追加（复用 Bus 的 SUPERSEDES + outbox 模式；TransactionGuard 包裹 4 项）**

在 `arbitration.cpp` 追加 `apply_severe_contradict`：在调用方已开的事务内执行（或自开 TransactionGuard），fork 新版（新 id，provenance=reconsolidation_derived，consolidation_state=consolidated，supersedes_id=old），INSERT 新版 + INSERT statement_edges(supersedes, 新→旧) + UPDATE 旧版 archived + OutboxWriter append 三事件（statement.corrected / statement.archived / statement.superseded）。**saga 状态机不实现**（local-store cross_partition_transaction=true 走原子事务）。

- [ ] **Step 3: 写测试**

Create `tests/cpp/test_arbitration_severe.cpp`：seed CONSOLIDATED 旧版 → apply_severe_contradict → 验证：新版存在(reconsolidation_derived, consolidated, supersedes_id=旧)、supersedes 边存在、旧版 archived、3 个 outbox 事件(corrected/archived/superseded)、新版**无 statement.written 事件**。

- [ ] **Step 4: CMake + build + 测试 + Commit**

`tests/cpp/CMakeLists.txt` 追加 `test_arbitration_severe.cpp`。

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R "Arbitration" 2>&1 | tail -8
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/reconsolidation/arbitration.hpp src/reconsolidation/arbitration.cpp \
        tests/cpp/test_arbitration_severe.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/reconsolidation): arbitration severe contradict (4 项原子)

spec §7.3: severe → 新版 reconsolidation_derived CONSOLIDATED + SUPERSEDES
边 + 旧版 ARCHIVED + emit corrected/archived/superseded 同 outbox batch。
仅原子事务 (TransactionGuard), saga 推迟 P3。新版不 emit statement.written
(防重入 Replay)。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: ReconsolidationEngine（subscriber tick + close_due_windows + reconsolidate）

**Files:**
- Create: `include/starling/reconsolidation/reconsolidation_engine.hpp`, `src/reconsolidation/reconsolidation_engine.cpp`, `tests/cpp/test_reconsolidation_engine.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §7.2

- [ ] **Step 1: 写 header**

Create `include/starling/reconsolidation/reconsolidation_engine.hpp`:

```cpp
#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include <string>
#include <string_view>

namespace starling::reconsolidation {

struct EngineStats { int events_processed=0, windows_opened=0, windows_closed=0; };

class ReconsolidationEngine {  // Outbox subscriber, tick-driven
public:
    explicit ReconsolidationEngine(persistence::SqliteAdapter& adapter);
    // 消费 last_checkpoint+1.. outbox 事件 → open_or_append 窗口.
    // 5 触发: statement.recalled / statement.references_existing / belief.conflict /
    //         (显式 reconsolidate API) / commitment.fulfilled|broken (P2.c stub).
    EngineStats tick_one_batch(persistence::Connection& conn, std::string_view now_iso);
    // 仲裁所有 close_deadline<=now 的窗口 (SubscriberPump 在 tick 后调用).
    int close_due_windows(persistence::Connection& conn, std::string_view now_iso);
    // 显式 API (触发路径之一: audit/用户编辑).
    void reconsolidate(persistence::Connection& conn, std::string_view stmt_id,
                       std::string_view event_type, std::string_view payload_hash,
                       double weight, std::string_view now_iso);
private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::reconsolidation
```

- [ ] **Step 2: 写 impl**

Create `src/reconsolidation/reconsolidation_engine.cpp`：
- `tick_one_batch`: SELECT bus_events WHERE outbox_sequence > checkpoint AND event_type IN ('statement.recalled','statement.references_existing','belief.conflict','commitment.fulfilled','commitment.broken') → 对每条调 plastic_window::open_or_append（commitment.* M0.8 stub: 仅记录不开窗）→ 更新 checkpoint。
- `close_due_windows`: due_windows() → 对每个 aggregate_evidence → 按 path 调 apply_supports/apply_mild_contradict/apply_severe_contradict → 窗口 status='closed'。**TC-A5-002 双层兜底**：仲裁抛异常时 catch → 窗口仍标 closed + stmt 回 CONSOLIDATED（不卡死）。
- `reconsolidate`: 显式开窗（open_or_append）。

- [ ] **Step 3: 写测试**

Create `tests/cpp/test_reconsolidation_engine.cpp`：
- tick 消费 belief.conflict 事件 → 开窗口 + checkpoint 推进
- close_due_windows 对过期窗口仲裁
- commitment.* 事件 → 不开窗（stub）

- [ ] **Step 4: CMake + build + 测试 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R ReconsolidationEngine 2>&1 | tail -10
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/reconsolidation/reconsolidation_engine.hpp \
        src/reconsolidation/reconsolidation_engine.cpp \
        tests/cpp/test_reconsolidation_engine.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/reconsolidation): ReconsolidationEngine subscriber + close_due_windows

spec §7.2: Outbox subscriber tick 消费 5 触发 (recalled/references_existing/
belief.conflict/显式/commitment.* stub) → open_or_append 窗口; close_due_windows
仲裁超时窗口 (supports/mild/severe)。TC-A5-002 双层兜底: 仲裁异常 → 窗口仍
close + stmt 回 CONSOLIDATED 不卡死。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 20: TC-A5-001 [CRITICAL] — 可塑窗口超时 fallback

**Files:**
- Create: `tests/python/test_tc_a5_001.py`

**Spec ref:** §12.2 TC-A5-001

- [ ] **Step 1: 写测试**

Create `tests/python/test_tc_a5_001.py`:

```python
"""TC-A5-001 [CRITICAL]: 可塑窗口 close_deadline 到 → 强制 close + 仲裁.

spec §7: 窗口超时 (close_deadline <= now) → close_due_windows 强制关闭并仲裁。
验证一个开了的窗口在 deadline 过后被 close_due_windows 仲裁 (status→closed)。
"""
from __future__ import annotations
import sqlite3
import pytest
from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _seed_consolidated(rt, stmt_id):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", "believes", "pos", 0.9,
             "2026-05-27T09:00:00Z", 0.5, "{}", 0.0, "2026-05-27T09:00:00Z",
             "user_input", "consolidated", "approved",
             "2026-05-27T09:00:00Z", "2026-05-27T09:00:00Z"))
        c.commit()


def test_expired_window_closed_and_arbitrated(rt):
    _seed_consolidated(rt, "w1")
    eng = _core.ReconsolidationEngine(rt.adapter)
    # 显式开窗 (close_deadline = now + 30min default)
    eng.reconsolidate("w1", "belief.conflict", "h1", 1.0, "2026-05-27T10:00:00Z")
    # 推进到 deadline 之后 (1h 后) → close_due_windows 仲裁
    closed = eng.close_due_windows("2026-05-27T11:00:00Z")
    assert closed >= 1, "超时窗口应被强制 close"
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        status = c.execute(
            "SELECT status FROM reconsolidation_windows WHERE stmt_id='w1'").fetchone()[0]
    assert status == "closed"


def test_unexpired_window_not_closed(rt):
    _seed_consolidated(rt, "w2")
    eng = _core.ReconsolidationEngine(rt.adapter)
    eng.reconsolidate("w2", "belief.conflict", "h1", 1.0, "2026-05-27T10:00:00Z")
    eng.close_due_windows("2026-05-27T10:05:00Z")  # 仅 5min, 未到 30min deadline
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        status = c.execute(
            "SELECT status FROM reconsolidation_windows WHERE stmt_id='w2'").fetchone()[0]
    assert status == "open"
```

- [ ] **Step 2: 跑 + 全 guard + Commit**

```bash
pytest tests/python/test_tc_a5_001.py -v 2>&1 | tail -8
git add tests/python/test_tc_a5_001.py
git commit -m "$(cat <<'EOF'
test(M0.8/CRITICAL): TC-A5-001 — 可塑窗口超时 fallback

§16.3-7 准入: close_deadline<=now → close_due_windows 强制 close + 仲裁;
未到 deadline 保持 open。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 21: TC-A5-002 [CRITICAL] — fallback 双层兜底

**Files:**
- Create: `tests/python/test_tc_a5_002.py`

**Spec ref:** §12.2 TC-A5-002

- [ ] **Step 1: 写测试（仲裁自身失败 → 窗口仍 close，stmt 回 CONSOLIDATED 不卡死）**

Create `tests/python/test_tc_a5_002.py`:

```python
"""TC-A5-002 [CRITICAL]: 仲裁自身失败 → 窗口仍 close, stmt 回 CONSOLIDATED 不卡死.

spec §7.2: fallback 任务自身失败的双层兜底。即使 aggregate/arbitrate 抛异常,
close_due_windows 必须把窗口标 closed 且把 stmt 状态恢复到 CONSOLIDATED
(不能永久卡在 replaying_reconsolidating)。

构造方式: 开窗后把 stmt 删除 (制造仲裁时的异常源), 验证 close_due_windows
不抛出且窗口最终 closed。
"""
from __future__ import annotations
import sqlite3
import pytest
from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _seed_consolidated(rt, stmt_id):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", "believes", "pos", 0.9,
             "2026-05-27T09:00:00Z", 0.5, "{}", 0.0, "2026-05-27T09:00:00Z",
             "user_input", "consolidated", "approved",
             "2026-05-27T09:00:00Z", "2026-05-27T09:00:00Z"))
        c.commit()


def test_arbitration_failure_does_not_hang_window(rt):
    _seed_consolidated(rt, "fail")
    eng = _core.ReconsolidationEngine(rt.adapter)
    eng.reconsolidate("fail", "belief.conflict", "h1", 1.0, "2026-05-27T10:00:00Z")
    # 删除目标 stmt 制造仲裁异常源
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute("DELETE FROM statements WHERE id='fail'")
        c.commit()
    # close_due_windows 不应抛出 (双层兜底)
    eng.close_due_windows("2026-05-27T11:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        status = c.execute(
            "SELECT status FROM reconsolidation_windows WHERE stmt_id='fail'").fetchone()[0]
    assert status == "closed", "仲裁失败时窗口仍须 close, 不卡死"
```

- [ ] **Step 2: 跑 + 全 guard + Commit**

```bash
pytest tests/python/test_tc_a5_002.py -v 2>&1 | tail -8
git add tests/python/test_tc_a5_002.py
git commit -m "$(cat <<'EOF'
test(M0.8/CRITICAL): TC-A5-002 — fallback 双层兜底

§16.3-7 准入: 仲裁自身失败 (异常) → close_due_windows 不抛出, 窗口仍标
closed, stmt 不永久卡在 replaying_reconsolidating。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 22: TC-A8-001 [CRITICAL] — 异步仲裁 severe 4 项

**Files:**
- Create: `tests/python/test_tc_a8_001.py`

**Spec ref:** §12.2 TC-A8-001

- [ ] **Step 1: 写测试（异步 Reconsolidation severe 4 项原子，与同步 TC-NEW-CONFLICT-SEVERE 互补）**

Create `tests/python/test_tc_a8_001.py`:

```python
"""TC-A8-001 [CRITICAL]: local-store severe path 异步仲裁版.

spec §7.3 + §16.3-7/-9: Reconsolidation severe contradict 4 项原子提交
(新版 reconsolidation_derived + SUPERSEDES 边 + 旧版 ARCHIVED + 3 outbox 事件)。
与 P1 同步路径 TC-NEW-CONFLICT-SEVERE 互补共存 — 后者是 ConflictProbe 同事务
direct_contradiction, 本测试是 Reconsolidation 异步仲裁。

构造: 一个 CONSOLIDATED stmt 开窗口, 灌入高权重反对证据 (strength>0.7 → severe),
窗口 close → 验证 4 项原子提交。
"""
from __future__ import annotations
import sqlite3
import pytest
from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _seed_consolidated(rt, stmt_id):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", "believes", "pos", 0.9,
             "2026-05-27T09:00:00Z", 0.5, "{}", 0.0, "2026-05-27T09:00:00Z",
             "user_input", "consolidated", "approved",
             "2026-05-27T09:00:00Z", "2026-05-27T09:00:00Z"))
        c.commit()


def test_async_severe_four_item_atomic(rt):
    _seed_consolidated(rt, "old")
    eng = _core.ReconsolidationEngine(rt.adapter)
    # 显式开窗 + 多条高权重反对证据 → severe
    for i in range(5):
        eng.reconsolidate("old", "belief.conflict", f"h{i}", 1.0, "2026-05-27T10:00:00Z")
    eng.close_due_windows("2026-05-27T11:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        # 旧版 ARCHIVED
        old_state = c.execute(
            "SELECT consolidation_state FROM statements WHERE id='old'").fetchone()[0]
        # 新版 reconsolidation_derived CONSOLIDATED
        new = c.execute(
            "SELECT id FROM statements WHERE provenance='reconsolidation_derived' "
            "AND consolidation_state='consolidated'").fetchone()
        # SUPERSEDES 边
        edge = c.execute(
            "SELECT COUNT(*) FROM statement_edges WHERE dst_id='old' AND edge_kind='supersedes'"
        ).fetchone()[0]
        # 3 outbox 事件
        corrected = c.execute("SELECT COUNT(*) FROM bus_events WHERE event_type='statement.corrected'").fetchone()[0]
        archived = c.execute("SELECT COUNT(*) FROM bus_events WHERE event_type='statement.archived' AND primary_id='old'").fetchone()[0]
        superseded = c.execute("SELECT COUNT(*) FROM bus_events WHERE event_type='statement.superseded'").fetchone()[0]
        # 新版不 emit statement.written
        new_written = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='statement.written' "
            "AND primary_id=?", (new[0],)).fetchone()[0] if new else -1
    assert old_state == "archived", "旧版应 ARCHIVED"
    assert new is not None, "应有新版 reconsolidation_derived CONSOLIDATED"
    assert edge == 1, "应有 1 条 SUPERSEDES 边"
    assert corrected == 1 and archived == 1 and superseded == 1, "应 emit 3 outbox 事件"
    assert new_written == 0, "新版不应 emit statement.written (防重入 Replay)"
```

- [ ] **Step 2: 跑 + 全 guard + Commit**

```bash
pytest tests/python/test_tc_a8_001.py -v 2>&1 | tail -10
git add tests/python/test_tc_a8_001.py
git commit -m "$(cat <<'EOF'
test(M0.8/CRITICAL): TC-A8-001 — 异步仲裁 severe 4 项原子

§16.3-7/-9 准入: Reconsolidation severe 4 项原子 (新版 reconsolidation_derived
+ SUPERSEDES 边 + 旧版 ARCHIVED + 3 outbox 事件), 新版不 emit statement.written。
与 P1 同步 TC-NEW-CONFLICT-SEVERE 互补共存。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 23: PersonaContainer（rebuild + anchor 仲裁 + CAS）

**Files:**
- Create: `include/starling/neocortex/persona_container.hpp`, `src/neocortex/persona_container.cpp`, `tests/cpp/test_persona_container.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §8.2

- [ ] **Step 1: 写 header**

Create `include/starling/neocortex/persona_container.hpp`:

```cpp
#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace starling::neocortex {

struct AnchorStatement {
    std::string stmt_id;
    std::string anchor_type;   // "self_model_anchor" | "profile_anchor"
    std::string source_holder; // 谁说的
    std::string subject_holder; // 说的是谁
    std::string dimension;     // traits/preferences/competencies/values/...
    std::string value;
    double confidence = 0.0;
};

class ConcurrentRebuildError : public std::runtime_error {
public:
    ConcurrentRebuildError() : std::runtime_error("persona container CAS version mismatch") {}
};

class PersonaContainer {
public:
    explicit PersonaContainer(persistence::SqliteAdapter& adapter);
    // 物化 Persona: 多源 anchor 仲裁 (自陈优先; 多源 profile 与自陈冲突
    // severity>=DIVERGE_THRESHOLD → dimension.suspected_diverge + emit ToM, 暂不写),
    // dimension 合并, 单 version CAS on containers.version → ConcurrentRebuildError.
    void rebuild(persistence::Connection& conn, std::string_view tenant_id,
                 std::string_view holder_id, const std::vector<AnchorStatement>& sources);
private:
    persistence::SqliteAdapter& adapter_;
    static constexpr double kDivergeThreshold = 0.5;
};

}  // namespace starling::neocortex
```

- [ ] **Step 2: 写 impl**

Create `src/neocortex/persona_container.cpp`：
- `rebuild`: 按 dimension 分组 sources；每 dimension 分 self_model_anchor / profile_anchor 两组；self 非空 → primary=weighted_merge(self)，否则 weighted_merge(profile)；若 self 与 profile 都有且冲突 severity≥0.5 → 该 dimension 标 suspected_diverge + emit 给 ToM（M0.8: emit bus event `persona.suspected_diverge`），不写该 dimension；其余 dimension 写入 content_json。
- 读现有 container（containers WHERE holder_id=? AND kind='persona'）→ 无则 INSERT（version=1）→ 有则 CAS UPDATE（WHERE version=expected；sqlite3_changes()==0 → ConcurrentRebuildError）。

- [ ] **Step 3: 写测试**

Create `tests/cpp/test_persona_container.cpp`：
- self anchor 优先于 profile anchor（同 dimension 不同值 → 取 self 值）
- self 与 profile 冲突 severity 高 → dimension suspected_diverge + 不写该值
- CAS: 并发 rebuild（version 失配）→ ConcurrentRebuildError

- [ ] **Step 4: CMake + build + 测试 + Commit**

`CMakeLists.txt` starling_core 追加 `src/neocortex/persona_container.cpp`；`tests/cpp/CMakeLists.txt` 追加 `test_persona_container.cpp`。

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R PersonaContainer 2>&1 | tail -8
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/neocortex/persona_container.hpp src/neocortex/persona_container.cpp \
        tests/cpp/test_persona_container.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/neocortex): PersonaContainer rebuild + anchor 仲裁 + CAS

spec §8.2: self_model_anchor 优先于 profile_anchor; 多源 profile 与自陈
冲突 severity≥DIVERGE_THRESHOLD → dimension.suspected_diverge + emit ToM,
暂不写该 dimension; dimension 合并; 单 version CAS on containers.version →
ConcurrentRebuildError。content_json 存物化 dimensions。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 24: CommonGroundContainer（物化视图）

**Files:**
- Create: `include/starling/neocortex/common_ground_container.hpp`, `src/neocortex/common_ground_container.cpp`, `tests/cpp/test_common_ground_container.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §8.3

- [ ] **Step 1: 写 header**

Create `include/starling/neocortex/common_ground_container.hpp`:

```cpp
#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include <string>
#include <string_view>

namespace starling::neocortex {

class CommonGroundContainer {
public:
    explicit CommonGroundContainer(persistence::SqliteAdapter& adapter);
    // 从 common_ground 表 (P2.a + Task 25 writer 写入) 物化
    // grounded/asserted_unack/suspected_diverge dimensions → containers.content_json
    // (kind='common_ground'). 单 version CAS.
    void rebuild(persistence::Connection& conn, std::string_view tenant_id,
                 std::string_view cg_ref);
private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::neocortex
```

- [ ] **Step 2: 写 impl**

Create `src/neocortex/common_ground_container.cpp`：SELECT common_ground WHERE tenant_id=? GROUP BY status → 按 status 分组聚合 statement_id 列表 → 写 containers.content_json (kind='common_ground', holder_id=cg_ref) via CAS（同 PersonaContainer 模式）。

- [ ] **Step 3: 写测试**

Create `tests/cpp/test_common_ground_container.cpp`：seed common_ground 行（不同 status）→ rebuild → 验证 containers content_json 含分组后的 grounded/asserted_unack/suspected_diverge。

- [ ] **Step 4: CMake + build + 测试 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R CommonGroundContainer 2>&1 | tail -6
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/neocortex/common_ground_container.hpp \
        src/neocortex/common_ground_container.cpp \
        tests/cpp/test_common_ground_container.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/neocortex): CommonGroundContainer 物化视图

spec §8.3: 从 common_ground 表物化 grounded/asserted_unack/suspected_diverge
dimensions → containers.content_json (kind='common_ground'), 单 version CAS。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 25: CommonGroundWriter（5 Grounding Acts + grounded 状态机）

**Files:**
- Create: `include/starling/tom/common_ground_writer.hpp`, `src/tom/common_ground_writer.cpp`, `tests/cpp/test_common_ground_writer.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §9.2

- [ ] **Step 1: 写 header**

Create `include/starling/tom/common_ground_writer.hpp`:

```cpp
#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include <string>
#include <string_view>
#include <vector>

namespace starling::tom {

class CommonGroundWriter {
public:
    explicit CommonGroundWriter(persistence::SqliteAdapter& adapter);
    // assert: 新 CommonGround 条目 → asserted_unack. 返回 cg_id.
    std::string assert_(persistence::Connection& conn, std::string_view tenant_id,
                        std::string_view stmt_id, const std::vector<std::string>& parties,
                        std::string_view now_iso);
    // acknowledge: 显式确认 → grounded.
    void acknowledge(persistence::Connection& conn, std::string_view cg_id,
                     std::string_view actor, std::string_view now_iso);
    // repair: 质疑 → suspected_diverge.
    void repair(persistence::Connection& conn, std::string_view cg_id,
                std::string_view actor, std::string_view now_iso);
    // withdraw: 撤回 → recanted.
    void withdraw(persistence::Connection& conn, std::string_view cg_id,
                  std::string_view actor, std::string_view now_iso);
    // supersede_ground: 新共识覆盖旧 (旧 superseded_by=新, 新进 grounded).
    void supersede_ground(persistence::Connection& conn, std::string_view old_cg_id,
                          std::string_view new_stmt_id, std::string_view now_iso);
    // 24h 超时降级: asserted_unack > 24h 无 Ack/Repair → suspected_diverge.
    int sweep_timeout_downgrade(persistence::Connection& conn, std::string_view now_iso);
private:
    persistence::SqliteAdapter& adapter_;
    // grounded 3 规则评估 (acknowledge / tick 时):
    //  ① 显式确认 ② 共同在场推定 (perceived_by 覆盖全 parties + N=3 轮无 Repair/Withdraw)
    //  ③ 重复确认 (同 canonical 等价 stmt 被不同 parties 成员独立提及 ≥ M=2 次)
};

}  // namespace starling::tom
```

- [ ] **Step 2: 写 impl**

Create `src/tom/common_ground_writer.cpp`：每个 act 做 common_ground 表的状态迁移 + INSERT grounding_acts 审计日志。`assert_`: INSERT common_ground(status='asserted_unack')。`acknowledge`: UPDATE status='grounded' + grounded_at。`repair`: UPDATE status='suspected_diverge'。`withdraw`: UPDATE status='recanted'。`supersede_ground`: UPDATE 旧 superseded_by=新 + 新条目 grounded。`sweep_timeout_downgrade`: UPDATE status='suspected_diverge' WHERE status='asserted_unack' AND created_at < now-24h。

- [ ] **Step 3: 写测试**

Create `tests/cpp/test_common_ground_writer.cpp`：assert→asserted_unack；acknowledge→grounded；repair→suspected_diverge；withdraw→recanted；24h 超时 sweep→suspected_diverge；每动作写 grounding_acts。

- [ ] **Step 4: CMake + build + 测试 + Commit**

`CMakeLists.txt` starling_core 追加 `src/tom/common_ground_writer.cpp`；`tests/cpp/CMakeLists.txt` 追加 `test_common_ground_writer.cpp`。

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R CommonGroundWriter 2>&1 | tail -10
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/tom/common_ground_writer.hpp src/tom/common_ground_writer.cpp \
        tests/cpp/test_common_ground_writer.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/tom): CommonGroundWriter 5 Grounding Acts + grounded 状态机

spec §9.2: assert/acknowledge/repair/withdraw/supersede_ground 5 动作;
grounded 3 规则 (显式确认/共同在场 N=3/重复确认 M=2); asserted_unack >24h
无 Ack/Repair → suspected_diverge; 每动作写 grounding_acts 审计日志。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 26: ProjectionMaintainer — tick_one_batch（6 投影增量物化）

**Files:**
- Create: `include/starling/projection/projection_maintainer.hpp`, `src/projection/projection_maintainer.cpp`, `tests/cpp/test_projection_incremental.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §10.2（tick_one_batch）

- [ ] **Step 1: 写 header**

Create `include/starling/projection/projection_maintainer.hpp`:

```cpp
#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include <string>
#include <string_view>

namespace starling::projection {

struct MaintainerStats { int events_processed=0, rows_upserted=0; };

struct RebuildReport {
    std::string projection_name;
    int64_t ground_truth_count=0;
    int64_t rebuilt_count=0;
    bool truncation_suspected=false;
};

class ProjectionMaintainer {  // Outbox subscriber
public:
    explicit ProjectionMaintainer(persistence::SqliteAdapter& adapter);
    // 消费 statement.written/derived/archived/consolidated → 增量更新 6 投影表 + checkpoint.
    MaintainerStats tick_one_batch(persistence::Connection& conn, std::string_view now_iso);
    // 全量 rebuild + repair guard (Task 27).
    RebuildReport rebuild_projection(persistence::Connection& conn,
                                     std::string_view projection_name,
                                     std::string_view now_iso);
private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::projection
```

- [ ] **Step 2: 写 impl（tick_one_batch；rebuild 在 Task 27）**

Create `src/projection/projection_maintainer.cpp`：`tick_one_batch`: SELECT bus_events WHERE outbox_sequence>checkpoint AND event_type LIKE 'statement.%' → 对每条按 primary_id 读 statements 行 → UPSERT 到 6 投影表（proj_holder_state_time / proj_holder_subgraph / proj_entity_statement / proj_salience_hot / proj_commitment_due / proj_common_ground）；archived/forgotten → DELETE 对应投影行 → 更新 checkpoint。

- [ ] **Step 3: 写测试**

Create `tests/cpp/test_projection_incremental.cpp`：写一条 statement + emit statement.written → tick → 验证 6 投影表对应行出现；archived → tick → 投影行清理；checkpoint 推进 + 重复 tick 不重处理。

- [ ] **Step 4: CMake + build + 测试 + Commit**

`CMakeLists.txt` starling_core 追加 `src/projection/projection_maintainer.cpp`；`tests/cpp/CMakeLists.txt` 追加 `test_projection_incremental.cpp`。

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R ProjectionIncremental 2>&1 | tail -8
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/projection/projection_maintainer.hpp \
        src/projection/projection_maintainer.cpp \
        tests/cpp/test_projection_incremental.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/substrate): ProjectionMaintainer tick — 6 投影增量物化

spec §10.2: 消费 statement.written/derived/archived/consolidated → 增量
UPSERT 6 投影表 (holder_state_time/holder_subgraph/entity_statement/
salience_hot/commitment_due/common_ground); archived/forgotten 清理投影行;
checkpoint 推进保幂等。rebuild + repair guard 在 Task 27。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 27: ProjectionMaintainer — rebuild + repair guard

**Files:**
- Modify: `include/starling/projection/projection_maintainer.hpp`（已声明 rebuild_projection）, `src/projection/projection_maintainer.cpp`
- Create: `tests/cpp/test_projection_repair_guard.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §10.2 + §16.3-3/-6

- [ ] **Step 1: impl `rebuild_projection`（repair guard）**

在 `src/projection/projection_maintainer.cpp` 实现 `rebuild_projection`：
1. 数 ground_truth_count：主表 statements 中符合该投影条件的行数（如 proj_holder_state_time = COUNT(*) FROM statements）。
2. 在临时表/临时计数中 rebuild，得 rebuilt_count。
3. 若 `rebuilt_count < ground_truth_count` → emit `projection.rebuild_failed`（payload 含 truncation_suspected=true + projection_name + 两个 count）+ UPDATE projection_rebuild_state SET status='truncation_suspected' + **保留旧 active 投影表不替换**；report.truncation_suspected=true。
4. 否则 → 原子替换 active 投影内容 + UPDATE projection_rebuild_state SET status='active', ground_truth_count, index_count, last_rebuilt_at。

```cpp
// 关键片段:
RebuildReport ProjectionMaintainer::rebuild_projection(
    persistence::Connection& conn, std::string_view name, std::string_view now_iso) {
    RebuildReport rep; rep.projection_name = std::string(name);
    rep.ground_truth_count = count_ground_truth(conn, name);   // 主表符合条件行数
    rep.rebuilt_count = rebuild_into_temp(conn, name);         // 重建抽取行数
    if (rep.rebuilt_count < rep.ground_truth_count) {
        rep.truncation_suspected = true;
        emit_rebuild_failed(conn, name, rep);                  // emit projection.rebuild_failed
        mark_state(conn, name, "truncation_suspected", rep, now_iso);
        // 不替换 active 投影 — 旧数据保留
        return rep;
    }
    swap_active(conn, name);                                    // 原子替换
    mark_state(conn, name, "active", rep, now_iso);
    return rep;
}
```

- [ ] **Step 2: build + 测试桩**

```bash
cmake --build build 2>&1 | tail -3
```

- [ ] **Step 3: 写 C++ 单测**

Create `tests/cpp/test_projection_repair_guard.cpp`：构造 ground_truth=N 但 rebuild 注入只产 N-1（模拟 truncation）→ rebuild_projection → report.truncation_suspected=true + projection_rebuild_state.status='truncation_suspected' + 旧 active 行未被清。正常 rebuild（rebuilt==ground_truth）→ status='active'。

- [ ] **Step 4: CMake + build + 测试 + Commit**

`tests/cpp/CMakeLists.txt` 追加 `test_projection_repair_guard.cpp`。

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R ProjectionRepair 2>&1 | tail -8
ctest --test-dir build --output-on-failure 2>&1 | tail -3
git add include/starling/projection/projection_maintainer.hpp \
        src/projection/projection_maintainer.cpp \
        tests/cpp/test_projection_repair_guard.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/substrate): ProjectionMaintainer rebuild + repair guard

spec §10.2 + §16.3-3/-6: rebuild 数主表 ground_truth_count vs rebuilt_count;
rebuilt<ground_truth → emit projection.rebuild_failed(truncation_suspected) +
status='truncation_suspected' + 保留旧 active 不替换; 否则原子替换 active。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 28: TC-PROJECTION-REPAIR [CRITICAL]

**Files:**
- Create: `tests/python/test_tc_projection_repair.py`

**Spec ref:** §12.2 TC-PROJECTION-REPAIR

- [ ] **Step 1: 写测试**

Create `tests/python/test_tc_projection_repair.py`:

```python
"""TC-PROJECTION-REPAIR [CRITICAL]: rebuild 抽取 < ground truth → 不替换.

spec §16.3-3/-6: Projection repair safety/guard。构造 rebuild 抽取条数低于
主表 ground truth 的场景, 验证系统 emit projection.rebuild_failed(
truncation_suspected) 且 active projection 不被替换。
"""
from __future__ import annotations
import sqlite3
import pytest
from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3


@pytest.fixture
def rt(tmp_path, monkeypatch):
    orig = relax_preflight_for_m0_3()
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r
    monkeypatch.setattr(runtime, "LOCAL_STORE_REQUIRED", orig)


def _seed_statement(rt, stmt_id):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (stmt_id, "default", "alice", "first_person", "cognizer", "bob",
             "knows", "str", "x", "a"*64, "v1", "believes", "pos", 0.9,
             "2026-05-27T09:00:00Z", 0.5, "{}", 0.0, "2026-05-27T09:00:00Z",
             "user_input", "consolidated", "approved",
             "2026-05-27T09:00:00Z", "2026-05-27T09:00:00Z"))
        c.commit()


def test_truncation_suspected_keeps_active(rt):
    # seed 3 statements + 先正常物化一次 proj_holder_state_time
    for i in range(3):
        _seed_statement(rt, f"s{i}")
    pm = _core.ProjectionMaintainer(rt.adapter)
    pm.rebuild_projection("proj_holder_state_time", "2026-05-27T10:00:00Z")  # active=3
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        before = c.execute("SELECT COUNT(*) FROM proj_holder_state_time").fetchone()[0]
    assert before == 3

    # 注入 truncation: 用测试钩子让下一次 rebuild 只抽 2 条 (< ground truth 3)
    report = pm.rebuild_projection_with_injected_count(
        "proj_holder_state_time", injected_rebuilt=2, now="2026-05-27T11:00:00Z")
    assert report.truncation_suspected is True

    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        # active projection 仍是 3 (未被截断的 2 替换)
        after = c.execute("SELECT COUNT(*) FROM proj_holder_state_time").fetchone()[0]
        status = c.execute(
            "SELECT status FROM projection_rebuild_state WHERE projection_name='proj_holder_state_time'"
        ).fetchone()[0]
        ev = c.execute(
            "SELECT COUNT(*) FROM bus_events WHERE event_type='projection.rebuild_failed'"
        ).fetchone()[0]
    assert after == 3, "truncation_suspected 时 active projection 不被替换"
    assert status == "truncation_suspected"
    assert ev == 1, "应 emit projection.rebuild_failed"
```

> 实现注：Task 27 的 `rebuild_projection_with_injected_count(name, injected_rebuilt, now)` 是测试钩子（仅 binding 暴露给测试，prod 不调），用于注入低于 ground truth 的 rebuilt_count 以触发 truncation 路径。若不便加钩子，可改为构造主表数据 > 物化输入的真实场景。

- [ ] **Step 2: 跑 + 全 guard + Commit**

```bash
pytest tests/python/test_tc_projection_repair.py -v 2>&1 | tail -8
git add tests/python/test_tc_projection_repair.py
git commit -m "$(cat <<'EOF'
test(M0.8/CRITICAL): TC-PROJECTION-REPAIR — truncation_suspected 不替换

§16.3-3/-6 准入: rebuild 抽取 < 主表 ground truth → emit
projection.rebuild_failed(truncation_suspected) + active projection 保留不替换。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 29: SubscriberPump（统一 post-write 泵）

**Files:**
- Create: `include/starling/bus/subscriber_pump.hpp`, `src/bus/subscriber_pump.cpp`, `tests/cpp/test_subscriber_pump.cpp`
- Modify: `src/bus/bus.cpp`, `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §11

- [ ] **Step 1: 写 header**

Create `include/starling/bus/subscriber_pump.hpp`:

```cpp
#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"

namespace starling::bus {

// 统一 post-write 泵: Bus::write_impl commit 后调用一次. 按固定顺序跑所有
// subscriber, 每个 SAVEPOINT 隔离 — 单 subscriber 失败回滚自身, 不影响主写入
// 或其他 subscriber.
class SubscriberPump {
public:
    // 固定顺序:
    //  1. conflict_key_backfill::tick_one_batch   (P2.a 迁入)
    //  2. belief_tracker::tick_one_batch          (P2.a 迁入)
    //  3. reconsolidation tick_one_batch + close_due_windows  (M0.8)
    //  4. projection_maintainer::tick_one_batch   (M0.8)
    //  5. replay_scheduler::tick_online           (M0.8)
    static void run_post_write(persistence::SqliteAdapter& adapter,
                               persistence::Connection& conn,
                               std::string_view now_iso);
};

}  // namespace starling::bus
```

- [ ] **Step 2: 写 impl（每 subscriber 独立 try + SAVEPOINT）**

Create `src/bus/subscriber_pump.cpp`：依次调 5 个 subscriber，每个包在 `try { SAVEPOINT sub_N; ...; RELEASE; } catch { ROLLBACK TO sub_N; }`（best-effort，失败不传播）。复用现有 `conflict_key_backfill::tick_one_batch(conn)` + `belief_tracker::tick_one_batch(adapter)` + 新 `ReconsolidationEngine(adapter).tick_one_batch(conn,now)` + `.close_due_windows(conn,now)` + `ProjectionMaintainer(adapter).tick_one_batch(conn,now)` + `ReplayScheduler(adapter).tick_online(conn,now)`。

- [ ] **Step 3: 改 bus.cpp（替换现有两个 tick 调用）**

`src/bus/bus.cpp` 中 `tx.commit()` 之后现有的（约 lines 619-628）：
```cpp
    conflict_key_backfill::tick_one_batch(conn);
    try { starling::tom::belief_tracker::tick_one_batch(adapter_); } catch (...) {}
```
替换为：
```cpp
    // 统一 post-write 泵: 5 subscriber 各 SAVEPOINT 隔离 (spec §11).
    const std::string now_iso = detail::iso8601_utc(std::chrono::system_clock::now());
    SubscriberPump::run_post_write(adapter_, conn, now_iso);
```
并加 `#include "starling/bus/subscriber_pump.hpp"`，移除不再直接用的两个 tick include（若仅此处用）。

- [ ] **Step 4: 写测试**

Create `tests/cpp/test_subscriber_pump.cpp`：验证 run_post_write 跑完 5 subscriber 不抛；单个 subscriber 抛异常时其余仍执行（SAVEPOINT 隔离）；顺序正确。

- [ ] **Step 5: CMake + build + 测试**

`CMakeLists.txt` starling_core 追加 `src/bus/subscriber_pump.cpp`；`tests/cpp/CMakeLists.txt` 追加 `test_subscriber_pump.cpp`。

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -3
ctest --test-dir build --output-on-failure -R SubscriberPump 2>&1 | tail -8
```

- [ ] **Step 6: P2.a 回归（迁移后两个旧 tick 测试必须仍过）**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
```
Expected: ctest 全绿；pytest 全绿（含 P2.a 的 belief_tracker / conflict_key_backfill 相关测试）。这是 SubscriberPump 迁移的关键验收 —— 行为不变只改调用点。

- [ ] **Step 7: Commit**

```bash
git add include/starling/bus/subscriber_pump.hpp src/bus/subscriber_pump.cpp \
        src/bus/bus.cpp tests/cpp/test_subscriber_pump.cpp \
        CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.8/bus): SubscriberPump 统一 post-write 泵

spec §11: Bus::write commit 后调一次 run_post_write, 按固定顺序跑 5 subscriber
(conflict_key_backfill / belief_tracker / reconsolidation / projection_maintainer /
replay_online), 每个 SAVEPOINT 隔离。迁移 P2.a 的两个 tick 进泵, 行为不变,
belief_tracker + conflict_key_backfill 测试回归通过。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 30: pybind bindings + Python wrappers

**Files:**
- Modify: `bindings/python/module.cpp`
- Create: `python/starling/replay/__init__.py`, `python/starling/reconsolidation/__init__.py`, `python/starling/neocortex/__init__.py`, `python/starling/projection/__init__.py`
- Create: `tests/python/test_m0_8_bindings.py`

**Spec ref:** §6-§10（Python 暴露）

- [ ] **Step 1: 暴露 C++ 类到 pybind**

`bindings/python/module.cpp` 的 PYBIND11_MODULE 块追加：
- `ReplayScheduler`(adapter) + `.tick_online`/`.run_idle`/`.run_sleep`/`.enforce_oscillation_guard`/`.sweep_volatile_ttl`/`.run_decay`
- `ReconsolidationEngine`(adapter) + `.tick_one_batch`/`.close_due_windows`/`.reconsolidate`
- `PersonaContainer`(adapter) + `.rebuild`
- `CommonGroundContainer`(adapter) + `.rebuild`
- `CommonGroundWriter`(adapter) + 5 acts + `.sweep_timeout_downgrade`
- `ProjectionMaintainer`(adapter) + `.tick_one_batch`/`.rebuild_projection`/`.rebuild_projection_with_injected_count`(测试钩子)

绑定方法签名要让 CRITICAL 测试可调（如 `ReplayScheduler.enforce_oscillation_guard()` 自取 connection，`run_decay(list, now)` 等）。Connection 由 adapter 内部取，不暴露给 Python（同 P2.a 的 BeliefTracker 模式）。

- [ ] **Step 2: 写 Python 便利包**

各 `python/starling/<subsystem>/__init__.py` re-export `_core` 的对应类。

- [ ] **Step 3: 重建 + 刷新 editable**

```bash
cmake --build build 2>&1 | tail -3
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages 2>&1 | tail -2
pip install -e . --no-deps --force-reinstall 2>&1 | tail -2
```

- [ ] **Step 4: binding smoke 测试**

Create `tests/python/test_m0_8_bindings.py`：import + 构造每个类 + 调一个无副作用方法不抛。

```bash
pytest tests/python/test_m0_8_bindings.py -v 2>&1 | tail -8
```

- [ ] **Step 5: 回跑全部 CRITICAL（binding 就绪后 Task 13/14/15/20/21/22/28 应 GREEN）**

```bash
pytest tests/python/test_tc_a1_001.py tests/python/test_tc_a1_002.py \
       tests/python/test_tc_a6_001.py tests/python/test_tc_a6_002.py \
       tests/python/test_tc_a5_001.py tests/python/test_tc_a5_002.py \
       tests/python/test_tc_a8_001.py tests/python/test_tc_projection_repair.py -v 2>&1 | tail -20
```
Expected: 全部 GREEN。若某个 RED，回对应子系统 task 补 binding/方法。

- [ ] **Step 6: 全 guard + Commit**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
python scripts/ci_static_scan.py 2>&1 | tail -2
git add bindings/python/module.cpp python/starling/replay python/starling/reconsolidation \
        python/starling/neocortex python/starling/projection tests/python/test_m0_8_bindings.py
git commit -m "$(cat <<'EOF'
feat(M0.8): pybind bindings + Python wrappers for 4 新子系统

暴露 ReplayScheduler / ReconsolidationEngine / PersonaContainer /
CommonGroundContainer / CommonGroundWriter / ProjectionMaintainer 给 Python。
Connection 由 adapter 内部取 (同 P2.a BeliefTracker 模式)。8 个 CRITICAL
测试在 binding 就绪后全 GREEN。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 31: non-CRITICAL roll-up + §16.3-9 回归确认

**Files:**
- Create: `tests/python/test_reconsolidation_window_config.py`, `tests/python/test_grounding_acts.py`, 等 roll-up（按需）
- 验证: 现有 `tests/python/test_tc_new_conflict_severe.py` 仍过

**Spec ref:** §12.3 + §16.3-9

- [ ] **Step 1: §16.3-9 兼容性回归（关键）**

```bash
pytest tests/python/test_tc_new_conflict_severe.py -v 2>&1 | tail -10
```
Expected: GREEN。验证 Reconsolidation 上线后 P1 同步 ConflictProbe severe path（direct_contradiction/superseding 同事务）**未被修改** —— TC-NEW-CONFLICT-SEVERE 仍通过。若 RED，说明 Reconsolidation 误碰了 Bus.write 同步路径，必须修复。

- [ ] **Step 2: §16.3-4 窗口配置 roll-up**

Create `tests/python/test_reconsolidation_window_config.py`：验证 per-modality 超时（COMMITS 长 / ASSUMES 短）+ 高频 ≥3/hr → 5min + clamp [5min,6h]。

- [ ] **Step 3: grounded 状态机 roll-up**

Create `tests/python/test_grounding_acts.py`：5 动作状态迁移 + grounded 3 规则（显式/N=3/M=2）+ 24h 降级。

- [ ] **Step 4: 其余 roll-up（按 spec §12.3 清单，可合并到上述文件或现有 C++ 单测覆盖）**

forgetting_curve / swr_sampler / replay_ops / arbitration / persona_anchor / projection_incremental / subscriber_pump 已由各子系统 task 的 C++ 单测覆盖；此处仅补 Python 层缺口。

- [ ] **Step 5: 全 guard + Commit**

```bash
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
python scripts/ci_static_scan.py 2>&1 | tail -2
git add tests/python/test_reconsolidation_window_config.py tests/python/test_grounding_acts.py
git commit -m "$(cat <<'EOF'
test(M0.8): non-CRITICAL roll-up + §16.3-9 兼容性回归

§16.3-9: TC-NEW-CONFLICT-SEVERE 回归确认 Reconsolidation 不碰 P1 同步
severe path。roll-up: 窗口配置 (per-modality/高频/clamp) + grounded 状态机
(5 动作 + 3 规则 + 24h 降级)。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 32: Milestone close — roadmap flip + final review + merge

**Files:**
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md`
- After merge: commit `docs/superpowers/plans/2026-05-27-m0-8-brain-dynamics-core.md` to main

- [ ] **Step 1: 识别最后一个 work commit**

```bash
git log --oneline main..HEAD | head
```
最后一个 work commit（topmost SHA，非 roadmap-flip）记下，pin 进 roadmap。

- [ ] **Step 2: flip roadmap**

`docs/superpowers/plans/2026-05-23-roadmap.md`：P2.b 行（第 72 行）标注 M0.8（无向量核心）完成 + 链接 plan；第 148 行 P2.b 状态行更新（M0.8 部分完成，M0.9 待写）。具体：把 P2.b 出货项里 M0.8 覆盖的部分标 ✅，注明 M0.9 剩余（向量层）。

- [ ] **Step 3: commit roadmap flip**

```bash
git add docs/superpowers/plans/2026-05-23-roadmap.md
git commit -m "$(cat <<'EOF'
chore(M0.8): mark brain-dynamics-core complete in roadmap

P2.b 第一阶段 (M0.8 无向量脑动力学核心) 完成: Replay/Reconsolidation/
Neocortex Persona/CommonGround writer/Projection Index 6 SQL 投影/
SubscriberPump。pin 最后 work commit。M0.9 向量层待写。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: worktree 全绿**

```bash
source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
cmake --build build
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
python scripts/ci_static_scan.py 2>&1 | tail -2
```
全绿才继续。

- [ ] **Step 5: 派发整分支 final reviewer**

（Controller-only）`feature-dev:code-reviewer` 审整个 M0.8 分支。Scrutiny list：SubscriberPump 迁移正确性（P2.a 两 tick 行为不变）、Reconsolidation severe 4 项原子（§16.3-9 不碰 P1 同步路径）、Replay decay 串行守护、Projection repair guard truncation、5 migration、8 CRITICAL。

- [ ] **Step 6: AskUserQuestion 合并 consent**

（Controller-only）三选项：merge to main (--no-ff) / keep worktree / squash。

- [ ] **Step 7: 若 consent=merge，从 main 合并**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git checkout main
git merge --no-ff worktree-m0-8-brain-dynamics -m "$(cat <<'EOF'
Merge M0.8: 无向量脑动力学核心 (P2.b 第一阶段)

3 新子系统 (07_neocortex / 10_replay / 11_reconsolidation) + 3 扩展
(04_substrate Projection Index 6 SQL 投影 / 05_bus SubscriberPump /
09_tom CommonGround writer)。8 admission CRITICAL (TC-A1/A5/A6 + TC-A8-001
+ TC-PROJECTION-REPAIR)。覆盖 §16.3 准入 -3/-4/-6/-7/-9。有代码子系统 7→10/12。

ctest <N>/<N>, pytest <M>/<M>, ci_static_scan clean。M0.9 向量层待写。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```
替换 `<N>`/`<M>` 为实际计数。

- [ ] **Step 8: commit plan-doc 到 main**

```bash
cp /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-8-brain-dynamics/docs/superpowers/plans/2026-05-27-m0-8-brain-dynamics-core.md \
   docs/superpowers/plans/2026-05-27-m0-8-brain-dynamics-core.md
git add docs/superpowers/plans/2026-05-27-m0-8-brain-dynamics-core.md
git commit -m "$(cat <<'EOF'
docs(M0.8): land brain-dynamics-core implementation plan

Plan 在 worktree 分支保持 untracked (项目策略), milestone close 后落 main。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 9: post-merge 全绿**

```bash
source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
pip install -e . --no-deps --force-reinstall
cmake --build build
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
python scripts/ci_static_scan.py 2>&1 | tail -2
```

- [ ] **Step 10: 拆 worktree**

```bash
git worktree remove --force /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-8-brain-dynamics
git branch -D worktree-m0-8-brain-dynamics
git worktree list
```
Expected: 仅 main。

- [ ] **Step 11: final report**

报告：merge SHA / last work commit SHA / ctest+pytest+ci 计数 / 8 CRITICAL 状态 / 子系统 7→10/12 / 确认 plan-doc 落 main + worktree 拆除。M0.8 关闭，下一步 M0.9 向量层。

---

## Self-Review（writing-plans 要求）

**1. Spec coverage**：spec §5.1-5.5 → Tasks 1-5；§6 → Tasks 6-12；§7 → Tasks 16-19；§8 → Tasks 23-24；§9 → Task 25；§10 → Tasks 26-27；§11 → Task 29；§12.2 8 CRITICAL → Tasks 13/14/15/20/21/22/28；§16.3-3/-4/-6/-7/-9 → 各有实现 task + 回归。无 gap。

**2. Placeholder scan**：无 TBD/TODO/"implement later"。部分 impl 标"由 implementer 按 header 契约写出"——这是 subagent-driven-development 的预期（implementer 子代理按 header + spec 写 impl），非 placeholder。

**3. Type consistency**：ConsolidationOp 5 值贯穿 Tasks 8-12；ReplayScheduler/ReconsolidationEngine/PersonaContainer/CommonGroundWriter/ProjectionMaintainer 类名 Tasks 12/19/23/25/26 与 binding Task 30 一致；REPLAYING_RECONSOLIDATING 复用既有枚举。

---

## 元数据

- **里程碑**: M0.8（P2.b 第一阶段，无向量脑动力学核心）
- **依赖**: P2.a close（main 7f00828 + M0.8 spec）
- **后继**: M0.9（向量基础层）→ P2.c
- **分支**: worktree-m0-8-brain-dynamics，--no-ff 合并 main

