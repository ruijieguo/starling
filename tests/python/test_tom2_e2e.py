"""P3.a2 e2e:二阶信念生产 → 巩固 → META_BELIEF 检索(a1×a2 闭环)+ 绑定面。

触发面注记:单 agent 抽取流所有语句 holder=self("Bob 信 P"是扁平一阶表示),
自动二阶建模的触发面是**多 holder 写入**(dashboard 演示数据/程序化/未来
多智能体 ingestion)。本测试程序化种多 holder 行,走真 belief_tracker 批。
"""
import sqlite3

import starling
from starling import _core

CANNED = (
    '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
    '"subject":"Bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)

NOW = "2026-06-12T10:00:00Z"


def _seed_multi_holder(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            "INSERT INTO cognizers(id,tenant_id,kind,canonical_name,"
            "canonical_name_normalized,external_id,created_at,last_seen_at) "
            "VALUES('alice','default','self','Alice','alice','',?,?)", (NOW, NOW))
        conn.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,"
            "subject_kind,subject_id,predicate,object_kind,object_value,"
            "canonical_object_hash,canonical_object_hash_version,modality,"
            "polarity,confidence,observed_at,salience,affect_json,activation,"
            "last_accessed,provenance,evidence_json,consolidation_state,"
            "review_status,nesting_depth,created_at,updated_at) VALUES("
            "'BOB1','default','bob','FIRST_PERSON','entity','launch','status',"
            "'str','on track','h-bob1','v1','BELIEVES','POS',0.8,?,0.6,'{}',"
            "0.0,?,'user_input','[{\"engram_id\":\"eng-b1\"}]','consolidated',"
            "'approved',0,?,?)", (NOW, NOW, NOW, NOW))
        conn.execute(
            "INSERT INTO bus_events(event_id,tenant_id,event_type,primary_id,"
            "aggregate_id,outbox_sequence,idempotency_key,payload_json,created_at)"
            " VALUES('ev-bob1','default','statement.written','BOB1','BOB1',"
            "900001,'ik-bob1','{\"stmt_id\":\"BOB1\",\"engram_ref_id\":\"eng-b1\"}',?)",
            (NOW,))
        conn.commit()
    finally:
        conn.close()


_STMT_COLS = (
    "id,tenant_id,holder_id,holder_perspective,subject_kind,subject_id,"
    "predicate,object_kind,object_value,canonical_object_hash,"
    "canonical_object_hash_version,modality,polarity,confidence,observed_at,"
    "salience,affect_json,activation,last_accessed,provenance,evidence_json,"
    "consolidation_state,review_status,nesting_depth,created_at,updated_at"
)


def _ins_stmt(conn, *, id, holder, subject_kind, subject_id, object_kind,
              object_value, depth, observed):
    """Insert one consolidated/approved statement row."""
    conn.execute(
        f"INSERT INTO statements({_STMT_COLS}) VALUES("
        "?,?,?,'FIRST_PERSON',?,?,'believes',?,?,?,'v1','BELIEVES','POS',0.8,?,"
        "0.6,'{}',0.0,?,'user_input',?,'consolidated','approved',?,?,?)",
        (id, "default", holder, subject_kind, subject_id, object_kind,
         object_value, "h-" + id, observed, observed,
         '[{"engram_id":"eng-' + id + '"}]', depth, observed, observed))


def _seed_partner_depth2_chain(db_path: str) -> None:
    """Seed a self cognizer (alice) + a structurally-real depth-2 nested belief
    held by partner `bob`: flat leaf DL0(d0) <- D1(d1,->DL0) <- D2(d2,->D1), plus
    a statement.written bus event whose stmt_id=D2. belief_tracker mirrors the
    partner's depth-2 source to a self depth-3 meta-belief (auto path, Phase 4)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            "INSERT INTO cognizers(id,tenant_id,kind,canonical_name,"
            "canonical_name_normalized,external_id,created_at,last_seen_at) "
            "VALUES('alice','default','self','Alice','alice','',?,?)", (NOW, NOW))
        # Flat leaf (depth-0).
        _ins_stmt(conn, id="DL0", holder="bob", subject_kind="entity",
                  subject_id="launch", object_kind="str", object_value="on track",
                  depth=0, observed="2026-06-12T09:00:30Z")
        # Depth-1 nested over the leaf.
        _ins_stmt(conn, id="D1", holder="bob", subject_kind="cognizer",
                  subject_id="peer", object_kind="statement", object_value="DL0",
                  depth=1, observed="2026-06-12T09:01:00Z")
        # Depth-2 nested over the depth-1 row — the source the tracker mirrors.
        _ins_stmt(conn, id="D2", holder="bob", subject_kind="cognizer",
                  subject_id="peer", object_kind="statement", object_value="D1",
                  depth=2, observed="2026-06-12T09:02:00Z")
        conn.execute(
            "INSERT INTO bus_events(event_id,tenant_id,event_type,primary_id,"
            "aggregate_id,outbox_sequence,idempotency_key,payload_json,created_at)"
            " VALUES('ev-d2','default','statement.written','D2','D2',"
            "900001,'ik-d2','{\"stmt_id\":\"D2\",\"engram_ref_id\":\"eng-D2\"}',?)",
            (NOW,))
        conn.commit()
    finally:
        conn.close()


def _seed_partner_depth3_chain(db_path: str) -> None:
    """Seed self (alice) + a structurally-real depth-3 nested belief held by
    partner `bob`: TL0(d0) <- T1(d1) <- T2(d2) <- T3(d3), plus a statement.written
    bus event whose stmt_id=T3. Phase 4 / Gap 1 headline: belief_tracker must mirror
    the partner's depth-3 source to a self depth-4 meta-belief through the FULL
    pipeline (bus -> tracker -> StatementWriter -> NestingDepthWriter). Pre-decouple
    this would have hit the causation kChainMax=3 guard and written nothing."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(
            "INSERT INTO cognizers(id,tenant_id,kind,canonical_name,"
            "canonical_name_normalized,external_id,created_at,last_seen_at) "
            "VALUES('alice','default','self','Alice','alice','',?,?)", (NOW, NOW))
        _ins_stmt(conn, id="TL0", holder="bob", subject_kind="entity",
                  subject_id="launch", object_kind="str", object_value="on track",
                  depth=0, observed="2026-06-12T09:00:30Z")
        _ins_stmt(conn, id="T1", holder="bob", subject_kind="cognizer",
                  subject_id="peer", object_kind="statement", object_value="TL0",
                  depth=1, observed="2026-06-12T09:01:00Z")
        _ins_stmt(conn, id="T2", holder="bob", subject_kind="cognizer",
                  subject_id="peer", object_kind="statement", object_value="T1",
                  depth=2, observed="2026-06-12T09:02:00Z")
        _ins_stmt(conn, id="T3", holder="bob", subject_kind="cognizer",
                  subject_id="peer", object_kind="statement", object_value="T2",
                  depth=3, observed="2026-06-12T09:03:00Z")
        conn.execute(
            "INSERT INTO bus_events(event_id,tenant_id,event_type,primary_id,"
            "aggregate_id,outbox_sequence,idempotency_key,payload_json,created_at)"
            " VALUES('ev-t3','default','statement.written','T3','T3',"
            "900001,'ik-t3','{\"stmt_id\":\"T3\",\"engram_ref_id\":\"eng-T3\"}',?)",
            (NOW,))
        conn.commit()
    finally:
        conn.close()


def test_auto_mirror_depth_three_source_produces_depth_four(tmp_path):
    """Gap 1 headline e2e: partner bob's REAL depth-3 nested belief -> belief_tracker
    mirrors to a self depth-4 meta-belief through the whole pipeline (proves the
    causation-chain decouple end-to-end, not just in the unit function);
    what_does_X_think_Y_believes(alice, bob) recalls the full 4-level chain down to
    the depth-0 leaf TL0."""
    db = str(tmp_path / "tom2_d4.db")
    llm = starling.make_stub_llm(default_response=CANNED)
    mem = starling.Memory.open(db, agent="alice", llm=llm)
    try:
        _seed_partner_depth3_chain(db)

        stats = _core.belief_tracker_tick(mem._rt.adapter)
        assert stats.second_order_written == 1

        ro = sqlite3.connect(db)
        holder, subject, depth, obj = ro.execute(
            "SELECT holder_id, subject_id, nesting_depth, object_value "
            "FROM statements WHERE provenance='tom_inferred' "
            "AND holder_id='alice'").fetchone()
        ro.close()
        # The headline: depth-3 source -> self depth-4 meta-belief.
        assert (holder, subject, depth, obj) == ("alice", "bob", 4, "T3")

        mem.tick()  # consolidate the volatile-born meta-belief for recall

        nested = _core.what_does_X_think_Y_believes(
            mem._rt.adapter, "alice", "bob", "default", "2026-06-13T00:00:00Z")
        outer = next(n for n in nested if n.outer.object_value == "T3")
        assert outer.inner.id == "T3"
        # .chain unwraps T3 -> T2 -> T1 -> TL0: four levels to the depth-0 leaf.
        ids = [(c.level, c.id, c.object_value, c.object_kind) for c in outer.chain]
        assert ids == [
            (1, "T3", "T2", "statement"),
            (2, "T2", "T1", "statement"),
            (3, "T1", "TL0", "statement"),
            (4, "TL0", "on track", "str"),
        ], ids

        # Idempotency (Gap 6) through the pipeline: a second tracker tick over the
        # same already-consumed event writes no new nested row.
        stats2 = _core.belief_tracker_tick(mem._rt.adapter)
        assert stats2.second_order_written == 0
        ro = sqlite3.connect(db)
        n_rows = ro.execute(
            "SELECT COUNT(*) FROM statements WHERE provenance='tom_inferred' "
            "AND holder_id='alice' AND subject_id='bob'").fetchone()[0]
        ro.close()
        assert n_rows == 1
    finally:
        mem.close()


def test_auto_mirror_recall_returns_three_deep_chain(tmp_path):
    """Phase 5 e2e: partner bob's depth-2 nested belief -> belief_tracker mirrors
    to a self depth-3 meta-belief; what_does_X_think_Y_believes(alice, bob)
    recalls the full chain (3 levels) down to the depth-0 leaf DL0."""
    db = str(tmp_path / "tom2_chain.db")
    llm = starling.make_stub_llm(default_response=CANNED)
    mem = starling.Memory.open(db, agent="alice", llm=llm)
    try:
        _seed_partner_depth2_chain(db)

        # belief_tracker batch consumes D2's statement.written -> self depth-3.
        stats = _core.belief_tracker_tick(mem._rt.adapter)
        assert stats.second_order_written == 1

        ro = sqlite3.connect(db)
        holder, subject, depth, obj = ro.execute(
            "SELECT holder_id, subject_id, nesting_depth, object_value "
            "FROM statements WHERE provenance='tom_inferred' "
            "AND holder_id='alice'").fetchone()
        ro.close()
        assert (holder, subject, depth, obj) == ("alice", "bob", 3, "D2")

        # Consolidate the volatile-born meta-belief so the recall stable-state
        # filter admits it (mirrors the depth-1 test's mem.tick() consolidation).
        mem.tick()

        nested = _core.what_does_X_think_Y_believes(
            mem._rt.adapter, "alice", "bob", "default", "2026-06-13T00:00:00Z")
        # The self depth-3 meta-belief anchors (holder=alice, subject=bob).
        outer = next(n for n in nested if n.outer.object_value == "D2")
        # .inner = immediate inner D2 (backward-compat).
        assert outer.inner.id == "D2"
        # .chain unwraps D2 -> D1 -> DL0: three levels ending at the depth-0 leaf.
        ids = [(c.level, c.id, c.object_value, c.object_kind) for c in outer.chain]
        assert ids == [
            (1, "D2", "D1", "statement"),
            (2, "D1", "DL0", "statement"),
            (3, "DL0", "on track", "str"),
        ], ids

        # max_unwrap=1 truncates to the immediate inner only.
        capped = _core.what_does_X_think_Y_believes(
            mem._rt.adapter, "alice", "bob", "default", "2026-06-13T00:00:00Z",
            max_unwrap=1)
        capped_outer = next(n for n in capped if n.outer.object_value == "D2")
        assert [c.id for c in capped_outer.chain] == ["D2"]
    finally:
        mem.close()


def test_second_order_auto_then_meta_belief_query(tmp_path):
    db = str(tmp_path / "tom2.db")
    llm = starling.make_stub_llm(default_response=CANNED)
    mem = starling.Memory.open(db, agent="alice", llm=llm)
    try:
        _seed_multi_holder(db)

        # belief_tracker 批:消费 BOB1 的 statement.written → 自动二阶。
        stats = _core.belief_tracker_tick(mem._rt.adapter)
        assert stats.second_order_written == 1

        ro = sqlite3.connect(db)
        row = ro.execute(
            "SELECT holder_id, subject_id, nesting_depth, provenance, salience "
            "FROM statements WHERE object_kind='statement'").fetchone()
        ro.close()
        assert row is not None
        holder, subject, depth, prov, sal = row
        assert (holder, subject, depth, prov) == ("alice", "bob", 1, "tom_inferred")
        assert sal >= 0.6 * 0.8 - 1e-9     # salience 继承(×0.8)

        # P2.o 闭环巩固(tom_inferred pf=0.25,继承 salience 后可采样)。
        mem.tick()
        r = mem.query(intent="META_BELIEF", k=10)
        assert not r["abstained"], r["abstention_reason"]
        assert len(r["entries"]) == 1
        assert r["entries"][0]["label"] == "INFERRED"
        assert r["receipt"].intent_name == "META_BELIEF"

        # 绑定面冒烟:二阶查询 / 估计器 / 预测依据。
        nested = _core.what_does_X_think_Y_believes(
            mem._rt.adapter, "alice", "bob", "default", "2026-06-13T00:00:00Z")
        assert len(nested) == 1 and nested[0].inner.id == "BOB1"
        assert _core.tom_depth_estimate(
            mem._rt.adapter, "alice", "default", "2026-06-13T00:00:00Z") >= 1
        basis = _core.predict_X_would(
            mem._rt.adapter, "bob", "launch", "default", "2026-06-13T00:00:00Z")
        assert len(basis.beliefs) == 1
    finally:
        mem.close()


def test_grounding_seven_acts_bindings(tmp_path):
    db = str(tmp_path / "cg7.db")
    llm = starling.make_stub_llm(default_response=CANNED)
    mem = starling.Memory.open(db, agent="alice", llm=llm)
    try:
        w = _core.CommonGroundWriter(mem._rt.adapter)
        cg = w.assert_("default", "stmt-1", ["alice", "bob"], NOW)
        w.acknowledge_manual(cg, "reviewer-jane", NOW)
        ro = sqlite3.connect(db)
        status, actor = ro.execute(
            "SELECT status, audit_actor FROM common_ground WHERE id=?",
            (cg,)).fetchone()
        assert (status, actor) == ("grounded", "reviewer-jane")

        w.unground(cg, "erasure", NOW)
        assert ro.execute("SELECT status FROM common_ground WHERE id=?",
                          (cg,)).fetchone()[0] == "suspected_diverge"

        cg2 = w.assert_("default", "stmt-2", ["alice", "bob"], NOW)
        w.acknowledge(cg2, "bob", NOW)
        w.expire_ground(cg2, "policy", NOW)
        assert ro.execute("SELECT status FROM common_ground WHERE id=?",
                          (cg2,)).fetchone()[0] == "expired"
        acts = {r[0] for r in ro.execute(
            "SELECT DISTINCT act FROM grounding_acts").fetchall()}
        ro.close()
        assert {"assert", "acknowledge", "unground", "expire"} <= acts
    finally:
        mem.close()


def test_request_reconsolidation_opens_window(tmp_path):
    """P3.a3:reconsolidate.requested 显式触发(#4)→ 引擎异步开窗。"""
    db = str(tmp_path / "recon.db")
    llm = starling.make_stub_llm(default_response=CANNED)
    mem = starling.Memory.open(db, agent="alice", llm=llm)
    try:
        assert mem.remember("Bob owns the auth module").outcome == "accepted"
        mem.tick()   # 巩固(窗口只对 CONSOLIDATED/ARCHIVED 开)
        ro = sqlite3.connect(db)
        stmt_id = ro.execute(
            "SELECT id FROM statements WHERE consolidation_state='consolidated'"
        ).fetchone()[0]

        ev_id = _core.request_reconsolidation(
            mem._rt.adapter, "default", stmt_id, "req-001", NOW)
        assert ev_id

        eng = _core.ReconsolidationEngine(mem._rt.adapter)
        eng.tick_one_batch(NOW)
        n = ro.execute(
            "SELECT COUNT(*) FROM reconsolidation_windows WHERE stmt_id=?",
            (stmt_id,)).fetchone()[0]
        ro.close()
        assert n == 1
    finally:
        mem.close()
