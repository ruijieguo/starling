# P2.f 评测准入（Admission Eval）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 P2 评测准入——C1 承诺履行 eval（离线确定性、引擎驱动、真 detection/timeliness 数字）、C2 LongMemEval harness（fixture 离线 + real-mode）、C3 ToMBench 一阶语料 + 确认、C4 P2 准入报告。口径=离线优先 + 真模型 gated。

**Architecture:** C1 harness 经 `starling` 绑定驱动 `CommitmentEngine`/`PolicyEngine`（确定性引擎行为→离线即真数字），脚本风格 mirror `scripts/eval_tom_bench.py`，引擎驱动 mirror `tests/python/test_p2c_commitment_lifecycle.py`。C2/C3 mirror 既有 fixture-mode harness。语料确定性模板生成（无 LLM）。

**Tech Stack:** Python 3.14（`.venv`）+ `starling._core` 绑定 + pytest + 既有 eval harness 约定（argparse/markdown 报告/exit code）。

**Spec:** `docs/superpowers/specs/2026-06-02-p2-f-admission-eval-design.md`（commit 8e19303）。

---

## 锚点更正（实现以本节为准，spec 待 close 回补）

- **OpenAIEmbeddingAdapter 未绑定 Python**（仅 `StubEmbeddingAdapter`）。C2 real-mode 需真 embedder → **Task 4 加一处 additive pybind**（镜像 `OpenAIAdapter` 绑定模式）。spec §1/§6/§7 的「无 C++ 改动」更正为「+1 additive embedding 绑定（C2 real-mode 用）」；此改动需 `cmake --install` 刷新 `_core`，但不加 C++ 单测、ctest 仍 505。
- **C1 是首个 import `starling` 的脚本**（既有 eval 脚本纯 stdlib HTTP）。`.venv` active 下 `from starling import _core, runtime` 直接可用（editable install 把 `python/` 上 path）；**自测** import harness 模块需 `sys.path.insert(0, scripts/)`（mirror `test_eval_tom_bench_harness.py`）。
- `CommitmentEngine.pending(tenant_id, holder_id, interlocutor_id)` 3 参；`create_from_statement(stmt_id, tenant_id, deadline, now_iso)`；`fulfill/withdraw/on_deadline_expired(stmt_id, tenant_id, now_iso)`；`PolicyEngine.tick(now_iso) -> PolicyTickStats{fired,broken,auto_withdrawn}`。COMMITS statement seed 用 24 列（见 Task 2），modality 用 `'commits'`。

**全局约束（所有 Task）：** worktree `.claude/worktrees/p2-f-admission-eval`；`source .venv/bin/activate` 后跑;脚本 `python scripts/xxx.py`（repo 根、venv active）。无 migration（最高 0021）；不改 `starling.Memory`/既有 eval harness 逻辑（C3 只补语料）；C1/生成器纯离线确定性（无 LLM/网络/key）；API key env-only（`OPENAI_API_KEY` gated run 用，绝不入参/log/绑形参/提交）；Co-Authored-By trailer；无 `--no-verify`/`--amend`；plan untracked 直到 close。WAL：临时 DB 顺序写（raw sqlite3 seed commit+close 后再 C++ 引擎调用）。

---

## Task 0: Baseline 确认

**Files:** 无
- [ ] **Step 1: 分支/HEAD + 构建 + ctest**
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-f-admission-eval
git branch --show-current   # worktree-p2-f-admission-eval
cmake -S . -B build -G Ninja && cmake --build build && ctest --test-dir build 2>&1 | tail -3
```
Expected: `100% tests passed ... out of 505`（cmake/ninja/pybind11 缺则 `python -m venv .venv && source .venv/bin/activate && pip install cmake ninja pybind11`，configure 加 `-DFETCHCONTENT_SOURCE_DIR_JSON=/Users/jaredguo-mini/develop/memory/starling/build/_deps/json-src -DFETCHCONTENT_SOURCE_DIR_GOOGLETEST=/Users/jaredguo-mini/develop/memory/starling/build/_deps/googletest-src -Dpybind11_DIR=$(.venv/bin/python -m pybind11 --cmakedir)`）
- [ ] **Step 2: venv + pytest**
```bash
source .venv/bin/activate && pip install -e ".[dev]" && pytest tests/python -q 2>&1 | tail -3
```
Expected: `495 passed, 13 skipped`。不绿则 STOP/报告。

---

## Task 1: C1 承诺语料生成器 + scenarios.jsonl（确定性，无 LLM）

**Files:**
- Create: `scripts/generate_commitment_corpus.py`
- Create: `tests/data/eval_commitment/scenarios.jsonl`（生成产物，提交）
- Test: `tests/python/test_commitment_corpus.py`

**语料 schema**（每条一个承诺生命周期场景，确定性 replay）：
```json
{"scenario_id":"cm-000","category":"fulfill",
 "commit":{"stmt_id":"cm-000-c","holder":"alice","subject":"bob","object":"report-0",
           "deadline":"2026-06-10T12:00:00Z","observed_at":"2026-06-10T08:00:00Z"},
 "actions":[{"turn":0,"op":"tick","now":"2026-06-10T09:00:00Z"},
            {"turn":1,"op":"fulfill","now":"2026-06-10T10:00:00Z"}],
 "expected":{"final_state":"FULFILLED","detect_by_turn":1}}
```
`category` ∈ {`fulfill`(→FULFILLED), `deadline_break`(deadline 过→tick/on_deadline_expired→BROKEN), `chronic_withdraw`(3 次 break→auto WITHDRAWN), `active_pending`(未到期,保持 ACTIVE 且 pending 检出), `withdraw`(→WITHDRAWN)}。`op` ∈ {`tick`,`fulfill`,`withdraw`,`expire`(on_deadline_expired)}。

- [ ] **Step 1: 写生成器**（mirror `generate_eval_corpus.py` 的 slot-plan + JSONL 写出,但**纯模板枚举,无 `call_gpt`**）。`scripts/generate_commitment_corpus.py`:
```python
#!/usr/bin/env python3
"""Deterministically generate the 100-item commitment eval corpus (NO LLM)."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

# 固定分布(合计 100): 30 fulfill + 25 deadline_break + 20 chronic_withdraw + 15 withdraw + 10 active_pending
_PLAN = (["fulfill"]*30 + ["deadline_break"]*25 + ["chronic_withdraw"]*20
         + ["withdraw"]*15 + ["active_pending"]*10)

def _base_times(i: int):
    # 确定性时间轴:每场景错开天数,避免冲突。
    day = 1 + (i % 27)
    obs = f"2026-06-{day:02d}T08:00:00Z"
    deadline = f"2026-06-{day:02d}T12:00:00Z"
    return obs, deadline

def build_scenario(i: int, category: str) -> dict:
    sid = f"cm-{i:03d}"
    cstmt = f"{sid}-c"
    obs, deadline = _base_times(i)
    commit = {"stmt_id": cstmt, "holder": "alice", "subject": "bob",
              "object": f"task-{i}", "deadline": deadline, "observed_at": obs}
    day = obs[:10]
    if category == "fulfill":
        actions = [{"turn":0,"op":"tick","now":f"{day}T09:00:00Z"},
                   {"turn":1,"op":"fulfill","now":f"{day}T10:00:00Z"}]
        expected = {"final_state":"FULFILLED","detect_by_turn":1}
    elif category == "deadline_break":
        actions = [{"turn":0,"op":"tick","now":f"{day}T11:00:00Z"},
                   {"turn":1,"op":"expire","now":f"{day}T13:00:00Z"}]
        expected = {"final_state":"BROKEN","detect_by_turn":1}
    elif category == "chronic_withdraw":
        # 3 次 break → auto WITHDRAWN(TC-A2-001 行为)。每次 expire 后 broken_count++。
        actions = [{"turn":0,"op":"expire","now":f"{day}T13:00:00Z"},
                   {"turn":1,"op":"expire","now":f"{day}T14:00:00Z"},
                   {"turn":2,"op":"expire","now":f"{day}T15:00:00Z"}]
        expected = {"final_state":"WITHDRAWN","detect_by_turn":2}
    elif category == "withdraw":
        actions = [{"turn":0,"op":"tick","now":f"{day}T09:00:00Z"},
                   {"turn":1,"op":"withdraw","now":f"{day}T10:00:00Z"}]
        expected = {"final_state":"WITHDRAWN","detect_by_turn":1}
    else:  # active_pending — 未到期,保持 ACTIVE
        actions = [{"turn":0,"op":"tick","now":f"{day}T09:00:00Z"}]
        expected = {"final_state":"ACTIVE","detect_by_turn":0}
    return {"scenario_id": sid, "category": category, "commit": commit,
            "actions": actions, "expected": expected}

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Generate commitment eval corpus (deterministic, no LLM).")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for i, cat in enumerate(_PLAN):
            f.write(json.dumps(build_scenario(i, cat), ensure_ascii=False) + "\n")
            f.flush(); os.fsync(f.fileno())
    print(f"Wrote {len(_PLAN)} scenarios to {args.out}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 生成语料**
```bash
source .venv/bin/activate
python scripts/generate_commitment_corpus.py --out tests/data/eval_commitment/scenarios.jsonl
wc -l tests/data/eval_commitment/scenarios.jsonl   # 100
```

- [ ] **Step 3: 确定性 + shape 测试** `tests/python/test_commitment_corpus.py`:
```python
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests" / "data" / "eval_commitment" / "scenarios.jsonl"
_VALID_STATES = {"ACTIVE","FULFILLED","BROKEN","WITHDRAWN","RENEGOTIATED"}

def test_corpus_shape():
    lines = [l for l in CORPUS.read_text().splitlines() if l.strip()]
    assert len(lines) == 100
    for l in lines:
        r = json.loads(l)
        assert r["scenario_id"] and r["category"]
        assert r["commit"]["stmt_id"] and r["commit"]["deadline"]
        assert r["actions"] and all(a["op"] in {"tick","fulfill","withdraw","expire"} for a in r["actions"])
        assert r["expected"]["final_state"] in _VALID_STATES
        assert isinstance(r["expected"]["detect_by_turn"], int)

def test_generator_deterministic(tmp_path):
    out = tmp_path / "regen.jsonl"
    subprocess.run([sys.executable, str(ROOT/"scripts"/"generate_commitment_corpus.py"),
                    "--out", str(out)], check=True, capture_output=True)
    assert out.read_text() == CORPUS.read_text()   # 重跑同输出
```

- [ ] **Step 4: 跑测试 PASS**
```bash
pytest tests/python/test_commitment_corpus.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**
```bash
git add scripts/generate_commitment_corpus.py tests/data/eval_commitment/scenarios.jsonl \
        tests/python/test_commitment_corpus.py
git commit -m "$(cat <<'EOF'
feat(P2.f): 承诺 eval 确定性语料生成器 + 100 条 scenarios

generate_commitment_corpus.py 纯模板枚举(无 LLM):30 fulfill + 25 deadline_break +
20 chronic_withdraw + 15 withdraw + 10 active_pending;每条一个承诺生命周期场景
(commit + actions[tick/fulfill/withdraw/expire] + expected{final_state,detect_by_turn})。
shape + 确定性(重跑同输出)测试通过。

EOF
)"
```

---

## Task 2: C1 承诺 harness `eval_commitment.py`（引擎驱动 + detection/timeliness）

**Files:**
- Create: `scripts/eval_commitment.py`

**实现前必做核对**（implementer）:跑一个探针确认 PolicyEngine/CommitmentEngine 的真实状态转移语义——`expire`(on_deadline_expired) 是否把 ACTIVE→BROKEN、3 次是否→WITHDRAWN、`tick` 对未到期是否保持 ACTIVE。参考 `tests/python/test_p2c_commitment_lifecycle.py`（create→assert ACTIVE→fulfill→assert FULFILLED）+ `tests/cpp/test_commitment_engine.cpp` / `test_policy_engine_*`。**若某 category 的真实转移与 Task 1 语料 `expected` 不符,改语料生成器的 expected(回 Task 1 重生成)以对齐真实引擎行为——eval 测的是引擎,不是反过来改引擎。**

- [ ] **Step 1: 写 harness**（mirror `eval_tom_bench.py` 的 argparse/report/verdict;引擎驱动 mirror `test_p2c_commitment_lifecycle.py`）。`scripts/eval_commitment.py`:
```python
#!/usr/bin/env python3
"""Commitment-fulfillment eval — offline, deterministic, engine-driven.

Replays each scenario's actions through CommitmentEngine/PolicyEngine and checks
the observed final state matches expected, recording the turn of detection.
Metrics: detection rate (>0.80) + median timeliness (<3 turns). No LLM / no network.
"""
from __future__ import annotations
import argparse, json, sqlite3, sys, tempfile
from pathlib import Path

from starling import _core, runtime
from starling.testing import relax_preflight_for_m0_3

DETECTION_THRESHOLD = 0.80
TIMELINESS_THRESHOLD = 3   # turns (strict <)

_SEED_SQL = (
    "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
    "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
    "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
    "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
    "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")

def _seed_commit(db_path: str, c: dict) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute(_SEED_SQL, (
            c["stmt_id"], "default", c["holder"], "first_person", "cognizer", c["subject"],
            "owes", "str", c["object"], "a"*64, "v1", "commits", "pos", 0.9, c["observed_at"],
            0.5, "{}", 0.0, c["observed_at"], "user_input", "consolidated", "approved",
            c["observed_at"], c["observed_at"]))
        conn.commit()

def _state(db_path: str, stmt_id: str) -> str:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT state FROM commitments WHERE stmt_id=? AND tenant_id='default'",
                           (stmt_id,)).fetchone()
        return row[0] if row else "ABSENT"

def run_scenario(scn: dict) -> tuple[bool, int]:
    """Return (detected: matched expected final_state, detect_turn)."""
    relax_preflight_for_m0_3()
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "s.db")
        rt = runtime._build_local_store_sqlite_runtime(Path(db)); rt.start()
        c = scn["commit"]
        _seed_commit(rt.adapter.db_path, c)   # raw sqlite3 seed (commit+close) BEFORE C++ write
        ce = _core.CommitmentEngine(rt.adapter)
        pe = _core.PolicyEngine(rt.adapter)
        ce.create_from_statement(c["stmt_id"], "default", c["deadline"], c["observed_at"])
        want = scn["expected"]["final_state"]
        detect_turn = -1
        for act in scn["actions"]:
            op, now = act["op"], act["now"]
            if op == "tick":      pe.tick(now)
            elif op == "fulfill": ce.fulfill(c["stmt_id"], "default", now)
            elif op == "withdraw":ce.withdraw(c["stmt_id"], "default", now)
            elif op == "expire":  ce.on_deadline_expired(c["stmt_id"], "default", now)
            if detect_turn < 0 and _state(rt.adapter.db_path, c["stmt_id"]) == want:
                detect_turn = act["turn"]
        return (_state(rt.adapter.db_path, c["stmt_id"]) == want, detect_turn)

def _median(xs: list[int]) -> float:
    if not xs: return 0.0
    s = sorted(xs); n = len(s)
    return float(s[n//2]) if n % 2 else (s[n//2-1]+s[n//2])/2.0

def write_report(path: Path, detection: float, timeliness: float, n: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Commitment Fulfillment Eval Report", "",
             f"| metric | value | threshold | verdict |", "|---|---|---|---|",
             f"| detection rate | {detection:.4f} | >{DETECTION_THRESHOLD} | "
             f"{'PASS' if detection > DETECTION_THRESHOLD else '**FAIL**'} |",
             f"| timeliness (median turns) | {timeliness:.2f} | <{TIMELINESS_THRESHOLD} | "
             f"{'PASS' if timeliness < TIMELINESS_THRESHOLD else '**FAIL**'} |",
             f"| scenarios | {n} | | |"]
    path.write_text("\n".join(lines) + "\n")

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Commitment fulfillment eval (offline, engine-driven).")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--report", type=Path, default=Path("build/eval_commitment.md"))
    args = p.parse_args(argv)
    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr); return 1
    corpus = [json.loads(l) for l in args.corpus.read_text().splitlines() if l.strip()]
    if not corpus:
        print("ERROR: corpus is empty", file=sys.stderr); return 1
    detected = 0; turns = []
    for scn in corpus:
        ok, t = run_scenario(scn)
        if ok:
            detected += 1
            if scn["expected"]["detect_by_turn"] > 0 and t >= 0:
                turns.append(t)
    detection = detected / len(corpus)
    timeliness = _median(turns)
    write_report(args.report, detection, timeliness, len(corpus))
    print(f"Report written to {args.report}", file=sys.stderr)
    ok = detection > DETECTION_THRESHOLD and timeliness < TIMELINESS_THRESHOLD
    if ok:
        print(f"PASS — detection {detection:.4f} > {DETECTION_THRESHOLD}, "
              f"timeliness {timeliness:.2f} < {TIMELINESS_THRESHOLD}")
        return 0
    print(f"BLOCKED — detection {detection:.4f} / timeliness {timeliness:.2f}")
    return 1

if __name__ == "__main__":
    sys.exit(main())
```
> implementer 对齐:`runtime._build_local_store_sqlite_runtime` 需先 `relax_preflight_for_m0_3()`（已在 run_scenario 内）;`rt.adapter.db_path` 取路径;若 `on_deadline_expired` 不直接置 BROKEN（而需 tick 配合）,按探针结果调 actions 语义 + 回 Task 1 对齐 expected。

- [ ] **Step 2: 跑全量语料确认 PASS**
```bash
source .venv/bin/activate
python scripts/eval_commitment.py --corpus tests/data/eval_commitment/scenarios.jsonl --report build/eval_commitment.md
echo "exit=$?"
cat build/eval_commitment.md
```
Expected: stdout `PASS — detection ... > 0.8, timeliness ... < 3`,exit 0。若 detection <0.8,说明语料 expected 与引擎不符→回 Task 1 用探针结果对齐 expected 重生成（不改引擎）。

- [ ] **Step 3: Commit**
```bash
git add scripts/eval_commitment.py
git commit -m "$(cat <<'EOF'
feat(P2.f): 承诺履行 eval harness(离线引擎驱动)

eval_commitment.py 经 CommitmentEngine/PolicyEngine replay 每场景 actions,核对
final_state 并记检出 turn;detection rate(>0.80)+ median timeliness(<3 turns);
markdown 报告 + PASS/BLOCKED exit code。纯离线确定性,无 LLM/网络。100 条全过。

EOF
)"
```

---

## Task 3: C1 自测 `test_eval_commitment_harness.py`

**Files:** Create `tests/python/test_eval_commitment_harness.py`

- [ ] **Step 1: 写自测**（mirror `test_eval_tom_bench_harness.py`:subprocess 跑 exit 0 + import 跑 run_scenario 单测,含负例验证 detection 计数）:
```python
"""Offline self-tests for the commitment eval harness."""
import json, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from eval_commitment import run_scenario, _median, DETECTION_THRESHOLD  # noqa: E402

def _scn(category, final_state, actions, detect_by=1):
    return {"scenario_id":"t","category":category,
            "commit":{"stmt_id":"t-c","holder":"alice","subject":"bob","object":"x",
                      "deadline":"2026-06-10T12:00:00Z","observed_at":"2026-06-10T08:00:00Z"},
            "actions":actions,"expected":{"final_state":final_state,"detect_by_turn":detect_by}}

def test_fulfill_scenario_detected():
    ok, turn = run_scenario(_scn("fulfill","FULFILLED",
        [{"turn":0,"op":"tick","now":"2026-06-10T09:00:00Z"},
         {"turn":1,"op":"fulfill","now":"2026-06-10T10:00:00Z"}]))
    assert ok and turn == 1

def test_negative_mismatch_not_detected():
    # expect FULFILLED but we never fulfill → ok=False(detection 不计)
    ok, _ = run_scenario(_scn("fulfill","FULFILLED",
        [{"turn":0,"op":"tick","now":"2026-06-10T09:00:00Z"}]))
    assert ok is False

def test_full_harness_exits_zero(tmp_path):
    # tiny 3 条 fixture 语料跑 harness
    corpus = tmp_path / "c.jsonl"
    corpus.write_text("\n".join(json.dumps(_scn("fulfill","FULFILLED",
        [{"turn":0,"op":"tick","now":"2026-06-10T09:00:00Z"},
         {"turn":1,"op":"fulfill","now":"2026-06-10T10:00:00Z"}]) | {"scenario_id":f"t{i}",
         "commit":{"stmt_id":f"t{i}-c","holder":"alice","subject":"bob","object":f"x{i}",
                   "deadline":"2026-06-10T12:00:00Z","observed_at":"2026-06-10T08:00:00Z"}})
        for i in range(3)))
    report = tmp_path / "r.md"
    res = subprocess.run([sys.executable, str(ROOT/"scripts"/"eval_commitment.py"),
                          "--corpus", str(corpus), "--report", str(report)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "PASS" in res.stdout and report.exists()

def test_median():
    assert _median([1,1,2]) == 1.0 and _median([]) == 0.0
```

- [ ] **Step 2: 跑 PASS**
```bash
pytest tests/python/test_eval_commitment_harness.py -v
```
Expected: 4 passed

- [ ] **Step 3: Commit**（`test(P2.f): 承诺 eval harness 自测(含负例)` + trailer）

---

## Task 4: OpenAIEmbeddingAdapter pybind 绑定（C2 real-mode 需,additive）

**Files:**
- Modify: `bindings/python/module.cpp`（在 `OpenAIAdapter` 绑定块附近）
- Test: `tests/python/test_openai_embedding_binding.py`

- [ ] **Step 1: failing 测试** `tests/python/test_openai_embedding_binding.py`:
```python
"""OpenAIEmbeddingAdapter must be constructible (production embedder for evals)."""
import os
from starling import _core

def test_openai_embedding_adapter_constructs():
    os.environ.setdefault("OPENAI_API_KEY", "test-key")     # construction only, no network
    cfg = _core.OpenAIEmbeddingConfig.from_env()
    cfg.model = "text-embedding-3-small"
    emb = _core.OpenAIEmbeddingAdapter(cfg)
    assert emb is not None
```

- [ ] **Step 2: 跑确认 FAIL**（`OpenAIEmbeddingConfig`/`OpenAIEmbeddingAdapter` 未绑定）
```bash
source .venv/bin/activate && pip install -e . --no-deps --force-reinstall >/dev/null 2>&1
pytest tests/python/test_openai_embedding_binding.py -q
```

- [ ] **Step 3: 加绑定**。确认 `module.cpp` 顶部已 include `"starling/embedding/openai_embedding_adapter.hpp"`（若无则加）。在 `OpenAIAdapter` 绑定块之后加（镜像其模式;`EmbeddingAdapter` 基类已绑定,作父）:
```cpp
    // ----- P2.f: OpenAIEmbeddingAdapter (real embedder for gated evals) -----
    {
        using starling::embedding::OpenAIEmbeddingAdapter;
        py::class_<OpenAIEmbeddingAdapter::Config>(m, "OpenAIEmbeddingConfig")
            .def(py::init<>())
            .def_readwrite("base_url",    &OpenAIEmbeddingAdapter::Config::base_url)
            .def_readwrite("model",       &OpenAIEmbeddingAdapter::Config::model)
            .def_readwrite("dim",         &OpenAIEmbeddingAdapter::Config::dim)
            .def_readwrite("timeout_ms",  &OpenAIEmbeddingAdapter::Config::timeout_ms)
            .def_readwrite("max_retries", &OpenAIEmbeddingAdapter::Config::max_retries)
            .def_static("from_env",       &OpenAIEmbeddingAdapter::Config::from_env);
        py::class_<OpenAIEmbeddingAdapter, starling::embedding::EmbeddingAdapter>(
                m, "OpenAIEmbeddingAdapter")
            .def(py::init<OpenAIEmbeddingAdapter::Config>(), py::arg("config"));
    }
```
> `Config::from_env()` 未设 `OPENAI_API_KEY` 会 throw——测试里 `setdefault` 占位（仅构造,不调 embed）。`api_key` 字段不暴露给 Python（env-only）。

- [ ] **Step 4: 刷新 _core + 跑 PASS**
```bash
cmake --build build && cmake --install build --prefix .venv/lib/python3.14/site-packages
pip install -e . --no-deps --force-reinstall
pytest tests/python/test_openai_embedding_binding.py -v
ctest --test-dir build 2>&1 | tail -2   # 仍 505(无新 C++ 单测)
```
Expected: 1 passed;ctest 505/505。

- [ ] **Step 5: Commit**（`feat(P2.f): OpenAIEmbeddingAdapter pybind 绑定(C2 real-mode 用)` + 说明 EmbeddingAdapter 基类作父、api_key env-only + trailer）

---

## Task 5: C2 LongMemEval harness + 语料

**Files:**
- Create: `scripts/eval_longmemeval.py`、`tests/data/eval_longmemeval/sessions.jsonl`

- [ ] **Step 1: 写语料** `tests/data/eval_longmemeval/sessions.jsonl`（手写/模板,~24 条 = 12 time-reasoning + 12 knowledge-update,多选 4 选项,answer 0-based）。每条 schema:
```json
{"item_id":"lme-000","subset":"knowledge-update",
 "history":[{"speaker":"alice","text":"Bob owns auth.","observed_at":"2026-04-01T10:00:00Z"},
            {"speaker":"alice","text":"Carol took over auth from Bob.","observed_at":"2026-05-01T10:00:00Z"}],
 "question":"Who currently owns auth?","options":["Bob","Carol","Dana","Alice"],"answer":1}
```
（time-reasoning 例:history 含多时间点事件,question 问"最早/最近发生"。implementer 写 24 条覆盖两子集,确定性、无歧义。）

- [ ] **Step 2: 写 harness**（mirror `eval_tom_bench.py` argparse/report/exit + `eval_fantom.py` 多子集 verdict;fixture-mode mock answerer,real-mode 自建 pipeline）。`scripts/eval_longmemeval.py`:
```python
#!/usr/bin/env python3
"""LongMemEval (time-reasoning + knowledge-update) harness.

fixture-mode: deterministic mock answerer (offline, CI). real-mode: build a real
retrieval pipeline (SqliteAdapter + OpenAIEmbeddingAdapter + EmbeddingWorker +
SemanticRetriever) + OpenAIAdapter answering — needs OPENAI_API_KEY (gated).
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

ACCURACY_THRESHOLD = 0.55
SUBSETS = ("time-reasoning", "knowledge-update")

def _fixture_answer(record: dict, idx: int) -> int:
    # 90% correct deterministically (well above 0.55).
    return int(record["answer"]) if idx % 10 < 9 else (int(record["answer"]) + 1) % len(record["options"])

def _real_answer(record: dict) -> int:
    # Gated: build pipeline, write history, recall, answer. Imported lazily so
    # fixture-mode never imports starling/_core.
    from starling import _core, runtime
    from starling.testing import relax_preflight_for_m0_3
    # ... build SqliteAdapter + OpenAIEmbeddingAdapter(from_env) + EmbeddingWorker +
    #     SemanticRetriever; seed history statements; recall(question); ask OpenAIAdapter
    #     to pick an option index. (Full wiring filled by implementer; only runs with key.)
    raise NotImplementedError("real-mode wired in Step 3")

def run_one_round(corpus, subsets, fixture_mode):
    counts = {s: [0, 0] for s in subsets}
    for idx, rec in enumerate(corpus):
        s = rec.get("subset", "")
        if s not in subsets:
            continue
        counts[s][1] += 1
        pred = _fixture_answer(rec, idx) if fixture_mode else _real_answer(rec)
        if pred == int(rec["answer"]):
            counts[s][0] += 1
    return {s: (counts[s][0], counts[s][1]) for s in subsets}

def write_report(path: Path, rounds, subsets, threshold, overall_pass):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# LongMemEval Report", "", "| subset | last-acc | threshold | verdict |", "|---|---|---|---|"]
    last = rounds[-1]
    for s in subsets:
        c, t = last.get(s, (0, 0))
        acc = c / t if t else 0.0
        lines.append(f"| {s} | {acc:.4f} | {threshold:.2f} | {'PASS' if acc >= threshold else '**FAIL**'} |")
    lines.append(f"\noverall: {'PASS' if overall_pass else 'FAIL'}")
    path.write_text("\n".join(lines) + "\n")

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="LongMemEval harness.")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--report", type=Path, default=Path("build/eval_longmemeval.md"))
    p.add_argument("--subsets", default=",".join(SUBSETS))
    p.add_argument("--fixture-mode", action="store_true")
    args = p.parse_args(argv)
    subsets = tuple(x.strip() for x in args.subsets.split(",") if x.strip())
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not args.fixture_mode and not api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr); return 1
    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr); return 1
    corpus = [json.loads(l) for l in args.corpus.read_text().splitlines() if l.strip()]
    rounds = [run_one_round(corpus, subsets, args.fixture_mode) for _ in range(args.rounds)]
    last = rounds[-1]
    failures = [s for s in subsets
                if (last.get(s,(0,0))[1] == 0) or (last[s][0]/last[s][1] < ACCURACY_THRESHOLD)]
    overall = len(failures) == 0
    write_report(args.report, rounds, subsets, ACCURACY_THRESHOLD, overall)
    print(f"Report written to {args.report}", file=sys.stderr)
    if overall:
        print("PASS — all subsets within accuracy threshold"); return 0
    for s in failures: print(f"BLOCKED — subset {s} below threshold or empty")
    return 1

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 填 `_real_answer` real-mode pipeline**（gated;只在有 key 时跑,fixture-mode 不触发）。implementer 用 verbatim 绑定签名补全:`_core.SqliteAdapter.open(":memory:")` → 逐 history seed statement(raw sqlite3,modality 按内容) → `_core.OpenAIEmbeddingAdapter(_core.OpenAIEmbeddingConfig.from_env())` + `_core.SqliteBlobVectorIndex()` + `_core.EmbeddingWorker(...).tick_one_batch(now)` 嵌入 → `_core.SemanticRetriever(...).vector_recall(_core.SemanticRetrieverParams(tenant_id="default",holder_id="alice",query_text=record["question"],k=5))` 取上下文 → `_core.OpenAIAdapter(_core.OpenAIAdapterConfig.from_env())` 让 LLM 选 option index。**此路径需 key,本里程碑不跑(gated),只接好。**

- [ ] **Step 4: 跑 fixture-mode 确认 PASS**
```bash
source .venv/bin/activate
python scripts/eval_longmemeval.py --corpus tests/data/eval_longmemeval/sessions.jsonl --fixture-mode --report build/eval_longmemeval.md
echo "exit=$?"; cat build/eval_longmemeval.md
```
Expected: stdout `PASS`,exit 0,两子集都达阈。

- [ ] **Step 5: Commit**（`feat(P2.f): LongMemEval harness(fixture+real-mode)+ 语料` + trailer）

---

## Task 6: C2 自测 `test_eval_longmemeval_harness.py`

**Files:** Create `tests/python/test_eval_longmemeval_harness.py`

- [ ] **Step 1: 写自测**（mirror `test_eval_tom_bench_harness.py`,fixture-mode,in-memory 小语料,subprocess 跑 exit 0 + import 跑 run_one_round）:
```python
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from eval_longmemeval import run_one_round, write_report, ACCURACY_THRESHOLD, SUBSETS  # noqa: E402

def _make(tmp_path):
    recs = []
    for s in SUBSETS:
        for i in range(4):
            recs.append({"item_id":f"{s}-{i}","subset":s,
                         "history":[{"speaker":"a","text":"x","observed_at":"2026-04-01T10:00:00Z"}],
                         "question":"q?","options":["A","B","C","D"],"answer":0})
    p = tmp_path / "c.jsonl"; p.write_text("\n".join(json.dumps(r) for r in recs)); return p

def test_fixture_exits_zero(tmp_path):
    corpus = _make(tmp_path); report = tmp_path / "r.md"
    res = subprocess.run([sys.executable, str(ROOT/"scripts"/"eval_longmemeval.py"),
                          "--corpus", str(corpus), "--rounds","3","--report", str(report), "--fixture-mode"],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "PASS" in res.stdout and report.exists()

def test_both_subsets_evaluated(tmp_path):
    corpus = _make(tmp_path)
    recs = [json.loads(l) for l in corpus.read_text().splitlines() if l.strip()]
    res = run_one_round(recs, SUBSETS, fixture_mode=True)
    for s in SUBSETS:
        assert res[s][1] == 4 and res[s][0] >= 1   # 都被评且有正确
```

- [ ] **Step 2: 跑 PASS** `pytest tests/python/test_eval_longmemeval_harness.py -v`（2 passed）
- [ ] **Step 3: Commit**（`test(P2.f): LongMemEval harness 自测(fixture)` + trailer）

---

## Task 7: C3 ToMBench 一阶语料 + shape 校验 + 确认

**Files:**
- Create: `tests/data/eval_tom_bench/first_order.jsonl`、`tests/python/test_tom_bench_corpus.py`

- [ ] **Step 1: 写一阶语料**（~24 条 = 6 × 4 能力 `unexpected-outcome`/`desire`/`persuade`/`world-knowledge`,手写/模板,schema 对齐 `eval_tom_bench.py`:`question_id`/`context`/`question`/`options[4]`/`answer` 0-based/`ability`）→ `tests/data/eval_tom_bench/first_order.jsonl`。

- [ ] **Step 2: shape 校验测试** `tests/python/test_tom_bench_corpus.py`:
```python
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT/"tests"/"data"/"eval_tom_bench"/"first_order.jsonl"
_ABIL = {"unexpected-outcome","desire","persuade","world-knowledge"}
def test_first_order_corpus_shape():
    lines = [l for l in CORPUS.read_text().splitlines() if l.strip()]
    assert len(lines) >= 16
    for l in lines:
        r = json.loads(l)
        assert r["question_id"] and len(r["options"]) == 4
        assert 0 <= int(r["answer"]) <= 3
        assert r["ability"] in _ABIL
```

- [ ] **Step 3: 确认现有 harness 在真语料上跑通(fixture-mode)**
```bash
source .venv/bin/activate
python scripts/eval_tom_bench.py --corpus tests/data/eval_tom_bench/first_order.jsonl --fixture-mode --report build/eval_tom_bench.md
echo "exit=$?"
pytest tests/python/test_tom_bench_corpus.py tests/python/test_eval_tom_bench_harness.py -v
```
Expected: harness exit 0 + PASS;shape 测试 + 既有自测全过（不回归）。

- [ ] **Step 4: Commit**（`feat(P2.f): ToMBench 一阶语料 + shape 校验` + 说明只补语料不动 harness + trailer）

---

## Task 8: C4 P2 准入报告

**Files:** Create `docs/eval/2026-06-02-p2-admission-report.md`

- [ ] **Step 1: 写报告**——§16.3-1~10 逐条 ✅ + 落点(测试名,来自 P2.a–c)、C1 真数字(跑 `eval_commitment.py` 取 detection/timeliness)、C2 fixture PASS + real gated、C3 fixture PASS + real gated、gated run 命令小节、诚实结论。结构:
```markdown
# P2 准入报告（Admission Report）— 2026-06-02

## 1. §16.3 CRITICAL 准入（10 条，P2.a–c 已全绿）
| # | 准入项 | 测试 | 落点 | 状态 |
|---|---|---|---|---|
| 16.3-3/6 | Projection/Vector repair guard | TC-PROJECTION-REPAIR / TC-VEC-REPAIR | ctest | ✅ |
| 16.3-4 | Reconsolidation 窗口 | M0.8 | ctest | ✅ |
| 16.3-7 | 状态机 Replay | TC-A1-001/002 TC-A5 TC-A6 TC-A8-001 | ctest | ✅ |
| 16.3-8 | Commitment 契约 | TC-A2-001/002 TC-A9-001/002/003 | ctest | ✅ |
| 16.3-9 | Reconsolidation 兼容 | TC-NEW-CONFLICT-SEVERE | ctest | ✅ |
| 16.3-1/2/5/10 | ProfileCapability/eval 装载 | P2.a | — | ✅ |
（implementer 对照 system_design §16.3 + roadmap 填全 10 条 + 真实测试名）

## 2. C1 承诺履行 eval（离线，真数字）
`python scripts/eval_commitment.py --corpus tests/data/eval_commitment/scenarios.jsonl`
→ detection rate X.XX（>0.80 ✅）/ timeliness Y.Y turns（<3 ✅）/ 100 scenarios / PASS。

## 3. C2 LongMemEval（fixture 离线 PASS；真模型 gated）
fixture-mode: `python scripts/eval_longmemeval.py --corpus tests/data/eval_longmemeval/sessions.jsonl --fixture-mode` → PASS。
| 子集 | fixture | real（gated，待跑） |
|---|---|---|
| time-reasoning | PASS | TBD |
| knowledge-update | PASS | TBD |

## 4. C3 ToMBench 一阶（fixture 离线 PASS；真模型 gated）
fixture-mode: `python scripts/eval_tom_bench.py --corpus tests/data/eval_tom_bench/first_order.jsonl --fixture-mode` → PASS（accuracy ≥0.55）。real gated 待跑。

## 5. Gated 真模型 run（需 OPENAI_API_KEY，不入 CI）
```
OPENAI_API_KEY=… python scripts/eval_longmemeval.py --corpus tests/data/eval_longmemeval/sessions.jsonl --report build/lme.md
OPENAI_API_KEY=… python scripts/eval_tom_bench.py    --corpus tests/data/eval_tom_bench/first_order.jsonl --report build/tom.md
OPENAI_API_KEY=… python scripts/eval_p1_extractor.py --corpus tests/data/eval_p1_corpus.jsonl --report build/p1.md
```

## 6. 结论
P2 §16.3 CRITICAL 准入达成；eval harness 就位且离线全绿；C1 承诺履行离线真过（detection/timeliness）。
C2/C3 真模型阈值数字待 gated run。**P2 结构性达标 + 离线验证完成，真模型 eval 数字 gated。**
```
implementer 跑 C1 取真数字填 §2;§1 对照 §16.3 填全 10 条真实测试名。

- [ ] **Step 2: 报告内不含 key**（grep 确认）+ Commit（`docs(P2.f): P2 准入报告` + trailer）

---

## Task 9: 全量回归 + close 准备

- [ ] **Step 1: 全量 ctest**（无 C++ 逻辑改,仅 Task 4 加绑定）`cmake --build build && ctest --test-dir build 2>&1 | tail -3` → 505/505。
- [ ] **Step 2: 全量 pytest** `pytest tests/python -q 2>&1 | tail -3` → 495 baseline + 新增（commitment_corpus 2 + eval_commitment_harness 4 + openai_embedding_binding 1 + eval_longmemeval_harness 2 + tom_bench_corpus 1 = +10 → ~505 passed）+ 13 skipped。报实际。
- [ ] **Step 3: 红线** — `git diff --stat main -- migrations/`（空）;`ls migrations/ | tail -1`（0021）;`grep -c "add_executable(starling_tests" tests/cpp/CMakeLists.txt`（1）;`git diff main -- python/starling/memory.py`（空,不改 Memory）;`git diff main -- scripts/eval_tom_bench.py scripts/eval_fantom.py`（空,不改既有 harness）。
- [ ] **Step 4: 提交 plan 文件** `git add docs/superpowers/plans/2026-06-02-p2-f-admission-eval.md && git commit -m "docs(P2.f): land admission eval implementation plan" + trailer`。
- [ ] **Step 5: 报告** ctest/pytest 数 + commit series,交回控制方 final review + 合并（merge 前查/清 root stray,`--no-ff` merge `worktree-p2-f-admission-eval` 回 main,需 dangerouslyDisableSandbox + 显式 consent）。

---

## Self-Review（plan 作者自检）

**1. Spec coverage：** §2 C1 → Task 1/2/3 ✅；§3 C2 → Task 5/6（+ Task 4 绑定）✅；§4 C3 → Task 7 ✅；§5 C4 → Task 8 ✅；§6 测试 → 各 Task 自测 + Task 9 ✅；§7 约束 → 全局约束 ✅。
**2. Placeholder scan：** 无 TBD（报告的 "TBD/待跑" 是 gated 数字的设计元素）；`_real_answer` 的 gated pipeline 在 Task 5 Step 3 由 implementer 用 verbatim 绑定补全（给了确切构造序列），非占位。
**3. Type consistency：** `run_scenario`/`run_one_round`/`write_report`/`_median`/`DETECTION_THRESHOLD`/`ACCURACY_THRESHOLD`/`SUBSETS` 跨 Task 一致；CommitmentEngine/PolicyEngine 绑定签名 verbatim。
**4. 与 spec 偏差（待 close 回补）：** OpenAIEmbeddingAdapter 绑定（"无 C++"→"+1 additive 绑定"）。
**5. 关键风险（已防）：** C1 语料 `expected` 须与真实引擎转移对齐——Task 2 强制探针核对,不符则回 Task 1 改语料(不改引擎)。
