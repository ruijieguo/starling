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
