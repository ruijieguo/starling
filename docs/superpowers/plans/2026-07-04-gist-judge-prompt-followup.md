# gist v2 Judge-Prompt Follow-up Implementation Plan

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
