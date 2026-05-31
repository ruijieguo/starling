# P2.d 模式补全（Pattern Completion / CA3 spreading-activation）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付独立 `PatternCompletor` 检索器（新 `pattern_completion` recall 模式）：给定 cue → `vector_recall` 取种子 → 沿 `statement_edges` 带权 spreading-activation 游走 → 返回 activation 最高的 top-K 情节性子图，隐私先行、纯在线、与 06_hippocampus.md §3 伪代码逐行对应。

**Architecture:** `PatternCompletor` 组合（持引用）`SemanticRetriever` 拿种子 + `SqliteAdapter`。游走用 C++ 循环；每跳一条预编译"边扩展" SQL（`json_each(?frontier) ⋈ statement_edges ⋈ statements`，前向 + 对称边反向 UNION ALL，scope 谓词逐字对齐 `SqliteBlobVectorIndex::search_topk`）。合并取最大不累加；终止于"无新节点 / max 收敛"或 `node_cap` 截断。纯读，无 migration。

**Tech Stack:** C++20 + raw SQLite（≥3.46，JSON1 内建）+ pybind11 + Python 3.14 + GoogleTest + pytest + Ninja。

**Spec:** `docs/superpowers/specs/2026-05-31-p2-d-pattern-completion-design.md`（commit f8a0da1）。所有决策已锁定，本 plan 不重新讨论。

---

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `include/starling/retrieval/pattern_completor.hpp` | `PatternCompletionParams` / `CompletionScored` / `CompletionResult` / `PatternCompletor` 类声明 | Create |
| `src/retrieval/pattern_completor.cpp` | 种子初始化 + 边扩展 SQL + 游走循环 + 取 StatementRow | Create |
| `CMakeLists.txt` | `starling_core` target_sources append `.cpp` | Modify（L114 后） |
| `tests/cpp/CMakeLists.txt` | `STARLING_TEST_SOURCES` append 测试 | Modify（L119 后） |
| `tests/cpp/test_pattern_completor.cpp` | 资源边界 + 隐私 + 算法单测 | Create |
| `bindings/python/module.cpp` | 4 个 pybind class（镜像 SemanticRetriever 那组） | Modify（L1334 后） |
| `tests/python/test_pattern_completion.py` | Python 端到端 smoke | Create |

**关键约束（贯穿所有 Task）：**
- worktree `.claude/worktrees/p2-d-pattern-completion`（branch `worktree-p2-d-pattern-completion`），全部命令在此目录跑。
- 纯读 + 纯在线，**无 migration**（最高现存 0021 不变；`statement_edges`/`statements` schema 不动）。
- `SemanticRetriever`/`vector_recall` **不改**（纯组合调用）。单一 `starling_tests`。
- SQL helpers：`starling::bus::detail::bind_sv` / `make_sqlite_error`（`starling/bus/sqlite_helpers.hpp`）、`starling::persistence::StmtHandle`（`starling/persistence/sqlite_handles.hpp`）、checked `sqlite3_prepare_v2`。参考 `src/retrieval/semantic_retriever.cpp`、`src/vector/sqlite_blob_vector_index.cpp`。
- 每 commit 带 trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`；无 `--no-verify` / `--amend`（hook 失败开新 commit）。
- 本 plan 文件保留 **untracked** 直到 milestone close。API key env-only。
- pybind 改动后刷新 `_core.so`（见 Task 5）。
- **scope 谓词逐字对齐**（隐私边界，不可改）：`tenant_id` + `(?holder='' OR s.holder_id=?holder)` + `(?perspective='' OR s.holder_perspective=?perspective)` + `s.consolidation_state IN ('consolidated','archived')` + `s.review_status NOT IN ('rejected','pending_review')`。`visible_only` 恒 true，永不放宽。

**`degraded` 落地真相（重要）：** 现 `SemanticRetriever::vector_recall` 把 `SemanticResult.degraded` 硬编码 `false`（embedder 恒在，见 `semantic_retriever.cpp:59`）。故 P2.d 的 `CompletionResult.degraded` = 传播 `seeds.degraded`（当前恒 false，接线待 vector_recall 未来补 degraded 路径），并以**空种子早退**作为"不游走"的实际触发。不写"无 embedder→degraded=true"的假测试。

---

## Task 0: Baseline 确认

**Files:** 无（只跑命令）

- [ ] **Step 1: 确认 worktree 与分支**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-d-pattern-completion
git branch --show-current
git rev-parse --short HEAD
```
Expected: `worktree-p2-d-pattern-completion` / `f8a0da1`

- [ ] **Step 2: 配置 + 构建 + ctest baseline**

Run:
```bash
cmake -S . -B build -G Ninja
cmake --build build
ctest --test-dir build
```
Expected: `100% tests passed, 0 tests failed out of 486`

- [ ] **Step 3: pytest baseline**

Run:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/python -q
```
Expected: `487 passed, 13 skipped`

> baseline 不绿不要往下走 —— 报告并停。

---

## Task 1: 头文件 + 类型 + CMake 接线 + 空壳（编译/链接通）

**Files:**
- Create: `include/starling/retrieval/pattern_completor.hpp`
- Create: `src/retrieval/pattern_completor.cpp`
- Modify: `CMakeLists.txt`（L114 `src/prospective/policy_engine.cpp` 后）
- Modify: `tests/cpp/CMakeLists.txt`（L119 `test_policy_engine_subscriber.cpp` 后）
- Create: `tests/cpp/test_pattern_completor.cpp`

- [ ] **Step 1: 写头文件（完整类型契约）**

`include/starling/retrieval/pattern_completor.hpp`:
```cpp
#pragma once
#include <string>
#include <vector>
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/semantic_retriever.hpp"
#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {

struct PatternCompletionParams {
    std::string tenant_id, holder_id, holder_perspective;  // perspective "" = any
    std::string cue_text;          // 部分线索 → 嵌入 → 种子
    int seed_k = 5;                // 种子数（vector_recall k）
    int budget = 20;               // 最大传播步数
    int result_k = 20;             // 返回 top-K
    int node_cap = 1000;           // 访问节点上限
    double theta_propagate = 0.05;
    double decay = 0.5;            // 每步衰减
    std::string trace_id, query_id;
};

struct CompletionScored { StatementRow row; double activation; };

struct CompletionResult {
    std::vector<CompletionScored> rows;   // activation 降序, ≤ result_k
    bool completion_truncated = false;     // 访问节点 ≥ node_cap
    bool degraded = false;                 // 传播自 seeds.degraded
};

class PatternCompletor {
public:
    PatternCompletor(persistence::SqliteAdapter& a, SemanticRetriever& seeds)
        : adapter_(a), seeds_(seeds) {}
    CompletionResult complete(persistence::Connection&, const PatternCompletionParams&);
    persistence::Connection& connection() { return adapter_.connection(); }
private:
    persistence::SqliteAdapter& adapter_;
    SemanticRetriever& seeds_;
};

}  // namespace starling::retrieval
```

- [ ] **Step 2: 写空壳 .cpp（返回空结果，先让它编译链接）**

`src/retrieval/pattern_completor.cpp`:
```cpp
#include "starling/retrieval/pattern_completor.hpp"

namespace starling::retrieval {

CompletionResult PatternCompletor::complete(persistence::Connection& /*conn*/,
                                            const PatternCompletionParams& /*params*/) {
    return CompletionResult{};  // Task 2+ 填充
}

}  // namespace starling::retrieval
```

- [ ] **Step 3: CMake 接线** —— `CMakeLists.txt` 在 `    src/prospective/policy_engine.cpp` 行后、`)` 前加一行：
```cmake
    src/prospective/policy_engine.cpp
    src/retrieval/pattern_completor.cpp
)
```

- [ ] **Step 4: 测试接线** —— `tests/cpp/CMakeLists.txt` 在 `    test_policy_engine_subscriber.cpp` 行后、`)` 前加一行：
```cmake
    test_policy_engine_subscriber.cpp
    test_pattern_completor.cpp
)
```

- [ ] **Step 5: 写最小测试（构造 + 链接 + 空结果）**

`tests/cpp/test_pattern_completor.cpp`:
```cpp
// test_pattern_completor.cpp -- P2.d Pattern Completion (CA3 spreading-activation)
#include "starling/retrieval/pattern_completor.hpp"
#include "starling/retrieval/semantic_retriever.hpp"
#include "starling/embedding/stub_embedding_adapter.hpp"
#include "starling/embedding/embedding_worker.hpp"
#include "starling/vector/sqlite_blob_vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>
#include <string>

using starling::embedding::EmbeddingWorker;
using starling::embedding::StubEmbeddingAdapter;
using starling::persistence::Connection;
using starling::persistence::SqliteAdapter;
using starling::retrieval::CompletionResult;
using starling::retrieval::PatternCompletionParams;
using starling::retrieval::PatternCompletor;
using starling::retrieval::SemanticRetriever;
using starling::vector::SqliteBlobVectorIndex;

namespace {

// Seed a visible statement. render_text = "<subj> <pred> <obj>" = "bob knows <obj>".
// holder/perspective/tenant overridable for privacy/tenant tests.
void seed_stmt(sqlite3* db, const std::string& id, const std::string& obj = "x",
               const std::string& holder = "alice",
               const std::string& perspective = "first_person",
               const std::string& tenant = "default",
               const std::string& state = "consolidated",
               const std::string& review = "approved") {
    std::string s =
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES('"
        + id + "','" + tenant + "','" + holder + "','" + perspective + "','cognizer',"
        "'bob','knows','str','" + obj + "','" + std::string(64, 'a') + "','v1',"
        "'believes','pos',0.9,'2026-05-31T09:00:00Z',0.5,'{}',0.0,"
        "'2026-05-31T09:00:00Z','user_input','" + state + "','" + review + "',"
        "'2026-05-31T09:00:00Z','2026-05-31T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

// Insert a statement_edges row. Default kind MAY_OVERLAP_WITH, tenant default.
void seed_edge(sqlite3* db, const std::string& id, const std::string& src,
               const std::string& dst, double weight,
               const std::string& kind = "MAY_OVERLAP_WITH",
               const std::string& tenant = "default") {
    std::string s =
        "INSERT INTO statement_edges(id,tenant_id,src_id,dst_id,edge_kind,weight,"
        "created_at,metadata_json) VALUES('"
        + id + "','" + tenant + "','" + src + "','" + dst + "','" + kind + "',"
        + std::to_string(weight) + ",'2026-05-31T00:00:00Z','{\"resolved\":false}')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}

// Embed exactly the already-inserted statements (call BEFORE inserting walk-only
// target nodes so the worker doesn't auto-create overlap edges among them).
void embed_existing(SqliteAdapter& adapter, StubEmbeddingAdapter& emb,
                    SqliteBlobVectorIndex& idx, Connection& conn) {
    EmbeddingWorker worker(adapter, emb, idx);
    worker.tick_one_batch(conn, "2026-05-31T10:00:00Z");
}

}  // namespace

TEST(PatternCompletor, ConstructsAndReturnsEmptyWhenNoSeeds) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;
    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);

    PatternCompletionParams p;
    p.tenant_id = "default";
    p.holder_id = "alice";
    p.cue_text  = "bob knows nothing";  // 无任何向量 → 无种子

    auto res = pc.complete(conn, p);
    EXPECT_TRUE(res.rows.empty());
    EXPECT_FALSE(res.completion_truncated);
}
```

- [ ] **Step 6: 构建 + 跑该测试**

Run:
```bash
cmake --build build
ctest --test-dir build -R PatternCompletor
```
Expected: `ConstructsAndReturnsEmptyWhenNoSeeds` PASS（空壳即满足）

- [ ] **Step 7: Commit**
```bash
git add include/starling/retrieval/pattern_completor.hpp src/retrieval/pattern_completor.cpp \
        CMakeLists.txt tests/cpp/CMakeLists.txt tests/cpp/test_pattern_completor.cpp
git commit -m "$(cat <<'EOF'
feat(P2.d): PatternCompletor 类型骨架 + CMake 接线

pattern_completor.hpp 定 PatternCompletionParams/CompletionScored/CompletionResult/
PatternCompletor(组合 SemanticRetriever);空壳 complete() 返回空结果;接入 starling_core
与 starling_tests;ConstructsAndReturnsEmptyWhenNoSeeds 通过。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 种子 + 空种子早退 + 种子-only

**Files:**
- Modify: `src/retrieval/pattern_completor.cpp`
- Test: `tests/cpp/test_pattern_completor.cpp`

- [ ] **Step 1: 写 failing 测试（种子-only：1 种子无边 → 返回种子, activation 1.0）**

追加到 `test_pattern_completor.cpp`:
```cpp
TEST(PatternCompletor, SeedsOnlyNoEdges) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);   // 只嵌入 seed

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);

    PatternCompletionParams p;
    p.tenant_id = "default";
    p.holder_id = "alice";
    p.holder_perspective = "first_person";
    p.cue_text  = "bob knows cats";  // == seed render_text
    p.seed_k    = 5;

    auto res = pc.complete(conn, p);
    ASSERT_EQ(res.rows.size(), 1u);
    EXPECT_EQ(res.rows[0].row.id, "seed");
    EXPECT_DOUBLE_EQ(res.rows[0].activation, 1.0);
    EXPECT_FALSE(res.completion_truncated);
    EXPECT_FALSE(res.degraded);
}
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cmake --build build && ctest --test-dir build -R PatternCompletor.SeedsOnlyNoEdges`
Expected: FAIL（空壳返回空，`rows.size()==0`）

- [ ] **Step 3: 实现种子 + activation 初始化 + top-K 取行**

替换 `src/retrieval/pattern_completor.cpp` 全文：
```cpp
#include "starling/retrieval/pattern_completor.hpp"

#include <sqlite3.h>
#include <algorithm>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

namespace starling::retrieval {

namespace {
using starling::bus::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

// Fetch a full StatementRow by (id, tenant) re-checking visibility — mirrors
// semantic_retriever.cpp kSelectByIdSql exactly (defense-in-depth on top of the
// walk's per-hop scope predicate).
constexpr const char* kSelectByIdSql =
    "SELECT id, tenant_id, holder_id, holder_perspective, "
    "       subject_kind, subject_id, predicate, "
    "       object_kind, object_value, canonical_object_hash, "
    "       modality, polarity, confidence, observed_at, "
    "       valid_from, valid_to, consolidation_state, review_status, "
    "       evidence_json "
    "  FROM statements "
    " WHERE id = ?1 AND tenant_id = ?2 "
    "   AND consolidation_state IN ('consolidated','archived') "
    "   AND review_status NOT IN ('rejected','pending_review') "
    " LIMIT 1;";

StatementRow fetch_row(persistence::Connection& conn, const std::string& id,
                       const std::string& tenant) {
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, kSelectByIdSql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PatternCompletor::fetch_row prepare");
    StmtHandle h{raw};
    sqlite3_bind_text(raw, 1, id.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(raw, 2, tenant.c_str(), -1, SQLITE_TRANSIENT);

    auto col = [raw](int i) {
        const unsigned char* t = sqlite3_column_text(raw, i);
        return t ? std::string(reinterpret_cast<const char*>(t)) : std::string();
    };
    StatementRow row;  // empty id signals "vanished / not visible"
    if (sqlite3_step(raw) != SQLITE_ROW) return row;
    row.id = col(0); row.tenant_id = col(1); row.holder_id = col(2);
    row.holder_perspective = col(3); row.subject_kind = col(4); row.subject_id = col(5);
    row.predicate = col(6); row.object_kind = col(7); row.object_value = col(8);
    row.canonical_object_hash = col(9); row.modality = col(10); row.polarity = col(11);
    row.confidence = sqlite3_column_double(raw, 12); row.observed_at = col(13);
    row.valid_from = col(14); row.valid_to = col(15); row.consolidation_state = col(16);
    row.review_status = col(17); row.evidence_json = col(18);
    return row;
}

}  // namespace

CompletionResult PatternCompletor::complete(persistence::Connection& conn,
                                            const PatternCompletionParams& params) {
    CompletionResult out;

    // Step 1: seeds via vector_recall (privacy-first; reused verbatim).
    SemanticRetrieverParams sp;
    sp.tenant_id = params.tenant_id;
    sp.holder_id = params.holder_id;
    sp.holder_perspective = params.holder_perspective;
    sp.query_text = params.cue_text;
    sp.k = params.seed_k;
    sp.trace_id = params.trace_id;
    sp.query_id = params.query_id;
    auto seeds = seeds_.vector_recall(conn, sp);
    out.degraded = seeds.degraded;
    if (seeds.rows.empty()) return out;  // no seeds → no walk

    // Step 2: activation init (seeds at 1.0).
    std::unordered_map<std::string, double> activation;
    std::unordered_set<std::string> visited;
    for (const auto& s : seeds.rows) {
        activation[s.row.id] = 1.0;
        visited.insert(s.row.id);
    }

    // Step 3: spreading-activation walk — Task 4 填充（先空着）。

    // Step 4: top result_k by activation desc.
    std::vector<std::pair<std::string, double>> ranked(activation.begin(), activation.end());
    std::sort(ranked.begin(), ranked.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });
    if (static_cast<int>(ranked.size()) > params.result_k)
        ranked.resize(static_cast<size_t>(params.result_k));

    for (const auto& [id, act] : ranked) {
        StatementRow row = fetch_row(conn, id, params.tenant_id);
        if (row.id.empty()) continue;  // vanished between walk and fetch
        out.rows.push_back(CompletionScored{std::move(row), act});
    }
    return out;
}

}  // namespace starling::retrieval
```

- [ ] **Step 4: 跑测试确认 PASS（含 Task 0/1 的 ConstructsAndReturnsEmptyWhenNoSeeds + SeedsOnlyNoEdges）**

Run: `cmake --build build && ctest --test-dir build -R PatternCompletor`
Expected: 2 passed（空种子早退 + 种子-only 各通过）

- [ ] **Step 5: Commit**
```bash
git add src/retrieval/pattern_completor.cpp tests/cpp/test_pattern_completor.cpp
git commit -m "$(cat <<'EOF'
feat(P2.d): 种子初始化 + 空种子早退 + top-K 取行

complete() 经 vector_recall 取种子(activation=1.0),空种子早退(degraded 传播自
seeds);fetch_row 复用 semantic_retriever kSelectByIdSql 再校验可见性;top-K 排序取
StatementRow。游走循环留待 Task 4。SeedsOnlyNoEdges 通过。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 边扩展 SQL（前向+对称反向 + scope 谓词）+ edge_weight/clamp + 单跳

**Files:**
- Modify: `src/retrieval/pattern_completor.cpp`
- Test: `tests/cpp/test_pattern_completor.cpp`

- [ ] **Step 1: 写 failing 测试（单跳前向 + 边权用存储相似度 + clamp）**

追加：
```cpp
// 单跳前向:seed→A(w=0.9)、seed→B(w=0.5)。decay=0.5 →
//   A=0.9*0.5=0.45, B=0.5*0.5=0.25。存储相似度参与(高权更高)。
TEST(PatternCompletor, OneHopForwardUsesStoredWeight) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);   // 只嵌入 seed
    seed_stmt(db, "A", "a");                     // walk-only 目标,无向量
    seed_stmt(db, "B", "b");
    seed_edge(db, "e1", "seed", "A", 0.9);
    seed_edge(db, "e2", "seed", "B", 0.5);

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats"; p.seed_k = 5;

    auto res = pc.complete(conn, p);
    std::unordered_map<std::string, double> act;
    for (const auto& r : res.rows) act[r.row.id] = r.activation;
    ASSERT_TRUE(act.count("A")); ASSERT_TRUE(act.count("B"));
    EXPECT_DOUBLE_EQ(act["A"], 0.45);
    EXPECT_DOUBLE_EQ(act["B"], 0.25);
    EXPECT_GT(act["A"], act["B"]);
}

// clamp:w=1.5→1.0→A=0.5;w=-0.2→0→contrib=0<θ→B 被剪。
TEST(PatternCompletor, EdgeWeightClamped) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "A", "a");
    seed_stmt(db, "B", "b");
    seed_edge(db, "e1", "seed", "A", 1.5);   // → clamp 1.0
    seed_edge(db, "e2", "seed", "B", -0.2);  // → clamp 0 → 剪

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    std::unordered_map<std::string, double> act;
    for (const auto& r : res.rows) act[r.row.id] = r.activation;
    ASSERT_TRUE(act.count("A"));
    EXPECT_DOUBLE_EQ(act["A"], 0.5);
    EXPECT_FALSE(act.count("B")) << "negative-weight edge must be pruned";
}

// 对称反向:边写 src=A dst=seed;种子=seed → A 经反向 UNION 可达,act=0.5。
TEST(PatternCompletor, SymmetricReverseTraversal) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "A", "a");
    seed_edge(db, "e1", "A", "seed", 1.0);   // seed 作为 dst

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    std::unordered_map<std::string, double> act;
    for (const auto& r : res.rows) act[r.row.id] = r.activation;
    ASSERT_TRUE(act.count("A"));
    EXPECT_DOUBLE_EQ(act["A"], 0.5);
}
```

- [ ] **Step 2: 跑确认 FAIL**

Run: `cmake --build build && ctest --test-dir build -R "PatternCompletor.OneHop|PatternCompletor.EdgeWeight|PatternCompletor.Symmetric"`
Expected: FAIL（游走未实现，A/B 不在结果）

- [ ] **Step 3: 实现 edge_weight + 边扩展 SQL + 单步传播**

在 `src/retrieval/pattern_completor.cpp` 的匿名 namespace 内、`fetch_row` 之前，加：
```cpp
// per-kind 乘子;P2.d 全部传播边默认 1.0(MAY_OVERLAP_WITH 用存储余弦权)。
double kind_multiplier(const std::string& /*kind*/) { return 1.0; }

// edge_weight = kind_multiplier × clamp(stored_weight, 0, 1)。
double edge_weight(const std::string& kind, double stored_weight) {
    double w = stored_weight;
    if (w < 0.0) w = 0.0;
    if (w > 1.0) w = 1.0;
    return kind_multiplier(kind) * w;
}

// frontier id 集合 → JSON 数组字面量。statement id 为 UUID(无引号/反斜杠),手工拼安全。
std::string build_frontier_json(const std::unordered_map<std::string, double>& activation) {
    std::string s = "[";
    bool first = true;
    for (const auto& kv : activation) {
        if (!first) s += ",";
        s += "\"" + kv.first + "\"";
        first = false;
    }
    s += "]";
    return s;
}

struct EdgeHit { std::string src_id, target_id, edge_kind; double weight; };

// 每跳边扩展:前向(前沿作 src,target=dst,所有传播边) + 对称反向(前沿作 dst,
// target=src,仅 MAY_OVERLAP_WITH)。scope 谓词逐字对齐 search_topk,隐私永不放宽。
std::vector<EdgeHit> expand(persistence::Connection& conn,
                            const std::string& frontier_json,
                            const PatternCompletionParams& p) {
    const char* sql =
        "SELECT f.value AS src_id, e.dst_id AS target_id, e.edge_kind, e.weight"
        "  FROM json_each(?1) f"
        "  JOIN statement_edges e ON e.tenant_id = ?2 AND e.src_id = f.value"
        "  JOIN statements s ON s.id = e.dst_id AND s.tenant_id = e.tenant_id"
        " WHERE e.edge_kind IN ('MAY_OVERLAP_WITH','derived_from','evidence',"
        "                       'OBSERVED_BY','SHARED_GROUND')"
        "   AND (?3 = '' OR s.holder_id = ?3)"
        "   AND (?4 = '' OR s.holder_perspective = ?4)"
        "   AND s.consolidation_state IN ('consolidated','archived')"
        "   AND s.review_status NOT IN ('rejected','pending_review')"
        " UNION ALL "
        "SELECT f.value AS src_id, e.src_id AS target_id, e.edge_kind, e.weight"
        "  FROM json_each(?1) f"
        "  JOIN statement_edges e ON e.tenant_id = ?2 AND e.dst_id = f.value"
        "  JOIN statements s ON s.id = e.src_id AND s.tenant_id = e.tenant_id"
        " WHERE e.edge_kind IN ('MAY_OVERLAP_WITH')"
        "   AND (?3 = '' OR s.holder_id = ?3)"
        "   AND (?4 = '' OR s.holder_perspective = ?4)"
        "   AND s.consolidation_state IN ('consolidated','archived')"
        "   AND s.review_status NOT IN ('rejected','pending_review')";
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "PatternCompletor::expand prepare");
    StmtHandle h{raw};
    auto bind_txt = [raw](int i, const std::string& v) {
        sqlite3_bind_text(raw, i, v.c_str(), -1, SQLITE_TRANSIENT);
    };
    bind_txt(1, frontier_json);
    bind_txt(2, p.tenant_id);
    bind_txt(3, p.holder_id);
    bind_txt(4, p.holder_perspective);

    auto col = [raw](int i) {
        const unsigned char* t = sqlite3_column_text(raw, i);
        return t ? std::string(reinterpret_cast<const char*>(t)) : std::string();
    };
    std::vector<EdgeHit> hits;
    while (sqlite3_step(raw) == SQLITE_ROW) {
        hits.push_back(EdgeHit{col(0), col(1), col(2), sqlite3_column_double(raw, 3)});
    }
    return hits;
}
```

然后把 `complete()` 里 `// Step 3: ... 留待 Task 4（先空着）` 替换为**单步**传播（Task 4 再扩成循环）：
```cpp
    // Step 3: spreading-activation walk（Task 3 单步;Task 4 扩成多步循环 + 终止）。
    {
        const std::string frontier_json = build_frontier_json(activation);
        auto hits = expand(conn, frontier_json, params);
        std::unordered_map<std::string, double> next;
        for (const auto& e : hits) {
            const double contrib =
                activation[e.src_id] * edge_weight(e.edge_kind, e.weight) * params.decay;
            if (contrib < params.theta_propagate) continue;
            auto it = next.find(e.target_id);
            if (it == next.end() || contrib > it->second) next[e.target_id] = contrib;
        }
        for (const auto& kv : next) {
            visited.insert(kv.first);
            auto it = activation.find(kv.first);
            if (it == activation.end() || kv.second > it->second)
                activation[kv.first] = kv.second;
        }
    }
```

- [ ] **Step 4: 跑确认 PASS**

Run: `cmake --build build && ctest --test-dir build -R PatternCompletor`
Expected: 5 passed（前 2 + OneHopForwardUsesStoredWeight + EdgeWeightClamped + SymmetricReverseTraversal）

- [ ] **Step 5: Commit**
```bash
git add src/retrieval/pattern_completor.cpp tests/cpp/test_pattern_completor.cpp
git commit -m "$(cat <<'EOF'
feat(P2.d): 边扩展 SQL(前向+对称反向)+ edge_weight/clamp + 单步传播

expand() 每跳一条 json_each(?frontier) ⋈ statement_edges ⋈ statements,前向走全部
5 类传播边、对称反向仅 MAY_OVERLAP_WITH;scope 谓词逐字对齐 search_topk。
edge_weight=kind_multiplier×clamp(stored,0,1),MAY_OVERLAP_WITH 用存储余弦权。
单步传播 + max 合并。OneHop/EdgeWeightClamped/SymmetricReverse 通过。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 隐私严格逐跳 + 租户隔离（专项 checkpoint）

**Files:**
- Test: `tests/cpp/test_pattern_completor.cpp`（实现已在 Task 3 的 SQL 内，本 Task 专项验证隐私不变式）

> 隐私谓词已随 Task 3 的 `expand` SQL 落地。本 Task 是**隐私 checkpoint**：单独验证"跨视角/跨 holder/跨租户节点绝不进 activation 或输出"。若任一测试挂，回 Task 3 SQL 修。

- [ ] **Step 1: 写隐私 + 租户测试**

追加：
```cpp
// 严格逐跳:overlap 边连到别 perspective 的陈述 → 该节点不进结果。
TEST(PatternCompletor, StrictPerHopExcludesOtherPerspective) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats", "alice", "first_person");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "other", "cats", "alice", "third_person");  // 别 perspective
    seed_edge(db, "e1", "seed", "other", 1.0);

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    for (const auto& r : res.rows)
        EXPECT_NE(r.row.id, "other") << "cross-perspective node must never be activated";
}

// 别 holder 同理被排除。
TEST(PatternCompletor, StrictPerHopExcludesOtherHolder) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats", "alice", "first_person");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "bobstmt", "cats", "bob", "first_person");  // 别 holder
    seed_edge(db, "e1", "seed", "bobstmt", 1.0);

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    for (const auto& r : res.rows)
        EXPECT_NE(r.row.id, "bobstmt") << "cross-holder node must never be activated";
}

// 跨租户边不可桥:边在 default,dst 仅存在于 tenant 'other' → JOIN 无果。
TEST(PatternCompletor, TenantIsolationNotBridged) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats", "alice", "first_person", "default");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "xt", "cats", "alice", "first_person", "other");  // 别租户
    seed_edge(db, "e1", "seed", "xt", 1.0, "MAY_OVERLAP_WITH", "default");

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    for (const auto& r : res.rows)
        EXPECT_NE(r.row.id, "xt") << "cross-tenant node must never be bridged";
}
```

- [ ] **Step 2: 跑测试**

Run: `cmake --build build && ctest --test-dir build -R "PatternCompletor.Strict|PatternCompletor.Tenant"`
Expected: 3 passed（Task 3 的 scope 谓词已保证；若 FAIL 回 Task 3 修 SQL）

- [ ] **Step 3: Commit**
```bash
git add tests/cpp/test_pattern_completor.cpp
git commit -m "$(cat <<'EOF'
test(P2.d): 隐私严格逐跳 + 租户隔离 checkpoint

验证跨 perspective/holder/tenant 节点绝不进 activation 或输出(scope 谓词随
Task 3 expand SQL 已落地)。StrictPerHopExcludesOtherPerspective/OtherHolder +
TenantIsolationNotBridged 通过。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 多步游走循环（max 合并 + θ/收敛终止 + node_cap 截断）

**Files:**
- Modify: `src/retrieval/pattern_completor.cpp`
- Test: `tests/cpp/test_pattern_completor.cpp`

- [ ] **Step 1: 写多步测试（菱形 max 不累加 / 衰减链 θ 收敛 / node_cap 截断）**

追加：
```cpp
// 菱形:seed→A,seed→B,A→D,B→D(全 w=1.0,decay=0.5)。
//   A=B=0.5;D 经两路各得 0.5*0.5=0.25,max 合并 → 0.25(非 sum 0.5)。
TEST(PatternCompletor, DiamondMaxNotAccumulate) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);
    seed_stmt(db, "A", "a"); seed_stmt(db, "B", "b"); seed_stmt(db, "D", "d");
    seed_edge(db, "e1", "seed", "A", 1.0);
    seed_edge(db, "e2", "seed", "B", 1.0);
    seed_edge(db, "e3", "A", "D", 1.0);
    seed_edge(db, "e4", "B", "D", 1.0);

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats";

    auto res = pc.complete(conn, p);
    std::unordered_map<std::string, double> act;
    for (const auto& r : res.rows) act[r.row.id] = r.activation;
    ASSERT_TRUE(act.count("D"));
    EXPECT_DOUBLE_EQ(act["D"], 0.25) << "max-merge, not sum";
    EXPECT_DOUBLE_EQ(act["A"], 0.5);
}

// 衰减链 seed→n1→n2→n3→n4→n5(全 w=1.0)。activation=0.5^depth:
//   n1=.5 n2=.25 n3=.125 n4=.0625 n5=.03125<θ(0.05) → n5 被剪。
TEST(PatternCompletor, DecayChainThetaCutoff) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);
    for (int i = 1; i <= 5; ++i) seed_stmt(db, "n" + std::to_string(i), "n" + std::to_string(i));
    seed_edge(db, "c0", "seed", "n1", 1.0);
    seed_edge(db, "c1", "n1", "n2", 1.0);
    seed_edge(db, "c2", "n2", "n3", 1.0);
    seed_edge(db, "c3", "n3", "n4", 1.0);
    seed_edge(db, "c4", "n4", "n5", 1.0);

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats"; p.result_k = 20;

    auto res = pc.complete(conn, p);
    std::unordered_map<std::string, double> act;
    for (const auto& r : res.rows) act[r.row.id] = r.activation;
    EXPECT_TRUE(act.count("n4")); EXPECT_DOUBLE_EQ(act["n4"], 0.0625);
    EXPECT_FALSE(act.count("n5")) << "activation 0.03125 < theta 0.05 → pruned";
}

// node_cap 截断:seed 连 1100 个目标(w=1.0)→ node_count≥1000 → truncated,结果≤result_k。
TEST(PatternCompletor, NodeCapTruncation) {
    auto adapter = SqliteAdapter::open(":memory:");
    Connection& conn = adapter->connection();
    sqlite3* db = conn.raw();
    StubEmbeddingAdapter emb(8);
    SqliteBlobVectorIndex idx;

    seed_stmt(db, "seed", "cats");
    embed_existing(*adapter, emb, idx, conn);
    for (int i = 0; i < 1100; ++i) {
        std::string nid = "t" + std::to_string(i);
        seed_stmt(db, nid, nid);
        seed_edge(db, "edge" + std::to_string(i), "seed", nid, 1.0);
    }

    SemanticRetriever sr(*adapter, emb, idx);
    PatternCompletor pc(*adapter, sr);
    PatternCompletionParams p;
    p.tenant_id = "default"; p.holder_id = "alice"; p.holder_perspective = "first_person";
    p.cue_text = "bob knows cats"; p.result_k = 20; p.node_cap = 1000;

    auto res = pc.complete(conn, p);
    EXPECT_TRUE(res.completion_truncated);
    EXPECT_LE(res.rows.size(), 20u);
}
```

- [ ] **Step 2: 跑确认 FAIL**

Run: `cmake --build build && ctest --test-dir build -R "PatternCompletor.Diamond|PatternCompletor.Decay|PatternCompletor.NodeCap"`
Expected: FAIL（单步只走一跳，n2+/D 不可达；无截断）

- [ ] **Step 3: 把单步替换为多步循环**

把 Task 3 加的 `// Step 3: ... 单步` 整块替换为：
```cpp
    // Step 3: spreading-activation walk（06_hippocampus.md §3）。
    int node_count = static_cast<int>(visited.size());
    bool truncated = false;
    for (int step = 0; step < params.budget; ++step) {
        const std::string frontier_json = build_frontier_json(activation);
        auto hits = expand(conn, frontier_json, params);

        std::unordered_map<std::string, double> next;
        for (const auto& e : hits) {
            const double contrib =
                activation[e.src_id] * edge_weight(e.edge_kind, e.weight) * params.decay;
            if (contrib < params.theta_propagate) continue;
            auto it = next.find(e.target_id);
            if (it == next.end() || contrib > it->second) next[e.target_id] = contrib;
        }

        bool any_new = false;
        for (const auto& kv : next) {
            if (visited.insert(kv.first).second) { ++node_count; any_new = true; }
            auto it = activation.find(kv.first);
            if (it == activation.end() || kv.second > it->second)
                activation[kv.first] = kv.second;
        }

        if (node_count >= params.node_cap) { truncated = true; break; }
        // 收敛:本步无新节点即停。(设计的 max(activation)<θ 被种子 1.0 支配、永不触发;
        //  re-expand-all 下"无新节点"是 operative 收敛判据,budget 为兜底上限。)
        if (!any_new) break;
    }
    out.completion_truncated = truncated;
```

- [ ] **Step 4: 跑全部 PatternCompletor 测试确认 PASS**

Run: `cmake --build build && ctest --test-dir build -R PatternCompletor`
Expected: 11 passed（Task 1–5 全部）

- [ ] **Step 5: Commit**
```bash
git add src/retrieval/pattern_completor.cpp tests/cpp/test_pattern_completor.cpp
git commit -m "$(cat <<'EOF'
feat(P2.d): 多步 spreading-activation 循环 + max 合并 + node_cap 截断

单步扩成 budget 步循环:每步 re-expand 全 activation,max 合并(步内+跨步),
node_count≥node_cap 截断 completion_truncated,无新节点即收敛(种子 1.0 使
max<θ 永不触发,budget 兜底)。Diamond/DecayChain/NodeCap 通过,11 项全绿。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: pybind 绑定 + 刷新 _core.so

**Files:**
- Modify: `bindings/python/module.cpp`（L1334 `SemanticRetriever` 绑定块后）

- [ ] **Step 1: 加 4 个 pybind class（镜像 SemanticRetriever 那组）**

在 `bindings/python/module.cpp` 的 `SemanticRetriever` 绑定（`.def("vector_recall", ...)` 收尾的 `;`）之后插入：
```cpp
    // ── P2.d: Pattern Completion ──────────────────────────────────────────
    py::class_<starling::retrieval::PatternCompletionParams>(
            m, "PatternCompletionParams")
        .def(py::init([](std::string tenant_id, std::string holder_id,
                         std::string holder_perspective, std::string cue_text,
                         int seed_k, int budget, int result_k, int node_cap,
                         double theta_propagate, double decay,
                         std::string trace_id, std::string query_id) {
            starling::retrieval::PatternCompletionParams p;
            p.tenant_id = std::move(tenant_id);
            p.holder_id = std::move(holder_id);
            p.holder_perspective = std::move(holder_perspective);
            p.cue_text = std::move(cue_text);
            p.seed_k = seed_k; p.budget = budget; p.result_k = result_k;
            p.node_cap = node_cap; p.theta_propagate = theta_propagate; p.decay = decay;
            p.trace_id = std::move(trace_id); p.query_id = std::move(query_id);
            return p;
        }),
        py::arg("tenant_id") = "", py::arg("holder_id") = "",
        py::arg("holder_perspective") = "", py::arg("cue_text") = "",
        py::arg("seed_k") = 5, py::arg("budget") = 20, py::arg("result_k") = 20,
        py::arg("node_cap") = 1000, py::arg("theta_propagate") = 0.05,
        py::arg("decay") = 0.5, py::arg("trace_id") = "", py::arg("query_id") = "")
        .def_readwrite("tenant_id",          &starling::retrieval::PatternCompletionParams::tenant_id)
        .def_readwrite("holder_id",          &starling::retrieval::PatternCompletionParams::holder_id)
        .def_readwrite("holder_perspective", &starling::retrieval::PatternCompletionParams::holder_perspective)
        .def_readwrite("cue_text",           &starling::retrieval::PatternCompletionParams::cue_text)
        .def_readwrite("seed_k",             &starling::retrieval::PatternCompletionParams::seed_k)
        .def_readwrite("budget",             &starling::retrieval::PatternCompletionParams::budget)
        .def_readwrite("result_k",           &starling::retrieval::PatternCompletionParams::result_k)
        .def_readwrite("node_cap",           &starling::retrieval::PatternCompletionParams::node_cap)
        .def_readwrite("theta_propagate",    &starling::retrieval::PatternCompletionParams::theta_propagate)
        .def_readwrite("decay",              &starling::retrieval::PatternCompletionParams::decay)
        .def_readwrite("trace_id",           &starling::retrieval::PatternCompletionParams::trace_id)
        .def_readwrite("query_id",           &starling::retrieval::PatternCompletionParams::query_id);

    py::class_<starling::retrieval::CompletionScored>(m, "CompletionScored")
        .def_readonly("row",        &starling::retrieval::CompletionScored::row)
        .def_readonly("activation", &starling::retrieval::CompletionScored::activation);

    py::class_<starling::retrieval::CompletionResult>(m, "CompletionResult")
        .def_readonly("rows",                 &starling::retrieval::CompletionResult::rows)
        .def_readonly("completion_truncated", &starling::retrieval::CompletionResult::completion_truncated)
        .def_readonly("degraded",             &starling::retrieval::CompletionResult::degraded);

    py::class_<starling::retrieval::PatternCompletor>(m, "PatternCompletor")
        .def(py::init<starling::persistence::SqliteAdapter&,
                      starling::retrieval::SemanticRetriever&>(),
             py::keep_alive<1, 2>(), py::keep_alive<1, 3>(),
             py::arg("adapter"), py::arg("seeds"))
        .def("complete",
             [](starling::retrieval::PatternCompletor& s,
                const starling::retrieval::PatternCompletionParams& p) {
                 return s.complete(s.connection(), p);
             },
             py::arg("params"));
```
确认 `module.cpp` 顶部已 `#include "starling/retrieval/pattern_completor.hpp"`（若无则在 retrieval includes 处加）。

- [ ] **Step 2: 构建 + 刷新 _core.so（cmake --install 是关键）**

Run:
```bash
cmake --build build
cmake --install build --prefix .venv/lib/python3.14/site-packages
pip install -e . --no-deps --force-reinstall
```
Expected: 构建 + 安装无错

- [ ] **Step 3: 冒烟（绑定可导入 + 类存在）**

Run:
```bash
python -c "from starling import _core; print(_core.PatternCompletor, _core.PatternCompletionParams, _core.CompletionResult)"
```
Expected: 打印三个类型，无 AttributeError

- [ ] **Step 4: Commit**
```bash
git add bindings/python/module.cpp
git commit -m "$(cat <<'EOF'
feat(P2.d): PatternCompletor pybind 绑定

PatternCompletionParams/CompletionScored/CompletionResult/PatternCompletor 绑定,
镜像 SemanticRetriever(py::keep_alive 引用保活 adapter+seeds,complete conn-free)。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Python smoke

**Files:**
- Create: `tests/python/test_pattern_completion.py`

- [ ] **Step 1: 写端到端 smoke（复用 runtime fixture 形态）**

`tests/python/test_pattern_completion.py`:
```python
"""P2.d Pattern Completion smoke — 写 statements → 嵌入 → overlap 边 → complete()。"""
import sqlite3
from starling import _core
from starling.testing import relax_preflight_for_m0_3  # 同其他 runtime 测试


def _seed_stmt(db, sid, obj, holder="alice", perspective="first_person", tenant="default"):
    db.execute(
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
        "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
        "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
        "created_at,updated_at) VALUES(?,?,?,?,'cognizer','bob','knows','str',?,?,'v1',"
        "'believes','pos',0.9,'2026-05-31T09:00:00Z',0.5,'{}',0.0,"
        "'2026-05-31T09:00:00Z','user_input','consolidated','approved',"
        "'2026-05-31T09:00:00Z','2026-05-31T09:00:00Z')",
        (sid, tenant, holder, perspective, obj, "a" * 64),
    )


def _seed_edge(db, eid, src, dst, weight, tenant="default"):
    db.execute(
        "INSERT INTO statement_edges(id,tenant_id,src_id,dst_id,edge_kind,weight,"
        "created_at,metadata_json) VALUES(?,?,?,?,'MAY_OVERLAP_WITH',?,"
        "'2026-05-31T00:00:00Z','{\"resolved\":false}')",
        (eid, tenant, src, dst, weight),
    )


def test_pattern_completion_returns_connected_subgraph(tmp_path):
    db_path = str(tmp_path / "pc.db")
    adapter = _core.SqliteAdapter.open(db_path)

    raw = sqlite3.connect(db_path)
    _seed_stmt(raw, "seed", "cats")
    raw.commit()

    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    worker = _core.EmbeddingWorker(adapter, emb, idx)
    worker.tick_one_batch("2026-05-31T10:00:00Z")   # 只嵌入 seed

    _seed_stmt(raw, "A", "a")
    _seed_stmt(raw, "B", "b")
    _seed_edge(raw, "e1", "seed", "A", 0.9)
    _seed_edge(raw, "e2", "A", "B", 0.8)
    raw.commit()
    raw.close()

    sr = _core.SemanticRetriever(adapter, emb, idx)
    pc = _core.PatternCompletor(adapter, sr)
    params = _core.PatternCompletionParams(
        tenant_id="default", holder_id="alice", holder_perspective="first_person",
        cue_text="bob knows cats", seed_k=5,
    )
    res = pc.complete(params)

    ids = {r.row.id: r.activation for r in res.rows}
    assert "seed" in ids and ids["seed"] == 1.0
    assert "A" in ids          # seed→A 0.9*0.5=0.45
    assert "B" in ids          # A→B 0.45*0.8*0.5=0.18 ≥ 0.05
    assert not res.completion_truncated
```

> 注：`EmbeddingWorker`/`SemanticRetriever`/`PatternCompletor` 的 pybind 方法 conn-free（内部用 `connection()`）；构造按各自 binding 签名。若 `worker.tick_one_batch` 的 binding 需要时间参数形态不同，对照 `tests/python` 现有 embedding worker 测试。

- [ ] **Step 2: 跑 smoke**

Run: `pytest tests/python/test_pattern_completion.py -v`
Expected: PASS

- [ ] **Step 3: Commit**
```bash
git add tests/python/test_pattern_completion.py
git commit -m "$(cat <<'EOF'
test(P2.d): Pattern Completion Python smoke

写 statements → 嵌入 seed → overlap 边 → PatternCompletor.complete() 返回
连通子图(seed 1.0 + A + 二跳 B),验证绑定端到端。

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: 全量回归 + milestone close 准备

**Files:** 无（回归）+ 本 plan 文件提交

- [ ] **Step 1: 全量 ctest**

Run: `cmake --build build && ctest --test-dir build`
Expected: `100% tests passed, 0 tests failed out of 497`（486 baseline + 11 PatternCompletor）

- [ ] **Step 2: 全量 pytest + CI 静态扫描**

Run:
```bash
pytest tests/python -q
```
Expected: `488 passed, 13 skipped`（487 + 1 smoke）；CI 静态扫描（若有 `scripts/ci_static_scan*`）OK

- [ ] **Step 3: 确认无回归红线**

逐一确认：M0.8（replay/reconsolidation）、M0.9（`SemanticRetriever`/vector_recall/repair guard）、P2.a–c 测试全绿；`statement_edges`/`statements` schema 未改（`git diff --stat main -- migrations/` 为空）；单一 `starling_tests`。

- [ ] **Step 4: 提交本 plan 文件（close 时转 tracked）**
```bash
git add docs/superpowers/plans/2026-05-31-p2-d-pattern-completion.md
git commit -m "$(cat <<'EOF'
docs(P2.d): land pattern completion implementation plan

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: 交回控制方做 final review + 合并**

报告：PatternCompletor 落地，11 C++ 单测 + 1 Python smoke 全绿，ctest 497 / pytest 488，无回归。等控制方 final code review 后，按 superpowers:finishing-a-development-branch 合并（merge 前 `git -C /Users/jaredguo-mini/develop/memory/starling status` 查并清 stray，再 `--no-ff` merge `worktree-p2-d-pattern-completion` 回 main，需 dangerouslyDisableSandbox + 显式 consent）。

---

## Self-Review（plan 作者自检，已跑）

**1. Spec coverage：**
- §2 算法 → Task 2（种子/init）+ Task 5（循环/max/θ/node_cap）✅
- §3 组件类型 → Task 1（头文件全类型）✅
- §5 边权/参数 → Task 3（edge_weight/clamp）+ Task 1（params 默认）✅
- §6 隐私+逐跳 SQL → Task 3（expand SQL）+ Task 4（隐私 checkpoint）✅
- §7 截断/降级/错误 → Task 5（truncated）+ Task 2（空种子/degraded 传播）+ make_sqlite_error ✅
- §8 测试 → Task 2–5（11 单测）+ Task 7（smoke）；逐项对齐 spec §8 列表 ✅
- §9 实施约束 → 文件结构"关键约束" + 各 Task Run 命令 ✅
- 无 migration ✅；pybind → Task 6 ✅

**2. Placeholder scan：** 无 TBD/TODO；每个 code step 有完整代码；commit message 完整。✅

**3. Type consistency：** `PatternCompletionParams`/`CompletionScored`/`CompletionResult`/`PatternCompletor` 跨 Task 一致；`complete(Connection&, const PatternCompletionParams&)` 签名一致；`expand`/`edge_weight`/`build_frontier_json`/`fetch_row` 命名跨 Task 一致；pybind 字段名与 hpp 字段一一对应。✅

> 注：`degraded` 当前传播自 `vector_recall`（恒 false），plan 已如实标注（不写假"无 embedder"测试）；"无新节点"作为 operative 收敛判据已在 Task 5 注释说明（设计 `max(activation)<θ` 被种子 1.0 支配）。
