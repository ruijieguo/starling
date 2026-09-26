<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# P3.b2 OpenClaw memory 插件 实现计划
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Starling 成为 OpenClaw 的 `plugins.slots.memory` provider —— 一个瘦 TS HTTP 客户端把 OpenClaw memory 操作路由到 Starling dashboard FastAPI,在 docker 内隔离开发集成测试。

**Architecture:** Starling 端先补两个 dashboard 端点(`POST /api/forget` 走新 `StatementStore.forget`→forgotten,`GET /api/statement/{id}` 走新 `queries.statement_by_id`);再做 TS 插件(`integrations/openclaw/`)实现 OpenClaw memory 注册接口,作适配层调 dashboard;最后 docker 隔离端到端验证 —— **dashboard 跑本机 host(macOS Mach-O `_core.so` 不能进 Linux 容器),OpenClaw 跑单容器经 `host.docker.internal` 连本机**(Task 7 实测修正;原「starling 挂载本机容器」作废)。核心语义留 C++/Python,插件只翻译+传输+容错。

**Tech Stack:** C++20(StatementStore/memoryops facade)+ pybind11 + FastAPI(dashboard)+ TypeScript(OpenClaw plugin-sdk, fetch)+ vitest + Docker compose。

**工作目录:** repo 根 live main checkout `/Users/jaredguo-mini/develop/memory/starling`(Task 2 改 C++/binding 需重建 `_core.so`,scikit-build editable finder 指向 main 的 `python/`)。TS 插件 `integrations/openclaw/` 是 repo 内新目录(类似 dashboard/web 的 standalone npm)。

**硬约束(每个 Task 适用):**
- explicit-path `git add <file>`(绝不 `git add .`/`-A`);无 `--no-verify`/`--amend`。
- 核心逻辑 C++(`src/`+`include/starling/store/`+`src/memory/`),Python/TS 仅转发,不重写语义。
- 改 C++/binding 后必跑 `--python-editable` 重建。构建:`PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`(repo 根)。
- API key / token 只在 env / `~/.starling/starling.json`(0600)/ 进程内存,绝不入日志 / 绑定 / git。
- 不破坏现有 ctest(587 OFF 默认)+ pytest 全绿。

---

## File Structure

**Starling 端(Task 1-2):**
- Modify `python/starling/dashboard/queries.py` — 加 `statement_by_id`(read-only SQL)。
- Modify `python/starling/dashboard/routes/inspect.py` — 加 `GET /statement/{id}` route。
- Modify `include/starling/store/statement_store.hpp` — 抽象基类加 `virtual int forget(...)=0`。
- Modify `include/starling/store/sqlite_statement_store.hpp` — 加 `forget` override 声明。
- Modify `src/store/sqlite_statement_store.cpp` — 实现 `forget`(→forgotten)。
- Modify `include/starling/memory/memory_ops.hpp` — 声明 `memoryops::forget`。
- Modify `src/memory/memory_ops.cpp` — 实现 `memoryops::forget`(逐 id store.forget)。
- Modify `bindings/python/bind_13_memory_ops.cpp` — 加 `m.def("memory_forget")`。
- Modify `python/starling/_memory_core.py` — `MemoryCore.forget`。
- Modify `python/starling/dashboard/engine.py` — `DashboardEngine.forget`。
- Modify `python/starling/dashboard/routes/commands.py` — `POST /forget` route。
- Modify `tests/cpp/test_statement_store.cpp` — `forget` 钉测。
- Modify `tests/python/test_dashboard_inspect.py` — `statement_by_id` 钉测。
- Modify `tests/python/test_dashboard_commands.py` — `forget` 钉测。
- Register ctest target:`forget` 测试并入既有 `test_statement_store`(无需新 CMake)。

**TS 插件端(Task 3-7,`integrations/openclaw/`):**
- Create `integrations/openclaw/openclaw.plugin.json` — manifest(`id:"starling", kind:"memory", configSchema`)。
- Create `integrations/openclaw/package.json` — `{type:"module", openclaw:{extensions:["./dist/index.js"]}}`。
- Create `integrations/openclaw/tsconfig.json`。
- Create `integrations/openclaw/src/config.ts` — 解析校验插件 config。
- Create `integrations/openclaw/src/client.ts` — StarlingClient(fetch + token + 读降级 + 写重试队列)。
- Create `integrations/openclaw/src/map.ts` — OpenClaw ↔ dashboard schema 纯函数映射。
- Create `integrations/openclaw/src/runtime.ts` — 组装七能力调 client。
- Create `integrations/openclaw/src/index.ts` — `definePluginEntry` + register。
- Create `integrations/openclaw/test/*.test.ts` — vitest 单元(map/client)。
- Create `integrations/openclaw/docker/docker-compose.yml` + `openclaw.Dockerfile` + `README.md`。

---

## Task 1: `GET /api/statement/{id}` 点读(纯 Python,read-only)

**Files:**
- Modify: `python/starling/dashboard/queries.py`
- Modify: `python/starling/dashboard/routes/inspect.py`
- Test: `tests/python/test_dashboard_inspect.py`

- [ ] **Step 1: 写失败测试**

在 `tests/python/test_dashboard_inspect.py` 末尾追加(沿用该文件既有 `client` fixture / remember 写入模式;若该文件 fixture 名不同,对齐 `test_dashboard_commands.py` 的 `_engine_with_llm`+`TestClient(create_app(cfg, engine=eng))`):

```python
def test_statement_by_id_roundtrip(client):
    rid = client.post("/api/remember", json={"text": "Bob owns auth"}).json()
    sid = rid["statement_ids"][0]
    r = client.get(f"/api/statement/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == sid and body["consolidation_state"] in (
        "volatile", "consolidated", "archived")


def test_statement_by_id_404_when_absent(client):
    r = client.get("/api/statement/does-not-exist")
    assert r.status_code == 404 and r.json()["detail"] == "not_found"
```

- [ ] **Step 2: 跑红**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest tests/python/test_dashboard_inspect.py -k statement_by_id -q`
Expected: FAIL(404 route 未定义 → 实际返回 404 但 roundtrip 拿不到 200;或 `statement_by_id` AttributeError)。

- [ ] **Step 3: 实现 `queries.statement_by_id`**

在 `python/starling/dashboard/queries.py` 的 `statements(...)` 函数后追加:

```python
def statement_by_id(db_path: str, tenant: str, statement_id: str) -> dict | None:
    """Single statement by id, tenant-scoped. None when absent or cross-tenant."""
    with open_ro(db_path) as conn:
        rows = _rows(
            conn,
            "SELECT id, holder_id, holder_perspective, subject_id, predicate, "
            "object_kind, object_value, modality, polarity, confidence, salience, "
            "observed_at, review_status, consolidation_state, nesting_depth, "
            "created_at, updated_at "
            "FROM statements WHERE tenant_id = ? AND id = ?",
            (tenant, statement_id),
        )
        return rows[0] if rows else None
```

- [ ] **Step 4: 实现 route**

`python/starling/dashboard/routes/inspect.py` —— 改 import 行加 `HTTPException`,在 `queues` route 后、`return router` 前追加 route:

```python
from fastapi import APIRouter, Depends, HTTPException, Request
```
```python
    @router.get("/statement/{statement_id}")
    async def statement(request: Request, statement_id: str):
        c = _cfg(request)
        row = queries.statement_by_id(c.db_path, c.tenant, statement_id)
        if row is None:
            raise HTTPException(status_code=404, detail="not_found")
        return row
```

- [ ] **Step 5: 跑绿**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest tests/python/test_dashboard_inspect.py -q`
Expected: PASS(含既有 + 2 新)。

- [ ] **Step 6: commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add python/starling/dashboard/queries.py python/starling/dashboard/routes/inspect.py tests/python/test_dashboard_inspect.py
git commit -F - <<'EOF'
feat(P3.b2/dash): GET /api/statement/{id} 单条点读

queries.statement_by_id(tenant-scoped read-only)+ inspect route,
404 when absent/cross-tenant。供 OpenClaw 插件 get 能力用。

EOF
```

---

## Task 2: `POST /api/forget` → forgotten(C++ store + facade + binding + Python + route)

**Files:**
- Modify: `include/starling/store/statement_store.hpp`, `include/starling/store/sqlite_statement_store.hpp`, `src/store/sqlite_statement_store.cpp`
- Modify: `include/starling/memory/memory_ops.hpp`, `src/memory/memory_ops.cpp`, `bindings/python/bind_13_memory_ops.cpp`
- Modify: `python/starling/_memory_core.py`, `python/starling/dashboard/engine.py`, `python/starling/dashboard/routes/commands.py`
- Test: `tests/cpp/test_statement_store.cpp`, `tests/python/test_dashboard_commands.py`

### 2a — C++ `StatementStore.forget`(TDD)

- [ ] **Step 1: 写失败 ctest**

`tests/cpp/test_statement_store.cpp` 追加(用既有 `make_adapter`/`seed`/`state_of` helper):

```cpp
TEST(StatementStore, ForgetMovesNonterminalToForgotten) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "s1", "consolidated");
    seed(a->connection(), "s2", "archived");
    EXPECT_EQ(st.forget("s1", "default", "2026-06-15T00:00:00Z"), 1);
    EXPECT_EQ(state_of(a->connection(), "s1"), "forgotten");
    EXPECT_EQ(st.forget("s2", "default", "2026-06-15T00:00:00Z"), 1);
    EXPECT_EQ(state_of(a->connection(), "s2"), "forgotten");
}

TEST(StatementStore, ForgetIsIdempotentAndTenantScoped) {
    auto a = make_adapter();
    SqliteStatementStore st(a->connection());
    seed(a->connection(), "s1", "forgotten");
    EXPECT_EQ(st.forget("s1", "default", "2026-06-15T00:00:00Z"), 0);   // 已 forgotten 不动
    seed(a->connection(), "s2", "consolidated");
    EXPECT_EQ(st.forget("s2", "other-tenant", "2026-06-15T00:00:00Z"), 0);  // 跨租户不动
    EXPECT_EQ(state_of(a->connection(), "s2"), "consolidated");
}
```

- [ ] **Step 2: 跑红**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build && (cd build && ctest -R StatementStore.Forget --output-on-failure)`
Expected: 编译失败(`forget` 未声明)。

- [ ] **Step 3: 声明 + 实现 `forget`**

`include/starling/store/statement_store.hpp` —— 在 `archive_nonterminal` 声明后追加:

```cpp
    // P3.b2 逻辑删除: any state → forgotten(真移出检索;幂等,已 forgotten 不动)。
    // recall SQL 仅取 consolidated/archived,故 forgotten 立即不可检索;向量/投影
    // 物理清理由 tick 的 embedding_worker/projection 最终一致跟进。
    virtual int forget(std::string_view id, std::string_view tenant,
                       std::string_view updated_at) = 0;
```

`include/starling/store/sqlite_statement_store.hpp` —— 在 `archive_nonterminal` override 后追加:

```cpp
    int forget(std::string_view, std::string_view, std::string_view) override;
```

`src/store/sqlite_statement_store.cpp` —— 在 `archive_nonterminal` 实现后追加(镜像其结构):

```cpp
int SqliteStatementStore::forget(std::string_view id, std::string_view tenant,
                                 std::string_view updated_at) {
    // P3.b2:→ forgotten(逻辑删除终态),幂等守卫已 forgotten 不动。
    sqlite3* db = conn_.raw();
    const char* sql =
        "UPDATE statements SET consolidation_state='forgotten', updated_at=? "
        "WHERE id=? AND tenant_id=? "
        "  AND consolidation_state != 'forgotten'";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "StatementStore::forget prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, updated_at);
    bind_sv(h.get(), 2, id);
    bind_sv(h.get(), 3, tenant);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "StatementStore::forget step");
    return sqlite3_changes(db);
}
```

- [ ] **Step 4: 跑绿(ctest)**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build && (cd build && ctest -R StatementStore --output-on-failure)`
Expected: PASS(含 2 新 Forget 测试 + 既有 StatementStore 测试不退)。

### 2b — `memoryops::forget` facade + binding

- [ ] **Step 5: 声明 + 实现 facade**

`include/starling/memory/memory_ops.hpp` —— 在 `tick_all` 声明后追加(对齐既有 namespace `starling::memoryops`):

```cpp
// P3.b2:逻辑删除一批 statements(→forgotten),返回实际转换计数。
int forget(persistence::SqliteAdapter& adapter, std::string_view tenant,
           const std::vector<std::string>& ids, std::string_view now_iso);
```

`src/memory/memory_ops.cpp` —— 顶部 include 加 `#include "starling/store/sqlite_statement_store.hpp"`;在 `tick_all` 实现后、`}  // namespace` 前追加:

```cpp
int forget(persistence::SqliteAdapter& adapter, std::string_view tenant,
           const std::vector<std::string>& ids, std::string_view now_iso) {
    auto& conn = adapter.connection();
    int n = 0;
    for (const auto& id : ids)
        n += store::SqliteStatementStore(conn).forget(id, tenant, now_iso);
    return n;
}
```

- [ ] **Step 6: 绑定 `memory_forget`**

`bindings/python/bind_13_memory_ops.cpp` —— 在 `memory_tick_all` 的 `m.def` 后、`}` 前追加(facade 是纯 C++ + SQLite,释放 GIL):

```cpp
    m.def("memory_forget",
          [](starling::persistence::SqliteAdapter& adapter,
             const std::string& tenant, const std::vector<std::string>& ids,
             const std::string& now_iso) {
              int n = 0;
              {
                  py::gil_scoped_release release;
                  n = starling::memoryops::forget(adapter, tenant, ids, now_iso);
              }
              return n;
          },
          py::arg("adapter"), py::arg("tenant"), py::arg("ids"), py::arg("now_iso"));
```

- [ ] **Step 7: 重建 editable `_core`**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build --python-editable`
Expected: 构建成功;`.venv/bin/python -c "from starling import _core; print(hasattr(_core,'memory_forget'))"` → `True`。

### 2c — Python 转发 + route(TDD)

- [ ] **Step 8: 写失败 pytest**

`tests/python/test_dashboard_commands.py` 追加:

```python
def test_forget_removes_from_recall(client):
    rid = client.post("/api/remember", json={"text": "Bob owns auth"}).json()
    sid = rid["statement_ids"][0]
    client.post("/api/tick", json={})
    assert client.post("/api/recall", json={"query": "auth", "k": 5}).json()["results"]
    f = client.post("/api/forget", json={"ids": [sid]})
    assert f.status_code == 200 and f.json()["forgotten"] == 1
    hits = client.post("/api/recall", json={"query": "auth", "k": 5}).json()["results"]
    assert all(h["subject"] != "Bob" or h["predicate"] != "responsible_for" for h in hits) \
        or hits == []   # forgotten 立即移出检索


def test_forget_idempotent(client):
    f = client.post("/api/forget", json={"ids": ["nope"]})
    assert f.status_code == 200 and f.json()["forgotten"] == 0
```

- [ ] **Step 9: 跑红**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest tests/python/test_dashboard_commands.py -k forget -q`
Expected: FAIL(404,`/api/forget` 未定义)。

- [ ] **Step 10: MemoryCore.forget + engine.forget**

`python/starling/_memory_core.py` —— `MemoryCore` 加方法(close 前):

```python
    def forget(self, ids, *, now=None) -> dict:
        """逻辑删除(→forgotten):核心 `memoryops::forget`,这里只签名归一。
        forgotten 立即移出检索;向量/投影清理由 tick 跟进。"""
        now_iso = parse_now(now).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        n = _core.memory_forget(self.rt.adapter, tenant=self.tenant,
                                ids=list(ids), now_iso=now_iso)
        return {"forgotten": n}
```

`python/starling/dashboard/engine.py` —— 加转发(对齐既有 `remember`/`tick` 单行转发,持引擎写锁;参照该文件 remember 是否包 `with self._lock`,一致即可):

```python
    def forget(self, ids, *, now=None) -> dict:
        return self._core.forget(ids, now=now)
```

- [ ] **Step 11: route**

`python/starling/dashboard/routes/commands.py` —— 加 body model(与 `RememberBody` 并列)+ route(`working_set` 后、`return router` 前):

```python
class ForgetBody(BaseModel):
    ids: list[str]
    now: str | None = None
```
```python
    @router.post("/forget")
    async def forget(body: ForgetBody, request: Request):
        eng = _engine(request)
        r = await to_thread.run_sync(partial(eng.forget, body.ids, now=body.now))
        await _broadcast(request, "statement_forgotten", r)
        return r
```

- [ ] **Step 12: 跑绿**

Run: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest tests/python/test_dashboard_commands.py -q`
Expected: PASS(含既有 + 2 新 forget)。

- [ ] **Step 13: 回归 + commit**

Run: `(cd build && ctest --output-on-failure) && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest tests/python -q`
Expected: ctest 全绿(新增 2 + 既有不退)+ pytest 全绿。

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add include/starling/store/statement_store.hpp include/starling/store/sqlite_statement_store.hpp src/store/sqlite_statement_store.cpp \
        include/starling/memory/memory_ops.hpp src/memory/memory_ops.cpp bindings/python/bind_13_memory_ops.cpp \
        python/starling/_memory_core.py python/starling/dashboard/engine.py python/starling/dashboard/routes/commands.py \
        tests/cpp/test_statement_store.cpp tests/python/test_dashboard_commands.py
git commit -F - <<'EOF'
feat(P3.b2): POST /api/forget → forgotten 逻辑删除

StatementStore.forget(→forgotten 幂等守卫)+ memoryops::forget facade +
memory_forget 绑定 + MemoryCore/engine 转发 + dashboard route。forgotten
立即移出检索(recall SQL 仅 consolidated/archived);向量/投影清理 tick 跟进。
供 OpenClaw 插件 remove 能力用。

EOF
```

---

## Task 3: 最小「hello memory」插件骨架 + docker 加载验收

**契约已确定(探查完成):** 见 `docs/superpowers/specs/2026-06-15-p3-b2-openclaw-contract.md`——hybrid runtime 路线(`registerMemoryRuntime` + `registerTool`(memory_store/forget)+ `registerMemoryFlushPlan` + hooks),`MemorySearchManager` 文件/行读模型,synthetic path `statement://<tenant>/<id>`。本 Task:落最小可加载插件骨架(占槽 + `registerMemoryRuntime` stub manager 打通),Task 4-6 据契约展开七能力。**docker 验收(不污染本机 OpenClaw)。**

**Files:**
- Create: `integrations/openclaw/openclaw.plugin.json`, `package.json`, `tsconfig.json`, `src/index.ts`(最小)
- Create: `integrations/openclaw/docker/openclaw.Dockerfile`, `docker/README.md`(探查用最小镜像)

_(注册契约探查已完成,固化于 `docs/superpowers/specs/2026-06-15-p3-b2-openclaw-contract.md`;以下落最小骨架。)_

- [ ] **Step 2: 最小插件骨架**

`openclaw.plugin.json`(照 lancedb 模板,configSchema 换 Starling 字段):

```json
{
  "id": "starling",
  "kind": "memory",
  "configSchema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "dashboardUrl": { "type": "string" },
      "token": { "type": "string" },
      "tenant": { "type": "string" },
      "holder": { "type": "string" },
      "autoCapture": { "type": "boolean" },
      "autoRecall": { "type": "boolean" }
    },
    "required": ["dashboardUrl", "token"]
  }
}
```

`package.json`:

```json
{
  "name": "@starling/openclaw-memory",
  "version": "0.1.0",
  "type": "module",
  "openclaw": { "extensions": ["./dist/index.js"] }
}
```

`src/index.ts` —— `definePluginEntry({id:"starling",kind:"memory",configSchema,register(api){ api.registerMemoryRuntime(stub); }})`,stub.getMemorySearchManager 返回 manager:`search→[]`、`readFile→{text:"",path}`、`status→ok`、`probes→false`(契约 §C skeleton)。验证插件被 OpenClaw 加载 + 占槽 + builtin memory_search 命中 stub。

- [ ] **Step 3: 验收(docker 内)**

`openclaw.Dockerfile`:node 基础镜像 → `npm i -g openclaw`(或 host 版本对齐)→ 装本插件 → 配 `plugins.slots.memory = "starling"`。启动 OpenClaw,触发一次 memory_search → 看到插件 stub 返回(日志/输出)。
Expected: OpenClaw 启动无插件加载错误;memory_search 命中本插件(即使返回空)。

- [ ] **Step 4: commit**

```bash
cd /Users/jaredguo-mini/develop/memory/starling
git add integrations/openclaw/openclaw.plugin.json integrations/openclaw/package.json integrations/openclaw/tsconfig.json integrations/openclaw/src/index.ts integrations/openclaw/docker/openclaw.Dockerfile integrations/openclaw/docker/README.md
git commit -F - <<'EOF'
feat(P3.b2/plugin): OpenClaw memory 注册契约 + 最小插件骨架

确定 plugins.slots.memory 注册 API(见 docker/README 契约),最小插件
可被 OpenClaw 加载且一个能力打通。Task 4-6 据此展开七能力。

EOF
```

---

## Task 4: `config.ts` + `map.ts`(config 校验 + 能力↔dashboard 映射)

**Files:** Create `integrations/openclaw/src/config.ts`, `src/map.ts`, `test/map.test.ts`

**说明:** dashboard 侧请求/响应 schema **已确定**(下表),OpenClaw 侧入参 schema 用 Task 3 契约。map 是无 I/O 纯函数,便于单测。

dashboard 契约(确定):
- `POST /api/remember` `{text, holder?, interlocutor?, now?}` → `{engram_ref, statement_ids, outcome}`
- `POST /api/recall` `{query, perspective?, k?, mode?, intent?, target?}` → `{results:[{subject,predicate,object,score}]}`(intent 非空走 planner 返回 `{results,context_pack,...}`)
- `GET /api/working_set?interlocutor=&goal=&token_budget=` → working set(含 `render`)
- `POST /api/forget` `{ids, now?}` → `{forgotten}`
- `GET /api/statement/{id}` → statement dict | 404
- `POST /api/tick` `{now?}` → 维护计数

- [ ] **Step 1: 写失败 vitest(map 纯函数)** —— 针对每个能力写一条:给定 OpenClaw 入参(Task 3 形状)→ 断言产出确切 dashboard request(method/path/body);给定 dashboard response → 断言产出 OpenClaw 期望的 memory 结果形状(如 recall results 拼 `subject predicate object` 文本 + score)。
- [ ] **Step 2: 跑红** `cd integrations/openclaw && npx vitest run test/map.test.ts`
- [ ] **Step 3: 实现 `map.ts`**(契约 §B 适配规则)—— 纯函数:**search**:recall `{results}` → `MemorySearchResult[]`(`path="statement://<tenant>/<id>"`、`startLine=endLine=0`、`snippet="<subject> <predicate> <object>"`、`score`、`source:"memory"`、`citation=<id>`);**get**:`readFile.relPath` 反解 `statement://<tenant>/<id>` → id(+ tenant 校验) → `{text:渲染, path:relPath}`;**recall(auto)**:working_set.render → `{prependContext}`;**capture**:`{text}` → remember body(holder=config.holder/agent);**remove**:`{memoryId}` → forget `{ids:[memoryId]}`;**index**:→ tick(或 no-op)。synthetic path 编/解码是核心纯函数(`encodePath(tenant,id)`/`decodePath(relPath)`),单测覆盖往返 + 非法 path 降级。
- [ ] **Step 4: 实现 `config.ts`** —— 解析校验 `dashboardUrl/token/tenant/holder/autoCapture/autoRecall`,缺 required 报明确错误;token 只入内存不打日志。
- [ ] **Step 5: 跑绿 + commit**(explicit-path add `integrations/openclaw/src/config.ts src/map.ts test/map.test.ts`)。

---

## Task 5: `client.ts`(HTTP + 读降级 + 写重试队列)

**Files:** Create `integrations/openclaw/src/client.ts`, `test/client.test.ts`

**说明:** 纯 HTTP 传输 + 容错,**不依赖 OpenClaw API**,可确切实现。`fetch` + `Authorization`/token header(对齐 dashboard `require_token` 的鉴权头格式,Task 3 确认 header 名)。

- [ ] **Step 1: 写失败 vitest(mock fetch):**
  - 读(GET/recall)dashboard 不可达(fetch reject)→ 返回空结果 + 不抛(降级)。
  - 写(remember/forget)失败 → 入重试队列,下次 flush 成功后队列清空;指数退避。
  - 401 → 不重试,抛配置错误(明确分类)。
- [ ] **Step 2: 跑红** `npx vitest run test/client.test.ts`
- [ ] **Step 3: 实现 `client.ts`:** `get/post` 包 fetch + token header;读路径 try/catch → 空+warn;写路径失败 → 内存队列(可选磁盘持久化于插件 data dir)+ 指数退避重试(上限可配);401 单独抛。token 绝不入日志/错误消息。
- [ ] **Step 4: 跑绿 + commit**(explicit-path add `src/client.ts test/client.test.ts`)。

---

## Task 6: `runtime.ts` + `index.ts`(MemoryPluginRuntime + register 全挂)

**Files:** Modify `integrations/openclaw/src/index.ts`;Create `src/runtime.ts`

**说明:** 用契约(§B/§C)把能力挂到 OpenClaw。`runtime.ts` 导出 `makeStarlingRuntime(cfg,api)` 返回 `MemoryPluginRuntime`,外加 `buildPromptSection`/`buildFlushPlan`。

- [ ] **Step 1:** `runtime.ts` 的 `MemorySearchManager`:`search`=map.search→client.recall→map;`readFile`=map.get(decodePath)→client.statement→map;`sync`=client.tick(或 no-op);`status`=client.overview/ok;`probeEmbedding/Vector`=查 client config 就绪(降级 false)。读路径全经 client 降级(不可达→空,不抛)。
- [ ] **Step 2:** `buildFlushPlan`(契约 §E `MemoryFlushPlan`:softThresholdTokens/forceFlushTranscriptBytes/reserveTokensFloor/prompt/systemPrompt/relativePath)+ `buildPromptSection`(告知 memory_store/forget 工具存在)。
- [ ] **Step 3:** `index.ts` `definePluginEntry`(契约 §C skeleton):`registerMemoryRuntime(rt)` + `registerMemoryPromptSection` + `registerMemoryFlushPlan` + `registerTool(memory_store{text}→client.remember)` + `registerTool(memory_forget{memoryId}→client.forget)` + 条件 `api.on("before_agent_start"→prependContext=working_set)`(autoRecall) + `api.on("before_compaction"→读 sessionFile→remember)`(autoCapture)。
- [ ] **Step 4 验收:** `cd integrations/openclaw && npx tsc --noEmit` 通过 + 插件加载无错(docker,Task 7 端到端)。
- [ ] **Step 5: commit**(explicit-path add `src/runtime.ts src/index.ts`)。

---

## Task 7: docker compose + 集成测试 + README

**Files:** Create `integrations/openclaw/docker/docker-compose.yml`, 完善 `openclaw.Dockerfile`, `README.md`

> **拓扑修正(Task 7 实测):** Starling `_core.so` 是 macOS Mach-O(arm64),**不能在 Linux
> 容器加载**。故 **dashboard 跑本机 host(非容器)**,OpenClaw 跑容器经 `host.docker.internal`
> 连本机;compose **只含 `openclaw` 一个服务**(无 starling 服务、无本机挂载)。原 Step 1 的
> 「starling 容器挂载本机 venv 复用 _core.so」**作废**,以下为已实现版本。

- [x] **Step 1: compose 单服务 + 本机 dashboard**
  - **本机起 Starling**(repo 根):`STARLING_DASH_HOST=0.0.0.0 .venv/bin/python scripts/run_dashboard.py --no-build`(必须 bind `0.0.0.0`,默认 `127.0.0.1` 容器够不着;token 在 `~/.starling/starling.json`)。
  - `openclaw`:`openclaw.Dockerfile`(node:22-slim)`npm i -g openclaw@2026.6.6`(pin)+ **镜像内 `tsc` build 本插件**到 `/opt/starling-plugin`;`entrypoint.sh` 运行时按 env 渲染 `openclaw.json`:`plugins.load.paths=["/opt/starling-plugin"]` + `plugins.slots.memory="starling"` + `dashboardUrl="http://host.docker.internal:<port>"` + token/tenant(env,**不写进 image 层/git**)。compose `extra_hosts:["host.docker.internal:host-gateway"]`。
  - **config 解析坑(2026.6.6 实测):** OpenClaw 用 **`OPENCLAW_CONFIG_PATH`** 定位 config;**切勿设 `OPENCLAW_HOME`**(会被当自身 base dir 追加 `/.openclaw`,config 静默移位 → 插件不被发现)。
- [x] **Step 2: 集成测试脚本(`integration-test.sh` + `roundtrip.mjs`/`downgrade.mjs`)**
  - host 端编排:`compose up` → `openclaw plugins inspect starling`(loaded)→ 容器内 `roundtrip.mjs`(import 编译后 `dist/*.js`)发 capture → host `GET /api/overview` 验证 `counts.statements` 增(**实测 0→1 通过**);recall 为 best-effort(见下观察)。
  - 降级(`downgrade.mjs`):client 指不可达 URL → 读返回 []/null(不抛)、写入重试队列(queueLength 增);URL 恢复 → `flushQueue()` 排空。**实测全绿。**
- [x] **Step 3: README**(`docker/README.md`)—— 起停 + 集成测试步骤 + 配置(token/tenant/holder 经 env)+ **实测观察 1-7**;强调 token 不入 image/git。
- [ ] **Step 4:** 回归 `(cd build && ctest)` + `pytest`(确认 Task 1-2 后端未退);commit(explicit-path add `docker/*` + 改的文档)。

**实测遗留观察(详见 README §4):** ① 写路径端到端通(容器→host 跨界建 statement + 向量);
② `/api/recall`/`/api/working_set` 对刚 remember 的数据返空(host 端直调 `DashboardEngine.recall`
亦复现)—— **Starling 检索内部行为,非插件/docker 缺陷**,留 Starling 侧跟进;插件已对空降级不中断;
③ 插件 doctor(2026.6.6)要求 manifest 声明 `contracts.tools:["memory_store","memory_forget"]`
才能干净注册两个写工具(非致命,插件仍占槽加载)—— 留插件侧 follow-up。

---

## Self-Review

- **Spec coverage:** 七能力(T4 map + T6 runtime)、tenant/holder 映射(T4 config)、读降级+写重试(T5)、remove→forgotten(T2)、get(T1)、docker 集成(T7:单 openclaw 容器 + 本机 dashboard,经 `host.docker.internal`;原「两服务挂载本机 venv」因 macOS Mach-O `_core.so` 不能进 Linux 容器而修正)、最小后端增量(T1-2)—— 全覆盖。
- **接口未定的诚实处理:** OpenClaw 注册 API 形状是真实未定点,集中在 Task 3 关卡解决,Task 4-6 显式依赖其产出(符合「禁止跨阶段预写未定接口」);dashboard 侧 schema 已确定故 Task 1-2/4/5 给确切代码。
- **类型一致:** `forget(ids)`→`memory_forget(adapter,tenant,ids,now_iso)`→`StatementStore.forget(id,tenant,updated_at)` 贯穿一致;`statement_by_id(db_path,tenant,id)` 与 route 一致;`{forgotten}`/`{results}` 响应键贯穿 pytest 断言一致。
- **边界:** C++ 仅 `StatementStore.forget` + `memoryops::forget`(核心语义入核);Python/TS 转发;forgotten 派生清理走 tick(一致性模型对齐 P3.b1)。

## Execution Handoff

**计划完成,保存于 `docs/superpowers/plans/2026-06-15-p3-b2-openclaw-memory-plugin.md`。两种执行方式:**

1. **Subagent-Driven(推荐)** —— 每 Task 派 fresh subagent + 两阶段 review(spec 合规 → 代码质量),Task 间快速迭代。
2. **Inline Execution** —— 本会话内分批执行 + 检查点。

**注:** Task 1-2(Starling 后端)确定可立即 TDD 执行;Task 3 是 docker 内 OpenClaw 探查关卡,需 docker 环境就绪。建议先执行 Task 1-2(补齐后端端点),再进 Task 3-7(插件 + docker)。
