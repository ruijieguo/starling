#!/usr/bin/env python3
"""WP1.B:来源路径答题读数(官方口径,零抽取)。

三个臂:src_base(九月来源路径配置:focused_window、k 30、8000 字节)、src_gold(只给金标话轮)、
src_gold_ctx(金标话轮加同会话邻接话轮)。两个金标臂是构造出来的参照,不是系统能力。
检索、过滤、预算与渲染都在 C++ 核心完成,本脚本只做编排、留痕与统计。
登记见 build/prereg_wp1b_source_answer.md(本机文件):阈值与读法先于任何答题请求写定。
真实请求只在 `run` 子命令里发生,且必须显式给 --real-run;`report` 完全离线。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import eval_official_protocol as proto  # noqa: E402
import eval_socialmem_source_matrix as matrix  # noqa: E402

ARMS = ("src_base", "src_gold", "src_gold_ctx")
# WP1.E 扩展臂:src_cov60 是 WP1.D 按登记规则选出的放大 k 来源臂;src_base_rerun 与 src_base 输入完全相同,
# 只用来量同一输入重跑一次的随机波动。WP1.B 的三个臂与既有读数不变。
ANSWER_ARMS = ARMS + ("src_cov60", "src_base_rerun")
_SPECS = {
    "src_base": {"kind": "replay", "strategy": "focused_window", "k": 30, "max_context_bytes": 8000},
    "src_gold": {"kind": "oracle", "radius": 0},
    "src_gold_ctx": {"kind": "oracle", "radius": 2},
    "src_cov60": {"kind": "replay", "strategy": "focused_coverage", "k": 60, "max_context_bytes": 16000},
    "src_base_rerun": {"kind": "replay", "strategy": "focused_window", "k": 30, "max_context_bytes": 8000},
}
BOOTSTRAP_SEED = 20261010
BOOTSTRAP_DRAWS = 5000
PRIMARY_TYPES = ("Q5", "Q9")
GUARD_TYPES = ("Q2", "Q4", "Q6")
MAX_CONSECUTIVE_FAILURES = 4       # 连续传输类失败的中止线(构造失败 ValueError 不计)
PARSE_CHECK_AFTER = 30             # 已判这么多开放题后才检查裁判解析失败率
PARSE_FAILURE_LIMIT = 0.05
BAD_JUDGE_STATUSES = ("parse_failed", "regex_fallback")   # 两者都不是裁判给出的分数:计入中止线,不进汇总
_EPS = 1e-9


def arm_spec(arm: str) -> dict:
    if arm not in _SPECS:
        raise ValueError(f"unknown arm: {arm!r}; valid={list(ANSWER_ARMS)}")
    return dict(_SPECS[arm])


def build_recall(arm: str, record: dict, library, work, *, now_iso: str) -> dict:
    spec = arm_spec(arm)
    if spec["kind"] == "replay":
        return matrix.replay_question(record, library, work, strategy=spec["strategy"], k=spec["k"],
                                      max_context_bytes=spec["max_context_bytes"], now_iso=now_iso)
    return matrix.oracle_question(record, library, work, radius=spec["radius"], now_iso=now_iso)


def answer_item(record: dict, recall: dict, *, prompts: dict, answerer, judge, strict_judge,
                backbone: str, judge_model: str) -> dict:
    """官方口径作答并判分:选择题字母比对,开放题 0 到 1 分项裁判,大于等于 0.7 记正确。"""
    lines = [line for line in recall["block"].split("\n") if line.strip()]
    prompt = proto.official_answer_prompt(prompts, record, lines)
    response = answerer(prompt, backbone)
    fmt = record.get("answer_format", "multiple_choice")
    row = {"item_id": record["item_id"], "query_type": record.get("query_type"), "answer_format": fmt,
           "recall_block": lines, "block_sha256": hashlib.sha256(recall["block"].encode("utf-8")).hexdigest(),
           "source_turn_ids": [ref.get("turn_id") for ref in recall["source_refs"]],
           "context_bytes": recall.get("context_bytes"), "source_count": recall.get("source_count"),
           "prompt": prompt, "response": response,
           "judge_status": None, "judge_raw": None, "strict_verdict": None}
    if fmt == "multiple_choice":
        ok = proto.official_mc_correct(response, record)
        row.update(ok=ok, score=1.0 if ok else 0.0)
        return row
    reference = str(record["answer"])
    verdict = judge(record["question"], reference, response, judge_model or backbone)
    row.update(score=verdict["score"], judge_raw=verdict["raw"], judge_status=verdict["status"],
               judge_rationale=verdict["rationale"], ok=proto.official_is_correct(verdict["score"]))
    if strict_judge is not None:
        row["strict_verdict"] = bool(strict_judge(record["question"], reference, response, backbone))
    return row


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def load_rows(journal, arm: str | None = None) -> dict[str, dict]:
    """读回已完成的题:{item_id: 行}。只收 ok 为布尔的行;error 行与坏行跳过;同题后写覆盖先写。"""
    path = Path(journal)
    rows: dict[str, dict] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or not isinstance(row.get("item_id"), str) or not isinstance(row.get("ok"), bool):
            continue
        if arm is not None and row.get("arm") != arm:
            continue
        rows[row["item_id"]] = row
    return rows


def run_arm(arm: str, records: list[dict], recall_for, answer_for, *, journal) -> list[dict]:
    """逐题落盘、按题续跑。单题失败写 error 行并排除出统计(不计 0 分),下次续跑重试;
    连续 4 次非构造类失败、或裁判解析失败率超线,抛错中止。"""
    journal = Path(journal)
    done = load_rows(journal, arm)
    rows: list[dict] = []
    streak = 0
    for record in records:
        item = record["item_id"]
        if item in done:
            rows.append(done[item])
            continue
        try:
            recall = recall_for(record)
            row = dict(answer_for(record, recall))
        except Exception as exc:                      # noqa: BLE001 — 单题失败不毁整轮
            _append(journal, {"key": f"{arm}|{item}", "arm": arm, "item_id": item,
                              "error": f"{type(exc).__name__}: {exc}"})
            print(f"  ! {arm}|{item} FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            if not isinstance(exc, ValueError):
                streak += 1
                if streak >= MAX_CONSECUTIVE_FAILURES:
                    raise RuntimeError(f"abort: {streak} consecutive failures in {arm}") from exc
            continue
        streak = 0
        row.update(key=f"{arm}|{item}", arm=arm, item_id=item)
        _append(journal, row)
        rows.append(row)
        judged = [r for r in rows if r.get("judge_status")]
        if len(judged) >= PARSE_CHECK_AFTER and \
                sum(1 for r in judged if r["judge_status"] in BAD_JUDGE_STATUSES) / len(judged) > PARSE_FAILURE_LIMIT:
            raise RuntimeError(f"abort: judge parse failures or regex fallbacks above {PARSE_FAILURE_LIMIT:.0%} in {arm}")
    return rows


def paired_network_bootstrap(items, *, seed: int, draws: int) -> dict:
    """items:[(网络号, a 分, b 分)]。点估计为逐题均值差 b−a;区间按网络整体重采样,
    每次抽样取差值总和除以题数(比值估计),2.5% 与 97.5% 分位线性插值。"""
    if not items:
        raise ValueError("items required")
    cells: dict[str, list] = defaultdict(lambda: [0.0, 0])
    for network, a, b in items:
        cell = cells[network]
        cell[0] += b - a
        cell[1] += 1
    keys = sorted(cells)
    rng = random.Random(seed)
    samples = []
    for _ in range(draws):
        picks = [cells[rng.choice(keys)] for _ in keys]
        samples.append(sum(p[0] for p in picks) / sum(p[1] for p in picks))
    samples.sort()

    def quantile(q: float) -> float:
        pos = q * (len(samples) - 1)
        low = int(pos)
        high = min(low + 1, len(samples) - 1)
        return samples[low] + (samples[high] - samples[low]) * (pos - low)

    n = len(items)
    mean_a = sum(a for _, a, _ in items) / n
    mean_b = sum(b for _, _, b in items) / n
    return {"n": n, "networks": len(keys), "mean_a": mean_a, "mean_b": mean_b, "delta": mean_b - mean_a,
            "lo": quantile(0.025), "hi": quantile(0.975)}


def read_base_vs_full(delta: float, lo: float) -> str:
    """登记规则 1(src_base 减 S_full,Q5+Q9 官方均分)。"""
    if delta >= -0.05 - _EPS and lo >= -0.10 - _EPS:
        return "来源路径已接近全历史"
    if delta < -0.10 - _EPS:
        return "来源路径落后全历史"
    return "无法区分"


def read_gold_vs_base(delta: float, lo: float) -> str:
    """登记规则 2(src_gold_ctx 减 src_base,Q5+Q9 官方均分)。"""
    if delta >= 0.10 - _EPS and lo > 0:
        return "召回有可挖空间"
    if delta < 0.05 - _EPS:
        return "召回不是主要限制"
    return "无法区分"


def read_cov_mc_vs_base(delta: float, lo: float) -> str:
    """WP1.E 登记读法 1(src_cov60 减 src_base,Q2+Q6 选择题,每题记 1 或 0)。"""
    if delta >= 0.10 - _EPS and lo > 0:
        return "放大 k 有可确认的选择题增益"
    if delta < 0.05 - _EPS:
        return "放大 k 对选择题没有增益"
    return "无法区分"


def second_judge_selection(rows: list[dict], n: int) -> list[dict]:
    """二裁选取:开放题且回答非空,按 sha256(题号|臂名) 升序取前 n 份。规则先于任何分数。"""
    eligible = [r for r in rows if r.get("answer_format", "multiple_choice") != "multiple_choice"
                and str(r.get("response") or "").strip()]
    eligible.sort(key=lambda r: hashlib.sha256(f"{r['item_id']}|{r['arm']}".encode("utf-8")).hexdigest())
    return eligible[:n]


def build_report(records: list[dict], rows_by_arm: dict, full_rows: dict, *,
                 seed: int = BOOTSTRAP_SEED, draws: int = BOOTSTRAP_DRAWS) -> dict:
    by_id = {r["item_id"]: r for r in records}
    sources = dict(rows_by_arm)
    sources["S_full"] = full_rows

    def primary(item: str) -> bool:
        rec = by_id[item]
        return rec["query_type"] in PRIMARY_TYPES and rec.get("answer_format", "multiple_choice") != "multiple_choice"

    def fallback(rows: dict, item: str) -> bool:
        return rows[item].get("judge_status") == "regex_fallback"

    arms = {}
    for name, rows in sources.items():
        have = [r["item_id"] for r in records if r["item_id"] in rows]
        flagged = [i for i in have if fallback(rows, i)]
        ids = [i for i in have if primary(i) and i not in flagged]
        scores = [float(rows[i]["score"]) for i in ids]
        arms[name] = {"q5q9": {"n": len(ids), "mean_score": (sum(scores) / len(scores)) if scores else None,
                               "ge07": sum(1 for i in ids if rows[i]["ok"])},
                      "answered": len(have), "missing": len(records) - len(have),
                      "regex_fallback": flagged}
    mc = {}
    for qt in GUARD_TYPES:
        ids = [r["item_id"] for r in records
               if r["query_type"] == qt and r.get("answer_format", "multiple_choice") == "multiple_choice"]
        cell = {"n": len(ids)}
        for name, rows in sources.items():
            cell[name] = sum(1 for i in ids if i in rows and rows[i]["ok"])
        mc[qt] = cell

    def pair(a_rows: dict, b_rows: dict):
        ids = [r["item_id"] for r in records
               if r["item_id"] in a_rows and r["item_id"] in b_rows and primary(r["item_id"])
               and not fallback(a_rows, r["item_id"]) and not fallback(b_rows, r["item_id"])]
        items = [(by_id[i]["source"]["network_id"], float(a_rows[i]["score"]), float(b_rows[i]["score"])) for i in ids]
        return paired_network_bootstrap(items, seed=seed, draws=draws) if items else None

    paired = {"base_vs_full": pair(full_rows, rows_by_arm["src_base"]),
              "gold_ctx_vs_base": pair(rows_by_arm["src_base"], rows_by_arm["src_gold_ctx"]),
              "gold_ctx_vs_gold": pair(rows_by_arm["src_gold"], rows_by_arm["src_gold_ctx"])}
    if paired["base_vs_full"]:
        paired["base_vs_full"]["read"] = read_base_vs_full(paired["base_vs_full"]["delta"], paired["base_vs_full"]["lo"])
    if paired["gold_ctx_vs_base"]:
        paired["gold_ctx_vs_base"]["read"] = read_gold_vs_base(paired["gold_ctx_vs_base"]["delta"],
                                                               paired["gold_ctx_vs_base"]["lo"])
    cov = rows_by_arm.get("src_cov60")
    rerun = rows_by_arm.get("src_base_rerun")
    base_rows = rows_by_arm["src_base"]

    def mc_ids(rows_a: dict, rows_b: dict) -> list[str]:
        return [r["item_id"] for r in records
                if r["query_type"] in ("Q2", "Q6") and r.get("answer_format", "multiple_choice") == "multiple_choice"
                and r["item_id"] in rows_a and r["item_id"] in rows_b]

    report = {"arms": arms, "mc": mc, "paired": paired, "bootstrap": {"seed": seed, "draws": draws}}
    if cov:
        ids = mc_ids(base_rows, cov)
        items = [(by_id[i]["source"]["network_id"], float(base_rows[i]["ok"]), float(cov[i]["ok"])) for i in ids]
        mc_pair = paired_network_bootstrap(items, seed=seed, draws=draws) if items else None
        if mc_pair:
            mc_pair["read"] = read_cov_mc_vs_base(mc_pair["delta"], mc_pair["lo"])
        paired["cov60_vs_base_mc"] = mc_pair
        paired["cov60_vs_base_open"] = pair(base_rows, cov)
        paired["cov60_vs_full_open"] = pair(full_rows, cov)
        if paired["cov60_vs_full_open"]:
            paired["cov60_vs_full_open"]["read"] = read_base_vs_full(paired["cov60_vs_full_open"]["delta"],
                                                                     paired["cov60_vs_full_open"]["lo"])
    if rerun:
        flip_ids = mc_ids(base_rows, rerun)
        open_ids = [r["item_id"] for r in records
                    if primary(r["item_id"]) and r["item_id"] in base_rows and r["item_id"] in rerun
                    and not fallback(base_rows, r["item_id"]) and not fallback(rerun, r["item_id"])]
        diffs = [abs(float(base_rows[i]["score"]) - float(rerun[i]["score"])) for i in open_ids]
        report["noise"] = {
            "mc_q2q6_n": len(flip_ids),
            "mc_q2q6_flips": sum(1 for i in flip_ids if bool(base_rows[i]["ok"]) != bool(rerun[i]["ok"])),
            "open_n": len(open_ids),
            "open_mean_abs_diff": (sum(diffs) / len(diffs)) if diffs else None}
    return report


def _sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_corpus(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def library_index(source: Path) -> dict[str, Path]:
    """题号到九月来源库的映射(该题所在组的 frozen.db)。"""
    index: dict[str, Path] = {}
    for path in sorted(Path(source).glob("runs/*/questions/*.json")):
        index[json.loads(path.read_text(encoding="utf-8"))["item_id"]] = path.parent.parent / "frozen.db"
    return index


def _run(args) -> int:
    if not args.real_run:
        print("ERROR: 缺 --real-run:run 会发出真实作答与裁判请求,拒绝误触网络。", file=sys.stderr)
        return 1
    from starling import _core

    core_sha = _sha256_file(_core.__file__)
    if args.require_core_sha256 and core_sha != args.require_core_sha256:
        print(f"ERROR: 加载的核心 {core_sha[:12]} 不是要求的 {args.require_core_sha256[:12]}。", file=sys.stderr)
        return 1
    try:
        prompts = proto.load_official_prompts(args.prompts, args.prompts_sha256)
    except (OSError, ValueError, ImportError) as exc:
        print(f"ERROR: 官方提示文件不可用: {exc}", file=sys.stderr)
        return 1
    records = _load_corpus(args.corpus)
    if args.limit > 0:
        records = records[:args.limit]
    libraries = library_index(args.source)
    absent = [r["item_id"] for r in records if r["item_id"] not in libraries]
    if absent:
        print(f"ERROR: {len(absent)} 道题没有九月来源库: {absent[:3]}", file=sys.stderr)
        return 1
    import eval_judge_audit as audit
    import eval_ladder as ladder

    answerer = ladder.make_real_answerer_fn(max_tokens=ladder.OFFICIAL_ANSWER_MAX_TOKENS, enable_thinking=False)
    judge = proto.make_official_judge_fn(audit._chat_completion, prompts)
    strict = audit.make_real_ladder_judge_fn() if args.strict_corun else None
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    used = sorted({libraries[r["item_id"]] for r in records})
    manifest = {"arm": args.arm, "spec": arm_spec(args.arm), "core_sha256": core_sha,
                "corpus_sha256": _sha256_file(args.corpus), "prompts_sha256": args.prompts_sha256,
                "backbone": args.backbone, "judge_model": args.judge_model, "now_iso": args.now_iso,
                "strict_corun": bool(args.strict_corun), "questions": len(records),
                "libraries": {p.parent.name: _sha256_file(p) for p in used},
                "code_sha256": {Path(__file__).name: _sha256_file(__file__),
                                Path(matrix.__file__).name: _sha256_file(matrix.__file__)}}
    (out / f"manifest_{args.arm}.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                                   encoding="utf-8")
    work = out / f"scratch_{args.arm}"
    rows = run_arm(
        args.arm, records,
        lambda rec: build_recall(args.arm, rec, libraries[rec["item_id"]], work, now_iso=args.now_iso),
        lambda rec, recall: answer_item(rec, recall, prompts=prompts, answerer=answerer, judge=judge,
                                        strict_judge=strict, backbone=args.backbone, judge_model=args.judge_model),
        journal=out / f"{args.arm}_journal.jsonl")
    if work.exists() and not any(work.iterdir()):
        work.rmdir()
    print(json.dumps({"arm": args.arm, "answered": len(rows), "questions": len(records),
                      "errors": len(records) - len(rows)}, ensure_ascii=False))
    return 0


def _report(args) -> int:
    records = _load_corpus(args.corpus)
    rows_by_arm = {arm: load_rows(args.out / f"{arm}_journal.jsonl", arm)
                   for arm in ANSWER_ARMS if arm in ARMS or (args.out / f"{arm}_journal.jsonl").exists()}
    report = build_report(records, rows_by_arm, load_rows(args.full_journal))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.result is not None:
        args.result.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="对一个臂发出真实作答与裁判请求(需 --real-run)")
    run.add_argument("--arm", choices=ANSWER_ARMS, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--source", type=Path, default=Path("build/socialmem_20260917_source_focus"))
    run.add_argument("--corpus", type=Path, default=Path("build/socialmem_pilot110_corpus.jsonl"))
    run.add_argument("--prompts", type=Path, required=True)
    run.add_argument("--prompts-sha256", required=True)
    run.add_argument("--backbone", default="qwen3.8-27b")
    run.add_argument("--judge-model", default="")
    run.add_argument("--strict-corun", action="store_true")
    run.add_argument("--now-iso", default="2026-12-08T00:00:00Z")
    run.add_argument("--require-core-sha256", default=None)
    run.add_argument("--limit", type=int, default=0)
    run.add_argument("--real-run", action="store_true")
    rep = sub.add_parser("report", help="离线汇总三个臂与 S_full 的配对读数")
    rep.add_argument("--out", type=Path, required=True)
    rep.add_argument("--corpus", type=Path, default=Path("build/socialmem_pilot110_corpus.jsonl"))
    rep.add_argument("--full-journal", type=Path, required=True)
    rep.add_argument("--result", type=Path, default=None)
    args = parser.parse_args(argv)
    return _run(args) if args.cmd == "run" else _report(args)


if __name__ == "__main__":
    sys.exit(main())
