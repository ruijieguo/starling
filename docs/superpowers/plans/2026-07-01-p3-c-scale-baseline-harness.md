<!-- r56-current-status:start -->
> **当前状态（R6.8，2026-09-26）**：本机无用编译中间产物已清理，删除4,041个可重建文件，目录占用减少612.48 MiB，保留证据核验一致。R6.8已完成中文设计、RED失败用例、C++原生SourceSelectionV1/JsonObject实现、133题来源选择、同期QA和独立核验；C++ 1395项、binding/localhost HTTP 20项、选择编排14项、QA编排16项通过。结构化请求133/133带合同且无Markdown围栏失败，但3题超过20条预算；v9为52/133，selector为60/133，净增6.02个百分点，六网络95%区间[-5.60,16.28]，候选正常127/133低于v9的130/133，门槛未通过，不晋升默认策略。结果仅为同八库、六网络133题开发集，不是完整SocialMemBench或生产结论。详见[当前设计](../specs/2026-09-26-socialmem-r68-structured-selection-design.md)和[当前报告](../../eval/2026-09-26-socialmem-r68-structured-selection.md)。
<!-- r56-current-status:end -->

> **R4.9 当前契约（2026-09-24）**：主题相关性与成员排序的 C++ 实现、回归、A/B 离线消融及真实复评已完成；检索回答 17/57、原生回答 16/57，较 R4.8 各净减 1 题，来源锚点 48→51/104，未证明准确率提升，不晋升默认策略。完整结果、归因边界及下一轮语义/事件证据方向见[中文评测报告](../../eval/2026-09-24-socialmem-r49-topic-ranking.md)。下文历史阶段记录保留原口径。

> R4.3 当前评测：事件状态与信念归属实验完成，检索 17/57、原生回答 19/57，0 技术失败，未晋升；详见 [中文评测报告](../../eval/2026-09-22-socialmem-r43-state-attribution.md)。下一轮先补结构化 claim metadata。
> **R4.0 当前契约（2026-09-22）**：已确认的证据覆盖、C++ 混合回答边界及双臂评测状态见 [统一中文设计](../specs/2026-09-21-socialmem-r40-evidence-profile-design.md)。本文历史阶段事实保留原口径，现行实现与验证状态以该入口为准。 实评已封存：两臂均 19/57，较父净增 3，区间跨零；原生回答 3 次截断，不晋升。详见 [中文评测报告](../../eval/2026-09-22-socialmem-r40-evidence-profile.md)。 R4.1 当前设计：人物—话题—时间链主体优先选择见 [中文设计](../specs/2026-09-22-socialmem-r41-subject-topic-timeline-design.md)；R4.0 评测报告已封存。 R4.2 当前设计：主体时间链与支持性第三方证据见 [中文设计](../specs/2026-09-22-socialmem-r42-support-lane-design.md)；R4.1 评测已封存。R4.2 评测已封存，详见 [中文评测报告](../../eval/2026-09-22-socialmem-r42-support-lane.md)。 R4.3 事件状态与信念归属设计见 [中文设计](../specs/2026-09-22-socialmem-r43-state-attribution-design.md)。
> R4.4 设计：下一轮将把已校验 semantic_claim_json metadata 接入 C++ 状态与归属车道；先 RED 测试，再实现，详见 [中文设计](../specs/2026-09-22-socialmem-r44-claim-attribution-design.md)。

> **人物会话覆盖终态（2026-09-19）**：99开发自由题同期对照完成：旧邻句40/99、人物会话覆盖43/99，净增+3题；未达到本轮事前扩大开发验证条件，不晋升。来源公开锚点182→188/200，不等于QA收益。详见[本轮报告](../../eval/2026-09-19-socialmem-source-coverage.md)。

> **回答消融终态（2026-09-19）**：99开发自由题四组合完成：SOURCE旧指导42/99、JSON旧指导46/99、SOURCE新指导37/99、JSON新指导34/99。仅作机制诊断，不晋升；不能替代733题或保留集成绩。详见[本轮报告](../../eval/2026-09-18-socialmem-answer-ablation.md)。

> **单次综合回答终态（2026-09-18）**：733开发题309/733（42.16%），较376题对照净增-67、-9.14个百分点；95%网络差值区间[-12.94，-5.37]个百分点。未满足全部事前门槛，不晋升；推荐仍grounded_v1/512。详见[本轮报告](../../eval/2026-09-18-socialmem-synthesis-answer.md)。

> **两阶段证据回答完成（2026-09-18）**：733开发题313/733＝42.70%，较同1024容量父47.07%下降4.37个百分点，观测tokens增加69.46%，未晋升；推荐仍为grounded_v1/512。C++引用核验已实现，语义推断仍未验证。详见[本轮诊断报告](../../eval/2026-09-18-socialmem-evidence-answer.md)。

> **回答容量实验完成（2026-09-18）**：733题开发345/733＝47.07%，相对grounded_v1/512的332/733净增13题（+1.77个百分点）；网络区间下界为-0.70个百分点，未晋升。截断60→3，技术失败74→20，观测tokens3,185,355。保留grounded_v1/512为通过门槛的推荐开发配置；详见[当前报告](../../eval/2026-09-18-socialmem-answer-capacity.md)。

> **紧凑回答实验完成（2026-09-18）**：733题开发248/733＝33.83%，相对父45.29%下降11.46个百分点，不晋升；截断60→0，技术失败74→2。当前最佳开发仍为grounded_v1的332/733；核心C++、原评分和历史全量身份保持。详见[本轮报告](../../eval/2026-09-18-socialmem-compact-answer.md)。

> **证据约束回答完成（2026-09-18）**：C++自由回答政策使开发273/733→332/733（45.29%，+8.05百分点），通过预注册开发门槛；技术失败11→74，60项回答截断。来源/模型/评分不变，默认legacy保持；无本轮保留或全量成绩，详见[当前报告](../../eval/2026-09-17-socialmem-grounded-answer.md)。

> **人物检索优化已验收（2026-09-17）**：C++人物路由与邻接完成开发及保留集验证，同一候选392/1031=38.02%，原baseline20.47%，累计+17.56百分点；保留集19.46%→39.93%。默认bm25保持，模型/评分不变，结构谓词能力另行验证；详见[当前报告](../../eval/2026-09-17-socialmem-source-focus.md)。历史结果按各自冻结版本解释。

# P3.c Scale-Baseline Harness Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A parameterized, offline (FakeLLM) load-test harness that seeds the memory machinery to P3 scale, measures the maintenance tick (per-stage) and retrieval latency, and emits a baseline report that fingers the real bottleneck — the measurement prelude to P3.c optimization.

**Architecture:** A standalone Python CLI `scripts/load_test_p3c.py` driving the public `Memory` facade + a `FakeLLMAdapter` end-to-end. Three phases — seed / tick / retrieval — each timed; results written as JSON + a human summary under `bench/`. A tiny-scale pytest smoke guards the harness mechanics in CI. Application-layer tooling: **no core memory semantics added** (Python is the correct home; it only seeds + measures through the public API and consumes the existing C++ `StageTimer` output).

**Tech Stack:** Python 3 (stdlib: `argparse`, `time.perf_counter`, `statistics`, `json`, `random`), the `starling` package (`Memory`, `make_stub_llm`, `TickStats`), pytest.

## Global Constraints

- **Design spec (authoritative):** `docs/superpowers/specs/2026-07-01-p3-c-scale-baseline-harness-design.md`. Scale interpretation: `--cognizers N` (target 1000), `--statements M` = **total** statements distributed across N cognizers (target 10000; NOT per-cognizer), `--queries Q`, `--seed S`.
- **Offline determinism:** use `starling.make_stub_llm(default_response=...)` (a `_core.FakeLLMAdapter`) — no network. The FakeLLMAdapter **ignores the prompt** and returns the canned response. Distinctness of the M statements comes from the **varying `remember()` payload text** (the idempotency key is `sha256(payload)`, `memory_ops.cpp:33` — distinct payloads never dedup); the **unique canned response per remember** (`fake.set_default_response(unique_json, True, "")`) makes the extracted STATEMENT vary (distinct subject/object → real corpus variety), NOT to avoid dedup. (Eng-review MEDIUM-4 corrected the original "dedup collapses to 1 row" claim — that never fires here.)
- **Holder model (eng-review decision A — BLOCKER-1 fix):** in Starling one agent's `Memory` recalls only its OWN statements — `Memory.query` hard-codes `querier = self.agent = "self"` (`memory.py:172`, `_memory_core.py:225`) and the planner filters `holder_id = querier` (`retrieval_planner.cpp:208`, `semantic_retriever.cpp:37`). So seed ALL statements under **`holder="self"`** (NOT `cog-N` — that hides them from the querier) and make the **1000 cognizers distinct SUBJECTS** (`subject = cog-{idx % cognizers}` in the canned response). The agent's memory holds M statements ABOUT N cognizers; retrieval as self scans them all.
- **Retrieval must exercise the real scan (BLOCKER-2 fix):** query with **NON-EMPTY** text (`query("")` skips the semantic path → abstains, `retrieval_planner.cpp:241`) for content that EXISTS in the corpus (an `obj_{k}` that was seeded), as `holder=self`. The smoke tests MUST assert `entries` non-empty / `abstained` False — else a green suite hides zero real retrieval (the O(n) cosine scan is `sqlite_blob_vector_index.cpp:61-95`, the actual bottleneck).
- **Known load-bearing facts (eng-review MEDIUM-4/5):** seeded statements land `review_status = review_requested` (`pred_N` isn't a core predicate, `predicate_registry.hpp:16`) — still retrievable (planner excludes only `rejected`/`pending_review`), but document it. `remember()` runs **3 extraction passes** (belief/episodic/general-fact, `_memory_core.py:145-190`); under FakeLLM only 1 persists per call (1:1 remember:statement holds), but seed `throughput_per_s` includes all 3 passes + the post-write subscriber pump.
- **Architecture boundary (CLAUDE.md):** this is tooling. Add NO algorithm / budget / state-machine / pipeline logic. Seed + measure through the public API only; consume `TickStats.stage_timings_ms` (already built in Phase 3b) for the per-stage breakdown.
- **Phase order:** seed → tick-to-drain (embeds the corpus so retrieval has vectors) → retrieval. Retrieval runs after the tick so statements are embedded (the facade uses `StubEmbeddingAdapter(8)`).
- **Build/test:** no C++ change → NO rebuild needed. Run tests with `.venv/bin/python -m pytest` (tools in `.venv/bin`, NOT system PATH). The harness itself runs as `.venv/bin/python scripts/load_test_p3c.py ...`.
- **Test design (benchmark):** the smoke test asserts **structural** properties (corpus size, report keys, percentiles computed, all phases ran) — NOT specific latency numbers (those are environment-dependent). A benchmark test that pins a wall-clock number is a flaky test.
- **git:** explicit-path `git add`; no `-A`/`--no-verify`/`--amend`. Footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File structure

- **Create** `scripts/load_test_p3c.py` — the CLI harness: data generation, the 3 phase functions (`run_seed`, `run_tick_drain`, `run_retrieval`), report assembly (`build_report` / `write_report`), and `main(argv)`.
- **Create** `tests/python/test_load_test_p3c_smoke.py` — tiny-scale smoke of `main()` + the phase functions.
- **Create** `bench/.gitignore` — ignore transient report outputs (`*.json`) but keep the dir tracked.

---

## Task 1: Harness skeleton + deterministic data generation + seed phase

**Files:**
- Create: `scripts/load_test_p3c.py`
- Create: `bench/.gitignore`
- Test: `tests/python/test_load_test_p3c_smoke.py`

**Interfaces (Produces):**
- `open_memory(db_path: str) -> tuple[Memory, FakeLLMAdapter]` — opens an offline `Memory` over `db_path`, returns it + the mutable fake so callers can set per-remember responses.
- `unique_statement_json(idx: int, cognizers: int) -> str` — a canned extraction response (JSON array of ONE statement); `subject = cog-{idx % cognizers}` (the cognizer as SUBJECT), `object = obj_{idx}` (unique) so the corpus spans N cognizer-subjects with M distinct objects.
- `run_seed(mem, fake, *, cognizers: int, statements: int, rng: random.Random) -> dict` — seeds `statements` statements under **`holder=self`** (the agent — the querier that can retrieve them; decision A), spanning `cognizers` distinct subjects; returns `{"seeded": int, "elapsed_s": float, "throughput_per_s": float}`.

- [ ] **Step 1: Write the failing smoke test (seed portion)**

```python
# tests/python/test_load_test_p3c_smoke.py
import random
import importlib.util
from pathlib import Path

# Load the script module by path (it lives in scripts/, not the package).
_SPEC = importlib.util.spec_from_file_location(
    "load_test_p3c",
    Path(__file__).resolve().parents[2] / "scripts" / "load_test_p3c.py",
)
lt = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(lt)


def test_seed_runs_and_counts(tmp_path):
    mem, fake = lt.open_memory(str(tmp_path / "seed.db"))
    rng = random.Random(1234)
    res = lt.run_seed(mem, fake, cognizers=3, statements=12, rng=rng)
    assert res["seeded"] == 12
    assert res["elapsed_s"] >= 0.0
    assert res["throughput_per_s"] > 0
    # Distinctness is by-construction: each remember() gets a distinct payload
    # (f"seed statement {idx} ...") so the engram idempotency key (sha256 of
    # payload, memory_ops.cpp:33) never collides — M remembers → M engrams → M
    # statements. Retrievability is proven in Task 2's retrieval test (retrieval
    # needs the tick to embed the corpus into statement_vectors first).
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py::test_seed_runs_and_counts -v`
Expected: FAIL (module `scripts/load_test_p3c.py` does not exist yet).

- [ ] **Step 3: Implement the skeleton + seed phase**

```python
# scripts/load_test_p3c.py
"""P3.c scale-baseline harness — offline (FakeLLM) load test + baseline report.

Seeds the memory machinery to scale, measures the maintenance tick (per-stage)
and retrieval latency, and emits a baseline report. Application-layer tooling:
seeds + measures through the public Memory API; adds no core semantics. See
docs/superpowers/specs/2026-07-01-p3-c-scale-baseline-harness-design.md.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from pathlib import Path

from starling import Memory, make_stub_llm


def open_memory(db_path: str):
    """Open an offline Memory over db_path; return (mem, fake_llm).

    The FakeLLMAdapter is returned so the caller can set a unique canned
    response before each remember (the adapter ignores the prompt).
    """
    fake = make_stub_llm(default_response=unique_statement_json(0, 1))
    mem = Memory.open(db_path, agent="self", tenant_id="default", llm=fake)
    return mem, fake


def unique_statement_json(idx: int, cognizers: int) -> str:
    """A canned extraction response (JSON array of ONE statement).

    holder=self (the agent owns it — the querier that can retrieve it);
    subject=cog-{idx % cognizers} is the COGNIZER the fact is ABOUT (decision A:
    cognizers are subjects, not holders); object=obj_{idx} is unique per idx.
    """
    return (
        '[{"holder":"self","holder_perspective":"FIRST_PERSON",'
        f'"subject":"cog-{idx % cognizers}","predicate":"pred_{idx % 131}",'
        f'"object":"obj_{idx}","modality":"BELIEVES","polarity":"POS",'
        '"nesting_depth":0}]'
    )


def run_seed(mem, fake, *, cognizers: int, statements: int,
             rng: random.Random) -> dict:
    """Seed `statements` statements under holder=self, spanning N cognizer-subjects."""
    start = time.perf_counter()
    seeded = 0
    for idx in range(statements):
        fake.set_default_response(unique_statement_json(idx, cognizers), True, "")
        # holder defaults to the agent ("self") — the querier that can retrieve
        # these (decision A). Distinct payload → distinct engram (no dedup).
        mem.remember(f"seed statement {idx} topic {rng.randint(0, 1_000_000)}",
                     now="2026-07-01T00:00:00Z")
        seeded += 1
    elapsed = time.perf_counter() - start
    return {
        "seeded": seeded,
        "elapsed_s": round(elapsed, 4),
        "throughput_per_s": round(seeded / elapsed, 2) if elapsed > 0 else 0.0,
    }
```

Also create `bench/.gitignore` with:

```
# transient baseline reports
*.json
!.gitignore
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py::test_seed_produces_distinct_statements -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/load_test_p3c.py tests/python/test_load_test_p3c_smoke.py bench/.gitignore
git commit -m "feat(P3.c/bench): harness skeleton + deterministic seed phase"
```

---

## Task 2: Tick-to-drain + retrieval measurement phases

**Files:**
- Modify: `scripts/load_test_p3c.py`
- Test: `tests/python/test_load_test_p3c_smoke.py`

**Interfaces:**
- Consumes: `open_memory`, `run_seed` (Task 1); `Memory.tick(now) -> TickStats` (`.embedded`, `.stage_timings_ms` = list of `{"stage": str, "ms": int}`); `Memory.query(text, *, intent, k) -> dict` (`["entries"]`).
- Produces:
  - `run_tick_drain(mem, *, max_ticks: int = 1000) -> dict` — runs `tick()` until the embed queue TRULY drains (`TickStats.embedded == 0` **AND** `"embed"` NOT in `stats.stages_skipped` — LOW-6 guard: `embed` is a Soft stage shed under DEGRADED, so `embedded==0` alone can be a false drain) or `max_ticks`; returns `{"ticks": int, "elapsed_s": float, "stage_ms_total": dict[str, float], "top_stage": str, "embed_shed_ticks": int}` (per-stage ms summed across executed ticks; `top_stage` = costliest; `embed_shed_ticks` > 0 flags a DEGRADED-tripped run whose drain may be incomplete).
  - `run_retrieval(mem, *, queries: int, statements: int, rng: random.Random) -> dict` — issues `queries` `Memory.query` calls for **EXISTING** objects (`obj_{rng.randint(0, statements-1)}`, non-empty text, `holder=self` — BLOCKER-2), times each; returns `{"queries": int, "p50_ms": float, "p95_ms": float, "p99_ms": float, "throughput_per_s": float, "abstained_count": int}`. `abstained_count` surfaces whether queries hit the real O(n) scan vs the abstain path (a green suite with all-abstain = meaningless numbers, the BLOCKER-2 trap).

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/python/test_load_test_p3c_smoke.py
def test_tick_drain_reports_stage_breakdown(tmp_path):
    mem, fake = lt.open_memory(str(tmp_path / "tick.db"))
    rng = random.Random(7)
    lt.run_seed(mem, fake, cognizers=3, statements=12, rng=rng)
    res = lt.run_tick_drain(mem, max_ticks=50)
    assert res["ticks"] >= 1
    assert isinstance(res["stage_ms_total"], dict) and res["stage_ms_total"]
    # The 8 known stages are the only keys; top_stage is one of them.
    assert res["top_stage"] in res["stage_ms_total"]
    # Smoke scale must not trip DEGRADED, so the drain is a real drain (LOW-6).
    assert res["embed_shed_ticks"] == 0


def test_retrieval_hits_the_scan_not_the_abstain_path(tmp_path):
    mem, fake = lt.open_memory(str(tmp_path / "ret.db"))
    rng = random.Random(9)
    lt.run_seed(mem, fake, cognizers=3, statements=12, rng=rng)
    lt.run_tick_drain(mem, max_ticks=50)   # embed the corpus before retrieval
    res = lt.run_retrieval(mem, queries=20, statements=12, rng=rng)
    assert res["queries"] == 20
    for key in ("p50_ms", "p95_ms", "p99_ms"):
        assert res[key] >= 0.0
    assert res["p99_ms"] >= res["p50_ms"]   # monotone percentiles
    assert res["throughput_per_s"] > 0
    # BLOCKER-2 proof: querying EXISTING objects as holder=self must hit the real
    # O(n) scan, not the abstain path. If every query abstained (holder mismatch
    # / empty text), the p-latencies would be meaningless. Not all-abstain:
    assert res["abstained_count"] < res["queries"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py -k "tick_drain or retrieval" -v`
Expected: FAIL (`run_tick_drain` / `run_retrieval` not defined).

- [ ] **Step 3: Implement the two phases**

```python
# add to scripts/load_test_p3c.py

def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Nearest-rank percentile (pct in [0,100]) over a non-empty sorted list."""
    if not sorted_vals:
        return 0.0
    rank = max(1, int(round(pct / 100.0 * len(sorted_vals))))
    return sorted_vals[min(rank, len(sorted_vals)) - 1]


def run_tick_drain(mem, *, max_ticks: int = 1000) -> dict:
    """Run tick() until the embed queue TRULY drains (or max_ticks); sum stage costs."""
    start = time.perf_counter()
    stage_ms_total: dict[str, float] = {}
    ticks = 0
    embed_shed_ticks = 0
    for _ in range(max_ticks):
        stats = mem.tick("2026-07-01T00:05:00Z")
        ticks += 1
        if "embed" in stats.stages_skipped:
            embed_shed_ticks += 1
        for entry in stats.stage_timings_ms:
            stage_ms_total[entry["stage"]] = (
                stage_ms_total.get(entry["stage"], 0.0) + float(entry["ms"]))
        # LOW-6 guard: `embed` is a Soft stage shed under DEGRADED, so
        # embedded==0 while embed was SKIPPED is NOT a real drain — keep ticking.
        if stats.embedded == 0 and "embed" not in stats.stages_skipped:
            break
    elapsed = time.perf_counter() - start
    top_stage = max(stage_ms_total, key=stage_ms_total.get) if stage_ms_total else ""
    return {
        "ticks": ticks,
        "elapsed_s": round(elapsed, 4),
        "stage_ms_total": {k: round(v, 3) for k, v in stage_ms_total.items()},
        "top_stage": top_stage,
        "embed_shed_ticks": embed_shed_ticks,
    }


def run_retrieval(mem, *, queries: int, statements: int,
                  rng: random.Random) -> dict:
    """Issue `queries` retrieval calls for EXISTING objects; report percentiles."""
    latencies_ms: list[float] = []
    abstained_count = 0
    hi = max(0, statements - 1)
    start = time.perf_counter()
    for _ in range(queries):
        text = f"obj_{rng.randint(0, hi)}"   # an object that was seeded (BLOCKER-2)
        t0 = time.perf_counter()
        result = mem.query(text, intent="FACT_LOOKUP", k=10)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
        if result.get("abstained"):
            abstained_count += 1
    elapsed = time.perf_counter() - start
    latencies_ms.sort()
    return {
        "queries": queries,
        "p50_ms": round(_percentile(latencies_ms, 50), 3),
        "p95_ms": round(_percentile(latencies_ms, 95), 3),
        "p99_ms": round(_percentile(latencies_ms, 99), 3),
        "throughput_per_s": round(queries / elapsed, 2) if elapsed > 0 else 0.0,
        "abstained_count": abstained_count,
    }
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py -k "tick_drain or retrieval" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/load_test_p3c.py tests/python/test_load_test_p3c_smoke.py
git commit -m "feat(P3.c/bench): tick-drain stage breakdown + retrieval percentiles"
```

---

## Task 3: Report assembly + CLI + end-to-end smoke

**Files:**
- Modify: `scripts/load_test_p3c.py`
- Test: `tests/python/test_load_test_p3c_smoke.py`

**Interfaces:**
- Consumes: `open_memory`, `run_seed`, `run_tick_drain`, `run_retrieval`.
- Produces:
  - `build_report(params: dict, seed: dict, tick: dict, retrieval: dict) -> dict` — assembles the full report dict.
  - `write_report(report: dict, out_dir: str) -> Path` — writes `<out_dir>/p3c_baseline_<cognizers>c_<statements>s.json`, returns the path.
  - `format_summary(report: dict) -> str` — the human-readable summary string.
  - `main(argv: list[str] | None = None) -> int` — argparse CLI running all phases; exit 0.

- [ ] **Step 1: Write the failing end-to-end test**

```python
# append to tests/python/test_load_test_p3c_smoke.py
def test_main_end_to_end_writes_report(tmp_path):
    out = tmp_path / "bench"
    rc = lt.main([
        "--db", str(tmp_path / "e2e.db"),
        "--cognizers", "3", "--statements", "12", "--queries", "10",
        "--seed", "42", "--out-dir", str(out),
    ])
    assert rc == 0
    reports = list(out.glob("p3c_baseline_*.json"))
    assert len(reports) == 1
    import json as _json
    report = _json.loads(reports[0].read_text())
    for key in ("params", "seed", "tick", "retrieval", "caveats"):
        assert key in report
    assert report["seed"]["seeded"] == 12
    assert report["retrieval"]["queries"] == 10
    assert report["tick"]["top_stage"]           # non-empty bottleneck call-out
    # BLOCKER-2 e2e: retrieval hit the real scan, not the all-abstain path.
    assert report["retrieval"]["abstained_count"] < report["retrieval"]["queries"]
    # The tick stages are EXACTLY the 8 known ones — this meaningfully confirms
    # persona-rebuild is NOT a live tick stage (the empirical inert check;
    # replaces the vacuous "persona" substring assertion which was always true).
    assert set(report["tick"]["stage_ms_total"]) == {
        "embed", "policy", "common_ground", "replay_oscillation_guard",
        "replay_ttl_sweep", "replay_idle", "projection", "outbox",
    }
    assert "persona" not in report["tick"]["stage_ms_total"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py::test_main_end_to_end_writes_report -v`
Expected: FAIL (`main` not defined).

- [ ] **Step 3: Implement report + CLI**

```python
# add to scripts/load_test_p3c.py

# Validity caveats — printed + embedded in the report so the baseline is never
# mistaken for a production profile (eng-review MAJOR-3).
_CAVEATS = [
    "FakeLLM + StubEmbedding(8-dim): extraction-LLM and embedding-network cost "
    "are EXCLUDED. A real embedder is ~1536-dim, so the O(n) cosine scan cost is "
    "under-measured (~190x). top_stage reflects the SQLite/scan machinery, NOT "
    "the production embedding/LLM hotspot — do not pick an optimization target "
    "from this alone without an LLM-in-the-loop cross-check.",
    "Retrieval is single-holder (holder=self owns all rows) and SEQUENTIAL; "
    "sustained-concurrent 100 QPS is deferred (out of scope for this baseline).",
    "If retrieval.abstained_count > 0, those queries hit the abstain path, not "
    "the scan — their latencies are not retrieval-scan latency.",
    "If tick.embed_shed_ticks > 0, the drain tripped DEGRADED load-shedding and "
    "may be incomplete (some statements left un-embedded).",
]


def build_report(params: dict, seed: dict, tick: dict, retrieval: dict) -> dict:
    return {"params": params, "seed": seed, "tick": tick,
            "retrieval": retrieval, "caveats": _CAVEATS}


def write_report(report: dict, out_dir: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = report["params"]
    path = out / f"p3c_baseline_{p['cognizers']}c_{p['statements']}s.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True))
    return path


def format_summary(report: dict) -> str:
    seed, tick, ret = report["seed"], report["tick"], report["retrieval"]
    lines = [
        "=== P3.c scale-baseline ===",
        f"seed:      {seed['seeded']} stmts in {seed['elapsed_s']}s "
        f"({seed['throughput_per_s']}/s)",
        f"tick:      {tick['ticks']} ticks, {tick['elapsed_s']}s; "
        f"top stage = {tick['top_stage']}; embed_shed_ticks={tick['embed_shed_ticks']}",
        "  stage_ms_total: " + ", ".join(
            f"{k}={v}" for k, v in sorted(
                tick["stage_ms_total"].items(), key=lambda kv: -kv[1])),
        f"retrieval: {ret['queries']} q; p50={ret['p50_ms']}ms "
        f"p95={ret['p95_ms']}ms p99={ret['p99_ms']}ms "
        f"({ret['throughput_per_s']}/s); abstained={ret['abstained_count']}/{ret['queries']}",
        "caveats:",
        *(f"  - {c}" for c in report.get("caveats", [])),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P3.c scale-baseline load-test harness.")
    ap.add_argument("--db", required=True, help="SQLite path to seed into")
    ap.add_argument("--cognizers", type=int, default=1000)
    ap.add_argument("--statements", type=int, default=10000, help="total statements")
    ap.add_argument("--queries", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="bench")
    ap.add_argument("--max-ticks", type=int, default=100000)
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    mem, fake = open_memory(args.db)
    params = {"cognizers": args.cognizers, "statements": args.statements,
              "queries": args.queries, "seed": args.seed}
    print(f"seeding {args.statements} stmts across {args.cognizers} cognizers ...")
    seed = run_seed(mem, fake, cognizers=args.cognizers,
                    statements=args.statements, rng=rng)
    print(f"draining tick queue (max {args.max_ticks}) ...")
    tick = run_tick_drain(mem, max_ticks=args.max_ticks)
    print(f"retrieval x{args.queries} (existing objects, holder=self) ...")
    retrieval = run_retrieval(mem, queries=args.queries,
                              statements=args.statements, rng=rng)

    report = build_report(params, seed, tick, retrieval)
    path = write_report(report, args.out_dir)
    print(format_summary(report))
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the full smoke suite to verify pass**

Run: `.venv/bin/python -m pytest tests/python/test_load_test_p3c_smoke.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Run the harness at a small real scale (sanity) + full pytest gate**

Run: `.venv/bin/python scripts/load_test_p3c.py --db /tmp/p3c.db --cognizers 20 --statements 200 --queries 50 --seed 1`
Expected: prints the summary + writes `bench/p3c_baseline_20c_200s.json`. Then:
Run: `.venv/bin/python -m pytest tests/python -q`
Expected: full suite green (harness adds only the smoke tests; no existing test touched).

- [ ] **Step 6: Commit**

```bash
git add scripts/load_test_p3c.py tests/python/test_load_test_p3c_smoke.py
git commit -m "feat(P3.c/bench): baseline report + CLI + end-to-end smoke"
```

---

## Slice acceptance

The harness runs offline (FakeLLM) end-to-end: seeds M distinct statements under `holder=self` spanning N cognizer-SUBJECTS (deterministic via `--seed`; decision A), drains the maintenance tick (per-stage breakdown from the 3b `StageTimer`, LOW-6-guarded against a DEGRADED false-drain), drives Q retrieval queries for EXISTING objects as `holder=self` (p50/p95/p99 + throughput + `abstained_count`), and writes a JSON + human report under `bench/` with the top tick-stage bottleneck AND the validity caveats (embedding/LLM cost excluded). The smoke pytest asserts harness mechanics + **retrieval actually hits the O(n) scan, not the abstain path** (`abstained_count < queries` — BLOCKER-2) + the tick stages are exactly the 8 known ones (persona-rebuild is not among them) — no wall-clock thresholds. Full pytest green. **Deferred (next, now-measured slices):** admission thresholds set from the baseline; sustained-concurrent 100 QPS; optimizing the fingered bottleneck.

## Self-review

**Spec coverage:** parameterized scale (Task 1/3 CLI) ✅; FakeLLM offline + unique-canned-response distinct seeding (Task 1) ✅; 3 phases seed/tick/retrieval (Tasks 1-2) ✅; per-stage breakdown reusing StageTimer (Task 2) ✅; p50/p95/p99 + throughput (Task 2) ✅; JSON + human report under bench/ (Task 3) ✅; smoke pytest (Tasks 1-3) ✅; architecture boundary = tooling, no core logic ✅; empirical persona-inert check (Task 3 assertion) ✅. Deferred items are explicitly out of scope.

**Placeholder scan:** every step has real code + exact run commands + expected output. No TBD/TODO.

**Type consistency:** `open_memory→(mem,fake)`, `unique_statement_json(idx,cognizers)->str`, `run_seed(...)->dict{seeded,elapsed_s,throughput_per_s}`, `run_tick_drain(...)->dict{ticks,elapsed_s,stage_ms_total,top_stage,embed_shed_ticks}`, `run_retrieval(mem,*,queries,statements,rng)->dict{queries,p50_ms,p95_ms,p99_ms,throughput_per_s,abstained_count}`, `build_report(params,seed,tick,retrieval)->dict{...,caveats}`, `write_report->Path`, `main(argv)->int` — consistent across tasks. `TickStats.stage_timings_ms` entries are `{"stage","ms"}`; `TickStats.stages_skipped` is a `list[str]` (3b/LW.3), both consumed in Task 2 (the drain guard reads `stages_skipped`).

## /plan-eng-review resolutions (2026-07-01, FULL + outside-voice)
- **BLOCKER-1 (holder model) → decision A:** seed under `holder=self`, cognizers = distinct SUBJECTS. `Memory.query` queries as `self`; rows under a different holder are invisible.
- **BLOCKER-2 (retrieval measured the abstain path) → fixed:** query non-empty text for EXISTING objects as `holder=self`; smoke asserts `abstained_count < queries`.
- **MAJOR-3 (validity) → fixed:** `_CAVEATS` embedded in the report + printed (embedding/LLM cost excluded; ~190× scan under-measure; single-holder sequential).
- **MEDIUM-4/5 (wrong dedup mechanism; 3-pipeline remember) → documented** in Global Constraints.
- **LOW-6 (drain false-stop under DEGRADED) → guarded:** `run_tick_drain` breaks only when `embedded==0` AND `embed` not in `stages_skipped`; `embed_shed_ticks` surfaced.
- **Termination worry → RESOLVED** by the outside voice: embed batch=32 (`embedding_worker.hpp:11`), the LEFT-JOIN scan only re-fetches unembedded rows, stub never fails → M drains in ⌈M/32⌉ ticks; `--max-ticks` caps runaway.
- Still tunable / left to impl: baseline scale under FakeLLM (`--cognizers`/`--statements`); `bench/` (not `build/`) for output; smoke stays tiny (3 cognizers × 12) so no CI marker needed.

## Eng-review outputs

**What already exists (reused, not rebuilt):** 3b `StageTimer` + `TickStats.stage_timings_ms`/`stages_skipped`; the public `Memory` API (`open`/`remember`/`query`/`tick`); `make_stub_llm` (offline FakeLLM); the `scripts/eval_*` argparse+report precedent; `StubEmbeddingAdapter(8)`. No parallel infra built.

**NOT in scope (deferred, with rationale):** admission pass/fail thresholds (set from THIS baseline — guessing now = arbitrary red gate); sustained-concurrent 100 QPS (needs a read-path concurrency analysis — single-writer/GIL); optimizing the fingered bottleneck (the NEXT, now-measured slice); a real-LLM/real-embedder profile (this baseline is FakeLLM+stub by design — the caveats flag what it excludes).

**Failure modes (per new codepath):**
- `run_seed` remember() raises → propagates, crashes the run (fail-loud, correct for a measurement tool). No forced-failure test (internal tooling).
- `run_tick_drain` non-termination → `--max-ticks` cap + LOW-6 guard; `embed_shed_ticks` surfaces a DEGRADED false-drain. Tested (`embed_shed_ticks == 0`).
- `run_retrieval` all-abstain → **would silently produce meaningless p-latencies** (the critical gap). Now has BOTH a test (`abstained_count < queries`) AND a report signal.

**Parallelization:** Sequential — all 3 tasks build one file (`scripts/load_test_p3c.py`) + its smoke test, each depending on the prior.

## Implementation Tasks
All findings were folded into the plan tasks above (not deferred); these mirror the revised Tasks 1-3.

- [ ] **T1 (P1, CC: ~10min)** — seed phase, holder=self + cognizer-subjects (BLOCKER-1) — `scripts/load_test_p3c.py`, `tests/python/test_load_test_p3c_smoke.py`, `bench/.gitignore`. Verify: `pytest ...::test_seed_runs_and_counts`.
- [ ] **T2 (P1, CC: ~15min)** — tick-drain guard + retrieval-over-existing-objects + `abstained_count` (BLOCKER-2 + LOW-6). Verify: `pytest ... -k "tick_drain or retrieval"`.
- [ ] **T3 (P1, CC: ~10min)** — report + caveats + CLI + e2e smoke (MAJOR-3). Verify: full smoke + a small real-scale run.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | codex timed out (6m, no output) → Claude Opus outside-voice ran |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 6 findings (2 blocker / 1 major / 2 medium / 1 low), ALL folded |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

Step 0 scope: ACCEPTED as-is — 3 files, 0 new classes, reuses existing infra; no complexity-gate trigger. Architecture sound (Python tooling over the public API, no core semantics). Code quality clean (`_percentile` nearest-rank correct-by-design; fail-loud). Tests strengthened to assert retrieval hits the real scan (`abstained_count < queries`).

- **OUTSIDE VOICE (Claude Opus subagent; codex timed out at 6m):** empirically ran the harness logic against the built `_core` and caught 2 BLOCKERS the multi-section review missed — (1) `Memory.query` queries as `self` but the plan seeded under `holder=cog-N`, so retrieval returned 0/abstained (`memory.py:172`, `retrieval_planner.cpp:208`); (2) `run_retrieval` therefore timed the abstain path, not the O(n) scan — a green smoke suite hiding meaningless numbers. Plus MAJOR-3 (FakeLLM+stub excludes embedding+LLM cost; ~190× scan under-measure), MEDIUM-4 (the "dedup collapses to 1 row" mechanism was wrong — distinctness comes from the varying payload), MEDIUM-5 (3-pipeline remember), LOW-6 (embed is Soft → `embedded==0` can be a false drain). ALL folded.
- **CROSS-MODEL:** no tension — the outside voice confirmed my read (the O(n) scan IS representative) then found the deeper bug that the query never reaches the scan. Both agree the architecture is sound; the blockers were measurement-correctness.
- **VERDICT:** ENG CLEARED — 6 findings, ALL folded into the revised plan (holder=self+subjects / query-existing-objects+assert-non-abstain / report caveats / drain guard / doc corrections). Ready to implement subagent-driven.

NO UNRESOLVED DECISIONS
