from pathlib import Path
import pytest
from starling import _core
from starling.memory import Memory, make_stub_llm


def test_request_reconsolidation_rejected_when_draining(tmp_path):
    mem = Memory.open(tmp_path / "wg_recon.db", llm=make_stub_llm(default_response='[]'))
    mem._rt.begin_drain()
    assert mem._rt.health() == _core.RuntimeHealth.DRAINING
    with pytest.raises(_core.WriteGateRejected):
        mem._core.request_reconsolidation("stmt-x", request_id="req-1")
