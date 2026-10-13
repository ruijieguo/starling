#!/usr/bin/env python3
"""阶段二 B:开发切分里 WP3 之外的 226 题(Q2 Q4 Q5 Q6 Q9)用现有来源路径臂补答。

登记见 build/prereg_stage2_dev226.md。臂设置与第 1 步 wp3_src_v9 完全相同,只换题;补完后与第 1 步的 507 题
合成 733 题开发基线。子命令:
  reference 零请求:从 WP1 矩阵的逐题话轮表里取出一个臂,写成零请求参照文件
  precheck  零请求:在九月来源保留库上回放一次,来源话轮序列必须与参照逐题相同
  answer    发出作答与判分请求(需 --real-run,需通过的 precheck.json)
  report    零请求:每类、选择题与开放题两大类、全体的描述读数;给了第 1 步的语料与 journal 时再给 733 题合并读数
没有对照臂,所以没有增益或退步的判定。没有 --real-run 不发任何请求。
模型、端点与钥匙变量名只写在 profiles 文件里,本文件不点名任何模型。"""
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

ARM = "stage2_src_v9"
SRC_ARM = wp3.ARM
STAGE2_TYPES = ("Q2", "Q4", "Q5", "Q6", "Q9")
DEV_TYPES = ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9")
CATEGORIES = ("multiple_choice", "open_ended")
DEFAULT_MATRIX_ARM = "evidence_profile_v9|k30|b24000"
DEFAULT_CORPUS = Path("build/stage2/dev226_corpus.jsonl")
DEFAULT_SOURCE = wp3.DEFAULT_SOURCE
DEFAULT_REFERENCE = Path("build/stage2/matrix_reference.json")
DEFAULT_MATRIX_ROWS = Path("build/wp1_matrix/full/rows.jsonl")


def arm_spec() -> dict:
    return wp3.arm_spec()


# ---------------------------- 零请求参照 ----------------------------

def reference_from_matrix(rows: list[dict], arm: str) -> dict:
    """从矩阵逐题话轮表里取一个臂,按题号排序;同一题在该臂里出现两次或该臂不存在都拒绝。"""
    chosen: dict[str, list] = {}
    for row in rows:
        if row.get("arm") != arm:
            continue
        item = row["item_id"]
        if item in chosen:
            raise ValueError(f"臂 {arm} 里题 {item} 出现两次")
        chosen[item] = list(row["turn_ids"])
    if not chosen:
        raise ValueError(f"矩阵里没有臂 {arm}")
    return {"rows": [{"item_id": i, "turn_ids": chosen[i]} for i in sorted(chosen)]}


def merge_rows(first: dict, second: dict) -> dict:
    """合并两份按题号索引的行;任何题号同时出现在两份里就拒绝,不静默覆盖。"""
    both = sorted(set(first) & set(second))
    if both:
        raise ValueError(f"{len(both)} 道题同时出现在两份 journal 里,例 {both[:3]}")
    return {**first, **second}


# ---------------------------- 读数 ----------------------------

def _category(record: dict) -> str:
    return "multiple_choice" if record.get("answer_format", "multiple_choice") == "multiple_choice" else "open_ended"


def build_report(records: list[dict], rows: dict, *, seed: int = ans.BOOTSTRAP_SEED,
                 draws: int = ans.BOOTSTRAP_DRAWS, types: tuple = STAGE2_TYPES, arm: str = ARM) -> dict:
    """每类、选择题与开放题两大类、全体的官方均分、0.7 以上计数与按网络的区间。
    只看 types 里的题;裁判坏状态的行不进汇总,单列。"""
    recs = [r for r in records if r["query_type"] in types]
    missing = [r["item_id"] for r in recs if r["item_id"] not in rows]
    excluded = [r["item_id"] for r in recs if r["item_id"] in rows
                and rows[r["item_id"]].get("judge_status") in proto.BAD_JUDGE_STATUSES]
    usable = [r for r in recs if r["item_id"] in rows and r["item_id"] not in excluded]

    def cell(group: list[dict]) -> dict:
        if not group:
            return {"n": 0, "mean_score": None, "ge07": 0, "networks": 0, "lo": None, "hi": None}
        items = [(r["source"]["network_id"], float(rows[r["item_id"]]["score"])) for r in group]
        boot = wp3.network_bootstrap(items, seed=seed, draws=draws)
        return {"n": len(group), "mean_score": boot["mean"],
                "ge07": sum(1 for r in group if rows[r["item_id"]]["ok"]),
                "networks": boot["networks"], "lo": boot["lo"], "hi": boot["hi"]}

    return {"arm": arm, "questions": len(recs), "answered": len(recs) - len(missing),
            "missing": missing, "excluded": excluded,
            "by_type": {qt: cell([r for r in usable if r["query_type"] == qt]) for qt in types},
            "by_category": {c: cell([r for r in usable if _category(r) == c]) for c in CATEGORIES},
            "overall": cell(usable), "complete": not missing and not excluded,
            "bootstrap": {"seed": seed, "draws": draws}}


# ---------------------------- 命令 ----------------------------

def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def _load(args) -> list[dict]:
    records = ans._load_corpus(args.corpus)
    return records[:args.limit] if args.limit > 0 else records


def _libraries(args, records):
    libs = ans.library_index(args.source)
    absent = [r["item_id"] for r in records if r["item_id"] not in libs]
    if absent:
        return None, f"{len(absent)} 道题没有九月来源库: {absent[:3]}"
    return libs, None


def _reference(args) -> int:
    try:
        rows = [json.loads(line) for line in args.matrix_rows.read_text(encoding="utf-8").splitlines() if line.strip()]
        reference = reference_from_matrix(rows, args.arm)
    except (OSError, ValueError) as exc:
        return _fail(str(exc))
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(reference, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"arm": args.arm, "questions": len(reference["rows"]), "result": str(args.result)},
                     ensure_ascii=False))
    return 0


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
        out = wp3.recall(rec, libs[rec["item_id"]], work, now_iso=args.now_iso)
        rows.append({"item_id": rec["item_id"], "turn_ids": [ref.get("turn_id") for ref in out["source_refs"]]})
    if work.exists() and not any(work.iterdir()):
        work.rmdir()
    gate = wp3.replay_gate(rows, reference)
    result = {"arm": ARM, "spec": arm_spec(), "core_sha256": core_sha,
              "corpus_sha256": ans._sha256_file(args.corpus), "reference_sha256": ans._sha256_file(args.reference), **gate}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "precheck.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "differing"} | {"differing": result["differing"][:5]},
                     ensure_ascii=False))
    return 0 if result["ready"] else 2


def _answer(args) -> int:
    if not args.real_run:
        return _fail("缺 --real-run:answer 会发出真实作答与判分请求,拒绝误触网络。")
    pre_path = args.out / "precheck.json"
    pre = json.loads(pre_path.read_text(encoding="utf-8")) if pre_path.is_file() else None
    if not isinstance(pre, dict) or pre.get("ready") is not True:
        return _fail("缺少或未通过 precheck.json:先跑零请求的 precheck 并确认通过。")
    core_sha, problem = sb._core_gate(args)
    if problem:
        return _fail(problem)
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
                "corpus_sha256": ans._sha256_file(args.corpus), "reference_sha256": pre.get("reference_sha256"),
                "prompts_sha256": args.prompts_sha256, "profiles_sha256": sb.profiles_sha256(args.profiles),
                "backbone": backbone, "judge_model": judge_model, "now_iso": args.now_iso, "questions": len(records),
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
            lambda rec: wp3.recall(rec, libs[rec["item_id"]], work, now_iso=args.now_iso),
            lambda rec, rc: ans.answer_item(rec, rc, prompts=prompts, answerer=answerer, judge=judge,
                                            strict_judge=None, backbone=backbone, judge_model=judge_model),
            journal=args.out / f"{ARM}_journal.jsonl")
    if work.exists() and not any(work.iterdir()):
        work.rmdir()
    print(json.dumps({"arm": ARM, "answered": len(rows), "questions": len(records),
                      "errors": len(records) - len(rows)}, ensure_ascii=False))
    return 0


SETTING_KEYS = ("spec", "core_sha256", "prompts_sha256", "backbone", "judge_model", "now_iso")


def merge_settings_problem(manifests: list) -> str | None:
    """合并读数前核对各臂设置逐项相同。臂名、profiles 文件哈希、代码哈希与参照哈希不比较。
    缺任何一份 manifest 或缺任何设置键都拒绝,不把「两边都没记」当成相同。"""
    if not manifests or any(not isinstance(m, dict) for m in manifests):
        return "合并需要每份 journal 旁边都有 manifest,缺一份就不合并。"
    for m in manifests:
        absent = [k for k in SETTING_KEYS if k not in m]
        if absent:
            return f"manifest 缺少设置键 {absent},不合并。"
    first = manifests[0]
    for m in manifests[1:]:
        for key in SETTING_KEYS:
            if m[key] != first[key]:
                return f"设置不一致: {key}。不同设置下的行不能合并成一份读数。"
    return None


def _manifest_of(journal: Path, arm: str):
    path = Path(journal).parent / f"manifest_{arm}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _report(args) -> int:
    if (args.wp3_corpus is None) != (args.wp3_journal is None):
        return _fail("--wp3-corpus 与 --wp3-journal 必须一起给。")
    records = ans._load_corpus(args.corpus)
    types = tuple(t.strip() for t in args.types.split(",") if t.strip()) if args.types else STAGE2_TYPES
    unknown = [t for t in types if t not in DEV_TYPES]
    if unknown:
        return _fail(f"--types 里有不认识的题型 {unknown};可用 {list(DEV_TYPES)}")
    dropped = sorted({r["query_type"] for r in records} - set(types))
    if dropped:
        return _fail(f"语料里有题型 {dropped} 不在 --types {list(types)} 里,报告会静默漏掉它们;请用 --types 明确列出。")
    journal = args.out / f"{ARM}_journal.jsonl"
    if not journal.exists():
        return _fail(f"缺 journal: {journal}")
    rows = ans.load_rows(journal, ARM)
    out = {"stage2": build_report(records, rows, types=types)}
    groups = []
    if args.wp3_corpus is not None:
        groups.append(("dev_split", "dev_split", [(args.wp3_corpus, args.wp3_journal, SRC_ARM)]))
    if args.also:
        groups.append(("merged", args.merged_label, [(Path(c), Path(j), a) for c, j, a in args.also]))
    for key, label, extras in groups:
        for _, jpath, _arm in extras:
            if not Path(jpath).exists():
                return _fail(f"缺 journal: {jpath}")
        problem = merge_settings_problem([_manifest_of(journal, ARM)] + [_manifest_of(j, a) for _, j, a in extras])
        if problem:
            return _fail(problem)
        combined, merged = list(records), rows
        try:
            for cpath, jpath, arm in extras:
                more = ans._load_corpus(cpath)
                dup = sorted({r["item_id"] for r in combined} & {r["item_id"] for r in more})
                if dup:
                    return _fail(f"{len(dup)} 道题同时出现在多份语料里,例 {dup[:3]}")
                combined += more
                merged = merge_rows(merged, ans.load_rows(jpath, arm))
        except ValueError as exc:
            return _fail(str(exc))
        out[key] = build_report(combined, merged, types=DEV_TYPES, arm=label)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.result is not None:
        args.result.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    base = argparse.ArgumentParser(add_help=False)
    base.add_argument("--out", type=Path, required=True)
    base.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    run = argparse.ArgumentParser(add_help=False, parents=[base])
    run.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    run.add_argument("--require-core-sha256", default=None)
    run.add_argument("--now-iso", default=wp3.NOW_ISO)
    run.add_argument("--limit", type=int, default=0)
    ref = sub.add_parser("reference", help="零请求:从矩阵逐题话轮表导出一个臂的参照文件")
    ref.add_argument("--matrix-rows", type=Path, default=DEFAULT_MATRIX_ROWS)
    ref.add_argument("--arm", default=DEFAULT_MATRIX_ARM)
    ref.add_argument("--result", type=Path, required=True)
    pre = sub.add_parser("precheck", parents=[run], help="零请求:回放并与参照比对")
    pre.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    answer = sub.add_parser("answer", parents=[run], help="发出作答与判分请求(需 --real-run)")
    answer.add_argument("--prompts", type=Path, required=True)
    answer.add_argument("--prompts-sha256", required=True)
    answer.add_argument("--profile", default=None)
    answer.add_argument("--profiles", type=Path, default=sb.DEFAULT_PROFILES)
    answer.add_argument("--real-run", action="store_true")
    report = sub.add_parser("report", parents=[base], help="零请求:描述性读数")
    report.add_argument("--result", type=Path, default=None)
    report.add_argument("--wp3-corpus", type=Path, default=None)
    report.add_argument("--wp3-journal", type=Path, default=None)
    report.add_argument("--types", default=None, help="逗号分隔的题型;默认 Q2,Q4,Q5,Q6,Q9;语料里有不在其中的题型就拒绝")
    report.add_argument("--also", nargs=3, action="append", metavar=("CORPUS", "JOURNAL", "ARM"), default=None,
                        help="再并入一份语料与 journal 做合并读数;旁边必须有设置相同的 manifest;可重复")
    report.add_argument("--merged-label", default="merged", help="--also 合并读数在报告里的臂名")
    args = parser.parse_args(argv)
    if args.cmd == "answer":
        try:
            args.profile = args.profile or sb.default_profile_name(args.profiles)
        except ValueError as exc:
            parser.error(str(exc))
    return {"reference": _reference, "precheck": _precheck, "answer": _answer, "report": _report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
