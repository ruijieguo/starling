"""开发切分里 WP3 之外的 226 题(Q2 Q4 Q5 Q6 Q9)的来源路径臂(阶段二 B)的离线测试。无网络、无模型。
登记见 build/prereg_stage2_dev226.md。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))


def _load():
    path = _SCRIPTS / "eval_socialmem_stage2_dev226.py"
    if not path.exists():
        pytest.fail("scripts/eval_socialmem_stage2_dev226.py 尚不存在(功能缺失)")
    spec = importlib.util.spec_from_file_location("eval_socialmem_stage2_dev226", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rec(item, qt, net, fmt="multiple_choice"):
    return {"item_id": item, "query_type": qt, "answer_format": fmt, "source": {"network_id": net}}


def _mc(ok):
    return {"score": 1.0 if ok else 0.0, "ok": ok, "judge_status": None}


def _open(score, status="ok"):
    return {"score": score, "ok": score >= 0.7, "judge_status": status}


def test_arm_label_and_setting_are_fixed():
    mod = _load()
    assert mod.ARM == "stage2_src_v9"
    assert mod.arm_spec() == {"mode": "sources", "strategy": "evidence_profile_v9", "k": 30, "max_context_bytes": 24000}
    assert mod.STAGE2_TYPES == ("Q2", "Q4", "Q5", "Q6", "Q9")
    assert mod.DEV_TYPES == ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9")
    assert mod.DEFAULT_MATRIX_ARM == "evidence_profile_v9|k30|b24000"


def test_reference_from_matrix_keeps_one_arm_sorted_by_question():
    mod = _load()
    rows = [{"arm": "A", "item_id": "b", "turn_ids": ["t2", "t3"]},
            {"arm": "A", "item_id": "a", "turn_ids": ["t1"]},
            {"arm": "B", "item_id": "a", "turn_ids": ["x"]}]
    assert mod.reference_from_matrix(rows, "A") == {
        "rows": [{"item_id": "a", "turn_ids": ["t1"]}, {"item_id": "b", "turn_ids": ["t2", "t3"]}]}
    with pytest.raises(ValueError):
        mod.reference_from_matrix(rows + [{"arm": "A", "item_id": "a", "turn_ids": ["t9"]}], "A")
    with pytest.raises(ValueError):
        mod.reference_from_matrix(rows, "C")


def test_report_splits_by_type_and_official_category_and_excludes_bad_judge_rows():
    mod = _load()
    recs = [_rec("a", "Q2", "n1"), _rec("b", "Q2", "n1", "long_form"), _rec("c", "Q4", "n2"),
            _rec("d", "Q5", "n2", "long_form"), _rec("e", "Q6", "n3"), _rec("f", "Q9", "n3", "long_form"),
            _rec("g", "Q5", "n3", "long_form")]
    rows = {"a": _mc(True), "b": _open(0.8), "c": _mc(False), "d": _open(0.5, "parse_failed"),
            "e": _mc(True), "f": _open(0.9)}
    rep = mod.build_report(recs, rows, seed=1, draws=200)
    assert rep["arm"] == "stage2_src_v9" and rep["questions"] == 7 and rep["answered"] == 6
    assert rep["missing"] == ["g"] and rep["excluded"] == ["d"] and rep["complete"] is False
    assert rep["bootstrap"] == {"seed": 1, "draws": 200}
    bt = rep["by_type"]
    assert list(bt) == ["Q2", "Q4", "Q5", "Q6", "Q9"]
    assert bt["Q2"]["n"] == 2 and bt["Q2"]["mean_score"] == pytest.approx(0.9) and bt["Q2"]["ge07"] == 2
    assert bt["Q4"]["n"] == 1 and bt["Q4"]["mean_score"] == pytest.approx(0.0) and bt["Q4"]["ge07"] == 0
    assert bt["Q5"]["n"] == 0 and bt["Q5"]["mean_score"] is None
    assert bt["Q6"]["n"] == 1 and bt["Q9"]["mean_score"] == pytest.approx(0.9)
    cat = rep["by_category"]
    assert cat["multiple_choice"]["n"] == 3 and cat["multiple_choice"]["mean_score"] == pytest.approx(2 / 3)
    assert cat["multiple_choice"]["ge07"] == 2
    assert cat["open_ended"]["n"] == 2 and cat["open_ended"]["mean_score"] == pytest.approx(0.85)
    ov = rep["overall"]
    assert ov["n"] == 5 and ov["mean_score"] == pytest.approx(0.74) and ov["ge07"] == 4 and ov["networks"] == 3
    assert ov["lo"] <= ov["mean_score"] <= ov["hi"]


def test_report_ignores_records_outside_the_requested_types():
    mod = _load()
    recs = [_rec("a", "Q2", "n1"), _rec("z", "Q1", "n1", "long_form")]
    rep = mod.build_report(recs, {"a": _mc(True)}, seed=1, draws=50)
    assert rep["questions"] == 1 and rep["missing"] == [] and rep["complete"] is True


def test_merge_rows_refuses_questions_present_in_both_journals():
    mod = _load()
    a, b = {"x": _mc(True)}, {"y": _mc(False)}
    assert mod.merge_rows(a, b) == {"x": a["x"], "y": b["y"]}
    with pytest.raises(ValueError):
        mod.merge_rows(a, {"x": _mc(False)})


def test_report_can_cover_the_whole_development_split_under_its_own_label():
    mod = _load()
    recs = [_rec("a", "Q1", "n1", "long_form"), _rec("b", "Q4", "n2")]
    rep = mod.build_report(recs, {"a": _open(0.6), "b": _mc(True)}, seed=1, draws=100,
                           types=mod.DEV_TYPES, arm="dev_split")
    assert rep["arm"] == "dev_split" and list(rep["by_type"]) == list(mod.DEV_TYPES)
    assert rep["by_type"]["Q1"]["n"] == 1 and rep["by_type"]["Q1"]["ge07"] == 0
    assert rep["by_type"]["Q7"]["n"] == 0
    assert rep["by_category"]["multiple_choice"]["n"] == 1 and rep["by_category"]["open_ended"]["n"] == 1
    assert rep["complete"] is True


def _args(tmp_path, cmd, *extra):
    return [cmd, "--out", str(tmp_path / "o"), "--corpus", str(tmp_path / "c.jsonl"), *extra]


def test_main_refuses_to_answer_without_real_run_and_touches_nothing(tmp_path, capsys):
    mod = _load()
    code = mod.main(_args(tmp_path, "answer", "--prompts", str(tmp_path / "p.yaml"), "--prompts-sha256", "0" * 64))
    assert code == 1
    assert "--real-run" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()


def test_main_answer_refuses_without_a_passing_precheck(tmp_path, capsys):
    mod = _load()
    (tmp_path / "c.jsonl").write_text(json.dumps(_rec("a", "Q2", "n1")) + "\n", encoding="utf-8")
    (tmp_path / "o").mkdir()
    code = mod.main(_args(tmp_path, "answer", "--prompts", str(tmp_path / "p.yaml"), "--prompts-sha256", "0" * 64,
                          "--real-run"))
    assert code == 1
    assert "precheck" in capsys.readouterr().err
    assert not (tmp_path / "o" / f"{mod.ARM}_journal.jsonl").exists()


def test_main_report_writes_the_stage2_report_and_adds_the_dev_split_when_given_the_wp3_journal(tmp_path, capsys):
    mod = _load()
    recs = [_rec("a", "Q2", "n1"), _rec("b", "Q5", "n2", "long_form")]
    (tmp_path / "c.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    (tmp_path / "w.jsonl").write_text(json.dumps(_rec("w", "Q1", "n1", "long_form")) + "\n", encoding="utf-8")
    out = tmp_path / "o"
    out.mkdir()
    rows = [{"key": f"{mod.ARM}|a", "arm": mod.ARM, "item_id": "a", "ok": True, "score": 1.0, "judge_status": None},
            {"key": f"{mod.ARM}|b", "arm": mod.ARM, "item_id": "b", "ok": False, "score": 0.3, "judge_status": "ok"}]
    (out / f"{mod.ARM}_journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    wj = tmp_path / "wj.jsonl"
    wj.write_text(json.dumps({"key": "wp3_src_v9|w", "arm": "wp3_src_v9", "item_id": "w", "ok": True,
                              "score": 0.9, "judge_status": "ok"}) + "\n", encoding="utf-8")
    (out / f"manifest_{mod.ARM}.json").write_text(json.dumps(_manifest_for(mod.ARM)), encoding="utf-8")
    (tmp_path / "manifest_wp3_src_v9.json").write_text(json.dumps(_manifest_for("wp3_src_v9")), encoding="utf-8")
    result = tmp_path / "res.json"
    assert mod.main(_args(tmp_path, "report", "--result", str(result))) == 0
    only = json.loads(capsys.readouterr().out)
    assert only["stage2"]["overall"]["n"] == 2 and "dev_split" not in only
    assert mod.main(_args(tmp_path, "report", "--wp3-journal", str(wj))) == 1
    assert "wp3-corpus" in capsys.readouterr().err
    assert mod.main(_args(tmp_path, "report", "--wp3-corpus", str(tmp_path / "w.jsonl"), "--wp3-journal", str(wj),
                          "--result", str(result))) == 0
    both = json.loads(capsys.readouterr().out)
    assert both["dev_split"]["arm"] == "dev_split" and both["dev_split"]["overall"]["n"] == 3
    assert json.loads(result.read_text(encoding="utf-8")) == both


def test_main_reference_writes_the_reference_for_one_matrix_arm(tmp_path):
    mod = _load()
    rows = [{"arm": "A", "item_id": "a", "turn_ids": ["t1"]}, {"arm": "B", "item_id": "a", "turn_ids": ["x"]}]
    src = tmp_path / "rows.jsonl"
    src.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    dst = tmp_path / "ref.json"
    assert mod.main(["reference", "--matrix-rows", str(src), "--arm", "A", "--result", str(dst)]) == 0
    assert json.loads(dst.read_text(encoding="utf-8")) == {"rows": [{"item_id": "a", "turn_ids": ["t1"]}]}
    assert mod.main(["reference", "--matrix-rows", str(src), "--arm", "Z", "--result", str(dst)]) == 1


def test_driver_source_names_no_model_provider_endpoint_or_key_variable():
    path = _SCRIPTS / "eval_socialmem_stage2_dev226.py"
    if not path.exists():
        pytest.fail("scripts/eval_socialmem_stage2_dev226.py 尚不存在(功能缺失)")
    source = path.read_text(encoding="utf-8").lower()
    for forbidden in ("qwen", "deepseek", "doubao", "gpt-", "dashscope", "tokenkey", "api_key=", "sk-"):
        assert forbidden not in source, forbidden


# ---------------------------- 报告范围与合并守卫(阶段二最终读数前的加固) ----------------------------

def _jrow(arm, item, score, status="ok"):
    return {"key": f"{arm}|{item}", "arm": arm, "item_id": item, "ok": score >= 0.7, "score": score,
            "judge_status": status}


def _manifest_for(arm, **over):
    base = {"arm": arm, "spec": {"mode": "sources", "k": 30}, "core_sha256": "c", "prompts_sha256": "p",
            "backbone": "b", "judge_model": "j", "now_iso": "t", "profiles_sha256": "p1"}
    return {**base, **over}


def _report_dir(tmp_path, mod, recs, rows):
    (tmp_path / "c.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    out = tmp_path / "o"
    out.mkdir()
    (out / f"{mod.ARM}_journal.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return out


def test_merge_settings_problem_requires_identical_settings_and_present_manifests():
    mod = _load()
    m = _manifest_for("x")
    assert mod.merge_settings_problem([m, dict(m, profiles_sha256="p2", arm="y")]) is None
    assert "core_sha256" in mod.merge_settings_problem([m, dict(m, core_sha256="d")])
    assert "spec" in mod.merge_settings_problem([m, dict(m, spec={"mode": "sources", "k": 45})])
    assert "manifest" in mod.merge_settings_problem([m, None])
    assert "manifest" in mod.merge_settings_problem([])


def test_main_report_refuses_to_drop_questions_whose_type_is_not_in_types(tmp_path, capsys):
    mod = _load()
    recs = [_rec("a", "Q2", "n1"), _rec("b", "Q7", "n2", "short_answer")]
    _report_dir(tmp_path, mod, recs, [_jrow(mod.ARM, "a", 1.0)])
    assert mod.main(_args(tmp_path, "report")) == 1
    err = capsys.readouterr().err
    assert "--types" in err and "Q7" in err
    assert mod.main(_args(tmp_path, "report", "--types", "Q2,Q10")) == 1
    assert "Q10" in capsys.readouterr().err
    assert mod.main(_args(tmp_path, "report", "--types", "Q2,Q7")) == 0
    rep = json.loads(capsys.readouterr().out)["stage2"]
    assert list(rep["by_type"]) == ["Q2", "Q7"] and rep["questions"] == 2
    assert rep["missing"] == ["b"] and rep["by_type"]["Q2"]["n"] == 1


def test_main_report_also_merges_other_journals_only_when_settings_match(tmp_path, capsys):
    mod = _load()
    out = _report_dir(tmp_path, mod, [_rec("a", "Q2", "n1")], [_jrow(mod.ARM, "a", 1.0)])
    (out / f"manifest_{mod.ARM}.json").write_text(json.dumps(_manifest_for(mod.ARM)), encoding="utf-8")
    other = tmp_path / "x"
    other.mkdir()
    (tmp_path / "xc.jsonl").write_text(json.dumps(_rec("w", "Q1", "n1", "long_form")) + "\n", encoding="utf-8")
    journal = other / "wp3_src_v9_journal.jsonl"
    journal.write_text(json.dumps(_jrow("wp3_src_v9", "w", 0.5)) + "\n", encoding="utf-8")
    also = ["--also", str(tmp_path / "xc.jsonl"), str(journal), "wp3_src_v9", "--merged-label", "all_test"]
    assert mod.main(_args(tmp_path, "report", *also)) == 1            # 另一份 journal 旁边没有 manifest
    assert "manifest" in capsys.readouterr().err
    manifest = other / "manifest_wp3_src_v9.json"
    manifest.write_text(json.dumps(_manifest_for("wp3_src_v9", profiles_sha256="p2")), encoding="utf-8")
    assert mod.main(_args(tmp_path, "report", *also)) == 0            # 只有 profiles 文件哈希不同,不算设置不同
    merged = json.loads(capsys.readouterr().out)["merged"]
    assert merged["arm"] == "all_test" and merged["overall"]["n"] == 2 and merged["by_type"]["Q1"]["n"] == 1
    manifest.write_text(json.dumps(_manifest_for("wp3_src_v9", core_sha256="other")), encoding="utf-8")
    assert mod.main(_args(tmp_path, "report", *also)) == 1            # 核心不同,拒绝合并
    assert "core_sha256" in capsys.readouterr().err


def test_main_report_wp3_journal_merge_also_requires_matching_manifests(tmp_path, capsys):
    mod = _load()
    _report_dir(tmp_path, mod, [_rec("a", "Q2", "n1")], [_jrow(mod.ARM, "a", 1.0)])
    (tmp_path / "w.jsonl").write_text(json.dumps(_rec("w", "Q1", "n1", "long_form")) + "\n", encoding="utf-8")
    wj = tmp_path / "wj.jsonl"
    wj.write_text(json.dumps(_jrow("wp3_src_v9", "w", 0.9)) + "\n", encoding="utf-8")
    assert mod.main(_args(tmp_path, "report", "--wp3-corpus", str(tmp_path / "w.jsonl"), "--wp3-journal", str(wj))) == 1
    assert "manifest" in capsys.readouterr().err


def test_main_report_refuses_questions_present_in_two_corpora(tmp_path, capsys):
    mod = _load()
    out = _report_dir(tmp_path, mod, [_rec("a", "Q2", "n1")], [_jrow(mod.ARM, "a", 1.0)])
    (out / f"manifest_{mod.ARM}.json").write_text(json.dumps(_manifest_for(mod.ARM)), encoding="utf-8")
    other = tmp_path / "x"
    other.mkdir()
    (tmp_path / "xc.jsonl").write_text(json.dumps(_rec("a", "Q1", "n1", "long_form")) + "\n", encoding="utf-8")
    journal = other / "wp3_src_v9_journal.jsonl"
    journal.write_text(json.dumps(_jrow("wp3_src_v9", "z", 0.5)) + "\n", encoding="utf-8")
    (other / "manifest_wp3_src_v9.json").write_text(json.dumps(_manifest_for("wp3_src_v9")), encoding="utf-8")
    assert mod.main(_args(tmp_path, "report", "--also", str(tmp_path / "xc.jsonl"), str(journal), "wp3_src_v9")) == 1
    assert "多份语料" in capsys.readouterr().err


def _extra_arm(tmp_path, name, arm, item, qt, score):
    """造一份额外的语料、journal 与 manifest,返回 --also 的三个参数。"""
    folder = tmp_path / name
    folder.mkdir()
    (tmp_path / f"{name}.jsonl").write_text(json.dumps(_rec(item, qt, "n1", "long_form")) + "\n", encoding="utf-8")
    (folder / f"{arm}_journal.jsonl").write_text(json.dumps(_jrow(arm, item, score)) + "\n", encoding="utf-8")
    (folder / f"manifest_{arm}.json").write_text(json.dumps(_manifest_for(arm)), encoding="utf-8")
    return ["--also", str(tmp_path / f"{name}.jsonl"), str(folder / f"{arm}_journal.jsonl"), arm]


def test_main_report_also_is_repeatable_and_refuses_overlap_between_the_extras(tmp_path, capsys):
    """可重复合并(三份并成一份读数)是保留切分复测要用的形状;这条用例在实现之后补,是对既有行为的锁定,不是先红后绿。"""
    mod = _load()
    out = _report_dir(tmp_path, mod, [_rec("a", "Q2", "n1")], [_jrow(mod.ARM, "a", 1.0)])
    (out / f"manifest_{mod.ARM}.json").write_text(json.dumps(_manifest_for(mod.ARM)), encoding="utf-8")
    three = _extra_arm(tmp_path, "x", "armx", "w", "Q1", 0.5) + _extra_arm(tmp_path, "y", "army", "v", "Q8", 0.9)
    assert mod.main(_args(tmp_path, "report", *three, "--merged-label", "three")) == 0
    merged = json.loads(capsys.readouterr().out)["merged"]
    assert merged["arm"] == "three" and merged["overall"]["n"] == 3
    assert merged["by_type"]["Q1"]["n"] == 1 and merged["by_type"]["Q8"]["n"] == 1 and merged["by_type"]["Q2"]["n"] == 1
    clash = _extra_arm(tmp_path, "p", "armp", "w", "Q1", 0.5) + _extra_arm(tmp_path, "q", "armq", "w", "Q8", 0.9)
    assert mod.main(_args(tmp_path, "report", *clash)) == 1
    assert "多份语料" in capsys.readouterr().err
