"""FOLLOWUP-3 [P1 bus]: causation_chain inheritance + system.runaway emission.

Spec docs/design/subsystems_design/05_bus.md:273:
    Bus 生成新事件 N：若有 parent，N.causation_chain = parent.causation_chain + [parent.event_id]
docs/design/subsystems_design/05_bus.md:274:
    len(causation_chain) > 3 → 拒绝派生事件，emit system.runaway(...)

Pre-fix: bus.cpp:118-120 set causation_chain = { parent_event_id }, dropping
the parent's accumulated ancestry. Multi-hop subscribers could not trace a
storm to its root, idempotency_root was wrong off the second hop, and the
overflow path threw without emitting system.runaway.

This test pins the new behavior:
  1. Empty parent → empty chain (root event).
  2. Single parent → chain == [parent.event_id].
  3. Grandchild → chain == [grandparent.event_id, parent.event_id].
  4. Depth-4 attempt → DERIVED EVENT REJECTED + system.runaway emitted with
     chain_root + depth + source_event_id payload.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from starling import _core, runtime


@pytest.fixture
def rt(tmp_path):
    r = runtime._build_local_store_sqlite_runtime(tmp_path / "starling.db")
    r.start()
    yield r


def _seed_engram(rt, engram_id: str) -> None:
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        conn.execute(
            "INSERT INTO engrams("
            "  id,tenant_id,content_hash,source_kind,ingest_policy,ingest_mode,"
            "  privacy_class,retention_mode,refcount,payload_inline,created_at,"
            "  source_item_id"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (engram_id, "default", f"hash-{engram_id}", "user_input", "store",
             "whole_record", "internal", "audit_retain", 0, b"\x00",
             "2026-05-26T09:00:00Z", engram_id))
        conn.commit()


def _make_extracted(*, predicate: str, object_value: str, object_hash: str):
    s = _core.ExtractedStatement()
    s.holder_id          = "alice"
    s.holder_tenant_id   = "default"
    s.holder_perspective = _core.Perspective.FIRST_PERSON
    s.subject_kind       = "cognizer"
    s.subject_id         = "bob"
    s.predicate          = predicate
    s.object_kind        = "str"
    s.object_value       = object_value
    s.canonical_object_hash = object_hash
    s.modality           = _core.Modality.BELIEVES
    s.polarity           = _core.Polarity.POS
    s.confidence         = 0.9
    s.observed_at        = "2026-05-26T09:00:00Z"
    s.source_hash        = f"src-{object_value}"
    s.perceived_by       = ["alice"]
    return s


def _chain_for_event(rt, event_id: str) -> list[str]:
    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        row = conn.execute(
            "SELECT causation_chain_json FROM bus_events WHERE event_id = ?",
            (event_id,)).fetchone()
    assert row is not None, f"bus_events row for {event_id!r} missing"
    return json.loads(row[0])


def test_root_event_has_empty_causation_chain(rt):
    _seed_engram(rt, "engram-root")
    s = _make_extracted(predicate="responsible_for",
                        object_value="auth", object_hash="a" * 64)
    out = _core.Bus(rt.adapter).write(s, "engram-root", "span-root", None)
    assert out["kind"] == "accepted"
    chain = _chain_for_event(rt, out["event_id"])
    assert chain == [], \
        f"root event must have empty causation_chain; got {chain!r}"


def test_single_parent_chain_has_one_entry(rt):
    _seed_engram(rt, "engram-1a")
    _seed_engram(rt, "engram-1b")
    bus = _core.Bus(rt.adapter)
    out_p = bus.write(_make_extracted(predicate="responsible_for",
                                      object_value="auth-p",
                                      object_hash="b" * 64),
                      "engram-1a", "span-1a", None)
    parent_event_id = out_p["event_id"]

    out_c = bus.write(_make_extracted(predicate="responsible_for",
                                      object_value="auth-c",
                                      object_hash="c" * 64),
                      "engram-1b", "span-1b", parent_event_id)
    chain = _chain_for_event(rt, out_c["event_id"])
    assert chain == [parent_event_id], \
        f"child must have [parent.event_id]; got {chain!r}"


def test_grandchild_inherits_parent_chain_plus_parent_id(rt):
    """Spec: N.causation_chain = parent.causation_chain + [parent.event_id]."""
    for eg in ("engram-2a", "engram-2b", "engram-2c"):
        _seed_engram(rt, eg)
    bus = _core.Bus(rt.adapter)
    out_g = bus.write(_make_extracted(predicate="responsible_for",
                                      object_value="auth-g",
                                      object_hash="d" * 64),
                      "engram-2a", "span-2a", None)
    g_event_id = out_g["event_id"]

    out_p = bus.write(_make_extracted(predicate="responsible_for",
                                      object_value="auth-pp",
                                      object_hash="e" * 64),
                      "engram-2b", "span-2b", g_event_id)
    p_event_id = out_p["event_id"]
    assert _chain_for_event(rt, p_event_id) == [g_event_id]

    out_c = bus.write(_make_extracted(predicate="responsible_for",
                                      object_value="auth-cc",
                                      object_hash="f" * 64),
                      "engram-2c", "span-2c", p_event_id)
    chain = _chain_for_event(rt, out_c["event_id"])
    assert chain == [g_event_id, p_event_id], (
        "grandchild chain must accumulate: "
        f"expected [{g_event_id!r}, {p_event_id!r}], got {chain!r}"
    )


def test_chain_overflow_rejects_and_emits_system_runaway(rt):
    """Depth-4 attempt → derived write rejected + system.runaway event emitted.

    Build a chain of length 3 (root → c1 → c2 → c3 has chain length 3 itself
    after inheritance: [root, c1, c2]), then attempt c4 whose chain would be
    length 4. The Bus must:
      - reject the c4 write (no statement row, no statement.written event)
      - emit a single system.runaway event with chain_root + depth +
        source_event_id in the payload
    """
    for eg in ("engram-3a", "engram-3b", "engram-3c", "engram-3d", "engram-3e"):
        _seed_engram(rt, eg)
    bus = _core.Bus(rt.adapter)
    out0 = bus.write(_make_extracted(predicate="responsible_for",
                                     object_value="o0", object_hash="0" * 64),
                     "engram-3a", "span-3a", None)
    out1 = bus.write(_make_extracted(predicate="responsible_for",
                                     object_value="o1", object_hash="1" * 64),
                     "engram-3b", "span-3b", out0["event_id"])
    out2 = bus.write(_make_extracted(predicate="responsible_for",
                                     object_value="o2", object_hash="2" * 64),
                     "engram-3c", "span-3c", out1["event_id"])
    # out2.causation_chain = [out0, out1] (length 2); a child of out2 would
    # have chain [out0, out1, out2] = length 3 (still legal); a grandchild
    # of out2 would have chain length 4 → overflow.
    out3 = bus.write(_make_extracted(predicate="responsible_for",
                                     object_value="o3", object_hash="3" * 64),
                     "engram-3d", "span-3d", out2["event_id"])
    chain3 = _chain_for_event(rt, out3["event_id"])
    assert len(chain3) == 3, f"out3 chain should be length 3, got {len(chain3)}"

    # out4 attempt → would produce chain length 4. Must reject + emit runaway.
    with pytest.raises(Exception) as excinfo:
        bus.write(_make_extracted(predicate="responsible_for",
                                  object_value="o4", object_hash="4" * 64),
                  "engram-3e", "span-3e", out3["event_id"])
    assert "runaway" in str(excinfo.value).lower() or \
           "causation" in str(excinfo.value).lower(), \
        f"rejection error must mention runaway/causation; got {excinfo.value!r}"

    with sqlite3.connect(str(rt.adapter.db_path)) as conn:
        # No statement.written for span-3e (the rejected write)
        n_written_overflow = conn.execute(
            "SELECT COUNT(*) FROM bus_events "
            " WHERE event_type = 'statement.written' "
            "   AND payload_json LIKE '%span-3e%'").fetchone()[0]
        assert n_written_overflow == 0, \
            "rejected write must NOT produce a statement.written event"

        # Exactly one system.runaway emitted, payload includes chain_root + depth.
        runaway_rows = conn.execute(
            "SELECT payload_json, causation_chain_json FROM bus_events "
            " WHERE event_type = 'system.runaway'").fetchall()
    assert len(runaway_rows) == 1, \
        f"expected exactly 1 system.runaway, got {len(runaway_rows)}"
    payload = json.loads(runaway_rows[0][0])
    assert payload.get("chain_root") == out0["event_id"], \
        f"runaway payload chain_root must be the chain origin {out0['event_id']!r}; got {payload!r}"
    assert payload.get("depth") == 4, \
        f"runaway payload depth must be 4 (the rejected attempt); got {payload!r}"
    assert payload.get("source_event_id") == out3["event_id"], \
        f"runaway source_event_id must be the parent that triggered overflow; got {payload!r}"
