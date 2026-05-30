from starling import _core


def test_classes_exist():
    for n in ["CommitmentEngine", "PolicyEngine", "AffectVector", "ActionGuard", "GuardVerdict"]:
        assert hasattr(_core, n), n


def test_affect_salience_callable():
    v = _core.AffectVector()
    v.valence = 0.5
    v.arousal = 0.8
    v.novelty = 0.6
    v.stakes = 0.9
    assert _core.affect_salience(v, 1.0) > 0.0


def test_action_guard_check():
    g = _core.ActionGuard()
    g.allowed_actions = {"log_note"}
    assert _core.action_guard_check(g, "log_note") == _core.GuardVerdict.Allow
    assert _core.action_guard_check(g, "nope") == _core.GuardVerdict.Blocked
