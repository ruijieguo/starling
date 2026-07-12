import sqlite3
from pathlib import Path

from starling import _core
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

_STUB = ('[{"holder":"self","holder_perspective":"FIRST_PERSON","subject":"Bob",'
         '"predicate":"responsible_for","object":"auth","modality":"BELIEVES",'
         '"polarity":"POS","nesting_depth":0}]')


def _engine(tmp_path):
    cfg = DashboardConfig(db_path=str(tmp_path / "cmd.db"), token="")
    eng = DashboardEngine(cfg)
    fake = _core.FakeLLMAdapter(); fake.set_default_response(_STUB, True, "")
    eng.llm = fake
    return cfg, eng


def _samples(cfg):
    conn = sqlite3.connect(str(Path(cfg.db_path).parent / "metrics.db"))
    try:
        return conn.execute(
            "SELECT ts, backlog, embedded FROM embed_depth_samples ORDER BY ts").fetchall()
    finally:
        conn.close()


def test_sample_appends_row_matching_backlog(tmp_path):
    cfg, eng = _engine(tmp_path)
    # 写一条未 embed 的 statement(backlog=1)
    eng.remember("Bob owns auth", holder="self")
    eng.sample_embed_depth()
    rows = _samples(cfg)
    assert len(rows) == 1
    # backlog 与 queries 的 embedding_backlog 口径一致(未 embed 的 statement 数)
    conn = sqlite3.connect(f"file:{cfg.db_path}?mode=ro", uri=True)
    backlog = conn.execute(
        "SELECT COUNT(*) FROM statements s LEFT JOIN statement_vectors v "
        "ON v.stmt_id=s.id WHERE s.tenant_id=? AND v.stmt_id IS NULL", ("default",)).fetchone()[0]
    conn.close()
    assert rows[0][1] == backlog


def test_retention_prunes_old_rows(tmp_path):
    cfg, eng = _engine(tmp_path)
    # 手动塞一行超出保留窗口的旧样本
    mp = Path(cfg.db_path).parent / "metrics.db"
    eng.sample_embed_depth()                      # 建表 + 一行 now
    conn = sqlite3.connect(str(mp))
    conn.execute("INSERT INTO embed_depth_samples(ts,backlog,embedded) VALUES('2020-01-01T00:00:00Z',9,9)")
    conn.commit(); conn.close()
    eng.sample_embed_depth()                      # 再采一次 → retention 应删 2020 那行
    tss = [r[0] for r in _samples(cfg)]
    assert not any(t.startswith("2020") for t in tss)


def test_sampler_swallows_errors_no_raise(tmp_path, monkeypatch):
    cfg, eng = _engine(tmp_path)
    monkeypatch.setattr(eng, "_metrics_db_path", Path("/nonexistent-dir/xx/metrics.db"))
    eng.sample_embed_depth()                       # 不抛(保活)
