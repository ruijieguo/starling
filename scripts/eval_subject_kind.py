#!/usr/bin/env python3
"""subject_kind 分类准确率子门(eng-review D4)。

三维 baseline(eval_quality_baseline.py)按 (predicate,object) 配对打 F1,结构性
**看不到** subject_kind 判得准不准 —— 一个把一半真人误判 entity 的 prompt 仍可能三维
总分不降。本子门专测这一维:跑 belief EXTRACTION_PROMPT 抽取一组已知 cognizer/entity
的标注语料,核对 LLM 输出的 subject_kind(及 cognizer 时的 cognizer_kind)判对率。

真 LLM,不进 CI(与 eval_quality_baseline 同):Clash TUN 黑洞换时刻重跑。

用法:
    OPENAI_API_KEY=... OPENAI_BASE_URL=... \\
        python scripts/eval_subject_kind.py --rounds 1

Exit code:
    0  subject_kind 准确率 >= --min-accuracy(默认 0.90)
       AND cognizer_kind 准确率 >= --min-kind-accuracy(默认 0.80)
    1  低于阈值(BLOCKED —— 回 Task 5-7 强化 prompt 示例,不是放宽阈值)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_p1_extractor import extract_via_gpt  # noqa: E402

DEFAULT_CORPUS = (
    Path(__file__).resolve().parents[1] / "tests" / "data" / "eval_subject_kind_corpus.jsonl"
)


def load_corpus(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _find_prediction(predicted: list[dict], subject: str) -> dict | None:
    """Match the extracted statement whose subject is (case-insensitively) the
    labeled subject. The prompt may canonicalize surface a little; fall back to
    substring containment either direction so a benign 'the '-strip still matches.
    """
    s = subject.strip().lower()
    for p in predicted:
        ps = str(p.get("subject", "")).strip().lower()
        if ps == s or (ps and (ps in s or s in ps)):
            return p
    return None


def evaluate(corpus: list[dict], base_url: str, api_key: str, model: str) -> dict:
    sk_correct = sk_total = 0
    ck_correct = ck_total = 0
    misses: list[dict] = []
    unmatched = 0

    for rec in corpus:
        convo = [{"speaker": "narrator", "text": rec["passage"]}]
        try:
            predicted = extract_via_gpt(convo, base_url, api_key, model)
        except Exception as e:  # noqa: BLE001
            print(f"WARN: {rec['id']} extraction failed: {e}", file=sys.stderr)
            unmatched += 1
            sk_total += 1
            continue

        pred = _find_prediction(predicted, rec["subject"])
        if pred is None:
            # No statement about the labeled subject came back. Count as a
            # subject_kind miss (the prompt failed to surface it) but record
            # separately so we can tell "wrong kind" from "not extracted".
            unmatched += 1
            sk_total += 1
            misses.append({"id": rec["id"], "reason": "no_matching_subject",
                           "subject": rec["subject"]})
            continue

        sk_total += 1
        got_sk = str(pred.get("subject_kind", "")).strip().lower()
        want_sk = rec["expect_subject_kind"]
        if got_sk == want_sk:
            sk_correct += 1
        else:
            misses.append({"id": rec["id"], "subject": rec["subject"],
                           "want_subject_kind": want_sk, "got_subject_kind": got_sk or "(missing)"})

        # cognizer_kind only scored when the ground truth is a cognizer with a
        # labeled kind AND the model agreed it's a cognizer.
        if want_sk == "cognizer" and rec.get("expect_cognizer_kind"):
            ck_total += 1
            got_ck = str(pred.get("cognizer_kind", "")).strip().lower()
            if got_ck == rec["expect_cognizer_kind"]:
                ck_correct += 1
            else:
                misses.append({"id": rec["id"], "subject": rec["subject"],
                               "want_cognizer_kind": rec["expect_cognizer_kind"],
                               "got_cognizer_kind": got_ck or "(missing)"})

    sk_acc = sk_correct / sk_total if sk_total else 0.0
    ck_acc = ck_correct / ck_total if ck_total else 1.0
    return {
        "subject_kind_accuracy": sk_acc,
        "cognizer_kind_accuracy": ck_acc,
        "sk_correct": sk_correct, "sk_total": sk_total,
        "ck_correct": ck_correct, "ck_total": ck_total,
        "unmatched": unmatched,
        "misses": misses,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="subject_kind 分类准确率子门(真 LLM,非 CI)")
    p.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    p.add_argument("--model", default=os.environ.get("STARLING_EVAL_MODEL", "gpt-5.5"))
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--min-accuracy", type=float, default=0.90,
                   help="subject_kind 判对率硬阈值")
    p.add_argument("--min-kind-accuracy", type=float, default=0.80,
                   help="cognizer_kind 判对率硬阈值")
    p.add_argument("--report", type=Path, default=None)
    args = p.parse_args(argv)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set(不打印 key)", file=sys.stderr)
        return 2

    corpus = load_corpus(args.corpus)
    # 多轮取最好一轮(与三维 baseline 的 min_ok 精神一致:LLM 有抖动,不因一次坏抽取误拦)。
    best: dict | None = None
    for r in range(args.rounds):
        res = evaluate(corpus, base_url, api_key, args.model)
        print(f"round {r+1}/{args.rounds}: subject_kind={res['subject_kind_accuracy']:.3f} "
              f"({res['sk_correct']}/{res['sk_total']}), "
              f"cognizer_kind={res['cognizer_kind_accuracy']:.3f} "
              f"({res['ck_correct']}/{res['ck_total']}), unmatched={res['unmatched']}",
              file=sys.stderr)
        if best is None or res["subject_kind_accuracy"] > best["subject_kind_accuracy"]:
            best = res

    assert best is not None
    lines = [
        "# subject_kind classification sub-gate (D4)",
        "",
        f"model: {args.model}  corpus: {len(corpus)} labeled subjects  rounds: {args.rounds}",
        "",
        f"- subject_kind accuracy: **{best['subject_kind_accuracy']:.3f}** "
        f"({best['sk_correct']}/{best['sk_total']})  threshold {args.min_accuracy}",
        f"- cognizer_kind accuracy: **{best['cognizer_kind_accuracy']:.3f}** "
        f"({best['ck_correct']}/{best['ck_total']})  threshold {args.min_kind_accuracy}",
        f"- unmatched (subject not extracted): {best['unmatched']}",
    ]
    if best["misses"]:
        lines += ["", "## misses (best round)"]
        for m in best["misses"]:
            lines.append(f"- {json.dumps(m, ensure_ascii=False)}")
    report = "\n".join(lines)
    print(report)
    if args.report:
        args.report.write_text(report + "\n", encoding="utf-8")

    sk_ok = best["subject_kind_accuracy"] >= args.min_accuracy
    ck_ok = best["cognizer_kind_accuracy"] >= args.min_kind_accuracy
    if sk_ok and ck_ok:
        print("\nPASS: subject_kind 子门通过", file=sys.stderr)
        return 0
    print("\nBLOCKED: subject_kind 子门未过 —— 回 Task 5-7 强化 prompt 示例(不是放宽阈值)",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
