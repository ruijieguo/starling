# 世界/场景管理：完整设计

日期 2026-10-25。状态：**设计稿，未实现**。承接 `2026-10-19-form-s-source-lane-design.md` §14 的用户裁定。

**范围**：多世界 Dashboard、快照、回滚（两种语义）、分叉、场景清单。

**不在范围**：感知授权（已在形态 S 落地）、**场景级召回隔离（用户 2026-10-25 明确放弃）**、跨世界检索。

### 0.1 已裁定事项

| 事项 | 决定 | 日期 |
|---|---|---|
| 按场景隔离召回 | **放弃，不做** | 2026-10-25 用户裁定 |
| 默认世界是否搬家 | **不搬**，`dashboard.db` 原地；新世界才进 `worlds/`。理由：不动物理部署；代价是两套布局并存，写进 §2.3 | 2026-10-25 默认值 |
| 快照保留份数 | **5**，清理优先保留 manual；且至少留 1 份 auto 作回滚锚点（N<2 拒绝） | 2026-10-25 默认值 |
| 分片推进 | **W1+W2 先做完停下**，看过效果再决定 W3–W5 | 2026-10-25 默认值 |

后三项是按设计默认值定的，不是我替你做的产品决定——任何一项要改，改配置或改分片顺序即可，不影响别处。

**关于"放弃按场景隔离召回"的后果**：`SourceSearchScope` 不加 session 字段，`statements` / `episodic_events` 也无需加场景列。这同时确认了 §12 的两条"未解"仍然是未解（并发场景的精确回滚做不到、右脑无法按场景归属）——放弃场景过滤等于接受这两条长期存在，不再有"给语句加场景列"的改造动机。

---

## 0. 结论

四条可执行的决定：

1. **一个世界 = 一个数据库文件 + 一个租户 id**。快照、回滚、分叉因此全部退化为文件操作，完整性由构造保证，而不是靠"逐表删干净"。
2. **快照用 `VACUUM INTO`**，不搬 2.4GB 的 WAL 库，只写活数据。生产库实测 **57MB / 0.16 秒**。
3. **场景不是召回边界**（沿用形态 S §3.3），它的管理能力建立在 `source_unit_meta.session_id` 上，因此**只对形态 S 落地之后摄入的数据可见**。
4. **"只回滚该场景、保留后续" = 分叉 + 重新摄入原话**，是语义重建不是精确恢复。这一点 §14.2 已经写死，本设计不试图改变它。

---

## 1. 既有事实（实测，非推断）

### 1.1 生产库现状（`~/.starling/dashboard.db`，2026-10-25 01:11）

| 项 | 实测值 |
|---|---|
| 文件大小 | 2.4 GB |
| WAL | 1.4 GB |
| `page_count` | 642,193 |
| `freelist_count` | 627,259（**97.7%** 是空洞） |
| `page_size` | 4096 |
| `VACUUM INTO` 产出 | **57 MB，0.16 秒** |
| `statement_vectors` 占用 | 29 MB |
| engrams / statements | 101 / 3,632 |
| `statements` 中 volatile | 3,290 |
| `bus_events` | 10,514 |
| 租户数 | 1（`default`） |
| `schema_migrations` 最高版本 | **36** |

**最后一条是关键**：生产库还没有 `source_unit_meta`、`source_unit_vectors`、`cognizer_group_membership`——迁移 0037 尚未应用（服务自 10-17 起没重启过）。也就是说**场景层今天是空的**，场景 UI 上线后第一次打开会是空列表，这不是 bug。

### 1.2 快照机制实测

在带 1.4GB WAL、97.7% freelist 的活库上实测：

| 场景 | 结果 |
|---|---|
| 有并发读事务时 `VACUUM INTO` | 成功 |
| 在写事务内 `VACUUM INTO` | 失败：`cannot VACUUM from within a transaction` |
| 耗时 | 0.16 秒（这个库） |

结论：快照必须**用独立连接、在事务之外**执行；不能复用引擎那条写连接。

### 1.3 世界状态散布在 32 张表

`src/memory/memory_ops.cpp:800` 的 `clear_tenant` 列出了全部租户作用域表（从 `episodic_events` 到 `replay_ledger`），并有守卫测试 `tests/cpp/test_memory_ops.cpp:539 ClearTenant.CoversEveryTenantScopedTable`——它用 `pragma_table_info` 扫描任何带 `tenant_id` / `window_tenant_id` 列的表，清单漏一张就红。

这张清单是**世界级**操作的现成工具（清空、按世界抽取）。它**不是**场景级工具：没有一张表带场景列，场景信息只在 `source_unit_meta.session_id` 里，而语句（`statements`）无法确定性回溯到场景。

### 1.4 原话 payload 自足

`src/retrieval/source_retriever.cpp:1384` 起的写入路径：每个 `(session_id, 听众集合)` 分组成一个 engram，payload 含说话人、文本、场景、句序、世界时刻、听众、来源；`retention_mode='audit_retain'`，只追加不改写。这是"重新摄入"唯一可依赖的输入。

---

## 2. 核心决策：一个世界 = 一个文件 + 一个租户

### 2.1 决定

```
~/.starling/
  worlds.json                       ← 注册表（唯一权威）
  dashboard.db                      ← 默认世界 default（保持原地，不迁移）
  metrics.db                        ← 默认世界的指标库（现状位置）
  worlds/
    <world-name>/                   ← 新建世界的目录
      world.db
      metrics.db
      snapshots/                    ← 该世界的快照
  ingest-spool/tenant-<encoded>/    ← 现状不变，按租户分区的
```

**不变式**：一个 `world.db` 内只允许存在一个租户 id，且必须等于该世界配置里的租户 id。激活世界时校验；不满足则拒开（`world_tenant_mismatch`）。

### 2.2 为什么不是"一个库、多租户"

现有代码本来就支持多租户共库（`tenant_id` 列），看起来更省事。否决它的理由是**回滚**：

- 多世界共库时，某个世界的快照是整个库的快照（含别的世界）。恢复它等于把别的世界也一起回滚——错的。
- 要只恢复一个世界，就得从快照库里逐表抽取 `tenant_id = W` 的行再搬回来。这正是 §14.2 警告的"逐表按场景删除会漏表"的同构问题，只从场景换成了世界。虽然 `clear_tenant` 的清单加守卫测试把这个风险压低了，但**正确性要靠一张手维护的清单 + 一个测试来保证**，而文件方案**根本不需要这张清单**。
- 世界是安全边界。文件级隔离下，租户过滤写错最多泄漏到"同一个世界内的另一个租户"，而那个世界本来就只有一个租户。

### 2.3 代价（明确列出）

| 代价 | 说明 |
|---|---|
| 多世界 = 多引擎 | 每个活世界有自己的 C++ Runtime / 写连接 / embedder。**只允许一个活世界**（§8），其余是冷文件。 |
| 迁移按文件跑 | 开世界时 `MigrationRunner` 在该文件上跑一次。多世界 = 多份迁移，但这正是隔离的代价。 |
| 默认世界不搬家 | `dashboard.db` 原地保留。新世界才进 `worlds/`。避免动生产部署。 |
| 世界数不该多 | 用户裁定"大多数情况下只有一个世界"。本设计不为上千世界做优化。 |

---

## 3. 注册表 `worlds.json`

### 3.1 形态

```json
{
  "version": 1,
  "default": "default",
  "active": "default",
  "worlds": {
    "default": {
      "tenant": "default",
      "db_path": "/Users/x/.starling/dashboard.db",
      "snapshot_dir": "/Users/x/.starling/worlds/default/snapshots",
      "created_at": "2026-10-17T08:20:46Z",
      "label": "主世界"
    }
  },
  "snapshots": {
    "default": [
      {"id": "20261025T011200Z-a1b2", "path": "/Users/x/.starling/worlds/default/snapshots/20261025T011200Z-a1b2.db",
       "kind": "auto|manual", "reason": "scene_boundary",
       "created_at": "...", "world_time": "2026-10-24T18:03:11Z",
       "sessions_complete": 12, "size_bytes": 60123456, "note": ""}
    ]
  }
}
```

- 权限 0600，写入用 **临时文件 + `os.replace`**（与 `starling.json` 同款原子写，见 `python/starling/dashboard/config.py`）。
- 所有读写都在世界管理锁内，单写者。
- `db_path` **只由注册表给出，永不接受客户端传路径**（§14.2 的硬约束）。

### 3.2 为什么是 JSON 而不是又一个 SQLite

注册表要满足的是：小、低频、单进程、原子、人可读可修。JSON + 原子替换全部满足。用 sidecar SQLite 会引入第二套迁移机制，收益是事务性——但单写者 + 原子替换已经够了。**若将来出现并发管理请求，再换 SQLite**，那时是替换一个模块而不是改全部调用方。

---

## 4. 快照

### 4.1 做法

```
VACUUM INTO '<snapshot_dir>/<id>.db'    -- 独立连接，事务之外
```

- **独立连接**（不能用引擎那条写连接：`VACUUM` 不能在事务内，而引擎连接随时可能在事务里）。
- 得到的是**紧凑、自洽、可直接当世界库打开**的文件，无 WAL、无 freelist。
- 时间戳 `<UTC compact>-<4 hex>`，单调可排序，同名冲突时加后缀。

### 4.2 元数据

每条快照记录四个关键字段：

| 字段 | 用途 |
|---|---|
| `world_time` | 快照覆盖到的**世界时刻水位**（`MAX(observed_at)` on `source_unit_meta`，为空则 `MAX(created_at)` on `engrams`） |
| `sessions_complete` | 快照时该世界已有的场景数 |
| `size_bytes` | 显示与配额判断 |
| `kind` | `auto`（场景边界）/ `manual` |

`world_time` 是回滚的锚：**"丢掉后续"回滚到哪个快照，就是看它的 `world_time`**。

### 4.3 触发

| 触发 | 时机 | kind |
|---|---|---|
| 场景边界 | 摄入批次的 `session_id` 在该世界内**首次出现**时，先拍快照再写 | auto |
| 手动 | Dashboard 按钮 / `POST /api/worlds/{w}/snapshots` | manual |

场景边界自动快照是"能回滚到任意场景之前"的前提：没有它，手动快照只能回到拍过的点。

成本：实测 0.16 秒 / 57MB（当前库）。**代价随记忆量线性增长**，`statement_vectors` 已占 29MB/57MB，是主要增长项。

### 4.4 保留 N 份

- `snapshot_retention` 默认 **5**，可配置（§14.1 的要求）。
- 清理在最旧的非 `manual` 快照上做（手动快照优先保留）；若全是 manual 则按时间清最旧的。
- **清理后必须至少保留最近一份 auto 快照**，否则"丢掉后续"就没有锚点。若 N<2，配置被拒。

### 4.5 磁盘守卫

拍快照前检查：`free_space > 3 × 当前快照体积`，否则拒绝并回 507。理由：`VACUUM INTO` 失败会留半个文件，且写满磁盘会拖垮主库 WAL。

---

## 5. 回滚：两种语义

### 5.1 语义 A — 丢掉后续（恢复到快照 S）

```
1. 关闭活世界引擎（停 tick、停 ingest worker、close core）
2. 校验 S 的文件可打开、tenant 一致、integrity_check 通过
3. 目标库改名为 <db>.pre-rollback-<ts>（保留，供再回滚）
4. S 复制到目标路径（跨文件系统时先 copy 到同目录再 os.replace）
5. 重建引擎
```

- **完整、确定、零 LLM 成本**。
- 语义是"回到那一刻"，因此 S 之后的一切（包括其他并发场景）一并消失——这正是 §14.2 说的并发场景下的必然结果。
- 旧库不删，改名保留；清理交给显式的"清理回收站"操作，避免一次误操作不可逆。

### 5.2 语义 B — 只回滚该场景，保留后续

场景 S 的边界：

```
cut = MAX(observed_at) over source_unit_meta WHERE session_id = S
```

```
1. 找到 world_time ≤ cut 的最近快照 S0（没有 → 拒绝，报 "snapshot too old"）
2. 分叉：从 S0 生成新世界 W'
3. 从**当前世界**（不是 S0）导出所有 min(observed_at) > cut 的场景的原话
4. 重新摄入到 W'：
   - 每个 (session_id, audience) 分组 → 一次 source_turns 摄入
   - 走正常写入路径（重新嵌入、重新 LLM 抽取）
5. W' 成为候选世界，用户确认后才切换
```

三点必须写进 UI：

1. **这是语义重建，不是精确恢复。** 重新抽取会产生不同的语句、不同的置信度、不同的向量。
2. **要花 token。** 每个保留场景重新抽一次。
3. **并发场景可能重叠。** 若 S 与 S' 的世界时刻区间相交，按 `cut` 切分会把 S' 的一部分也切掉。逐场景精确切分在"一个查询、一张语句表、没有场景列"的结构下做不到——这是已知限制，不是待办。

### 5.3 两种语义的取舍

| | 丢掉后续 | 只回滚该场景 |
|---|---|---|
| 成本 | 文件复制 | 文件复制 + 全部保留场景重新抽取 |
| 结果 | 逐字节精确 | 语义重建，右脑不保证一致 |
| 并发场景 | 一并回滚 | 边界模糊 |
| 依赖 | 无 | 原话可重放（形态 S §3.5） |

---

## 6. 分叉

**分叉就是"以某个快照为起点创建一个新世界"**，与语义 B 的步骤 2 是同一个操作，因此先实现分叉，语义 B 只是它上面加一次重新摄入。

```
POST /api/worlds/{w}/fork {snapshot_id, name}
→ 复制快照文件到 worlds/<name>/world.db
→ 注册新世界（tenant 沿用来源租户，见下）
→ 打开新世界跑迁移（快照已是当前版本，应为 no-op）
```

**租户 id 的决定：分叉时保留来源租户 id 不变。**

曾经考虑让新世界用自己的名字作 tenant id，被否决：那需要把快照里所有 `tenant_id` 行改写成新值，而 `statements.tenant_id` 是**不可变字段**（迁移 0007 的触发器会 ABORT），绕过它要么禁触发器要么直改表，两条路都在破坏不变量。

因此 §2.1 的不变式要精确表述：*一个世界文件里**至多**一个租户 id；但同一个租户 id 可以出现在多个世界文件里（分叉后代）。*

代价是 §8.2 那条：同一租户的两个世界共用 spool 分区。

---

## 7. 场景清单

数据来源只有一处：`source_unit_meta`。

```sql
SELECT session_id,
       COUNT(*)                    AS units,
       MIN(observed_at)            AS first_at,
       MAX(observed_at)            AS last_at,
       COUNT(DISTINCT speaker)     AS speakers
  FROM source_unit_meta
 WHERE tenant_id = ?1
 GROUP BY session_id
 ORDER BY first_at DESC
```

| 限制 | 状态 |
|---|---|
| 只覆盖形态 S 之后的数据 | 已知。生产库今天 0 行（迁移 0037 未应用） |
| 没有场景列的表无法归属 | 已知。`statements` 无法确定性地回溯到场景——因此场景删除**只能**走快照回滚 |
| 场景名来自调用方 | `session_id` 是可信后端的断言（信任模型 A），Starling 不验证，只展示 |
| 无 `observed_at` 的 unit | `observed_at IS NULL` 的 unit 不参与召回（设计如此），场景清单里单独计数但不参与 `world_time` 水位 |

---

## 8. 世界切换与引擎生命周期

### 8.1 只允许一个活世界

`app.state.engine` 是单引擎。切换世界 = 换引擎，不是并存。

```
switch(world):
  with _world_lock:
     old = app.state.engine
     if old is not None:
         with old._lock:              # 等所有在飞请求结束
             old.close()
     cfg = config.with_world(world)   # db_path + tenant 换成该世界的
     app.state.engine = None          # 让 _engine() 按新 cfg 惰性重建
     app.state.config = cfg
     eng = _engine_like(app.state)    # 立即建一次，暴露启动失败
```

- 路由本来就每次请求 `_engine(request)` 从 `app.state` 取（`routes/commands.py:78`），所以切换后新请求自动拿到新引擎。
- 在飞请求：`old.close()` 前先拿 `old._lock`，保证没人正在用。
- **切换前必须确认没有 ingest job 在跑**：`stop_ingest_worker()` 是有界等待（5 秒），超时则拒绝切换并报 `ingest_busy`。
- 切换失败（新世界库损坏 / 迁移失败 / 租户不符）→ 回滚到旧引擎，状态机不前进。

### 8.2 metrics.db 与 spool

- `metrics.db` 是 `db_path` 的兄弟（`engine.py:238`），所以按世界自动分开——**前提是新世界有自己的目录**（§2.1 的布局满足）。
- spool 已经按租户分区（`tenant_spool_dir`），世界切换后自动指向正确分区。默认世界与分叉世界若共用 tenant id（§6），**spool 分区会共用**——这是分叉的已知副作用，写进限制里。分叉出的世界应当**暂停摄入**直到用户显式确认要继续。

---

## 9. Dashboard 面

新增导航组「世界 · 会话」，排在「总览」之后、「原始数据 · 证据」之前（世界是比 engram 更上游的划分）。**注意**：`dashboard/web/src/lib/nav.test.ts:8` 断言了 11 个组的精确标题列表，加组必须同步改测试。

| 页面 | 内容 |
|---|---|
| `/worlds` | 世界列表：名称、路径、大小、场景数、语句数、最后活动、是否当前；操作：新建、切换、快照、分叉、删除 |
| `/worlds/[name]`（或 `/worlds?world=`） | 该世界的场景清单 + 快照清单（含 `world_time`、大小、kind、删除） |
| `/scenes`（可选，或并入上表） | 当前世界的场景列表，含每条场景的时间区间与 unit 数 |

危险操作（删除世界、回滚）要求**手输世界名确认**——沿用 `clear_memory` 的 `confirm` 范式（`engine.py:626`），它有现成的 400 `confirm_mismatch` 语义。

API：

```
GET    /api/worlds                       列表（注册表 + 每个世界一行统计）
POST   /api/worlds                       新建 {name, label}
POST   /api/worlds/{w}/activate          切换
DELETE /api/worlds/{w}                   删除（须 confirm，且不能删 default 或 active）
GET    /api/worlds/{w}/snapshots         快照列表
POST   /api/worlds/{w}/snapshots         手动快照 {note}
DELETE /api/worlds/{w}/snapshots/{id}    删除快照
POST   /api/worlds/{w}/rollback          回滚 {mode: "discard_after"|"scene", cutoff|snapshot_id, confirm}
POST   /api/worlds/{w}/fork              分叉 {snapshot_id, name}
GET    /api/worlds/{w}/scenes            场景清单
```

统计数字从各世界库只读连接查（`mode=ro`，与 `engine.py:391` 的既有做法一致），**不打开引擎**——否则列 5 个世界就要建 5 个引擎。

---

## 10. 落点（C++/Python 边界裁定）

按仓库硬规则"换一种绑定语言是否需要重写该逻辑"判定：

| 逻辑 | 落点 | 理由 |
|---|---|---|
| 快照（`VACUUM INTO` + 校验 + 元数据） | **C++** `src/governance/world_store.cpp` | 换语言要重写：连接管理、一致性、错误分类 |
| 回滚的顺序与原子性 | **C++** 同上 | 状态机语义 |
| 保留 N 份的裁剪策略 | **C++** 同上 | 策略，不是适配 |
| 场景清单查询 | **C++** 同上 | 单一权威 SQL |
| 注册表读写（JSON） | **C++**（`nlohmann::json` 已用） | 同一份逻辑换语言要重写 |
| 世界切换时引擎重建 | **Python** `dashboard/world_manager.py` | 它调的就是 Python 侧的引擎生命周期；没有绑定语言能共享 |
| 路由 | Python | 适配 |
| 页面 | SvelteKit | 前端 |

**不落 C++ 的部分**要说明白：引擎重建本质是 Python 对象生命周期管理，不属于核心语义。

新增迁移：无。注册表是文件，快照是文件，不碰 schema。

---

## 11. 分片与验收

每片独立可合，测试确定性（无 LLM 依赖，嵌入用 stub）。

| 片 | 内容 | 验收 |
|---|---|---|
| W1 | 注册表 + 新建/列出/切换/删除世界 + `/worlds` 页 | 单测：注册表原子写、路径校验（拒相对路径/越界路径）、tenant 不变式；手动：新建 worlds 里点一遍 |
| W2 | 快照（手动）+ 列表 + 删除 + 保留 N | 单测：`VACUUM INTO` 产物可打开且 `integrity_check=ok`、`world_time` 正确、裁剪按 N 且保留至少 1 份 auto、磁盘守卫；实测：在生产库副本上拍，比对 57MB 量级 |
| W3 | 回滚语义 A（丢掉后续） | 单测：回滚后语句数等于快照时的数、旧库被改名保留、失败时目标库不被破坏（用损坏快照 + 只读目录两条路测） |
| W4 | 场景清单 + 场景边界自动快照 + `/scenes` 页 | 单测：新 session 首次写入触发一次快照且只触发一次；场景清单的 `first_at/last_at` 与写入一致 |
| W5 | 分叉 + 回滚语义 B（重新摄入） | 单测：分叉后两库互不影响（写一个不动另一个）、tenant id 相同的不变式例外成立；语义 B 用 stub LLM 验证"原话被重新提交"，不验证内容一致 |

**预注册**：W1–W5 都是功能交付，不是基准增益，验收判据是上面的确定性测试。凡涉及评测数字的（如重新摄入后的召回质量）都属于新的评测任务，需要单独预注册。

---

## 12. 风险与未解

| 风险 | 处置 |
|---|---|
| 快照体积随记忆线性增长 | 保留 N 默认 5；`/worlds` 显示当前快照总量；磁盘守卫 |
| 回滚窗口 = 最后 N 个场景 | 显式报 `snapshot too old`，不静默回退到更早的快照 |
| zvec 向量后端（默认关闭）向量在 SQLite 之外 | **分片内 fail loud**：`vector_backend=zvec` 时快照/回滚直接拒绝（`snapshot_unsupported_backend`），不做半截快照 |
| 分叉共用 tenant id → 共用 spool 分区 | 分叉后新世界**暂停摄入**，UI 提示"世界 <name> 与 <parent> 共用摄入分区" |
| 生产库 97.7% 是 freelist | W2 上线时顺带建议一次 `VACUUM`（离线）；不做成自动，因为 2.4GB 的 VACUUM 需要独占 |
| `VACUUM INTO` 失败留半个文件 | 先写 `<id>.db.partial` 再 `os.replace`；失败则删 partial |
| 多世界 = 多份迁移历史 | 每个世界库自带 `schema_migrations`；版本不一致时拒绝激活（报 `world_schema_behind`），提示先升级 |

**未解**（不假装解决了）：

1. **并发场景的精确回滚**做不到——没有场景列，只能按世界时刻切。要解决得先给语句加场景归属，那是另一个设计。
2. **重新摄入的语义一致性**无法保证。形态 S §3.5 已写明：这是重建不是恢复。
3. **默认世界迁不迁目录**：本设计选"不迁"（`dashboard.db` 原地），代价是默认世界与新世界布局不一致。若将来要统一，需要一个搬运世界的操作——本设计不做。
