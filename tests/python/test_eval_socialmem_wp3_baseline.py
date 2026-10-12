"""WP3 来源路径基线(开发切分 Q1 Q3 Q7 Q8,不建库)的离线测试。无网络、无模型。
登记见 build/prereg_wp3_source_baseline.md。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))


def _load():
    path = _SCRIPTS / "eval_socialmem_wp3_baseline.py"
    if not path.exists():
        pytest.fail("scripts/eval_socialmem_wp3_baseline.py 尚不存在(功能缺失)")
    spec = importlib.util.spec_from_file_location("eval_socialmem_wp3_baseline", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rec(item, qt, net, fmt="long_form"):
    return {"item_id": item, "query_type": qt, "answer_format": fmt, "source": {"network_id": net}}


def _row(score, status="ok"):
    return {"score": score, "ok": score >= 0.7, "judge_status": status}


def test_arm_is_the_wp2b_control_setting_and_only_this_arm_exists():
    mod = _load()
    assert mod.ARM == "wp3_src_v9"
    assert mod.arm_spec() == {"mode": "sources", "strategy": "evidence_profile_v9", "k": 30, "max_context_bytes": 24000}
    assert mod.WP3_TYPES == ("Q1", "Q3", "Q7", "Q8")


def test_replay_gate_requires_every_turn_sequence_to_match_the_reference():
    mod = _load()
    ref = {"rows": [{"item_id": "a", "turn_ids": ["t1", "t2"]}, {"item_id": "b", "turn_ids": ["t3"]}]}
    rows = [{"item_id": "a", "turn_ids": ["t1", "t2"]}, {"item_id": "b", "turn_ids": ["t3"]}]
    assert mod.replay_gate(rows, ref) == {"equal": 2, "of": 2, "ready": True, "differing": []}
    rows[1]["turn_ids"] = ["t9"]
    gate = mod.replay_gate(rows, ref)
    assert gate == {"equal": 1, "of": 2, "ready": False, "differing": ["b"]}
    assert mod.replay_gate([], ref)["ready"] is False
    assert mod.replay_gate(rows[:1], ref)["ready"] is False      # 少题也不放行


def test_report_gives_per_type_and_overall_descriptives_and_excludes_bad_judge_statuses():
    mod = _load()
    recs = [_rec("a", "Q1", "n1"), _rec("b", "Q1", "n2"), _rec("c", "Q7", "n1", "short_answer"),
            _rec("d", "Q8", "n3"), _rec("e", "Q3", "n2"), _rec("f", "Q8", "n3")]
    rows = {"a": _row(1.0), "b": _row(0.5), "c": _row(0.8), "d": _row(0.0, "parse_failed"), "e": _row(0.7)}
    rep = mod.build_report(recs, rows, seed=1, draws=200)
    assert rep["arm"] == "wp3_src_v9"
    assert rep["answered"] == 5 and rep["missing"] == ["f"] and rep["excluded"] == ["d"]
    assert rep["by_type"]["Q1"]["n"] == 2 and rep["by_type"]["Q1"]["mean_score"] == pytest.approx(0.75)
    assert rep["by_type"]["Q1"]["ge07"] == 1 and rep["by_type"]["Q1"]["networks"] == 2
    assert rep["by_type"]["Q7"] == dict(n=1, mean_score=pytest.approx(0.8), ge07=1, networks=1, lo=pytest.approx(0.8), hi=pytest.approx(0.8))
    assert rep["by_type"]["Q8"]["n"] == 0 and rep["by_type"]["Q8"]["mean_score"] is None
    assert rep["by_type"]["Q3"]["n"] == 1
    assert rep["overall"]["n"] == 4 and rep["overall"]["mean_score"] == pytest.approx((1.0 + 0.5 + 0.8 + 0.7) / 4)
    assert rep["overall"]["ge07"] == 3 and rep["overall"]["networks"] == 2
    assert rep["overall"]["lo"] <= rep["overall"]["mean_score"] <= rep["overall"]["hi"]
    assert rep["complete"] is False
    assert rep["bootstrap"] == {"seed": 1, "draws": 200}


def test_report_is_complete_only_when_every_question_has_a_usable_row():
    mod = _load()
    recs = [_rec("a", "Q1", "n1"), _rec("b", "Q7", "n2", "short_answer")]
    rep = mod.build_report(recs, {"a": _row(1.0), "b": _row(0.2)}, seed=1, draws=50)
    assert rep["complete"] is True and rep["missing"] == [] and rep["excluded"] == []
    assert rep["overall"]["n"] == 2 and rep["overall"]["ge07"] == 1


def test_network_bootstrap_interval_uses_whole_networks():
    mod = _load()
    out = mod.network_bootstrap([("n1", 1.0)] * 3 + [("n2", 0.0)], seed=7, draws=2000)
    assert out["mean"] == pytest.approx(0.75)
    assert out["lo"] == pytest.approx(0.0) and out["hi"] == pytest.approx(1.0)
    assert out["networks"] == 2


def _args(tmp_path, cmd, *extra):
    return [cmd, "--out", str(tmp_path / "o"), "--corpus", str(tmp_path / "c.jsonl"), *extra]


def test_main_refuses_to_answer_without_real_run_and_touches_nothing(tmp_path, capsys):
    mod = _load()
    code = mod.main(_args(tmp_path, "answer", "--prompts", str(tmp_path / "p.yaml"), "--prompts-sha256", "0" * 64))
    assert code == 1
    assert "--real-run" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()


def test_main_answer_refuses_without_a_passing_precheck(tmp_path, capsys, monkeypatch):
    mod = _load()
    (tmp_path / "c.jsonl").write_text(json.dumps(_rec("a", "Q1", "n1")) + "\n", encoding="utf-8")
    (tmp_path / "o").mkdir()
    monkeypatch.setenv("WP3_TEST_KEY", "unit-test-value")
    code = mod.main(_args(tmp_path, "answer", "--prompts", str(tmp_path / "p.yaml"), "--prompts-sha256", "0" * 64,
                          "--real-run"))
    assert code == 1
    assert "precheck" in capsys.readouterr().err
    assert not (tmp_path / "o" / f"{mod.ARM}_journal.jsonl").exists()


def test_main_report_reads_the_journal_and_writes_the_result(tmp_path, capsys):
    mod = _load()
    recs = [_rec("a", "Q1", "n1"), _rec("b", "Q8", "n2")]
    (tmp_path / "c.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    out = tmp_path / "o"
    out.mkdir()
    rows = [{"key": f"{mod.ARM}|a", "arm": mod.ARM, "item_id": "a", "ok": True, "score": 0.9, "judge_status": "ok"},
            {"key": f"{mod.ARM}|b", "arm": mod.ARM, "item_id": "b", "ok": False, "score": 0.3, "judge_status": "ok"}]
    (out / f"{mod.ARM}_journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    result = tmp_path / "res.json"
    assert mod.main(_args(tmp_path, "report", "--result", str(result))) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["overall"]["n"] == 2 and printed["by_type"]["Q1"]["ge07"] == 1
    assert json.loads(result.read_text(encoding="utf-8")) == printed


def test_main_report_fails_loudly_without_a_journal(tmp_path, capsys):
    mod = _load()
    (tmp_path / "c.jsonl").write_text(json.dumps(_rec("a", "Q1", "n1")) + "\n", encoding="utf-8")
    (tmp_path / "o").mkdir()
    assert mod.main(_args(tmp_path, "report")) == 1
    assert "journal" in capsys.readouterr().err


def test_driver_source_names_no_model_provider_endpoint_or_key_variable():
    source = (_SCRIPTS / "eval_socialmem_wp3_baseline.py").read_text(encoding="utf-8").lower()
    for forbidden in ("qwen", "deepseek", "doubao", "gpt-", "dashscope", "tokenkey", "api_key=", "sk-"):
        assert forbidden not in source, forbidden
