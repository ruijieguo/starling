"""Read-only SQLite inspection queries for the dashboard.

Opens a fresh read-only connection per call (`mode=ro` + PRAGMA query_only).
List endpoints return rows as dicts keyed by cursor column names, so they are
robust to schema column additions. The engine remains the single writer.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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
               predicate: str = "", review_status: str = "", limit: int = 100,
               offset: int = 0) -> dict:
    where = ["tenant_id = ?"]
    params: list = [tenant]
    # review_status 过滤(片 6 审批队列复用本查询:筛 review_requested)。
    for col, val in (("holder_id", holder), ("holder_perspective", perspective),
                     ("predicate", predicate), ("review_status", review_status)):
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
            "SELECT replay_batch_id, mode, sampled_count, ops_applied_json, "
            "started_at, finished_at "
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


# ── Vitals: Phase 0 read-only observability (pipeline lag + lifecycle stuck) ──
#
#   subscriber-pump checkpoints (global single-row) ─┐
#   bus_events.outbox_sequence (global monotonic) ───┼─► lag = head − cursor
#                                                     │   (GLOBAL signal, not
#                                                     │    tenant-scoped: the
#                                                     │    pumps process every
#                                                     │    tenant's events)
#   statements (tenant) ─► VOLATILE-stuck ────────────┤
#   extraction_attempt⋈pipeline_run (tenant) ─► fails ─┤  (tenant-scoped)
#   reconsolidation_windows (tenant) ─► overdue ──────┘
#
# Each block degrades to ok=False (empty) if its table is absent (migration not
# run) rather than 500-ing — the dashboard is a diagnostic surface, the worst
# case is a missing panel, never a crash. Embedded-mode caveat for the UI: lag
# reflects "distance since the last tick processed events", not a distributed
# queue depth — pumps advance synchronously inside tick()/remember().
_PUMP_CHECKPOINTS = (
    # (pump label, checkpoint table, cursor column)
    ("belief_tracker", "tom_belief_tracker_checkpoint", "last_processed_outbox_sequence"),
    ("reconsolidation", "reconsolidation_checkpoint", "last_processed_outbox_sequence"),
    ("projection", "projection_subscriber_checkpoint", "last_processed_outbox_sequence"),
    ("common_ground", "common_ground_subscriber_checkpoint", "last_processed_outbox_sequence"),
    ("policy_engine", "policy_engine_checkpoint", "seq"),
)


def _rows_or_empty(conn, sql: str, params: tuple = ()):
    """(rows, ok) — ok=False (empty rows) when the table is absent."""
    try:
        return _rows(conn, sql, params), True
    except sqlite3.OperationalError:
        return [], False


def _count_or_zero(conn, sql: str, params: tuple = ()) -> int:
    try:
        return conn.execute(sql, params).fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def brain_map(db_path: str, tenant: str) -> dict:
    """Phase 3 片 1 — 类脑 IA 落地页:9 脑区活体计数(经 plan-design-review 定稿)。
    每区一个只读计数(tenant-scoped,逐区 _count_or_zero 独立降级,缺表→0);
    dormant=True 标记尚未落地的区(片 3 落地后全 9 区皆 active);落地页静默显、
    导航空组不渲染。对话/配置/透视镜无「容量」语义 → count=None(不显计数徽标)。脑区句式与排序
    与 nav 一致:功能名 + 脑区 gloss,按记忆流(输入→快存→慢存→他者→意图→固化→
    内省→体征→配置)。consolidation_state 在 DB 存小写串。"""
    with open_ro(db_path) as conn:
        def n(sql: str, params: tuple = ()) -> int:
            return _count_or_zero(conn, sql, params)
        regions = [
            {"key": "converse", "label": "对话", "region": None,
             "href": "/converse", "count": None, "dormant": False},
            {"key": "short_term", "label": "短期记忆", "region": "海马",
             "href": "/working-set", "dormant": False,
             "count": n("SELECT COUNT(*) FROM statements WHERE tenant_id=? AND "
                        "consolidation_state IN ('volatile','replaying_consolidating')", (tenant,))},
            {"key": "long_term", "label": "长期记忆", "region": "新皮层",
             "href": "/statements", "dormant": False,
             "count": n("SELECT COUNT(*) FROM statements WHERE tenant_id=? AND "
                        "consolidation_state='consolidated'", (tenant,))},
            {"key": "theory_of_mind", "label": "他者心智", "region": "心智化",
             "href": "/cognizers", "dormant": False,
             "count": n("SELECT COUNT(*) FROM cognizers WHERE tenant_id=?", (tenant,))},
            {"key": "prospective", "label": "意图与承诺", "region": "前额叶",
             "href": "/commitments", "dormant": False,
             "count": n("SELECT COUNT(*) FROM commitments WHERE tenant_id=?", (tenant,))},
            {"key": "consolidation", "label": "睡眠与固化", "region": "回放",
             "href": "/replay", "dormant": False,
             "count": n("SELECT COUNT(*) FROM replay_ledger")},
            {"key": "lens", "label": "透视镜", "region": None,
             "href": "/lens", "count": None, "dormant": False},  # 片 3 已落地(来源取证)
            {"key": "vitals", "label": "生命体征", "region": "脑干",
             "href": "/vitals", "dormant": False,
             "count": n("SELECT COUNT(*) FROM bus_events WHERE tenant_id=? AND "
                        "dispatch_status='pending'", (tenant,))},   # 出箱待派发(0=健康)
            {"key": "config", "label": "配置", "region": None,
             "href": "/settings", "count": None, "dormant": False},
        ]
        return {"regions": regions}


# ── Phase 3 片 3 — 透视镜(Lens):来源取证(只读检视) ─────────────────────
# statement 不直接存 extraction_span_key;它的 source_spans 存 engram_ref/chunk,
# span_key = sha256(engram_ref⏟chunk⏟predicate⏟canonical_object_hash)由 C++
# compute_extraction_span_key 算出。**绝不在 Python 复算该哈希**(那是核心语义、
# 换绑定语言要重写=出界)。链路改走 C++ 已写入的 bus event:statement.written 事件
# payload 同时带 stmt_id 与 extraction_span_key → extraction_attempt。Python 只读。

_PROV_PREVIEW_CHARS = 280   # engram 源文预览上限(privacy:只取 inline、未抹除的前 N 字符)

_PROV_STMT_COLS = (
    "id, holder_id, holder_perspective, subject_kind, subject_id, predicate, "
    "object_kind, object_value, modality, polarity, confidence, salience, "
    "consolidation_state, review_status, provenance, derived_depth, nesting_depth, "
    "observed_at, created_at, updated_at, evidence_json, derived_from_json, supersedes_id"
)


def _safe_json(raw, fallback):
    """(value, ok) — ok=False(→fallback)当列为 malformed/NULL/空。片 3 失败模式:
    遇坏 JSON 列不崩树,节点标注「无法解析」。"""
    if raw is None or raw == "":
        return fallback, True
    try:
        return json.loads(raw), True
    except (ValueError, TypeError):
        return fallback, False


def _extraction_for(conn, tenant: str, stmt_id: str) -> dict | None:
    """回溯某语句到创建它的 extraction_attempt(状态/原始 LLM 输出/error),只读。
    链路:bus_events(event_type=statement.written, primary_id=stmt_id)的 C++ 写入
    payload 带 extraction_span_key → extraction_attempt。派生/推断/系统写入无此事件
    → None(诚实:非抽取来源)。缺表(bus_events/extraction_attempt)→ 降级 None。

    实证发现(extractor.cpp):每 span_key 可有多行——创建语句的 success + 重复 remember
    的 noop;**原始 LLM 输出只在失败/解析失败行留底**(成功路径不存 raw)。故:
      ① 权威行 = 优先 success/partial(语句真正的创建),noop/failed 次之;
      ② raw LLM 输出从同一 pipeline_run 的失败/部分尝试取(failed_attempts)——这才是
         「回溯到原始 LLM 输出」的落点。span_key 哈希由 C++ 算,Python 只读、绝不复算。"""
    ev, _ = _rows_or_empty(
        conn,
        "SELECT payload_json FROM bus_events WHERE tenant_id=? AND primary_id=? "
        "AND event_type='statement.written' ORDER BY outbox_sequence ASC LIMIT 1",
        (tenant, stmt_id),
    )
    if not ev:
        return None
    payload, ok = _safe_json(ev[0]["payload_json"], {})
    span_key = payload.get("extraction_span_key") if ok and isinstance(payload, dict) else None
    if not span_key:
        return None
    empty = {"span_key": span_key, "status": None, "attempt_number": None,
             "raw_output": None, "error": None, "created_at": None,
             "run_id": None, "failed_attempts": []}
    rows, _ = _rows_or_empty(
        conn,
        "SELECT pipeline_run_id, status, attempt_number, raw_output, error, created_at "
        "FROM extraction_attempt WHERE extraction_span_key=? "
        "ORDER BY CASE status WHEN 'success' THEN 0 WHEN 'partial_success' THEN 1 "
        "WHEN 'failed' THEN 2 ELSE 3 END, created_at ASC LIMIT 1",
        (span_key,),
    )
    if not rows:
        return empty   # event 记了 span_key 但 ledger 无对应行(罕见:非抽取写入路径)
    a = rows[0]
    run_id = a["pipeline_run_id"]
    failed: list = []
    if run_id:
        # 同一 run 的失败/部分尝试携带原始 LLM 输出(成功不留底)——取证关键。
        failed, _ = _rows_or_empty(
            conn,
            "SELECT attempt_number, status, raw_output, error, created_at "
            "FROM extraction_attempt WHERE pipeline_run_id=? "
            "AND status IN ('failed','partial_success') "
            "ORDER BY attempt_number ASC LIMIT 10",
            (run_id,),
        )
    return {"span_key": span_key, "status": a["status"],
            "attempt_number": a["attempt_number"], "raw_output": a["raw_output"],
            "error": a["error"], "created_at": a["created_at"],
            "run_id": run_id, "failed_attempts": failed}


def _engrams_for(conn, tenant: str, evidence) -> list[dict]:
    """解析 evidence_json([{engram_ref,content_hash,status}])→ 逐条挂上 engram 元数据
    + 有界源文预览(只读)。privacy:仅 inline 且未抹除取前 _PROV_PREVIEW_CHARS 字符;
    uri-only / 已抹除 → 无预览。engram 缺失 → engram=None(孤儿证据,不崩)。"""
    out: list[dict] = []
    if not isinstance(evidence, list):
        return out
    for e in evidence:
        d = e if isinstance(e, dict) else {}
        ref = d.get("engram_ref")
        node = {"engram_ref": ref, "content_hash": d.get("content_hash"),
                "status": d.get("status"), "engram": None}
        if ref:
            rows, _ = _rows_or_empty(
                conn,
                "SELECT source_kind, privacy_class, created_at, erased_at, "
                "payload_inline FROM engrams WHERE tenant_id=? AND id=?",
                (tenant, ref),
            )
            if rows:
                g = rows[0]
                preview = None
                if g["erased_at"] is None and g["payload_inline"] is not None:
                    blob = g["payload_inline"]
                    try:
                        text = (blob.decode("utf-8", "replace")
                                if isinstance(blob, (bytes, bytearray)) else str(blob))
                        preview = text[:_PROV_PREVIEW_CHARS]
                    except Exception:
                        preview = None
                node["engram"] = {
                    "source_kind": g["source_kind"], "privacy_class": g["privacy_class"],
                    "created_at": g["created_at"], "erased": g["erased_at"] is not None,
                    "payload_preview": preview,
                }
        out.append(node)
    return out


def provenance(db_path: str, tenant: str, statement_id: str, *, max_depth: int = 6) -> dict | None:
    """片 3 透视镜:某语句的来源取证树(只读检视)。open_ro = 物理只读(query_only),
    故保证不写 statement.recalled、不沉淀(片 3 验收的「不 emit / 不写」由构造满足)。
    递归解析 statements 的 JSON 列 derived_from / supersedes(**非 SQL join**),逐节点
    回溯 extraction_attempt + 证据 engram。返回 None 当根语句缺失/跨租户(路由→404)。
    有界:max_depth 截断 + seen 去重(共享父 / supersedes 环 → 标 repeat,不展开,不爆栈)。"""
    with open_ro(db_path) as conn:
        seen: set[str] = set()

        def build(sid: str, depth: int) -> dict:
            rows, _ = _rows_or_empty(
                conn,
                f"SELECT {_PROV_STMT_COLS} FROM statements WHERE tenant_id=? AND id=?",
                (tenant, sid),
            )
            if not rows:
                return {"id": sid, "found": False}   # 孤儿父 / 跨租户引用,不崩
            r = rows[0]
            summary = {"subject_id": r["subject_id"], "predicate": r["predicate"],
                       "object_value": r["object_value"]}
            if sid in seen:
                # 已在上文展开(共享父或环):给摘要,不再递归。
                return {"id": sid, "found": True, "repeat": True, "summary": summary}
            seen.add(sid)
            ev, ev_ok = _safe_json(r["evidence_json"], [])
            df, df_ok = _safe_json(r["derived_from_json"], [])
            stmt = {k: r[k] for k in r.keys()
                    if k not in ("evidence_json", "derived_from_json")}
            node = {
                "id": sid, "found": True,
                "statement": stmt,
                "summary": summary,
                "origin": {"provenance": r["provenance"],
                           "extraction": _extraction_for(conn, tenant, sid)},
                "evidence": _engrams_for(conn, tenant, ev),
                "evidence_parse_error": not ev_ok,
                "derived_from_parse_error": not df_ok,
                "derived_from": [],
                "supersedes": None,
                "truncated": False,
            }
            has_deeper = bool((isinstance(df, list) and df) or r["supersedes_id"])
            if depth >= max_depth:
                node["truncated"] = has_deeper   # 到顶不再展开,诚实标注还有更深来源
                return node
            if isinstance(df, list):
                node["derived_from"] = [build(str(p), depth + 1) for p in df if p]
            if r["supersedes_id"]:
                node["supersedes"] = build(str(r["supersedes_id"]), depth + 1)
            return node

        root = build(str(statement_id), 0)
        return root if root.get("found") else None


def search_statements(db_path: str, tenant: str, q: str, *, limit: int = 20) -> dict:
    """透视镜取镜:按文本找语句(只读 LIKE over subject/predicate/object_value,
    tenant-scoped,有界 LIMIT)。副作用自由(open_ro)——故意不用语义召回,绕开
    recalled 旁路争议(片 3 验收:不 emit statement.recalled)。空 query → 空结果。"""
    text = (q or "").strip()
    if not text:
        return {"rows": [], "query": ""}
    like = f"%{text}%"
    with open_ro(db_path) as conn:
        rows = _rows(
            conn,
            "SELECT id, holder_id, subject_id, predicate, object_value, "
            "consolidation_state, review_status, observed_at FROM statements "
            "WHERE tenant_id=? AND (subject_id LIKE ? OR predicate LIKE ? "
            "OR object_value LIKE ?) ORDER BY observed_at DESC LIMIT ?",
            (tenant, like, like, like, limit),
        )
        return {"rows": rows, "query": text}


def lifecycle(db_path: str, tenant: str) -> dict:
    """Phase 3 片 4 — 生命周期:记忆从 VOLATILE 经固化到 CONSOLIDATED,再 ARCHIVED/FORGOTTEN。
    两层只读派生(决策 F4=A,零 migration,不新增状态转移审计表):
      ① 当前占用 occupancy = statements 按 consolidation_state 分组(**精确快照**)。
      ② 流转 events = bus_events 按 typed 'statement.*' 事件计数(**事件派生·累计**)。
    遗忘无 typed 事件(forget 直接 UPDATE→forgotten),故 FORGOTTEN 量由占用快照给出
    (forgotten 是终态,快照即累计)。tenant-scoped。run_sleep/idle 未驱动 → consolidated
    事件偏少,前端据 events 诚实标注(非静默空白)。缺表逐项降级。"""
    with open_ro(db_path) as conn:
        occ_rows, _ = _rows_or_empty(
            conn,
            "SELECT consolidation_state AS state, COUNT(*) AS n FROM statements "
            "WHERE tenant_id=? GROUP BY consolidation_state",
            (tenant,),
        )
        ev_rows, _ = _rows_or_empty(
            conn,
            "SELECT event_type, COUNT(*) AS n FROM bus_events "
            "WHERE tenant_id=? AND event_type LIKE 'statement.%' GROUP BY event_type",
            (tenant,),
        )
        return {
            "occupancy": {r["state"]: r["n"] for r in occ_rows},
            "events": {r["event_type"]: r["n"] for r in ev_rows},
        }


def _project_iso(last_accessed_iso: str, seconds: float):
    """投影绝对时点 = last_accessed + Δt(纯日期算术;曲线数学全在 C++)。
    seconds<0(S0<=0 / target 出界)或 None / 溢出 → None。"""
    if seconds is None or seconds < 0 or not last_accessed_iso:
        return None
    try:
        base = datetime.fromisoformat(last_accessed_iso.replace("Z", "+00:00"))
        return (base + timedelta(seconds=seconds)).astimezone(
            timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError, OSError):
        return None


def forecast(db_path: str, tenant: str, *, now: str, limit: int = 200,
             threshold: float = 0.05) -> dict:
    """Phase 3 片 5 — 衰减预报:把 C++ forgetting_curve 投影到候选语句,排「最快被遗忘」。
    **公式与其逆全在 C++**(compute_s_t / seconds_until_retrievability);这里只做只读
    候选装载 + 调绑定 + 排序(换绑定语言不需重写=守边界,绝不在 Python 复算公式)。
    输入**镜像 op_decay**:salience/access_count/modality/last_accessed + active_grounded
    =受 ACTIVE commitment 保护;op_decay 不读 affect → valence 传 0,保持预报与实际衰减
    一致。候选**有界 LIMIT**(按 last_accessed ASC,最久未访问优先=最可能低 S(t)),
    不全表算。只取 VOLATILE/CONSOLIDATED(archived/forgotten 已终态)。threshold=0.05
    与 op_decay 归档阈值一致。tenant-scoped。"""
    from starling import _core
    with open_ro(db_path) as conn:
        prot_rows, _ = _rows_or_empty(
            conn,
            "SELECT DISTINCT cp.protected_stmt_id AS sid FROM commitment_protection cp "
            "JOIN commitments c ON c.tenant_id=cp.tenant_id AND c.stmt_id=cp.commitment_stmt_id "
            "WHERE cp.tenant_id=? AND c.state='ACTIVE'",
            (tenant,),
        )
        protected = {r["sid"] for r in prot_rows}
        rows, _ = _rows_or_empty(
            conn,
            "SELECT id, subject_id, predicate, object_value, modality, salience, "
            "access_count, last_accessed, consolidation_state FROM statements "
            "WHERE tenant_id=? AND consolidation_state IN ('volatile','consolidated') "
            "ORDER BY last_accessed ASC LIMIT ?",
            (tenant, limit),
        )
    out = []
    for r in rows:
        grounded = r["id"] in protected
        modality = r["modality"] or ""
        la = r["last_accessed"] or ""
        sal = r["salience"] or 0.0
        acc = r["access_count"] or 0
        s_t = _core.forgetting_s_t(
            salience=sal, access_count=acc, active_grounded=grounded,
            modality=modality, affect_valence=0.0, last_accessed_iso=la, now_iso=now)
        secs = _core.forgetting_seconds_until(
            salience=sal, access_count=acc, active_grounded=grounded,
            modality=modality, affect_valence=0.0, target=threshold)
        out.append({**r, "active_grounded": grounded, "s_t": s_t,
                    "forget_at": _project_iso(la, secs)})
    out.sort(key=lambda x: x["s_t"])   # 升序:最可能被遗忘在前
    return {"rows": out, "threshold": threshold, "now": now, "candidate_limit": limit}


def vitals(db_path: str, tenant: str, *, now: str, list_limit: int = 50) -> dict:
    """Phase 0 observability: per-subscriber outbox lag (global) + VOLATILE-stuck
    / extraction failures / overdue reconsolidation windows (tenant-scoped)."""
    with open_ro(db_path) as conn:
        head_row = conn.execute(
            "SELECT MAX(outbox_sequence) AS head FROM bus_events").fetchone()
        head = head_row["head"] if head_row and head_row["head"] is not None else 0

        lag: list[dict] = []
        for label, table, col in _PUMP_CHECKPOINTS:
            try:
                r = conn.execute(f"SELECT {col} AS cur FROM {table} LIMIT 1").fetchone()
            except sqlite3.OperationalError:
                lag.append({"pump": label, "ok": False, "cursor": None,
                            "head": head, "lag": None})
                continue
            cur = r["cur"] if r and r["cur"] is not None else 0
            lag.append({"pump": label, "ok": True, "cursor": cur,
                        "head": head, "lag": max(0, head - cur)})
        # in-process dispatcher checkpoint(s), keyed per consumer_id
        disp, _ = _rows_or_empty(
            conn, "SELECT consumer_id, last_delivered_sequence FROM consumer_checkpoint")
        for r in disp:
            cur = r["last_delivered_sequence"] or 0
            lag.append({"pump": f"dispatcher:{r['consumer_id']}", "ok": True,
                        "cursor": cur, "head": head, "lag": max(0, head - cur)})

        volatile_stuck, _ = _rows_or_empty(
            conn,
            "SELECT id, subject_id, predicate, object_value, salience, replay_count, "
            "consolidation_state, created_at, observed_at, last_replayed "
            "FROM statements WHERE tenant_id=? "
            "AND consolidation_state IN ('volatile','replaying_consolidating') "
            "ORDER BY created_at ASC LIMIT ?",
            (tenant, list_limit),
        )
        volatile_stuck_total = _count_or_zero(
            conn,
            "SELECT COUNT(*) FROM statements WHERE tenant_id=? "
            "AND consolidation_state IN ('volatile','replaying_consolidating')",
            (tenant,),
        )

        extraction_failures, _ = _rows_or_empty(
            conn,
            "SELECT a.id, a.pipeline_run_id, a.extraction_span_key, a.attempt_number, "
            "a.status, a.error, a.raw_output, a.created_at "
            "FROM extraction_attempt a JOIN pipeline_run p ON p.id = a.pipeline_run_id "
            "WHERE p.tenant_id=? AND a.status='failed' "
            "ORDER BY a.created_at DESC LIMIT ?",
            (tenant, list_limit),
        )
        extraction_failures_total = _count_or_zero(
            conn,
            "SELECT COUNT(*) FROM extraction_attempt a JOIN pipeline_run p "
            "ON p.id = a.pipeline_run_id WHERE p.tenant_id=? AND a.status='failed'",
            (tenant,),
        )

        overdue_windows, _ = _rows_or_empty(
            conn,
            "SELECT stmt_id, opened_at, close_deadline, status FROM reconsolidation_windows "
            "WHERE tenant_id=? AND status='open' AND close_deadline < ? "
            "ORDER BY close_deadline ASC LIMIT ?",
            (tenant, now, list_limit),
        )
        overdue_windows_total = _count_or_zero(
            conn,
            "SELECT COUNT(*) FROM reconsolidation_windows WHERE tenant_id=? "
            "AND status='open' AND close_deadline < ?",
            (tenant, now),
        )

        max_lag = max((l["lag"] for l in lag if l["lag"] is not None), default=0)
        return {
            "outbox_head": head,
            "max_lag": max_lag,
            "lag": lag,
            "volatile_stuck": volatile_stuck,
            "volatile_stuck_total": volatile_stuck_total,
            "extraction_failures": extraction_failures,
            "extraction_failures_total": extraction_failures_total,
            "overdue_windows": overdue_windows,
            "overdue_windows_total": overdue_windows_total,
        }
