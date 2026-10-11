"""WP2.B 登记修订五:附加声明侧栏零请求后处理(声明条数与配对差)的离线测试。无网络、无模型。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))


def _load():
    path = _SCRIPTS / "eval_socialmem_structured_sidecar_stats.py"
    if not path.exists():
        pytest.fail("scripts/eval_socialmem_structured_sidecar_stats.py 尚不存在(功能缺失)")
    spec = importlib.util.spec_from_file_location("eval_socialmem_structured_sidecar_stats", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rec(item, qt, fmt="multiple_choice"):
    return {"item_id": item, "query_type": qt, "answer_format": fmt, "source": {"network_id": "n1"}}


RECS = [_rec("a", "Q2"), _rec("b", "Q2"), _rec("c", "Q6"), _rec("d", "Q6"), _rec("e", "Q4"),
        _rec("f", "Q5", "long_form")]
HYB = {"a": (1.0, 0), "b": (1.0, 2), "c": (0.0, 0), "d": (0.0, 0), "e": (1.0, 1), "f": (0.75, 3)}
CTRL = {"a": 1.0, "b": 0.0, "c": 0.0, "d": 0.0, "e": 1.0, "f": 0.5}


def _row(item, score, statements=0, status=None, arm="st_hyb"):
    return {"item_id": item, "arm": arm, "score": score, "ok": score >= 0.7,
            "statement_count": statements, "judge_status": status}


def _arms(hyb_spec=None, ctrl_scores=None):
    hyb = {i: _row(i, s, n) for i, (s, n) in (hyb_spec or HYB).items()}
    ctrl = {i: _row(i, s, 0, arm="st_ctrl") for i, s in (ctrl_scores or CTRL).items()}
    return ctrl, hyb


def test_sidecar_counts_are_listed_by_query_type():
    mod = _load()
    ctrl, hyb = _arms()
    stats = mod.sidecar_stats(RECS, ctrl, hyb)
    assert stats["by_type"]["Q2"] == {"questions": 2, "with_statements": 1, "statements_total": 2}
    assert stats["by_type"]["Q6"] == {"questions": 2, "with_statements": 0, "statements_total": 0}
    assert stats["by_type"]["Q4"] == {"questions": 1, "with_statements": 1, "statements_total": 1}
    assert stats["by_type"]["Q5"] == {"questions": 1, "with_statements": 1, "statements_total": 3}


def test_a_sidecar_on_fewer_than_a_quarter_of_the_q2_q6_choice_questions_is_flagged_mostly_empty():
    mod = _load()
    ctrl, hyb = _arms()
    stats = mod.sidecar_stats(RECS, ctrl, hyb)
    # 4 道 Q2+Q6 选择题里 1 道有声明,恰好四分之一,不算「不到四分之一」
    assert stats["mc_q2q6"] == {"questions": 4, "with_statements": 1, "share": 0.25, "sidecar_mostly_empty": False}
    hyb["b"] = _row("b", 1.0, 0)
    stats = mod.sidecar_stats(RECS, ctrl, hyb)
    assert stats["mc_q2q6"]["with_statements"] == 0 and stats["mc_q2q6"]["sidecar_mostly_empty"] is True


def test_paired_differences_are_listed_only_on_questions_with_a_nonempty_sidecar():
    mod = _load()
    ctrl, hyb = _arms()
    paired = mod.sidecar_stats(RECS, ctrl, hyb)["paired"]
    assert paired["mc_q2q6"] == {"n": 1, "ctrl": 0.0, "hyb": 1.0, "delta": pytest.approx(1.0)}
    assert paired["mc_q4"] == {"n": 1, "ctrl": 1.0, "hyb": 1.0, "delta": pytest.approx(0.0)}
    assert paired["open_q5q9"] == {"n": 1, "ctrl": 0.5, "hyb": 0.75, "delta": pytest.approx(0.25)}


def test_questions_without_a_control_row_are_counted_but_not_paired():
    mod = _load()
    ctrl, hyb = _arms()
    del ctrl["b"]
    stats = mod.sidecar_stats(RECS, ctrl, hyb)
    assert stats["by_type"]["Q2"]["with_statements"] == 1
    assert stats["paired"]["mc_q2q6"] is None


def test_regex_fallback_open_scores_are_left_out_of_the_open_pairing():
    mod = _load()
    ctrl, hyb = _arms()
    ctrl["f"] = _row("f", 0.5, 0, status="regex_fallback", arm="st_ctrl")
    assert mod.sidecar_stats(RECS, ctrl, hyb)["paired"]["open_q5q9"] is None


def test_main_reads_both_journals_and_writes_the_result(tmp_path):
    mod = _load()
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text("\n".join(json.dumps(r) for r in RECS) + "\n", encoding="utf-8")
    ctrl, hyb = _arms()
    for name, rows in (("st_ctrl", ctrl), ("st_hyb", hyb)):
        (tmp_path / f"{name}_journal.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows.values()) + "\n", encoding="utf-8")
    result = tmp_path / "result.json"
    assert mod.main(["--out", str(tmp_path), "--corpus", str(corpus), "--result", str(result)]) == 0
    data = json.loads(result.read_text(encoding="utf-8"))
    assert data["mc_q2q6"]["with_statements"] == 1 and data["paired"]["open_q5q9"]["n"] == 1


def test_main_refuses_when_a_journal_is_missing(tmp_path, capsys):
    mod = _load()
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(json.dumps(RECS[0]) + "\n", encoding="utf-8")
    assert mod.main(["--out", str(tmp_path), "--corpus", str(corpus)]) == 1
    assert "st_hyb" in capsys.readouterr().err
