# 世界/场景管理 W3 实现计划：回滚语义 A（丢掉后续）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal：** 把一个世界恢复到它的某一份快照。快照之后写入的一切都丢弃。被替换掉的库不删除，改名放进该世界的 `archive/` 目录，可以手动恢复，也可以显式清理。

**Architecture：** 回滚的顺序与原子性在 C++（`world_store`，spec §10）。Python 只负责活动世界的引擎生命周期：停线程、等租约、释放旧 Runtime、调 C++、重建引擎。不改注册表格式，不加迁移。

**Spec：** `docs/superpowers/specs/2026-10-25-world-scene-management-design.md` §5.1（语义 A）、§9（API）、§10（落点）、§11（W3 验收）。

**分支：** `feat/world-rollback`，从 `origin/main` `48e9f3b` 起。前端在 `feat/world-rollback-web`（worktree `world-web`），与后端并行，只依赖下面的 HTTP 契约。

## Global Constraints

沿用 W1+W2 计划（`docs/superpowers/plans/2026-10-25-world-scene-w1-w2.md`）的全部全局约束，另加：

- 回滚不接受客户端传路径：只接受 `snapshot_id`，路径从注册表取。
- 回滚**不写注册表**。快照、世界条目都不变；被替换的库进 `archive/`。这样就没有「先动磁盘后存注册表」的分叉（Codex 第二轮 Important 4 不适用于回滚）。
- 任何一步失败，目标库必须原样留在原处（spec §11：用损坏快照、只读目录两条路测）。
- 活动世界回滚必须确认旧 Runtime 已被回收（弱引用失效）才能动文件。回收不了就拒绝（`ingest_busy`）并恢复原引擎，绝不在还有写连接时替换库文件。
- clang-tidy：本机 `/opt/homebrew/opt/llvm/bin/clang-tidy`，**提交后**跑 `CLANG_TIDY=/opt/homebrew/opt/llvm/bin/clang-tidy .venv/bin/python scripts/ci_clang_tidy_diff.py origin/main build`。名字 ≥3 字符，`contains()` 不用 `count()`，绑定里 `py::dict("k"_a=...)`。
- C++/绑定改动后：`.venv/bin/cmake --build build && .venv/bin/cmake --install build --prefix .venv/lib/python3.14/site-packages`。

## 本计划已实测的事实（2026-10-26，不必再验证）

| 事实 | 后果 |
|---|---|
| 引擎丢引用 + `gc.collect()` 后，库目录只剩主文件，`-wal` / `-shm` 被 SQLite 删除 | 回滚前引擎释放干净时，主文件就是完整的库 |
| 之后再有只读连接打开过（统计、检视路由），会留下 32 KB 的 `-shm` 和 0 字节的 `-wal` | 判据是「`-wal` 不存在或为空」，不是「两个文件都不存在」；空的 `-wal` / `-shm` 在替换后删掉 |
| 有只读连接开着时 `PRAGMA wal_checkpoint(TRUNCATE)` 返回 `(0,0,0)`，不报忙 | C++ 侧**检测不到**还开着的写连接；这个前提只能由 Python 保证（弱引用断言） |
| 同目录内 `rename` 主文件后，旧 inode 原样保留在新名字下；新复制的文件改名到原路径后，引擎能正常打开，`journal_mode` 自动回到 `wal` | 归档 = 改名，零拷贝、零额外空间；恢复 = 复制快照到 partial 再改名 |
| 快照是 `VACUUM INTO` 产物，`journal_mode=delete`、无 freelist；生产快照 84 MB | 回滚的磁盘代价 ≈ 一份快照的大小，不是库文件大小 |

## File Structure

| 文件 | 改动 | 任务 |
|---|---|---|
| `include/starling/governance/world_store.hpp` | 声明 `RollbackOptions`、`RollbackResult`、`ArchiveEntry`、`rollback_world`、`list_rollback_archives`、`purge_rollback_archives` | T1 |
| `src/governance/world_store.cpp` | 实现上述函数 | T1 |
| `tests/cpp/test_world_store.cpp` | 回滚与归档的 GoogleTest | T1 |
| `bindings/python/bind_15_world.cpp` | `world_rollback`、`world_list_archives`、`world_purge_archives` | T2 |
| `python/starling/dashboard/world_manager.py` | `rollback()`、`purge_archives()`；把「停当前引擎」从 `_swap_engine` 抽出复用 | T2 |
| `python/starling/dashboard/routes/worlds.py` | `POST /rollback`、`DELETE /archives`；`WorldRow` 加两个字段；`_STATUS` 加新码 | T2 |
| `tests/python/test_dashboard_worlds.py` | 绑定、管理器、路由测试 | T2 |
| `dashboard/web/src/lib/worlds.ts` + `.test.ts` | 类型、API、错误文案 | T3 |
| `dashboard/web/src/lib/ws.ts`、`feed.ts` | 事件 `world_rolled_back` | T3 |
| `dashboard/web/src/routes/worlds/+page.svelte` + `page.test.ts` | 快照行「回滚到此」、世界行归档数与「清理归档」 | T3 |
| `docs/superpowers/specs/2026-10-25-world-scene-management-design.md` | 状态行、§5.1 注明已实现与归档位置 | T2 |

## 任务依赖与并行

```
T1 (C++) ──> T2 (绑定 + Python + 路由)      worktree world-core，分支 feat/world-rollback
T3 (前端)                                    worktree world-web，分支 feat/world-rollback-web，与 T1/T2 并行
```

## HTTP 契约（T2 与 T3 都以此为准）

```
POST   /api/worlds/{name}/rollback   body {"snapshot_id": str, "confirm": str, "mode": "discard_after" = default}
  200 {"world": name, "snapshot_id": id, "archived": bool, "active": bool}
  400 {"detail": "confirm_mismatch"}             # confirm != name
  400 {"detail": "rollback_mode_unsupported"}    # mode 不是 discard_after（"scene" 属于 W5）
  404 {"detail": "world_not_found" | "snapshot_not_found"}
  409 {"detail": "snapshot_corrupt"}             # 快照文件缺失、打不开或 integrity_check 不过；目标库未动
  409 {"detail": "world_tenant_mismatch"}        # 快照里有别的租户的行；目标库未动
  409 {"detail": "ingest_busy"}                  # 活动世界：后台线程停不下 / 在途请求不结束 / 旧 Runtime 回收不了
  503 {"detail": "world_switching"}
  507 {"detail": "insufficient_disk"}            # 可用空间 < 2 × 快照大小
  500 {"detail": "snapshot_failed" | "internal_error"}   # 归档或替换失败，已复原目标库

DELETE /api/worlds/{name}/archives?confirm=<name>
  200 {"deleted": int}                           # 删掉的归档文件数
  400 {"detail": "confirm_mismatch"}
  404 {"detail": "world_not_found"}

WorldRow 新增：  "archives": int, "archive_bytes": int
```

WebSocket：回滚成功广播 `{"type": "world_rolled_back", "payload": {"world": name, "snapshot_id": id}}`。它属于 `mutatesMemory` 的「改变可见状态」一侧。回滚的是活动世界时，前端整页刷新（同切换）。

---

### Task 1：回滚与归档（C++）

**Files:**
- Modify: `include/starling/governance/world_store.hpp`
- Modify: `src/governance/world_store.cpp`
- Modify: `tests/cpp/test_world_store.cpp`

**Interfaces（Produces）：**

```cpp
struct RollbackOptions {
    // 测试注入用：返回可用字节数。为空时用 std::filesystem::space(dir).available。
    std::function<std::int64_t(const std::filesystem::path&)> free_space;
};

struct RollbackResult {
    std::string archive_path;   // 被替换的库现在的位置；库原本不存在时为空
    std::int64_t restored_bytes = 0;
};

// 把世界 world 的库替换成快照 snapshot_id 的内容（spec §5.1 语义 A）。
// 前提（调用方保证）：该库上没有打开的写连接——C++ 检测不到它。
// 顺序：
//   1. 取世界（world_not_found）与快照（snapshot_not_found）。
//   2. 快照路径解析符号链接后必须严格在该世界 snapshot_dir 之下（snapshot_failed）。
//   3. 只读打开快照，PRAGMA integrity_check 必须为 "ok"；文件缺失或打不开同样算
//      （snapshot_corrupt）。
//   4. verify_world_tenant(快照路径, 世界租户)（world_tenant_mismatch）。
//   5. free_space(库所在目录) < 2 × 快照文件大小 → insufficient_disk。
//   6. 把快照复制到库所在目录的 `.<库文件名>.rollback-<hex>.partial`，只读打开做
//      PRAGMA quick_check，必须为 "ok"。
//   7. 库存在时：库旁边的 `-wal` 存在且非空 → 拒绝（snapshot_failed，说明还有未合并的
//      写入或写连接），什么都不改。否则 create_directories(<世界 home>/archive)，其中
//      世界 home = snapshot_dir 的父目录；把库改名为
//      `<archive>/<库文件名>.pre-rollback-<compact_now>-<4 hex>`；再删掉库旁边的空
//      `-wal` 和 `-shm`（只读读者会留下 32 KB 的 `-shm` 与 0 字节的 `-wal`，见实测表）。
//      改名跨文件系统失败（EXDEV）时什么都没变，抛 snapshot_failed。
//   8. 把 partial 改名为库路径。
// 第 1–6 步任何失败：目标库原样不动，partial 删掉。
// 第 7 步之后失败：把归档改名回库路径（复原），删掉 partial，抛 snapshot_failed。
// 不改注册表。所有非 WorldStoreError 的异常都转成 snapshot_failed。
RollbackResult rollback_world(const Registry& reg, const std::string& world,
                              const std::string& snapshot_id, const RollbackOptions& opts);

struct ArchiveEntry {
    std::string name;            // 文件名，例如 "world.db.pre-rollback-20261026T120000Z-ab12"
    std::int64_t size_bytes = 0;
};

// 列出 <世界 home>/archive 下文件名形如 "*.pre-rollback-<YYYYMMDDTHHMMSSZ>-<4 hex>" 的
// 普通文件（跳过符号链接），按名字降序（最新在前）。目录不存在时返回空。
[[nodiscard]] std::vector<ArchiveEntry> list_rollback_archives(const Registry& reg,
                                                               const std::string& world);

// 删除 list_rollback_archives 列出的全部文件，每个都经 remove_within(archive 目录, 文件)。
// 返回删除的个数。确认越界的文件不删，抛 snapshot_failed。
std::size_t purge_rollback_archives(const Registry& reg, const std::string& world);
```

- [ ] **Step 1：写失败的测试**（`TEST(WorldRollback, …)`、`TEST(WorldArchives, …)`）。至少覆盖：
  - `RestoresSnapshotContentAndArchivesThePreviousDb`：种 2 行 engram → 拍快照 → 再种 3 行 → 回滚。库里回到 2 行；`archive_path` 存在且里面是 5 行；`archive_path` 在 `<home>/archive/` 下。
  - `RefusesCorruptSnapshotAndLeavesTargetUntouched`：把快照文件写坏 → `snapshot_corrupt`；目标库字节不变（比较内容哈希或行数）、`archive/` 不存在或为空、没有 partial 残留。
  - `RefusesMissingSnapshotFile`：删掉快照文件 → `snapshot_corrupt`，目标不动。
  - `RefusesWhenDbDirectoryIsReadOnly`：把库所在目录设成只读（`fs::permissions`）→ 抛错（`snapshot_failed`）；目标库不动；测试结束前恢复权限。若以 root 运行则 `GTEST_SKIP()`。
  - `RefusesForeignTenantSnapshot`：快照里插一行别的租户 → `world_tenant_mismatch`，目标不动。
  - `RefusesInsufficientDisk`：`free_space` 返回 1 → `insufficient_disk`，目标不动。
  - `RefusesNonEmptyWal`：在目标库旁放一个非空 `-wal` → `snapshot_failed`，目标不动。
  - `UnknownWorldAndSnapshot`：`world_not_found` / `snapshot_not_found`。
  - `RestoresIntoAWorldWhoseDbDoesNotExistYet`：库从未创建 → 回滚成功，`archive_path` 为空。
  - `RollbackDoesNotChangeTheRegistry`：调用前后 `registry_to_json(reg)` 相同（参数是 const，但要确认没有别的副作用写回文件）。
  - `ListsAndPurgesArchives`：两次回滚 → 列出 2 个、名字降序；放一个不符合模式的 `keep.txt` 和一个指向外部的符号链接 → 都不列、不删；purge 返回 2，`keep.txt` 仍在。
- [ ] **Step 2：确认失败原因正确**（断言不成立，不是编译错误——先写空桩）。
- [ ] **Step 3：实现**。复用现有 helper：`open_read_only`、`remove_within`、`strictly_under`、`random_hex`、`compact_now`、`available_bytes`、`verify_world_tenant`、`persistence::Stmt`。复制用 `fs::copy_file(..., fs::copy_options::overwrite_existing)`。
- [ ] **Step 4：GREEN**：`ctest -R "World|RegistryValidation"` 全过；全量 `ctest` 全过。
- [ ] **Step 5：回退验证**：对 3 个关键保证（损坏快照不动目标、只读目录不动目标、第 7 步后失败会复原）各做一次「去掉修复 → 用例失败 → 恢复」，记进报告。
- [ ] **Step 6：提交**，再跑 clang-tidy 门禁，有诊断就修并另起提交。

### Task 2：绑定、管理器、路由

**Files:** `bind_15_world.cpp`、`world_manager.py`、`routes/worlds.py`、`tests/python/test_dashboard_worlds.py`、设计稿。

**绑定（Produces）：**

```python
_core.world_rollback(registry: dict, world: str, snapshot_id: str) -> dict
    # {"archive_path": str, "restored_bytes": int}；释放 GIL
_core.world_list_archives(registry: dict, world: str) -> list[dict]   # [{"name", "size_bytes"}]
_core.world_purge_archives(registry: dict, world: str) -> int
```

**`WorldManager`：**

```python
def rollback(self, name: str, snapshot_id: str) -> dict:
    """{"world", "snapshot_id", "archived": bool, "active": bool}"""
def purge_archives(self, name: str) -> int:
def archives(self, name: str) -> list[dict]:
```

- 全程持 `self.lock`。`self.load()` 取注册表，世界不存在 → `WorldStoreError world_not_found`（与其他方法一致，由路由映射）。
- **非活动世界**：直接调 `_core.world_rollback`。没有引擎在写它。
- **活动世界**：在 `_switch_window()` 内：
  1. 停当前引擎：quiesce 失败 → 恢复线程、`ingest_busy`；等租约超时 → 恢复线程、`ingest_busy`。把这段从 `_swap_engine` 抽成一个私有方法供两处共用，`_swap_engine` 行为不变（现有测试全过即证明）。
  2. 丢引擎、`gc.collect()`，在 `_RUNTIME_RELEASE_GRACE_S` 内等旧 Runtime 弱引用失效。**失效不了就不动文件**：按原 config 重建引擎、起线程、抛 `ingest_busy("old runtime still referenced")`。（切换时这里只记 warning；回滚替换的是同一个库文件，必须严格。）
  3. 调 `_core.world_rollback`。抛错时 C++ 已保证目标库未动或已复原：按原 config 重建引擎、起线程，原样抛出。
  4. 成功：按原 config 重建引擎（打开时会跑迁移，快照若是旧 schema 会补齐），起线程。`app.state.config` 不变。
- 引擎重建失败（极端：恢复后的库打不开）→ 引擎留 None，抛 `WorldSwitchError("world_open_failed")`；路由下次惰性重建。
- `purge_archives`：持 `self.lock` 调 C++。

**路由：**
- `POST /api/worlds/{name}/rollback`：body `{"snapshot_id": str, "confirm": str, "mode": str = "discard_after"}`。先查 `confirm == name`、`mode == "discard_after"`（不碰 manager），再 `await _run(mgr.rollback, ...)`，成功后广播 `world_rolled_back`。
- `DELETE /api/worlds/{name}/archives?confirm=<name>`。
- `WorldRow` 加 `archives`、`archive_bytes`（`list_rollback_archives` 的个数与大小合计；读不出时 0）。
- `_STATUS` 加 `snapshot_corrupt: 409`、`rollback_mode_unsupported: 400`。

- [ ] **Step 1：写失败的测试**。至少：
  - 绑定：`world_rollback` 往返、错误码透传。
  - 非活动世界回滚：语句数回到快照时的数；归档存在；注册表不变。
  - **活动世界回滚**：`remember` 写 1 条 → 拍快照 → 再写 1 条 → `rollback` → 引擎是新的、库里回到 1 条、后台线程重启、旧 Runtime 弱引用失效；回滚后 `remember` 照常写入。
  - 活动世界 + 损坏快照：`snapshot_corrupt`；引擎重建在原库上、数据不变、线程在跑、`switching` 已清。
  - 活动世界 + 旧 Runtime 回收不了（测试里故意持一个引用）：`ingest_busy`；文件未动；引擎恢复可用。
  - 活动世界 + 在途租约不结束（`_LEASE_DRAIN_TIMEOUT_S` 调小）：`ingest_busy`；文件未动。
  - 路由：`confirm_mismatch`、`rollback_mode_unsupported`、`snapshot_not_found`、200 形状、广播帧、`WorldRow.archives`、`DELETE /archives`。
  - 切换窗口内 `POST /rollback` → 503 `world_switching`。
- [ ] **Step 2：RED**（原因正确）。
- [ ] **Step 3：实现**。
- [ ] **Step 4：GREEN**：`tests/python/test_dashboard_worlds.py` 全过；全量 `pytest tests/python` 全过（基线：2848 passed / 630 skipped）。
- [ ] **Step 5：回退验证**：活动世界的「旧 Runtime 回收不了就不动文件」与「C++ 失败后在原库上重建」各做一次。
- [ ] **Step 6：更新设计稿**：状态行写 W3 已实现；§5.1 注明归档位置 `<世界 home>/archive/`、不写注册表、失败复原。
- [ ] **Step 7：提交**；跑 clang-tidy 门禁。

### Task 3：前端（与 T1/T2 并行）

**Files:** `dashboard/web/src/lib/worlds.ts` + `.test.ts`、`ws.ts`、`feed.ts`、`routes/worlds/+page.svelte` + `page.test.ts`。

- `worlds.ts`：`WorldRow` 加 `archives: number; archive_bytes: number`；`worldsApi.rollback(name, snapshotId, confirm)`（POST，`timeoutMs: 120_000`）、`worldsApi.purgeArchives(name, confirm)`；`ERROR_MESSAGES` 加：
  - `snapshot_corrupt`：「快照文件损坏或缺失，未做任何改动」
  - `rollback_mode_unsupported`：「不支持的回滚方式」
- `ws.ts`：`WS_EVENT_TYPES` 加 `world_rolled_back`；`feed.ts` 加文案「世界 {world} 已回滚到快照 {snapshot_id}」。
- 页面：
  - 快照行加「回滚到此」按钮（danger）。点开确认框，要求手输世界名，并显示：「该世界在这份快照之后写入的所有记忆都会被丢弃。当前的库会改名保留在该世界的 archive 目录，可手动恢复。」确认后调 `rollback`；回滚的是活动世界时成功后 `location.reload()`，否则刷新列表。
  - 世界行：`archives > 0` 时显示「归档 N 份 · 大小」与「清理归档」按钮（同样手输世界名确认）。
  - 进行中禁用按钮，错误用 `worldErrorMessage` 出 toast。
- [ ] 测试先行：`worlds.test.ts`（API 方法的 URL、方法、body；两条新错误文案）、`page.test.ts`（回滚确认框需输对名字才能提交；活动世界成功后 reload；非活动世界成功后刷新列表；`archives` 为 0 时不显示清理按钮）、`ws`/`feed` 词表测试（若有，比照 `world_switched`）。
- [ ] 门禁：`npx vitest run`、`npm run check`、`npm run build`。
- [ ] 提交。

## 合并与端到端验证（主会话执行）

1. 把 `feat/world-rollback-web` 合进 `feat/world-rollback`（文件不重叠）。
2. 全量门禁：build + install、`ctest`、`pytest tests/python`、前端三门、clang-tidy 门禁。
3. 隔离实例端到端（临时目录，unset `OPENAI_*`）：新建 `sim-1` → 切过去 → 写入 → 拍快照 → 再写入 → 回滚（活动世界）→ 语句数回到快照时 → 归档存在 → 清理归档；再对非活动的 default 做一次回滚。每步查 HTTP 与磁盘。
4. 在**生产库备份的副本**上回滚一次（复制到临时目录，绝不碰 `~/.starling`），记录耗时与归档大小。
5. 整支审查 → Codex 第三方审查 → 开 PR，CI 三项通过后交用户。**不部署**：上线由用户决定。

## 不在本计划内

- 语义 B（只回滚某个场景、保留后续，需要重新摄入）与分叉：W5。
- 场景清单、场景边界自动快照、`sessions_complete`：W4。
- 从归档恢复的 UI（「撤销回滚」）：归档是普通 SQLite 文件，W3 只提供列出与清理；需要时另立任务。
- Codex 第二轮 Important 4（建/删世界、删快照先动磁盘后写注册表）：三处在注册表写失败后都可恢复且不丢未授权的数据——建世界留下空目录，再建同名照常；删世界或删快照后注册项仍在，标 `stats_error` / `missing`，可以再删一次。彻底修需要注册表事务，另立任务。
