"""Read-only SQLite inspection queries for the dashboard.

Opens a fresh read-only connection per call (`mode=ro` + PRAGMA query_only).
List endpoints return rows as dicts keyed by cursor column names, so they are
robust to schema column additions. The engine remains the single writer.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def open_ro(db_path: str):
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def _rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    cur = conn.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def _count(conn, table: str, tenant: str | None) -> int:
    if tenant is None:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE tenant_id = ?", (tenant,)
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def overview(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        commit_states = _rows(
            conn,
            "SELECT state, COUNT(*) AS n FROM commitments WHERE tenant_id=? GROUP BY state",
            (tenant,),
        )
        queue = _rows(
            conn,
            "SELECT dispatch_status, COUNT(*) AS n FROM bus_events WHERE tenant_id=? "
            "GROUP BY dispatch_status",
            (tenant,),
        )
        return {
            "counts": {
                "statements": _count(conn, "statements", tenant),
                "statement_edges": _count(conn, "statement_edges", tenant),
                "cognizers": _count(conn, "cognizers", tenant),
                "commitments": _count(conn, "commitments", tenant),
                "bus_events": _count(conn, "bus_events", tenant),
            },
            "commitments_by_state": {r["state"]: r["n"] for r in commit_states},
            "queue_by_status": {r["dispatch_status"]: r["n"] for r in queue},
        }


def statements(db_path: str, tenant: str, *, holder: str = "", perspective: str = "",
               predicate: str = "", limit: int = 100, offset: int = 0) -> dict:
    where = ["tenant_id = ?"]
    params: list = [tenant]
    for col, val in (("holder_id", holder), ("holder_perspective", perspective),
                     ("predicate", predicate)):
        if val:
            where.append(f"{col} = ?")
            params.append(val)
    clause = " AND ".join(where)
    with open_ro(db_path) as conn:
        rows = _rows(
            conn,
            f"SELECT id, holder_id, holder_perspective, subject_id, predicate, "
            f"object_kind, object_value, modality, polarity, confidence, salience, "
            f"observed_at, review_status, consolidation_state, nesting_depth "
            f"FROM statements WHERE {clause} ORDER BY observed_at DESC "
            f"LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        edges = _rows(
            conn,
            "SELECT src_id, dst_id, edge_kind, weight FROM statement_edges "
            "WHERE tenant_id=? LIMIT 2000",
            (tenant,),
        )
        return {"rows": rows, "edges": edges}


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


def cognizers(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        nodes = _rows(
            conn,
            "SELECT id, kind, canonical_name, last_seen_at FROM cognizers "
            "WHERE tenant_id=? ORDER BY last_seen_at DESC LIMIT 500",
            (tenant,),
        )
        rels = _rows(
            conn,
            "SELECT a_id, b_id, affinity, power_asymmetry FROM cognizer_relations "
            "WHERE tenant_id=? LIMIT 2000",
            (tenant,),
        )
        presence = _rows(
            conn,
            "SELECT cognizer_id, observed_at, channel FROM cognizer_presence_log "
            "WHERE tenant_id=? ORDER BY observed_at DESC LIMIT 200",
            (tenant,),
        )
        return {"nodes": nodes, "relations": rels, "presence": presence}


def commitments(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        rows = _rows(
            conn,
            "SELECT c.stmt_id, c.state, c.broken_count, c.deadline, c.created_at, "
            "c.updated_at, s.subject_id, s.predicate, s.object_value "
            "FROM commitments c LEFT JOIN statements s ON s.id = c.stmt_id "
            "WHERE c.tenant_id=? ORDER BY c.updated_at DESC LIMIT 500",
            (tenant,),
        )
        triggers = _rows(
            conn,
            "SELECT commitment_stmt_id, kind, status FROM commitment_triggers "
            "WHERE tenant_id=? LIMIT 1000",
            (tenant,),
        )
        return {"rows": rows, "triggers": triggers}


def replay(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        state = _rows(conn, "SELECT * FROM replay_scheduler_state WHERE id=1")
        ledger = _rows(
            conn,
            "SELECT replay_batch_id, mode, sampled_count, started_at, finished_at "
            "FROM replay_ledger ORDER BY started_at DESC LIMIT 100",
        )
        windows = _rows(
            conn,
            "SELECT stmt_id, opened_at, close_deadline, status FROM reconsolidation_windows "
            "WHERE tenant_id=? ORDER BY opened_at DESC LIMIT 200",
            (tenant,),
        )
        return {"scheduler": state[0] if state else {}, "ledger": ledger, "windows": windows}


def conflicts(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        by_kind = _rows(
            conn,
            "SELECT edge_kind, COUNT(*) AS n FROM statement_edges WHERE tenant_id=? "
            "GROUP BY edge_kind",
            (tenant,),
        )
        edges = _rows(
            conn,
            "SELECT e.src_id, e.dst_id, e.edge_kind, e.weight, e.metadata_json, "
            "s.subject_id AS src_subject, s.predicate AS src_predicate, s.object_value AS src_object, "
            "d.subject_id AS dst_subject, d.predicate AS dst_predicate, d.object_value AS dst_object "
            "FROM statement_edges e "
            "LEFT JOIN statements s ON s.id = e.src_id AND s.tenant_id = e.tenant_id "
            "LEFT JOIN statements d ON d.id = e.dst_id AND d.tenant_id = e.tenant_id "
            "WHERE e.tenant_id=? AND e.edge_kind='CONFLICTS_WITH' "
            "ORDER BY e.weight DESC LIMIT 500",
            (tenant,),
        )
        return {"by_kind": {r["edge_kind"]: r["n"] for r in by_kind}, "conflicts": edges}


def queues(db_path: str, tenant: str) -> dict:
    with open_ro(db_path) as conn:
        dispatch = _rows(
            conn,
            "SELECT dispatch_status, COUNT(*) AS n FROM bus_events WHERE tenant_id=? "
            "GROUP BY dispatch_status",
            (tenant,),
        )
        backlog = conn.execute(
            "SELECT COUNT(*) FROM statements s LEFT JOIN statement_vectors v "
            "ON v.stmt_id = s.id WHERE s.tenant_id=? AND v.stmt_id IS NULL",
            (tenant,),
        ).fetchone()[0]
        vec = _rows(
            conn,
            "SELECT status, COUNT(*) AS n FROM statement_vectors WHERE tenant_id=? "
            "GROUP BY status",
            (tenant,),
        )
        return {
            "dispatch": {r["dispatch_status"]: r["n"] for r in dispatch},
            "embedding_backlog": backlog,
            "vectors_by_status": {r["status"]: r["n"] for r in vec},
        }
