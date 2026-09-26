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

# gist v2 Judge-Prompt Follow-up Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reword `kNormGistPromptTemplate` so the consolidation JUDGE treats holder consensus as sufficient evidence (no demographic skepticism) and emits one concise no-added-scope norm sentence aligned with the set-level tightness verify — while staying a coherence filter — unblocking gist v2 promotion end-to-end.

**Architecture:** A single `constexpr std::string_view` string-literal edit in `src/replay/gist_prompt.cpp`. `build_norm_gist_prompt`'s substitution logic is unchanged. Validation is a manual real-LLM re-dogfood (v2 promotes + v1 does not regress).

**Tech Stack:** C++20 kernel (`src/replay/`), GoogleTest (`tests/cpp/`), pybind11 `_core`, DashScope (qwen-plus + text-embedding-v3) for the manual re-dogfood.

**Approved spec:** `docs/superpowers/specs/2026-07-04-gist-judge-prompt-followup-design.md` (branch `feat/gist-judge-prompt` @ `1b09c71`, off `main@c5ce05a` which has entailment fix PR #47).

## Global Constraints

- **架构边界(硬):** the judge prompt is core consolidation semantics → C++ core single-source `constexpr`, NOT Python config.
- **Only `kNormGistPromptTemplate` changes.** `min_confidence` floor, `similarity_threshold`, the entity judge (`kEntityGistPromptTemplate`), the entailment verify prompts (`kEntailmentPromptTemplate` / `kSemanticEntailmentTemplate`), and the v2 default-OFF state are ALL untouched.
- **Each placeholder appears exactly once** (`build_norm_gist_prompt` uses `replace_first`, not `replace_all`): `{predicate}`, `{object}`, `{holder_count}`, `{holders}`. NEVER introduce a second `{holder_count}` — it would survive as a literal.
- **Blast radius = all people-norm gists (v1 exact + v2 semantic)** both use this template. The reword is strictly clearer (concise + consensus-is-evidence), expected to help v1 — but v1 non-regression MUST be proven by the re-dogfood.
- Existing gist tests do NOT pin the template prose (they drive `FakeLLMAdapter` with canned `{confidence, summary}` JSON) → no wording pin; **full `ctest` + `pytest tests/python` green is the commit gate.**
- Build: `python scripts/configure_build.py --build --python-editable` (the template is in `starling_core`; the editable reinstall keeps `_core` in sync for the Python re-dogfood).
- clang-tidy is CI-only; this is a string-literal edit (no identifiers / no logic) → no new lint surface.
- git: explicit-path `git add` only (no `git add .` / `-A`); no `--no-verify` / `--amend`. End commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/replay/gist_prompt.cpp` | single-source prompt templates | Reword `kNormGistPromptTemplate` (lines 18-28). |
| `tests/cpp/test_gist_prompt.cpp` | prompt-builder unit tests | Add a guard test (framing + no-residual-placeholder). |

No other files. `build_norm_gist_prompt`, `parse_gist_judgment`, `gist_prompt.hpp`, bindings, Python — all unchanged.

---

### Task 1: Reword the norm-judge template + guard test

**Files:**
- Modify: `src/replay/gist_prompt.cpp:18-28` (`kNormGistPromptTemplate`)
- Test: `tests/cpp/test_gist_prompt.cpp`

**Interfaces:**
- Consumes: `build_norm_gist_prompt(const GistCluster&)` (unchanged — fills `{predicate}`, `{object}`, `{holder_count}`, `{holders}` via `replace_first`); `GistCluster` (`gist_clustering.hpp`).
- Produces: no new symbol. The reworded template string.

**Pre-existing tests that MUST stay green (they are structural, not wording pins) — do not modify them:**
- `GistPrompt.BuildFillsClusterContext` asserts the filled prompt contains `"likes"`, `"coffee"`, `"3 distinct holders"`, `"alice, bob, carol"`, and no `"{predicate}"`. The reworded template KEEPS the Candidate block line `asserted by {holder_count} distinct holders: {holders}` verbatim, so `"3 distinct holders"` + `"alice, bob, carol"` remain present.
- `GistPrompt.EntityClusterRoutesToEntityJudge` exercises the entity template (`kEntityGistPromptTemplate`), which this task does NOT touch.

- [ ] **Step 1: Write the failing guard test**

Add to `tests/cpp/test_gist_prompt.cpp` (uses the existing `sample_cluster()` helper + `build_norm_gist_prompt`, both already in the file):

```cpp
// The reworded norm judge carries the consensus-is-evidence + concise-no-scope framing,
// and leaves NO residual placeholder. A duplicated {holder_count} (replace_first fills
// only the first) or a reversion to the old demographic-skeptic wording would fail this.
TEST(GistPrompt, NormJudgeConsensusFramingNoResidualPlaceholders) {
    const std::string prompt = build_norm_gist_prompt(sample_cluster());
    // consensus-is-evidence (anti-skepticism) + concise-no-scope intent present
    EXPECT_NE(prompt.find("independent agreement IS the evidence"), std::string::npos);
    EXPECT_NE(prompt.find("add no cause"), std::string::npos);
    // every placeholder filled exactly once → none survives literally
    EXPECT_EQ(prompt.find("{holder_count}"), std::string::npos);
    EXPECT_EQ(prompt.find("{predicate}"), std::string::npos);
    EXPECT_EQ(prompt.find("{object}"), std::string::npos);
    EXPECT_EQ(prompt.find("{holders}"), std::string::npos);
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R GistPrompt --output-on-failure 2>&1 | tail -20`
Expected: `NormJudgeConsensusFramingNoResidualPlaceholders` FAILS on `find("independent agreement IS the evidence")` (the old template lacks that phrase). Pre-existing `GistPrompt.*` tests still PASS.

- [ ] **Step 3: Reword the template**

In `src/replay/gist_prompt.cpp`, replace the `kNormGistPromptTemplate` definition (the `R"PROMPT(...)PROMPT"` block, lines 18-28) with — verbatim:

```cpp
constexpr std::string_view kNormGistPromptTemplate =
    R"PROMPT(You are the consolidation faculty of a brain-like memory system. Several DISTINCT holders have INDEPENDENTLY asserted the same belief. Their independent agreement IS the evidence — you are consolidating THIS memory's observed consensus, NOT judging whether the wider population holds it, so do NOT require demographic, cultural, or sample-size evidence. Judge only whether their shared belief is a COHERENT, generalizable belief worth recording as a norm, rather than a coincidental or incoherent overlap.

Candidate norm:
  predicate: {predicate}
  object: {object}
  asserted by {holder_count} distinct holders: {holders}

Reply with ONLY a JSON object (no prose, no markdown):
{"confidence": <number 0.0-1.0 — how coherent and generalizable the shared belief is, GIVEN the holders' agreement as sufficient evidence>, "summary": "<ONE short plain sentence stating ONLY the shared belief; add no cause, scope, category, interpretation, or detail beyond what the holders assert>"}
)PROMPT";
```

Leave the leading `// CORE single-source NORM-gist prompt...` comment (lines 13-17) — optionally update it to note the consensus-is-evidence framing, but do not change other templates. Confirm `{predicate}`, `{object}`, `{holder_count}`, `{holders}` each appear EXACTLY ONCE in the new block.

- [ ] **Step 4: Run the guard + pre-existing prompt tests to verify green**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R GistPrompt --output-on-failure 2>&1 | tail -20`
Expected: `NormJudgeConsensusFramingNoResidualPlaceholders` PASS; `BuildFillsClusterContext`, `EntityClusterRoutesToEntityJudge`, and all other `GistPrompt.*` PASS unchanged.

- [ ] **Step 5: Full-suite regression gate**

Run: `python scripts/configure_build.py --build --python-editable && ctest --test-dir build --output-on-failure 2>&1 | tail -15 && .venv/bin/python -m pytest tests/python -q 2>&1 | tail -15`
Expected: full `ctest` green; `pytest tests/python` green. (No test pins the template prose, so the reword is behavior-neutral to the suite; the `--python-editable` reinstall syncs `_core` for Task 2.)

- [ ] **Step 6: Commit**

```bash
git add src/replay/gist_prompt.cpp tests/cpp/test_gist_prompt.cpp
git commit -m "feat(gist): reword norm judge — consensus-is-evidence + concise no-scope

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Real-LLM re-dogfood validation (manual, not a CI gate)

**Files:**
- Create: `$CLAUDE_JOB_DIR/tmp/gist_judge_revalidate.py` (ephemeral — not committed; needs `DASHSCOPE_API_KEY`, so it is a manual check, not a pytest)

**Interfaces:**
- Consumes: `starling._core` (`OpenAIEmbeddingConfig`/`OpenAIEmbeddingAdapter`, `MemoryCore`, `worker.tick_one_batch`, `run_replay`), `starling.memory.make_openai_llm`, `starling.runtime._build_local_store_sqlite_runtime`. Same harness as the entailment-fix dogfood.
- Produces: before/after numbers + promoted summaries for the PR body. **Baseline (pre-this-slice):** tired + coffee v2 semantic clusters → `abstracted=0, gist_gated=1`.

**Deliverable:** run the script; paste output into the PR. Per the spec's realistic success bar: (1) the judge now emits a **concise, no-added-scope** summary (inspect the text), (2) at least one clean `abstracted=1` for a v2 semantic cluster within a few attempts, (3) **v1 people-norm does not regress**.

- [ ] **Step 1: Write the revalidation script**

Create `$CLAUDE_JOB_DIR/tmp/gist_judge_revalidate.py`:

```python
"""Post-judge-reword re-dogfood: v2 semantic clusters now promote a CONCISE gist
(pre-fix judge summaries were verbose/over-scoped or over-skeptical → gated), and v1
people-norm (same-object) still promotes (no regression)."""
import os, sqlite3
from pathlib import Path
from starling import _core
from starling import runtime as rt
from starling._memory_core import MemoryCore
from starling.memory import make_openai_llm

BASE = os.path.join(os.environ["CLAUDE_JOB_DIR"], "tmp", "gist_judge.db")

def run(seed_rows, threshold, label, attempts=3):
    best = None
    for attempt in range(attempts):
        for f in (BASE, BASE + "-wal", BASE + "-shm"):
            if os.path.exists(f):
                os.remove(f)
        r = rt._build_local_store_sqlite_runtime(Path(BASE)); r.start(); del r
        c = sqlite3.connect(BASE)
        for i, (h, p, o) in enumerate(seed_rows):
            c.execute(
                "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
                "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
                "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
                "affect_json,activation,last_accessed,provenance,replay_count,consolidation_state,"
                "review_status,access_count,created_at,updated_at) VALUES(" + ",".join("?" * 26) + ")",
                (f"s{i}", "default", h, "first_person", "cognizer", h, p, "str", o,
                 (f"h{i}" + "0" * 64)[:64] if threshold > 0 else "a" * 64,  # v1: SAME hash (exact)
                 "v1", "believes", "pos", 0.9, "2026-05-27T09:00:00Z", 0.5, "{}", 0.0,
                 "2026-05-27T09:00:00Z", "user_input", 2, "volatile", "approved", 1,
                 "2026-05-27T09:00:00Z", "2026-05-27T09:00:00Z"))
        c.commit(); c.close()
        r = rt._build_local_store_sqlite_runtime(Path(BASE)); r.start()
        core = MemoryCore(r, agent="self", tenant_id="default", llm=None,
                          adapter_name="d", source_prefix="d-")
        ecfg = _core.OpenAIEmbeddingConfig.from_env(); ecfg.model = "text-embedding-v3"; ecfg.dim = 1024
        core.set_embedder(_core.OpenAIEmbeddingAdapter(ecfg))
        core.worker.tick_one_batch("2026-06-27T09:00:00Z")   # embed only, keep volatile
        core.consolidation_llm = make_openai_llm(
            model="qwen-plus", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
        core.gist_thresholds = {"min_holders": 3, "min_replay_count": 1, "min_confidence": 0.0,
                                "similarity_threshold": threshold, "entity_gist_enabled": 0}
        rs = core.run_replay("sleep", now="2026-06-27T12:00:00Z")
        core.close()
        conn = sqlite3.connect(BASE)
        row = conn.execute("SELECT consolidation_summary FROM statements "
                           "WHERE provenance LIKE 'consolidation%'").fetchone()
        conn.close()
        summ = row[0] if row else None
        print(f"{label} [attempt {attempt}]: candidates={rs.get('gist_candidates')} "
              f"abstracted={rs.get('abstracted')} gated={rs.get('gist_gated')} "
              f"failed={rs.get('gist_failed')}" + (f"  summary={summ!r}" if summ else ""))
        if rs.get("abstracted"):
            best = summ
            break
    print(f"  => {label}: {'PROMOTED' if best else 'still gated after ' + str(attempts) + ' attempts'}")

# v2 semantic — varied objects (threshold 0.5). Pre-fix: hard 0.
run([("alice", "feels", "exhausted"), ("bob", "is", "very tired"), ("carol", "feels", "worn out"),
     ("dave", "is", "fatigued"), ("erin", "feels", "drained")], 0.5, "v2 TIRED (synonyms)")
run([("alice", "enjoys", "espresso"), ("bob", "loves", "cappuccino"), ("carol", "craves", "latte"),
     ("dave", "adores", "macchiato"), ("erin", "likes", "americano")], 0.5, "v2 COFFEE (varied)")
# v1 people-norm — SAME (predicate, object) exact cluster (threshold 0). Must NOT regress.
run([("alice", "knows", "coffee"), ("bob", "knows", "coffee"), ("carol", "knows", "coffee")],
    0.0, "v1 EXACT (same object)")
```

- [ ] **Step 2: Run it against the real LLM + embedder**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling-web
OPENAI_API_KEY="$DASHSCOPE_API_KEY" \
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1" \
timeout 400 .venv/bin/python "$CLAUDE_JOB_DIR/tmp/gist_judge_revalidate.py"
```
Expected (per the spec's realistic success bar — LLM is stochastic, so `attempts` retries):
- `v2 TIRED` and `v2 COFFEE` → `abstracted=1` on at least one attempt (pre-fix hard 0), with a CONCISE `summary` (e.g. "People feel tired." / "People enjoy coffee drinks.") that carries NO added scope clause.
- `v1 EXACT` → `abstracted=1` (no regression).
Do NOT print `DASHSCOPE_API_KEY`. If a v2 cluster is still only intermittent across the retries, record that honestly (the reworded judge produces concise summaries but end-to-end determinism is a further follow-up) rather than tuning further in this slice.

- [ ] **Step 3: Record results (no commit — ephemeral script)**

Capture the printed before/after + promoted summaries into the PR description. Nothing to commit for this task. Mark it complete in the ledger with the observed numbers + whether v2 promoted and v1 held.

---

## Self-Review

**1. Spec coverage:**
- Spec «Design: reword `kNormGistPromptTemplate`» → Task 1 Step 3 (verbatim). ✅
- Spec «single placeholder occurrences» → Task 1 constraint + guard test (`{holder_count}` absent). ✅
- Spec «Testing: existing green (no wording pin)» → Task 1 Step 5 + the noted pre-existing structural tests. ✅
- Spec «Testing: re-dogfood v2 promotes + v1 no regression + realistic stochastic bar» → Task 2. ✅
- Spec «Out of scope (entity judge / floor / threshold / default / verify prompts)» → Global Constraints; only `kNormGistPromptTemplate` + one test touched. ✅

**2. Placeholder scan:** No TBD/TODO; the reworded template + guard test + dogfood script are complete; commands have expected output. ✅

**3. Type consistency:** No new symbols. `build_norm_gist_prompt` / `GistCluster` / `sample_cluster()` referenced with their existing signatures. The guard test's pinned phrases (`"independent agreement IS the evidence"`, `"add no cause"`) appear verbatim in the Task 1 Step 3 template. The Candidate block `asserted by {holder_count} distinct holders: {holders}` is preserved so the pre-existing `"3 distinct holders"` / `"alice, bob, carol"` assertions still pass. ✅

## Execution Handoff

Execute via **superpowers:subagent-driven-development** (fresh implementer + task-reviewer per task, whole-branch review at the end), per project cadence. Then PR; CI green + explicit user 合并 before merge.
