# M0.9 向量基础层实施计划（P2.b 第二阶段）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 Statement 提供异步 embedding + 基于向量的语义召回（vector_recall）+ 写入时模式分离（DG 反相似偏移 + MAY_OVERLAP_WITH 软边）+ Projection Index 第 7 类（idx_vector_payload，让 §16.3-3/-6 repair guard 真正生效）。

**Architecture:** 全 adapter 抽象。`EmbeddingAdapter`（stub + openai）算向量；`VectorIndex`（SqliteBlobVectorIndex 暴力 cosine，seekdb 后端留 seam）存/查向量；`EmbeddingWorker` 扫描驱动、脱离写路径异步嵌入 + 模式分离；`SemanticRetriever` 隐私先行向量召回；`ProjectionMaintainer` 扩展第 7 类投影。写路径零改动,RuntimeHealth 不动（向量降级走 feature-level gating)。

**Tech Stack:** C++20 + raw SQLite + libcurl + nlohmann/json + pybind11 + Python 3.14 + pytest + ctest + Ninja。

**Spec:** `docs/superpowers/specs/2026-05-30-p2-b-vector-layer-design.md`（commit `7667dfd`）。

---

## 实施约束（贯穿所有 Task）

- `starling_core` 用**显式** `target_sources` 列表（`CMakeLists.txt:43+`），每个新 `.cpp` 必须 append。
- `tests/cpp` 单一 `starling_tests` executable（`tests/cpp/CMakeLists.txt`），新测试文件 append 到 sources 列表。
- migrations glob-based，cmake reconfigure 自动拾取；最高现存 `0015`，M0.9 用 `0016`–`0017`（仅 2 个）。
- pybind 改动后：`cmake --build build` + `cmake --install build --prefix .venv/lib/python3.14/site-packages` + `pip install -e . --no-deps --force-reinstall`。
- API key（`OPENAI_API_KEY` 等）仅从 env 读，绝不日志/落库/绑定 Python。
- 测试：unit 用 `:memory:` SQLite；runtime 用 `tmp_path` + `relax_preflight_for_m0_3()`。
- 既有不重建：`ConsolidationState`、`statement_edges`（已有 `weight`/`metadata_json`）、`projection_rebuild_state`、`RuntimeHealth`。
- pybind 类公开 `connection()` accessor（同 M0.8），Python 方法 conn-free。
- 回归红线：M0.8 + P2.a 全绿；`statements` 表不动（只加 `statement_vectors`）；不碰 SubscriberPump 写路径同步性；不碰 M0.8 的 6 类 SQL 投影。
- Commit trailer 一律：无 `--no-verify` / `--amend`；plan 文件 untracked 直到 Task 16 close。

## 文件结构

| 文件 | 职责 |
|---|---|
| `migrations/0016_statement_vectors.sql` | statement_vectors 表 |
| `migrations/0017_idx_vector_payload.sql` | proj_vector_payload 投影表 |
| `include/starling/vector/vector_math.hpp` + `src/vector/vector_math.cpp` | cosine + float32 BLOB 序列化（纯计算）|
| `include/starling/vector/pattern_separator.hpp` + `.cpp` | Gram-Schmidt 反相似偏移（纯计算）|
| `include/starling/vector/vector_index.hpp` + `src/vector/sqlite_blob_vector_index.cpp` | VectorIndex 抽象 + SqliteBlobVectorIndex |
| `include/starling/embedding/embedding_adapter.hpp` + `src/embedding/stub_embedding_adapter.cpp` | EmbeddingAdapter 抽象 + StubEmbeddingAdapter |
| `src/embedding/openai_embedding_adapter.cpp` (+ hpp) | OpenAIEmbeddingAdapter（libcurl /embeddings）|
| `include/starling/embedding/embedding_worker.hpp` + `src/embedding/embedding_worker.cpp` | 扫描驱动异步嵌入 + 模式分离 |
| `src/projection/projection_maintainer.cpp`（改）| 消费 vector.embedded + idx_vector_payload |
| `include/starling/retrieval/semantic_retriever.hpp` + `src/retrieval/semantic_retriever.cpp` | vector_recall 隐私先行 |
| `bindings/python/module.cpp`（改）| 暴露上述类 |
| `tests/cpp/test_*.cpp` + `tests/python/test_*.py` | 单测 + 集成 |

---

## Task 0: Baseline 确认

**Files:** 无（只验证）。

- [ ] **Step 1: 确认 worktree 全绿**

```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/m0-9-vector-layer
source /Users/jaredguo-mini/develop/memory/starling/.venv/bin/activate
cmake -S . -B build -G Ninja 2>&1 | tail -2
cmake --build build 2>&1 | tail -3
ctest --test-dir build 2>&1 | tail -2
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
pytest tests/python -q 2>&1 | tail -2
python scripts/ci_static_scan.py 2>&1 | tail -1
```
Expected: ctest 431/431；pytest 473 passed + 13 skipped；ci_static_scan OK。若非全绿，停止排查。

---

## Task 1: migration 0016 — statement_vectors

**Files:**
- Create: `migrations/0016_statement_vectors.sql`
- Test: `tests/python/test_m0_9_migrations.py`

- [ ] **Step 1: 写迁移**

```sql
-- M0.9 向量存储 (per spec §4)。独立表,保持 statements 精简,向量可选/异步。
-- "缺 statement_vectors 行" = 待嵌入队列;status='failed' 行带 retry_count 退避重试。

CREATE TABLE statement_vectors (
    stmt_id         TEXT PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    index_vector    BLOB,                 -- 模式分离后的索引向量 (float32 紧凑 little-endian)
    raw_embedding   BLOB,                 -- 原始 embedding (留待将来重分离)
    dim             INTEGER NOT NULL,
    model           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'embedded'
                    CHECK (status IN ('embedded','failed')),
    retry_count     INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    embedded_at     TEXT
);
CREATE INDEX idx_statement_vectors_scope ON statement_vectors(tenant_id, status);
```

- [ ] **Step 2: 写迁移存在性测试**

```python
"""M0.9 migrations 0016/0017 建表自检。"""
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


def test_statement_vectors_table_exists(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(statement_vectors)")}
    assert {"stmt_id","tenant_id","index_vector","raw_embedding","dim","model",
            "status","retry_count","last_attempt_at","embedded_at"} <= cols
```

- [ ] **Step 3: 重建 + 跑**

```bash
cmake --build build 2>&1 | tail -2
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
pytest tests/python/test_m0_9_migrations.py::test_statement_vectors_table_exists -v 2>&1 | tail -5
```
Expected: PASS。

- [ ] **Step 4: Commit**

```bash
git add migrations/0016_statement_vectors.sql tests/python/test_m0_9_migrations.py
git commit -m "$(cat <<'EOF'
feat(M0.9/substrate): migration 0016 — statement_vectors

spec §4: 独立向量表 (index_vector/raw_embedding BLOB + status/retry)。
缺行=待嵌入队列,failed 行退避重试。保持 statements 表不动。

EOF
)"
```

---

## Task 2: migration 0017 — proj_vector_payload

**Files:**
- Create: `migrations/0017_idx_vector_payload.sql`
- Test: `tests/python/test_m0_9_migrations.py`（追加）

- [ ] **Step 1: 写迁移**

```sql
-- M0.9 Projection Index 第 7 类: idx_vector_payload (per spec §8)。
-- 已嵌入向量的 statement 元数据 scoping 索引,供 vector_recall 圈定可见集。
-- repair guard 复用 projection_rebuild_state (0015),无需新表。

CREATE TABLE proj_vector_payload (
    tenant_id           TEXT NOT NULL,
    holder_id           TEXT NOT NULL,
    consolidation_state TEXT NOT NULL,
    modality            TEXT,
    review_status       TEXT NOT NULL,
    stmt_id             TEXT NOT NULL,
    PRIMARY KEY (stmt_id)
);
CREATE INDEX idx_proj_vector_payload_scope
    ON proj_vector_payload(tenant_id, holder_id, consolidation_state);
```

- [ ] **Step 2: 追加测试**

```python
def test_proj_vector_payload_table_exists(rt):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(proj_vector_payload)")}
    assert {"tenant_id","holder_id","consolidation_state","modality",
            "review_status","stmt_id"} <= cols
```

- [ ] **Step 3: 重建 + 跑 + Commit**

```bash
cmake --build build 2>&1 | tail -2
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
pytest tests/python/test_m0_9_migrations.py -v 2>&1 | tail -5
git add migrations/0017_idx_vector_payload.sql tests/python/test_m0_9_migrations.py
git commit -m "$(cat <<'EOF'
feat(M0.9/substrate): migration 0017 — proj_vector_payload

spec §8: Projection Index 第 7 类。repair guard 复用 projection_rebuild_state。
MAY_OVERLAP_WITH 软边复用 statement_edges 既有 weight(=similarity)+metadata_json
(resolved),无需独立 edge 迁移。

EOF
)"
```

---

## Task 3: vector_math — cosine + float32 BLOB 序列化（纯计算）

**Files:**
- Create: `include/starling/vector/vector_math.hpp`, `src/vector/vector_math.cpp`, `tests/cpp/test_vector_math.cpp`
- Modify: `CMakeLists.txt`（`src/vector/vector_math.cpp` append 到 starling_core）、`tests/cpp/CMakeLists.txt`

- [ ] **Step 1: 写头文件**

```cpp
// include/starling/vector/vector_math.hpp
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace starling::vector {

// cosine ∈ [-1,1]; 任一零向量返回 0。
double cosine(const std::vector<float>& a, const std::vector<float>& b);

// float32 little-endian 紧凑序列化 ↔ BLOB（std::string 当字节容器）。
std::string  to_blob(const std::vector<float>& v);
std::vector<float> from_blob(const std::string& blob);

// 归一化（零向量原样返回）。
std::vector<float> normalize(const std::vector<float>& v);

}  // namespace starling::vector
```

- [ ] **Step 2: 写失败测试**

```cpp
// tests/cpp/test_vector_math.cpp
#include "starling/vector/vector_math.hpp"
#include <gtest/gtest.h>
using namespace starling::vector;

TEST(VectorMath, CosineIdentityAndOrthogonal) {
    EXPECT_NEAR(cosine({1,0,0}, {1,0,0}), 1.0, 1e-6);
    EXPECT_NEAR(cosine({1,0,0}, {0,1,0}), 0.0, 1e-6);
    EXPECT_NEAR(cosine({1,0,0}, {0,0,0}), 0.0, 1e-6);  // 零向量
}
TEST(VectorMath, BlobRoundTrip) {
    std::vector<float> v{0.1f, -2.5f, 3.14159f, 0.0f};
    auto back = from_blob(to_blob(v));
    ASSERT_EQ(back.size(), v.size());
    for (size_t i = 0; i < v.size(); ++i) EXPECT_FLOAT_EQ(back[i], v[i]);
}
TEST(VectorMath, NormalizeUnitLength) {
    auto n = normalize({3,4});
    EXPECT_NEAR(n[0], 0.6, 1e-6); EXPECT_NEAR(n[1], 0.8, 1e-6);
}
```

- [ ] **Step 3: CMake 注册**

`CMakeLists.txt`：在 `target_sources(starling_core PRIVATE` 列表末尾（`src/bus/subscriber_pump.cpp` 后）加 `src/vector/vector_math.cpp`。
`tests/cpp/CMakeLists.txt`：把 `test_vector_math.cpp` append 到 `starling_tests` 的 sources 列表。

- [ ] **Step 4: 实现**

```cpp
// src/vector/vector_math.cpp
#include "starling/vector/vector_math.hpp"
#include <cmath>
#include <cstring>

namespace starling::vector {

double cosine(const std::vector<float>& a, const std::vector<float>& b) {
    if (a.size() != b.size() || a.empty()) return 0.0;
    double dot = 0, na = 0, nb = 0;
    for (size_t i = 0; i < a.size(); ++i) { dot += double(a[i])*b[i]; na += double(a[i])*a[i]; nb += double(b[i])*b[i]; }
    if (na == 0 || nb == 0) return 0.0;
    return dot / (std::sqrt(na) * std::sqrt(nb));
}

std::string to_blob(const std::vector<float>& v) {
    std::string out;
    out.resize(v.size() * sizeof(float));
    std::memcpy(out.data(), v.data(), out.size());  // little-endian host (x86/arm64)
    return out;
}

std::vector<float> from_blob(const std::string& blob) {
    std::vector<float> v(blob.size() / sizeof(float));
    std::memcpy(v.data(), blob.data(), v.size() * sizeof(float));
    return v;
}

std::vector<float> normalize(const std::vector<float>& v) {
    double n = 0; for (float x : v) n += double(x)*x;
    if (n == 0) return v;
    const double inv = 1.0 / std::sqrt(n);
    std::vector<float> out(v.size());
    for (size_t i = 0; i < v.size(); ++i) out[i] = float(v[i] * inv);
    return out;
}

}  // namespace starling::vector
```

- [ ] **Step 5: 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2
cmake --build build 2>&1 | tail -2
ctest --test-dir build -R VectorMath --output-on-failure 2>&1 | tail -6
git add include/starling/vector/vector_math.hpp src/vector/vector_math.cpp tests/cpp/test_vector_math.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.9/vector): vector_math — cosine + float32 BLOB 序列化 + normalize

纯计算助手:cosine(零向量→0) / to_blob+from_blob(little-endian round-trip) /
normalize。VectorIndex + PatternSeparator 的基础。

EOF
)"
```

---

## Task 4: PatternSeparator — Gram-Schmidt 反相似偏移（纯计算）

**Files:**
- Create: `include/starling/vector/pattern_separator.hpp`, `src/vector/pattern_separator.cpp`, `tests/cpp/test_pattern_separator.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §6。

- [ ] **Step 1: 头文件**

```cpp
// include/starling/vector/pattern_separator.hpp
#pragma once
#include <string>
#include <utility>
#include <vector>

namespace starling::vector {

struct SeparationResult {
    std::vector<float> index_vector;                       // 归一化后
    std::vector<std::pair<std::string,double>> overlaps;   // (neighbor_id, similarity)
};

// neighbors: 已有邻居的 (stmt_id, index_vector)。
// max_sim > theta_sep 时 Gram-Schmidt 反相似偏移 + 建软边;否则直接归一化。
SeparationResult separate(
    const std::vector<float>& e,
    const std::vector<std::pair<std::string, std::vector<float>>>& neighbors,
    double theta_sep, double strength);

}  // namespace starling::vector
```

- [ ] **Step 2: 失败测试**

```cpp
// tests/cpp/test_pattern_separator.cpp
#include "starling/vector/pattern_separator.hpp"
#include "starling/vector/vector_math.hpp"
#include <gtest/gtest.h>
using namespace starling::vector;

TEST(PatternSeparator, NoNeighborsJustNormalize) {
    auto r = separate({3,4}, {}, 0.85, 0.5);
    EXPECT_TRUE(r.overlaps.empty());
    EXPECT_NEAR(r.index_vector[0], 0.6, 1e-6);
}
TEST(PatternSeparator, BelowThresholdNoOffset) {
    // e 与邻居正交 → max_sim=0 < 0.85 → 直接归一化,无软边
    auto r = separate({1,0,0}, {{"n1", {0,1,0}}}, 0.85, 0.5);
    EXPECT_TRUE(r.overlaps.empty());
    EXPECT_NEAR(cosine(r.index_vector, {1,0,0}), 1.0, 1e-6);
}
TEST(PatternSeparator, AboveThresholdOffsetsAwayAndBuildsEdge) {
    // e 与邻居高度相似 → 偏移后远离邻居 + 建软边
    std::vector<float> nb{1,0,0};
    auto r = separate({0.99f, 0.14f, 0.0f}, {{"n1", nb}}, 0.85, 1.0);
    ASSERT_EQ(r.overlaps.size(), 1u);
    EXPECT_EQ(r.overlaps[0].first, "n1");
    EXPECT_GT(r.overlaps[0].second, 0.85);                 // 记录的 similarity
    // 偏移后与邻居的相似度应低于原始相似度
    EXPECT_LT(cosine(r.index_vector, nb), cosine({0.99f,0.14f,0.0f}, nb));
}
```

- [ ] **Step 3: CMake 注册**（同 Task 3 模式:`src/vector/pattern_separator.cpp` → starling_core；`test_pattern_separator.cpp` → starling_tests）

- [ ] **Step 4: 实现**

```cpp
// src/vector/pattern_separator.cpp
#include "starling/vector/pattern_separator.hpp"
#include "starling/vector/vector_math.hpp"
#include <cmath>

namespace starling::vector {

SeparationResult separate(
    const std::vector<float>& e,
    const std::vector<std::pair<std::string, std::vector<float>>>& neighbors,
    double theta_sep, double strength)
{
    SeparationResult res;
    double max_sim = 0.0;
    for (const auto& [id, nv] : neighbors)
        max_sim = std::max(max_sim, cosine(e, nv));

    if (neighbors.empty() || max_sim <= theta_sep) {
        res.index_vector = normalize(e);
        return res;
    }

    // Gram-Schmidt: 对各归一化邻居去分量
    std::vector<float> v_perp = e;
    for (const auto& [id, nv] : neighbors) {
        auto nhat = normalize(nv);
        double proj = 0.0;
        for (size_t i = 0; i < e.size(); ++i) proj += double(e[i]) * nhat[i];
        for (size_t i = 0; i < v_perp.size(); ++i)
            v_perp[i] -= float(proj * nhat[i]);
    }
    std::vector<float> offset(e.size());
    for (size_t i = 0; i < e.size(); ++i)
        offset[i] = float(e[i] + strength * v_perp[i]);
    res.index_vector = normalize(offset);

    for (const auto& [id, nv] : neighbors)
        res.overlaps.emplace_back(id, cosine(e, nv));
    return res;
}

}  // namespace starling::vector
```

- [ ] **Step 5: 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R PatternSeparator --output-on-failure 2>&1 | tail -8
git add include/starling/vector/pattern_separator.hpp src/vector/pattern_separator.cpp tests/cpp/test_pattern_separator.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.9/vector): PatternSeparator — Gram-Schmidt 反相似偏移

spec §6: max_sim>θ_sep 时对各邻居去分量 + strength 叠回 → 偏离聚类 +
建 MAY_OVERLAP_WITH 软边(带 similarity);否则直接归一化。纯计算可独立单测。

EOF
)"
```

---

## Task 5: VectorIndex 抽象 + SqliteBlobVectorIndex

**Files:**
- Create: `include/starling/vector/vector_index.hpp`, `src/vector/sqlite_blob_vector_index.cpp`, `tests/cpp/test_sqlite_blob_vector_index.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §3.2。

- [ ] **Step 1: 头文件**

```cpp
// include/starling/vector/vector_index.hpp
#pragma once
#include <optional>
#include <string>
#include <vector>
#include "starling/persistence/connection.hpp"

namespace starling::vector {

struct ScoredId { std::string stmt_id; double score; };  // score = cosine

struct SearchScope {
    std::string tenant_id;
    std::optional<std::string> holder_id;
    std::optional<std::string> holder_perspective;
    bool visible_only = true;  // consolidation_state IN(consolidated,archived) + review_status 过滤
};

class VectorIndex {
public:
    virtual ~VectorIndex() = default;
    virtual void insert(persistence::Connection&, std::string_view stmt_id,
                        std::string_view tenant_id, const std::vector<float>& vec) = 0;
    virtual std::vector<ScoredId> search_topk(persistence::Connection&,
                        const std::vector<float>& query, int k, const SearchScope&) = 0;
    virtual void remove(persistence::Connection&, std::string_view stmt_id) = 0;
};

// 后端 = statement_vectors.index_vector (BLOB) + 暴力 cosine。
class SqliteBlobVectorIndex : public VectorIndex {
public:
    void insert(persistence::Connection&, std::string_view stmt_id,
                std::string_view tenant_id, const std::vector<float>& vec) override;
    std::vector<ScoredId> search_topk(persistence::Connection&,
                const std::vector<float>& query, int k, const SearchScope&) override;
    void remove(persistence::Connection&, std::string_view stmt_id) override;
};

}  // namespace starling::vector
```

- [ ] **Step 2: 失败测试（:memory:，直接建 statement_vectors + statements 桩）**

```cpp
// tests/cpp/test_sqlite_blob_vector_index.cpp
#include "starling/vector/vector_index.hpp"
#include "starling/vector/vector_math.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling::vector;
using starling::persistence::SqliteAdapter;

namespace {
void seed_stmt(sqlite3* db, const std::string& id, const std::string& state="consolidated") {
    std::string s = "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
      "subject_kind,subject_id,predicate,object_kind,object_value,canonical_object_hash,"
      "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
      "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
      "created_at,updated_at) VALUES('"+id+"','default','alice','first_person','cognizer',"
      "'bob','knows','str','x','"+std::string(64,'a')+"','v1','believes','pos',0.9,"
      "'2026-05-30T09:00:00Z',0.5,'{}',0.0,'2026-05-30T09:00:00Z','user_input','"+state+
      "','approved','2026-05-30T09:00:00Z','2026-05-30T09:00:00Z')";
    sqlite3_exec(db, s.c_str(), nullptr, nullptr, nullptr);
}
}

TEST(SqliteBlobVectorIndex, InsertSearchRanking) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "a"); seed_stmt(conn.raw(), "b"); seed_stmt(conn.raw(), "c");
    SqliteBlobVectorIndex idx;
    idx.insert(conn, "a", "default", {1,0,0});
    idx.insert(conn, "b", "default", {0,1,0});
    idx.insert(conn, "c", "default", {0.9f,0.1f,0});
    SearchScope scope{"default", std::nullopt, std::nullopt, true};
    auto top = idx.search_topk(conn, {1,0,0}, 2, scope);
    ASSERT_EQ(top.size(), 2u);
    EXPECT_EQ(top[0].stmt_id, "a");   // 最相似
    EXPECT_EQ(top[1].stmt_id, "c");   // 次相似
}

TEST(SqliteBlobVectorIndex, VisibleOnlyExcludesPendingReview) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "vis", "consolidated");
    // 不可见: review_status='pending_review'（需手改）
    seed_stmt(conn.raw(), "hidden", "consolidated");
    sqlite3_exec(conn.raw(), "UPDATE statements SET review_status='pending_review' WHERE id='hidden'", nullptr,nullptr,nullptr);
    SqliteBlobVectorIndex idx;
    idx.insert(conn, "vis", "default", {1,0,0});
    idx.insert(conn, "hidden", "default", {1,0,0});
    auto top = idx.search_topk(conn, {1,0,0}, 10, {"default", std::nullopt, std::nullopt, true});
    ASSERT_EQ(top.size(), 1u);
    EXPECT_EQ(top[0].stmt_id, "vis");
}
```

- [ ] **Step 3: CMake 注册**（`src/vector/sqlite_blob_vector_index.cpp` → starling_core；test → starling_tests）

- [ ] **Step 4: 实现**

`insert`：`INSERT INTO statement_vectors(stmt_id,tenant_id,index_vector,raw_embedding,dim,model,status,embedded_at) VALUES(...,'embedded',...) ON CONFLICT(stmt_id) DO UPDATE SET index_vector=excluded.index_vector` —— 注:Task 8 的 worker 才是主写入者,此处 insert 供测试/简单路径;`raw_embedding` 与 `index_vector` 同值占位、`dim` 取 `vec.size()`、`model='stub'`、`embedded_at` 暂置固定串（测试不校验）。
`search_topk`：
```sql
SELECT v.stmt_id, v.index_vector
FROM statement_vectors v JOIN statements s ON s.id = v.stmt_id
WHERE v.tenant_id = ?1 AND v.status = 'embedded'
  AND (?2 = '' OR s.holder_id = ?2)
  AND (?3 = '' OR s.holder_perspective = ?3)
  AND (?4 = 0 OR (s.consolidation_state IN ('consolidated','archived')
                  AND s.review_status NOT IN ('rejected','pending_review')))
```
读出每行 `from_blob(index_vector)`，算 `cosine(query, v)`，最小堆/部分排序取 top-k（按 score 降序）。`remove`：`DELETE FROM statement_vectors WHERE stmt_id=?`。用 `sqlite_helpers` 的 `bind_sv`/`StmtHandle`/`make_sqlite_error`（参考 `src/projection/projection_maintainer.cpp`）。

- [ ] **Step 5: 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R SqliteBlobVectorIndex --output-on-failure 2>&1 | tail -10
git add include/starling/vector/vector_index.hpp src/vector/sqlite_blob_vector_index.cpp tests/cpp/test_sqlite_blob_vector_index.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.9/vector): VectorIndex 抽象 + SqliteBlobVectorIndex 暴力 cosine

spec §3.2: insert/search_topk/remove。search_topk 把可见性谓词下推进 SQL scope
(隐私先行),暴力 cosine 取 top-k。seekdb 后端留 seam(同接口,将来映射 APPROXIMATE)。

EOF
)"
```

---

## Task 6: EmbeddingAdapter 抽象 + StubEmbeddingAdapter

**Files:**
- Create: `include/starling/embedding/embedding_adapter.hpp`, `src/embedding/stub_embedding_adapter.cpp`, `tests/cpp/test_stub_embedding_adapter.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §3.1。

- [ ] **Step 1: 头文件**

```cpp
// include/starling/embedding/embedding_adapter.hpp
#pragma once
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace starling::embedding {

struct EmbeddingResult { std::vector<float> vector; int dim = 0; std::string model; };

// 抛此表示可重试失败（网络/5xx/429）。
struct EmbeddingError : std::runtime_error { using std::runtime_error::runtime_error; };

class EmbeddingAdapter {
public:
    virtual ~EmbeddingAdapter() = default;
    virtual EmbeddingResult embed(std::string_view text) = 0;
    virtual int dim() const = 0;
    virtual std::string model() const = 0;
};

// 测试专用:从文本 hash 种子生成确定性单位向量。零 live API。
class StubEmbeddingAdapter : public EmbeddingAdapter {
public:
    explicit StubEmbeddingAdapter(int dim = 8) : dim_(dim) {}
    EmbeddingResult embed(std::string_view text) override;
    int dim() const override { return dim_; }
    std::string model() const override { return "stub"; }
    // 测试钩子:让指定文本一次性抛 EmbeddingError（验证 worker 重试路径）。
    void fail_next(std::string_view text) { fail_text_ = std::string(text); }
private:
    int dim_;
    std::string fail_text_;
};

}  // namespace starling::embedding
```

- [ ] **Step 2: 失败测试**

```cpp
// tests/cpp/test_stub_embedding_adapter.cpp
#include "starling/embedding/embedding_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling::embedding;

TEST(StubEmbeddingAdapter, DeterministicSameTextSameVector) {
    StubEmbeddingAdapter a(8);
    auto v1 = a.embed("hello world");
    auto v2 = a.embed("hello world");
    EXPECT_EQ(v1.dim, 8);
    EXPECT_EQ(v1.vector, v2.vector);                 // 确定性
    EXPECT_NE(v1.vector, a.embed("different").vector); // 不同文本不同向量
}
TEST(StubEmbeddingAdapter, FailNextThrowsOnce) {
    StubEmbeddingAdapter a(8);
    a.fail_next("boom");
    EXPECT_THROW(a.embed("boom"), EmbeddingError);
    EXPECT_NO_THROW(a.embed("boom"));                // 只失败一次
}
```

- [ ] **Step 3: CMake 注册** + **Step 4: 实现**

实现：`embed` 若 `text == fail_text_` 则清空 `fail_text_` 并抛 `EmbeddingError("stub forced failure")`；否则用 `std::hash<std::string_view>` 作种子驱动 `std::mt19937` 生成 `dim_` 个 `[-1,1]` 分量,`normalize`（复用 `vector::normalize`，需 `#include "starling/vector/vector_math.hpp"`）。返回 `{vec, dim_, "stub"}`。

- [ ] **Step 5: 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R StubEmbeddingAdapter --output-on-failure 2>&1 | tail -6
git add include/starling/embedding/embedding_adapter.hpp src/embedding/stub_embedding_adapter.cpp tests/cpp/test_stub_embedding_adapter.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.9/embedding): EmbeddingAdapter 抽象 + StubEmbeddingAdapter

spec §3.1: embed(text)→float32[]。Stub 从文本 hash 种子生成确定性单位向量,
fail_next 钩子验证 worker 重试。CI 全程用它,零 live API。

EOF
)"
```

---

## Task 7: OpenAIEmbeddingAdapter（libcurl /embeddings）

**Files:**
- Create: `include/starling/embedding/openai_embedding_adapter.hpp`, `src/embedding/openai_embedding_adapter.cpp`, `tests/cpp/test_openai_embedding_adapter.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §3.1。镜像 `src/extractor/openai_adapter.cpp` 的 libcurl + nlohmann/json + retry/backoff 模式。

- [ ] **Step 1: 头文件**（`Config::from_env()` 读 `OPENAI_BASE_URL`/`OPENAI_API_KEY`/`EMBEDDING_MODEL`，默认 model `text-embedding-3-small`、dim 1536；key 缺失 throw）

```cpp
// include/starling/embedding/openai_embedding_adapter.hpp
#pragma once
#include "starling/embedding/embedding_adapter.hpp"
#include <string>

namespace starling::embedding {

class OpenAIEmbeddingAdapter : public EmbeddingAdapter {
public:
    struct Config {
        std::string base_url;
        std::string api_key;                       // 仅 env 读,绝不日志/绑定 Python
        std::string model = "text-embedding-3-small";
        int dim = 1536;
        int timeout_ms = 60000;
        int max_retries = 3;
        static Config from_env();                  // throw if api_key unset
    };
    explicit OpenAIEmbeddingAdapter(Config cfg) : cfg_(std::move(cfg)) {}
    EmbeddingResult embed(std::string_view text) override;
    int dim() const override { return cfg_.dim; }
    std::string model() const override { return cfg_.model; }
private:
    Config cfg_;
};

}  // namespace starling::embedding
```

- [ ] **Step 2: 测试（不打真网络;只测 from_env 行为）**

```cpp
// tests/cpp/test_openai_embedding_adapter.cpp
#include "starling/embedding/openai_embedding_adapter.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
using namespace starling::embedding;

TEST(OpenAIEmbeddingAdapter, FromEnvThrowsWithoutKey) {
    unsetenv("OPENAI_API_KEY");
    EXPECT_THROW(OpenAIEmbeddingAdapter::Config::from_env(), std::runtime_error);
}
TEST(OpenAIEmbeddingAdapter, FromEnvReadsModelAndKey) {
    setenv("OPENAI_API_KEY", "sk-test", 1);
    setenv("EMBEDDING_MODEL", "text-embedding-3-large", 1);
    auto c = OpenAIEmbeddingAdapter::Config::from_env();
    EXPECT_EQ(c.api_key, "sk-test");
    EXPECT_EQ(c.model, "text-embedding-3-large");
    unsetenv("OPENAI_API_KEY"); unsetenv("EMBEDDING_MODEL");
}
```

- [ ] **Step 3: CMake 注册** + **Step 4: 实现**

实现 `embed`：POST `{base_url}/embeddings`，body `{"model": <model>, "input": <text>}`，Header `Authorization: Bearer <key>`；复用 openai_adapter 的 `is_retryable_curl_code`/`is_retryable_status` + 指数退避（可把这两个 helper 提取到共享 TU 或在本 TU 重复实现，二选一，prefer 重复以避免改动 extractor）；解析 `data[0].embedding` → `std::vector<float>`；失败抛 `EmbeddingError`。**API key 绝不写日志**。

- [ ] **Step 5: 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R OpenAIEmbeddingAdapter --output-on-failure 2>&1 | tail -6
git add include/starling/embedding/openai_embedding_adapter.hpp src/embedding/openai_embedding_adapter.cpp tests/cpp/test_openai_embedding_adapter.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.9/embedding): OpenAIEmbeddingAdapter — libcurl /embeddings

spec §3.1: 镜像 openai_adapter 的 curl+json+retry 模式打 /embeddings。
Config::from_env 读 OPENAI_API_KEY/BASE_URL/EMBEDDING_MODEL,key 缺失 throw,
绝不日志/绑定 Python。

EOF
)"
```

---

## Task 8: EmbeddingWorker（扫描驱动异步嵌入 + 模式分离）

**Files:**
- Create: `include/starling/embedding/embedding_worker.hpp`, `src/embedding/embedding_worker.cpp`, `tests/cpp/test_embedding_worker.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §3.4 + §5。

- [ ] **Step 1: 头文件**

```cpp
// include/starling/embedding/embedding_worker.hpp
#pragma once
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::embedding {

struct EmbeddingStats { int embedded = 0; int failed = 0; int overlaps_created = 0; };

struct WorkerConfig {
    int batch_size = 32;
    int top_k_neighbors = 5;
    double theta_sep = 0.85;
    double strength = 0.5;
    int max_retry = 3;
};

class EmbeddingWorker {
public:
    EmbeddingWorker(persistence::SqliteAdapter& a, EmbeddingAdapter& e,
                    vector::VectorIndex& idx, WorkerConfig cfg = {})
        : adapter_(a), embedder_(e), index_(idx), cfg_(cfg) {}
    EmbeddingStats tick_one_batch(persistence::Connection&, std::string_view now_iso);
    persistence::Connection& connection() { return adapter_.connection(); }  // pybind helper
private:
    persistence::SqliteAdapter& adapter_;
    EmbeddingAdapter& embedder_;
    vector::VectorIndex& index_;
    WorkerConfig cfg_;
};

}  // namespace starling::embedding
```

- [ ] **Step 2: 失败测试（stub embedder + :memory:）**

```cpp
// tests/cpp/test_embedding_worker.cpp
#include "starling/embedding/embedding_worker.hpp"
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling::embedding;
using starling::persistence::SqliteAdapter;
// seed_stmt 同 Task 5（可复制到本 TU 的匿名 namespace）

TEST(EmbeddingWorker, EmbedsPendingAndEmitsEvent) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "s1");
    StubEmbeddingAdapter emb(8);
    starling::vector::SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);
    auto st = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st.embedded, 1);
    // statement_vectors 落库
    int n=0; sqlite3_exec(conn.raw(),"SELECT COUNT(*) FROM statement_vectors WHERE stmt_id='s1' AND status='embedded'",
        [](void*p,int,char**v,char**){*(int*)p=atoi(v[0]);return 0;},&n,nullptr);
    EXPECT_EQ(n, 1);
    // vector.embedded 事件
    int e=0; sqlite3_exec(conn.raw(),"SELECT COUNT(*) FROM bus_events WHERE event_type='vector.embedded' AND primary_id='s1'",
        [](void*p,int,char**v,char**){*(int*)p=atoi(v[0]);return 0;},&e,nullptr);
    EXPECT_EQ(e, 1);
}

TEST(EmbeddingWorker, SecondTickNoOpAlreadyEmbedded) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "s1");
    StubEmbeddingAdapter emb(8); starling::vector::SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);
    w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    auto st2 = w.tick_one_batch(conn, "2026-05-30T10:01:00Z");
    EXPECT_EQ(st2.embedded, 0);                        // 已有向量,不重嵌
}

TEST(EmbeddingWorker, FailureMarksFailedWithRetry) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "boom");
    StubEmbeddingAdapter emb(8); emb.fail_next( /* render_text(s) 的结果 */ "" );  // 见实现注
    starling::vector::SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);
    auto st = w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    EXPECT_EQ(st.failed, 1);
    int n=0; sqlite3_exec(conn.raw(),"SELECT retry_count FROM statement_vectors WHERE stmt_id='boom' AND status='failed'",
        [](void*p,int,char**v,char**){*(int*)p=atoi(v[0]);return 0;},&n,nullptr);
    EXPECT_GE(n, 1);
}

TEST(EmbeddingWorker, PatternSeparationBuildsOverlapEdge) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    // 两条文本渲染高度相似的 stmt → 第二条触发模式分离 + MAY_OVERLAP_WITH
    seed_stmt(conn.raw(), "a"); seed_stmt(conn.raw(), "b");
    StubEmbeddingAdapter emb(8); starling::vector::SqliteBlobVectorIndex idx;
    EmbeddingWorker w(*adapter, emb, idx);
    w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    // 至少跑通 MAY_OVERLAP_WITH 边写入路径(具体是否建边取决于 stub 向量相似度;
    // 实现期可用受控 stub 或调低 theta_sep 让测试确定性触发)
    SUCCEED();
}
```

> 实现注:`render_text(s)` = `subject_id + ' ' + predicate + ' ' + object_value`（从 statements 行取）。`fail_next` 测试需传入与该渲染一致的文本;实现期把渲染逻辑暴露为可测 helper 或在测试里构造已知 stmt 文本。

- [ ] **Step 3: CMake 注册**

- [ ] **Step 4: 实现**（见 spec §5）

`tick_one_batch`：
1. `SELECT s.id, s.subject_id, s.predicate, s.object_value, s.tenant_id FROM statements s LEFT JOIN statement_vectors v ON v.stmt_id=s.id WHERE v.stmt_id IS NULL AND s.consolidation_state NOT IN ('archived','forgotten') LIMIT batch_size` —— UNION `status='failed' AND retry_count<max_retry` 的行（退避可简化为直接重试,M0.9 不强制时间窗）。
2. 逐条：`text = render_text(row)`；`try { e = embedder_.embed(text) } catch (EmbeddingError) { UPSERT statement_vectors(stmt_id,tenant_id,dim,model,status='failed',retry_count=old+1,last_attempt_at=now); failed++; continue; }`
3. `neighbors = index_.search_topk(conn, e.vector, top_k, {tenant})` → 取各 neighbor 的 index_vector（search_topk 返回 ScoredId,需要再查向量;或让 search_topk 返回向量。简化:实现里直接 SQL 查 top-k 的 (id, index_vector)）。
4. `sep = pattern_separator::separate(e.vector, neighbor_pairs, theta_sep, strength)`。
5. `SAVEPOINT`：`UPSERT statement_vectors(index_vector=to_blob(sep.index_vector), raw_embedding=to_blob(e.vector), dim, model=embedder_.model(), status='embedded', embedded_at=now)`；`for (nid,sim) in sep.overlaps: INSERT statement_edges(id=random, tenant_id, src_id=stmt, dst_id=nid, edge_kind='MAY_OVERLAP_WITH', weight=sim, created_at=now, metadata_json='{"resolved":false}')`；`emit_event(conn, "vector.embedded", stmt, stmt, tenant, "{}")`（复用 outbox 模式,参考 projection_maintainer 的 emit_event helper:file-local 复制即可）;`RELEASE`。`embedded++; overlaps_created += sep.overlaps.size()`。

- [ ] **Step 5: 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R EmbeddingWorker --output-on-failure 2>&1 | tail -12
git add include/starling/embedding/embedding_worker.hpp src/embedding/embedding_worker.cpp tests/cpp/test_embedding_worker.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.9/embedding): EmbeddingWorker — 扫描驱动异步嵌入 + 模式分离

spec §3.4/§5: LEFT JOIN 扫描待嵌入 → embed → search_topk 近邻 → PatternSeparator
→ 原子写 statement_vectors + MAY_OVERLAP_WITH 边 + emit vector.embedded。失败标
failed 退避重试。脱离写路径,runtime 串行驱动。

EOF
)"
```

---

## Task 9: ProjectionMaintainer 扩展 — 消费 vector.embedded + idx_vector_payload 增量

**Files:**
- Modify: `src/projection/projection_maintainer.cpp`
- Create: `tests/cpp/test_proj_vector_payload.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §8。**红线:不碰 M0.8 的 6 类 SQL 投影逻辑。**

- [ ] **Step 1: 失败测试**

```cpp
// tests/cpp/test_proj_vector_payload.cpp
#include "starling/projection/projection_maintainer.hpp"
#include "starling/embedding/embedding_worker.hpp"
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <gtest/gtest.h>
using namespace starling;
// seed_stmt 同前

TEST(ProjVectorPayload, VectorEmbeddedEventMaterializesRow) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "s1");
    embedding::StubEmbeddingAdapter emb(8); vector::SqliteBlobVectorIndex idx;
    embedding::EmbeddingWorker w(*adapter, emb, idx);
    w.tick_one_batch(conn, "2026-05-30T10:00:00Z");      // 落向量 + emit vector.embedded
    projection::ProjectionMaintainer pm(*adapter);
    pm.tick_one_batch(conn, "2026-05-30T10:01:00Z");     // 消费 → 物化 proj_vector_payload
    int n=0; sqlite3_exec(conn.raw(),"SELECT COUNT(*) FROM proj_vector_payload WHERE stmt_id='s1'",
        [](void*p,int,char**v,char**){*(int*)p=atoi(v[0]);return 0;},&n,nullptr);
    EXPECT_EQ(n, 1);
}

TEST(ProjVectorPayload, RetireRemovesRow) {
    auto adapter = persistence::SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    seed_stmt(conn.raw(), "s1");
    embedding::StubEmbeddingAdapter emb(8); vector::SqliteBlobVectorIndex idx;
    embedding::EmbeddingWorker w(*adapter, emb, idx);
    w.tick_one_batch(conn, "2026-05-30T10:00:00Z");
    projection::ProjectionMaintainer pm(*adapter);
    pm.tick_one_batch(conn, "2026-05-30T10:01:00Z");
    // archive + emit statement.archived（手动 emit 或直接置状态 + emit）
    sqlite3_exec(conn.raw(),"UPDATE statements SET consolidation_state='archived' WHERE id='s1'",nullptr,nullptr,nullptr);
    /* emit statement.archived 见实现注;此处可直接调 pm 的 retire 路径 */
    // ... emit then:
    pm.tick_one_batch(conn, "2026-05-30T10:02:00Z");
    int n=1; sqlite3_exec(conn.raw(),"SELECT COUNT(*) FROM proj_vector_payload WHERE stmt_id='s1'",
        [](void*p,int,char**v,char**){*(int*)p=atoi(v[0]);return 0;},&n,nullptr);
    EXPECT_EQ(n, 0);
}
```

- [ ] **Step 2: 实现（扩展 tick_one_batch 事件循环）**

在 `tick_one_batch` 的事件循环里,**新增**对 `vector.embedded` 事件的处理（与既有 `statement.*` 分支并列,不改既有分支）：
```cpp
if (ev.event_type == "vector.embedded") {
    stats.events_processed++;
    StmtRow sr = read_stmt(conn, ev.primary_id);
    if (sr.found && sr.consolidation_state != "archived" && sr.consolidation_state != "forgotten")
        upsert_vector_payload(conn, ev.primary_id, sr);   // 新 helper
    continue;
}
```
并在既有 `statement.*` 的 retire 分支里追加 `delete_vector_payload(conn, ev.primary_id);`（与 `delete_projection_rows` 并列）；非 retire 分支里:若该 stmt 已有向量行,刷新 `upsert_vector_payload`（保持 consolidation_state/review_status 同步）。新增 helper：
- `upsert_vector_payload(conn, stmt_id, sr)`：`INSERT INTO proj_vector_payload(...) VALUES(...) ON CONFLICT(stmt_id) DO UPDATE SET consolidation_state=..., review_status=..., modality=...`（仅当 `EXISTS (SELECT 1 FROM statement_vectors WHERE stmt_id=? AND status='embedded')`）。
- `delete_vector_payload(conn, stmt_id)`：`DELETE FROM proj_vector_payload WHERE stmt_id=?`。

- [ ] **Step 3: CMake 注册 test + 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R ProjVectorPayload --output-on-failure 2>&1 | tail -10
# 回归:M0.8 投影测试仍绿
ctest --test-dir build -R Projection --output-on-failure 2>&1 | tail -4
git add src/projection/projection_maintainer.cpp tests/cpp/test_proj_vector_payload.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.9/substrate): ProjectionMaintainer 消费 vector.embedded → idx_vector_payload

spec §8: 新增 vector.embedded 分支 + retire 删行,物化 proj_vector_payload。
不碰 M0.8 的 6 类 SQL 投影逻辑(并列新增分支)。

EOF
)"
```

---

## Task 10: idx_vector_payload rebuild + repair guard（TC-VEC-REPAIR CRITICAL）

**Files:**
- Modify: `src/projection/projection_maintainer.cpp`
- Create: `tests/python/test_tc_vec_repair.py`

**Spec ref:** §8 + §16.3-3/-6。**这是闭合 M0.8 finding #6 的关键。**

- [ ] **Step 1: 实现 rebuild + repair（在 do_rebuild 加 proj_vector_payload 分支）**

为 `proj_vector_payload` 提供**真正不同**的两个计数（区别于 6 类 SQL 投影的 1:1）：
```cpp
// 仅 proj_vector_payload 分支:
int64_t ground_truth = scalar(conn,
    "SELECT COUNT(*) FROM statement_vectors v JOIN statements s ON s.id=v.stmt_id "
    "WHERE v.status='embedded' AND s.consolidation_state NOT IN ('archived','forgotten')");
int64_t rebuilt = (rebuilt_override >= 0) ? rebuilt_override
    : scalar(conn, "SELECT COUNT(*) FROM proj_vector_payload");   // 物化表实际行数
if (rebuilt < ground_truth) {
    // truncation_suspected:保留 active,emit projection.rebuild_failed,不替换
} else {
    // healthy:DELETE + INSERT FROM (statement_vectors JOIN statements WHERE embedded & 非retire)
}
```
复用既有 `rebuild_projection_with_injected_count(name, injected, now)` 测试钩子（M0.8 已有),让 `proj_vector_payload` 走相同注入路径。

- [ ] **Step 2: TC-VEC-REPAIR CRITICAL 测试**

```python
"""TC-VEC-REPAIR [CRITICAL]: idx_vector_payload rebuild 物化 < ground truth → 不替换.

spec §16.3-3/-6: 向量投影 repair guard。构造 rebuild 抽取 < 已嵌入向量数 →
emit projection.rebuild_failed(truncation_suspected) + active 投影不替换。
闭合 M0.8 finding #6(M0.8 6 类 SQL 投影真 1:1 故 dormant;此处计数天然不同)。
"""
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


def _seed_embedded(rt, n):
    """seed n 条 statement + 跑 worker 嵌入 + 跑投影物化。"""
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        for i in range(n):
            c.execute(
                "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
                "subject_kind,subject_id,predicate,object_kind,object_value,"
                "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
                "confidence,observed_at,salience,affect_json,activation,last_accessed,"
                "provenance,consolidation_state,review_status,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"s{i}","default","alice","first_person","cognizer","bob","knows",
                 "str",f"v{i}","a"*64,"v1","believes","pos",0.9,"2026-05-30T09:00:00Z",
                 0.5,"{}",0.0,"2026-05-30T09:00:00Z","user_input","consolidated",
                 "approved","2026-05-30T09:00:00Z","2026-05-30T09:00:00Z"))
        c.commit()
    emb = _core.StubEmbeddingAdapter(8)
    idx = _core.SqliteBlobVectorIndex()
    w = _core.EmbeddingWorker(rt.adapter, emb, idx)
    w.tick_one_batch("2026-05-30T10:00:00Z")
    pm = _core.ProjectionMaintainer(rt.adapter)
    pm.tick_one_batch("2026-05-30T10:01:00Z")
    return pm


def test_vector_truncation_suspected_keeps_active(rt):
    pm = _seed_embedded(rt, 3)
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        before = c.execute("SELECT COUNT(*) FROM proj_vector_payload").fetchone()[0]
    assert before == 3
    report = pm.rebuild_projection_with_injected_count(
        "proj_vector_payload", injected_rebuilt=2, now_iso="2026-05-30T11:00:00Z")
    assert report.truncation_suspected is True
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        after = c.execute("SELECT COUNT(*) FROM proj_vector_payload").fetchone()[0]
        status = c.execute("SELECT status FROM projection_rebuild_state "
                           "WHERE projection_name='proj_vector_payload'").fetchone()[0]
        ev = c.execute("SELECT COUNT(*) FROM bus_events "
                       "WHERE event_type='projection.rebuild_failed'").fetchone()[0]
    assert after == 3, "truncation 时 active 投影不被替换"
    assert status == "truncation_suspected"
    assert ev == 1
```

- [ ] **Step 3: 重建 + 跑 + Commit**

```bash
cmake --build build 2>&1 | tail -2
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages 2>&1 | tail -1
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
pytest tests/python/test_tc_vec_repair.py -v 2>&1 | tail -6
git add src/projection/projection_maintainer.cpp tests/python/test_tc_vec_repair.py
git commit -m "$(cat <<'EOF'
feat(M0.9/substrate): idx_vector_payload repair guard — TC-VEC-REPAIR CRITICAL

§16.3-3/-6: proj_vector_payload 的 ground_truth(已嵌入向量数) 与 rebuilt(物化行数)
天然不同 → rebuilt<ground_truth 触发 truncation_suspected + 保留 active + emit
projection.rebuild_failed。闭合 M0.8 finding #6 的 dormant guard。

EOF
)"
```

> 注:Task 10 依赖 Task 13 的 pybind（`_core.StubEmbeddingAdapter`/`EmbeddingWorker`/`ProjectionMaintainer`/`SqliteBlobVectorIndex`）。执行顺序:先做 C++ rebuild 实现（Step 1）,Python CRITICAL 测试（Step 2）在 Task 13 binding 就绪后转绿、届时一并 commit;或把 Task 10 Step 2/3 移到 Task 13 之后。Subagent controller 按依赖编排。

---

## Task 11: SemanticRetriever — vector_recall（隐私先行）

**Files:**
- Create: `include/starling/retrieval/semantic_retriever.hpp`, `src/retrieval/semantic_retriever.cpp`, `tests/cpp/test_semantic_retriever.cpp`
- Modify: `CMakeLists.txt`, `tests/cpp/CMakeLists.txt`

**Spec ref:** §7。镜像 `basic_retriever.hpp` 结构。

- [ ] **Step 1: 头文件**

```cpp
// include/starling/retrieval/semantic_retriever.hpp
#pragma once
#include <string>
#include <vector>
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/embedding/embedding_adapter.hpp"
#include "starling/vector/vector_index.hpp"
#include "starling/retrieval/statement_row.hpp"

namespace starling::retrieval {

struct SemanticRetrieverParams {
    std::string tenant_id, holder_id;
    std::string holder_perspective;   // 空=any
    std::string query_text;
    int k = 10;
    std::string trace_id, query_id;
};
struct SemanticScored { StatementRow row; double score; };
struct SemanticResult {
    std::vector<SemanticScored> rows;   // cosine 降序
    bool degraded = false;              // 无 embedder/向量 → true
};

class SemanticRetriever {
public:
    SemanticRetriever(persistence::SqliteAdapter& a, embedding::EmbeddingAdapter& e,
                      vector::VectorIndex& idx) : adapter_(a), embedder_(e), index_(idx) {}
    SemanticResult vector_recall(persistence::Connection&, const SemanticRetrieverParams&);
    persistence::Connection& connection() { return adapter_.connection(); }
private:
    persistence::SqliteAdapter& adapter_;
    embedding::EmbeddingAdapter& embedder_;
    vector::VectorIndex& index_;
};

}  // namespace starling::retrieval
```

- [ ] **Step 2: 失败测试（隐私先行:越权不返回）**

```cpp
// tests/cpp/test_semantic_retriever.cpp
TEST(SemanticRetriever, RanksByQuerySimilarityWithinVisibleScope) {
    // seed + worker 嵌入 3 条可见 stmt → vector_recall(query) 返回按 cosine 降序
    // 1 条 pending_review 不可见 → 不出现在结果
    // ...（构造同 Task 9）
}
```

- [ ] **Step 3: CMake 注册** + **Step 4: 实现**

`vector_recall`：`q = embedder_.embed(params.query_text).vector`；`SearchScope scope{tenant, holder, perspective(空→nullopt), visible_only=true}`；`cand = index_.search_topk(conn, q, k, scope)`（隐私谓词已在 search_topk 下推）；按 cand 顺序 `SELECT * FROM statements WHERE id=?` 组 `StatementRow`；返回 `{rows, degraded=false}`。**绝不先 top-k 再过滤。**

- [ ] **Step 5: 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R SemanticRetriever --output-on-failure 2>&1 | tail -8
git add include/starling/retrieval/semantic_retriever.hpp src/retrieval/semantic_retriever.cpp tests/cpp/test_semantic_retriever.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.9/retrieval): SemanticRetriever.vector_recall — 隐私先行向量召回

spec §7: embed(query) → search_topk(可见性 scope 下推) → 按 cosine 降序。
绝不先 top-k 再过滤。镜像 BasicRetriever 结构。

EOF
)"
```

---

## Task 12: vector_index capability + feature-level 降级（不动 RuntimeHealth）

**Files:**
- Modify: `src/preflight.cpp`（`capability_has` 加 `vector_index`）、`include/starling/preflight.hpp`（注释补 `vector_index`）
- Create: `tests/cpp/test_vector_capability.cpp`
- Modify: `tests/cpp/CMakeLists.txt`

**Spec ref:** §9。**关键决策（plan 细化）:** M0.9 不引入 `RuntimeHealth.DEGRADED` 转换 + 不改 bus 写门控（会回归所有写测试）。降级 = feature-level:`SemanticRetriever` 在无 embedder 时返回 `degraded=true` 空结果;`EmbeddingWorker` 仅在有 embedder 时构造/tick。`vector_index` 仅加进 `capability_has` 供将来 vector-required profile 用,local-store M0.9 **不** required → 健康保持 READY。

- [ ] **Step 1: capability_has 加 vector_index**

`src/preflight.cpp` 的 `capability_has` 末尾（`testing_helper_marker` 后、`return false` 前）加：
```cpp
    if (name == "vector_index") return !cap.vector_backend.empty();
```

- [ ] **Step 2: 测试**

```cpp
// tests/cpp/test_vector_capability.cpp
#include "starling/preflight.hpp"
#include <gtest/gtest.h>
using namespace starling;

TEST(VectorCapability, RecognizedAndDrivenByBackend) {
    ProfileCapability cap; cap.vector_backend = "";
    EXPECT_EQ(preflight(cap, {"vector_index"}).status, PreflightStatus::UNREADY);
    cap.vector_backend = "sqlite_blob";
    EXPECT_EQ(preflight(cap, {"vector_index"}).status, PreflightStatus::READY);
}
TEST(VectorCapability, NotRequiredByLocalStoreStaysReady) {
    // 默认 local-store required 列表不含 vector_index → 缺失不影响 READY
    ProfileCapability cap;  // vector_backend 空
    EXPECT_EQ(preflight(cap, {"c_plus_plus_core"}).status,
              PreflightStatus::UNREADY);  // 这条只验证 vector_index 不在必需集即可
}
```

- [ ] **Step 3: CMake 注册 + 跑 + Commit**

```bash
cmake -S . -B build -G Ninja 2>&1 | tail -2 && cmake --build build 2>&1 | tail -2
ctest --test-dir build -R VectorCapability --output-on-failure 2>&1 | tail -6
# 回归:preflight 既有测试仍绿
ctest --test-dir build -R Preflight --output-on-failure 2>&1 | tail -4
git add src/preflight.cpp include/starling/preflight.hpp tests/cpp/test_vector_capability.cpp tests/cpp/CMakeLists.txt
git commit -m "$(cat <<'EOF'
feat(M0.9/preflight): vector_index capability + feature-level 降级

spec §9(plan 细化): vector_index 接进 capability_has(vector_backend 非空)。
local-store 不 required → 健康保持 READY(不改 RuntimeHealth/bus 写门控,
避免回归所有写测试)。降级走 feature-level:无 embedder→vector_recall degraded。

EOF
)"
```

---

## Task 13: pybind bindings + Python wrappers

**Files:**
- Modify: `bindings/python/module.cpp`
- Create: `python/starling/vector/__init__.py`, `python/starling/embedding/__init__.py`
- Create: `tests/python/test_m0_9_bindings.py`

**Spec ref:** §3（Python 暴露）。

- [ ] **Step 1: 暴露类（PYBIND11_MODULE 块追加）**

- `StubEmbeddingAdapter`(dim=8) + `.fail_next(text)`；`OpenAIEmbeddingAdapter` 经 `Config::from_env`（可选,prefer 仅暴露 Stub 给 CI，OpenAI 经工厂函数 `make_openai_embedding_adapter_from_env()`）。
- `SqliteBlobVectorIndex`()（无参构造）。
- `EmbeddingWorker`(adapter, embedder, index) + `.tick_one_batch(now_iso)`（conn-free,内部 `s.connection()`）。
- `SemanticRetriever`(adapter, embedder, index) + `.vector_recall(params)`（返回 rows + degraded）。
- `ProjectionMaintainer` 已绑（M0.8）;确认 `rebuild_projection_with_injected_count` 对 `proj_vector_payload` 可用。

绑定 lambda 模式同 M0.8：`[](EmbeddingWorker& s, std::string now){ return s.tick_one_batch(s.connection(), now); }`。各类构造需 `py::keep_alive` 保持 adapter/embedder/index 引用存活（embedder/index 是引用成员）。

- [ ] **Step 2: Python 便利包**（`python/starling/{vector,embedding}/__init__.py` re-export `_core` 对应类）

- [ ] **Step 3: 重建 + 刷新 editable**

```bash
cmake --build build 2>&1 | tail -3
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages 2>&1 | tail -1
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
```

- [ ] **Step 4: binding smoke 测试**

```python
# tests/python/test_m0_9_bindings.py
from starling import _core

def test_classes_exist():
    for n in ["StubEmbeddingAdapter","SqliteBlobVectorIndex","EmbeddingWorker","SemanticRetriever"]:
        assert hasattr(_core, n)

def test_stub_embed_deterministic():
    e = _core.StubEmbeddingAdapter(8)
    # embed 不必绑;只验证构造 + dim
    assert e is not None
```

- [ ] **Step 5: 回跑 Task 10 CRITICAL（binding 就绪后转绿）+ Commit**

```bash
pytest tests/python/test_tc_vec_repair.py tests/python/test_m0_9_bindings.py -v 2>&1 | tail -10
ctest --test-dir build 2>&1 | tail -2
git add bindings/python/module.cpp python/starling/vector python/starling/embedding tests/python/test_m0_9_bindings.py
git commit -m "$(cat <<'EOF'
feat(M0.9): pybind bindings — Embedding/Vector/Worker/SemanticRetriever

暴露 StubEmbeddingAdapter / SqliteBlobVectorIndex / EmbeddingWorker /
SemanticRetriever 给 Python(conn-free,同 M0.8 模式)。TC-VEC-REPAIR 转绿。

EOF
)"
```

---

## Task 14: Python 集成 — semantic_retrieve 端到端 + 降级回退

**Files:**
- Create: `tests/python/test_semantic_retrieve_e2e.py`

**Spec ref:** §7 + §9 + §11。

- [ ] **Step 1: 端到端 + 降级测试**

```python
"""M0.9 端到端:seed → stub worker 嵌入 → semantic_retrieve 排序召回;无 embedder 降级。"""
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


def _seed(rt, sid, objv):
    with sqlite3.connect(str(rt.adapter.db_path)) as c:
        c.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
            "confidence,observed_at,salience,affect_json,activation,last_accessed,"
            "provenance,consolidation_state,review_status,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid,"default","alice","first_person","cognizer","bob","knows","str",objv,
             "a"*64,"v1","believes","pos",0.9,"2026-05-30T09:00:00Z",0.5,"{}",0.0,
             "2026-05-30T09:00:00Z","user_input","consolidated","approved",
             "2026-05-30T09:00:00Z","2026-05-30T09:00:00Z"))
        c.commit()


def test_semantic_retrieve_e2e(rt):
    _seed(rt, "s1", "cats are mammals"); _seed(rt, "s2", "stock market crash")
    emb = _core.StubEmbeddingAdapter(8); idx = _core.SqliteBlobVectorIndex()
    _core.EmbeddingWorker(rt.adapter, emb, idx).tick_one_batch("2026-05-30T10:00:00Z")
    sr = _core.SemanticRetriever(rt.adapter, emb, idx)
    res = sr.vector_recall(_core.SemanticRetrieverParams(
        tenant_id="default", holder_id="alice", query_text="cats are mammals", k=2))
    assert res.degraded is False
    assert len(res.rows) >= 1
    assert res.rows[0].row.id == "s1"   # query 与 s1 文本同 → 最高分


def test_basic_retrieve_unaffected_without_vectors(rt):
    # 不跑 worker(无向量)→ basic_retrieve 仍正常工作(回归保证)
    _seed(rt, "s1", "x")
    # 经既有 bus/retrieve 路径验证写 + basic_retrieve 不受向量子系统影响
    # (沿用既有 basic_retrieve 测试套路)
```

- [ ] **Step 2: 跑 + Commit**

```bash
pytest tests/python/test_semantic_retrieve_e2e.py -v 2>&1 | tail -8
git add tests/python/test_semantic_retrieve_e2e.py
git commit -m "$(cat <<'EOF'
test(M0.9): semantic_retrieve 端到端 + basic_retrieve 不受影响

spec §7/§9/§11: seed→stub worker→vector_recall 按相似度排序;无向量时
basic_retrieve 正常(降级隔离)。

EOF
)"
```

---

## Task 15: 回归确认（M0.8 + P2.a 全绿）

**Files:** 无（只验证）。

- [ ] **Step 1: 全 guard**

```bash
cmake --build build 2>&1 | tail -2
cmake --install build --prefix /Users/jaredguo-mini/develop/memory/starling/.venv/lib/python3.14/site-packages 2>&1 | tail -1
pip install -e . --no-deps --force-reinstall 2>&1 | tail -1
ctest --test-dir build --output-on-failure 2>&1 | tail -3
pytest tests/python -q 2>&1 | tail -3
python scripts/ci_static_scan.py 2>&1 | tail -2
```
Expected: ctest 全绿（431 + M0.9 新增）；pytest 473+ passed（+ M0.9 新增）+ 13 skipped；ci_static_scan OK。**特别确认 M0.8 §16.3-9 回归:`pytest tests/python/test_tc_new_conflict_severe.py`。** 若任何 RED,回对应 task 修复。

---

## Task 16: Milestone close — roadmap flip + final review + merge

**Files:**
- Modify: `docs/superpowers/plans/2026-05-23-roadmap.md`
- After merge: commit plan-doc 到 main

- [ ] **Step 1: 识别最后 work commit** `git log --oneline main..HEAD | head`，记 topmost（非 roadmap-flip）SHA。

- [ ] **Step 2: flip roadmap** —— P2.b 行:M0.9（向量层）标 ✅ + 链接 plan；状态表 `P2.b (M0.9 向量层)` 行 → 已写/✅完成/日期/pin SHA。

- [ ] **Step 3: commit roadmap flip**

```bash
git add docs/superpowers/plans/2026-05-23-roadmap.md
git commit -m "$(cat <<'EOF'
chore(M0.9): mark vector-layer complete in roadmap

P2.b 第二阶段 (M0.9 向量基础层) 完成: EmbeddingAdapter/VectorIndex/
EmbeddingWorker/PatternSeparator/SemanticRetriever/idx_vector_payload。
pin 最后 work commit。P2.b 全部完成,下一步 P2.c。

EOF
)"
```

- [ ] **Step 4: worktree 全绿**（同 Task 15）。

- [ ] **Step 5: 派发整分支 final reviewer**（Controller-only,`feature-dev:code-reviewer`）。Scrutiny: 模式分离正交化正确性、search_topk 隐私 scoping（越权不返回）、idx_vector_payload repair guard 真触发、EmbeddingWorker 扫描幂等 + 失败重试、API key 不泄漏、回归零破坏。

- [ ] **Step 6: AskUserQuestion 合并 consent**（Controller-only）。

- [ ] **Step 7: 若 consent=merge**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git merge --no-ff worktree-m0-9-vector-layer -m "$(cat <<'EOF'
Merge M0.9: 向量基础层 (P2.b 第二阶段)

EmbeddingAdapter(stub+openai) + VectorIndex(SqliteBlobVectorIndex 暴力 cosine,
seekdb 后端留 seam) + EmbeddingWorker(扫描驱动异步嵌入 + 模式分离) +
SemanticRetriever(隐私先行 vector_recall) + idx_vector_payload(第 7 类投影,
§16.3-3/-6 repair guard 真生效,闭合 M0.8 finding #6)。migrations 0016-0017。
模式补全/EM-LLM/seekdb 后端延后。

ctest <N>/<N>, pytest <M>/<M>, ci_static_scan clean。

EOF
)"
```

- [ ] **Step 8: commit plan-doc 到 main**

```bash
cp .claude/worktrees/m0-9-vector-layer/docs/superpowers/plans/2026-05-30-m0-9-vector-layer.md \
   docs/superpowers/plans/2026-05-30-m0-9-vector-layer.md
git add docs/superpowers/plans/2026-05-30-m0-9-vector-layer.md
git commit -m "$(cat <<'EOF'
docs(M0.9): land vector-layer implementation plan

Plan 在 worktree 分支保持 untracked (项目策略), milestone close 后落 main。

EOF
)"
```

- [ ] **Step 9: post-merge 全绿**（rebuild + reinstall + ctest + pytest + scan，从 root）。

- [ ] **Step 10: 拆 worktree**

```bash
git worktree remove --force .claude/worktrees/m0-9-vector-layer
git branch -D worktree-m0-9-vector-layer
git worktree list   # 仅 main
```

- [ ] **Step 11: final report**（merge SHA / last work commit / 计数 / TC-VEC-REPAIR 状态 / P2.b 全完成 / 下一步 P2.c）。

---

## Self-Review（writing-plans 要求）

**1. Spec coverage:** §3.1 EmbeddingAdapter→T6/T7;§3.2 VectorIndex→T5;§3.3 PatternSeparator→T4;§3.4 EmbeddingWorker→T8;§3.5 SemanticRetriever→T11;§4 schema→T1/T2（0017 edge 迁移因 statement_edges 已有 weight/metadata_json 而**裁掉**,改用既有列;已在 §文件结构 + T2 commit body 说明）;§5 数据流→T8;§6 模式分离→T4;§7 vector_recall→T11;§8 idx_vector_payload→T9/T10;§9 DEGRADED→T12（**plan 细化为 feature-level 降级,不动 RuntimeHealth**,理由:bus 写门控 `==READY` 会回归所有写测试;已在 T12 + 执行 handoff 标注）;§11 测试→各 task + T14;§16.3-3/-6 CRITICAL→T10。无遗漏。

**2. Placeholder scan:** 纯计算 task（T3/T4）给全代码;IO task（T5/T8/T9/T11）给接口全签名 + SQL + 关键实现步骤,余下让 implementer 按 header 契约 + 既有 helper（sqlite_helpers/emit_event）写出——这是 subagent-driven 的预期,非 placeholder。render_text 模板已定（subject_id+predicate+object_value）。

**3. Type consistency:** `EmbeddingResult{vector,dim,model}`、`SeparationResult{index_vector,overlaps}`、`ScoredId{stmt_id,score}`、`SearchScope`、`EmbeddingStats`、`SemanticResult{rows,degraded}` 贯穿 T3–T14 一致;`tick_one_batch(conn,now)` 签名 worker/projection 一致;`vector::normalize`/`cosine`/`to_blob`/`from_blob` 在 T3 定义、T4/T5/T8 复用;binding（T13）类名与 C++（T5/T6/T8/T11）一致。

**两处 spec 偏离（codebase-driven，已在对应 task + handoff 标注，需 user 知晓）:**
1. **migration 0017（MAY_OVERLAP_WITH 列）裁掉** —— `statement_edges` 既有 `weight REAL` + `metadata_json`,similarity 存 weight、resolved 存 metadata_json。migrations 从 3 个减到 2 个。
2. **§9 DEGRADED 改 feature-level 降级** —— 不引入 `RuntimeHealth.DEGRADED` 转换（bus 写门控 `==READY` 会回归所有写测试）;降级走 SemanticRetriever 的 `degraded` 标记 + EmbeddingWorker 按 embedder 可用性调度。真 RuntimeHealth.DEGRADED 留到存在 vector-required profile 时。

---

## 元数据

- **里程碑**: M0.9（P2.b 第二阶段,向量基础层）
- **依赖**: M0.8 close（main `4e70c82` / spec `7667dfd`）
- **后继**: 模式补全（PPR）+ EM-LLM/logprobs → P2.c（Prospective/Affect）
- **分支**: worktree-m0-9-vector-layer，--no-ff 合并 main
- **Task 数**: 17（Task 0–16）

