# Starling Memory: Agent Memory with Multi-Subject Social Cognition and Brain-Like Dynamics

### A Technical Report

**中文版: [Starling_Technical_Report.zh-CN.md](Starling_Technical_Report.zh-CN.md)**

---

## Abstract

Endowing large language model (LLM) agents with Theory of Mind (ToM) — the capacity to infer others' beliefs, intentions, and knowledge states and to act on them appropriately — is usually pursued as a *reasoning* problem, attacked with prompting, chain-of-thought, or reinforcement learning that coaxes the model to "think through" what another mind holds. This report argues an orthogonal position: **Theory of Mind is first a problem of representation, not of inference.** Once the structure of social cognition — who believes what, on what evidence, from whose perspective, and for whom it is mutual — is encoded into the memory substrate itself, mental-state attribution turns from a brittle reasoning chain into a query over a typed graph of beliefs.

On this stance we built Starling Memory and offer three contributions. **First, a multi-subject social-mind representation.** We replace the subject-less *fact* with a holder-attributed *statement* as memory's atomic unit, collapsing five concerns that conventional memory treats separately — attribution, contradiction, retraction, perspective, and recursive belief — into facets of a single representational primitive. **Second, a dual representation of higher-order belief.** We distinguish *symbolic* nesting of propositional attitudes from *situated* reconstruction of perceptual access, and argue that the latter — grounding false belief in *which world-states each agent could observe, and when* — is the cognitively correct basis for higher-order ToM, and the source of our largest gains on nested-belief benchmarks. **Third, brain-like memory dynamics.** Drawing on Complementary Learning Systems (CLS), consolidation, and reconsolidation, we model memory as a dynamical system with fast encoding and slow consolidation, prioritized replay, recall-induced plasticity, adaptive forgetting, and prospective self-cueing — not as a static store.

On the HiToM higher-order ToM benchmark, injecting Starling's deterministic nested-tracking machinery into zing-14b (a 14-billion-parameter reasoning model built on Qwen3-14B) raises overall accuracy from 0.793 to 0.834, with the gain **monotonically concentrated at the deepest reasoning orders** (+10.8 points at order 3, +8.3 at order 4); for a stronger reasoning model (deepseek-v4-pro) the deepest-order gain is larger still, roughly +14 to +18 points at orders 3–4. We characterize the **boundary** with equal rigor: deterministic structure yields a net gain only in the narrow regime where it is more reliable than the model's own reasoning (deep nested tracking), and is redundant or harmful where a strong model already succeeds. That boundary — a falsifiable account of *when structured memory beats free reasoning* — is itself one of our empirical contributions.

---

## 1 Introduction

### 1.1 Theory of Mind: from a reasoning puzzle to a representation puzzle

Theory of Mind is a cornerstone of human social intelligence: understanding that others hold beliefs that may differ from one's own and may be false (false belief) underwrites cooperation, deception, teaching, and empathy. Developmental psychology measures it with the classic Sally–Anne false-belief task (Wimmer & Perner, 1983), and stacks it into higher-order mentalizing — "A thinks B doesn't know that C has changed her mind."

A growing literature asks whether LLMs possess Theory of Mind. The findings are in tension: models do passably on canonical first-order tasks yet degrade sharply under mild perturbation or deeper nesting (Ullman, 2023), suggesting reliance on **superficial patterns rather than robust social reasoning** (Shapira et al., 2024). The dominant response pushes on the *reasoning* side — longer chains of thought, process rewards, adversarial training.

We offer a different diagnosis. In standard retrieval-augmented memory, a memory is a subject-less proposition (a triple or a span of text), and social information is flattened: the speaker, the subject, and the belief-holder collapse into one layer; perspective and evidence become unaddressable. On such a substrate, any question about "who thinks whom believes what" must be reconstructed at reasoning time — brittle and unauditable. We therefore argue: **rather than have the model reason out social structure each time, encode that structure into the representation of memory.** Mental-state attribution should be a *query* over a typed, perspectival, nestable belief graph, not a stochastic inference.

### 1.2 Memory: from retrieval to a brain-like dynamical system

A second tension concerns memory itself. Agent memory has matured into a capable retrieval stack, but its implicit ontology is **static**: written-then-fixed — no consolidation, no forgetting curve, no revise-on-recall, and no prospection that wakes the agent without an external query. Biological memory is precisely a *dynamical system*: Complementary Learning Systems theory (McClelland et al., 1995) holds that the hippocampus's fast encoding and the neocortex's slow consolidation cooperate to balance rapid learning against catastrophic forgetting; a memory becomes briefly labile when retrieved and must re-stabilize (reconsolidation, Nader et al., 2000); emotional salience modulates what is preferentially consolidated (McGaugh, 2004).

We hold that a memory system for long-horizon human-AI collaboration should treat these dynamics as first-class design goals, not after-the-fact patches. This is more than biological analogy: consolidation buffers against extraction noise, the no-overwrite character of reconsolidation preserves the provenance of beliefs for audit and mentalizing, and salience modulation focuses finite computation on what matters.

### 1.3 Contributions

1. **An attribution-first memory ontology (§3.1–3.2):** an argument that taking the *statement* as the atomic unit and the *cognizer* as a first-class subject resolves multi-subject attribution, perspective, contradiction, and recursive belief at the representational level.
2. **A dual representation of higher-order belief, with a cognitive argument (§3.3):** distinguishing symbolic belief-nesting from perception-grounded false-belief reconstruction, arguing why the latter is the correct basis for higher-order ToM, and supporting the claim empirically (§5).
3. **A structural account of common knowledge (§3.4):** characterizing common knowledge as a fixpoint over events co-witnessed by a group, distinct from distributed knowledge.
4. **Memory as a brain-like dynamical system (§4):** unifying the consolidation lifecycle, prioritized replay, no-overwrite reconsolidation, salience modulation, and prospective cueing under CLS, each with its neuroscientific grounding and computational rationale.
5. **A boundary characterization of when structure helps (§5):** a falsifiable criterion — deterministic memory structure yields a net gain on a task iff it is more accurate than the model's free reasoning there — empirically delimited across benchmarks.

---

## 2 Design Philosophy and System Overview

### 2.1 Three axioms

Every mechanism in Starling is generated by three axioms, each grounded in a result from cognitive science or neuroscience.

**Axiom I (Attribution): there are no isolated facts, only statements attributed to a subject.** Every memory is a judgment indexed to the mind that holds it, the perspective by which that mind acquired it (firsthand, quoted, inferred, or hearsay), and the evidence on which it rests. This commitment makes attribution, contradiction, retraction, perspective, and second-order ToM facets of one representation rather than separate engineering problems.

**Axiom II (Two timescales): memory is a cooperation of subsystems at two timescales (Complementary Learning Systems).** New information first enters a fast, labile "hippocampal" form and only settles, after replay, pattern separation, and reconsolidation, into stable "neocortical" semantics, norms, and personas. The fast channel resists catastrophic forgetting; the slow channel accretes structure.

**Axiom III (Goal reconstruction): memory is reconstructed for the current goal, not replayed like a tape (Conway's Self-Memory System).** Retrieval returns a "mind summary" shaped by the querier's perspective and intent, and abstains explicitly when evidence is insufficient, rather than mechanically stitching similar fragments.

### 2.2 Architecture: cognitive middleware with a statement spine

Starling does not rewrite the vector store; it layers a cognitive tier — attribution, Theory of Mind, brain-like replay, and prospection — atop existing memory stacks, and can coexist with mem0, Letta, cognee, or Graphiti. Internally it is organized around a single **statement bus** through which all reads and writes are serialized (yielding cross-subsystem consistency, idempotency, and recoverability); around the bus sit cooperating subsystems for evidence retention, fast/slow memory, subject modeling, mentalizing, replay-driven consolidation, reconsolidation, prospection, and perspective-aware retrieval.

The cognitive kernel is implemented in modern C++ for predictable latency on the hot path, exposed to applications through language bindings. One objective signal is worth noting: among all kernel modules, the **Theory-of-Mind module is the largest by code volume** — social cognition is a first-class, deeply-implemented concern here, not a prompt-layer veneer.

---

## 3 Multi-Subject Social-Mind Representation

This section presents the representational core that separates Starling from retrieval memory. We discuss, in turn: the statement as a unifying primitive (§3.1), the cognizer as an epistemic agent (§3.2), the dual representation of higher-order belief (§3.3), common knowledge as a fixpoint (§3.4), and perspective-aware retrieval with epistemic honesty (§3.5).

### 3.1 An attribution-first commitment: the statement as a unifying primitive

Starling's central representational commitment is that **no proposition exists unowned.** Formally, memory's atomic unit is a *statement*, a nine-tuple:

> Statement = ⟨ holder, subject, predicate, object, modality, polarity, time, evidence, confidence ⟩

where *holder* is the cognizer who holds the judgment; *subject/predicate/object* form the propositional content; *modality* is the propositional attitude (belief, knowledge, desire, intention, commitment, norm, …); *polarity* is affirmation/negation/unknown; *evidence* anchors provenance; *time* distinguishes "when observed" from "when the fact holds"; and *confidence* records graded belief and preserves its revision history.

The theoretical economy of this single shape is that it unifies, as facets of one primitive, five things retrieval memory treats as separate engineering problems:

- **Attribution** is carried directly by *holder* and the perspective field — the same proposition reported firsthand, quoted, inferred, or as hearsay is one shape with a different perspective value, not four special cases.
- **Contradiction** is not resolved by overwrite: two content-equivalent statements of opposite polarity coexist via an explicit conflict relation, because they typically belong to different subjects' perspectives, and the difference is a cognitive cue, not noise.
- **Retraction** is a new statement in a "recanted" attitude layered over the old, the prior version archived rather than deleted, preserving the history of "I once believed otherwise."
- **Recursive belief** — second- and higher-order mentalizing — arises naturally by letting the *object* slot recursively reference another statement (§3.3).

Making the propositional attitude (*modality*) explicit, and in particular promoting **commitments** and **norms** to first-class attitudes, has an under-appreciated consequence: only thus can a memory like "I promised to deliver by Friday" drive runtime behavior — prospective reminders, fulfillment tracking, trust updates — rather than lie inert as text. This is where Starling parts ways with stashing social information in metadata.

> **A principle running throughout.** Whatever a representational structure can stably solve, we do not delegate to runtime model inference. Theory of Mind is a data-structure problem, not a prompt-engineering one; only in the representation does it become stably queryable, auditable, and free of LLM stochasticity.

### 3.2 The cognizer as an epistemic agent

Rather than model a user as an opaque isolation key (`user_id`), Starling promotes every user, agent, group, or role into a first-class *cognizer* — an addressable epistemic agent carrying: a cross-source stable identity (the same physical person under a different role is a different subject); **directional trust** that rises and falls with fulfilled commitments (A's trust in B is neither B's in A nor the system's in A); a **social relation graph** stored from the observer's vantage, so each party may hold an independent view of the same relationship (informed by Fiske's four relational models: communal, authority, equality, market); and a **knowledge frontier** characterizing what this subject *could* know.

The significance of this promotion is more than tidiness. A subject can be the *referent* of another's belief, or the nested *object* of a deeper one — it is precisely this "a subject can be referenced by a belief" property that makes arbitrary-order mentalizing expressible at the representational level (§3.3). By contrast, a non-cognizer *entity* (a thing, a concept) has no beliefs, trust, or knowledge frontier and may only be talked about, never hold a belief — so "who is entitled to hold a belief" is controlled at the type level.

### 3.3 The dual representation of higher-order belief (a core contribution)

"I think you think X" has two complementary representations in Starling. Distinguishing them is the key to why the system gains on higher-order benchmarks.

**(a) Symbolic nesting: attitudes about attitudes.** A meta-belief is a statement whose *object* recursively references another statement; nesting depth descends along the holder→subject chain. This expresses arbitrary-order propositional attitudes directly as graph structure: in "self believes ⟨Alice believes ⟨the project is delayed⟩⟩," each layer's holder is that layer's believing subject. The chain is queried by a recursive unwind operator; depth is bounded not by a cognitive cap but only by acyclicity and a loose ceiling. A subtle and important design is the **mirror-vs-fabrication distinction**: when a partner has actually expressed a belief, the system may unconditionally form a corresponding meta-belief (a faithful mirror); but to *infer* the partner's order-k belief as a self-held order-(k+1) model requires an **order estimator** to confirm the partner has demonstrated mentalizing at the relevant depth — otherwise it refuses, lest it fabricate deeper mental states the partner never exhibited. The estimator adaptively reads "how many orders deep to model this partner" from the nesting-depth distribution of their recent behavior, no longer saturating at second order as early designs did.

**(b) Perception-grounded false-belief reconstruction (our thesis).** Symbolic nesting expresses beliefs that have been *stated*, but does not explain the *origin* of false belief. We argue: **false belief is fundamentally a question about perceptual access evolving over time, not bare propositional nesting.** Sally wrongly believes the marble is still in the basket because she was *absent* when it was moved. Accordingly, Starling maintains a mechanism independent of symbolic nesting: from the objective events of a scene it reconstructs *the world-state each subject could observe at each moment*, and answers "what does X currently believe the state to be" by X's *last firsthand* observation — and whether that state is "stale" (≠ the current truth) is precisely the false-belief signal.

The higher-order generalization is the crucial part. To answer "c₁ thinks c₂ thinks … cₙ thinks the theme is where," the system takes the holder's last firsthand state **among the events that every observer on the chain co-witnessed** — a cross-subject **co-witness intersection**. It further enforces an **observation-primacy** principle: telling and informing (and even lies) must not override firsthand observation, and only fill gaps for an agent never present. It is this perception-grounded mechanism — not the symbolic nesting — that yields the largest gains on higher-order nested benchmarks (§5). This aligns with a cognitive insight: robust higher-order ToM rests on tracking *information flow* (who learned what, and when), not on formal manipulation of nested clauses.

### 3.4 Common knowledge as a fixpoint over co-witnessed events

Social coordination often relies on *common knowledge* — not merely that everyone knows, but that everyone knows that everyone knows, ad infinitum. It is strictly stronger than distributed knowledge: if Anne privately tells A, B, and C the same thing, all three know it (distributed knowledge holds), yet it is not common knowledge, because A does not know that B knows. Rather than approximate the concept by infinite nesting, Starling gives it a structural fixpoint characterization: **for a group G, the current state of X becomes common knowledge iff the latest relevant event any member of G perceived was co-witnessed by all of G** (a public establishment). Its computation reuses the co-witness intersection of §3.3(b): a private telling cannot satisfy all-co-witnessed and so does not constitute common knowledge; only joint co-presence at a public event closes the infinite regress. Establishing common ground further involves grounding acts (assert, acknowledge, repair, withdraw) and promotion rules — e.g. an assertion can be promoted from "asserted-but-unacknowledged" to "grounded" once all parties were present and no one objected within a few rounds — with timeout downgrades that prevent presuming consensus.

### 3.5 Perspective-aware retrieval and epistemic honesty

By Axiom III, retrieval is a reconstruction for the current goal. Given the querier, perspective, intent, and goal, the planner first does something retrieval memory usually does not: **perspective masking precedes semantic ranking.** It masks by the target subject's knowledge frontier, removing — *before* ranking — what that subject could not possibly know. This is a non-bypassable privacy and epistemic constraint, because the system holds metadata such as "A thinks B doesn't know X," which must never leak under the wrong perspective. This mask-then-rank order is what lets Starling answer counterfactual-perspective questions like "standing in Bob's shoes, how would he understand this?"

What retrieval returns is not undifferentiated text but a **mind summary** with pragmatic annotation: each item is labeled by its epistemic status — settled consensus, a party's belief (with confidence), single-source hearsay, behavioral inference, a pending commitment, or an *unresolved conflict*. When evidence is insufficient, only recanted, in unresolved conflict, or below a relevance threshold, the system **abstains explicitly**, giving a structured "I don't know, because …" rather than confabulating. This epistemic honesty — knowing what one does not know — is, in collaboration premised on reliability, as important as recall.

---

## 4 Brain-Like Memory Dynamics

If Pillar 1 answers "what to remember, and for whom," Pillar 2 answers "how memory lives over time." Starling treats neuroscience not as rhetoric but lands its dynamics as computable, auditable mechanisms. A governing design choice: the hippocampus and neocortex are not two physical stores but two logical *phases* of one memory population, distinguished by a **consolidation state** — "moving" a memory between them is a phase transition. This is the system's reading of CLS as "memory as cross-phase flow."

### 4.1 Complementary Learning Systems: why two timescales

CLS theory supplies the computational motive for two systems (McClelland et al., 1995): a single fast-plastic network learning continually would catastrophically overwrite old knowledge, while a single slow network could not encode new experience promptly. The brain's solution is a division of labor — the hippocampus rapidly encodes episodes, and offline replay during rest slowly interleaves them into neocortical semantic structure. Starling accordingly admits new statements in a labile phase into fast memory, settling them into stable semantics, norms, and personas only after replay and reconsolidation. Slow memory accepts no direct writes, updating only through the consolidation channel — which both preserves the anti-catastrophic-forgetting buffer and provides a gate against LLM extraction noise: statements that fail the consolidation threshold never pollute the stable semantic layer.

### 4.2 The consolidation lifecycle: memory as a continuant

A memory's "consolidation state" is a continuant spanning its whole life, tracing a trajectory from labile, to first consolidation, to settled, to (long-unrecalled) archived, to forgotten — permitting a single retrograde step when recalled, back into the plastic phase (§4.4). This lifecycle unifies operations that retrieval memory keeps disjoint (write, dedup, expire, delete) into transitions of one state machine, letting a few invariants govern global correctness: transitions are mostly one-way, provenance is frozen on write, and only a severe contradiction begets a new version while preserving the old via archival and a supersession chain. Compared with a "draft–stable–tombstone" trichotomy, the richer lifecycle carries the biological distinction between consolidation and reconsolidation, at the cost only of a slightly larger state space.

### 4.3 Prioritized replay: the computational principle of offline reactivation

Consolidation is driven by a **replay scheduler** that emulates the hippocampus's offline reactivation during rest and sleep. Two computational principles run through it.

First, **forgetting is active and structured.** We model a memory's retrievability as exponential decay, S(t) = exp(−Δt / S₀), whose characteristic lifetime S₀ scales with rehearsal frequency (the spacing effect), intrinsic salience, whether the memory is under an active social commitment, and the propositional attitude — a **commitment** resists decay far more strongly than an **assumption** (a lifetime ratio of roughly 8:1). This renders the intuition "important memories decay slowly" as a tunable, cognitively grounded curve (fusing the Ebbinghaus curve with Anderson's active forgetting).

Second, **replay is prioritized.** Inspired by preferential reactivation during hippocampal sharp-wave ripples (Buzsáki) and by prioritized experience replay in machine learning (Schaul et al., 2015; Mattar & Daw, 2018), the scheduler samples by a composite weight: salience, novelty, involvement in an unresolved conflict, emotional arousal, and goal-relevance raise a memory's replay probability, while it decays with the number of prior replays to reflect diminishing returns. A key structural constraint: memories the system itself derived are excluded from the sampling pool, severing the "derive–replay–re-derive" self-excitation loop — a stability condition that must be imposed explicitly when engineering biological replay. Sleep-phase replay also performs **semantic abstraction**: when enough independent subjects assert the same proposition, the system, gated by a double LLM entailment check, pools it into a generalized norm — the engineering counterpart of CLS's "hippocampal detail rising into a neocortical schema."

### 4.4 No-overwrite reconsolidation: the labile-to-restabilize cycle and its epistemic meaning

In neuroscience, a retrieved memory becomes briefly labile and must re-stabilize (reconsolidation, Nader et al., 2000); within this window it can be modified. Starling accordingly stipulates: **a memory becomes plastic only after being recalled or encountering conflict, and a revision never overwrites the prior version.** Recall or conflict opens a **plastic window** (whose duration adapts to the propositional attitude, from minutes to hours, with the ceiling taken from the neuroscience of reconsolidation); when it closes, the system aggregates the evidence accumulated meanwhile and arbitrates: weak corroboration merely nudges confidence without a new version, while a severe contradiction **forks** a new version, links it to the old by a supersession relation, and archives — not deletes — the old.

This "no overwrite" design has a deep **epistemic meaning**, not merely versioning hygiene: preserving a belief's history and provenance lets the system answer "when, and on what basis, did I change my mind," supporting audit, rollback, and second-order reflection on the evolution of its own beliefs; and it categorically avoids the amnesia of destructive updates — "I said X, but memory has overwritten it." Identity-bearing fields (holder, source, perspective) are forbidden in-place edits; every correction must go through the explicit supersession path — elevating "the traceability of memory" to a system invariant.

### 4.5 Salience modulation and prospective memory

**Affect as salience.** Emotion in biological memory is not decoration but a modulator of what is preferentially consolidated, how slowly it decays, and in what mood it is more readily recalled (McGaugh, 2004; Bower, 1981). Starling reduces a low-dimensional affect vector (valence, arousal, novelty, stakes — rooted in the PAD dimensional model) to a salience scalar, and lets it modulate a memory's fate at write, replay, forgetting, and retrieval-reranking. We note candidly that content-driven affective appraisal is currently early-stage, with most affect signals running on neutral defaults — an honest maturity boundary, not a finished capability.

**Prospective memory: woken without a query.** Reactive retrieval returns memory only when asked; prospective memory lets an agent act *proactively* at the right moment — the cognitive prerequisite for fulfilling commitments and intentions (the multiprocess framework of McDaniel & Einstein). Starling realizes it with a **commitment state machine** (active → fulfilled / broken / renegotiated / withdrawn) and typed **triggers** (time, event, state, and their compounds): a background rhythm, with no external query whatsoever, still inspects due time-triggers and raises the corresponding commitment, spontaneously surfacing "it's time to follow up" into working memory. An active commitment also **shields its associated memories from decay** — the engineering image of the psychological "intention-superiority effect" (uncompleted intentions retain heightened accessibility, Goschke & Kuhl). For external actions, a fail-closed **action guard** ensures unauthorized behavior is blocked by default.

### 4.6 Neuroscience anchors, summarized

| Mechanism | Neuroscience / cognitive-science basis |
|---|---|
| Fast/slow dual systems, consolidation lifecycle | Complementary Learning Systems (McClelland et al., 1995); episodic/semantic memory (Tulving, 1985) |
| Prioritized replay | Hippocampal sharp-wave ripples (Buzsáki); prioritized experience replay (Schaul et al., 2015; Mattar & Daw, 2018) |
| Adaptive forgetting | Ebbinghaus forgetting curve; active forgetting (Anderson) |
| Pattern separation / completion | Dentate-gyrus sparse coding / CA3 autoassociation (Yassa & Stark, 2011) |
| No-overwrite reconsolidation | The plastic window of reconsolidation (Nader et al., 2000) |
| Salience modulation | Amygdalar modulation of emotional-memory consolidation (McGaugh, 2004); mood-congruent recall (Bower, 1981) |
| Goal-reconstructed retrieval | Self-Memory System (Conway & Pleydell-Pearce, 2000) |
| Prospective memory | Multiprocess framework (McDaniel & Einstein); intention-superiority (Goschke & Kuhl) |
| Social-relation modeling | Four elementary forms of sociality (Fiske, 1992) |

---

## 5 High-Order Belief Reasoning: An Empirical Study

This section tests the central thesis empirically: does encoding the structure of social cognition into memory improve higher-order belief reasoning? We report gains, and characterize their boundary with equal rigor — the latter being itself a finding.

### 5.1 Research questions and method

We ask three questions. **(Q1)** Can deterministic nested-tracking structure improve a model on higher-order mentalizing tasks? **(Q2)** If so, how is the gain distributed across reasoning orders? **(Q3)** Under what conditions does it hold, vanish, or reverse?

To isolate "the contribution of memory structure," we adopt a **same-model-in-the-loop** paradigm: one LLM both extracts memory from a story and answers the question; Starling sits between, injecting the extracted structured mental state as scaffolding. Because the answerer and the extractor are the *same* model, this paradigm directly measures whether structured memory *helped the model itself*, rather than swapping in a stronger solver. As controls, we add a "bare model" (no injection) and a "machine-only" mode (the deterministic operators answer directly, isolating the memory mechanism). Evaluation spans HiToM (zero- to fourth-order nested false belief), ToMBench (eight social-cognition abilities), and commitment-fulfillment and long-horizon tasks; significance is estimated by item-matched paired tests. Models range from a 14-billion-parameter model (zing-14b) to stronger reasoning models.

### 5.2 Principal finding: the order-dependence of the gain

We evaluate the same mechanism on two models of differing strength: a 14-billion-parameter model reinforcement-tuned for reasoning (zing-14b, trained on Qwen3-14B — our cleanest measurement, a same-day paired run with zero extraction failure on both arms) and a stronger reasoning model (deepseek-v4-pro). In both cases, injecting Starling's nested tracking raises overall HiToM accuracy (zing-14b: 0.793 → 0.834, +4.2 points, paired p ≈ 2×10⁻⁵; deepseek: 0.751 → 0.803, +5.2 points). But the aggregate hides a more meaningful structure — **for both models the gain is monotonically concentrated at the deepest reasoning orders**:

| Order | zing-14b — base → +Starling (Δ) | deepseek-v4-pro — base → +Starling (Δ) |
|---|---|---|
| 0 (fact) | 1.000 → 1.000 (0.0) | 0.992 → 0.933 (−5.8) |
| 1 | 0.913 → 0.925 (+1.3) | 0.958 → 0.921 (−3.8) |
| 2 | 0.729 → 0.733 (+0.4) | 0.675 → 0.733 (+5.8) |
| **3** | 0.663 → **0.771** (**+10.8**) | 0.588 → **0.746** (**+15.8**) |
| **4** | 0.658 → **0.742** (**+8.3**) | 0.542 → **0.679** (**+13.8**) |

This distribution answers Q1 and Q2 for both models: the gain is real, and it appears exactly where each model's own reasoning begins to fail. Orders 0–1 carry no gain — the models are already competent there, and the injection is best gated off; only when nesting deepens beyond what working memory sustains does deterministic co-witness tracking pay off.

The *comparison between the two models* is itself informative. The larger deep-order deltas for deepseek (+15.8 / +13.8 vs. zing-14b's +10.8 / +8.3) do **not** indicate that structure helps stronger models more; they reflect a **lower untutored baseline** — deepseek degrades more steeply with depth (order-4 at 0.542) than the reasoning-tuned zing-14b (0.658), leaving more room to recover. Tellingly, *after* injection the two models converge toward a common deep-order band (order-3 ≈ 0.75 for both; order-4 in 0.68–0.74), because that band is set largely by the deterministic tracker's own accuracy rather than by the base model — Starling supplies a near model-independent floor for deep-order tracking. The two diverge only at the shallow end, where the stronger deepseek is near-ceiling (order-0/1 ≈ 0.95–0.99) and the scaffold can only add noise (−5.8 / −3.8) — a divergence partly confounded, since the deepseek arms, unlike zing-14b's, were not same-day paired. (The deepseek baseline here is a clean run with zero extraction failure; the widely-cited +6.4-point figure uses an earlier, fallback-depleted baseline, and against clean baselines the overall lift is +5.2 to +5.7 points, while the deep-order lift is robust across every baseline choice: +14 to +18 points at orders 3–4.)

What underwrites the gain are three generalizable mechanism refinements, all within the perception-grounded representation of §3.3(b): **room-scope awareness** (a subject who has left is no longer mistaken for having witnessed moves elsewhere), **observation/hearsay separation** (firsthand observation is primary; telling and lies only fill gaps), and a **competence gate** (inject only at order ≥ 2, avoiding interference where the model is already competent). Notably, none of these is a benchmark-specific special case; each is a faithful realization of the principle "false belief is perceptual access."

### 5.3 The boundary: when deterministic structure helps

The answer to Q3 is the most scientifically interesting part of the study. We find a simple criterion governs everything:

> **Deterministic structure yields a net gain iff it is more accurate than the model's free reasoning on the task** (det_acc > cot_acc).

Because the same model walks both paths in the in-loop paradigm, injection helps only when the deterministic operator captures multi-step mechanical tracking (deep co-witness intersection) that the model's reasoning drops. That regime is narrow. We delimit its boundary across benchmarks and report failures candidly:

- **On shallow / flat tasks, the gain vanishes.** In end-to-end ToMBench evaluation, injection is statistically indistinguishable from baseline (flat overall). A strong model already reads first-order beliefs, desires, and intentions straight from the story; the deterministic scaffold is redundant.
- **Beware "gains" that are artifacts.** A +9.2-point gain observed on one common-knowledge subtask proved, on inspection, to be a **definitional artifact**: the gold answers happened to adopt our operator's own co-witness definition, so injection merely overrode the model's more conservative reading; on a harder variant whose gold does not favor the operator, the gain falls to non-significance.
- **On out-of-distribution narratives, injection hurts.** On literary, Chinese-language, or scaffold-restructured narratives, extraction degrades under complex prose, the downstream machinery miscomputes, and the net effect is −9 to −20 points.

Together these boundaries support a conclusion that is unsurprising yet often evaded: **when the augmented model is already strong, it is itself an excellent belief tracker**; the value of deterministic structure lies not in "making the model reason better" but in "tracking for it within the narrow seam where its mechanical tracking fails." The HiToM gain is, in essence, the *enforcement of conventions* on an under-specified benchmark (making room-scope and observation-primacy explicit), not a lift in reasoning capability. We therefore stop at the generalizable ceiling, declining to chase higher fitted scores by reverse-engineering the benchmark's generator.

### 5.4 From boundary to deployable safety

Since the helpful regime is narrow and the harmful regime is real, deploying deterministic injection unconditionally is not robust. We therefore introduce a **semantic-routing gate**: a lightweight discriminator decides whether a question falls within deterministic structure's helpful regime, injecting only when it does. The gate pulls the worst-case degradation of indiscriminate injection on out-of-distribution narratives from −9 points to −0.7 points (near-neutral), converting the system from "sometimes hurts" to "helps or at least does no harm." This is a falsifiable, deployable design distilled from an honest negative result — and it echoes our overall methodology: treat memory structure as a *conditional* augmentation, not an unconditional panacea.

> **On evidence levels.** This section's HiToM per-order results and ToMBench tables come from controlled, reproducible eval artifacts; the magnitudes for out-of-distribution narratives (literary, cross-lingual, scaffolded) and some paired p-values come from exploratory runs and are reported as directional, not primary. All "gains" presume the same-model-in-the-loop setting and measure the marginal contribution of memory structure to that model.

---

## 6 An Illustrative Scenario

Suppose Alice announces in a group chat: "Bob is no longer on auth; Carol takes over." This one utterance exercises all three pillars at once. **At the representational layer**, the system extracts several perspectival statements: that self believes Bob is no longer responsible and Carol now is; a second-order belief — that self believes *Alice believes* Carol is now responsible; and a statement held by Alice (she asserts Bob is no longer responsible). The old "Bob owns auth" statement severely contradicts the new information, so reconsolidation triggers: a new version is forked and the old is archived and linked by supersession rather than deleted — the history "Bob owned it for ~8 months" is preserved for later reference.

When the user later asks "Is Bob still on auth?", the **retrieval layer** follows the supersession chain to the current fact, attaches the evidence span of Alice's original words, and checks whether this is yet common ground with the user — if not, it proactively notes "this is the first time I'm telling you." And when asked "Does Bob know this?", the **social-cognition layer** does not retrieve a record but queries Bob's knowledge frontier: if he was absent from the announcement and has no other visible path to learn it, the system judges that he *does not yet know*, and accordingly suggests syncing it to him. That "Bob doesn't know" judgment is exactly the epistemic distinction a subject-less vector store cannot express and an attribution-first representation yields naturally.

---

## 7 Related Work

**Theory of Mind and LLMs.** A line of work probes LLM social reasoning with false-belief tasks (ToMBench, HiToM, FanToM) and reveals fragility under perturbation and depth (Ullman, 2023; Shapira et al., 2024). The dominant improvements push on the reasoning side — stronger prompts, process rewards, adversarial and trajectory-level training. Starling is complementary and orthogonal: it does not train the model but supplies a deterministic, auditable memory substrate that makes social structure explicit; and our evaluation (§5) precisely delimits the regime where this structure augments a strong reasoning model versus where it is redundant or harmful.

**Agent memory and cognitive architectures.** Mainstream stacks (mem0, Letta, cognee, Graphiti/Zep) are capable at fact retention but take subject-less facts as their ontology and isolation keys for multi-user separation. Starling differs at the ontological layer: it replaces the subject-less fact with a perspectival, nestable, lifecycle-bearing *belief*, and can thus express what these systems structurally cannot — recursive mentalizing, knowledge frontiers, common-ground closure, perspective-aware abstention. It does not replace them but layers atop them as cognitive middleware. Earlier symbolic cognitive architectures (e.g. ACT-R's declarative memory, computational CLS models) are an intellectual lineage for this work; Starling can be read as an engineering synthesis that lands these classic ideas — with modern LLM extraction as the front end and an auditable graph as the substrate — in the new setting of agent memory.

---

## 8 Limitations and Outlook

We close on an honest characterization of boundaries, both as scientific discipline and in the diagnostic spirit of §5.

- **The helpful regime is narrow.** Deterministic structure is robustly helpful only on deep nested tracking; its generalization to broader social-cognition tasks is mostly neutral or harmful. The semantic-routing gate converts this risk into "helps or does no harm," but does not widen the helpful regime itself — an open research question.
- **Strong dependence on extraction quality.** The entire social-cognition machine takes extraction output as input; a weak model or out-of-distribution prose degrades it at the extraction seam. Improving extraction robustness (especially on literary and cross-lingual text) is a prerequisite for unlocking this representation's potential.
- **Several brain-like mechanisms are not yet fully instantiated.** Content-driven affective appraisal and more complete prospective action execution are, at present, more design than implementation. We label maturity honestly and do not overclaim.
- **Privacy–mentalizing tension.** The system holds sensitive metadata like "A thinks B doesn't know X," whose safety depends on perspective masking running early in retrieval and being non-bypassable — a safety boundary requiring continued audit.
- **Statistical power.** Some conclusions rest on moderate-scale paired experiments; larger-scale replication across more model families is future work.

Looking ahead, we see the most promising direction as generalizing "memory structure as a conditional augmentation" from higher-order ToM to broader social reasoning (responsibility attribution, normative conflict, trust propagation), and exploring finer-grained synergy between representational structure and model reasoning.

---

## 9 Conclusion

This report argues a position and supports it with a system and an empirical study: **Theory of Mind is first a problem of representation, and memory is first a dynamical system.** When the structure of social cognition — attribution, perspective, recursive belief, common ground, perceptual access — is encoded into the memory substrate, higher-order mentalizing turns from a brittle inference into an auditable query; and when memory is endowed with brain-like dynamics of consolidation, forgetting, reconsolidation, and prospection, it turns from a static store into a cognitive organ that evolves with goals and time. Our gains on higher-order nested benchmarks — whose monotonic concentration at the deepest orders is itself instructive — together with our precise characterization of *when* deterministic structure helps, suggest that making social cognition an auditable data structure and dynamics, rather than a prompt-layer patch, offers a clear, falsifiable, and honest direction for the memory systems behind long-horizon human-AI collaboration.

---

## References (selected)

- Wimmer, H., & Perner, J. (1983). *Beliefs about beliefs: Representation and constraining function of wrong beliefs in young children's understanding of deception.* Cognition.
- McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). *Why there are complementary learning systems in the hippocampus and neocortex.* Psychological Review.
- Tulving, E. (1985). *Memory and consciousness.* Canadian Psychology.
- Conway, M. A., & Pleydell-Pearce, C. W. (2000). *The construction of autobiographical memories in the self-memory system.* Psychological Review.
- Nader, K., Schafe, G. E., & LeDoux, J. E. (2000). *Fear memories require protein synthesis in the amygdala for reconsolidation after retrieval.* Nature.
- Yassa, M. A., & Stark, C. E. L. (2011). *Pattern separation in the hippocampus.* Trends in Neurosciences.
- McGaugh, J. L. (2004). *The amygdala modulates the consolidation of memories of emotionally arousing experiences.* Annual Review of Neuroscience.
- Bower, G. H. (1981). *Mood and memory.* American Psychologist.
- Mattar, M. G., & Daw, N. D. (2018). *Prioritized memory access explains planning and hippocampal replay.* Nature Neuroscience.
- Schaul, T., Quan, J., Antonoglou, I., & Silver, D. (2015). *Prioritized Experience Replay.* arXiv:1511.05952.
- McDaniel, M. A., & Einstein, G. O. (2000). *Strategic and automatic processes in prospective memory retrieval: a multiprocess framework.* Applied Cognitive Psychology.
- Goschke, T., & Kuhl, J. (1993). *Representation of intentions: Persisting activation in memory.* Journal of Experimental Psychology.
- Fiske, A. P. (1992). *The four elementary forms of sociality.* Psychological Review.
- Ullman, T. (2023). *Large language models fail on trivial alterations to theory-of-mind tasks.* arXiv:2302.08399.
- Shapira, N., et al. (2024). *Clever Hans or neural theory of mind? Stress testing social reasoning in large language models.* EACL.
- Chen, Z., et al. (2024). *ToMBench: Benchmarking Theory of Mind in Large Language Models.* ACL.
- He, Y., et al. (2023). *HI-TOM: A benchmark for evaluating higher-order theory of mind reasoning in large language models.* EMNLP Findings.
- Kim, H., et al. (2023). *FANToM: A benchmark for stress-testing machine theory of mind in interactions.* EMNLP.
