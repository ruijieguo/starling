# Emotion Appraisal as a New Representational Capability for Starling — Research & Design

> **Status:** RESEARCH + DESIGN ONLY. No production code changes. This document audits Starling's
> existing affect representation, summarizes appraisal theory, designs an `appraise_emotion`
> operator in the style of the existing `src/tom/mentalizing_*.cpp` family, and gives an honest
> feasibility/ROI verdict for the ToMBench dimensions where Starling currently has **no representation**.
>
> **Arc context:** This is the second candidate in the "per-family deterministic social-cognition
> operator" arc. The first (`detect_faux_pas`,
> `docs/superpowers/specs/2026-06-24-faux-pas-detection-design.md`) established the house style:
> the C++ core computes a **deterministic structural precondition** (an asymmetry the LLM tends to
> lose track of); the **semantic judgment stays with the LLM**; everything is **perception-derived /
> holder-robust** to dodge the holder-gap. `appraise_emotion` is the same shape applied to Emotion.

---

## 0. The eval finding that motivates this (one paragraph)

A rigorous ToMBench eval established that Starling's representational strength — physical-state
false belief × multi-agent perception × nesting (`perception_state`, `what_does_X_think`,
`does_X_know`, `what_does_X_think_Y_believes`) — coincides **exactly** with where deepseek-v4-pro is
**already saturated** (Location / Identity / 2nd-order false belief ≈ 1.00 baseline). The remaining
headroom lives in dimensions Starling does **not** represent at all. The largest of these is
**Emotion** (≈440 items with room: Atypical emotional reactions **0.54**, Hidden emotions **0.86**,
Moral emotions **0.86**), which has a *principled theory* (appraisal theory) behind it — unlike the
other gaps (Desire→action/emotion, Intention-from-behavior, Non-Literal pragmatics), which are
open-ended social inference. The question this doc answers: **for the Emotion gap, what new
representational capability would Starling need, and is it worth building?**

---

## Part A — Audit: what affect representation Starling has TODAY (grounded in code)

### A.1 `AffectVector` is a salience-scoring scalar bundle, not an emotion representation

The entire affect type is five floats:

```cpp
// include/starling/affect/affect_vector.hpp:7-13
struct AffectVector {
    float valence = 0.f;    // -1..+1
    float arousal = 0.f;    //  0..1
    float dominance = 0.f;  // -1..+1
    float novelty = 0.f;    //  0..1
    float stakes = 0.f;     //  0..1
};
```

`valence/arousal/dominance` are a **PAD/VAD core-affect** triple (Pleasure≈valence, Arousal,
Dominance); `novelty/stakes` are EM-LLM-style surprise/importance knobs. Crucially, the **only
consumer** of this struct is a single scalar reduction:

```cpp
// src/affect/affect_vector.cpp:7-14
double salience(const AffectVector& v, double surprise_decay) {
    return (0.4 + 0.6 * abs((double)v.valence))
         * (0.4 + 0.6 * v.arousal)
         * (0.3 + 0.7 * v.novelty)
         * (0.3 + 0.7 * v.stakes)
         * (0.6 + 0.4 * surprise_decay);
}
```

Note `dominance` is **not even used** in `salience()` — it is stored but inert. Per
`docs/design/system_design.md:1179-1185`, `salience` exists for exactly three mechanical purposes:
(1) VOLATILE write-queue priority, (2) Replay Scheduler sampling weight, (3) retrieval reranker
multiplier. **AffectVector answers "how memorable is this row," never "what does X feel."**

### A.2 Where it is stored and computed — and the decisive fact: it is **always birth-neutral**

- **Stored** as an embedded JSON string per statement: `statements.affect_json` (raw `"{}"` when
  absent), surfaced on `retrieval::StatementRow::affect_json`
  (`include/starling/retrieval/statement_row.hpp:30`). It is a value object, never its own table
  (`system_design.md:1185`).
- **Parsed** by `affect::parse_affect_json` (`src/affect/affect_vector.cpp:28-43`), with NaN/inf
  sanitized to 0 so a malformed blob can't poison downstream salience math.
- **Written:** the statement writer binds birth salience from a **fully-neutral** vector:
  ```cpp
  // src/bus/statement_writer.cpp:203-206
  // 出生 salience = 中性 AffectVector 的公式值(≈0.0144),非 0。spec §3.9
  sqlite3_bind_double(h.get(), i++, affect::salience(affect::AffectVector{}));
  ```
  **There is no code path that computes a non-neutral `AffectVector` from content.** Greps across
  `src/extractor/`, `python/starling/extractor/`, and `src/bus/` find **zero** writers of
  `valence/arousal/...` — the extractor emits no affect at all
  (`include/starling/extractor/extracted_statement.hpp:14`: "no salience/affect"). Per
  `system_design.md:1187`, an affect *appraiser* was explicitly **deferred to P3** ("写入时尚无评估器
  为 Statement 打 affect"); it was never built. So in practice every statement carries `affect ≈
  neutral`, and `salience` differentiates rows only through later inheritance (e.g. 2nd-order
  inference inherits `src.salience * 0.8`, `src/tom/second_order.cpp:170-176`).

### A.3 Downstream affect plumbing (all salience-only)

- **`affect_buffer`** (`include/starling/hippocampus/affect_buffer.hpp`,
  `src/hippocampus/affect_buffer.cpp`) — *not* an emotion store. It is a **derived view**: "the
  tenant's top-C VOLATILE rows with `salience >= θ_buffer` (0.6)," used to exempt high-salience rows
  from the VOLATILE TTL sweep. Zero emotion semantics; it's a memory-retention priority set.
- **`affect_reranker`** (`src/retrieval/affect_reranker.cpp:37-65`) — multiplies retrieval score by
  `(1 + 0.4·salience)` and an L1 PAD distance to a *querier* affect vector. This is mood-congruent
  retrieval ranking, again not emotion attribution.
- **Replay** (`src/replay/replay_scheduler.cpp:140-165`, `swr_sampler.cpp`) — feeds `affect_arousal`
  into the sampling weight `(1 + arousal_bonus·affect_arousal)`. Pure prioritization.
- **`trust_priors`** (`src/cognizer/cognizer_hub.cpp:224,345-367`) — stored as an **opaque
  `trust_priors_json` string** on the cognizer row, "kept as opaque strings for P2.a." A planned
  `downgrade_trust_priors` on commitment breach is an explicit **TODO(P3)**, not implemented
  (`src/prospective/commitment_engine.cpp:256-257`). Trust priors are **not** wired into any affect
  or emotion computation today.

### A.4 What the read-side already gives us for free (the appraisal substrate)

Appraisal needs the agent's **goals/desires**. Starling already extracts and buckets them:

- **`Modality`** enum (`python/starling/schema/enums.py:16-28`) includes `desires`, `intends`,
  `believes`, `prefers`, `commits` — the BDI vocabulary appraisal reads.
- **`mental_state_of`** (`src/tom/mentalizing_profile.cpp:10-37`, declared
  `include/starling/tom/mentalizing.hpp:226-232`) returns a `MentalState` with `.desires`
  (modality `desires`), `.intentions` (modality `intends`), `.preferences` (predicate/modality
  `prefers`), `.beliefs`, `.commitments`. **This is the goal/desire feed `appraise_emotion` needs.**
- **`what_does_X_think(adapter, frontier, x, theme, ...)`** (`src/tom/mentalizing_think.cpp:16-65`)
  returns X's last-perceived `state_value` for a theme **and `is_stale`** (≠ global truth) — the
  per-character, perception-derived, holder-robust state read that `detect_faux_pas` already
  leans on. This is how we learn **what happened to the theme** without the holder-gap.
- **`StatementRow`** carries `holder_id`, `subject_id`, `predicate`, `object_value`, `polarity`,
  `modality`, `evidence_json` — enough to identify a desire's target and a desire↔event match.

### A.5 The EXACT gap

| Capability | Status today |
|---|---|
| PAD/VAD core-affect *type* | ✅ exists (`AffectVector`), but reduced to one scalar `salience` |
| Non-neutral affect ever *computed from content* | ❌ never — birth-neutral always; appraiser deferred P3, never built |
| Emotion *labels* (anger/guilt/gratitude/fear/relief/pride/shame…) | ❌ no representation anywhere |
| **Appraisal logic** (goal-relevance / congruence / agency / certainty → emotion) | ❌ **none** |
| Agent goals/desires to appraise *against* | ✅ `mental_state_of().desires/intentions/preferences` |
| What happened to the theme (event/state) | ✅ `what_does_X_think` (`state_value`, `is_stale`), `perception_state` |
| Who caused it (agency/actor) | ⚠️ partial — `perception_state` has `source_event_id`; episodic events have an actor, but actor↔event↔desire linkage is not assembled anywhere |
| Felt-vs-displayed (display rules) for Hidden emotions | ❌ no representation |
| Eval surface even *attempts* emotion | ❌ server **gates OFF** emotion (`scripts/starling_tomeval_server.py:237`: `_GATE_OFF_CUES = ("emotion","feel","feeling",...)`) |

**Plain statement:** Starling has **no meaningful affect representation for emotion** — it has a PAD
vector that is never populated and is collapsed to a memorability scalar, plus zero appraisal logic.
The *read substrate* for appraisal (desires, perceived events) exists and is good; the *appraisal
computation and the emotion vocabulary do not exist at all.* This makes `appraise_emotion` a
**from-scratch build of the appraisal layer**, not an extension of existing affect code. (It can,
however, **reuse** `mental_state_of` + `what_does_X_think` wholesale for its inputs, exactly as
`detect_faux_pas` reused the perception primitives.)

---

## Part B — Appraisal theory (the principled basis)

Appraisal theory (Lazarus; Ortony-Clore-Collins / OCC; Scherer; Roseman; Smith & Ellsworth) holds
that an emotion is not a direct function of an event but of the agent's **appraisal** of that event
**relative to that agent's goals**. Two people, same event, different goals → different emotions.
That "same event, different goal → different emotion" property is *exactly* what the ToMBench
Emotion sub-abilities probe, and it is why a memory engine that stores **per-agent goals** has
something real to contribute.

### B.1 Core appraisal dimensions

| Dimension | Question | Source in Starling |
|---|---|---|
| **Goal-relevance** | Does the event touch any goal of X at all? | does the event's theme/object match an X desire/intention? |
| **Goal-congruence** | Does it *help* (congruent) or *hurt* (incongruent) X's goal? | desire polarity + desire target value vs. event outcome value (**the crux**) |
| **Agency / blame** | Who caused it — self / other / circumstance? | event actor vs. X (self), vs. another cognizer (other), vs. none (circumstance) |
| **Certainty** | Is the outcome settled or still in doubt? | is the desire/threat resolved (state reached) or pending? |
| **Novelty / expectedness** | Was it expected? Atypical? | `is_stale` / surprise; matched vs. mismatched default |
| **Coping / effort / control** | Can X do anything about it? | (weak in Starling — deferred) |

### B.2 The appraisal → discrete-emotion mapping (OCC / Roseman, reduced)

The classic reduction routes the **(goal-congruence × agency × certainty)** tuple to a discrete
emotion. The minimal table Starling can target:

| Goal-congruence | Agency | Certainty | → Emotion | OCC family |
|---|---|---|---|---|
| congruent (helped) | other | settled | **gratitude** | fortunes-of-other / attribution |
| congruent | self | settled | **pride** | attribution (self) — *moral* |
| congruent | circumstance | settled | **joy / happiness** | well-being |
| congruent | (any) | **uncertain→resolved** | **relief** | prospect-based |
| incongruent (hurt) | other | settled | **anger** | attribution (other) |
| incongruent | self | settled | **guilt / regret** | attribution (self) — *moral* |
| incongruent | self + norm-violation, audience | settled | **shame** | attribution (self) — *moral* |
| incongruent | circumstance | settled | **sadness / distress** | well-being |
| incongruent | (any) | **uncertain / pending** | **fear / anxiety** | prospect-based |
| congruent-for-other, incongruent-for-self | other | settled | **envy / resentment** | fortunes-of-other |
| incongruent-for-other, X dislikes other | other | settled | **gloating** (schadenfreude) | fortunes-of-other |

The two pivots are **goal-congruence** (helped vs. hurt) and **agency** (self vs. other vs.
circumstance); **certainty** mainly toggles the prospect emotions (fear/relief). This is the
deterministic core. (Display/intensity and the long tail of blends stay with the LLM.)

### B.3 Mapping to the ToMBench Emotion sub-abilities

| Sub-ability | What it requires | What appraisal supplies |
|---|---|---|
| **Atypical emotional reactions** (0.54 — biggest room) | the emotion is **not** the situation's default, because **X has an unusual specific goal/desire** | this is *the* appraisal payoff: feed X's actual desire (e.g. X *wanted* the team to lose) → congruence flips → emotion flips away from the default. Needs the per-agent desire, which Starling stores. |
| **Hidden emotions** (0.86) | **felt vs. displayed** diverge — needs goal (→ felt) **plus a social display rule** (→ shown) | appraisal computes the *felt* emotion from goal-congruence; the *display* layer (suppress/mask) is a **second representation Starling does not have** — flagged as out-of-scope for v1 (the gap is the display rule, not the felt emotion). |
| **Moral emotions** (0.86) | guilt / shame / pride — **self-agency** appraisal | directly the agency=self rows of the table. Needs to detect X is the actor of an incongruent (guilt) or congruent (pride) outcome, plus norm-violation for shame. |
| **Discrepant emotions** (two parties feel differently about one event) | **different goals** for the same event | appraise each party against *their own* `mental_state_of().desires` → congruence differs → emotions differ. This is the cleanest fit and the deterministic sweet-spot. |

---

## Part C — Design: `appraise_emotion(adapter, x, theme/event, tenant, as_of)`

Designed to mirror `detect_faux_pas` / `what_does_X_think` precisely: core ToM logic in C++
(`src/tom/mentalizing_*.cpp`, declared in `include/starling/tom/mentalizing.hpp`); a thin pybind
wrapper in `bindings/python/bind_08_tom.cpp` + `python/starling/tom/primitives.py`; and a thin,
gated server consumer. It computes a **deterministic appraisal precondition** and hands the LLM a
*grounded* emotion hypothesis + its basis; it does **not** claim to be the final emotion judge.

### C.1 Signature & return type

```cpp
// include/starling/tom/mentalizing.hpp (new)

// The deterministic appraisal of how an event bears on X's goals. emotion is the
// table-derived discrete label; agency/goal_congruence/certainty are the appraisal
// tuple that produced it; basis is the auditable evidence (the matched desire row +
// the event/state row) the LLM can read. Mirrors FauxPasCandidate: a structural
// precondition, NOT a semantic verdict — the LLM still judges nuance/intensity/blends.
struct EmotionAppraisal {
    std::string emotion;            // "gratitude"|"anger"|"guilt"|"pride"|"fear"|
                                    //   "relief"|"joy"|"sadness"|"shame"|"" (undetermined)
    std::string goal_congruence;    // "congruent" | "incongruent" | "irrelevant" | "unknown"
    std::string agency;             // "self" | "other" | "circumstance" | "unknown"
    std::string certainty;          // "settled" | "pending" | "unknown"
    std::string matched_desire_id;  // statements.id of the X-desire this event touched ("" if none)
    std::string actor;              // the cognizer who caused the event ("" if circumstance/unknown)
    std::vector<retrieval::StatementRow> basis;  // [matched desire row, event/state row] — auditable
};

// Appraise how `theme`'s latest state-change bears on X's goals, as of `as_of`.
// Reads X's desires (mental_state_of) + the event/state of `theme` (what_does_X_think /
// perception_state actor) and routes the (goal_congruence × agency × certainty) tuple
// through a deterministic table to a discrete emotion. Returns emotion="" (undetermined)
// when goal-relevance or congruence cannot be established deterministically (the honest
// abstention). Holder-robust: desires via mental_state_of(holder=x); event via perception.
EmotionAppraisal appraise_emotion(
    persistence::SqliteAdapter& adapter,
    cognizer::KnowledgeFrontier& frontier,   //透传 to what_does_X_think (seam, like detect_faux_pas)
    std::string_view x,
    std::string_view theme,                  // the event's theme/subject to appraise against
    std::string_view tenant,
    std::string_view as_of);
```

A batch form `appraise_all(adapter, frontier, tenant, as_of) -> vector<EmotionAppraisal>` (scan
cast × themes, like `detect_faux_pas` does) is the natural server-facing entry point, since the eval
question rarely names (X, theme) explicitly.

### C.2 Algorithm

```
1. READ X's goals:
   ms = mental_state_of(x, tenant, as_of)
   desires = ms.desires ∪ ms.intentions ∪ ms.preferences   // BDI goal feed
   if desires empty: return {emotion:"", goal_congruence:"irrelevant", ...}   // honest abstain

2. READ the event/state of `theme`:
   sb = what_does_X_think(x, theme, ..., observer="")        // X's last-perceived state
   if not sb.has_belief: return {emotion:"", certainty:"unknown", ...}        // X never perceived it
   event_value  = sb.state_value          // the outcome state (e.g. "broken", "gone", "won")
   event_actor  = perception_state.source_event → episodic actor (see C.4 "hard part")

3. GOAL-RELEVANCE: find the desire whose target == theme (subject_id/object_value match `theme`).
   matched = first d in desires where d.subject_id==theme OR d.object_value mentions theme
   if none: goal_congruence = "irrelevant"; emotion = ""   // event doesn't touch a known goal

4. GOAL-CONGRUENCE (THE CRUX — see C.4):
   desired_value = matched.object_value ; desired_polarity = matched.polarity
   congruent  if (event_value == desired_value)  XOR (desired_polarity == "neg")
   incongruent otherwise
   // i.e. X desired theme→V (pos): event reaching V = congruent; X desired NOT V (neg): V = incongruent.

5. AGENCY:
   if event_actor == x           : agency = "self"
   elif event_actor is a cognizer: agency = "other"  (actor != x)
   elif event_actor == ""        : agency = "circumstance"

6. CERTAINTY:
   settled  if the desire's target state is now reached/decided (event_value is a terminal state)
   pending  if the relevant outcome is still open (no terminal state yet for theme)
   // primarily distinguishes fear (pending+incongruent) / relief (resolved+was-incongruent).

7. MAP via the B.2 table:  emotion = TABLE[(goal_congruence, agency, certainty)]
   basis = [matched desire row, event/state row as a StatementRow]
   return EmotionAppraisal{emotion, goal_congruence, agency, certainty, matched.id, event_actor, basis}
```

### C.3 The deterministic mapping table (C++ — exactly B.2, encoded)

```cpp
// (goal_congruence, agency, certainty) -> emotion. "" agency/certainty = wildcard.
static std::string map_emotion(std::string_view cong, std::string_view ag, std::string_view cert) {
    if (cert == "pending" && cong == "incongruent") return "fear";
    if (cong == "congruent") {
        if (cert == "resolved_from_incongruent")   return "relief";
        if (ag == "other")                          return "gratitude";
        if (ag == "self")                           return "pride";   // moral
        return "joy";
    }
    if (cong == "incongruent") {
        if (ag == "other")                          return "anger";
        if (ag == "self")                           return "guilt";   // moral (shame if norm+audience)
        return "sadness";
    }
    return "";  // irrelevant / unknown -> undetermined (abstain)
}
```

### C.4 The HARD parts — honest accounting of deterministic vs. LLM

| Step | Deterministically computable? | Honest note |
|---|---|---|
| Read X's desires | ✅ yes | `mental_state_of().desires/intentions/preferences` already exists and is holder-bucketed. **BUT** subject to the **holder-gap**: a *narrated* desire ("Anna hoped the box was empty") may land with `holder=narrator` unless the extractor attributes it to Anna. This is the **same failure that bit SP-A** (surface mental state ≈ baseline because holders were wrong). Mitigation: appraisal inherits whatever desire-attribution quality the extractor has; the operator should **abstain (emotion="")** when no desire is held *by X*, not guess. |
| Read the event/state | ✅ yes | `what_does_X_think` is per-character, perception-derived, holder-robust — the good case. |
| **Goal-congruence (the crux)** | ⚠️ **partly** | Deterministic *iff* (a) the matched desire has a structured target value (`object_value`/polarity) and (b) the event has a comparable outcome value. When both are clean state-dimension facts (location/content/won-lost), `event_value == desired_value` is a real boolean. When the desire is abstract ("wanted the party to go well") or the event outcome is narrated prose, congruence is **not** structurally decidable → must **abstain or defer to the LLM**. *This is the single make-or-break step.* It is **more tractable than irony/humor** (there is a theory and, in the clean case, a literal value comparison) but it is **not free** — it needs desire targets to be extracted as structured values, which today they often are not. |
| **Agency / actor** | ⚠️ **partly** | `perception_state.source_event_id` exists, and episodic events (`modality='occurred'`, migration 0025) carry actor-ish fields, but **no code assembles event→actor→(self/other) for appraisal today**. A small deterministic join (event's actor cognizer vs. X) is buildable but is **new plumbing**, and narrated causality ("because Tom broke it") may not surface a structured actor → agency="unknown" → fall back to well-being emotions (joy/sadness) or abstain. |
| Certainty (fear/relief) | ⚠️ weakest | Requires reasoning about whether an outcome is *settled*; Starling has no explicit "resolved/pending" marker. v1 should treat certainty as `settled` by default and only emit fear/relief when a pending→resolved transition is structurally evident; otherwise collapse to the settled-row emotion. |
| Intensity / blends / display | ❌ no | Stays with the LLM. Out of scope for v1. |

**Bottom line for Part C:** the operator is **principled and partially deterministic**. Its honest
contract (mirroring `detect_faux_pas`): it emits a **grounded emotion hypothesis with its appraisal
tuple and auditable basis** *when the desire is held by X and both the desire target and the event
outcome are structured enough to compare*, and **abstains (`emotion=""`) otherwise** rather than
fabricate. The two structural dependencies — **desire-target extraction quality** (holder-gap +
structured value) and **event→actor assembly** — are the build's real cost and risk, not the table.

### C.5 Eval-surface consumer (thin, gated) — and the one wiring change to flag

The eval server currently **gates OFF** emotion (`scripts/starling_tomeval_server.py:237`,
`_GATE_OFF_CUES = ("emotion","feel","feeling","think the","thinks the","really think")`). Shipping
`appraise_emotion` means **flipping that gate from OFF to a positive emotion route**: on an
emotion-cued question, call `appraise_all(...)`, and for any candidate with non-empty `emotion`,
inject a definitional, abstaining line — *"Starling appraisal: X **desired** [matched desire];
[theme] outcome was [event_value] → goal-**incongruent**, caused by **[actor]** (other) → likely
**anger**. (Felt emotion; display not modeled.)"* — else fall back to the existing dump. Priority
mutually-exclusive with the chain / mental_state / faux_pas routes, identical to the faux-pas design
§6. The server stays logic-free (call + format + gate).

---

## Part D — The other mismatched dimensions (honest verdict, one paragraph each)

**Desire→action / Desire→emotion.** *Verdict: low ROI; mostly LLM-territory.* The desire→emotion
half is a **strict subset of `appraise_emotion`** and comes for free if appraisal is built — no
separate operator. The desire→action half ("given X wants W, what will X do?") is open-ended
**causal/practical inference**: the space of actions isn't enumerable from the store, and this is
precisely where LLMs beat symbolic systems. `predict_X_would`
(`src/tom/mentalizing_more.cpp:176-218`) already returns the *basis* (relevant beliefs/preferences/
commitments) without fabricating the action — that honest-basis contract is the right ceiling for a
symbolic system here. Plus the **holder-gap bites again**: a narrated desire must be attributed to X
to be usable. Don't build a dedicated desire→action operator.

**Intention-from-behavior.** *Verdict: fundamentally LLM-territory; do not build.* Inferring the
intention behind an observed action ("he picked up the umbrella → he intends to go out") requires
**world-knowledge priors** about action→goal mappings that are not in the store and not
deterministically derivable. Starling can *store* an intention once stated (`modality='intends'`,
surfaced by `mental_state_of().intentions`) and can *track* commitments, but **abducing** an
unstated intention from behavior is exactly the inductive social inference LLMs are good at and
symbolic operators are not. No representational fit.

**Non-Literal pragmatics (irony / humor / white-lies).** *Verdict: not deterministically
representable; not a symbolic-operator fit.* Detecting irony/humor/white-lies needs
**world-knowledge + social-norm reasoning + speaker-intent-vs-literal-content contrast** that has no
structural signature in the store. The one *exception* already in flight is **faux-pas**, which
works **only** because it reduces to a *structural* precondition (an ignorance asymmetry from
perception) and leaves the semantic "was it actually offensive" judgment to the LLM
(`docs/superpowers/specs/2026-06-24-faux-pas-detection-design.md`). Irony/humor/white-lies have **no
comparable structural reduction**, so they stay with the LLM.

**Curiosity flag (separate investigation).** Desire-influence-on-emotions (**0/48**) and
Intention-Discrepant (**0/80**) show deepseek at **exactly 0%** baseline. A 0% (not low-but-random)
score is almost never a genuine capability gap — random guessing on a multiple-choice item floors
well above 0. This signature points to a **dataset/scoring/option-mapping artifact** (e.g. an
answer-key offset, a label-format mismatch, or a parser that never matches the expected option for
that sub-ability). **Action: before treating these as "Starling headroom," audit the eval harness
for these two sub-abilities specifically** — if it's a scoring bug, the "room" is illusory and these
items should be excluded from ROI math.

---

## Part E — Feasibility + ROI verdict

### E.1 Effort & shape

- **New core module** `src/tom/mentalizing_appraise.cpp` (+ declaration in `mentalizing.hpp`, +
  `bind_08_tom.cpp` POD/`m.def`, + `primitives.py` wrapper, + server route). The **appraisal table
  and tuple routing are small and cheap** — a day. It does **not** extend the existing
  `AffectVector`/salience code (that stays a memorability scalar); it **reuses**
  `mental_state_of` + `what_does_X_think` for inputs, exactly like `detect_faux_pas`.
- **The real cost is two upstream dependencies, not the operator:** (1) **desire-target
  extraction** — desires must carry a *structured target value/polarity*, and must be attributed to
  the *right holder* (the holder-gap); (2) **event→actor assembly** — a deterministic
  event→actor→(self/other) join that does not exist yet. Without (1) and (2), the operator abstains
  most of the time and degenerates to ≈ baseline (the SP-A outcome).

### E.2 The crux risk

**Goal-congruence derivation × the holder-gap.** Appraisal's whole value is "same event, different
*goal* → different emotion." If the goal (desire) isn't extracted as a structured target held by X,
the congruence step can't fire and the operator can't beat the LLM (which infers the goal from prose
anyway). This is the **same root cause** that made SP-A's surface mental-state injection ≈ baseline.
The bet is only as good as desire-attribution quality on the Emotion items — **which is unmeasured.**

### E.3 Realistic ROI

- The Emotion room is **~440 items**, but deepseek already scores **0.86** on Hidden and Moral —
  so the *actionable* room is mostly **Atypical reactions (0.54)** plus the discrepant-emotion cases.
- **Hidden emotions** need a **display-rule representation Starling does not have** (felt-vs-shown);
  appraisal supplies only the *felt* side → limited lift there.
- **Atypical / Discrepant** are the genuine fit: they hinge on **X's specific, non-default goal**,
  which is exactly what a per-agent memory store can supply that a generic prior can't — *if* the
  desire is captured. EmoBench (similar appraisal-style items) would benefit from the same operator.
- Net: **plausible single-digit lift concentrated in Atypical/Discrepant**, gated entirely on
  desire-extraction quality. Not a sure thing; better-grounded than any other gap because a theory
  and a (partial) deterministic core exist.

### E.4 Recommendation — **CONDITIONAL BUILD (build the cheap probe first, then decide)**

`appraise_emotion` is the **only** ToMBench gap worth building toward, because it's the only one
with a principled theory and a partly-deterministic core, and because Starling already owns the
goal/desire substrate other systems lack. But do **not** commit to the full build blind. Sequence:

1. **First, a measurement spike (cheap, no new core):** on the ToMBench Emotion + Desire-influence
   sets, measure how often a desire is (a) extracted with a structured target and (b) attributed to
   the correct holder X. This directly sizes the crux risk. *Also runs the Part-D curiosity audit on
   the two 0% sub-abilities.* **If desire-attribution is poor, stop here** — appraisal will ≈
   baseline, and the right investment is upstream desire-extraction, not the operator.
2. **If the substrate is adequate,** build `appraise_emotion` v1 = the table + tuple over
   `mental_state_of` + `what_does_X_think`, with **honest abstention** (`emotion=""` when congruence
   isn't structurally decidable), plus the minimal **event→actor** join. Re-run ToMBench Emotion
   gated; do **not** promise a fixed lift (per the faux-pas precedent).
3. **Defer:** display-rule modeling (Hidden emotions' felt-vs-shown), certainty/coping richness,
   and any non-neutral `AffectVector` *write* path — out of scope until v1 proves lift.

### E.5 Prioritized list

| Capability | Verdict | Why |
|---|---|---|
| **`appraise_emotion`** (felt emotion via appraisal table over desires+perception) | **BUILD — but gate on a desire-attribution measurement spike first** | only gap with a theory + partial determinism; reuses existing substrate; concentrated room in Atypical/Discrepant |
| Desire→emotion | **subsumed** | falls out of `appraise_emotion` for free |
| Display-rule layer (Hidden emotions: felt vs shown) | **DEFER** | a second representation Starling lacks; modest room (already 0.86) |
| Event→actor assembly | **BUILD as a dependency of `appraise_emotion`** | needed for the agency axis; small deterministic join |
| Desire→action operator | **DON'T BUILD** | open-ended causal inference = LLM territory; `predict_X_would` basis is the right ceiling |
| Intention-from-behavior | **DON'T BUILD** | abduction needs world-knowledge priors; no structural signature |
| Non-Literal (irony/humor/white-lies) | **DON'T BUILD** | no structural reduction (unlike faux-pas); LLM territory |
| Audit the two 0% sub-abilities | **INVESTIGATE (not build)** | 0% ⇒ likely scoring/dataset artifact; exclude from ROI until verified |

---

## Appendix — Code references (file:line)

- `include/starling/affect/affect_vector.hpp:7-20` — `AffectVector` (PAD+novelty+stakes) + `salience`/`parse` decls.
- `src/affect/affect_vector.cpp:7-43` — `salience()` (dominance unused) + `parse_affect_json` (NaN-safe).
- `src/bus/statement_writer.cpp:203-206` — birth salience from **neutral** `AffectVector{}` (no content appraisal).
- `include/starling/extractor/extracted_statement.hpp:14` — extractor emits "no salience/affect".
- `system_design.md:1158-1187` — §3.9 AffectVector spec; affect appraiser **deferred to P3**, never built.
- `src/hippocampus/affect_buffer.cpp` + `.hpp` — salience-priority retention view (no emotion).
- `src/retrieval/affect_reranker.cpp:37-65` — mood-congruent reranking (no emotion attribution).
- `src/replay/replay_scheduler.cpp:140-165`, `swr_sampler.cpp:39` — arousal→sampling weight.
- `src/cognizer/cognizer_hub.cpp:224,345-367` — `trust_priors_json` **opaque**; `commitment_engine.cpp:256-257` downgrade is TODO(P3).
- `python/starling/schema/enums.py:16-28` — `Modality` (desires/intends/believes/prefers/commits).
- `src/tom/mentalizing_profile.cpp:10-37` + `mentalizing.hpp:226-232` — `mental_state_of` → `MentalState{desires,intentions,...}` (the goal feed).
- `src/tom/mentalizing_think.cpp:16-65` — `what_does_X_think` (`state_value`, `is_stale`; perception-derived, holder-robust).
- `src/tom/mentalizing_more.cpp:176-218` — `predict_X_would` (honest-basis contract; the ceiling for desire→action).
- `src/tom/mentalizing_fauxpas.cpp` + `docs/superpowers/specs/2026-06-24-faux-pas-detection-design.md` — house style: deterministic structural precondition, LLM keeps the semantic judgment.
- `bindings/python/bind_08_tom.cpp:206-241` — binding pattern (`MentalState`, `detect_faux_pas`) to mirror.
- `python/starling/tom/primitives.py:201-224` — thin wrapper pattern to mirror.
- `scripts/starling_tomeval_server.py:237` — `_GATE_OFF_CUES` currently **disables** emotion routing (the gate to flip).
