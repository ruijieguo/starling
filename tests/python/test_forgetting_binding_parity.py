"""forgetting-curve binding parity — Phase 3 片 5。

钉住 _core.forgetting_s_t / forgetting_seconds_until 与 src/replay/forgetting_curve.cpp
同输入同输出(DRY:dashboard 衰减预报复用 C++ 曲线,绝不在 Python 复现公式)。
若 C++ 公式变动,这些钉测会失败,提醒同步更新文档/前端解读。"""
import math

from starling import _core

_BASE = 86400.0   # forgetting_curve.cpp kBase = 1 day
_MOD = {"COMMITS": 4.0, "NORM_OUGHT": 3.0, "KNOWS": 2.0, "BELIEVES": 1.0, "ASSUMES": 0.5}


def _s0(*, salience=0.0, access_count=0, active_grounded=False, modality="BELIEVES", valence=0.0):
    """手算 compute_s0(钉测参照)。"""
    return (_BASE * (1 + 0.5 * access_count) * (1 + salience)
            * (1 + 2 * (1 if active_grounded else 0))
            * _MOD.get(modality, 1.0) * (1 + 0.3 * abs(valence)))


def _s_t(*, last="2026-01-01T00:00:00Z", now="2026-01-01T00:00:00Z", **kw):
    return _core.forgetting_s_t(salience=kw.get("salience", 0.0),
                                access_count=kw.get("access_count", 0),
                                active_grounded=kw.get("active_grounded", False),
                                modality=kw.get("modality", "BELIEVES"),
                                affect_valence=kw.get("valence", 0.0),
                                last_accessed_iso=last, now_iso=now)


def test_s_t_fresh_is_one():
    assert _s_t() == 1.0                      # Δt=0 → 1.0


def test_s_t_matches_exp_minus_one_at_one_s0():
    # S0(BELIEVES 默认)=86400 → Δt=1 day → S(t)=exp(-1)。
    assert math.isclose(_s_t(now="2026-01-02T00:00:00Z"), math.exp(-1), rel_tol=1e-9)


def test_seconds_until_is_curve_inverse():
    secs = _core.forgetting_seconds_until(salience=0.0, access_count=0, active_grounded=False,
                                          modality="BELIEVES", affect_valence=0.0, target=0.05)
    assert math.isclose(secs, -_s0() * math.log(0.05), rel_tol=1e-9)


def test_seconds_until_invalid_target_is_negative():
    for bad in (0.0, 1.0, 1.5, -0.1):
        assert _core.forgetting_seconds_until(
            salience=0.0, access_count=0, active_grounded=False,
            modality="BELIEVES", affect_valence=0.0, target=bad) < 0.0


def test_grounded_and_access_and_modality_slow_decay():
    # active_grounded / access_count / 更"硬"的 modality 抬高 S0 → 同 Δt 下 S(t) 更高(更难忘)。
    plain = _s_t(now="2026-02-01T00:00:00Z")
    assert _s_t(now="2026-02-01T00:00:00Z", active_grounded=True) > plain
    assert _s_t(now="2026-02-01T00:00:00Z", access_count=10) > plain
    assert _s_t(now="2026-02-01T00:00:00Z", modality="COMMITS") > plain
