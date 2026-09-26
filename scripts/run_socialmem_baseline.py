#!/usr/bin/env python3
"""External, resumable SocialMemBench baseline orchestration.

This module deliberately imports no Starling code at module import time.  A
worker selects the frozen package only after its ``sys.path`` has been fixed;
the live worktree must never participate in a frozen baseline run.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable


TERMINAL_STATUSES = frozenset({
    "ok", "answer_failure", "judge_failure", "query_failure", "ingestion_failure",
    "technical_failure", "budget_failure", "invalid_answer",
})


def _value(record: dict, name: str, default: Any = "") -> Any:
    return record.get(name, record.get("source", {}).get(name, default))


def _network_id(record: dict) -> str:
    value = _value(record, "network_id")
    if value in (None, ""):
        raise ValueError("record is missing network_id")
    return str(value)


def _scope(record: dict) -> str:
    # Older frozen corpora have no scope annotation.  Treat that explicitly as
    # the all-session observer scope, rather than silently coalescing a future
    # scoped corpus with it.
    return str(_value(record, "evaluation_scope", "all") or "all")


def _history_hash(history: list[dict]) -> str:
    payload = json.dumps(history, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:24]


def prepare_groups(records: Iterable[dict]) -> list[dict]:
    """Group records by network and evaluation scope with a single history.

    A different history inside one group is a corpus identity failure.  It is
    unsafe to choose one arbitrarily because that would write memories for a
    question using another question's observed session.
    """
    grouped: dict[tuple[str, str], dict] = {}
    item_ids: set[str] = set()
    for record in records:
        item_id = str(record.get("item_id") or _value(record, "qa_id"))
        if not item_id:
            raise ValueError("record is missing item_id")
        if item_id in item_ids:
            raise ValueError(f"duplicate item_id: {item_id!r}")
        item_ids.add(item_id)
        network_id, scope = _network_id(record), _scope(record)
        key = (network_id, scope)
        history = list(record.get("history") or [])
        history_hash = _history_hash(history)
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = {
                "network_id": network_id,
                "evaluation_scope": scope,
                "history": history,
                "history_sha256": history_hash,
                "records": [record],
                "group_id": _stable_id(network_id, scope, history_hash),
            }
        else:
            if existing["history_sha256"] != history_hash:
                raise ValueError(
                    "history mismatch in network/evaluation_scope "
                    f"{network_id!r}/{scope!r}")
            existing["records"].append(record)
    return [grouped[key] for key in sorted(grouped)]


def ingestion_record(record: dict) -> dict:
    """Return the only corpus material permitted to enter the ingestion path."""
    item_id = str(record.get("item_id") or _value(record, "qa_id"))
    if not item_id:
        raise ValueError("record is missing item_id")
    return {
        "item_id": item_id,
        "network_id": _network_id(record),
        "evaluation_scope": _scope(record),
        "history": list(record.get("history") or []),
    }


def _verify_artifact_fingerprint(payload: dict, fingerprint: dict | None, path: Path) -> None:
    if fingerprint is not None and payload.get("fingerprint") != fingerprint:
        raise RuntimeError(f"fingerprint mismatch for archived artifact: {path}")


def question_states(question_dir: Path, item_ids: Iterable[str],
                    fingerprint: dict | None = None) -> dict[str, str]:
    """Classify resumability without treating an interrupted request as done."""
    states: dict[str, str] = {}
    for item_id in item_ids:
        stable = _stable_id(str(item_id))
        # Human-readable fixture tests may use the item id directly; production
        # filenames always use stable ids so corpus IDs cannot escape the folder.
        result_paths = (question_dir / f"{stable}.json", question_dir / f"{item_id}.json")
        started_paths = (question_dir / f"{stable}.started", question_dir / f"{item_id}.started")
        result = next((path for path in result_paths if path.exists()), None)
        if result is not None:
            try:
                payload = json.loads(result.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            _verify_artifact_fingerprint(payload, fingerprint, result)
            if payload.get("terminal") is True or payload.get("status") in TERMINAL_STATUSES:
                states[str(item_id)] = "terminal"
                continue
        started = next((path for path in started_paths if path.exists()), None)
        if started is not None:
            try:
                _verify_artifact_fingerprint(json.loads(started.read_text(encoding="utf-8")), fingerprint, started)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid started marker: {started}") from exc
            states[str(item_id)] = "incomplete"
        else:
            states[str(item_id)] = "pending"
    return states


def scope_state(scope_dir: Path, fingerprint: dict) -> str:
    """Return terminal/pending/incomplete without retrying an interrupted ingest."""
    completed = scope_dir / "scope.json"
    if completed.exists():
        payload = json.loads(completed.read_text(encoding="utf-8"))
        _verify_artifact_fingerprint(payload, fingerprint, completed)
        if not (scope_dir / "frozen.db").is_file():
            raise RuntimeError(f"completed scope snapshot missing: {scope_dir}")
        return "terminal"
    started = scope_dir / "scope.started"
    if started.exists():
        payload = json.loads(started.read_text(encoding="utf-8"))
        _verify_artifact_fingerprint(payload, fingerprint, started)
        return "incomplete"
    return "pending"


def _result_for(item_id: str, results: Iterable[dict]) -> dict | None:
    found = None
    for row in results:
        if str(row.get("item_id")) == str(item_id):
            found = row
    return found


def _bucket(records: list[dict], results: list[dict]) -> dict:
    total = correct = failed = executed = incomplete = 0
    for record in records:
        total += 1
        row = _result_for(str(record.get("item_id")), results)
        if row is None:
            continue
        status = str(row.get("status", ""))
        if status in ("budget_blocked", "unexecuted"):
            continue
        if status == "incomplete":
            incomplete += 1
            continue
        executed += 1
        correct += int(bool(row.get("correct")))
        failed += int(status != "ok")
    successful = executed - failed
    return {
        "total": total, "correct": correct, "accuracy": correct / total if total else 0.0,
        "executed": executed, "unexecuted": total - executed - incomplete,
        "incomplete": incomplete, "failed": failed,
        "technical": failed,
        "coverage": executed / total if total else 0.0,
        "successful_denominator": successful,
        "successful_accuracy": correct / successful if successful else 0.0,
    }


def summarize(records: list[dict], results: list[dict]) -> dict:
    """Summarize with every corpus item in the primary denominator."""
    by_format: dict[str, list[dict]] = defaultdict(list)
    by_network: dict[str, list[dict]] = defaultdict(list)
    by_query_type: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_format[str(record.get("answer_format", "multiple_choice"))].append(record)
        by_network[_network_id(record)].append(record)
        by_query_type[str(record.get("query_type", "unknown"))].append(record)
    return {
        **_bucket(records, results),
        "by_format": {key: _bucket(value, results) for key, value in sorted(by_format.items())},
        "by_network": {key: _bucket(value, results) for key, value in sorted(by_network.items())},
        "by_query_type": {key: _bucket(value, results) for key, value in sorted(by_query_type.items())},
    }


def _json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_extraction_receipt_archive(scope_dir: Path, outcomes: list[dict]) -> Path:
    """Archive one native three-channel receipt for every extracted holder."""
    holders: dict[str, dict] = {}
    for outcome in outcomes:
        holder = str(outcome.get("holder") or "").strip()
        if not holder:
            raise ValueError("receipt holder is required")
        if holder in holders:
            raise ValueError(f"duplicate holder in extraction receipts: {holder}")
        receipt = outcome.get("receipt")
        if not isinstance(receipt, dict) or not isinstance(receipt.get("channels"), dict):
            raise ValueError(f"receipt missing for holder: {holder}")
        channels = receipt["channels"]
        if set(channels) != {"belief", "general_fact", "episodic"}:
            raise ValueError(f"receipt channels incomplete for holder: {holder}")
        holders[holder] = receipt
    path = scope_dir / "extraction.receipts.json"
    _json_write(path, {"schema_version": 1, "holders": holders})
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _run_fingerprint(work: Path, identity: dict) -> dict:
    return {
        "corpus_sha256": identity["corpus_sha256"],
        "config_sha256": identity["config_sha256"],
        "scope_manifest_sha256": identity["scope_manifest_sha256"],
        "core_sha256": identity["core_sha256"],
        "frozen_files_sha256": hashlib.sha256(
            json.dumps(identity["frozen_files"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }


def _verify_identity(work: Path, config: dict) -> dict:
    validate_answer_policy(config)
    for key, expected in {"created_at": "2026-06-01T00:00:00Z",
                          "max_retries": 0,
                          "embedding_max_batch_inputs": 10}.items():
        if config.get(key) != expected:
            raise RuntimeError(f"unsupported baseline configuration: {key}")
    if config.get("lifecycle") not in ("immediate", "sleep"):
        raise RuntimeError("unsupported baseline configuration: lifecycle")
    identity = json.loads((work / "identity.json").read_text(encoding="utf-8"))
    if str(identity.get("core_sha256")) != str(config.get("core_sha256")):
        raise RuntimeError("config/identity frozen core hash mismatch")
    corpus_hash = _sha256(work / "corpus.jsonl")
    if corpus_hash != str(identity.get("corpus_sha256")):
        raise RuntimeError("corpus hash differs from identity.json; re-freeze before running")
    if _sha256(work / "config.json") != str(identity.get("config_sha256")):
        raise RuntimeError("config hash differs from identity.json; re-freeze before running")
    if _sha256(work / "scope-manifest.json") != str(identity.get("scope_manifest_sha256")):
        raise RuntimeError("scope manifest hash differs from identity.json; re-freeze before running")
    frozen = work / "frozen"
    for relative, expected in identity.get("frozen_files", {}).items():
        path = frozen / relative
        if not path.is_file() or _sha256(path) != expected:
            raise RuntimeError(f"frozen file hash mismatch: {relative}")
    return _run_fingerprint(work, identity)


def _frozen_imports(work: Path, config: dict, identity: dict):
    frozen = (work / "frozen").resolve()
    frozen_python, frozen_scripts = str(frozen / "python"), str(frozen / "scripts")
    for entry in (frozen_scripts, frozen_python):
        while entry in sys.path:
            sys.path.remove(entry)
    sys.path[:0] = [frozen_python, frozen_scripts]
    module_names = tuple(name for name in sys.modules if name == "starling" or name.startswith("starling.")) + (
        "eval_judge_audit", "eval_ladder", "eval_ladder_pipeline", "eval_longmemeval")
    for name in module_names:
        loaded = sys.modules.get(name)
        if loaded is not None and not str(getattr(loaded, "__file__", "")).startswith(str(frozen)):
            raise RuntimeError(f"non-frozen module already loaded: {name}")
    # The project's editable-install finder precedes PathFinder and otherwise
    # redirects even a frozen sys.path to the live checkout. Disable only this
    # project's redirector in the dedicated evaluation worker.
    sys.meta_path[:] = [finder for finder in sys.meta_path
                       if type(finder).__module__ != "_starling_memory_editable"]
    from starling import _core, runtime
    import eval_judge_audit as audit
    import eval_ladder as ladder
    import eval_ladder_pipeline as pipe
    import eval_longmemeval as longmem
    core_file = Path(_core.__file__)
    expected = str(config["core_sha256"])
    if _sha256(core_file) != expected:
        raise RuntimeError(f"frozen _core hash mismatch: {core_file}")
    for module in (sys.modules["starling"], _core, runtime, audit, ladder, pipe, longmem):
        module_path = Path(module.__file__).resolve()
        try:
            relative = module_path.relative_to(frozen).as_posix()
        except ValueError as exc:
            raise RuntimeError(f"module loaded outside frozen tree: {module.__name__}") from exc
        if _sha256(module_path) != identity["frozen_files"].get(relative):
            raise RuntimeError(f"frozen module hash mismatch: {relative}")
    return _core, runtime, audit, ladder, pipe, longmem


@contextmanager
def _provider_environment(key_env: str, endpoint: str):
    """Construct an env-backed native config without retaining a secret."""
    old_key, old_base = os.environ.get("OPENAI_API_KEY"), os.environ.get("OPENAI_BASE_URL")
    if key_env:
        key = os.environ.get(key_env)
        if not key:
            raise RuntimeError(f"missing required environment variable {key_env}")
        os.environ["OPENAI_API_KEY"] = key
    if endpoint:
        os.environ["OPENAI_BASE_URL"] = endpoint
    try:
        yield
    finally:
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key
        if old_base is None:
            os.environ.pop("OPENAI_BASE_URL", None)
        else:
            os.environ["OPENAI_BASE_URL"] = old_base


def _make_native_adapters(core: Any, config: dict) -> tuple[Any, Any, Any, Any]:
    with _provider_environment("DASHSCOPE_API_KEY", str(config["extract_endpoint"])):
        extract_cfg = core.OpenAIAdapterConfig.from_env()
        extract_cfg.model = str(config["extract_model"])
        extract_cfg.timeout_ms, extract_cfg.max_retries = int(config["timeout_ms"]), 0
        extract_cfg.max_tokens, extract_cfg.json_object_output = int(config["extract_max_tokens"]), False
        extract_cfg.enable_thinking = config.get("extract_enable_thinking")
        extract_llm = core.OpenAIAdapter(extract_cfg)
        old_batch = os.environ.get("EMBEDDING_MAX_BATCH")
        os.environ["EMBEDDING_MAX_BATCH"] = str(config["embedding_max_batch_inputs"])
        try:
            embedding_cfg = core.OpenAIEmbeddingConfig.from_env()
            embedding_cfg.base_url = str(config["embedding_endpoint"])
            embedding_cfg.model, embedding_cfg.dim = str(config["embedding_model"]), int(config["embedding_dim"])
            embedding_cfg.timeout_ms, embedding_cfg.max_retries = int(config["timeout_ms"]), 0
            embedder = core.OpenAIEmbeddingAdapter(embedding_cfg)
        finally:
            if old_batch is None:
                os.environ.pop("EMBEDDING_MAX_BATCH", None)
            else:
                os.environ["EMBEDDING_MAX_BATCH"] = old_batch
    with _provider_environment(str(config["answer_key_env"]), str(config["answer_endpoint"])):
        answer_cfg = core.OpenAIAdapterConfig.from_env()
        answer_cfg.model = str(config["answer_model"])
        answer_cfg.enable_thinking = config.get("answer_enable_thinking")
        answer_cfg.timeout_ms, answer_cfg.max_retries = int(config["timeout_ms"]), 0
        answer_cfg.max_tokens, answer_cfg.json_object_output = int(config["answer_max_tokens"]), False
        answer_llm = core.OpenAIAdapter(answer_cfg)
        judge_cfg = core.OpenAIAdapterConfig.from_env()
        judge_cfg.model = str(config["answer_model"])
        judge_cfg.timeout_ms, judge_cfg.max_retries = int(config["timeout_ms"]), 0
        judge_cfg.max_tokens, judge_cfg.json_object_output = int(config["judge_max_tokens"]), False
        judge_llm = core.OpenAIAdapter(judge_cfg)
    return extract_llm, embedder, answer_llm, judge_llm


def _response_payload(response: Any) -> dict:
    raw = json.loads(response.to_json())
    return {"response": raw, "raw_xml": str(getattr(response, "raw_xml", "")),
            "raw_completion": str(getattr(response, "raw_completion", ""))}


def response_text(response: Any, stage: str) -> tuple[dict, str, str | None]:
    """Keep the full native receipt while using legacy raw_xml answer semantics."""
    payload = _response_payload(response)
    text = payload["raw_xml"].strip()
    if not bool(getattr(response, "ok", False)):
        return payload, text, f"{stage} response not ok: {getattr(response, 'error', '')}"
    if getattr(response, "error", ""):
        return payload, text, f"{stage} response error: {getattr(response, 'error', '')}"
    if not text:
        return payload, text, f"{stage} response empty"
    return payload, text, None


def _database_stats(db_path: Path) -> dict:
    tables = ("extraction_attempt", "pipeline_run", "statements", "statement_vectors")
    stats: dict[str, int | None | str] = {}
    with sqlite3.connect(db_path) as conn:
        for table in tables:
            try:
                stats[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.DatabaseError:
                stats[table] = None
                stats[f"{table}_error"] = "table unavailable"
    return stats


class BudgetLedger:
    """Durable request reservations.  Unknown/crashed work stays reserved."""
    def __init__(self, path: Path, budget: int):
        self.path, self.budget = Path(path), int(budget)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS reservations ("
                         "id INTEGER PRIMARY KEY, scope TEXT, stage TEXT, upper_bound INTEGER, "
                         "actual INTEGER, state TEXT NOT NULL)")

    def reserve(self, scope: str, stage: str, upper_bound: int) -> dict:
        if upper_bound < 0:
            raise ValueError("upper_bound must be non-negative")
        with sqlite3.connect(self.path, isolation_level=None) as conn:
            conn.execute("BEGIN IMMEDIATE")
            used = conn.execute("SELECT COALESCE(SUM(CASE WHEN state='settled' THEN actual ELSE upper_bound END),0) "
                                "FROM reservations WHERE state IN ('reserved','settled','charged_upper')").fetchone()[0]
            if int(used) + int(upper_bound) > self.budget:
                conn.execute("COMMIT")
                return {"state": "blocked", "remaining": self.budget - int(used)}
            cursor = conn.execute("INSERT INTO reservations(scope,stage,upper_bound,actual,state) VALUES(?,?,?,?,?)",
                                  (scope, stage, int(upper_bound), None, "reserved"))
            conn.execute("COMMIT")
        return {"id": int(cursor.lastrowid), "state": "reserved", "upper_bound": int(upper_bound)}

    def reserve_wait(self, scope: str, stage: str, upper_bound: int) -> dict:
        deadline = time.monotonic() + 600
        while True:
            result = self.reserve(scope, stage, upper_bound)
            if result["state"] != "blocked" or not self.snapshot()["reserved"]:
                return result
            if time.monotonic() >= deadline:
                return result
            time.sleep(1)

    def charge_upper(self, reservation_id: int) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE reservations SET state='charged_upper' WHERE id=? AND state='reserved'",
                         (reservation_id,))

    def settle(self, reservation_id: int, actual: int) -> None:
        if actual < 0:
            raise ValueError("actual must be non-negative")
        with sqlite3.connect(self.path, isolation_level=None) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT upper_bound,state FROM reservations WHERE id=?", (reservation_id,)).fetchone()
            if row is None:
                raise RuntimeError("unknown reservation")
            if row[1] != "reserved":
                raise RuntimeError("reservation is not active")
            if int(actual) > int(row[0]):
                raise RuntimeError("actual request count exceeds reservation")
            conn.execute("UPDATE reservations SET actual=?,state='settled' WHERE id=?", (int(actual), reservation_id))
            conn.execute("COMMIT")

    def snapshot(self) -> dict:
        with sqlite3.connect(self.path) as conn:
            used, reserved = conn.execute(
                "SELECT COALESCE(SUM(CASE WHEN state='settled' THEN actual ELSE upper_bound END),0),"
                "COALESCE(SUM(CASE WHEN state='reserved' THEN upper_bound ELSE 0 END),0) "
                "FROM reservations WHERE state IN ('reserved','settled','charged_upper')").fetchone()
            upper = conn.execute("SELECT COALESCE(SUM(upper_bound),0) FROM reservations WHERE state='charged_upper'").fetchone()[0]
        return {"budget": self.budget, "committed": int(used) - int(reserved),
                "reserved": int(reserved), "charged_upper": int(upper), "remaining": self.budget - int(used)}


class BudgetBlocked(RuntimeError):
    pass


def apply_lifecycle(core: Any, adapter: Any, config: dict) -> dict:
    """选择已实现的原生生命周期阶段；不在编排层改变声明状态。"""
    mode = config.get("lifecycle", "immediate")
    if mode == "immediate":
        return {"mode": mode, "stats": {}}
    if mode != "sleep":
        raise ValueError(f"unsupported lifecycle: {mode!r}")
    stats = core.ReplayScheduler(adapter).run_sleep(str(config["query_time"]))
    return {"mode": mode, "stats": {name: getattr(stats, name) for name in (
        "sampled", "compressed", "abstracted", "gist_candidates", "gist_failed",
        "gist_gated", "forced_consolidated", "ttl_archived", "replay_batch_id")}}


def history_holders(history: list[dict]) -> list[str]:
    """公共会话观察者协议提供的显式人物清单，不扫描租户私有记忆。"""
    return sorted({str(turn["speaker"]) for turn in history})


def retain_history_sources(core: Any, adapter: Any, history: list[dict], created_at: str,
                           preserve_invalid_time: bool = False) -> dict:
    """数据集字段映射；分组、验证、幂等和来源持久化全部在C++。"""
    turns = [{"speaker": turn["speaker"], "text": turn["text"],
              "turn_id": turn.get("turn_id"),
              "session_id": (str(turn["session_index"]) if turn.get("session_index") is not None
                             else turn.get("session_id")),
              "turn_index": turn.get("message_index", turn.get("turn_index")),
              "observed_at": turn.get("observed_at")} for turn in history]
    extra = (True,) if preserve_invalid_time else ()
    return json.loads(core.retain_source_turns(adapter, "default", history_holders(history),
                                              json.dumps(turns, ensure_ascii=False), created_at, *extra))


def _build_extraction_config(config: dict):
    """构造唯一的 Python 配置载体，再由 C++ 完成语义校验。

    运行器只把实验开关映射到 ``ExtractionConfig``；谓词目录、证据规则、
    admission 和持久化仍由 native policy 执行。默认值必须保持 legacy 行为，
    以便来源臂和既有归档不因运行器升级而改变。
    """
    from starling.extractor.config import ExtractionConfig

    return ExtractionConfig(
        semantic_claim_contract=bool(config.get("semantic_claim_contract", False)),
        preserve_text_objects=bool(config.get("preserve_text_objects", False)),
        claim_allow_code_fence=bool(config.get("claim_allow_code_fence", False)),
        claim_protocol_retry_budget=int(config.get("claim_protocol_retry_budget", 0)),
        claim_output_mode=str(config.get("claim_output_mode", "legacy")),
        claim_batch_size=int(config.get("claim_batch_size", 0)),
        claim_batch_target_units=bool(config.get("claim_batch_target_units", False)),
    )


def question_request_bound(record: dict, config: dict, frozen_db: Path | None) -> int:
    """按冻结的检索模式预约外部请求；不估算原生评分或选择行为。"""
    mode = config.get("recall_mode")
    if mode is None:
        with sqlite3.connect(frozen_db) as conn:
            queries = max(1, conn.execute("SELECT COUNT(DISTINCT holder_id) FROM statements "
                                         "WHERE tenant_id='default'").fetchone()[0])
    elif mode in ("sources", "full"):
        queries = 0
    elif mode in ("statements", "hybrid"):
        queries = len(history_holders(record["history"]))
    else:
        raise ValueError(f"unsupported recall_mode: {mode!r}")
    free_text = record.get("answer_format", "multiple_choice") != "multiple_choice"
    return queries + 1 + int(free_text) + int(free_text and config.get("answer_policy") == "evidence_v1")


def _build_scope_database(group: dict, scope_dir: Path, modules: tuple, config: dict,
                          adapters: tuple, ledger: BudgetLedger,
                          extraction_reservation: dict) -> tuple[Path, dict]:
    core, runtime, _, ladder, pipe, _ = modules
    extract_llm, embedder, _, _ = adapters
    db_path = scope_dir / "network.db"
    rt = runtime._build_local_store_sqlite_runtime(db_path)
    rt.start()
    sources = (retain_history_sources(core, rt.adapter, group["history"], str(config["created_at"]),
                                     preserve_invalid_time=config.get("preserve_invalid_time", False))
               if config.get("retain_sources", False) else None)
    original = ladder._build_extract_llm
    ladder._build_extract_llm = lambda *_args, **_kwargs: extract_llm
    try:
        extraction = ladder.make_real_extract_fn(
            core, str(config["extract_model"]), "dashscope",
            extraction_config=_build_extraction_config(config),
            preserve_invalid_time=bool(config.get("preserve_invalid_time", False)),
            holder_isolation=bool(config.get("holder_isolation", False)))(rt.adapter, {
                "history": group["history"], "item_id": group["group_id"],
            }, str(config["extract_model"]))
    finally:
        ladder._build_extract_llm = original
        ledger.charge_upper(extraction_reservation["id"])
    _json_write(scope_dir / "extraction.completed.json", {"extraction": extraction})
    write_extraction_receipt_archive(scope_dir, extraction)
    expected_holders = history_holders(group["history"])
    by_holder = {str(row.get("holder")): row for row in extraction}
    holder_failures = [
        {"holder": holder,
         "failure_category": str(by_holder[holder].get("failure_category") or "unknown"),
         "failure_detail": str(by_holder[holder].get("failure_detail") or "")}
        for holder in expected_holders
        if holder not in by_holder or by_holder[holder].get("extraction_failed") is True
    ]
    holder_complete = [
        holder for holder in expected_holders
        if holder in by_holder and by_holder[holder].get("extraction_failed") is False
    ]
    scope_state = "complete" if not holder_failures and set(by_holder) == set(expected_holders) else "partial"
    replay = apply_lifecycle(core, rt.adapter, config)
    stats_before_embedding = _database_stats(db_path)
    statement_count = int(stats_before_embedding.get("statements") or 0)
    embedding_reservation = ledger.reserve_wait(group["group_id"], "scope_embedding",
                                           _embedding_reservation(statement_count))
    if embedding_reservation["state"] == "blocked":
        raise BudgetBlocked("budget_blocked_before_scope_embedding")
    index = core.SqliteBlobVectorIndex()
    before_requests = int(embedder.request_count)
    embedding = pipe.embed_seeded(core, rt.adapter, embedder, index, str(config["query_time"]), max_ticks=200)
    actual_embedding_requests = int(embedder.request_count) - before_requests
    ledger.settle(embedding_reservation["id"], actual_embedding_requests)
    if embedding.get("final_health", {}).get("complete") is not True:
        raise RuntimeError(f"final embedding health incomplete: {embedding}")
    frozen = scope_dir / "frozen.db"
    with sqlite3.connect(db_path) as source, sqlite3.connect(frozen) as destination:
        source.backup(destination)
    return frozen, {"extraction": extraction, "scope_state": scope_state,
                    "holder_complete": holder_complete, "holder_failures": holder_failures,
                    "replay": replay, "embedding": embedding, "sources": sources,
                    "embedding_request_count": actual_embedding_requests,
                    "database": _database_stats(db_path)}


def validate_answer_policy(config: dict) -> str:
    """Reject invalid combinations before retrieval can spend a provider request."""
    policy = config.get("answer_policy", "legacy")
    if policy not in ("legacy", "grounded_v1", "grounded_compact_v1", "evidence_v1", "synthesis_v1", "grounded_memory_v1", "grounded_memory_v2"):
        raise ValueError("unknown answer_policy")
    if policy in ("grounded_memory_v1", "grounded_memory_v2"):
        if config.get("recall_mode") not in ("sources", "hybrid"):
            raise ValueError(f"{policy} requires sources or hybrid recall")
        return policy
    if policy != "legacy" and config.get("recall_mode") != "sources":
        raise ValueError(f"{policy} requires sources recall")
    return policy


def answer_prompt(core, ladder, record: dict, recall: dict, config: dict) -> str:
    """Only route the policy; all new evidence guidance lives in the native core."""
    policy = validate_answer_policy(config)
    if policy == "grounded_memory_v1" and record.get("answer_format", "multiple_choice") != "multiple_choice":
        return core.grounded_memory_answer_prompt(str(record["question"]), json.dumps(recall, ensure_ascii=False))
    if policy == "grounded_memory_v2" and record.get("answer_format", "multiple_choice") != "multiple_choice":
        return core.compact_grounded_memory_answer_prompt(str(record["question"]), json.dumps(recall, ensure_ascii=False))
    if policy == "synthesis_v1" and record.get("answer_format", "multiple_choice") != "multiple_choice":
        return core.synthesis_source_answer_prompt(str(record["question"]), recall["block"])
    if policy == "evidence_v1" and record.get("answer_format", "multiple_choice") != "multiple_choice":
        return core.source_evidence_prompt(str(record["question"]), recall["block"])
    if policy == "grounded_compact_v1" and record.get("answer_format", "multiple_choice") != "multiple_choice":
        return core.compact_source_answer_prompt(str(record["question"]), recall["block"])
    if policy == "grounded_v1" and record.get("answer_format", "multiple_choice") != "multiple_choice":
        return core.grounded_source_answer_prompt(str(record["question"]), recall["block"])
    recalled = [line.lstrip("- ").strip() for line in recall["block"].splitlines() if line.strip()]
    return (ladder._ladder_prompt(record, recalled)
            if record.get("answer_format", "multiple_choice") == "multiple_choice"
            else ladder._ladder_prompt_free(record, recalled))


def _answer_question(record: dict, database: Path, modules: tuple, config: dict,
                     embedder: Any, answer_llm: Any, judge_llm: Any) -> dict:
    core, runtime, audit, ladder, pipe, longmem = modules
    rt = runtime._build_local_store_sqlite_runtime(database)
    rt.start()
    index = core.SqliteBlobVectorIndex()
    started = time.perf_counter()
    before = int(getattr(embedder, "request_count", 0))
    receipt: dict[str, Any] = {"item_id": str(record["item_id"]), "status": "technical_failure",
                               "correct": False, "stages": {}}
    try:
        query_started = time.perf_counter()
        validate_answer_policy(config)
        mode = config.get("recall_mode")
        if mode is None or mode == "full":
            recall = pipe.recall_block(core, "S_full" if mode == "full" else "S_star",
                                      adapter=rt.adapter, embedder=embedder, index=index,
                                      question=str(record["question"]), history=list(record.get("history") or []),
                                      k=int(config["k"]), now_iso=str(config["query_time"]))
        else:
            recall = pipe.recall_observer_block(core, adapter=rt.adapter, embedder=embedder, index=index,
                question=str(record["question"]), allowed_holders=history_holders(record["history"]),
                mode=mode, k=int(config["k"]), now_iso=str(config["query_time"]),
                max_context_bytes=int(config["max_context_bytes"]),
                include_unknown_time=config.get("include_unknown_time", False),
                source_strategy=config.get("source_strategy", "bm25"),
                **{key:config[key] for key in ("source_seed_k", "source_seed_max_context_bytes", "source_dialogue_radius",
                                               "min_source_items")
                   if key in config})
        receipt["recall"] = recall
    except Exception as exc:  # one question is always a scored zero, never a group abort
        receipt.update(status="query_failure", error=f"{type(exc).__name__}: {exc}", correct=False)
        receipt["stages"]["query"] = {"seconds": time.perf_counter() - started,
                                      "error": receipt["error"]}
        receipt.update(terminal=True, elapsed_seconds=time.perf_counter() - started,
                       embedding_request_delta=int(getattr(embedder, "request_count", 0)) - before,
                       database=_database_stats(database))
        return receipt
    receipt["stages"]["query"] = {"seconds": time.perf_counter() - query_started}

    answer_started = time.perf_counter()
    try:
        prompt = answer_prompt(core, ladder, record, recall, config)
        if config.get("answer_policy") == "evidence_v1" and record.get("answer_format", "multiple_choice") != "multiple_choice":
            native = core.answer_with_evidence(str(record["question"]), recall["block"], answer_llm)
            response = native.answer_response
            receipt.update(evidence=_response_payload(native.evidence_response),
                           evidence_prompt=native.evidence_prompt, final_prompt=native.answer_prompt,
                           evidence_validation=json.loads(native.validation_json),
                           evidence_fallback=native.fallback, evidence_fallback_reason=native.fallback_reason,
                           budget_unknown=native.budget_unknown)
        else:
            response = answer_llm.extract(prompt, "")
        answer, answer_text, answer_error = response_text(response, "answer")
        receipt.update(prompt=prompt, answer=answer)
        receipt["stages"]["answer"] = {"seconds": time.perf_counter() - answer_started,
                                       "error": answer_error}
        if answer_error:
            receipt.update(status="answer_failure", error=answer_error)
            raise StopIteration
    except StopIteration:
        pass
    except Exception as exc:
        receipt.update(status="answer_failure", error=f"{type(exc).__name__}: {exc}", budget_unknown=True)
        receipt["stages"]["answer"] = {"seconds": time.perf_counter() - answer_started,
                                       "error": receipt["error"]}
    else:
        if record.get("answer_format", "multiple_choice") == "multiple_choice":
            try:
                predicted = longmem._parse_option_index(answer_text, len(record["options"]))
                if predicted is None:
                    raise ValueError("option parser returned None")
                receipt.update(status="ok", prediction=predicted,
                               correct=predicted == int(record["answer"]))
            except (TypeError, ValueError) as exc:
                receipt.update(status="invalid_answer", error=f"{type(exc).__name__}: {exc}")
        else:
            judge_started = time.perf_counter()
            try:
                judge_prompt = audit._judge_prompt(str(record["question"]), str(record["answer"]), answer_text)
                judge_response = judge_llm.extract(judge_prompt, "")
                judge, judge_text, judge_error = response_text(judge_response, "judge")
                receipt.update(judge_prompt=judge_prompt, judge=judge)
                receipt["stages"]["judge"] = {"seconds": time.perf_counter() - judge_started,
                                                  "error": judge_error}
                if judge_error:
                    receipt.update(status="judge_failure", error=judge_error)
                else:
                    receipt.update(status="ok", correct=audit._parse_judge_verdict(judge_text))
            except Exception as exc:
                receipt.update(status="judge_failure", error=f"{type(exc).__name__}: {exc}", budget_unknown=True)
                receipt["stages"]["judge"] = {"seconds": time.perf_counter() - judge_started,
                                                  "error": receipt["error"]}
    receipt.update(
        terminal=True,
        elapsed_seconds=time.perf_counter() - started,
        embedding_request_delta=int(getattr(embedder, "request_count", 0)) - before,
        native_attempt_count=sum(_response_attempts(receipt.get(stage)) for stage in ("evidence", "answer", "judge")),
        database=_database_stats(database),
    )
    return receipt


def _exclusive_started(path: Path, payload: dict) -> bool:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    return True


def _estimate_group_requests(group: dict) -> int:
    holders = len({str(turn.get("speaker") or "unknown") for turn in group["history"]})
    # Three extraction channels with a maximum of three native attempts each,
    # then one query embedding per holder plus answer/judge per question.
    return holders * 9 + len(group["records"]) * (holders + 2)


def _embedding_reservation(statement_count: int) -> int:
    """Worker worst case: three logical passes plus permanent batch fallback."""
    n = max(0, int(statement_count))
    return min(200 * 36, 3 * n + 4 * ((3 * n + 31) // 32))


def _response_attempts(payload: dict | None) -> int:
    if not payload:
        return 0
    raw = payload.get("response", {})
    return int(raw.get("attempt_count", len(raw.get("http_attempts", [])) or 0))


def offline_native_smoke(work: Path | str, scratch: Path) -> dict:
    """Exercise frozen runtime, FakeLLM, StubEmbedding, snapshot, and query offline."""
    work, scratch = Path(work).resolve(), Path(scratch)
    config = json.loads((work / "config.json").read_text(encoding="utf-8"))
    fingerprint = _verify_identity(work, config)
    identity = json.loads((work / "identity.json").read_text(encoding="utf-8"))
    core, runtime, audit, ladder, pipe, longmem = _frozen_imports(work, config, identity)
    source = scratch / "source.db"
    rt = runtime._build_local_store_sqlite_runtime(source)
    rt.start()
    history = [{"speaker": "Ada", "text": "Ada chose option zero.",
                "observed_at": "2026-01-01T00:00:00Z"}]
    extractor = core.FakeLLMAdapter()
    extractor.set_default_response("[]")
    original = ladder._build_extract_llm
    ladder._build_extract_llm = lambda *_args, **_kwargs: extractor
    try:
        outcomes = ladder.make_real_extract_fn(core)(rt.adapter, {"history": history}, "offline")
    finally:
        ladder._build_extract_llm = original
    three_phase_database = _database_stats(source)
    pipe.seed_history_statements(str(source), "offline", history)
    embedder, index = core.StubEmbeddingAdapter(8), core.SqliteBlobVectorIndex()
    embedding = pipe.embed_seeded(core, rt.adapter, embedder, index, str(config["query_time"]))
    frozen = scratch / "frozen.db"
    with sqlite3.connect(source) as source_conn, sqlite3.connect(frozen) as frozen_conn:
        source_conn.backup(frozen_conn)
    frozen_hash_before = _sha256(frozen)
    question_db = scratch / "question.db"
    shutil.copyfile(frozen, question_db)
    extractor = core.FakeLLMAdapter()
    extractor.set_default_response("<statements />")
    extraction, _, extraction_error = response_text(extractor.extract("offline extraction", ""), "extract")
    answerer, judge = core.FakeLLMAdapter(), core.FakeLLMAdapter()
    answerer.set_default_response("Ada")
    judge.set_default_response("YES")
    result = _answer_question({"item_id": "offline-question", "history": history,
                               "question": "Who chose the option?", "options": [],
                               "answer": "Ada", "answer_format": "short_answer"},
                              question_db, (core, runtime, audit, ladder, pipe, longmem),
                              config, embedder, answerer, judge)
    return {"fingerprint": fingerprint, "extraction": extraction,
            "three_phase_outcomes": outcomes, "three_phase_database": three_phase_database,
            "extraction_error": extraction_error, "embedding": embedding, "result": result,
            "frozen_unchanged": frozen_hash_before == _sha256(frozen)}


def _run_group(work_text: str, group: dict, config: dict, identity: dict,
               fingerprint: dict) -> dict:
    work = Path(work_text)
    scope_dir = work / "runs" / group["group_id"]
    questions = scope_dir / "questions"
    scope_dir.mkdir(parents=True, exist_ok=True)
    questions.mkdir(exist_ok=True)
    print(f"[scope] {group['network_id']}/{group['evaluation_scope']} "
          f"({len(group['records'])} questions)", flush=True)
    _json_write(scope_dir / "ingestion.json", {
        "network_id": group["network_id"], "evaluation_scope": group["evaluation_scope"],
        "history_sha256": group["history_sha256"],
        "records": [ingestion_record(record) for record in group["records"]],
        "fingerprint": fingerprint,
        "request_upper_bound": _estimate_group_requests(group),
    })
    states = question_states(questions, [str(record["item_id"]) for record in group["records"]], fingerprint)
    result_rows: list[dict] = []
    for record in group["records"]:
        item_id = str(record["item_id"])
        stable = _stable_id(item_id)
        result_path = questions / f"{stable}.json"
        if states[item_id] == "terminal":
            result_rows.append(json.loads(result_path.read_text(encoding="utf-8")))
        elif states[item_id] == "incomplete":
            result_rows.append({"item_id": item_id, "status": "incomplete", "correct": False})
    pending = [record for record in group["records"] if states[str(record["item_id"])] == "pending"]
    if not pending:
        return {"group": group["group_id"], "results": result_rows, "summary": summarize(group["records"], result_rows)}
    current_scope_state = scope_state(scope_dir, fingerprint)
    if current_scope_state == "incomplete":
        result_rows.extend({"item_id": str(record["item_id"]), "status": "incomplete", "correct": False}
                           for record in pending)
        return {"group": group["group_id"], "results": result_rows,
                "summary": summarize(group["records"], result_rows)}
    ledger = BudgetLedger(work / "request-ledger.sqlite", int(config["http_budget"]))
    extraction_reservation: dict | None = None
    if current_scope_state != "terminal":
        extraction_reservation = ledger.reserve_wait(
            group["group_id"], "scope_extraction",
            9 * len({str(t.get("speaker") or "unknown") for t in group["history"]}))
        if extraction_reservation["state"] == "blocked":
            return {"group": group["group_id"], "results": result_rows,
                    "budget_blocked": True, "summary": summarize(group["records"], result_rows)}
        if not _exclusive_started(scope_dir / "scope.started", {
                "group": group["group_id"], "fingerprint": fingerprint, "started_at": time.time(),
                "reservation": extraction_reservation}):
            result_rows.extend({"item_id": str(record["item_id"]), "status": "incomplete", "correct": False}
                               for record in pending)
            return {"group": group["group_id"], "results": result_rows,
                    "summary": summarize(group["records"], result_rows)}
    modules = _frozen_imports(work, config, identity)
    adapters = _make_native_adapters(modules[0], config)
    frozen_db = scope_dir / "frozen.db"
    try:
        metadata = json.loads((scope_dir / "scope.json").read_text(encoding="utf-8")) if frozen_db.exists() else None
    except (OSError, json.JSONDecodeError):
        metadata = None
    if metadata is None:
        ingestion_started = time.perf_counter()
        try:
            frozen_db, metadata = _build_scope_database(group, scope_dir, modules, config, adapters, ledger,
                                                       extraction_reservation)
            metadata["elapsed_seconds"] = time.perf_counter() - ingestion_started
            _json_write(scope_dir / "scope.json", {"group": group["group_id"], "fingerprint": fingerprint,
                                                     "extraction_reservation": extraction_reservation,
                                                     **metadata})
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if extraction_reservation is not None:
                ledger.charge_upper(extraction_reservation["id"])
            _json_write(scope_dir / "scope.failure.json", {
                "group": group["group_id"], "fingerprint": fingerprint, "error": error,
                "elapsed_seconds": time.perf_counter() - ingestion_started,
                "database": _database_stats(scope_dir / "network.db"),
                "embedding_request_count": getattr(adapters[1], "request_count", None),
            })
            if isinstance(exc, BudgetBlocked):
                result_rows.extend({"item_id": str(r["item_id"]), "status": "incomplete", "correct": False}
                                   for r in pending)
                return {"group": group["group_id"], "results": result_rows,
                        "budget_blocked": True, "summary": summarize(group["records"], result_rows)}
            for record in pending:
                item_id, stable = str(record["item_id"]), _stable_id(str(record["item_id"]))
                _json_write(questions / f"{stable}.json", {"item_id": item_id, "status": "ingestion_failure",
                                                              "fingerprint": fingerprint, "terminal": True,
                                                              "correct": False, "error": error,
                                                              "database": _database_stats(scope_dir / "network.db")})
                result_rows.append(json.loads((questions / f"{stable}.json").read_text(encoding="utf-8")))
            return {"group": group["group_id"], "results": result_rows, "summary": summarize(group["records"], result_rows)}
    for record in pending:
        item_id, stable = str(record["item_id"]), _stable_id(str(record["item_id"]))
        started, result_path = questions / f"{stable}.started", questions / f"{stable}.json"
        reservation = ledger.reserve_wait(group["group_id"], f"question:{stable}",
                                         question_request_bound(record, config, frozen_db))
        if reservation["state"] == "blocked":
            result_rows.append({"item_id": item_id, "status": "budget_blocked", "correct": False})
            continue
        if not _exclusive_started(started, {"item_id": item_id, "fingerprint": fingerprint,
                                            "started_at": time.time(), "reservation": reservation}):
            result_rows.append({"item_id": item_id, "status": "incomplete", "correct": False})
            continue
        question_db = questions / f"{stable}.db"
        shutil.copyfile(frozen_db, question_db)
        try:
            result = _answer_question(record, question_db, modules, config,
                                      adapters[1], adapters[2], adapters[3])
        except Exception as exc:
            # The request boundary is now uncertain: leave the reservation in
            # place, but carry on to independently runnable questions.
            result = {"item_id": item_id, "status": "technical_failure", "terminal": True,
                      "correct": False, "error": f"{type(exc).__name__}: {exc}",
                      "budget_unknown": True, "database": _database_stats(question_db)}
        else:
            if result.get("budget_unknown"):
                ledger.charge_upper(reservation["id"])
            else:
                ledger.settle(reservation["id"], int(result["embedding_request_delta"]) +
                              int(result.get("native_attempt_count", 0)))
        result["fingerprint"] = fingerprint
        _json_write(result_path, result)
        result_rows.append(result)
    return {"group": group["group_id"], "results": result_rows, "summary": summarize(group["records"], result_rows)}


@contextmanager
def _work_lock(work: Path):
    lock_path = work / ".run-socialmem-baseline.lock"
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_running_summary(work: Path, config: dict, fingerprint: dict,
                           records: list[dict], outcomes: list[dict], estimate: int) -> None:
    results = [result for outcome in outcomes for result in outcome["results"]]
    _json_write(work / "summary.json", {
        "state": "running", "config": {key: value for key, value in config.items() if "key" not in key.lower()},
        "fingerprint": fingerprint, "basic_request_estimate": estimate,
        "ledger": BudgetLedger(work / "request-ledger.sqlite", int(config["http_budget"])).snapshot(),
        "groups": outcomes, "summary": summarize(records, results),
    })


def run(work: Path | str, groups: list[dict] | None = None, workers: int = 4) -> dict:
    """Run prepared groups in isolated worker processes and write a full summary."""
    work = Path(work)
    config = json.loads((work / "config.json").read_text(encoding="utf-8"))
    fingerprint = _verify_identity(work, config)
    identity = json.loads((work / "identity.json").read_text(encoding="utf-8"))
    all_records = _read_jsonl(work / "corpus.jsonl")
    canonical = prepare_groups(all_records)
    groups = canonical if groups is None else validate_groups(canonical, groups)
    estimate = sum(_estimate_group_requests(group) for group in groups)
    with _work_lock(work):
        if workers <= 1:
            outcomes = []
            for group in groups:
                outcomes.append(_run_group(str(work), group, config, identity, fingerprint))
                _write_running_summary(work, config, fingerprint, all_records, outcomes, estimate)
        else:
            with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(_run_group, str(work), group, config, identity, fingerprint)
                           for group in groups]
                outcomes = []
                for future in concurrent.futures.as_completed(futures):
                    outcomes.append(future.result())
                    _write_running_summary(work, config, fingerprint, all_records, outcomes, estimate)
    results = [result for outcome in outcomes for result in outcome["results"]]
    summary = summarize(all_records, results)
    report = {"state": "complete" if summary["executed"] == len(all_records) else "partial",
              "config": {key: value for key, value in config.items() if "key" not in key.lower()},
              "fingerprint": fingerprint, "basic_request_estimate": estimate,
              "ledger": BudgetLedger(work / "request-ledger.sqlite", int(config["http_budget"])).snapshot(),
              "groups": outcomes, "summary": summary}
    _json_write(work / "summary.json", report)
    return report


def validate_groups(canonical: list[dict], selected: list[dict]) -> list[dict]:
    known = {g["group_id"]: g for g in canonical}
    if len({g["group_id"] for g in selected}) != len(selected):
        raise ValueError("duplicate group outside frozen corpus selection")
    for group in selected:
        if group != known.get(group["group_id"]):
            raise ValueError("group differs from frozen corpus")
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--groups", type=int, default=0, help="run only the first N scopes")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    groups = prepare_groups(_read_jsonl(args.work / "corpus.jsonl"))
    if args.groups:
        groups = groups[:args.groups]
    report = run(args.work, groups=groups, workers=args.workers)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
