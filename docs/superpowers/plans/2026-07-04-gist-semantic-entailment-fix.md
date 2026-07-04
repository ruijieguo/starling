# gist v2 Semantic Entailment Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Phase-4 per-member entailment gate — for semantic clusters only (`member_objects.size() > 1`, always people-norm) — with a single set-level faithful-generalization check, so gist v2 semantic clustering can promote faithful gists instead of gating all of them.

**Architecture:** `gate_candidate` (`gist_writer.cpp`, file-static) branches on `cluster.member_objects.size() > 1`. A semantic cluster now makes ONE entailment call using a new `build_semantic_entailment_prompt` that lists all member objects and asks for a faithful generalization (coverage + tightness); exact + entity clusters keep the existing per-object loop byte-for-byte. The new prompt reuses the existing `{"entailed": <bool>}` reply shape, so `parse_entailment_verdict` / `EntailmentVerdict` are unchanged.

**Tech Stack:** C++20 kernel (`src/replay/`, `include/starling/replay/`), GoogleTest (`tests/cpp/`), pybind11 `_core`, DashScope (qwen-plus + text-embedding-v3) for the manual re-dogfood.

**Approved spec:** `docs/superpowers/specs/2026-07-04-gist-semantic-entailment-fix-design.md` (branch `feat/gist-semantic-entailment` @ `b7941bf`).

## Global Constraints

- **架构边界(硬):** entailment 是核心 consolidation 语义 → 实现于 C++ 核心(`src/` + `include/starling/`);prompt 是 single-source C++ 常量,**不是** Python/binding config。
- **Behavior-neutral(exact + entity):** exact + entity cluster(`member_objects` 空)走 else-branch,字节等价。语义 cluster 之前 100%-gated + v2 default-OFF → 生产零行为变化。**已有 exact/entity 的 gist 测试无改动即绿。**
- **语义机制变更(预期,非回归):** 现有测试 `GistWriter.PerMemberEntailmentGatesSemanticFalseMerge`(`tests/cpp/test_gist_writer.cpp:613`)钉的是旧的**逐成员**机制;它按设计被本修复取代 → Task 2 **重写**它为 set-level 机制。这是本 slice 唯一预期改动的既有测试。
- **复用不新增:** `parse_entailment_verdict` + `EntailmentVerdict{bool entailed, bool ok}` 形状不变(`{entailed}` bool)。
- **构建:** `python scripts/configure_build.py --build --python-editable`(`gist_prompt`/`gist_writer` 在 `starling_core`;Python re-dogfood 需 `_core` 同步——只 `pip install -e .` 不够)。**提交门:全量 `ctest` + `pytest tests/python` 绿。**
- **clang-tidy(CI-only 门),新 C++ clean by construction:** identifier-length ≥ 3、`[[nodiscard]]` 新 builder、无 raw-pointer 算术、designated aggregate init、无 NEW const/ref 数据成员、无 empty/comment-only catch、`bugprone-branch-clone`(两分支勿完全相同——本修复天然不同)。
- **git:** 显式路径 `git add`(禁 `git add .` / `-A`);不用 `--no-verify` / `--amend`。commit message 末尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `include/starling/replay/gist_prompt.hpp` | prompt builder + verdict declarations | Declare `build_semantic_entailment_prompt`; fix the stale per-member comment on `build_entailment_prompt`. |
| `src/replay/gist_prompt.cpp` | single-source prompt templates + builders | Add `kSemanticEntailmentTemplate` + `build_semantic_entailment_prompt`. |
| `src/replay/gist_writer.cpp` | Phase-3/4 judge+gate + write | Branch `gate_candidate` on `member_objects.size() > 1`. |
| `tests/cpp/test_gist_prompt.cpp` | prompt-builder unit tests | Add a `build_semantic_entailment_prompt` test. |
| `tests/cpp/test_gist_writer.cpp` | gate/write tests | Rewrite `PerMemberEntailmentGatesSemanticFalseMerge`; add set-level promote + recording tests. |

No changes to clustering, scheduler, bindings, or Python core.

---

### Task 1: Set-level semantic entailment prompt + builder

**Files:**
- Modify: `include/starling/replay/gist_prompt.hpp` (declare builder; fix stale comment)
- Modify: `src/replay/gist_prompt.cpp` (template + builder)
- Test: `tests/cpp/test_gist_prompt.cpp`

**Interfaces:**
- Consumes: `GistCluster{ predicate, member_objects (distinct object strings), holder_ids }` (`gist_clustering.hpp:18`); anonymous-namespace helpers `replace_first`, `join_with_commas` (`gist_prompt.cpp` — same TU, directly callable).
- Produces: `[[nodiscard]] std::string build_semantic_entailment_prompt(const GistCluster& cluster, std::string_view summary);` — a filled prompt whose reply is the existing `{"entailed": <bool>}` shape.

- [ ] **Step 1: Write the failing test**

Add to `tests/cpp/test_gist_prompt.cpp` (include `gist_prompt.hpp` + `gist_clustering.hpp` are already used there). Mirror the file's existing style:

```cpp
// Set-level semantic entailment prompt: lists EVERY varied member object (joined),
// fills holder_count/predicate/summary, and leaves no residual {placeholder}.
TEST(GistPrompt, SemanticEntailmentListsAllObjectsNoResidualPlaceholders) {
    starling::replay::GistCluster cluster;
    cluster.predicate = "enjoys";
    cluster.holder_ids = {"alice", "bob", "carol"};
    cluster.member_objects = {"espresso", "cappuccino", "latte"};

    const std::string prompt = starling::replay::build_semantic_entailment_prompt(
        cluster, "People enjoy coffee drinks.");

    // Every varied object appears.
    EXPECT_NE(prompt.find("espresso"), std::string::npos);
    EXPECT_NE(prompt.find("cappuccino"), std::string::npos);
    EXPECT_NE(prompt.find("latte"), std::string::npos);
    // predicate, holder_count, summary all filled.
    EXPECT_NE(prompt.find("enjoys"), std::string::npos);
    EXPECT_NE(prompt.find("3"), std::string::npos);                       // holder_count
    EXPECT_NE(prompt.find("People enjoy coffee drinks."), std::string::npos);
    // Reuses the existing verdict contract.
    EXPECT_NE(prompt.find("entailed"), std::string::npos);
    // No residual template placeholders.
    EXPECT_EQ(prompt.find("{objects}"), std::string::npos);
    EXPECT_EQ(prompt.find("{predicate}"), std::string::npos);
    EXPECT_EQ(prompt.find("{holder_count}"), std::string::npos);
    EXPECT_EQ(prompt.find("{summary}"), std::string::npos);
}
```

- [ ] **Step 2: Run the test to verify it fails (build error — function undeclared)**

Run: `python scripts/configure_build.py --build 2>&1 | tail -20`
Expected: compile error — `build_semantic_entailment_prompt` not declared. (This is the TDD red; the symbol does not exist yet.)

- [ ] **Step 3: Declare the builder + fix the stale comment in the header**

In `include/starling/replay/gist_prompt.hpp`, replace the comment block on `build_entailment_prompt` (currently lines 35-40) so it no longer claims the semantic path is per-member, and add the new declaration:

```cpp
// `object` is the single member phrasing checked this call. EXACT / entity clusters
// call this once with the shared object_value. (Semantic clusters — varied objects —
// use build_semantic_entailment_prompt instead; see gate_candidate.)
[[nodiscard]] std::string build_entailment_prompt(const GistCluster& cluster,
                                                  std::string_view object,
                                                  std::string_view summary);

// #38-C v2 semantic-cluster entailment (set-level). A semantic cluster groups the SAME
// predicate over VARIED objects; a summary generalizing across them is never entailed by
// any single object, so per-object verification structurally rejects every semantic gist.
// This lists ALL member objects and asks for a FAITHFUL GENERALIZATION — coverage (every
// object is an instance of the summary) AND tightness (no scope broader than the set).
[[nodiscard]] std::string build_semantic_entailment_prompt(const GistCluster& cluster,
                                                           std::string_view summary);
```

- [ ] **Step 4: Add the template + builder in `src/replay/gist_prompt.cpp`**

Add the template inside the anonymous namespace, after `kEntailmentPromptTemplate` (near line 43):

```cpp
// #38-C v2 set-level semantic entailment. Lists every varied member object and asks the
// verifier to confirm the summary FAITHFULLY GENERALIZES the set: coverage (each object
// is an instance) + tightness (no scope broader than the set warrants). Reuses the
// {entailed} reply shape → parse_entailment_verdict unchanged.
constexpr std::string_view kSemanticEntailmentTemplate =
    R"PROMPT(You are the verification faculty of a memory system. A consolidation step produced a candidate NORM summary generalizing over {holder_count} distinct holders who each INDEPENDENTLY assert a related belief with the SAME predicate ({predicate}) but VARIED objects:
  {objects}
Check whether the summary is a FAITHFUL GENERALIZATION of this set — (a) COVERAGE: every listed object is an instance or case of the summary; (b) TIGHTNESS: the summary introduces no scope, claim, category, or detail broader than this set of objects warrants. If ANY listed object is not an instance of the summary, or the summary over-reaches beyond what the set supports, it is NOT faithful.

Candidate summary: {summary}

Reply with ONLY a JSON object (no prose, no markdown):
{"entailed": <true if the summary covers EVERY listed object AND stays within the set's scope; false otherwise>}
)PROMPT";
```

Add the builder as a public function (outside the anonymous namespace), next to `build_entailment_prompt` (after line 171):

```cpp
std::string build_semantic_entailment_prompt(const GistCluster& cluster,
                                             std::string_view summary) {
    std::string prompt(kSemanticEntailmentTemplate);
    replace_first(prompt, "{holder_count}", std::to_string(cluster.holder_ids.size()));
    replace_first(prompt, "{predicate}", cluster.predicate);
    replace_first(prompt, "{objects}", join_with_commas(cluster.member_objects));
    replace_first(prompt, "{summary}", summary);
    return prompt;
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R GistPrompt --output-on-failure 2>&1 | tail -20`
Expected: `GistPrompt.SemanticEntailmentListsAllObjectsNoResidualPlaceholders` PASS (and the pre-existing GistPrompt tests still PASS).

- [ ] **Step 6: Commit**

```bash
git add include/starling/replay/gist_prompt.hpp src/replay/gist_prompt.cpp tests/cpp/test_gist_prompt.cpp
git commit -m "feat(gist): set-level semantic entailment prompt + builder

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Branch `gate_candidate` on semantic clusters

**Files:**
- Modify: `src/replay/gist_writer.cpp:104-127` (`gate_candidate`)
- Test: `tests/cpp/test_gist_writer.cpp` (rewrite one test, add two)

**Interfaces:**
- Consumes: `build_semantic_entailment_prompt` (Task 1); `build_entailment_prompt`, `parse_entailment_verdict`, `EntailmentVerdict` (unchanged); `GistCluster.member_objects`; test helpers `seed`, `find_semantic_gist_clusters`, `SqliteBlobVectorIndex`, `SequencedLLM` (all already in `test_gist_writer.cpp`).
- Produces: no new public symbol. `gate_candidate` (file-static) is exercised through the public `write_gist_proposals`.

- [ ] **Step 1: Rewrite the breaking test to the set-level mechanism**

`gate_candidate`'s current per-member loop makes N entailment calls for a semantic cluster; `GistWriter.PerMemberEntailmentGatesSemanticFalseMerge` (`test_gist_writer.cpp:613-648`) pins that by feeding a `SequencedLLM` 4 replies (1 judge + 3 members). After this task a semantic cluster makes exactly 1 set-level call, so that test must be rewritten. Replace it (same seed/vector setup) with the two behaviours below. **First, extend `SequencedLLM` to record the prompts it receives** so a test can assert the set-level prompt shape — change its `extract` (lines 104-109) to:

```cpp
    starling::extractor::LLMResponse extract(std::string_view prompt,
                                             std::string_view) override {
        seen_prompts.emplace_back(prompt);
        if (next_ < replies_.size()) {
            return replies_[next_++];
        }
        return starling::extractor::LLMResponse{.ok = false, .error = "seq_exhausted"};
    }
    std::vector<std::string> seen_prompts;   // prompts received, in call order
```

Replace `TEST(GistWriter, PerMemberEntailmentGatesSemanticFalseMerge)` with:

```cpp
// #38-C v2 (fixed): a SEMANTIC cluster is verified by ONE set-level faithful-generalization
// call, NOT per member. The sequence gives a set-level FALSE then a would-be second reply;
// only the FALSE is consumed (gated), proving a single entailment call. The recorded prompt
// carries every varied object (the set-level builder was used).
TEST(GistWriter, SemanticSetLevelEntailmentGatesFalseMerge) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed(db, {.id = "m1", .holder = "alice", .hashfill = 'a', .state = "consolidated",
              .object_value = "code review"});
    seed(db, {.id = "m2", .holder = "bob", .hashfill = 'b', .state = "consolidated",
              .object_value = "reviewing code"});
    seed(db, {.id = "m3", .holder = "carol", .hashfill = 'c', .state = "consolidated",
              .object_value = "pull-request review"});
    starling::vector::SqliteBlobVectorIndex index;
    index.insert(conn, "m1", "default", {1.0F, 0.0F});
    index.insert(conn, "m2", "default", {0.99F, 0.10F});
    index.insert(conn, "m3", "default", {0.98F, 0.15F});

    const GistThresholds cfg{.min_distinct_holders = 3, .min_replay_count = 1,
                             .min_confidence = 0.6, .similarity_threshold = 0.8};
    const auto clusters =
        find_semantic_gist_clusters(conn, index, "default", {"m1", "m2", "m3"}, cfg, {});
    ASSERT_EQ(clusters.size(), 1U);
    ASSERT_EQ(clusters[0].member_objects.size(), 3U);   // varied → set-level gate engages

    // judge passes floor; set-level entailment FALSE → gated. A trailing reply proves the
    // gate does NOT make a second (per-member) call — it stays unconsumed.
    SequencedLLM llm({
        starling::extractor::LLMResponse{.raw_xml = R"({"confidence":0.9,"summary":"value review"})",
                                         .ok = true},
        starling::extractor::LLMResponse{.raw_xml = R"({"entailed": false})", .ok = true},
        starling::extractor::LLMResponse{.raw_xml = R"({"entailed": true})", .ok = true},  // must stay unused
    });
    const auto outcome = write_gist_proposals(
        *adapter, {{.tenant_id = "default", .cluster = clusters[0]}}, "2026-06-28T12:00:00Z", &llm);
    EXPECT_EQ(outcome.gated, 1);
    EXPECT_EQ(outcome.written, 0);
    // Exactly two prompts: judge + ONE set-level entailment (not 1 + 3).
    ASSERT_EQ(llm.seen_prompts.size(), 2U);
    // The entailment prompt is the set-level one: it names every varied object.
    EXPECT_NE(llm.seen_prompts[1].find("code review"), std::string::npos);
    EXPECT_NE(llm.seen_prompts[1].find("reviewing code"), std::string::npos);
    EXPECT_NE(llm.seen_prompts[1].find("pull-request review"), std::string::npos);
}

// Converse: a semantic cluster whose set-level entailment is TRUE is promoted — the fix
// lets faithful semantic gists through (pre-fix they were 100% gated). The trailing FALSE
// reply again stays unconsumed, proving a single entailment call.
TEST(GistWriter, SemanticSetLevelEntailmentPromotes) {
    auto adapter = SqliteAdapter::open(":memory:");
    auto& conn = adapter->connection();
    sqlite3* db = conn.raw();
    seed(db, {.id = "m1", .holder = "alice", .hashfill = 'a', .state = "consolidated",
              .object_value = "code review"});
    seed(db, {.id = "m2", .holder = "bob", .hashfill = 'b', .state = "consolidated",
              .object_value = "reviewing code"});
    seed(db, {.id = "m3", .holder = "carol", .hashfill = 'c', .state = "consolidated",
              .object_value = "pull-request review"});
    starling::vector::SqliteBlobVectorIndex index;
    index.insert(conn, "m1", "default", {1.0F, 0.0F});
    index.insert(conn, "m2", "default", {0.99F, 0.10F});
    index.insert(conn, "m3", "default", {0.98F, 0.15F});

    const GistThresholds cfg{.min_distinct_holders = 3, .min_replay_count = 1,
                             .min_confidence = 0.6, .similarity_threshold = 0.8};
    const auto clusters =
        find_semantic_gist_clusters(conn, index, "default", {"m1", "m2", "m3"}, cfg, {});
    ASSERT_EQ(clusters.size(), 1U);

    SequencedLLM llm({
        starling::extractor::LLMResponse{.raw_xml = R"({"confidence":0.9,"summary":"people review code"})",
                                         .ok = true},
        starling::extractor::LLMResponse{.raw_xml = R"({"entailed": true})", .ok = true},
        starling::extractor::LLMResponse{.raw_xml = R"({"entailed": false})", .ok = true},  // must stay unused
    });
    const auto outcome = write_gist_proposals(
        *adapter, {{.tenant_id = "default", .cluster = clusters[0]}}, "2026-06-28T12:00:00Z", &llm);
    EXPECT_EQ(outcome.written, 1);
    EXPECT_EQ(outcome.gated, 0);
    ASSERT_EQ(llm.seen_prompts.size(), 2U);   // one judge + one set-level entailment
    EXPECT_EQ(col_int(conn.raw(),
                      std::string("SELECT COUNT(*) FROM statements ") + kGistWhere), 1);
}
```

- [ ] **Step 2: Run the tests to verify they fail (old gate still per-member)**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R GistWriter --output-on-failure 2>&1 | tail -30`
Expected: `SemanticSetLevelEntailmentGatesFalseMerge` FAILS — with the old per-member loop, the judge + m1(true→uses 2nd reply `false`?)… concretely: old code consumes reply[1]=`false` on the FIRST member → gates, but makes 3 member calls → `seen_prompts.size()` becomes 2 only if it short-circuits on the first false. It gates on member 1 (`false`), so `seen_prompts.size()==2` may hold, BUT `seen_prompts[1]` is the per-object prompt for `"code review"` only — it will NOT contain `"reviewing code"` / `"pull-request review"` → the object assertions FAIL. `SemanticSetLevelEntailmentPromotes` FAILS: old code consumes reply[1]=`true` (member 1), reply[2]=`false` (member 2) → gated, not written → `outcome.written==0` fails. Both red as required.

- [ ] **Step 3: Implement the `gate_candidate` branch**

In `src/replay/gist_writer.cpp`, replace the per-member loop (the block at lines ~111-125, from the `// Per-member entailment` comment through the closing `}` before `return GateDecision::Pass;`) with:

```cpp
    // Phase-4 entailment (#38-C v2 false-merge safety). Semantic clusters (varied objects)
    // use ONE set-level faithful-generalization check — a summary that generalizes across
    // varied objects is never entailed by any single object, so per-object verification
    // structurally rejects every semantic gist. Exact / entity clusters (member_objects
    // empty, or a degenerate single object) keep the per-object check unchanged.
    if (cluster.member_objects.size() > 1) {
        const extractor::LLMResponse verify_resp =
            gist_llm.generate(build_semantic_entailment_prompt(cluster, judgment.summary));
        if (!verify_resp.ok) { return GateDecision::Failed; }
        const EntailmentVerdict verdict = parse_entailment_verdict(verify_resp.raw_xml);
        if (!verdict.ok) { return GateDecision::Failed; }
        if (!verdict.entailed) { return GateDecision::Gated; }
    } else {
        const std::vector<std::string> objects =
            cluster.member_objects.empty() ? std::vector<std::string>{cluster.object_value}
                                           : cluster.member_objects;
        for (const auto& object : objects) {
            const extractor::LLMResponse verify_resp =
                gist_llm.generate(build_entailment_prompt(cluster, object, judgment.summary));
            if (!verify_resp.ok) { return GateDecision::Failed; }
            const EntailmentVerdict verdict = parse_entailment_verdict(verify_resp.raw_xml);
            if (!verdict.ok) { return GateDecision::Failed; }
            if (!verdict.entailed) { return GateDecision::Gated; }
        }
    }
    return GateDecision::Pass;
```

- [ ] **Step 4: Run the gist tests to verify they pass (and exact/entity unchanged)**

Run: `python scripts/configure_build.py --build && ctest --test-dir build -R "GistWriter|GistClustering|GistPrompt" --output-on-failure 2>&1 | tail -30`
Expected: `SemanticSetLevelEntailmentGatesFalseMerge` + `SemanticSetLevelEntailmentPromotes` PASS. All pre-existing exact/entity tests (`LlmJudgedGistGetsConfidenceAndSummary`, `NotEntailedSummaryGated`, `EntailmentVerifyIndependentlyGates`, `EntailmentVerifyIndependentlyPasses`, `EntityGistKeepsSpecificSubject`, `ConfidenceAtFloorPasses`, …) PASS **unchanged** (behavior-neutral for the exact/entity path).

- [ ] **Step 5: Full suite gate**

Run: `python scripts/configure_build.py --build --python-editable && ctest --test-dir build --output-on-failure 2>&1 | tail -15 && .venv/bin/python -m pytest tests/python -q 2>&1 | tail -15`
Expected: full `ctest` green; `pytest tests/python` green (the `--python-editable` reinstall keeps `_core` in sync — no Python behavior changed, existing gist parity tests stay green).

- [ ] **Step 6: Commit**

```bash
git add src/replay/gist_writer.cpp tests/cpp/test_gist_writer.cpp
git commit -m "fix(gist): set-level entailment for semantic clusters (unblocks v2)

Semantic clusters (member_objects.size()>1) now verify their summary with ONE
set-level faithful-generalization call instead of per-object entailment, which
structurally rejected every cross-object generalization. Exact + entity paths
unchanged. Rewrites the per-member mechanism test to the set-level mechanism.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Real-LLM re-dogfood validation (manual, not a CI gate)

**Files:**
- Create: `$CLAUDE_JOB_DIR/tmp/gist_entailment_revalidate.py` (ephemeral — not committed; it needs `DASHSCOPE_API_KEY` so it is a manual check, not a pytest)

**Interfaces:**
- Consumes: `starling._core` (`OpenAIEmbeddingConfig`/`OpenAIEmbeddingAdapter`, `MemoryCore`, `worker.tick_one_batch`, `run_replay`), `starling.memory.make_openai_llm`, `starling.runtime._build_local_store_sqlite_runtime`. Same setup as the session's earlier dogfood (embed via `worker.tick_one_batch` to keep rows volatile; `run_replay("sleep")` with `similarity_threshold=0.5`; real qwen consolidation LLM).
- Produces: before/after numbers for the PR body. **Baseline (pre-fix, already measured this session):** tight-synonym semantic cluster → `abstracted=0, gist_gated=1`.

**Deliverable:** run the script; paste its output into the PR. Success = the faithful cluster now promotes (`abstracted=1`) AND the poisoned cluster still gates (`gist_gated=1`).

- [ ] **Step 1: Write the revalidation script**

Create `$CLAUDE_JOB_DIR/tmp/gist_entailment_revalidate.py`:

```python
"""Post-fix re-dogfood: prove gist v2 semantic clustering now PROMOTES a faithful gist
(pre-fix it was 100% gated), and a poisoned cluster still GATES (false-merge safety)."""
import os, sqlite3
from pathlib import Path
from starling import _core
from starling import runtime as rt
from starling._memory_core import MemoryCore
from starling.memory import make_openai_llm

BASE = os.path.join(os.environ["CLAUDE_JOB_DIR"], "tmp", "gist_reval.db")

def run(seed_rows, label):
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
             (f"h{i}" + "0" * 64)[:64], "v1", "believes", "pos", 0.9, "2026-05-27T09:00:00Z",
             0.5, "{}", 0.0, "2026-05-27T09:00:00Z", "user_input", 2, "volatile", "approved",
             1, "2026-05-27T09:00:00Z", "2026-05-27T09:00:00Z"))
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
                            "similarity_threshold": 0.5, "entity_gist_enabled": 0}
    rs = core.run_replay("sleep", now="2026-06-27T12:00:00Z")
    core.close()
    print(f"{label}: candidates={rs.get('gist_candidates')} abstracted={rs.get('abstracted')} "
          f"gated={rs.get('gist_gated')} failed={rs.get('gist_failed')}")

# Faithful tight-synonym cluster → EXPECT abstracted=1 (pre-fix was 0).
run([("alice", "feels", "exhausted"), ("bob", "is", "very tired"),
     ("carol", "feels", "worn out"), ("dave", "is", "fatigued"), ("erin", "feels", "drained")],
    "FAITHFUL (tired synonyms)")
# Poisoned cluster (one antonym outlier) → EXPECT gated=1 (false-merge safety intact).
run([("alice", "enjoys", "espresso"), ("bob", "loves", "cappuccino"),
     ("carol", "craves", "latte"), ("dave", "adores", "macchiato"), ("erin", "hates", "all coffee")],
    "POISONED (coffee + antonym)")
```

- [ ] **Step 2: Run it against the real LLM + embedder**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling-web
OPENAI_API_KEY="$DASHSCOPE_API_KEY" \
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1" \
timeout 200 .venv/bin/python "$CLAUDE_JOB_DIR/tmp/gist_entailment_revalidate.py"
```
Expected:
- `FAITHFUL (tired synonyms): candidates=1 abstracted=1 gated=0 failed=0` (pre-fix baseline was `abstracted=0 gated=1` — the fix's payoff).
- `POISONED (coffee + antonym): ... gated=1` (the outlier "hates all coffee" fails coverage → false-merge safety intact). If the poisoned cluster instead does not even form (the antonym embeds far and drops below the 0.5 floor → `candidates=0`), that is also an acceptable safety outcome — note which occurred.

Do NOT print `DASHSCOPE_API_KEY`. If the embedding cosine is too low for the poisoned outlier to cluster, adjust the poisoned corpus so the outlier clusters (to actually exercise the coverage gate) OR record that clustering excluded it.

- [ ] **Step 3: Record results (no commit — ephemeral script)**

Capture the printed before/after into the eventual PR description. There is nothing to commit for this task (the script is ephemeral validation, not shipped code). Mark the task complete in the ledger with the observed numbers.

---

## Self-Review

**1. Spec coverage:**
- Spec «Design: set-level template + builder» → Task 1. ✅
- Spec «gate_candidate branch» → Task 2. ✅
- Spec «Behavior-neutrality (exact + entity unchanged)» → Task 2 Step 4 (pre-existing tests pass unchanged). ✅
- Spec «Testing: mechanism via unit; semantics via real-LLM re-dogfood» → Task 2 (mechanism, SequencedLLM 1-call proof + recorded prompt) + Task 3 (real qwen). ✅
- Spec «Out of scope (threshold / default-flip / entity-semantic)» → not implemented; Global Constraints + Task boundaries hold the line. ✅

**2. Placeholder scan:** No TBD/TODO; every code step carries complete code; commands have expected output. ✅

**3. Type consistency:** `build_semantic_entailment_prompt(const GistCluster&, std::string_view) -> std::string` is declared (Task 1 header), defined (Task 1 cpp), and called (Task 2 gate_candidate) with identical signature. `EntailmentVerdict{ok, entailed}` + `parse_entailment_verdict` reused unchanged. `SequencedLLM.seen_prompts` added in Task 2 Step 1 before its Step-1 use. ✅

**Known intended test change (not a regression):** `GistWriter.PerMemberEntailmentGatesSemanticFalseMerge` is rewritten to `SemanticSetLevelEntailmentGatesFalseMerge` — the only pre-existing test that changes, because it pinned the old per-member mechanism this fix replaces (called out in Global Constraints).

## Execution Handoff

Execute via **superpowers:subagent-driven-development** (fresh implementer + task-reviewer per task, whole-branch review at the end), per project cadence. Then PR; CI green + explicit user 合并 before merge.
