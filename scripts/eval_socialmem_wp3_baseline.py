#!/usr/bin/env python3
"""WP3:来源路径基线(开发切分 Q1 Q3 Q7 Q8,不建库)。

登记见 build/prereg_wp3_source_baseline.md。子命令:
  precheck  零请求:在九月来源保留库上回放一次,来源话轮序列必须与登记参照逐题相同
  answer    对唯一的臂发出作答与判分请求(需 --real-run,需通过的 precheck.json)
  report    零请求:每类与全体的描述性读数,按网络整体重采样给区间
只有一个臂,没有对照,所以没有增益或退步的判定。没有 --real-run 不发任何请求。
模型、端点与钥匙变量名只写在 profiles 文件里,本文件不点名任何模型。"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import eval_official_protocol as proto  # noqa: E402
import eval_socialmem_source_answer as ans  # noqa: E402
import eval_socialmem_source_matrix as matrix  # noqa: E402
import eval_socialmem_structured_build as sb  # noqa: E402

ARM = "wp3_src_v9"
WP3_TYPES = ("Q1", "Q3", "Q7", "Q8")
NOW_ISO = "2026-12-08T00:00:00Z"
DEFAULT_CORPUS = Path("build/wp3/wp3_dev_corpus.jsonl")
DEFAULT_SOURCE = Path("build/socialmem_20260917_source_focus")
DEFAULT_REFERENCE = Path("build/wp3/replay_precheck.json")
_SPEC = {"mode": "sources", "strategy": "evidence_profile_v9", "k": 30, "max_context_bytes": 24000}


def arm_spec() -> dict:
    return dict(_SPEC)


# ---------------------------- 零请求门 ----------------------------

def replay_gate(rows: list[dict], reference: dict) -> dict:
    """来源话轮序列必须与登记参照逐题相同,题数也必须相同,才放行。"""
    want = {r["item_id"]: r["turn_ids"] for r in reference.get("rows", [])}
    got = {r["item_id"]: r["turn_ids"] for r in rows}
    differing = sorted(i for i in want if got.get(i) != want[i])
    equal = len(want) - len(differing)
    return {"equal": equal, "of": len(want), "ready": bool(want) and not differing and set(got) == set(want),
            "differing": differing}


def recall(record: dict, library, work, *, now_iso: str = NOW_ISO) -> dict:
    """在库的临时副本上回放一次来源召回(sources 模式,桩嵌入)。"""
    import eval_ladder_pipeline as pipe
    from starling import _core

    spec = arm_spec()
    holders = sorted({str(t["speaker"]) for t in record["history"]})
    with matrix._library_copy(library, work, f"{ARM}|{record['item_id']}") as ctx:
        out = pipe.recall_observer_block(
            ctx.core, adapter=ctx.rt.adapter, embedder=_core.StubEmbeddingAdapter(8), index=ctx.index,
            question=record["question"], allowed_holders=holders, mode=spec["mode"], now_iso=now_iso,
            k=spec["k"], max_context_bytes=spec["max_context_bytes"], include_unknown_time=True,
            source_strategy=spec["strategy"])
    return {"source_refs": out["source_refs"], "context_bytes": int(out["context_bytes"]),
            "source_count": int(out["source_count"]), "block": out["block"]}


# ---------------------------- 读数 ----------------------------

def network_bootstrap(items: list[tuple], *, seed: int, draws: int) -> dict:
    """items:[(网络号, 分数)]。均值的区间按网络整体重采样:每次抽同样多的网络(有放回),
    均值取分数总和除以题数,2.5% 与 97.5% 分位线性插值。"""
    if not items:
        raise ValueError("items required")
    cells: dict[str, list] = defaultdict(lambda: [0.0, 0])
    for network, score in items:
        cells[network][0] += score
        cells[network][1] += 1
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

    return {"mean": sum(s for _, s in items) / len(items), "networks": len(keys),
            "lo": quantile(0.025), "hi": quantile(0.975)}


def build_report(records: list[dict], rows: dict, *, seed: int = ans.BOOTSTRAP_SEED,
                 draws: int = ans.BOOTSTRAP_DRAWS) -> dict:
    """每类与全体的官方均分、0.7 以上计数与按网络的区间。裁判坏状态的行不进汇总,单列。"""
    missing = [r["item_id"] for r in records if r["item_id"] not in rows]
    excluded = [r["item_id"] for r in records if r["item_id"] in rows
                and rows[r["item_id"]].get("judge_status") in proto.BAD_JUDGE_STATUSES]
    usable = [r for r in records if r["item_id"] in rows and r["item_id"] not in excluded]

    def cell(recs: list[dict]) -> dict:
        if not recs:
            return {"n": 0, "mean_score": None, "ge07": 0, "networks": 0, "lo": None, "hi": None}
        items = [(r["source"]["network_id"], float(rows[r["item_id"]]["score"])) for r in recs]
        boot = network_bootstrap(items, seed=seed, draws=draws)
        return {"n": len(recs), "mean_score": boot["mean"], "ge07": sum(1 for r in recs if rows[r["item_id"]]["ok"]),
                "networks": boot["networks"], "lo": boot["lo"], "hi": boot["hi"]}

    by_type = {qt: cell([r for r in usable if r["query_type"] == qt]) for qt in WP3_TYPES}
    return {"arm": ARM, "questions": len(records), "answered": len(records) - len(missing),
            "missing": missing, "excluded": excluded, "by_type": by_type, "overall": cell(usable),
            "complete": not missing and not excluded, "bootstrap": {"seed": seed, "draws": draws}}


# ---------------------------- 命令 ----------------------------

def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def _load(args):
    records = ans._load_corpus(args.corpus)
    if args.limit > 0:
        records = records[:args.limit]
    return records


def _libraries(args, records):
    libs = ans.library_index(args.source)
    absent = [r["item_id"] for r in records if r["item_id"] not in libs]
    if absent:
        return None, f"{len(absent)} 道题没有九月来源库: {absent[:3]}"
    return libs, None


def _precheck(args) -> int:
    core_sha, problem = sb._core_gate(args)
    if problem:
        return _fail(problem)
    records = _load(args)
    libs, problem = _libraries(args, records)
    if problem:
        return _fail(problem)
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    work = args.out / "scratch_precheck"
    rows = []
    for rec in records:
        out = recall(rec, libs[rec["item_id"]], work, now_iso=args.now_iso)
        rows.append({"item_id": rec["item_id"], "turn_ids": [ref.get("turn_id") for ref in out["source_refs"]],
                     "block_sha256": hashlib.sha256(out["block"].encode("utf-8")).hexdigest()})
    if work.exists() and not any(work.iterdir()):
        work.rmdir()
    result = {"arm": ARM, "spec": arm_spec(), "core_sha256": core_sha, "corpus_sha256": ans._sha256_file(args.corpus),
              "reference_sha256": ans._sha256_file(args.reference), **replay_gate(rows, reference)}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "precheck.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "differing"} | {"differing": result["differing"][:5]},
                     ensure_ascii=False))
    return 0 if result["ready"] else 2


def _answer(args) -> int:
    if not args.real_run:
        return _fail("缺 --real-run:answer 会发出真实作答与裁判请求,拒绝误触网络。")
    core_sha, problem = sb._core_gate(args)
    if problem:
        return _fail(problem)
    pre_path = args.out / "precheck.json"
    pre = json.loads(pre_path.read_text(encoding="utf-8")) if pre_path.is_file() else None
    problem = sb.precheck_problem(pre, core_sha256=core_sha)
    if problem:
        return _fail(problem)
    if pre.get("corpus_sha256") != ans._sha256_file(args.corpus):
        return _fail("precheck.json 对应的语料与本次 --corpus 不一致。")
    try:
        prompts = proto.load_official_prompts(args.prompts, args.prompts_sha256)
    except (OSError, ValueError, ImportError) as exc:
        return _fail(f"官方提示文件不可用: {exc}")
    config = sb.build_config(args.profile, args.profiles)
    records = _load(args)
    libs, problem = _libraries(args, records)
    if problem:
        return _fail(problem)
    import eval_judge_audit as audit
    import eval_ladder as ladder

    backbone, judge_model = config["answer_model"], config["answer_model"]
    used = sorted({libs[r["item_id"]] for r in records})
    manifest = {"arm": ARM, "spec": arm_spec(), "profile": config["profile"], "core_sha256": core_sha,
                "corpus_sha256": ans._sha256_file(args.corpus), "prompts_sha256": args.prompts_sha256,
                "profiles_sha256": sb.profiles_sha256(args.profiles), "backbone": backbone, "judge_model": judge_model,
                "now_iso": args.now_iso, "questions": len(records),
                "libraries": {p.parent.name: ans._sha256_file(p) for p in used},
                "code_sha256": {Path(__file__).name: ans._sha256_file(__file__)}}
    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / f"manifest_{ARM}.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
    problem = sb.manifest_conflict(previous, manifest)
    if problem:
        return _fail(problem)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    work = args.out / f"scratch_{ARM}"
    with sb.answer_channel(config):
        answerer = ladder.make_real_answerer_fn(max_tokens=ladder.OFFICIAL_ANSWER_MAX_TOKENS, enable_thinking=False)
        judge = proto.make_official_judge_fn(audit._chat_completion, prompts)
        rows = ans.run_arm(
            ARM, records,
            lambda rec: recall(rec, libs[rec["item_id"]], work, now_iso=args.now_iso),
            lambda rec, rc: ans.answer_item(rec, rc, prompts=prompts, answerer=answerer, judge=judge,
                                            strict_judge=None, backbone=backbone, judge_model=judge_model),
            journal=args.out / f"{ARM}_journal.jsonl")
    if work.exists() and not any(work.iterdir()):
        work.rmdir()
    print(json.dumps({"arm": ARM, "answered": len(rows), "questions": len(records),
                      "errors": len(records) - len(rows)}, ensure_ascii=False))
    return 0


def _report(args) -> int:
    records = ans._load_corpus(args.corpus)
    journal = args.out / f"{ARM}_journal.jsonl"
    if not journal.exists():
        return _fail(f"缺 journal: {journal}")
    text = json.dumps(build_report(records, ans.load_rows(journal, ARM)), ensure_ascii=False, indent=2)
    if args.result is not None:
        args.result.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out", type=Path, required=True)
    common.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    common.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    common.add_argument("--require-core-sha256", default=None)
    common.add_argument("--now-iso", default=NOW_ISO)
    common.add_argument("--limit", type=int, default=0)
    pre = sub.add_parser("precheck", parents=[common], help="零请求:回放并与登记参照比对")
    pre.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    answer = sub.add_parser("answer", parents=[common], help="发出作答与判分请求(需 --real-run)")
    answer.add_argument("--prompts", type=Path, required=True)
    answer.add_argument("--prompts-sha256", required=True)
    answer.add_argument("--profile", default=None)
    answer.add_argument("--profiles", type=Path, default=sb.DEFAULT_PROFILES)
    answer.add_argument("--real-run", action="store_true")
    report = sub.add_parser("report", parents=[common], help="零请求:描述性读数")
    report.add_argument("--result", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.cmd == "answer":
        try:
            args.profile = args.profile or sb.default_profile_name(args.profiles)
        except ValueError as exc:
            parser.error(str(exc))
    return {"precheck": _precheck, "answer": _answer, "report": _report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
