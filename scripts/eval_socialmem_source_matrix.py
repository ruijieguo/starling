#!/usr/bin/env python3
"""WP1.A:零抽取来源召回消融矩阵(回放既有来源库,不发模型请求,不使用嵌入)。

只度量「金标证据话轮是否进入召回块」。检索、过滤、预算与渲染都在 C++ 核心里完成,本脚本只做
数据映射、库拷贝与统计。每次回放都在库的临时副本上进行,用后即删,原库不被写入。
登记见 build/prereg_wp1_source_matrix.md(本机文件):选臂规则与有效性前置条件先于运行写定。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import defaultdict
from contextlib import closing, contextmanager
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ALIGNED = ("Q2", "Q4", "Q5", "Q6", "Q9")
STRATEGIES = ("bm25", "focused", "focused_window", "focused_dialogue", "focused_coverage",
              "evidence_profile_v6", "evidence_profile_v9")
KS = (10, 20, 30)
BYTE_BUDGETS = (8000, 24000)
BASELINE = ("focused_window", 30, 8000)
MARGIN = 3                      # 主指标至少比基线多这么多题
GUARD_SLACK = 2                 # 守卫类每类最多比基线少这么多题
BOUND_FRACTION = 0.95           # 上下文字节达到预算的这个比例,记为预算受限
VALIDITY_MIN_EQUAL = 224        # 基线臂区块与九月存档逐字相同的题数下限
GUARDS = ("Q2", "Q4", "Q6")
GAP_MARGIN = 10                 # WP1.D:Q2+Q6 全命中题数至少比基线多这么多
PRIMARY_SLACK = 3               # WP1.D:Q5+Q9 全命中题数最多比基线少这么多
BYTE_CEILING = 12000            # WP1.D:226 题平均上下文字节数上限
EXT_KS = (40, 50, 60)
EXT_BYTE_BUDGETS = (8000, 16000)


def arm_key(strategy: str, k: int, max_context_bytes: int) -> str:
    return f"{strategy}|k{k}|b{max_context_bytes}"


def full_arms() -> list[tuple[str, int, int]]:
    return [(s, k, b) for s in STRATEGIES for k in KS for b in BYTE_BUDGETS]


def extended_arms() -> list[tuple[str, int, int]]:
    """WP1.D 扩展网格:基线臂加 7 种策略 x k 40/50/60 x 字节预算 8000/16000,共 43 个臂。"""
    return [BASELINE] + [(s, k, b) for s in STRATEGIES for k in EXT_KS for b in EXT_BYTE_BUDGETS]


def arms_for_grid(name: str) -> list[tuple[str, int, int]]:
    if name == "full":
        return full_arms()
    if name == "extended":
        return extended_arms()
    raise ValueError(f"unknown grid: {name!r}; valid=['full', 'extended']")


def gold_turn_ids(record: dict) -> list[str]:
    """金标证据话轮号:去重,保持首次出现的顺序。没有可用金标证据的题直接拒绝。"""
    ids: list[str] = []
    for gold in record.get("gold_statements") or []:
        turn = gold.get("turn_id")
        if not isinstance(turn, str) or not turn:
            raise ValueError(f"gold evidence without a turn_id: {record.get('item_id')}")
        if turn not in ids:
            ids.append(turn)
    if not ids:
        raise ValueError(f"no gold evidence: {record.get('item_id')}")
    return ids


def coverage(gold: list[str], refs: list[dict]) -> dict:
    seen = {ref.get("turn_id") for ref in refs}
    hit = sum(1 for turn in gold if turn in seen)
    return {"gold": len(gold), "hit": hit, "all": hit == len(gold)}


def development_records(records: list[dict], split: dict) -> list[dict]:
    """开发切分内的对口五类;保留切分的网络与其它题型一概不进入。"""
    dev, reserved = set(split["development_networks"]), set(split["reserved_networks"])
    if dev & reserved:
        raise ValueError("split lists a network as both development and reserved")
    return [r for r in records
            if r["query_type"] in ALIGNED and r["source"]["network_id"] in dev]


def _block(items: list[dict]) -> dict:
    n = len(items)
    return {"n": n, "all_gold": sum(1 for r in items if r["all"]),
            "turns_hit": sum(r["hit"] for r in items), "turns_total": sum(r["gold"] for r in items),
            "mean_bytes": sum(r["context_bytes"] for r in items) / n,
            "budget_bound": sum(1 for r in items if r["budget_bound"])}


def summarize(rows: list[dict]) -> dict:
    """arm -> 分组 -> 指标。分组为各题型、Q5+Q9(主指标)与 ALL。"""
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_arm[row["arm"]].append(row)
    out: dict = {}
    for arm, items in by_arm.items():
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in items:
            groups[row["query_type"]].append(row)
        primary = groups.get("Q5", []) + groups.get("Q9", [])
        gap = groups.get("Q2", []) + groups.get("Q6", [])
        result = {qt: _block(group) for qt, group in groups.items()}
        if primary:
            result["Q5+Q9"] = _block(primary)
        if gap:
            result["Q2+Q6"] = _block(gap)
        result["ALL"] = _block(items)
        out[arm] = result
    return out


def _count(arm: dict, group: str) -> int:
    return int((arm.get(group) or {}).get("all_gold", 0))


def select_arm(summary: dict, baseline: str) -> str | None:
    """登记的选臂规则:主指标至少多 3 题;守卫类每类不低于基线减 2;
    并列取主指标最高,再取平均字节更小,再取臂名字典序靠前。基线本身不会被选中。"""
    if baseline not in summary:
        raise ValueError(f"baseline arm missing from summary: {baseline}")
    base = summary[baseline]
    floor = _count(base, "Q5+Q9") + MARGIN
    eligible = []
    for key, arm in summary.items():
        if key == baseline:
            continue
        if _count(arm, "Q5+Q9") < floor:
            continue
        if any(_count(arm, g) < _count(base, g) - GUARD_SLACK for g in GUARDS):
            continue
        eligible.append((-_count(arm, "Q5+Q9"), float(arm["ALL"]["mean_bytes"]), key))
    return min(eligible)[2] if eligible else None


def select_gap_arm(summary: dict, baseline: str) -> str | None:
    """WP1.D 登记的选臂规则:Q2+Q6 全命中至少多 10 题;Q4 不低于基线减 2;Q5+Q9 不低于基线减 3;
    226 题平均上下文字节不超过 12000。并列取 Q2+Q6 最高,再取平均字节更小,再取臂名字典序靠前。
    基线本身不会被选中。"""
    if baseline not in summary:
        raise ValueError(f"baseline arm missing from summary: {baseline}")
    base = summary[baseline]
    eligible = []
    for key, arm in summary.items():
        if key == baseline:
            continue
        gap = _count(arm, "Q2+Q6")
        if gap < _count(base, "Q2+Q6") + GAP_MARGIN:
            continue
        if _count(arm, "Q4") < _count(base, "Q4") - GUARD_SLACK:
            continue
        if _count(arm, "Q5+Q9") < _count(base, "Q5+Q9") - PRIMARY_SLACK:
            continue
        mean_bytes = float(arm["ALL"]["mean_bytes"])
        if mean_bytes > BYTE_CEILING:
            continue
        eligible.append((-gap, mean_bytes, key))
    return min(eligible)[2] if eligible else None


def reference_agreement(rows: list[dict], reference: list[dict], arm: str) -> dict:
    """某个臂的区块哈希与参考行逐题相同的题数(有效性前置条件:已安装核心的确定性)。"""
    ref = {(r["arm"], r["item_id"]): r["block_sha256"] for r in reference}
    mine = [r for r in rows if r["arm"] == arm]
    equal = sum(1 for r in mine if ref.get((arm, r["item_id"])) == r["block_sha256"])
    return {"equal": equal, "of": len(mine)}


@contextmanager
def _library_copy(library, work, tag: str):
    """在库的临时副本上开一个原生运行时;离开时先放掉全部引用,再删副本及其 WAL 文件。"""
    from starling import _core, runtime

    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    copy = work / f"{hashlib.sha256(tag.encode('utf-8')).hexdigest()[:16]}.db"
    if copy.exists():
        raise FileExistsError(str(copy))
    with closing(sqlite3.connect(Path(library).resolve().as_uri() + "?mode=ro", uri=True)) as source, \
            closing(sqlite3.connect(copy)) as target:
        source.backup(target)
    ctx = SimpleNamespace(core=_core, rt=None, embedder=None, index=None)
    try:
        ctx.rt = runtime._build_local_store_sqlite_runtime(copy)
        ctx.rt.start()
        ctx.embedder = _core.StubEmbeddingAdapter(8)          # sources 模式不使用嵌入
        ctx.index = _core.SqliteBlobVectorIndex()
        yield ctx
    finally:
        ctx.rt = ctx.embedder = ctx.index = None
        for suffix in ("", "-wal", "-shm"):
            Path(str(copy) + suffix).unlink(missing_ok=True)


def replay_question(record: dict, library, work, *, strategy: str, k: int,
                    max_context_bytes: int, now_iso: str) -> dict:
    """在库的临时副本上回放一次来源召回,用后删除副本。"""
    import eval_ladder_pipeline as pipe

    tag = f"replay|{record['item_id']}|{strategy}|{k}|{max_context_bytes}"
    with _library_copy(library, work, tag) as ctx:
        holders = sorted({str(turn["speaker"]) for turn in record["history"]})
        result = pipe.recall_observer_block(
            ctx.core, adapter=ctx.rt.adapter, embedder=ctx.embedder, index=ctx.index,
            question=record["question"], allowed_holders=holders, mode="sources", now_iso=now_iso,
            k=k, max_context_bytes=max_context_bytes, include_unknown_time=True,
            source_strategy=strategy)
    diagnostics = result.get("source_diagnostics") or {}
    nbytes = int(result["context_bytes"])
    bound = int(diagnostics.get("budget_skipped") or 0) > 0 or nbytes >= BOUND_FRACTION * max_context_bytes
    return {"source_refs": result["source_refs"], "context_bytes": nbytes,
            "source_count": int(result["source_count"]), "budget_bound": bound, "block": result["block"]}


def _collect_pool(core, adapter, embedder, index, record: dict, now_iso: str) -> str:
    """原生完整合格来源池(授权、时间、完整性过滤之后),按时间顺序,一行一条来源。"""
    observer = core.ObserverRetriever(adapter, core.SemanticRetriever(adapter, embedder, index))
    query = core.ObserverQuery()
    query.tenant_id = "default"
    query.allowed_holders = sorted({str(turn["speaker"]) for turn in record["history"]})
    query.question = record["question"]
    query.as_of_iso8601 = now_iso
    query.include_unknown_time = True
    query.mode = "sources"
    return core.collect_selection_pool(observer, query)


def _position_key(ref: dict):
    session, index = ref.get("session_id"), ref.get("turn_index")
    if isinstance(session, str) and session and isinstance(index, int) and not isinstance(index, bool):
        return session, index
    return None


def oracle_selection_ids(refs: list[dict], sizes: list[int], gold: list[str], *, radius: int,
                         k: int, max_bytes: int) -> list[int]:
    """金标参照臂的选择:金标话轮必选,再按距离(其次池顺序)补同会话邻接话轮,直到条数或字节
    预算用尽,放不下的邻接跳过。返回 1 起的池内编号(升序),交给原生 apply_source_selection 渲染。
    金标本身缺失或放不下直接报错,绝不静默少给。"""
    if len(refs) != len(sizes):
        raise ValueError("pool refs and sizes differ in length")
    if not gold:
        raise ValueError("gold evidence required")
    wanted = set(gold)
    gold_pos = [i for i, ref in enumerate(refs) if ref.get("turn_id") in wanted]
    missing = wanted - {refs[i].get("turn_id") for i in gold_pos}
    if missing:
        raise ValueError(f"gold turn missing from the pool: {sorted(missing)}")
    if len(gold_pos) > k:
        raise ValueError("gold turns exceed the source limit")
    used = sum(sizes[i] for i in gold_pos) + len(gold_pos) - 1
    if used > max_bytes:
        raise ValueError("gold turns exceed the byte budget")
    selected = set(gold_pos)
    if radius > 0:
        anchors = [key for key in (_position_key(refs[i]) for i in gold_pos) if key is not None]
        candidates = []
        for pos, ref in enumerate(refs):
            key = _position_key(ref)
            if pos in selected or key is None:
                continue
            distances = [abs(key[1] - anchor[1]) for anchor in anchors if anchor[0] == key[0]]
            if distances and min(distances) <= radius:
                candidates.append((min(distances), pos))
        for _, pos in sorted(candidates):
            if len(selected) >= k:
                break
            if used + sizes[pos] + 1 > max_bytes:
                continue
            selected.add(pos)
            used += sizes[pos] + 1
    return [pos + 1 for pos in sorted(selected)]


def oracle_question(record: dict, library, work, *, radius: int, now_iso: str,
                    k: int = 20, max_context_bytes: int = 8000) -> dict:
    """只给金标话轮(radius 大于 0 时加同会话邻接话轮)的参照臂:这是构造出来的上限参照,
    不是系统能力。池、预算与渲染都由原生核心完成,本函数只决定选哪几条。"""
    gold = gold_turn_ids(record)
    with _library_copy(library, work, f"oracle|{record['item_id']}|{radius}") as ctx:
        raw = _collect_pool(ctx.core, ctx.rt.adapter, ctx.embedder, ctx.index, record, now_iso)
        pool = json.loads(raw)
        refs = pool["source_refs"]
        lines = pool["block"].split("\n") if pool["block"] else []
        if len(lines) != len(refs):
            raise ValueError("source pool rows and refs differ in length")
        ids = oracle_selection_ids(refs, [len(line.encode("utf-8")) for line in lines], gold,
                                   radius=radius, k=k, max_bytes=max_context_bytes)
        out = json.loads(ctx.core.apply_source_selection(
            record["question"], raw, json.dumps({"source_ids": ids}), k, max_context_bytes))
    return {"source_refs": out["source_refs"], "context_bytes": int(out["context_bytes"]),
            "source_count": int(out["source_count"]), "budget_bound": False,
            "block": out["block"], "pool_size": len(refs)}


def run_matrix(records: list[dict], library_for, arms, work, *, now_iso: str) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        gold = gold_turn_ids(record)
        library = library_for(record)
        for strategy, k, nbytes in arms:
            out = replay_question(record, library, work, strategy=strategy, k=k,
                                  max_context_bytes=nbytes, now_iso=now_iso)
            cov = coverage(gold, out["source_refs"])
            rows.append({
                "arm": arm_key(strategy, k, nbytes), "item_id": record["item_id"],
                "query_type": record["query_type"], "gold": cov["gold"], "hit": cov["hit"],
                "all": cov["all"], "context_bytes": out["context_bytes"],
                "source_count": out["source_count"], "budget_bound": out["budget_bound"],
                "block_sha256": hashlib.sha256(out["block"].encode("utf-8")).hexdigest(),
                "turn_ids": [ref.get("turn_id") for ref in out["source_refs"]]})
    return rows


def _sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=Path("build/socialmem_20260917_source_focus"))
    p.add_argument("--out", type=Path, required=True, help="新目录;已存在则拒绝")
    p.add_argument("--now-iso", default="2026-12-08T00:00:00Z")
    p.add_argument("--baseline-only", action="store_true", help="只回放基线臂(有效性检验)")
    p.add_argument("--require-core-sha256", default=None, help="已加载核心的 SHA-256 不符则拒绝运行")
    p.add_argument("--grid", choices=("full", "extended"), default="full",
                   help="full=WP1.A 的 42 臂;extended=WP1.D 的 43 臂(基线加 k 40/50/60 与字节 8000/16000)")
    p.add_argument("--reference-rows", type=Path, default=None,
                   help="extended 网格的有效性参考:WP1.A 的 rows.jsonl(基线臂区块须逐题相同)")
    args = p.parse_args(argv)
    if args.out.exists():
        print(f"ERROR: {args.out} 已存在,拒绝覆盖。", file=sys.stderr)
        return 1
    from starling import _core

    core_sha = _sha256_file(_core.__file__)
    if args.require_core_sha256 and core_sha != args.require_core_sha256:
        print(f"ERROR: 加载的核心 {core_sha[:12]} 不是要求的 {args.require_core_sha256[:12]}。", file=sys.stderr)
        return 1
    corpus_path, split_path = args.source / "corpus.jsonl", args.source / "network-split.json"
    corpus = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    split = json.loads(split_path.read_text(encoding="utf-8"))
    records = development_records(corpus, split)
    group_of: dict[str, str] = {}
    september_block: dict[str, str] = {}
    for path in sorted(args.source.glob("runs/*/questions/*.json")):
        q = json.loads(path.read_text(encoding="utf-8"))
        group_of[q["item_id"]] = path.parent.parent.name
        block = (q.get("recall") or {}).get("block")
        if isinstance(block, str):
            september_block[q["item_id"]] = hashlib.sha256(block.encode("utf-8")).hexdigest()
    missing = [r["item_id"] for r in records if r["item_id"] not in group_of]
    if missing:
        print(f"ERROR: {len(missing)} 道题在九月产物里没有库映射: {missing[:3]}", file=sys.stderr)
        return 1
    groups = sorted({group_of[r["item_id"]] for r in records})
    libraries = {g: _sha256_file(args.source / "runs" / g / "frozen.db") for g in groups}
    arms = [BASELINE] if args.baseline_only else arms_for_grid(args.grid)
    base_key = arm_key(*BASELINE)
    reference: list[dict] = []
    if args.grid == "extended" and not args.baseline_only:
        if args.reference_rows is None or not args.reference_rows.exists():
            print("ERROR: --grid extended 需要 --reference-rows 指向 WP1.A 的 rows.jsonl。", file=sys.stderr)
            return 1
        reference = [json.loads(line) for line in args.reference_rows.read_text(encoding="utf-8").splitlines()
                     if line.strip()]
    args.out.mkdir(parents=True)
    rows = run_matrix(records, lambda r: args.source / "runs" / group_of[r["item_id"]] / "frozen.db",
                      arms, args.out / "scratch", now_iso=args.now_iso)
    (args.out / "scratch").rmdir()
    with (args.out / "rows.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if args.grid == "extended" and not args.baseline_only:
        equal, threshold = reference_agreement(rows, reference, base_key)["equal"], len(records)
    else:
        equal = sum(1 for r in rows if r["arm"] == base_key and r["block_sha256"] == september_block.get(r["item_id"]))
        threshold = VALIDITY_MIN_EQUAL
    valid = equal >= threshold
    summary = summarize(rows)
    chooser = select_gap_arm if args.grid == "extended" else select_arm
    selected = None if (args.baseline_only or not valid) else chooser(summary, base_key)
    report = {"core_sha256": core_sha, "corpus_sha256": _sha256_file(corpus_path),
              "split_sha256": _sha256_file(split_path), "now_iso": args.now_iso, "questions": len(records),
              "arms": [arm_key(*a) for a in arms], "baseline": base_key, "libraries": libraries,
              "validity": {"baseline_block_equal": equal, "of": len(records),
                           "threshold": threshold, "valid": valid},
              "selected": selected,
              "selection_status": ("baseline_only" if args.baseline_only else
                                   "invalid_replay" if not valid else
                                   "selected" if selected else "no_arm_qualifies"),
              "summary": summary}
    report["grid"] = args.grid
    report["pool_exhausted"] = {arm_key(*a): sum(1 for r in rows if r["arm"] == arm_key(*a) and r["source_count"] < a[1])
                                for a in arms}
    (args.out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("core_sha256", "questions", "validity", "selected", "selection_status")},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
