"""WP2.B:结构化声明合同库建库与受控对比的离线测试(无网络、无模型、不读真语料)。"""
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
NOW = "2026-12-08T00:00:00Z"

TURNS = [
    {"speaker": "Ada", "text": "Copper lantern in Kyoto.", "turn_id": "s1_t2", "session_id": "s1",
     "turn_index": 2, "observed_at": "2025-01-01T10:00:00Z"},
    {"speaker": "Bob", "text": "I prefer green tea.", "turn_id": "s1_t3", "session_id": "s1",
     "turn_index": 3, "observed_at": "2025-01-01T10:05:00Z"},
]


def _load(name="eval_socialmem_structured_build"):
    path = _SCRIPTS / f"{name}.py"
    if not path.exists():
        pytest.fail(f"scripts/{name}.py 尚不存在(功能缺失)")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hist(n, speakers):
    return [{"speaker": speakers[i % len(speakers)], "text": f"t{i}", "turn_id": f"t{i:03d}", "session_index": 1,
             "message_index": i + 1, "observed_at": "2025-01-01T10:00:00"} for i in range(n)]


def _q(item, net, n, speakers, qt="Q2", scope="all_history"):
    return {"item_id": item, "query_type": qt, "answer_format": "multiple_choice", "question": "q?",
            "options": ["a", "b", "c", "d"], "answer": 0, "history": _hist(n, speakers), "gold_statements": [],
            "evaluation_scope": scope, "source": {"network_id": net}}


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


# ---------------------------- 臂与配置 ----------------------------

def test_arm_specs_follow_the_registration():
    mod = _load()
    assert mod.ARMS == ("st_ctrl", "st_hyb", "st_hyb_cov")
    assert mod.arm_spec("st_ctrl") == {"mode": "sources", "strategy": "evidence_profile_v9", "k": 30,
                                       "max_context_bytes": 24000}
    assert mod.arm_spec("st_hyb") == {"mode": "hybrid", "strategy": "evidence_profile_v9", "k": 30,
                                      "max_context_bytes": 24000}
    assert mod.arm_spec("st_hyb_cov") == {"mode": "hybrid", "strategy": "focused_coverage", "k": 10,
                                          "max_context_bytes": 8000, "min_source_items": 7, "source_seed_k": 5,
                                          "source_seed_max_context_bytes": 4000, "source_dialogue_radius": 1}
    with pytest.raises(ValueError, match="arm"):
        mod.arm_spec("nope")


def test_control_and_main_arm_differ_only_in_mode():
    mod = _load()
    ctrl, hyb = mod.arm_spec("st_ctrl"), mod.arm_spec("st_hyb")
    assert {k: v for k, v in ctrl.items() if k != "mode"} == {k: v for k, v in hyb.items() if k != "mode"}
    assert ctrl["mode"] != hyb["mode"]
    assert mod.CONTROL_REFERENCE_ARM == "evidence_profile_v9|k30|b24000"


def test_build_config_is_the_registered_extraction_setup():
    mod = _load()
    cfg = mod.build_config()
    expected = {
        "extract_model": "qwen3.8-27b", "extract_provider": "dashscope", "extract_max_tokens": 8192,
        "extract_enable_thinking": False, "timeout_ms": 120000, "max_retries": 0,
        "claim_output_mode": "json_object", "claim_allow_code_fence": True, "claim_protocol_retry_budget": 1,
        "claim_batch_size": 8, "claim_batch_target_units": True, "holder_isolation": True,
        "semantic_claim_contract": True, "preserve_text_objects": True, "lifecycle": "sleep",
        "retain_sources": True, "preserve_invalid_time": True, "include_unknown_time": True,
        "embedding_model": "qwen3.7-text-embedding", "embedding_dim": 1024, "embedding_max_batch_inputs": 10,
        "created_at": "2026-06-01T00:00:00Z", "query_time": NOW}
    for key, value in expected.items():
        assert cfg[key] == value, key
    runner = _load("run_socialmem_baseline")
    policy = runner._build_extraction_config(cfg).to_native_policy()
    assert policy.semantic_claim_contract is True and policy.claim_batch_size == 8
    assert policy.claim_batch_target_units is True and policy.claim_protocol_retry_budget == 1


# ---------------------------- 分组与建库状态 ----------------------------

def test_plan_groups_orders_the_smallest_history_first_and_bounds_requests():
    mod = _load()
    recs = [_q("a", "n1", 40, ["A", "B", "C"]), _q("b", "n1", 40, ["A", "B", "C"]),
            _q("c", "n2", 10, ["A", "B"]), _q("d", "n3", 25, ["A", "B", "C", "D"])]
    plan = mod.plan_groups(recs)
    assert [g["turns"] for g in plan] == [10, 25, 40]
    assert [g["holders"] for g in plan] == [2, 4, 3]
    assert [g["request_upper_bound"] for g in plan] == [18, 36, 27]
    assert [len(g["records"]) for g in plan] == [1, 1, 2]
    assert {"group_id", "network_id", "evaluation_scope"} <= set(plan[0])


def test_scope_status_reads_the_archived_files(tmp_path):
    mod = _load()
    d = tmp_path / "s"
    assert mod.scope_status(d) == "pending"
    d.mkdir()
    assert mod.scope_status(d) == "pending"
    (d / "scope.failure.json").write_text("{}", encoding="utf-8")
    assert mod.scope_status(d) == "failed"
    (d / "scope.failure.json").unlink()
    (d / "scope.json").write_text(json.dumps({"scope_state": "complete"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="snapshot"):
        mod.scope_status(d)
    (d / "frozen.db").write_bytes(b"x")
    assert mod.scope_status(d) == "complete"
    (d / "scope.json").write_text(json.dumps({"scope_state": "partial"}), encoding="utf-8")
    assert mod.scope_status(d) == "partial"


def test_known_tokens_counts_each_reported_total_once():
    mod = _load()
    receipt = {"channels": {
        "belief": {"attempts": [{"extraction": {"total_tokens": 10, "structured_output": {"total_tokens": 10}},
                                 "admission": {"total_tokens": 4}}]},
        "episodic": {"response": {"total_tokens": 7}}}}
    assert mod.known_tokens(receipt) == 21
    assert mod.known_tokens({}) == 0


def test_abort_reason_follows_the_registered_stop_lines():
    mod = _load()
    ok = [{"holders": 5, "holder_failures": 0, "tokens": 100}] * 6
    assert mod.abort_reason(ok) is None
    assert mod.abort_reason([{"holders": 5, "holder_failures": 0, "tokens": 12_000_000}]) is None
    assert mod.abort_reason([{"holders": 5, "holder_failures": 0, "tokens": 12_000_001}]) == "token_cap"
    assert mod.abort_reason([{"holders": 4, "holder_failures": 4, "tokens": 1}] * 5) is None
    assert mod.abort_reason([{"holders": 4, "holder_failures": 1, "tokens": 1}] * 6) is None
    assert mod.abort_reason([{"holders": 4, "holder_failures": 2, "tokens": 1}] * 6) == "holder_failure_rate"


def test_smoke_passes_with_at_most_one_failed_holder_in_a_built_scope():
    mod = _load()
    assert mod.SMOKE_FAILURE_TOLERANCE == 1
    assert mod.smoke_passed({"scope_state": "complete", "holders": 4, "holder_failures": 0}) is True
    assert mod.smoke_passed({"scope_state": "partial", "holders": 4, "holder_failures": 1}) is True
    assert mod.smoke_passed({"scope_state": "partial", "holders": 4, "holder_failures": 2}) is False
    assert mod.smoke_passed({"scope_state": "failed", "holders": 4, "holder_failures": 0}) is False
    assert mod.smoke_passed({"scope_state": "failed", "holders": 4, "holder_failures": 1}) is False


# ---------------------------- 覆盖诊断 ----------------------------

def test_linked_turn_ids_reads_the_claim_source_turns():
    mod = _load()
    rows = [("Ada", json.dumps({"source_turn": {"turn_id": "s1_t2"}})),
            ("Ada", json.dumps({"source_turn": {"turn_id": "s1_t3"}})),
            ("Bob", json.dumps({"source_turn": {"turn_id": "unknown_turn"}})),
            ("Bob", "not json"), ("Ada", ""), ("Ada", None)]
    linked, owned = mod.linked_turn_ids(rows, TURNS)
    assert linked == {"s1_t2", "s1_t3"}
    assert owned == {"s1_t2"}          # s1_t3 的说话人是 Bob,Ada 的声明回链它不算本人


def test_gold_link_coverage_reports_turn_and_whole_question_coverage():
    mod = _load()
    rec = {"gold_statements": [{"turn_id": "s1_t2"}, {"turn_id": "s1_t3"}, {"turn_id": "s1_t2"}]}
    assert mod.gold_link_coverage(rec, {"s1_t2"}, {"s1_t2"}) == {
        "gold": 2, "linked": 1, "owned": 1, "all_linked": False, "all_owned": False}
    assert mod.gold_link_coverage(rec, {"s1_t2", "s1_t3"}, {"s1_t2"}) == {
        "gold": 2, "linked": 2, "owned": 1, "all_linked": True, "all_owned": False}


# ---------------------------- 召回回放 ----------------------------

def test_recall_for_arm_replays_on_a_copy_and_keeps_sources_equal_across_modes(tmp_path):
    from starling import _core
    mod = _load()
    lib = _library(tmp_path)
    before = _events(lib)
    rec = {"item_id": "q1", "query_type": "Q5", "answer_format": "long_form", "question": "copper lantern Kyoto",
           "history": TURNS}
    work, emb = tmp_path / "work", _core.StubEmbeddingAdapter(8)
    ctrl = mod.recall_for_arm("st_ctrl", rec, lib, work, embedder=emb, now_iso=NOW)
    hyb = mod.recall_for_arm("st_hyb", rec, lib, work, embedder=emb, now_iso=NOW)
    cov = mod.recall_for_arm("st_hyb_cov", rec, lib, work, embedder=emb, now_iso=NOW)
    assert "s1_t2" in [r["turn_id"] for r in ctrl["source_refs"]]
    assert [r["turn_id"] for r in hyb["source_refs"]] == [r["turn_id"] for r in ctrl["source_refs"]]
    assert ctrl["statement_count"] == 0 and hyb["statement_count"] == 0
    assert cov["source_count"] >= 1
    assert ctrl["context_bytes"] == len(ctrl["block"].encode("utf-8"))
    assert _events(lib) == before
    assert not any(p.suffix == ".db" for p in work.glob("*"))


def test_control_agreement_counts_identical_blocks_against_the_matrix_reference():
    mod = _load()
    rows = [{"item_id": "a", "block_sha256": "h1"}, {"item_id": "b", "block_sha256": "h2"}]
    ref = [{"arm": mod.CONTROL_REFERENCE_ARM, "item_id": "a", "block_sha256": "h1"},
           {"arm": mod.CONTROL_REFERENCE_ARM, "item_id": "b", "block_sha256": "zz"},
           {"arm": "other", "item_id": "b", "block_sha256": "h2"}]
    assert mod.control_agreement(rows, ref) == {"equal": 1, "of": 2}


# ---------------------------- 读法与报告 ----------------------------

@pytest.mark.parametrize("delta,lo,label", [
    (0.12, 0.01, "结构化声明有可确认的选择题增益"), (0.10, 0.02, "结构化声明有可确认的选择题增益"),
    (0.12, 0.0, "无法区分"), (0.05, 0.01, "无法区分"),
    (0.04, -0.10, "附加声明对选择题没有增益"), (-0.08, -0.20, "附加声明对选择题没有增益")])
def test_rule_one_reads_the_structured_arm_against_the_control(delta, lo, label):
    mod = _load()
    assert mod.read_hyb_mc_vs_ctrl(delta, lo) == label


def _rec(item, qt, net, fmt="multiple_choice"):
    return {"item_id": item, "query_type": qt, "answer_format": fmt, "source": {"network_id": net}}


def _row(score, ok=None, status=None):
    return {"score": score, "ok": (score >= 0.7) if ok is None else ok, "judge_status": status}


def test_build_report_pairs_the_structured_arm_with_the_control_and_checks_the_guards():
    mod = _load()
    recs = [_rec("a", "Q2", "n1"), _rec("b", "Q2", "n2"), _rec("c", "Q6", "n3"), _rec("d", "Q4", "n1"),
            _rec("e", "Q5", "n2", "long_form"), _rec("f", "Q9", "n3", "long_form")]
    ctrl = {"a": _row(0.0), "b": _row(0.0), "c": _row(1.0), "d": _row(1.0), "e": _row(0.5), "f": _row(1.0)}
    hyb = {"a": _row(1.0), "b": _row(1.0), "c": _row(1.0), "d": _row(1.0), "e": _row(0.75), "f": _row(1.0)}
    report = mod.build_report(recs, {"st_ctrl": ctrl, "st_hyb": hyb}, seed=1, draws=200)
    assert report["mc"]["Q2"] == {"n": 2, "st_ctrl": 0, "st_hyb": 2}
    assert report["mc"]["Q4"] == {"n": 1, "st_ctrl": 1, "st_hyb": 1}
    pair = report["paired"]["hyb_vs_ctrl_mc"]
    assert pair["n"] == 3 and pair["networks"] == 3 and pair["delta"] == pytest.approx(2 / 3)
    assert pair["read"] in {"结构化声明有可确认的选择题增益", "无法区分", "附加声明对选择题没有增益"}
    assert report["guards"]["q4_mc"] == {"ctrl": 1, "hyb": 1, "held": True}
    assert report["guards"]["open_mean_delta"] == pytest.approx(0.125)
    assert report["guards"]["open_held"] is True
    assert "st_hyb_cov" not in report["arms"]


def test_build_report_excludes_regex_fallback_scores_from_the_open_summary():
    mod = _load()
    recs = [_rec("e", "Q5", "n2", "long_form"), _rec("f", "Q9", "n3", "long_form")]
    ctrl = {"e": _row(0.5), "f": _row(1.0)}
    hyb = {"e": _row(1.0, status="regex_fallback"), "f": _row(1.0)}
    report = mod.build_report(recs, {"st_ctrl": ctrl, "st_hyb": hyb}, seed=1, draws=50)
    assert report["arms"]["st_hyb"]["q5q9"]["n"] == 1
    assert report["arms"]["st_hyb"]["regex_fallback"] == ["e"]
    assert report["paired"]["hyb_vs_ctrl_open"]["n"] == 1


# ---------------------------- 命令行 ----------------------------

def test_main_refuses_to_build_without_real_run_and_touches_nothing(tmp_path, capsys):
    mod = _load()
    out = tmp_path / "o"
    assert mod.main(["build", "--out", str(out)]) == 1
    assert "--real-run" in capsys.readouterr().err
    assert not out.exists()


def _answer_args(tmp_path, arm="st_ctrl"):
    return ["answer", "--arm", arm, "--out", str(tmp_path / "a"), "--builds", str(tmp_path / "b"),
            "--prompts", str(tmp_path / "p.yaml"), "--prompts-sha256", "0" * 64]


def test_main_refuses_to_answer_without_real_run_and_touches_nothing(tmp_path, capsys):
    mod = _load()
    assert mod.main(_answer_args(tmp_path)) == 1
    assert "--real-run" in capsys.readouterr().err
    assert not (tmp_path / "a").exists()


def test_main_rejects_an_unknown_arm(tmp_path):
    mod = _load()
    with pytest.raises(SystemExit):
        mod.main(_answer_args(tmp_path, arm="nope"))


# ---------------------------- 请求前门禁(登记修订一) ----------------------------

def test_precheck_gate_requires_equal_sources_across_modes_and_only_reports_the_reference():
    mod = _load()
    ctrl = [{"item_id": "a", "block_sha256": "h1", "turn_ids": ["t1", "t2"]},
            {"item_id": "b", "block_sha256": "h2", "turn_ids": ["t3"]}]
    hyb = [{"item_id": "a", "turn_ids": ["t1", "t2"]}, {"item_id": "b", "turn_ids": ["t3"]}]
    ref = [{"arm": mod.CONTROL_REFERENCE_ARM, "item_id": "a", "block_sha256": "h1"},
           {"arm": mod.CONTROL_REFERENCE_ARM, "item_id": "b", "block_sha256": "zz"}]
    assert mod.precheck_summary(ctrl, hyb, ref) == {"mode_equal": 2, "of": 2, "reference_equal": 1, "ready": True}
    hyb[1] = {"item_id": "b", "turn_ids": ["t9"]}
    result = mod.precheck_summary(ctrl, hyb, ref)
    assert result["mode_equal"] == 1 and result["ready"] is False


def test_precheck_gate_is_not_ready_when_a_question_has_no_structured_replay():
    mod = _load()
    ctrl = [{"item_id": "a", "block_sha256": "h1", "turn_ids": ["t1"]}]
    assert mod.precheck_summary(ctrl, [], [])["ready"] is False
    assert mod.precheck_summary([], [], [])["ready"] is False


# ---------------------------- 单组建库(假模型,离线) ----------------------------

def _build_env(tmp_path, response):
    from types import SimpleNamespace
    from starling import _core, runtime
    base, pipe, ladder = _load("run_socialmem_baseline"), _load("eval_ladder_pipeline"), _load("eval_ladder")
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(response, True, "")
    stub = _core.StubEmbeddingAdapter(8)

    def drain(core, adapter, _embedder, index, now, **kwargs):
        return pipe.embed_seeded(core, adapter, stub, index, now, **kwargs)

    modules = (_core, runtime, None, ladder, SimpleNamespace(embed_seeded=drain), None)
    ledger = base.BudgetLedger(tmp_path / "ledger.sqlite", 100000)
    return modules, (fake, SimpleNamespace(request_count=0), None, None), ledger


def test_build_one_group_archives_a_complete_scope_and_never_rebuilds_a_terminal_one(tmp_path):
    mod = _load()
    modules, adapters, ledger = _build_env(tmp_path, '{"schema_version":2,"statements":[]}')
    group = mod.plan_groups([_q("x", "n1", 12, ["Ada", "Bob"])])[0]
    out = tmp_path / "out"
    summary = mod.build_one_group(group, out, mod.build_config(), modules=modules, adapters=adapters, ledger=ledger)
    scope = out / "runs" / group["group_id"]
    assert summary["status"] == "complete" and summary["holders"] == 2 and summary["holder_failures"] == 0
    assert mod.smoke_passed(summary) is True
    assert (scope / "frozen.db").is_file() and (scope / "extraction.receipts.json").is_file()
    marker = (scope / "scope.json").stat().st_mtime_ns
    again = mod.build_one_group(group, out, mod.build_config(), modules=modules, adapters=adapters, ledger=ledger)
    assert again == summary and (scope / "scope.json").stat().st_mtime_ns == marker
    assert ledger.snapshot()["reserved"] == 0


def test_build_one_group_archives_a_failed_scope_without_raising_and_keeps_it_terminal(tmp_path):
    from types import SimpleNamespace
    mod = _load()
    modules, adapters, ledger = _build_env(tmp_path, '{"schema_version":2,"statements":[]}')
    group = mod.plan_groups([_q("x", "n1", 12, ["Ada", "Bob"])])[0]
    out = tmp_path / "out"

    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    core, runtime_module, audit, _ladder, pipe, longmem = modules
    broken = (core, runtime_module, audit, SimpleNamespace(_build_extract_llm=None, make_real_extract_fn=boom),
              pipe, longmem)
    summary = mod.build_one_group(group, out, mod.build_config(), modules=broken, adapters=adapters, ledger=ledger)
    scope = out / "runs" / group["group_id"]
    assert summary["status"] == "failed" and summary["holder_failures"] == 2
    assert mod.smoke_passed(summary) is False
    assert "boom" in (scope / "scope.failure.json").read_text(encoding="utf-8")
    assert ledger.snapshot()["reserved"] == 0
    again = mod.build_one_group(group, out, mod.build_config(), modules=modules, adapters=adapters, ledger=ledger)
    assert again["status"] == "failed"          # 终态不重建,不重复花费


# ---------------------------- 供应商配置与调度(登记修订八) ----------------------------

FLASH_DIFF_KEYS = {"profile", "extract_model", "extract_provider", "extract_endpoint", "extract_key_env",
                   "answer_model", "answer_endpoint", "answer_key_env",
                   "embedding_model", "embedding_endpoint", "embedding_dim", "embedding_key_env"}
RELAY = "https://api.tokenkey.dev/v1"


def test_profiles_keep_the_original_setup_and_add_the_relay_flash_setup():
    mod = _load()
    assert set(mod.load_profiles()) == {"dashscope", "tokenkey_flash", "tokenkey_max"}
    base_cfg, flash = mod.build_config(), mod.build_config("tokenkey_flash")
    assert mod.build_config("dashscope") == base_cfg
    assert base_cfg["profile"] == "dashscope"
    assert base_cfg["extract_key_env"] == base_cfg["answer_key_env"] == base_cfg["embedding_key_env"] == "DASHSCOPE_API_KEY"
    assert {k for k in set(flash) | set(base_cfg) if flash.get(k) != base_cfg.get(k)} == FLASH_DIFF_KEYS
    expected = {"profile": "tokenkey_flash", "extract_model": "qwen3.8-flash", "answer_model": "qwen3.8-flash",
                "extract_provider": "tokenkey", "extract_endpoint": RELAY, "answer_endpoint": RELAY,
                "embedding_endpoint": RELAY, "extract_key_env": "DEEPSEEK_API_KEY",
                "answer_key_env": "DEEPSEEK_API_KEY", "embedding_key_env": "DEEPSEEK_API_KEY",
                "embedding_model": "doubao-embedding-vision", "embedding_dim": 2048}
    for key, value in expected.items():
        assert flash[key] == value, key
    assert flash["claim_batch_size"] == 8 and flash["max_retries"] == 0 and flash["extract_enable_thinking"] is False


def test_an_unknown_profile_is_rejected():
    with pytest.raises(ValueError, match="profile"):
        _load().build_config("nope")


def test_make_adapters_builds_four_native_adapters_from_the_configured_key_variables(monkeypatch):
    import os
    from starling import _core
    mod = _load()
    monkeypatch.setenv("WP2B_TEST_KEY", "dummy-key-value")
    monkeypatch.setenv("OPENAI_API_KEY", "sentinel-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://sentinel.invalid/v1")
    monkeypatch.delenv("EMBEDDING_MAX_BATCH", raising=False)
    cfg = dict(mod.build_config("tokenkey_flash"), extract_key_env="WP2B_TEST_KEY", answer_key_env="WP2B_TEST_KEY",
               embedding_key_env="WP2B_TEST_KEY")
    adapters = mod.make_adapters(_core, cfg)
    assert [type(a).__name__ for a in adapters] == ["OpenAIAdapter", "OpenAIEmbeddingAdapter", "OpenAIAdapter",
                                                    "OpenAIAdapter"]
    assert adapters[1].dim() == 2048 and adapters[1].model() == "doubao-embedding-vision"
    assert os.environ["OPENAI_API_KEY"] == "sentinel-key"
    assert os.environ["OPENAI_BASE_URL"] == "https://sentinel.invalid/v1"
    assert "EMBEDDING_MAX_BATCH" not in os.environ


def test_make_adapters_refuses_an_unset_key_variable_and_restores_the_environment(monkeypatch):
    import os
    from starling import _core
    mod = _load()
    monkeypatch.delenv("WP2B_NO_SUCH_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sentinel-key")
    cfg = dict(mod.build_config("tokenkey_flash"), extract_key_env="WP2B_NO_SUCH_KEY")
    with pytest.raises(RuntimeError, match="WP2B_NO_SUCH_KEY"):
        mod.make_adapters(_core, cfg)
    assert os.environ["OPENAI_API_KEY"] == "sentinel-key"


def test_answer_channel_points_the_openai_variables_at_the_profile_and_restores_them(monkeypatch):
    import os
    mod = _load()
    monkeypatch.setenv("WP2B_TEST_KEY", "dummy-key-value")
    monkeypatch.setenv("OPENAI_API_KEY", "sentinel-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    cfg = dict(mod.build_config("tokenkey_flash"), answer_key_env="WP2B_TEST_KEY")
    with mod.answer_channel(cfg):
        assert os.environ["OPENAI_API_KEY"] == "dummy-key-value"
        assert os.environ["OPENAI_BASE_URL"] == RELAY
    assert os.environ["OPENAI_API_KEY"] == "sentinel-key" and "OPENAI_BASE_URL" not in os.environ
    with pytest.raises(ZeroDivisionError):
        with mod.answer_channel(cfg):
            1 / 0
    assert os.environ["OPENAI_API_KEY"] == "sentinel-key" and "OPENAI_BASE_URL" not in os.environ


def test_answer_channel_refuses_an_unset_key_variable(monkeypatch):
    mod = _load()
    monkeypatch.delenv("WP2B_NO_SUCH_KEY", raising=False)
    with pytest.raises(RuntimeError, match="WP2B_NO_SUCH_KEY"):
        with mod.answer_channel(dict(mod.build_config("tokenkey_flash"), answer_key_env="WP2B_NO_SUCH_KEY")):
            pass


def _fake_groups(n, holders=4):
    return [{"group_id": f"g{i:02d}", "holders": holders} for i in range(n)]


def _threads(workers):
    from concurrent.futures import ThreadPoolExecutor
    return ThreadPoolExecutor(max_workers=workers)


def test_schedule_groups_runs_every_group_once_when_nothing_aborts():
    mod = _load()
    seen = []

    def worker(group):
        seen.append(group["group_id"])
        return {"scope": group["group_id"], "holders": group["holders"], "holder_failures": 0, "tokens": 1}

    groups = _fake_groups(5)
    summaries, reason = mod.schedule_groups(groups, worker, workers=2, abort_check=lambda s: None,
                                            executor_factory=_threads)
    assert reason is None and sorted(seen) == [g["group_id"] for g in groups]
    assert sorted(s["scope"] for s in summaries) == sorted(seen)


def test_schedule_groups_stops_submitting_once_the_abort_line_fires():
    mod = _load()
    seen = []

    def worker(group):
        seen.append(group["group_id"])
        return {"scope": group["group_id"], "holders": group["holders"], "holder_failures": group["holders"],
                "tokens": 0}

    summaries, reason = mod.schedule_groups(_fake_groups(10), worker, workers=1,
                                            abort_check=lambda s: "stop" if len(s) >= 3 else None,
                                            executor_factory=_threads)
    assert reason == "stop" and len(seen) == 3 and len(summaries) == 3


def test_schedule_groups_counts_prior_summaries_and_keeps_the_window_bounded():
    mod = _load()
    seen = []
    prior = [{"scope": "smoke", "holders": 4, "holder_failures": 0, "tokens": 5}]

    def worker(group):
        seen.append(group["group_id"])
        return {"scope": group["group_id"], "holders": group["holders"], "holder_failures": 4, "tokens": 0}

    summaries, reason = mod.schedule_groups(_fake_groups(10), worker, workers=2, prior=prior,
                                            abort_check=lambda s: "stop" if len(s) >= 3 else None,
                                            executor_factory=_threads)
    assert reason == "stop"
    assert 2 <= len(summaries) <= 3 and len(seen) <= 4 and len(seen) < 10


def test_schedule_groups_turns_a_crashing_worker_into_a_failed_summary():
    mod = _load()

    def worker(group):
        raise RuntimeError("boom")

    summaries, reason = mod.schedule_groups(_fake_groups(2, holders=3), worker, workers=1,
                                            abort_check=lambda s: None, executor_factory=_threads)
    assert reason is None and len(summaries) == 2
    assert all(s["status"] == "worker_crash" and s["holder_failures"] == 3 and s["holders"] == 3 for s in summaries)
    assert {s["scope"] for s in summaries} == {"g00", "g01"}


def test_profile_option_is_accepted_and_validated(tmp_path, capsys):
    mod = _load()
    assert mod.main(["build", "--out", str(tmp_path / "o"), "--profile", "tokenkey_flash"]) == 1
    assert "--real-run" in capsys.readouterr().err
    assert mod.main(_answer_args(tmp_path) + ["--profile", "tokenkey_flash"]) == 1
    assert not (tmp_path / "o").exists() and not (tmp_path / "a").exists()
    with pytest.raises(SystemExit):
        mod.main(["build", "--out", str(tmp_path / "o"), "--profile", "nope"])


# ---------------------------- 外置配置、放宽冒烟门与前置门(登记修订十一) ----------------------------

MODEL_KEYS = ("extract_model", "extract_provider", "extract_endpoint", "extract_key_env",
              "answer_model", "answer_endpoint", "answer_key_env",
              "embedding_model", "embedding_endpoint", "embedding_dim", "embedding_key_env")


def _profile_entry(**over):
    entry = {"extract_model": "m-1", "extract_provider": "p", "extract_endpoint": "https://example.invalid/v1",
             "extract_key_env": "TEST_KEY_ENV", "answer_model": "m-1", "answer_endpoint": "https://example.invalid/v1",
             "answer_key_env": "TEST_KEY_ENV", "embedding_model": "e-1",
             "embedding_endpoint": "https://example.invalid/v1", "embedding_dim": 8,
             "embedding_key_env": "TEST_KEY_ENV"}
    entry.update(over)
    return entry


def _write_profiles(tmp_path, **profiles):
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"schema_version": 1, "default_profile": next(iter(profiles)), "profiles": profiles}),
                    encoding="utf-8")
    return path


def test_the_shipped_profiles_file_is_structurally_valid_and_keeps_the_registered_default():
    mod = _load()
    assert tuple(mod.MODEL_KEYS) == MODEL_KEYS
    profiles = mod.load_profiles()
    assert {"dashscope", "tokenkey_flash"} <= set(profiles)
    assert mod.default_profile_name() in profiles
    for name, entry in profiles.items():
        assert set(entry) == set(MODEL_KEYS), name
        for key in MODEL_KEYS:
            if key != "embedding_dim":
                assert isinstance(entry[key], str) and entry[key], (name, key)
        dim = entry["embedding_dim"]
        assert dim is None or (type(dim) is int and dim > 0), name


def test_load_profiles_rejects_malformed_entries_without_echoing_their_values(tmp_path):
    mod = _load()
    secret = "sk-this-looks-like-a-pasted-secret-0123456789"
    cases = {
        "unknown key": _profile_entry(extra_field="x"),
        "missing key": {k: v for k, v in _profile_entry().items() if k != "answer_model"},
        "string dimension": _profile_entry(embedding_dim="1024"),
        "zero dimension": _profile_entry(embedding_dim=0),
        "bool dimension": _profile_entry(embedding_dim=True),
        "pasted secret as key variable": _profile_entry(extract_key_env=secret),
        "non-https endpoint": _profile_entry(answer_endpoint="http://example.invalid/v1"),
        "empty model": _profile_entry(extract_model=""),
    }
    for label, entry in cases.items():
        path = _write_profiles(tmp_path, bad=entry)
        with pytest.raises(ValueError) as info:
            mod.load_profiles(path)
        assert secret not in str(info.value), label
        assert "bad" in str(info.value), label


def test_load_profiles_rejects_a_wrong_schema_a_missing_default_or_an_unreadable_file(tmp_path):
    mod = _load()
    good = {"ok": _profile_entry()}
    for payload in ({"schema_version": 2, "default_profile": "ok", "profiles": good},
                    {"schema_version": 1, "profiles": good},
                    {"schema_version": 1, "default_profile": "missing", "profiles": good},
                    {"schema_version": 1, "default_profile": "ok"},
                    {"schema_version": 1, "default_profile": "ok", "profiles": []},
                    {"schema_version": 1, "default_profile": "ok", "profiles": {}},
                    [1]):
        path = tmp_path / "p.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError):
            mod.load_profiles(path)
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    for path in (broken, tmp_path / "missing.json"):
        with pytest.raises(ValueError, match="profiles"):
            mod.load_profiles(path)


def test_a_profile_note_is_allowed_and_dropped(tmp_path):
    mod = _load()
    path = _write_profiles(tmp_path, ok=_profile_entry(note="any text"))
    assert "note" not in mod.load_profiles(path)["ok"]


def test_build_config_reads_a_custom_profiles_file_and_resolves_its_default(tmp_path):
    mod = _load()
    path = _write_profiles(tmp_path, other=_profile_entry(extract_model="m-9", embedding_dim=16), second=_profile_entry())
    cfg = mod.build_config("other", path)
    assert cfg["profile"] == "other" and cfg["extract_model"] == "m-9" and cfg["embedding_dim"] == 16
    assert cfg["claim_batch_size"] == 8 and cfg["max_retries"] == 0
    assert mod.build_config(None, path) == cfg and mod.default_profile_name(path) == "other"
    with pytest.raises(ValueError, match="profile"):
        mod.build_config("dashscope", path)


def test_the_driver_source_names_no_model_provider_endpoint_or_key_variable():
    source = (_SCRIPTS / "eval_socialmem_structured_build.py").read_text(encoding="utf-8").lower()
    for forbidden in ("qwen", "doubao", "gemini", "deepseek", "gpt-", "text-embedding", "dashscope", "tokenkey",
                      "aliyuncs"):
        assert forbidden not in source, forbidden


def test_a_profile_without_a_known_embedding_dimension_is_not_buildable(tmp_path):
    mod = _load()
    path = _write_profiles(tmp_path, nodim=_profile_entry(embedding_dim=None), fine=_profile_entry())
    assert mod.buildable_problem(mod.build_config("fine", path)) is None
    problem = mod.buildable_problem(mod.build_config("nodim", path))
    assert problem and "embedding_dim" in problem and "nodim" in problem
    empty = mod.buildable_problem(dict(mod.build_config("fine", path), extract_model=""))
    assert empty and "extract_model" in empty


def test_main_build_refuses_a_profile_without_a_known_embedding_dimension_and_creates_nothing(tmp_path, capsys):
    mod = _load()
    path = _write_profiles(tmp_path, nodim=_profile_entry(embedding_dim=None))
    out = tmp_path / "o"
    code = mod.main(["build", "--out", str(out), "--profile", "nodim", "--profiles", str(path), "--real-run",
                     "--corpus", str(tmp_path / "missing.jsonl")])
    assert code == 1 and "embedding_dim" in capsys.readouterr().err and not out.exists()


def test_profiles_option_selects_names_from_the_given_file(tmp_path):
    mod = _load()
    path = _write_profiles(tmp_path, only=_profile_entry())
    assert mod.main(["build", "--out", str(tmp_path / "o"), "--profile", "only", "--profiles", str(path)]) == 1
    assert mod.main(["build", "--out", str(tmp_path / "o"), "--profiles", str(path)]) == 1
    with pytest.raises(SystemExit):
        mod.main(["build", "--out", str(tmp_path / "o"), "--profile", "dashscope", "--profiles", str(path)])
    with pytest.raises(SystemExit):
        mod.main(["build", "--out", str(tmp_path / "o"), "--profiles", str(tmp_path / "missing.json")])
    assert not (tmp_path / "o").exists()


def test_profiles_sha256_is_the_digest_of_the_file_bytes(tmp_path):
    import hashlib
    mod = _load()
    path = _write_profiles(tmp_path, ok=_profile_entry())
    assert mod.profiles_sha256(path) == hashlib.sha256(path.read_bytes()).hexdigest()
    assert mod.profiles_sha256() == hashlib.sha256(Path(mod.DEFAULT_PROFILES).read_bytes()).hexdigest()


def test_check_built_matches_compares_only_the_model_settings():
    mod = _load()
    current = mod.build_config()
    assert mod.check_built_matches(dict(current, core_sha256="x", http_budget=1), current) is None
    for key, value in (("extract_model", "other"), ("embedding_dim", 7), ("embedding_model", "other")):
        problem = mod.check_built_matches(dict(current, **{key: value}), current)
        assert problem and key in problem


def _fake_llm(reply="ok", ok=True, error=""):
    from starling import _core
    fake = _core.FakeLLMAdapter()
    fake.set_default_response(reply, ok, error)
    return fake


def _preflight_config(dim=8):
    return dict(_load().build_config(), embedding_dim=dim)


def test_preflight_passes_when_both_chat_channels_answer_and_the_embedding_dimension_matches():
    from starling import _core
    mod = _load()
    good = _fake_llm()
    report = mod.preflight(_preflight_config(8), (good, _core.StubEmbeddingAdapter(8), good, good))
    assert report == {"extract_chat": True, "answer_chat": True, "embedding_dim": 8}


def test_preflight_refuses_a_dimension_mismatch_and_names_both_numbers():
    from starling import _core
    mod = _load()
    good = _fake_llm()
    with pytest.raises(RuntimeError, match=r"维度.*16.*8|维度.*8.*16"):
        mod.preflight(_preflight_config(16), (good, _core.StubEmbeddingAdapter(8), good, good))


def test_preflight_refuses_an_empty_or_failed_chat_reply_on_either_channel():
    from starling import _core
    mod = _load()
    good, stub = _fake_llm(), _core.StubEmbeddingAdapter(8)
    for bad in (_fake_llm("", True, ""), _fake_llm("boom", False, "upstream_failure: permanent_400")):
        with pytest.raises(RuntimeError, match="抽取"):
            mod.preflight(_preflight_config(8), (bad, stub, good, good))
        with pytest.raises(RuntimeError, match="作答"):
            mod.preflight(_preflight_config(8), (good, stub, bad, good))


def test_preflight_refuses_a_failing_embedding():
    from starling import _core
    mod = _load()
    good, stub = _fake_llm(), _core.StubEmbeddingAdapter(8)
    stub.fail_next(mod.PREFLIGHT_TEXT)
    with pytest.raises(RuntimeError, match="嵌入"):
        mod.preflight(_preflight_config(8), (good, stub, good, good))


# ---------------------------- 隔离答题(登记:对照臂放在去掉声明的库上,对 28 题重答) ----------------------------

_VISIBLE_MC = "来源选择认得声明对选择题有可见影响"
_VISIBLE_OPEN = "来源选择认得声明对开放题有可见影响"
_INDISTINGUISHABLE = "无法区分"


def _claims_db(path, rows):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("create table statements (id text primary key, holder_id text, semantic_claim_json text)")
        conn.executemany("insert into statements values (?,?,?)", rows)
        conn.commit()


def _file_sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_isolation_arms_are_the_control_arm_twice_and_leave_the_registered_arms_alone():
    mod = _load()
    assert mod.ARMS == ("st_ctrl", "st_hyb", "st_hyb_cov")
    assert mod.ISOLATION_ARMS == ("st_ctrl_noclaim", "st_ctrl_repeat")
    for arm in mod.ISOLATION_ARMS:
        assert mod.arm_spec(arm) == mod.arm_spec("st_ctrl")


def test_strip_claims_clears_only_the_claim_column_on_a_copy_and_leaves_the_source_untouched(tmp_path):
    mod = _load()
    src, dst = tmp_path / "src.db", tmp_path / "out" / "dst.db"
    _claims_db(src, [("a", "Ada", '{"x":1}'), ("b", "Bob", None), ("c", "Ada", ""), ("d", "Bob", '{"y":2}')])
    before = _file_sha(src)
    info = mod.strip_claims(src, dst)
    assert _file_sha(src) == before
    assert info == {"statements": 4, "claims_cleared": 2}
    with closing(sqlite3.connect(dst)) as conn:
        rows = conn.execute("select id, holder_id, semantic_claim_json from statements order by id").fetchall()
    assert rows == [("a", "Ada", ""), ("b", "Bob", ""), ("c", "Ada", ""), ("d", "Bob", "")]


def test_strip_claims_refuses_to_overwrite_a_copy_and_a_missing_source_leaves_nothing_behind(tmp_path):
    mod = _load()
    src = tmp_path / "src.db"
    _claims_db(src, [("a", "Ada", '{"x":1}')])
    dst = tmp_path / "dst.db"
    dst.write_bytes(b"x")
    with pytest.raises(FileExistsError):
        mod.strip_claims(src, dst)
    assert dst.read_bytes() == b"x"
    with pytest.raises(FileNotFoundError):
        mod.strip_claims(tmp_path / "nope.db", tmp_path / "d2.db")
    assert not (tmp_path / "d2.db").exists()


def test_load_item_list_returns_corpus_order_and_rejects_unknown_duplicate_or_empty_lists(tmp_path):
    mod = _load()
    recs = [_rec("a", "Q2", "n1"), _rec("b", "Q5", "n2", "long_form"), _rec("c", "Q6", "n3")]
    path = tmp_path / "items.txt"
    path.write_text("c\na\n", encoding="utf-8")
    assert mod.load_item_list(path, recs) == ["a", "c"]
    for bad in ("a\nzzz\n", "a\na\n", "\n\n", ""):
        path.write_text(bad, encoding="utf-8")
        with pytest.raises(ValueError):
            mod.load_item_list(path, recs)


def test_isolation_gate_for_the_stripped_arm_needs_the_reference_turn_sequences():
    mod = _load()
    ref = [{"arm": mod.CONTROL_REFERENCE_ARM, "item_id": "a", "turn_ids": ["t1", "t2"], "block_sha256": "h1"},
           {"arm": mod.CONTROL_REFERENCE_ARM, "item_id": "b", "turn_ids": ["t3"], "block_sha256": "h2"},
           {"arm": "other", "item_id": "b", "turn_ids": ["zz"], "block_sha256": "zz"}]
    rows = [{"item_id": "a", "turn_ids": ["t1", "t2"], "block_sha256": "x1"},
            {"item_id": "b", "turn_ids": ["t3"], "block_sha256": "x2"}]
    assert mod.isolation_gate("st_ctrl_noclaim", rows, reference=ref, original={}) == {
        "arm": "st_ctrl_noclaim", "turn_ids_equal": 2, "block_equal": 0, "of": 2, "ready": True}
    rows[1]["turn_ids"] = ["t9"]
    gate = mod.isolation_gate("st_ctrl_noclaim", rows, reference=ref, original={})
    assert gate["turn_ids_equal"] == 1 and gate["ready"] is False


def test_isolation_gate_for_the_repeat_arm_needs_the_original_blocks_and_rejects_empty_or_unknown():
    mod = _load()
    orig = {"a": {"block_sha256": "h1", "source_turn_ids": ["t1"]}, "b": {"block_sha256": "h2", "source_turn_ids": ["t3"]}}
    rows = [{"item_id": "a", "turn_ids": ["t1"], "block_sha256": "h1"},
            {"item_id": "b", "turn_ids": ["t3"], "block_sha256": "h2"}]
    gate = mod.isolation_gate("st_ctrl_repeat", rows, reference=[], original=orig)
    assert gate["block_equal"] == 2 and gate["of"] == 2 and gate["ready"] is True
    rows[0]["block_sha256"] = "zz"
    assert mod.isolation_gate("st_ctrl_repeat", rows, reference=[], original=orig)["ready"] is False
    assert mod.isolation_gate("st_ctrl_repeat", [], reference=[], original=orig)["ready"] is False
    with pytest.raises(ValueError):
        mod.isolation_gate("st_ctrl", rows, reference=[], original=orig)


@pytest.mark.parametrize("net,flips_claimless,flips_repeat,label", [
    (3, 4, 2, _VISIBLE_MC), (-3, 5, 3, _VISIBLE_MC),
    (2, 6, 0, _INDISTINGUISHABLE), (3, 3, 2, _INDISTINGUISHABLE), (0, 4, 0, _INDISTINGUISHABLE)])
def test_isolation_rule_one_reads_the_multiple_choice_change_against_the_repeat_noise(
        net, flips_claimless, flips_repeat, label):
    mod = _load()
    assert mod.read_isolation_mc(net, flips_claimless, flips_repeat) == label


@pytest.mark.parametrize("c_lo,c_hi,r_lo,r_hi,label", [
    (0.02, 0.20, -0.05, 0.05, _VISIBLE_OPEN), (-0.20, -0.02, -0.05, 0.05, _VISIBLE_OPEN),
    (-0.01, 0.20, -0.05, 0.05, _INDISTINGUISHABLE), (0.02, 0.20, 0.01, 0.10, _INDISTINGUISHABLE),
    (-0.10, 0.10, -0.05, 0.05, _INDISTINGUISHABLE)])
def test_isolation_rule_two_reads_the_open_interval_against_the_repeat_interval(c_lo, c_hi, r_lo, r_hi, label):
    mod = _load()
    assert mod.read_isolation_open(c_lo, c_hi, r_lo, r_hi) == label


def test_isolation_report_pairs_both_new_arms_with_the_original_journal_on_the_listed_items_only():
    mod = _load()
    recs = [_rec("a", "Q2", "n1"), _rec("b", "Q6", "n2"), _rec("c", "Q2", "n3"),
            _rec("d", "Q5", "n1", "long_form"), _rec("e", "Q9", "n2", "long_form"), _rec("z", "Q4", "n3")]
    items = ["a", "b", "c", "d", "e"]
    orig = {"a": _row(1.0), "b": _row(0.0), "c": _row(1.0), "d": _row(0.5), "e": _row(1.0), "z": _row(1.0)}
    noclaim = {"a": _row(0.0), "b": _row(0.0), "c": _row(0.0), "d": _row(1.0), "e": _row(1.0)}
    repeat = {"a": _row(1.0), "b": _row(0.0), "c": _row(1.0), "d": _row(0.5), "e": _row(1.0)}
    report = mod.build_isolation_report(recs, items, orig, {"st_ctrl_noclaim": noclaim, "st_ctrl_repeat": repeat},
                                        seed=1, draws=200)
    assert report["mc"]["n"] == 3 and report["mc"]["orig_correct"] == 2
    assert report["mc"]["st_ctrl_noclaim"] == {"correct": 0, "net": -2, "flips": 2}
    assert report["mc"]["st_ctrl_repeat"] == {"correct": 2, "net": 0, "flips": 0}
    assert report["mc"]["read"] == _INDISTINGUISHABLE
    assert report["open"]["n"] == 2
    assert report["open"]["st_ctrl_noclaim"]["delta"] == pytest.approx(0.25)
    assert report["open"]["st_ctrl_repeat"]["delta"] == pytest.approx(0.0)
    assert report["open"]["read"] == _INDISTINGUISHABLE
    assert report["flips"]["st_ctrl_noclaim"] == {"a": "答对变答错", "c": "答对变答错"}
    assert report["flips"]["st_ctrl_repeat"] == {}


def test_isolation_report_lists_missing_rows_and_unreliable_judge_scores_and_leaves_them_out():
    mod = _load()
    recs = [_rec("a", "Q2", "n1"), _rec("b", "Q6", "n2"),
            _rec("d", "Q5", "n1", "long_form"), _rec("e", "Q9", "n2", "long_form")]
    items = ["a", "b", "d", "e"]
    orig = {"a": _row(1.0), "b": _row(1.0), "d": _row(0.5), "e": _row(1.0)}
    noclaim = {"a": _row(1.0), "d": _row(1.0, status="regex_fallback"), "e": _row(1.0)}
    repeat = {"a": _row(1.0), "b": _row(1.0), "d": _row(0.5), "e": _row(1.0)}
    report = mod.build_isolation_report(recs, items, orig, {"st_ctrl_noclaim": noclaim, "st_ctrl_repeat": repeat},
                                        seed=1, draws=50)
    assert report["missing"]["st_ctrl_noclaim"] == ["b"]
    assert report["missing"]["st_ctrl_repeat"] == []
    assert report["excluded"]["st_ctrl_noclaim"] == ["d"]
    assert report["mc"]["st_ctrl_noclaim"]["flips"] == 0
    assert report["open"]["st_ctrl_noclaim"]["n"] == 1


def test_main_refuses_an_isolation_arm_without_items_and_a_regular_arm_with_items(tmp_path, capsys):
    mod = _load()
    assert mod.main(_answer_args(tmp_path, arm="st_ctrl_noclaim")) == 1
    assert "--items" in capsys.readouterr().err
    assert mod.main(_answer_args(tmp_path, arm="st_ctrl") + ["--items", str(tmp_path / "i.txt")]) == 1
    assert "--items" in capsys.readouterr().err
    assert not (tmp_path / "a").exists()


def test_main_refuses_to_answer_an_isolation_arm_without_real_run_and_touches_nothing(tmp_path, capsys):
    mod = _load()
    args = _answer_args(tmp_path, arm="st_ctrl_repeat") + ["--items", str(tmp_path / "i.txt")]
    assert mod.main(args) == 1
    assert "--real-run" in capsys.readouterr().err
    assert not (tmp_path / "a").exists()


# ---------------------------- 隔离答题:路径、门文件校验与命令 ----------------------------

def test_stripped_library_paths_put_each_copy_under_its_group_directory(tmp_path):
    mod = _load()
    libs = {"a": tmp_path / "runs" / "g1" / "frozen.db", "b": tmp_path / "runs" / "g1" / "frozen.db",
            "c": tmp_path / "runs" / "g2" / "frozen.db"}
    out = tmp_path / "out"
    paths = mod.stripped_library_paths(libs, out)
    assert paths == {"a": out / "stripped" / "g1" / "frozen.db", "b": out / "stripped" / "g1" / "frozen.db",
                     "c": out / "stripped" / "g2" / "frozen.db"}


def _ready_precheck(**over):
    pre = {"core_sha256": "c0", "items_sha256": "i0", "ready": True,
           "gates": {"st_ctrl_noclaim": {"ready": True}, "st_ctrl_repeat": {"ready": True}}}
    pre.update(over)
    return pre


def test_isolation_precheck_problem_accepts_a_matching_ready_file_and_names_each_mismatch():
    mod = _load()
    check = mod.isolation_precheck_problem
    assert check(_ready_precheck(), "st_ctrl_noclaim", items_sha256="i0", core_sha256="c0") is None
    assert "isolation_precheck.json" in check(None, "st_ctrl_noclaim", items_sha256="i0", core_sha256="c0")
    assert "名单" in check(_ready_precheck(), "st_ctrl_noclaim", items_sha256="zz", core_sha256="c0")
    assert "核心" in check(_ready_precheck(), "st_ctrl_noclaim", items_sha256="i0", core_sha256="zz")
    not_ready = _ready_precheck(gates={"st_ctrl_noclaim": {"ready": False}, "st_ctrl_repeat": {"ready": True}})
    assert "门" in check(not_ready, "st_ctrl_noclaim", items_sha256="i0", core_sha256="c0")
    assert check(not_ready, "st_ctrl_repeat", items_sha256="i0", core_sha256="c0") is None
    assert "门" in check(_ready_precheck(gates={}), "st_ctrl_noclaim", items_sha256="i0", core_sha256="c0")


def test_isolation_precheck_refuses_a_non_empty_stripped_directory_before_touching_anything(tmp_path, capsys):
    mod = _load()
    out = tmp_path / "o"
    (out / "stripped" / "g1").mkdir(parents=True)
    (out / "stripped" / "g1" / "frozen.db").write_bytes(b"x")
    args = ["isolation-precheck", "--builds", str(tmp_path / "b"), "--out", str(out),
            "--items", str(tmp_path / "i.txt"), "--original-journal", str(tmp_path / "j.jsonl")]
    assert mod.main(args) == 1
    assert "stripped" in capsys.readouterr().err
    assert (out / "stripped" / "g1" / "frozen.db").read_bytes() == b"x"
    assert not (out / "isolation_precheck.json").exists()


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def test_isolation_report_command_reads_the_journals_and_prints_the_registered_readings(tmp_path, capsys):
    mod = _load()
    recs = [_rec("a", "Q2", "n1"), _rec("b", "Q6", "n2"), _rec("d", "Q5", "n3", "long_form")]
    corpus, items, orig = tmp_path / "c.jsonl", tmp_path / "i.txt", tmp_path / "orig.jsonl"
    _write_jsonl(corpus, recs)
    items.write_text("a\nb\nd\n", encoding="utf-8")

    def row(arm, item, score):
        return {"arm": arm, "item_id": item, "ok": score >= 0.7, "score": score, "judge_status": None}

    _write_jsonl(orig, [row("st_ctrl", "a", 1.0), row("st_ctrl", "b", 0.0), row("st_ctrl", "d", 0.5),
                        row("st_ctrl", "zz", 1.0)])
    out = tmp_path / "out"
    out.mkdir()
    _write_jsonl(out / "st_ctrl_noclaim_journal.jsonl",
                 [row("st_ctrl_noclaim", "a", 0.0), row("st_ctrl_noclaim", "b", 0.0), row("st_ctrl_noclaim", "d", 1.0)])
    _write_jsonl(out / "st_ctrl_repeat_journal.jsonl",
                 [row("st_ctrl_repeat", "a", 1.0), row("st_ctrl_repeat", "b", 0.0), row("st_ctrl_repeat", "d", 0.5)])
    result = tmp_path / "res.json"
    args = ["isolation-report", "--corpus", str(corpus), "--out", str(out), "--items", str(items),
            "--original-journal", str(orig), "--result", str(result)]
    assert mod.main(args) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["mc"]["n"] == 2 and printed["open"]["n"] == 1
    assert printed["mc"]["st_ctrl_noclaim"] == {"correct": 0, "net": -1, "flips": 1}
    assert printed["mc"]["st_ctrl_repeat"] == {"correct": 1, "net": 0, "flips": 0}
    assert printed["mc"]["read"] == "无法区分"
    assert json.loads(result.read_text(encoding="utf-8")) == printed


def test_isolation_report_command_fails_loudly_when_an_arm_journal_is_missing(tmp_path, capsys):
    mod = _load()
    corpus, items, orig = tmp_path / "c.jsonl", tmp_path / "i.txt", tmp_path / "orig.jsonl"
    _write_jsonl(corpus, [_rec("a", "Q2", "n1")])
    items.write_text("a\n", encoding="utf-8")
    _write_jsonl(orig, [{"arm": "st_ctrl", "item_id": "a", "ok": True, "score": 1.0, "judge_status": None}])
    out = tmp_path / "out"
    out.mkdir()
    args = ["isolation-report", "--corpus", str(corpus), "--out", str(out), "--items", str(items),
            "--original-journal", str(orig)]
    assert mod.main(args) == 1
    assert "journal" in capsys.readouterr().err


def test_isolation_library_problem_checks_each_library_hash_against_the_precheck_record(tmp_path):
    mod = _load()
    lib = tmp_path / "g1" / "frozen.db"
    lib.parent.mkdir()
    lib.write_bytes(b"aaa")
    pre = {"source_sha256": {"g1": _file_sha(lib)}, "stripped_sha256": {"g1": _file_sha(lib)}}
    assert mod.isolation_library_problem(pre, "st_ctrl_noclaim", {"x": lib}) is None
    assert mod.isolation_library_problem(pre, "st_ctrl_repeat", {"x": lib}) is None
    other = tmp_path / "g2" / "frozen.db"
    other.parent.mkdir()
    other.write_bytes(b"c")
    assert "g2" in mod.isolation_library_problem(pre, "st_ctrl_repeat", {"x": lib, "y": other})
    assert "g1" in mod.isolation_library_problem(pre, "st_ctrl_noclaim", {"x": tmp_path / "g1" / "missing.db"})
    lib.write_bytes(b"bbb")
    assert "g1" in mod.isolation_library_problem(pre, "st_ctrl_repeat", {"x": lib})
    assert "g1" in mod.isolation_library_problem({}, "st_ctrl_noclaim", {"x": lib})
