# P2.j 社会域接线（CanonicalScope 七元组 + CommonGround grounding）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把社会域 scope（Commitment/Norm/CommonGround）接进冲突键七元组，并让 CommonGround grounding 协议在生产路径真实跑通（assert→acknowledge→grounded），使 `perspective_take` 返回真实 common ground。关闭 codex review 两条 High（#2 CommonGround 占位、#3 CanonicalScope 占位）。

**Architecture:** 新增 `statements.scope_parties_json`（独立于 `perceived_by`，migration 0022）作 grounding 群体；`scope_of()` 按 modality + scope_parties 分支 → 3 臂 `canonical_bytes` 入冲突键第 7 元；新 `CommonGroundSubscriber` 接进 `SubscriberPump`，消费 `statement.written` 触发 assert/acknowledge/repair/co-presence/timeout + 容器 rebuild；`common_ground::query()` 真读表使 `perspective_take` 返回真实 cg。`interlocutor` 显式串入 `Memory.remember`/`Extractor.run`。

**Tech Stack:** C++20 core（tom/ + bus/ + extractor 数据模型 + binding，worktree + cmake 重建）+ pybind11 + Python 3.14；ctest + pytest + `scripts/ci_static_scan.py`；migration 0022（CMake glob 自动发现）。

**Spec:** `docs/superpowers/specs/2026-06-06-p2-j-social-scope-wiring-design.md`（commit b2f2721）。

**执行位置：** 改 C++ → **worktree 隔离 + cmake 重建**。编译 recipe（记忆 worktree-cpp-editable-build-recipe）：`python3.14 -m venv .venv && source .venv/bin/activate && pip install -q cmake==4.3.2 ninja scikit-build-core pybind11 && pip install -e ".[dev,dashboard]" --no-build-isolation --config-settings=build-dir=build`。改 C++/绑定/migration 后刷新 `_core`：`cmake --build build && cmake --install build --prefix .venv/lib/python3.14/site-packages`。每 Task commit 本地；push/merge main 需显式 consent。baseline：ctest 493 / pytest 536(+13 skip) / ci_static_scan 绿 / migration 最高 0021。

---

## 文件结构

**新建**
- `migrations/0022_scope_parties_and_cg_subscriber.sql` — statements.scope_parties_json + 不可变 trigger + common_ground.rounds_since_assert + common_ground_subscriber_checkpoint
- `include/starling/tom/common_ground_subscriber.hpp` + `src/tom/common_ground_subscriber.cpp` — CommonGroundSubscriber
- `tests/cpp/test_common_ground_subscriber.cpp` — 协议六路径

**修改**
- `include/starling/extractor/extracted_statement.hpp` — 加 `scope_parties`
- `src/bus/statement_writer.cpp` — INSERT 加 scope_parties_json
- `include/starling/extractor/extractor.hpp` + `src/extractor/extractor.cpp` — run() 加 interlocutor 形参 + 填 scope_parties/perceived_by
- `bindings/python/module.cpp` — Extractor.run 加 interlocutor arg；CommonGroundWriter 已绑（确认）；加人工 grounding 绑定
- `include/starling/bus/canonical_scope.hpp` + `src/bus/canonical_scope.cpp` — scope_of 分支 + 3 臂 canonical_bytes
- `src/bus/conflict_key_backfill.cpp` — stmt_proxy 读 scope_parties_json
- `python/starling/bus/canonical_scope.py` — Python scope_of 分支（parity）
- `src/bus/subscriber_pump.cpp` — 接 CommonGroundSubscriber（#7）
- `src/tom/common_ground.cpp` — query() 真读
- `python/starling/memory.py` + `python/starling/dashboard/engine.py` — remember(interlocutor=) 串线
- `tests/cpp/test_canonical_scope.cpp` — un-stub
- `tests/cpp/test_tom_engine_perspective.cpp` — un-stub
- `tests/cpp/test_conflict_key.cpp` + `tests/python/test_conflict_key.py` — 加 scope parity 用例
- `docs/superpowers/plans/2026-05-23-roadmap.md` — #2/#3 改「已接线 P2.j」

---

## Task 0: Baseline + worktree + 重建

**Files:** 无

- [ ] **Step 1: 建 worktree + venv + 全量构建 + baseline**

Run（主仓库 `/Users/jaredguo-mini/develop/memory/starling`）：
```bash
cd /Users/jaredguo-mini/develop/memory/starling
git worktree add .claude/worktrees/p2-j-social-scope -b worktree-p2-j-social-scope main
cd .claude/worktrees/p2-j-social-scope
python3.14 -m venv .venv && source .venv/bin/activate
pip install -q cmake==4.3.2 ninja scikit-build-core pybind11 2>&1 | tail -1
pip install -e ".[dev,dashboard]" --no-build-isolation --config-settings=build-dir=build 2>&1 | tail -3
ctest --test-dir build 2>&1 | grep -E "tests passed|failed"
python -m pytest -q 2>&1 | tail -2
python scripts/ci_static_scan.py
```
Expected: ctest `100% tests passed ... out of 493`；pytest `536 passed, 13 skipped`；scan `OK`。**后续所有命令在此 worktree + 其 .venv。** 无 commit。

---

## Task 1: Migration 0022 + 数据模型 + Extractor.run 串 interlocutor（C++ + 绑定 + 重建）

**Files:**
- Create: `migrations/0022_scope_parties_and_cg_subscriber.sql`
- Modify: `include/starling/extractor/extracted_statement.hpp`、`src/bus/statement_writer.cpp`、`include/starling/extractor/extractor.hpp`、`src/extractor/extractor.cpp`、`bindings/python/module.cpp`

- [ ] **Step 1: 写 migration 0022**

Create `migrations/0022_scope_parties_and_cg_subscriber.sql`：
```sql
-- P2.j 社会域接线：scope_parties（独立于 perceived_by 的 grounding 群体）+
-- CommonGroundSubscriber checkpoint + common_ground 轮次计数（#2 共同在场推定）。

-- 1. statements.scope_parties_json：grounding 参与方（sorted{self,interlocutor}），
--    可空；仅对话语境填。与 perceived_by_json（信息可见性）语义分离。
ALTER TABLE statements ADD COLUMN scope_parties_json TEXT;

-- 2. 不可变 trigger（沿用 0007 NULL-safe 模式）。
CREATE TRIGGER trg_statements_immutable_scope_parties_json
BEFORE UPDATE OF scope_parties_json ON statements
FOR EACH ROW
WHEN NEW.scope_parties_json IS NOT OLD.scope_parties_json
BEGIN
    SELECT RAISE(ABORT, 'immutable field: scope_parties_json may not be updated in-place; use statement.corrected + supersedes');
END;

-- 3. common_ground 轮次计数（#2 共同在场推定 N=3）。
ALTER TABLE common_ground ADD COLUMN rounds_since_assert INTEGER NOT NULL DEFAULT 0;

-- 4. CommonGroundSubscriber outbox checkpoint（singleton，仿 tom_belief_tracker_checkpoint）。
CREATE TABLE common_ground_subscriber_checkpoint (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0,
    last_updated_at TEXT NOT NULL
);
INSERT INTO common_ground_subscriber_checkpoint (id, last_processed_outbox_sequence, last_updated_at)
    VALUES (1, 0, '2026-06-06T00:00:00Z');
```
（注：`ALTER TABLE ADD COLUMN` 不能加 `NOT NULL` 无 default 的列，故 scope_parties_json 可空——符合设计「仅对话语境填」。）

- [ ] **Step 2: ExtractedStatement 加 scope_parties**

Modify `include/starling/extractor/extracted_statement.hpp`，在 `std::vector<std::string> perceived_by;` 行后加：
```cpp
    std::vector<std::string>     scope_parties;        // grounding 参与方（sorted{self,interlocutor}）；空=私有。独立于 perceived_by。
```

- [ ] **Step 3: StatementWriter 写 scope_parties_json**

Modify `src/bus/statement_writer.cpp`：
- INSERT 列表里 `perceived_by_json,` 后加 `scope_parties_json,`；VALUES 对应位置（`?, ?, ?, ?,` 那段 perceived_by 的 `?` 后）加一个 `?`。当前 INSERT 片段：
```
"  provenance, evidence_json, source_spans_json, perceived_by_json,"
```
改为：
```
"  provenance, evidence_json, source_spans_json, perceived_by_json, scope_parties_json,"
```
对应 VALUES 段 `"  ?, ?, ?, ?,"`（provenance/evidence/spans/perceived 那行）改为 `"  ?, ?, ?, ?, ?,"`。
- 绑定：在 `bind_sv(h.get(), i++, perc);`（perceived_by_json）后加：
```cpp
    if (s.scope_parties.empty()) {
        sqlite3_bind_null(h.get(), i++);
    } else {
        const std::string sp_json = perceived_by_json(s.scope_parties);  // 复用 JSON-array-of-strings 序列化
        bind_sv(h.get(), i++, sp_json);
    }
```
（`perceived_by_json(const std::vector<std::string>&)` helper 已在本文件，复用即可。注意 `sp_json` 生命周期：`bind_sv` 用 SQLITE_TRANSIENT 还是 STATIC？若 STATIC，需保证 sp_json 活到 step；为安全把声明提到 step 之前的作用域。implementer 核对 bind_sv 的 text 拷贝语义；若非 TRANSIENT，用一个外层 `std::string sp_json;` 在 if 外声明。）

- [ ] **Step 4: Extractor.run 加 interlocutor 形参 + 填字段**

Modify `include/starling/extractor/extractor.hpp` 的 `run` 声明，末尾加一个默认参数：
```cpp
    ExtractionRunResult run(
        std::string_view                        engram_ref_id,
        const std::vector<std::uint8_t>&        payload_bytes,
        std::string_view                        holder_id,
        std::string_view                        holder_tenant_id,
        const ExistingRefMap&                   existing_ref_map,
        std::string_view                        interlocutor = "");
```
Modify `src/extractor/extractor.cpp` 的 `run` 定义签名同步加 `std::string_view interlocutor`（去掉 `= ""`，定义不重复默认值）。在 statement 写入循环（现 1064-1073）的 `perceived_by` 填充处改为：
```cpp
        for (auto& stmt : parsed.statements) {
            stmt.holder_id        = std::string(holder_id);
            stmt.holder_tenant_id = std::string(holder_tenant_id);
            stmt.chunk_index      = chunk_index;
            if (stmt.source_hash.empty()) {
                stmt.source_hash = "chunk-" + std::to_string(chunk_index);
            }
            if (!interlocutor.empty()) {
                // 对话语境：grounding 参与方 + 可见性都含 self+interlocutor（#2 前提 perceived_by⊇parties）。
                std::vector<std::string> pair{std::string(holder_id), std::string(interlocutor)};
                std::sort(pair.begin(), pair.end());
                stmt.scope_parties = pair;
                if (stmt.perceived_by.empty()) stmt.perceived_by = pair;
            } else if (stmt.perceived_by.empty()) {
                stmt.perceived_by = {std::string(holder_id)};
            }
```
（确保 `#include <algorithm>` 在 extractor.cpp。`scope_parties` 仅在 interlocutor 非空时填；否则保持空→scope Null。）

- [ ] **Step 5: 绑定 Extractor.run 加 interlocutor arg**

Modify `bindings/python/module.cpp` 的 `Extractor` `.def("run", ...)` lambda（现 1104-1119）：lambda 加 `const std::string& interlocutor` 末参 + 透传 + `py::arg("interlocutor") = ""`：
```cpp
        .def("run",
             [](starling::extractor::Extractor& self,
                const std::string& engram_ref_id,
                py::bytes payload,
                const std::string& holder_id,
                const std::string& holder_tenant_id,
                const std::map<std::string, std::string>& existing_ref_map,
                const std::string& interlocutor) {
                 std::string s = payload;
                 std::vector<std::uint8_t> v(s.begin(), s.end());
                 return self.run(engram_ref_id, v, holder_id, holder_tenant_id, existing_ref_map, interlocutor);
             },
             py::arg("engram_ref_id"),
             py::arg("payload_bytes"),
             py::arg("holder_id"),
             py::arg("holder_tenant_id"),
             py::arg("existing_ref_map"),
             py::arg("interlocutor") = "");
```

- [ ] **Step 6: 重建 + 校验 migration + 字段**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope && source .venv/bin/activate
cmake --build build 2>&1 | tail -4
cmake --install build --prefix .venv/lib/python3.14/site-packages 2>&1 | tail -1
ctest --test-dir build 2>&1 | grep -E "tests passed|failed"
python -c "
import tempfile, sqlite3
from starling import _core, runtime
db=tempfile.mktemp(suffix='.db'); rt=runtime._build_local_store_sqlite_runtime
import starling.runtime as R; R.relax_preflight_for_embedded()
r=R._build_local_store_sqlite_runtime(__import__('pathlib').Path(db)); r.start()
c=sqlite3.connect(db)
cols=[x[1] for x in c.execute('PRAGMA table_info(statements)')]
assert 'scope_parties_json' in cols, cols
cg=[x[1] for x in c.execute('PRAGMA table_info(common_ground)')]
assert 'rounds_since_assert' in cg, cg
assert c.execute(\"SELECT count(*) FROM common_ground_subscriber_checkpoint\").fetchone()[0]==1
print('migration 0022 ok')
"
ls migrations/ | tail -1
```
Expected: build 成功；ctest 仍 493（数据模型新增不破老测试）；`migration 0022 ok`；migrations 末尾 `0022_scope_parties_and_cg_subscriber.sql`。

- [ ] **Step 7: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope
git add migrations/0022_scope_parties_and_cg_subscriber.sql include/starling/extractor/extracted_statement.hpp src/bus/statement_writer.cpp include/starling/extractor/extractor.hpp src/extractor/extractor.cpp bindings/python/module.cpp
git commit -F - <<'EOF'
feat(P2.j): migration 0022 scope_parties + Extractor.run 串 interlocutor

statements.scope_parties_json（grounding 参与方，独立于 perceived_by，不可变 trigger
沿用 0007）+ common_ground.rounds_since_assert（#2）+ common_ground_subscriber_checkpoint。
ExtractedStatement.scope_parties；StatementWriter 写该列；Extractor.run 加 interlocutor
形参，对话语境填 scope_parties=perceived_by=sorted{self,interlocutor}。绑定 run 加 interlocutor arg。

EOF
```

---

## Task 2: Memory.remember(interlocutor=) + DashboardEngine 串线（Python）

**Files:** Modify `python/starling/memory.py`、`python/starling/dashboard/engine.py`

- [ ] **Step 1: memory.py remember 加 interlocutor**

Modify `python/starling/memory.py` 的 `remember`（现 1158）签名 + run 调用：
```python
    def remember(self, text: str, *, holder: Optional[str] = None,
                 interlocutor: Optional[str] = None,
                 now: Optional[str] = None) -> RememberResult:
```
把 `r = ext.run(engram_ref, payload, holder, self._tenant, {})` 改为：
```python
        r = ext.run(engram_ref, payload, holder, self._tenant, {}, interlocutor or "")
```

- [ ] **Step 2: engine.py remember 加 interlocutor**

Modify `python/starling/dashboard/engine.py`：其 `remember`（约 138-144 区，find the def remember）加 `interlocutor: Optional[str] = None` kwarg，run 调用末尾加 `interlocutor or ""`：
```python
        r = _core.Extractor(self._conn, self.llm, EXTRACTION_PROMPT).run(engram_ref, payload, holder, self._tenant, {}, interlocutor or "")
```
（implementer：先 grep `def remember` in engine.py 确认签名 + Optional 已 import；没 import 则加 `from typing import Optional`。）

- [ ] **Step 3: 校验 + Commit**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope && source .venv/bin/activate
python -c "
import tempfile
from starling.memory import Memory, make_stub_llm
m=Memory.open(tempfile.mktemp(suffix='.db'), llm=make_stub_llm(default_response='[{\"holder\":\"self\",\"holder_perspective\":\"FIRST_PERSON\",\"subject\":\"Bob\",\"predicate\":\"responsible_for\",\"object\":\"auth\",\"modality\":\"BELIEVES\",\"polarity\":\"POS\",\"nesting_depth\":0}]'))
r=m.remember('Bob is responsible for auth.', interlocutor='bob')
print('remember w/ interlocutor:', r.outcome, len(r.statement_ids))
import sqlite3; c=sqlite3.connect(m._rt.adapter.db_path)
sp=c.execute('SELECT scope_parties_json FROM statements LIMIT 1').fetchone()
print('scope_parties_json:', sp[0])
"
python -m pytest -q 2>&1 | tail -2
```
Expected: `remember w/ interlocutor: accepted 1`；`scope_parties_json: ["bob","self"]`（sorted）；pytest 536+13（remember 加 kwarg 不破老测试）。
```bash
git add python/starling/memory.py python/starling/dashboard/engine.py
git commit -F - <<'EOF'
feat(P2.j): Memory.remember / DashboardEngine 串 interlocutor → scope_parties

remember(interlocutor=) 透传到 Extractor.run，对话语境下 Statement 写
scope_parties=sorted{self,interlocutor}（喂 CanonicalScope CommonGround 臂 + grounding 协议）。

EOF
```

---

## Task 3: CanonicalScope（scope_of 分支 + 3 臂 + backfill + Python parity + un-stub）（C++ + Python + 重建）

**Files:**
- Modify: `include/starling/bus/canonical_scope.hpp`、`src/bus/canonical_scope.cpp`、`src/bus/conflict_key_backfill.cpp`、`python/starling/bus/canonical_scope.py`、`tests/cpp/test_canonical_scope.cpp`、`tests/cpp/test_conflict_key.cpp`、`tests/python/test_conflict_key.py`

- [ ] **Step 1: canonical_scope.hpp 把 scope_of 改成 ExtractedStatement 具体重载**

Modify `include/starling/bus/canonical_scope.hpp`：
- 顶部加前向声明（避免重 include）：
```cpp
namespace starling::extractor { struct ExtractedStatement; }
```
- 把现有 `template <typename StmtT> CanonicalScope scope_of(const StmtT&) { return CanonicalScopeNull{}; }` **替换**为声明：
```cpp
// scope_of: derive the canonical scope from an ExtractedStatement (P2.j).
// modality 优先：COMMITS→Commitment；NORM_*→Norm；else scope_parties≥2→CommonGround；else Null。
CanonicalScope scope_of(const starling::extractor::ExtractedStatement& stmt);
```

- [ ] **Step 2: canonical_scope.cpp 实现 scope_of + 3 臂 canonical_bytes**

Modify `src/bus/canonical_scope.cpp`：includes 加：
```cpp
#include "starling/extractor/extracted_statement.hpp"
#include "starling/schema/statement_enums.hpp"
#include <algorithm>
```
三臂 `canonical_bytes` 替换 throw：
```cpp
std::string CanonicalScopeNorm::canonical_bytes() const {
    std::string out = kind;
    for (const auto& m : members_sorted) { out += '\x1f'; out += m; }
    return out;
}

std::string CanonicalScopeCommitment::canonical_bytes() const {
    return principal + '\x1f' + beneficiary;
}

std::string CanonicalScopeCommonGround::canonical_bytes() const {
    std::string out;
    bool first = true;
    for (const auto& p : parties_sorted) { if (!first) out += '\x1f'; out += p; first = false; }
    return out;
}
```
`canonical_scope_bytes` 不变。新增 `scope_of`：
```cpp
CanonicalScope scope_of(const starling::extractor::ExtractedStatement& stmt) {
    using M = schema::Modality;
    if (stmt.modality == M::COMMITS) {
        std::string beneficiary;
        for (const auto& p : stmt.scope_parties) {
            if (p != stmt.holder_id) { beneficiary = p; break; }
        }
        return CanonicalScopeCommitment{stmt.holder_id, beneficiary};
    }
    if (stmt.modality == M::NORM_OUGHT || stmt.modality == M::NORM_FORBID) {
        std::vector<std::string> members{stmt.holder_id, stmt.subject_id};
        std::sort(members.begin(), members.end());
        const std::string kind = (stmt.modality == M::NORM_OUGHT) ? "obligation" : "prohibition";
        return CanonicalScopeNorm{kind, members};
    }
    if (stmt.scope_parties.size() >= 2) {
        std::vector<std::string> parties = stmt.scope_parties;
        std::sort(parties.begin(), parties.end());
        return CanonicalScopeCommonGround{parties};
    }
    return CanonicalScopeNull{};
}
```

- [ ] **Step 3: conflict_key_backfill 读 scope_parties_json 进 proxy**

Modify `src/bus/conflict_key_backfill.cpp` 建 stmt_proxy 的 SELECT（现 144-150）：列表末尾加 `scope_parties_json`（成第 10 列，索引 9）：
```cpp
                const char* sql =
                    "SELECT holder_id, subject_kind, subject_id, predicate, "
                    "       canonical_object_hash, modality, "
                    "       valid_from, valid_to, event_time_start, "
                    "       scope_parties_json "
                    "FROM statements "
                    "WHERE id = ? AND tenant_id = ? "
                    "LIMIT 1";
```
在 `stmt_proxy.event_time_start = get_opt(8);` 后加（解析 JSON 数组 → vector<string>，用 nlohmann，文件顶部 `#include <nlohmann/json.hpp>`）：
```cpp
                    {
                        const std::string sp = get_text(9);
                        if (!sp.empty()) {
                            try {
                                auto arr = nlohmann::json::parse(sp);
                                if (arr.is_array())
                                    for (const auto& e : arr)
                                        if (e.is_string()) stmt_proxy.scope_parties.push_back(e.get<std::string>());
                            } catch (...) { /* 容错：坏 JSON 当无 scope */ }
                        }
                    }
```
（`get_text(9)` 对 NULL 返回 ""，故旧行无 scope_parties→空→Null→键不变。）

- [ ] **Step 4: Python scope_of 分支（parity）**

Modify `python/starling/bus/canonical_scope.py`（implementer 先 Read 全文确认 `CanonicalScope*` 类 + `canonical_scope_bytes` + `scope_of` 现状）。把 `scope_of(stmt)` 改成 mirror C++：
```python
def scope_of(stmt):
    mod = stmt.modality.name if hasattr(stmt.modality, 'name') else str(stmt.modality)
    parties = list(getattr(stmt, 'scope_parties', []) or [])
    holder = stmt.holder_id
    if mod == 'COMMITS':
        beneficiary = next((p for p in parties if p != holder), "")
        return CanonicalScopeCommitment(principal=holder, beneficiary=beneficiary)
    if mod in ('NORM_OUGHT', 'NORM_FORBID'):
        members = sorted([holder, stmt.subject_id])
        kind = 'obligation' if mod == 'NORM_OUGHT' else 'prohibition'
        return CanonicalScopeNorm(kind=kind, members_sorted=members)
    if len(parties) >= 2:
        return CanonicalScopeCommonGround(parties_sorted=sorted(parties))
    return CanonicalScopeNull()
```
并实现各 arm 的 `canonical_bytes`（mirror C++，`'\x1f'.join` 风格）：Norm=`kind` + `''.join('\x1f'+m ...)`；Commitment=`principal+'\x1f'+beneficiary`；CommonGround=`'\x1f'.join(parties_sorted)`；Null=`''`。implementer 按现有类形态补齐（dataclass 或普通类，照现有写法）。

- [ ] **Step 5: un-stub test_canonical_scope.cpp**

Replace `tests/cpp/test_canonical_scope.cpp` 的 stub 测试（现锁恒 Null）为 4 分支（保留 include + 框架）：
```cpp
#include "starling/bus/canonical_scope.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/schema/statement_enums.hpp"
#include <gtest/gtest.h>

using namespace starling;
using namespace starling::bus;

static extractor::ExtractedStatement base() {
    extractor::ExtractedStatement s;
    s.holder_id = "self"; s.subject_kind = "cognizer"; s.subject_id = "bob";
    s.predicate = "p"; s.modality = schema::Modality::BELIEVES;
    return s;
}

TEST(CanonicalScope, PlainBeliefIsNull) {
    auto s = base();
    EXPECT_TRUE(std::holds_alternative<CanonicalScopeNull>(scope_of(s)));
}
TEST(CanonicalScope, CommitsIsCommitment) {
    auto s = base(); s.modality = schema::Modality::COMMITS;
    s.scope_parties = {"bob", "self"};
    auto sc = scope_of(s);
    ASSERT_TRUE(std::holds_alternative<CanonicalScopeCommitment>(sc));
    EXPECT_EQ(std::get<CanonicalScopeCommitment>(sc).principal, "self");
    EXPECT_EQ(std::get<CanonicalScopeCommitment>(sc).beneficiary, "bob");
}
TEST(CanonicalScope, NormOughtIsNorm) {
    auto s = base(); s.modality = schema::Modality::NORM_OUGHT;
    auto sc = scope_of(s);
    ASSERT_TRUE(std::holds_alternative<CanonicalScopeNorm>(sc));
    EXPECT_EQ(std::get<CanonicalScopeNorm>(sc).kind, "obligation");
    EXPECT_FALSE(std::get<CanonicalScopeNorm>(sc).canonical_bytes().empty());
}
TEST(CanonicalScope, TwoPartiesIsCommonGround) {
    auto s = base(); s.scope_parties = {"self", "bob"};
    auto sc = scope_of(s);
    ASSERT_TRUE(std::holds_alternative<CanonicalScopeCommonGround>(sc));
    EXPECT_EQ(std::get<CanonicalScopeCommonGround>(sc).parties_sorted, (std::vector<std::string>{"bob","self"}));
}
TEST(CanonicalScope, DifferentPartiesDifferentBytes) {
    auto a = base(); a.scope_parties = {"self","bob"};
    auto b = base(); b.scope_parties = {"self","carol"};
    EXPECT_NE(canonical_scope_bytes(scope_of(a)), canonical_scope_bytes(scope_of(b)));
}
```
（implementer 核对 test_canonical_scope.cpp 原 include/框架对齐。）

- [ ] **Step 6: test_conflict_key 加 scope parity 用例**

`tests/cpp/test_conflict_key.cpp`：加一个 CommonGround scope 用例，打印其 hex：
```cpp
TEST(ConflictKey, ScopeParityFixtureHex) {
    auto s = make_parity_stmt();
    s.scope_parties = {"bob", "self"};   // → CommonGround scope
    auto hex = canonical_conflict_key_hex(s);
    std::cout << "SCOPE_PARITY_HEX=" << hex << std::endl;
    EXPECT_EQ(hex.size(), 64u);
    EXPECT_NE(hex, "128e262474462a27c39126dbfc4c3876cac63f6d11f53a0161a8b6c8b66f8790");  // 与无 scope 不同
}
```
`tests/python/test_conflict_key.py`：加镜像断言（implementer 跑 C++ 取 SCOPE_PARITY_HEX 粘进来）：
```python
SCOPE_PARITY_HEX = "REPLACE_WITH_CPP_SCOPE_OUTPUT"  # implementer: paste C++ ScopeParityFixtureHex stdout

def test_scope_parity_hex_matches_cpp():
    class S(ParityStmt):
        scope_parties = ["bob", "self"]
    assert SCOPE_PARITY_HEX != "REPLACE_WITH_CPP_SCOPE_OUTPUT", "paste C++ hex"
    assert canonical_conflict_key_hex(S()) == SCOPE_PARITY_HEX
```
（注：原 `PARITY_HEX`（BELIEVES，无 scope_parties）**必须不变**——scope=Null→""→键不变，证无回归。ParityStmt 加 `scope_parties` 类属性默认 `[]` 以免 getattr 缺失：在 `ParityStmt` 类体加 `scope_parties = []`。）

- [ ] **Step 7: 重建 + 测试 + parity**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope && source .venv/bin/activate
cmake --build build 2>&1 | tail -4 && cmake --install build --prefix .venv/lib/python3.14/site-packages 2>&1 | tail -1
ctest --test-dir build -R "CanonicalScope|ConflictKey" 2>&1 | tail -6
# 取 SCOPE_PARITY_HEX 粘进 test_conflict_key.py
ctest --test-dir build -R ScopeParityFixtureHex -V 2>&1 | grep SCOPE_PARITY_HEX
```
implementer：把上面打印的 SCOPE_PARITY_HEX 值粘进 `tests/python/test_conflict_key.py` 的 `SCOPE_PARITY_HEX`，再：
```bash
ctest --test-dir build 2>&1 | grep -E "tests passed|failed"
python -m pytest tests/python/test_conflict_key.py -q 2>&1 | tail -2
```
Expected: CanonicalScope 5 + ConflictKey 全 passed；原 `ParityFixtureHex`/`test_parity_hex_matches_cpp` 仍绿（PARITY_HEX 不变）；scope parity C++==Python；full ctest 全 passed。

- [ ] **Step 8: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope
git add include/starling/bus/canonical_scope.hpp src/bus/canonical_scope.cpp src/bus/conflict_key_backfill.cpp python/starling/bus/canonical_scope.py tests/cpp/test_canonical_scope.cpp tests/cpp/test_conflict_key.cpp tests/python/test_conflict_key.py
git commit -F - <<'EOF'
feat(P2.j): CanonicalScope scope_of 分支 + 3 臂 canonical_bytes（七元组带 scope）

scope_of 按 modality 分支（COMMITS→Commitment(holder,interlocutor)；NORM_*→Norm(kind,
sorted{holder,subject})；scope_parties≥2→CommonGround(sorted parties)；else Null）。
3 臂 canonical_bytes（\x1f 分隔）。backfill proxy 读 scope_parties_json。Python 镜像
保 C++/Python 冲突键 parity。un-stub test_canonical_scope；原 PARITY_HEX 不变（无 scope→键不变，无回归）。

EOF
```

---

## Task 4: CommonGroundSubscriber — assert/acknowledge/repair + 容器 rebuild + 接 SubscriberPump（C++ + 重建）

**Files:**
- Create: `include/starling/tom/common_ground_subscriber.hpp`、`src/tom/common_ground_subscriber.cpp`、`tests/cpp/test_common_ground_subscriber.cpp`
- Modify: `src/bus/subscriber_pump.cpp`、`CMakeLists.txt`/`tests/cpp/CMakeLists.txt`（新源 + 新测试注册）

- [ ] **Step 1: 写 common_ground_subscriber.hpp**

```cpp
#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/connection.hpp"
#include <string_view>

namespace starling::tom {

// Consumes statement.written events after Bus.write (via SubscriberPump) and
// drives the CommonGround grounding lifecycle: assert new dialogue statements
// (scope_parties>=2) into asserted_unack; acknowledge on same-proposition
// restatement by the other party (#1/#3); repair on opposite-polarity restatement;
// then rebuild the CommonGroundContainer projection. Co-presence(#2)/timeout are
// in Task 5. Own singleton checkpoint common_ground_subscriber_checkpoint.
class CommonGroundSubscriber {
public:
    static int tick_one_batch(persistence::SqliteAdapter& adapter,
                              persistence::Connection& conn,
                              std::string_view now_iso,
                              int batch_size = 100);
};

}  // namespace starling::tom
```

- [ ] **Step 2: 写 common_ground_subscriber.cpp**

实现要点（implementer 按 belief_tracker.cpp 的 checkpoint-consumer 模式 + CommonGroundWriter/Container 签名写全）：
```cpp
#include "starling/tom/common_ground_subscriber.hpp"
#include "starling/tom/common_ground_writer.hpp"
#include "starling/neocortex/common_ground_container.hpp"
#include "starling/persistence/sqlite_helpers.hpp"   // StmtHandle / bind_sv / make_sqlite_error（核对实际头）
#include <sqlite3.h>
#include <nlohmann/json.hpp>
#include <string>
#include <vector>

namespace starling::tom {
namespace {
std::string col(sqlite3_stmt* h, int i) {
    const char* t = reinterpret_cast<const char*>(sqlite3_column_text(h, i));
    return t ? t : "";
}
}  // namespace

int CommonGroundSubscriber::tick_one_batch(persistence::SqliteAdapter& adapter,
                                           persistence::Connection& conn,
                                           std::string_view now_iso,
                                           int batch_size) {
    sqlite3* db = conn.raw();
    // 1. read checkpoint
    int last_seq = 0;
    {
        sqlite3_stmt* raw=nullptr;
        sqlite3_prepare_v2(db,"SELECT last_processed_outbox_sequence FROM common_ground_subscriber_checkpoint WHERE id=1",-1,&raw,nullptr);
        persistence::StmtHandle h(raw);
        if (sqlite3_step(h.get())==SQLITE_ROW) last_seq=sqlite3_column_int(h.get(),0);
    }
    // 2. read statement.written events after checkpoint
    struct Ev { std::string stmt_id, tenant; int seq; };
    std::vector<Ev> evs;
    {
        sqlite3_stmt* raw=nullptr;
        sqlite3_prepare_v2(db,
            "SELECT primary_id, tenant_id, outbox_sequence FROM bus_events "
            "WHERE outbox_sequence > ? AND event_type='statement.written' "
            "ORDER BY outbox_sequence LIMIT ?",-1,&raw,nullptr);
        persistence::StmtHandle h(raw);
        sqlite3_bind_int(h.get(),1,last_seq);
        sqlite3_bind_int(h.get(),2,batch_size);
        while (sqlite3_step(h.get())==SQLITE_ROW)
            evs.push_back({col(h.get(),0), col(h.get(),1), sqlite3_column_int(h.get(),2)});
    }
    if (evs.empty()) return 0;

    CommonGroundWriter writer(adapter);
    neocortex::CommonGroundContainer container(adapter);
    int max_seq = last_seq;
    std::vector<std::string> rebuilt_refs;   // 去重 rebuild

    for (const auto& ev : evs) {
        max_seq = ev.seq;
        // load the new statement's proposition + scope_parties
        std::string holder, subject_id, predicate, hash, polarity, sp_json;
        {
            sqlite3_stmt* raw=nullptr;
            sqlite3_prepare_v2(db,
                "SELECT holder_id, subject_id, predicate, canonical_object_hash, polarity, "
                "       COALESCE(scope_parties_json,'') FROM statements WHERE id=? AND tenant_id=?",-1,&raw,nullptr);
            persistence::StmtHandle h(raw);
            persistence::bind_sv(h.get(),1,ev.stmt_id);
            persistence::bind_sv(h.get(),2,ev.tenant);
            if (sqlite3_step(h.get())!=SQLITE_ROW) continue;
            holder=col(h.get(),0); subject_id=col(h.get(),1); predicate=col(h.get(),2);
            hash=col(h.get(),3); polarity=col(h.get(),4); sp_json=col(h.get(),5);
        }
        std::vector<std::string> parties;
        if (!sp_json.empty()) { try { auto a=nlohmann::json::parse(sp_json); if(a.is_array()) for(auto&e:a) if(e.is_string()) parties.push_back(e.get<std::string>()); } catch(...){} }
        if (parties.size() < 2) continue;   // 非对话 Statement，跳过

        // match existing asserted_unack entries of same proposition (cg ⋈ statements)
        struct Match { std::string cg_id, asserter; std::string polarity; };
        std::vector<Match> matches;
        {
            sqlite3_stmt* raw=nullptr;
            sqlite3_prepare_v2(db,
                "SELECT cg.id, st.holder_id, st.polarity FROM common_ground cg "
                "JOIN statements st ON st.id=cg.statement_id AND st.tenant_id=cg.tenant_id "
                "WHERE cg.tenant_id=? AND cg.status='asserted_unack' "
                "  AND st.subject_id=? AND st.predicate=? AND st.canonical_object_hash=?",-1,&raw,nullptr);
            persistence::StmtHandle h(raw);
            persistence::bind_sv(h.get(),1,ev.tenant);
            persistence::bind_sv(h.get(),2,subject_id);
            persistence::bind_sv(h.get(),3,predicate);
            persistence::bind_sv(h.get(),4,hash);
            while (sqlite3_step(h.get())==SQLITE_ROW)
                matches.push_back({col(h.get(),0), col(h.get(),1), col(h.get(),2)});
        }

        bool handled = false;
        for (const auto& m : matches) {
            if (m.asserter == holder) continue;          // 同一方不算确认/repair
            if (m.polarity == polarity) writer.acknowledge(conn, m.cg_id, holder, now_iso);  // #1/#3 显式/重复
            else                        writer.repair(conn, m.cg_id, holder, now_iso);       // 矛盾
            handled = true;
        }
        if (!handled) {
            // 新命题 → assert（cg_ref = self::other 由 parties 推；这里 parties 已 sorted）
            writer.assert_(conn, ev.tenant, ev.stmt_id, parties, now_iso);
        }
        // cg_ref：两方 sorted → "a::b"
        if (parties.size()>=2) rebuilt_refs.push_back(parties[0] + "::" + parties[1]);
    }

    // 3. rebuild affected containers（去重）
    std::sort(rebuilt_refs.begin(), rebuilt_refs.end());
    rebuilt_refs.erase(std::unique(rebuilt_refs.begin(), rebuilt_refs.end()), rebuilt_refs.end());
    for (const auto& ref : rebuilt_refs) {
        // tenant 取自 evs（同 batch 同 tenant 常见；逐 ref 用其 tenant 更稳——简化用首个 ev.tenant）
        container.rebuild(conn, evs.front().tenant, ref, now_iso);
    }

    // 4. advance checkpoint
    {
        sqlite3_stmt* raw=nullptr;
        sqlite3_prepare_v2(db,"UPDATE common_ground_subscriber_checkpoint SET last_processed_outbox_sequence=?, last_updated_at=? WHERE id=1",-1,&raw,nullptr);
        persistence::StmtHandle h(raw);
        sqlite3_bind_int(h.get(),1,max_seq);
        persistence::bind_sv(h.get(),2,now_iso);
        sqlite3_step(h.get());
    }
    return static_cast<int>(evs.size());
}

}  // namespace starling::tom
```
（implementer 核对：`persistence::StmtHandle`/`bind_sv`/`make_sqlite_error` 的确切头与命名空间——belief_tracker.cpp / common_ground_writer.cpp 用的是哪套 helper（可能是 `starling::bus::detail::` 或 `persistence::`），照搬一致；`#include <algorithm>`。cg_ref 拼法用 parties sorted 两元 `a::b`，与 Python facade `f"{self}::{interlocutor}"` 对齐——注意 facade 是 `self::interlocutor` 未排序，而这里 sorted；**统一约定**见 Task 7 Step 0。）

- [ ] **Step 3: 接进 SubscriberPump（#7）**

Modify `src/bus/subscriber_pump.cpp`：include 加 `#include "starling/tom/common_ground_subscriber.hpp"`；在 policy_engine（#6）之后加：
```cpp
    // 7. common_ground — grounding 协议（assert/acknowledge/repair + 容器 rebuild）。
    run_isolated(conn, "common_ground", [&]{
        starling::tom::CommonGroundSubscriber::tick_one_batch(adapter, conn, now_iso);
    });
```

> **架构注记（已核实，重要）**：`StatementWriter` 在写 Statement 时 emit `statement.written` 到 `bus_events`（statement_writer.cpp:328-347），但 `Extractor.run` **不调 Bus::write**——`run_post_write` 仅由 `Bus::write`（bus.cpp:622）触发。故所有 subscriber（belief_tracker / conflict_key_backfill / 本 CommonGroundSubscriber）都是 **checkpoint 驱动、滞后**：`remember` 写的 statement.written 在**下一次 Bus.write**（如下一个 remember 的 engram append_evidence）才被处理。这是既有模式，非本期引入。为让 grounding 可确定性 flush（测试 + 生产 tick），下一步把 subscriber 暴露成可 tick 并并入 `Memory.tick()`。

- [ ] **Step 3b: 暴露 subscriber tick 绑定（供 Memory.tick / 测试 flush）**

Modify `bindings/python/module.cpp`，加一个 static 绑定（放在 CommonGroundContainer 绑定附近）：
```cpp
    // P2.j: CommonGroundSubscriber tick（供 Memory.tick / 测试确定性 flush 滞后事件）
    m.def("_common_ground_tick",
          [](starling::persistence::SqliteAdapter& adapter, const std::string& now_iso) {
              return starling::tom::CommonGroundSubscriber::tick_one_batch(
                  adapter, adapter.connection(), now_iso);
          },
          py::arg("adapter"), py::arg("now_iso"));
```
（module.cpp 顶部确认 `#include "starling/tom/common_ground_subscriber.hpp"`。）

- [ ] **Step 4: CMake 注册新源 + 新测试**

- root `CMakeLists.txt`：找 `src/tom/common_ground_writer.cpp` 那行，同组加 `src/tom/common_ground_subscriber.cpp`。
- `tests/cpp/CMakeLists.txt`：找 `test_common_ground_writer.cpp` 那行，同组加 `test_common_ground_subscriber.cpp`。

- [ ] **Step 5: 写 test_common_ground_subscriber.cpp**

测 assert/acknowledge/repair + rebuild。需 seed engram + 两条同命题异方 statement + 跑 subscriber。implementer 仿 test_extractor_orchestrator / test_common_ground_writer 的 adapter+migrate fixture：
```cpp
#include "starling/tom/common_ground_subscriber.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/persistence/migration_runner.hpp"
#include <gtest/gtest.h>
// + helpers

using namespace starling;

namespace {
// 直接插一条 statement + 一条 bus_events(statement.written) 模拟写入。
// 字段：scope_parties_json=["bob","self"]，holder/ subject/predicate/hash/polarity。
// 见 plan 正文：seed 两条同 (subject,predicate,hash) 异 holder（self / bob），
// 跑 tick_one_batch 后断言：第一条→assert(asserted_unack)，第二条(bob)→acknowledge(grounded)。
}

TEST(CommonGroundSubscriber, AssertThenAcknowledgeGrounds) {
    // 1. open adapter + migrate
    // 2. INSERT statements S1(holder=self, scope_parties=["bob","self"], subj=bob,pred=p,hash=h,pol=pos)
    //    + bus_events(event_type='statement.written', primary_id=S1, tenant, outbox_sequence=1)
    // 3. tick_one_batch(adapter, conn, now) → S1 asserted_unack
    //    assert SELECT count FROM common_ground WHERE status='asserted_unack' == 1
    // 4. INSERT S2(holder=bob, scope_parties=["bob","self"], 同 subj/pred/hash, pol=pos)
    //    + bus_events(... primary_id=S2, outbox_sequence=2)
    // 5. tick_one_batch 再跑 → S1 entry → grounded
    //    assert SELECT status FROM common_ground == 'grounded'
}
TEST(CommonGroundSubscriber, OppositePolarityRepairs) {
    // 同上但 S2 polarity=neg → repair → suspected_diverge
}
TEST(CommonGroundSubscriber, RebuildsContainer) {
    // 跑后 SELECT content_json FROM containers WHERE kind='common_ground' AND holder_id='bob::self' 非空
}
```
（implementer 把上面伪步写成真实 SQL seed + 断言；helper 可借 test_common_ground_writer.cpp 的 `_status`/adapter fixture。cg_ref 用 sorted parties `bob::self`。）

- [ ] **Step 6: 重建 + 测试**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope && source .venv/bin/activate
cmake --build build 2>&1 | tail -5 && cmake --install build --prefix .venv/lib/python3.14/site-packages 2>&1 | tail -1
ctest --test-dir build -R CommonGroundSubscriber 2>&1 | tail -6
ctest --test-dir build 2>&1 | grep -E "tests passed|failed"
```
Expected: CommonGroundSubscriber 3 passed；full ctest 全 passed。

- [ ] **Step 7: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope
git add include/starling/tom/common_ground_subscriber.hpp src/tom/common_ground_subscriber.cpp tests/cpp/test_common_ground_subscriber.cpp src/bus/subscriber_pump.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(P2.j): CommonGroundSubscriber assert/acknowledge/repair + 容器 rebuild

接进 SubscriberPump(#7)，消费 statement.written：scope_parties≥2 的新命题→assert_()
(asserted_unack)；另一方同命题复述(同 subj/pred/hash+同 polarity)→acknowledge()(grounded，
覆盖 #1 显式/#3 重复)；polarity 相反→repair()(suspected_diverge)；改后 rebuild
CommonGroundContainer。own checkpoint，SAVEPOINT 隔离。

EOF
```

---

## Task 5: #2 共同在场推定（轮次）+ #4 人工确认（C++ + 绑定 + 重建）

**Files:** Modify `src/tom/common_ground_subscriber.cpp`、`include/starling/tom/common_ground_writer.hpp`（若需暴露）、`bindings/python/module.cpp`、`tests/cpp/test_common_ground_subscriber.cpp`

- [ ] **Step 1: #2 共同在场推定（rounds_since_assert）**

Modify `src/tom/common_ground_subscriber.cpp`：在 `for (const auto& ev : evs)` 循环里，处理完 assert/ack/repair 后，对**未被本事件显式确认**的、该 cg_ref scope 下的 `asserted_unack` 条目，且 `perceived_by(S) ⊇ parties`（本期 perceived_by 与 parties 同集，恒成立）时，自增 `rounds_since_assert`；达 N=3 → acknowledge（co-presence，actor="copresence"）。追加（在每 ev 处理尾部）：
```cpp
        // #2 共同在场推定：该 scope 下 asserted_unack 条目轮次+1，达 3 自动 grounded。
        {
            // 自增本 scope（同 tenant、parties 重叠）所有 asserted_unack 的 rounds，
            // 简化：按 statement 的 parties 串作 scope key 匹配 common_ground.parties_json。
            const std::string parties_js = "[\"" + parties[0] + "\",\"" + parties[1] + "\"]";
            sqlite3_stmt* raw=nullptr;
            sqlite3_prepare_v2(db,
                "UPDATE common_ground SET rounds_since_assert = rounds_since_assert + 1 "
                "WHERE tenant_id=? AND status='asserted_unack' AND parties_json=?",-1,&raw,nullptr);
            persistence::StmtHandle h(raw);
            persistence::bind_sv(h.get(),1,ev.tenant);
            persistence::bind_sv(h.get(),2,parties_js);
            sqlite3_step(h.get());
        }
        {
            // 达 N=3 → grounded（co-presence）。逐条 acknowledge 以走审计 + grounded_at。
            std::vector<std::string> due;
            sqlite3_stmt* raw=nullptr;
            sqlite3_prepare_v2(db,
                "SELECT id FROM common_ground WHERE tenant_id=? AND status='asserted_unack' AND rounds_since_assert >= 3",-1,&raw,nullptr);
            persistence::StmtHandle h(raw);
            persistence::bind_sv(h.get(),1,ev.tenant);
            while (sqlite3_step(h.get())==SQLITE_ROW) due.push_back(col(h.get(),0));
            for (const auto& id : due) writer.acknowledge(conn, id, "copresence", now_iso);
        }
```
（注：parties_js 拼法须与 assert_ 写入的 `json_array_of_strings(parties)` 字节一致——parties 已 sorted，writer 的 `json_array_of_strings` 也按序输出；implementer 核对两处 JSON 字节相同，否则改用 LIKE 或规范化比较。）

- [ ] **Step 2: #4 人工确认绑定**

`CommonGroundWriter.acknowledge` 已可带 actor。暴露 Python 人工 grounding：Modify `bindings/python/module.cpp`，确认/补 `CommonGroundWriter` 绑定有 `acknowledge`（grep；test_grounding_acts.py 已用 `_core.CommonGroundWriter(rt.adapter).acknowledge(cg, actor, now)`，故绑定已存在）。**无需新代码**——#4 即「用现有 acknowledge 绑定 + 任意 human/policy actor 串」。在 plan 验收里以 pytest 证：human actor acknowledge → grounded + grounding_acts.actor 记该 actor。若绑定缺 acknowledge，按 test 用法补 `.def("acknowledge", [](CommonGroundWriter& w, cg_id, actor, now){ w.acknowledge(w.connection(), cg_id, actor, now); }, ...)`。

- [ ] **Step 3: 测试 #2 + #4**

`tests/cpp/test_common_ground_subscriber.cpp` 加：
```cpp
TEST(CommonGroundSubscriber, CoPresenceGroundsAfterThreeRounds) {
    // S1(self) assert → asserted_unack
    // 再来 3 条同 scope(parties=["bob","self"]) 的 statement.written（holder 任意、不同命题，避免触发 #1）
    //   每条 tick 一次 → rounds_since_assert 累加
    // 第 3 轮后 SELECT status == 'grounded'
}
```
Python #4：`tests/python/`（或 test_grounding_acts.py 已覆盖 acknowledge）确认 human actor 路径——本 plan 复用现有 test_grounding_acts.py `test_assert_then_acknowledge_grounds`（actor="alice" 即人工/policy actor 语义），无需新增。

- [ ] **Step 4: 重建 + 测试 + Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope && source .venv/bin/activate
cmake --build build 2>&1 | tail -3 && cmake --install build --prefix .venv/lib/python3.14/site-packages 2>&1 | tail -1
ctest --test-dir build -R CommonGroundSubscriber 2>&1 | tail -6 && ctest --test-dir build 2>&1 | grep -E "tests passed|failed"
git add src/tom/common_ground_subscriber.cpp bindings/python/module.cpp tests/cpp/test_common_ground_subscriber.cpp
git commit -F - <<'EOF'
feat(P2.j): grounding #2 共同在场推定（N=3 轮）+ #4 人工确认

#2：subscriber 每轮自增 asserted_unack 的 rounds_since_assert，达 3 自动 acknowledge
(actor=copresence)。#4：复用 CommonGroundWriter.acknowledge 绑定带 human/policy actor →
grounded + grounding_acts 记 actor。四条 grounded 规则齐。

EOF
```

---

## Task 6: query() 真读 + perspective_take un-stub（C++ + 重建）

**Files:** Modify `src/tom/common_ground.cpp`、`tests/cpp/test_tom_engine_perspective.cpp`

- [ ] **Step 1: query() 真读**

Replace `src/tom/common_ground.cpp` 的 stub body：
```cpp
#include "starling/tom/common_ground.hpp"
#include "starling/persistence/sqlite_helpers.hpp"   // 核对实际 helper 头
#include <sqlite3.h>

namespace starling::tom::common_ground {

std::vector<CommonGroundEntry> query(
    persistence::SqliteAdapter& adapter,
    std::string_view self_id,
    std::string_view target_id,
    std::string_view tenant_id,
    std::string_view as_of_iso8601)
{
    std::vector<CommonGroundEntry> out;
    sqlite3* db = adapter.connection().raw();
    // parties_json 同含 self 与 target；status 活跃；as_of 过滤（grounded_at<=as_of 或 NULL）。
    const char* sql =
        "SELECT id, tenant_id, statement_id, status, parties_json, created_at, updated_at "
        "FROM common_ground "
        "WHERE tenant_id=? "
        "  AND status IN ('grounded','asserted_unack','suspected_diverge') "
        "  AND parties_json LIKE ? AND parties_json LIKE ? "
        "  AND (grounded_at IS NULL OR grounded_at <= ?) "
        "  AND (expired_at IS NULL OR expired_at > ?)";
    sqlite3_stmt* raw=nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) return out;
    persistence::StmtHandle h(raw);
    const std::string like_self   = std::string("%\"") + std::string(self_id)   + "\"%";
    const std::string like_target = std::string("%\"") + std::string(target_id) + "\"%";
    const std::string as_of(as_of_iso8601);
    persistence::bind_sv(h.get(),1,tenant_id);
    persistence::bind_sv(h.get(),2,like_self);
    persistence::bind_sv(h.get(),3,like_target);
    persistence::bind_sv(h.get(),4,as_of);
    persistence::bind_sv(h.get(),5,as_of);
    auto col=[&](int i){ const char* t=reinterpret_cast<const char*>(sqlite3_column_text(h.get(),i)); return t?std::string(t):std::string(); };
    while (sqlite3_step(h.get())==SQLITE_ROW) {
        CommonGroundEntry e;
        e.id=col(0); e.tenant_id=col(1); e.statement_id=col(2); e.status=col(3);
        e.parties_json=col(4); e.created_at=col(5); e.updated_at=col(6);
        out.push_back(std::move(e));
    }
    return out;
}

}  // namespace starling::tom::common_ground
```
（注：`LIKE '%"id"%'` 匹配 JSON 数组里的引号包裹 id，避免子串误命中；implementer 核对 helper 头/命名空间一致。`self_id` 在 perspective_take 里硬编码 "system_self"——但本期 grounding 用真实 agent id（如 "self"）。这关系到 cg_ref/self_id 约定，见 Task 7 Step 0 统一。）

- [ ] **Step 2: un-stub test_tom_engine_perspective**

Modify `tests/cpp/test_tom_engine_perspective.cpp:142` 的 `CommonGroundAlwaysEmptyInP2a`：改为 seed 一条 grounded common_ground（parties 含 "system_self" 与 target）后断言 `ctx.cg` 非空：
```cpp
// TC-TOM-CG-REAL (P2.j): perspective_take returns real common ground.
TEST_F(ToMEngineTest, CommonGroundReturnsGroundedEntries) {
    // seed: INSERT INTO common_ground(id,tenant_id,statement_id,status,parties_json,created_at,updated_at)
    //   VALUES('cg1','default','stmt-x','grounded','["alice","system_self"]','t','t')
    //   （parties 含 system_self + alice；perspective_take 硬编码 self=system_self）
    ToMEngine engine(*adapter_, *hub_, *frontier_);
    auto ctx = engine.perspective_take("alice", "default", "2026-05-26T10:00:00Z");
    EXPECT_FALSE(ctx.cg.empty()) << "P2.j: common_ground::query must return grounded entries";
    EXPECT_EQ(ctx.cg[0].status, "grounded");
}
```
（implementer 用该测试 fixture 的 adapter 直接 INSERT seed common_ground 行；parties_json 必须含 `"system_self"` 与 `"alice"`。）

- [ ] **Step 3: 重建 + 测试 + Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope && source .venv/bin/activate
cmake --build build 2>&1 | tail -3 && cmake --install build --prefix .venv/lib/python3.14/site-packages 2>&1 | tail -1
ctest --test-dir build -R "ToMEngine|CommonGround" 2>&1 | tail -6 && ctest --test-dir build 2>&1 | grep -E "tests passed|failed"
git add src/tom/common_ground.cpp tests/cpp/test_tom_engine_perspective.cpp
git commit -F - <<'EOF'
feat(P2.j): common_ground::query 真读 + perspective_take un-stub

query() 按 tenant + status 活跃 + parties_json 同含 self/target + as_of 过滤真读表；
perspective_take 返回真实 cg。un-stub test_tom_engine_perspective（原锁 cg 恒空 → 改 seed
grounded 条目断言非空）。

EOF
```

---

## Task 7: Python 读路径 + grounding 端到端（Python）

**Files:** Modify `python/starling/memory.py`（cg_ref 约定）；新增/补 `tests/python/test_common_ground_e2e.py`

- [ ] **Step 0: 统一 cg_ref / self_id 约定（关键一致性）**

三处必须一致：
1. subscriber rebuild 的 cg_ref（Task 4：sorted parties `parties[0]::parties[1]`，如 `bob::self`）。
2. Python facade 读 container 的 cg_ref（`memory.py:1212` / `engine.py`：`f"{self._agent}::{interlocutor}"`，如 `self::bob`，**未排序**）。
3. `perspective_take` 的 self_id（硬编码 `"system_self"`）。

**决策**：cg_ref 统一用 **sorted parties** `min::max`。故：
- Modify `python/starling/memory.py:1212` 与 dashboard `engine.py` 的 cg_ref 构造为 sorted：
```python
        _pair = sorted([self._agent, interlocutor])
        cg = _core.CommonGroundContainer(adapter).read(self._tenant, f"{_pair[0]}::{_pair[1]}")
```
（两处都改。）`perspective_take` 的 query 用 parties_json 包含匹配（Task 6 用 LIKE 同含 self+target，与 cg_ref 排序无关，已 OK）。self_id "system_self" 仅影响 perspective_take 的 query 过滤——本期 e2e 走 Memory.remember(agent=默认"self")，grounding parties 用真实 agent，故 perspective_take 测试用 system_self seed（Task 6）独立验证；端到端走 container 读路径（Task 7）。

- [ ] **Step 1: CommonGroundSubscriber 并入 Memory.tick（确定性 flush 滞后事件）**

已核实（见 Task 4 架构注记）：subscriber 滞后于 statement.written（仅 Bus.write 触发 pump）。把它并入 `Memory.tick`，使 `tick()` 能确定性处理累积的 grounding 事件。Modify `python/starling/memory.py` 的 `tick`（现 177-185，已 tick EmbeddingWorker + policy），加一行：
```python
        cg = _core._common_ground_tick(self._rt.adapter, now)   # P2.j: flush grounding 滞后事件
```
（implementer：核对 `tick` 返回的 `TickStats` 是否要纳入 `cg` 计数；不纳入也可，至少调用以推进 grounding。`now` 参数沿用 tick 的 now。）

- [ ] **Step 2: grounding 端到端 pytest**

Create `tests/python/test_common_ground_e2e.py`：self 断言 X 给 bob → bob 复述 X → `tick()` flush（assert 后紧接 acknowledge）→ grounded → `render_working_set("bob")` 出现 common ground：
```python
import tempfile
from starling.memory import Memory, make_stub_llm

_JSON = '[{{"holder":"{h}","holder_perspective":"FIRST_PERSON","subject":"Bob","predicate":"responsible_for","object":"auth","modality":"BELIEVES","polarity":"POS","nesting_depth":0}}]'

def test_grounding_end_to_end():
    db = tempfile.mktemp(suffix=".db")
    m = Memory.open(db, agent="self", tenant_id="default",
                    llm=make_stub_llm(default_response=_JSON.format(h="self")))
    m.remember("Bob is responsible for auth.", interlocutor="bob")        # self 断言（statement.written 入队）
    m.remember("Bob is responsible for auth.", holder="bob", interlocutor="self")  # bob 复述（入队）
    m.tick("2026-06-06T10:00:00Z")   # flush：S1 assert(asserted_unack) → S2 同命题异方 → acknowledge(grounded) + rebuild
    ws = m.render_working_set("bob")
    blob = str(getattr(ws, "sections", ws))   # ContextBlock or dict — implementer 对齐真实结构
    assert "auth" in blob, f"common ground 'auth' 应出现在 working set: {blob}"
```
（implementer：核对 `render_working_set` 返回类型（ContextBlock 有 `.sections`？还是 dict），把 `blob` 取法对齐；两条 remember 在**一个 tick 批**内被顺序处理：S1→assert、S2 匹配 S1 的 asserted_unack→acknowledge→grounded，故单次 tick 即 grounded。)

- [ ] **Step 3: 跑 + Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope && source .venv/bin/activate
python -m pytest tests/python/test_common_ground_e2e.py -q 2>&1 | tail -4
python -m pytest -q 2>&1 | tail -2
git add python/starling/memory.py python/starling/dashboard/engine.py tests/python/test_common_ground_e2e.py
git commit -F - <<'EOF'
feat(P2.j): cg_ref sorted 约定统一 + grounding 端到端 pytest

memory.py/engine.py 读 container 的 cg_ref 统一 sorted min::max（与 subscriber rebuild 一致）。
test_common_ground_e2e：self 断言→bob 复述→grounded→render_working_set 出现 common ground。

EOF
```

---

## Task 8: 回归 + roadmap 登记 + close

**Files:** Modify `docs/superpowers/plans/2026-05-23-roadmap.md`

- [ ] **Step 1: 全量回归**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope && source .venv/bin/activate
cmake --build build 2>&1 | tail -2
ctest --test-dir build 2>&1 | grep -E "tests passed|failed"
python -m pytest -q 2>&1 | tail -2
python scripts/ci_static_scan.py
ls migrations/ | tail -1
grep -rnE "sk-[A-Za-z0-9]{16,}" python src include scripts 2>/dev/null || echo "OK 无真实密钥"
```
Expected: ctest 全 passed（数较 493 增：+CanonicalScope 分支用例 +CommonGroundSubscriber 测试 -1 旧 stub 等）；pytest 全 passed（+e2e）；ci_static_scan OK；migrations 末 `0022_...`；无密钥。

- [ ] **Step 2: roadmap 登记**

Modify `docs/superpowers/plans/2026-05-23-roadmap.md` 的「已知缺口」节：把 #2 CommonGround、#3 CanonicalScope 两条从「未接线」改为「**已接线（P2.j，merge <SHA>）**」，并在 P2 收尾表加 P2.j 行（仿 P2.i 行格式）：
```markdown
| **P2.j 社会域接线 ✅** | CanonicalScope 七元组带 scope + CommonGround grounding 协议真接线（codex #2/#3） | codex review：CommonGround query/subscriber 占位、CanonicalScope scope_of 恒 Null | **[2026-06-06-p2-j-social-scope-wiring.md](2026-06-06-p2-j-social-scope-wiring.md)（已完成）**：scope_parties_json（独立 perceived_by，migration 0022）+ scope_of 按 modality 分支 + 3 臂 canonical_bytes（C++/Python parity）+ CommonGroundSubscriber（assert/ack#1#3/共同在场#2/repair/超时 + 容器 rebuild）+ query 真读 + perspective_take un-stub；改 C++（worktree+重建）；ctest/pytest/ci_static_scan 全绿 |
```

- [ ] **Step 3: 提交 plan + roadmap（close）**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-j-social-scope
git add docs/superpowers/plans/2026-06-06-p2-j-social-scope-wiring.md docs/superpowers/plans/2026-05-23-roadmap.md
git commit -F - <<'EOF'
docs(P2.j): land 社会域接线 实施计划 + roadmap 登记（#2/#3 已接线）

CanonicalScope 七元组带 scope + CommonGround grounding 协议真接线。改 C++（migration
0022 + worktree+重建）；ctest/pytest/ci_static_scan 全绿。roadmap #2/#3 改「已接线 P2.j」。

EOF
```

- [ ] **Step 4: 合并 main（需显式 consent + dangerouslyDisableSandbox）**

> ⚠ 合并前 `git -C /Users/jaredguo-mini/develop/memory/starling status`；删 main 工作树里 untracked 的 plan 副本（若有）再 `git merge --no-ff --no-commit worktree-p2-j-social-scope` + `git commit -F -`（git merge 不接 `-F -`）；合并后主仓库 `cmake --build build && cmake --install build`（C++ 改动）+ 跑主仓库 ctest/pytest/ci_static_scan。**需用户显式同意**。

---

## 自检（writing-plans self-review）

**1. Spec 覆盖：** §2 数据模型→Task 1（migration 0022 + scope_parties + writer + run interlocutor）+ Task 2（remember 串线）；§3 CanonicalScope→Task 3（scope_of + 3 臂 + backfill + Python parity + un-stub）；§4 CommonGroundSubscriber→Task 4（assert/ack#1#3/repair/rebuild + pump）+ Task 5（#2 共同在场 + #4 人工）；§5 query+perspective_take→Task 6；§5 Python 读路径→Task 7（cg_ref 统一 + e2e）；§6 测试→各 Task 内联 + Task 8 回归；§7 约束→各 Task（worktree+重建/parity/不可变 trigger/ci_static_scan）；§8 验收→Task 8。无缺口。

**2. 占位扫描：** subscriber 触发路径已核实（Task 4 架构注记：StatementWriter emit statement.written，pump 滞后处理，故并入 Memory.tick 做确定性 flush，Task 7 e2e 据此用单次 tick）。剩余 implementer 指令（Task 4 Step 5 测试 seed SQL、Task 7 render_working_set 返回结构、helper 头命名空间、JSON 字节一致性）是**真实依赖核对点**非 TBD；subscriber.cpp / query / scope_of / canonical_bytes / migration / e2e 均含完整代码。Task 5 #4「无需新代码」是真实结论（acknowledge 绑定已存在，test_grounding_acts 已覆盖）。

**3. 类型一致：** `scope_parties`（ExtractedStatement 字段，vector<string>，Task 1 定义 → Task 3 scope_of 读 → backfill proxy 填 → writer 写 scope_parties_json）；`scope_of(const ExtractedStatement&)→CanonicalScope`（Task 3 hpp/cpp/Python 一致，conflict_key.cpp 既有调用点不变）；`canonical_bytes`（3 臂，\x1f，C++/Python 同）；`CommonGroundSubscriber::tick_one_batch(adapter, conn, now_iso, batch)`（Task 4 hpp/cpp/pump 调用一致）；`CommonGroundWriter.assert_(conn,tenant,stmt_id,parties,now)`/`acknowledge(conn,cg_id,actor,now)`/`repair(...)`（Task 4/5 用法与既有签名一致）；`CommonGroundContainer.rebuild(conn,tenant,cg_ref,now)`（Task 4 用法一致）；`query(adapter,self,target,tenant,as_of)`（Task 6 签名不变，仅换 body）；`remember(text,*,holder,interlocutor,now)` + `Extractor.run(...,interlocutor="")`（Task 1/2 绑定/facade 一致）；cg_ref=sorted `min::max`（Task 4 rebuild ↔ Task 7 read 统一）。一致。
