# P2.e 应用接口层（Application Surface）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付公开 `starling.Memory` 门面 + `render_working_set` 渲染 prompt-ready `ContextBlock`，让小应用十几行 Python 即可写记忆 / 检索 / 把"我是谁 / 共识 / 相关记忆 / 待办承诺 / 当前情绪"喂进一轮对话，且离线可跑。

**Architecture:** 三层——C++ 给现有类加只读接口（`PersonaContainer.read` / `CommonGroundContainer.read` / `CommitmentEngine.pending`）+ `StatementRow.affect_json` 列；Python `starling.Memory` 门面组合 _core(retrievers/Extractor/readers/PolicyEngine/EmbeddingWorker)；Python `working_set` 模块组装 + 近似 token 预算 + 渲染。纯读，无 migration。

**Tech Stack:** C++20 + raw SQLite + nlohmann/json + pybind11 + Python 3.14 + GoogleTest + pytest + Ninja。

**Spec:** `docs/superpowers/specs/2026-06-01-p2-e-application-surface-design.md`（commit a115527）。

---

## 锚点更正（实现以本节为准，spec 三处待 close 时回补）

1. **Persona `content_json`** 实为 `{"dimensions":{<dim>:{"value":<str|null>,"confidence":<num>,"suspected_diverge":<bool>}}}`（每 dimension 一个仲裁值）。`PersonaView.dimensions` = `std::map<std::string,std::string>`（dim→value，跳过 value=null / suspected_diverge=true 的）。
2. **CommonGround `content_json`** 实为 `{"grounded":["sid",…],"asserted_unack":[…],"suspected_diverge":[…]}`（statement_id 数组）。`read` 解析 id 后 JOIN `statements` 取 `subject_id/predicate/object_value` 渲染成文本。`rebuild(tenant, cg_ref, now)` 无 sources。CG 把 **cg_ref 存进 `holder_id` 列**，`kind='common_ground'`。
3. **Extractor** Python 方法是 `.run(engram_ref_id, payload_bytes, holder_id, holder_tenant_id, existing_ref_map)`，构造 `Extractor(connection, FakeLLMAdapter)`。`Memory.open(llm=…)` 收一个 **LLM adapter**（`_core.FakeLLMAdapter` 或 `_core.OpenAIAdapter`），内部建 `Extractor(self._conn, llm)`；helper `make_stub_llm(rules)` / `make_openai_llm(...)`。

**全局约束（所有 Task）：** worktree `.claude/worktrees/p2-e-application-surface`；`source .venv/bin/activate` 后 `cmake --build build` / `ctest` / `pytest`；无 migration（最高 0021 不变）；rebuild/五态机写路径不改（只加 read/pending）；read/pending conn-free；Co-Authored-By trailer；无 `--no-verify`/`--amend`；plan untracked 直到 close；API key env-only（`OPENAI_API_KEY` 绝不入参/log/绑形参）；SQL helpers `bus::detail::bind_sv`/`make_sqlite_error`、`persistence::StmtHandle`、checked `sqlite3_prepare_v2`、nlohmann 解析。pybind 改动后刷新 `_core.so`：`cmake --build build && cmake --install build --prefix .venv/lib/python3.14/site-packages && pip install -e . --no-deps --force-reinstall`（`cmake --install` 是关键；pip 撞 json 网络错加 `--config-settings="cmake.define.FETCHCONTENT_SOURCE_DIR_JSON=$(pwd)/build/_deps/json-src"`）。

---

## Task 0: Baseline 确认

**Files:** 无

- [ ] **Step 1: 分支/HEAD + 构建 + ctest**
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-e-application-surface
git branch --show-current   # worktree-p2-e-application-surface
cmake -S . -B build -G Ninja && cmake --build build && ctest --test-dir build
```
Expected: `100% tests passed ... out of 498`

- [ ] **Step 2: venv + pytest**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/python -q
```
Expected: `488 passed, 13 skipped`。不绿则 STOP / 报告。

---

## Task 1: `StatementRow.affect_json` 列（additive）

**Files:**
- Modify: `include/starling/retrieval/statement_row.hpp`
- Modify: `src/retrieval/basic_retriever.cpp`、`src/retrieval/semantic_retriever.cpp`、`src/retrieval/pattern_completor.cpp`
- Modify: `bindings/python/module.cpp`（StatementRow 绑定，~L557）
- Test: `tests/cpp/test_semantic_retriever.cpp`（加一条 affect 透传断言）

- [ ] **Step 1: failing 测试** — 在 `tests/cpp/test_semantic_retriever.cpp` 末尾追加（seed 一条带 affect_json 的 stmt，断言检索返回它）：
```cpp
TEST(SemanticRetriever, CarriesAffectJson) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    // 复用本文件已有 seed helper 写一条 stmt;然后改它的 affect_json:
    seed_stmt(db, "s1", "cats");
    sqlite3_exec(db, "UPDATE statements SET affect_json='{\"valence\":0.7}' WHERE id='s1'",
                 nullptr, nullptr, nullptr);
    StubEmbeddingAdapter emb(8); SqliteBlobVectorIndex idx;
    EmbeddingWorker(*adapter, emb, idx).tick_one_batch(conn, "2026-06-01T10:00:00Z");
    SemanticRetriever sr(*adapter, emb, idx);
    SemanticRetrieverParams p; p.tenant_id="default"; p.holder_id="alice";
    p.k=1; p.query_text="bob knows cats";
    auto res = sr.vector_recall(conn, p);
    ASSERT_GE(res.rows.size(), 1u);
    EXPECT_EQ(res.rows[0].row.affect_json, "{\"valence\":0.7}");
}
```
> 注：该测试文件 `seed_stmt` 写的 `affect_json` 默认 `'{}'`；上面 UPDATE 覆盖。若 `seed_stmt` 签名不含 affect，UPDATE 方式最稳。

- [ ] **Step 2: 跑确认 FAIL**（`StatementRow` 无 `affect_json` 字段 → 编译失败）
Run: `source .venv/bin/activate && cmake --build build 2>&1 | tail -5`
Expected: 编译错误 `no member named 'affect_json'`

- [ ] **Step 3: 加字段** — `include/starling/retrieval/statement_row.hpp` 在 `evidence_json` 字段后加：
```cpp
    std::string evidence_json;       // raw JSON array of EvidenceRef-like dicts
    std::string affect_json;         // raw affect JSON ("{}" if absent); P2.e
```

- [ ] **Step 4: 三处 SELECT 追列 + 三处 populator 追行**
在 `basic_retriever.cpp` 的 `kSelectSqlBase`、`semantic_retriever.cpp` 的 `kSelectByIdSql`、`pattern_completor.cpp` 的 `kSelectByIdSql`，把 SELECT 列表里的 `"       evidence_json "` 改为 `"       evidence_json, affect_json "`（即 evidence_json 后加 `, affect_json`，列变为 index 19）。
然后三处 populator：
- `basic_retriever.cpp` 在 `row.evidence_json = col_text(18);` 后加 `row.affect_json = col_text(19);`
- `semantic_retriever.cpp` 在 `row.evidence_json = col_text(18);` 后加 `row.affect_json = col_text(19);`
- `pattern_completor.cpp` 在 `row.review_status = col(17); row.evidence_json = col(18);` 后加 `row.affect_json = col(19);`

- [ ] **Step 5: pybind 暴露** — `bindings/python/module.cpp` 把 StatementRow 绑定末行
`.def_readonly("evidence_json",          &starling::retrieval::StatementRow::evidence_json);`
改为以 `;` 收尾前再加一行：
```cpp
        .def_readonly("evidence_json",          &starling::retrieval::StatementRow::evidence_json)
        .def_readonly("affect_json",            &starling::retrieval::StatementRow::affect_json);
```

- [ ] **Step 6: 构建 + 全量 ctest（确认无回归 + 新测试过）**
```bash
cmake --build build && ctest --test-dir build --output-on-failure 2>&1 | tail -6
```
Expected: `100% tests passed ... out of 499`（498 + CarriesAffectJson）

- [ ] **Step 7: Commit**
```bash
git add include/starling/retrieval/statement_row.hpp src/retrieval/basic_retriever.cpp \
        src/retrieval/semantic_retriever.cpp src/retrieval/pattern_completor.cpp \
        bindings/python/module.cpp tests/cpp/test_semantic_retriever.cpp
git commit -m "$(cat <<'EOF'
feat(P2.e): StatementRow.affect_json 列(additive)

statement_row.hpp 加 affect_json 字段;3 个 retriever SELECT 末尾追 affect_json
(col 19)+ populator;pybind def_readonly 暴露。检索返回的记忆自带 affect,供
working set 取 peak。CarriesAffectJson 通过,既有检索测试不回归。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `PersonaContainer.read` + `PersonaView` + 绑定 + 测试

**Files:**
- Modify: `include/starling/neocortex/persona_container.hpp`、`src/neocortex/persona_container.cpp`
- Modify: `bindings/python/module.cpp`（PersonaContainer 绑定）
- Test: `tests/cpp/test_persona_read.cpp`（新）+ `tests/cpp/CMakeLists.txt`

- [ ] **Step 1: 加测试文件 + 接线** — `tests/cpp/CMakeLists.txt` 在 `add_executable(starling_tests ...)` 列表里 `test_pattern_completor.cpp` 之后、`)` 之前加一行 `    test_persona_read.cpp`。新建 `tests/cpp/test_persona_read.cpp`：
```cpp
// test_persona_read.cpp -- P2.e PersonaContainer.read
#include "starling/neocortex/persona_container.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <string>
#include <vector>

using starling::neocortex::AnchorStatement;
using starling::neocortex::PersonaContainer;
using starling::neocortex::PersonaView;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;

TEST(PersonaRead, RebuildThenRead) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    PersonaContainer pc(*adapter);
    std::vector<AnchorStatement> sources = {
        {"s1", "self_model_anchor", "traits", "concise", 0.9},
        {"s2", "self_model_anchor", "preferences", "dark mode", 0.8},
    };
    pc.rebuild(conn, "default", "alice", sources, "2026-06-01T09:00:00Z");

    PersonaView v = pc.read(conn, "default", "alice");
    EXPECT_TRUE(v.found);
    EXPECT_EQ(v.holder_id, "alice");
    EXPECT_EQ(v.dimensions["traits"], "concise");
    EXPECT_EQ(v.dimensions["preferences"], "dark mode");
}

TEST(PersonaRead, MissingReturnsNotFound) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    PersonaContainer pc(*adapter);
    PersonaView v = pc.read(conn, "default", "nobody");
    EXPECT_FALSE(v.found);
    EXPECT_TRUE(v.dimensions.empty());
}
```

- [ ] **Step 2: 跑确认 FAIL**（`PersonaView` / `read` 未定义 → 编译错误）
Run: `source .venv/bin/activate && cmake --build build 2>&1 | tail -5`

- [ ] **Step 3: 头文件加 `PersonaView` + `read` 声明** — `include/starling/neocortex/persona_container.hpp`，在 `class PersonaContainer` 之前加 view，在 `rebuild(...)` 声明后加 `read`：
```cpp
struct PersonaView {
    bool found = false;
    std::string tenant_id, holder_id;
    int version = 0;
    std::map<std::string, std::string> dimensions;   // dim → arbitrated value(跳过 null/diverged)
};
```
（确保头文件已 `#include <map>`；`class PersonaContainer` 的 public 段加：）
```cpp
    PersonaView read(persistence::Connection& conn, std::string_view tenant_id,
                     std::string_view holder_id);
```

- [ ] **Step 4: 实现 `read`** — `src/neocortex/persona_container.cpp` 末尾（namespace 内）加。content_json 形如 `{"dimensions":{"traits":{"value":"concise","confidence":0.9,"suspected_diverge":false},...}}`：
```cpp
PersonaView PersonaContainer::read(persistence::Connection& conn,
                                   std::string_view tenant_id, std::string_view holder_id) {
    PersonaView v;
    v.tenant_id = std::string(tenant_id);
    v.holder_id = std::string(holder_id);
    const char* sql =
        "SELECT content_json, version FROM containers"
        " WHERE tenant_id=?1 AND holder_id=?2 AND kind='persona' LIMIT 1";
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw starling::bus::detail::make_sqlite_error(db, "PersonaContainer::read prepare");
    starling::persistence::StmtHandle h{raw};
    starling::bus::detail::bind_sv(raw, 1, tenant_id);
    starling::bus::detail::bind_sv(raw, 2, holder_id);
    if (sqlite3_step(raw) != SQLITE_ROW) return v;  // found=false
    const unsigned char* cj = sqlite3_column_text(raw, 0);
    std::string content = cj ? reinterpret_cast<const char*>(cj) : "{}";
    v.version = sqlite3_column_int(raw, 1);
    v.found = true;
    auto j = nlohmann::json::parse(content, nullptr, /*allow_exceptions=*/false);
    if (j.is_object() && j.contains("dimensions") && j["dimensions"].is_object()) {
        for (auto& [dim, entry] : j["dimensions"].items()) {
            if (!entry.is_object()) continue;
            if (entry.value("suspected_diverge", false)) continue;
            const auto& val = entry["value"];
            if (val.is_string()) v.dimensions[dim] = val.get<std::string>();
        }
    }
    return v;
}
```
（确保 `persona_container.cpp` 顶部已 include：`"starling/bus/sqlite_helpers.hpp"`、`"starling/persistence/sqlite_handles.hpp"`、`<nlohmann/json.hpp>`——对照文件现有 include 风格补缺的。）

- [ ] **Step 5: pybind 绑定** — `bindings/python/module.cpp` 在 PersonaContainer 的 `.def("rebuild", ...)` 那条 class_ 链上、`;` 收尾前加 `.def("read", ...)`，并在其前加 `PersonaView` 的 class_：
```cpp
    py::class_<starling::neocortex::PersonaView>(m, "PersonaView")
        .def_readonly("found",      &starling::neocortex::PersonaView::found)
        .def_readonly("tenant_id",  &starling::neocortex::PersonaView::tenant_id)
        .def_readonly("holder_id",  &starling::neocortex::PersonaView::holder_id)
        .def_readonly("version",    &starling::neocortex::PersonaView::version)
        .def_readonly("dimensions", &starling::neocortex::PersonaView::dimensions);
```
PersonaContainer 的链上加（在 rebuild 之后）：
```cpp
        .def("read",
             [](starling::neocortex::PersonaContainer& self,
                const std::string& tenant_id, const std::string& holder_id) {
                 return self.read(self.connection(), tenant_id, holder_id);
             },
             py::arg("tenant_id"), py::arg("holder_id"))
```

- [ ] **Step 6: 构建 + 测试**
```bash
cmake --build build && ctest --test-dir build -R PersonaRead --output-on-failure
```
Expected: 2 passed（RebuildThenRead + MissingReturnsNotFound）

- [ ] **Step 7: Commit**
```bash
git add include/starling/neocortex/persona_container.hpp src/neocortex/persona_container.cpp \
        bindings/python/module.cpp tests/cpp/test_persona_read.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(P2.e): PersonaContainer.read + PersonaView 绑定

read 解析物化 content_json({"dimensions":{dim:{value,confidence,suspected_diverge}}})
→ dim→value(跳 null/diverged);found=false 表未物化。rebuild 写路径不改。
RebuildThenRead/MissingReturnsNotFound 通过。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `CommonGroundContainer.read` + `CommonGroundView` + 绑定 + 测试

**Files:**
- Modify: `include/starling/neocortex/common_ground_container.hpp`、`src/neocortex/common_ground_container.cpp`
- Modify: `bindings/python/module.cpp`
- Test: `tests/cpp/test_common_ground_read.cpp`（新）+ `tests/cpp/CMakeLists.txt`

`read`：SELECT content_json（`{"grounded":["sid"],...}`）→ 解析 id → JOIN `statements` 取 `subject_id||' '||predicate||' '||object_value` 渲染。grounded/asserted_unack/suspected_diverge 三组各渲染成文本列表。

- [ ] **Step 1: 测试文件 + 接线** — `tests/cpp/CMakeLists.txt` 加 `    test_common_ground_read.cpp`。新建 `tests/cpp/test_common_ground_read.cpp`：
```cpp
// test_common_ground_read.cpp -- P2.e CommonGroundContainer.read
#include "starling/neocortex/common_ground_container.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <string>

using starling::neocortex::CommonGroundContainer;
using starling::neocortex::CommonGroundView;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;

namespace {
void seed_stmt(sqlite3* db, const std::string& id, const std::string& obj) {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
        "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES('" + id + "','default','alice','first_person','cognizer',"
        "'bob','knows','str','" + obj + "','" + std::string(64,'a') + "','v1','believes','pos',"
        "0.9,'2026-06-01T09:00:00Z',0.5,'{}',0.0,'2026-06-01T09:00:00Z','user_input',"
        "'consolidated','approved','2026-06-01T09:00:00Z','2026-06-01T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
void seed_cg(sqlite3* db, const std::string& sid, const std::string& status) {
    std::string s = "INSERT INTO common_ground(id,tenant_id,statement_id,status,created_at,updated_at)"
        " VALUES('cg-" + sid + "','default','" + sid + "','" + status +
        "','2026-06-01T09:00:00Z','2026-06-01T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
}  // namespace

TEST(CommonGroundRead, RebuildThenRead) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_stmt(db, "s1", "auth");
    seed_cg(db, "s1", "grounded");
    CommonGroundContainer cg(*adapter);
    cg.rebuild(conn, "default", "alice::bob", "2026-06-01T09:00:00Z");

    CommonGroundView v = cg.read(conn, "default", "alice::bob");
    EXPECT_TRUE(v.found);
    ASSERT_EQ(v.grounded.size(), 1u);
    EXPECT_NE(v.grounded[0].find("auth"), std::string::npos);  // 渲染含 object
}

TEST(CommonGroundRead, MissingReturnsNotFound) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    CommonGroundContainer cg(*adapter);
    CommonGroundView v = cg.read(conn, "default", "none::none");
    EXPECT_FALSE(v.found);
}
```
> 注：`common_ground` 表的确切列以 migration 为准——implementer 写测试前 `grep -A12 "CREATE TABLE.*common_ground" migrations/*.sql` 对齐列名（上面 seed_cg 的列若不符按实际改；`statement_id`/`status` 是 rebuild 读的列，见 common_ground_container.cpp 的 sel_sql）。

- [ ] **Step 2: 跑确认 FAIL**

- [ ] **Step 3: 头文件 view + read 声明** — `include/starling/neocortex/common_ground_container.hpp`：
```cpp
struct CommonGroundView {
    bool found = false;
    std::string tenant_id, cg_ref;
    int version = 0;
    std::vector<std::string> grounded, asserted_unack, suspected_diverge;  // 渲染后的文本
};
```
（确保已 include `<string>`/`<vector>`；class public 段加 `CommonGroundView read(persistence::Connection&, std::string_view tenant_id, std::string_view cg_ref);`）

- [ ] **Step 4: 实现 `read`** — `src/neocortex/common_ground_container.cpp`，解析 content_json 三数组，对每个 id JOIN statements 渲染：
```cpp
CommonGroundView CommonGroundContainer::read(persistence::Connection& conn,
        std::string_view tenant_id, std::string_view cg_ref) {
    CommonGroundView v;
    v.tenant_id = std::string(tenant_id);
    v.cg_ref = std::string(cg_ref);
    sqlite3* db = conn.raw();
    const char* sql =
        "SELECT content_json, version FROM containers"
        " WHERE tenant_id=?1 AND holder_id=?2 AND kind='common_ground' LIMIT 1";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw starling::bus::detail::make_sqlite_error(db, "CommonGroundContainer::read prepare");
    starling::persistence::StmtHandle h{raw};
    starling::bus::detail::bind_sv(raw, 1, tenant_id);
    starling::bus::detail::bind_sv(raw, 2, cg_ref);
    if (sqlite3_step(raw) != SQLITE_ROW) return v;
    const unsigned char* cj = sqlite3_column_text(raw, 0);
    std::string content = cj ? reinterpret_cast<const char*>(cj) : "{}";
    v.version = sqlite3_column_int(raw, 1);
    v.found = true;
    auto j = nlohmann::json::parse(content, nullptr, false);

    // 渲染单个 statement_id → "subject predicate object"
    auto render = [&](const std::string& sid) -> std::string {
        const char* q =
            "SELECT subject_id, predicate, object_value FROM statements"
            " WHERE id=?1 AND tenant_id=?2 LIMIT 1";
        sqlite3_stmt* sr = nullptr;
        if (sqlite3_prepare_v2(db, q, -1, &sr, nullptr) != SQLITE_OK) return sid;
        starling::persistence::StmtHandle sh{sr};
        starling::bus::detail::bind_sv(sr, 1, sid);
        starling::bus::detail::bind_sv(sr, 2, tenant_id);
        if (sqlite3_step(sr) != SQLITE_ROW) return sid;
        auto t = [sr](int i){ const unsigned char* c=sqlite3_column_text(sr,i);
                              return c ? std::string(reinterpret_cast<const char*>(c)) : std::string(); };
        return t(0) + " " + t(1) + " " + t(2);
    };
    auto fill = [&](const char* key, std::vector<std::string>& out) {
        if (j.is_object() && j.contains(key) && j[key].is_array())
            for (const auto& e : j[key]) if (e.is_string()) out.push_back(render(e.get<std::string>()));
    };
    fill("grounded", v.grounded);
    fill("asserted_unack", v.asserted_unack);
    fill("suspected_diverge", v.suspected_diverge);
    return v;
}
```
（补 include：`sqlite_helpers.hpp` / `sqlite_handles.hpp` / `<nlohmann/json.hpp>` 若缺。）

- [ ] **Step 5: pybind** — 加 `CommonGroundView` class_ + CommonGroundContainer 链上 `.def("read", [lambda self.connection()], py::arg("tenant_id"), py::arg("cg_ref"))`，形如 Task 2。view 的 def_readonly：found/tenant_id/cg_ref/version/grounded/asserted_unack/suspected_diverge。

- [ ] **Step 6: 构建 + 测试**
```bash
cmake --build build && ctest --test-dir build -R CommonGroundRead --output-on-failure
```
Expected: 2 passed

- [ ] **Step 7: Commit**（message: `feat(P2.e): CommonGroundContainer.read + CommonGroundView 绑定` + 说明解析 3 id 数组 JOIN statements 渲染 + trailer）

---

## Task 4: `CommitmentEngine.pending` + `CommitmentView` + 绑定 + 测试

**Files:**
- Modify: `include/starling/prospective/commitment_engine.hpp`、`src/prospective/commitment_engine.cpp`
- Modify: `bindings/python/module.cpp`
- Test: `tests/cpp/test_commitment_pending.cpp`（新）+ `tests/cpp/CMakeLists.txt`

`pending`：`commitments`（state='ACTIVE'）⋈ `statements`（id=stmt_id AND tenant）取承诺内容；`fired = EXISTS(commitment_triggers WHERE commitment_stmt_id=stmt_id AND tenant_id=? AND status='fired')`；interlocutor 非空 best-effort 过滤（`subject_id=? OR object_value=?`）。

- [ ] **Step 1: 测试文件 + 接线** — `tests/cpp/CMakeLists.txt` 加 `    test_commitment_pending.cpp`。新建测试：seed 一条 COMMITS statement（subject/object 含 "bob"）+ `CommitmentEngine.create_from_statement` 立 ACTIVE + 一条 `commitment_triggers status='fired'`；断言 `pending(tenant, "alice", "bob")` 返回 1 条、`fired=true`、`object_value` 命中。（列以 migration 0021 commitments / 0019 triggers / 0001 statements 为准。）
```cpp
// test_commitment_pending.cpp -- P2.e CommitmentEngine.pending
#include "starling/prospective/commitment_engine.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
#include <sqlite3.h>
#include <string>

using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::prospective::CommitmentEngine;
using starling::prospective::CommitmentView;

namespace {
void seed_commit_stmt(sqlite3* db, const std::string& id, const std::string& obj) {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
        "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES('" + id + "','default','alice','first_person','cognizer',"
        "'bob','owes','str','" + obj + "','" + std::string(64,'a') + "','v1','commits','pos',"
        "0.9,'2026-06-01T09:00:00Z',0.5,'{}',0.0,'2026-06-01T09:00:00Z','user_input',"
        "'consolidated','approved','2026-06-01T09:00:00Z','2026-06-01T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
void seed_fired_trigger(sqlite3* db, const std::string& cid) {
    std::string s = "INSERT INTO commitment_triggers(id,commitment_stmt_id,tenant_id,kind,"
        "spec_json,status,created_at) VALUES('t-" + cid + "','" + cid +
        "','default','time','{}','fired','2026-06-01T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
}  // namespace

TEST(CommitmentPending, ActiveTowardInterlocutorWithFired) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_commit_stmt(db, "c1", "design doc");
    CommitmentEngine ce(*adapter);
    ce.create_from_statement(conn, "c1", "default", "2026-06-01T08:00:00Z", "2026-06-01T07:00:00Z");
    seed_fired_trigger(db, "c1");

    auto rows = ce.pending(conn, "default", "alice", "bob");
    ASSERT_EQ(rows.size(), 1u);
    EXPECT_EQ(rows[0].stmt_id, "c1");
    EXPECT_EQ(rows[0].state, "ACTIVE");
    EXPECT_TRUE(rows[0].fired);
    EXPECT_EQ(rows[0].object_value, "design doc");
    EXPECT_EQ(rows[0].subject_id, "bob");
}

TEST(CommitmentPending, InterlocutorFilterExcludesOthers) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed_commit_stmt(db, "c1", "design doc");   // subject_id='bob'
    CommitmentEngine ce(*adapter);
    ce.create_from_statement(conn, "c1", "default", "", "2026-06-01T07:00:00Z");
    auto rows = ce.pending(conn, "default", "alice", "carol");  // 不命中 bob
    EXPECT_TRUE(rows.empty());
}
```
> seed_commit_stmt 的 holder_id='alice'（committer），subject_id='bob'（interlocutor）。`create_from_statement(conn, stmt_id, tenant, deadline, now)` 签名见 header。

- [ ] **Step 2: 跑确认 FAIL**

- [ ] **Step 3: 头文件 view + pending 声明** — `include/starling/prospective/commitment_engine.hpp`：
```cpp
struct CommitmentView {
    std::string stmt_id, state, deadline;
    std::string subject_id, predicate, object_value;
    bool fired = false;
};
```
（class public 段加：）
```cpp
    std::vector<CommitmentView> pending(persistence::Connection& conn,
            std::string_view tenant_id, std::string_view holder_id,
            std::string_view interlocutor_id);
```
（确保 header include `<vector>`。）

- [ ] **Step 4: 实现 `pending`** — `src/prospective/commitment_engine.cpp`：
```cpp
std::vector<CommitmentView> CommitmentEngine::pending(persistence::Connection& conn,
        std::string_view tenant_id, std::string_view holder_id, std::string_view interlocutor_id) {
    const char* sql =
        "SELECT c.stmt_id, c.state, COALESCE(c.deadline,''), s.subject_id, s.predicate, s.object_value,"
        "       EXISTS(SELECT 1 FROM commitment_triggers t"
        "              WHERE t.commitment_stmt_id=c.stmt_id AND t.tenant_id=c.tenant_id"
        "                AND t.status='fired') AS fired"
        "  FROM commitments c JOIN statements s ON s.id=c.stmt_id AND s.tenant_id=c.tenant_id"
        " WHERE c.tenant_id=?1 AND c.state='ACTIVE' AND s.holder_id=?2"
        "   AND (?3='' OR s.subject_id=?3 OR s.object_value=?3)"
        " ORDER BY c.deadline";
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw starling::bus::detail::make_sqlite_error(db, "CommitmentEngine::pending prepare");
    starling::persistence::StmtHandle h{raw};
    starling::bus::detail::bind_sv(raw, 1, tenant_id);
    starling::bus::detail::bind_sv(raw, 2, holder_id);
    starling::bus::detail::bind_sv(raw, 3, interlocutor_id);
    auto t = [raw](int i){ const unsigned char* c=sqlite3_column_text(raw,i);
                           return c ? std::string(reinterpret_cast<const char*>(c)) : std::string(); };
    std::vector<CommitmentView> out;
    while (sqlite3_step(raw) == SQLITE_ROW) {
        CommitmentView v;
        v.stmt_id=t(0); v.state=t(1); v.deadline=t(2);
        v.subject_id=t(3); v.predicate=t(4); v.object_value=t(5);
        v.fired = sqlite3_column_int(raw, 6) != 0;
        out.push_back(std::move(v));
    }
    return out;
}
```
（补 include `sqlite_helpers.hpp`/`sqlite_handles.hpp` 若缺。）

- [ ] **Step 5: pybind** — `CommitmentView` class_（def_readonly: stmt_id/state/deadline/subject_id/predicate/object_value/fired）+ CommitmentEngine 链上 `.def("pending", [lambda self.connection()], py::arg("tenant_id"), py::arg("holder_id"), py::arg("interlocutor_id"))`。

- [ ] **Step 6: 构建 + 测试**
```bash
cmake --build build && ctest --test-dir build -R CommitmentPending --output-on-failure
```
Expected: 2 passed

- [ ] **Step 7: Commit**（`feat(P2.e): CommitmentEngine.pending + CommitmentView 绑定` + 说明 ⋈statements + fired EXISTS + interlocutor best-effort + trailer）

---

## Task 5: `starling.Memory` —— open/close + llm helper + remember

**Files:**
- Create: `python/starling/memory.py`
- Modify: `python/starling/__init__.py`
- Test: `tests/python/test_memory_facade.py`（新）

- [ ] **Step 1: failing 测试** — `tests/python/test_memory_facade.py`：
```python
"""P2.e Memory facade — open / remember(stub llm) / close。"""
import starling
from starling import _core

# 一个最简 canned XML:抽出一条 alice 视角的 statement。
CANNED_XML = (
    "<extraction><statement>"
    "<holder ref=\"alice\"/><perspective>first_person</perspective>"
    "<subject kind=\"cognizer\" id=\"bob\"/><predicate>owns</predicate>"
    "<object kind=\"str\" canonical_hash=\"h-auth\">auth</object>"
    "<modality>believes</modality><polarity>pos</polarity>"
    "<confidence>0.9</confidence><observed_at>2026-06-01T09:00:00Z</observed_at>"
    "<perceived_by ref=\"alice\"/></statement></extraction>"
)

def test_open_remember_close(tmp_path):
    llm = starling.make_stub_llm(default_xml=CANNED_XML)
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=llm)
    res = mem.remember("Bob owns the auth module")
    assert res.outcome in ("accepted", "idempotent")
    assert len(res.statement_ids) >= 1
    mem.close()

def test_remember_without_llm_raises(tmp_path):
    mem = starling.Memory.open(str(tmp_path / "m2.db"), agent="alice")  # 无 llm
    try:
        mem.remember("anything")
        assert False, "should raise"
    except RuntimeError:
        pass
    finally:
        mem.close()
```
> 注：CANNED_XML 的确切标签须对齐 Extractor 的 XML 解析（参考 `tests/python/test_m0_4_acceptance.py` 的 `SCENARIO_XML`）；implementer 以该样例为准微调标签。stub 用 `set_default_response` 对任意输入返回它。

- [ ] **Step 2: 跑确认 FAIL**（`starling.Memory` / `make_stub_llm` 不存在）
Run: `source .venv/bin/activate && pytest tests/python/test_memory_facade.py -q`

- [ ] **Step 3: 写 `python/starling/memory.py`**（open/close + make_stub_llm/make_openai_llm + remember）：
```python
"""Starling Memory — public application-surface facade (P2.e)."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from starling import _core
from starling import runtime as _runtime
from starling.testing import relax_preflight_for_m0_3


def make_stub_llm(*, default_xml: str, responses: Optional[dict] = None) -> "_core.FakeLLMAdapter":
    """离线确定性 LLM adapter。default_xml 对任意输入返回;responses 可按 prompt_input_hash 覆盖。"""
    llm = _core.FakeLLMAdapter()
    llm.set_default_response(default_xml, True, "")
    for h, xml in (responses or {}).items():
        llm.set_response(h, xml, True, "")
    return llm


def make_openai_llm(*, model: str = "gpt-4o-mini", base_url: str = "") -> "_core.OpenAIAdapter":
    """生产 LLM adapter。key 走 env OPENAI_API_KEY(绝不入参/log)。"""
    return _core.OpenAIAdapter(model, base_url)   # ctor 形参以 module.cpp OpenAIAdapter 绑定为准


@dataclass
class RememberResult:
    engram_ref: str
    statement_ids: list
    outcome: str


class Memory:
    def __init__(self, rt, *, agent: str, tenant_id: str, llm) -> None:
        self._rt = rt
        self._agent = agent
        self._tenant = tenant_id
        self._llm = llm
        self._conn = rt.adapter.connection()
        # 复用单一 embedder/index 实例(worker 与 retriever 共享):
        self._emb = _core.StubEmbeddingAdapter(8)
        self._idx = _core.SqliteBlobVectorIndex()
        self._semantic = _core.SemanticRetriever(rt.adapter, self._emb, self._idx)
        self._completor = _core.PatternCompletor(rt.adapter, self._semantic)
        self._worker = _core.EmbeddingWorker(rt.adapter, self._emb, self._idx)
        self._policy = _core.PolicyEngine(rt.adapter)

    @classmethod
    def open(cls, db_path, *, agent: str = "self", tenant_id: str = "default", llm=None) -> "Memory":
        relax_preflight_for_m0_3()
        rt = _runtime._build_local_store_sqlite_runtime(Path(db_path))
        rt.start()
        return cls(rt, agent=agent, tenant_id=tenant_id, llm=llm)

    def remember(self, text, *, holder: Optional[str] = None,
                 now: str = "2026-06-01T09:00:00Z") -> RememberResult:
        if self._llm is None:
            raise RuntimeError("Memory.remember requires an llm adapter (make_stub_llm/make_openai_llm)")
        holder = holder or self._agent
        payload = text.encode("utf-8")
        inp = _core.EngramInput()  # 直接构造;字段按 evidence/inputs._build 设的最小集
        # 用 inputs.for_user_input 更稳:
        from starling.evidence.inputs import for_user_input
        inp = for_user_input(
            tenant_id=self._tenant, adapter_name="facade", adapter_version="1",
            source_item_id="mem-" + str(abs(hash(text))), source_version="1",
            payload_bytes=payload, privacy_class=_core.PrivacyClass.NORMAL,
            retention_mode=_core.EngramRetentionMode.VERBATIM, created_at=now)
        out = self._rt.bus.append_evidence(inp, None)
        if out["kind"] not in ("accepted", "idempotent"):
            return RememberResult(engram_ref="", statement_ids=[], outcome=out["kind"])
        engram_ref = out["engram_ref"].id
        ext = _core.Extractor(self._conn, self._llm)
        r = ext.run(engram_ref, payload, holder, self._tenant, {})
        return RememberResult(engram_ref=engram_ref,
                              statement_ids=list(r.accepted_statement_ids), outcome=out["kind"])

    def close(self) -> None:
        pass  # adapter 随 GC 释放;预留 hook
```
> **implementer 关键对齐**（写前 grep/读确认，否则按实际改）：
> - `for_user_input` 的必填形参（`privacy_class`/`retention_mode` 的确切 enum 名 —— `_core.PrivacyClass.*` / `_core.EngramRetentionMode.*`，对照 `evidence/inputs.py` 与 module.cpp enum 绑定）。
> - `out["engram_ref"]` 是 `EngramRef`，`.id` 取字符串。
> - `_core.OpenAIAdapter` 构造形参（对照 module.cpp ~L691）。
> - `Extractor.run` 第 2 参 `payload_bytes` 接受 `bytes`。

- [ ] **Step 4: 导出** — `python/starling/__init__.py` 改为：
```python
"""Starling Memory public API."""
from starling import _core
from starling.memory import Memory, make_stub_llm, make_openai_llm, RememberResult

__all__ = ["_core", "Memory", "make_stub_llm", "make_openai_llm", "RememberResult"]
__version__ = "0.0.1"
```

- [ ] **Step 5: 刷新 _core.so（Task 1-4 改了 C++/绑定）+ 跑测试**
```bash
source .venv/bin/activate
cmake --build build && cmake --install build --prefix .venv/lib/python3.14/site-packages
pip install -e . --no-deps --force-reinstall
pytest tests/python/test_memory_facade.py -v
```
Expected: 2 passed（test_open_remember_close + test_remember_without_llm_raises）

- [ ] **Step 6: Commit**（`feat(P2.e): Memory.open/remember/close + llm helper` + trailer）

---

## Task 6: `Memory.recall` + `tick`

**Files:** Modify `python/starling/memory.py`；Test `tests/python/test_memory_facade.py`

- [ ] **Step 1: failing 测试** — 追加：写两条记忆 → tick(嵌入) → recall 命中。
```python
def test_recall_and_tick(tmp_path):
    llm = starling.make_stub_llm(default_xml=CANNED_XML)
    mem = starling.Memory.open(str(tmp_path / "m3.db"), agent="alice", llm=llm)
    mem.remember("Bob owns the auth module")
    stats = mem.tick()                       # 嵌入 + 承诺 tick
    assert stats.embedded >= 0
    hits = mem.recall("bob owns auth", mode="semantic", k=5)
    assert isinstance(hits, list)
    mem.close()
```
> 注:stub 抽取的 statement 需为 consolidated/approved 才被 recall——若抽取产物默认 VOLATILE，recall 可能空。断言放宽为 `isinstance(list)` + 不抛错;真正的"命中"由 working_set 测试(Task 7)用受控数据验证。

- [ ] **Step 2: 跑确认 FAIL**（`recall`/`tick` 不存在）

- [ ] **Step 3: 实现 recall + tick** — `memory.py` 的 `Memory` 加：
```python
    @dataclass
    class _Noop: ...

    def recall(self, query, *, perspective: str = "first_person", k: int = 10, mode: str = "semantic"):
        if mode == "completion":
            res = self._completor.complete(_core.PatternCompletionParams(
                tenant_id=self._tenant, holder_id=self._agent,
                holder_perspective=perspective, cue_text=query, result_k=k))
            return [{"row": s.row, "score": s.activation} for s in res.rows]
        res = self._semantic.vector_recall(_core.SemanticRetrieverParams(
            tenant_id=self._tenant, holder_id=self._agent,
            holder_perspective=perspective, query_text=query, k=k))
        return [{"row": s.row, "score": s.score} for s in res.rows]

    def tick(self, now: str = "2026-06-01T10:00:00Z"):
        self._worker.tick_one_batch(now)
        return self._policy.tick(now)
```
> `recall` 返回 list[dict{row, score}]（row 是 `_core.StatementRow`）。`tick` 返回 `PolicyTickStats`（`.embedded` 不在其中——实为 `.fired/.broken/.auto_withdrawn`）。**修正**：`tick` 应返回一个聚合;先把 worker 批量数与 policy stats 合：
```python
    @dataclass
    class TickStats:
        embedded: int; fired: int; broken: int; auto_withdrawn: int

    def tick(self, now: str = "2026-06-01T10:00:00Z") -> "Memory.TickStats":
        embedded = self._worker.tick_one_batch(now)   # 若返回 int 计数;否则置 0
        ps = self._policy.tick(now)
        return Memory.TickStats(embedded=embedded if isinstance(embedded, int) else 0,
                                fired=ps.fired, broken=ps.broken, auto_withdrawn=ps.auto_withdrawn)
```
> implementer 确认 `tick_one_batch` 返回值类型（若 void 则 embedded=0）。测试相应放宽。

- [ ] **Step 4: 跑测试 PASS**
```bash
pytest tests/python/test_memory_facade.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**（`feat(P2.e): Memory.recall + tick` + trailer）

---

## Task 7: `working_set` 模块（ContextBlock + render_working_set + token 预算）

**Files:**
- Create: `python/starling/working_set.py`
- Modify: `python/starling/memory.py`（加 `render_working_set` 调用 working_set）
- Test: `tests/python/test_working_set.py`（新）

- [ ] **Step 1: failing 测试** — `tests/python/test_working_set.py`：用受控数据（直接 rebuild persona/CG + 立到期承诺 + tick）验证 5 段 + ⚠ 提醒 + 截断。
```python
import starling
from starling import _core
from starling.testing import relax_preflight_for_m0_3
from starling import runtime as _runtime
import sqlite3, pathlib

def _seed_commit_stmt(db, sid, holder, subject, obj):
    db.execute(
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
        "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES(?,?,?,?,'cognizer',?,'owes','str',?,?, 'v1','commits',"
        "'pos',0.9,'2026-06-01T09:00:00Z',0.5,'{}',0.0,'2026-06-01T09:00:00Z','user_input',"
        "'consolidated','approved','2026-06-01T09:00:00Z','2026-06-01T09:00:00Z')",
        (sid,"default",holder,subject,obj,"a"*64))

def test_working_set_has_reminder_after_tick(tmp_path):
    relax_preflight_for_m0_3()
    rt = _runtime._build_local_store_sqlite_runtime(pathlib.Path(str(tmp_path/"ws.db")))
    rt.start()
    db = sqlite3.connect(str(rt.adapter.db_path)); db.execute("PRAGMA busy_timeout=30000")
    _seed_commit_stmt(db, "c1", "alice", "bob", "design doc"); db.commit(); db.close()
    ce = _core.CommitmentEngine(rt.adapter)
    ce.create_from_statement("c1", "default", "2026-06-01T07:00:00Z", "2026-06-01T06:00:00Z")
    # 立一条 fired 的 trigger(直接 seed,模拟 PolicyEngine 已 fire):
    db = sqlite3.connect(str(rt.adapter.db_path)); db.execute("PRAGMA busy_timeout=30000")
    db.execute("INSERT INTO commitment_triggers(id,commitment_stmt_id,tenant_id,kind,spec_json,"
               "status,created_at) VALUES('t1','c1','default','time','{}','fired','2026-06-01T07:00:00Z')")
    db.commit(); db.close()

    mem = starling.Memory.open(str(tmp_path/"ws.db"), agent="alice")  # 复用同库? 见下
    cb = mem.render_working_set(interlocutor="bob", goal="auth", token_budget=2000)
    rendered = cb.render()
    assert "design doc" in rendered
    assert "⚠" in rendered                         # fired → 提醒
    labels = {b.label for b in cb.blocks}
    assert "pending_commitments" in labels
    mem.close()
```
> **WAL 注意**：上面 open 第二个 Memory 指向同库会与第一个 adapter 冲突。**修正**：整个测试用**一个** `Memory`/adapter——先 `mem=Memory.open(...)`，用 `mem._rt.adapter` 建 `CommitmentEngine`，seed 用 `sqlite3.connect(mem._rt.adapter.db_path)` 且在 Memory 打开后、操作间 commit+close（沿用 P2.d smoke 教训：顺序写、busy_timeout、不并发）。implementer 按此重排，避免双 adapter。

- [ ] **Step 2: 跑确认 FAIL**

- [ ] **Step 3: 写 `python/starling/working_set.py`**：
```python
"""Working Set — assemble a prompt-ready ContextBlock from memory (P2.e)."""
from __future__ import annotations
from dataclasses import dataclass, field

def _est(text: str) -> int:        # 近似 token = char//4
    return max(1, len(text) // 4)

@dataclass
class WorkingBlock:
    label: str
    content: str
    token_estimate: int = 0
    def __post_init__(self):
        if not self.token_estimate:
            self.token_estimate = _est(self.content)

@dataclass
class ContextBlock:
    blocks: list = field(default_factory=list)
    truncated: list = field(default_factory=list)
    def render(self) -> str:
        titles = {"persona": "## About me", "common_ground": "## What we share",
                  "relevant_memories": "## Relevant memories",
                  "pending_commitments": "## Pending commitments", "affect": "## Current tone"}
        parts = []
        for b in self.blocks:
            if b.content.strip():
                parts.append(titles.get(b.label, "## " + b.label) + "\n" + b.content)
        return "\n\n".join(parts)

# 优先序:先保动作关键,memories 吃剩余大头。
_PRIORITY = ["pending_commitments", "persona", "common_ground", "relevant_memories", "affect"]

def assemble(sections: dict, token_budget: int) -> ContextBlock:
    """sections: label -> content str。按优先序分配预算,超额截断(按 char)记入 truncated。"""
    cb = ContextBlock()
    remaining = token_budget
    for label in _PRIORITY:
        content = sections.get(label, "")
        if not content:
            continue
        est = _est(content)
        if est <= remaining:
            cb.blocks.append(WorkingBlock(label, content))
            remaining -= est
        else:
            keep_chars = remaining * 4
            cb.blocks.append(WorkingBlock(label, content[:keep_chars]))
            cb.truncated.append(label)
            remaining = 0
    return cb
```

- [ ] **Step 4: `Memory.render_working_set`** — `memory.py` 加（组合 readers + recall + pending + affect）：
```python
    def render_working_set(self, interlocutor, *, goal=None, token_budget: int = 2000):
        from starling import working_set as _ws
        sections = {}
        # persona
        pv = _core.PersonaContainer(self._rt.adapter).read(self._tenant, self._agent)
        if pv.found and pv.dimensions:
            sections["persona"] = "; ".join(f"{k}: {v}" for k, v in pv.dimensions.items())
        # common ground
        cg = _core.CommonGroundContainer(self._rt.adapter).read(self._tenant, f"{self._agent}::{interlocutor}")
        if cg.found and cg.grounded:
            sections["common_ground"] = "\n".join("- " + g for g in cg.grounded)
        # relevant memories
        hits = self.recall(goal or "", mode="semantic", k=5) if goal else []
        if hits:
            sections["relevant_memories"] = "\n".join(
                "- " + f"{h['row'].subject_id} {h['row'].predicate} {h['row'].object_value}" for h in hits)
        # pending commitments(fired → ⚠)
        pend = _core.CommitmentEngine(self._rt.adapter).pending(self._tenant, self._agent, interlocutor)
        if pend:
            lines = []
            for c in pend:
                tag = "⚠ DUE: " if c.fired else ""
                lines.append(f"- {tag}{c.subject_id} {c.predicate} {c.object_value}"
                             + (f" (by {c.deadline})" if c.deadline else ""))
            sections["pending_commitments"] = "\n".join(lines)
        # affect(relevant_memories 的 peak salience)
        peak = 0.0; peak_av = None
        for h in hits:
            aj = h["row"].affect_json
            if aj and aj != "{}":
                av = _core.affect_parse_json(aj)
                s = _core.affect_salience(av, 1.0)
                if s > peak: peak, peak_av = s, av
        if peak_av is not None:
            sections["affect"] = f"salience {peak:.2f}"
        return _ws.assemble(sections, token_budget)
```
> implementer 对齐 `affect_parse_json` / `affect_salience` 的 Python 绑定名（module.cpp affect 段）。

- [ ] **Step 5: 跑测试 PASS**
```bash
source .venv/bin/activate
cmake --install build --prefix .venv/lib/python3.14/site-packages   # 确保 readers 已装
pytest tests/python/test_working_set.py tests/python/test_memory_facade.py -v
```
Expected: 全 passed（含 ⚠ 提醒断言）

- [ ] **Step 6: Commit**（`feat(P2.e): working_set 模块 + Memory.render_working_set` + trailer）

---

## Task 8: `examples/quickstart.py` + 冒烟

**Files:** Create `examples/quickstart.py`；Test `tests/python/test_quickstart_smoke.py`（新）

- [ ] **Step 1: 写 `examples/quickstart.py`**（离线、可独立 `python examples/quickstart.py` 跑、打印 working set）：
```python
"""Starling Memory quickstart — offline, no API key. Run: python examples/quickstart.py"""
import tempfile, pathlib, sqlite3
import starling
from starling import _core

CANNED_XML = (  # stub 抽取:把任意 remember 抽成一条 alice 视角 statement
    "<extraction><statement>"
    "<holder ref=\"alice\"/><perspective>first_person</perspective>"
    "<subject kind=\"cognizer\" id=\"bob\"/><predicate>owns</predicate>"
    "<object kind=\"str\" canonical_hash=\"h-auth\">auth</object>"
    "<modality>believes</modality><polarity>pos</polarity>"
    "<confidence>0.9</confidence><observed_at>2026-06-01T09:00:00Z</observed_at>"
    "<perceived_by ref=\"alice\"/></statement></extraction>"
)

def main() -> str:
    tmp = pathlib.Path(tempfile.mkdtemp()) / "quickstart.db"
    mem = starling.Memory.open(str(tmp), agent="alice", llm=starling.make_stub_llm(default_xml=CANNED_XML))
    mem.remember("Bob owns the auth module.")
    # 显式物化 persona + common ground(本期不自动):
    _core.PersonaContainer(mem._rt.adapter).rebuild(
        "default", "alice",
        [_core.AnchorStatement(stmt_id="a1", anchor_type="self_model_anchor",
                               dimension="traits", value="concise", confidence=0.9)],
        "2026-06-01T09:00:00Z")
    # 立一条到期承诺 + fired trigger(演示提醒):
    db = sqlite3.connect(str(tmp)); db.execute("PRAGMA busy_timeout=30000")
    db.execute("INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
        "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES('c1','default','alice','first_person','cognizer','bob',"
        "'owes','str','design doc',?, 'v1','commits','pos',0.9,'2026-06-01T09:00:00Z',0.5,'{}',0.0,"
        "'2026-06-01T09:00:00Z','user_input','consolidated','approved','2026-06-01T09:00:00Z',"
        "'2026-06-01T09:00:00Z')", ("a"*64,))
    db.execute("INSERT INTO commitment_triggers(id,commitment_stmt_id,tenant_id,kind,spec_json,status,"
        "created_at) VALUES('t1','c1','default','time','{}','fired','2026-06-01T07:00:00Z')")
    db.commit(); db.close()
    _core.CommitmentEngine(mem._rt.adapter).create_from_statement(
        "c1", "default", "2026-06-01T07:00:00Z", "2026-06-01T06:00:00Z")

    mem.tick()
    cb = mem.render_working_set(interlocutor="bob", goal="auth")
    out = cb.render()
    mem.close()
    return out

if __name__ == "__main__":
    print(main())
```

- [ ] **Step 2: 冒烟测试** — `tests/python/test_quickstart_smoke.py`：
```python
import importlib.util, pathlib

def test_quickstart_runs_offline():
    spec = importlib.util.spec_from_file_location(
        "quickstart", str(pathlib.Path(__file__).resolve().parents[2] / "examples" / "quickstart.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    out = mod.main()
    assert "Pending commitments" in out
    assert "⚠" in out          # 到期承诺提醒
```

- [ ] **Step 3: 跑**
```bash
source .venv/bin/activate
python examples/quickstart.py        # 应打印 working set
pytest tests/python/test_quickstart_smoke.py -v
```
Expected: quickstart 打印含 ⚠ 的 working set;smoke passed。

- [ ] **Step 4: Commit**（`feat(P2.e): examples/quickstart.py + 冒烟` + trailer）

---

## Task 9: 全量回归 + close 准备

- [ ] **Step 1: 全量 ctest**
```bash
source .venv/bin/activate && cmake --build build && ctest --test-dir build 2>&1 | tail -4
```
Expected: `100% tests passed`（≈ 498 + CarriesAffectJson + PersonaRead×2 + CommonGroundRead×2 + CommitmentPending×2 = 505；报实际）

- [ ] **Step 2: 全量 pytest**
```bash
pytest tests/python -q 2>&1 | tail -3
```
Expected: 488 baseline + 新增 facade/working_set/quickstart 测试 全 passed

- [ ] **Step 3: 红线检查**
```bash
git diff --stat main -- migrations/ ; echo "(空=无 migration)"
git diff --stat main -- src/neocortex/persona_container.cpp | grep -c rebuild || true   # rebuild 不应被改动逻辑
grep -c "add_executable(starling_tests" tests/cpp/CMakeLists.txt   # =1
```
确认：无 migration；rebuild/五态机写路径未改逻辑（只加 read/pending）；单一 starling_tests。

- [ ] **Step 4: 提交 plan 文件**
```bash
git add docs/superpowers/plans/2026-06-01-p2-e-application-surface.md
git commit -m "$(cat <<'EOF'
docs(P2.e): land application surface implementation plan

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: 报告** — ctest/pytest 数 + commit series，交回控制方做 final review + 合并（merge 前 `git -C /Users/jaredguo-mini/develop/memory/starling status` 查/清 stray，再 `--no-ff` merge `worktree-p2-e-application-surface` 回 main，需 dangerouslyDisableSandbox + 显式 consent）。

---

## Self-Review（plan 作者自检）

**1. Spec coverage：**
- §3 C++ readers → Task 2/3/4 + affect Task 1 ✅
- §4 Memory 门面 → Task 5（open/remember/close/llm helper）+ Task 6（recall/tick）✅
- §5 ContextBlock/render_working_set → Task 7 ✅
- §6 quickstart + 测试 → Task 8 + 各 Task 测试 ✅
- §7 实施约束 → 全局约束 + 各 Task ✅
- 无 migration ✅

**2. Placeholder scan：** 无 TBD。三处"implementer 对齐"是**真实锚点核对**（enum 名 / XML 标签 / tick 返回类型 / common_ground 列名 / OpenAIAdapter 形参），非占位——因这些细节 anchor agent 未逐字确认，已给出确切核对命令与 fallback。

**3. Type consistency：** `PersonaView/CommonGroundView/CommitmentView`、`Memory`/`RememberResult`/`TickStats`/`ContextBlock`/`WorkingBlock`、`make_stub_llm`/`make_openai_llm` 跨 Task 一致；`read`/`pending` 签名一致；conn-free lambda 一致。

**4. 与 spec 偏差（已在"锚点更正"标注，待 close 回补 spec）：** persona content_json shape、CG 返 id→渲染、Memory.open(llm=) 取 adapter 而非 extractor 对象、Extractor.run（非 extract）。
