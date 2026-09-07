#!/usr/bin/env python3
"""judge 对抗审计(评测组合方案 §3.1 / impl-spec §3.1;照搬 Penfield Labs 方法)。

**目的**:测出被测 judge 会把多少"话题相邻但事实错误"的答案误判为对。这个
接受率 = 分数的**不可解读带 α_judge**——记分卡里所有 Δ < α_judge 的一律标
`n.s.`,不得作为"提升/不降"证据。Penfield 在 LoCoMo 上实测 62.81%:α 高得
离谱就说明该基准默认 judge 不可用,须换更强 judge 或换结构化评分。

方法:
  对每道题,由"干扰器"LM 生成 K 个话题相邻但事实错误的答案,用被测 judge
  (同配置)去评;被判"正确"的比例 = α_judge。

本文件是 **PR-2**:fixture-mode(离线、确定性、CI 可跑)用一个确定性 mock 干扰器
+ mock judge 算出 α_judge,把整条审计管线(生成→评判→聚合→按基准出带)打通;
**real-mode(真干扰器 + 真 judge LLM)是 gated 真跑**,只留 sound 接线点,不行使网络。

  python scripts/eval_judge_audit.py --benchmark longmemeval \
      --corpus tests/data/eval_longmemeval/sessions.jsonl \
      --k 3 --fixture-mode --report build/judge_audit_longmemeval.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

# α_judge 高于此阈值 → 该基准默认 judge 不可信,报告显式告警(Penfield: LoCoMo 62.81%)。
JUDGE_UNUSABLE_THRESHOLD = 0.40

# chat 重试:吸收 Clash TUN 的间歇性 TLS 掐断(见 _chat_completion)。
CHAT_MAX_ATTEMPTS = 4
CHAT_BACKOFF_S = 2.0

# fixture 干扰器每题生成的对抗答案数(与 --k 一致时用 --k)。
DEFAULT_K = 3


def load_corpus(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _fixture_distractors(rec: dict, k: int) -> list[str]:
    """确定性 mock 干扰器:为一题造 k 个"话题相邻但事实错误"的答案。

    real-mode 由真 LM 生成(prompt:"给出与问题相关、听起来合理、但事实错误的答案")。
    fixture 里从选项中挑非正确项 + 合成变体,保证确定性与可复现。"""
    opts = rec.get("options")
    out: list[str] = []
    if opts:
        answer_idx = int(rec.get("answer", 0))
        wrong = [o for i, o in enumerate(opts) if i != answer_idx]
        out.extend(wrong[:k])
    # 不足 k 个则用确定性合成串补齐(话题词 + 错误后缀)。
    q = rec.get("question", "")
    topic = q.split()[0] if q else "it"
    while len(out) < k:
        h = hashlib.sha256(f"{rec.get('item_id','')}|{len(out)}".encode()).hexdigest()[:6]
        out.append(f"{topic} is actually {h}")
    return out[:k]


def _fixture_judge_accepts(rec: dict, distractor: str, idx: int) -> bool:
    """确定性 mock judge:是否把这个故意错误答案误判为对。

    用 (item_id, distractor, idx) 的哈希决定,使审计可复现。刻意让一部分
    "话题相邻"的错误答案蒙混过关(≈ 真 judge 对模糊答案的宽松),好让 α_judge
    非平凡。real-mode 下由真 judge(同评测配置)取代。"""
    # 完全字面等于某个正确选项才"显然对";否则按话题相邻度的哈希量决定。
    h = hashlib.sha256(f"{rec.get('item_id','')}|{distractor}|{idx}".encode()).hexdigest()
    frac = int(h[:4], 16) / 0xFFFF
    # ≈ 1/3 的话题相邻错误答案被误判为对(骨架自测量级,非真实声明)。
    return frac < 0.33


# ------------------------- real-mode 接线点(gated 真跑)-------------------------
# real-mode 把 fixture 的确定性 mock 换成:干扰器=真 LM 生成"话题相邻但事实错误"
# 的候选,judge=与评测**同配置**的 LLM-judge。α_judge 只有在审计用的 judge 与
# ladder 打分用的是**同一个 judge** 时才可解读,故 _judge_prompt/_parse_judge_verdict
# 是**契约**:T6 把 ladder 的 config["judge"] 接到 make_real_ladder_judge_fn 上,
# 两处 judge 逐字节同源(“除记忆块外全部锁死”)。纯函数(prompt 组装 / 回复解析)
# 离线可测;网络只在工厂返回的闭包被实际调用时发生。


def _reference_answer(rec: dict) -> str:
    """题目参考答案文本:MC→options[answer];自由文本→answer 原文。"""
    if rec.get("answer_format", "multiple_choice") == "multiple_choice":
        opts = rec.get("options") or []
        idx = int(rec.get("answer", 0))
        return str(opts[idx]) if 0 <= idx < len(opts) else ""
    return str(rec.get("answer", ""))


def _distractor_prompt(rec: dict, k: int) -> str:
    """真干扰器 prompt:造 k 个"话题相邻、听起来合理、但事实错误"的候选答案。"""
    return (
        "You are generating ADVERSARIAL answers to audit a memory-QA judge.\n"
        f"Question: {rec.get('question', '')}\n"
        f"The CORRECT answer is: {_reference_answer(rec)}\n"
        f"Write exactly {k} distinct answers that are each on-topic and "
        "plausible-sounding but FACTUALLY WRONG, and are NOT paraphrases of the "
        "correct answer. One answer per line. No numbering, no commentary."
    )


def _strip_list_prefix(line: str) -> str:
    """去掉行首项目符号 / 序号前缀(纯字符串处理)。"""
    for bullet in ("- ", "* ", "• "):
        if line.startswith(bullet):
            return line[len(bullet):].strip()
    digits = 0
    while digits < len(line) and line[digits].isdigit():
        digits += 1
    if 0 < digits < len(line) and line[digits] in ").":
        return line[digits + 1:].strip()
    return line


def _parse_distractors(text: str, k: int) -> list[str]:
    """从干扰器回复解析至多 k 个非空候选(纯函数):剥行号/项目符号,去重保序。

    干扰器少产时**不**用合成串补齐——那会往审计里塞明显垃圾、把 judge 显得更严,
    使 α_judge 被低估(不安全方向)。宁可该题探针数变少,也让每个探针都是真对抗。"""
    out: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = _strip_list_prefix(raw.strip())
        if not line or line in seen:
            continue
        seen.add(line)
        out.append(line)
        if len(out) >= k:
            break
    return out


def _judge_prompt(question: str, reference: str, candidate: str) -> str:
    """canonical LLM-judge prompt(契约:ladder 打分与本审计必须同源)。
    判"候选是否与参考答案语义等价、事实正确",只回一个词 YES / NO。"""
    return (
        "You are a strict grader for a memory-QA benchmark.\n"
        f"Question: {question}\n"
        f"Reference (correct) answer: {reference}\n"
        f"Candidate answer: {candidate}\n"
        "Is the candidate factually correct and equivalent to the reference for "
        "this question? Answer with exactly one word: YES or NO."
    )


def _parse_judge_verdict(text: str) -> bool:
    """解析 judge 回复为 bool(纯函数):首个 yes/no 类词;缺失/歧义→False(保守)。"""
    for tok in text.replace("\n", " ").lower().split():
        word = tok.strip(".,!:;\"'()")
        if word in ("yes", "y", "correct", "true"):
            return True
        if word in ("no", "n", "incorrect", "wrong", "false"):
            return False
    return False


def _chat_completion(prompt: str, backbone: str, max_tokens: int) -> str:
    """经 proven HTTP 路径发一次 chat completion(网络仅此处发生)。

    复用 eval_longmemeval 的形状:_core.OpenAIAdapterConfig.from_env() 验证与
    C++ Extractor 相同的配置装配(api_key 只从 env 读、走 Authorization header,
    绝不入参/日志),再走 urllib POST /chat/completions。backbone 覆盖 model。"""
    import os
    import urllib.error
    import urllib.request

    from starling import _core

    cfg = _core.OpenAIAdapterConfig.from_env()  # OPENAI_API_KEY 未设则 raise
    if backbone:
        cfg.model = backbone
    _core.OpenAIAdapter(cfg)  # 离线构造,校验配置装配;此处不发网络
    api_key = os.environ.get("OPENAI_API_KEY", "")
    payload = json.dumps({
        "model": cfg.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    # 瞬时网络故障必须重试:本机 Clash TUN 会间歇性掐断 TLS
    # (SSL: UNEXPECTED_EOF_WHILE_READING / transport EOF),按进程与时刻区别对待——
    # 大 payload 实测 40KB 也能 3s 通过,故不是体积问题而是抖动。归因阶梯一轮要发
    # 上千次 chat,不吸收抖动的话单题失败会被 journal 记成 error 而排除出统计,
    # 样本量无声流失(2026-08 冒烟实测:S_star 首题即因 SSL EOF 丢失)。
    last_exc: Exception | None = None
    for attempt in range(CHAT_MAX_ATTEMPTS):
        req = urllib.request.Request(
            url=f"{cfg.base_url}/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return str(body["choices"][0]["message"]["content"]).strip()
        except urllib.error.HTTPError as exc:
            # 4xx 是**确定性**错误(模型名不存在/鉴权失败),重试只是浪费额度与时间。
            if 400 <= exc.code < 500 and exc.code != 429:
                raise
            last_exc = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                json.JSONDecodeError, KeyError) as exc:
            last_exc = exc          # 传输层抖动 / 半截响应 → 重试
        if attempt < CHAT_MAX_ATTEMPTS - 1:
            time.sleep(CHAT_BACKOFF_S * (2 ** attempt))
    raise RuntimeError(
        f"chat completion 连续 {CHAT_MAX_ATTEMPTS} 次失败: "
        f"{type(last_exc).__name__}: {last_exc}")


def make_real_ladder_judge_fn():
    """canonical LLM-judge(ladder config["judge"] 用):
    (question, reference, candidate, backbone) -> bool。网络仅在调用时发生。"""
    def _judge(question: str, reference: str, candidate: str, backbone: str) -> bool:
        content = _chat_completion(
            _judge_prompt(question, reference, candidate), backbone, max_tokens=8)
        return _parse_judge_verdict(content)
    return _judge


def make_real_distractor_fn(backbone: str):
    """真干扰器工厂:返回 (rec, k) -> list[str]。网络仅在闭包被调用时发生。"""
    def _distract(rec: dict, k: int) -> list[str]:
        content = _chat_completion(_distractor_prompt(rec, k), backbone, max_tokens=512)
        return _parse_distractors(content, k)
    return _distract


def make_real_judge_fn(backbone: str):
    """审计内部 judge 工厂:(rec, distractor, idx) -> bool,委托 canonical judge。

    候选=已知错误的干扰答案;judge 若判"对"即**误接受**(计入 α_judge)。与 ladder
    打分同源(make_real_ladder_judge_fn),T6 两处接同一 judge。"""
    ladder_judge = make_real_ladder_judge_fn()

    def _judge(rec: dict, distractor: str, idx: int) -> bool:  # noqa: ARG001
        return ladder_judge(rec.get("question", ""), _reference_answer(rec),
                            distractor, backbone)
    return _judge


def audit(corpus: list[dict], k: int, fixture_mode: bool,
          distractor_fn=None, judge_fn=None) -> dict:
    """跑一遍对抗审计,返回 α_judge + 分子分母 + 逐 subset 明细。

    distractor_fn(rec, k)->list[str] 与 judge_fn(rec, distractor, idx)->bool 可注入:
      - fixture_mode:缺省用确定性 mock(_fixture_distractors/_fixture_judge_accepts)。
      - real-mode:**必须**注入(见 make_real_distractor_fn/make_real_judge_fn);缺任一
        → NotImplementedError(CLI 不自动行使网络,真跑由 T6/T7 gated driver 注入)。"""
    if fixture_mode:
        distractor_fn = distractor_fn or _fixture_distractors
        judge_fn = judge_fn or _fixture_judge_accepts
    elif distractor_fn is None or judge_fn is None:
        raise NotImplementedError(
            "real-mode judge 审计是 gated 真跑:须注入 distractor_fn + judge_fn"
            "(make_real_distractor_fn / make_real_judge_fn);CLI 不自动行使网络。")
    accepted = 0
    total = 0
    per_subset: dict[str, list[int]] = {}
    for rec in corpus:
        s = rec.get("subset", "default")
        per_subset.setdefault(s, [])
        for i, d in enumerate(distractor_fn(rec, k)):
            total += 1
            hit = int(judge_fn(rec, d, i))
            accepted += hit
            per_subset[s].append(hit)
    alpha_judge = (accepted / total) if total else 0.0
    subset_alpha = {
        s: (sum(v) / len(v) if v else 0.0) for s, v in per_subset.items()
    }
    return {
        "alpha_judge": alpha_judge,
        "accepted": accepted,
        "total": total,
        "subset_alpha": subset_alpha,
        "unusable": alpha_judge > JUDGE_UNUSABLE_THRESHOLD,
    }


def build_report(benchmark: str, corpus: list[dict], result: dict,
                 k: int, config: dict) -> dict:
    return {
        "benchmark": benchmark,
        "corpus_hash": _corpus_hash(corpus),
        "k": k,
        "config": config,
        "alpha_judge": result["alpha_judge"],
        "accepted": result["accepted"],
        "total": result["total"],
        "subset_alpha": result["subset_alpha"],
        "unusable": result["unusable"],
    }


def _corpus_hash(records: list[dict]) -> str:
    blob = "\n".join(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="judge 对抗审计(fixture-mode 骨架)。")
    p.add_argument("--benchmark", required=True)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--k", type=int, default=DEFAULT_K)
    p.add_argument("--fixture-mode", action="store_true",
                   help="离线确定性 mock 干扰器+judge(CI)。省略=real-mode(需 --real-run)。")
    p.add_argument("--real-run", action="store_true",
                   help="显式行使真跑:干扰器+judge 都用真 LM(花 API)。与 --fixture-mode "
                        "互斥;两者都不给则拒跑(防误触网络)。")
    p.add_argument("--backbone", default="",
                   help="real-mode 的干扰器/judge 模型(须与 ladder 的 answer backbone "
                        "同配置,否则 α_judge 不可解读)。")
    p.add_argument("--provider", choices=("openai", "dashscope"), default="openai",
                   help="real-mode 的供应商。dashscope 时 env-swap OPENAI_*→DASHSCOPE_*。")
    p.add_argument("--report", type=Path, default=Path("build/judge_audit.json"))
    args = p.parse_args(argv)

    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr)
        return 1
    corpus = load_corpus(args.corpus)
    if not corpus:
        print(f"ERROR: empty corpus: {args.corpus}", file=sys.stderr)
        return 1
    # 模式互斥 + 默认拒跑(防误触网络花 API);都给则含义矛盾。
    if args.fixture_mode and args.real_run:
        print("ERROR: --fixture-mode 与 --real-run 互斥。", file=sys.stderr)
        return 1
    if not args.fixture_mode and not args.real_run:
        print("ERROR: 未指定模式。--fixture-mode 跑离线骨架,或 --real-run 显式行使"
              "真跑(干扰器+judge 都是真 LM,花 API)。", file=sys.stderr)
        return 1

    if args.fixture_mode:
        config = {"judge": "fixture", "distractor": "fixture", "mode": "fixture"}
        result = audit(corpus, args.k, True)
    else:
        # real-mode:注入真干扰器 + 真 judge。judge 必须与 ladder 打分**同源**
        # (make_real_ladder_judge_fn),否则 α_judge 度量的不是 ladder 用的那个
        # judge,band 就不可解读(见 §3.1)。
        if args.provider == "dashscope":
            import os
            saved = (os.environ.get("OPENAI_API_KEY"),
                     os.environ.get("OPENAI_BASE_URL"))
            os.environ["OPENAI_API_KEY"] = os.environ["DASHSCOPE_API_KEY"]
            os.environ["OPENAI_BASE_URL"] = os.environ.get("DASHSCOPE_BASE_URL", "")
        config = {"judge": args.backbone or "env-default",
                  "distractor": args.backbone or "env-default",
                  "provider": args.provider, "mode": "real"}
        result = audit(corpus, args.k, False,
                       distractor_fn=make_real_distractor_fn(args.backbone),
                       judge_fn=make_real_judge_fn(args.backbone))
        if args.provider == "dashscope":
            import os
            if saved[0] is not None:
                os.environ["OPENAI_API_KEY"] = saved[0]
            if saved[1] is not None:
                os.environ["OPENAI_BASE_URL"] = saved[1]
    report = build_report(args.benchmark, corpus, result, args.k, config)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"Report written to {args.report}", file=sys.stderr)
    print(f"[{args.benchmark}] α_judge = {result['alpha_judge']:.4f} "
          f"({result['accepted']}/{result['total']})"
          + ("  ⚠ JUDGE UNUSABLE (换更强 judge 或结构化评分)" if result["unusable"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
