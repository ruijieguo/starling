#!/usr/bin/env python3
"""WP3 全上下文参照臂(开发切分 Q1 Q3 Q7 Q8):每题把整段历史按官方全上下文格式交给作答模型,
再用官方裁判打分,与来源路径基线 wp3_src_v9 逐题配对描述差距。登记见 build/prereg_wp3_fullctx.md。

不建库、不召回、不嵌入:提示只由题目自带的历史和官方 llm_answer 模板构成。
作答模型、端点与钥匙变量名来自 profiles 文件,本文件不点名任何模型。
没有 --real-run 不发任何请求;作答前必须有通过的零请求 precheck.json。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_official_protocol as proto  # noqa: E402
import eval_socialmem_source_answer as ans  # noqa: E402
import eval_socialmem_structured_build as sb  # noqa: E402
import eval_socialmem_wp3_baseline as wp3  # noqa: E402

ARM = "wp3_full_ctx"
SRC_ARM = wp3.ARM


def arm_spec() -> dict:
    return {"mode": "full_context", "format": "official", "template": "llm_answer",
            "history": "whole_history_per_question"}


def build_prompt(prompts: dict, record: dict) -> str:
    """官方全上下文提示:llm_answer 模板加官方写法的整段历史。"""
    return proto.official_answer_prompt(
        prompts, record, [proto.official_full_context(record.get("history", []))], full_context=True)


def prompt_gate(records: list[dict], prompts: dict, *, expected_questions: int, expected_total_bytes: int) -> dict:
    """零请求门:逐题造出提示,题数与提示总字节必须等于登记值,不得有空历史。"""
    sizes: list[int] = []
    empty: list[str] = []
    for rec in records:
        if not rec.get("history"):
            empty.append(rec["item_id"])
        sizes.append(len(build_prompt(prompts, rec).encode("utf-8")))
    total = sum(sizes)
    problems: list[str] = []
    if len(records) != expected_questions:
        problems.append(f"questions: 题数 {len(records)} 不等于登记的 {expected_questions}")
    if total != expected_total_bytes:
        problems.append(f"total_bytes: 提示总字节 {total} 不等于登记的 {expected_total_bytes}")
    if empty:
        problems.append(f"empty_history: {len(empty)} 题历史为空,例 {empty[:5]}")
    return {"questions": len(records), "total_bytes": total, "max_bytes": max(sizes) if sizes else 0,
            "empty_history": empty, "problems": problems, "ready": not problems}


def answer_row(record: dict, *, prompts: dict, answerer, judge, backbone: str, judge_model: str) -> dict:
    """官方口径作答并判分:0 到 1 分项裁判,大于等于 0.7 记正确。只答开放式题,遇选择题在发请求前抛错。"""
    fmt = record.get("answer_format", "multiple_choice")
    if fmt == "multiple_choice":
        raise ValueError("全上下文参照臂只答开放式题,选择题不在本步范围")
    context = proto.official_full_context(record.get("history", []))
    prompt = build_prompt(prompts, record)
    response = answerer(prompt, backbone)
    verdict = judge(record["question"], str(record["answer"]), response, judge_model or backbone)
    return {"item_id": record["item_id"], "query_type": record.get("query_type"), "answer_format": fmt,
            "context_bytes": len(context.encode("utf-8")), "prompt": prompt, "response": response,
            "judge_status": verdict["status"], "judge_raw": verdict["raw"],
            "judge_rationale": verdict["rationale"], "score": verdict["score"],
            "ok": proto.official_is_correct(verdict["score"])}


def build_report(records: list[dict], rows: dict, *, seed: int = ans.BOOTSTRAP_SEED,
                 draws: int = ans.BOOTSTRAP_DRAWS) -> dict:
    """每类与全体的描述读数,口径与来源路径基线报告完全相同,只换臂名。"""
    report = wp3.build_report(records, rows, seed=seed, draws=draws)
    report["arm"] = ARM
    return report


def _usable(rows: dict, item: str) -> bool:
    row = rows.get(item)
    return row is not None and row.get("judge_status") not in proto.BAD_JUDGE_STATUSES


def paired_report(records: list[dict], src_rows: dict, full_rows: dict, *, seed: int = ans.BOOTSTRAP_SEED,
                  draws: int = ans.BOOTSTRAP_DRAWS) -> dict:
    """来源路径减全上下文,逐题配对,只取两臂都有可用分数的题。区间按网络整体重采样。
    读法沿用登记规则 1(来源路径是否已接近全历史),对每类与全体各读一次。"""
    paired = [r for r in records if _usable(src_rows, r["item_id"]) and _usable(full_rows, r["item_id"])]
    paired_ids = {r["item_id"] for r in paired}
    unpaired = [r["item_id"] for r in records if r["item_id"] not in paired_ids]

    def cell(recs: list[dict]) -> dict:
        if not recs:
            return {"n": 0, "networks": 0, "mean_src": None, "mean_full": None,
                    "delta": None, "lo": None, "hi": None, "reading": None}
        items = [(r["source"]["network_id"], float(full_rows[r["item_id"]]["score"]),
                  float(src_rows[r["item_id"]]["score"])) for r in recs]
        boot = ans.paired_network_bootstrap(items, seed=seed, draws=draws)
        return {"n": boot["n"], "networks": boot["networks"], "mean_src": boot["mean_b"],
                "mean_full": boot["mean_a"], "delta": boot["delta"], "lo": boot["lo"], "hi": boot["hi"],
                "reading": ans.read_base_vs_full(boot["delta"], boot["lo"])}

    return {"arms": {"src": SRC_ARM, "full": ARM}, "questions": len(records), "paired": len(paired),
            "unpaired": unpaired, "by_type": {qt: cell([r for r in paired if r["query_type"] == qt])
                                              for qt in wp3.WP3_TYPES},
            "overall": cell(paired), "complete": not unpaired, "bootstrap": {"seed": seed, "draws": draws}}


def precheck_problem(pre, *, corpus_sha256: str, prompts_sha256: str) -> str | None:
    """作答前核对放行门文件:存在、ready 为真、对应同一份语料与同一份官方提示。"""
    if not isinstance(pre, dict):
        return "缺少 precheck.json:先跑零请求的 precheck。"
    if pre.get("ready") is not True:
        return "precheck.json 的 ready 不为真:先跑零请求的 precheck 并确认通过。"
    if pre.get("corpus_sha256") != corpus_sha256:
        return "precheck.json 对应的语料与本次 --corpus 不一致。"
    if pre.get("prompts_sha256") != prompts_sha256:
        return "precheck.json 对应的官方提示与本次 --prompts-sha256 不一致。"
    return None


# ---------------------------- 命令 ----------------------------

def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def _precheck(args) -> int:
    try:
        prompts = proto.load_official_prompts(args.prompts, args.prompts_sha256)
    except (OSError, ValueError, ImportError) as exc:
        return _fail(f"官方提示文件不可用: {exc}")
    records = ans._load_corpus(args.corpus)
    gate = prompt_gate(records, prompts, expected_questions=args.expected_questions,
                       expected_total_bytes=args.expected_total_bytes)
    result = {"arm": ARM, "spec": arm_spec(), "corpus_sha256": ans._sha256_file(args.corpus),
              "prompts_sha256": args.prompts_sha256, "expected_questions": args.expected_questions,
              "expected_total_bytes": args.expected_total_bytes, "questions": gate["questions"],
              "total_bytes": gate["total_bytes"], "max_bytes": gate["max_bytes"],
              "empty_history_count": len(gate["empty_history"]), "problems": gate["problems"],
              "ready": gate["ready"]}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "precheck.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ready"] else 2


def _answer(args) -> int:
    if not args.real_run:
        return _fail("缺 --real-run:answer 会发出真实作答与裁判请求,拒绝误触网络。")
    pre_path = args.out / "precheck.json"
    pre = json.loads(pre_path.read_text(encoding="utf-8")) if pre_path.is_file() else None
    problem = precheck_problem(pre, corpus_sha256=ans._sha256_file(args.corpus), prompts_sha256=args.prompts_sha256)
    if problem:
        return _fail(problem)
    try:
        prompts = proto.load_official_prompts(args.prompts, args.prompts_sha256)
    except (OSError, ValueError, ImportError) as exc:
        return _fail(f"官方提示文件不可用: {exc}")
    core_sha, problem = sb._core_gate(args)
    if problem:
        return _fail(problem)
    config = sb.build_config(args.profile, args.profiles)
    records = ans._load_corpus(args.corpus)
    import eval_judge_audit as audit
    import eval_ladder as ladder

    backbone, judge_model = config["answer_model"], config["answer_model"]
    manifest = {"arm": ARM, "spec": arm_spec(), "profile": config["profile"], "core_sha256": core_sha,
                "corpus_sha256": ans._sha256_file(args.corpus), "prompts_sha256": args.prompts_sha256,
                "profiles_sha256": sb.profiles_sha256(args.profiles), "backbone": backbone,
                "judge_model": judge_model, "answer_max_tokens": ladder.OFFICIAL_ANSWER_MAX_TOKENS,
                "enable_thinking": False, "questions": len(records),
                "code_sha256": {Path(__file__).name: ans._sha256_file(__file__)}}
    manifest_path = args.out / f"manifest_{ARM}.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
    problem = sb.manifest_conflict(previous, manifest)
    if problem:
        return _fail(problem)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with sb.answer_channel(config):
        answerer = ladder.make_real_answerer_fn(max_tokens=ladder.OFFICIAL_ANSWER_MAX_TOKENS, enable_thinking=False)
        judge = proto.make_official_judge_fn(audit._chat_completion, prompts)
        rows = ans.run_arm(
            ARM, records, lambda rec: None,
            lambda rec, _recall: answer_row(rec, prompts=prompts, answerer=answerer, judge=judge,
                                            backbone=backbone, judge_model=judge_model),
            journal=args.out / f"{ARM}_journal.jsonl")
    print(json.dumps({"arm": ARM, "answered": len(rows), "questions": len(records),
                      "errors": len(records) - len(rows)}, ensure_ascii=False))
    return 0


def _report(args) -> int:
    records = ans._load_corpus(args.corpus)
    journal = args.out / f"{ARM}_journal.jsonl"
    for path in (journal, args.src_journal):
        if not path.exists():
            return _fail(f"缺 journal: {path}")
    full_rows = ans.load_rows(journal, ARM)
    src_rows = ans.load_rows(args.src_journal, SRC_ARM)
    text = json.dumps({"full_ctx": build_report(records, full_rows),
                       "paired": paired_report(records, src_rows, full_rows)}, ensure_ascii=False, indent=2)
    if args.result is not None:
        args.result.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--corpus", type=Path, required=True)
        p.add_argument("--out", type=Path, required=True)

    def prompts_args(p):
        p.add_argument("--prompts", type=Path, required=True)
        p.add_argument("--prompts-sha256", required=True)

    pre = sub.add_parser("precheck", help="零请求:造全部提示并核对登记的题数与总字节")
    common(pre)
    prompts_args(pre)
    pre.add_argument("--expected-questions", type=int, required=True)
    pre.add_argument("--expected-total-bytes", type=int, required=True)
    run = sub.add_parser("answer", help="真跑:作答加官方裁判,需要 --real-run 与通过的 precheck.json")
    common(run)
    prompts_args(run)
    run.add_argument("--profile", default=None)
    run.add_argument("--profiles", type=Path, default=sb.DEFAULT_PROFILES)
    run.add_argument("--require-core-sha256", default=None)
    run.add_argument("--real-run", action="store_true")
    rep = sub.add_parser("report", help="零请求:读 journal 出每类读数与配对差")
    common(rep)
    rep.add_argument("--src-journal", type=Path, required=True)
    rep.add_argument("--result", type=Path, default=None)
    args = parser.parse_args(argv)
    return {"precheck": _precheck, "answer": _answer, "report": _report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
