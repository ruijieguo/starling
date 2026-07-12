import sqlite3
import time
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
    except sqlite3.OperationalError:
        return []          # table not created yet (no sample taken so far) — empty, not an error
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


def test_sampler_runs_on_idle_tick(tmp_path):
    """回归测试(review fix):did_work=False 的空闲轮也必须采到样本。此前
    sample_embed_depth 挂在 app.py `_on_tick` 上,而 `_on_tick` 只在
    engine._loop 判定 did_work=True 时才被调(engine.py _loop);embedder
    卡死/空闲轮(did_work=False)因此被静默跳过——恰好是「backlog 卡住/增长」
    这个本序列要回答的场景。修法:sample_embed_depth 现由 engine._loop 每轮
    无条件调用(紧邻 _sample_backpressure),不再经 on_tick/did_work 门控。"""
    cfg, eng = _engine(tmp_path)
    try:
        # 自检:全新引擎 + 空 DB 上手动 tick() 一次,确认真是空闲轮
        # (did_work=False)——不能靠 remember() 造数据,否则可能巧合命中某个
        # 非零字段,削弱这条断言要证明的东西。这次手动 tick 不经过
        # start_background_tick 的 _loop,不会写 metrics.db。
        stats = eng.tick("2026-07-12T00:00:00Z")
        did_work = any(v for k, v in stats.items()
                       if k not in ("stage_timings_ms", "stages_skipped"))
        assert not did_work, f"test setup invalid, expected an idle tick: {stats}"
        # (手动 tick() 走 self._core.tick 直连,不经 engine._loop,不会创建/
        # 写 metrics.db——所以这里还不能用 _samples(cfg),表可能都不存在。)

        # on_tick=None:样本必须来自 engine._loop 自身,不依赖 app.py 的桥接
        # 回调——若 sample_embed_depth 又被重新挂回 did_work 门控的 on_tick
        # 分支,这里永远不会有 on_tick 可调,样本也就永远不会出现,测试会超时失败。
        eng.start_background_tick(0.05)
        deadline = time.monotonic() + 5.0
        rows = []
        while time.monotonic() < deadline:
            rows = _samples(cfg)
            if rows:
                break
            time.sleep(0.05)
        assert rows, "空闲轮(did_work=False)未采到 embed-depth 样本"
    finally:
        eng.close()
