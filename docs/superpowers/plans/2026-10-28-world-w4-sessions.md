# 世界管理 W4 实现计划：会话清单与自动快照（按会话 / 按时间）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal：** 实现设计稿 `docs/superpowers/specs/2026-10-25-world-scene-management-design.md` 的 W4，并按 2026-10-28 的用户裁定调整范围。

1. **会话清单。** 按 `session_id` 汇总 `source_unit_meta`，接口为 `GET /api/worlds/{w}/sessions`，前端新增 `/sessions` 页。
2. **自动快照，每个世界各自配置两种触发：**
   - **按会话**：某个 `session_id` 在该世界第一次写入之前，先拍一份快照。
   - **按时间**：距上一份自动快照已超过间隔、且这期间有新写入时，拍一份。
3. **快照元数据补齐**：`sessions_complete`、触发它的 `session_id`、内容标记 `content_mark`。

**分支：** `feat/world-sessions`，叠在 `feat/world-hardening`（`25290f2`，PR #112）之上。PR 的 base 填 `feat/world-hardening`。合并顺序：#111 → #112 → W4。

## 用户裁定（2026-10-28）

- **场景不是通用概念。** 陪伴机器人这类真实部署是长时程连续交互，不需要按场景组织。会话（`session_id`）只当作元数据保留，取「一次相遇」最自然；它不切断召回（这一点 2026-10-25 已裁定）。界面统一叫「会话」，不叫「场景」。
- **两种触发都实现，每个世界单独配置。**
  - 默认世界：按时间，每 24 小时一次，按会话关闭。它是日常在用的连续部署。
  - 新建世界：默认按会话，按时间关闭。创建时可以改，之后也能改。
  - 已有注册表里没有这个字段时，按上面两条补默认值。
- **自动快照失败时照常摄入，只记录失败。** 失败写日志；`/api/ingest_status` 和 `GET /api/worlds` 里给出失败计数、最近一次错误及其时间。向量后端是 zvec 时直接不拍，不计为失败。
- **后台线程只用非阻塞方式取管理锁。** 取不到时：
  - 按时间：跳过这一轮；
  - 按会话：把任务放回 spool，不计重试次数。

  这样切换和回滚不会被后台线程拖成 `ingest_busy`。

## Global Constraints

- 沿用 W1–W3 与加固计划的全局约束：
  - 核心逻辑放在 C++，Python 只做适配。
  - 锁顺序固定为 `manager.lock → _gate → _build_lock → engine._lock → supervisor`，不新增锁，也不新增锁边。
  - clang-tidy：标识符名至少 3 个字符；判断成员用 `contains()`，不用 `count()`。
  - 测试不碰 `~/.starling`，并且是确定性的：时钟可注入，用 Event，不用会抖的 sleep。
- **进程内读写活动世界库的规矩**（W3 B2）：同一进程里每一条打开活动世界库的连接，要么持引擎租约，要么持 `manager.lock`；回滚两者都会等。本计划新增的打开点按如下方式满足：
  - 自动快照和它的判断：在 `manager.lock` 内读写；
  - 会话清单路由：持租约，与 `_list_worlds` 相同。
- **默认世界升级后的第一轮检查会拍一份快照。** 原因是它按时间触发，库里有内容，又还没有自动快照。按 W3 的实测，大约 100 MB、0.4 秒。这是预期行为，要写进 PR 描述。
- C++ 或绑定改动后执行：`.venv/bin/cmake --build build && .venv/bin/cmake --install build --prefix .venv/lib/python3.14/site-packages`。clang-tidy 门禁在提交之后跑：`CLANG_TIDY=/opt/homebrew/opt/llvm/bin/clang-tidy .venv/bin/python scripts/ci_clang_tidy_diff.py origin/main build`。
- 前端改动后跑三项门禁：`npm run check`、`npx vitest run`、`npm run build`。

## HTTP 契约（各任务以此为准）

```
GET  /api/worlds
  每个世界行新增  auto_snapshot: {on_session: bool, interval_hours: int}
  顶层新增        auto_snapshot_status: {failures: int, last_error: str|null, last_error_at: str|null}
  快照行新增      sessions_complete: int|null（W4 之前的条目为 null）
                  session_id: str|null（只有 reason="session" 时非空）
                  reason 取值：manual | session | interval
POST /api/worlds                       body 新增可选 auto_snapshot: {on_session, interval_hours}
PUT  /api/worlds/{w}/auto_snapshot     body {on_session: bool, interval_hours: int}
                                       → {world, auto_snapshot}；404 world_not_found；400 invalid_auto_snapshot
GET  /api/worlds/{w}/sessions?limit=200   limit 取 1–1000
  → {world, source_lane_enabled: bool, total: int, null_observed: int, truncated: bool,
     sessions: [{session_id, units, speakers, first_at, last_at,
                 anchor: {snapshot_id, created_at} | null}]}
  404 world_not_found；503 world_switching
GET  /api/ingest_status                新增 auto_snapshot_failures: int, auto_snapshot_last_error: str|null
```

新错误码 `invalid_auto_snapshot` 映射为 400。现有错误码不变。

`interval_hours` 取 0–8760，0 表示关闭。

`source_lane_enabled` 取当前 config 的值。对非活动世界也是这个值，因为它表示「新写入会不会产生会话」。

## 任务依赖

- T1 → T2 → T3 顺序执行：T2 依赖 T1 的绑定，T3 依赖 T2 的 manager 方法。
- T4（前端）只依赖上面的 HTTP 契约。它可以在 T1 完成之后，放在单独的 worktree 里与 T2/T3 并行（同 W3 的做法），最后合并进本分支。

---

### Task 1：C++——自动快照配置、快照元数据、按触发拍快照、会话清单

**Files：** `include/starling/governance/world_store.hpp`、`src/governance/world_store.cpp`、`tests/cpp/test_world_store.cpp`。

**数据结构**

- `struct AutoSnapshotConfig { bool on_session = false; std::int64_t interval_hours = 0; };`，放进 `WorldEntry`，字段名 `auto_snapshot`。
  - JSON 形如 `"auto_snapshot": {"on_session": bool, "interval_hours": int}`。
  - 加载时缺这个字段，在 `registry_from_json` 里补默认值：默认世界 `{false, 24}`，其余世界 `{true, 0}`。补默认值需要知道哪个是默认世界，`world_from_json` 不知道，所以放在 `registry_from_json`。
  - 保存时总是写出这个字段。
  - 字段存在但形状不对时报 `registry_corrupt`：不是对象、`on_session` 不是布尔、`interval_hours` 不是整数或超出 0–8760。
- `SnapshotEntry` 新增三个字段：
  - `std::optional<std::int64_t> sessions_complete`：缺省时 JSON 里不写这个字段；
  - `std::string session_id`：为空时不写；
  - `std::string content_mark`：为空时不写。

  三个都是可选读取，W2/W3 的旧条目照常加载。
- 注册表校验加两条：
  - `kind="manual"` 时 `reason` 必须是 `"manual"`；
  - `kind="auto"` 时 `reason` 必须是 `"session"` 或 `"interval"`。

  否则报 `registry_corrupt`。W2/W3 只产生过 manual/manual 的条目，所以这两条不影响现有数据。

**函数**

- `create_world(...)` 新增参数 `const AutoSnapshotConfig& auto_snapshot = AutoSnapshotConfig{true, 0}`。`ensure_registry` 给默认世界写 `{false, 24}`。
- `void set_auto_snapshot(Registry&, const std::string& world, const AutoSnapshotConfig&)`：
  - 世界不存在时报 `world_not_found`；
  - `interval_hours` 越界时报 `invalid_auto_snapshot`。
- `take_snapshot` 在 `VACUUM INTO` **之前**，用同一条只读连接算出 `sessions_complete` 和 `content_mark`，写进条目：
  - `sessions_complete` 取 `COUNT(DISTINCT session_id) FROM source_unit_meta WHERE tenant_id=?`，表不存在时记 0；
  - `content_mark` 的格式见下。

  这两个值必须先于 `VACUUM INTO` 算。这样快照里的内容只会多于标记，不会少于标记，最坏只是多拍一次，不会漏拍。`SnapshotOptions` 新增 `session_id` 字段，原样写进条目。
- `content_mark`：
  - 格式 `"e<count>:<max_rowid>|s<count>:<max_rowid>|u<count>:<max_rowid>"`，三段依次取 `engrams`、`statements`、`source_unit_meta`，每段都按 `tenant_id` 过滤；某张表不存在时那一段写 `-`。
  - 原地更新（例如 tick 改 activation）不改变标记，插入和删除会改变它。这正是「有没有新写入」的判据。
  - 三张表的计数都为 0 时，标记取空串，表示库里没有内容。
- `struct AutoTrigger { std::string kind; /* "session" | "interval" */ std::string session_id; std::string now_iso; };`
- `struct AutoSnapshotResult { std::optional<SnapshotEntry> taken; std::string skipped; };`
  - `skipped` 的取值：`disabled`、`known_session`、`not_due`、`unchanged`、`empty`、`unsupported_backend`。
  - 拍了快照时 `skipped` 为空。
- `AutoSnapshotResult take_auto_snapshot(Registry&, const std::string& world, const AutoTrigger&, const SnapshotOptions& base)`：
  - 世界不存在时报 `world_not_found`。
  - `base.vector_backend != "sqlite"` 时返回 `skipped="unsupported_backend"`，不抛异常。
  - **按会话**：
    - `on_session` 为 false → `disabled`；
    - `session_id` 为空 → `invalid_auto_snapshot`；
    - 库里已经有这个会话 → `known_session`。判断方式：只读查 `SELECT 1 FROM source_unit_meta WHERE tenant_id=? AND session_id=? LIMIT 1`，表不存在算没有；
    - 否则拍一份：`kind="auto"`，`reason="session"`，`session_id` 填入。
  - **按时间**：
    - `interval_hours == 0` → `disabled`；
    - 算出当前 `content_mark`，为空 → `empty`；
    - 取该世界 `created_at` 最新的一份 auto 快照（任意 reason）作为 last；
    - last 存在、能解析出时间、`now - last.created_at < interval_hours` → `not_due`；
    - last 存在、带 `content_mark` 且与当前相同 → `unchanged`；
    - 否则拍一份：`kind="auto"`，`reason="interval"`。
    - last 的 `created_at` 解析不了，或者 last 没有 `content_mark`（W4 之前的条目），一律按「需要拍」处理。
  - 拍快照走 `take_snapshot` 的原有路径，磁盘守卫和保留策略照常生效，失败照常抛出。
  - `now_iso` 解析不了时报 `invalid_auto_snapshot`。
- `struct SessionRow { std::string session_id; std::int64_t units; std::int64_t speakers; std::string first_at; std::string last_at; std::string anchor_snapshot_id; std::string anchor_created_at; };`
- `struct SessionList { std::vector<SessionRow> rows; std::int64_t total; std::int64_t null_observed; bool truncated; };`
- `SessionList list_sessions(const Registry&, const std::string& world, std::int64_t limit)`：
  - 只读打开该世界的库，执行设计稿 §7 的 SQL，按 `first_at DESC` 排序，取前 `limit` 行。
  - `total` 是会话总数，`truncated = total > limit`。
  - `null_observed` 是 `observed_at IS NULL` 的 unit 数。
  - 锚点：在注册表里找 `kind="auto"`、`reason="session"`、`session_id` 相同的那份快照；同一会话有多份时取最新一份。
  - 表不存在或库文件不存在时，返回空列表、`total=0`。
  - `limit` 不在 1–1000 内报 `invalid_auto_snapshot`。
  - 只读打开失败报 `snapshot_failed`。

**测试步骤**

- [ ] **Step 1：先写会失败的测试**，至少覆盖：
  - 旧注册表缺 `auto_snapshot` 时，默认世界加载为 `{false,24}`，其余世界为 `{true,0}`；保存后再加载，值不变。
  - 形状不对的 `auto_snapshot`、越界的 `interval_hours`、kind 与 reason 不匹配，都报 `registry_corrupt`。
  - `set_auto_snapshot` 的正常写入与两种错误。
  - `take_snapshot` 写进条目的 `sessions_complete` 和 `content_mark` 与库内容一致。另写一个用例：在 `VACUUM INTO` 之前插入一行（用测试钩子，或在快照前后写入），断言快照文件里的行数 ≥ 标记里的计数。
  - 按会话：新会话拍、已知会话不拍、`on_session=false` 不拍、`session_id` 为空报错。
  - 按时间，用注入的 `now_iso`：
    - 没有 auto 快照且库有内容 → 拍；
    - 间隔没到 → `not_due`；
    - 间隔到了但标记相同 → `unchanged`；
    - 间隔到了、标记不同 → 拍；
    - 空库 → `empty`；
    - 旧条目没有标记、间隔已到 → 拍；
    - 有一份比 last 更新的 manual 快照 → 不影响判断。
  - zvec 后端 → `unsupported_backend`，不抛异常，不写盘。
  - 保留策略：有多份 auto 快照时，仍至少留一份 auto。这一条用已有测试覆盖，跑过即可。
  - `list_sessions`：
    - `units`、`speakers`、`first_at`、`last_at` 与写入一致；
    - 排序正确；
    - `limit` 截断，`truncated` 和 `total` 正确；
    - 锚点关联到对应会话的最新一份快照；
    - 表不存在、库文件不存在时为空；
    - `null_observed` 计数正确；
    - `limit` 越界报错。
- [ ] **Step 2：RED。**
- [ ] **Step 3：实现。**
- [ ] **Step 4：GREEN。** `ctest -R 'World|RegistryValidation'` 和全量 `ctest -j8` 都通过，全量基线 1615。
- [ ] **Step 5：回退验证。** 把标记的计算挪到 `VACUUM INTO` 之后，或者让按时间触发忽略标记，相应的用例必须失败。
- [ ] **Step 6：提交**，然后跑 clang-tidy 门禁。

### Task 2：绑定与 WorldManager——配置、触发核心、会话钩子、按时间的调度线程

**Files：** `bindings/python/bind_15_world.cpp`、`python/starling/dashboard/world_manager.py`、`python/starling/dashboard/engine.py`（只加一个异常类和一个属性）、`tests/python/test_dashboard_worlds.py`（以及新的绑定测试文件，按需添加）。

**绑定**

- 新增 `world_set_auto_snapshot`、`world_take_auto_snapshot`、`world_list_sessions`，都释放 GIL。
- `world_create` 新增可选参数 `auto_snapshot`（dict）。
- 快照 dict 带上三个新字段：`sessions_complete` 为 `None` 或 int，`session_id` 为 `None` 或 str，`content_mark` 只在内部使用。
- 注册表 dict 原样往返，与现有做法一致。

**engine.py（只做两件事）**

- 定义 `class SessionSnapshotDeferred(Exception)`。
- 在 `DashboardEngine.__init__` 里加 `self.session_snapshot_hook = None`。
- 调用点在 T3 加，这里不加。

**WorldManager**

- `create(name, label, auto_snapshot=None)`：透传给 C++。
- `set_auto_snapshot(name, on_session, interval_hours)`：持 `self.lock`，`load` 后写回 `save`，返回新配置。
- `auto_snapshot_status()`：返回 `{failures, last_error, last_error_at}`，在 `_gate` 下读。
- `_auto_snapshot(trigger_kind, session_id="", *, blocking=False) -> str`，这是两种触发共用的核心：
  1. 用 `self.lock.acquire(blocking=blocking)` 取锁，取不到返回 `"busy"`。
  2. 取到后先 `load`，再确认当前引擎正在写的库就是注册表里活动世界的库（`_same_db`），不一致返回 `"skipped:world_moved"`。
  3. 调 `_core.world_take_auto_snapshot(reg, active, trigger, now, vector_backend=...)`，`now` 来自注入的时钟。
  4. 拍了快照就 `save` 注册表。`save` 失败时，与 `take_snapshot` 一样补偿：调 `world_discard_snapshot_file`。
  5. 返回 `"taken:<id>"` 或 `"skipped:<reason>"`。

  任何 `WorldStoreError` 或其他异常都计为失败：计数加一，记下最近错误和时间，打 `logger.warning`，返回 `"failed"`，**不往外抛**。
- **时钟注入**：`WorldManager(..., clock=None)`，默认用 UTC 现在时刻生成秒精度的 ISO 字符串。测试传入固定时钟。
- **会话钩子**：`_make_session_hook()` 返回 `hook(session_id)`，内部调 `_auto_snapshot("session", session_id)`：
  - 结果为 `"busy"` 时抛 `SessionSnapshotDeferred`；
  - 其余结果都正常返回。失败也正常返回，这是用户裁定的「照常摄入」。
- **挂钩**：`_start_workers(engine, cfg)` 在起线程之前设 `engine.session_snapshot_hook = self._make_session_hook()`。lifespan 启动时的引擎在 T3 里也要挂上。
- **按时间调度线程**：
  - `start_scheduler(poll_s=600.0, first_delay_s=60.0)`：起一个名为 `starling-auto-snapshot` 的 daemon 线程。它先等 `first_delay_s`，之后每隔 `poll_s` 调一次 `_auto_snapshot("interval")`，等待一律用 `Event.wait`。结果为 `"busy"` 时什么都不做，等下一轮。
  - `stop_scheduler(timeout_s=5.0)`：set 停止事件并 join。
  - 重复 start 不起第二个线程。
- **关停**：`disable_workers()` 在现有逻辑之后调 `stop_scheduler()`。这一步放在锁外：线程只做非阻塞取锁，所以 join 时不会等到持锁的线程。

**测试步骤**

- [ ] **Step 1：先写会失败的测试**，至少覆盖：
  - 绑定往返：`set_auto_snapshot`；`create` 带配置；快照的新字段；`list_sessions` 的 dict 形状。
  - `_auto_snapshot`：
    - `"interval"` 在固定时钟下按 T1 的规则拍或不拍，拍了之后注册表里有条目；
    - 注入 `save` 失败时，快照文件已被丢弃，计数加一；
    - 注入 `world_take_auto_snapshot` 抛 `insufficient_disk` 时，返回 `"failed"`，状态里有错误信息，不往外抛。
  - 锁被另一个线程持有时（用 Event 控制），`_auto_snapshot` 返回 `"busy"`，不阻塞。会话钩子在这种情况下抛 `SessionSnapshotDeferred`。
  - 会话钩子：新会话拍一份，同一会话第二次不拍。这里要真的往 `source_unit_meta` 写一行：调 `retain_source_turns`，或直接 SQL 插入。
  - 调度线程：
    - `first_delay_s=0`、`poll_s` 很小、时钟可推进，第一轮拍一份；
    - 时钟没推进，第二轮返回 `not_due`；
    - `stop_scheduler` 之后线程已退出；
    - `disable_workers` 会顺带停掉调度线程；
    - 重复 start 只有一个线程。
  - 挂钩：`_start_workers` 之后 `engine.session_snapshot_hook` 不为 None。
- [ ] **Step 2：RED。**
- [ ] **Step 3：实现。**
- [ ] **Step 4：GREEN。** 先跑 `test_dashboard_worlds.py`，再跑全量 pytest，基线 2922 passed / 630 skipped。
- [ ] **Step 5：回退验证。** 把非阻塞取锁改成阻塞，「锁被持有」的用例必须超时失败；去掉「失败不外抛」，失败用例必须红。
- [ ] **Step 6：提交。**

### Task 3：摄入调用点、路由、lifespan 接线、设计稿

**Files：** `python/starling/dashboard/engine.py`、`python/starling/dashboard/routes/worlds.py`、`python/starling/dashboard/routes/inspect.py`、`python/starling/dashboard/app.py`、`tests/python/test_dashboard_worlds.py`、设计稿。

**摄入调用点**

- 位置：`_retain_transcript_turns` 里，`clean_turns_ts` 有结果、代数检查通过（那段 `with self._lock` 已经退出）之后，`retain_source_turns` 之前。
- 条件：`self.session_snapshot_hook` 不为 None，且 `session_id` 非空。满足时调 `self.session_snapshot_hook(session_id)`。
- 调用时**不得**持有 `self._lock`，这一点要写进注释（锁顺序）。
- 这个函数本来就只在 lane 开启时才被调用，所以 lane 关闭时不会出现会话快照。这是设计如此。

**`_ingest_drain_once`**

- 新增 `except SessionSnapshotDeferred`，放在通用的 `except Exception` 之前：把 claimed 改名回 `job_path`，**不加** `attempts`，返回 `"deferred"`。
- 此时这个任务还什么都没写，因为调用点在任何写入之前。

**路由**

- `CreateWorldBody` 新增 `auto_snapshot: AutoSnapshotBody | None = None`。`AutoSnapshotBody` 定义为 `on_session: bool`、`interval_hours: int`，范围交给 C++ 校验。
- `PUT /worlds/{name}/auto_snapshot`：调 `mgr.set_auto_snapshot`。
- `GET /worlds/{name}/sessions`：
  - 持 `mgr.lease()`，与 `_list_worlds` 相同；
  - 调 `_core.world_list_sessions(reg, name, limit)`；
  - 返回 HTTP 契约里的形状，`source_lane_enabled` 取 `request.app.state.config`。
- `_world_row` 加 `auto_snapshot`；`_list_worlds` 顶层加 `auto_snapshot_status`。
- `_snapshot_row` 的白名单加 `sessions_complete` 和 `session_id`，缺值时为 None。`content_mark` 不外露。
- `invalid_auto_snapshot` 映射为 400。
- `inspect.ingest_status`：在引擎结果上合并 `auto_snapshot_failures` 和 `auto_snapshot_last_error`。没有 WorldManager 时两项分别给 0 和 None。

**lifespan**

- 启动时：
  - lifespan 自己建的、或外部注入的引擎，在起摄入线程之前挂上 `session_snapshot_hook`（调 manager 的公开方法，例如 `mgr.attach_hooks(eng)`，由它设置钩子）；
  - `workers_enabled=True` 之后调 `mgr.start_scheduler()`。
- 关停时，`disable_workers()` 已经会停掉调度线程（T2）。
- 没有 WorldManager（`:memory:` 等情况）时，以上都不做。

**设计稿**

- §4.2：补上 `sessions_complete`、`session_id`、`content_mark`，以及「标记先于 VACUUM 计算」。
- §4.3：两种触发、每个世界单独配置、默认值、失败照常摄入、非阻塞取锁。
- §7：标题和正文改称「会话」，补上「场景不是通用概念」的裁定。
- §9：API 与页面改为 `/sessions`。
- §11 W4 验收行：改成新的范围。
- §12：
  - 保留份数与间隔共同决定可回滚的窗口；
  - 升级后第一轮会给默认世界拍一份快照。
- 状态行：W4 在 `feat/world-sessions` 上实现。
- 删掉过时的「生产库场景层为空」说法。生产库迁移版本已是 37，`source_unit_meta` 有 1393 行，1 个会话。

**测试步骤**

- [ ] **Step 1：先写会失败的测试**，至少覆盖：
  - **摄入端到端**（真实引擎，lane 开启并用 stub 嵌入，临时 spool，manager 挂钩）：
    - 一个新会话的 transcript 任务在写入前拍一份 `reason="session"` 的快照，快照里没有这个会话的 unit；
    - 同一会话的第二个任务不再拍；
    - 钩子返回 busy 时（manager.lock 被另一个线程持有），任务回到 spool，`attempts` 不变，库里没有写入；锁释放后，下一次 drain 照常拍并写入；
    - 快照失败（注入 `insufficient_disk`）时任务照常完成，`ingest_status` 里失败计数为 1。
  - **路由**：
    - `PUT auto_snapshot` 正常写入、400 和 404；
    - `POST /api/worlds` 带配置和不带配置（不带时用新世界的默认值）；
    - `GET /sessions` 返回的形状、`limit` 越界返回 400、未知世界返回 404、切换窗口内返回 503；
    - 快照行的新字段；
    - `GET /api/worlds` 返回的 `auto_snapshot_status`。
  - **lifespan**：
    - `with TestClient(app)` 之后调度线程在跑、钩子已挂上；
    - 退出之后调度线程已停。
- [ ] **Step 2：RED。**
- [ ] **Step 3：实现。**
- [ ] **Step 4：GREEN。** 先跑 `test_dashboard_worlds.py`，再跑全量 pytest。
- [ ] **Step 5：回退验证。**
  - 把调用点挪到 `retain_source_turns` 之后，「快照里没有这个会话」的用例必须失败；
  - 去掉 `SessionSnapshotDeferred` 分支，busy 用例必须失败。
- [ ] **Step 6：提交。**

### Task 4：前端——会话页、自动快照设置、快照元数据

**Files：** `dashboard/web/src/lib/worlds.ts`（以及对应的 `.test.ts`）、`dashboard/web/src/lib/nav.ts`、`nav.test.ts`、`dashboard/web/src/routes/worlds/+page.svelte`（以及 `page.test.ts`）、新建 `dashboard/web/src/routes/sessions/+page.svelte` 和 `page.test.ts`。

**类型与 API**

- 按 HTTP 契约补类型：
  - `AutoSnapshotConfig`、`AutoSnapshotStatus`；
  - `SnapshotRow` 增加 `sessions_complete` 和 `session_id`；
  - `SessionRow`、`SessionList`。
- 新增两个 API 函数：`setAutoSnapshot(name, cfg)`、`listSessions(name, limit)`。
- 新错误码 `invalid_auto_snapshot` 的文案：「自动快照设置无效（间隔须为 0–8760 小时）」。

**导航**

- 「世界 · 会话」组增加一项 `{ href: '/sessions', label: '会话', icon: 'list' }`，同步修改 `nav.test.ts`。

**`/worlds` 页**

- 每个世界行显示自动快照设置，例如「按会话 · 每 24 小时」「关闭」，带一个「设置」按钮。点开后是一个小表单：「按会话」复选框，加上间隔小时数输入，0 表示关闭。保存时调 `PUT`。
- 新建世界的对话框里加同样两个字段，默认值为按会话开、间隔 0。
- 快照行：
  - `reason` 显示为「手动」「会话开始前」「定时」；
  - 显示 `sessions_complete`，为 null 时显示 `—`；
  - reason 是「会话开始前」时，显示 `session_id` 的前 8 位。
- `auto_snapshot_status.failures > 0` 时，页面顶部显示提示：「自动快照失败 N 次，最近一次：<时间> <错误>；摄入未受影响，失败的会话没有回滚锚点」。

**`/sessions` 页**

- 默认显示活动世界，可以通过下拉框切到别的世界。
- 表格列：会话（`session_id` 的前 12 位，悬停显示全文）、话轮数、说话人数、开始、最近、回滚锚点。
  - 有锚点时显示快照 id，并提供「回滚到此会话之前」按钮。按钮沿用 `ConfirmDialog`，要手输世界名确认，调用与 `/worlds` 页相同的回滚 API、相同的错误文案。活动世界回滚成功后整页刷新。
  - 没有锚点时显示「无」，悬停说明：未开启按会话快照、快照失败，或已被保留策略清理。
- `source_lane_enabled` 为 false 时，表格上方提示：「左脑 lane 未开启：新的写入不会记录会话」。
- `truncated` 为真时，提示「只显示最近 N 个会话，共 M 个」。
- 空列表时显示「这个世界还没有会话记录」。

**测试步骤**

- [ ] **Step 1：先写会失败的测试**（vitest，mock API）：
  - 导航项；
  - 两个新 API 函数的请求形状；
  - 错误文案；
  - `/worlds` 页：设置的显示与保存、新建对话框带上配置、快照行的 reason 文案与 `—`、失败提示；
  - `/sessions` 页：
    - 表格各列；
    - 有锚点时显示回滚按钮、确认名不符时不能提交、调用了回滚 API；
    - 没有锚点时显示「无」；
    - lane 关闭的提示、截断的提示、空列表；
    - 切换世界下拉框。
- [ ] **Step 2：RED。**
- [ ] **Step 3：实现。**
- [ ] **Step 4：GREEN。** 前端三项门禁全过，基线 vitest 291。
- [ ] **Step 5：提交。**

## 合并与验证（主会话执行）

1. 全量门禁：ctest、pytest、前端三项、clang-tidy。
2. 隔离实例端到端，用 `$CLAUDE_JOB_DIR/tmp/e2e/` 下的脚本，扩展如下：
   - 新建一个按会话触发的世界，开启 lane，用 stub 嵌入。放进两个 transcript 任务，它们的 `session_id` 不同。断言：
     - 拍了两份 `reason="session"` 的快照；
     - `/sessions` 有两行，各自带锚点；
     - 回滚到第二个会话之前，那个会话消失，第一个会话还在。
   - 默认世界按时间触发：用注入时钟（或很短的 `poll_s` 加推进时钟），断言有一份 `reason="interval"` 的快照；没有新写入的那一轮不拍。
   - W3 的完整场景和 H1 的恢复检查重跑一遍。
3. 用生产库的只读副本（`VACUUM INTO`）跑一次 `list_sessions` 和按时间的 `take_auto_snapshot`，记录耗时与快照大小。
4. 整支审查和 Codex 审查之后，开 PR，base 为 `feat/world-hardening`。不部署。
