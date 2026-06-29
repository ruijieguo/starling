"""/api/vitals — Phase 0 read-only observability (pipeline lag + lifecycle stuck).

Mirrors test_dashboard_inspect's seed-then-TestClient pattern. Seeds a known
outbox head, a behind-checkpoint, a VOLATILE-stuck statement, a failed
extraction attempt, and an overdue reconsolidation window — then asserts the
vitals endpoint reports each, that lag is computed per pump, and that the
tenant-scoped blocks exclude other tenants.
"""
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from starling.dashboard import DashboardConfig, create_app

_STMT_COLS = (
    "id, tenant_id, holder_id, holder_perspective, subject_kind, subject_id, "
    "predicate, object_kind, object_value, canonical_object_hash, "
    "canonical_object_hash_version, modality, polarity, confidence, observed_at, "
    "salience, affect_json, activation, last_accessed, provenance, created_at, "
    "updated_at, consolidation_state"
)


def _stmt(conn, sid, tenant, state, *, salience=0.5, created="2026-04-10T10:00:00Z"):
    conn.execute(
        f"INSERT INTO statements ({_STMT_COLS}) VALUES ({','.join('?' * 23)})",
        (sid, tenant, "self", "first_person", "cognizer", "Bob", "responsible_for",
         "str", "auth", f"h{sid}", "v1", "BELIEVES", "POS", 0.9, "2026-04-10T10:00:00Z",
         salience, "{}", 0.0, "2026-04-10T10:00:00Z", "test", created,
         "2026-04-10T10:00:00Z", state),
    )


def _seed(db_path: str):
    from pathlib import Path
    from starling import runtime as rt
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r  # release the writer handle before raw seeding
    conn = sqlite3.connect(db_path)

    # outbox head = 5 (global); reconsolidation checkpoint behind at 3 -> lag 2
    conn.execute(
        "INSERT INTO bus_events (event_id, tenant_id, event_type, primary_id, "
        "aggregate_id, outbox_sequence, idempotency_key, payload_json, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        ("e5", "default", "statement.written", "s1", "s1", 5, "idem5", "{}",
         "2026-04-10T10:00:00Z"),
    )
    conn.execute(
        "UPDATE reconsolidation_checkpoint SET last_processed_outbox_sequence=3 WHERE id=1")

    _stmt(conn, "vol1", "default", "volatile", salience=0.004)   # stuck (default)
    _stmt(conn, "vol2", "other", "volatile")                      # other tenant
    _stmt(conn, "con1", "default", "consolidated")                # not stuck

    conn.execute("INSERT INTO pipeline_run (id, tenant_id, started_at, status) "
                 "VALUES (?,?,?,?)", ("pr1", "default", "2026-04-10T10:00:00Z", "failed"))
    conn.execute(
        "INSERT INTO extraction_attempt (id, pipeline_run_id, extraction_span_key, "
        "attempt_number, status, raw_output, error, created_at) VALUES (?,?,?,?,?,?,?,?)",
        ("ea1", "pr1", "span1", 3, "failed", "<raw llm body>", "json_parse_error",
         "2026-04-10T10:00:00Z"),
    )

    # 成本(0027):一个 finished run 的两次 success attempt,各带 token/latency,
    # 用于断言 /vitals 历史成本(租户级总和 + 按 run 汇总)。ea1(failed)成本默认 0。
    conn.execute("INSERT INTO pipeline_run (id, tenant_id, started_at, status) "
                 "VALUES (?,?,?,?)", ("pr_cost", "default", "2026-04-10T11:00:00Z", "finished"))
    for sid, span, attempt, ts, pt, ct, tt, lat in [
        ("eac1", "spanc1", 1, "2026-04-10T11:00:00Z", 100, 20, 120, 300),
        ("eac2", "spanc2", 1, "2026-04-10T11:00:01Z", 50, 10, 60, 150),
    ]:
        conn.execute(
            "INSERT INTO extraction_attempt (id, pipeline_run_id, extraction_span_key, "
            "attempt_number, status, created_at, prompt_tokens, completion_tokens, "
            "total_tokens, latency_ms) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (sid, "pr_cost", span, attempt, "success", ts, pt, ct, tt, lat),
        )
    # 跨租户隔离:other 租户的成本绝不进入 default 的聚合。
    conn.execute("INSERT INTO pipeline_run (id, tenant_id, started_at, status) "
                 "VALUES (?,?,?,?)", ("pr_other", "other", "2026-04-10T11:00:00Z", "finished"))
    conn.execute(
        "INSERT INTO extraction_attempt (id, pipeline_run_id, extraction_span_key, "
        "attempt_number, status, created_at, prompt_tokens, completion_tokens, "
        "total_tokens, latency_ms) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("eao1", "pr_other", "spano1", 1, "success", "2026-04-10T11:00:00Z", 999, 999, 999, 999),
    )

    conn.execute(
        "INSERT INTO reconsolidation_windows (stmt_id, tenant_id, opened_at, "
        "close_deadline, status) VALUES (?,?,?,?,?)",
        ("vol1", "default", "2026-04-10T00:00:00Z", "2026-04-10T01:00:00Z", "open"),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "vitals.db")
    _seed(db)
    cfg = DashboardConfig(db_path=db, token="")   # tenant defaults to "default"
    return TestClient(create_app(cfg))


def test_vitals_shape_and_head(client):
    r = client.get("/api/vitals")
    assert r.status_code == 200
    body = r.json()
    assert body["outbox_head"] == 5
    assert set(body) >= {"outbox_head", "max_lag", "lag", "volatile_stuck",
                         "volatile_stuck_total", "extraction_failures",
                         "extraction_failures_total", "extraction_cost",
                         "extraction_cost_runs", "overdue_windows",
                         "overdue_windows_total"}


def test_vitals_per_pump_lag(client):
    lag = {l["pump"]: l for l in client.get("/api/vitals").json()["lag"]}
    # reconsolidation checkpoint at 3, head 5 -> lag 2
    assert lag["reconsolidation"]["lag"] == 2
    # an untouched pump (cursor 0) lags the full head
    assert lag["belief_tracker"]["lag"] == 5
    assert client.get("/api/vitals").json()["max_lag"] == 5


def test_vitals_volatile_stuck_tenant_and_state_filtered(client):
    body = client.get("/api/vitals").json()
    ids = {s["id"] for s in body["volatile_stuck"]}
    assert ids == {"vol1"}                       # vol2 other-tenant, con1 consolidated
    assert body["volatile_stuck_total"] == 1


def test_vitals_extraction_failures_surface_error_and_raw(client):
    fails = client.get("/api/vitals").json()["extraction_failures"]
    assert len(fails) == 1
    assert fails[0]["error"] == "json_parse_error"
    assert fails[0]["raw_output"] == "<raw llm body>"


def test_vitals_overdue_windows(client):
    body = client.get("/api/vitals").json()
    assert {w["stmt_id"] for w in body["overdue_windows"]} == {"vol1"}
    assert body["overdue_windows_total"] == 1


def test_vitals_extraction_cost_aggregate_tenant_scoped(client):
    cost = client.get("/api/vitals").json()["extraction_cost"]
    # default 租户:eac1(120)+eac2(60)=180;ea1(failed)默认 0;other 租户的 999 不泄漏。
    assert cost["total_tokens"] == 180
    assert cost["prompt_tokens"] == 150       # 100+50 (+0)
    assert cost["completion_tokens"] == 30    # 20+10
    assert cost["latency_ms"] == 450          # 300+150 (+0)
    assert cost["attempts"] == 3              # ea1 + eac1 + eac2 (default-tenant rows)


def test_vitals_extraction_cost_runs_grouped_and_isolated(client):
    runs = {r["run_id"]: r for r in client.get("/api/vitals").json()["extraction_cost_runs"]}
    assert "pr_other" not in runs             # cross-tenant cost excluded
    assert runs["pr_cost"]["total_tokens"] == 180
    assert runs["pr_cost"]["attempts"] == 2
    assert runs["pr1"]["total_tokens"] == 0   # the failed run carries zero cost
