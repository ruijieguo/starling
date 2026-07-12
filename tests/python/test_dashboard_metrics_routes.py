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
    assert series[0]["backlog_avg"] == 6.0            # (5+7)/2,round(...,1)
    assert series[0]["embedded"] == 12                # 桶内最后一条样本的值(非求和)
    assert series[1]["backlog_avg"] == 2.0 and series[1]["embedded"] == 20


def test_latency_buckets_percentiles(env):
    cfg, client = env
    _seed_extraction(cfg, [("2026-07-12T00:00:10Z", 100, 50), ("2026-07-12T00:00:20Z", 300, 60),
                           ("2026-07-12T00:00:30Z", 200, 70)])
    r = client.get("/api/metrics/latency?since=2026-07-11T00:00:00Z&bucket=3600")
    assert r.status_code == 200
    b = r.json()["series"][0]
    assert b["count"] == 3 and b["total_tokens"] == 180
    assert 100 <= b["p50_ms"] <= 300 and b["p95_ms"] >= b["p50_ms"]


def test_latency_cross_bucket(env):
    cfg, client = env
    _seed_extraction(cfg, [("2026-07-12T00:00:10Z", 100, 50), ("2026-07-12T00:00:20Z", 300, 60),
                           ("2026-07-12T01:00:10Z", 200, 70)])
    r = client.get("/api/metrics/latency?since=2026-07-11T00:00:00Z&bucket=3600")
    assert r.status_code == 200
    series = r.json()["series"]
    assert len(series) == 2                          # 两个小时桶
    assert series[0]["count"] == 2 and series[0]["total_tokens"] == 110
    assert series[1]["count"] == 1 and series[1]["total_tokens"] == 70


def test_embed_depth_missing_metrics_db_returns_empty(env):
    cfg, client = env
    # metrics.db 从未被采样器建过(Task 1 采样器与本查询解耦,谁先跑不影响另一方)——
    # 缺文件必须诚实返回空 series,不 500。
    r = client.get("/api/metrics/embed_depth?since=2026-07-11T00:00:00Z&bucket=3600")
    assert r.status_code == 200
    assert r.json() == {"series": []}


def test_bucket_zero_does_not_500(env):
    cfg, client = env
    _seed_metrics(cfg, [("2026-07-12T00:00:10Z", 5, 10)])
    r = client.get("/api/metrics/embed_depth?since=2026-07-11T00:00:00Z&bucket=0")
    assert r.status_code == 200                      # 路由钳制 bucket>=1,不除零 500
    assert len(r.json()["series"]) == 1


def test_metrics_requires_token(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "cmd.db"), token="secret")
    eng = DashboardEngine(cfg)
    client = TestClient(create_app(cfg, engine=eng))
    assert client.get("/api/metrics/embed_depth").status_code == 401
    assert client.get("/api/metrics/latency").status_code == 401
    assert client.get("/api/metrics/gist_quality").status_code == 401


# ── gist_quality (Task 3): funnel(candidates+abstracted) + confidence/member/summary
# distributions. funnel is only two stages — NOT the full candidates→abstracted/
# gated/failed pipeline — because replay_scheduler.cpp's write_ledger only persists
# ops_applied_json={"compress","gist_candidates"}; abstracted/gated/failed never hit
# the ledger. So candidates comes from replay_ledger.ops_applied_json (bucketed by
# started_at) and abstracted comes from counting consolidation_abstract statements
# (bucketed by created_at) — each such statement IS a promoted gist. ──
def _seed_gist(cfg):
    conn = sqlite3.connect(cfg.db_path)
    # replay_ledger: one idle batch, ops_applied_json carries gist_candidates=3.
    conn.execute("INSERT INTO replay_ledger(replay_batch_id,mode,sampled_count,ops_applied_json,started_at)"
                 " VALUES('b1','idle',3,'{\"compress\":0,\"gist_candidates\":3}','2026-07-12T00:00:10Z')")
    # consolidation_abstract statements (the gists themselves): distinct
    # confidence/derived_from/summary to drive the three distribution assertions.
    # Column set is the full real NOT NULL set from `PRAGMA table_info(statements)`
    # (the brief's sample row omitted affect_json, which is NOT NULL with no default).
    for i, (conf, df, summ) in enumerate([(0.82, '["a","b"]', "People value X"),
                                          (0.55, '["a","b","c"]', "A longer summary sentence here")]):
        conn.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
            "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
            "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
            "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
            "derived_from_json,consolidation_summary,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"g{i}", "default", "__common_ground__", "inferred", "entity",
             "__people__", "values", "str", f"X{i}", ("h" + str(i)) * 16,
             "v1", "believes", "pos", conf, "2026-07-12T00:00:10Z", 0.5,
             "{}", 0.0, "2026-07-12T00:00:10Z", "consolidation_abstract", "consolidated",
             "approved", df, summ, "2026-07-12T00:00:10Z", "2026-07-12T00:00:10Z"))
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
