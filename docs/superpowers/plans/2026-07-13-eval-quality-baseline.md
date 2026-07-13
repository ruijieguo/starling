# 质量回归基线(dogfood 子项 C)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一个 orchestrator `scripts/eval_quality_baseline.py` 复用既有 3 维 benchmark harness 的 `run_one_round`,在小固定 corpus 子集真 LLM 跑 N 轮取中位数 → git-committed 基线 JSON → 重跑 diff 判回归。

**Architecture:** import(非 subprocess)三维 harness 的 `run_one_round`,orchestrator 自己跑 N 轮取中位数(脚本 main 用 last-round 判据,不复用)。真 LLM 段(`collect_scores`,含 3 个每维适配器 + 每维 try/except 韧性)与纯逻辑段(`diff_against_baseline`/`render_report`/`has_regression`/`median`/`load_baseline`/`save_baseline`)解耦——纯逻辑注入 mock 分数 fixture 单测、进 pytest 门;真 LLM 段手动验证、不进 CI。

**Tech Stack:** Python 3(stdlib argparse/json/statistics)、既有 `scripts/eval_*.py`、pytest。零 C++/绑定改动。

## Global Constraints

- **复用不重写**:import 既有 `eval_p1_extractor.run_one_round` / `eval_longmemeval.run_one_round` / `eval_tom_bench.run_one_round` + 它们的阈值常量;orchestrator 只加 子集选择 + N 轮中位数 + 基线 diff + 组合报告。
- **解耦**:`collect_scores`(真 LLM)与 `diff_against_baseline`/`render_report`/`has_regression`/`median`/`load_baseline`/`save_baseline`(纯逻辑)分离;纯逻辑 fixture 单测进 pytest 门、零真 LLM;真 LLM 跑不进 CI/pytest(Clash TUN 不可靠)。
- **韧性(硬)**:每维 eval 用 try/except 包;某维**抛异常**(如 longmemeval real-mode 从未跑过可能崩、或 Clash 网络故障)→ 该维记为 `ERRORED`(current=None),**报「需重跑」而非质量回归、不崩其余维**。整轮分数近 0(疑似网络黑洞)→ 报告标「疑似网络,verify」。
- **基线纪律**:只在有意质量变更后 `--update`(非每次重写,避免 LLM 噪声 diff);LLM 噪声用 N 轮中位数 + 容差带吸收。
- **退出码**:全 OK=0;有真回归(相对退化超容差 或 破阈值)=1;无回归但有 ERRORED/不完整=2(需重跑)。
- **env / 安全**:LLM 端点从 `OPENAI_API_KEY`/`OPENAI_BASE_URL` 读(longmemeval embeddings 另读 `DASHSCOPE_*`);**绝不打印 key**。
- **git**:显式路径 `git add`(禁 `.`/`-A`);不用 `--no-verify`/`--amend`;commit 尾 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- **pytest**:一律 `.venv/bin/python -m pytest tests/python`;无 C++/绑定改动 → 无需 configure_build。
- **NEVER merge**:PR + CI 绿 + 用户明确「合并」。

## File Structure

- `scripts/eval_quality_baseline.py`(新):orchestrator。纯逻辑函数 + `collect_scores`(3 适配器)+ `main`(argparse)。
- `tests/python/test_eval_quality_baseline.py`(新):纯逻辑 fixture 单测(零真 LLM)。
- `tests/data/eval_baseline.json`(新,Task 3 真机 `--update` 生成后提交):git-committed 基线。

## 基线 JSON schema(统一,eval_id → metrics → {median, threshold})

```json
{
  "meta": {"model": "deepseek-v4-pro", "updated_at": "2026-07-13T10:00:00Z", "rounds": 3, "max_items": 15, "tolerance": 0.05},
  "evals": {
    "extract": {"holder": {"median": 0.90, "threshold": 0.85}, "holder_perspective": {"median": 0.85, "threshold": 0.80}, "predicate": {"median": 0.80, "threshold": 0.75}, "object": {"median": 0.75, "threshold": 0.70}, "nesting_depth_1": {"median": 0.65, "threshold": 0.60}},
    "tom":     {"accuracy": {"median": 0.65, "threshold": 0.55}},
    "recall":  {"overall": {"median": 0.70, "threshold": 0.55}}
  }
}
```
- extract 有 5 个 per-field metric(阈值来自 `P1_THRESHOLDS`);tom 1 个(`ACCURACY_THRESHOLD`=0.55);recall 1 个 overall(`ACCURACY_THRESHOLD`=0.55,= sum(correct)/sum(total) over subsets)。

---

### Task 1: 纯逻辑 + 基线读写 + fixture 测试(TDD,零真 LLM)

**Files:**
- Create: `scripts/eval_quality_baseline.py`(先只放纯逻辑函数 + 常量;`collect_scores`/`main` 留 Task 2)
- Test: `tests/python/test_eval_quality_baseline.py`

**Interfaces:**
- Produces(Task 2 消费):
  - `median(values: list[float]) -> float`
  - `first_n(corpus: list, n: int | None) -> list`
  - `EVAL_THRESHOLDS: dict[str, dict[str, float]]`（`{"extract": P1_THRESHOLDS, "tom": {"accuracy":0.55}, "recall": {"overall":0.55}}`）
  - `diff_against_baseline(current: dict[str, dict[str, float] | None], baseline_evals: dict, tolerance: float) -> list[dict]`（每 finding：`{eval_id, metric, baseline, current, threshold, verdict}`，verdict ∈ `OK/REGRESSION/BELOW_THRESHOLD/ERRORED/MISSING`）
  - `render_report(findings: list[dict], meta: dict) -> str`
  - `has_regression(findings) -> bool` / `exit_code(findings) -> int`
  - `save_baseline(path, current: dict, meta: dict) -> None` / `load_baseline(path) -> dict | None`

- [ ] **Step 1: 写失败测试 `tests/python/test_eval_quality_baseline.py`**

```python
"""质量回归基线 orchestrator 的纯逻辑 fixture 单测——零真 LLM(diff/容差/阈值/
中位数/基线读写/ERRORED 韧性)。真 LLM 段(collect_scores 的 3 适配器)不在此。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eval_quality_baseline import (  # noqa: E402
    median, first_n, diff_against_baseline, render_report, has_regression,
    exit_code, save_baseline, load_baseline, EVAL_THRESHOLDS,
)


def test_median_odd_even():
    assert median([0.5]) == 0.5
    assert median([0.2, 0.8, 0.5]) == 0.5
    assert median([0.2, 0.8, 0.4, 0.6]) == 0.5   # 均值 of 中间两个


def test_first_n():
    assert first_n([1, 2, 3, 4, 5], 3) == [1, 2, 3]
    assert first_n([1, 2], 5) == [1, 2]
    assert first_n([1, 2, 3], None) == [1, 2, 3]


def test_thresholds_shape():
    assert set(EVAL_THRESHOLDS) == {"extract", "tom", "recall"}
    assert EVAL_THRESHOLDS["tom"]["accuracy"] == 0.55
    assert EVAL_THRESHOLDS["recall"]["overall"] == 0.55
    assert "predicate" in EVAL_THRESHOLDS["extract"]


def _baseline_evals():
    return {
        "extract": {"predicate": {"median": 0.80, "threshold": 0.75}},
        "tom": {"accuracy": {"median": 0.65, "threshold": 0.55}},
        "recall": {"overall": {"median": 0.70, "threshold": 0.55}},
    }


def test_diff_ok_within_tolerance():
    # 略降但在容差内 → OK,无回归
    cur = {"extract": {"predicate": 0.78}, "tom": {"accuracy": 0.63}, "recall": {"overall": 0.68}}
    findings = diff_against_baseline(cur, _baseline_evals(), tolerance=0.05)
    assert all(f["verdict"] == "OK" for f in findings)
    assert not has_regression(findings)
    assert exit_code(findings) == 0


def test_diff_relative_regression():
    # predicate 从 0.80 掉到 0.72 = 降 0.08 > 容差 0.05 → REGRESSION
    cur = {"extract": {"predicate": 0.72}, "tom": {"accuracy": 0.65}, "recall": {"overall": 0.70}}
    findings = diff_against_baseline(cur, _baseline_evals(), tolerance=0.05)
    reg = [f for f in findings if f["eval_id"] == "extract" and f["metric"] == "predicate"][0]
    assert reg["verdict"] == "REGRESSION"
    assert has_regression(findings)
    assert exit_code(findings) == 1


def test_diff_below_threshold():
    # tom 掉破绝对地板 0.55(即便相对基线降幅可能在容差内)→ BELOW_THRESHOLD
    cur = {"extract": {"predicate": 0.80}, "tom": {"accuracy": 0.50}, "recall": {"overall": 0.70}}
    findings = diff_against_baseline(cur, _baseline_evals(), tolerance=0.20)  # 大容差,只测阈值地板
    tom = [f for f in findings if f["eval_id"] == "tom"][0]
    assert tom["verdict"] == "BELOW_THRESHOLD"
    assert has_regression(findings)
    assert exit_code(findings) == 1


def test_diff_errored_is_not_regression_but_exit_2():
    # 某维 current=None(collect_scores 抛异常/网络故障)→ ERRORED,非回归,退出 2
    cur = {"extract": {"predicate": 0.80}, "tom": None, "recall": {"overall": 0.70}}
    findings = diff_against_baseline(cur, _baseline_evals(), tolerance=0.05)
    tom = [f for f in findings if f["eval_id"] == "tom"][0]
    assert tom["verdict"] == "ERRORED"
    assert not has_regression(findings)     # ERRORED 不是质量回归
    assert exit_code(findings) == 2         # 但也不是干净 0——需重跑


def test_report_contains_verdicts():
    cur = {"extract": {"predicate": 0.72}, "tom": None, "recall": {"overall": 0.70}}
    findings = diff_against_baseline(cur, _baseline_evals(), tolerance=0.05)
    rep = render_report(findings, {"model": "m", "rounds": 3})
    assert "REGRESSION" in rep and "ERRORED" in rep and "predicate" in rep


def test_baseline_roundtrip(tmp_path):
    p = tmp_path / "eval_baseline.json"
    cur = {"extract": {"predicate": 0.80}, "tom": {"accuracy": 0.65}, "recall": {"overall": 0.70}}
    save_baseline(p, cur, {"model": "m", "rounds": 3, "max_items": 15, "tolerance": 0.05})
    loaded = load_baseline(p)
    assert loaded["evals"]["extract"]["predicate"]["median"] == 0.80
    assert loaded["evals"]["extract"]["predicate"]["threshold"] == EVAL_THRESHOLDS["extract"]["predicate"]
    assert loaded["evals"]["tom"]["accuracy"]["threshold"] == 0.55
    assert loaded["meta"]["model"] == "m"


def test_load_missing_baseline(tmp_path):
    assert load_baseline(tmp_path / "nope.json") is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/python/test_eval_quality_baseline.py -q`
Expected: FAIL(`ModuleNotFoundError` 或 `ImportError: cannot import name ...`——`eval_quality_baseline` 未创建/函数未定义)。

- [ ] **Step 3: 写 `scripts/eval_quality_baseline.py` 的纯逻辑段**

```python
#!/usr/bin/env python3
"""质量回归基线 orchestrator(dogfood 子项 C)。

复用既有 3 维 benchmark harness(eval_p1_extractor / eval_longmemeval /
eval_tom_bench)的 run_one_round,在小固定 corpus 子集真 LLM 跑 N 轮取中位数,
写/diff 一个 git-committed 基线 JSON,判质量回归。非 CI(真 LLM/Clash 不可靠)。

  # 建/更新基线(有意质量变更后)
  python scripts/eval_quality_baseline.py --update
  # 检查回归(改 prompt/gist/extractor 前后)
  python scripts/eval_quality_baseline.py --check
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

# 复用既有 harness 的阈值常量(不重写 eval 逻辑)。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_p1_extractor import P1_THRESHOLDS               # noqa: E402
from eval_tom_bench import ACCURACY_THRESHOLD as TOM_THRESHOLD    # noqa: E402
from eval_longmemeval import ACCURACY_THRESHOLD as RECALL_THRESHOLD  # noqa: E402

EVAL_THRESHOLDS: dict[str, dict[str, float]] = {
    "extract": dict(P1_THRESHOLDS),                 # 5 个 per-field F1 阈值
    "tom":     {"accuracy": TOM_THRESHOLD},         # 0.55
    "recall":  {"overall": RECALL_THRESHOLD},       # 0.55
}

DEFAULT_BASELINE = Path(__file__).resolve().parents[1] / "tests" / "data" / "eval_baseline.json"
# 整轮所有指标都 < 此地板 = 疑似网络黑洞(Clash TUN),非质量(见 clash-tun 记忆)。
NETWORK_FLOOR = 0.05


def median(values: list[float]) -> float:
    """N 轮某指标的中位数(抗离群;偶数取中间两者均值,statistics.median 语义)。"""
    return float(statistics.median(values))


def first_n(corpus: list, n: int | None) -> list:
    """确定性小固定子集:前 n 条(n=None → 全量)。同一 corpus 每次同样本 → 可比。"""
    return corpus if n is None else corpus[:n]


def diff_against_baseline(current: dict[str, dict[str, float] | None],
                          baseline_evals: dict, tolerance: float) -> list[dict]:
    """逐 eval_id / metric 判定。current[eval_id] 为 None = 该维 ERRORED(采分抛异常)。
    verdict: OK / REGRESSION(相对退化超容差)/ BELOW_THRESHOLD(破绝对地板)/
    ERRORED(采分失败)/ MISSING(基线无此项)。"""
    findings: list[dict] = []
    for eval_id, metrics in baseline_evals.items():
        cur_eval = current.get(eval_id)
        if cur_eval is None:
            findings.append({"eval_id": eval_id, "metric": "*", "baseline": None,
                             "current": None, "threshold": None, "verdict": "ERRORED"})
            continue
        for metric, spec in metrics.items():
            base = spec["median"]
            thr = spec["threshold"]
            cur = cur_eval.get(metric)
            if cur is None:
                verdict = "ERRORED"
            elif cur < thr:
                verdict = "BELOW_THRESHOLD"
            elif cur < base - tolerance:
                verdict = "REGRESSION"
            else:
                verdict = "OK"
            findings.append({"eval_id": eval_id, "metric": metric, "baseline": base,
                             "current": cur, "threshold": thr, "verdict": verdict})
    return findings


def has_regression(findings: list[dict]) -> bool:
    """真质量回归 = 相对退化 或 破阈值(ERRORED 不算——那是采不到分,另计)。"""
    return any(f["verdict"] in ("REGRESSION", "BELOW_THRESHOLD") for f in findings)


def exit_code(findings: list[dict]) -> int:
    """0=全 OK;1=有真回归;2=无回归但有 ERRORED(需重跑)。"""
    if has_regression(findings):
        return 1
    if any(f["verdict"] == "ERRORED" for f in findings):
        return 2
    return 0


def render_report(findings: list[dict], meta: dict) -> str:
    lines = ["# 质量回归基线报告",
             f"model={meta.get('model')} rounds={meta.get('rounds')} "
             f"max_items={meta.get('max_items')} tolerance={meta.get('tolerance')}",
             "", "| eval | metric | baseline | current | threshold | verdict |",
             "|---|---|---|---|---|---|"]
    mark = {"OK": "✅ OK", "REGRESSION": "⚠ REGRESSION", "BELOW_THRESHOLD": "✗ BELOW_THRESHOLD",
            "ERRORED": "⁇ ERRORED(需重跑)", "MISSING": "· MISSING"}
    for f in findings:
        b = "—" if f["baseline"] is None else f"{f['baseline']:.3f}"
        c = "—" if f["current"] is None else f"{f['current']:.3f}"
        t = "—" if f["threshold"] is None else f"{f['threshold']:.2f}"
        lines.append(f"| {f['eval_id']} | {f['metric']} | {b} | {c} | {t} | {mark.get(f['verdict'], f['verdict'])} |")
    verdict = ("✗ 有质量回归" if has_regression(findings)
               else ("⁇ 有维度采分失败,需重跑" if any(f['verdict'] == 'ERRORED' for f in findings)
                     else "✅ 无回归"))
    lines += ["", f"**总判定:{verdict}**"]
    return "\n".join(lines) + "\n"


def save_baseline(path: Path, current: dict[str, dict[str, float]], meta: dict) -> None:
    """current[eval_id][metric] = 中位数 → 加各自 threshold → 写 schema。跳过 None 维。"""
    evals: dict = {}
    for eval_id, metrics in current.items():
        if metrics is None:
            continue
        evals[eval_id] = {
            metric: {"median": val, "threshold": EVAL_THRESHOLDS[eval_id][metric]}
            for metric, val in metrics.items()
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meta": meta, "evals": evals}, indent=2, ensure_ascii=False) + "\n")


def load_baseline(path: Path) -> dict | None:
    if not Path(path).exists():
        return None
    return json.loads(Path(path).read_text())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/python/test_eval_quality_baseline.py -q`
Expected: PASS(10 测试)。

- [ ] **Step 5: 提交**

```bash
git add scripts/eval_quality_baseline.py tests/python/test_eval_quality_baseline.py
git commit -m "$(cat <<'EOF'
feat(eval): quality regression baseline — pure logic (diff/threshold/report/IO)

质量回归基线 orchestrator 的纯逻辑段:median / first_n 子集 / diff_against_baseline
(相对退化超容差 或 破 harness 阈值,ERRORED 韧性)/ render_report / has_regression /
exit_code(0 OK/1 回归/2 需重跑)/ 基线 JSON 读写。复用既有 harness 的阈值常量。
fixture 单测覆盖、零真 LLM。collect_scores/CLI 留下一任务。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: collect_scores(3 适配器,真 LLM)+ CLI

**Files:**
- Modify: `scripts/eval_quality_baseline.py`(加 `collect_scores` + 3 个每维适配器 + `main`)
- Test: `tests/python/test_eval_quality_baseline.py`(加 collect_scores 的可测部分:注入 mock run_one_round 验中位数聚合 + 韧性,零真 LLM)

**Interfaces:**
- Consumes: Task 1 的 `median`/`first_n`/`diff_against_baseline`/`render_report`/`exit_code`/`save_baseline`/`load_baseline`/`EVAL_THRESHOLDS`;既有 `eval_p1_extractor.run_one_round(corpus, base_url, api_key, model)->dict[field,float]`、`eval_tom_bench.run_one_round(corpus, *, fixture_mode, base_url, api_key, model, abilities)->float`、`eval_longmemeval.run_one_round(corpus, subsets, fixture_mode)->dict[subset,(correct,total)]`。
- Produces: `collect_scores(rounds, max_items, model, base_url, api_key) -> dict[str, dict[str, float] | None]`;`main(argv) -> int`。

- [ ] **Step 1: 写失败测试(collect_scores 聚合 + 韧性,注入 mock,零真 LLM)**

加到 `tests/python/test_eval_quality_baseline.py`:

```python
import eval_quality_baseline as eqb  # noqa: E402


def test_score_one_eval_medians_over_rounds():
    # 注入 fake run_one_round(3 轮返回不同 f1)→ 断言每 field 取中位数。
    calls = {"n": 0}
    rounds_out = [
        {"predicate": 0.70, "object": 0.60},
        {"predicate": 0.80, "object": 0.65},
        {"predicate": 0.90, "object": 0.55},
    ]
    def fake():
        i = calls["n"]; calls["n"] += 1
        return rounds_out[i]
    got = eqb._score_dim_dict(rounds=3, call=fake)
    assert got == {"predicate": 0.80, "object": 0.60}   # 各 field 中位数


def test_score_dim_resilient_all_rounds_error():
    # 每轮都抛 → 该维 None(ERRORED),不冒泡崩溃。
    def boom():
        raise RuntimeError("transport_error:SSL connect error")
    got = eqb._score_dim_dict(rounds=3, call=boom)
    assert got is None


def test_score_dim_partial_error_uses_good_rounds():
    # 3 轮里 1 轮抛、2 轮好 → 用好的 2 轮取中位数,不因 1 轮网络抖动丢整维。
    seq = [{"predicate": 0.80}, RuntimeError("blip"), {"predicate": 0.60}]
    it = iter(seq)
    def maybe():
        v = next(it)
        if isinstance(v, Exception):
            raise v
        return v
    got = eqb._score_dim_dict(rounds=3, call=maybe)
    assert got == {"predicate": 0.70}   # median(0.80, 0.60)
```

（注:`call` 是**零参 thunk**——闭包封「这维怎么调 run_one_round(含异质签名 + corpus + args)」;`_score_dim_dict(rounds, call)` 只管通用聚合「跑 rounds 次、收字典型分数、每 key 取中位数、全错返回 None、per-round try 韧性」,可注入 fake 单测。float 型(tom)用 `_score_dim_float(rounds, call, metric_name)` 同理返回 `{"accuracy": median}`。）

- [ ] **Step 2: 跑确认失败**

Run: `.venv/bin/python -m pytest tests/python/test_eval_quality_baseline.py -q`
Expected: FAIL(`_score_dim_dict` 未定义)。

- [ ] **Step 3: 实现 collect_scores + 适配器 + main（追加到 `scripts/eval_quality_baseline.py`）**

```python
import os
import time

# 复用既有 harness 的 run_one_round(不重写 eval 逻辑)。
import eval_p1_extractor
import eval_longmemeval
import eval_tom_bench

_CORPORA = {
    "extract": Path(__file__).resolve().parents[1] / "tests/data/eval_p1_corpus.jsonl",
    "recall":  Path(__file__).resolve().parents[1] / "tests/data/eval_longmemeval/sessions.jsonl",
    "tom":     Path(__file__).resolve().parents[1] / "tests/data/eval_tom_bench/first_order.jsonl",
}


def _load_corpus(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _score_dim_dict(rounds, call) -> dict[str, float] | None:
    """跑零参 thunk `call` rounds 次(call 返回 dict[metric,float]),每 metric 取
    中位数;某轮抛则跳过该轮,全轮皆抛返回 None(该维 ERRORED)。"""
    per_metric: dict[str, list[float]] = {}
    ok_rounds = 0
    for r in range(rounds):
        try:
            out = call()
        except Exception as exc:  # noqa: BLE001 — 网络/pipeline 故障 → 跳该轮,不崩整维
            print(f"    round {r+1}/{rounds} ERRORED: {exc}", file=sys.stderr)
            continue
        ok_rounds += 1
        for k, v in out.items():
            per_metric.setdefault(k, []).append(float(v))
    if ok_rounds == 0:
        return None
    return {k: median(vs) for k, vs in per_metric.items()}


def _score_dim_float(rounds, call, metric_name="accuracy") -> dict[str, float] | None:
    """同 _score_dim_dict,但零参 thunk `call` 返回单个 float。"""
    vals: list[float] = []
    for r in range(rounds):
        try:
            vals.append(float(call()))
        except Exception as exc:  # noqa: BLE001
            print(f"    round {r+1}/{rounds} ERRORED: {exc}", file=sys.stderr)
    if not vals:
        return None
    return {metric_name: median(vals)}


def _flag_network(scores: dict[str, float] | None) -> dict[str, float] | None:
    """整维所有指标都 < NETWORK_FLOOR = 疑似 Clash 黑洞非质量 → 返回 None(ERRORED,报重跑)。"""
    if scores is None:
        return None
    if scores and all(v < NETWORK_FLOOR for v in scores.values()):
        print("    WARN: 所有指标近 0 → 疑似网络黑洞(Clash),记 ERRORED 需重跑", file=sys.stderr)
        return None
    return scores


def collect_scores(rounds: int, max_items: int | None, model: str,
                   base_url: str, api_key: str) -> dict[str, dict[str, float] | None]:
    """真 LLM 段:三维各自适配器调 run_one_round rounds 次取中位数。每维 try/except
    韧性(某维崩 → None=ERRORED,不崩其余)。longmemeval real-mode 从未真跑过,
    可能在此首次暴露 bug——被 _score_dim_dict 的 per-round try 兜住报 ERRORED。"""
    current: dict[str, dict[str, float] | None] = {}

    # 抽取:eval_p1_extractor.run_one_round(corpus, base_url, api_key, model) -> dict[field,f1]
    extract_corpus = first_n(_load_corpus(_CORPORA["extract"]), max_items)
    current["extract"] = _flag_network(_score_dim_dict(rounds,
        call=lambda: eval_p1_extractor.run_one_round(extract_corpus, base_url, api_key, model)))

    # ToM:eval_tom_bench.run_one_round(corpus, *, fixture_mode, base_url, api_key, model, abilities) -> float
    tom_corpus = first_n(_load_corpus(_CORPORA["tom"]), max_items)
    current["tom"] = _flag_network(_score_dim_float(rounds,
        call=lambda: eval_tom_bench.run_one_round(
            tom_corpus, fixture_mode=False, base_url=base_url, api_key=api_key,
            model=model, abilities=eval_tom_bench.FIRST_ORDER_ABILITIES)))

    # 召回:eval_longmemeval.run_one_round(corpus, subsets, fixture_mode=False) -> dict[subset,(c,t)]
    #   模型经 env(CHAT_MODEL);headline = overall = sum(correct)/sum(total)。
    #   real-mode 惰性 import _core、每 record 建整条 pipeline(重),从未真跑=可能崩→ERRORED。
    os.environ.setdefault("CHAT_MODEL", model)
    recall_corpus = first_n(_load_corpus(_CORPORA["recall"]), max_items)
    def _recall_overall():
        by_subset = eval_longmemeval.run_one_round(recall_corpus, eval_longmemeval.SUBSETS, False)
        c = sum(v[0] for v in by_subset.values())
        t = sum(v[1] for v in by_subset.values())
        return {"overall": (c / t if t else 0.0)}
    current["recall"] = _flag_network(_score_dim_dict(rounds, call=_recall_overall))

    return current


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="质量回归基线 orchestrator(非 CI,真 LLM)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="重跑 diff 基线判回归(默认)")
    mode.add_argument("--update", action="store_true", help="跑一遍覆写基线(有意质量变更后)")
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--tolerance", type=float, default=0.05)
    p.add_argument("--max-items", type=int, default=15)
    p.add_argument("--model", default="deepseek-v4-pro")
    p.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    p.add_argument("--report", type=Path, default=None, help="可选:报告落盘路径")
    args = p.parse_args(argv)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set(不打印 key)", file=sys.stderr)
        return 2

    print(f"跑三维 eval(rounds={args.rounds} max_items={args.max_items} model={args.model})...",
          file=sys.stderr)
    current = collect_scores(args.rounds, args.max_items, args.model, base_url, api_key)
    meta = {"model": args.model, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rounds": args.rounds, "max_items": args.max_items, "tolerance": args.tolerance}

    if args.update:
        save_baseline(args.baseline, current, meta)
        print(f"基线已写 {args.baseline}", file=sys.stderr)
        # 覆写后打印一份「当前 vs 自身」报告(全 OK/ERRORED)供核对。
        errored = [k for k, v in current.items() if v is None]
        if errored:
            print(f"WARN: 以下维采分失败(基线未含)需重跑:{errored}", file=sys.stderr)
        return 2 if errored else 0

    # --check(默认)
    baseline = load_baseline(args.baseline)
    if baseline is None:
        print(f"ERROR: 基线不存在 {args.baseline} —— 先 --update 建基线", file=sys.stderr)
        return 2
    findings = diff_against_baseline(current, baseline["evals"], args.tolerance)
    report = render_report(findings, meta)
    print(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report)
    return exit_code(findings)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过 + orchestrator import 无误**

```bash
.venv/bin/python -m pytest tests/python/test_eval_quality_baseline.py -q
.venv/bin/python -c "import sys; sys.path.insert(0,'scripts'); import eval_quality_baseline as e; print('import ok', bool(e.collect_scores), bool(e.main))"
.venv/bin/python scripts/eval_quality_baseline.py --check 2>&1 | tail -3   # 无 OPENAI_API_KEY → 干净 return 2 提示,不崩
```
Expected: pytest 全绿(13 测试);import ok;无 key 时 `--check` 打印 ERROR 提示 + return 2(不 traceback)。

- [ ] **Step 5: 全量 pytest(确认零回归)**

Run: `.venv/bin/python -m pytest tests/python -q`
Expected: 全绿(新增纯逻辑测试;既有 eval harness 自测不受影响——本任务只 import 它们的 run_one_round/常量,未改它们)。

- [ ] **Step 6: 提交**

```bash
git add scripts/eval_quality_baseline.py tests/python/test_eval_quality_baseline.py
git commit -m "$(cat <<'EOF'
feat(eval): quality baseline collect_scores (3 adapters) + CLI

collect_scores import 三维 harness run_one_round(不重写):extract(per-field F1)/
tom(accuracy)/recall(longmemeval overall);每维适配器封异质签名,_score_dim_*
跑 N 轮取中位数 + per-round try 韧性(某轮/某维网络故障→跳/ERRORED 不崩整体)+
_flag_network(整维近 0=疑似 Clash 黑洞→ERRORED 报重跑)。CLI --check/--update。
longmemeval real-mode 从未真跑,首次真跑在 Task 3。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: 真机手动验证(非 CI 门,controller 执行)

**Files:** 无代码;`tests/data/eval_baseline.json`(`--update` 生成后提交)。

- [ ] **Step 1: 确认 env(不打印 key)+ 建首个基线**

```bash
export PATH="$PWD/.venv/bin:$PATH"
# OPENAI_API_KEY / OPENAI_BASE_URL 应已在 env(~/.starling/starling.json 有 provider);不回显。
.venv/bin/python -c "import os;print('OPENAI_API_KEY set:', bool(os.environ.get('OPENAI_API_KEY')),' BASE:', bool(os.environ.get('OPENAI_BASE_URL')))"
.venv/bin/python scripts/eval_quality_baseline.py --update --rounds 3 --max-items 15 2>&1 | tail -20
```
Expected: 三维跑完写出 `tests/data/eval_baseline.json`。**关键观察**:recall(longmemeval real-mode 首次真跑)是否 ERRORED——若崩(pipeline 构造 bug),记录 traceback = **dogfood 抓到的真 bug**;此时 extract+tom 应仍成功入基线,recall 记 ERRORED。

- [ ] **Step 2: `--check` 证同基线 diff=0**

```bash
.venv/bin/python scripts/eval_quality_baseline.py --check --rounds 3 --max-items 15 2>&1 | tail -25; echo "exit=$?"
```
Expected: 报告各维 `✅ OK`(LLM 噪声在容差内);exit=0(或若某维 ERRORED 则 exit=2)。若某维报 REGRESSION 而非网络,说明容差需调——记录实测轮间波动定容差。

- [ ] **Step 3:(可选)证能抓回归**

临时把 `python/starling/extractor/prompts.py` 的 belief_prompt 改劣一版(或 `--tolerance 0.001` 放大灵敏度)→ `--check` → 应报 REGRESSION、exit=1;复原。证 diff 机制真能抓质量退化,不是摆设。

- [ ] **Step 4: 提交基线 + 记结果**

```bash
git add tests/data/eval_baseline.json
git commit -m "$(cat <<'EOF'
chore(eval): commit first quality baseline (3-dim, real LLM)

首个质量回归基线:extract per-field F1 / tom accuracy / recall overall,
rounds=3 max_items=15。真机 --update 生成。<longmemeval real-mode 首跑结果记 PR body>。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```
真机结果(三维中位数、longmemeval real-mode 是否可跑/抓到 bug、实测轮间波动 vs 容差、回归验证)全进 PR body。Clash 黑洞([[clash-tun-owns-all-network-flakiness]])则换时刻重跑。

## Self-Review

**1. Spec coverage(逐节对 spec):**
- Design ①(orchestrator 两模式 --check/--update)→ Task 2 main。✓
- Design ②(三维 + 复用 run_one_round + 小固定子集)→ Task 2 collect_scores + `_CORPORA` + first_n;开放取舍解为 **import(非 subprocess)**——三 run_one_round 都可干净 import + orchestrator 自跑 N 轮中位数(脚本 main 用 last-round 不复用)。✓
- Design ③(基线 JSON schema)→ Task 1 save/load_baseline + schema。✓(细化:extract 5 per-field metric,统一 eval_id→metric→{median,threshold})
- Design ④(回归判据 + 报告 + 退出码)→ Task 1 diff/render/has_regression/exit_code。✓
- Design ⑤(LLM 噪声 N 轮中位数 + 容差 + 网络故障区分)→ Task 1 median、Task 2 `_score_dim_*` per-round try + `_flag_network`。✓
- Testing(fixture 纯逻辑进门 / 真 LLM 手动)→ Task 1+2 fixture 测试 + Task 3 手动。✓
- Out of scope(dashboard/真实数据/CI/FANToM/4+维)→ 未纳入。✓

**2. Placeholder scan:** 无 TBD/TODO;每步含完整代码或精确命令。longmemeval real-mode「首跑可能崩」不是占位——是显式风险 + 韧性兜底 + Task 3 验证点。✓

**3. Type consistency:**
- `collect_scores → dict[eval_id, dict[metric,float] | None]`(Task 2)喂 `diff_against_baseline(current, baseline_evals, tolerance)`(Task 1)——current 形态一致(None=ERRORED)。✓
- `save_baseline(current, meta)` 的 current 同上;写出 schema 被 `load_baseline` 读回、`baseline["evals"]` 喂 diff。✓
- `EVAL_THRESHOLDS[eval_id][metric]`(Task 1)被 save_baseline 用来附 threshold;key 与 collect_scores 产出的 metric key 一致(extract=P1_THRESHOLDS 的 field、tom=accuracy、recall=overall)。✓
- `_score_dim_dict`/`_score_dim_float`(Task 2)返回 `dict[metric,float]|None`,与 diff 的 current[eval_id] 契合。✓

**下一步:** self-review 通过 → /plan-eng-review(codex 外部视角:import-vs-subprocess 抉择、collect_scores/纯逻辑解耦、网络故障 vs 质量回归区分、longmemeval 首跑风险)→ subagent-driven-development。
