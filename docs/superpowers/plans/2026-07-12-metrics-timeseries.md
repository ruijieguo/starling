# 信号时间序列仪表化(dogfood 子项 B)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 3 个只读 API 端点把 embed 队列深度、extraction 延迟、gist 质量代理呈现为时间分桶序列,回答 gated 问题(P3.c 并发 / 方案2 确认 / gist v2 default-flip)。

**Architecture:** 纯 host 仪表化。大部分信号从既有表**只读派生**(extraction_attempt、replay_ledger、consolidation_abstract statements);唯一需**采样**的 embed 队列深度由后台 tick 回调每轮追加到 host 自持 `~/.starling/metrics.db`(独立于 core 的 dashboard.db,天然单写者)。零 C++ 内核改动。

**Tech Stack:** FastAPI host(`python/starling/dashboard/`)、sqlite3(host metrics.db + 只读派生)、Python `statistics`(百分位)。**无 C++。**

**Approved spec:** `docs/superpowers/specs/2026-07-12-metrics-timeseries-design.md`(@ `429b7eb`)。

**⚠️ spec 修正(勘察 2026-07-12,已折叠进本计划 Task 3):** spec §③ 设想 gist funnel = candidates→abstracted/gated/failed 全从 `replay_ledger.ops_applied_json` 派生。但 `src/replay/replay_scheduler.cpp:385-386` 写的 `ops_applied_json` **只含 `{compress, gist_candidates}`**——`abstracted/gist_gated/gist_failed` 未持久化。修正:funnel = **`gist_candidates`(replay_ledger)+ `abstracted`(= `consolidation_abstract` statements 按 `created_at` 计数,每个促成 gist 就是一条 statement)**,给出**促成率**(gist v2 的核心信号);`gist_gated/gist_failed` 需 C++ 改 replay 才能持久化 → **deferred backlog**(保持本 slice 零内核)。

## Global Constraints

- 架构边界(硬):全 host 应用适配——只读派生查询 + host 自持采样表 + host tick 回调;零 C++ 内核改动;`metrics.db` 是 host 建表(`CREATE TABLE IF NOT EXISTS` via 独立 sqlite3 连接)不进 C++ MigrationRunner;不碰 C++ HealthSampler(健康门);不动 `TickOutcome`(加 dict 字段=已知地雷撞 `TickStats(**dict)`)。
- 单写者不变:`metrics.db` 唯一写者=采样器(host 后台 tick 线程),不与 core `dashboard.db` 共享写连接;API 端点只读 `mode=ro` 打开 `metrics.db` 与 `dashboard.db`。
- 采样器保活:异常吞掉记 log 不杀 tick(对齐现有 background tick 异常处理)。
- 只读端点:经 `require_token`(无 token 401);派生查询走 `open_ro`/`mode=ro` 不改库。
- pytest 一律 `.venv/bin/python -m pytest`。零内核改动→无需 `configure_build`。
- git:显式路径 `git add`(禁 `.`/`-A`);不用 `--no-verify`/`--amend`;commit 尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- NEVER merge:PR + CI 绿 + 用户明确合并。

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `python/starling/dashboard/engine.py` | metrics.db 建表 + embed 深度采样器 + retention | + 方法 |
| `python/starling/dashboard/app.py` | lifespan/on_tick 每 tick 调采样器 | 改 on_tick |
| `python/starling/dashboard/queries.py` | 3 个只读派生 helper(embed_depth / latency / gist_quality) | + helper |
| `python/starling/dashboard/routes/inspect.py` | 3 个只读端点 | + 路由 |
| `tests/python/test_dashboard_metrics_sampler.py` | 采样器 | 新建 |
| `tests/python/test_dashboard_metrics_routes.py` | 3 端点 | 新建 |

---

### Task 1: metrics.db 表 + embed 深度采样器

**Files:**
- Modify: `python/starling/dashboard/engine.py`(`__init__` 尾 + 新方法)
- Modify: `python/starling/dashboard/app.py`(lifespan 的 `_on_tick`)
- Test: `tests/python/test_dashboard_metrics_sampler.py`

**Interfaces:**
- Consumes:`self._db_path`(engine.py:155)、`self._lock`(仅读 dashboard.db 不必,但采样在 tick 线程);现有 `embedding_backlog` SQL(queries.py `queues`)。
- Produces:
  - `DashboardEngine.sample_embed_depth() -> None`(读 backlog+embedded → append 一行到 metrics.db → retention 裁剪)
  - `DashboardEngine._metrics_db_path`(= `Path(self._db_path).parent / "metrics.db"`)

- [ ] **Step 1: 写失败的采样器测试**

新建 `tests/python/test_dashboard_metrics_sampler.py`:

```python
import sqlite3
from pathlib import Path

from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB = ('[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob",'
         '"predicate":"responsible_for","object":"auth","modality":"BELIEVES",'
         '"polarity":"POS","nesting_depth":0}]')


def _engine(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "cmd.db"), token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter(); fake.set_default_response(_STUB, True, "")
    eng.llm = fake
    return cfg, eng


def _samples(cfg):
    conn = sqlite3.connect(str(Path(cfg.db_path).parent / "metrics.db"))
    try:
        return conn.execute(
            "SELECT ts, backlog, embedded FROM embed_depth_samples ORDER BY ts").fetchall()
    finally:
        conn.close()


def test_sample_appends_row_matching_backlog(tmp_path):
    cfg, eng = _engine(tmp_path)
    # 写一条未 embed 的 statement(backlog=1)
    eng.remember("Bob owns auth", holder="self")
    eng.sample_embed_depth()
    rows = _samples(cfg)
    assert len(rows) == 1
    # backlog 与 queries 的 embedding_backlog 口径一致(未 embed 的 statement 数)
    conn = sqlite3.connect(f"file:{cfg.db_path}?mode=ro", uri=True)
    backlog = conn.execute(
        "SELECT COUNT(*) FROM statements s LEFT JOIN statement_vectors v "
        "ON v.stmt_id=s.id WHERE s.tenant_id=? AND v.stmt_id IS NULL", ("default",)).fetchone()[0]
    conn.close()
    assert rows[0][1] == backlog


def test_retention_prunes_old_rows(tmp_path):
    cfg, eng = _engine(tmp_path)
    # 手动塞一行超出保留窗口的旧样本
    mp = Path(cfg.db_path).parent / "metrics.db"
    eng.sample_embed_depth()                      # 建表 + 一行 now
    conn = sqlite3.connect(str(mp))
    conn.execute("INSERT INTO embed_depth_samples(ts,backlog,embedded) VALUES('2020-01-01T00:00:00Z',9,9)")
    conn.commit(); conn.close()
    eng.sample_embed_depth()                      # 再采一次 → retention 应删 2020 那行
    tss = [r[0] for r in _samples(cfg)]
    assert not any(t.startswith("2020") for t in tss)


def test_sampler_swallows_errors_no_raise(tmp_path, monkeypatch):
    cfg, eng = _engine(tmp_path)
    monkeypatch.setattr(eng, "_metrics_db_path", Path("/nonexistent-dir/xx/metrics.db"))
    eng.sample_embed_depth()                       # 不抛(保活)
```

- [ ] **Step 2: 跑确认失败**

Run: `.venv/bin/python -m pytest tests/python/test_dashboard_metrics_sampler.py -q`
Expected: FAIL(`sample_embed_depth` 不存在)。

- [ ] **Step 3: 实现采样器**

`engine.py`(`import sqlite3`、`from datetime import datetime, timezone`、`from pathlib import Path` 已有;确认 `_now_iso` 模块级 helper 在)。`__init__` 末尾加:

```python
        # dogfood 子项 B:embed 深度采样序列。HOST 独立 sqlite(唯一写者=采样器,
        # 天然单写者;与 core 的 dashboard.db 无共享写连接)。非记忆 schema,不进
        # C++ MigrationRunner。
        self._metrics_db_path = Path(self._db_path).parent / "metrics.db"
        self._metrics_retention_days = 30
```

新方法(放在 `sample_embed_depth` 命名附近):

```python
    def sample_embed_depth(self) -> None:
        """采一个 embed 队列深度样本 → metrics.db(host,append-only + retention)。
        由后台 tick 每轮调用。异常吞掉记 log,绝不杀 tick(保活)。"""
        try:
            # 只读 dashboard.db 算 backlog(未 embed 的 statement 数)+ embedded 数
            with sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True) as ro:
                backlog = ro.execute(
                    "SELECT COUNT(*) FROM statements s LEFT JOIN statement_vectors v "
                    "ON v.stmt_id=s.id WHERE s.tenant_id=? AND v.stmt_id IS NULL",
                    (self._core.tenant,)).fetchone()[0]
                embedded = ro.execute(
                    "SELECT COUNT(*) FROM statement_vectors WHERE tenant_id=? AND status='embedded'",
                    (self._core.tenant,)).fetchone()[0]
            with sqlite3.connect(str(self._metrics_db_path)) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS embed_depth_samples ("
                    " ts TEXT NOT NULL, backlog INTEGER NOT NULL, embedded INTEGER NOT NULL)")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_embed_depth_ts ON embed_depth_samples(ts)")
                conn.execute("INSERT INTO embed_depth_samples(ts,backlog,embedded) VALUES(?,?,?)",
                             (_now_iso(), backlog, embedded))
                cutoff = (datetime.now(timezone.utc)
                          - timedelta(days=self._metrics_retention_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute("DELETE FROM embed_depth_samples WHERE ts < ?", (cutoff,))
                conn.commit()
        except Exception:  # noqa: BLE001 — 保活:采样失败不杀 tick
            logger.exception("embed-depth sampler failed")
```

(`from datetime import timedelta` 补进 import;`self._core.tenant` 是 MemoryCore 的 tenant——确认属性名,若不同据实改。)

- [ ] **Step 4: 挂到 tick**

`app.py` lifespan 的 `_on_tick(stats)`(:59)体内加一行(在广播前后均可):

```python
                def _on_tick(stats: dict) -> None:
                    if hasattr(eng, "sample_embed_depth"):
                        eng.sample_embed_depth()    # 子项 B:每 tick 采 embed 深度样本
                    asyncio.run_coroutine_threadsafe(
                        mgr.broadcast({"type": "tick", "payload": stats}), loop)
```

- [ ] **Step 5: 跑测试 + 全量回归 + Commit**

Run: `.venv/bin/python -m pytest tests/python/test_dashboard_metrics_sampler.py -q && .venv/bin/python -m pytest tests/python -q 2>&1 | tail -3`
Expected: 3 passed;全量绿。

```bash
git add python/starling/dashboard/engine.py python/starling/dashboard/app.py tests/python/test_dashboard_metrics_sampler.py
git commit -m "feat(metrics): embed-depth sampler → host metrics.db (per-tick, retention, keepalive)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `/api/metrics/embed_depth` + `/api/metrics/latency`

**Files:**
- Modify: `python/starling/dashboard/queries.py`(2 helper)
- Modify: `python/starling/dashboard/routes/inspect.py`(2 路由)
- Test: `tests/python/test_dashboard_metrics_routes.py`

**Interfaces:**
- Consumes:`open_ro(db_path)`(queries.py:17)、`_rows`(:28)、`_cfg(request)`(inspect.py:42)、`build_inspect_router` 模式;Task 1 的 `metrics.db`(path = `Path(db_path).parent/"metrics.db"`)。
- Produces:
  - `queries.metrics_embed_depth(db_path, since_iso, bucket_s) -> {"series":[{"bucket_ts","backlog_max","backlog_avg","embedded"}]}`
  - `queries.metrics_latency(db_path, tenant, since_iso, bucket_s) -> {"series":[{"bucket_ts","count","p50_ms","p95_ms","total_tokens"}]}`
  - `GET /api/metrics/embed_depth?since=&bucket=` / `GET /api/metrics/latency?since=&bucket=`

- [ ] **Step 1: 写失败的端点测试**

新建 `tests/python/test_dashboard_metrics_routes.py`(夹具:TestClient + 直接种子 metrics.db / extraction_attempt):

```python
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app
from starling.dashboard.engine import DashboardEngine


@pytest.fixture
def env(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "cmd.db"), token="")
    eng = DashboardEngine(cfg)
    return cfg, TestClient(create_app(cfg, engine=eng))


def _seed_metrics(cfg, rows):
    mp = Path(cfg.db_path).parent / "metrics.db"
    conn = sqlite3.connect(str(mp))
    conn.execute("CREATE TABLE IF NOT EXISTS embed_depth_samples("
                 "ts TEXT NOT NULL, backlog INTEGER NOT NULL, embedded INTEGER NOT NULL)")
    conn.executemany("INSERT INTO embed_depth_samples VALUES(?,?,?)", rows)
    conn.commit(); conn.close()


def _seed_extraction(cfg, rows):
    conn = sqlite3.connect(cfg.db_path)
    for i, (ts, lat, tok) in enumerate(rows):
        conn.execute(
            "INSERT INTO extraction_attempt(id,pipeline_run_id,extraction_span_key,"
            "attempt_number,status,created_at,prompt_tokens,completion_tokens,total_tokens,latency_ms)"
            " VALUES(?,?,?,1,'success',?,0,0,?,?)",
            (f"e{i}", f"p{i}", f"span{i}", ts, tok, lat))
    conn.commit(); conn.close()


def test_embed_depth_buckets(env):
    cfg, client = env
    _seed_metrics(cfg, [("2026-07-12T00:00:10Z", 5, 10), ("2026-07-12T00:00:40Z", 7, 12),
                        ("2026-07-12T01:00:10Z", 2, 20)])
    r = client.get("/api/metrics/embed_depth?since=2026-07-11T00:00:00Z&bucket=3600")
    assert r.status_code == 200
    series = r.json()["series"]
    assert len(series) == 2                          # 两个小时桶
    assert series[0]["backlog_max"] == 7             # 第一个桶两样本 max


def test_latency_buckets_percentiles(env):
    cfg, client = env
    _seed_extraction(cfg, [("2026-07-12T00:00:10Z", 100, 50), ("2026-07-12T00:00:20Z", 300, 60),
                           ("2026-07-12T00:00:30Z", 200, 70)])
    r = client.get("/api/metrics/latency?since=2026-07-11T00:00:00Z&bucket=3600")
    assert r.status_code == 200
    b = r.json()["series"][0]
    assert b["count"] == 3 and b["total_tokens"] == 180
    assert 100 <= b["p50_ms"] <= 300 and b["p95_ms"] >= b["p50_ms"]


def test_metrics_requires_token(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "cmd.db"), token="secret")
    eng = DashboardEngine(cfg)
    client = TestClient(create_app(cfg, engine=eng))
    assert client.get("/api/metrics/embed_depth").status_code == 401
    assert client.get("/api/metrics/latency").status_code == 401
```

- [ ] **Step 2: 跑确认失败** — 404/无 helper。

- [ ] **Step 3: queries helper**

`queries.py` 加(百分位在 Python 算,避 SQLite 无 percentile;数据量小):

```python
def _bucket(ts: str, bucket_s: int) -> str:
    # ts ISO8601 → 桶起点 ISO(按 bucket_s 秒对齐)。用 epoch 整除。
    from datetime import datetime, timezone
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    epoch = int(dt.timestamp())
    start = epoch - (epoch % bucket_s)
    return datetime.fromtimestamp(start, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def metrics_embed_depth(db_path: str, since_iso: str, bucket_s: int) -> dict:
    mp = str(Path(db_path).parent / "metrics.db")
    import os
    if not os.path.exists(mp):
        return {"series": []}
    with open_ro(mp) as conn:
        rows = _rows(conn, "SELECT ts, backlog, embedded FROM embed_depth_samples "
                           "WHERE ts >= ? ORDER BY ts", (since_iso,))
    buckets: dict = {}
    for r in rows:
        b = _bucket(r["ts"], bucket_s)
        agg = buckets.setdefault(b, {"backlog_max": 0, "backlog_sum": 0, "n": 0, "embedded": 0})
        agg["backlog_max"] = max(agg["backlog_max"], r["backlog"])
        agg["backlog_sum"] += r["backlog"]; agg["n"] += 1; agg["embedded"] = r["embedded"]
    series = [{"bucket_ts": b, "backlog_max": a["backlog_max"],
               "backlog_avg": round(a["backlog_sum"] / a["n"], 1), "embedded": a["embedded"]}
              for b, a in sorted(buckets.items())]
    return {"series": series}


def _pct(sorted_vals: list, q: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, int(q * len(sorted_vals)))
    return int(sorted_vals[idx])


def metrics_latency(db_path: str, tenant: str, since_iso: str, bucket_s: int) -> dict:
    with open_ro(db_path) as conn:
        rows = _rows(conn, "SELECT created_at, latency_ms, total_tokens FROM extraction_attempt "
                           "WHERE created_at >= ? ORDER BY created_at", (since_iso,))
    buckets: dict = {}
    for r in rows:
        b = _bucket(r["created_at"], bucket_s)
        agg = buckets.setdefault(b, {"lat": [], "tokens": 0})
        agg["lat"].append(r["latency_ms"]); agg["tokens"] += r["total_tokens"] or 0
    series = []
    for b, a in sorted(buckets.items()):
        lat = sorted(a["lat"])
        series.append({"bucket_ts": b, "count": len(lat), "p50_ms": _pct(lat, 0.50),
                       "p95_ms": _pct(lat, 0.95), "total_tokens": a["tokens"]})
    return {"series": series}
```

(`from pathlib import Path` 确认在 queries.py import；tenant 参数留给 latency 若要按租户过滤——extraction_attempt 无 tenant_id 列则忽略 tenant,据 schema 定,当前 extraction_attempt 无 tenant_id 故不过滤。)

- [ ] **Step 4: 端点**

`inspect.py` 挨着现有只读路由加:

```python
    @router.get("/metrics/embed_depth")
    async def metrics_embed_depth(request: Request, since: str = "", bucket: int = 3600):
        c = _cfg(request)
        return queries.metrics_embed_depth(c.db_path, since or _default_since(), bucket)

    @router.get("/metrics/latency")
    async def metrics_latency(request: Request, since: str = "", bucket: int = 3600):
        c = _cfg(request)
        return queries.metrics_latency(c.db_path, c.tenant, since or _default_since(), bucket)
```

`_default_since()` 模块级 helper(inspect.py 或 queries.py):`(datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")`。

- [ ] **Step 5: 跑测试 + Commit**

Run: `.venv/bin/python -m pytest tests/python/test_dashboard_metrics_routes.py -q`
Expected: 3 passed。

```bash
git add python/starling/dashboard/queries.py python/starling/dashboard/routes/inspect.py tests/python/test_dashboard_metrics_routes.py
git commit -m "feat(metrics): GET /api/metrics/embed_depth + /latency (bucketed, host-derive)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `/api/metrics/gist_quality`

**Files:**
- Modify: `python/starling/dashboard/queries.py`(1 helper)
- Modify: `python/starling/dashboard/routes/inspect.py`(1 路由)
- Test: 扩 `tests/python/test_dashboard_metrics_routes.py`

**Interfaces:**
- Produces:`queries.metrics_gist_quality(db_path, tenant, since_iso, bucket_s) -> {"funnel":[{"bucket_ts","candidates","abstracted"}], "confidence":[{"bucket","n"}], "member_counts":[{"members","n"}], "summary_lengths":[{"len_bucket","n"}]}`;`GET /api/metrics/gist_quality?since=&bucket=`。

**⚠️ 修正(见 header):** `replay_ledger.ops_applied_json` 只含 `{compress, gist_candidates}`(`replay_scheduler.cpp:385-386`)——`abstracted/gated/failed` 未持久化。故 funnel = `gist_candidates`(解 `ops_applied_json`,按 `started_at` 桶)+ `abstracted`(= `consolidation_abstract` statements 按 `created_at` 同桶计数)。`gated/failed` 不派生(需 C++ 改 replay 持久化,deferred backlog)。

- [ ] **Step 1: 写失败的测试**(加到 test_dashboard_metrics_routes.py)

```python
def _seed_gist(cfg):
    conn = sqlite3.connect(cfg.db_path)
    # replay_ledger:两次 idle,ops_applied_json 含 gist_candidates
    conn.execute("INSERT INTO replay_ledger(replay_batch_id,mode,sampled_count,ops_applied_json,started_at)"
                 " VALUES('b1','idle',3,'{\"compress\":0,\"gist_candidates\":3}','2026-07-12T00:00:10Z')")
    # consolidation_abstract statements(促成的 gist):不同 confidence/derived_from/summary
    for i, (conf, df, summ) in enumerate([(0.82, '["a","b"]', "People value X"),
                                          (0.55, '["a","b","c"]', "A longer summary sentence here")]):
        conn.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,subject_id,predicate,object_value,"
            "provenance,confidence,derived_from_json,consolidation_summary,created_at,"
            "consolidation_state,review_status,modality,polarity,object_kind,subject_kind,"
            "holder_perspective,canonical_object_hash,canonical_object_hash_version,observed_at,"
            "salience,activation,last_accessed,replay_count,access_count,updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?, 'consolidated','approved','believes','pos','str',"
            "'cognizer','first_person',?, 'v1','2026-07-12T00:00:10Z',0.5,0.0,"
            "'2026-07-12T00:00:10Z',1,1,'2026-07-12T00:00:10Z')",
            (f"g{i}","default","__common_ground__","__people__","values",f"X{i}",
             "consolidation_abstract",conf,df,summ,"2026-07-12T00:00:10Z",("h"+str(i))*16))
    conn.commit(); conn.close()


def test_gist_quality_funnel_and_distributions(env):
    cfg, client = env
    _seed_gist(cfg)
    r = client.get("/api/metrics/gist_quality?since=2026-07-11T00:00:00Z&bucket=3600")
    assert r.status_code == 200
    d = r.json()
    assert d["funnel"][0]["candidates"] == 3 and d["funnel"][0]["abstracted"] == 2
    assert sum(c["n"] for c in d["confidence"]) == 2       # 两个 gist 的 confidence
    assert sum(m["n"] for m in d["member_counts"]) == 2    # derived_from 长度分布
    assert sum(s["n"] for s in d["summary_lengths"]) == 2
```

(注:`statements` 的完整列集以真实 schema 为准——implementer 先 `PRAGMA table_info(statements)` 取全 NOT NULL 列,种子行补齐;上面列集是示意,实现时据实补全避免 NOT NULL 报错。)

- [ ] **Step 2: 跑确认失败**。

- [ ] **Step 3: helper + 端点**

`queries.py`:

```python
def metrics_gist_quality(db_path: str, tenant: str, since_iso: str, bucket_s: int) -> dict:
    import json as _json
    with open_ro(db_path) as conn:
        led = _rows(conn, "SELECT ops_applied_json, started_at FROM replay_ledger "
                          "WHERE started_at >= ?", (since_iso,))
        gists = _rows(conn, "SELECT confidence, derived_from_json, consolidation_summary, created_at "
                            "FROM statements WHERE tenant_id=? AND provenance='consolidation_abstract' "
                            "AND created_at >= ?", (tenant, since_iso))
    # funnel:candidates(ledger)+ abstracted(consolidation_abstract 计数)按桶
    funnel: dict = {}
    for r in led:
        b = _bucket(r["started_at"], bucket_s)
        try:
            cand = int(_json.loads(r["ops_applied_json"] or "{}").get("gist_candidates", 0))
        except Exception:
            cand = 0
        funnel.setdefault(b, {"candidates": 0, "abstracted": 0})["candidates"] += cand
    for g in gists:
        b = _bucket(g["created_at"], bucket_s)
        funnel.setdefault(b, {"candidates": 0, "abstracted": 0})["abstracted"] += 1
    funnel_series = [{"bucket_ts": b, **v} for b, v in sorted(funnel.items())]
    # confidence 分布(0.1 桶)
    conf: dict = {}
    for g in gists:
        key = round(float(g["confidence"] or 0), 1)
        conf[key] = conf.get(key, 0) + 1
    # member 数分布 + summary 长度分布(0/50/100/200+ 桶)
    members: dict = {}
    summ: dict = {}
    for g in gists:
        try:
            m = len(_json.loads(g["derived_from_json"] or "[]"))
        except Exception:
            m = 0
        members[m] = members.get(m, 0) + 1
        slen = len(g["consolidation_summary"] or "")
        lb = "0-50" if slen < 50 else "50-100" if slen < 100 else "100-200" if slen < 200 else "200+"
        summ[lb] = summ.get(lb, 0) + 1
    return {"funnel": funnel_series,
            "confidence": [{"bucket": k, "n": v} for k, v in sorted(conf.items())],
            "member_counts": [{"members": k, "n": v} for k, v in sorted(members.items())],
            "summary_lengths": [{"len_bucket": k, "n": v} for k, v in summ.items()]}
```

`inspect.py`:

```python
    @router.get("/metrics/gist_quality")
    async def metrics_gist_quality(request: Request, since: str = "", bucket: int = 3600):
        c = _cfg(request)
        return queries.metrics_gist_quality(c.db_path, c.tenant, since or _default_since(), bucket)
```

- [ ] **Step 4: 跑测试 + 全量 + Commit**

Run: `.venv/bin/python -m pytest tests/python/test_dashboard_metrics_routes.py -q && .venv/bin/python -m pytest tests/python -q 2>&1 | tail -3`
Expected: 全绿。

```bash
git add python/starling/dashboard/queries.py python/starling/dashboard/routes/inspect.py tests/python/test_dashboard_metrics_routes.py
git commit -m "feat(metrics): GET /api/metrics/gist_quality (funnel candidates+abstracted, confidence/member/summary distributions)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 真机验证(手动,非 CI 门)

**Files:** ephemeral `$CLAUDE_JOB_DIR/tmp/metrics_e2e.sh`(不提交)。

- [ ] **Step 1: 重启 dashboard 上新代码**

`launchctl kickstart -k gui/$(id -u)/io.starling.dashboard`;等端口。

- [ ] **Step 2: 3 端点 curl(带 token)**

```bash
TOKEN=$(.venv/bin/python -c "import json;print(json.load(open('/Users/jaredguo-mini/.starling/starling.json'))['token'])")
for ep in embed_depth latency gist_quality; do
  echo "== /api/metrics/$ep =="
  curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8787/api/metrics/$ep?since=2026-07-01T00:00:00Z&bucket=3600" | python3 -m json.tool | head -20
done
```
断言:3 端点均 200 + 合理 JSON 结构。等几个 tick(~30s×N)看 `embed_depth.series` 增长;`latency` 应有历史 extraction_attempt 分桶(85 行数据)。

- [ ] **Step 3: 记录进 PR body**

真实 ingest 刚起步、gist 可能稀疏——如实报「端点工作 + latency 已有历史趋势 + embed_depth/gist_quality 待数据累积」。不 commit(ephemeral)。

---

## Self-Review

**1. Spec coverage:** spec §① 三族信号→Task1(embed 采样)+Task2(latency 派生)+Task3(gist 派生);§② metrics.db host 表→Task1;§③ 采样器蹭 tick→Task1 Step4;§④ 3 端点→Task2/3;§⑤ 架构边界(零C++/不碰HealthSampler/不动TickOutcome/metrics.db非migration)→Global Constraints;§⑥ 测试→各 Task;§⑦ 成功判据→Task4。**spec §③ funnel 修正**(abstracted/gated/failed 未持久化)已折叠进 header + Task3。✅
**2. Placeholder scan:** 无 TBD。三处「据实」(self._core.tenant 属性名、statements 完整 NOT NULL 列集、extraction_attempt 无 tenant_id 故 latency 不过滤)是标注的实现时对真实 schema 核实点,给了指引。✅
**3. Type consistency:** `sample_embed_depth()`、`metrics_embed_depth/metrics_latency/metrics_gist_quality(db_path,...)`、`_bucket/_pct/_default_since` helper 跨任务一致;metrics.db 路径 `Path(db_path).parent/"metrics.db"` 在采样器/embed_depth helper/测试一致;端点返回 shape(series/funnel/confidence/...)与测试断言一致。✅

## Execution Handoff

superpowers:subagent-driven-development(每任务 implementer+reviewer,最后 whole-branch review),按项目 cadence。然后 PR;CI 绿 + 用户明确合并。
