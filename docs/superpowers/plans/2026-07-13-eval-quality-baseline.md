# 质量回归基线(dogfood 子项 C)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** orchestrator `scripts/eval_quality_baseline.py` 复用既有 **2 维** benchmark harness(extract F1 / ToM accuracy)的 `run_one_round`,在**全量小 corpus** 真 LLM 跑 N 轮取中位数 → git-committed 基线 JSON → 重跑 diff 判回归。

**Architecture:** import(非 subprocess)2 维 harness 的 `run_one_round`,orchestrator 自跑 N 轮取中位数。真 LLM 段(`collect_scores`)与纯逻辑段(diff/report/median/IO/config-check)解耦——纯逻辑 + collect_scores 接线(注入 mock run_one_round)fixture 单测、进 pytest 门;真 LLM 手动、不进 CI。

**Tech Stack:** Python 3(argparse/json/hashlib/statistics)、既有 `scripts/eval_p1_extractor.py`/`eval_tom_bench.py`、pytest。零 C++/绑定。

## Global Constraints

- **复用不重写**:import `eval_p1_extractor.run_one_round`/`eval_tom_bench.run_one_round` + 阈值常量;orchestrator 只加全量 corpus 加载 + N 轮中位数 + 基线 diff/完整性/可比性 + 报告。
- **范围 = 2 维(extract+tom)**;recall/longmemeval 拿掉作 follow-up(codex #2/#7/#8:real-mode 基本坏)。
- **全量小 corpus,非 first-N**(codex #3:`corpus[:15]` 漏 ability/偏 subset)。可选 `--max-items` 默认 None=全量。
- **解耦 + 可测**:纯逻辑 + `collect_scores`(注入 mock)fixture 单测进 pytest 门、零真 LLM;真 LLM 跑不进 CI/pytest(Clash 不可靠)。
- **网络故障诚实报不隐藏(codex #4/#5)**:harness `run_one_round` 内部吞 per-record 网络异常当答错(→低分不抛),故分数层无法区分网络崩 vs 质量崩。**不用 `_flag_network` 藏近 0 分成 ERRORED**;0/低分照实报 `BELOW_THRESHOLD`(退出 1),某维全指标近 0 时报告**附注**「疑似网络,查 stderr」。
- **min 成功轮(codex #6)**:某维成功轮 < `--min-ok`(默认 2)→ `INCOMPLETE`(不从 1 样本判定)。
- **基线完整性(codex #1/#12)**:`--update` 要求 extract+tom 都成功采分才写——任一维 None/INCOMPLETE 则**拒写、保留旧基线**、退出 2。`--check` 基线缺配置维 → `MISSING` verdict。
- **配置可比性(codex #10)**:基线元数据记 model + rounds + max_items + 每维 corpus sha256;`--check` 比对当前——model 或 corpus hash 不匹配 → 拒 diff、提示 `--update`、退出 2。
- **退出码**:全 OK=0;真回归(REGRESSION/BELOW_THRESHOLD)=1;无回归但 ERRORED/INCOMPLETE/MISSING/配置不匹配=2。
- **env/安全**:LLM 从 `OPENAI_API_KEY`/`OPENAI_BASE_URL` 读;**不打印 key**。
- **git**:显式路径 add;不用 `--no-verify`/`--amend`;commit 尾 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。
- **pytest**:`.venv/bin/python -m pytest tests/python`;无 C++/绑定 → 无需 configure_build。
- **NEVER merge**:PR + CI 绿 + 用户明确「合并」。

## File Structure
- `scripts/eval_quality_baseline.py`(新)、`tests/python/test_eval_quality_baseline.py`(新)、`tests/data/eval_baseline.json`(Task 3 `--update` 生成后提交)。

## 基线 JSON schema(eval_id → metric → {median, threshold};meta 含可比性字段)

```json
{
  "meta": {"model": "deepseek-v4-pro", "updated_at": "2026-07-13T...", "rounds": 3,
           "max_items": null, "tolerance": 0.05,
           "corpus_hash": {"extract": "sha256:...", "tom": "sha256:..."}},
  "evals": {
    "extract": {"holder": {"median": 0.90, "threshold": 0.85}, "holder_perspective": {"median": 0.85, "threshold": 0.80}, "predicate": {"median": 0.80, "threshold": 0.75}, "object": {"median": 0.75, "threshold": 0.70}, "nesting_depth_1": {"median": 0.65, "threshold": 0.60}},
    "tom":     {"accuracy": {"median": 0.65, "threshold": 0.55}}
  }
}
```

---

### Task 1: 纯逻辑 + 基线读写 + 完整性/可比性 + fixture 测试(TDD,零真 LLM)

**Files:** Create `scripts/eval_quality_baseline.py`(先纯逻辑段);Test `tests/python/test_eval_quality_baseline.py`。

**Interfaces (Produces,Task 2 消费):**
- `median(values)->float`、`corpus_hash(records:list[dict])->str`、`EVAL_IDS=("extract","tom")`、`EVAL_THRESHOLDS: dict`、`NETWORK_FLOOR=0.05`
- `diff_against_baseline(current: dict[str, dict[str,float]|None], baseline_evals: dict, tolerance: float) -> list[dict]`(finding:`{eval_id, metric, baseline, current, threshold, verdict}`,verdict∈`OK/REGRESSION/BELOW_THRESHOLD/ERRORED/MISSING`)
- `render_report(findings, meta, current)->str`(near-0 附注读 current)、`has_regression(findings)->bool`、`exit_code(findings)->int`
- `config_mismatch(baseline_meta, cur_model, cur_hashes)->list[str]`
- `save_baseline(path, current, meta)`（**任一配置维 None→raise**）、`load_baseline(path)->dict|None`

- [ ] **Step 1: 写失败测试 `tests/python/test_eval_quality_baseline.py`**

```python
"""质量回归基线 orchestrator 纯逻辑 + collect_scores 接线的 fixture 单测——零真
LLM(diff/容差/阈值/中位数/完整性/可比性/near-0 附注/接线)。真 LLM 手动跑不在此。"""
import json, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import eval_quality_baseline as eqb  # noqa: E402
from eval_quality_baseline import (  # noqa: E402
    median, corpus_hash, diff_against_baseline, render_report, has_regression,
    exit_code, config_mismatch, save_baseline, load_baseline,
    EVAL_IDS, EVAL_THRESHOLDS,
)


def test_median():
    assert median([0.5]) == 0.5
    assert median([0.2, 0.8, 0.5]) == 0.5


def test_eval_ids_and_thresholds():
    assert EVAL_IDS == ("extract", "tom")
    assert EVAL_THRESHOLDS["tom"]["accuracy"] == 0.55
    assert "predicate" in EVAL_THRESHOLDS["extract"]
    assert "recall" not in EVAL_IDS   # recall 是 follow-up


def test_corpus_hash_stable_and_sensitive():
    a = [{"id": 1, "x": "a"}, {"id": 2}]
    assert corpus_hash(a) == corpus_hash(list(a))       # 稳定
    assert corpus_hash(a) != corpus_hash([{"id": 1, "x": "b"}, {"id": 2}])  # 内容变则变


def _baseline():
    return {
        "extract": {"predicate": {"median": 0.80, "threshold": 0.75}},
        "tom": {"accuracy": {"median": 0.65, "threshold": 0.55}},
    }


def test_diff_ok_within_tolerance():
    cur = {"extract": {"predicate": 0.78}, "tom": {"accuracy": 0.63}}
    f = diff_against_baseline(cur, _baseline(), tolerance=0.05)
    assert all(x["verdict"] == "OK" for x in f) and not has_regression(f) and exit_code(f) == 0


def test_diff_relative_regression():
    cur = {"extract": {"predicate": 0.72}, "tom": {"accuracy": 0.65}}  # predicate 降 0.08>0.05
    f = diff_against_baseline(cur, _baseline(), tolerance=0.05)
    r = [x for x in f if x["metric"] == "predicate"][0]
    assert r["verdict"] == "REGRESSION" and has_regression(f) and exit_code(f) == 1


def test_diff_below_threshold():
    cur = {"extract": {"predicate": 0.80}, "tom": {"accuracy": 0.50}}  # tom 破 0.55 地板
    f = diff_against_baseline(cur, _baseline(), tolerance=0.20)
    assert [x for x in f if x["eval_id"] == "tom"][0]["verdict"] == "BELOW_THRESHOLD"
    assert exit_code(f) == 1


def test_diff_errored_dim_is_exit_2_not_regression():
    cur = {"extract": {"predicate": 0.80}, "tom": None}   # tom 采分失败(None)
    f = diff_against_baseline(cur, _baseline(), tolerance=0.05)
    assert [x for x in f if x["eval_id"] == "tom"][0]["verdict"] == "ERRORED"
    assert not has_regression(f) and exit_code(f) == 2


def test_diff_missing_dim_when_baseline_lacks_it():
    # 基线只有 extract(缺 tom)→ tom 报 MISSING(非静默 exit 0)——codex #1
    base = {"extract": {"predicate": {"median": 0.80, "threshold": 0.75}}}
    cur = {"extract": {"predicate": 0.80}, "tom": {"accuracy": 0.65}}
    f = diff_against_baseline(cur, base, tolerance=0.05)
    assert [x for x in f if x["eval_id"] == "tom"][0]["verdict"] == "MISSING"
    assert exit_code(f) == 2


def test_report_near_zero_network_annotation():
    # 某维全指标近 0 → 报告附注疑似网络(但仍 BELOW_THRESHOLD 不隐藏)——codex #4
    cur = {"extract": {"predicate": 0.0}, "tom": {"accuracy": 0.65}}
    f = diff_against_baseline(cur, _baseline(), tolerance=0.05)
    rep = render_report(f, {"model": "m"}, cur)
    assert "BELOW_THRESHOLD" in rep and "疑似网络" in rep


def test_config_mismatch_model_and_hash():
    meta = {"model": "m1", "corpus_hash": {"extract": "h1", "tom": "h2"}}
    assert config_mismatch(meta, "m1", {"extract": "h1", "tom": "h2"}) == []       # 全一致
    assert "model" in " ".join(config_mismatch(meta, "m2", {"extract": "h1", "tom": "h2"}))
    assert "extract" in " ".join(config_mismatch(meta, "m1", {"extract": "hX", "tom": "h2"}))


def test_save_baseline_requires_all_dims(tmp_path):
    # 任一配置维 None → 拒写(raise),保护旧基线——codex #1/#12
    with pytest.raises(ValueError):
        save_baseline(tmp_path / "b.json", {"extract": {"predicate": 0.8}, "tom": None},
                      {"model": "m"})
    assert not (tmp_path / "b.json").exists()


def test_baseline_roundtrip(tmp_path):
    p = tmp_path / "eval_baseline.json"
    cur = {"extract": {"predicate": 0.80}, "tom": {"accuracy": 0.65}}
    save_baseline(p, cur, {"model": "m", "rounds": 3, "max_items": None, "tolerance": 0.05,
                           "corpus_hash": {"extract": "h1", "tom": "h2"}})
    loaded = load_baseline(p)
    assert loaded["evals"]["extract"]["predicate"]["median"] == 0.80
    assert loaded["evals"]["extract"]["predicate"]["threshold"] == EVAL_THRESHOLDS["extract"]["predicate"]
    assert loaded["evals"]["tom"]["accuracy"]["threshold"] == 0.55
    assert load_baseline(tmp_path / "nope.json") is None
```

- [ ] **Step 2: 跑确认失败**

Run: `.venv/bin/python -m pytest tests/python/test_eval_quality_baseline.py -q`
Expected: FAIL(`eval_quality_baseline` 未创建 / 函数未定义)。

- [ ] **Step 3: 写 `scripts/eval_quality_baseline.py` 纯逻辑段**

```python
#!/usr/bin/env python3
"""质量回归基线 orchestrator(dogfood 子项 C)。复用既有 2 维 benchmark harness
(extract F1 / ToM accuracy)的 run_one_round,全量小 corpus 真 LLM 跑 N 轮取中位数,
写/diff 一个 git-committed 基线 JSON,判质量回归。非 CI(真 LLM/Clash 不可靠)。

  python scripts/eval_quality_baseline.py --update   # 有意质量变更后建/更新基线
  python scripts/eval_quality_baseline.py --check     # 改 prompt/extractor 前后查回归
"""
from __future__ import annotations
import argparse, hashlib, json, statistics, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_p1_extractor import P1_THRESHOLDS               # noqa: E402
from eval_tom_bench import ACCURACY_THRESHOLD as TOM_THRESHOLD  # noqa: E402

EVAL_IDS = ("extract", "tom")   # recall(longmemeval)= follow-up
EVAL_THRESHOLDS: dict[str, dict[str, float]] = {
    "extract": dict(P1_THRESHOLDS),
    "tom": {"accuracy": TOM_THRESHOLD},
}
DEFAULT_BASELINE = Path(__file__).resolve().parents[1] / "tests" / "data" / "eval_baseline.json"
NETWORK_FLOOR = 0.05   # 某维全指标 < 此值 = 报告附注疑似网络(不隐藏,仍报 BELOW_THRESHOLD)


def median(values: list[float]) -> float:
    return float(statistics.median(values))


def corpus_hash(records: list[dict]) -> str:
    """corpus 内容确定性 hash(可比性 codex #10):同内容同 hash,内容变则变。"""
    blob = "\n".join(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def diff_against_baseline(current: dict[str, dict[str, float] | None],
                          baseline_evals: dict, tolerance: float) -> list[dict]:
    """遍历**配置维**(EVAL_IDS,非仅基线维——故基线缺维 → MISSING,codex #1)。
    current[eval_id] 为 None = 该维采分失败/不完整 → ERRORED。"""
    findings: list[dict] = []
    for eval_id in EVAL_IDS:
        cur_eval = current.get(eval_id)
        base_eval = baseline_evals.get(eval_id)
        if base_eval is None:
            findings.append({"eval_id": eval_id, "metric": "*", "baseline": None,
                             "current": None, "threshold": None, "verdict": "MISSING"})
            continue
        if cur_eval is None:
            findings.append({"eval_id": eval_id, "metric": "*", "baseline": None,
                             "current": None, "threshold": None, "verdict": "ERRORED"})
            continue
        for metric, spec in base_eval.items():
            base, thr = spec["median"], spec["threshold"]
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
    return any(f["verdict"] in ("REGRESSION", "BELOW_THRESHOLD") for f in findings)


def exit_code(findings: list[dict]) -> int:
    if has_regression(findings):
        return 1
    if any(f["verdict"] in ("ERRORED", "INCOMPLETE", "MISSING") for f in findings):
        return 2
    return 0


def _dim_all_near_zero(current: dict, eval_id: str) -> bool:
    ce = current.get(eval_id)
    return bool(ce) and all(v < NETWORK_FLOOR for v in ce.values())


def render_report(findings: list[dict], meta: dict, current: dict) -> str:
    mark = {"OK": "✅ OK", "REGRESSION": "⚠ REGRESSION", "BELOW_THRESHOLD": "✗ BELOW_THRESHOLD",
            "ERRORED": "⁇ ERRORED", "INCOMPLETE": "⁇ INCOMPLETE", "MISSING": "· MISSING"}
    lines = ["# 质量回归基线报告",
             f"model={meta.get('model')} rounds={meta.get('rounds')} max_items={meta.get('max_items')}",
             "", "| eval | metric | baseline | current | threshold | verdict |",
             "|---|---|---|---|---|---|"]
    for f in findings:
        b = "—" if f["baseline"] is None else f"{f['baseline']:.3f}"
        c = "—" if f["current"] is None else f"{f['current']:.3f}"
        t = "—" if f["threshold"] is None else f"{f['threshold']:.2f}"
        lines.append(f"| {f['eval_id']} | {f['metric']} | {b} | {c} | {t} | {mark.get(f['verdict'], f['verdict'])} |")
    # near-0 附注:诚实报不隐藏(codex #4)——0 分仍 BELOW_THRESHOLD,只提示可能是网络。
    for eval_id in EVAL_IDS:
        if _dim_all_near_zero(current, eval_id):
            lines.append(f"\n> ⚠ `{eval_id}` 全指标近 0 —— 疑似网络黑洞(Clash),查 stderr 的 "
                         f"transport WARN;非质量则换时刻重跑(见 clash-tun 记忆)。仍按 BELOW_THRESHOLD 计。")
    verdict = ("✗ 有质量回归" if has_regression(findings)
               else ("⁇ 有维度不可测/缺失,需重跑或重建" if exit_code(findings) == 2 else "✅ 无回归"))
    lines += ["", f"**总判定:{verdict}**"]
    return "\n".join(lines) + "\n"


def config_mismatch(baseline_meta: dict, cur_model: str, cur_hashes: dict[str, str]) -> list[str]:
    """基线 vs 当前配置不可比项(codex #10):model 或某维 corpus 内容变 → 不可 diff。"""
    out = []
    if baseline_meta.get("model") != cur_model:
        out.append(f"model: baseline={baseline_meta.get('model')} current={cur_model}")
    base_h = baseline_meta.get("corpus_hash", {})
    for eval_id in EVAL_IDS:
        if base_h.get(eval_id) != cur_hashes.get(eval_id):
            out.append(f"corpus[{eval_id}]: 内容变(hash 不匹配)")
    return out


def save_baseline(path: Path, current: dict[str, dict[str, float] | None], meta: dict) -> None:
    """写基线。**要求所有配置维都成功采分**(codex #1/#12)——任一 None → raise,不写、保旧基线。"""
    missing = [e for e in EVAL_IDS if current.get(e) is None]
    if missing:
        raise ValueError(f"拒绝写基线:以下配置维采分失败 {missing};保留旧基线,先重跑")
    evals = {
        eval_id: {m: {"median": v, "threshold": EVAL_THRESHOLDS[eval_id][m]}
                  for m, v in current[eval_id].items()}
        for eval_id in EVAL_IDS
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"meta": meta, "evals": evals}, indent=2, ensure_ascii=False) + "\n")


def load_baseline(path: Path) -> dict | None:
    return json.loads(Path(path).read_text()) if Path(path).exists() else None
```

- [ ] **Step 4: 跑确认通过**

Run: `.venv/bin/python -m pytest tests/python/test_eval_quality_baseline.py -q`
Expected: PASS(纯逻辑 12 测试;collect_scores 接线测试 Task 2 加)。

- [ ] **Step 5: 提交**

```bash
git add scripts/eval_quality_baseline.py tests/python/test_eval_quality_baseline.py
git commit -m "$(cat <<'EOF'
feat(eval): quality regression baseline — pure logic (2-dim, integrity + comparability)

纯逻辑段:median / corpus_hash(可比性)/ diff_against_baseline(遍历配置维→
基线缺维报 MISSING 非静默;ERRORED/INCOMPLETE)/ render_report(near-0 诚实附注
不隐藏)/ config_mismatch(model+corpus hash)/ save_baseline(任一维 None 拒写保旧
基线)/ exit_code 0/1/2。范围 2 维 extract+tom,recall=follow-up。fixture 零真 LLM。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: collect_scores(2 适配器,真 LLM)+ CLI + 接线测试

**Files:** Modify `scripts/eval_quality_baseline.py`(加 collect_scores + 适配器 + main);Test `tests/python/test_eval_quality_baseline.py`(加接线测试)。

**Interfaces:**
- Consumes: Task 1 全部;既有 `eval_p1_extractor.run_one_round(corpus, base_url, api_key, model)->dict[field,float]`、`eval_tom_bench.run_one_round(corpus, *, fixture_mode, base_url, api_key, model, abilities)->float` + `FIRST_ORDER_ABILITIES`。
- Produces: `_score_dim(rounds, min_ok, call)->dict[str,float]|None`;`load_corpora(max_items)->dict[eval_id,(records,hash)]`;`collect_scores(corpora, rounds, min_ok, model, base_url, api_key)->dict[eval_id, dict|None]`;`main(argv)->int`。

- [ ] **Step 1: 写失败测试(collect_scores 接线 + _score_dim 聚合/韧性,注入 mock,零真 LLM)——codex #11**

加到 `tests/python/test_eval_quality_baseline.py`:

```python
def test_score_dim_medians_over_rounds():
    outs = iter([{"predicate": 0.70}, {"predicate": 0.80}, {"predicate": 0.90}])
    got = eqb._score_dim(rounds=3, min_ok=2, call=lambda: next(outs))
    assert got == {"predicate": 0.80}


def test_score_dim_incomplete_when_too_few_ok():
    # 3 轮里 2 轮抛(仅 1 成功)< min_ok=2 → None(INCOMPLETE,不从 1 样本判定)codex #6
    seq = iter([{"predicate": 0.80}, RuntimeError("x"), RuntimeError("y")])
    def maybe():
        v = next(seq)
        if isinstance(v, Exception): raise v
        return v
    assert eqb._score_dim(rounds=3, min_ok=2, call=maybe) is None


def test_score_dim_uses_good_rounds_when_min_met():
    seq = iter([{"predicate": 0.80}, RuntimeError("x"), {"predicate": 0.60}])
    def maybe():
        v = next(seq)
        if isinstance(v, Exception): raise v
        return v
    assert eqb._score_dim(rounds=3, min_ok=2, call=maybe) == {"predicate": 0.70}


def test_collect_scores_wires_both_dims(monkeypatch):
    # codex #11:monkeypatch 2 个真 run_one_round,验 collect_scores 用正确签名调 +
    # 组装 extract(dict)/tom(float→{"accuracy":...})两维,零真 LLM。
    seen = {}
    def fake_extract(corpus, base_url, api_key, model):
        seen["extract"] = (len(corpus), base_url, api_key, model)
        return {"predicate": 0.80, "object": 0.70}
    def fake_tom(corpus, *, fixture_mode, base_url, api_key, model, abilities):
        seen["tom"] = (len(corpus), fixture_mode, model)
        return 0.66
    monkeypatch.setattr(eqb.eval_p1_extractor, "run_one_round", fake_extract)
    monkeypatch.setattr(eqb.eval_tom_bench, "run_one_round", fake_tom)
    corpora = {"extract": ([{"a": 1}], "he"), "tom": ([{"b": 2}], "ht")}
    cur = eqb.collect_scores(corpora, rounds=1, min_ok=1, model="M",
                             base_url="U", api_key="K")
    assert cur["extract"] == {"predicate": 0.80, "object": 0.70}
    assert cur["tom"] == {"accuracy": 0.66}
    assert seen["extract"][1:] == ("U", "K", "M")     # 签名传对
    assert seen["tom"][2] == "M" and seen["tom"][1] is False   # fixture_mode=False
```

- [ ] **Step 2: 跑确认失败**

Run: `.venv/bin/python -m pytest tests/python/test_eval_quality_baseline.py -q`
Expected: FAIL(`_score_dim`/`collect_scores` 未定义)。

- [ ] **Step 3: 实现 collect_scores + 适配器 + main(追加到 `scripts/eval_quality_baseline.py`)**

```python
import os, time

import eval_p1_extractor
import eval_tom_bench

_CORPUS_PATH = {
    "extract": Path(__file__).resolve().parents[1] / "tests/data/eval_p1_corpus.jsonl",
    "tom":     Path(__file__).resolve().parents[1] / "tests/data/eval_tom_bench/first_order.jsonl",
}


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def load_corpora(max_items: int | None) -> dict[str, tuple[list[dict], str]]:
    """全量小 corpus(codex #3:不 first-N 偏样本);--max-items 若给则截前 N(记 hash 供可比)。"""
    out = {}
    for eval_id, path in _CORPUS_PATH.items():
        recs = _load_jsonl(path)
        if max_items is not None:
            recs = recs[:max_items]
        out[eval_id] = (recs, corpus_hash(recs))
    return out


def _score_dim(rounds: int, min_ok: int, call) -> dict[str, float] | None:
    """跑零参 thunk `call`(返回 dict[metric,float])rounds 次;成功轮 < min_ok → None
    (INCOMPLETE,codex #6);否则每 metric 取中位数。call 抛=该轮失败(跳过)。"""
    per_metric: dict[str, list[float]] = {}
    ok = 0
    for r in range(rounds):
        try:
            out = call()
        except Exception as exc:  # noqa: BLE001 — 该轮失败,跳过
            print(f"    round {r+1}/{rounds} ERRORED: {exc}", file=sys.stderr)
            continue
        ok += 1
        for k, v in out.items():
            per_metric.setdefault(k, []).append(float(v))
    if ok < min_ok:
        print(f"    只有 {ok}/{rounds} 成功轮 < min_ok={min_ok} → INCOMPLETE", file=sys.stderr)
        return None
    return {k: median(vs) for k, vs in per_metric.items()}


def collect_scores(corpora: dict[str, tuple[list[dict], str]], rounds: int, min_ok: int,
                   model: str, base_url: str, api_key: str) -> dict[str, dict[str, float] | None]:
    """真 LLM 段:2 维各自适配器调 run_one_round。注:harness 内部吞 per-record 网络异常
    当答错(→低分不抛),故网络崩表现为低分非异常——不在此隐藏,交给 diff/report 诚实报
    (codex #4/#5)。某维彻底崩(全轮抛)→ None。"""
    extract_recs = corpora["extract"][0]
    tom_recs = corpora["tom"][0]
    current: dict[str, dict[str, float] | None] = {}
    current["extract"] = _score_dim(rounds, min_ok,
        call=lambda: eval_p1_extractor.run_one_round(extract_recs, base_url, api_key, model))
    current["tom"] = _tom_wrap(_score_dim(rounds, min_ok,
        call=lambda: {"accuracy": eval_tom_bench.run_one_round(
            tom_recs, fixture_mode=False, base_url=base_url, api_key=api_key,
            model=model, abilities=eval_tom_bench.FIRST_ORDER_ABILITIES)}))
    return current


def _tom_wrap(scores):   # _score_dim 已把 float 包成 {"accuracy":...};透传 None
    return scores


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="质量回归基线 orchestrator(非 CI,真 LLM)")
    m = p.add_mutually_exclusive_group()
    m.add_argument("--check", action="store_true", help="重跑 diff 判回归(默认)")
    m.add_argument("--update", action="store_true", help="跑一遍覆写基线(有意质量变更后)")
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--min-ok", type=int, default=2)
    p.add_argument("--tolerance", type=float, default=0.05)
    p.add_argument("--max-items", type=int, default=None, help="每维截前 N(默认全量)")
    p.add_argument("--model", default="deepseek-v4-pro")
    p.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    p.add_argument("--report", type=Path, default=None)
    args = p.parse_args(argv)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set(不打印 key)", file=sys.stderr)
        return 2

    corpora = load_corpora(args.max_items)
    cur_hashes = {e: corpora[e][1] for e in EVAL_IDS}
    print(f"跑 {len(EVAL_IDS)} 维(rounds={args.rounds} min_ok={args.min_ok} "
          f"max_items={args.max_items} model={args.model})...", file=sys.stderr)
    current = collect_scores(corpora, args.rounds, args.min_ok, args.model, base_url, api_key)
    meta = {"model": args.model,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rounds": args.rounds, "max_items": args.max_items, "tolerance": args.tolerance,
            "corpus_hash": cur_hashes}

    if args.update:
        try:
            save_baseline(args.baseline, current, meta)
        except ValueError as exc:  # 任一维 None → 拒写保旧基线(codex #1/#12)
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"基线已写 {args.baseline}", file=sys.stderr)
        return 0

    baseline = load_baseline(args.baseline)
    if baseline is None:
        print(f"ERROR: 基线不存在 {args.baseline} —— 先 --update 建基线", file=sys.stderr)
        return 2
    mism = config_mismatch(baseline["meta"], args.model, cur_hashes)
    if mism:  # 配置不可比 → 拒 diff(codex #10)
        print("ERROR: 配置与基线不可比,先 --update 重建基线:\n  " + "\n  ".join(mism), file=sys.stderr)
        return 2
    findings = diff_against_baseline(current, baseline["evals"], args.tolerance)
    report = render_report(findings, meta, current)
    print(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report)
    return exit_code(findings)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试 + import 冒烟**

```bash
.venv/bin/python -m pytest tests/python/test_eval_quality_baseline.py -q
.venv/bin/python scripts/eval_quality_baseline.py --check 2>&1 | tail -2   # 无 key → return 2 提示,不崩
```
Expected: pytest 全绿(16 测试);无 key 时 `--check` 打印 ERROR + return 2(无 traceback)。

- [ ] **Step 5: 全量 pytest**

Run: `.venv/bin/python -m pytest tests/python -q`
Expected: 全绿(新增测试;既有 eval harness 自测不受影响——只 import 其 run_one_round/常量,未改)。

- [ ] **Step 6: 提交**

```bash
git add scripts/eval_quality_baseline.py tests/python/test_eval_quality_baseline.py
git commit -m "$(cat <<'EOF'
feat(eval): quality baseline collect_scores (2 adapters) + CLI + wiring test

collect_scores import extract/tom 的 run_one_round(全量 corpus);_score_dim N 轮
中位数 + min_ok 成功轮门(codex #6);无 _flag_network(网络崩表现为低分,交 diff/
report 诚实报 codex #4/#5)。CLI --check 加 config_mismatch 拒不可比(codex #10)、
--update 任一维 None 拒写保旧基线(codex #1/#12)。collect_scores 接线 monkeypatch
测试验 2 签名(codex #11)。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: 真机手动验证(非 CI 门,controller 执行)

**Files:** `tests/data/eval_baseline.json`(`--update` 生成后提交)。

- [ ] **Step 1: 确认 env + 建首个基线**

```bash
export PATH="$PWD/.venv/bin:$PATH"
.venv/bin/python -c "import os;print('OPENAI_API_KEY set:', bool(os.environ.get('OPENAI_API_KEY')),' BASE set:', bool(os.environ.get('OPENAI_BASE_URL')))"
.venv/bin/python scripts/eval_quality_baseline.py --update 2>&1 | tail -15
```
Expected: extract+tom 都成功 → 写 `tests/data/eval_baseline.json`(记两维中位数 + corpus hash + model)。若某维近 0(疑似 Clash)→ save 拒写(全维要求),换时刻重跑。

- [ ] **Step 2: `--check` 证同基线 diff=0**

```bash
.venv/bin/python scripts/eval_quality_baseline.py --check 2>&1 | tail -20; echo "exit=$?"
```
Expected: 两维 `✅ OK`(噪声在容差内),exit=0。若报 REGRESSION 而非网络,记录实测轮间波动定容差。

- [ ] **Step 3:(可选)证抓回归 + 证配置守卫**

`--check --model other-model` → 应报「配置不可比」exit=2(证 #10 守卫);把 belief_prompt 改劣一版 `--check` → 应报 REGRESSION exit=1(证 diff 真抓质量退化);复原。

- [ ] **Step 4: 提交基线 + 结果进 PR body**

```bash
git add tests/data/eval_baseline.json
git commit -m "$(cat <<'EOF'
chore(eval): commit first quality baseline (extract + tom, real LLM)

首个 2 维质量回归基线:extract per-field F1 + tom accuracy,rounds=3 全量 corpus。
真机 --update 生成。

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```
真机结果(两维中位数、实测轮间波动 vs 容差、回归/配置守卫验证)进 PR body;Clash 黑洞([[clash-tun-owns-all-network-flakiness]])则换时刻重跑。

## Self-Review

**1. Spec coverage:** ①两模式→Task2 main✓;②2 维全量 corpus 复用 run_one_round→collect_scores/load_corpora✓;③基线 schema(+corpus_hash)→save/load✓;④回归判据+完整性(#1/#12)+可比性(#10)+退出码→diff/save/config_mismatch/exit_code✓;⑤N 轮中位数+min_ok(#6)+诚实报不隐藏(#4/#5)→_score_dim/render near-0 附注✓;Testing(fixture 纯逻辑+接线,真 LLM 手动)→Task1+2 测试+Task3✓;Out of scope(recall follow-up 等)未纳入✓。

**2. Placeholder scan:** 无 TBD/TODO;每步完整代码/命令。`_tom_wrap` 是透传 helper(_score_dim 已把 tom 的 float 在 call thunk 里包成 `{"accuracy":...}`),非占位。

**3. Type consistency:** `collect_scores→dict[eval_id, dict|None]`(Task2)喂 `diff_against_baseline`/`save_baseline`(Task1);`load_corpora→dict[eval_id,(records,hash)]` 喂 collect_scores + cur_hashes;`_score_dim(rounds,min_ok,call)` 零参 thunk;`config_mismatch(meta,model,hashes)` 与 main 调用一致;EVAL_IDS/EVAL_THRESHOLDS key(extract 5 field / tom accuracy)贯通 diff/save/collect。✓

**下一步:** plan-eng-review 加固已折进(codex 12 findings)→ subagent-driven-development。

## Failure modes(每条:有无测试/有无处理/可见性)

| 场景 | 测试 | 处理 | 可见 |
|---|---|---|---|
| 某维彻底崩(全轮抛) | `test_diff_errored_dim_is_exit_2` | `_score_dim`→None → diff ERRORED → exit 2(不崩) | 报告 ERRORED,非静默 |
| 网络黑洞(harness 吞成低分) | `test_report_near_zero_network_annotation` | 照实报 BELOW_THRESHOLD(exit 1)+ near-0 附注「疑似网络」 | 报告 + stderr WARN,人判 |
| 部分轮失败(<min_ok) | `test_score_dim_incomplete_when_too_few_ok` | INCOMPLETE→None → exit 2 | 报告 + stderr,非 1 样本误判 |
| 基线漏配置维 | `test_diff_missing_dim_when_baseline_lacks_it` | MISSING verdict → exit 2 | 报告 MISSING,非静默 exit 0 |
| --update 某维采分失败 | `test_save_baseline_requires_all_dims` | 拒写、保旧基线、exit 2 | ERROR 提示,旧基线不损 |
| 配置(model/corpus)变 | `test_config_mismatch_model_and_hash` | --check 拒 diff、exit 2、提示重建 | ERROR 提示,不误 diff |
| 无 OPENAI_API_KEY | (手动) | 打印 ERROR(不含 key)+ exit 2 | 非 traceback |

**无 critical gap**(无「既无测试又无处理又静默」路径)。

## Worktree parallelization
**Sequential,无并行。** Task 2 消费 Task 1 的纯逻辑;Task 3 消费 Task 2;同一 script 文件,无独立 lane。

## Implementation Tasks
codex 12 findings 全裁定折进:**拿掉 recall** 消除 #2/#7/#8/#9;**折进** #1/#3/#4/#5/#6/#10/#11/#12(全量 corpus / 诚实报不隐藏 / min-ok / 基线完整性 / 可比性 / 接线测试)。无独立新 task——Task 1→3 顺序执行含全部加固。**follow-up**:修 longmemeval real-mode(512→32768 / env 安全 / per-subset)后加 recall 第 3 维;extract corpus 分层(若发现 first-N 偏)。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 12 findings, all adjudicated(recall 拿掉消 4 条 + 8 条折进重写) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean(post-rework) | 3 self-findings(全 ⊆ codex);scope 收窄 3 维→2 维 |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | —(纯脚本,无 UI) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **CODEX:** 12 findings,几条 serious 是我漏的——#1/#12 基线静默漏维、#2 recall overall 塌验收、#3 子集漏 ability、#6 部分轮当完整、#7 longmemeval 512-token 崩 reasoning、#8 env 不安全、#10 无配置可比性。裁定:**拿掉 recall**(消 #2/#7/#8/#9);**折进重写** #1/#3/#4/#5/#6/#10/#11/#12(全量 corpus、诚实报不隐藏、min-ok、基线完整性守卫、config 可比性、collect_scores 接线测试)。
- **CROSS-MODEL:** 无 tension。codex 扩展并加深了 3 条 self-finding(#4/#5=_flag_network、#9=CHAT_MODEL[recall 拿掉后 moot]、#11=接线测试),无反对。
- **VERDICT:** ENG CLEARED(post-rework)——计划从不健全 3 维重写为健全 2 维(extract+ToM);recall 作 follow-up。subagent-driven next。

NO UNRESOLVED DECISIONS
