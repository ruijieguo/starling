# Starling Memory: A Technical Report

### Agent Memory with Multi-Subject Social-Mind Representation and Brain-Like Dynamics

**中文版: [Starling_Technical_Report.zh-CN.md](Starling_Technical_Report.zh-CN.md)**

---

## Abstract

Mainstream agent-memory stacks are, at bottom, vector-RAG over `user_id` isolation: they remember *what was said* but cannot model *who believes what*. Starling Memory argues that an agent capable of long-horizon collaboration needs not larger recall but a **continuously-evolving model of each interaction partner** — a portrait of the other, what the agent believes about them, and what the agent thinks *they* believe — paired with a set of **brain-like memory dynamics**: fast write / slow consolidation, priority replay, reconsolidation (without overwrite), adaptive forgetting, salience modulation, and prospective triggers.

This report presents three contributions. **(1) Multi-subject social-mind representation:** memory's atom is a *holder-attributed* `Statement` rather than a subject-less `Fact`, collapsing attribution, conflict, retraction, perspective, and nested belief into one shape; the `Cognizer` is a first-class subject, not a database column; higher-order beliefs are realized by three complementary representations — symbolic nesting, an adaptive ToM-order estimator, and perception-grounded false-belief tracking — yielding arbitrary-order mentalizing. **(2) Brain-like dynamics:** a six-state consolidation lifecycle spanning every memory's life, scaffolded on the fast (hippocampal) / slow (neocortical) dual timescales of Complementary Learning Systems (CLS), realizing sharp-wave-ripple (SWR)-style priority replay, an Ebbinghaus forgetting curve, a no-overwrite reconsolidation *supersedes* chain, and a prospective commitment state machine. **(3) High-order belief reasoning:** on the HiToM higher-order ToM benchmark, injecting Starling's deterministic nested-tracking operators into a 14B model lifts overall accuracy **0.7925 → 0.8342 (+4.2pp, paired-significant), with the gain monotonically concentrated at the deepest orders — order-3 +10.8pp, order-4 +8.3pp**; for the stronger deepseek model the deep-order gains reach +15–17pp.

Starling's core is modern C++20 (~24.8k lines, with Theory of Mind being the single largest module); Python is a thin binding layer. We are equally candid about the **capability boundary**: the deterministic operators help only in the narrow regime where they are *more accurate than the model's own reasoning* (deep nested tracking); on shallow/flat tasks a strong model already solves, they are flat or harmful. A semantic-routing gate collapses the worst case from −8.9pp to −0.7pp, converting the system from "sometimes hurts" to "helps or neutral."

**Keywords:** agent memory; theory of mind; higher-order belief reasoning; complementary learning systems; memory consolidation and reconsolidation; cognitive middleware.

---

## 1 Introduction

### 1.1 The problem: vector stores remember facts, but cannot model minds

Over the last two years, agent memory matured from "stuff the transcript into context" into a robust engineering stack — vector retrieval + knowledge graphs + temporal edges (mem0, Letta, cognee, Graphiti/Zep). These systems are good at **fact retention**, but they share an implicit ontology: memory is a pile of **subject-less facts**, isolated by dimensions like `user_id`. That ontology exposes three structural gaps the moment real social collaboration is required:

- **Attribution collapse.** "Bob is no longer on auth" — who said that? Did I witness it, did Alice report it, or did I infer it? In a flat fact store the speaker, the subject, and the belief-holder are flattened into one layer and cannot be queried apart.
- **Missing perspective.** Meta-beliefs like "I thought Bob didn't know this yet" are the foundation of social tact, negotiation, and confidentiality; they require the system to hold a *nested* "A thinks B believes X" structure, not a sentence-level similarity hit.
- **Staticity.** Once written, a fact is inert — no consolidation, no forgetting curve, no "recall-then-revise," and certainly no *prospection* that can wake the agent with no user query.

In the vocabulary of social-intelligence research, today's systems lean on **superficial patterns rather than genuine social reasoning**: they can recite, but they cannot stand in the other's perspective, infer the other's mental state, and act on it.

### 1.2 Design stance: cognitive middleware, not a storage rewrite

Starling does not try to replace the vector store; it sits **on top** of it as cognitive middleware: a triad of *data model + runtime scheduler + retrieval planner* that can layer over mem0 / Letta / cognee / Graphiti and add the `holder` dimension, the `Statement` ontology, Theory of Mind (ToM), brain-like replay, and prospection. Three **non-goals** bound its ambition: it does not rewrite the vector store, does not train models, and does not chase formal-logic completeness.

### 1.3 Contributions

1. **An attribution-first memory ontology (§3.1–3.2):** the single shape `Statement(holder, subject, predicate, object, modality, polarity, time, evidence, confidence)` solves attribution, conflict, retraction, perspective, and second-order ToM at the schema level; `Cognizer` is a first-class subject with stable identity, directional trust, a Fiske relation graph, a knowledge frontier, and a persona.
2. **Arbitrary-order mentalizing (§3.3–3.5):** three complementary representations — symbolic nesting (`nesting_depth`, soft cap 32), an adaptive order estimator, and perception-grounded false-belief tracking (`what_does_X_think` / `what_does_X_think_chain`, co-witness intersection + observation-primacy) — plus a common-knowledge closure operator.
3. **Brain-like memory dynamics (§4):** a six-state consolidation lifecycle + CLS dual timescales + SWR priority replay + Ebbinghaus forgetting + no-overwrite reconsolidation + a prospective commitment machine, all landed in a runnable C++ core and an auditable event bus.
4. **Perspective-aware retrieval and a "mind summary" (§3.6):** context is reconstructed per `(querier, perspective, intent, goal)`; the perspective filter runs *before* semantic ranking (a privacy hard-constraint); the output is a "mind summary" with 8 pragmatic tags and explicit abstention.
5. **A defensible evaluation of high-order belief reasoning, with honest boundaries (§5):** we quantify Starling's gain for weak and strong models on HiToM/ToMBench, localize where the gain concentrates (deep nesting), and candidly report generalization failures and harmful regimes with their causes.

---

## 2 System Overview

### 2.1 Three axioms

Every mechanism in Starling is generated by three axioms, each grounded in a neuroscientific or cognitive-science result.

- **Axiom I — There are no isolated facts, only statements attributed to a subject.** Every memory is `Statement(holder, subject, predicate, object, modality, polarity, time, evidence, confidence)`. One shape simultaneously solves attribution, conflict, retraction, perspective, and second-order ToM.
- **Axiom II — Two timescales cooperate (Complementary Learning Systems, CLS).** Writes first land in the Hippocampus (`VOLATILE`); only after Replay, pattern separation/completion, and reconsolidation do they rise into the Neocortex as stable semantics / norms / skills / personas. This is the engineering of McClelland et al. (1995): the fast channel cycles in-and-out to resist catastrophic forgetting; the slow channel interleaves gradually to settle structure.
- **Axiom III — Memory is reconstructed for the current goal, not replayed like a tape (Conway's Self-Memory System, SMS).** Retrieval returns a perspective-shaped mind summary, with the option to abstain, rather than fanning out a pile of tools.

### 2.2 The Statement Bus spine and twelve subsystems

The system has a single entry point — the **Statement Bus**: every read and write passes through it, with no bypass. Inside the Bus: `Validator` → `ConflictProbe` → `outbox` → `event dispatcher`. Around the spine sit twelve subsystems:

| # | Subsystem | Responsibility |
|---|---|---|
| 1 | Substrate Adapter | physical-backend abstraction over three store profiles; capability preflight; projection index |
| 2 | EngramStore | verbatim evidence storage + retention policy |
| 3 | Hippocampus | fast memory (VOLATILE), event segmentation, Working Set, Affect Buffer |
| 4 | Neocortex | slow memory (CONSOLIDATED), per-holder subgraphs, five subzones, Persona/CommonGround containers |
| 5 | Statement Bus | write entry, validation, conflict probe, event dispatch, idempotency |
| 6 | Cognizer Hub | subject registry, alias normalization, trust, KnowledgeFrontier, relation edges |
| 7 | ToM Engine | nested-belief tracking, `perspective_take`, mentalizing primitives |
| 8 | Replay Scheduler | Online/Idle/Sleep consolidation, forgetting curve, SWR priority sampling |
| 9 | Reconsolidation Engine | recall-induced plasticity, arbitration, supersedes chain |
| 10 | Prospective Loop | Trigger + Commitment five-state machine + ActionGuard |
| 11 | Retrieval Planner | 9 intents + 7-step planning + Context Pack 8 tags + abstention |
| 12 | Runtime Governance | RuntimeHealth (4 states), PipelineRun ledger, ScopedWorkGate throttle (cross-cutting) |

### 2.3 Data flow: a Statement's physical path from birth to old age

```
append_evidence ─► EngramStore (permanent verbatim) ─► Bus emit: evidence.appended
   ─► Extractor (LLM extracts several Statements) ─► Bus.write (Validator + ConflictProbe)
   ─► Hippocampus (state=VOLATILE) ─► Replay Scheduler (priority sampling, REPLAYING_CONSOLIDATING)
   ─► Neocortex (CONSOLIDATED, emits statement.derived)
        │                                     │
   recalled / conflict ▼              decay S(t)<0.05 ▼
   REPLAYING_RECONSOLIDATING (plastic window)   ARCHIVED ──► FORGOTTEN (per retention_mode)
```

Three **data-flow invariants** guarantee the brain-like semantics are correct:

- **EngramStore is always written first**, then the Statement; `Statement.evidence` must trace back to the original. This is the engineering of "the hippocampus always keeps the verbatim original," and it lets extraction errors be traced and corrected.
- **State transitions are mostly one-way**; the only backward path is `ARCHIVED → REPLAYING_RECONSOLIDATING` (re-awakened by recall).
- **provenance is frozen on write**; a mild correction only adjusts confidence + appends history (no new version); a severe contradiction forks a new version + supersedes edge + archives the old + emits outbox events — four items committed atomically.

### 2.4 Execution flow: the event trigger chain

The write path fans out to different subscribers by `provenance` (`user_input` triggers Replay/ToM/Affect/Prospect; `replay_derived`/`tom_inferred` trigger only a subset). Two key invariants cut self-excitation loops: **Replay does not subscribe to `statement.derived`** (else derive → replay → re-derive loops forever); and **causation_chain ≤ 3**, beyond which it emits `system.runaway`. Retrieval is a **pure-read module**, emitting only fire-and-forget `statement.recalled` and never mutating state directly — that event then asynchronously triggers the reconsolidation window decision.

### 2.5 Implementation scale and engineering discipline

Starling's core is implemented entirely in the C++20 kernel (`src/` + `include/starling/`); Python only does application adaptation (signature normalization, DTO defaults, prompt config, read-only inspection). The test is: "would another binding language need to rewrite this logic?" As of this report:

| Metric | Scale |
|---|---|
| C++ kernel (src + include) | ~24,831 lines |
| Largest C++ module | **`tom/` (Theory of Mind): 3,143 lines / 22 files** |
| Other major modules | bus 2,588 · replay 1,837 · extractor 1,339 · retrieval 1,316 · cognizer 1,236 · prospective 1,099 · reconsolidation 1,054 · neocortex 581 · hippocampus 223 |
| Python adaptation layer | ~6,319 lines |
| SQL migrations (embedded at build time) | 28 |
| Tests | 143 C++ ctest files + 160 pytest files |
| Commit history | 740 commits |

One objective signal is worth stating: **Theory of Mind is the single largest C++ module**, not a thin prompt-layer patch — empirical evidence that "the social mind" is a first-class, deeply-implemented concern in this system.

---

## 3 Multi-Subject Social-Mind Representation (Pillar 1)

This is where Starling departs from vector-RAG memory. We build up layer by layer: the atom (§3.1) → the subject (§3.2) → nested belief (§3.3) → common ground (§3.4) → perception/mental state (§3.5) → perspective retrieval (§3.6) → persona (§3.7).

### 3.1 The Statement atom: one shape that collapses five concerns

The atom of memory is the frozen `Statement` (`python/starling/schema/statement.py`, 36 fields), designed so that attribution, conflict, retraction, perspective, and second-order ToM share one shape:

- **Subject dimension:** `id`, `tenant_id`, `holder: CognizerRef` (who holds this judgment — must be a Cognizer), `holder_perspective ∈ {FIRST_PERSON, QUOTED, INFERRED, HEARSAY}`. **`holder_perspective` is precisely what collapses "perspective" into the atom:** the same proposition reported first-hand vs. quoted vs. inferred vs. hearsay is one shape with a different perspective value.
- **Content dimension:** `subject` (a Cognizer or Entity — **deliberately not a StatementRef**, so recursion happens only in `object` and the normalization key stays computable), `predicate`, `object` (the **recursive slot**: a scalar, a Cognizer/Entity ref, or a `StatementRef` — the latter being a belief-about-a-belief), `modality`, `polarity`, `confidence` + an append-only `confidence_history`. `modality` and `polarity` are orthogonal: the former is the propositional attitude, the latter POS/NEG/UNKNOWN.
- **Time dimension (five distinct times):** `observed_at`, `event_time`, `inferred_at`, `valid_from`, `valid_to` — separating "when observed" from "when the fact takes/loses effect."
- **Evidence and attribution:** `evidence`, `source_spans`, `temporal_anchor`, `derived_from`, `perceived_by` (who perceived it — information visibility), `supersedes`. **Conflict** = two statements sharing a `canonical_object_hash` but differing in polarity/holder, expressed by a `CONFLICTS_WITH` edge rather than overwrite; **retraction** = a new statement with `modality=RECANTED` + a `supersedes` pointer, the old version archived not deleted.
- **Brain-like dynamics and governance:** `salience`, `affect`, `activation`, `consolidation_state`, `review_status`, `provenance`, plus `nesting_depth` (soft cap 32) carrying second-order ToM.

`modality` offers 12 propositional attitudes: `BELIEVES, KNOWS, ASSUMES, DOUBTS, DESIRES, INTENDS, COMMITS, PREFERS, NORM_OUGHT, NORM_FORBID, RECANTED, OCCURRED` — unifying belief, knowledge, desire, intention, commitment, preference, norm, retraction, and objective events into one atom. Promoting commitments (`COMMITS`) and norms (`NORM_OUGHT`) to first-class attitudes is exactly what lets them drive runtime behavior (prospective triggers, decay protection).

> **Design trade-off:** making the atom a holder-bearing `Statement` rather than a `Memory`/`Fact` (mem0-style) solves multi-subject isolation at the schema level once and for all — the long-term payoff far exceeds the initial complexity. The system's judgment is blunt: **ToM is a data-structure problem, not a model problem**; only by putting it in the schema do you get stable queries, auditability, and freedom from the LLM's stochastic reasoning.

### 3.2 Cognizer: a first-class cognitive subject (vs. a user_id column)

`Cognizer` (`python/starling/schema/cognizer.py`) promotes user/agent/group/role to first-class subjects with lifecycle, knowledge boundary, and inter-subject relations:

- **Stable identity:** `id = UUID5(namespace, kind + external_id)`, not an autoincrement — the same physical person under a different `kind` is a different subject. Three-layer normalization `aliases → canonical_name → external_id`; `normalize_alias` folds whitespace and ASCII case while passing CJK bytes through, so "Xiao Hong" and "XiaoHong" resolve to one subject.
- **Directional, context-scoped trust:** `trust_priors[B]` is "A's prior trust in B," not the system's trust in A; initialized neutral at 0.5, raised/lowered by `commitment.fulfilled`/`broken`.
- **A social graph richer than an edge label:** `RelationEdge` carries `fiske_weights` (Fiske's four relational models `Communal/Authority/Equality/Market`, summing to 1), `affinity`, context-scoped `trust`, `power_asymmetry`, and a validity window. Crucially, **relations are stored as Statements with the observer as `holder`, so each party's view of the A–B relationship is independent** — multi-perspective is native. The persisted edge vocabulary has 14 kinds (`BELIEVES_ABOUT, TRUSTS, COMMITTED_TO, CONFLICTS_WITH, SHARED_GROUND, OBSERVED_BY, PERCEIVED_BY, NORM_OF, MAY_OVERLAP_WITH, SUPERSEDES, DERIVED_FROM …`).

As a foil, `Entity` (a non-cognizer) has no persona, no knowledge frontier, no trust, can appear only as subject/object, and **can never be a holder**. This boundary makes "who may hold a belief" type-controlled.

> **vs. a `user_id`:** a user_id is an opaque isolation key; a Cognizer is an addressable subject — with cross-source stable identity, directional per-domain trust, a Fiske-typed relation graph, a knowledge frontier, and a persona — and **it can itself be the `subject` or nested `object` of another subject's belief**, which is exactly what makes higher-order ToM expressible.

### 3.3 Nested belief and arbitrary-order ToM: three complementary representations

"I think you think X" is represented **three complementary ways** in Starling; a report should keep them apart.

**(a) Symbolic nesting (Statement-graph nesting).** A meta-belief is a statement with `object_kind='statement'` whose `object` points to the inner statement's id; depth is carried by `nesting_depth`. The holder/subject chain descends level by level: outer `holder=self, subject=X, predicate=believes, object→inner`; inner `holder=X, subject=Y, …`. Depth is bounded by three guardrails, not a cognitive cap: a soft cap `kDefaultMaxNestingDepth=32`, a `NestingCycle` detector, and ancestor-chain walking. The 2026-06 redesign **removed the old "three-order cognitive cap" in favor of arbitrary order**. Queries use `what_does_X_think_Y_believes` with a `WITH RECURSIVE` unwrap, with `level < max` keeping it cycle-safe. A conceptual heart here is the **mirror-vs-fabrication** split: the LLM extractor emits only flat statements, and nested rows are produced *programmatically* by `tom::second_order`. The **auto path** (mirroring a belief the partner actually authored) is *un-gated* — a gate would be tautological; the **explicit path** (wrapping a partner's order-k belief into self's order-(k+1)) lands **only if the depth estimator says `estimate(partner) ≥ k+1`**, else it records `gated_order`. This is the anti-fabrication gate: don't invent deeper mental states the partner never demonstrated.

**(b) Adaptive ToM-order estimator.** `depth_estimator::estimate` reads the partner's statements over a 7-day window and folds a `nesting_depth` histogram into a credible order (a depth needs ≥3 statements to be credited), keeping a `{0,1,2}` floor for shallow partners but **no longer saturating at 2**, cached for an hour. This lets the system dynamically choose "how many orders deep to model" per partner.

**(c) Perception-grounded false-belief tracking (the HiToM mechanism).** This representation is *not* symbolic — it reconstructs "who perceived what state of a theme, when." `PerceptionReconstructor` recomputes each subject's `perception_state` from all `OCCURRED` events. The primitive `what_does_X_think` returns `StateBelief{state_value, is_stale}` — X's *last-perceived* state, with `is_stale = (≠ the global latest truth)` being the Sally-Anne false-belief signal. The arbitrary-order generalization `what_does_X_think_chain([c1..cN])` reads "c1 thinks c2 thinks … cN thinks the theme is where," answering with the holder's highest-position state **among events every observer co-witnessed** (**co-witness intersection**), and enforcing **observation-primacy**: tell/inform (hearsay) must not override first-hand observation and only fills gaps for an agent never present. **The clean +6.4% gain on the roadmap comes from (c), not the symbolic nesting (a).**

### 3.4 Common ground and the common-knowledge operator

The **common-ground container** `CommonGround` holds N-ary `parties` and three buckets: `grounded` ("both know that both know"), `asserted_unack` ("one said it, the other hasn't confirmed"), and `suspected_diverge` ("suspect the other actually believes otherwise"). Its lifecycle is driven by **seven grounding acts**: `assert_ / acknowledge / repair / withdraw / supersede_ground / expire_ground / unground`. The **closure** `asserted_unack → grounded` fires on one of four rules: explicit confirmation; co-presence presumption (`perceived_by` covers all parties with no repair/withdraw for 3 rounds); repeated confirmation (≥2 parties independently mention it); or audited manual confirmation. A 24h timeout downgrades to `suspected_diverge` — it never presumes grounding.

The **common-knowledge operator** (iterated mutual belief) is distinct from first-order sharing: if Anne privately tells A, B, and C the same thing, all three believe it (first-order sharing hits) but it is **not** common knowledge (A doesn't know that B knows). `is_common_knowledge` implements the closure: **X's current state is common knowledge among group G iff the latest theme-event any member of G perceived was co-witnessed by all of G (a public establishment).** It is implemented as a set-intersection / fixpoint over perceived `source_event_id` sets, reusing the event-intersection logic of `what_does_X_think_chain`.

### 3.5 Perception/knowledge tracking, BDI+K mental state, faux-pas detection

- **KnowledgeFrontier** captures "what this subject *could* know": the visibility closure is `(presence log) ∪ (explicitly told ∪ accessible sources ∪ group membership) EXCEPT (explicitly told NOT)`, all time-bounded. On top of it, the tri-valued knowledge query `does_X_know → {FullKnowledge, NotKnown, Unknowable}` makes an epistemic distinction most memory systems cannot: "has asserted it" vs. "hasn't, but has a visible evidence path" vs. "no visible path at all."
- **BDI+K mental-state internalization:** the core C++ aggregate `mental_state_of(X) → {beliefs, knowledge, desires, intentions, commitments, preferences}`. Bucketing is **predicate-first then modality** (resolving the "modality=BELIEVES but predicate=prefers" ambiguity), with each statement landing in exactly one bucket. Its doctrine is worth quoting: **the capability lives in the C++ core, available out of the box; the eval server / OpenClaw / future bindings are thin consumers, not re-implementations.**
- **Faux-pas detection:** `detect_faux_pas` scans `cast × themes`, classifying who holds a stale view (left before the state changed) via `what_does_X_think(...).is_stale`, producing the *structural precondition* of a gaffe (semantic sensitivity is explicitly not judged here).
- **Entity/theme grounding:** the seam that makes all of the above actually *hit*. One eval scored just 0.39 — perception was "95% correct on every probe that grounds," but "59/100 probes never ground" due to **surface drift at the grounding seam** ("Xiao Hong" vs "XiaoHong"; "cabbage" vs "the cabbage" vs "cabbages" compared by raw exact match). The fix adds a deterministic `normalize_theme` (article-strip + conservative singularization) *before* the byte-parity-frozen `canonicalize_object`, leaving the hash unchanged. End-to-end lift: **location-false-belief precision 0.39 → ~0.78, grounding rate 0.41 → ~0.83.**

### 3.6 Perspective-aware retrieval and the "mind summary"

The retrieval planner reconstructs context per the four-tuple `(querier, perspective, intent, goal)`, not as a fan-out of tools. `PlannerQuery` carries `querier` (who is asking), `perspective` (from whose viewpoint), `intent`, and `target`. The **9 QueryIntents:** `FACT_LOOKUP, BELIEF_OF_OTHER, META_BELIEF, HISTORY, COMMITMENT_DUE, PREFERENCE, NORM_LOOKUP, COMMON_GROUND, ABSTAIN_CHECK`.

The **7-step pipeline:** `parse → mask → plan → fetch → fuse → ground → abstain`. One hard invariant defines the system's privacy stance: **the perspective filter must run before semantic ranking** — the `mask` step applies the target's `KnowledgeFrontier` as an EnigmaToM-style iterative mask, a non-bypassable privacy boundary; the retrieval receipt must *prove* the filter ran (`frontier_masked_count`) or results are not returned. The perspective snapshot is given by `perspective_take(target)` = `(filter by target's visible-evidence set) ⊕ (target's belief subgraph) ⊕ (shared common ground)` — any dialogue/planning/negotiation calls it first, then decides.

The output is not undifferentiated RAG text but a **"mind summary" with 8 pragmatic tags**, letting the LLM understand each memory's epistemic status: `FACT` (settled consensus), `BELIEF` (one party's view + confidence), `HEARSAY` (single source, possibly stale), `INFERRED` (from behavior), `COMMON` (all parties know), `TODO` (commitment + deadline), `CONFLICT` (parties disagree, unresolved), `ABSTAIN` (no reliable memory). Reranking fuses relevance, recency, salience, activation, and affect-consistency. **Abstention** fires on four conditions (priority `frontier > recanted > conflict > score`): masked-to-empty, only-recanted evidence, unresolved conflict, or max-score < 0.25 — emitting a structured "I don't know, because ___" rather than a fabrication. The receipt's four-valued `sufficiency` (`SUFFICIENT/MISSING_INFO/NEEDS_RAW/ABSTAINED`) lets evaluators distinguish "not found" from "permission-masked" from "projection-stale" from "actively abstained."

### 3.7 The Persona container: a stable portrait of the other

`Persona` is a **materialized view**, not a Statement: the authoritative facts stay in the Statement graph, and the container is rebuilt by `Bus.rebuild_container` under a single-version CAS. Its **two-channel** design maps onto neuroscience: Persona is the **slow channel** (updated every N sessions via Replay, mapped to vmPFC's stable self/other model), while per-holder beliefs are the **fast channel** (updated every write, mapped to dmPFC's fast social-belief update) — a single session never touches Persona. **Multi-source arbitration:** the `self_model_anchor` (the subject's self-statements) beats the `profile_anchor` (others' statements about them); when both exist and their confidence gap ≥ 0.5, it marks `suspected_diverge` and defers to the ToM Engine rather than writing. Concurrent rebuilds are guarded by optimistic CAS, throwing `ConcurrentRebuildError` with no auto-retry on a version mismatch.

---

## 4 Brain-Like Dynamics (Pillar 2)

If Pillar 1 is "what to remember and for whom," Pillar 2 is "how memory lives over time." Starling's dynamics are not a metaphor — each is landed in formulas, parameters, and auditable state machines. One governing fact: **the Hippocampus and the Neocortex are logical partitions over a single `statements` table, distinguished only by the `consolidation_state` column — not physical tables.** "Moving" a memory between stores = flipping a string label + emitting a Bus event. This is itself the design's reading of CLS as "cross-view flow."

### 4.1 Complementary Learning Systems (CLS)

Axiom II is CLS verbatim-engineered (McClelland et al., 1995): writes first enter the Hippocampus (`VOLATILE`, fast in-and-out to resist catastrophic forgetting) and rise into the Neocortex as stable semantics only after replay, pattern separation/completion, and reconsolidation. The Neocortex accepts no direct writes — only post-consolidation via the Bus — and holds **five subzones:** Semantic / Procedural / Norms / Personae / CommonGround. The EngramStore is **peer to** the Hippocampus/Neocortex (pointed at by `Statement.evidence`), the engineering of "the hippocampus always keeps the verbatim original"; its ingest policy includes a **self-pollution guard** — `SYSTEM_INTERNAL/REPLAY_OUTPUT` are always `NO_STORE`, so replay outputs can't be re-ingested as fresh evidence.

### 4.2 The six-state consolidation lifecycle

`consolidation_state` is a first-class column spanning a memory's whole life. Six states (parity-asserted on both the C++ and Python sides):

| State | Semantics |
|---|---|
| `VOLATILE` | just written to the hippocampal partition, unconsolidated |
| `REPLAYING_CONSOLIDATING` | selected from VOLATILE; first consolidation into the neocortex |
| `REPLAYING_RECONSOLIDATING` | recalled from CONSOLIDATED/ARCHIVED; re-consolidation of an existing version |
| `CONSOLIDATED` | settled in the neocortex, long-term queryable |
| `ARCHIVED` | long-unrecalled; off the hot path but index-retained, still recallable |
| `FORGOTTEN` | removed from all retrieval; EngramStore handled per retention_mode |

The state machine declares 11 legal transitions (T1–T11 + T7-P1), but at runtime it is guarded **not by a `can_transition` function but by per-edge SQL compare-and-swap (CAS):** each store method carries a `WHERE consolidation_state='<from>'` clause, so an illegal or duplicate transition matches 0 rows and becomes a silent idempotent no-op — eliminating concurrency races by construction. Backstops: an oscillation cap `MAX_CONSOLIDATION_ATTEMPTS=5` (force CONSOLIDATED + pending-review beyond it), a VOLATILE TTL of 7 days (unless in the Affect Buffer), decay protection for unsettled commitments, and decay-exemption for common-ground entries.

### 4.3 Replay scheduling: forgetting curve, SWR sampling, consolidation ops, three modes

**Forgetting/decay curve (Ebbinghaus).** Pure exponential retrievability:

```
S(t) = exp(-Δt / S0)
S0 = 86400 · (1 + 0.5·access_count) · (1 + salience)
        · (1 + 2.0·active_grounded) · decay_modifier(modality) · (1 + 0.3·|valence|)
```

`decay_modifier` by modality: **COMMITS=4.0, NORM_OUGHT=3.0, KNOWS=2.0, BELIEVES=1.0, ASSUMES=0.5** — commitments resist decay ~8× longer than assumptions. A statement archives when `S(t) < 0.05` and not `active_grounded`. This fuses MemoryBank (Ebbinghaus) with Anderson's active forgetting.

**Sharp-wave-ripple (SWR) priority sampling** (hippocampal SWR + prioritized experience replay, PER):

```
w = salience · novelty_decay(last_replayed) · (conflict?1.5:1) · (1 + 0.4·arousal)
       · (goal_relevant?1.5:1) · provenance_factor / (1 + replay_count)
```

`provenance_factor`: `user_input=1.0`, `tom_inferred=0.25`, derived kinds = 0. Three hard gates precede the formula: provenance 0 → 0 (derived/reconsolidation statements never re-enter the sampling pool, **breaking replay loops**), `derived_depth ≥ 3` → 0, and a 5-minute cooldown. Neuroscientifically, hippocampal SWRs preferentially reactivate high-salience, high-novelty, high-prediction-error episodes during rest (Buzsáki; Mattar & Daw, 2018; Schaul et al., 2015).

**Consolidation operators.** The kernel's `enum ConsolidationOp { Compress, Abstract, Reinforce, Decay, Reconcile }`: compress (cluster-merge similar episodes), abstract (multi-holder same-predicate → feeds Persona rebuild), reinforce, decay (→ARCHIVED), reconcile (route conflict to reconsolidation; replay itself does not arbitrate). **Three scheduling modes** map onto awake/quiet-rest/sleep replay: Online (every 3 writes, sample 3, compress only), Idle (sample 30 + gist proposals), Sleep (full sweep of 200 + full gist write).

**Gist semanticization (sleep-time abstraction).** A NORM-gist requires ≥3 distinct holders asserting the same `(predicate, object-hash)`, judged by an LLM at confidence ≥0.6, then passed through **an independent per-member entailment-verification LLM** (the load-bearing guard against confabulation/over-generalization) before being written as an inert norm. This is CLS's "hippocampal detail → neocortical schema" transfer: pooling ≥3 independent episodes into a generalized semantic norm.

### 4.4 Pattern separation and completion

The design maps these onto dentate-gyrus (DG) sparse coding and CA3 autoassociation:

- **Pattern separation (write-time, DG):** on a near-duplicate (cosine > 0.85), apply a **Gram-Schmidt orthogonalization** offset against neighbors and record a `MAY_OVERLAP_WITH` soft edge; it **keeps subtle differences by default rather than merge-deduping (the fundamental difference from mem0)** — "differences are often cognitive cues, not noise; merging irreversibly loses *who* believed *what* *when*."
- **Pattern completion (retrieval-time, CA3):** a spreading-activation walk from ANN seeds, each hop `contribution = activation · edge_weight · decay`, **merging by MAX not sum** (attractor behavior: a node's activation = its strongest path), returning a connected episodic subgraph rather than an isolated row.

The **Working Set** (prefrontal active maintenance) assembles within a 2000-token budget by fixed priority `pending commitments > persona > common ground > relevant memories > affect` — a fired commitment is injected as a `⚠ DUE:` line.

### 4.5 Reconsolidation: no overwrite

The thesis: Starling mutates a memory only **after recall/conflict**, and **never deletes the old version** — an engineering analog of brain plasticity, contrasted with mem0's destructive UPDATE.

- **Plastic window (Nader, 2000):** the reconsolidation engine is an outbox subscriber; recall does not open a window directly but emits an event consumed asynchronously. Four opening triggers: `statement.recalled / references_existing / belief.conflict / reconsolidate.requested`. Duration is adaptive: default 30 minutes; by modality `COMMITS=360 / NORM_OUGHT=180 / KNOWS=60 / BELIEVES=30 / ASSUMES=5` minutes; high-frequency targets shrink to 5; clamped to **5 minutes–6 hours** (the 6h ceiling cites Nader's 2000 neuroscience reference).
- **Arbitration on recall:** at window close, aggregated evidence yields a `strength` falling into three paths: **<0.3 Supports** (confidence ↑ → CONSOLIDATED), **[0.3,0.7] MildContradict** (confidence ↓ + append history, **provenance unchanged, no new version**, avoiding chain growth from small nudges), **>0.7 SevereContradict** (goes to supersedes).
- **Supersedes chain (preserved, not deleted):** a severe contradiction commits 4 items atomically inside a SAVEPOINT (nested, not BEGIN) — fork a new row (`supersedes_id = old id`, deliberately *not* emitting `statement.written` to avoid replay re-entry), write a `supersedes` edge, **archive the old row rather than delete it**, and emit 3 events. At the schema level, `BEFORE UPDATE` triggers `RAISE(ABORT)` on any in-place edit of identity fields, forcing the supersedes path.

### 4.6 Affect and salience modulation

The `AffectVector` has five dimensions: `valence[-1,1], arousal[0,1], dominance[-1,1], novelty[0,1], stakes[0,1]` (the PAD/VAD triple + two appraisal knobs). Salience reduction:

```
salience = (0.4+0.6·|valence|)·(0.4+0.6·arousal)·(0.3+0.7·novelty)·(0.3+0.7·stakes)·(0.6+0.4·surprise_decay)
```

Affect modulates memory at several points: the replay-sampling `(1+0.4·arousal)` (amygdalar/noradrenergic modulation of consolidation, McGaugh), the forgetting `(1+0.3·|valence|)` (emotional-memory enhancement; flashbulb memories), the retrieval-rerank affect-consistency (mood-congruent recall, Bower), and the Affect Buffer's 7-day TTL exemption for high-salience VOLATILE rows (a synaptic-tag-and-capture analog).

> **Implementation candor:** we report the true "wired vs. designed-reserved" status. The write path currently leaves `affect_json` empty and a content-driven appraiser is not yet online (slated for P3), so apart from second-order ToM salience inheritance (×0.8), most affect terms run on birth-neutral values; `appraise_emotion` (an OCC/Scherer appraisal-theory operator) is presently a research/design draft. **Fully wired today** are: the six-state CAS lifecycle, SWR-weighted replay (salience/arousal/novelty/provenance), Ebbinghaus decay plus the compress/decay ops, gist semanticization, DG pattern separation + CA3 completion, the full reconsolidation supersedes machine, and the prospective tick loop firing time triggers with no query.

### 4.7 Prospective memory: woken without a query

The prospective loop lets the agent act proactively with no user query. The **Commitment five-state machine** (`ACTIVE/FULFILLED/BROKEN/RENEGOTIATED/WITHDRAWN`) guards every transition atomically with `WHERE state='ACTIVE'`: fulfill → FULFILLED; deadline expired with `broken_count<3` → BROKEN; `≥3` → auto-WITHDRAWN (chronic failure); renegotiation chain <3 → RENEGOTIATED (+ supersedes edge + new ACTIVE), ≥3 → blocked. BROKEN is non-terminal ("they promised again later"). **Four trigger types:** time (ISO instant), event (event type), state (field predicate, whitelisted against injection), compound (all_of/any_of, recursive, depth ≤16). **ActionGuard** is fail-closed (`Allow/RequiresApproval/Blocked`) and guards external actions.

The "no-prompt" loop is concrete: the dashboard engine spawns a 30-second daemon thread `starling-bg-tick → tick_all → policy.tick`, which — with no event at all — still fires due TimeTriggers (`commitment.fire`) and breaks/auto-withdraws overdue commitments, entirely self-initiated. A fired commitment surfaces as a `⚠ DUE:` line in the Working Set and is pushed to the UI over WebSocket. The **intention-superiority effect** has an engineering analog: an active commitment shields its statements from decay via the `active_grounded` flag, lifted by `commitment.released` on completion (cf. McDaniel & Einstein's multiprocess framework; Goschke & Kuhl's intention-superiority).

### 4.8 Neuroscience anchors, summarized

| Mechanism | Neuroscience basis |
|---|---|
| Fast/slow dual systems, six-state consolidation | Complementary Learning Systems (McClelland et al., 1995); episodic/semantic (Tulving, 1985) |
| SWR priority replay | Hippocampal sharp-wave ripples (Buzsáki); prioritized experience replay (Mattar & Daw, 2018; Schaul et al., 2015) |
| Forgetting curve / active forgetting | Ebbinghaus forgetting curve; Anderson active forgetting |
| Pattern separation / completion | DG sparse coding / CA3 autoassociation (Yassa & Stark, 2011) |
| Reconsolidation plastic window (5min–6h) | Reconsolidation (Nader, 2000) |
| Affect modulation | Amygdalar emotional consolidation (McGaugh); mood-congruent recall (Bower); PAD dimensions (Mehrabian-Russell) |
| Goal-reconstructed retrieval | Self-Memory System (Conway, 2000) |
| Prospective memory | Time/event dual-process (McDaniel & Einstein); intention-superiority (Goschke & Kuhl); BA10 (Burgess) |
| Social-relation modeling | Fiske's four relational models |

---

## 5 High-Order Belief Reasoning: Evaluation (Pillar 3)

This is the section that most demands honesty. We give **defensible headline results**, the **per-order distribution** of the gain, and **where the system does not help or actively hurts, and why.** Every number is verified against first-hand eval artifacts (ToMEval `metrics.json`) or committed in-repo docs, and we explicitly separate **clean/current** numbers from **artifacts the project itself retracted**.

### 5.1 Setup: Starling-in-the-loop, three modes

Three measurement modes must not be conflated:

1. **Bare-LLM ToM floor:** the MCQ goes straight to the LLM, Starling untouched — "how high can the model get on its own." `max_tokens=32768` (a reasoning model's hidden CoT counts against the budget; too small a cap truncates to empty and mis-scores).
2. **Starling-machinery-only:** the nesting is produced by **deterministic C++** (`belief_tracker → what_does_X_think_chain`), not LLM reasoning; `--mode deterministic` seeds beliefs from the templated question to isolate the memory machine.
3. **Starling-in-the-loop, end-to-end** (`scripts/starling_tomeval_server.py`): an OpenAI-compatible endpoint the external ToMEval harness POSTs to. Per request: parse the story → `remember()` into a throwaway Starling DB (the LLM drives extraction) → dump the scaffold → the LLM answers the MCQ augmented with the dump. **The same LLM is both Starling's extractor and the final answerer** — so this mode measures whether structured memory *helped the model*. Injection by priority: order≥2 nested questions get `chain`; common-knowledge questions get `ck`; otherwise belief_digest/mental_state/faux_pas/memory_dump.

The gating flags *are* the safety mechanism: `STARLING_CHAIN_ONLY` (inject only on order≥2, since order-0/1 injection measured a net −0.096), `STARLING_PASSTHROUGH` (zero-injection paired baseline), `STARLING_NO_THINK_EXTRACT` (append `/no_think` to extraction prompts, because thinking-model `<think>` traces break the extraction parser), `STARLING_NO_THINK_ANSWER` (tell a weak model to read the injection, not re-derive it).

Models tested: deepseek-v4-pro (primary in-loop LLM + answerer), deepseek-v4-flash, local Qwen3-14B (v3.4) and Qwen3-8B (v3.2); gpt-5.5 etc. appear only in bare-LLM baseline tables. (Note: "o3/o4" in the docs means **HiToM order-3/order-4**, *not* model names.) Significance uses same-id paired McNemar / binomial tests.

### 5.2 Datasets

| Dataset | Measures | Order / structure |
|---|---|---|
| **HiToM** | nested false belief in multi-room, multi-agent stories with deception | **order 0–4**, 240 items/order; order-k = "A thinks B thinks … (k deep) X is where" |
| **ToMBench** | 8 social-cognition ability families | first/second-order false belief + Desire/Intention/Knowledge/Emotion/Non-literal/Hinting/Persuasion |
| **ToMBench 2nd-order subset** | Perner-Wimmer second-order false belief | 200 items (196 clean) |
| **FanToM** | information asymmetry in multi-party dialogue | factual/belief/answerability (bare-LLM profiling only) |
| **Commitment** | promise/deadline tracking | 100 scenarios, offline-deterministic, no LLM |
| **LongMemEval** | long-horizon memory | time-reasoning / knowledge-update subsets |
| **CK v1/v2** | iterated mutual belief / common knowledge | v1 co-presence gold, v2 announcement gold |

### 5.3 Headline results

**Bare-LLM ToM floors (no Starling):**

| Dataset (N) | deepseek-v4-pro | gpt-5.5 |
|---|---|---|
| HiToM (1200) | 0.7458 | 0.7758 |
| ToMBench (5720) | 0.8271 | 0.8509 |
| FanToM (11292) | 0.8612 | 0.8841 |
| BigToM (5000) | 0.9068 | 0.9160 |
| EmoBench (800) | 0.7275 | 0.7425 |

**Admission gate (Starling machinery / end-to-end):**

| Track | Result | Threshold |
|---|---|---|
| ToMBench 1st-order (24), deepseek-v4-flash ×3 | **1.000 / 1.000 / 1.000** | ≥0.55 ✅ |
| ToMBench 2nd-order — bare-LLM floor | **0.990** (clean 194/196) | ≥0.70 ✅ |
| ToMBench 2nd-order — Starling machine (deterministic) | **1.0000** (196/196) | ≥0.70 ✅ |
| ToMBench 2nd-order — end-to-end (extracted) | **1.0000** (195/195) | ≥0.70 ✅ |
| ToMBench full profile (2860), deepseek-v4-pro | **0.8315** (2378/2860) | profile |
| Commitment (100) — detection / timeliness | **1.0000 / 1.00 turns** | >0.80 / <3 ✅ |
| LongMemEval (24×3) — time / knowledge-update | **1.0000 / 1.0000** | ≥0.55 ✅ |
| Perception location-FB (100) — end-to-end precision | **0.39 → ~0.78** | — |

ToMBench full, by ability family: strongest **Multiple Desires 1.0, False Belief 0.97, Hinting 0.95**; weakest **Emotion Regulation 0.35, Discrepant Desires 0.45, Persuasion 0.52** — losses concentrate on abilities needing fine emotional/motivational inference rather than tracking.

### 5.4 The high-order story: gains concentrate at the deepest orders

**The cleanest, most defensible result — Qwen3-14B v3.4** (same-day paired, 0 fallback, 0 extraction failures):

| order | baseline (overall 0.7925) | +Starling (overall **0.8342**) | Δ |
|---|---|---|---|
| 0 | 1.000 | 1.000 | 0 |
| 1 | 0.9125 | 0.925 | +1.3 |
| 2 | 0.7292 | 0.733 | +0.4 |
| **3** | 0.6625 | **0.7708** | **+10.8** |
| **4** | 0.6583 | **0.7417** | **+8.3** |
| **overall** | 0.7925 | **0.8342** | **+4.2pp** (p≈1.9e-5) |

The gain is **monotonically concentrated at the deepest orders (3/4)** — exactly where CoT working memory begins to break down and the deterministic "co-witness intersection" operator pays off. Orders 0/1 are flat (the model already handles them), which is precisely why `CHAIN_ONLY` gates injection to order≥2.

**The stronger deepseek-v4-pro:** fixed-Starling 0.8025 vs. an archived baseline 0.738 = **+6.4%**, with order-3 +16.7pp and order-4 +15.8pp. Honesty demands a caveat: the project's own notes record that 0.738 baseline as depleted by ~64 proxy fallbacks; against cleaner same-repo baselines (0.7458/0.7508) the fix is **+5.2–5.7pp**; but **the order-3/4 lift of +14–17.5pp is robust regardless of which baseline is chosen.** The defensible framing is therefore: **~+5–6.4pp overall, concentrated in orders 3/4.**

Three generalizable fixes underwrite this gain: **(1) room-scope awareness** (`perception_reconstructor.cpp`: a character who left a room no longer mis-witnesses moves in others); **(2) observation/hearsay separation** (`mentalizing_chain.cpp`: first-hand observation is primary, tell/lie only fills gaps); **(3) the `CHAIN_ONLY` competence gate** (inject only order≥2).

> **A retracted artifact (do not cite):** an earlier "+4.4" result was judged by the project to be a *depleted-baseline artifact* — a clean (unfixed) Starling rerun vs. the archived baseline was actually −0.005 (≈ baseline). The report discards it accordingly.

### 5.5 The weak-model sweet spot and the extraction dependency

Applying the same injection to the weaker **Qwen3-8B v3.2** gives overall ≈ −1.4pp (p=0.24, not significant) — extraction degrades on hard stories → the chain miscomputes → no net gain. The sweet-spot condition is thus clear: **the model must be strong enough to extract reliably AND still have a nesting gap**; 14B qualifies, 8B does not. Starling's deterministic operators are an *amplifier, not magic*: they depend on one good extraction that turns the story into trackable perception state.

### 5.6 The honest boundary: where it doesn't help, where it hurts, and why

One inequality governs everything: **deterministic injection helps ⟺ `det_acc(task) > cot_acc(task)`** — because the same LLM walks both paths, there is a net gain only when the operator captures multi-step mechanical tracking (deep co-witness intersection) the model's free reasoning drops. That regime is narrow.

| Probe | Result | Verdict |
|---|---|---|
| ToMBench in-loop (300 / full 5720) | +1.3pp (p=0.39) / −0.05pp | flat |
| ToMBench layered "optimization" | net +4 → −1 → −9 (worse each layer) | hurts |
| **CK v1** (co-presence gold) | +9.2pp (p=4.8e-7) | **definitional artifact**: the gold *is* the operator's own co-witness definition; injection overrides deepseek's more defensible reading |
| **CK v2** (announcement gold) | +0.83pp (p=0.5) | boundary: no real gap |
| faux-pas (ToMBench) | operator fires 0/6 → inert | structural mismatch |
| ExploreToM literary order-2 | **−19.6pp** | literary prose breaks extraction |
| SocialMind Chinese literary 1st-order | **−8.9pp** | same |
| info-flow scaffolding interface | **−8.9pp** | hurts |

> **Evidence levels.** The HiToM per-order results, the ToMBench/admission tables, and the in-loop ToMBench numbers are read from committed eval artifacts (`metrics.json`). The ExploreToM (−19.6pp), SocialMind (−8.9pp), and scaffolding (−8.9pp) hurt-deltas, together with the 14B/8B p-values, come from exploratory PoC runs not committed as `metrics.json`; they are reported here as directional evidence, not as primary benchmarks.

**Why deepseek doesn't need help:** the boundary study proves directly that deepseek, *given stipulated conventions*, solves every structured tracking task at ceiling — including order-5 six-agent chains with forced re-convergence (15/15). The HiToM gain is fundamentally **convention-enforcement on an under-specified benchmark** (room-scoping + observation-primacy), not a compute-capability gain. Residual HiToM misses use *non-standard nested gold* (deepseek gets them wrong too; standard recursive ToM ≠ HiToM's gold); matching them would mean reverse-engineering the generator = eval-fitting, which is forbidden — so we stop at the generalizable ceiling.

### 5.7 The semantic-routing safety gate

Since the helpful regime is narrow and the harmful regime is real, the key to productization is a **never-hurt gate.** An LLM router maps any question/language to `{operator, agents, theme}` or `NONE`; gating injection through it pulls the worst case of indiscriminate injection from **−8.9pp back to −0.7pp (≈ neutral).** This converts Starling from "sometimes hurts" to "helps or neutral," and is the piece judged shippable.

### 5.8 Reproducibility and operational caveats

The load-bearing caveats are baked into the code: the **fd leak** (the in-loop server must `mem.close()` + `gc.collect()` + unlink the temp DB per request, else after thousands of requests libcurl cannot get a socket → empty answers — the true cause of the early "70% fallback," not rate-limiting); **silent extraction failure** (on adapter error the path degrades to empty, so the server emits a parseable `\boxed{A}` fallback rather than an empty string); **HTTP transport** (the baseline is routed through the C++ adapter forcing HTTP/1.1 to avoid HTTP/2 tail-stall under 24-way concurrency); and `max_tokens=32768`. Most p-values come from one-off PoC scripts (uncommitted) and are flagged as such.

---

## 6 A Worked Example: Alice / Bob / Carol

One scenario threading all three pillars. **Input:** Alice says in a group chat, "Bob is no longer on auth; Carol takes over now."

**Write (§3.1 + §4.5).** Four Statements are extracted:

| ID | holder | subject | predicate | object | modality | polarity |
|---|---|---|---|---|---|---|
| S1 | self | Bob | responsible_for | auth | BELIEVES | NEG |
| S2 | self | Carol | responsible_for | auth | BELIEVES | POS |
| S3 | self | Alice | BELIEVES | ⟨S2⟩ | — | POS (2nd-order) |
| S4 | Alice | Bob | responsible_for | auth | BELIEVES | NEG |

Event sequence: `evidence.appended → statement.written ×4 → belief.conflict → corrected + archived + superseded`. The old "Bob is on auth" statement is hit by the conflict probe; the severe-contradiction path atomically writes the new version + a supersedes edge + archives (does not delete) the old one in one transaction. High salience enters the Affect Buffer; ToM updates common ground (everyone present → Bob marked "should know").

**Retrieval (§3.6).** Query "Is Bob still on auth?" (intent=`FACT_LOOKUP`): parse → mask (querier=user, no masking) → Neocortex hits the supersedes chain → EngramStore fetches Alice's quoted span → `ToM.shared_with([self,user])` checks common ground, finds it unshared → proactive grounding. The Context Pack returns three tags: `[FACT]` Bob is no longer on auth, Carol now owns it (with EngramStore evidence), `[HISTORY]` Bob owned it for ~8 months, `[COMMON]` this is the first time I'm telling you — confirm you're aware?

**Meta-belief (§3.3c).** Query "Does Bob know this?" (intent=`META_BELIEF`): `does_X_know(Bob, ⟨Carol now responsible⟩)` decided via the KnowledgeFrontier — if Bob was absent from the announcement and has no visible path, it returns `NotKnown`, prompting "you may need to sync this to Bob." This is exactly the epistemic distinction a subject-less vector store cannot express.

---

## 7 Related Work

**vs. mainstream agent-memory stacks.** Starling positions itself as cognitive middleware, not a replacement: any open-source system can be a SubstrateAdapter backend, with Starling layering holder + Statement + ToM + Replay + Prospective on top. Concretely: **mem0**'s `actor_id` is the embryo of holder, and its `{user_id, agent_id, run_id, actor_id}` map to `Cognizer.id`; Starling adds second-order ToM + commitment triggers + holder-dimension isolation. **Letta**'s sleeptime → Replay, shared_blocks → CommonGround, ToolRulesSolver's 8 rules → ActionPolicyGraph, and its Identity ORM is a direct design reference for Cognizer. **Graphiti** is episode-first and **has no holder dimension** (migration must add it); its `valid_at/invalid_at/expired_at` map to Starling's temporal fields and supersedes. **cognee**'s DataPoint subclasses → Statement subclasses; its multi-user access control → ProfileCapability. The core difference: these systems record subject-less facts; Starling records **perspectival, nestable, lifecycle-bearing beliefs.**

**vs. ToM evaluation and social-reasoning research.** ToM benchmarks (ToMBench, HiToM, FanToM, …) measure an LLM's social reasoning; recent work — e.g., the line of improving small-model social reasoning via adversarial cases and trajectory-level alignment — argues that current models often rely on **superficial patterns rather than genuine reasoning.** Starling is complementary but orthogonal to that line: it does not train the model but provides a **deterministic, auditable memory substrate** that makes "who perceived what, who thinks who believes what" explicit; and its evaluation (§5) candidly delineates exactly which regime (deep nesting) this deterministic structure augments a strong CoT model in, versus where it is redundant or harmful.

---

## 8 Design Trade-offs

Every choice corresponds to an abandoned alternative.

| Choice | Alternative | Rationale |
|---|---|---|
| Statement (mandatory holder) as the atom | Memory/Fact as the atom (mem0-style) | schema-level multi-subject isolation; long-term payoff > initial complexity |
| Nested Statement for higher-order ToM | a prompt-layer ToM module | ToM is a data-structure problem, not a model problem; in the schema it is stably queryable, auditable, and free of LLM randomness |
| Six-state machine | three states (DRAFT/STABLE/TOMBSTONED) | six states reflect the CLS consolidation/reconsolidation biology |
| Reconsolidation fork+supersedes | UPDATE the original Statement | a version chain serves ToM/audit/rollback; prevents "I said X but memory overwrote it" |
| Keep differences by default (pattern separation) | merge-dedupe by default | multi-perspective must coexist; differences are often cognitive cues, not noise |
| Async background Replay consolidation | synchronous extract-and-store | sync slows writes and loses the chance to recombine; sleep-time offline replay is the CLS neuroscience basis |
| Single Bus entry + outbox | direct DB writes + triggers | event serialization + cross-subsystem idempotency + restart recoverability |
| Commitments/norms as first-class Statement subclasses | metadata or a side KV table | an industry-wide gap; only first-class citizens can drive runtime behavior |
| Natural-language belief list into the Context Pack | a formal belief base (PDDL) | LLMs understand NL far better than formal logic; formalization is an optional P3+ |
| C++ core + multi-language bindings | pure Python/Rust/Go | predictable latency; zero-overhead abstractions; same-stack as the storage layer |

---

## 9 Limitations and Boundaries

We deliberately close on an honest characterization of boundaries — both as engineering discipline and in the diagnostic spirit of §5.

- **The deterministic operators' value regime is narrow:** only deep nested tracking (HiToM order-3/4) satisfies `det_acc > cot_acc`; generalization to ToMBench/ExploreToM/SocialMind and several interfaces is NULL or harmful. The semantic-routing gate is currently the only "never-hurt" wrapper judged shippable.
- **Strong dependence on one good extraction:** the entire perception/ToM machine takes extraction output as input; a weak model or literary prose degrades it at the extraction seam, causing chain miscomputation (§5.5–5.6).
- **Some brain-like mechanisms are wired but not yet fed:** a content-driven affect appraiser, `appraise_emotion`, recurring/cron triggers, and a full `ActionPolicyGraph` executor are slated for P3+; affect currently runs largely on birth-neutral values (§4.6). We flag this rather than overclaim.
- **LLM extraction cost:** at least one LLM call per Engram; at-scale cost is unestimated. Mitigation: a dedicated small extractor + extraction-dedup caching.
- **Privacy vs. ToM tension:** the system holds metadata like "A thinks B doesn't know X" that must never leak under the wrong perspective — hence the perspective filter runs early in the pipeline and cannot be skipped (§3.6).
- **Conflict retention vs. UX:** keeping multiple perspectives is a design choice, but presenting "3 mutually-conflicting beliefs" can confuse an LLM; mitigation = the Context Pack's CONFLICT tag + confidence ordering + injecting only the top-confidence view by default.
- **Evaluation significance:** most p-values come from uncommitted one-off scripts; FanToM and full ToMBench-5720 are bare-LLM profiling, and in-loop ToMBench-5720 is flat.

---

## 10 Conclusion

Starling Memory recasts "agent memory" from subject-less vector retrieval into an **attribution-bearing, nestable, lifecycle-bearing multi-subject mind representation**, and keeps that memory alive over time with a set of brain-like dynamics landed in formulas and state machines. The three contributions reinforce one another: the attribution-first `Statement` ontology makes higher-order belief stably expressible and queryable; the CLS six-state dynamics let memory consolidate, forget, revise-on-recall, and wake without a prompt; and on high-order belief reasoning, the deterministic nested-tracking operators deliver a robust gain at the deepest orders (Qwen3-14B overall +4.2pp, order-3 +10.8pp; deepseek order-3/4 +15–17pp).

Equally important is our honesty about the boundary: this deterministic structure yields a net gain only in the narrow regime where it is more accurate than a strong model's free reasoning, and we hold the downside with a never-hurt semantic-routing gate. We believe this route — making social cognition an *auditable data structure and dynamics, not a prompt patch* — offers a clear and falsifiable direction for the memory systems behind long-horizon human-AI collaboration.

---

## References (selected)

- McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). *Why there are complementary learning systems in the hippocampus and neocortex.* Psychological Review.
- Tulving, E. (1985). *Memory and consciousness.* Canadian Psychology.
- Yassa, M. A., & Stark, C. E. L. (2011). *Pattern separation in the hippocampus.* Trends in Neurosciences.
- Nader, K., Schafe, G. E., & LeDoux, J. E. (2000). *Fear memories require protein synthesis in the amygdala for reconsolidation after retrieval.* Nature.
- Conway, M. A., & Pleydell-Pearce, C. W. (2000). *The construction of autobiographical memories in the self-memory system.* Psychological Review.
- Mattar, M. G., & Daw, N. D. (2018). *Prioritized memory access explains planning and hippocampal replay.* Nature Neuroscience.
- Schaul, T., Quan, J., Antonoglou, I., & Silver, D. (2015). *Prioritized Experience Replay.* arXiv:1511.05952.
- McGaugh, J. L. (2004). *The amygdala modulates the consolidation of memories of emotionally arousing experiences.* Annual Review of Neuroscience.
- Bower, G. H. (1981). *Mood and memory.* American Psychologist.
- Mehrabian, A., & Russell, J. A. (1974). *An Approach to Environmental Psychology* (PAD model).
- McDaniel, M. A., & Einstein, G. O. (2000). *Strategic and automatic processes in prospective memory retrieval: a multiprocess framework.*
- Goschke, T., & Kuhl, J. (1993). *Representation of intentions: persisting activation in memory* (intention-superiority).
- Fiske, A. P. (1992). *The four elementary forms of sociality.* Psychological Review.
- Chen, Z., et al. (2024). *ToMBench: Benchmarking Theory of Mind in Large Language Models.* ACL.
- He, Y., et al. (2023). *HI-TOM: A Benchmark for Evaluating Higher-Order Theory of Mind Reasoning in LLMs.*
- Kim, H., et al. (2023). *FANToM: A Benchmark for Stress-testing Machine Theory of Mind in Interactions.* EMNLP.

> The kernel mechanisms cited here are verifiable in the corresponding modules (`src/tom/`, `src/replay/`, `src/reconsolidation/`, `python/starling/schema/`); the full design is in `docs/design/system_design.md` and `docs/design/subsystems_design/`; the evaluation harnesses are `scripts/eval_*.py` and `scripts/starling_tomeval_server.py`.
