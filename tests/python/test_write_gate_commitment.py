import pytest
from starling import _core
from starling.memory import Memory, make_stub_llm


def _drained(tmp_path, name):
    mem = Memory.open(tmp_path / name, llm=make_stub_llm(default_response='[]'))
    mem._rt.begin_drain()
    assert mem._rt.health() == _core.RuntimeHealth.DRAINING
    return mem


def test_fulfill_rejected_when_draining(tmp_path):
    mem = _drained(tmp_path, "wg_ful.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.fulfill_commitment("stmt-nonexistent")


def test_withdraw_rejected_when_draining(tmp_path):
    mem = _drained(tmp_path, "wg_wd.db")
    with pytest.raises(_core.WriteGateRejected):
        mem._core.withdraw_commitment("stmt-nonexistent")
