"""provenance query — Phase 3 片 3 透视镜:某语句来源取证树(只读检视)。

两条路子:① 真 remember 路径造出真实链路 statement → bus_events(statement.written
带 extraction_span_key)→ extraction_attempt,断言 drill 回溯到原始 LLM 输出
(span_key 哈希由 C++ 算、Python 绝不复算——只读 bus 事件 payload)。
② 裸 SQL 造 派生 / 前身 / 坏 JSON / 环 / 深度 等边角,断言递归与降级正确。"""
import sqlite3
from pathlib import Path

import pytest

from starling import _core
from starling.dashboard import DashboardConfig, queries
from starling.dashboard.engine import DashboardEngine

_STUB_JSON = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)

# 裸插语句用:NOT-NULL 无默认列全给值;evidence/derived/supersedes/provenance/state 可覆盖。
_COLS = (
    "id, tenant_id, holder_id, holder_perspective, subject_kind, subject_id, "
    "predicate, object_kind, object_value, canonical_object_hash, modality, "
    "polarity, confidence, observed_at, salience, affect_json, activation, "
    "last_accessed, provenance, created_at, updated_at, "
    "evidence_json, derived_from_json, supersedes_id, consolidation_state"
)


def _ins(conn, sid, *, tenant="default", evidence="[]", derived="[]",
         supersedes=None, provenance="user_input", subj="X", obj="v",
         predicate="rel", state="volatile"):
    conn.execute(
        f"INSERT INTO statements ({_COLS}) VALUES ({','.join('?' * 25)})",
        (sid, tenant, "self", "first_person", "cognizer", subj, predicate,
         "str", obj, f"h{sid}", "BELIEVES", "POS", 0.9, "2026-04-10T10:00:00Z",
         0.5, "{}", 0.0, "2026-04-10T10:00:00Z", provenance,
         "2026-04-10T10:00:00Z", "2026-04-10T10:00:00Z",
         evidence, derived, supersedes, state),
    )


def _fresh_db(db_path: str):
    """Build the schema via the runtime, release the writer, return a raw conn."""
    from starling import runtime as rt
    from starling.testing import relax_preflight_for_m0_3
    relax_preflight_for_m0_3()
    r = rt._build_local_store_sqlite_runtime(Path(db_path))
    r.start()
    del r
    return sqlite3.connect(db_path)


def _engine(db, *, body=_STUB_JSON, ok=True, error=""):
    cfg = DashboardConfig(db_path=db, token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(body, ok, error)
    eng.llm = fake
    return eng


def _eng_row(conn, eid, *, tenant="default", privacy="internal", erased=None,
             payload=b"the source sentence", content_hash="ch1"):
    # source_item_id=eid:满足 idx_engrams_source_identity 唯一(否则各默认值撞键)。
    conn.execute(
        "INSERT INTO engrams (id, tenant_id, content_hash, source_kind, ingest_policy, "
        "ingest_mode, privacy_class, retention_mode, payload_inline, created_at, erased_at, "
        "source_item_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (eid, tenant, content_hash, "user_input", "store", "inline", privacy,
         "default", payload, "2026-04-10T10:00:00Z", erased, eid),
    )


def _ev_ref(eid, content_hash="ch1"):
    return f'[{{"engram_ref":"{eid}","content_hash":"{content_hash}","status":"active"}}]'


# ── ① 真实链路 ────────────────────────────────────────────────────────────
def test_provenance_traces_real_extraction(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = str(tmp_path / "p.db")
    eng = _engine(db)
    sid = eng.remember("Bob is responsible for auth")["statement_ids"][0]

    tree = queries.provenance(db, "default", sid)
    assert tree is not None
    assert tree["found"] and tree["id"] == sid
    ex = tree["origin"]["extraction"]
    assert ex is not None and ex["span_key"]
    # 权威行 = 创建该语句的 success(优先于重复 remember 写的 noop 行)。
    assert ex["status"] == "success"
    # 实证:成功路径不留 raw_output(仅失败/解析失败行留底)——诚实为 None,非空字符串。
    assert ex["raw_output"] is None
    assert ex["failed_attempts"] == []          # fake 一次成功,无失败尝试
    assert tree["origin"]["provenance"] == "user_input"
    # 证据 engram 已挂(inline → 有源文预览)。
    assert tree["evidence"] and tree["evidence"][0]["engram"] is not None


def test_provenance_drill_is_read_only(tmp_path, monkeypatch):
    # 片 3 验收:取证不写(不 emit statement.recalled / 不沉淀)。open_ro 物理只读,
    # 这里以 bus_events 行数前后不变实证。
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = str(tmp_path / "ro.db")
    eng = _engine(db)
    sid = eng.remember("Bob is responsible for auth")["statement_ids"][0]
    with queries.open_ro(db) as c:
        before = c.execute("SELECT COUNT(*) FROM bus_events").fetchone()[0]
    queries.provenance(db, "default", sid)
    queries.provenance(db, "default", sid)
    with queries.open_ro(db) as c:
        after = c.execute("SELECT COUNT(*) FROM bus_events").fetchone()[0]
    assert before == after


def test_provenance_none_when_absent_or_cross_tenant(tmp_path):
    db = str(tmp_path / "x.db")
    conn = _fresh_db(db)
    _ins(conn, "owned", tenant="default")
    _ins(conn, "alien", tenant="other")
    conn.commit()
    conn.close()
    assert queries.provenance(db, "default", "nope") is None      # 缺失
    assert queries.provenance(db, "default", "alien") is None      # 跨租户(tenant-scoped)
    assert queries.provenance(db, "default", "owned") is not None


# ── ② 递归与降级边角 ──────────────────────────────────────────────────────
def test_provenance_derived_from_recurses(tmp_path):
    db = str(tmp_path / "d.db")
    conn = _fresh_db(db)
    _ins(conn, "P", subj="parent")
    _ins(conn, "C", subj="child", derived='["P"]', provenance="tom_inferred")
    conn.commit()
    conn.close()
    tree = queries.provenance(db, "default", "C")
    assert tree["origin"]["provenance"] == "tom_inferred"
    assert len(tree["derived_from"]) == 1
    assert tree["derived_from"][0]["id"] == "P" and tree["derived_from"][0]["found"]
    assert tree["derived_from"][0]["summary"]["subject_id"] == "parent"


def test_provenance_orphan_parent_does_not_crash(tmp_path):
    db = str(tmp_path / "o.db")
    conn = _fresh_db(db)
    _ins(conn, "C", derived='["GONE"]')   # 父不存在
    conn.commit()
    conn.close()
    tree = queries.provenance(db, "default", "C")
    assert tree["derived_from"][0] == {"id": "GONE", "found": False}


def test_provenance_supersedes_chain(tmp_path):
    db = str(tmp_path / "s.db")
    conn = _fresh_db(db)
    _ins(conn, "B", subj="old")
    _ins(conn, "A", subj="new", supersedes="B")
    conn.commit()
    conn.close()
    tree = queries.provenance(db, "default", "A")
    assert tree["supersedes"] is not None
    assert tree["supersedes"]["id"] == "B" and tree["supersedes"]["found"]


def test_provenance_malformed_json_degrades(tmp_path):
    # 坏 evidence_json / derived_from_json → 节点标注解析失败,不崩树,其余字段在。
    db = str(tmp_path / "m.db")
    conn = _fresh_db(db)
    _ins(conn, "M", evidence="{not json", derived="also bad")
    conn.commit()
    conn.close()
    tree = queries.provenance(db, "default", "M")
    assert tree["found"] is True
    assert tree["evidence_parse_error"] is True and tree["evidence"] == []
    assert tree["derived_from_parse_error"] is True and tree["derived_from"] == []


def test_provenance_cycle_guard(tmp_path):
    # A 取代 B、B 取代 A(环)→ 不无限递归,二度回到 A 标 repeat。
    db = str(tmp_path / "c.db")
    conn = _fresh_db(db)
    _ins(conn, "A", supersedes="B")
    _ins(conn, "B", supersedes="A")
    conn.commit()
    conn.close()
    tree = queries.provenance(db, "default", "A", max_depth=8)
    assert tree["supersedes"]["id"] == "B"
    assert tree["supersedes"]["supersedes"]["id"] == "A"
    assert tree["supersedes"]["supersedes"]["repeat"] is True


def test_provenance_max_depth_truncates(tmp_path):
    # 链 A→B→C,max_depth=1:B 在深度上限,truncated 标真且不再展开 C。
    db = str(tmp_path / "t.db")
    conn = _fresh_db(db)
    _ins(conn, "A", supersedes="B")
    _ins(conn, "B", supersedes="C")
    _ins(conn, "C")
    conn.commit()
    conn.close()
    tree = queries.provenance(db, "default", "A", max_depth=1)
    assert tree["supersedes"]["id"] == "B"
    assert tree["supersedes"]["truncated"] is True
    assert tree["supersedes"]["supersedes"] is None


def test_provenance_surfaces_failed_attempt_raw_output(tmp_path):
    # 同一 run:attempt1 解析失败(留底原始 LLM 输出)+ attempt2 success → drill 选
    # success 为权威行,并把同 run 失败尝试的原始输出抬出来(「回溯到原始 LLM 输出」落点)。
    db = str(tmp_path / "fa.db")
    conn = _fresh_db(db)
    _ins(conn, "S", subj="Bob", predicate="responsible_for", obj="auth")
    conn.execute("INSERT INTO pipeline_run (id, tenant_id, started_at, status) "
                 "VALUES ('run1','default','2026-04-10T10:00:00Z','done')")
    conn.execute(
        "INSERT INTO extraction_attempt (id, pipeline_run_id, extraction_span_key, "
        "attempt_number, status, raw_output, error, created_at) VALUES "
        "('a1','run1','SK',1,'failed','LLM said garbage','json_parse','2026-04-10T10:00:00Z')")
    conn.execute(
        "INSERT INTO extraction_attempt (id, pipeline_run_id, extraction_span_key, "
        "attempt_number, status, raw_output, error, created_at) VALUES "
        "('a2','run1','SK',2,'success',NULL,NULL,'2026-04-10T10:00:01Z')")
    conn.execute(
        "INSERT INTO bus_events (event_id, tenant_id, event_type, primary_id, "
        "aggregate_id, outbox_sequence, idempotency_key, payload_json, created_at) "
        "VALUES ('e1','default','statement.written','S','S',1,'idem1',?,"
        "'2026-04-10T10:00:01Z')",
        ('{"stmt_id":"S","extraction_span_key":"SK"}',))
    conn.commit()
    conn.close()
    ex = queries.provenance(db, "default", "S")["origin"]["extraction"]
    assert ex["status"] == "success" and ex["run_id"] == "run1"
    assert len(ex["failed_attempts"]) == 1
    assert ex["failed_attempts"][0]["raw_output"] == "LLM said garbage"
    assert ex["failed_attempts"][0]["error"] == "json_parse"


def test_provenance_non_extraction_origin_has_no_attempt(tmp_path):
    # 裸插(无 bus 事件)的派生语句 → extraction=None(诚实:非抽取来源)。
    db = str(tmp_path / "n.db")
    conn = _fresh_db(db)
    _ins(conn, "D", provenance="reconsolidation_derived")
    conn.commit()
    conn.close()
    tree = queries.provenance(db, "default", "D")
    assert tree["origin"]["extraction"] is None
    assert tree["origin"]["provenance"] == "reconsolidation_derived"


def test_provenance_engram_preview_privacy_guard(tmp_path):
    # 证据源文预览:仅 inline + 未抹除 + 非 regulated/sensitive 才显;否则抑制(节点仍在)。
    # 钉死隐私不变式——provenance 直读 payload_inline 绕过检索层抹除过滤,故须自守。
    db = str(tmp_path / "eng.db")
    conn = _fresh_db(db)
    _eng_row(conn, "e_ok", privacy="internal")
    _eng_row(conn, "e_reg", privacy="regulated")
    _eng_row(conn, "e_personal", privacy="personal")
    _eng_row(conn, "e_sensitive", privacy="sensitive")
    _eng_row(conn, "e_erased", privacy="internal", erased="2026-05-01T00:00:00Z")
    _ins(conn, "S_ok", evidence=_ev_ref("e_ok"))
    _ins(conn, "S_reg", evidence=_ev_ref("e_reg"))
    _ins(conn, "S_personal", evidence=_ev_ref("e_personal"))
    _ins(conn, "S_sensitive", evidence=_ev_ref("e_sensitive"))
    _ins(conn, "S_erased", evidence=_ev_ref("e_erased"))
    conn.commit()
    conn.close()
    ok = queries.provenance(db, "default", "S_ok")["evidence"][0]["engram"]
    assert ok is not None and ok["payload_preview"] == "the source sentence"   # internal → 显
    # regulated / personal / sensitive 三个 PII/受控级都抑制源文(节点与 privacy_class 仍在)。
    for sid, pc in (("S_reg", "regulated"), ("S_personal", "personal"), ("S_sensitive", "sensitive")):
        eng = queries.provenance(db, "default", sid)["evidence"][0]["engram"]
        assert eng["payload_preview"] is None and eng["privacy_class"] == pc
    er = queries.provenance(db, "default", "S_erased")["evidence"][0]["engram"]
    assert er["payload_preview"] is None and er["erased"] is True                  # 抹除抑制


# ── 取镜:只读文本查找 ────────────────────────────────────────────────────
def test_search_statements_finds_and_scopes(tmp_path):
    db = str(tmp_path / "se.db")
    conn = _fresh_db(db)
    _ins(conn, "h1", obj="auth-service", subj="Bob")
    _ins(conn, "h2", obj="billing", subj="Carol")
    _ins(conn, "h3", obj="auth-service", subj="Bob", tenant="other")
    conn.commit()
    conn.close()
    hits = queries.search_statements(db, "default", "auth")
    ids = {r["id"] for r in hits["rows"]}
    assert ids == {"h1"}                      # 命中 default 的 auth,跨租户 h3 排除
    assert queries.search_statements(db, "default", "")["rows"] == []   # 空 query → 空
    assert queries.search_statements(db, "default", "Carol")["rows"][0]["id"] == "h2"
