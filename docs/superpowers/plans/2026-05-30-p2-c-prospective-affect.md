# P2.c 前瞻与情感 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Commitment 五态机 + PolicyEngine(4 Trigger + post-write/tick 双入口)+ active_holding 反向保护(SQL EXISTS)+ AffectVector 五维驱动优先级重放权重 + ActionGuard 最小护栏。

**Architecture:** 全 stateless-per-tick SQL-backed(对齐 ReplayScheduler/EmbeddingWorker)。CommitmentEngine 管五态机;PolicyEngine 经 SubscriberPump 第 6 subscriber(post-write)+ runtime tick(time)驱动;保护走 `commitment_protection` JOIN `commitments.state='ACTIVE'` 的 SQL EXISTS(无 in-memory set,持久性满足 boot-replay)。AffectVector 采样时算,写路径零改动。

**Tech Stack:** C++20 + raw SQLite + libcurl + nlohmann/json + pybind11 + Python 3.14 + pytest + ctest + Ninja。

**Spec:** `docs/superpowers/specs/2026-05-30-p2-c-prospective-affect-design.md`（commit `5f271f2`）。

---

## 实施约束（贯穿所有 Task）

- `starling_core` 显式 `target_sources`（`CMakeLists.txt`,当前末尾 `src/embedding/openai_embedding_adapter.cpp`),每个新 `.cpp` append；单一 `starling_tests`(`tests/cpp/CMakeLists.txt`,末尾 `test_vector_capability.cpp`),新测试 append。
- migrations glob-based,最高现存 `0017`,P2.c 用 `0018`–`0020`。
- pybind 改动后刷新 Python `_core.so`：`cmake --build build && cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages && pip install -e . --no-deps --force-reinstall`。**`cmake --install` 是关键**(单 `pip install -e` 因 scikit-build GLOB staleness 不刷新 migrations/新符号)。
- 测试：unit 用 `:memory:`;runtime 用 `tmp_path` + `relax_preflight_for_m0_3()`。
- SQL helpers：`starling::bus::detail::bind_sv`/`make_sqlite_error`(`starling/bus/sqlite_helpers.hpp`)、`starling::persistence::StmtHandle`(`starling/persistence/sqlite_handles.hpp`),checked `sqlite3_prepare_v2`;参考 `src/projection/projection_maintainer.cpp`、`src/vector/sqlite_blob_vector_index.cpp`。
- `emit_event`:复用 `projection_maintainer.cpp` 的 file-local helper(BusEvent + `compute_window_bucket` + `compute_idempotency_key` + `OutboxWriter::append`),copy 到各 .cpp 匿名 namespace。
- pybind 类公开 `connection()` accessor,Python 方法 conn-free。
- 红线回归:M0.8 + M0.9 + P2.a 全绿;SubscriberPump 第 6 subscriber 不 regress 前 5;`op_decay` 改后 M0.8 decay 测试回归;§16.3-9 TC-NEW-CONFLICT-SEVERE 仍过;`statements` 表不动(只加 3 张 commitment 表)。
- 无 `--no-verify`/`--amend`;plan untracked 直到 Task 16 close。

## 文件结构

| 文件 | 职责 |
|---|---|
| `migrations/0018_commitments.sql` / `0019_commitment_triggers.sql` / `0020_commitment_protection.sql` | 3 张表 |
| `include/starling/affect/affect_vector.hpp` + `src/affect/affect_vector.cpp` | 五维 + salience + parse(纯计算)|
| `include/starling/prospective/action_guard.hpp` + `src/prospective/action_guard.cpp` | 最小护栏 check |
| `include/starling/prospective/commitment_engine.hpp` + `src/prospective/commitment_engine.cpp` | 五态机 |
| `include/starling/prospective/trigger.hpp` + `src/prospective/trigger.cpp` | 4 类 Trigger 评估 |
| `include/starling/prospective/policy_engine.hpp` + `src/prospective/policy_engine.cpp` | post-write + tick |
| `src/replay/consolidation_ops.cpp`(改)| op_decay 保护 EXISTS |
| `src/replay/replay_scheduler.cpp`(改)| AffectVector 喂 sample_weight |
| `src/bus/subscriber_pump.cpp`(改)| 第 6 subscriber policy_engine |
| `bindings/python/module.cpp`(改)| 暴露 4 类 |
| `tests/cpp/test_*.cpp` + `tests/python/test_*.py` | 单测 + 集成 + 5 CRITICAL |

---

## Task 0: Baseline 确认

**Files:** 无。

- [ ] **Step 1: 确认 worktree 全绿**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-c-prospective-affect
source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
cmake -S . -B build -G Ninja 2>&1 | tail -2
cmake --build build 2>&1 | tail -3
ctest --test-dir build 2>&1 | grep -E "tests passed|failed"
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages 2>&1 | tail -1
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
pytest tests/python -q 2>&1 | tail -2
python scripts/ci_static_scan.py 2>&1 | tail -1
```
Expected: ctest 456/456;pytest 480 passed + 13 skipped;ci_static_scan OK。

---

## Task 1: migration 0018 — commitments

**Files:**
- Create: `migrations/0018_commitments.sql`
- Test: `tests/python/test_p2c_migrations.py`

- [ ] **Step 1: 写迁移**

```sql
-- P2.c Commitment 五态机 (per spec §5)。绑定 modality=COMMITS statement。
CREATE TABLE commitments (
    stmt_id      TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    state        TEXT NOT NULL DEFAULT 'ACTIVE'
                 CHECK (state IN ('created','ACTIVE','FULFILLED','BROKEN','RENEGOTIATED','WITHDRAWN')),
    broken_count INTEGER NOT NULL DEFAULT 0,
    deadline     TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX idx_commitments_state ON commitments(tenant_id, state);
CREATE INDEX idx_commitments_deadline ON commitments(state, deadline);
```

- [ ] **Step 2: 写存在性测试**

```python
"""P2.c migrations 0018/0019/0020 建表自检。"""
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


def test_commitments_table_exists(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(commitments)")}
    assert {"stmt_id", "tenant_id", "state", "broken_count", "deadline",
            "created_at", "updated_at"} <= cols
```

- [ ] **Step 3: 重建 + 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -1 && cmake --build build 2>&1 | tail -2
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages 2>&1 | tail -1
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
pytest tests/python/test_p2c_migrations.py::test_commitments_table_exists -v 2>&1 | tail -5
git add migrations/0018_commitments.sql tests/python/test_p2c_migrations.py
git commit -m "$(cat <<'EOF'
feat(P2.c/prospective): migration 0018 — commitments 五态机表

spec §4: commitments(stmt_id PK, state CHECK 6 值, broken_count, deadline)。
绑定 modality=COMMITS statement。statements 表不动。

EOF
)"
```

---

## Task 2: migration 0019 — commitment_triggers

**Files:**
- Create: `migrations/0019_commitment_triggers.sql`
- Test: `tests/python/test_p2c_migrations.py`（追加 `test_commitment_triggers_table_exists`,断言列 `{id,commitment_stmt_id,tenant_id,kind,spec_json,status,created_at}`)

- [ ] **Step 1: 写迁移**

```sql
-- P2.c PolicyEngine Trigger 注册 (per spec §6)。
CREATE TABLE commitment_triggers (
    id                 TEXT PRIMARY KEY,
    commitment_stmt_id TEXT NOT NULL,
    tenant_id          TEXT NOT NULL,
    kind               TEXT NOT NULL CHECK (kind IN ('time','event','state','compound')),
    spec_json          TEXT NOT NULL DEFAULT '{}',
    status             TEXT NOT NULL DEFAULT 'armed' CHECK (status IN ('armed','fired','cleared')),
    created_at         TEXT NOT NULL
);
CREATE INDEX idx_commitment_triggers_kind ON commitment_triggers(tenant_id, kind, status);

-- PolicyEngine.run_post_write 的 outbox 消费游标 (Task 8 依赖)。
CREATE TABLE policy_engine_checkpoint (
    id  INTEGER PRIMARY KEY CHECK (id = 1),
    seq INTEGER NOT NULL DEFAULT 0
);
INSERT INTO policy_engine_checkpoint(id, seq) VALUES (1, 0);
```

- [ ] **Step 2: 追加测试 + 重建 + 跑 + Commit**

```bash
cmake --build build 2>&1 | tail -2
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages 2>&1 | tail -1
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
pytest tests/python/test_p2c_migrations.py -v 2>&1 | tail -5
git add migrations/0019_commitment_triggers.sql tests/python/test_p2c_migrations.py
git commit -m "$(cat <<'EOF'
feat(P2.c/prospective): migration 0019 — commitment_triggers

spec §6: Trigger 注册表 (kind time/event/state/compound + spec_json + status)。

EOF
)"
```

---

## Task 3: migration 0020 — commitment_protection

**Files:**
- Create: `migrations/0020_commitment_protection.sql`
- Test: `tests/python/test_p2c_migrations.py`（追加 `test_commitment_protection_table_exists`,断言列 `{commitment_stmt_id,protected_stmt_id}`)

- [ ] **Step 1: 写迁移**

```sql
-- P2.c active_holding 反向保护映射 (per spec §7)。decay EXISTS-join commitments.state='ACTIVE'。
CREATE TABLE commitment_protection (
    commitment_stmt_id TEXT NOT NULL,
    protected_stmt_id  TEXT NOT NULL,
    PRIMARY KEY (protected_stmt_id, commitment_stmt_id)
);
```

- [ ] **Step 2: 追加测试 + 重建 + 跑 + Commit**

```bash
cmake --build build 2>&1 | tail -2
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages 2>&1 | tail -1
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
pytest tests/python/test_p2c_migrations.py -v 2>&1 | tail -6
git add migrations/0020_commitment_protection.sql tests/python/test_p2c_migrations.py
git commit -m "$(cat <<'EOF'
feat(P2.c/prospective): migration 0020 — commitment_protection

spec §7: active_holding 保护映射 (commitment_stmt_id, protected_stmt_id)。
decay EXISTS-join commitments.state='ACTIVE'。

EOF
)"
```

---

## Task 4: AffectVector — 五维 + salience + parse（纯计算）

**Files:**
- Create: `include/starling/affect/affect_vector.hpp`, `src/affect/affect_vector.cpp`, `tests/cpp/test_affect_vector.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §3.4。与 `python/starling/schema/affect.py` 公式对拍。

- [ ] **Step 1: 头文件**

```cpp
// include/starling/affect/affect_vector.hpp
#pragma once
#include <string_view>

namespace starling::affect {

struct AffectVector {
    float valence = 0.f;    // -1..+1
    float arousal = 0.f;    //  0..1
    float dominance = 0.f;  // -1..+1
    float novelty = 0.f;    //  0..1
    float stakes = 0.f;     //  0..1
};

// salience 公式 (对拍 affect.py)：
// (0.4+0.6|valence|)·(0.4+0.6·arousal)·(0.3+0.7·novelty)·(0.3+0.7·stakes)·(0.6+0.4·surprise_decay)
double salience(const AffectVector&, double surprise_decay = 1.0);

// 解析 affect_json (keys: valence/arousal/dominance/novelty/stakes;缺/非法默认 0)。
AffectVector parse_affect_json(std::string_view json);

}  // namespace starling::affect
```

- [ ] **Step 2: 失败测试**

```cpp
// tests/cpp/test_affect_vector.cpp
#include "starling/affect/affect_vector.hpp"
#include <gtest/gtest.h>
using namespace starling::affect;

TEST(AffectVector, SalienceParityWithPython) {
    // affect.py: valence=0.5,arousal=0.8,novelty=0.6,stakes=0.9,surprise_decay=1.0
    AffectVector v{0.5f, 0.8f, 0.0f, 0.6f, 0.9f};
    double expect = (0.4+0.6*0.5)*(0.4+0.6*0.8)*(0.3+0.7*0.6)*(0.3+0.7*0.9)*(0.6+0.4*1.0);
    EXPECT_NEAR(salience(v, 1.0), expect, 1e-6);
}
TEST(AffectVector, ParseJsonAndDefaults) {
    auto v = parse_affect_json(R"({"valence":-0.5,"arousal":0.7})");
    EXPECT_NEAR(v.valence, -0.5, 1e-6);
    EXPECT_NEAR(v.arousal, 0.7, 1e-6);
    EXPECT_NEAR(v.stakes, 0.0, 1e-6);            // 缺字段默认 0
    EXPECT_NO_THROW(parse_affect_json("{}"));
    EXPECT_NO_THROW(parse_affect_json("not json")); // 非法不抛,全 0
}
```

- [ ] **Step 3: CMake 注册**（`src/affect/affect_vector.cpp` → starling_core；`test_affect_vector.cpp` → starling_tests）

- [ ] **Step 4: 实现**

`salience`：用 `std::abs(v.valence)`,按公式返回 double。`parse_affect_json`：`nlohmann::json::parse`(try/catch,失败返回默认 AffectVector{}),`j.value("valence", 0.0f)` 逐字段。`#include <nlohmann/json.hpp>` + `<cmath>`。

- [ ] **Step 5: 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -1 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R AffectVector --output-on-failure 2>&1 | tail -6
git add include/starling/affect/affect_vector.hpp src/affect/affect_vector.cpp tests/cpp/test_affect_vector.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.c/affect): AffectVector 五维 + salience + parse_affect_json

spec §3.4: 移植 affect.py salience 公式 (五维加权积) + affect_json 解析
(缺/非法默认 0,不抛)。与 Python 端对拍。优先级重放权重的基础。

EOF
)"
```

---

## Task 5: ActionGuard — 最小护栏 check（纯计算）

**Files:**
- Create: `include/starling/prospective/action_guard.hpp`, `src/prospective/action_guard.cpp`, `tests/cpp/test_action_guard.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §3.5 / §9。不接执行器,纯护栏逻辑。

- [ ] **Step 1: 头文件**

```cpp
// include/starling/prospective/action_guard.hpp
#pragma once
#include <map>
#include <set>
#include <string>
#include <string_view>

namespace starling::prospective {

struct ActionGuard {
    std::string profile_name;
    std::set<std::string> allowed_actions;
    std::set<std::string> requires_approval;
    std::map<std::string, int> idempotency_window_sec;
};

enum class GuardVerdict { Allow, RequiresApproval, Blocked };

// fail-closed: ∉ allowed_actions → Blocked;∈ requires_approval → RequiresApproval;else Allow。
GuardVerdict check(const ActionGuard&, std::string_view action_name);

}  // namespace starling::prospective
```

- [ ] **Step 2: 失败测试**

```cpp
// tests/cpp/test_action_guard.cpp
#include "starling/prospective/action_guard.hpp"
#include <gtest/gtest.h>
using namespace starling::prospective;

TEST(ActionGuard, FailClosedAndApproval) {
    ActionGuard g;
    g.allowed_actions = {"send_reminder", "log_note"};
    g.requires_approval = {"send_reminder"};
    EXPECT_EQ(check(g, "log_note"), GuardVerdict::Allow);
    EXPECT_EQ(check(g, "send_reminder"), GuardVerdict::RequiresApproval);
    EXPECT_EQ(check(g, "delete_everything"), GuardVerdict::Blocked);  // fail-closed
}
```

- [ ] **Step 3: CMake 注册** + **Step 4: 实现**

`check`：`if (allowed_actions.count(name)==0) return Blocked; if (requires_approval.count(name)) return RequiresApproval; return Allow;`。

- [ ] **Step 5: 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -1 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R ActionGuard --output-on-failure 2>&1 | tail -5
git add include/starling/prospective/action_guard.hpp src/prospective/action_guard.cpp tests/cpp/test_action_guard.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.c/prospective): ActionGuard 最小护栏 check (fail-closed)

spec §3.5/§9: ∉allowed→Blocked / ∈requires_approval→RequiresApproval / else Allow。
不接执行器 (代码库无 tool-calling),纯护栏 primitive + 单测。

EOF
)"
```

---

## Task 6: CommitmentEngine — 五态机（TC-A2-001/002 CRITICAL）

**Files:**
- Create: `include/starling/prospective/commitment_engine.hpp`, `src/prospective/commitment_engine.cpp`, `tests/cpp/test_commitment_engine.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §3.1 / §5。

- [ ] **Step 1: 头文件**

```cpp
// include/starling/prospective/commitment_engine.hpp
#pragma once
#include <string>
#include <string_view>
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::prospective {

inline constexpr int kMaxBrokenCount = 3;
inline constexpr int kMaxRenegotiationChain = 3;

class CommitmentEngine {
public:
    explicit CommitmentEngine(persistence::SqliteAdapter& a) : adapter_(a) {}
    // 建 ACTIVE commitment + 写 commitment_protection(自身 stmt)+ emit commitment.active_holding。
    void create_from_statement(persistence::Connection&, std::string_view stmt_id,
                               std::string_view tenant_id, std::string_view deadline,
                               std::string_view now_iso);
    // ACTIVE → FULFILLED + emit commitment.fulfilled/released。
    void fulfill(persistence::Connection&, std::string_view stmt_id, std::string_view now_iso);
    // ACTIVE/RENEGOTIATED → WITHDRAWN + emit commitment.withdrawn/released。
    void withdraw(persistence::Connection&, std::string_view stmt_id, std::string_view now_iso);
    // deadline 过期:broken_count<3 → BROKEN(count++);>=3 → WITHDRAWN + auto_withdrawn + trust_priors。
    void on_deadline_expired(persistence::Connection&, std::string_view stmt_id, std::string_view now_iso);
    // 链长<3 → 旧 supersedes + 新 ACTIVE + renegotiated;>=3 → false + renegotiation_blocked。
    bool renegotiate(persistence::Connection&, std::string_view old_stmt_id,
                     std::string_view new_stmt_id, std::string_view now_iso);
    persistence::Connection& connection() { return adapter_.connection(); }
private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::prospective
```

- [ ] **Step 2: 失败测试（含 TC-A2-001/002 CRITICAL）**

```cpp
// tests/cpp/test_commitment_engine.cpp
#include "starling/prospective/commitment_engine.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling::prospective;
using starling::persistence::SqliteAdapter;
namespace {
void seed_commits_stmt(sqlite3* db, const std::string& id) {  // modality=COMMITS
    std::string s = "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
      "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
      "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
      "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
      "created_at,updated_at) VALUES('"+id+"','default','alice','first_person','cognizer',"
      "'bob','will_send','str','report','"+std::string(64,'a')+"','v1','COMMITS','pos',0.9,"
      "'2026-05-30T09:00:00Z',0.5,'{}',0.0,'2026-05-30T09:00:00Z','user_input','consolidated',"
      "'approved','2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
std::string scol(sqlite3* db, const std::string& q) {
    std::string out; sqlite3_exec(db,q.c_str(),
        [](void*p,int,char**v,char**){*(std::string*)p=v[0]?v[0]:"";return 0;},&out,nullptr); return out;
}
int icol(sqlite3* db, const std::string& q) {
    int n=0; sqlite3_exec(db,q.c_str(),[](void*p,int,char**v,char**){*(int*)p=v[0]?atoi(v[0]):0;return 0;},&n,nullptr); return n;
}
}

TEST(CommitmentEngine, CreateActivates) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_commits_stmt(c.raw(), "c1");
    CommitmentEngine(*a).create_from_statement(c, "c1", "default", "2026-05-30T18:00:00Z", "2026-05-30T10:00:00Z");
    EXPECT_EQ(scol(c.raw(), "SELECT state FROM commitments WHERE stmt_id='c1'"), "ACTIVE");
    EXPECT_EQ(icol(c.raw(), "SELECT COUNT(*) FROM commitment_protection WHERE protected_stmt_id='c1'"), 1);
    EXPECT_EQ(icol(c.raw(), "SELECT COUNT(*) FROM bus_events WHERE event_type='commitment.active_holding' AND primary_id='c1'"), 1);
}

// TC-A2-001 [CRITICAL]: broken_count 累至 3 → 下次到期 auto WITHDRAWN
TEST(CommitmentEngine, ThreeBrokenAutoWithdrawn) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_commits_stmt(c.raw(), "c1");
    CommitmentEngine eng(*a);
    eng.create_from_statement(c, "c1", "default", "2026-05-30T18:00:00Z", "2026-05-30T10:00:00Z");
    // 模拟反复到期: 每次 on_deadline_expired 把 ACTIVE→BROKEN(为下次到期需先回 ACTIVE,测试直接 UPDATE 回 ACTIVE 模拟 renegotiate)
    for (int i = 0; i < 3; ++i) {
        eng.on_deadline_expired(c, "c1", "2026-05-30T19:00:00Z");   // BROKEN, count++
        sqlite3_exec(c.raw(), "UPDATE commitments SET state='ACTIVE' WHERE stmt_id='c1'", nullptr,nullptr,nullptr);
    }
    eng.on_deadline_expired(c, "c1", "2026-05-30T20:00:00Z");       // count>=3 → WITHDRAWN
    EXPECT_EQ(scol(c.raw(), "SELECT state FROM commitments WHERE stmt_id='c1'"), "WITHDRAWN");
    EXPECT_EQ(icol(c.raw(), "SELECT COUNT(*) FROM bus_events WHERE event_type='commitment.auto_withdrawn' AND primary_id='c1'"), 1);
}

// TC-A2-002 [CRITICAL]: renegotiation 链长达 3 → 拒绝
TEST(CommitmentEngine, RenegotiationChainCappedAtThree) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_commits_stmt(c.raw(), "c0");
    CommitmentEngine eng(*a);
    eng.create_from_statement(c, "c0", "default", "", "2026-05-30T10:00:00Z");
    // 链: c0 ← c1 ← c2 (链长 2 OK), 第 3 次 c3 (链长 3) 拒绝
    seed_commits_stmt(c.raw(), "c1"); EXPECT_TRUE(eng.renegotiate(c, "c0", "c1", "2026-05-30T11:00:00Z"));
    seed_commits_stmt(c.raw(), "c2"); EXPECT_TRUE(eng.renegotiate(c, "c1", "c2", "2026-05-30T12:00:00Z"));
    seed_commits_stmt(c.raw(), "c3"); EXPECT_FALSE(eng.renegotiate(c, "c2", "c3", "2026-05-30T13:00:00Z"));
    EXPECT_GE(icol(c.raw(), "SELECT COUNT(*) FROM bus_events WHERE event_type='commitment.renegotiation_blocked'"), 1);
}
```

> 实现注:`create_from_statement` UPSERT commitments(state='ACTIVE',broken_count=0,deadline) + INSERT commitment_protection(stmt,stmt) + emit `commitment.active_holding`。`on_deadline_expired` 读 broken_count:`>=3`→ state='WITHDRAWN' + emit `commitment.auto_withdrawn` + (trust_priors 下调:本期可 stub 注释,cognizer_hub 下调留接口,emit 事件为准);`else`→ state='BROKEN',broken_count+1,emit `commitment.broken`。`renegotiate`:用 `statement_edges` supersedes 链算长度(`SELECT COUNT` 沿 supersedes 链,或简化为 commitments 的 renegotiation 计数列——本期用 supersedes 边数:`old_stmt_id` 上溯 supersedes 链);`>=kMaxRenegotiationChain`→ emit `commitment.renegotiation_blocked` + return false;else INSERT supersedes 边 + 新 commitment ACTIVE + emit `commitment.renegotiated` + return true。所有 emit 复用 file-local `emit_event`。

- [ ] **Step 3: CMake 注册 + 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -1 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R CommitmentEngine --output-on-failure 2>&1 | tail -10
git add include/starling/prospective/commitment_engine.hpp src/prospective/commitment_engine.cpp tests/cpp/test_commitment_engine.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.c/prospective): CommitmentEngine 五态机 — TC-A2-001/002 CRITICAL

spec §5: create→ACTIVE / fulfill / withdraw / on_deadline_expired(broken_count<3→
BROKEN, >=3→auto WITHDRAWN+trust_priors) / renegotiate(链长<3→supersedes+ACTIVE,
>=3→renegotiation_blocked)。§16.3-8 TC-A2-001(3次BROKEN auto WITHDRAWN)+
TC-A2-002(链长3拒绝)。

EOF
)"
```

---

## Task 7: Trigger 系统 — 4 类评估 + compound 短路

**Files:**
- Create: `include/starling/prospective/trigger.hpp`, `src/prospective/trigger.cpp`, `tests/cpp/test_trigger.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §3.3 / §6。

- [ ] **Step 1: 头文件**

```cpp
// include/starling/prospective/trigger.hpp
#pragma once
#include <string>
#include <string_view>
#include "starling/persistence/connection.hpp"

namespace starling::prospective {

// 评估上下文:当前 bus 事件(供 event/state trigger)。time trigger 由 deadline 判定。
struct TriggerContext {
    std::string now_iso;
    std::string event_type;      // 当前评估的 bus 事件(post-write);time tick 时为空
    std::string event_primary_id;
};

// 评估单个 trigger 的 spec_json(kind 决定语义)。返回是否命中。
// time: spec {"at": iso} 且 now>=at;event: spec {"event_type":..,"predicate":..} 匹配 ctx;
// state: spec {"target":..,"field":..,"op":..,"value":..} 查 conn 谓词;
// compound: spec {"all_of":[..]} / {"any_of":[..]} 递归短路。
bool evaluate_trigger(persistence::Connection&, std::string_view kind,
                      std::string_view spec_json, const TriggerContext&);

}  // namespace starling::prospective
```

- [ ] **Step 2: 失败测试**

```cpp
// tests/cpp/test_trigger.cpp
#include "starling/prospective/trigger.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling::prospective;
using starling::persistence::SqliteAdapter;

TEST(Trigger, TimeFiresWhenDue) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    TriggerContext ctx{"2026-05-30T12:00:00Z", "", ""};
    EXPECT_TRUE(evaluate_trigger(c, "time", R"({"at":"2026-05-30T11:00:00Z"})", ctx));
    EXPECT_FALSE(evaluate_trigger(c, "time", R"({"at":"2026-05-30T13:00:00Z"})", ctx));
}
TEST(Trigger, EventMatchesType) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    TriggerContext ctx{"2026-05-30T12:00:00Z", "statement.written", "s1"};
    EXPECT_TRUE(evaluate_trigger(c, "event", R"({"event_type":"statement.written"})", ctx));
    EXPECT_FALSE(evaluate_trigger(c, "event", R"({"event_type":"cognizer.observed"})", ctx));
}
TEST(Trigger, CompoundAllOfShortCircuits) {
    auto a = SqliteAdapter::open(":memory:"); auto& c = a->connection();
    TriggerContext ctx{"2026-05-30T12:00:00Z", "statement.written", "s1"};
    // all_of: time(命中) + event(命中) → true
    EXPECT_TRUE(evaluate_trigger(c, "compound",
        R"({"all_of":[{"kind":"time","spec":{"at":"2026-05-30T11:00:00Z"}},{"kind":"event","spec":{"event_type":"statement.written"}}]})", ctx));
    // all_of: time(命中) + event(未命中) → false
    EXPECT_FALSE(evaluate_trigger(c, "compound",
        R"({"all_of":[{"kind":"time","spec":{"at":"2026-05-30T11:00:00Z"}},{"kind":"event","spec":{"event_type":"x"}}]})", ctx));
}
```

- [ ] **Step 3: CMake 注册** + **Step 4: 实现**

`evaluate_trigger` dispatch on kind:`time`→ 比较 `spec["at"]` 与 `ctx.now_iso`(字符串 ISO 可直接 `<=` 比较,字典序即时间序);`event`→ `spec["event_type"] == ctx.event_type`(可选 predicate 进一步匹配);`state`→ 按 `spec` 的 target/field/op/value 查 `conn`(P2.c 支持 statement 字段谓词:`SELECT EXISTS(SELECT 1 FROM statements WHERE <field> <op> <value>)`);`compound`→ 解析 `all_of`/`any_of` 数组,递归 `evaluate_trigger(conn, child.kind, child.spec.dump(), ctx)`,`all_of` 遇 false 即返回 false(短路),`any_of` 遇 true 即返回 true。`#include <nlohmann/json.hpp>`。

- [ ] **Step 5: 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -1 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R Trigger --output-on-failure 2>&1 | tail -8
git add include/starling/prospective/trigger.hpp src/prospective/trigger.cpp tests/cpp/test_trigger.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.c/prospective): Trigger 4 类评估 + compound 短路

spec §3.3/§6: time(at<=now) / event(event_type 匹配) / state(statement 谓词) /
compound(all_of/any_of 递归短路)。

EOF
)"
```

---

## Task 8: PolicyEngine.run_post_write（建 commitment + trigger + commitment.* 迁移）

**Files:**
- Create: `include/starling/prospective/policy_engine.hpp`, `src/prospective/policy_engine.cpp`, `tests/cpp/test_policy_engine_post_write.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §3.2 / §2(入口 1)。

- [ ] **Step 1: 头文件**

```cpp
// include/starling/prospective/policy_engine.hpp
#pragma once
#include "starling/prospective/commitment_engine.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::prospective {

struct PolicyTickStats { int fired = 0; int broken = 0; int auto_withdrawn = 0; };

class PolicyEngine {
public:
    explicit PolicyEngine(persistence::SqliteAdapter& a) : adapter_(a), commitment_engine_(a) {}
    // 入口1 (SubscriberPump 调): 消费 statement.written(COMMITS→建 commitment+注册 trigger;
    //   评估 event/state trigger) + commitment.fulfilled/withdrawn(→ 状态迁移)。checkpoint 驱动。
    void run_post_write(persistence::Connection&, std::string_view now_iso);
    // 入口2 (runtime 调): TimeTrigger 到期 fire + deadline 过期 → BROKEN/auto-withdrawn。
    PolicyTickStats tick(persistence::Connection&, std::string_view now_iso);
    persistence::Connection& connection() { return adapter_.connection(); }
private:
    persistence::SqliteAdapter& adapter_;
    CommitmentEngine commitment_engine_;
};

}  // namespace starling::prospective
```

- [ ] **Step 2: 失败测试**

```cpp
// tests/cpp/test_policy_engine_post_write.cpp — 写 COMMITS statement + statement.written 事件 →
//   run_post_write → commitments 行 ACTIVE + commitment.active_holding 事件。
//   (用 OutboxWriter 造 statement.written 事件 + seed COMMITS statement;构造同 test_commitment_engine)
//   断言: commitments WHERE stmt_id state='ACTIVE';commitment_triggers 有 time trigger(若 deadline)。
```

> 实现注:`run_post_write` 用独立 checkpoint(`policy_engine_checkpoint`,需在某 migration 建或复用一张 checkpoint 表;简化:本期用 `SELECT bus_events WHERE outbox_sequence > checkpoint`,checkpoint 存 `commitment_triggers` 之外的小表或一个 `policy_engine_state(id PK, checkpoint)` 表——在 0019 迁移里附带建 `policy_engine_state`)。处理:`statement.written` 且该 stmt modality='COMMITS' → `commitment_engine_.create_from_statement`(deadline 取 statement.event_time_end 或 observed_at);注册 `TimeTrigger(at=deadline)` 进 commitment_triggers。`commitment.fulfilled` → `commitment_engine_.fulfill`;`commitment.withdrawn` → `withdraw`。event/state trigger:对 armed trigger 调 `evaluate_trigger`,命中 → emit `commitment.fire` + status='fired'。**checkpoint 表**:在 migration 0019 末尾加 `CREATE TABLE policy_engine_checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER NOT NULL DEFAULT 0); INSERT INTO policy_engine_checkpoint(id,seq) VALUES(1,0);`(plan Task 2 补该表)。

- [ ] **Step 3: CMake 注册 + 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -1 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R PolicyEnginePostWrite --output-on-failure 2>&1 | tail -8
git add include/starling/prospective/policy_engine.hpp src/prospective/policy_engine.cpp tests/cpp/test_policy_engine_post_write.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.c/prospective): PolicyEngine.run_post_write 入口

spec §3.2: 消费 statement.written(COMMITS→建 commitment + 注册 trigger + 评估
event/state trigger → commitment.fire) + commitment.fulfilled/withdrawn 迁移。
checkpoint 驱动 (policy_engine_checkpoint)。

EOF
)"
```

---

## Task 9: PolicyEngine.tick（TimeTrigger fire + deadline 过期）

**Files:**
- Modify: `src/prospective/policy_engine.cpp`
- Create: `tests/cpp/test_policy_engine_tick.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §3.2 / §2(入口 2)/ §5。

- [ ] **Step 1: 失败测试**

```cpp
// tests/cpp/test_policy_engine_tick.cpp
// 1) TimeTrigger 到期: 建 ACTIVE commitment + armed time trigger(at 过去) → tick(now) →
//    commitment.fire 事件 + trigger status='fired'。
// 2) deadline 过期: ACTIVE commitment deadline<now, broken_count<3 → tick → state='BROKEN' + commitment.broken。
```

- [ ] **Step 2: 实现 tick**

`tick(now)`：
1. TimeTrigger:`SELECT t.id, t.commitment_stmt_id, t.spec_json FROM commitment_triggers t JOIN commitments c ON c.stmt_id=t.commitment_stmt_id WHERE t.kind='time' AND t.status='armed' AND c.state='ACTIVE'`;对每条 `evaluate_trigger(conn,"time",spec,ctx{now})` 命中 → emit `commitment.fire` + UPDATE status='fired';`stats.fired++`。
2. deadline 过期:`SELECT stmt_id FROM commitments WHERE state='ACTIVE' AND deadline IS NOT NULL AND deadline <= now`;对每条 `commitment_engine_.on_deadline_expired(conn, stmt_id, now)`;按结果 `stats.broken++`/`auto_withdrawn++`(可查 state 判定)。
先收集再写(不嵌套 cursor)。

- [ ] **Step 3: CMake 注册 + 跑 + Commit**

```bash
cmake --build build 2>&1 | tail -2
ctest --test-dir build -R PolicyEngineTick --output-on-failure 2>&1 | tail -8
git add src/prospective/policy_engine.cpp tests/cpp/test_policy_engine_tick.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.c/prospective): PolicyEngine.tick — TimeTrigger fire + deadline 过期

spec §3.2/§5: tick 轮询 armed TimeTrigger(命中→commitment.fire)+ ACTIVE
deadline 过期(→ on_deadline_expired:BROKEN/auto-withdrawn)。先收集再写。

EOF
)"
```

---

## Task 10: op_decay 反向保护 SQL EXISTS（TC-A9-001/002/003 CRITICAL）

**Files:**
- Modify: `src/replay/consolidation_ops.cpp`
- Create: `tests/cpp/test_commitment_protection_decay.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §7。**红线:只改 `active_grounded` 赋值,不动 op_decay 其余逻辑;M0.8 decay 测试回归。**

- [ ] **Step 1: 失败测试（含 3 个 CRITICAL）**

```cpp
// tests/cpp/test_commitment_protection_decay.cpp
#include "starling/replay/consolidation_ops.hpp"
#include "starling/prospective/commitment_engine.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling;
// seed_commits_stmt + helpers 同 test_commitment_engine;另需把 stmt 置 consolidated + S(t)<0.05 可衰减
// (seed 时 consolidation_state='consolidated', salience 低 / last_accessed 久远使 compute_s_t<0.05)

// TC-A9-001 [CRITICAL]: ACTIVE commitment 保护 → decay 不 ARCHIVE
TEST(CommitmentProtectionDecay, ActiveHoldingPreventsArchive) {
    auto a = persistence::SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_decayable_commits(c.raw(), "c1");  // consolidated + 可衰减
    prospective::CommitmentEngine(*a).create_from_statement(c, "c1", "default", "", "2026-05-30T10:00:00Z");  // ACTIVE + 保护
    replay::op_decay(c, {"c1"}, "default", "2027-01-01T00:00:00Z");  // 远期 → S(t)<0.05
    EXPECT_EQ(scol(c.raw(), "SELECT consolidation_state FROM statements WHERE id='c1'"), "consolidated");  // 未 ARCHIVE
}

// TC-A9-002 [CRITICAL]: terminal → 保护解除 → decay ARCHIVE
TEST(CommitmentProtectionDecay, TerminalReleasesProtection) {
    auto a = persistence::SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_decayable_commits(c.raw(), "c1");
    prospective::CommitmentEngine eng(*a);
    eng.create_from_statement(c, "c1", "default", "", "2026-05-30T10:00:00Z");
    eng.fulfill(c, "c1", "2026-05-30T11:00:00Z");  // → FULFILLED (state≠ACTIVE)
    replay::op_decay(c, {"c1"}, "default", "2027-01-01T00:00:00Z");
    EXPECT_EQ(scol(c.raw(), "SELECT consolidation_state FROM statements WHERE id='c1'"), "archived");  // 已 ARCHIVE
}

// TC-A9-003 [CRITICAL]: 新实例/重启后保护 durable
TEST(CommitmentProtectionDecay, ProtectionDurableAcrossNewInstance) {
    auto a = persistence::SqliteAdapter::open(":memory:"); auto& c = a->connection();
    seed_decayable_commits(c.raw(), "c1");
    prospective::CommitmentEngine(*a).create_from_statement(c, "c1", "default", "", "2026-05-30T10:00:00Z");
    // 模拟"重启": 不重建任何 in-memory 状态,直接用同 conn 跑 decay(保护全在 SQL)
    // (真重启语义: 新 CommitmentEngine/PolicyEngine 实例不携带状态; 保护来自 commitments+commitment_protection 表)
    prospective::CommitmentEngine fresh_engine(*a);  // 新实例,无 in-memory set
    (void)fresh_engine;
    replay::op_decay(c, {"c1"}, "default", "2027-01-01T00:00:00Z");
    EXPECT_EQ(scol(c.raw(), "SELECT consolidation_state FROM statements WHERE id='c1'"), "consolidated");  // 仍保护
}
```

> `seed_decayable_commits`:seed COMMITS statement,`consolidation_state='consolidated'`,`salience` 低 + `last_accessed` 久远,使 `compute_s_t(now=2027)` < 0.05。`scol`/helpers 同前。

- [ ] **Step 2: 实现（consolidation_ops.cpp 的 op_decay）**

把 `in.active_grounded = false;`(约 line 114)替换为 SQL EXISTS 保护查询:
```cpp
// active_grounded: 受 ACTIVE commitment 反向保护 (P2.c §7) → 不衰减
{
    sqlite3_stmt* pst = nullptr;
    const char* psql =
        "SELECT EXISTS(SELECT 1 FROM commitment_protection cp "
        " JOIN commitments c ON c.stmt_id = cp.commitment_stmt_id "
        " WHERE cp.protected_stmt_id = ?1 AND c.state = 'ACTIVE')";
    if (sqlite3_prepare_v2(db, psql, -1, &pst, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "op_decay: prepare protection EXISTS");
    StmtHandle hp(pst);
    bind_sv(hp.get(), 1, id);
    in.active_grounded = (sqlite3_step(hp.get()) == SQLITE_ROW && sqlite3_column_int(hp.get(), 0) == 1);
}
```
（其余 op_decay 逻辑不动:`if (state != "consolidated") continue;` 与 `compute_s_t<0.05 && !in.active_grounded` 保持。）

- [ ] **Step 3: CMake 注册 + 跑 + 回归 + Commit**

```bash
cmake --build build 2>&1 | tail -2
ctest --test-dir build -R "CommitmentProtectionDecay|Decay|Consolidation" --output-on-failure 2>&1 | tail -12
git add src/replay/consolidation_ops.cpp tests/cpp/test_commitment_protection_decay.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.c/replay): op_decay active_holding 反向保护 — TC-A9-001/002/003 CRITICAL

spec §7: active_grounded 从硬编码 false 改为 SQL EXISTS(commitment_protection
JOIN commitments state='ACTIVE')。§16.3-8 TC-A9-001(ACTIVE 不archive)+
TC-A9-002(terminal 解除)+ TC-A9-003(新实例/重启 durable)。M0.8 decay 回归通过。

EOF
)"
```

---

## Task 11: AffectVector → 优先级重放权重

**Files:**
- Modify: `src/replay/replay_scheduler.cpp`
- Create: `tests/cpp/test_affect_replay_weight.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §8。**写路径零改动,采样时算。**

- [ ] **Step 1: 失败测试**

```cpp
// tests/cpp/test_affect_replay_weight.cpp
// seed 两条 consolidated statement: high affect_json(高 salience/arousal) vs low({})。
// 跑 ReplayScheduler 的采样(run_idle/run_sleep 或暴露的采样入口)→ 高 affect 的 sample_weight 更大 /
// 优先被采。最小可测: 验证 high-affect statement 进入 replay_ledger / 被选中,low 的不被选(或权重低)。
// (依采样入口的实际可观测产物断言;若采样不直接可观测,改测一个暴露的 helper 计算 weight)
```

> 实现注:`replay_scheduler.cpp` 构造 `SamplerInputs` 处(约 line 128-146,现 `r.salience=column`,line 131-132 `r.affect_arousal=0.0`):解析 `affect_json` → `affect::AffectVector` → 若 affect_json 非 `{}`/有效:`r.salience = affect::salience(av)`(覆盖 column),`r.affect_arousal = av.arousal`;否则保持 column salience + arousal=0。`#include "starling/affect/affect_vector.hpp"`。`sample_weight` 公式已用 `in.salience` + `(1+arousal_bonus·affect_arousal)`,喂真值即激活。

- [ ] **Step 2: 实现 + CMake 注册 + 跑 + 回归 + Commit**

```bash
cmake --build build 2>&1 | tail -2
ctest --test-dir build -R "AffectReplayWeight|Replay|Swr" --output-on-failure 2>&1 | tail -10
git add src/replay/replay_scheduler.cpp tests/cpp/test_affect_replay_weight.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.c/replay): AffectVector 驱动优先级重放权重

spec §8: ReplayScheduler 构造 SamplerInputs 时解析 affect_json → AffectVector →
salience()/arousal 喂 sample_weight(现硬编码 0)。高 affect 优先采样。写路径零改动,
M0.8 replay 回归通过。

EOF
)"
```

---

## Task 12: SubscriberPump 第 6 subscriber — policy_engine

**Files:**
- Modify: `src/bus/subscriber_pump.cpp`
- Create: `tests/cpp/test_policy_engine_subscriber.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §2 / §3.2。**红线:不 regress 前 5 subscriber;SAVEPOINT 隔离。**

- [ ] **Step 1: 失败测试**

```cpp
// tests/cpp/test_policy_engine_subscriber.cpp
// 写一条 COMMITS statement 经 Bus.write(走完整 SubscriberPump)→ commitments 行 ACTIVE。
// 同时断言 belief_tracker/projection 等既有 subscriber 仍工作(不 regress)。
```

- [ ] **Step 2: 实现（subscriber_pump.cpp run_post_write 末尾加第 6 个）**

在 `run_isolated(conn, "replay_online", ...)` 之后追加:
```cpp
run_isolated(conn, "policy_engine", [&]{
    prospective::PolicyEngine(adapter_).run_post_write(conn, now_iso);
});
```
`#include "starling/prospective/policy_engine.hpp"`。**不改前 5 个 run_isolated。**

- [ ] **Step 3: 跑 + 回归 + Commit**

```bash
cmake --build build 2>&1 | tail -2
ctest --test-dir build -R "PolicyEngineSubscriber|SubscriberPump" --output-on-failure 2>&1 | tail -8
ctest --test-dir build 2>&1 | grep -E "tests passed|failed"
git add src/bus/subscriber_pump.cpp tests/cpp/test_policy_engine_subscriber.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.c/bus): SubscriberPump 第 6 subscriber policy_engine

spec §2: run_post_write 末尾 SAVEPOINT 隔离调 PolicyEngine.run_post_write。
不 regress 前 5 subscriber(conflict_key/belief_tracker/reconsolidation/projection/
replay_online)。

EOF
)"
```

---

## Task 13: pybind bindings + Python wrappers

**Files:**
- Modify: `bindings/python/module.cpp`
- Create: `python/starling/prospective/__init__.py`, `python/starling/affect/__init__.py`
- Create: `tests/python/test_p2c_bindings.py`

**Spec ref:** §3(Python 暴露)。

- [ ] **Step 1: 暴露类**

`bindings/python/module.cpp` 追加（include 4 个新 header）:
- `affect::AffectVector`(def_readwrite 五维)+ `affect::salience`(自由函数 `m.def("affect_salience", ...)`)+ `affect::parse_affect_json`。
- `prospective::ActionGuard`(def_readwrite 三字段)+ `GuardVerdict` enum + `m.def("action_guard_check", ...)`。
- `prospective::CommitmentEngine`(init adapter& + `create_from_statement`/`fulfill`/`withdraw`/`on_deadline_expired`/`renegotiate`,conn-free lambda 用 `s.connection()`)。
- `prospective::PolicyEngine`(init adapter& + `run_post_write`/`tick`,conn-free)。
单 adapter& 引用成员不需 keep_alive(adapter 由 runtime 持有;若按值无所谓)。conn-free lambda 同 M0.8/M0.9 模式。

- [ ] **Step 2: Python 便利包**（`python/starling/{prospective,affect}/__init__.py` re-export `_core` 对应符号,mirror `python/starling/replay/__init__.py`)

- [ ] **Step 3: 刷新 + smoke + Commit**

```bash
cmake --build build 2>&1 | tail -3
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages 2>&1 | tail -1
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
python -c "from starling import _core; print(hasattr(_core,'CommitmentEngine'), hasattr(_core,'PolicyEngine'), hasattr(_core,'AffectVector'))"
pytest tests/python/test_p2c_bindings.py -v 2>&1 | tail -6
git add bindings/python/module.cpp python/starling/prospective python/starling/affect tests/python/test_p2c_bindings.py
git commit -m "$(cat <<'EOF'
feat(P2.c): pybind bindings — Commitment/PolicyEngine/AffectVector/ActionGuard

暴露 CommitmentEngine / PolicyEngine(conn-free)+ AffectVector/salience +
ActionGuard/check 给 Python。

EOF
)"
```

> `test_p2c_bindings.py`:`for n in ["CommitmentEngine","PolicyEngine","AffectVector","ActionGuard"]: assert hasattr(_core,n)` + 构造 AffectVector/ActionGuard。

---

## Task 14: Python 集成 — commitment 生命周期端到端

**Files:**
- Create: `tests/python/test_p2c_commitment_lifecycle.py`

**Spec ref:** §11。

- [ ] **Step 1: 端到端测试**

```python
"""P2.c 端到端: COMMITS statement → ACTIVE → 保护 → fulfill/break。"""
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


def _seed_commits(rt, sid):  # modality=COMMITS, consolidated
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
            "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
            "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
            "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid,"default","alice","first_person","cognizer","bob","will_send","str","report",
             "a"*64,"v1","COMMITS","pos",0.9,"2026-05-30T09:00:00Z",0.5,"{}",0.0,
             "2026-05-30T09:00:00Z","user_input","consolidated","approved",
             "2026-05-30T09:00:00Z","2026-05-30T09:00:00Z"))
        c.commit()


def test_commitment_lifecycle(rt):
    _seed_commits(rt, "c1")
    eng = _core.CommitmentEngine(rt.adapter)
    eng.create_from_statement("c1", "default", "2026-05-30T18:00:00Z", "2026-05-30T10:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        assert c.execute("SELECT state FROM commitments WHERE stmt_id='c1'").fetchone()[0] == "ACTIVE"
        assert c.execute("SELECT COUNT(*) FROM commitment_protection WHERE protected_stmt_id='c1'").fetchone()[0] == 1
    eng.fulfill("c1", "2026-05-30T11:00:00Z")
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        assert c.execute("SELECT state FROM commitments WHERE stmt_id='c1'").fetchone()[0] == "FULFILLED"
```

- [ ] **Step 2: 跑 + Commit**

```bash
pytest tests/python/test_p2c_commitment_lifecycle.py -v 2>&1 | tail -6
git add tests/python/test_p2c_commitment_lifecycle.py
git commit -m "$(cat <<'EOF'
test(P2.c): commitment 生命周期端到端 (create→ACTIVE→保护→fulfill)

spec §11: 经 binding 验证五态机 + active_holding 保护落库。

EOF
)"
```

---

## Task 15: 回归确认（M0.8 + M0.9 + P2.a 全绿）

**Files:** 无。

- [ ] **Step 1: 全 guard**

```bash
cmake --build build 2>&1 | tail -2
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages 2>&1 | tail -1
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
ctest --test-dir build 2>&1 | grep -E "tests passed|failed"
pytest tests/python -q 2>&1 | tail -2
python scripts/ci_static_scan.py 2>&1 | tail -1
```
Expected: ctest 全绿(456 + P2.c 新增);pytest 480+ passed + 13 skipped(+ P2.c);ci_static_scan OK。**特别确认:`pytest tests/python/test_tc_new_conflict_severe.py`(§16.3-9)+ M0.8 decay 相关 C++ 测试。** 任何 RED 回对应 task 修复。

---

## Task 16: Milestone close — roadmap flip + final review + merge

**Files:**
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md`
- After merge: commit plan-doc 到 main

- [ ] **Step 1: 识别最后 work commit** `git log --oneline main..HEAD | head`,记 topmost(非 roadmap-flip)SHA。
- [ ] **Step 2: flip roadmap** —— P2.c 行(第 73 行)标 ✅ + 链接 plan;状态表加 `P2.c | 已写 | ✅ 完成 | 日期 | <SHA>`(P2 全部完成)。
- [ ] **Step 3: commit roadmap flip**

```bash
git add docs/superpowers/plans/2026-05-23-roadmap.md
git commit -m "$(cat <<'EOF'
chore(P2.c): mark prospective-affect complete in roadmap

P2.c 完成: CommitmentEngine 五态机 + PolicyEngine + Trigger + active_holding
保护 + AffectVector replay-weight + ActionGuard。P2 全部完成(P2.a/P2.b/P2.c)。
pin 最后 work commit。下一步 P3。

EOF
)"
```

- [ ] **Step 4: worktree 全绿**（同 Task 15）。
- [ ] **Step 5: 派发整分支 final reviewer**（Controller-only,`feature-dev:code-reviewer`)。Scrutiny:五态机迁移正确性(broken_count/链长守护)、op_decay 保护 EXISTS(不误archive/不漏保护 + M0.8 decay 不regress)、SubscriberPump 第6 subscriber 不regress前5、AffectVector 公式对拍、PolicyEngine checkpoint 幂等、5 CRITICAL、回归零破坏。
- [ ] **Step 6: AskUserQuestion 合并 consent**（Controller-only)。
- [ ] **Step 7: 若 consent=merge,从 main --no-ff 合并**（合并前 `git -C <root> status` 检查 root 工作树无 stray;merge 用 `git -C <root> merge --no-ff worktree-p2-c-prospective-affect`,counts 替换实际)。
- [ ] **Step 8: commit plan-doc 到 main**（cp worktree plan → root docs/ + commit）。
- [ ] **Step 9: post-merge 全绿**（root 重建 + reinstall + ctest + pytest + scan)。
- [ ] **Step 10: 拆 worktree**（`git worktree remove --force` + `git branch -D` + `git worktree list` 仅 main)。
- [ ] **Step 11: final report**（merge SHA / last work commit / counts / 5 CRITICAL 状态 / P2 全完成 / 下一步 P3)。

---

## Self-Review（writing-plans 要求）

**1. Spec coverage:** §3.1 CommitmentEngine→T6;§3.2 PolicyEngine→T8/T9;§3.3 Trigger→T7;§3.4 AffectVector→T4;§3.5 ActionGuard→T5;§4 schema→T1/T2/T3;§5 五态机→T6;§6 Trigger→T7;§7 保护→T10;§8 AffectVector replay-weight→T11;§9 ActionGuard→T5;§11 测试→各 task + T14;5 CRITICAL→T6(A2-001/002)+T10(A9-001/002/003);SubscriberPump 集成→T12。无遗漏。

**2. Placeholder scan:** 纯计算/迁移 task 给全代码;集成 task(T8/T9/T10/T11/T12)给 header + 关键 SQL + 实现注 + 测试意图,余下让 implementer 按 header + 既有 helper 写出(subagent-driven 预期)。无 TBD/TODO。

**3. Type consistency:** `CommitmentEngine` 方法签名(create_from_statement/fulfill/withdraw/on_deadline_expired/renegotiate)T6 定义、T8/T9/T14 复用一致;`PolicyEngine`(run_post_write/tick)T8/T9/T12 一致;`AffectVector`/`salience`/`parse_affect_json` T4 定义、T11 复用;`evaluate_trigger` T7 定义、T8/T9 复用;`op_decay` 签名不变(只改内部 active_grounded)。

**补充(实现依赖,implementer 注意):**
- **`policy_engine_checkpoint` 表**:T8 的 run_post_write 用 checkpoint 消费 bus_events。该表须在 **migration 0019**(Task 2)末尾附带建:`CREATE TABLE policy_engine_checkpoint(id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER NOT NULL DEFAULT 0); INSERT INTO policy_engine_checkpoint(id,seq) VALUES(1,0);`。Task 2 实现时一并加。
- **trust_priors 下调**(auto_withdrawn):cognizer_hub 下调公式 §8.3 本期可留 emit `commitment.auto_withdrawn` 事件为准 + 注释 stub(完整下调接口留后续),不阻塞 TC-A2-001(测试只断言 state=WITHDRAWN + auto_withdrawn 事件)。

---

## 元数据

- **里程碑**:P2.c(前瞻与情感)
- **依赖**:P2.b close(M0.9 merge `d47fcae`,main `5f271f2` + spec)
- **后继**:P3(ActionPolicyGraph / tool 执行 / Affect Buffer 写时 / Working Set 渲染)
- **分支**:worktree-p2-c-prospective-affect,--no-ff 合并 main
- **Task 数**:17(Task 0–16)

