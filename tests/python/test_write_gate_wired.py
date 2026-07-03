"""TC-WRITE-GATE-WIRED: production Runtime 构造时 install_write_gate 已接线。

验证:
- start() 后 adapter.write_admitted() == True  (READY → 放行)
- begin_drain() 后 adapter.write_admitted() == False (DRAINING → 拒)
- bare adapter(无钩子)write_admitted() 恒 True
"""
from pathlib import Path

from starling import _core
from starling import runtime as rt_mod


def test_production_runtime_wires_write_gate(tmp_path: Path) -> None:
    """READY 放行 / DRAINING 拒写。"""
    rt = rt_mod._build_local_store_sqlite_runtime(tmp_path / "wired.db")
    rt.start()
    assert rt.adapter.write_admitted() is True      # READY → 放行
    rt.begin_drain()
    assert rt.adapter.write_admitted() is False     # DRAINING → 拒


def test_bare_adapter_write_admitted_always_true(tmp_path: Path) -> None:
    """裸 adapter(无 install_write_gate 钩子)write_admitted() 恒 True。

    验证 set_write_admit 未调用时的缺省行为:!write_admit_ → True。
    """
    adapter = _core.SqliteAdapter.open(str(tmp_path / "bare.db"))
    assert adapter.write_admitted() is True
