# 世界/场景管理 W1+W2 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal：** 交付多世界注册表与切换（W1）和快照（W2）。范围到 W2 为止，不做回滚、场景清单和分叉。

**Architecture：** 一个世界由一个 SQLite 文件和一个租户 id 组成。快照用 `VACUUM INTO` 从**只读连接**写出紧凑文件。注册表的读写、快照、保留策略和世界统计都放在 C++ 的 `starling::governance::WorldStore`。Python 层只做三件事：把 C++ 函数绑定出来、在引擎生命周期内切换世界、注册 HTTP 路由。前端新增一个 `/worlds` 页面。

**Tech Stack：** C++20、SQLite 3.46+（本机 3.51/3.54）、nlohmann_json、GoogleTest 1.15.2、pybind11 3、FastAPI、SvelteKit（Svelte 5 runes）、vitest。

**Spec：** `docs/superpowers/specs/2026-10-25-world-scene-management-design.md`（§0.1 裁定表、§2 布局、§3 注册表、§4 快照、§8 切换、§9 Dashboard、§10 落点、§12 风险）

## Global Constraints

- 核心逻辑放 C++（`src/` 和 `include/starling/`），Python 只做适配。判断标准是：换一种绑定语言时，这段逻辑是否需要重写。注册表、快照、保留策略和统计放 C++。切换时重建引擎放 Python。
- 只用显式路径 `git add`，禁止 `git add .` 和 `git add -A`。不用 `--no-verify` 和 `--amend`。
- 提交信息以 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 结尾。
- PR 改动行上的 C++ 参数名和变量名至少 3 个字符，否则 CI clang-tidy 会失败。`.clang-tidy` 设置了 `WarningsAsErrors: '*'`，只检查改动行。
- 新 C++ 代码用 `persistence::Stmt` 包装 SQL，不手写 `sqlite3_prepare_v2` 样板（见 `include/starling/persistence/stmt.hpp`）。
- 世界路径只能来自服务端注册表，任何 API 都不接受客户端传入文件路径（spec §3.1、§14.2）。
- 世界名（同时也是目录名）必须匹配 `^[a-z0-9][a-z0-9_-]{0,31}$`。
- 默认世界 `default` 的库保持在原地（`~/.starling/dashboard.db`），只有新世界放在 `worlds/<name>/world.db`（§0.1）。
- 快照默认保留 5 份，`snapshot_retention < 2` 时拒绝。清理优先删除 auto 快照，并且至少保留 1 份 auto（§4.4）。
- `vector_backend=zvec` 时拒绝快照（`snapshot_unsupported_backend`，§12）。
- 拍快照前检查磁盘空间：可用空间不足当前库活数据量的 3 倍时拒绝，并返回 HTTP 507（§4.5）。
- 先写 `<id>.db.partial`，再改名为 `<id>.db`。失败时删除 partial 文件（§12）。
- W2 只做手动快照。场景边界自动快照属于 W4，不在本计划内。不过 `kind` 字段和保留策略都要支持 `auto`，以免 W4 改动数据格式。

## 本计划已实测的 SQLite 事实（不必再验证）

| 事实 | 后果 |
|---|---|
| `VACUUM INTO ?` 支持绑定参数，路径含空格和单引号也能用 | 路径一律走 `Stmt::bind` |
| 只读连接（`mode=ro`）的 `VACUUM INTO` 成功，WAL 库和已关闭的库都可以 | 快照用只读连接，绝不碰引擎的写连接 |
| 有未提交的写事务时 `VACUUM INTO` 成功，快照不包含未提交的行 | 拍快照时不需要停写 |
| 在事务内执行 `VACUUM INTO` 报 `cannot VACUUM from within a transaction` | 快照必须开一条独立的新连接 |
| 目标文件已存在时报 `output file already exists` | partial 文件名要唯一，写前先删残留 |
| 产出文件的 `journal_mode=delete`，`integrity_check=ok` | 快照可以直接当世界库打开 |
| 生产库 2.4GB、97.7% 是 freelist，`VACUUM INTO` 产出 57MB，耗时 0.16 秒 | 磁盘守卫用活数据量 `(page_count - freelist_count) * page_size` 计算，不用文件大小 |
| 生产库里没有 `tenant_id <> 'default'` 的行（2026-10-25 扫描） | 默认世界注册为 `tenant=default` 是安全的 |
| `DashboardEngine.close()` 不释放 C++ 连接，`del` 加 `gc.collect()` 后连接数从 4 降到 0，同一文件可以立即重开 | 切换世界时必须丢弃引用并 `gc.collect()`，然后断言旧 Runtime 的弱引用已失效 |

## File Structure

| 文件 | 职责 | 任务 |
|---|---|---|
| `include/starling/governance/world_store.hpp` | 结构体（`WorldEntry`、`SnapshotEntry`、`Registry`、`WorldStats`）、异常 `WorldStoreError`、函数声明 | T1 |
| `src/governance/world_store.cpp` | 注册表 JSON 读写（原子写）、名称校验、世界增删和激活、快照、保留策略、统计 | T1、T2 |
| `tests/cpp/test_world_store.cpp` | 上述全部的 GoogleTest | T1、T2 |
| `CMakeLists.txt` | 把 `src/governance/world_store.cpp` 加进 `starling_core` | T1 |
| `tests/cpp/CMakeLists.txt` | 把 `test_world_store.cpp` 加进 `starling_tests` | T1 |
| `bindings/python/bind_15_world.cpp` | 把 `WorldStore` 函数绑成 `_core.world_*`，C++ 结构体转换成 dict | T3 |
| `bindings/python/bindings.hpp`、`module.cpp`、`bindings/python/CMakeLists.txt` | 注册 `bind_15_world` | T3 |
| `python/starling/dashboard/world_manager.py` | 世界切换的引擎生命周期，以及注册表路径解析和启动引导 | T4 |
| `python/starling/dashboard/routes/worlds.py` | `/api/worlds*` 路由 | T5 |
| `python/starling/dashboard/app.py` | 启动时引导注册表，挂载 worlds 路由 | T4、T5 |
| `python/starling/dashboard/engine.py` | 给 `DashboardEngine` 加 `quiesce()`，在切换前停 tick 和摄入 | T4 |
| `tests/python/test_dashboard_worlds.py` | 绑定、切换、路由的 pytest | T3、T4、T5 |
| `dashboard/web/src/lib/worlds.ts` + `.test.ts` | 前端类型与 API 调用 | T6 |
| `dashboard/web/src/lib/nav.ts`、`nav.test.ts` | 新增「世界 · 会话」导航组 | T6 |
| `dashboard/web/src/lib/components/NavIcon.svelte` | 新增 `globe` 图标 | T6 |
| `dashboard/web/src/lib/ws.ts` | 事件词表加入 `world_switched`、`snapshot_created` | T6 |
| `dashboard/web/src/routes/worlds/+page.svelte` + `page.test.ts` | 世界列表、切换、新建、删除、快照 | T7 |

## 任务依赖与并行

```
T1 ──> T2 ──> T3 ──> T4 ──> T5        (后端链，worktree feat/world-core)
T6 ──> T7                             (前端链，worktree feat/world-web，与后端并行)
```

前端链只依赖本计划写死的 HTTP 契约（下节），不依赖后端代码，所以可以和后端链同时进行。

## HTTP 契约（前后端共同遵守，T5 和 T6/T7 都以此为准）

所有路由都挂在 `/api` 下，并且都要求 bearer token（沿用 `make_require_token`）。

```
GET    /api/worlds
  200 {"active": "default", "default": "default", "snapshot_retention": 5,
       "worlds": [WorldRow, ...]}            # 按 name 升序

POST   /api/worlds                 body {"name": str, "label": str = ""}
  200 WorldRow
  400 {"detail": "invalid_world_name"}
  409 {"detail": "world_exists"}

POST   /api/worlds/{name}/activate
  200 {"active": name}
  404 {"detail": "world_not_found"}
  409 {"detail": "ingest_busy"}              # 摄入线程 5 秒内没停下
  500 {"detail": "world_open_failed"}         # 新世界打不开，已回到旧世界

DELETE /api/worlds/{name}?confirm=<name>
  200 {"deleted": name}
  400 {"detail": "confirm_mismatch"}
  404 {"detail": "world_not_found"}
  409 {"detail": "world_protected"}          # default 或当前活动世界

GET    /api/worlds/{name}/snapshots
  200 {"snapshots": [SnapshotRow, ...]}      # 按 created_at 降序
  404 {"detail": "world_not_found"}

POST   /api/worlds/{name}/snapshots body {"note": str = ""}
  200 SnapshotRow
  404 {"detail": "world_not_found"}
  409 {"detail": "snapshot_unsupported_backend"}
  507 {"detail": "insufficient_disk"}

DELETE /api/worlds/{name}/snapshots/{snapshot_id}
  200 {"deleted": snapshot_id}
  404 {"detail": "snapshot_not_found"}

WorldRow    = {"name", "label", "tenant", "created_at", "active": bool,
               "db_bytes": int, "live_bytes": int, "statements": int,
               "engrams": int, "snapshots": int, "snapshot_bytes": int}
SnapshotRow = {"id", "kind": "auto"|"manual", "reason", "note",
               "created_at", "world_time", "size_bytes": int}
```

WebSocket 广播（沿用 `ws_manager.broadcast({"type": ..., "payload": ...})`）：
- 切换成功：`{"type": "world_switched", "payload": {"active": name}}`
- 快照成功：`{"type": "snapshot_created", "payload": {"world": name, "id": id}}`

---

### Task 1：WorldStore 注册表（C++）

**Files:**
- Create: `include/starling/governance/world_store.hpp`
- Create: `src/governance/world_store.cpp`
- Create: `tests/cpp/test_world_store.cpp`
- Modify: `CMakeLists.txt`（`src/governance/metrics_gatherer.cpp` 之后加一行）
- Modify: `tests/cpp/CMakeLists.txt`（`test_tick_load_shedding.cpp` 之后加一行）

**Interfaces:**
- Produces（T2 和 T3 都会用到，名称和签名不能改）：

```cpp
namespace starling::governance {

class WorldStoreError : public std::runtime_error {
public:
    WorldStoreError(std::string code, const std::string& detail);
    [[nodiscard]] const std::string& code() const noexcept;   // 见下表
private:
    std::string code_;
};
// code 取值：invalid_world_name | world_exists | world_not_found | world_protected
//           | registry_corrupt | invalid_retention | snapshot_not_found
//           | insufficient_disk | snapshot_failed | world_tenant_mismatch

struct SnapshotEntry {
    std::string id;           // 20261025T011200Z-a1b2
    std::string path;         // 绝对路径
    std::string kind;         // "auto" | "manual"
    std::string reason;       // manual 时 "manual"
    std::string note;
    std::string created_at;   // ISO-8601 UTC 秒精度
    std::string world_time;   // 快照覆盖到的世界时刻水位，可为空
    std::int64_t size_bytes = 0;
};

struct WorldEntry {
    std::string name;
    std::string tenant;
    std::string db_path;      // 绝对路径
    std::string snapshot_dir; // 绝对路径
    std::string label;
    std::string created_at;
};

struct Registry {
    int version = 1;
    std::string default_world = "default";
    std::string active = "default";
    int snapshot_retention = 5;
    std::map<std::string, WorldEntry> worlds;                       // 按 name 排序
    std::map<std::string, std::vector<SnapshotEntry>> snapshots;    // world name → 列表
};

[[nodiscard]] bool is_valid_world_name(std::string_view name);
[[nodiscard]] Registry load_registry(const std::filesystem::path& registry_path);
void save_registry(const std::filesystem::path& registry_path, const Registry& reg);
// 注册表文件不存在时，创建只含 default 世界的注册表并保存。
// 注册表已存在时，原样返回，不修改 default 的路径。
[[nodiscard]] Registry ensure_registry(const std::filesystem::path& registry_path,
                                       const std::filesystem::path& default_db_path,
                                       const std::string& default_tenant);
// 新世界目录为 <registry_dir>/worlds/<name>/，库文件为 world.db，快照目录为 snapshots/。
// 只创建目录和注册项，不创建库文件，库文件留到首次激活时由 SqliteAdapter 建。
// tenant 固定为 name（新建世界不是分叉，没有来源租户）。
WorldEntry create_world(Registry& reg, const std::filesystem::path& registry_dir,
                        const std::string& name, const std::string& label,
                        std::string_view now_iso);
// 拒绝删除 default 和当前活动世界，抛 world_protected。
// 删除注册项、对应的快照列表，并删除 <registry_dir>/worlds/<name>/ 整个目录。
// 只删 registry_dir 之下的路径（防止注册表被篡改后删到外部目录）。
void delete_world(Registry& reg, const std::filesystem::path& registry_dir,
                  const std::string& name);
void set_active(Registry& reg, const std::string& name);

}  // namespace starling::governance
```

注册表 JSON 格式（spec §3.1）：

```json
{
  "version": 1,
  "default": "default",
  "active": "default",
  "snapshot_retention": 5,
  "worlds": {
    "default": {"tenant": "default", "db_path": "...", "snapshot_dir": "...",
                "label": "主世界", "created_at": "..."}
  },
  "snapshots": {"default": [{"id": "...", "path": "...", "kind": "manual",
                             "reason": "manual", "note": "", "created_at": "...",
                             "world_time": "", "size_bytes": 0}]}
}
```

`ensure_registry` 创建默认世界时，`snapshot_dir` 设为 `<registry_dir>/worlds/default/snapshots`（spec §3.1，已修正过的路径），`label` 为 `"主世界"`，`created_at` 取当前 UTC 时间。

- [ ] **Step 1：写失败的测试**

`tests/cpp/test_world_store.cpp`：

```cpp
// test_world_store.cpp — 世界注册表（W1）与快照（W2）。
// 设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md §3/§4。

#include "starling/governance/world_store.hpp"

#include <gtest/gtest.h>

#include <atomic>
#include <filesystem>
#include <fstream>
#include <string>

namespace starling::governance {
namespace {

namespace fs = std::filesystem;

// 每个用例一个独立的临时目录，析构时删除。
class TempDir {
public:
    TempDir() {
        static std::atomic<int> seq{0};
        path_ = fs::temp_directory_path() /
                ("starling-world-" + std::to_string(::getpid()) + "-" +
                 std::to_string(++seq));
        fs::remove_all(path_);
        fs::create_directories(path_);
    }
    ~TempDir() { std::error_code err; fs::remove_all(path_, err); }
    TempDir(const TempDir&) = delete;
    TempDir& operator=(const TempDir&) = delete;
    TempDir(TempDir&&) = delete;
    TempDir& operator=(TempDir&&) = delete;
    [[nodiscard]] const fs::path& path() const { return path_; }
private:
    fs::path path_;
};

std::string code_of(const std::function<void()>& action) {
    try { action(); } catch (const WorldStoreError& err) { return err.code(); }
    return "<no throw>";
}

TEST(WorldName, AcceptsAndRejects) {
    EXPECT_TRUE(is_valid_world_name("default"));
    EXPECT_TRUE(is_valid_world_name("sim-1"));
    EXPECT_TRUE(is_valid_world_name("a_b"));
    EXPECT_TRUE(is_valid_world_name("0abc"));
    EXPECT_FALSE(is_valid_world_name(""));
    EXPECT_FALSE(is_valid_world_name("-lead"));
    EXPECT_FALSE(is_valid_world_name("Upper"));
    EXPECT_FALSE(is_valid_world_name("has space"));
    EXPECT_FALSE(is_valid_world_name("../escape"));
    EXPECT_FALSE(is_valid_world_name("a/b"));
    EXPECT_FALSE(is_valid_world_name(std::string(33, 'a')));
    EXPECT_TRUE(is_valid_world_name(std::string(32, 'a')));
}

TEST(WorldRegistry, EnsureCreatesDefaultOnce) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    const auto db_path = tmp.path() / "dashboard.db";
    const auto first = ensure_registry(reg_path, db_path, "default");
    ASSERT_TRUE(fs::exists(reg_path));
    EXPECT_EQ(first.active, "default");
    EXPECT_EQ(first.default_world, "default");
    EXPECT_EQ(first.snapshot_retention, 5);
    ASSERT_EQ(first.worlds.count("default"), 1U);
    const auto& dflt = first.worlds.at("default");
    EXPECT_EQ(dflt.tenant, "default");
    EXPECT_EQ(fs::path(dflt.db_path), db_path);
    EXPECT_EQ(fs::path(dflt.snapshot_dir), tmp.path() / "worlds" / "default" / "snapshots");

    // 第二次调用不能覆盖已有注册表（哪怕传了不同的 default 路径）。
    auto edited = load_registry(reg_path);
    edited.worlds.at("default").label = "改过的";
    save_registry(reg_path, edited);
    const auto second = ensure_registry(reg_path, tmp.path() / "other.db", "default");
    EXPECT_EQ(second.worlds.at("default").label, "改过的");
    EXPECT_EQ(fs::path(second.worlds.at("default").db_path), db_path);
}

TEST(WorldRegistry, SaveIsAtomicAndRoundTrips) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    SnapshotEntry snap;
    snap.id = "20261025T011200Z-a1b2";
    snap.path = (tmp.path() / "x.db").string();
    snap.kind = "manual";
    snap.reason = "manual";
    snap.note = "备注 with 'quote'";
    snap.created_at = "2026-10-25T01:12:00Z";
    snap.world_time = "2026-10-24T18:03:11Z";
    snap.size_bytes = 123;
    reg.snapshots["default"].push_back(snap);
    save_registry(reg_path, reg);
    // 原子写：目录里不能留下临时文件。
    for (const auto& entry : fs::directory_iterator(tmp.path())) {
        EXPECT_EQ(entry.path().filename().string().find(".tmp"), std::string::npos)
            << entry.path();
    }
    EXPECT_EQ(fs::status(reg_path).permissions() & fs::perms::all,
              fs::perms::owner_read | fs::perms::owner_write);
    const auto back = load_registry(reg_path);
    ASSERT_EQ(back.snapshots.at("default").size(), 1U);
    const auto& got = back.snapshots.at("default").front();
    EXPECT_EQ(got.id, snap.id);
    EXPECT_EQ(got.note, snap.note);
    EXPECT_EQ(got.world_time, snap.world_time);
    EXPECT_EQ(got.size_bytes, 123);
}

TEST(WorldRegistry, CorruptFileFailsLoud) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    { std::ofstream out(reg_path); out << "{not json"; }
    EXPECT_EQ(code_of([&] { (void)load_registry(reg_path); }), "registry_corrupt");
    // 损坏的注册表不能被 ensure_registry 悄悄重建（会丢掉其他世界的登记）。
    EXPECT_EQ(code_of([&] {
        (void)ensure_registry(reg_path, tmp.path() / "d.db", "default");
    }), "registry_corrupt");
}

TEST(WorldRegistry, RejectsRetentionBelowTwo) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    reg.snapshot_retention = 1;
    EXPECT_EQ(code_of([&] { save_registry(reg_path, reg); }), "invalid_retention");
    // 手改文件写入 1，加载时也要拒绝。
    { std::ofstream out(reg_path); out << R"({"version":1,"default":"default","active":"default","snapshot_retention":1,"worlds":{"default":{"tenant":"default","db_path":"/x","snapshot_dir":"/y","label":"","created_at":""}},"snapshots":{}})"; }
    EXPECT_EQ(code_of([&] { (void)load_registry(reg_path); }), "invalid_retention");
}

TEST(WorldRegistry, CreateWorldLayoutAndValidation) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    const auto made = create_world(reg, tmp.path(), "sim-1", "模拟一", "2026-10-25T01:00:00Z");
    EXPECT_EQ(made.tenant, "sim-1");
    EXPECT_EQ(fs::path(made.db_path), tmp.path() / "worlds" / "sim-1" / "world.db");
    EXPECT_EQ(fs::path(made.snapshot_dir), tmp.path() / "worlds" / "sim-1" / "snapshots");
    EXPECT_TRUE(fs::is_directory(made.snapshot_dir));
    EXPECT_FALSE(fs::exists(made.db_path));   // 库留到首次激活
    EXPECT_EQ(reg.worlds.count("sim-1"), 1U);
    EXPECT_EQ(code_of([&] {
        (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    }), "world_exists");
    EXPECT_EQ(code_of([&] {
        (void)create_world(reg, tmp.path(), "../evil", "", "2026-10-25T01:00:00Z");
    }), "invalid_world_name");
}

TEST(WorldRegistry, SetActiveAndDeleteGuards) {
    const TempDir tmp;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    EXPECT_EQ(code_of([&] { set_active(reg, "nope"); }), "world_not_found");
    set_active(reg, "sim-1");
    EXPECT_EQ(reg.active, "sim-1");
    EXPECT_EQ(code_of([&] { delete_world(reg, tmp.path(), "sim-1"); }), "world_protected");
    EXPECT_EQ(code_of([&] { delete_world(reg, tmp.path(), "default"); }), "world_protected");
    EXPECT_EQ(code_of([&] { delete_world(reg, tmp.path(), "nope"); }), "world_not_found");
    set_active(reg, "default");
    const auto dir = tmp.path() / "worlds" / "sim-1";
    ASSERT_TRUE(fs::exists(dir));
    delete_world(reg, tmp.path(), "sim-1");
    EXPECT_EQ(reg.worlds.count("sim-1"), 0U);
    EXPECT_EQ(reg.snapshots.count("sim-1"), 0U);
    EXPECT_FALSE(fs::exists(dir));
}

TEST(WorldRegistry, DeleteRefusesPathOutsideRegistryDir) {
    const TempDir tmp;
    const TempDir outside;
    const auto reg_path = tmp.path() / "worlds.json";
    auto reg = ensure_registry(reg_path, tmp.path() / "dashboard.db", "default");
    (void)create_world(reg, tmp.path(), "sim-1", "", "2026-10-25T01:00:00Z");
    // 模拟被篡改的注册表：db_path 指到外部目录。
    reg.worlds.at("sim-1").db_path = (outside.path() / "world.db").string();
    reg.worlds.at("sim-1").snapshot_dir = (outside.path() / "snapshots").string();
    { std::ofstream out(outside.path() / "keep.txt"); out << "x"; }
    delete_world(reg, tmp.path(), "sim-1");
    EXPECT_TRUE(fs::exists(outside.path() / "keep.txt"));   // 外部文件不受影响
    EXPECT_EQ(reg.worlds.count("sim-1"), 0U);
}

}  // namespace
}  // namespace starling::governance
```

文件开头还需要 `#include <functional>` 和 `#include <unistd.h>`（`getpid`）。

- [ ] **Step 2：登记新文件并确认测试失败**

在 `CMakeLists.txt` 的 `src/governance/metrics_gatherer.cpp` 下面加一行：

```cmake
    src/governance/world_store.cpp
```

在 `tests/cpp/CMakeLists.txt` 的 `test_tick_load_shedding.cpp` 下面加一行：

```cmake
    test_world_store.cpp
```

先创建只含 `#include "starling/governance/world_store.hpp"` 的空 `src/governance/world_store.cpp`，以及只有 include guard 的空头文件，然后运行：

```bash
cd <worktree> && .venv/bin/cmake --build build --target starling_tests 2>&1 | tail -5
```

预期：编译失败，报 `WorldStoreError`、`is_valid_world_name` 等未声明。

- [ ] **Step 3：写头文件**

把上面 Interfaces 里的完整声明写进 `include/starling/governance/world_store.hpp`。需要的 include：`<cstdint>`、`<filesystem>`、`<map>`、`<stdexcept>`、`<string>`、`<string_view>`、`<vector>`。文件开头用一段注释说明设计稿路径，并说明这个文件是 W1/W2 的唯一权威实现。

- [ ] **Step 4：写实现**

`src/governance/world_store.cpp` 的要点：

```cpp
#include "starling/governance/world_store.hpp"

#include <nlohmann/json.hpp>

#include <chrono>
#include <cstdio>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <random>
#include <sstream>
#include <system_error>

namespace starling::governance {

namespace fs = std::filesystem;
using Json = nlohmann::json;

WorldStoreError::WorldStoreError(std::string code, const std::string& detail)
    : std::runtime_error(code + ": " + detail), code_(std::move(code)) {}
const std::string& WorldStoreError::code() const noexcept { return code_; }

bool is_valid_world_name(std::string_view name) {
    if (name.empty() || name.size() > 32) { return false; }
    const auto alnum = [](char chr) {
        return (chr >= 'a' && chr <= 'z') || (chr >= '0' && chr <= '9');
    };
    if (!alnum(name.front())) { return false; }
    for (const char chr : name) {
        if (!alnum(chr) && chr != '_' && chr != '-') { return false; }
    }
    return true;
}
```

其余部分：

- **JSON 映射**：在匿名命名空间里写 `to_json`/`from_json`，或手写 `entry_to_json`/`entry_from_json`。缺字段时用默认值：`label`、`note`、`world_time` 为空，`size_bytes` 为 0，`snapshot_retention` 为 5。顶层不是对象、`worlds` 不是对象、`worlds` 里缺 `default_world` 对应的世界时，一律抛 `registry_corrupt`。`nlohmann::json::parse` 抛出的 `parse_error` 也转成 `registry_corrupt`。
- **`validate(const Registry&)`**：`snapshot_retention < 2` 抛 `invalid_retention`。`load_registry` 和 `save_registry` 都要调用它。
- **`save_registry`**：确保父目录存在。在同目录生成临时文件名 `.worlds-<随机十六进制>.tmp`，用 `std::ofstream` 写入 `dump(2)`，flush 并关闭，然后 `fs::permissions(tmp, owner_read | owner_write, replace)`，再 `fs::rename(tmp, reg_path)`。任一步抛异常都要先 `fs::remove(tmp, err)` 再重新抛出。
- **`ensure_registry`**：注册表存在就调 `load_registry`（损坏时让异常继续抛出），不存在就构造只含默认世界的注册表并保存。`registry_dir = registry_path.parent_path()`。
- **`create_world`**：校验名称，然后检查重名，接着 `fs::create_directories(<dir>/snapshots)`，最后写入 `reg.worlds[name]`。
- **`delete_world`**：先依次检查名称是否存在、是否为 default、是否为活动世界，然后从 `reg.worlds` 和 `reg.snapshots` 中删除。只有当 `<registry_dir>/worlds/<name>` 经 `fs::weakly_canonical` 后仍以 `fs::weakly_canonical(registry_dir / "worlds")` 为前缀时，才执行 `fs::remove_all`。外部路径一律不碰。
- **当前时间工具**：`iso_now()` 返回 `%Y-%m-%dT%H:%M:%SZ`，`compact_now()` 返回 `%Y%m%dT%H%M%SZ`。两者都用 `gmtime_r`，T2 会复用。

- [ ] **Step 5：构建并运行测试**

```bash
cd <worktree> && .venv/bin/cmake --build build --target starling_tests && build/tests/cpp/starling_tests --gtest_filter='World*'
```

预期：`WorldName.*` 和 `WorldRegistry.*` 全部 PASS。

- [ ] **Step 6：本地对改动行跑 clang-tidy**

```bash
cd <worktree> && CLANG_TIDY=/opt/homebrew/opt/llvm/bin/clang-tidy .venv/bin/python scripts/ci_clang_tidy_diff.py 4080733 build
```

预期：没有新的诊断。若报短标识符（`readability-identifier-length`），改成 3 个字符以上的名字。

- [ ] **Step 7：提交**

```bash
git add include/starling/governance/world_store.hpp src/governance/world_store.cpp tests/cpp/test_world_store.cpp CMakeLists.txt tests/cpp/CMakeLists.txt
git commit -F - <<'MSG'
feat(world): 世界注册表 WorldStore（W1 核心）

一个世界 = 一个 SQLite 文件 + 一个租户 id。注册表 worlds.json 0600、
临时文件 + rename 原子写；损坏时 fail loud，不会被 ensure 悄悄重建。
名称限 [a-z0-9][a-z0-9_-]{0,31}；delete 只删 registry 目录下的路径。

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

---

### Task 2：快照、保留策略与世界统计（C++）

**Files:**
- Modify: `include/starling/governance/world_store.hpp`（追加声明）
- Modify: `src/governance/world_store.cpp`
- Modify: `tests/cpp/test_world_store.cpp`（追加用例）

**Interfaces:**
- Consumes：T1 的 `Registry`、`WorldEntry`、`SnapshotEntry`、`WorldStoreError`、`iso_now`/`compact_now`。
- Produces：

```cpp
struct WorldStats {
    std::int64_t db_bytes = 0;        // 主文件 + -wal 的字节数；文件不存在时为 0
    std::int64_t live_bytes = 0;      // (page_count - freelist_count) * page_size
    std::int64_t statements = 0;      // WHERE tenant_id = tenant
    std::int64_t engrams = 0;         // WHERE tenant_id = tenant
    std::string world_time;           // 见 snapshot_world_time
};
// 只读打开 db_path（mode=ro）。库文件不存在时返回全 0 的统计，不抛异常。
// 表不存在时（库是空的、未迁移），对应计数为 0。
[[nodiscard]] WorldStats world_stats(const std::string& db_path, const std::string& tenant);

// 世界时刻水位：source_unit_meta 存在且有非空 observed_at 时取 MAX(observed_at)，
// 否则取 engrams 的 MAX(created_at)，都没有则为空字符串。只读，按 tenant 过滤。
[[nodiscard]] std::string snapshot_world_time(const std::string& db_path,
                                              const std::string& tenant);

struct SnapshotOptions {
    std::string kind = "manual";      // "manual" | "auto"
    std::string reason = "manual";
    std::string note;
    // 测试注入用：返回可用字节数。为空时用 std::filesystem::space(dir).available。
    std::function<std::int64_t(const std::filesystem::path&)> free_space;
};

// 1. 取世界；不存在抛 world_not_found。
// 2. 只读打开 db_path，计算 live_bytes；free_space(snapshot_dir) < 3 * live_bytes 时
//    抛 insufficient_disk（不写任何文件）。
// 3. id = compact_now() + "-" + 4 位随机十六进制；与该世界已有的 id 重复时重新生成。
// 4. 删掉残留的 <id>.db.partial，再用只读连接执行 VACUUM INTO ?（绑定参数）写到 partial。
// 5. 关闭连接，再用只读连接打开 partial，PRAGMA integrity_check 必须为 "ok"，
//    否则删掉 partial 并抛 snapshot_failed。
// 6. fs::rename(partial, <id>.db)，填 size_bytes、world_time、created_at。
// 7. 插到 reg.snapshots[world] 的开头（最新在前），然后调用 apply_retention。
// 8. 不负责 save_registry，由调用方保存。
// 任何 SQLite 错误都转成 snapshot_failed，并保证不留下 partial 文件。
SnapshotEntry take_snapshot(Registry& reg, const std::string& world,
                            const SnapshotOptions& opts);

// 按保留份数 N 修剪 reg.snapshots[world]，并删除对应的文件，返回被删除的 id 列表。
// 规则（spec §4.4）：
//   - 总数 <= N：不删。
//   - 超出部分从最旧的开始删，优先删 auto；auto 删完还超出时才删 manual，从最旧的开始。
//   - 但列表里有 auto 时，至少保留最新的 1 份 auto（回滚锚点）。
std::vector<std::string> apply_retention(Registry& reg, const std::string& world);

// 删除一份快照（注册项 + 文件）。不存在时抛 snapshot_not_found。
// 只删 snapshot_dir 之下的文件（防篡改，规则同 delete_world）。
void delete_snapshot(Registry& reg, const std::string& world, const std::string& snapshot_id);
```

`world_time` 实现时注意：`source_unit_meta` 在生产库里**不存在**（迁移停在 36）。先查 `sqlite_master` 判断表是否存在，再查询，不能依赖 SQL 报错。

- [ ] **Step 1：写失败的测试**

在 `test_world_store.cpp` 追加以下内容（同一个匿名命名空间内）。需要 `#include "starling/persistence/sqlite_adapter.hpp"`、`"starling/persistence/stmt.hpp"`、`<sqlite3.h>`、`<vector>`。

```cpp
// 用真实迁移建一个有数据的世界库，保证快照测的是 Starling 真实的 schema。
void seed_world_db(const fs::path& db_path, const std::string& tenant, int engram_rows) {
    auto adapter = persistence::SqliteAdapter::open(db_path);
    auto& conn = adapter->connection();
    for (int idx = 0; idx < engram_rows; ++idx) {
        // source_item_id 必须各不相同：idx_engrams_source_identity 是
        // (tenant_id, adapter_name, source_item_id, source_version, chunk_index) 唯一索引，
        // 只填必填列时后四列全是默认值 ''/0，第二行就会撞唯一约束（已实测）。
        persistence::Stmt ins(conn.raw(),
            "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
            "ingest_mode,privacy_class,retention_mode,created_at,source_item_id) "
            "VALUES(?1,?2,?3,'conversation','default','inline','normal','audit_retain',?4,?1)");
        ins.bind("eng-" + std::to_string(idx), tenant, "h" + std::to_string(idx),
                 "2026-10-2" + std::to_string(idx % 5) + "T00:00:00Z");
        ins.step_done();
    }
}

Registry registry_with_world(const TempDir& tmp, const std::string& name) {
    auto reg = ensure_registry(tmp.path() / "worlds.json", tmp.path() / "dashboard.db",
                               "default");
    if (name != "default") {
        (void)create_world(reg, tmp.path(), name, "", "2026-10-25T01:00:00Z");
    }
    return reg;
}

std::int64_t count_rows(const std::string& db_path, const char* sql) {
    sqlite3* raw = nullptr;
    EXPECT_EQ(sqlite3_open_v2(("file:" + db_path + "?mode=ro").c_str(), &raw,
                              SQLITE_OPEN_READONLY | SQLITE_OPEN_URI, nullptr), SQLITE_OK);
    persistence::SqliteHandle handle(raw);
    persistence::Stmt query(raw, sql);
    EXPECT_TRUE(query.step_row());
    return sqlite3_column_int64(query.raw(), 0);
}

TEST(WorldSnapshot, ProducesIntactCompactCopy) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 5);

    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    EXPECT_EQ(snap.kind, "manual");
    EXPECT_TRUE(fs::exists(snap.path));
    EXPECT_GT(snap.size_bytes, 0);
    EXPECT_EQ(snap.world_time, "2026-10-24T00:00:00Z");   // engrams MAX(created_at)
    EXPECT_EQ(fs::path(snap.path).parent_path(), fs::path(world.snapshot_dir));
    EXPECT_EQ(count_rows(snap.path, "SELECT COUNT(*) FROM engrams"), 5);
    EXPECT_EQ(count_rows(snap.path, "SELECT COUNT(*) FROM pragma_integrity_check "
                                    "WHERE integrity_check='ok'"), 1);
    // 不留 partial。
    for (const auto& entry : fs::directory_iterator(world.snapshot_dir)) {
        EXPECT_EQ(entry.path().extension(), ".db") << entry.path();
    }
    ASSERT_EQ(reg.snapshots.at("sim-1").size(), 1U);
    EXPECT_EQ(reg.snapshots.at("sim-1").front().id, snap.id);
}

TEST(WorldSnapshot, SnapshotIsIndependentOfLaterWrites) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 2);
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    seed_world_db(world.db_path, "sim-1", 0);   // 重开库不改变行
    {
        auto adapter = persistence::SqliteAdapter::open(world.db_path);
        persistence::Stmt del(adapter->connection().raw(), "DELETE FROM engrams");
        del.step_done();
    }
    EXPECT_EQ(count_rows(world.db_path, "SELECT COUNT(*) FROM engrams"), 0);
    EXPECT_EQ(count_rows(snap.path, "SELECT COUNT(*) FROM engrams"), 2);
}

TEST(WorldSnapshot, TakenWhileWriterHoldsOpenTransaction) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 1);
    auto adapter = persistence::SqliteAdapter::open(world.db_path);
    adapter->connection().begin_immediate();
    persistence::Stmt ins(adapter->connection().raw(),
        "INSERT INTO engrams(id,tenant_id,content_hash,source_kind,ingest_policy,"
        "ingest_mode,privacy_class,retention_mode,created_at,source_item_id) "
        "VALUES('uncommitted','sim-1','hx','conversation','default','inline','normal',"
        "'audit_retain','2026-10-25T00:00:00Z','uncommitted')");
    ins.step_done();
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});   // 不能报错
    adapter->connection().rollback();
    EXPECT_EQ(count_rows(snap.path, "SELECT COUNT(*) FROM engrams"), 1);   // 不含未提交行
}

TEST(WorldSnapshot, PathWithSpacesAndQuotes) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    auto& world = reg.worlds.at("sim-1");
    world.snapshot_dir = (tmp.path() / "worlds" / "sim-1" / "it's a dir").string();
    fs::create_directories(world.snapshot_dir);
    seed_world_db(world.db_path, "sim-1", 1);
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    EXPECT_TRUE(fs::exists(snap.path));
}

TEST(WorldSnapshot, DiskGuardRefusesWithoutWriting) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    seed_world_db(world.db_path, "sim-1", 3);
    SnapshotOptions opts;
    opts.free_space = [](const fs::path&) -> std::int64_t { return 1; };
    EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "sim-1", opts); }), "insufficient_disk");
    EXPECT_TRUE(fs::is_empty(world.snapshot_dir));
    EXPECT_EQ(reg.snapshots.count("sim-1") == 0 || reg.snapshots.at("sim-1").empty(), true);
}

TEST(WorldSnapshot, UnknownWorldAndMissingDb) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "nope", SnapshotOptions{}); }),
              "world_not_found");
    // 库文件还没创建（世界从未激活）：拒绝，并且不留 partial。
    EXPECT_EQ(code_of([&] { (void)take_snapshot(reg, "sim-1", SnapshotOptions{}); }),
              "snapshot_failed");
    EXPECT_TRUE(fs::is_empty(reg.worlds.at("sim-1").snapshot_dir));
}

// 保留策略不需要真实快照文件，构造注册项即可。
SnapshotEntry fake_snapshot(const fs::path& dir, const std::string& stamp,
                            const std::string& kind) {
    SnapshotEntry snap;
    snap.id = stamp;
    snap.path = (dir / (stamp + ".db")).string();
    snap.kind = kind;
    snap.reason = kind;
    snap.created_at = stamp;
    { std::ofstream out(snap.path); out << "x"; }
    return snap;
}

std::vector<std::string> ids_of(const std::vector<SnapshotEntry>& snaps) {
    std::vector<std::string> out;
    for (const auto& snap : snaps) { out.push_back(snap.id); }
    return out;
}

TEST(WorldRetention, PrefersDroppingAutoKeepsNewestAuto) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    reg.snapshot_retention = 3;
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    // 列表最新在前：t5..t1
    reg.snapshots["sim-1"] = {
        fake_snapshot(dir, "t5", "manual"), fake_snapshot(dir, "t4", "auto"),
        fake_snapshot(dir, "t3", "manual"), fake_snapshot(dir, "t2", "auto"),
        fake_snapshot(dir, "t1", "manual"),
    };
    const auto removed = apply_retention(reg, "sim-1");
    // 超出 2 份：先删最旧的 auto t2；auto 只剩 t4，必须保留；再删最旧的 manual t1。
    EXPECT_EQ(removed, (std::vector<std::string>{"t2", "t1"}));
    EXPECT_EQ(ids_of(reg.snapshots.at("sim-1")), (std::vector<std::string>{"t5", "t4", "t3"}));
    EXPECT_FALSE(fs::exists(dir / "t2.db"));
    EXPECT_FALSE(fs::exists(dir / "t1.db"));
    EXPECT_TRUE(fs::exists(dir / "t4.db"));
}

TEST(WorldRetention, AllManualDropsOldest) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    reg.snapshot_retention = 2;
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    reg.snapshots["sim-1"] = {fake_snapshot(dir, "t3", "manual"),
                              fake_snapshot(dir, "t2", "manual"),
                              fake_snapshot(dir, "t1", "manual")};
    EXPECT_EQ(apply_retention(reg, "sim-1"), (std::vector<std::string>{"t1"}));
    EXPECT_EQ(ids_of(reg.snapshots.at("sim-1")), (std::vector<std::string>{"t3", "t2"}));
}

TEST(WorldRetention, UnderLimitIsNoop) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const fs::path dir = reg.worlds.at("sim-1").snapshot_dir;
    reg.snapshots["sim-1"] = {fake_snapshot(dir, "t1", "auto")};
    EXPECT_TRUE(apply_retention(reg, "sim-1").empty());
    EXPECT_EQ(reg.snapshots.at("sim-1").size(), 1U);
}

TEST(WorldRetention, TakeSnapshotAppliesRetention) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    reg.snapshot_retention = 2;
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);
    for (int idx = 0; idx < 3; ++idx) { (void)take_snapshot(reg, "sim-1", SnapshotOptions{}); }
    EXPECT_EQ(reg.snapshots.at("sim-1").size(), 2U);
    std::size_t files = 0;
    for (const auto& entry : fs::directory_iterator(reg.worlds.at("sim-1").snapshot_dir)) {
        (void)entry;
        ++files;
    }
    EXPECT_EQ(files, 2U);
}

TEST(WorldSnapshotDelete, RemovesEntryAndFile) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    seed_world_db(reg.worlds.at("sim-1").db_path, "sim-1", 1);
    const auto snap = take_snapshot(reg, "sim-1", SnapshotOptions{});
    EXPECT_EQ(code_of([&] { delete_snapshot(reg, "sim-1", "missing"); }), "snapshot_not_found");
    delete_snapshot(reg, "sim-1", snap.id);
    EXPECT_FALSE(fs::exists(snap.path));
    EXPECT_TRUE(reg.snapshots.at("sim-1").empty());
}

TEST(WorldStats, CountsTenantRowsAndHandlesMissingDb) {
    const TempDir tmp;
    auto reg = registry_with_world(tmp, "sim-1");
    const auto& world = reg.worlds.at("sim-1");
    const auto empty = world_stats(world.db_path, "sim-1");   // 文件不存在
    EXPECT_EQ(empty.db_bytes, 0);
    EXPECT_EQ(empty.engrams, 0);
    seed_world_db(world.db_path, "sim-1", 4);
    const auto stats = world_stats(world.db_path, "sim-1");
    EXPECT_EQ(stats.engrams, 4);
    EXPECT_EQ(stats.statements, 0);
    EXPECT_GT(stats.db_bytes, 0);
    EXPECT_GT(stats.live_bytes, 0);
    EXPECT_EQ(world_stats(world.db_path, "other").engrams, 0);   // 按租户过滤
}
```

- [ ] **Step 2：确认测试失败**

```bash
cd <worktree> && .venv/bin/cmake --build build --target starling_tests 2>&1 | tail -5
```

预期：编译失败，报 `take_snapshot`、`WorldStats` 等未声明。

- [ ] **Step 3：写实现**

在头文件里追加 Interfaces 中的声明，需要 `#include <functional>`。实现要点：

- **只读打开**：写一个匿名命名空间里的辅助函数

  ```cpp
  persistence::SqliteHandle open_read_only(const std::string& path) {
      sqlite3* raw = nullptr;
      const std::string uri = "file:" + path + "?mode=ro";
      const int code = sqlite3_open_v2(uri.c_str(), &raw,
                                       SQLITE_OPEN_READONLY | SQLITE_OPEN_URI, nullptr);
      persistence::SqliteHandle handle(raw);
      if (code != SQLITE_OK) {
          throw WorldStoreError("snapshot_failed",
              std::string("open ") + path + ": " + (raw ? sqlite3_errmsg(raw) : "alloc"));
      }
      sqlite3_busy_timeout(raw, 5000);
      return handle;
  }
  ```

  注意：URI 里的路径如果含 `?` 或 `#` 需要转义。world 名称校验已经排除了这两个字符，但 `snapshot_dir` 可能来自手改的注册表，所以要对 `%`、`?`、`#` 做百分号编码（分别编码为 `%25`、`%3f`、`%23`）。
- **表存在检查**：`SELECT 1 FROM sqlite_master WHERE type='table' AND name=?1`。
- **`world_stats`**：文件不存在时返回默认值。`db_bytes = file_size(db) + file_size(db + "-wal")`（wal 不存在则按 0 计）。`live_bytes` 用 `PRAGMA page_count`、`PRAGMA freelist_count`、`PRAGMA page_size` 计算。`statements` 和 `engrams` 先检查表是否存在，再执行 `SELECT COUNT(*) ... WHERE tenant_id=?1`。`world_time` 调用 `snapshot_world_time`。
- **`take_snapshot`**：按 Interfaces 里的 8 步实现。库文件不存在时，在打开连接之前就抛 `snapshot_failed`，否则 `mode=ro` 会报 `unable to open`，错误信息不清楚。VACUUM 用

  ```cpp
  persistence::Stmt vac(handle.get(), "VACUUM INTO ?1");
  vac.bind(partial.string());
  vac.step_done();
  ```

  `handle.reset()` 关闭源连接之后，再对 partial 跑 `PRAGMA integrity_check`。用 `try/catch (const std::exception&)` 包住第 4 到第 6 步，catch 里执行 `fs::remove(partial, err)` 后抛 `snapshot_failed`。`WorldStoreError` 本身要原样重新抛出，不要二次包装。
- **`apply_retention`**：按 spec 规则实现。建议的算法：

  ```cpp
  auto& list = reg.snapshots[world];          // 最新在前
  std::vector<std::string> removed;
  const auto limit = static_cast<std::size_t>(reg.snapshot_retention);
  const auto newest_auto = std::find_if(list.begin(), list.end(),
      [](const SnapshotEntry& snap) { return snap.kind == "auto"; });
  const std::string keep_auto = newest_auto == list.end() ? "" : newest_auto->id;
  // 第一轮：从最旧的 auto 开始删（跳过 keep_auto）
  // 第二轮：仍超出时，从最旧的 manual 开始删
  ```

  删除文件时调用 `remove_within(dir, path)`，它和 `delete_world` 共用同一个防篡改前缀检查。
- **`delete_snapshot`**：找到条目，从列表中移除，再在防篡改检查通过后删除文件。

- [ ] **Step 4：运行全部 World 测试**

```bash
cd <worktree> && .venv/bin/cmake --build build --target starling_tests && build/tests/cpp/starling_tests --gtest_filter='World*'
```

预期：全部 PASS。

- [ ] **Step 5：全量 ctest，确认没有回归**

```bash
cd <worktree>/build && ../.venv/bin/ctest --output-on-failure -j8 2>&1 | tail -5
```

预期：`100% tests passed`。

- [ ] **Step 6：clang-tidy 检查改动行**

```bash
cd <worktree> && CLANG_TIDY=/opt/homebrew/opt/llvm/bin/clang-tidy .venv/bin/python scripts/ci_clang_tidy_diff.py 4080733 build
```

预期：没有新的诊断。

- [ ] **Step 7：提交**

```bash
git add include/starling/governance/world_store.hpp src/governance/world_store.cpp tests/cpp/test_world_store.cpp
git commit -F - <<'MSG'
feat(world): 快照、保留策略与世界统计（W2 核心）

快照走只读连接的 VACUUM INTO ?（绑定参数），先写 .partial、
integrity_check 通过后再 rename；不碰引擎写连接，写事务进行中也能拍，
且不含未提交行。磁盘守卫按活数据量（page_count - freelist）×3 判，
不按文件大小——生产库 2.4GB 里 97.7% 是 freelist。保留 N 份时优先删
auto、至少留最新 1 份 auto 作回滚锚点。

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

---

### Task 3：Python 绑定 `bind_15_world`

**Files:**
- Create: `bindings/python/bind_15_world.cpp`
- Modify: `bindings/python/bindings.hpp`（加 `void bind_15_world(pybind11::module_& m);`）
- Modify: `bindings/python/module.cpp`（`bind_14_governance(m);` 之后调用 `bind_15_world(m);`）
- Modify: `bindings/python/CMakeLists.txt`（`bind_14_governance.cpp` 之后加 `bind_15_world.cpp`）
- Create: `tests/python/test_dashboard_worlds.py`（本任务只写绑定测试，T4 和 T5 往里追加）

**Interfaces:**
- Consumes：T1 和 T2 的全部 C++ 接口。
- Produces（T4 和 T5 只通过这些名字调用 C++，注册表在 Python 里一律用 dict 表示）：

```python
_core.WorldStoreError          # Python 异常，继承 RuntimeError；args[0] 形如 "world_exists: ..."
_core.world_store_error_code(exc) -> str   # 从异常取 code（取 str(exc) 冒号前的部分）
_core.world_is_valid_name(name: str) -> bool
_core.world_ensure_registry(registry_path: str, default_db_path: str, default_tenant: str) -> dict
_core.world_load_registry(registry_path: str) -> dict
_core.world_save_registry(registry_path: str, registry: dict) -> None
_core.world_create(registry: dict, registry_dir: str, name: str, label: str, now_iso: str) -> dict
    # 返回 {"registry": <更新后的 dict>, "world": <WorldEntry dict>}
_core.world_delete(registry: dict, registry_dir: str, name: str) -> dict        # 返回更新后的 registry
_core.world_set_active(registry: dict, name: str) -> dict                        # 返回更新后的 registry
_core.world_stats(db_path: str, tenant: str) -> dict
    # {"db_bytes","live_bytes","statements","engrams","world_time"}
_core.world_take_snapshot(registry: dict, world: str, kind: str = "manual",
                          reason: str = "manual", note: str = "") -> dict
    # 返回 {"registry": <更新后的 dict>, "snapshot": <SnapshotEntry dict>}
    # 运行期间释放 GIL（py::gil_scoped_release），VACUUM 可能要几秒
_core.world_delete_snapshot(registry: dict, world: str, snapshot_id: str) -> dict  # 返回 registry
```

dict 的格式和磁盘上的 JSON **完全一致**（顶层键 `version`、`default`、`active`、`snapshot_retention`、`worlds`、`snapshots`），所以 Python 层不需要第二套序列化。实现方式：C++ 侧复用 T1 的 `to_json`/`from_json`，绑定层用 `json.dumps` 和 `json.loads` 在 `py::dict` 与 `nlohmann::json` 之间转换。更简单的写法是绑定层直接收发 JSON 字符串，再在 `bind_15_world.cpp` 里调用 Python `json` 模块。下面给出推荐写法。

在 T1 的头文件里追加两个序列化函数（T1 已经实现了 JSON 映射，这里只是把它们公开）：

```cpp
[[nodiscard]] std::string registry_to_json(const Registry& reg);
[[nodiscard]] Registry registry_from_json(const std::string& text);   // 失败抛 registry_corrupt
[[nodiscard]] std::string world_entry_to_json(const WorldEntry& entry);
[[nodiscard]] std::string snapshot_entry_to_json(const SnapshotEntry& entry);
```

- [ ] **Step 1：写失败的测试**

`tests/python/test_dashboard_worlds.py`：

```python
"""世界注册表与快照（W1/W2）：绑定、切换、路由。

设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md
"""
import sqlite3

import pytest

from starling import _core


def _code(exc) -> str:
    return _core.world_store_error_code(exc)


def test_binding_registry_roundtrip(tmp_path):
    reg_path = str(tmp_path / "worlds.json")
    reg = _core.world_ensure_registry(reg_path, str(tmp_path / "dashboard.db"), "default")
    assert reg["active"] == "default"
    assert reg["snapshot_retention"] == 5
    assert set(reg["worlds"]) == {"default"}

    out = _core.world_create(reg, str(tmp_path), "sim-1", "模拟一", "2026-10-25T01:00:00Z")
    reg = out["registry"]
    assert out["world"]["tenant"] == "sim-1"
    assert out["world"]["db_path"].endswith("worlds/sim-1/world.db")
    _core.world_save_registry(reg_path, reg)
    assert set(_core.world_load_registry(reg_path)["worlds"]) == {"default", "sim-1"}


def test_binding_error_codes(tmp_path):
    reg = _core.world_ensure_registry(str(tmp_path / "w.json"), str(tmp_path / "d.db"), "default")
    with pytest.raises(_core.WorldStoreError) as ei:
        _core.world_create(reg, str(tmp_path), "Bad Name", "", "2026-10-25T01:00:00Z")
    assert _code(ei.value) == "invalid_world_name"
    with pytest.raises(_core.WorldStoreError) as ei:
        _core.world_set_active(reg, "nope")
    assert _code(ei.value) == "world_not_found"
    assert isinstance(ei.value, RuntimeError)


def test_binding_snapshot_and_stats(tmp_path):
    reg = _core.world_ensure_registry(str(tmp_path / "w.json"), str(tmp_path / "d.db"), "default")
    reg = _core.world_create(reg, str(tmp_path), "sim-1", "", "2026-10-25T01:00:00Z")["registry"]
    db = reg["worlds"]["sim-1"]["db_path"]
    _core.SqliteAdapter.open(db)   # 跑迁移建库
    stats = _core.world_stats(db, "sim-1")
    assert stats["engrams"] == 0 and stats["db_bytes"] > 0

    out = _core.world_take_snapshot(reg, "sim-1", note="手动")
    snap = out["snapshot"]
    assert snap["kind"] == "manual" and snap["note"] == "手动"
    con = sqlite3.connect(f"file:{snap['path']}?mode=ro", uri=True)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()
    reg = _core.world_delete_snapshot(out["registry"], "sim-1", snap["id"])
    assert reg["snapshots"]["sim-1"] == []
```

- [ ] **Step 2：确认测试失败**

```bash
cd <worktree> && .venv/bin/python -m pytest tests/python/test_dashboard_worlds.py -q 2>&1 | tail -3
```

预期：`AttributeError: module 'starling._core' has no attribute 'world_ensure_registry'`。

- [ ] **Step 3：写绑定**

`bindings/python/bind_15_world.cpp` 的骨架：

```cpp
// bind_15_world — 世界注册表与快照（W1/W2）。注册表在 Python 侧以 dict 表示，
// 格式与 worlds.json 逐字一致；转换经 Python json 模块，C++ 是唯一的序列化实现。
// 设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md

#include "bind_common.hpp"

#include <pybind11/stl.h>

#include "starling/governance/world_store.hpp"

namespace starling::bindings {

namespace {

namespace gov = starling::governance;

py::object to_py(const std::string& text) {
    return py::module_::import("json").attr("loads")(text);
}

std::string from_py(const py::object& obj) {
    return py::module_::import("json").attr("dumps")(obj, py::arg("ensure_ascii") = false)
        .cast<std::string>();
}

gov::Registry reg_in(const py::dict& reg) { return gov::registry_from_json(from_py(reg)); }
py::object reg_out(const gov::Registry& reg) { return to_py(gov::registry_to_json(reg)); }

}  // namespace

// NOLINTNEXTLINE(readability-identifier-length) — `m` matches all sibling bind_NN units
void bind_15_world(pybind11::module_& m) {
    // 与 bind_07/bind_14 同一写法；what() 形如 "world_exists: sim-1"。
    py::register_exception<gov::WorldStoreError>(m, "WorldStoreError", PyExc_RuntimeError);
    m.def("world_store_error_code", [](const py::object& exc) {
        const auto text = py::str(exc).cast<std::string>();
        const auto pos = text.find(':');
        return pos == std::string::npos ? text : text.substr(0, pos);
    });
    m.def("world_is_valid_name", &gov::is_valid_world_name, py::arg("name"));
    m.def("world_ensure_registry",
          [](const std::string& reg_path, const std::string& db_path, const std::string& tenant) {
              return reg_out(gov::ensure_registry(reg_path, db_path, tenant));
          }, py::arg("registry_path"), py::arg("default_db_path"), py::arg("default_tenant"));
    // ... 其余函数按 Interfaces 依次绑定，返回值统一用 to_py(...) 转 dict
    m.def("world_take_snapshot",
          [](const py::dict& reg, const std::string& world, const std::string& kind,
             const std::string& reason, const std::string& note) {
              auto registry = reg_in(reg);
              gov::SnapshotOptions opts;
              opts.kind = kind;
              opts.reason = reason;
              opts.note = note;
              gov::SnapshotEntry snap;
              {
                  const py::gil_scoped_release release;
                  snap = gov::take_snapshot(registry, world, opts);
              }
              py::dict out;
              out["registry"] = reg_out(registry);
              out["snapshot"] = to_py(gov::snapshot_entry_to_json(snap));
              return out;
          }, py::arg("registry"), py::arg("world"), py::arg("kind") = "manual",
          py::arg("reason") = "manual", py::arg("note") = "");
}

}  // namespace starling::bindings
```

`world_stats` 返回 `py::dict`，键名见 Interfaces。

- [ ] **Step 4：重建 `_core` 并运行测试**

```bash
cd <worktree> && .venv/bin/cmake --build build && .venv/bin/cmake --install build --prefix .venv/lib/python3.14/site-packages && .venv/bin/python -m pytest tests/python/test_dashboard_worlds.py -q 2>&1 | tail -3
```

预期：3 passed。

- [ ] **Step 5：提交**

```bash
git add bindings/python/bind_15_world.cpp bindings/python/bindings.hpp bindings/python/module.cpp bindings/python/CMakeLists.txt include/starling/governance/world_store.hpp src/governance/world_store.cpp tests/python/test_dashboard_worlds.py
git commit -F - <<'MSG'
feat(world): Python 绑定 _core.world_*

注册表在 Python 侧是与 worlds.json 逐字一致的 dict，序列化只有 C++ 一份。
快照期间释放 GIL。WorldStoreError 继承 RuntimeError，code 取冒号前缀。

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

---

### Task 4：世界切换（Python 引擎生命周期）

**Files:**
- Create: `python/starling/dashboard/world_manager.py`
- Modify: `python/starling/dashboard/engine.py`（加 `quiesce()`）
- Modify: `python/starling/dashboard/app.py`（启动时引导注册表、按活动世界改写 config）
- Modify: `tests/python/test_dashboard_worlds.py`（追加）

**Interfaces:**
- Consumes：T3 的 `_core.world_*`。
- Produces（T5 的路由只调用这些）：

```python
class WorldSwitchError(Exception):
    """code: "world_not_found" | "ingest_busy" | "world_open_failed" """
    def __init__(self, code: str, detail: str = ""): ...
    code: str

class WorldManager:
    def __init__(self, app_state, registry_path: str): ...
    registry_path: str
    registry_dir: str
    lock: threading.RLock      # 世界管理锁，所有注册表读改写都在锁内
    def load(self) -> dict                        # 读当前注册表
    def save(self, reg: dict) -> None
    def active_world(self) -> dict                # 当前活动世界的 WorldEntry dict（含 name）
    def activate(self, name: str) -> None         # 抛 WorldSwitchError
    def create(self, name: str, label: str) -> dict    # WorldEntry dict；抛 _core.WorldStoreError
    def delete(self, name: str) -> None                 # 抛 _core.WorldStoreError
    def take_snapshot(self, name: str, note: str) -> dict   # SnapshotEntry dict
    def delete_snapshot(self, name: str, snapshot_id: str) -> None

def registry_path_for(config) -> str
    # STARLING_WORLDS_REGISTRY 环境变量优先；否则 <dirname(config.db_path)>/worlds.json
def bootstrap_worlds(config) -> "WorldManager.__init__ 所需的 registry_path"
    # 调 _core.world_ensure_registry(registry_path, config.db_path, config.tenant)，
    # 然后把 config.db_path / config.tenant 改写为活动世界的值（原地改写 config 对象）。
    # 活动世界不是 default 时，ingest 仍按租户分区，无需改 spool 路径。
```

`DashboardEngine.quiesce(timeout_s: float = 5.0) -> bool`：依次调用 `stop_ingest_worker()` 和 `stop_background_tick()`。两个线程都确认退出时返回 True。如果 `join(timeout)` 后线程仍然存活，返回 False，并且**不能**把 `_ingest_thread` 置为 None（保持现状，以便调用方回报 `ingest_busy`）。现有的 `stop_ingest_worker` 不管 join 是否成功都会把句柄置空，所以 `quiesce` 要在调用它**之前**保存线程引用，调用之后再检查 `is_alive()`。

**切换算法**（spec §8.1，完整照抄进 `activate`）：

```python
def activate(self, name: str) -> None:
    with self.lock:
        reg = self.load()
        if name not in reg["worlds"]:
            raise WorldSwitchError("world_not_found", name)
        if reg["active"] == name and self._state.engine is not None:
            return
        old_engine = self._state.engine
        old_cfg = self._state.config
        new_cfg = dataclasses.replace(old_cfg)
        new_cfg.db_path = reg["worlds"][name]["db_path"]
        new_cfg.tenant = reg["worlds"][name]["tenant"]
        if old_engine is not None:
            with old_engine._lock:                     # 等在飞请求结束
                if not old_engine.quiesce():
                    # 摄入线程没停下：恢复后台线程，状态不前进
                    self._restart_workers(old_engine)
                    raise WorldSwitchError("ingest_busy", "ingest worker did not stop in 5s")
            rt_ref = weakref.ref(old_engine._rt)
            self._state.engine = None
            old_engine = None
            gc.collect()
            if rt_ref() is not None:
                # C++ 连接没释放：不能在同一进程里开第二条写连接
                logger.warning("old runtime still referenced after switch")
        try:
            new_engine = DashboardEngine(new_cfg)
        except Exception as exc:
            # 新世界打不开：回到旧世界
            self._state.engine = DashboardEngine(old_cfg)
            self._start_workers(self._state.engine, old_cfg)
            raise WorldSwitchError("world_open_failed", str(exc)) from exc
        self._state.config = new_cfg
        self._state.engine = new_engine
        self._start_workers(new_engine, new_cfg)
        reg = _core.world_set_active(reg, name)
        self.save(reg)
```

`_start_workers(engine, cfg)`：只有 `self.workers_enabled` 为 True 时才动作——当 `cfg.tick_interval_s > 0` 时调用 `engine.start_background_tick(cfg.tick_interval_s, self.on_tick)`，然后调用 `engine.start_ingest_worker()`。`workers_enabled`（默认 False）和 `on_tick`（默认 None）是 WorldManager 的公开属性，由 `app.py` 的 lifespan 在启动后台线程之后赋值：`app.state.worlds.on_tick = _on_tick`、`app.state.worlds.workers_enabled = True`。这样直接构造 `TestClient(app)`、不跑 lifespan 的测试里，切换世界不会凭空起线程，与现有「无 lifespan 就无后台线程」的行为一致。`_restart_workers(engine)` 即 `_start_workers(engine, self._state.config)`。

**已知限制（写进 `activate` 的 docstring）**：`/ws/converse` 的锁外生成阶段持有旧引擎的引用，切换只等得到持锁段。若切换时恰有一轮对话在锁外生成，它会在旧引擎上完成提交（写进旧世界，这是正确的归属），旧 Runtime 在它结束前不会被回收，`rt_ref()` 非空时只记 warning 不报错。SQLite 本身允许多连接，所以即使立刻切回同一世界也不会损坏数据，只是暂时违反「单写连接」的进程内约定。

`dataclasses.replace(old_cfg)` 会复制配置，但 `config_path` 字段需要保留。它是 dataclass 字段，`replace` 会原样带过去，这一点要写测试确认。

**为什么新世界不改 `starling.json`**：活动世界记录在注册表的 `active` 字段，`starling.json` 里的 `db_path` 和 `tenant` 保持为默认世界的值。重启时由 `bootstrap_worlds` 根据注册表改写 config。这样可以保证设置页保存配置时不会把活动世界写回 `starling.json`。设置页会调用 `cfg.save()`，它序列化的是 `app.state.config`，其中 `db_path` 已经是活动世界的路径。**这一点必须处理**：在 `routes/config.py` 的两处 `cfg.save()` 之前，用 `dataclasses.replace(cfg, db_path=<default 世界的 db_path>, tenant=<default 世界的 tenant>)` 生成一份副本再保存。为此在 `WorldManager` 上加 `def persistable_config(self, cfg) -> DashboardConfig`，`routes/config.py` 改为 `request.app.state.worlds.persistable_config(cfg).save()`。`app.state.worlds` 不存在时（测试直接构造 app），回退到 `cfg.save()`。

- [ ] **Step 1：写失败的测试**

在 `tests/python/test_dashboard_worlds.py` 追加：

```python
import gc
import weakref

from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine
from starling.dashboard.world_manager import (WorldManager, WorldSwitchError,
                                              bootstrap_worlds, registry_path_for)

_STUB = ('[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob",'
         '"predicate":"responsible_for","object":"auth","modality":"BELIEVES",'
         '"polarity":"POS","nesting_depth":0}]')


def _cfg(tmp_path):
    return DashboardConfig(db_path=str(tmp_path / "dashboard.db"), token="",
                           tick_interval_s=0, source_lane_enabled=False,
                           ingest_spool_path=str(tmp_path / "spool"))


class _State:
    """最小 app.state 替身：WorldManager 只用 .engine 和 .config。"""
    def __init__(self, cfg):
        self.config = cfg
        self.engine = None


def _manager(tmp_path):
    cfg = _cfg(tmp_path)
    reg_path = bootstrap_worlds(cfg)
    state = _State(cfg)
    state.engine = DashboardEngine(cfg)
    return WorldManager(state, reg_path), state


def _remember(engine, text):
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(_STUB, True, "")
    engine.llm = fake
    return engine.remember(text)


def test_registry_path_defaults_next_to_db(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    assert registry_path_for(_cfg(tmp_path)) == str(tmp_path / "worlds.json")
    monkeypatch.setenv("STARLING_WORLDS_REGISTRY", str(tmp_path / "x" / "r.json"))
    assert registry_path_for(_cfg(tmp_path)) == str(tmp_path / "x" / "r.json")


def test_bootstrap_rewrites_config_to_active_world(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    cfg = _cfg(tmp_path)
    reg_path = bootstrap_worlds(cfg)
    reg = _core.world_load_registry(reg_path)
    reg = _core.world_create(reg, str(tmp_path), "sim-1", "", "2026-10-25T01:00:00Z")["registry"]
    reg = _core.world_set_active(reg, "sim-1")
    _core.world_save_registry(reg_path, reg)
    cfg2 = _cfg(tmp_path)
    bootstrap_worlds(cfg2)
    assert cfg2.tenant == "sim-1"
    assert cfg2.db_path.endswith("worlds/sim-1/world.db")


def test_activate_switches_engine_and_isolates_data(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    _remember(state.engine, "Bob owns auth")
    mgr.create("sim-1", "")
    old_rt = weakref.ref(state.engine._rt)
    mgr.activate("sim-1")
    gc.collect()
    assert old_rt() is None, "旧 Runtime 必须被释放（否则同文件会有两条写连接）"
    assert state.config.tenant == "sim-1"
    assert mgr.load()["active"] == "sim-1"
    # 新世界是空的
    con = sqlite3.connect(f"file:{state.config.db_path}?mode=ro", uri=True)
    assert con.execute("SELECT COUNT(*) FROM engrams").fetchone()[0] == 0
    con.close()
    # 切回默认世界，原数据仍在
    mgr.activate("default")
    con = sqlite3.connect(f"file:{state.config.db_path}?mode=ro", uri=True)
    assert con.execute("SELECT COUNT(*) FROM engrams").fetchone()[0] == 1
    con.close()


def test_activate_unknown_world(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, _state = _manager(tmp_path)
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("nope")
    assert ei.value.code == "world_not_found"


def test_activate_rolls_back_when_new_world_fails_to_open(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    # 让新世界的库文件是一个目录：SqliteAdapter.open 必然失败
    reg = mgr.load()
    import os
    os.makedirs(reg["worlds"]["sim-1"]["db_path"])
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("sim-1")
    assert ei.value.code == "world_open_failed"
    assert state.engine is not None
    assert state.config.tenant == "default"
    assert mgr.load()["active"] == "default"


def test_activate_refuses_when_ingest_will_not_stop(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    monkeypatch.setattr(state.engine, "quiesce", lambda timeout_s=5.0: False)
    with pytest.raises(WorldSwitchError) as ei:
        mgr.activate("sim-1")
    assert ei.value.code == "ingest_busy"
    assert mgr.load()["active"] == "default"


def test_quiesce_stops_threads(tmp_path):
    cfg = _cfg(tmp_path)
    eng = DashboardEngine(cfg)
    eng.start_background_tick(60.0)
    eng.start_ingest_worker(poll_interval_s=60.0)
    assert eng.quiesce() is True
    assert eng._tick_thread is None and eng._ingest_thread is None


def test_persistable_config_keeps_default_world(tmp_path, monkeypatch):
    monkeypatch.delenv("STARLING_WORLDS_REGISTRY", raising=False)
    mgr, state = _manager(tmp_path)
    mgr.create("sim-1", "")
    mgr.activate("sim-1")
    out = mgr.persistable_config(state.config)
    assert out.db_path == str(tmp_path / "dashboard.db")
    assert out.tenant == "default"
    assert state.config.tenant == "sim-1"      # 运行时 config 不被改动
```

- [ ] **Step 2：确认失败**

```bash
cd <worktree> && .venv/bin/python -m pytest tests/python/test_dashboard_worlds.py -q 2>&1 | tail -3
```

预期：`ModuleNotFoundError: No module named 'starling.dashboard.world_manager'`。

- [ ] **Step 3：实现 `quiesce`**

在 `engine.py` 的 `stop_ingest_worker` 之后加：

```python
    def quiesce(self, timeout_s: float = 5.0) -> bool:
        """停后台 tick 与摄入线程（世界切换前用）。两个线程都确认退出返回 True；
        任一线程 join 超时仍存活返回 False——调用方据此拒绝切换（ingest_busy）。
        stop_* 不管 join 成败都会清句柄，所以先留住线程引用，事后再判 is_alive。"""
        ingest, tick = self._ingest_thread, self._tick_thread
        self.stop_ingest_worker()
        self.stop_background_tick()
        alive = [t for t in (ingest, tick) if t is not None and t.is_alive()]
        if alive:
            # 句柄已被 stop_* 清掉；放回去，让调用方重启前能看到它们还在跑
            self._ingest_thread = ingest if ingest is not None and ingest.is_alive() else None
            self._tick_thread = tick if tick is not None and tick.is_alive() else None
            return False
        return True
```

`stop_*` 里的 join 超时现在写死为 5.0 秒，`timeout_s` 参数暂时只为接口预留。在 docstring 里写明这一点，不要额外扩展 `stop_*` 的签名。

- [ ] **Step 4：实现 `world_manager.py`**

按 Interfaces 和切换算法实现。日志用 `logging.getLogger(__name__)`。`create` 和 `delete` 都在 `self.lock` 内完成三步：`load`、调用 `_core.world_*`、`save`。`take_snapshot` 在拍快照前检查 `self._state.config.vector_backend == "zvec"`，满足时抛 `_core.WorldStoreError`。这个异常在 Python 侧无法直接构造，所以改为抛 `WorldSwitchError("snapshot_unsupported_backend")`，由路由统一映射成 409。`now_iso` 用 `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`。

- [ ] **Step 5：接进 `app.py`**

在 `create_app` 中、`config.validate_source_lane()` 之后加。必须放在 `create_app` 内部：生产入口 `scripts/run_dashboard.py` 先调 `create_app(cfg)`，之后才 `DashboardEngine(cfg)`，且两者共用同一个 cfg 对象，所以原地改写 config 后，引擎自然打开活动世界的库：

```python
    from starling.dashboard.world_manager import WorldManager, bootstrap_worlds
    registry_path = bootstrap_worlds(config)   # 原地把 config 改成活动世界
```

在 `app.state.engine = engine` 之后加：

```python
    app.state.worlds = WorldManager(app.state, registry_path)
```

lifespan 中定义 `_on_tick` 后，赋值 `app.state.worlds.on_tick = _on_tick`。tick 关闭时保持为 None，切换后也就不会启动 tick。

**`engine` 参数被外部注入时**（测试中常见），`bootstrap_worlds` 仍会执行，但测试传入的 `db_path` 在临时目录下，注册表会建在同一个临时目录里，不会碰到用户真实的 `~/.starling`。`conftest.py` 只隔离了 spool，没有隔离注册表，所以要在 `conftest.py` 的 `isolate_dashboard_ingest_spool` fixture 里加一行：

```python
    monkeypatch.setenv("STARLING_WORLDS_REGISTRY", str(tmp_path / "worlds.json"))
```

**注意**：上面的测试用例都会先 `monkeypatch.delenv("STARLING_WORLDS_REGISTRY")`，以验证默认路径的推导。这些用例里注册表落在 `tmp_path/worlds.json`，因为 `_cfg` 的 `db_path` 位于 `tmp_path` 下。

- [ ] **Step 6：`routes/config.py` 保存时写回默认世界**

把两处 `cfg.save()` 改成：

```python
        worlds = getattr(request.app.state, "worlds", None)
        (worlds.persistable_config(cfg) if worlds is not None else cfg).save()
```

在 `test_dashboard_worlds.py` 里追加测试：活动世界为 `sim-1` 时调用 `POST /api/config`，之后读取 `starling.json`，断言其中的 `db_path` 和 `tenant` 仍是默认世界的值。请求体按 `tests/python/test_dashboard_config_routes.py` 中已有的最小合法 body 构造，执行者需要先读那个文件找到现成的写法。

- [ ] **Step 7：运行测试与全量 pytest**

```bash
cd <worktree> && .venv/bin/python -m pytest tests/python/test_dashboard_worlds.py -q 2>&1 | tail -3
cd <worktree> && .venv/bin/python -m pytest tests/python -q -x -p no:cacheprovider 2>&1 | tail -5
```

预期：worlds 测试全部通过，全量 pytest 没有新增失败。已知环境问题：反向 DNS 查询 `getfqdn` 变慢时会有 6 个超时用例变红，这与本改动无关。

- [ ] **Step 8：提交**

```bash
git add python/starling/dashboard/world_manager.py python/starling/dashboard/engine.py python/starling/dashboard/app.py python/starling/dashboard/routes/config.py tests/python/test_dashboard_worlds.py tests/python/conftest.py
git commit -F - <<'MSG'
feat(world): 世界切换——引擎生命周期与注册表引导（W1）

切换 = 拿旧引擎锁等在飞请求 → quiesce（停 tick/摄入，5 秒停不下回
ingest_busy）→ 丢引用 + gc.collect 释放 C++ 写连接 → 建新引擎；新世界
打不开就回到旧世界。close() 本身不释放连接（实测 fd 4→4，del+gc 后
4→0），所以必须靠丢引用。活动世界只记在注册表，starling.json 永远写
默认世界，设置页保存不会把活动世界写进去。

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

---

### Task 5：`/api/worlds` 路由

**Files:**
- Create: `python/starling/dashboard/routes/worlds.py`
- Modify: `python/starling/dashboard/app.py`（`include_router`）
- Modify: `tests/python/test_dashboard_worlds.py`（追加）

**Interfaces:**
- Consumes：T4 的 `WorldManager`、`WorldSwitchError`，T3 的 `_core.world_stats` 和 `_core.world_store_error_code`。
- Produces：本计划开头的 HTTP 契约，逐字遵守。

错误码到 HTTP 状态的映射（写成模块级常量）：

```python
_STATUS = {
    "invalid_world_name": 400, "confirm_mismatch": 400,
    "world_not_found": 404, "snapshot_not_found": 404,
    "world_exists": 409, "world_protected": 409, "ingest_busy": 409,
    "snapshot_unsupported_backend": 409, "invalid_retention": 409,
    "insufficient_disk": 507,
    "world_open_failed": 500, "snapshot_failed": 500, "registry_corrupt": 500,
}
```

所有处理函数都用 `await to_thread.run_sync(partial(...))` 调用 WorldManager（和 `commands.py` 的写法一致），因为切换和快照都是阻塞操作。

`WorldRow` 的组装：对每个世界调用 `_core.world_stats(entry["db_path"], entry["tenant"])`（只读，不打开引擎），`snapshots` 取 `len(reg["snapshots"].get(name, []))`，`snapshot_bytes` 取各快照 `size_bytes` 之和，`active` 取 `name == reg["active"]`。

`DELETE /api/worlds/{name}` 的 `confirm` 是 query 参数。`confirm != name` 时返回 400 `confirm_mismatch`，此时不调用 manager。

- [ ] **Step 1：写失败的测试**

追加：

```python
def _client(tmp_path):
    cfg = _cfg(tmp_path)
    app = create_app(cfg)
    return TestClient(app), app


def test_routes_list_create_activate_delete(tmp_path):
    client, app = _client(tmp_path)
    body = client.get("/api/worlds").json()
    assert body["active"] == "default" and body["snapshot_retention"] == 5
    assert [w["name"] for w in body["worlds"]] == ["default"]

    assert client.post("/api/worlds", json={"name": "Bad"}).json()["detail"] == "invalid_world_name"
    row = client.post("/api/worlds", json={"name": "sim-1", "label": "模拟"}).json()
    assert row["name"] == "sim-1" and row["active"] is False and row["engrams"] == 0
    assert client.post("/api/worlds", json={"name": "sim-1"}).status_code == 409

    r = client.post("/api/worlds/sim-1/activate")
    assert r.status_code == 200 and r.json() == {"active": "sim-1"}
    assert app.state.config.tenant == "sim-1"
    assert client.post("/api/worlds/nope/activate").status_code == 404

    r = client.delete("/api/worlds/sim-1", params={"confirm": "sim-1"})
    assert r.status_code == 409 and r.json()["detail"] == "world_protected"
    client.post("/api/worlds/default/activate")
    r = client.delete("/api/worlds/sim-1", params={"confirm": "wrong"})
    assert r.status_code == 400 and r.json()["detail"] == "confirm_mismatch"
    r = client.delete("/api/worlds/sim-1", params={"confirm": "sim-1"})
    assert r.status_code == 200
    assert [w["name"] for w in client.get("/api/worlds").json()["worlds"]] == ["default"]


def test_routes_snapshots(tmp_path):
    client, app = _client(tmp_path)
    app.state.engine = DashboardEngine(app.state.config)   # 建库
    snap = client.post("/api/worlds/default/snapshots", json={"note": "n1"}).json()
    assert snap["kind"] == "manual" and snap["note"] == "n1" and snap["size_bytes"] > 0
    listed = client.get("/api/worlds/default/snapshots").json()["snapshots"]
    assert [s["id"] for s in listed] == [snap["id"]]
    assert client.get("/api/worlds").json()["worlds"][0]["snapshots"] == 1
    assert client.delete(f"/api/worlds/default/snapshots/{snap['id']}").status_code == 200
    assert client.delete("/api/worlds/default/snapshots/missing").status_code == 404
    assert client.post("/api/worlds/nope/snapshots", json={}).status_code == 404


def test_routes_snapshot_refused_for_zvec(tmp_path):
    client, app = _client(tmp_path)
    app.state.config.vector_backend = "zvec"
    r = client.post("/api/worlds/default/snapshots", json={})
    assert r.status_code == 409 and r.json()["detail"] == "snapshot_unsupported_backend"


def test_routes_require_token(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.token = "s3cret"
    client = TestClient(create_app(cfg))
    assert client.get("/api/worlds").status_code == 401
    assert client.get("/api/worlds", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_routes_never_accept_paths(tmp_path):
    client, _app = _client(tmp_path)
    # 名称校验本身就挡掉了路径；这里钉住它，防止将来放宽。
    for evil in ("../x", "a/b", "/abs"):
        assert client.post("/api/worlds", json={"name": evil}).status_code in (400, 404, 422)
```

- [ ] **Step 2：确认失败**

```bash
cd <worktree> && .venv/bin/python -m pytest tests/python/test_dashboard_worlds.py -q -k routes 2>&1 | tail -3
```

预期：404 Not Found，因为路由还没挂载。

- [ ] **Step 3：实现 `routes/worlds.py`**

```python
"""/api/worlds：世界注册表与快照（W1/W2）。

写操作经 WorldManager（世界管理锁内），统计只读查各世界库、不开引擎。
设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md §9
"""
from __future__ import annotations

from functools import partial

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from starling import _core
from starling.dashboard.world_manager import WorldSwitchError

_STATUS = {...}   # 见上


class CreateWorldBody(BaseModel):
    name: str
    label: str = ""


class SnapshotBody(BaseModel):
    note: str = ""


def _fail(code: str) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(code, 500), detail=code)


def _world_row(reg: dict, name: str) -> dict:
    entry = reg["worlds"][name]
    stats = _core.world_stats(entry["db_path"], entry["tenant"])
    snaps = reg.get("snapshots", {}).get(name, [])
    return {"name": name, "label": entry.get("label", ""), "tenant": entry["tenant"],
            "created_at": entry.get("created_at", ""), "active": name == reg["active"],
            "db_bytes": stats["db_bytes"], "live_bytes": stats["live_bytes"],
            "statements": stats["statements"], "engrams": stats["engrams"],
            "snapshots": len(snaps), "snapshot_bytes": sum(s["size_bytes"] for s in snaps)}


def _snapshot_row(snap: dict) -> dict:
    return {k: snap[k] for k in ("id", "kind", "reason", "note", "created_at",
                                 "world_time", "size_bytes")}


def build_worlds_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    async def _call(request: Request, fn, *args):
        mgr = request.app.state.worlds
        try:
            return await to_thread.run_sync(partial(getattr(mgr, fn), *args))
        except WorldSwitchError as exc:
            raise _fail(exc.code) from exc
        except _core.WorldStoreError as exc:
            raise _fail(_core.world_store_error_code(exc)) from exc

    @router.get("/worlds")
    async def list_worlds(request: Request):
        reg = await _call(request, "load")
        rows = await to_thread.run_sync(lambda: [_world_row(reg, n) for n in sorted(reg["worlds"])])
        return {"active": reg["active"], "default": reg["default"],
                "snapshot_retention": reg["snapshot_retention"], "worlds": rows}

    # 其余 6 个路由按契约逐一实现。activate 和 snapshot 成功后调用
    # request.app.state.ws_manager.broadcast({...})（见契约中的 WebSocket 部分）。
    return router
```

在 `app.py` 中，`include_router(build_config_router(...))` 之后加：

```python
    from starling.dashboard.routes.worlds import build_worlds_router
    app.include_router(build_worlds_router(require_token))
```

- [ ] **Step 4：运行测试**

```bash
cd <worktree> && .venv/bin/python -m pytest tests/python/test_dashboard_worlds.py -q 2>&1 | tail -3
```

预期：全部通过。

- [ ] **Step 5：全量回归**

```bash
cd <worktree> && .venv/bin/python -m pytest tests/python -q -p no:cacheprovider 2>&1 | tail -5
cd <worktree>/build && ../.venv/bin/ctest -j8 2>&1 | tail -3
```

预期：两者都没有新增失败。

- [ ] **Step 6：提交**

```bash
git add python/starling/dashboard/routes/worlds.py python/starling/dashboard/app.py tests/python/test_dashboard_worlds.py
git commit -F - <<'MSG'
feat(world): /api/worlds 路由（列表/新建/切换/删除/快照）

统计只读查各世界库，不开引擎——列 5 个世界不用建 5 个引擎。
删除须 confirm=<name>；default 与活动世界不可删。zvec 后端拒绝快照。

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

---

### Task 6：前端数据层与导航

**Files:**
- Create: `dashboard/web/src/lib/worlds.ts`
- Create: `dashboard/web/src/lib/worlds.test.ts`
- Modify: `dashboard/web/src/lib/nav.ts`
- Modify: `dashboard/web/src/lib/nav.test.ts`
- Modify: `dashboard/web/src/lib/components/NavIcon.svelte`
- Modify: `dashboard/web/src/lib/ws.ts`

**Interfaces:**
- Consumes：本计划开头的 HTTP 契约（不依赖后端代码）。
- Produces（T7 页面使用）：

```ts
export type WorldRow = {
	name: string; label: string; tenant: string; created_at: string; active: boolean;
	db_bytes: number; live_bytes: number; statements: number; engrams: number;
	snapshots: number; snapshot_bytes: number;
};
export type SnapshotRow = {
	id: string; kind: 'auto' | 'manual'; reason: string; note: string;
	created_at: string; world_time: string; size_bytes: number;
};
export type WorldsData = {
	active: string; default: string; snapshot_retention: number; worlds: WorldRow[];
};
export const WORLD_NAME_RE: RegExp;            // /^[a-z0-9][a-z0-9_-]{0,31}$/
export function isValidWorldName(name: string): boolean;
export function formatBytes(n: number): string;   // 0→"0 B"，1536→"1.5 KB"，57*2**20→"57.0 MB"
export const worldsApi: {
	list(): Promise<WorldsData>;
	create(name: string, label?: string): Promise<WorldRow>;
	activate(name: string): Promise<{ active: string }>;          // timeoutMs 60_000
	remove(name: string, confirm: string): Promise<{ deleted: string }>;
	snapshots(name: string): Promise<{ snapshots: SnapshotRow[] }>;
	snapshot(name: string, note?: string): Promise<SnapshotRow>;  // timeoutMs 120_000
	removeSnapshot(name: string, id: string): Promise<{ deleted: string }>;
};
// 错误码 → 中文提示（T7 的 toast 用）
export function worldErrorMessage(detail: string): string;
```

`worldErrorMessage` 的映射：

| detail | 文案 |
|---|---|
| `invalid_world_name` | 世界名只能用小写字母、数字、下划线和连字符，最长 32 个字符 |
| `world_exists` | 同名世界已存在 |
| `world_not_found` | 世界不存在 |
| `world_protected` | 默认世界和当前活动世界不能删除 |
| `confirm_mismatch` | 输入的名称与世界名不一致 |
| `ingest_busy` | 摄入任务正在进行，暂时不能切换，请稍后再试 |
| `world_open_failed` | 新世界打不开，已留在原世界 |
| `snapshot_unsupported_backend` | 当前向量后端（zvec）不支持快照 |
| `insufficient_disk` | 磁盘空间不足，快照需要至少 3 倍于数据量的可用空间 |
| 其他 | 操作失败：`<detail>` |

`ApiError.message` 的格式是 `"<status> <detail>"`（见 `api.ts`），T7 需要从中提取 detail。所以再导出 `export function apiDetail(err: unknown): string`：如果是 ApiError，取 message 第一个空格之后的部分，否则返回 `String(err)`。

所有路径段都用 `encodeURIComponent`，`remove` 的 confirm 用 `?confirm=${encodeURIComponent(confirm)}`。

**导航**：在 `NAV_GROUPS` 中「总览」与「原始数据 · 证据」之间插入：

```ts
	{
		// W1/W2 — 世界是比 engram 更上游的划分（一个世界 = 一个库文件 + 一个租户），
		// 故排在「原始数据 · 证据」之前。设计：2026-10-25-world-scene-management-design.md §9。
		title: '世界 · 会话',
		items: [{ href: '/worlds', label: '世界', icon: 'globe' }]
	},
```

`nav.test.ts` 第 8 行的用例标题改为 `'has 12 groups in memory-flow order, 世界·会话 then 原始数据·证据 between 总览 and 对话'`，期望数组在 `'总览'` 之后插入 `'世界 · 会话'`，并新增一个用例 `it('surfaces /worlds', ...)`。

**图标**：在 `NavIcon.svelte` 的 `{#if}` 链中加一个分支（lucide 的 globe 图标）：

```svelte
	{:else if name === 'globe'}
		<circle cx="12" cy="12" r="10" /><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" /><path d="M2 12h20" />
```

**ws 词表**：`WS_EVENT_TYPES` 末尾追加 `'world_switched'` 和 `'snapshot_created'`，并在注释里说明这两个事件来自 `routes/worlds.py`。`world_switched` 意味着整个数据源变了，各页都应该刷新。`mutatesMemory` 已经把除 `recall` 之外的事件都视为会改动数据，所以不用改。`lib/feed.ts` 的 switch 有 `default` 分支，不改也不会报错，但要在 feed 里加两条可读的文案：`world_switched` 显示「切换到世界 X」，`snapshot_created` 显示「世界 X 拍了快照」。执行者需要先读 `feed.ts` 中 `memory_cleared` 分支的写法，再照着补上，并在 `feed.test.ts` 加对应用例。

- [ ] **Step 1：写失败的测试**

`dashboard/web/src/lib/worlds.test.ts`：

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as tok from './token';
import { ApiError } from './api';
import {
	worldsApi, isValidWorldName, formatBytes, worldErrorMessage, apiDetail
} from './worlds';

let calls: Array<[string, RequestInit]> = [];
beforeEach(() => {
	calls = [];
	vi.spyOn(tok, 'getToken').mockReturnValue('');
	globalThis.fetch = vi.fn(async (p: string, init: RequestInit) => {
		calls.push([p, init]);
		return new Response(JSON.stringify({ ok: 1 }), { status: 200 });
	}) as unknown as typeof fetch;
});

describe('世界名校验（与后端 is_valid_world_name 同一规则）', () => {
	it.each(['default', 'sim-1', 'a_b', '0abc', 'a'.repeat(32)])('接受 %s', (n) =>
		expect(isValidWorldName(n)).toBe(true));
	it.each(['', '-x', 'Up', 'a b', '../x', 'a/b', 'a'.repeat(33)])('拒绝 %s', (n) =>
		expect(isValidWorldName(n)).toBe(false));
});

describe('formatBytes', () => {
	it('格式化', () => {
		expect(formatBytes(0)).toBe('0 B');
		expect(formatBytes(1536)).toBe('1.5 KB');
		expect(formatBytes(57 * 2 ** 20)).toBe('57.0 MB');
		expect(formatBytes(2.4 * 2 ** 30)).toBe('2.4 GB');
	});
});

describe('worldsApi 路径与方法', () => {
	it('list/create/activate/remove/snapshot', async () => {
		await worldsApi.list();
		await worldsApi.create('sim-1', '模拟');
		await worldsApi.activate('sim-1');
		await worldsApi.remove('sim-1', 'sim-1');
		await worldsApi.snapshots('sim-1');
		await worldsApi.snapshot('sim-1', 'n');
		await worldsApi.removeSnapshot('sim-1', 'id 1');
		expect(calls.map(([p, i]) => `${i.method ?? 'GET'} ${p}`)).toEqual([
			'GET /api/worlds',
			'POST /api/worlds',
			'POST /api/worlds/sim-1/activate',
			'DELETE /api/worlds/sim-1?confirm=sim-1',
			'GET /api/worlds/sim-1/snapshots',
			'POST /api/worlds/sim-1/snapshots',
			'DELETE /api/worlds/sim-1/snapshots/id%201'
		]);
		expect(JSON.parse(String(calls[1][1].body))).toEqual({ name: 'sim-1', label: '模拟' });
		expect(JSON.parse(String(calls[5][1].body))).toEqual({ note: 'n' });
	});
});

describe('错误文案', () => {
	it('已知码与兜底', () => {
		expect(worldErrorMessage('ingest_busy')).toContain('摄入');
		expect(worldErrorMessage('insufficient_disk')).toContain('3 倍');
		expect(worldErrorMessage('weird')).toBe('操作失败：weird');
	});
	it('从 ApiError 提取 detail', () => {
		expect(apiDetail(new ApiError(409, '/api/worlds', '409 world_exists'))).toBe('world_exists');
		expect(apiDetail(new Error('x'))).toBe('Error: x');
	});
});
```

- [ ] **Step 2：确认失败**

```bash
cd <worktree>/dashboard/web && npx vitest run src/lib/worlds.test.ts src/lib/nav.test.ts 2>&1 | tail -6
```

预期：`worlds.ts` 不存在；nav 用例期望 12 组，实际只有 11 组。

- [ ] **Step 3：实现**

按 Interfaces 写 `worlds.ts`，复用 `api` 的 `get`、`post`、`del`。然后改 nav、图标、ws 词表和 feed。

- [ ] **Step 4：跑前端三道门**

```bash
cd <worktree>/dashboard/web && npx vitest run 2>&1 | tail -4 && npm run check 2>&1 | tail -3 && npm run build 2>&1 | tail -3
```

预期：vitest 全部通过，svelte-check 0 errors，build 成功。

- [ ] **Step 5：提交**

```bash
git add dashboard/web/src/lib/worlds.ts dashboard/web/src/lib/worlds.test.ts dashboard/web/src/lib/nav.ts dashboard/web/src/lib/nav.test.ts dashboard/web/src/lib/components/NavIcon.svelte dashboard/web/src/lib/ws.ts dashboard/web/src/lib/feed.ts dashboard/web/src/lib/feed.test.ts
git commit -F - <<'MSG'
feat(web): 世界数据层、导航组「世界 · 会话」与 ws 事件

世界名校验与后端同一正则；错误码映射成中文提示。导航组排在
「原始数据 · 证据」之前——世界是比 engram 更上游的划分。

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

---

### Task 7：`/worlds` 页面

**Files:**
- Create: `dashboard/web/src/routes/worlds/+page.svelte`
- Create: `dashboard/web/src/routes/worlds/page.test.ts`

**Interfaces:**
- Consumes：T6 的 `worldsApi`、`WorldRow`、`SnapshotRow`、`formatBytes`、`isValidWorldName`、`worldErrorMessage`、`apiDetail`。UI 组件来自 `$lib/components/ui`（`Button`、`Input`、`Field`、`Card`、`Badge`、`EmptyState`、`Skeleton`、`ConfirmDialog`、`Drawer`），另外用 `PageHeader`、`createQuery`、`toast`、`lastWsEvent`、`mutatesMemory`。

**页面结构**：

1. `PageHeader`：标题「世界」，副标题「一个世界 = 一个数据库文件 + 一个租户。切换世界会重建引擎；快照是该世界库的紧凑只读副本。」
2. **世界列表**：每个世界一张 `Card`，内容如下：
   - 标题：`name`，`label` 不为空时显示为「name · label」。活动世界加 `Badge tone="brand"` 显示「当前」，默认世界加 `Badge tone="neutral"` 显示「默认」。
   - 统计行：语句 N · 原始数据 N · 活数据 `formatBytes(live_bytes)` · 文件 `formatBytes(db_bytes)` · 快照 N 份（`formatBytes(snapshot_bytes)`）
   - 按钮：
     - 非活动世界显示「切换到此世界」。点击后弹 `ConfirmDialog`，标题为「切换到 X？」，说明为「切换会停止当前世界的后台维护与摄入，并重建引擎。」
     - 「快照」按钮点击后，在 Drawer 中展示该世界的快照列表。
     - 非默认且非活动的世界显示「删除」按钮。点击后打开 Drawer，里面放一个 `Input`，要求手输世界名，只有输入与名称一致时确认按钮才可用。这沿用设置页危险区的模式：前端校验一次，后端还会再校验一次。
3. **新建世界**：`Card` 内放两个 `Field` 和 `Input`（名称、显示名）。名称不合法时 `invalid` 为 true，并显示 `Field.error`。按钮在名称不合法时禁用。创建成功后 toast 并 refetch。
4. **快照 Drawer**：标题为「X 的快照」。顶部有「立即拍快照」按钮和备注输入框。列表每行显示 `created_at`、`Badge`（kind：auto 用 info 色，manual 用 neutral 色）、`world_time`（为空时显示「—」）、`formatBytes(size_bytes)`、`note`，以及「删除」按钮（经 ConfirmDialog 确认）。列表底部注明「保留最近 {snapshot_retention} 份，超出时优先清理自动快照，并至少保留 1 份自动快照作为回滚锚点。」
5. 有在途操作时禁用对应按钮（`Button loading`）。所有错误都显示 `toast.error(worldErrorMessage(apiDetail(e)))`。
6. 收到 `world_switched` 或 `snapshot_created` 事件，或者 `mutatesMemory($lastWsEvent)` 为真时，refetch 列表。
7. 切换成功后执行 `location.reload()`。其他页面都按旧世界缓存了数据，刷新整页是最可靠的做法。spec §8 要求切换后新请求都走新引擎，前端的缓存也必须清掉。

`toast` 的方法：执行者需要先读 `$lib/ui/toast.ts`，确认 `toast.success` 和 `toast.error` 的签名。

- [ ] **Step 1：写失败的测试**

`dashboard/web/src/routes/worlds/page.test.ts`（照 `routes/settings/page.test.ts` 的写法 mock `$lib/worlds`）：

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { tick } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';

const list = vi.fn();
const create = vi.fn();
const activate = vi.fn();
const remove = vi.fn();
vi.mock('$lib/worlds', async (orig) => {
	const real = await orig<typeof import('$lib/worlds')>();
	return {
		...real,
		worldsApi: {
			list: (...a: unknown[]) => list(...a),
			create: (...a: unknown[]) => create(...a),
			activate: (...a: unknown[]) => activate(...a),
			remove: (...a: unknown[]) => remove(...a),
			snapshots: vi.fn(async () => ({ snapshots: [] })),
			snapshot: vi.fn(),
			removeSnapshot: vi.fn()
		}
	};
});

import Worlds from './+page.svelte';

const settle = async () => {
	await tick();
	await Promise.resolve();
	await Promise.resolve();
	await tick();
};

const DATA = {
	active: 'default', default: 'default', snapshot_retention: 5,
	worlds: [
		{ name: 'default', label: '主世界', tenant: 'default', created_at: '', active: true,
		  db_bytes: 2_500_000_000, live_bytes: 60_000_000, statements: 3632, engrams: 101,
		  snapshots: 0, snapshot_bytes: 0 },
		{ name: 'sim-1', label: '', tenant: 'sim-1', created_at: '', active: false,
		  db_bytes: 0, live_bytes: 0, statements: 0, engrams: 0, snapshots: 0, snapshot_bytes: 0 }
	]
};

const button = (c: HTMLElement, text: string) =>
	[...c.querySelectorAll('button')].find((b) => b.textContent?.trim() === text) as
		| HTMLButtonElement
		| undefined;

describe('/worlds', () => {
	beforeEach(() => {
		list.mockReset().mockResolvedValue(DATA);
		create.mockReset();
		activate.mockReset();
		remove.mockReset();
	});

	it('列出世界，当前与默认有标记，活动世界没有切换按钮', async () => {
		const { container } = render(Worlds);
		await settle();
		expect(container.textContent).toContain('default');
		expect(container.textContent).toContain('sim-1');
		expect(container.textContent).toContain('当前');
		expect(container.textContent).toContain('默认');
		expect(container.textContent).toContain('3632');
		const switches = [...container.querySelectorAll('button')].filter(
			(b) => b.textContent?.trim() === '切换到此世界'
		);
		expect(switches.length).toBe(1);   // 只有 sim-1 有
	});

	it('世界名不合法时新建按钮禁用，且不调用 API', async () => {
		const { container } = render(Worlds);
		await settle();
		const input = container.querySelector('input[name="world-name"]') as HTMLInputElement;
		await fireEvent.input(input, { target: { value: 'Bad Name' } });
		await tick();
		const btn = button(container, '新建世界')!;
		expect(btn.disabled).toBe(true);
		await fireEvent.click(btn);
		expect(create).not.toHaveBeenCalled();
	});

	it('合法名称可以新建', async () => {
		create.mockResolvedValue({ ...DATA.worlds[1], name: 'sim-2' });
		const { container } = render(Worlds);
		await settle();
		const input = container.querySelector('input[name="world-name"]') as HTMLInputElement;
		await fireEvent.input(input, { target: { value: 'sim-2' } });
		await tick();
		await fireEvent.click(button(container, '新建世界')!);
		await settle();
		expect(create).toHaveBeenCalledWith('sim-2', '');
	});

	it('加载失败显示错误态', async () => {
		list.mockReset().mockRejectedValue(new Error('500 boom'));
		const { container } = render(Worlds);
		await settle();
		expect(container.textContent).toContain('加载失败');
	});
});
```

- [ ] **Step 2：确认失败**

```bash
cd <worktree>/dashboard/web && npx vitest run src/routes/worlds/page.test.ts 2>&1 | tail -4
```

预期：`+page.svelte` 不存在。

- [ ] **Step 3：实现页面**

按「页面结构」实现。新建表单中名称输入框的 `name` 属性设为 `"world-name"`，显示名输入框设为 `"world-label"`。

- [ ] **Step 4：跑前端三道门**

```bash
cd <worktree>/dashboard/web && npx vitest run 2>&1 | tail -4 && npm run check 2>&1 | tail -3 && npm run build 2>&1 | tail -3
```

预期：全部通过。

- [ ] **Step 5：提交**

```bash
git add dashboard/web/src/routes/worlds/+page.svelte dashboard/web/src/routes/worlds/page.test.ts
git commit -F - <<'MSG'
feat(web): /worlds 页——世界列表、切换、新建、删除、快照

切换与删除都要确认；删除须手输世界名（前后端各校验一次）。切换成功后
整页刷新——其他页按旧世界缓存了数据。

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

---

## 合并与端到端验证（由主会话执行，不派给子代理）

1. 把 `feat/world-web` 合并进 `feat/world-core`（两边文件不重叠，应当没有冲突）：`git merge --no-ff --no-commit feat/world-web` 后执行 `git commit -F -`。
2. 在 world-core worktree 跑全量门禁：`cmake --build build`、`ctest`、`cmake --install`、`pytest tests/python`，以及前端的 `npm run check`、`npx vitest run`、`npm run build`。
3. 端到端：用临时目录起一个隔离的 dashboard（`STARLING_CONFIG`、`STARLING_WORLDS_REGISTRY`、`STARLING_DASH_INGEST_SPOOL` 都指向临时目录，并 unset `OPENAI_*`）。依次执行：新建 `sim-1`、切换过去、对 `sim-1` 拍快照、切回 `default`、对 `default` 拍快照、删除 `sim-1`。每一步都检查 HTTP 响应和磁盘文件。
4. 用**生产库的副本**跑一次快照，确认 57MB 这个量级可以复现。只读打开副本，绝不碰 `~/.starling/dashboard.db` 本身。
5. 开 PR，CI 三项（cpp-build-test、python-test、static-scan）全部通过后，交用户决定是否合并。

## 不在本计划内

- W3 回滚、W4 场景清单与场景边界自动快照、W5 分叉（`§0.1` 裁定：先做完 W1+W2 后停下）。
- 生产服务的部署与重启：生产库迁移停在 36，重启会触发 0037 等迁移。这一步需要用户单独决定。
