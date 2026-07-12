"""/api/metrics/embed_depth + /api/metrics/latency — dogfood 子项 B(Task 2)。

只读、host-derive 的时间分桶端点:embed_depth 读 Task 1 采样器写的 host
metrics.db(embed_depth_samples),latency 派生 dashboard.db 的
extraction_attempt(p50/p95 在 Python 算,避 SQLite 无 percentile)。两路由都
挂在 build_inspect_router 下,继承其 require_token 门(401 测试钉死)。
"""
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
