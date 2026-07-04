# gist v2 Judge-Prompt Follow-up — Design Spec

**Date:** 2026-07-04
**Slice:** Fix the consolidation JUDGE prompt so it produces promotable gist summaries — the second (post-entailment) blocker to gist v2 promoting end-to-end.
**Branch:** `feat/gist-judge-prompt` (off `main@c5ce05a`, which has the entailment fix PR #47).

## Problem / Context

PR #47 fixed the Phase-4 entailment gate (it no longer structurally rejects every
semantic cluster; a faithful summary now passes). But end-to-end, gist v2 still does not
promote with a real LLM: the earlier bottleneck simply moved **upstream to the JUDGE**
(`build_norm_gist_prompt` / `kNormGistPromptTemplate`), which produces summaries the
(now-correct) verify then gates.

Two failure modes, measured 2026-07-04 with real qwen-plus (temp 0):

1. **Verbose + adds interpretive scope.** Tired set {exhausted, very tired, worn out,
   fatigued, drained} → judge summary "People commonly report feeling … as a shared
   subjective experience of physical or mental depletion." The "physical or mental
   depletion" clause introduces scope beyond the objects → the set-level tightness verify
   correctly returns `entailed:false`.
2. **Over-skeptical — refuses to generalize.** Coffee set {espresso, cappuccino, latte,
   macchiato, americano} → `confidence:0.35` + a summary that is a meta-commentary:
   "…suggestive but insufficient to establish a genuine, generalizable norm without
   evidence of broader cultural, demographic, or behavioral consistency beyond this small,
   unrepresentative sample." This is not a norm sentence → fails both the confidence floor
   and the verify.

Both stem from the judge prompt's framing: "a genuine, generalizable NORM — something
people **in general** believe or do" invites demographic skepticism, and "one concise
sentence" is too weak to stop qwen adding interpretation. The system's design intent is
that ≥K independent holders IS the norm evidence (representativeness is the clustering
K-threshold's job, not the judge's) and the gist consolidates THIS memory's observed
consensus, not a claim about the wider population.

## Goal / Non-Goals

**Goal:** Reword `kNormGistPromptTemplate` so the judge (a) treats the holders' independent
agreement as sufficient evidence (no demographic/sample-size skepticism), and (b) emits one
short norm sentence adding no cause/scope/interpretation — aligned with what the set-level
tightness verify accepts — while **remaining a coherence filter** (it can still reject a
genuinely incoherent / coincidental mis-cluster via low confidence).

**Non-Goals (narrow scope, decided 2026-07-04):**
- The entity judge (`kEntityGistPromptTemplate`) — a separate default-OFF mode, not the
  validated failure; left unchanged.
- `min_confidence` floor, `similarity_threshold`, and the v2 default-OFF state — untouched.
- The entailment verify prompts (`kEntailmentPromptTemplate`, `kSemanticEntailmentTemplate`)
  — already correct (PR #47); untouched.
- Turning the judge into a pure renderer (rejected fork — keep the coherence gate).

## Design: reword `kNormGistPromptTemplate`

Replace the template (`src/replay/gist_prompt.cpp:18-28`) with:

```
You are the consolidation faculty of a brain-like memory system. Several DISTINCT holders have INDEPENDENTLY asserted the same belief. Their independent agreement IS the evidence — you are consolidating THIS memory's observed consensus, NOT judging whether the wider population holds it, so do NOT require demographic, cultural, or sample-size evidence. Judge only whether their shared belief is a COHERENT, generalizable belief worth recording as a norm, rather than a coincidental or incoherent overlap.

Candidate norm:
  predicate: {predicate}
  object: {object}
  asserted by {holder_count} distinct holders: {holders}

Reply with ONLY a JSON object (no prose, no markdown):
{"confidence": <number 0.0-1.0 — how coherent and generalizable the shared belief is, GIVEN the holders' agreement as sufficient evidence>, "summary": "<ONE short plain sentence stating ONLY the shared belief; add no cause, scope, category, interpretation, or detail beyond what the holders assert>"}
```

How each clause targets a failure mode:
- **Over-skepticism** ← "Their independent agreement IS the evidence … consolidating THIS
  memory's observed consensus, NOT judging whether the wider population holds it … do NOT
  require demographic, cultural, or sample-size evidence" + confidence reframed to "how
  coherent and generalizable … GIVEN the holders' agreement as sufficient evidence."
- **Verbose / over-scope** ← "ONE short plain sentence stating ONLY the shared belief; add
  no cause, scope, category, interpretation, or detail beyond what the holders assert" —
  deliberately mirrors the set-level verify's tightness criterion so a compliant judge
  summary passes verification.
- **Coherence gate preserved** ← "Judge only whether their shared belief is a COHERENT,
  generalizable belief … rather than a coincidental or incoherent overlap" — a truly
  mis-clustered / incoherent set still earns low confidence.

### Correctness constraint — single placeholder occurrences

`build_norm_gist_prompt` fills placeholders with `replace_first` (not `replace_all`), so
each of `{predicate}`, `{object}`, `{holder_count}`, `{holders}` must appear **exactly
once** in the template. The reworded intro deliberately says "Several DISTINCT holders"
(no count) and keeps the single `{holder_count}` in the Candidate block — a second
`{holder_count}` would be left as a literal. (Only the norm-judge template is touched;
`build_norm_gist_prompt`'s substitution code is unchanged.)

## Blast Radius / Behavior

`kNormGistPromptTemplate` is used by **every people-norm gist** — v1 (exact, same-object
clusters) AND v2 semantic (varied-object clusters). This is a wider blast radius than the
entailment fix (which was scoped to semantic clusters only). The reword is strictly
*clearer* (concise + consensus-is-evidence), so it is expected to help v1 rather than
regress it — but v1 non-regression MUST be validated (see Testing). The entity-gist path
and all thresholds are untouched.

Existing gist unit tests drive `FakeLLMAdapter` with canned `{confidence, summary}` JSON
(`set_default_response` / `SequencedLLM`); none pin the template's prose. So the reword
does not break them by construction — but that also means unit tests cannot prove the
reword *works*; that is the re-dogfood's job.

## Testing

**Unit (C++ ctest + pytest) — no regression:** full `ctest` + `pytest tests/python` green,
unchanged. The FakeLLM-driven gist tests do not pin prompt prose, so they stay green; run
them to confirm nothing depended on the old wording.

**Real-LLM re-dogfood (manual, not a CI gate) — the payoff + the v1 guard:** with real
qwen-plus + text-embedding-v3, seed volatile clusters, embed via `worker.tick_one_batch`,
`run_replay("sleep")`:
- **v2 semantic** (varied objects, `similarity_threshold=0.5`): the tired-synonym set and
  the coffee set now reach `abstracted=1` (pre-fix both were `gist_gated=1`), with a
  concise promoted summary. Capture the summary + the counts.
- **v1 people-norm** (same-object cluster, `similarity_threshold=0`): a 3-holder exact
  cluster still reaches `abstracted=1` — the reword did not regress the working v1 path.
- Optionally re-confirm false-merge safety still holds (a poisoned varied set still gates)
  — the verify is unchanged, so this is a sanity check, not the focus.

Record before/after numbers + the promoted summaries in the PR.

**Realistic success bar (LLM is stochastic).** Even at temperature 0 the verify verdict
has shown run-to-run variance, so success is NOT "abstracted=1 on every single run." It is:
(1) the judge now emits a **concise, no-added-scope** norm sentence (the primary,
directly-observable fix — inspect the summary text), and (2) at least one **clean
end-to-end `abstracted=1`** for a v2 semantic cluster within a small number of attempts
(pre-fix was a hard 0 across all attempts), and (3) **no v1 regression**. If the judge's
summaries are now concise/faithful but end-to-end promotion is still only intermittent,
that is honest signal that judge determinism (not this reword) is a further follow-up —
report it rather than tuning further in this slice.

## Build & Commit Gates

- `kNormGistPromptTemplate` is a `constexpr std::string_view` in `starling_core`. Build:
  `python scripts/configure_build.py --build --python-editable` (rebuild `_core` so the
  Python re-dogfood sees the new prompt — a bare `pip install -e .` is not enough).
- Commit gate: full `ctest` + `pytest tests/python` green.
- clang-tidy is CI-only; this is a string-literal edit (no identifiers/logic) — no new
  lint surface.
- git: explicit-path `git add` only (no `git add .` / `-A`); no `--no-verify` / `--amend`.

## Out of Scope (restated)

Entity judge prompt; confidence floor; similarity_threshold; v2 default-flip; entailment
verify prompts; making the judge a pure renderer. If the reworded judge still under-yields
end-to-end, that is a follow-up measurement — not this slice.
