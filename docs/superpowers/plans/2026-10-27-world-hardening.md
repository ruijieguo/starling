# 世界管理加固计划：布局约束解析后判断、惰性重建补起后台线程

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal：** 修两处 W3（PR #111）审查时另立的问题。
1. `validate_layout` 只要字面路径落在世界目录下就放行，不再看符号链接解析后的位置。结果是世界目录里指向外部的符号链接，能让 W2 的快照写入、清扫、保留策略和删快照都落到世界目录之外。
2. 引擎重开失败后，路由惰性重建出来的引擎不起 tick 和摄入线程，要重启服务才能恢复。

**分支：** `feat/world-hardening`，叠在 `feat/world-rollback`（`7c991b9`，PR #111）之上，因为两项都要改 W3 新加的代码。PR 以 `feat/world-rollback` 为 base，#111 合并后改 base 为 `main`。

**用户裁定（2026-10-27）：** 「`snapshots/` 是指向另一块盘的符号链接」这种布局不再支持。世界目录本身、非默认世界的库文件、`snapshots/` 三者，解析符号链接后都必须严格位于 `<注册表目录>/worlds/<名>` 之下，否则加载注册表时报 `registry_corrupt` 并说明原因。注册表目录本身可以是符号链接（例如整个 `~/.starling` 指到别处），这种情况照常支持。生产布局已核对：`~/.starling` 下没有符号链接，`worlds.json` 里的路径解析前后一致，所以不受影响。

## Global Constraints

- 沿用 W1+W2、W3 计划的全部全局约束：
  - 核心逻辑放在 C++，Python 只做适配；
  - 锁顺序 `manager.lock → _gate → _build_lock → engine._lock → supervisor`，不新增锁，也不新增锁边；
  - clang-tidy 要求名字 ≥3 字符、用 `contains()` 不用 `count()`；
  - 测试不碰 `~/.starling`。
- **H2 只在加载和保存时判定，不在每个操作里重查。** `WorldManager` 的每个操作都在 `self.lock` 内重新 `load()`，所以 `load_registry` 就是逐操作的判定点。`load` 与操作之间若被人改了文件系统，前提是对方已有世界目录的写权限，能直接改库，这种 TOCTOU 不在防护范围内。
- **H1 不改启动语义。** 「`tick_interval_s=0` 且启动时没有引擎」时不起摄入线程，这是已写进文档的既有行为，本计划不动。只有「运行中的引擎因失败路径被丢成 None」之后的那一次惰性重建才补起线程。
- C++ 或绑定改动后：`.venv/bin/cmake --build build && .venv/bin/cmake --install build --prefix .venv/lib/python3.14/site-packages`。clang-tidy 门禁在**提交后**跑：`CLANG_TIDY=/opt/homebrew/opt/llvm/bin/clang-tidy .venv/bin/python scripts/ci_clang_tidy_diff.py origin/main build`。

## File Structure

| 文件 | 改动 | 任务 |
|---|---|---|
| `src/governance/world_store.cpp` | `within_layout` 改为解析后判断；`validate_layout` 补世界目录本身的解析检查 | T1 |
| `include/starling/governance/world_store.hpp` | `load_registry` / `save_registry` 的注释写明布局规则 | T1 |
| `tests/cpp/test_world_store.cpp` | 布局拒绝与放行的用例；W3 镜像布局用例补一条「加载被拒」 | T1 |
| `python/starling/dashboard/world_manager.py` | 失败路径置「丢了线程」标志；`lease` 惰性重建后补起线程 | T2 |
| `python/starling/dashboard/app.py` | lifespan 关停时在 `_build_lock` 内关 `workers_enabled` | T2 |
| `tests/python/test_dashboard_worlds.py` | 失败后惰性重建起线程、无 lifespan 不起、关停后不起 | T2 |
| `docs/superpowers/specs/2026-10-25-world-scene-management-design.md` | §5.1 限制段删掉「重开失败后不起线程」；补布局规则 | T1、T2 |
| `dashboard/web/src/lib/worlds.ts` | `rollback_reopen_failed` 文案去掉「重启服务」 | T2 |

## 任务依赖

T1 → T2，顺序执行。T1 会重装 `_core`，与 T2 的 pytest 并行可能读到装了一半的扩展。

---

### Task 1：布局约束解析后判断（C++）

**Files:** `world_store.cpp`、`world_store.hpp`、`test_world_store.cpp`、设计稿。

**现状：** `within_layout(base, target)` 只要字面判断通过就返回 true；字面不通过时，再比较两侧解析后的结果（`world_store.cpp` 约 94–102 行）。`validate_layout` 对世界目录本身只做 `lexically_within(worlds_root, home)`。

**规则：**
- `within_layout(base, target)`：
  - 两侧都 `fs::weakly_canonical` 后用 `strictly_under` 判断，不再有字面通过就放行的捷径。
  - 换一种写法指向同一处的路径（`/tmp` 对 `/private/tmp`、软链过来的注册表目录），解析后两侧一致，仍然放行。
  - 解析出错（EACCES、ELOOP）时无法证明在里面，按越界处理，报 `registry_corrupt`，消息里带上错误原因。
  - 函数名和注释改成新语义，注释写明为什么不能保留字面捷径。
- `validate_layout`：
  - 在现有的 `lexically_within(worlds_root, home)` 之外，再要求 `weakly_canonical(home)` 严格位于 `weakly_canonical(worlds_root)` 之下。
  - 世界目录还不存在时（新注册表、未建目录的世界），`weakly_canonical` 照常可用，不特判。
  - 非默认世界的 `db_path`、所有世界的 `snapshot_dir` 都走新的 `within_layout`。默认世界的 `db_path` 照旧不受约束。
- `load_registry` 与 `save_registry` 都经 `validate_layout`，两边同一套规则：`load` 会拒绝的注册表，`save` 也不能写出去。
- `world_store.hpp` 里 `load_registry` / `save_registry` 的注释写明这三条布局规则，以及注册表目录本身可以是符号链接。

- [ ] **Step 1：写失败的测试**，至少包括：
  - `worlds/sim-1/snapshots` 指向外部 → `load_registry` 报 `registry_corrupt`，外部目录不变。
  - `worlds/sim-1` 本身指向外部 → `registry_corrupt`。
  - 非默认世界的库文件是指向外部的符号链接 → `registry_corrupt`。
  - `save_registry` 对上面三种布局同样报 `registry_corrupt`，原文件不被覆盖。
  - 放行：注册表目录经符号链接打开（现有 `LoadsThroughSymlinkedRegistryDir` 不改，必须仍过）；`snapshots/` 指向同一世界目录内的另一子目录；世界目录还不存在。
  - W3 用例 `ArchiveStaysInWorldDirWhenSnapshotsDirPointsOutside` 保留原断言（它直接调 `rollback_world`，不经 `load`），再补一条：同一布局下 `load_registry` 报 `registry_corrupt`。
- [ ] **Step 2：RED**，确认失败原因正确（报的是 `<no throw>`，不是编译错误）。
- [ ] **Step 3：实现。**
- [ ] **Step 4：GREEN**：`ctest -R 'World|RegistryValidation'` 全过，全量 `ctest -j8` 全过（基线 1597）；`tests/python/test_dashboard_worlds.py` 全过（基线 144）。
- [ ] **Step 5：回退验证**：把字面捷径加回去，第一条用例必须失败。
- [ ] **Step 6：更新设计稿**：§5.1 的归档段和 §12 写明布局规则；W3 计划里「快照放在另一块盘」的说法，改为「整个注册表目录可以外链，世界目录内的子路径不可以」。
- [ ] **Step 7：提交**，然后跑 clang-tidy 门禁。

### Task 2：惰性重建补起后台线程（Python）

**Files:** `world_manager.py`、`app.py`、`test_dashboard_worlds.py`、`worlds.ts`（含 `.test.ts`）、设计稿。

**现状：** 有两条失败路径会把引擎留成 None：
- 切换双失败：`_rollback` 重建旧世界也失败；
- 回滚重开失败：`_reopen_live_world` 失败，包括 `rollback_reopen_failed` 和 `world_open_failed`。

之后 `lease(build=...)` 惰性建出的引擎不调 `_start_workers`。这时摄入 spool 不再被消费，tick 也停了，直到重启服务。

**规则：**
- `WorldManager` 加一个私有标志 `_workers_lost`，初始为 False。
  - 置位：上面两条失败路径把 `self._state.engine` 置为 None 的那一处置 True。这一步在切换窗口内、持 `self.lock`；窗口内 `lease` 一律拒绝，所以不会和惰性构建并发。
  - 消费：`lease` 惰性构建分支在 `_build_lock` 内建好并写回引擎之后，若 `_workers_lost` 为真，调 `self._start_workers(engine, self._state.config)`（它自己会检查 `workers_enabled`），然后清标志。
  - 只有真正新建了引擎的那次构建会消费标志；拿到已有引擎的租约不碰它。
- 成功的切换和回滚发布新引擎时，`_start_workers` 已经起过线程，此时把 `_workers_lost` 清为 False。
- **关停屏障**：lifespan 关停段现在在 `manager.lock` 内把 `workers_enabled` 置 False。改为在 `manager.lock` 内再取 `_build_lock` 后再置位，顺序与既定锁序一致。这样关停之后的惰性构建看到的是 False，不会在关停后起线程。关停之前写回的引擎，会被关停段按 `app.state.engine` 停掉。写一个 `WorldManager` 方法（例如 `disable_workers()`）给 app.py 调用，app.py 不直接碰 `_build_lock`。
- 起线程失败（例如 `start_ingest_worker` 抛错）不能让本次租约失败：记 `logger.exception`，标志保持置位，下一次惰性构建会再试。
- 前端 `rollback_reopen_failed` 的文案改为：「已回滚到快照，但引擎重开失败；页面即将刷新，若仍异常请查看服务日志」。同步修改 `worlds.test.ts`。

- [ ] **Step 1：写失败的测试**，至少包括：
  - `workers_enabled=True`，回滚替换成功但重开失败 → engine 为 None。之后发一次 `lease(build=真实构建)`：建出的引擎摄入线程在跑，`tick_interval_s>0` 时 tick 线程也在跑，标志已清。再发一次租约不会重复起线程。
  - 切换双失败（`_rollback` 重建也失败）之后，同样的断言。
  - `workers_enabled=False`（无 lifespan），失败后惰性重建 → 不起线程。
  - 关停屏障：调用 `disable_workers()` 之后再惰性重建 → 不起线程。
  - 起线程抛错 → 租约照常返回引擎，标志仍置位；下一次真正新建引擎时再起。
  - 所有用例的 config 都用临时 spool（沿用 `_cfg`），测试结束时停掉线程。
- [ ] **Step 2：RED。**
- [ ] **Step 3：实现。**
- [ ] **Step 4：GREEN**：`tests/python/test_dashboard_worlds.py` 全过；全量 `pytest tests/python` 全过（基线 2890 passed / 630 skipped）；前端三门全过。
- [ ] **Step 5：回退验证**：去掉 `lease` 里的补起线程，第一条用例必须失败；去掉关停屏障里的 `_build_lock`，用确定性的方式（Event 卡住构建）证明会在关停后起线程。
- [ ] **Step 6：更新设计稿**：§5.1 和 §8.1 的限制段删掉「重开失败后惰性重建的引擎不起后台线程」，改为写明现在的行为。
- [ ] **Step 7：提交。**

## 合并与验证（主会话执行）

1. 全量门禁：ctest、pytest、前端三门、clang-tidy。
2. 隔离实例端到端：重跑 W3 的 `scenario.py`，再补一条「回滚重开失败 → 下一次命令请求 → 摄入线程恢复」。用 monkeypatch 让第一次重建失败，查 `/api/ingest/status` 或引擎线程状态。
3. 整支审查，然后开 PR（base 为 `feat/world-rollback`）。不部署。
