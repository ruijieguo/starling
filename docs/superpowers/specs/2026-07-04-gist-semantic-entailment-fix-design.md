# gist v2 Semantic Entailment Fix — Design Spec

**Date:** 2026-07-04
**Slice:** Fix the design bug that makes gist v2 semantic clustering inert end-to-end.
**Branch:** `feat/gist-semantic-entailment` (off `main@ceb4c61`).

## Problem / Root Cause

The #38-C v2 semantic-clustering gist feature (opt-in via `similarity_threshold > 0`)
clusters statements with the SAME predicate but VARIED objects by vector similarity —
that is its entire purpose (e.g. `espresso`, `cappuccino`, `latte` → one "people enjoy
coffee drinks" gist). Clustering works mechanically (`find_semantic_gist_clusters` →
`gist_candidates=1` for a coffee corpus).

But **every semantic cluster is then gated 100% of the time by the Phase-4 entailment
verify**, so no semantic gist is ever promoted. The gate
(`gist_writer.cpp` `gate_candidate`, calling `build_entailment_prompt`,
`gist_prompt.cpp:37`) checks the summary against **each varied member object
individually**, with the strict instruction that the summary must be entailed by holders
agreeing on `predicate + {that one object}` "WITHOUT adding any claim, scope, cause, or
detail not supported by the bare fact that those holders agree on this predicate +
object." A summary that generalizes ACROSS varied objects is, by construction, never
entailed by any single object → the per-member check rejects it.

**The two v2 features contradict:** semantic clustering groups varied objects; the
per-member entailment gate requires the summary to add no scope beyond each individual
object. They cannot both hold.

**Confirmed with a real LLM** (2026-07-04 dogfood, DashScope qwen-plus + text-embedding-v3):
- `member_objects.size()>1` semantic clusters form (`gist_candidates=1` at
  `similarity_threshold=0.5`) but are gated (`abstracted=0, gist_gated=1`) for both a
  loose ("coffee drinks") and a tight-synonym ("exhausted/worn out/fatigued") cluster.
- Raw entailment probes: `object=espresso` + summary "People enjoy various coffee drinks"
  → `{"entailed": false}`; `object=coffee` + "People enjoy coffee" → `{"entailed": true}`;
  even `object="worn out"` + "People feel tired" → `{"entailed": false}`. Only exact
  (same-object, v1 NORM) clusters pass.

The `FakeLLMAdapter` used in unit tests rubber-stamps `entailed=true`, so this is the
classic CI-green-but-inert-on-real-data gap — it only manifests with a real LLM.

## Goal / Non-Goals

**Goal:** Make gist v2 semantic clustering promote faithful gists when enabled, by
replacing the structurally-wrong per-member entailment (for semantic clusters only) with
a **set-level faithful-generalization** check that preserves false-merge safety.

**Non-Goals (this slice — narrow scope, decided 2026-07-04):**
- Threshold precision/recall tuning (the OTHER inert reason: real paraphrase cosine is
  only ~0.50–0.60; a safe-yet-firing `similarity_threshold` is unresolved).
- Flipping the v2 semantic default ON. `similarity_threshold` default stays `0.0` (OFF);
  v2 semantic remains opt-in. Whether to flip the default is a separate future decision
  gated on the threshold question above.
- Entity-semantic clusters: they do not exist (see Invariant below), so no work.

## Design: Set-Level Faithful-Generalization Entailment

### The clean invariant (verified in current code)

`GistCluster.member_objects` holds the distinct member object strings.
- `member_objects.size() > 1` ⟺ **semantic cluster** (varied objects). Only
  `expand_semantic_cluster` (`gist_clustering.cpp`) populates a multi-element
  `member_objects`, and it never sets `subject_id` → a semantic cluster is always
  people-norm (`subject_id` empty).
- Exact people-norm clusters and entity clusters both have `member_objects.size() <= 1`.
  Entity clusters (`find_norm_gist_clusters(by_subject=true)`) cluster by
  `(subject, predicate, canonical_object_hash)` — same hash = same object = exact. So
  entity clusters carry a subject but a single object.

Therefore the branch discriminator is exactly `cluster.member_objects.size() > 1`, and it
selects precisely the people-norm semantic clusters. Exact + entity paths are untouched.

### Why set-level (not per-member)

A faithful generalization gist must satisfy two safety properties:
1. **Coverage (false-merge safety):** every member object is an instance/case of the
   summary. A k-NN-mis-clustered outlier ("hates coffee" pulled in with espresso/latte)
   is not an instance → must gate.
2. **Tightness (no confabulated over-generalization):** the summary is no broader than
   the set of objects warrants ("people enjoy all beverages" from 5 coffee objects
   over-reaches → must gate).

**Tightness is inherently a set-level property** — a per-member call sees only one object
and cannot judge whether the summary is broader than the whole set. So the per-member
approach structurally cannot verify tightness; only a set-level check can. The set-level
check also catches coverage (it lists every object and gates if any is not an instance)
and costs **one** LLM call instead of N.

### New prompt template (people-norm semantic only)

Add `kSemanticEntailmentTemplate` to `gist_prompt.cpp`. It reuses the existing
`{"entailed": <bool>}` reply shape, so `parse_entailment_verdict` is unchanged.

```
You are the verification faculty of a memory system. A consolidation step produced a
candidate NORM summary generalizing over {holder_count} distinct holders who each
INDEPENDENTLY assert a related belief with the SAME predicate ({predicate}) but VARIED
objects:
  {objects}
Check whether the summary is a FAITHFUL GENERALIZATION of this set — (a) COVERAGE: every
listed object is an instance or case of the summary; (b) TIGHTNESS: the summary
introduces no scope, claim, category, or detail broader than this set of objects
warrants. If ANY listed object is not an instance of the summary, or the summary
over-reaches beyond what the set supports, it is NOT faithful.

Candidate summary: {summary}

Reply with ONLY a JSON object (no prose, no markdown):
{"entailed": <true if the summary covers EVERY listed object AND stays within the set's scope; false otherwise>}
```

`{objects}` is `join_with_commas(cluster.member_objects)` (the same helper
`build_norm_gist_prompt` uses). `{holder_count}` / `{predicate}` filled as elsewhere.

### New builder

```cpp
// gist_prompt.hpp
[[nodiscard]] std::string build_semantic_entailment_prompt(const GistCluster& cluster,
                                                           std::string_view summary);
```
`gist_prompt.cpp`: fill `kSemanticEntailmentTemplate` with `holder_count`, `predicate`,
`objects = join_with_commas(cluster.member_objects)`, `summary`. People-norm only — it is
never called for an entity cluster (those never have `member_objects.size() > 1`).

### gate_candidate branch (`gist_writer.cpp`)

Replace the current unconditional per-member loop (lines ~115–125) with:

```cpp
if (cluster.member_objects.size() > 1) {
    // Semantic cluster: one set-level faithful-generalization check. The summary
    // generalizes across varied objects, so per-member "no scope beyond this object"
    // is structurally wrong; verify coverage + tightness over the whole set at once.
    const extractor::LLMResponse verify_resp =
        gist_llm.generate(build_semantic_entailment_prompt(cluster, judgment.summary));
    if (!verify_resp.ok) { return GateDecision::Failed; }
    const EntailmentVerdict verdict = parse_entailment_verdict(verify_resp.raw_xml);
    if (!verdict.ok) { return GateDecision::Failed; }
    if (!verdict.entailed) { return GateDecision::Gated; }
} else {
    // Exact / entity cluster: unchanged — verify the one shared object (byte-identical).
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
```

Note the else-branch keeps `member_objects.empty() ? {object_value} : member_objects` so a
`member_objects.size()==1` cluster (a degenerate single-object case) still verifies its
one object exactly as today.

### Correctness (the three cases)

| Cluster | Summary | Set-level verdict |
|---|---|---|
| Tight synonyms {exhausted, worn out, fatigued, drained} | "people feel tired" | **PASS** — each an instance, not broader (old per-member wrongly gated) |
| False merge {espresso, latte, cappuccino, **hates coffee**} | "people enjoy coffee" | **GATE** — "hates coffee" not an instance (coverage) |
| Over-broad {espresso, latte, cappuccino} | "people enjoy all beverages" | **GATE** — broader than the set (tightness; only set-level can catch) |

### Behavior-neutrality

- Exact people-norm + entity clusters take the else-branch, byte-identical to today.
- Semantic clusters were 100%-gated (inert) before, and v2 semantic is default-OFF
  (`similarity_threshold=0.0`). So there is zero production behavior change; the only
  change is that an opt-in semantic run can now promote a faithful gist instead of
  gating everything.

## Files Touched

- `include/starling/replay/gist_prompt.hpp` — declare `build_semantic_entailment_prompt`.
- `src/replay/gist_prompt.cpp` — add `kSemanticEntailmentTemplate` + the builder.
- `src/replay/gist_writer.cpp` — branch `gate_candidate` on `member_objects.size() > 1`.
- `tests/cpp/` — unit tests (mechanism).
- `tests/python/` — optional parity/integration if a Python seam is convenient; primary
  end-to-end validation is the manual real-LLM re-dogfood (below).

No changes to clustering, scheduler, bindings, or Python core. `parse_entailment_verdict`
and `EntailmentVerdict` are reused unchanged.

## Testing Strategy

**Critical nuance:** `FakeLLMAdapter` returns a canned `entailed` verdict regardless of
prompt, and the OLD code already "passed" semantic clusters under a rubber-stamp
`entailed=true`. So a FakeLLM cannot demonstrate the semantic *correctness* of the fix —
it can only verify the *mechanism*. Semantic correctness is proven by the real-LLM
re-dogfood.

`gate_candidate` is file-static (anonymous namespace) → not directly unit-testable; tests
drive it through the public `write_gist_proposals` (C++) or `run_replay` (Python).
`FakeLLMAdapter` is already used from Python in `tests/python/test_consolidation_gist_llm.py`
(the natural template); a pure C++ test in `tests/cpp/` is equally fine if it records LLM
calls more cleanly. Pick the seam that lets the test assert the entailment call count/shape.

**Unit (mechanism):**
1. A semantic cluster (`member_objects` = 3+ distinct) drives `write_gist_proposals` /
   `run_replay` through a recording FakeLLM. Assert:
   - Exactly **one** entailment call is made (not N), and its prompt contains **every**
     member object (the joined set) — i.e. `build_semantic_entailment_prompt` was used.
   - With the FakeLLM returning `entailed=true`, the candidate → `Pass` (promoted).
   - With a prompt-conditional / sequenced FakeLLM returning `entailed=false` for the
     set-level call, the candidate → `Gated`.
2. An exact cluster (`member_objects` empty or size 1) still makes a per-object
   `build_entailment_prompt` call (else-branch unchanged), `entailed=true` → `Pass`.
3. Entity cluster (subject set, single object) unchanged — still entity entailment path.

Use whatever prompt-recording capability `FakeLLMAdapter` already exposes; if it lacks
per-prompt responses, a sequenced-response fake (return values in call order) suffices to
distinguish 1-call vs N-call.

**Real-LLM re-dogfood (manual, post-build) — semantics:**
Re-run the controlled dogfood (seed a semantic cluster raw, embed via
`worker.tick_one_batch` to keep the rows volatile, `run_replay("sleep")` with
`similarity_threshold=0.5`, real qwen consolidation LLM). Expected AFTER the fix:
- Tight-synonym cluster ("exhausted/worn out/…") → `abstracted=1` (a gist promoted, with
  a sensible summary), where before it was `gist_gated=1`.
- A deliberately-poisoned cluster (inject a "hates …" outlier) → still `gist_gated=1`
  (false-merge safety intact).

Record the before/after numbers in the PR description.

## Build & Commit Gates

- Build: `python scripts/configure_build.py --build --python-editable` (C++ + rebuild
  `_core`; a bare `pip install -e .` is not enough for binding/core changes). This slice
  touches no bindings, but `gist_prompt`/`gist_writer` are in `starling_core`, so the
  editable reinstall keeps `_core` in sync for the Python dogfood.
- Commit gate: full `ctest` + `pytest tests/python` green.
- clang-tidy is CI-only; write the new C++ clean by construction (identifier length ≥ 3,
  no raw-pointer arithmetic, `[[nodiscard]]` on the new builder, designated initializers,
  no new const/ref data members).
- git: explicit-path `git add` only (no `git add .` / `-A`); no `--no-verify` / `--amend`.

## Out of Scope (restated)

Threshold precision/recall tuning; v2 semantic default-flip; entity-semantic (nonexistent);
the entity and exact people-norm entailment paths (unchanged).
