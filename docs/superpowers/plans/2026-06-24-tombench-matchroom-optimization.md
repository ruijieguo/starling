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

# ToMBench match+room Optimization (L1 extraction quality + L2 confidence-gated definitive injection) Implementation Plan
> **当前评测进展（2026-09-17，写入修复与全量基线完成）**：C++坏时间容错及非流式截断/拒答识别已实现，94项C++和108项Python相关测试通过。49范围、473文档、7923话轮全部核验；qwen3.8-27b来源路径完整baseline为211/1031=20.47%，写入/回答失败0、裁判超时2，实际1848次HTTP、零重试。相较旧201/1031净增10题，其中恢复范围贡献8题；增益区间跨0，不宣称稳定质量提升。详见[本轮报告](../../eval/2026-09-17-socialmem-baseline-recovered.md)；旧默认结构路径及历史封存单列。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Starling's belief-digest injection a NET POSITIVE on the ToMBench match+room cells (Content false belief, Knowledge-attention) by fixing the two root causes the diagnostic found — wrong/fragmented digests — and stop it hurting non-fit questions, via a confidence-gated definitive injection.

**Architecture:** Three layers. **L2 (server):** drop the always-on raw dump; inject ONLY high-confidence computed content (chain/belief_digest/mental_state/faux_pas), definitively (not "reason step by step"); silent otherwise. **L1a (C++ `normalize_theme`):** strip leading quantifiers ("all"/"both"/"some") so theme variants ("all three toy" ≡ "three toy") merge instead of fragmenting the digest. **L1b (C++ reconstructor):** content-vs-label disambiguation for unexpected-contents so the digest computes the true content, not the re-extracted label.

**Tech Stack:** C++20 (`src/schema/`, `src/cognizer/`, gtest), Python (FastAPI eval server, pytest), the existing `what_does_X_think_chain` core op (unchanged), ToMEval harness (measurement).

## Global Constraints

- **Additive only**: must not regress the green baseline `ctest` 664 / `pytest` 658. `perceived_by_json` immutable; `canonicalize_*` bodies untouched (`normalize_theme` is the theme-side surface normalizer — extending its stoplist is in-scope).
- Core logic = C++ (L1a/L1b); the eval server (L2) is a thin adapter.
- TDD red→green→commit. Build from repo root: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build`; after C++ changes add `--python-editable` (+ `cmake --install build` if the editable import is stale); `ctest` via `.venv/bin/ctest --test-dir build`.
- Explicit-path `git add` (never `.`/`-A`); no `--no-verify`/`--amend`/push/merge.
- **Measurement tasks burn the deepseek API and need explicit user consent** — they are controller-run with the user present (marked CONSENT-GATED). Do NOT auto-run them inside subagent-driven execution.
- L1b is higher risk (the perception machinery is shared by #3/SP-A/SP-B). Its task assesses blast radius FIRST; if a fix breaks the perception/grounding ctests, STOP and report — do not force it.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `scripts/starling_tomeval_server.py` | L2: gated-definitive injection + digest self-consistency guard | 1 |
| `tests/python/test_tomeval_server_l2gate.py` | L2 unit tests (silent-fallback, definitive frame, thrash-skip) | 1 |
| `src/schema/normalize_theme.cpp` | L1a: strip leading quantifiers (repeated) | 2 |
| `tests/cpp/test_normalize_theme.cpp` | L1a ctest (quantifier merge + idempotence) | 2 |
| `src/cognizer/perception_reconstructor.cpp` | L1b: content-vs-label disambiguation | 4 |
| `tests/cpp/test_perception_reconstructor.cpp` (or the existing perception ctest) | L1b ctest (unexpected-contents) | 4 |

---

## Task 0: Confirm green baseline (controller)

- [ ] From repo root: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build && .venv/bin/ctest --test-dir build | tail -3 && .venv/bin/python -m pytest tests/python -q | tail -3`. Expected: ctest 664, pytest 658 passed. If red, STOP + report.
- [ ] Note the existing ToMBench 300-run numbers for later comparison: deepseek baseline = **82.3%**, Starling(current dump+digest) = **83.7%** (net +4/300, p=0.39). Results dirs: `/Users/jaredguo-mini/develop/ToMEval/results_{deepseek_baseline,starling}/ToMBench/.../exp_*/`.

---

## Task 1 (L2): Confidence-gated definitive injection + digest self-consistency guard

**Files:** Modify `scripts/starling_tomeval_server.py`; Create `tests/python/test_tomeval_server_l2gate.py`.

**Interfaces:**
- Consumes: existing `_chain_injection_for`, `_belief_digest_for(mem, db_path, user_content)`, `_mental_state_injection_for`, `_faux_pas_injection_for`, `_memory_dump`, `_distinct_perc(db_path, tenant, col)`, `_new_adapter`.
- Produces: `_starling_memory_for(story, user_content)` now returns ONLY computed content or `""` (no raw dump); `_answer(system, user, memdump)` uses a definitive frame when memdump is non-empty; `_belief_digest_for` skips themes whose perception "thrashes" (a value reappears after changing).

### Step 1: Read the current code to match exactly
- [ ] Read `scripts/starling_tomeval_server.py`: `_answer` (around lines 347-371 — the `"reason step by step"` frame), `_starling_memory_for` (around 376-396 — `dump = _memory_dump(...)` then `extra = (chain or ...)` then `return (dump + "\n\n" + extra) if extra else dump`), and `_belief_digest_for` (around 335-373 — the per-theme `bel`/`actual`/`stale` loop). Confirm exact line content before editing.

### Step 2: Write the failing unit tests `tests/python/test_tomeval_server_l2gate.py`
```python
import importlib.util
_spec = importlib.util.spec_from_file_location("srv", "scripts/starling_tomeval_server.py")
srv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(srv)

def test_answer_definitive_frame_no_reason_step():
    # when memory content is present, the frame is definitive, not "reason step by step"
    p = srv._answer("SYS", "USER", "FACTS")
    assert "FACTS" in p
    assert "reason step by step" not in p.lower()
    assert "do not re-derive" in p.lower() or "use them directly" in p.lower()

def test_answer_silent_when_no_memory():
    # no computed content -> just the question, no scaffold block
    p = srv._answer("SYS", "USER", "")
    assert "FACTS" not in p
    assert "[" not in p  # no injected memory block

def test_thrash_guard():
    # a theme whose values reappear after changing (cabbage->hat->cabbage) is low-confidence
    assert srv._thrashes(["cabbage", "cabbage", "hat", "hat", "cabbage"]) is True
    assert srv._thrashes(["basket", "basket", "box"]) is False
    assert srv._thrashes(["box"]) is False
    assert srv._thrashes([]) is False
```

### Step 3: Run → FAIL (`_thrashes` undefined; `_answer` still has reason-step).
Run: `.venv/bin/python -m pytest tests/python/test_tomeval_server_l2gate.py -v`

### Step 4: Implement `_thrashes` + the definitive `_answer` + the silent gate.
- [ ] Add the thrash helper (near `_belief_digest_for`):
```python
def _thrashes(values) -> bool:
    """A theme's perception 'thrashes' if a value reappears after changing
    (A...B...A) — a sign of label/content conflation (e.g. cabbage->hat->cabbage).
    Collapse consecutive duplicates, then a repeat means thrash."""
    seq = []
    for v in values:
        if not seq or seq[-1] != v:
            seq.append(v)
    return len(seq) != len(set(seq))
```
- [ ] In `_belief_digest_for`, BEFORE emitting a theme's line, skip it if its raw perception thrashes. Inside the `for T in themes:` loop, after computing `bel`, add:
```python
            # self-consistency guard: skip a theme whose perception thrashes
            con = sqlite3.connect(db_path)
            try:
                vals = [r[0] for r in con.execute(
                    "SELECT state_value FROM perception_state WHERE tenant_id=? AND theme_id=? "
                    "ORDER BY position", (tenant, T)).fetchall()]
            finally:
                con.close()
            if _thrashes(vals):
                continue
```
(Place this right after `bel`/`actual`/`stale` are computed and before `seg = ...`. Match the exact local variable names — `db_path`, `tenant`, `T` — already in scope per the current `_belief_digest_for` signature `(mem, db_path, user_content)`.)
- [ ] Replace `_answer`'s memdump block with a definitive frame (drop "reason step by step"):
```python
    if memdump:
        prompt += (
            "\n\n[Verified facts my memory computed — these are correct; use them "
            f"directly to answer, do not re-derive them]\n{memdump}\n\n"
            "Give the final answer as \\boxed{X}.")
```
- [ ] Rewrite `_starling_memory_for`'s return to drop the always-on dump — inject only computed content, else silent:
```python
        mem.remember(story)
        chain = _chain_injection_for(mem, user_content)
        computed = (chain
                    or _belief_digest_for(mem, db_path, user_content)
                    or _mental_state_injection_for(mem, user_content)
                    or _faux_pas_injection_for(mem, user_content))
        return computed  # "" -> silent (= raw baseline); the raw dump is no longer injected
```
(Remove the now-unused `dump = _memory_dump(...)` line in this function. Leave `_memory_dump` defined — other call sites / future use; just stop calling it here.)

### Step 5: Run unit tests → PASS.
Run: `.venv/bin/python -m pytest tests/python/test_tomeval_server_l2gate.py -v`

### Step 6: Regression — sibling server tests still green (gating/precedence intact).
Run: `.venv/bin/python -m pytest tests/python/test_tomeval_server_chain.py tests/python/test_tomeval_server_mentalstate.py tests/python/test_tomeval_server_fauxpas.py tests/python/test_tomeval_server_belief.py -q` → all pass. Then `.venv/bin/python -m pytest tests/python -q | tail -3` → still 658+ green.

### Step 7: Commit
```bash
git add scripts/starling_tomeval_server.py tests/python/test_tomeval_server_l2gate.py
git commit -F - <<'EOF'
feat(eval/L2): confidence-gated definitive injection + digest thrash guard

Drop the always-on raw dump; inject ONLY computed content (chain/belief_digest/
mental_state/faux_pas), definitively (no "reason step by step"); silent otherwise
(= baseline) so non-fit questions can't be dragged. Skip belief-digest themes whose
perception thrashes (A->B->A label/content conflation) so a wrong fact isn't injected.

EOF
```

---

## Task 2 (L1a): `normalize_theme` strips leading quantifiers

**Files:** Modify `src/schema/normalize_theme.cpp`; Modify/Create `tests/cpp/test_normalize_theme.cpp`.

**Interfaces:**
- Consumes: `starling::schema::normalize_theme(std::string_view) -> std::string` (signature unchanged, `include/starling/schema/normalize_theme.hpp`).
- Produces: `normalize_theme` now strips leading quantifiers repeatedly, so `"all three toys"`, `"three toys"`, `"all the three toy"` all normalize to `"three toy"`.

### Step 1: Find the existing ctest
- [ ] `grep -rln "normalize_theme" tests/cpp/` — find the existing normalize_theme ctest (the grounding work `8ffeb0a` added one). If none, create `tests/cpp/test_normalize_theme.cpp` and register it in `tests/cpp/CMakeLists.txt`. Read it to match the test style.

### Step 2: Write the failing ctest (add to the existing normalize_theme test file)
```cpp
TEST(NormalizeTheme, StripsLeadingQuantifiersAndMerges) {
    using starling::schema::normalize_theme;
    EXPECT_EQ(normalize_theme("all three toys"), "three toy");
    EXPECT_EQ(normalize_theme("three toys"),     "three toy");
    EXPECT_EQ(normalize_theme("all three toy"),  "three toy");
    EXPECT_EQ(normalize_theme("both hands"),     "hand");
    EXPECT_EQ(normalize_theme("all the marbles"),"marble");
    // idempotent + does not over-strip a bare word that merely starts with a determiner-like token
    EXPECT_EQ(normalize_theme("three toy"),      "three toy");
    EXPECT_EQ(normalize_theme("allowance"),      "allowance");  // "all" without a space boundary is untouched
}
```

### Step 3: Build → FAIL (`all three toy` != `three toy`).
Run: `.venv/bin/ctest --test-dir build -R NormalizeTheme --output-on-failure` (after a build).

### Step 4: Implement — make the leading-strip a repeated loop with quantifiers.
In `src/schema/normalize_theme.cpp`, replace the single-article strip block (the `for (std::string_view art : {"the ", "a ", "an "}) { ... break; }`) with a repeated strip over an extended determiner list:
```cpp
    bool stripped = true;
    while (stripped) {
        stripped = false;
        for (std::string_view det : {"the ", "a ", "an ", "all ", "both ", "some "}) {
            if (s.size() > det.size() && s.compare(0, det.size(), det) == 0) {
                s = s.substr(det.size());
                while (!s.empty() && std::isspace(static_cast<unsigned char>(s.front()))) s.erase(s.begin());
                stripped = true;
                break;
            }
        }
    }
```
(The trailing-space in each token ensures `"allowance"` — no space after `all` — is NOT stripped. `singularize(s)` already runs after and turns `"three toys"`→`"three toy"`.)

### Step 5: Build + run ctest → PASS.
Run: `.venv/bin/python scripts/configure_build.py --build --build-dir build && .venv/bin/ctest --test-dir build -R NormalizeTheme --output-on-failure`

### Step 6: Regression — grounding/theme ctests + the editable rebuild.
Run: `.venv/bin/ctest --test-dir build -R "Grounding|Normalize|Theme|Perception" --output-on-failure` → green. Then `.venv/bin/python scripts/configure_build.py --build --python-editable --build-dir build` (the server uses the editable package for `normalize_theme` via remember). Then `.venv/bin/python -m pytest tests/python -q | tail -3` → 658+ green.

### Step 7: Commit
```bash
git add src/schema/normalize_theme.cpp tests/cpp/test_normalize_theme.cpp
git commit -F - <<'EOF'
feat(schema/L1a): normalize_theme strips leading quantifiers (all/both/some)

Merge theme surface variants ("all three toys" == "three toys" == "three toy")
so multi-agent perception isn't fragmented into contradictory themes (the
Knowledge-attention digest split "three toy"@tray vs "all three toy"@plate).
Repeated leading-determiner strip; space-bounded so "allowance" is untouched.

EOF
```

---

## Task 3 (measure-1): re-measure with L1a+L2 — CONSENT-GATED (controller, user present)

> Do NOT run inside subagent-driven execution. The controller runs this with the user, because it burns the deepseek API.

- [ ] Restart the server with the editable build + deepseek env (per the session's recipe): `eval "$(grep -E '^export (DEEPSEEK_API_KEY|DEEPSEEK_BASE_URL)=' ~/.zshrc)"; export OPENAI_API_KEY=$DEEPSEEK_API_KEY OPENAI_BASE_URL=$DEEPSEEK_BASE_URL/v1; .venv/bin/python -m uvicorn scripts.starling_tomeval_server:app --port 8900`.
- [ ] Run the focused fit-family comparison on the SAME seeded items. Reuse `/Users/jaredguo-mini/develop/ToMEval/cfg_starling_ToMBench_fit.yaml` (Starling, port 8900) and `cfg_deepseek_ToMBench_fit.yaml` (deepseek baseline, **max_workers: 6** to avoid the HTTP/2-under-concurrency failure). Both `max_samples: 300` (seed 42 → same items). Baseline already exists (82.3%); re-run only Starling: `cd /Users/jaredguo-mini/develop/ToMEval && .venv/bin/python tasks/ToMBench/run.py --experiment-config cfg_starling_ToMBench_fit.yaml`.
- [ ] Paired McNemar vs baseline (reuse the session's analysis: parse `\boxed{}` from `prediction.jsonl`, pair by `sample_id`, `b01` vs `b10`, chi2/p). Report: overall delta + Belief/Knowledge by_ability delta + the negative-case count (should drop — L2 recovers them by construction). Decide GO/NO-GO for L1b based on whether the fit cells moved.

---

## Task 4 (L1b): content-vs-label disambiguation — HIGHER RISK, blast-radius-first

**Files:** Modify `src/cognizer/perception_reconstructor.cpp`; Modify the perception ctest.

**Interfaces:**
- Consumes: the episodic-event stream + the content-dim convention (B-phase commits `b3e27d3` episodic prompt, `dcefd50` content-dim perception, `52227d1` second-order). 
- Produces: for an unexpected-contents scene, a cognizer who has NOT opened the container perceives content = the LABEL (their false belief); a cognizer who HAS opened perceives content = the actual content. The label is NOT re-emitted as a later content perception (no A→B→A thrash).

### Step 1: Blast-radius assessment (do this FIRST, report before editing)
- [ ] Read `src/cognizer/perception_reconstructor.cpp` + grep for where content-dim perception rows are emitted (`grep -n "content" src/cognizer/perception_reconstructor.cpp`). Trace how the label and the opened content both become content-dim rows, and WHY the label re-appears at a later position (the diagnostic showed cabbage@p1 → hat@p2 → cabbage@p6). Identify the exact emission point.
- [ ] List every ctest that exercises the reconstructor/perception (`grep -rln "PerceptionReconstructor\|perception_state\|what_does_X_think\|content" tests/cpp/`). The fix MUST keep all of them green. If the only way to fix the re-emission also changes location-dim or second-order behavior used by #3/SP-A/SP-B, STOP and report the conflict — do not force it.

### Step 2: Write the failing ctest (unexpected-contents, add to the perception ctest file)
Mirror the existing perception-ctest seed style (episodic events → reconstruct → assert perception_state). Seed: a labeled container ("handbag" label "cabbage"); cognizer A opens it and sees "hat"; cognizer B never opens it. Assert:
```cpp
// after reconstruct, for theme "handbag" content dim:
//  - B's last-perceived content == "cabbage"  (label-belief; never opened)
//  - A's last-perceived content == "hat"       (opened-truth)
//  - the highest-position content for the theme is "hat" (NOT a re-emitted "cabbage")
```
(Use the exact assertion API the existing perception ctest uses — `what_does_X_think` or a direct perception_state query. Match the file's seed helpers; do not invent a new harness.)

### Step 3: Build → FAIL (label re-emitted; highest-position content == cabbage).

### Step 4: Implement the disambiguation in `perception_reconstructor.cpp`
Fix the emission so the label seeds the INITIAL content-belief for all present cognizers, and OPENING updates only the opener's content to the actual — and the label is NOT re-emitted as a later content row. (Exact change found in Step 1; the contract is: no A→B→A content thrash for a theme; opener sees truth, non-opener keeps label.) Keep location-dim emission unchanged.

### Step 5: Build + run the new ctest → PASS.
Run: `.venv/bin/python scripts/configure_build.py --build --build-dir build && .venv/bin/ctest --test-dir build -R "Perception|Reconstruct|Content" --output-on-failure`

### Step 6: Full ctest regression (the shared-machinery guard).
Run: `.venv/bin/ctest --test-dir build | tail -3` → still 664+ (additive). If ANY previously-green ctest fails, the fix has unacceptable blast radius → STOP and report (do not weaken other tests to pass). Then `--python-editable` rebuild + `.venv/bin/python -m pytest tests/python -q | tail -3` → 658+ green.

### Step 7: Commit
```bash
git add src/cognizer/perception_reconstructor.cpp tests/cpp/<perception_test_file>.cpp
git commit -F - <<'EOF'
feat(cognizer/L1b): content-vs-label disambiguation for unexpected-contents

A labeled container seeds the initial content-BELIEF (= label) for present
cognizers; opening updates only the opener's content to the truth. Stop
re-emitting the label as a later content perception (the cabbage->hat->cabbage
thrash that made the belief-digest compute the wrong content). Location-dim
unchanged; additive — full ctest stays green.

EOF
```

---

## Task 5 (measure-2): final re-measure — CONSENT-GATED (controller, user present)

> Same as Task 3, after L1b. Burns the API — controller-run with the user.

- [ ] Rebuild editable + restart the server. Re-run `cfg_starling_ToMBench_fit.yaml` (300 seeded items). Paired McNemar vs the 82.3% baseline.
- [ ] Report the final numbers: overall delta + Content-false-belief / Knowledge-attention by_ability delta + negative-case count. This is the "确切有效" verdict for L1+L2. Compare to the pre-optimization +4/300 (p=0.39). Honest write-up (significant or not, by how much).

---

## Final: review + handoff
After Task 4 (and the consent-gated measures): dispatch a final code-reviewer over the L1+L2 diff (server thinness, normalize_theme over-strip risk, reconstructor blast radius, no ctest/pytest regression). STOP before push/merge/roadmap (need consent). `appraise_emotion` is a SEPARATE follow-on plan (the user sequenced L1+L2 first, appraise after) — not in this plan.
