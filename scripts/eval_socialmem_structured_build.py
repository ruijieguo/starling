#!/usr/bin/env python3
"""WP2.B:声明合同库(结构化层)对来源路径的受控对比。

登记见 build/prereg_wp2b_structured_build.md。子命令:
  build     对每段历史新建声明合同库(发抽取与嵌入请求,需 --real-run)
  precheck  零请求:对照臂在新库上回放,与 WP1.A 矩阵参考行比区块哈希
  coverage  零请求:金标话轮被声明语句回链的覆盖诊断
  answer    对一个臂发出作答与判分请求(需 --real-run)
  report    零请求:汇总各臂的配对读数
  isolation-precheck  零请求:去声明库复制与两个隔离臂的来源门(登记:隔离答题)
  isolation-report    零请求:隔离臂对原 st_ctrl 日志的配对读数
没有 --real-run 不发任何请求,也不创建输出目录。"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import multiprocessing
import os
import re
import shutil
import sqlite3
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import eval_official_protocol as proto  # noqa: E402
import eval_socialmem_source_answer as ans  # noqa: E402
import eval_socialmem_source_matrix as matrix  # noqa: E402
import run_socialmem_baseline as base  # noqa: E402

ARMS = ("st_ctrl", "st_hyb", "st_hyb_cov")
ISOLATION_ARMS = ("st_ctrl_noclaim", "st_ctrl_repeat")   # 隔离答题:与 st_ctrl 同一设置,只换库或重复作答
CONTROL_REFERENCE_ARM = "evidence_profile_v9|k30|b24000"
NOW_ISO = "2026-12-08T00:00:00Z"
HTTP_BUDGET = 12000
TOKEN_CAP = 12_000_000           # 登记的中止线:累计已知 chat tokens
FAILURE_RATE_LIMIT = 0.25        # 登记的中止线:说话人失败率
FAILURE_CHECK_AFTER = 6          # 已完成至少这么多组之后才检查失败率
DEFAULT_CORPUS = Path("build/socialmem_pilot110_corpus.jsonl")
DEFAULT_REFERENCE = Path("build/wp1_matrix/full/rows.jsonl")
_EPS = 1e-9
_SPECS = {
    "st_ctrl": {"mode": "sources", "strategy": "evidence_profile_v9", "k": 30, "max_context_bytes": 24000},
    "st_hyb": {"mode": "hybrid", "strategy": "evidence_profile_v9", "k": 30, "max_context_bytes": 24000},
    "st_hyb_cov": {"mode": "hybrid", "strategy": "focused_coverage", "k": 10, "max_context_bytes": 8000,
                   "min_source_items": 7, "source_seed_k": 5, "source_seed_max_context_bytes": 4000,
                   "source_dialogue_radius": 1},
}


def arm_spec(arm: str) -> dict:
    key = "st_ctrl" if arm in ISOLATION_ARMS else arm
    if key not in _SPECS:
        raise ValueError(f"unknown arm: {arm!r}; valid={list(ARMS) + list(ISOLATION_ARMS)}")
    return dict(_SPECS[key])


DEFAULT_PROFILES = Path(__file__).resolve().parent / "eval_socialmem_structured_profiles.json"
PROFILES_SCHEMA_VERSION = 1
# 登记修订十一:模型、供应商、端点、钥匙变量名与嵌入维度只写在 profiles 文件里,驱动源码不点名任何模型。
MODEL_KEYS = ("extract_model", "extract_provider", "extract_endpoint", "extract_key_env",
              "answer_model", "answer_endpoint", "answer_key_env",
              "embedding_model", "embedding_endpoint", "embedding_dim", "embedding_key_env")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _check_profile_entry(name: str, entry) -> dict:
    """校验一个 profile。报错只点名 profile 与键,不回显任何值(值里可能被误贴了密钥)。"""
    if not isinstance(entry, dict):
        raise ValueError(f"profiles: 配置 {name!r} 必须是对象")
    unknown = sorted(set(entry) - set(MODEL_KEYS) - {"note"})
    if unknown:
        raise ValueError(f"profiles: 配置 {name!r} 含未登记的键 {unknown}")
    absent = [key for key in MODEL_KEYS if key not in entry]
    if absent:
        raise ValueError(f"profiles: 配置 {name!r} 缺键 {absent}")
    for key in MODEL_KEYS:
        value = entry[key]
        if key == "embedding_dim":
            if value is not None and not (type(value) is int and value > 0):
                raise ValueError(f"profiles: 配置 {name!r} 的 embedding_dim 必须是正整数或 null")
        elif not isinstance(value, str) or not value.strip():
            raise ValueError(f"profiles: 配置 {name!r} 的 {key} 必须是非空字符串")
        elif key.endswith("_key_env") and not _ENV_NAME.match(value):
            raise ValueError(f"profiles: 配置 {name!r} 的 {key} 必须是环境变量名,不能是密钥值")
        elif key.endswith("_endpoint") and not value.startswith("https://"):
            raise ValueError(f"profiles: 配置 {name!r} 的 {key} 必须以 https:// 开头")
    return {key: entry[key] for key in MODEL_KEYS}


def _read_profiles(path=None) -> tuple[str, dict]:
    target = DEFAULT_PROFILES if path is None else Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except OSError:
        raise ValueError(f"profiles 文件无法读取: {target.name}") from None
    except ValueError:
        raise ValueError(f"profiles 文件不是合法 JSON: {target.name}") from None
    if not isinstance(payload, dict):
        raise ValueError("profiles 文件顶层必须是对象")
    version = payload.get("schema_version")
    if type(version) is not int or version != PROFILES_SCHEMA_VERSION:
        raise ValueError(f"profiles 文件的 schema_version 必须是 {PROFILES_SCHEMA_VERSION}")
    raw = payload.get("profiles")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("profiles 文件的 profiles 必须是非空对象")
    default = payload.get("default_profile")
    if not isinstance(default, str) or default not in raw:
        raise ValueError("profiles 文件的 default_profile 必须是 profiles 里的一个名字")
    return default, {name: _check_profile_entry(name, entry) for name, entry in raw.items()}


def load_profiles(path=None) -> dict:
    return _read_profiles(path)[1]


def default_profile_name(path=None) -> str:
    return _read_profiles(path)[0]


def profiles_sha256(path=None) -> str:
    return hashlib.sha256((DEFAULT_PROFILES if path is None else Path(path)).read_bytes()).hexdigest()


def build_config(profile: str | None = None, profiles_path=None) -> dict:
    """登记的抽取与建库配置。模型相关的键来自 profiles 文件;不含任何密钥,
    密钥只在构造原生适配器的一刻按变量名从环境读取。profile 缺省取文件里的 default_profile。"""
    default, profiles = _read_profiles(profiles_path)
    name = default if profile is None else profile
    if name not in profiles:
        raise ValueError(f"unknown profile: {name!r}; valid={sorted(profiles)}")
    config = {
        "arm": "wp2b_structured_build", "profile": name,
        "extract_enable_thinking": False, "extract_max_tokens": 8192,
        "answer_enable_thinking": False, "answer_max_tokens": 1000, "judge_max_tokens": 400,
        "embedding_max_batch_inputs": 10, "max_retries": 0, "timeout_ms": 120000,
        "lifecycle": "sleep", "query_time": NOW_ISO, "created_at": "2026-06-01T00:00:00Z",
        "retain_sources": True, "preserve_invalid_time": True, "include_unknown_time": True,
        "semantic_claim_contract": True, "preserve_text_objects": True, "claim_output_mode": "json_object",
        "claim_allow_code_fence": True, "claim_protocol_retry_budget": 1, "claim_batch_size": 8,
        "claim_batch_target_units": True, "holder_isolation": True, "http_budget": HTTP_BUDGET,
    }
    config.update(profiles[name])
    return config


def buildable_problem(config: dict) -> str | None:
    """建库前的静态检查:嵌入维度必须已知,模型键不得为空。不发任何请求。"""
    name = config.get("profile")
    dim = config.get("embedding_dim")
    if type(dim) is not int or dim <= 0:
        return f"profile {name} 的 embedding_dim 未知(null),拒绝建库;先探明维度并写入 profiles 文件,不得猜。"
    for key in MODEL_KEYS:
        if key != "embedding_dim" and not str(config.get(key) or "").strip():
            return f"profile {name} 的 {key} 为空,拒绝建库。"
    return None


def check_built_matches(built: dict, current: dict) -> str | None:
    """作答前核对:建库时落盘的模型设置必须与当前 profile 一致。只比模型相关的键,不回显值。"""
    differing = [key for key in MODEL_KEYS if built.get(key) != current.get(key)]
    if differing:
        return f"建库配置与当前 profile 的模型设置不一致: {differing}"
    return None


def make_adapters(core, config: dict) -> tuple:
    """按配置里的钥匙变量名与端点构造四个原生适配器(抽取、嵌入、作答、裁判)。
    每个适配器在构造的一刻做进程内环境替换,构造完立即还原;原生适配器只在构造时快照钥匙。"""
    retries, timeout = int(config["max_retries"]), int(config["timeout_ms"])
    with base._provider_environment(str(config["extract_key_env"]), str(config["extract_endpoint"])):
        extract_cfg = core.OpenAIAdapterConfig.from_env()
        extract_cfg.model = str(config["extract_model"])
        extract_cfg.timeout_ms, extract_cfg.max_retries = timeout, retries
        extract_cfg.max_tokens, extract_cfg.json_object_output = int(config["extract_max_tokens"]), False
        extract_cfg.enable_thinking = config.get("extract_enable_thinking")
        extract_llm = core.OpenAIAdapter(extract_cfg)
    with base._provider_environment(str(config["embedding_key_env"]), str(config["embedding_endpoint"])):
        old_batch = os.environ.get("EMBEDDING_MAX_BATCH")
        os.environ["EMBEDDING_MAX_BATCH"] = str(config["embedding_max_batch_inputs"])
        try:
            embedding_cfg = core.OpenAIEmbeddingConfig.from_env()
            embedding_cfg.base_url = str(config["embedding_endpoint"])
            embedding_cfg.model, embedding_cfg.dim = str(config["embedding_model"]), int(config["embedding_dim"])
            embedding_cfg.timeout_ms, embedding_cfg.max_retries = timeout, retries
            embedder = core.OpenAIEmbeddingAdapter(embedding_cfg)
        finally:
            if old_batch is None:
                os.environ.pop("EMBEDDING_MAX_BATCH", None)
            else:
                os.environ["EMBEDDING_MAX_BATCH"] = old_batch
    with base._provider_environment(str(config["answer_key_env"]), str(config["answer_endpoint"])):
        answer_cfg = core.OpenAIAdapterConfig.from_env()
        answer_cfg.model = str(config["answer_model"])
        answer_cfg.enable_thinking = config.get("answer_enable_thinking")
        answer_cfg.timeout_ms, answer_cfg.max_retries = timeout, retries
        answer_cfg.max_tokens, answer_cfg.json_object_output = int(config["answer_max_tokens"]), False
        answer_llm = core.OpenAIAdapter(answer_cfg)
        judge_cfg = core.OpenAIAdapterConfig.from_env()
        judge_cfg.model = str(config["answer_model"])
        judge_cfg.timeout_ms, judge_cfg.max_retries = timeout, retries
        judge_cfg.max_tokens, judge_cfg.json_object_output = int(config["judge_max_tokens"]), False
        judge_llm = core.OpenAIAdapter(judge_cfg)
    return extract_llm, embedder, answer_llm, judge_llm


def answer_channel(config: dict):
    """作答与裁判走的通道:进程内把 OPENAI_API_KEY 与 OPENAI_BASE_URL 指向配置里的钥匙变量与端点,退出时还原。"""
    return base._provider_environment(str(config["answer_key_env"]), str(config["answer_endpoint"]))


# ---------------------------- 前置门(登记修订十一) ----------------------------

PREFLIGHT_PROMPT = "Reply with the single word: ok"
PREFLIGHT_TEXT = "preflight"


def preflight(config: dict, adapters: tuple) -> dict:
    """建库前发一条极小抽取通道 chat、一条极小作答通道 chat、一条极小嵌入。
    任一失败,或嵌入向量维度不等于配置的 embedding_dim,就抛 RuntimeError,此时尚未发出任何抽取请求。
    adapters 为 (抽取, 嵌入, 作答, 裁判),与 make_adapters 的返回顺序一致。报错不回显回复正文。"""
    extract_llm, embedder, answer_llm, _judge_llm = adapters
    for label, llm in (("抽取", extract_llm), ("作答", answer_llm)):
        try:
            _, _, error = base.response_text(llm.extract(PREFLIGHT_PROMPT, ""), f"preflight {label}")
        except Exception as exc:  # noqa: BLE001 — 任何传输或绑定异常都算前置门失败
            raise RuntimeError(f"前置门失败:{label}通道调用异常 {type(exc).__name__}") from None
        if error:
            raise RuntimeError(f"前置门失败:{label}通道 {error}")
    try:
        vector = embedder.embed(PREFLIGHT_TEXT)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"前置门失败:嵌入调用异常 {type(exc).__name__}") from None
    want, got = int(config["embedding_dim"]), len(vector)
    if got != want:
        raise RuntimeError(f"前置门失败:嵌入向量维度 {got} 与配置的 embedding_dim {want} 不一致")
    return {"extract_chat": True, "answer_chat": True, "embedding_dim": got}


# ---------------------------- 分组、状态与止损 ----------------------------

def plan_groups(records: list[dict]) -> list[dict]:
    """沿用基线运行器的分组(网络加评测范围,同组同一历史);历史话轮最少的排最前(冒烟组)。"""
    plan = []
    for group in base.prepare_groups(records):
        holders = len({str(t.get("speaker") or "unknown").strip() or "unknown" for t in group["history"]})
        plan.append({"group_id": group["group_id"], "network_id": group["network_id"],
                     "evaluation_scope": group["evaluation_scope"], "turns": len(group["history"]),
                     "holders": holders, "request_upper_bound": 9 * holders,
                     "history": group["history"], "history_sha256": group["history_sha256"],
                     "records": group["records"]})
    plan.sort(key=lambda g: (g["turns"], g["group_id"]))
    return plan


def scope_status(scope_dir) -> str:
    d = Path(scope_dir)
    if (d / "scope.failure.json").is_file():
        return "failed"
    done = d / "scope.json"
    if not done.is_file():
        return "pending"
    if not (d / "frozen.db").is_file():
        raise RuntimeError(f"completed scope snapshot missing: {d}")
    state = json.loads(done.read_text(encoding="utf-8")).get("scope_state")
    return "partial" if state == "partial" else "complete"


def known_tokens(payload, _under_structured: bool = False) -> int:
    """回执里供应商报告的 total_tokens 之和;structured_output 下是同一次调用的重复统计,不再加一遍。"""
    total = 0
    if isinstance(payload, dict):
        for key, value in payload.items():
            if (key == "total_tokens" and isinstance(value, (int, float)) and not isinstance(value, bool)
                    and not _under_structured):
                total += value
            else:
                total += known_tokens(value, _under_structured or key == "structured_output")
    elif isinstance(payload, list):
        for item in payload:
            total += known_tokens(item, _under_structured)
    return int(total)


def scope_summary(scope_dir, holders: int) -> dict:
    d = Path(scope_dir)
    status = scope_status(d)
    out = {"scope": d.name, "status": status, "scope_state": status, "holders": holders,
           "holder_failures": 0, "tokens": 0}
    if status in ("complete", "partial"):
        meta = json.loads((d / "scope.json").read_text(encoding="utf-8"))
        out["holder_failures"] = len(meta.get("holder_failures") or [])
        out["scope_state"] = meta.get("scope_state")
    elif status == "failed":
        out["holder_failures"] = holders
    receipts = d / "extraction.receipts.json"
    if receipts.is_file():
        archive = json.loads(receipts.read_text(encoding="utf-8"))
        out["tokens"] = sum(known_tokens(r) for r in (archive.get("holders") or {}).values())
    return out


SMOKE_FAILURE_TOLERANCE = 1   # 登记修订十一(事后放宽,已披露):冒烟组允许至多 1 个说话人失败


def smoke_passed(summary: dict) -> bool:
    failures = summary.get("holder_failures")
    return (summary.get("scope_state") in ("complete", "partial") and isinstance(failures, int)
            and failures <= SMOKE_FAILURE_TOLERANCE)


def abort_reason(summaries: list[dict]) -> str | None:
    """登记的中止线(冒烟组另行判定):累计已知 tokens 超限;已完成至少 6 组后说话人失败率超限。"""
    if sum(int(s.get("tokens", 0)) for s in summaries) > TOKEN_CAP:
        return "token_cap"
    if len(summaries) >= FAILURE_CHECK_AFTER:
        holders = sum(int(s.get("holders", 0)) for s in summaries)
        failures = sum(int(s.get("holder_failures", 0)) for s in summaries)
        if holders and failures / holders > FAILURE_RATE_LIMIT:
            return "holder_failure_rate"
    return None


def schedule_groups(groups, worker, *, workers, abort_check, prior=(), executor_factory=None, on_result=None):
    """滑动窗口调度(登记修订八):任一时刻在途组数不超过 workers,每收到一个结果就检查中止线,
    触发后不再提交新组,等在途的组结束并计入。返回 (本次新增的 summaries, 中止原因或 None);
    prior 只参与中止判定,不在返回值里。工作进程崩溃记为该组全部说话人失败。"""
    def _spawn_pool(count):
        return ProcessPoolExecutor(max_workers=count, mp_context=multiprocessing.get_context("spawn"))

    width = max(1, int(workers))
    factory = executor_factory or _spawn_pool
    queue, fresh, pending, reason = list(groups), [], {}, None
    with factory(width) as pool:
        while True:
            while reason is None and queue and len(pending) < width:
                group = queue.pop(0)
                pending[pool.submit(worker, group)] = group
            if not pending:
                break
            done, _ = wait(list(pending), return_when=FIRST_COMPLETED)
            for future in done:
                group = pending.pop(future)
                try:
                    summary = future.result()
                except Exception as exc:  # noqa: BLE001 — 一个工作进程崩溃只丢这一组
                    summary = {"scope": group["group_id"], "status": "worker_crash", "scope_state": "failed",
                               "holders": group["holders"], "holder_failures": group["holders"], "tokens": 0,
                               "error": f"{type(exc).__name__}: {exc}"[:300]}
                fresh.append(summary)
                if on_result is not None:
                    on_result(summary)
                if reason is None:
                    reason = abort_check(list(prior) + fresh)
    return fresh, reason


# ---------------------------- 覆盖诊断 ----------------------------

def linked_turn_ids(rows, history: list[dict]) -> tuple[set, set]:
    """rows 为 (持有者, 声明 JSON)。返回被声明回链的话轮号,以及其中说话人就是持有者的话轮号。"""
    speaker = {t["turn_id"]: t["speaker"] for t in history}
    linked: set = set()
    owned: set = set()
    for holder, raw in rows:
        if not raw:
            continue
        try:
            claim = json.loads(raw)
        except (TypeError, ValueError):
            continue
        turn = claim.get("source_turn") if isinstance(claim, dict) else None
        turn_id = turn.get("turn_id") if isinstance(turn, dict) else None
        if turn_id in speaker:
            linked.add(turn_id)
            if holder == speaker[turn_id]:
                owned.add(turn_id)
    return linked, owned


def gold_link_coverage(record: dict, linked: set, owned: set) -> dict:
    gold = set(matrix.gold_turn_ids(record))
    return {"gold": len(gold), "linked": len(gold & linked), "owned": len(gold & owned),
            "all_linked": gold <= linked, "all_owned": gold <= owned}


# ---------------------------- 召回回放 ----------------------------

def recall_for_arm(arm: str, record: dict, library, work, *, embedder, now_iso: str = NOW_ISO) -> dict:
    """在库的临时副本上回放一次召回,用后删除副本。hybrid 臂的查询嵌入由调用方传入。"""
    import eval_ladder_pipeline as pipe

    spec = arm_spec(arm)
    extra = {k: v for k, v in spec.items() if k not in ("mode", "strategy", "k", "max_context_bytes")}
    holders = sorted({str(t["speaker"]) for t in record["history"]})
    with matrix._library_copy(library, work, f"structured|{record['item_id']}|{arm}") as ctx:
        out = pipe.recall_observer_block(
            ctx.core, adapter=ctx.rt.adapter, embedder=embedder, index=ctx.index, question=record["question"],
            allowed_holders=holders, mode=spec["mode"], now_iso=now_iso, k=spec["k"],
            max_context_bytes=spec["max_context_bytes"], include_unknown_time=True,
            source_strategy=spec["strategy"], **extra)
    return {"source_refs": out["source_refs"], "context_bytes": int(out["context_bytes"]),
            "source_count": int(out["source_count"]), "statement_count": int(out.get("statement_count", 0)),
            "statement_ids": list(out.get("statement_ids") or []), "block": out["block"]}


def control_agreement(rows: list[dict], reference: list[dict]) -> dict:
    want = {r["item_id"]: r["block_sha256"] for r in reference if r.get("arm") == CONTROL_REFERENCE_ARM}
    return {"equal": sum(1 for r in rows if want.get(r["item_id"]) == r["block_sha256"]), "of": len(rows)}


def precheck_summary(ctrl_rows: list[dict], hyb_rows: list[dict], reference: list[dict]) -> dict:
    """请求前门禁(登记修订一):对照臂与主臂在新库上的来源话轮序列逐题相同才放行。
    与 WP1.A 矩阵参考行的区块相同数只报告,不设门禁。"""
    hyb = {r["item_id"]: r["turn_ids"] for r in hyb_rows}
    equal = sum(1 for r in ctrl_rows if hyb.get(r["item_id"]) == r["turn_ids"])
    total = len(ctrl_rows)
    return {"mode_equal": equal, "of": total,
            "reference_equal": control_agreement(ctrl_rows, reference)["equal"],
            "ready": total > 0 and equal == total}


# ---------------------------- 读法与报告 ----------------------------

def read_hyb_mc_vs_ctrl(delta: float, lo: float) -> str:
    """登记读法 1(st_hyb 减 st_ctrl,Q2+Q6 选择题,每题记 1 或 0)。"""
    if delta >= 0.10 - _EPS and lo > 0:
        return "结构化声明有可确认的选择题增益"
    if delta < 0.05 - _EPS:
        return "附加声明对选择题没有增益"
    return "无法区分"


def build_report(records: list[dict], rows_by_arm: dict, *, seed: int = ans.BOOTSTRAP_SEED,
                 draws: int = ans.BOOTSTRAP_DRAWS) -> dict:
    by_id = {r["item_id"]: r for r in records}

    def is_mc(item: str) -> bool:
        return by_id[item].get("answer_format", "multiple_choice") == "multiple_choice"

    def primary(item: str) -> bool:
        return by_id[item]["query_type"] in ans.PRIMARY_TYPES and not is_mc(item)

    def fallback(rows: dict, item: str) -> bool:
        return rows[item].get("judge_status") == "regex_fallback"

    def network(item: str) -> str:
        return by_id[item]["source"]["network_id"]

    arms = {}
    for name, rows in rows_by_arm.items():
        have = [r["item_id"] for r in records if r["item_id"] in rows]
        flagged = [i for i in have if fallback(rows, i)]
        ids = [i for i in have if primary(i) and i not in flagged]
        scores = [float(rows[i]["score"]) for i in ids]
        arms[name] = {"q5q9": {"n": len(ids), "mean_score": (sum(scores) / len(scores)) if scores else None,
                               "ge07": sum(1 for i in ids if rows[i]["ok"])},
                      "answered": len(have), "missing": len(records) - len(have), "regex_fallback": flagged}
    mc = {}
    for qt in ans.GUARD_TYPES:
        ids = [r["item_id"] for r in records if r["query_type"] == qt and is_mc(r["item_id"])]
        cell = {"n": len(ids)}
        for name, rows in rows_by_arm.items():
            cell[name] = sum(1 for i in ids if i in rows and rows[i]["ok"])
        mc[qt] = cell

    def mc_pair(a_rows: dict, b_rows: dict, types: tuple):
        ids = [r["item_id"] for r in records if r["query_type"] in types and is_mc(r["item_id"])
               and r["item_id"] in a_rows and r["item_id"] in b_rows]
        items = [(network(i), float(a_rows[i]["ok"]), float(b_rows[i]["ok"])) for i in ids]
        return ans.paired_network_bootstrap(items, seed=seed, draws=draws) if items else None

    def open_pair(a_rows: dict, b_rows: dict):
        ids = [r["item_id"] for r in records if primary(r["item_id"]) and r["item_id"] in a_rows
               and r["item_id"] in b_rows and not fallback(a_rows, r["item_id"]) and not fallback(b_rows, r["item_id"])]
        items = [(network(i), float(a_rows[i]["score"]), float(b_rows[i]["score"])) for i in ids]
        return ans.paired_network_bootstrap(items, seed=seed, draws=draws) if items else None

    ctrl, hyb = rows_by_arm["st_ctrl"], rows_by_arm["st_hyb"]
    main_pair = mc_pair(ctrl, hyb, ("Q2", "Q6"))
    if main_pair:
        main_pair["read"] = read_hyb_mc_vs_ctrl(main_pair["delta"], main_pair["lo"])
    paired = {"hyb_vs_ctrl_mc": main_pair, "hyb_vs_ctrl_open": open_pair(ctrl, hyb)}
    if "st_hyb_cov" in rows_by_arm:
        paired["hyb_cov_vs_ctrl_mc"] = mc_pair(ctrl, rows_by_arm["st_hyb_cov"], ("Q2", "Q6"))
        paired["hyb_cov_vs_ctrl_open"] = open_pair(ctrl, rows_by_arm["st_hyb_cov"])
    q4_ids = [r["item_id"] for r in records if r["query_type"] == "Q4" and is_mc(r["item_id"])
              and r["item_id"] in ctrl and r["item_id"] in hyb]
    q4_ctrl, q4_hyb = sum(1 for i in q4_ids if ctrl[i]["ok"]), sum(1 for i in q4_ids if hyb[i]["ok"])
    open_delta = paired["hyb_vs_ctrl_open"]["delta"] if paired["hyb_vs_ctrl_open"] else None
    guards = {"q4_mc": {"ctrl": q4_ctrl, "hyb": q4_hyb, "held": q4_hyb >= q4_ctrl - 2},
              "open_mean_delta": open_delta,
              "open_held": open_delta is not None and open_delta >= -0.05 - _EPS}
    return {"arms": arms, "mc": mc, "paired": paired, "guards": guards,
            "bootstrap": {"seed": seed, "draws": draws}}


# ---------------------------- 隔离答题(登记:对照臂放在去掉声明的库上,对 28 题重答) ----------------------------

ISOLATION_MIN_NET = 3             # 读法 1:选择题答对数净变化的下限
ISOLATION_EXTRA_FLIPS = 2         # 读法 1:去声明库的翻转数至少比同输入重复多这么多
READ_MC_VISIBLE = "来源选择认得声明对选择题有可见影响"
READ_OPEN_VISIBLE = "来源选择认得声明对开放题有可见影响"
READ_NO_DIFFERENCE = "无法区分"
FLIP_DOWN, FLIP_UP = "答对变答错", "答错变答对"
OPEN_FLIP_DOWN, OPEN_FLIP_UP = "达标变不达标", "未达标变达标"
_NOCLAIM, _REPEAT = ISOLATION_ARMS


def strip_claims(source, dest) -> dict:
    """备份方式复制库(源库只读打开),在复制里把全部语句的 semantic_claim_json 置空。
    源库不改;dest 已存在或源库不存在都直接拒绝,失败不留残件。"""
    source, dest = Path(source), Path(dest)
    if not source.is_file():
        raise FileNotFoundError(str(source))
    if dest.exists():
        raise FileExistsError(str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    part.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src, \
                closing(sqlite3.connect(part)) as out:
            src.backup(out)
            total = out.execute("select count(*) from statements").fetchone()[0]
            cleared = out.execute("select count(*) from statements "
                                  "where semantic_claim_json is not null and semantic_claim_json != ''").fetchone()[0]
            out.execute("update statements set semantic_claim_json = ''")
            out.commit()
            out.execute("pragma journal_mode=delete")        # 合并 WAL,复制是单个自含文件
        part.replace(dest)
    finally:
        for suffix in ("", "-wal", "-shm", "-journal"):
            Path(str(part) + suffix).unlink(missing_ok=True)
    return {"statements": total, "claims_cleared": cleared}


def load_item_list(path, records: list[dict]) -> list[str]:
    """读题号名单(每行一个),按语料顺序返回。空名单、重复题号、语料里没有的题号都拒绝。"""
    listed = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not listed:
        raise ValueError("题号名单为空")
    if len(set(listed)) != len(listed):
        raise ValueError("题号名单有重复")
    known = {r["item_id"] for r in records}
    unknown = [i for i in listed if i not in known]
    if unknown:
        raise ValueError(f"名单里有语料没有的题号: {unknown[:3]}")
    want = set(listed)
    return [r["item_id"] for r in records if r["item_id"] in want]


def isolation_gate(arm: str, rows: list[dict], *, reference: list[dict], original: dict) -> dict:
    """请求前门(登记):去声明库臂要求来源话轮序列与参考行逐题相同;重复臂要求区块哈希与原 st_ctrl 日志逐题相同。
    另一项只报告。rows 每行含 item_id、turn_ids、block_sha256;original 是原 st_ctrl 日志按题号索引。"""
    if arm not in ISOLATION_ARMS:
        raise ValueError(f"not an isolation arm: {arm!r}")
    ref = {r["item_id"]: r for r in reference if r.get("arm") == CONTROL_REFERENCE_ARM}
    orig = {i: {"turn_ids": o.get("source_turn_ids"), "block_sha256": o.get("block_sha256")}
            for i, o in original.items()}
    turn_source, block_source = (ref, ref) if arm == _NOCLAIM else (orig, orig)
    turns = sum(1 for r in rows if (turn_source.get(r["item_id"]) or {}).get("turn_ids") == r["turn_ids"])
    blocks = sum(1 for r in rows if (block_source.get(r["item_id"]) or {}).get("block_sha256") == r["block_sha256"])
    total = len(rows)
    needed = turns if arm == _NOCLAIM else blocks
    return {"arm": arm, "turn_ids_equal": turns, "block_equal": blocks, "of": total,
            "ready": total > 0 and needed == total}


def read_isolation_mc(net: int, flips_noclaim: int, flips_repeat: int) -> str:
    """登记读法 1(选择题):净变化绝对值不少于 3,且去声明库的翻转数比同输入重复至少多 2。"""
    if abs(net) >= ISOLATION_MIN_NET and flips_noclaim >= flips_repeat + ISOLATION_EXTRA_FLIPS:
        return READ_MC_VISIBLE
    return READ_NO_DIFFERENCE


def read_isolation_open(noclaim_lo: float, noclaim_hi: float, repeat_lo: float, repeat_hi: float) -> str:
    """登记读法 2(开放题):去声明库的区间不含 0,且同输入重复的区间含 0。"""
    if (noclaim_lo > 0 or noclaim_hi < 0) and repeat_lo <= 0 <= repeat_hi:
        return READ_OPEN_VISIBLE
    return READ_NO_DIFFERENCE


def build_isolation_report(records: list[dict], items: list[str], orig: dict, rows_by_arm: dict, *,
                           seed: int = ans.BOOTSTRAP_SEED, draws: int = ans.BOOTSTRAP_DRAWS) -> dict:
    """两个隔离臂各自对原 st_ctrl 日志,只看名单里的题。选择题翻转明细只含选择题;
    裁判解析失败或正则兜底的开放题分数(任一侧)不进汇总,单列在 excluded。
    between 的差值方向是去声明库臂减同输入重复臂,只描述,不设读法。"""
    by_id = {r["item_id"]: r for r in records}
    absent = [i for i in items if i not in by_id or i not in orig]
    if absent:
        raise ValueError(f"名单里的题缺语料或原日志行: {absent[:3]}")

    def is_mc(item: str) -> bool:
        return by_id[item].get("answer_format", "multiple_choice") == "multiple_choice"

    def network(item: str) -> str:
        return by_id[item]["source"]["network_id"]

    def unreliable(row: dict) -> bool:
        return row.get("judge_status") in ans.BAD_JUDGE_STATUSES

    def boot(pairs):
        return ans.paired_network_bootstrap(pairs, seed=seed, draws=draws) if pairs else None

    mc_ids = [i for i in items if is_mc(i)]
    open_ids = [i for i in items if not is_mc(i)]
    arms = [a for a in ISOLATION_ARMS if a in rows_by_arm]
    mc = {"n": len(mc_ids), "orig_correct": sum(1 for i in mc_ids if orig[i]["ok"])}
    open_ = {"n": len(open_ids)}
    flips, open_flips, missing, excluded, answered = {}, {}, {}, {}, {}
    for arm in arms:
        rows = rows_by_arm[arm]
        missing[arm] = [i for i in items if i not in rows]
        have_mc = [i for i in mc_ids if i in rows]
        changed = [i for i in have_mc if bool(rows[i]["ok"]) != bool(orig[i]["ok"])]
        mc[arm] = {"correct": sum(1 for i in have_mc if rows[i]["ok"]),
                   "net": sum(1 for i in have_mc if rows[i]["ok"]) - sum(1 for i in have_mc if orig[i]["ok"]),
                   "flips": len(changed)}
        flips[arm] = {i: (FLIP_DOWN if orig[i]["ok"] else FLIP_UP) for i in changed}
        usable = [i for i in open_ids if i in rows and not unreliable(rows[i]) and not unreliable(orig[i])]
        excluded[arm] = [i for i in open_ids if i in rows and i not in usable]
        open_[arm] = boot([(network(i), float(orig[i]["score"]), float(rows[i]["score"])) for i in usable])
        open_flips[arm] = {i: (OPEN_FLIP_DOWN if orig[i]["ok"] else OPEN_FLIP_UP)
                           for i in usable if bool(rows[i]["ok"]) != bool(orig[i]["ok"])}
        answered[arm] = {"mc": len(have_mc), "open": sum(1 for i in open_ids if i in rows)}
    complete = len(arms) == len(ISOLATION_ARMS) and not any(missing.values())
    mc["read"] = (read_isolation_mc(mc[_NOCLAIM]["net"], mc[_NOCLAIM]["flips"], mc[_REPEAT]["flips"])
                  if complete else None)
    if complete and open_[_NOCLAIM] and open_[_REPEAT]:
        open_["read"] = read_isolation_open(open_[_NOCLAIM]["lo"], open_[_NOCLAIM]["hi"],
                                            open_[_REPEAT]["lo"], open_[_REPEAT]["hi"])
    else:
        open_["read"] = None
    between = {}
    if len(arms) == len(ISOLATION_ARMS):
        rep, noc = rows_by_arm[_REPEAT], rows_by_arm[_NOCLAIM]
        between = {"mc": boot([(network(i), float(rep[i]["ok"]), float(noc[i]["ok"]))
                               for i in mc_ids if i in rep and i in noc]),
                   "open": boot([(network(i), float(rep[i]["score"]), float(noc[i]["score"]))
                                 for i in open_ids if i in rep and i in noc
                                 and not unreliable(rep[i]) and not unreliable(noc[i])])}
    return {"mc": mc, "open": open_, "flips": flips, "open_flips": open_flips, "missing": missing,
            "excluded": excluded, "answered": answered, "between": between,
            "bootstrap": {"seed": seed, "draws": draws}}


def stripped_library_paths(libs: dict, out) -> dict:
    """题号到去声明库副本的映射:每个组一个副本,放在 out/stripped/<组号>/frozen.db。"""
    return {item: Path(out) / "stripped" / Path(lib).parent.name / "frozen.db" for item, lib in libs.items()}


def isolation_precheck_problem(pre, arm: str, *, items_sha256: str, core_sha256: str) -> str | None:
    """作答前核对隔离门文件:存在、名单与核心都对得上、该臂的门已通过。"""
    if not isinstance(pre, dict):
        return "缺少 isolation_precheck.json:先跑零请求的 isolation-precheck。"
    if pre.get("items_sha256") != items_sha256:
        return "isolation_precheck.json 对应的题号名单与本次 --items 不一致。"
    if pre.get("core_sha256") != core_sha256:
        return "isolation_precheck.json 记录的核心与当前加载的核心不一致。"
    gate = (pre.get("gates") or {}).get(arm)
    if not isinstance(gate, dict) or gate.get("ready") is not True:
        return f"isolation_precheck.json 里 {arm} 的门没有通过。"
    return None


def isolation_library_problem(pre: dict, arm: str, libs: dict) -> str | None:
    """作答前核对要用的每个库文件的哈希:去声明库臂对 stripped_sha256,重复臂对 source_sha256。"""
    recorded = pre.get("stripped_sha256" if arm == _NOCLAIM else "source_sha256") or {}
    for lib in sorted({Path(p) for p in libs.values()}):
        group = lib.parent.name
        if not lib.is_file():
            return f"{arm} 的库文件不存在: {group}"
        if recorded.get(group) != ans._sha256_file(lib):
            return f"{arm} 的库 {group} 与 isolation_precheck.json 记录的哈希不一致。"
    return None


# ---------------------------- 建库 ----------------------------

def _live_modules():
    from starling import _core, runtime
    import eval_judge_audit as audit
    import eval_ladder as ladder
    import eval_ladder_pipeline as pipe
    import eval_longmemeval as longmem
    return (_core, runtime, audit, ladder, pipe, longmem)


def build_one_group(group: dict, out_dir, config: dict, *, modules, adapters, ledger) -> dict:
    """建一段历史的声明合同库,落盘 scope.json 或 scope.failure.json。已有终态的不重建,不重复花费。"""
    scope_dir = Path(out_dir) / "runs" / group["group_id"]
    holders = len({str(t.get("speaker") or "unknown").strip() or "unknown" for t in group["history"]})
    if scope_dir.exists():
        if scope_status(scope_dir) != "pending":
            return scope_summary(scope_dir, holders)
        shutil.rmtree(scope_dir)           # 上次中断留下的半成品
    scope_dir.mkdir(parents=True)
    started = time.perf_counter()
    reservation = ledger.reserve_wait(group["group_id"], "scope_extraction", 9 * holders)
    try:
        if reservation.get("state") == "blocked":
            raise base.BudgetBlocked("budget_blocked_before_scope_extraction")
        _, meta = base._build_scope_database(group, scope_dir, modules, config, adapters, ledger, reservation)
        meta["elapsed_seconds"] = time.perf_counter() - started
        base._json_write(scope_dir / "scope.json", {"group": group["group_id"], "network_id": group["network_id"],
                                                    "evaluation_scope": group["evaluation_scope"], **meta})
    except Exception as exc:  # noqa: BLE001 — 一组失败不拖垮其它组
        if "id" in reservation:
            ledger.charge_upper(reservation["id"])
        base._json_write(scope_dir / "scope.failure.json", {
            "group": group["group_id"], "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": time.perf_counter() - started})
    return scope_summary(scope_dir, holders)


def _worker(group: dict, *, out_dir: str, config: dict) -> dict:
    modules = _live_modules()
    adapters = make_adapters(modules[0], config)
    ledger = base.BudgetLedger(Path(out_dir) / "request-ledger.sqlite", int(config["http_budget"]))
    return build_one_group(group, out_dir, config, modules=modules, adapters=adapters, ledger=ledger)


def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def _core_gate(args):
    from starling import _core

    core_sha = ans._sha256_file(_core.__file__)
    if args.require_core_sha256 and core_sha != args.require_core_sha256:
        return None, f"加载的核心 {core_sha[:12]} 不是要求的 {args.require_core_sha256[:12]}。"
    return core_sha, None


def _build(args) -> int:
    if not args.real_run:
        return _fail("缺 --real-run:build 会发出真实抽取与嵌入请求,拒绝误触网络。")
    profile_config = build_config(args.profile, args.profiles)
    problem = buildable_problem(profile_config)
    if problem:
        return _fail(problem)
    core_sha, problem = _core_gate(args)
    if problem:
        return _fail(problem)
    records = ans._load_corpus(args.corpus)
    plan = plan_groups(records)
    config = dict(profile_config, core_sha256=core_sha)
    modules = _live_modules()
    adapters = make_adapters(modules[0], config)
    try:
        gate_report = preflight(config, adapters)
    except RuntimeError as exc:
        return _fail(str(exc))
    out = args.out
    if out.exists():
        if not args.resume:
            return _fail(f"{out} 已存在;续跑须显式 --resume,拒绝覆盖。")
        if json.loads((out / "config.json").read_text(encoding="utf-8")) != config:
            return _fail("续跑的配置或核心与首次不一致,拒绝。")
    else:
        out.mkdir(parents=True)
        (out / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        listing = [{k: g[k] for k in ("group_id", "network_id", "evaluation_scope", "turns", "holders",
                                       "request_upper_bound")} | {"questions": [r["item_id"] for r in g["records"]]}
                   for g in plan]
        (out / "plan.json").write_text(json.dumps(listing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out / "preflight.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(gate_report, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                                ensure_ascii=False) + "\n")
    ledger = base.BudgetLedger(out / "request-ledger.sqlite", HTTP_BUDGET)
    summaries: dict[str, dict] = {}
    smoke = plan[0]
    summaries[smoke["group_id"]] = build_one_group(smoke, out, config, modules=modules, adapters=adapters,
                                                   ledger=ledger)
    print(json.dumps({"smoke": summaries[smoke["group_id"]]}, ensure_ascii=False), flush=True)
    state = "complete"
    if not smoke_passed(summaries[smoke["group_id"]]):
        state = "aborted:smoke_failed"
    elif args.stop_after_smoke:
        state = "stopped_after_smoke"
    else:
        todo = []
        for group in plan[1:]:
            scope = out / "runs" / group["group_id"]
            if scope.exists() and scope_status(scope) != "pending":
                summaries[group["group_id"]] = scope_summary(scope, group["holders"])   # 已有终态,不重建
            else:
                todo.append(group)
        fresh, reason = schedule_groups(
            todo, functools.partial(_worker, out_dir=str(out), config=config), workers=args.workers,
            abort_check=abort_reason, prior=list(summaries.values()),
            on_result=lambda summary: print(json.dumps(summary, ensure_ascii=False), flush=True))
        for summary in fresh:
            summaries[summary["scope"]] = summary
        if reason:
            state = f"aborted:{reason}"
    base._json_write(out / "build_summary.json", {
        "state": state, "profile": config["profile"], "profiles_sha256": profiles_sha256(args.profiles),
        "core_sha256": core_sha, "groups": len(plan),
        "built": len(summaries), "known_tokens": sum(int(s.get("tokens", 0)) for s in summaries.values()),
        "ledger": ledger.snapshot(), "summaries": summaries})
    print(json.dumps({"state": state, "built": len(summaries), "of": len(plan)}, ensure_ascii=False))
    return 0 if state in ("complete", "stopped_after_smoke") else 3


# ---------------------------- 零请求子命令 ----------------------------

def _libraries(builds: Path, plan: list[dict]) -> dict[str, Path]:
    libs: dict[str, Path] = {}
    for group in plan:
        scope = builds / "runs" / group["group_id"]
        if scope_status(scope) not in ("complete", "partial"):
            continue
        for record in group["records"]:
            libs[record["item_id"]] = scope / "frozen.db"
    return libs


def _precheck(args) -> int:
    core_sha, problem = _core_gate(args)
    if problem:
        return _fail(problem)
    import hashlib

    from starling import _core

    records = ans._load_corpus(args.corpus)
    libs = _libraries(args.builds, plan_groups(records))
    absent = [r["item_id"] for r in records if r["item_id"] not in libs]
    if absent:
        return _fail(f"{len(absent)} 道题没有可用的新库: {absent[:3]}")
    reference = [json.loads(line) for line in args.reference_rows.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
    work = args.builds / "scratch_precheck"
    profile_config = build_config(args.profile, args.profiles)
    problem = buildable_problem(profile_config)
    if problem:
        return _fail(problem)
    stub = _core.StubEmbeddingAdapter(int(profile_config["embedding_dim"]))
    ctrl_rows, hyb_rows = [], []
    for rec in records:
        for arm, rows in (("st_ctrl", ctrl_rows), ("st_hyb", hyb_rows)):
            out = recall_for_arm(arm, rec, libs[rec["item_id"]], work, embedder=stub, now_iso=args.now_iso)
            rows.append({"item_id": rec["item_id"],
                         "block_sha256": hashlib.sha256(out["block"].encode("utf-8")).hexdigest(),
                         "turn_ids": [ref.get("turn_id") for ref in out["source_refs"]]})
    if work.exists() and not any(work.iterdir()):
        work.rmdir()
    result = {"core_sha256": core_sha, "reference_arm": CONTROL_REFERENCE_ARM,
              **precheck_summary(ctrl_rows, hyb_rows, reference)}
    (args.builds / "precheck.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ready"] else 2


def _coverage(args) -> int:
    records = ans._load_corpus(args.corpus)
    items, groups = {}, {}
    for group in plan_groups(records):
        scope = args.builds / "runs" / group["group_id"]
        status = scope_status(scope)
        groups[group["group_id"]] = status
        if status not in ("complete", "partial"):
            continue
        with closing(sqlite3.connect((scope / "frozen.db").resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            rows = conn.execute("select holder_id, semantic_claim_json from statements "
                                "where semantic_claim_json is not null and semantic_claim_json != ''").fetchall()
        linked, owned = linked_turn_ids(rows, group["history"])
        for rec in group["records"]:
            items[rec["item_id"]] = dict(gold_link_coverage(rec, linked, owned), query_type=rec["query_type"],
                                         scope=status, claims=len(rows))
    summary: dict = {}
    for item in items.values():
        for key in (item["query_type"], "ALL", f"scope:{item['scope']}"):
            cell = summary.setdefault(key, {"questions": 0, "gold": 0, "linked": 0, "owned": 0,
                                            "all_linked": 0, "all_owned": 0})
            cell["questions"] += 1
            for name in ("gold", "linked", "owned"):
                cell[name] += item[name]
            cell["all_linked"] += int(item["all_linked"])
            cell["all_owned"] += int(item["all_owned"])
    result = {"groups": groups, "summary": summary, "items": items}
    (args.builds / "coverage.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _report(args) -> int:
    records = ans._load_corpus(args.corpus)
    rows_by_arm = {arm: ans.load_rows(args.out / f"{arm}_journal.jsonl", arm) for arm in ARMS
                   if (args.out / f"{arm}_journal.jsonl").exists()}
    if "st_ctrl" not in rows_by_arm or "st_hyb" not in rows_by_arm:
        return _fail("报告至少需要 st_ctrl 与 st_hyb 两个臂的 journal。")
    text = json.dumps(build_report(records, rows_by_arm), ensure_ascii=False, indent=2)
    if args.result is not None:
        args.result.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


# ---------------------------- 作答 ----------------------------

def _answer(args) -> int:
    isolation = args.arm in ISOLATION_ARMS
    if isolation and args.items is None:
        return _fail("隔离臂必须给 --items 题号名单。")
    if not isolation and args.items is not None:
        return _fail("--items 只用于隔离臂;常规臂答 110 题全集。")
    if not args.real_run:
        return _fail("缺 --real-run:answer 会发出真实作答与裁判请求,拒绝误触网络。")
    core_sha, problem = _core_gate(args)
    if problem:
        return _fail(problem)
    built = args.builds / "config.json"
    if not built.is_file():
        return _fail(f"缺建库配置: {built}")
    built_config = json.loads(built.read_text(encoding="utf-8"))
    if built_config.get("profile") != args.profile:
        return _fail(f"建库用的 profile 是 {built_config.get('profile')},与本次 --profile {args.profile} 不一致。")
    profile_config = build_config(args.profile, args.profiles)
    problem = buildable_problem(profile_config) or check_built_matches(built_config, profile_config)
    if problem:
        return _fail(problem)
    config = dict(profile_config, core_sha256=core_sha)
    with answer_channel(config):
        return _answer_impl(args, core_sha, config)


def _answer_impl(args, core_sha: str, config: dict) -> int:
    backbone = args.backbone or config["answer_model"]
    judge_model = args.judge_model or config["answer_model"]
    pre = args.builds / "precheck.json"
    if not pre.is_file() or json.loads(pre.read_text(encoding="utf-8")).get("ready") is not True:
        return _fail("缺少通过的 precheck.json:先跑零请求的 precheck。")
    try:
        prompts = proto.load_official_prompts(args.prompts, args.prompts_sha256)
    except (OSError, ValueError, ImportError) as exc:
        return _fail(f"官方提示文件不可用: {exc}")
    from starling import _core

    import eval_judge_audit as audit
    import eval_ladder as ladder

    records = ans._load_corpus(args.corpus)
    isolation, items_sha = args.arm in ISOLATION_ARMS, None
    if isolation:
        try:
            wanted = set(load_item_list(args.items, records))
        except (OSError, ValueError) as exc:
            return _fail(f"题号名单不可用: {exc}")
        records = [r for r in records if r["item_id"] in wanted]
        items_sha = ans._sha256_file(args.items)
    if args.limit > 0:
        records = records[:args.limit]
    libs = _libraries(args.builds, plan_groups(ans._load_corpus(args.corpus)))
    absent = [r["item_id"] for r in records if r["item_id"] not in libs]
    if absent:
        return _fail(f"{len(absent)} 道题没有可用的新库: {absent[:3]}")
    if isolation:
        iso_path = args.out / "isolation_precheck.json"
        iso_pre = json.loads(iso_path.read_text(encoding="utf-8")) if iso_path.is_file() else None
        problem = isolation_precheck_problem(iso_pre, args.arm, items_sha256=items_sha, core_sha256=core_sha)
        if problem:
            return _fail(problem)
        chosen = {r["item_id"]: libs[r["item_id"]] for r in records}
        if args.arm == _NOCLAIM:
            chosen = stripped_library_paths(chosen, args.out)
        problem = isolation_library_problem(iso_pre, args.arm, chosen)
        if problem:
            return _fail(problem)
        libs = chosen
    embedder = (_core.StubEmbeddingAdapter(8) if arm_spec(args.arm)["mode"] == "sources"
                else make_adapters(_core, config)[1])
    answerer = ladder.make_real_answerer_fn(max_tokens=ladder.OFFICIAL_ANSWER_MAX_TOKENS, enable_thinking=False)
    judge = proto.make_official_judge_fn(audit._chat_completion, prompts)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    used = sorted({libs[r["item_id"]] for r in records})
    manifest = {"arm": args.arm, "spec": arm_spec(args.arm), "profile": config["profile"], "core_sha256": core_sha,
                "corpus_sha256": ans._sha256_file(args.corpus), "prompts_sha256": args.prompts_sha256,
                "profiles_sha256": profiles_sha256(args.profiles),
                "backbone": backbone, "judge_model": judge_model, "now_iso": args.now_iso,
                "questions": len(records), "libraries": {p.parent.name: ans._sha256_file(p) for p in used},
                "build_config_sha256": ans._sha256_file(args.builds / "config.json"),
                "code_sha256": {Path(__file__).name: ans._sha256_file(__file__)}}
    if isolation:
        manifest.update(items_sha256=items_sha, items=len(records),
                        variant="claims_cleared" if args.arm == _NOCLAIM else "original_library")
    (out / f"manifest_{args.arm}.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8")
    work = out / f"scratch_{args.arm}"

    def answer_for(rec: dict, recall: dict) -> dict:
        row = ans.answer_item(rec, recall, prompts=prompts, answerer=answerer, judge=judge, strict_judge=None,
                              backbone=backbone, judge_model=judge_model)
        row["statement_count"] = recall["statement_count"]
        return row

    rows = ans.run_arm(
        args.arm, records,
        lambda rec: recall_for_arm(args.arm, rec, libs[rec["item_id"]], work, embedder=embedder,
                                   now_iso=args.now_iso),
        answer_for, journal=out / f"{args.arm}_journal.jsonl")
    if work.exists() and not any(work.iterdir()):
        work.rmdir()
    print(json.dumps({"arm": args.arm, "answered": len(rows), "questions": len(records),
                      "errors": len(records) - len(rows)}, ensure_ascii=False))
    return 0


def _isolation_precheck(args) -> int:
    stripped_root = args.out / "stripped"
    if stripped_root.exists() and any(stripped_root.rglob("*")):
        return _fail(f"{stripped_root} 已有内容,拒绝覆盖;先人工核对再处理。")
    core_sha, problem = _core_gate(args)
    if problem:
        return _fail(problem)
    from starling import _core

    records = ans._load_corpus(args.corpus)
    try:
        items = load_item_list(args.items, records)
    except (OSError, ValueError) as exc:
        return _fail(f"题号名单不可用: {exc}")
    libs = _libraries(args.builds, plan_groups(records))
    absent = [i for i in items if i not in libs]
    if absent:
        return _fail(f"{len(absent)} 道题没有可用的新库: {absent[:3]}")
    original = ans.load_rows(args.original_journal, "st_ctrl")
    lacking = [i for i in items if i not in original]
    if lacking:
        return _fail(f"原 st_ctrl 日志缺 {len(lacking)} 道名单里的题: {lacking[:3]}")
    reference = [json.loads(line) for line in args.reference_rows.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
    by_id = {r["item_id"]: r for r in records}
    chosen = {i: libs[i] for i in items}
    used = sorted(set(chosen.values()))
    before = {p.parent.name: ans._sha256_file(p) for p in used}
    stripped = stripped_library_paths(chosen, args.out)
    strip_info = {}
    for lib in used:
        strip_info[lib.parent.name] = strip_claims(lib, args.out / "stripped" / lib.parent.name / "frozen.db")
    stub = _core.StubEmbeddingAdapter(8)
    work = args.out / "scratch_isolation_precheck"
    rows = {arm: [] for arm in ISOLATION_ARMS}
    for item in items:
        for arm, lib in ((_NOCLAIM, stripped[item]), (_REPEAT, chosen[item])):
            out = recall_for_arm(arm, by_id[item], lib, work, embedder=stub, now_iso=args.now_iso)
            rows[arm].append({"item_id": item, "block_sha256": hashlib.sha256(out["block"].encode("utf-8")).hexdigest(),
                              "turn_ids": [ref.get("turn_id") for ref in out["source_refs"]]})
    if work.exists() and not any(work.iterdir()):
        work.rmdir()
    after = {p.parent.name: ans._sha256_file(p) for p in used}
    if after != before:
        return _fail("源库哈希在复制与重放前后不一致,停止,不写门文件。")
    gates = {arm: isolation_gate(arm, rows[arm], reference=reference, original=original) for arm in ISOLATION_ARMS}
    result = {"core_sha256": core_sha, "items_sha256": ans._sha256_file(args.items), "items": len(items),
              "reference_arm": CONTROL_REFERENCE_ARM, "gates": gates,
              "ready": all(g["ready"] for g in gates.values()),
              "source_sha256": before, "source_sha256_after": after,
              "stripped_sha256": {p.parent.name: ans._sha256_file(p) for p in stripped.values()},
              "stripped": strip_info}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "isolation_precheck.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                                      encoding="utf-8")
    print(json.dumps({"gates": gates, "ready": result["ready"], "stripped": strip_info}, ensure_ascii=False))
    return 0 if result["ready"] else 2


def _isolation_report(args) -> int:
    records = ans._load_corpus(args.corpus)
    try:
        items = load_item_list(args.items, records)
    except (OSError, ValueError) as exc:
        return _fail(f"题号名单不可用: {exc}")
    original = ans.load_rows(args.original_journal, "st_ctrl")
    rows_by_arm = {}
    for arm in ISOLATION_ARMS:
        journal = args.out / f"{arm}_journal.jsonl"
        if not journal.exists():
            return _fail(f"缺 {arm} 的 journal: {journal}")
        rows_by_arm[arm] = ans.load_rows(journal, arm)
    try:
        report = build_isolation_report(records, items, original, rows_by_arm)
    except ValueError as exc:
        return _fail(str(exc))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.result is not None:
        args.result.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    common.add_argument("--require-core-sha256", default=None)
    common.add_argument("--profile", default=None, help="profiles 文件里的配置名;缺省取文件里的 default_profile")
    common.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES, help="profiles 文件路径")
    build = sub.add_parser("build", parents=[common], help="新建声明合同库(需 --real-run)")
    build.add_argument("--out", type=Path, required=True)
    build.add_argument("--workers", type=int, default=4)
    build.add_argument("--resume", action="store_true")
    build.add_argument("--stop-after-smoke", action="store_true")
    build.add_argument("--real-run", action="store_true")
    pre = sub.add_parser("precheck", parents=[common], help="零请求:对照臂复现检查")
    pre.add_argument("--builds", type=Path, required=True)
    pre.add_argument("--reference-rows", type=Path, default=DEFAULT_REFERENCE)
    pre.add_argument("--now-iso", default=NOW_ISO)
    cov = sub.add_parser("coverage", parents=[common], help="零请求:金标话轮回链覆盖")
    cov.add_argument("--builds", type=Path, required=True)
    answer = sub.add_parser("answer", parents=[common], help="对一个臂发出作答与判分请求(需 --real-run)")
    answer.add_argument("--arm", choices=ARMS + ISOLATION_ARMS, required=True)
    answer.add_argument("--out", type=Path, required=True)
    answer.add_argument("--builds", type=Path, required=True)
    answer.add_argument("--prompts", type=Path, required=True)
    answer.add_argument("--prompts-sha256", required=True)
    answer.add_argument("--backbone", default=None)
    answer.add_argument("--judge-model", default=None)
    answer.add_argument("--now-iso", default=NOW_ISO)
    answer.add_argument("--limit", type=int, default=0)
    answer.add_argument("--items", type=Path, default=None, help="题号名单,只用于隔离臂")
    answer.add_argument("--real-run", action="store_true")
    report = sub.add_parser("report", parents=[common], help="零请求:汇总配对读数")
    report.add_argument("--out", type=Path, required=True)
    report.add_argument("--result", type=Path, default=None)
    iso_pre = sub.add_parser("isolation-precheck", parents=[common], help="零请求:隔离臂的库副本与来源门")
    iso_pre.add_argument("--builds", type=Path, required=True)
    iso_pre.add_argument("--out", type=Path, required=True)
    iso_pre.add_argument("--items", type=Path, required=True)
    iso_pre.add_argument("--original-journal", type=Path, required=True)
    iso_pre.add_argument("--reference-rows", type=Path, default=DEFAULT_REFERENCE)
    iso_pre.add_argument("--now-iso", default=NOW_ISO)
    iso_rep = sub.add_parser("isolation-report", parents=[common], help="零请求:隔离臂的配对读数")
    iso_rep.add_argument("--out", type=Path, required=True)
    iso_rep.add_argument("--items", type=Path, required=True)
    iso_rep.add_argument("--original-journal", type=Path, required=True)
    iso_rep.add_argument("--result", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        args.profile = args.profile or default_profile_name(args.profiles)
        build_config(args.profile, args.profiles)
    except ValueError as exc:
        parser.error(str(exc))
    handler = {"build": _build, "precheck": _precheck, "coverage": _coverage, "answer": _answer,
               "report": _report, "isolation-precheck": _isolation_precheck,
               "isolation-report": _isolation_report}[args.cmd]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
