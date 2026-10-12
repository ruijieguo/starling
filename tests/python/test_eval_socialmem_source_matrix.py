"""WP1.A:零抽取来源召回消融矩阵的纯逻辑与原生回放测试(无网络、无模型、不读真语料)。"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_KEEP: list = []

TURNS = [
    {"speaker": "Ada", "text": "Copper lantern in Kyoto.", "turn_id": "s1_t2", "session_id": "s1",
     "turn_index": 2, "observed_at": "2025-01-01T10:00:00Z"},
    {"speaker": "Bob", "text": "I prefer green tea.", "turn_id": "s1_t3", "session_id": "s1",
     "turn_index": 3, "observed_at": "2025-01-01T10:05:00Z"},
]


def _load():
    path = _SCRIPTS / "eval_socialmem_source_matrix.py"
    if not path.exists():
        pytest.fail("scripts/eval_socialmem_source_matrix.py 尚不存在(功能缺失)")
    spec = importlib.util.spec_from_file_location("eval_socialmem_source_matrix", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rec(item, query_type, gold_turns, **over):
    rec = {"item_id": item, "query_type": query_type, "answer_format": "long_form",
           "question": "copper lantern Kyoto", "history": TURNS,
           "gold_statements": [{"turn_id": t, "object": "x"} for t in gold_turns],
           "source": {"network_id": "n1"}}
    rec.update(over)
    return rec


def _row(arm, item, query_type, gold, hit, nbytes=1000, count=10, bound=False):
    return {"arm": arm, "item_id": item, "query_type": query_type, "gold": gold, "hit": hit,
            "all": hit == gold, "context_bytes": nbytes, "source_count": count, "budget_bound": bound}


def _library(tmp_path):
    from starling import _core, runtime
    lib = tmp_path / "lib.db"
    rt = runtime._build_local_store_sqlite_runtime(lib)
    rt.start()
    _KEEP.append(rt)
    _core.retain_source_turns(rt.adapter, "default", ["Ada", "Bob"], json.dumps(TURNS), "2026-01-01T00:00:00Z")
    return lib


def _events(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("select count(*) from bus_events").fetchone()[0]


# ---------------------------- 金标证据与覆盖 ----------------------------

def test_gold_turn_ids_are_distinct_and_keep_first_seen_order():
    mod = _load()
    assert mod.gold_turn_ids(_rec("a", "Q5", ["t3", "t1", "t3", "t2"])) == ["t3", "t1", "t2"]


def test_gold_turn_ids_refuse_a_question_without_usable_gold_evidence():
    mod = _load()
    with pytest.raises(ValueError, match="gold"):
        mod.gold_turn_ids(_rec("a", "Q5", []))
    broken = _rec("a", "Q5", ["t1"])
    broken["gold_statements"][0]["turn_id"] = None
    with pytest.raises(ValueError, match="gold"):
        mod.gold_turn_ids(broken)


def test_coverage_counts_hits_and_full_coverage():
    mod = _load()
    refs = [{"turn_id": "t1"}, {"turn_id": "t9"}, {"turn_id": None}]
    assert mod.coverage(["t1", "t2"], refs) == {"gold": 2, "hit": 1, "all": False}
    assert mod.coverage(["t1"], refs) == {"gold": 1, "hit": 1, "all": True}
    assert mod.coverage(["t7"], []) == {"gold": 1, "hit": 0, "all": False}


def test_arm_key_is_stable_and_readable():
    mod = _load()
    assert mod.arm_key("focused_window", 30, 8000) == "focused_window|k30|b8000"


# ---------------------------- 汇总与选臂规则 ----------------------------

def test_summarize_groups_by_arm_and_query_type_with_the_primary_subset():
    mod = _load()
    rows = [_row("A", "q1", "Q5", 2, 2, 1000), _row("A", "q2", "Q5", 2, 1, 3000, bound=True),
            _row("A", "q3", "Q2", 1, 1, 500), _row("A", "q4", "Q9", 1, 1, 700),
            _row("B", "q1", "Q5", 2, 0, 200)]
    s = mod.summarize(rows)
    assert s["A"]["Q5"] == {"n": 2, "all_gold": 1, "turns_hit": 3, "turns_total": 4,
                            "mean_bytes": 2000.0, "budget_bound": 1}
    assert s["A"]["Q2"]["all_gold"] == 1
    assert s["A"]["Q5+Q9"]["n"] == 3 and s["A"]["Q5+Q9"]["all_gold"] == 2
    assert s["A"]["ALL"]["n"] == 4 and s["A"]["ALL"]["all_gold"] == 3
    assert s["B"]["Q5"]["turns_hit"] == 0 and "Q2" not in s["B"]


def _arm(primary, q2, q4, q6, mean_bytes=1000.0):
    return {"Q5+Q9": {"all_gold": primary}, "Q2": {"all_gold": q2}, "Q4": {"all_gold": q4},
            "Q6": {"all_gold": q6}, "ALL": {"mean_bytes": mean_bytes}}


def test_select_arm_needs_the_margin_and_a_held_guard():
    mod = _load()
    base = _arm(50, 30, 40, 10)
    summary = {"base": base, "gain": _arm(53, 30, 40, 10), "small": _arm(52, 30, 40, 10),
               "hurts_q6": _arm(60, 30, 40, 7)}
    assert mod.select_arm({"base": base, "small": summary["small"]}, "base") is None
    assert mod.select_arm({"base": base, "hurts_q6": summary["hurts_q6"]}, "base") is None
    assert mod.select_arm({"base": base, "gain": summary["gain"]}, "base") == "gain"
    tolerated = _arm(55, 28, 38, 8)             # 每类最多低 2 题仍算守住
    assert mod.select_arm({"base": base, "t": tolerated}, "base") == "t"
    assert mod.select_arm({"base": base, "t": _arm(55, 27, 40, 10)}, "base") is None


def test_select_arm_prefers_more_coverage_then_fewer_bytes_then_key_order():
    mod = _load()
    base = _arm(50, 30, 40, 10)
    summary = {"base": base, "b": _arm(56, 30, 40, 10, 2000.0), "a": _arm(56, 30, 40, 10, 2000.0),
               "c": _arm(56, 30, 40, 10, 3000.0), "best": _arm(57, 30, 40, 10, 9000.0)}
    assert mod.select_arm(summary, "base") == "best"
    del summary["best"]
    assert mod.select_arm(summary, "base") == "a"
    summary["lean"] = _arm(56, 30, 40, 10, 1500.0)
    assert mod.select_arm(summary, "base") == "lean"


def test_select_arm_never_returns_the_baseline_and_needs_it_present():
    mod = _load()
    assert mod.select_arm({"base": _arm(50, 30, 40, 10)}, "base") is None
    with pytest.raises(ValueError, match="baseline"):
        mod.select_arm({"x": _arm(60, 30, 40, 10)}, "base")


# ---------------------------- 开发切分守卫 ----------------------------

def test_development_records_keep_only_aligned_types_in_development_networks():
    mod = _load()
    split = {"development_networks": ["n1"], "reserved_networks": ["n2"]}
    recs = [_rec("a", "Q5", ["t"]), _rec("b", "Q5", ["t"], source={"network_id": "n2"}),
            _rec("c", "Q1", ["t"]), _rec("d", "Q9", ["t"])]
    assert [r["item_id"] for r in mod.development_records(recs, split)] == ["a", "d"]


def test_development_records_reject_a_network_listed_in_both_splits():
    mod = _load()
    with pytest.raises(ValueError, match="split"):
        mod.development_records([_rec("a", "Q5", ["t"])],
                                {"development_networks": ["n1"], "reserved_networks": ["n1"]})


# ---------------------------- 原生回放 ----------------------------

def test_replay_question_finds_the_gold_turn_on_a_copy_and_leaves_the_library_alone(tmp_path):
    mod = _load()
    lib = _library(tmp_path)
    before = _events(lib)
    work = tmp_path / "work"
    out = mod.replay_question(_rec("q1", "Q5", ["s1_t2"]), lib, work, strategy="bm25", k=5,
                              max_context_bytes=8000, now_iso="2026-12-08T00:00:00Z")
    assert "s1_t2" in [r["turn_id"] for r in out["source_refs"]]
    assert out["context_bytes"] > 0 and out["source_count"] >= 1 and out["budget_bound"] is False
    assert _events(lib) == before
    assert not list(work.glob("*")) or not any(p.suffix == ".db" for p in work.iterdir())   # 副本用完即删


def test_run_matrix_emits_one_row_per_arm_and_question(tmp_path):
    mod = _load()
    lib = _library(tmp_path)
    arms = [("bm25", 5, 8000), ("focused_window", 5, 8000)]
    rows = mod.run_matrix([_rec("q1", "Q5", ["s1_t2"])], lambda r: lib, arms, tmp_path / "work",
                          now_iso="2026-12-08T00:00:00Z")
    assert [r["arm"] for r in rows] == ["bm25|k5|b8000", "focused_window|k5|b8000"]
    assert all(r["item_id"] == "q1" and r["query_type"] == "Q5" and r["gold"] == 1
               and r["hit"] == 1 and r["all"] is True for r in rows)


# ---------------------------- WP1.B 金标参照臂 ----------------------------

def _need(mod, name):
    fn = getattr(mod, name, None)
    if fn is None:
        pytest.fail(f"scripts/eval_socialmem_source_matrix.py 尚无 {name}(功能缺失)")
    return fn


def _pool(sessions=((1, 6), (2, 3)), size=100):
    refs, sizes = [], []
    for session, count in sessions:
        for idx in range(1, count + 1):
            refs.append({"turn_id": f"s{session}_t{idx}", "session_id": str(session), "turn_index": idx})
            sizes.append(size)
    return refs, sizes


def test_oracle_ids_without_context_are_exactly_the_gold_positions():
    fn = _need(_load(), "oracle_selection_ids")
    refs, sizes = _pool()
    assert fn(refs, sizes, ["s1_t4", "s1_t2"], radius=0, k=20, max_bytes=8000) == [2, 4]


def test_oracle_ids_add_same_session_neighbours_only():
    fn = _need(_load(), "oracle_selection_ids")
    refs, sizes = _pool()
    assert fn(refs, sizes, ["s1_t3"], radius=1, k=20, max_bytes=8000) == [2, 3, 4]
    assert fn(refs, sizes, ["s1_t1"], radius=1, k=20, max_bytes=8000) == [1, 2]
    assert fn(refs, sizes, ["s2_t1"], radius=2, k=20, max_bytes=8000) == [7, 8, 9]


def test_oracle_neighbours_fill_by_distance_then_pool_order_until_k():
    fn = _need(_load(), "oracle_selection_ids")
    refs, sizes = _pool()
    assert fn(refs, sizes, ["s1_t3"], radius=2, k=3, max_bytes=8000) == [2, 3, 4]
    assert fn(refs, sizes, ["s1_t3"], radius=2, k=4, max_bytes=8000) == [1, 2, 3, 4]


def test_oracle_neighbours_respect_the_byte_budget():
    fn = _need(_load(), "oracle_selection_ids")
    refs, sizes = _pool()
    assert fn(refs, sizes, ["s1_t3"], radius=2, k=20, max_bytes=305) == [2, 3, 4]    # 三行 302 字节,四行 403


def test_oracle_neighbour_that_does_not_fit_is_skipped_not_fatal():
    fn = _need(_load(), "oracle_selection_ids")
    refs, sizes = _pool()
    sizes[0] = 8000
    assert fn(refs, sizes, ["s1_t3"], radius=2, k=20, max_bytes=8000) == [2, 3, 4, 5]


def test_oracle_gold_that_cannot_fit_or_is_missing_is_an_error():
    fn = _need(_load(), "oracle_selection_ids")
    refs, sizes = _pool()
    with pytest.raises(ValueError, match="gold"):
        fn(refs, sizes, ["s1_t1", "s1_t2", "s1_t3"], radius=0, k=2, max_bytes=8000)
    with pytest.raises(ValueError, match="gold"):
        fn(refs, sizes, ["s1_t1", "s1_t2"], radius=0, k=20, max_bytes=150)
    with pytest.raises(ValueError, match="gold"):
        fn(refs, sizes, ["nope"], radius=0, k=20, max_bytes=8000)
    with pytest.raises(ValueError, match="gold"):
        fn(refs, sizes, [], radius=0, k=20, max_bytes=8000)


def test_oracle_turns_without_a_session_or_index_get_no_neighbours():
    fn = _need(_load(), "oracle_selection_ids")
    refs, sizes = _pool()
    refs[2] = {"turn_id": "x", "session_id": None, "turn_index": None}
    assert fn(refs, sizes, ["x"], radius=2, k=20, max_bytes=8000) == [3]


def test_oracle_question_renders_only_the_gold_turn_and_leaves_the_library_alone(tmp_path):
    fn = _need(_load(), "oracle_question")
    lib = _library(tmp_path)
    before = _events(lib)
    work = tmp_path / "work"
    out = fn(_rec("q1", "Q5", ["s1_t2"]), lib, work, radius=0, now_iso="2026-12-08T00:00:00Z")
    assert [r["turn_id"] for r in out["source_refs"]] == ["s1_t2"]
    assert out["source_count"] == 1 and out["context_bytes"] == len(out["block"].encode("utf-8"))
    assert _events(lib) == before
    assert list(work.glob("*")) == []                                   # 副本用完即删


def test_oracle_question_with_context_adds_the_neighbouring_turn(tmp_path):
    fn = _need(_load(), "oracle_question")
    lib = _library(tmp_path)
    out = fn(_rec("q1", "Q5", ["s1_t2"]), lib, tmp_path / "work", radius=1, now_iso="2026-12-08T00:00:00Z")
    assert [r["turn_id"] for r in out["source_refs"]] == ["s1_t2", "s1_t3"]


def test_oracle_question_rejects_gold_outside_the_pool(tmp_path):
    fn = _need(_load(), "oracle_question")
    lib = _library(tmp_path)
    with pytest.raises(ValueError, match="gold"):
        fn(_rec("q1", "Q5", ["nope"]), lib, tmp_path / "work", radius=0, now_iso="2026-12-08T00:00:00Z")


# ---------------------------- WP1.D 扩展网格 ----------------------------

def test_extended_grid_adds_larger_k_and_a_smaller_byte_set():
    mod = _load()
    arms = _need(mod, "extended_arms")()
    assert len(arms) == len(set(arms)) == 43
    assert mod.BASELINE in arms
    extra = [a for a in arms if a != mod.BASELINE]
    assert {k for _, k, _ in extra} == {40, 50, 60}
    assert {b for _, _, b in extra} == {8000, 16000}
    assert {s for s, _, _ in arms} == set(mod.STRATEGIES)


def test_full_grid_is_unchanged_by_the_extended_grid():
    """防线:WP1.A 的 42 臂网格实现前后相同。"""
    mod = _load()
    assert len(mod.full_arms()) == 42 and mod.BASELINE in mod.full_arms()


def test_arms_for_grid_dispatches_and_rejects_unknown_names():
    mod = _load()
    fn = _need(mod, "arms_for_grid")
    assert fn("full") == mod.full_arms()
    assert fn("extended") == _need(mod, "extended_arms")()
    with pytest.raises(ValueError, match="grid"):
        fn("nope")


def test_summarize_adds_the_q2_q6_group_only_when_those_types_are_present():
    mod = _load()
    rows = [_row("A", "q1", "Q2", 1, 1), _row("A", "q2", "Q6", 2, 1), _row("A", "q3", "Q4", 1, 1),
            _row("B", "q4", "Q5", 1, 1)]
    s = mod.summarize(rows)
    assert s["A"]["Q2+Q6"]["n"] == 2 and s["A"]["Q2+Q6"]["all_gold"] == 1
    assert "Q2+Q6" not in s["B"]


def _gap_arm(gap, q4, q5q9, mean_bytes):
    return {"Q2+Q6": {"all_gold": gap}, "Q4": {"all_gold": q4}, "Q5+Q9": {"all_gold": q5q9},
            "ALL": {"mean_bytes": mean_bytes}}


def test_gap_arm_selection_needs_the_ten_question_margin():
    mod = _load()
    fn = _need(mod, "select_gap_arm")
    base = _gap_arm(38, 41, 59, 7000.0)
    assert fn({"base": base, "x": _gap_arm(47, 41, 59, 9000.0)}, "base") is None
    assert fn({"base": base, "x": _gap_arm(48, 41, 59, 9000.0)}, "base") == "x"


def test_gap_arm_selection_holds_both_guards():
    mod = _load()
    fn = _need(mod, "select_gap_arm")
    base = _gap_arm(38, 41, 59, 7000.0)
    assert fn({"base": base, "x": _gap_arm(50, 38, 59, 9000.0)}, "base") is None      # Q4 低于基线减 2
    assert fn({"base": base, "x": _gap_arm(50, 39, 59, 9000.0)}, "base") == "x"
    assert fn({"base": base, "x": _gap_arm(50, 41, 55, 9000.0)}, "base") is None      # Q5+Q9 低于基线减 3
    assert fn({"base": base, "x": _gap_arm(50, 41, 56, 9000.0)}, "base") == "x"


def test_gap_arm_selection_enforces_the_context_byte_ceiling():
    mod = _load()
    fn = _need(mod, "select_gap_arm")
    base = _gap_arm(38, 41, 59, 7000.0)
    assert fn({"base": base, "x": _gap_arm(60, 41, 59, 12000.0)}, "base") == "x"
    assert fn({"base": base, "x": _gap_arm(60, 41, 59, 12001.0)}, "base") is None


def test_gap_arm_selection_ties_break_by_coverage_then_bytes_then_name():
    mod = _load()
    fn = _need(mod, "select_gap_arm")
    base = _gap_arm(38, 41, 59, 7000.0)
    summary = {"base": base, "b": _gap_arm(52, 41, 59, 9000.0), "a": _gap_arm(52, 41, 59, 9000.0),
               "c": _gap_arm(52, 41, 59, 10000.0), "best": _gap_arm(53, 41, 59, 11900.0)}
    assert fn(summary, "base") == "best"
    del summary["best"]
    assert fn(summary, "base") == "a"
    summary["lean"] = _gap_arm(52, 41, 59, 8000.0)
    assert fn(summary, "base") == "lean"


def test_gap_arm_selection_never_returns_the_baseline_and_needs_it_present():
    mod = _load()
    fn = _need(mod, "select_gap_arm")
    assert fn({"base": _gap_arm(38, 41, 59, 7000.0)}, "base") is None
    with pytest.raises(ValueError, match="baseline"):
        fn({"x": _gap_arm(60, 41, 59, 9000.0)}, "base")


def test_reference_agreement_counts_identical_blocks_for_one_arm():
    mod = _load()
    fn = _need(mod, "reference_agreement")
    rows = [{"arm": "X", "item_id": "a", "block_sha256": "h1"}, {"arm": "X", "item_id": "b", "block_sha256": "h2"},
            {"arm": "Y", "item_id": "a", "block_sha256": "zz"}]
    ref = [{"arm": "X", "item_id": "a", "block_sha256": "h1"}, {"arm": "X", "item_id": "b", "block_sha256": "DIFF"}]
    assert fn(rows, ref, "X") == {"equal": 1, "of": 2}
    assert fn(rows, [], "X") == {"equal": 0, "of": 2}
    assert fn(rows, ref, "missing") == {"equal": 0, "of": 0}
