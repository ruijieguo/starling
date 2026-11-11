"""迁移 0040:events 加行身份 incarnation(裁定 R102、R118)。

只加列,不重建表,不回填:39 版库里的旧行迁移后 incarnation 为 '',其余列原样;之后新写的行由 C++ 在 INSERT 时
写一个随机身份(UUID v4);旧的 pending 行在 begin 第一次碰到它时补上身份。摘要排除这一列,所以迁移前后同一个库的
摘要不变。

离线:stub LLM、默认 stub 嵌入器,不发任何真实网络请求。
"""
import hashlib
import re
import sqlite3
from pathlib import Path

import starling
from starling import _core

# 与 tests/python/test_migration_0038.py 的 CANNED_JSON 相同:单元素 JSON 数组。
CANNED_JSON = (
    '[{"holder":"alice","holder_perspective":"FIRST_PERSON",'
    '"subject":"cog-bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)
NOW = "2026-11-11T00:00:00Z"
MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
UUID_V4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
# 0039 的 events 列(按表里的顺序)。
COLUMNS_39 = ["tenant_id", "holder_id", "key", "text", "interlocutor", "text_sha256", "engram_ref",
              "statement_ids_json", "seq", "state", "failure_category"]


def _mem(path, llm=None):
    return starling.Memory.open(str(path), agent="alice",
                                llm=llm or starling.make_stub_llm(default_response=CANNED_JSON))


def _failing_llm():
    llm = starling.make_stub_llm(default_response="")
    llm.set_default_response("", False, "stub extraction failure")
    return llm


def _library_at_39(path):
    """照迁移文件逐个执行 1..39,登记 schema_migrations(checksum 与 C++ 嵌入的相同),得到一个真正的 39 版库。"""
    with sqlite3.connect(str(path)) as db:
        db.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,name TEXT NOT NULL,"
                   "applied_at TEXT NOT NULL,checksum TEXT NOT NULL)")
        for migration in sorted(MIGRATIONS.glob("*.sql")):
            version = int(migration.name.split("_", 1)[0])
            if version >= 40:
                continue
            sql = migration.read_text()
            db.executescript(sql)
            db.execute("INSERT INTO schema_migrations VALUES(?,?,?,?)",
                       (version, migration.stem.split("_", 1)[1], NOW,
                        hashlib.sha256(sql.encode()).hexdigest()))
            db.commit()
    db.close()


def _insert_legacy(path, holder, key, text, seq, state, *, failure_category=""):
    with sqlite3.connect(str(path)) as db:
        db.execute("INSERT INTO events(tenant_id,holder_id,key,text,interlocutor,text_sha256,seq,state,"
                   "failure_category) VALUES('default',?,?,?,'bob',?,?,?,?)",
                   (holder, key, text, hashlib.sha256(text.encode()).hexdigest(), seq, state,
                    failure_category))
    db.close()


def _rows(path, columns):
    with sqlite3.connect(str(path)) as db:
        rows = db.execute(f"SELECT {','.join(columns)} FROM events ORDER BY key").fetchall()
    db.close()
    return rows


def _incarnation(path, key):
    with sqlite3.connect(str(path)) as db:
        (value,) = db.execute("SELECT incarnation FROM events WHERE key=?", (key,)).fetchone()
    db.close()
    return value


def _table_shape(path):
    with sqlite3.connect(str(path)) as db:
        info = [tuple(r[1:]) for r in db.execute("PRAGMA table_info(events)")]
        indexes = sorted(r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='events'"))
    db.close()
    return info, indexes


def _schema_version(path):
    with sqlite3.connect(str(path)) as db:
        (version,) = db.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    db.close()
    return version


def _read_only_digest(path):
    """只读打开(不跑迁移)算摘要。"""
    reader = _core.SqliteAdapter.open_read_only(str(path))
    try:
        assert reader.schema_version() == _schema_version(path)
        return _core.memory_digest(reader.connection(), "default")
    finally:
        reader.close()


def test_0040_adds_only_the_column_and_old_rows_read_blank(tmp_path):
    db = tmp_path / "v39.db"
    _library_at_39(db)
    assert _schema_version(db) == 39
    _insert_legacy(db, "alice", "k-committed", "bob:one", 0, "committed")
    _insert_legacy(db, "alice", "k-pending", "bob:two", 1, "pending", failure_category="timeout")
    _insert_legacy(db, "alice", "k-abandoned", "bob:three", 2, "abandoned")
    _insert_legacy(db, "", "k-unclaimed", "bob:four", 3, "pending")
    before_rows = _rows(db, COLUMNS_39)
    before_info, before_indexes = _table_shape(db)

    mem = _mem(db)                                        # 打开即迁移到最新
    mem.close()
    assert _schema_version(db) == 40 == _core.latest_schema_version()
    after_info, after_indexes = _table_shape(db)
    # 只多了末尾一列:TEXT NOT NULL DEFAULT '',不在主键里;原有列、主键、索引都不变。
    assert after_info[:-1] == before_info
    assert after_info[-1] == ("incarnation", "TEXT", 1, "''", 0)
    assert after_indexes == before_indexes
    # 不回填:旧行全是 '',其余列逐列原样。
    assert _rows(db, COLUMNS_39) == before_rows
    assert {key: _incarnation(db, key) for (key,) in _rows(db, ["key"])} == {
        "k-abandoned": "", "k-committed": "", "k-pending": "", "k-unclaimed": ""}


def test_remember_after_0040_writes_an_incarnation_and_fills_a_legacy_pending_row(tmp_path):
    db = tmp_path / "v39.db"
    _library_at_39(db)
    _insert_legacy(db, "alice", "k-committed", "bob:one", 0, "committed")
    _insert_legacy(db, "alice", "k-pending", "bob:two", 1, "pending", failure_category="timeout")
    mem = _mem(db)

    new = mem.remember_event("k-new", "bob:我负责鉴权模块", interlocutor="bob")
    assert new.outcome == "accepted"
    assert UUID_V4.match(_incarnation(db, "k-new"))
    # 旧的 pending 行:begin 补上身份,收尾照常。
    retried = mem.remember_event("k-pending", "bob:two", interlocutor="bob")
    assert retried.outcome == "accepted" and not retried.extraction_failed
    assert UUID_V4.match(_incarnation(db, "k-pending"))
    assert _incarnation(db, "k-pending") != _incarnation(db, "k-new")
    # 旧的 committed 行:begin 直接返回存的结果,不交给 finish,不补。
    assert mem.remember_event("k-committed", "bob:one", interlocutor="bob").outcome == "idempotent"
    assert _incarnation(db, "k-committed") == ""
    assert mem.next_seq() == 3
    mem.close()


def test_digest_is_unchanged_across_0040(tmp_path):
    """先建一个 39 版、带事件行(提交、pending、放弃)与语句和向量的库,迁到 40,摘要前后相同。

    带语句的 39 版库用当前代码写出来再退回 39:删掉 incarnation 列与 0040 的迁移记录。退回后的 events 表形与照迁移文件
    建出来的 39 版库逐列相同(下面先比这一项),所以这就是一个旧版本写出的库。"""
    db = tmp_path / "lib.db"
    mem = _mem(db)
    mem.remember_event("e#0", "bob:我负责鉴权模块", interlocutor="bob")
    mem.embed_pending("2026-01-01T00:01:00Z")
    mem.close()
    failing = _mem(db, llm=_failing_llm())
    assert failing.remember_event("e#1", "bob:明天开会", interlocutor="bob").extraction_failed
    assert failing.remember_event("e#2", "bob:作废", interlocutor="bob").extraction_failed
    failing.abandon_event("e#2")
    failing.close()

    with sqlite3.connect(str(db)) as conn:
        conn.execute("ALTER TABLE events DROP COLUMN incarnation")
        conn.execute("DELETE FROM schema_migrations WHERE version = 40")
    conn.close()
    reference = tmp_path / "ref39.db"
    _library_at_39(reference)
    assert _table_shape(db) == _table_shape(reference)
    assert _schema_version(db) == 39
    states = dict(_rows(db, ["key", "state"]))
    assert states == {"e#0": "committed", "e#1": "pending", "e#2": "abandoned"}
    before = _read_only_digest(db)
    rows_before = _rows(db, COLUMNS_39)

    mem = _mem(db)                                        # 迁到 40
    after = mem.digest()
    mem.close()
    assert _schema_version(db) == 40
    assert _rows(db, COLUMNS_39) == rows_before
    assert after == before == _read_only_digest(db)
    assert before != hashlib.sha256(b'{"events":[],"statement_vectors":[],"statements":[]}').hexdigest()
