"""Memory.digest 与召回命中的内容 id(逻辑摘要:换掉身份、只留内容)。

rise 的 config_hash 含起点 library 的摘要:两个库内容相同就必须给同一个摘要,内容
一变就必须变。行 id 是 UUID、库与库之间必然不同,所以字节比对没用。digest 按排除清单
规范化 statements / statement_vectors / events 三张表,把 UUID 换成被指向内容的 id,
再取 sha256。

离线:stub LLM、默认 stub 嵌入器,不发任何真实网络请求。
"""
import hashlib
import re
import sqlite3

import starling

# 与 tests/python/test_memory_remember_event.py 的 CANNED_JSON 相同:单元素 JSON 数组。
CANNED_JSON = (
    '[{"holder":"alice","holder_perspective":"FIRST_PERSON",'
    '"subject":"cog-bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)

EMPTY = hashlib.sha256(b'{"events":[],"statement_vectors":[],"statements":[]}').hexdigest()


def _failing_llm():
    llm = starling.make_stub_llm(default_response="")
    llm.set_default_response("", False, "stub extraction failure")
    return llm


def _db(tmp_path, name):
    return starling.Memory.open(str(tmp_path / name), agent="alice",
                                llm=starling.make_stub_llm(default_response=CANNED_JSON))


def _fill(mem):
    mem.remember_event("e#0", "bob:我负责鉴权模块", interlocutor="bob")
    mem.embed_pending("2026-01-01T00:01:00Z")


def _sql(tmp_path, name, sql):
    with sqlite3.connect(str(tmp_path / name)) as c:
        c.execute(sql)


def test_empty_library_digest_is_fixed(tmp_path):
    assert _db(tmp_path, "a.db").digest() == EMPTY == _db(tmp_path, "b.db").digest()


def test_same_content_different_uuids_same_digest(tmp_path):
    a, b = _db(tmp_path, "a.db"), _db(tmp_path, "b.db")
    _fill(a); _fill(b)
    assert a.digest() == b.digest() != EMPTY


def test_excluded_columns_do_not_change_digest(tmp_path):
    a = _db(tmp_path, "a.db"); _fill(a); d0 = a.digest()
    for sql in ("UPDATE statements SET access_count=access_count+5, last_accessed='2030-01-01T00:00:00Z',"
                " updated_at='2030-01-01T00:00:00Z', replay_count=replay_count+1,"
                " last_replayed='2030-01-01T00:00:00Z', last_replay_batch_id='x', inferred_at='2030-01-01T00:00:00Z'",
                "UPDATE statement_vectors SET retry_count=9, last_attempt_at='2030-01-01T00:00:00Z',"
                " embedded_at='2030-01-01T00:00:00Z'"):
        _sql(tmp_path, "a.db", sql)
    assert a.digest() == d0


def test_digest_columns_change_digest(tmp_path):
    a = _db(tmp_path, "a.db"); _fill(a); d0 = a.digest()
    _sql(tmp_path, "a.db", "UPDATE statements SET activation=activation+0.5")   # S18
    d1 = a.digest(); assert d1 != d0
    _sql(tmp_path, "a.db", "UPDATE statement_vectors SET raw_embedding=zeroblob(32)")
    d2 = a.digest(); assert d2 != d1
    _sql(tmp_path, "a.db", "UPDATE events SET failure_category='timeout'")
    assert a.digest() != d2


def test_statement_ids_json_uuids_are_mapped_to_content_ids(tmp_path):
    a, b = _db(tmp_path, "a.db"), _db(tmp_path, "b.db")
    _fill(a); _fill(b)
    with sqlite3.connect(str(tmp_path / "a.db")) as c:
        ids = [r[0] for r in c.execute("SELECT statement_ids_json FROM events")]
    with sqlite3.connect(str(tmp_path / "b.db")) as c:
        assert [r[0] for r in c.execute("SELECT statement_ids_json FROM events")] != ids
    assert a.digest() == b.digest()


def test_dangling_reference_maps_to_missing(tmp_path):
    a, b = _db(tmp_path, "a.db"), _db(tmp_path, "b.db")
    _fill(a); _fill(b)
    _sql(tmp_path, "a.db", "UPDATE statements SET supersedes_id='no-such-1'")
    _sql(tmp_path, "b.db", "UPDATE statements SET supersedes_id='no-such-2'")
    assert a.digest() == b.digest()


def test_abandoned_event_counts_only_key_and_state(tmp_path):
    def make(name, text):
        m = starling.Memory.open(str(tmp_path / name), agent="alice", llm=_failing_llm())
        m.remember_event("e#0", text, interlocutor="bob"); m.abandon_event("e#0"); return m
    a, b = make("a.db", "bob:one"), make("b.db", "bob:two")
    assert a.digest() == b.digest() != EMPTY


def test_rows_invisible_to_recall_still_count(tmp_path):
    # 全行进摘要:pending_review、volatile、forgotten、被取代后 archived 的行都进。
    a = _db(tmp_path, "a.db"); _fill(a); d0 = a.digest()
    _sql(tmp_path, "a.db", "UPDATE statements SET review_status='pending_review'")
    d1 = a.digest(); assert d1 != d0
    assert a.recall("bob", include_volatile=True) == []
    _sql(tmp_path, "a.db", "UPDATE statements SET object_value='billing'")
    assert a.digest() != d1


def test_content_ids_maps_statement_uuids_and_marks_unknown_ones_missing(tmp_path):
    a, b = _db(tmp_path, "a.db"), _db(tmp_path, "b.db")
    ids_a = list(a.remember_event("e#0", "bob:我负责鉴权模块", interlocutor="bob").statement_ids)
    ids_b = list(b.remember_event("e#0", "bob:我负责鉴权模块", interlocutor="bob").statement_ids)
    got = a.content_ids(ids_a + ["no-such-id"])
    assert set(got) == set(ids_a) | {"no-such-id"} and got["no-such-id"] == "missing"
    assert all(re.fullmatch(r"[0-9a-f]{64}", got[i]) for i in ids_a)       # 与召回命中的 content_id 同一形状
    assert sorted(got[i] for i in ids_a) == sorted(b.content_ids(ids_b).values())   # UUID 不同,内容 id 相同


def test_recall_hits_carry_same_content_id_across_libraries(tmp_path):
    a, b = _db(tmp_path, "a.db"), _db(tmp_path, "b.db")
    _fill(a); _fill(b)
    ha = a.recall("我负责鉴权模块", include_volatile=True)
    hb = b.recall("我负责鉴权模块", include_volatile=True)
    assert ha and [h["content_id"] for h in ha] == [h["content_id"] for h in hb]
    assert ha[0]["row"].id != hb[0]["row"].id

def test_tenant_name_is_not_content(tmp_path):
    # tenant 已由 WHERE tenant_id=?1 划定作用域,名字不是内容:同内容、不同 tenant 名,摘要相同。
    a = starling.Memory.open(str(tmp_path / "a.db"), agent="alice", tenant_id="alpha",
                             llm=starling.make_stub_llm(default_response=CANNED_JSON))
    b = starling.Memory.open(str(tmp_path / "b.db"), agent="alice", tenant_id="beta",
                             llm=starling.make_stub_llm(default_response=CANNED_JSON))
    _fill(a); _fill(b)
    assert a.digest() == b.digest() != EMPTY
