"""sample_embed_depth 的 fd 泄漏回归钉测。

背景:该采样器由后台 tick 每轮无条件调用,曾用 `with sqlite3.connect(...) as c`
—— 而 sqlite3.Connection.__exit__ 只提交事务、**不 close 连接**,fd 一直挂着。
每 tick 泄漏 3 个 fd(db + wal + 偶尔 shm),约 3 小时撑满 launchd 的 256 上限 →
accept() 得 EMFILE → 新连接被内核 RST(进程活着、端口在听却 Connection reset)。
本机观测器实测 66 次真实卡死、fd 峰值 255 坐实。修法:contextlib.closing。

这条测试跑多轮采样后比较 fd 数:泄漏时 fd 随轮数线性增长,修好后基本持平。
不钉死具体连接数(脆弱),只钉「不随轮数增长」这个不变式。
"""
import os
import sqlite3

import pytest

from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine


def _open_fd_count() -> int:
    """本进程当前打开的 fd 数。macOS/Linux 都能数 /dev/fd。"""
    try:
        return len(os.listdir("/dev/fd"))
    except OSError:  # 极端环境无 /dev/fd,退回 sentinel(测试会 skip)
        return -1


def test_sample_embed_depth_does_not_leak_fds(tmp_path):
    if _open_fd_count() < 0:
        pytest.skip("无 /dev/fd,无法数 fd")

    # DashboardEngine 构造时跑 C++ 迁移建全 schema,无需手动 seed。
    cfg = DashboardConfig(db_path=str(tmp_path / "dash.db"), token="")
    eng = DashboardEngine(cfg)

    # 预热:第一轮会建 metrics.db + 表 + 索引,并让 sqlite 打开 wal/shm 这类
    # 稳态 fd。从第二轮起才是「稳态」,基线在预热后取。
    eng.sample_embed_depth()
    eng.sample_embed_depth()
    baseline = _open_fd_count()

    # 泄漏版每轮 +3 fd;跑 40 轮,泄漏会让 fd 涨 ~120。
    for _ in range(40):
        eng.sample_embed_depth()
    after = _open_fd_count()

    grew = after - baseline
    # 稳态下允许 ±少量抖动(GC 时机、sqlite 内部),但绝不该随轮数线性涨。
    # 修好后实测 grew==0;给 5 的裕度挡偶发抖动,离泄漏版的 ~120 有两个数量级余地。
    assert grew <= 5, (
        f"sample_embed_depth 疑似泄漏 fd:40 轮后净增 {grew} 个"
        f"(baseline={baseline}, after={after})。"
        "检查 sqlite3.connect 是否用了 closing() 或 try/finally close。"
    )


def test_sample_embed_depth_still_writes_a_sample(tmp_path):
    """闭连接不能把功能一起关掉:验证采样仍落库(closing 不自动 commit,
    故第二块必须有显式 conn.commit())。"""
    cfg = DashboardConfig(db_path=str(tmp_path / "dash.db"), token="")
    eng = DashboardEngine(cfg)

    eng.sample_embed_depth()

    mp = tmp_path / "metrics.db"
    assert mp.exists(), "metrics.db 应被创建"
    conn = sqlite3.connect(str(mp))
    try:
        n = conn.execute("SELECT COUNT(*) FROM embed_depth_samples").fetchone()[0]
    finally:
        conn.close()
    assert n == 1, f"应写入恰好 1 条采样,实得 {n}(显式 commit 是否丢了?)"
