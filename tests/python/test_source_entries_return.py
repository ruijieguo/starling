"""形态 S §4.6：Python 两处返回结构的 source 条目。

两处结构**本就不同**（spec 已写明，v2 说错了）：
  - memory.py 返回 ``{"row": e.row, ...}``——整个 row 对象；
  - dashboard/engine.py 是扁平化的 subject/predicate/object。
共同点：source 条目带 ``kind="source"``，statement 条目补 ``kind="statement"``
（向后兼容）；lane 关闭时结构与本改动前等价。
"""
from __future__ import annotations

import inspect

from starling import memory as memory_module
from starling.dashboard import engine as engine_module


def test_memory_plan_query_shape_keeps_row_and_tags_kind():
    src = inspect.getsource(memory_module.Memory.query)
    # 语句条目仍是 {"row": ..., "score": ..., "label": ...}，只多一个 kind。
    assert '"row": e.row' in src
    assert '"kind": "statement"' in src
    # source 条目并列返回，字段齐全。
    assert '"source_entries"' in src
    for field in ("engram_ref", "clause_id", "speaker", "session_id",
                  "observed_at", "text", "provenance", "rrf_rank"):
        assert f'"{field}"' in src, field
    # 关闭时为空列表，不是缺键——调用方可以无条件迭代。
    assert 'getattr(r, "source_entries", ())' in src


def test_dashboard_plan_query_is_flat_and_tags_kind():
    src = inspect.getsource(engine_module.DashboardEngine.plan_query)
    # dashboard 是扁平结构，没有 row 包一层。
    assert '"subject": e.row.subject_id' in src
    assert '"kind": "statement"' in src
    assert '"source_results"' in src
    assert 'getattr(r, "source_entries", ())' in src
    # lane 计数进 receipt。
    for counter in ("source_candidates", "source_selected", "source_no_time",
                    "frontier_visible_engrams"):
        assert f'getattr(rc, "{counter}", 0)' in src, counter


def test_source_entries_absent_from_entry_dicts_when_lane_closed():
    """lane 关闭时不应把 source 混进 entries/results——两者分开承载。"""
    memory_src = inspect.getsource(memory_module.Memory.query)
    engine_src = inspect.getsource(engine_module.DashboardEngine.plan_query)
    # entries 列表里只有 statement；source 走独立的 source_entries / source_results。
    entries_block = memory_src.split('"entries":', 1)[1].split('"source_entries"', 1)[0]
    assert '"kind": "source"' not in entries_block
    results_block = engine_src.split('"results":', 1)[1].split('"context_pack"', 1)[0]
    assert '"kind": "source"' not in results_block
