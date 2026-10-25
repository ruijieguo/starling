"""世界注册表与快照（W1/W2）：绑定、切换、路由。

设计：docs/superpowers/specs/2026-10-25-world-scene-management-design.md
"""
import sqlite3

import pytest

from starling import _core


def _code(exc) -> str:
    return _core.world_store_error_code(exc)


def test_binding_registry_roundtrip(tmp_path):
    reg_path = str(tmp_path / "worlds.json")
    reg = _core.world_ensure_registry(reg_path, str(tmp_path / "dashboard.db"), "default")
    assert reg["active"] == "default"
    assert reg["snapshot_retention"] == 5
    assert set(reg["worlds"]) == {"default"}

    out = _core.world_create(reg, str(tmp_path), "sim-1", "模拟一", "2026-10-25T01:00:00Z")
    reg = out["registry"]
    assert out["world"]["tenant"] == "sim-1"
    assert out["world"]["db_path"].endswith("worlds/sim-1/world.db")
    _core.world_save_registry(reg_path, reg)
    assert set(_core.world_load_registry(reg_path)["worlds"]) == {"default", "sim-1"}


def test_binding_error_codes(tmp_path):
    reg = _core.world_ensure_registry(str(tmp_path / "w.json"), str(tmp_path / "d.db"), "default")
    with pytest.raises(_core.WorldStoreError) as ei:
        _core.world_create(reg, str(tmp_path), "Bad Name", "", "2026-10-25T01:00:00Z")
    assert _code(ei.value) == "invalid_world_name"
    with pytest.raises(_core.WorldStoreError) as ei:
        _core.world_set_active(reg, "nope")
    assert _code(ei.value) == "world_not_found"
    assert isinstance(ei.value, RuntimeError)


def test_binding_snapshot_and_stats(tmp_path):
    reg = _core.world_ensure_registry(str(tmp_path / "w.json"), str(tmp_path / "d.db"), "default")
    reg = _core.world_create(reg, str(tmp_path), "sim-1", "", "2026-10-25T01:00:00Z")["registry"]
    db = reg["worlds"]["sim-1"]["db_path"]
    _core.SqliteAdapter.open(db)   # 跑迁移建库
    stats = _core.world_stats(db, "sim-1")
    assert stats["engrams"] == 0 and stats["db_bytes"] > 0

    out = _core.world_take_snapshot(reg, "sim-1", note="手动")
    snap = out["snapshot"]
    assert snap["kind"] == "manual" and snap["note"] == "手动"
    con = sqlite3.connect(f"file:{snap['path']}?mode=ro", uri=True)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()
    reg = _core.world_delete_snapshot(out["registry"], "sim-1", snap["id"])
    assert reg["snapshots"]["sim-1"] == []
