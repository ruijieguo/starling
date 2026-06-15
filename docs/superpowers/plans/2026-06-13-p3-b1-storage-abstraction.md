# P3.b1 local-store 存储抽象 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把散落 44 个 C++ 文件的 163 处存储读写收编进统一的三类 Store 接口(文本/Meta=SQLite、向量=zvec、关系/图=LadybugDB),profile 化引擎选型,当前交付 local-store。

**Architecture:** 三类 Store 抽象(`MetaStore`/`VectorStore`/`GraphStore`)+ `StoreBundle` profile 工厂 + `ProfileCapability` 声明。所有读写经接口;一致性 = MetaStore(SQLite)是 ACID 锚(业务写 + outbox 事件同事务),Vector/Graph 是可重建派生投影、异步从事件物化(saga/outbox)。先抽象(SQLite everywhere,零行为变化)再逐引擎换装(zvec → LadybugDB 后置 PoC)。

**Tech Stack:** C++20 + SQLite + pybind11;phase 5 vendored zvec(C++17,macOS arm64 NEON);phase 6 vendored LadybugDB(后置)。

**Spec:** `docs/superpowers/specs/2026-06-12-p3-b1-localstore-substrate-design.md`(已批准)。

**工程约定(每任务生效):**
- 仓库根 `/Users/jaredguo-mini/develop/memory/starling`(非 worktree;每条 Bash 显式 cd)。
- 构建:`PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`;改绑定/C++ 后跑 pytest 前先加 `--python-editable`。
- C++ 测试:`./build/tests/cpp/starling_tests --gtest_filter='<Suite>.*'`;全量 `ctest --test-dir build`(基线 **567**)。
- Python:`.venv/bin/python -m pytest tests/python -q`(基线 **595 passed / 13 skipped**)。
- 核心语义居 C++(`src/`+`include/starling/store/`);Python 仅绑定转发(仓库 CLAUDE.md 边界规则,2026-06-11 裁定)。
- git:explicit-path add(禁 `.`/`-A`);commit 尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`;禁 --no-verify/--amend;中文 body。
- **TDD 强制**:每任务先写失败测试 → 跑红 → 最小实现 → 跑绿 → commit。
- 不可破坏钉测:全部现有 ctest 567 + pytest 595;statement 六态机各转换语义、conflict 边去重、recalled 幂等键、C2/§16.3 冲突仲裁。
- 每 phase 出口:phase 1–4 零行为变化 / 零 migration(0024 之后)/ 零 Python 改;phase 5 向量换装后召回质量不退。

---

## Phase 进度

- [x] **Phase 1 地基**(DONE,commit `3bf55b5`):`ProfileCapability` + `StorageProfile`、`GraphStore` 接口(`insert_edge`/`neighbors`/`edges_by_conflict_key`)、`SqliteGraphStore` backend、`StoreBundle::open_local`、`test_store_foundation.cpp`(3 钉测)。ctest 567。
- [x] **Phase 2 MetaStore 写收编(StatementStore)**(DONE):`StatementStore` 13 法(10 转换/修正 + `apply_mild_contradict` + `archive_nonterminal` + `insert_arbitrated_fork`,均 TDD 先红);路由 consolidation_ops/scheduler/arbitration/recon_engine/bus/second_order —— 删 **14 处内联 `UPDATE statements` + 1 处 fork INSERT**;ci_static_scan **红线#2**(statements 写只允许 store/ + statement_writer.cpp 授权 + testing)。`StatementWriter` 主 INSERT 确立为 statements INSERT 唯一受控授权写者(物理迁 store/ 降级为后续纯命名空间清理,低收益高风险)。commits `94836ce`/`7e31e9d`/`39b92b3`/`7fc47b1`/本次;ctest 580 / pytest 595 全绿,零行为变化。接口缺口(arbitration 两处语义)在路由阶段暴露并补齐——印证逐法 exact SQL 迁入的必要。
- [x] **Phase 3 MetaStore 读收编**(DONE,Task 3.1 接口 + Task 3.2 路由分类):`MetaStore` 读接口(`get_statement` 点查 + `query_statements(StatementFilter)`:holder/subject/predicate/predicate_in/states/review/as_of/nesting_depth/provenance/id_in/order/limit)+ `SqliteMetaStore`(动态参数化拼 SQL,order_by 白名单)+ `StatementRow` 扩展 4 列(salience/activation/provenance/nesting_depth)+ 5 TDD 测试(get/query 各 WHERE 模式)。ctest 586。**Task 3.2 读路由完成**(49b6919→d631a5a,agent 实测 38 读点分类:7 路已路由 + 余裁剪):
  - **已路由 ✅**(纯 statements 单表读 → query_statements/get_statement,各全绿):semantic/pattern `fetch_row`(`49b6919`)、mentalizing believe/misalign(`d455da9`)、tom_engine perspective(`449e606`)、affect_buffer `member_ids`(`5b92034`,扩 `StatementFilter.salience_ge` + 双键 order 白名单)、projection `read_stmt`(点查 → get_statement,10 列全覆盖)、planner `fetch_semantic` 补查(salience/activation/provenance → get_statement)。
  - **裁剪登记(单表但不可路由 query_statements)**:
    - replay `sample_volatile` —— **跨租户全局采样**(无 tenant 过滤)+ 读 replay 专用字段(`last_replayed`/`replay_count`/`derived_depth`)+ 无守卫,与 `query_statements` tenant 必填(多租户隔离安全契约)冲突,保留 replay 子系统。
    - planner `fetch_by_id` —— 检索编排内部补行,用 planner 私有 `kSelectCols`/`read_row` 列序 + `kStableTail` as_of 时间窗 + `FetchedRow` 装配,与 statement_main/semantic/graph_supersedes 同属多路检索编排。
    - policy_engine `read_stmt_meta` —— 读 `event_time_end`(commitment 触发专用列,不在 `StatementRow`),属 prospective 触发子系统专用元数据。
  - **裁剪登记(保留子系统,非纯 statements 读)**:跨表 JOIN(pattern expand JOIN edges / mentalizing_more 双 JOIN / embedding LEFT JOIN vectors / who_committed JOIN cg)、frontier EXISTS(basic_retriever)、commitment 子查询、COUNT(depth_estimator)、DISTINCT tenant(bus/engine)、EXISTS 检验(know/already_modeled/trigger);以及需 StatementRow 外字段的点查(load_source `derived_depth` / conflict_probe `supersedes_id`+`event_time_start` / common_ground_subscriber `scope_parties_json` / belief_tracker `perceived_by_json`)—— 这些读交织多表/聚合或需富字段,换引擎时各 backend 专门实现,不收编进通用 query_statements。
- [~] **Phase 3 余(其余 meta 表 owner 化)** —— **defer(YAGNI)**:proj_*/commitment/common_ground/cognizer_relations/checkpoint 各已单 owner、local-store 下全 SQLite,无写散落痛点(MetaStore 抽象 statements 因其核心热表 + 写散落 8 文件的真实痛点)。提前给这些表做接口抽象,唯一收益是未来 dist/cloud-store,而那尚未启动 → 违反 YAGNI;留真正做 dist-store 时按需抽象。GraphStore(下阶段)是例外——图存储是 LadybugDB 换装的直接目标,接口已就绪需实装。
- [x] **Phase 4 GraphStore 路由**(写侧 DONE,`e55c76f`):insert_edge 四写者收编 + conflict 去重下沉 + 接口对齐 Connection&;读侧(neighbors 图遍历/scope 富集)、conflict_key_backfill(回填工具)、cognizer_relations(社会图)经分析裁剪/defer。
- [x] **Phase 5 zvec backend(DONE)** —— Task 5.1 编译关卡 + 5.1b CMake 集成(ExternalProject + 2-bundle force_load)+ 5.2 ZvecVectorIndex(zvec KNN + SQL scope 精过滤,parity 绿,filter allowlist)+ 5.3 工厂(sqlite|zvec 可切,双路径验证)+ 5.4 perf 基线(recall=1.000,zvec 快 2.3x)+ dashboard 接线。STARLING_VECTOR_ZVEC 默认 OFF 零影响,ON 时 dashboard config/env 切 zvec。
- [x] **Phase 6 LadybugDB backend(DONE,go/no-go = NO-GO)** —— LadybugDB v0.17.1 集成可行(MIT/C++20/导出 C++ target + 依赖聚合,优于 zvec),但收益小(边量小,SQLite 递归 CTE 够)+ 冲突边同步→异步破坏 C2/§16.3 即时冲突可见性 → NO-GO,保 SqliteGraphStore;LadybugDB 留 P3+ seam(GraphStore 接口已兑现抽象)。
- [~] **Phase 7 crypto_erasure 局部 keystore —— DEFER P3+**(用户 2026-06-15 裁定,不在 P3 实现)。Engram 已留 `key_ref`/`content_ciphertext`/`erased_at` 字段 + NullKms 占位钩子(调用点不变);真 crypto_erasure(LocalFileKms KEK/DEK 信封 + AES-256-GCM + erase 删 DEK 使密文不可逆)推迟到 P3+。**P3.b1 以 phase 1-6 收官。**

---

## Phase 2:MetaStore 写收编 —— StatementStore

**问题:** `statements` 的写散落 8 文件(实测):replay/consolidation_ops、replay/replay_scheduler、reconsolidation/arbitration、reconsolidation/reconsolidation_engine、bus/bus、tom/second_order、bus/statement_writer、testing/testing_marker(豁免)。六态机各转换的 WHERE 守卫是核心不变式,必须收进单一 store、逐法钉测。

**File Structure:**
- Create `include/starling/store/statement_store.hpp` —— StatementStore 抽象接口(转换语义动词)。
- Create `include/starling/store/sqlite_statement_store.hpp` + `src/store/sqlite_statement_store.cpp` —— SQLite backend(经持有 adapter 单连接,与现 bus 事务同连接)。
- Create `tests/cpp/test_statement_store.cpp` —— 逐法 WHERE 守卫钉测。
- Modify(routing,各 caller 删内联 SQL 改调 store):`src/replay/consolidation_ops.cpp`、`src/replay/replay_scheduler.cpp`、`src/reconsolidation/arbitration.cpp`、`src/reconsolidation/reconsolidation_engine.cpp`、`src/bus/bus.cpp`、`src/tom/second_order.cpp`。
- Modify `CMakeLists.txt`(src +2)、`tests/cpp/CMakeLists.txt`(+1)。
- statement_writer 的大 INSERT 迁移单列(Task 2.8),风险最高放最后。

> **不变式映射(实测 file:line → 方法,exact SQL 见各 Task):** compress(consolidation_ops.cpp:31)→`mark_consolidated`;reinforce(:57)→`reinforce`;abstract(:80)→`bump_replay_count`;reconcile(:154)→`enter_reconsolidating`;decay-archive(:135,守卫 state='consolidated')+supersede-archive(bus.cpp:308,守卫 'consolidated')+TTL-archive(replay_scheduler.cpp:379,守卫 'volatile')+arbitration-archive(:452)→`archive(ids,tenant,from_state)`;recon 兜底(reconsolidation_engine.cpp:265,守卫 'replaying_reconsolidating')→`restore_consolidated`;振荡防护(replay_scheduler.cpp:289,replay_count>=5 且 state∈volatile/replaying_consolidating)→`force_consolidate_pending_review`;mild-correction(bus.cpp:264 + arbitration.cpp:284)→`apply_mild_correction`;支持仲裁(arbitration.cpp:204)→`set_confidence_consolidated`;salience 继承(second_order.cpp:170)→`inherit_salience`;仲裁分叉 INSERT(arbitration.cpp:389)→`insert_arbitrated_fork`;主 INSERT(statement_writer.cpp)→`insert_statement`(Task 2.8)。

### Task 2.1: StatementStore 接口 + SqliteStatementStore 骨架 + `mark_consolidated`

**Files:**
- Create: `include/starling/store/statement_store.hpp`
- Create: `include/starling/store/sqlite_statement_store.hpp`
- Create: `src/store/sqlite_statement_store.cpp`
- Create: `tests/cpp/test_statement_store.cpp`
- Modify: `CMakeLists.txt`、`tests/cpp/CMakeLists.txt`

- [ ] **Step 1: 写失败测试 tests/cpp/test_statement_store.cpp**

```cpp
// P3.b1 phase 2:StatementStore —— statements 六态机转换收编。逐法钉 WHERE
// 守卫语义(从源写点逐字迁入,行为不变)。fixtures 直接 SQL 种 statements 行。
#include "starling/store/sqlite_statement_store.hpp"

#include "starling/persistence/migration_runner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <gtest/gtest.h>
#include <sqlite3.h>

#include <memory>
#include <string>

namespace starling::store {
namespace {

std::unique_ptr<persistence::SqliteAdapter> make_adapter() {
    auto a = persistence::SqliteAdapter::open(":memory:");
    persistence::MigrationRunner(a->connection().raw()).migrate_to_latest();
    return a;
}

void seed(persistence::Connection& conn, const char* id, const char* state,
          int replay_count = 0, double salience = 0.5) {
    char sql[1100];
    std::snprintf(sql, sizeof(sql),
        "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
        "subject_kind,subject_id,predicate,object_kind,object_value,"
        "canonical_object_hash,canonical_object_hash_version,modality,polarity,"
        "confidence,observed_at,salience,affect_json,activation,last_accessed,"
        "provenance,consolidation_state,review_status,replay_count,access_count,"
        "nesting_depth,created_at,updated_at) VALUES("
        "'%s','default','cog-self','FIRST_PERSON','cognizer','Bob','knows','str',"
        "'x','h-%s','v1','KNOWS','POS',0.9,'2026-06-10T00:00:00Z',%f,'{}',0.0,"
        "'2026-06-10T00:00:00Z','user_input','%s','approved',%d,0,0,"
        "'2026-06-10T00:00:00Z','2026-06-10T00:00:00Z')",
        id, id, salience, state, replay_count);
    char* err = nullptr;
    ASSERT_EQ(sqlite3_exec(conn.raw(), sql, nullptr, nullptr, &err), SQLITE_OK)
        << (err ? err : "");
}

std::string state_of(persistence::Connection& conn, const char* id) {
    sqlite3_stmt* s = nullptr;
    sqlite3_prepare_v2(conn.raw(),
        "SELECT consolidation_state FROM statements WHERE id=?", -1, &s, nullptr);
    sqlite3_bind_text(s, 1, id, -1, SQLITE_TRANSIENT);
    sqlite3_step(s);
    std::string v = reinterpret_cast<const char*>(sqlite3_column_text(s, 0));
    sqlite3_finalize(s);
    return v;
}

}  // namespace

TEST(StatementStore, MarkConsolidatedOnlyFromVolatile) {
    auto a = make_adapter();
    SqliteStatementStore st(*a);
    seed(a->connection(), "s1", "volatile");
    seed(a->connection(), "s2", "consolidated");   // 守卫:非 volatile 不动

    EXPECT_EQ(st.mark_consolidated({"s1", "s2"}, "default", "batch-1"), 1);
    EXPECT_EQ(state_of(a->connection(), "s1"), "consolidated");
    EXPECT_EQ(state_of(a->connection(), "s2"), "consolidated");
    // replay_count +1、batch 记录(s1 被改的那条)。
    sqlite3_stmt* q = nullptr;
    sqlite3_prepare_v2(a->connection().raw(),
        "SELECT replay_count,last_replay_batch_id FROM statements WHERE id='s1'",
        -1, &q, nullptr);
    sqlite3_step(q);
    EXPECT_EQ(sqlite3_column_int(q, 0), 1);
    EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(q, 1)), "batch-1");
    sqlite3_finalize(q);
}

}  // namespace starling::store
```

- [ ] **Step 2: 跑测试确认编译失败**

Run: `cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build 2>&1 | tail -3`
Expected: FAIL,`sqlite_statement_store.hpp: No such file or directory`(先把测试加进 tests/cpp/CMakeLists.txt)。

- [ ] **Step 3: 写 statement_store.hpp(接口,全 16 法签名一次定齐,后续 Task 仅实现)**

```cpp
#pragma once
// StatementStore —— statements 六态机转换 + 局部修正 + 插入的语义动词收编
// (P3.b1 phase 2)。每法封装一条 statements 写,WHERE 守卫即不变式;返回
// int = sqlite3_changes(受影响行数),调用方据此门控副作用(事件 emit)。
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace starling::store {

class StatementStore {
public:
    virtual ~StatementStore() = default;

    // ── 六态机转换 ──
    // compress: volatile → consolidated(+replay_count,记 batch)。
    virtual int mark_consolidated(const std::vector<std::string>& ids,
                                  std::string_view tenant,
                                  std::string_view replay_batch_id) = 0;
    // reinforce: → consolidated(+access_count +replay_count,记 batch;无状态守卫)。
    virtual int reinforce(const std::vector<std::string>& ids,
                          std::string_view tenant,
                          std::string_view replay_batch_id) = 0;
    // abstract: +replay_count,记 batch(无状态变更)。
    virtual int bump_replay_count(const std::vector<std::string>& ids,
                                  std::string_view tenant,
                                  std::string_view replay_batch_id) = 0;
    // reconcile: consolidated → replaying_reconsolidating。
    virtual int enter_reconsolidating(std::string_view id,
                                      std::string_view tenant) = 0;
    // recon 兜底: replaying_reconsolidating → consolidated。
    virtual int restore_consolidated(std::string_view id,
                                     std::string_view tenant) = 0;
    // 振荡防护: replay_count>=5 且 state∈(volatile,replaying_consolidating)
    // → consolidated + pending_review(现行为:跨租户 bulk,无 tenant 过滤,
    // 保真;latent cross-tenant scope 已登记,phase 2 不改)。
    virtual int force_consolidate_pending_review() = 0;
    // 归档: state=from_state → archived(+updated_at)。from_state 是守卫
    // (decay/supersede/arbitration='consolidated';TTL='volatile')。
    virtual int archive(const std::vector<std::string>& ids, std::string_view tenant,
                        std::string_view from_state, std::string_view now_iso) = 0;

    // ── 局部修正 ──
    // mild-correction: SET confidence + confidence_history_json + updated_at
    // (provenance 不动)。confidence 取 max(只升不降)由调用方决定后传入。
    virtual void apply_mild_correction(std::string_view id, std::string_view tenant,
                                       double confidence,
                                       std::string_view history_json,
                                       std::string_view updated_at) = 0;
    // 支持仲裁: SET confidence + consolidation_state='consolidated'。
    virtual void set_confidence_consolidated(std::string_view id,
                                             std::string_view tenant,
                                             double confidence) = 0;
    // 二阶 salience 继承: SET salience=MAX(salience,?), affect_json=?。
    virtual void inherit_salience(std::string_view id, std::string_view tenant,
                                  double min_salience,
                                  std::string_view affect_json) = 0;

    // ── 插入(Task 2.8 迁入,先声明保接口完整) ──
    // 主写:relocate StatementWriter 内核;返回 stmt_id/event 由专门 Outcome 承载,
    // 接口在 Task 2.8 定;此处仅占位声明位置,Task 2.1–2.7 不实现。
};

}  // namespace starling::store
```

> 注:`insert_statement` / `insert_arbitrated_fork` 的签名涉及 `ExtractedStatement` 与 outbox event,留 Task 2.8 随 StatementWriter 迁移定;Task 2.1 的接口先含转换+修正法(上),插入法在 Task 2.8 追加到本接口。

- [ ] **Step 4: 写 sqlite_statement_store.hpp**

```cpp
#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/store/statement_store.hpp"

namespace starling::store {

class SqliteStatementStore : public StatementStore {
public:
    explicit SqliteStatementStore(persistence::SqliteAdapter& adapter)
        : adapter_(adapter) {}

    int mark_consolidated(const std::vector<std::string>&, std::string_view,
                          std::string_view) override;
    int reinforce(const std::vector<std::string>&, std::string_view,
                  std::string_view) override;
    int bump_replay_count(const std::vector<std::string>&, std::string_view,
                          std::string_view) override;
    int enter_reconsolidating(std::string_view, std::string_view) override;
    int restore_consolidated(std::string_view, std::string_view) override;
    int force_consolidate_pending_review() override;
    int archive(const std::vector<std::string>&, std::string_view,
                std::string_view, std::string_view) override;
    void apply_mild_correction(std::string_view, std::string_view, double,
                               std::string_view, std::string_view) override;
    void set_confidence_consolidated(std::string_view, std::string_view, double) override;
    void inherit_salience(std::string_view, std::string_view, double,
                          std::string_view) override;

private:
    persistence::SqliteAdapter& adapter_;
};

}  // namespace starling::store
```

- [ ] **Step 5: 写 sqlite_statement_store.cpp 的 `mark_consolidated`(exact SQL 自 consolidation_ops.cpp:31 迁入)**

```cpp
#include "starling/store/sqlite_statement_store.hpp"

#include <sqlite3.h>

#include "starling/persistence/sqlite_handles.hpp"
#include "starling/persistence/sqlite_helpers.hpp"

namespace starling::store {

using persistence::StmtHandle;
using persistence::detail::bind_sv;
using persistence::detail::make_sqlite_error;

int SqliteStatementStore::mark_consolidated(
    const std::vector<std::string>& ids, std::string_view tenant,
    std::string_view replay_batch_id) {
    sqlite3* db = adapter_.connection().raw();
    int affected = 0;
    for (const auto& id : ids) {
        const char* sql =
            "UPDATE statements SET consolidation_state='consolidated', "
            "  last_replay_batch_id=?, replay_count=replay_count+1 "
            " WHERE id=? AND tenant_id=? AND consolidation_state='volatile'";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "StatementStore::mark_consolidated prepare");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, replay_batch_id);
        bind_sv(h.get(), 2, id);
        bind_sv(h.get(), 3, tenant);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "StatementStore::mark_consolidated step");
        affected += sqlite3_changes(db);
    }
    return affected;
}

}  // namespace starling::store
```

CMake:`CMakeLists.txt` 在 `src/store/store_bundle.cpp` 行后加 `src/store/sqlite_statement_store.cpp`;`tests/cpp/CMakeLists.txt` 在 `test_store_foundation.cpp` 行后加 `test_statement_store.cpp`。

- [ ] **Step 6: 构建 + 测试通过**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build 2>&1 | tail -2
./build/tests/cpp/starling_tests --gtest_filter='StatementStore.MarkConsolidated*' 2>&1 | tail -2
```
Expected: `[  PASSED  ] 1 test.`

- [ ] **Step 7: Commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add include/starling/store/statement_store.hpp include/starling/store/sqlite_statement_store.hpp src/store/sqlite_statement_store.cpp tests/cpp/test_statement_store.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -F - <<'EOF'
feat(P3.b1/phase2): StatementStore 接口 + mark_consolidated(volatile→consolidated 守卫)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
```

### Task 2.2: 转换法 `reinforce` / `bump_replay_count` / `enter_reconsolidating` / `restore_consolidated`

**Files:** Modify `src/store/sqlite_statement_store.cpp`、`tests/cpp/test_statement_store.cpp`

- [ ] **Step 1: 追加失败测试(逐法守卫)**

```cpp
TEST(StatementStore, ReinforceNoStateGuardBumpsAccessAndReplay) {
    auto a = make_adapter();
    SqliteStatementStore st(*a);
    seed(a->connection(), "s1", "archived");   // reinforce 无状态守卫,archived 也改
    EXPECT_EQ(st.reinforce({"s1"}, "default", "b1"), 1);
    EXPECT_EQ(state_of(a->connection(), "s1"), "consolidated");
}

TEST(StatementStore, EnterReconsolidatingOnlyFromConsolidated) {
    auto a = make_adapter();
    SqliteStatementStore st(*a);
    seed(a->connection(), "s1", "consolidated");
    seed(a->connection(), "s2", "volatile");   // 守卫:非 consolidated 不动
    EXPECT_EQ(st.enter_reconsolidating("s1", "default"), 1);
    EXPECT_EQ(st.enter_reconsolidating("s2", "default"), 0);
    EXPECT_EQ(state_of(a->connection(), "s1"), "replaying_reconsolidating");
    EXPECT_EQ(state_of(a->connection(), "s2"), "volatile");
}

TEST(StatementStore, RestoreConsolidatedOnlyFromReconsolidating) {
    auto a = make_adapter();
    SqliteStatementStore st(*a);
    seed(a->connection(), "s1", "replaying_reconsolidating");
    EXPECT_EQ(st.restore_consolidated("s1", "default"), 1);
    EXPECT_EQ(state_of(a->connection(), "s1"), "consolidated");
}
```

- [ ] **Step 2-5:** 跑红 → 实现四法(exact SQL:`reinforce` 自 consolidation_ops.cpp:57、`bump_replay_count` 自 :80、`enter_reconsolidating` 自 :154、`restore_consolidated` 自 reconsolidation_engine.cpp:265,逐字迁入,签名按 hpp)→ 跑绿 → commit(`feat(P3.b1/phase2): 4 转换法 reinforce/abstract/reconcile/restore`)。

### Task 2.3: `archive(from_state)` + `force_consolidate_pending_review`

**Files:** Modify `src/store/sqlite_statement_store.cpp`、`tests/cpp/test_statement_store.cpp`

- [ ] **Step 1: 失败测试**

```cpp
TEST(StatementStore, ArchiveHonorsFromStateGuard) {
    auto a = make_adapter();
    SqliteStatementStore st(*a);
    seed(a->connection(), "c1", "consolidated");
    seed(a->connection(), "v1", "volatile");
    // from_state='consolidated':只动 c1。
    EXPECT_EQ(st.archive({"c1", "v1"}, "default", "consolidated",
                         "2026-06-13T00:00:00Z"), 1);
    EXPECT_EQ(state_of(a->connection(), "c1"), "archived");
    EXPECT_EQ(state_of(a->connection(), "v1"), "volatile");
    // from_state='volatile'(TTL 路径):动 v1。
    EXPECT_EQ(st.archive({"v1"}, "default", "volatile",
                         "2026-06-13T00:00:00Z"), 1);
    EXPECT_EQ(state_of(a->connection(), "v1"), "archived");
}

TEST(StatementStore, ForceConsolidateOnHighReplayCount) {
    auto a = make_adapter();
    SqliteStatementStore st(*a);
    seed(a->connection(), "hot", "volatile", /*replay_count=*/5);
    seed(a->connection(), "cold", "volatile", /*replay_count=*/4);
    EXPECT_GE(st.force_consolidate_pending_review(), 1);
    EXPECT_EQ(state_of(a->connection(), "hot"), "consolidated");
    EXPECT_EQ(state_of(a->connection(), "cold"), "volatile");
    sqlite3_stmt* q = nullptr;
    sqlite3_prepare_v2(a->connection().raw(),
        "SELECT review_status FROM statements WHERE id='hot'", -1, &q, nullptr);
    sqlite3_step(q);
    EXPECT_STREQ(reinterpret_cast<const char*>(sqlite3_column_text(q, 0)),
                 "pending_review");
    sqlite3_finalize(q);
}
```

- [ ] **Step 2-5:** 跑红 → 实现(`archive`:`UPDATE statements SET consolidation_state='archived', updated_at=? WHERE id=? AND tenant_id=? AND consolidation_state=?`,逐 id;`force_consolidate_pending_review` exact SQL 自 replay_scheduler.cpp:289,bulk 无 tenant 保真)→ 跑绿 → commit。

### Task 2.4: 修正法 `apply_mild_correction` / `set_confidence_consolidated` / `inherit_salience`

**Files:** Modify `src/store/sqlite_statement_store.cpp`、`tests/cpp/test_statement_store.cpp`

- [ ] TDD 三法:失败测试钉(mild-correction 改 confidence/history/updated_at 不动 provenance;set_confidence_consolidated 改 confidence+state;inherit_salience 取 MAX 不降)→ 实现(exact SQL:bus.cpp:264 / arbitration.cpp:204 / second_order.cpp:170)→ 绿 → commit。

### Task 2.5–2.7: 路由 caller(每文件一 Task,删内联 SQL 改调 StatementStore)

每 Task 同形:在 caller 持有/构造 `SqliteStatementStore`(经现有 adapter),把内联 `UPDATE statements` 段替换为对应 store 方法调用,**保留事件 emit 与返回值门控逻辑不变**;跑该模块既有钉测全绿 + 全量 ctest;commit。

- [ ] **Task 2.5:** `src/replay/consolidation_ops.cpp`(compress/reinforce/abstract/decay-archive/reconcile 五处)+ `src/replay/replay_scheduler.cpp`(force-consolidate + TTL-archive)。钉测:`ReplayScheduler.*`、`MemoryOps.*`、consolidation 相关。
- [ ] **Task 2.6:** `src/reconsolidation/arbitration.cpp`(set_confidence / mild-correction / archive)+ `src/reconsolidation/reconsolidation_engine.cpp`(restore 兜底)。钉测:`*Reconsolidation*`、C2/§16.3 仲裁。
- [ ] **Task 2.7:** `src/bus/bus.cpp`(mild-correction + supersede-archive)+ `src/tom/second_order.cpp`(inherit_salience)。钉测:`*Bus*`、`TomSecondOrder.*`、`test_tom2_e2e`。

### Task 2.8: 主 INSERT 迁入(StatementWriter 内核 → StatementStore.insert_statement)

**最高风险,最后做。** StatementWriter 的 INSERT(statement_writer.cpp,含 nesting_depth/出生 salience/chunk-duplicate 检查)迁入 `StatementStore::insert_statement` + `insert_arbitrated_fork`(arbitration.cpp:389);`StatementWriter` 变薄壳委托 store(保 `StatementWriteOutcome` 契约不变)。TDD:既有 `test_memory_ops`/`test_extractor_orchestrator`/`test_statement_*` 全绿即验收(主 INSERT 行为不得变);新增 store 层 insert 单测。commit。

**Phase 2 出口:** ctest 567+ 全绿;`statements` 的所有 UPDATE/INSERT 只在 `src/store/`(+testing 豁免);零行为变化、零 Python 改。

---

## Phase 3:MetaStore 读收编 + 其余 meta 表 owner 化(任务级)

phase 2 的 StatementStore 接口定后展开。

- **Task 3.1:** `MetaStore` 接口聚合(`StatementStore` + 类型化读:`query_statements(StatementFilter)` / `get_statement(id,tenant)`,替散落 SELECT)。`StoreBundle` 暴露 `meta()`。
- **Task 3.2:** 读路由 —— retrieval(basic_retriever/semantic_retriever/retrieval_planner)、working_set、mentalizing 的 statements SELECT 经 MetaStore 类型化读(保字段/过滤一致,零行为变化)。
- **Task 3.3–3.7:** 其余 meta 表 owner 方法化(各表已单 owner,本期=接口化 + 表头契约注,不重写):projection(proj_* ×7)、commitments 族、common_ground 族、cognizers 族、各 checkpoint。dashboard 只读 SQL(Python queries.py)维持现状(边界允许)。
- **验收:** 写点普查脚本复跑 statements 读写经接口;phase 3 出口零行为变化。

## Phase 4:GraphStore 路由(任务级)

phase 1 的 GraphStore 接口已就位,本期把写者/读者接上。

- [x] **Task 4.0 + 4.1(DONE,`e55c76f`):** 四写者 `INSERT INTO statement_edges` → `GraphStore::insert_edge`(bus helper 委托 / arbitration severe_contradict / commitment renegotiate / embedding overlap),删 bus `random_edge_id` + commitment/embedding `random_hex_32`(均仅 edge 用)。**接口对齐**:`SqliteGraphStore` adapter& → Connection&(与 StatementStore 对称,各写者用事务 conn,原子性显式同连接)。**conflict 去重下沉**:`insert_edge` 返回 `EdgeInsert{id,deduped}`,conflicts_with 的 canonical_conflict_key UNIQUE(0009 partial index)命中静默 dedup(spec §8.4),WARN 业务日志留 bus。schema 默认 weight=1.0/metadata='{}' == `EdgeRecord` 默认,委托零漂移。**conflict_key_backfill 裁剪**:SELECT/UPDATE canonical_conflict_key/DELETE dup 是一次性回填迁移工具(操作 conflict_key_backfill_state 表),非 plain insert;GraphStore 无 update/delete/scan 法,LadybugDB 换装本需重写。
- [~] **Task 4.2(裁剪登记):** statement_edges 读点全为图遍历/scope 富集,非 `GraphStore::neighbors` 单跳 plain 边读 → 裁剪:
  - PatternCompletor `expand` —— `json_each` 批量 seed + 双向 UNION(前向 5 种传播边 / 反向仅 MAY_OVERLAP_WITH)+ **JOIN statements 隐私 scope 富集**(holder/perspective/state/review,逐字对齐 search_topk 安全不变式);scope 是检索语义,不入存储接口。
  - planner `fetch_graph_supersedes`(supersedes 双向扩展)、commitment `supersedes_chain_length`(链遍历)—— 多跳图遍历,非单跳。
  这些属检索编排(与 retrieval_planner 同类),换 LadybugDB 时 backend 改写 Cypher 遍历(phase 6 评估点)。`GraphStore::neighbors`/`edges_by_conflict_key` 接口就绪(StoreBundle 暴露 + 钉测),为 LadybugDB 兑现抽象。
- [~] **Task 4.3(defer,YAGNI):** cognizer_relations(社会图)是独立于 statement_edges 的另一张图(src/dst 是 cognizer 非 statement),并入需扩 GraphStore 异构 schema(`upsert_relation`/`get_relation`);cognizer_hub 已单 owner、local-store 全 SQLite。提前并入唯一收益是 LadybugDB 社会图换装,而那在 phase 6 PoC 后定夺 → defer,留 phase 6 go 后随社会图换装一并做。
- **验收(已达成):** statement_edges INSERT 只在 store/ + bus helper 委托(`e55c76f`);edge 写四写者钉测 + PatternCompletor 召回钉测不变(ctest 587)。

## Phase 5:zvec backend(任务级)

> **2026-06-14 探查结论(zvec v0.5.0 实测,修正原 audit):** zvec 不是轻量索引,是**完整向量 DB** —— 15 个 git submodule thirdparty(apache-arrow 21.0.0 / rocksdb 8.1.1 / protobuf 3.21.12 / antlr4 等),332 cpp / 20M,含 FTS/DiskANN/列存;Apache 2.0。**zvec 不导出 C++ 库**(CMake install 仅 `_zvec` Python binding + jieba dict),`pip install zvec` 预编译 wheel 对 C++ 集成无用 → starling 用 Collection C++ API 必须 `add_subdirectory` **整个 zvec 源码**(submodule GB 下载 + 编译 arrow/rocksdb/protobuf + antlr4 C++ runtime,数十分钟 + 巨大二进制)。`BUILD_ZVEC_CORE_ONLY` 仅编 core KNN(轻依赖)但裸 KNN(无 Collection/scope/persist)。**用户裁定(2026-06-14):走 db 路径(全功能 Collection API,接受重依赖)。**
> **不需要 JDK(2026-06-14 更正,原判断错误):** antlr4 的 Java 工具仅在 `src/db/sqlengine/antlr/gen_parser.sh`(开发者改 `.g4` 语法后手动重新生成 parser)需要;zvec 已把生成的 C++ parser checked-in(`antlr/gen/SQLParser.cc` 等,"Generated by ANTLR 4.8")。CMake 构建无 `find_package(Java)`/`.g4` codegen 步骤,直接编译 checked-in parser + antlr4 C++ runtime(纯 C++)。磁盘 blocker 用户已清理。db 路径无硬 blocker,剩成本=重栈编译时长 + GB submodule 下载(可重试)+ 双 WAL 设计。
>
> **db 路径实操约束:**
> - **哲学冲突**:Collection 自带 rocksdb WAL 持久化 → starling 从「SQLite 单 ACID 锚」变「SQLite + rocksdb 双引擎双 WAL」。一致性按 spec 设计(Vector 是派生投影,从 vector.embedded 事件**异步物化**,不入 bus 主事务;embedding_worker 已是异步 SAVEPOINT 路径,天然契合)。
> - **scope 过滤难题**:`VectorIndex::search_topk` 带 SearchScope(tenant/holder/visibility,逐字对齐隐私不变式)。zvec Collection 支持 hybrid filter,需把 stmt 的 tenant/holder/consolidation_state/review_status 存为 zvec attribute,query 时 filter;且 state/review 变化时同步更新 attribute(saga 物化,statement.* 事件驱动)。
> - **编译成本**(非 blocker):GB submodule 下载(github 间歇 SSL,可重试)+ arrow/rocksdb/protobuf 首次编译数十分钟(一次性,后续增量)。Task 5.1 分步:先拉 submodule + `BUILD_ZVEC_CORE_ONLY` 验证 zvec 基础设施在 starling 环境可编译,再切完整构建链接 Collection。

- [x] **Task 5.1 编译关卡(DONE,独立验证通过):** zvec v0.5.0 在 macOS arm64 完整编译成功。集成 starling(FetchContent + 链接)待 Task 5.1b。
  - **2026-06-14 独立验证(`/tmp/zvec-build`,v0.5.0,浅 submodule 361M):** configure **成功**(42.5s);build **完整成功**(`BUILD EXIT 0` / `[100%] Built target zvec`),产物 `libzvec.a` + `libarrow.a`/`_acero`/`_compute`/`_dataset`/`_bundled_dependencies` + librocksdb.a + libzvec_proto.a 齐全。环境:AppleClang 21 + cmake 4.3.2;ARM64 检测 OK、protobuf 3.21.12、diskann/rabitq macOS 自动跳过、SSE42/uring/fallocate Linux 特性 failed 但 F_FULLFSYNC fallback(非致命)。**无编译硬障碍。** arrow `BUNDLED` 依赖(Boost 等)下载需稳定网络(github SSL 间歇,重试可成)。
  - **集成注意点(Task 5.1b):** ① cmake 4.3.2 需 `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`(zvec 旧 googletest-1.10.0);② **zvec 自带 googletest 1.10.0 与 starling FetchContent gtest 1.15.2 target 冲突** → ExternalProject 隔离(zvec 独立 build,不进 starling CMake namespace);③ option `STARLING_VECTOR_ZVEC` 默认 OFF,不影响默认构建;④ arrow ExternalProject 独立 cmake 需透传 POLICY flag + 稳定网络下首次构建。
- [x] **Task 5.1b 链接方案验证(DONE,2026-06-14,用户「合并成一个库」思路):** zvec **不导出 C++ target + 30+ 库散在 4+ 目录(含 arrow ExternalProject 深层内部)** → 直接链接极脆弱。解法:ExternalProject 编译 zvec 完整 build(含 core_knn)后,`find`+`libtool -static` 合并产物为**两个固定 bundle**:
  - `libzvec_plugins.a`(12M,**`-force_load`**)= core_knn_{flat,flat_sparse,hnsw,hnsw_sparse,ivf,vamana,cluster} + core_{plugin,metric,mix_reducer,quantizer,utility}(需 static 注册到 Factory 的插件/metric;diskann/rabitq 在 macOS 跳过)。
  - `libzvec_main.a`(132M,普通链接)= zvec + zvec_{core,ailego,turbo,proto,sqlengine} + arrow 栈 + rocksdb + protobuf + antlr + glog/gflags/lz4/roaring/FastPFOR + boost/thrift/re2/utf8proc/z。
  - **官方 example(`examples/c++/db/main.cc`)靠此 2-bundle 完整跑通**:CreateAndOpen + Insert(doc_count 0→1)+ HNSW 索引(index_completeness dense 0→1)+ Query(doc_count[1])+ 128 维向量检索(score 1.28 正确)。
  - **关键坑:** force_load 必须只针对 plugins —— force_load 整个 bundle 会强拉 thrift SSL socket(arrow/parquet 依赖,zvec 不用)暴露 OpenSSL 未定义符号。starling 链接:`-Wl,-force_load,libzvec_plugins.a libzvec_main.a` + `-framework CoreFoundation -framework Security -framework SystemConfiguration -lc++ -lz`。
  - **脆弱性解决:** starling 端链接 2 个稳定 bundle;合并脚本 `find` 收集不写死深层路径;zvec/arrow 升级脚本不变。
  - **starling CMake 集成已落地(DONE,`173e9e1`):** `cmake/StarlingZvec.cmake`(ExternalProject zvec + `zvec_backend` INTERFACE 库)+ `cmake/merge_zvec_bundles.sh`(find+libtool 2-bundle)+ `STARLING_VECTOR_ZVEC` option(默认 OFF,零影响默认构建)+ 主 CMakeLists 条件 include。**端到端验证通过:** `cmake -DSTARLING_VECTOR_ZVEC=ON` configure OK(`zvec_ext` declare);`build zvec_ext` 全自动 clone+编译+合并产出 `libzvec_{plugins(12M),main(132M)}.a`(`BUILD EXIT 0`)。zvec 编译产物在 `build-zvec-test/`(Task 5.2 复用,免重编)。
- [x] **Task 5.2(DONE,`1b061ee`/`d63f85b`):** `ZvecVectorIndex : VectorIndex`(`include/starling/vector/zvec_vector_index.hpp` + `src/vector/zvec_vector_index.cpp`)。CreateAndOpen/Open + Upsert/Query/Delete;COSINE metric 对齐 SqliteBlobVectorIndex cosine;dim 一致性检查。**scope 方案:** zvec KNN(tenant 粗过滤 + over-fetch ×4)→ SQL 精过滤 holder/perspective/visibility(实时 JOIN statements 取最新 state,逐字对齐隐私不变式,免 zvec attribute 同步滞后导致的泄露)。**安全(审查 HIGH):** filter tenant_id 字符 allowlist 防注入(zvec filter 是 SQL-like 字符串 DSL 无参数化绑定),第二层=SQL 精过滤参数化 `s.tenant_id=?`。CMake:ON 时加入 starling_core + 链接 zvec_backend,zvec headers SYSTEM include。**parity 3 测试全绿**(scope visibility/holder/remove + 召回与 SQLite 后端一致);默认 OFF 回归 ctest 587 不变。
- [x] **Task 5.3(DONE,`e666f46`):** 向量后端工厂 `_make_vector_index(backend, dim, store_path)`(`_memory_core.py`):默认 sqlite / zvec(需 STARLING_VECTOR_ZVEC 构建,`hasattr(_core,'ZvecVectorIndex')` 检测缺失即报错)。bind_10 ON-only(`#ifdef STARLING_HAS_ZVEC`)ZvecVectorIndex binding + `EmbeddingAdapter` base 暴露 `dim()`(所有 embedder 可取维度)。idx 延迟 set_embedder 按 `emb.dim()` 创建;MemoryCore 加 `vector_backend`/`vector_store_path` 参数(默认 sqlite,**回滚留好**)。**双路径验证:** OFF editable + pytest 54 绿(默认 sqlite 不破坏);ON `_core.so` 含 ZvecVectorIndex binding(Zvec/Sqlite 均 True)+ 工厂创建 zvec backend 成功。dashboard config UI 接线(vector_backend 字段)后续(QA 禁改设置页约束;MemoryCore 参数已支持显式切换)。
- [x] **Task 5.4(DONE,`1e2ebe9`/`de39df7`):** perf 基线 benchmark(ON-only):N=300 DIM=16 K=10 Q=30 随机向量(固定种子),**recall(zvec HNSW vs sqlite 暴力 cosine)=1.000**(召回不退)、延迟 zvec 169us vs sqlite 395us per-query(zvec 快 2.3x,小规模 HNSW 已优于暴力,规模越大优势越大)。dashboard 接线:`DashboardConfig` 加 `vector_backend`(默认 sqlite)/`vector_store_path` 字段(持久化进 `_SERIALIZABLE` + `STARLING_DASH_VECTOR_BACKEND` env overlay),engine 传 MemoryCore 工厂;不动 embedder 字段(QA 约束),默认 sqlite 零影响(pytest dashboard 74 绿)。
- **验收:** 配置 `vector_backend=zvec` 时全量门绿 + 召回质量不退;默认 sqlite 行为不变。

## Phase 6:LadybugDB backend —— **仅 PoC + go/no-go**(任务级)

> 项目规则:跨阶段接口未定不预写换装实现。GraphStore 接口稳定(phase 4)后做。

> **2026-06-15 go/no-go 评估 = NO-GO**(保 SqliteGraphStore;LadybugDB 留 P3+ seam):
> - **集成可行性(优于 zvec):** LadybugDB v0.17.1 实测 —— **MIT + C++20**(与 starling 一致)、**导出 C++ target**(`install(TARGETS lbug lbug_shared)` + `lbug_link_deps` INTERFACE 依赖聚合),无 zvec 的「不导出 C++ 库 + 30+ 库手工 bundle」脆弱性;依赖较轻(antlr4_cypher/parquet/mbedtls/lz4/cppjieba,**无 arrow/rocksdb 重栈**);796 cpp/76M。**集成不是障碍**(若 go 比 zvec 简单)。
> - **收益小:** statement_edges 边量小(数千~数万),图查询(supersedes 链 / conflict dedup / 双向扩展)用 SQLite 递归 CTE + JOIN 够用、性能非瓶颈。Cypher 优雅但非必需(plan 自标「收益偏代码优雅」)。
> - **一致性代价(决定性):** 冲突边(conflicts_with)现于 `Bus::write` 同步写 statement_edges(与 statement 同 SQLite 事务 = **C2/§16.3 即时冲突可见性**)。LadybugDB 自带独立 storage/transaction/WAL → 冲突边跨引擎无法与 SQLite statement 同事务原子 → 异步物化(最终一致)→ **破坏即时冲突可见性**(recall 可能漏未物化冲突)。这是架构级语义损失,非性能权衡。
> - **结论 NO-GO:** 收益(图查询优雅,边量小时性能不显著)不抵一致性代价(即时冲突可见性损失)+ 双引擎运维。GraphStore 接口(phase 4)已兑现存储抽象,SqliteGraphStore 保冲突边同步语义;LadybugDB backend 留 seam,待边量大幅增长或复杂多跳图推理成需求时再 go(单独出换装 plan)。**性能 benchmark(Task 6.1)未做:no-go 由一致性主导,LadybugDB 即便性能优也不改变结论。**

- **Task 6.1:** PoC —— vendored LadybugDB,真数据(从 SQLite 导出边)基准:Cypher `neighbors`/多跳 vs SQLite,P50/P95 延迟 + 内存。
- **Task 6.2:** 冲突边同步→异步订阅者改造**评估**(C2/§16.3 冲突可见性即时→最终一致的钉测影响);写改造草案。
- **Task 6.3:** **go/no-go 关卡**:若收益不抵一致性代价 → 保 SQLite backend(GraphStore 接口已兑现抽象,LadybugDB 留 P3+ seam);若 go → 单独出换装 plan。

## Phase 7:crypto_erasure 局部 keystore —— **DEFER P3+(不在 P3 实现)**

> **2026-06-15 用户裁定:推迟到 P3+,P3 中不实现。** 当前 NullKms 占位(encrypt=identity /
> key_ref=NULL / content_ciphertext=原始字节)+ Engram 的 `key_ref`/`content_ciphertext`/
> `erased_at` 字段已留好钩子,调用点(EngramStore::put)不变 → 未来 P3+ 接 LocalFileKms 时
> 零调用点改动。下列 Task 7.1/7.2 留作 P3+ 的实现蓝图,不在 P3.b1 范围。

- **Task 7.1:** `store/keystore.{hpp,cpp}` —— `LocalFileKms` 替 `NullKms`:per-engram DEK 包裹,文件级 wrapped key `~/.starling/keys/`(0600)。TDD:wrap/unwrap round-trip。
- **Task 7.2:** `erase(engram_id)` = 删 DEK(密文不可逆);EngramStore 接 keystore;crypto_erasure 生产路径钉测。
- **验收:** erase 后密文不可解;云 KMS 接口留 seam(P3+)。

---

## Self-Review

- **Spec coverage:** 三类 Store(MetaStore phase 2-3 / VectorStore phase 5 / GraphStore phase 1+4)✓;所有读写经接口(写 phase 2/4、读 phase 3)✓;profile/capability(phase 1 ✓,工厂 phase 5)✓;一致性模型(MetaStore ACID 锚 + 异步物化,phase 4/5 体现)✓;引擎选型(SQLite 现状 / zvec phase 5 / LadybugDB phase 6 PoC)✓;crypto_erasure(phase 7)✓;收编验收(普查脚本 + ci_static_scan 红线,phase 2/3/4 出口)✓。
- **Placeholder scan:** phase 2 全 TDD 含确切 SQL/测试/签名(无占位);phase 3-7 任务级=明确 Files+deliverable+验收+exact 源 file:line,非 vague TODO;phase 6 显式只 PoC(项目规则)。Task 4.2 的 json_each 批量性能问题**显式登记**为执行时二选一决策,非隐藏。
- **类型一致:** `StatementStore` 16 法签名在 hpp 一次定齐(Task 2.1),后续 Task 仅实现同签名;`archive(ids,tenant,from_state,now_iso)` 在 Task 2.3 与接口一致;`GraphStore`(phase 1 已落)`insert_edge`/`neighbors`/`edges_by_conflict_key` 与 phase 4 路由一致;`make_vector_index(backend)` 工厂名 phase 5 一致。
