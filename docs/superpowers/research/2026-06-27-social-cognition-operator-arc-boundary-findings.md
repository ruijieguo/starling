# Deterministic Social-Cognition Operator Arc — Boundary Findings & Methodology (Capstone)

> **Status:** RESEARCH / FINDINGS. Capstone of the "per-family deterministic social-cognition
> operator" arc. No production behavior changes here — this document records the decisive,
> exhaustive result of the gap-hunt so the line of research is not re-trodden, and distills the
> methodology (and the traps) for any future probing of LLM theory-of-mind gaps.
>
> **One-line conclusion:** `deepseek-v4-pro`, **given clearly stipulated conventions**, handles
> every structured social-cognition tracking task we could construct at ceiling — there is **no
> clean compute-regime gap** for a deterministic operator to fill. The single benchmark win in the
> arc (HiToM nested belief, **+6.4%**) was driven by Starling **enforcing conventions HiToM left
> under-specified** (room-scoping + observation-primacy), **not** by a fundamental tracking/compute
> deficit — and we proved this directly.

---

## 1. Goal

Find a social-cognition capability where (a) `deepseek-v4-pro` **systematically fails**, and (b)
Starling can compute the answer **deterministically** from its perception/belief model, such that
**injecting** the deterministic answer in-loop gives a **generalizable** benchmark lift (the way the
HiToM nested-belief chain did). Hard constraint from the user, repeated throughout: the lift must
**generalize**, not merely fit the eval.

## 2. Method (and why it matters)

1. **Pilot-first de-risking.** Before building any operator, run a *cheap* `deepseek` baseline pilot
   (10–15 hand-/generator-made items) on the candidate capability. Build only where `deepseek`
   genuinely fails. This caught every dead-end before it cost an operator.
2. **Externally-defensible gold.** The gold must be what *any* competent ToM reasoner would compute
   (the standard false-belief / co-witness model), **not** the operator's own output. When the gold
   is the operator's definition, the in-loop "win" is tautological (the operator is right by
   construction) and the only real signal is the baseline.
3. **Stipulate conventions in the prompt (Notes).** Toy-ToM relies on conventions that are
   *contestable* in the real world (co-presence ⇒ observation; observation beats hearsay; entering a
   room doesn't re-reveal state). If the eval leaves these implicit, a model "failure" may be a
   **definitional disagreement**, not a tracking error. Stipulating them (HiToM-style Notes) turns
   the test into a clean tracking test.
4. **Diagnose every failure.** For each wrong answer ask: *real tracking error, or a defensible
   different reading?* Repeatedly, `deepseek` was **more** epistemically rigorous than the operator
   (see §3 CK and the public-announce cases).

## 3. The complete boundary map

Every dimension below was probed with `deepseek-v4-pro` (CoT). "Boundary" = `deepseek` already
solves it, so a deterministic operator adds no generalizable lift.

| Dimension | Probe | `deepseek` baseline | Verdict |
|---|---|---|---|
| Surface (mental-state / faux-pas / emotion) | ToMBench per-family | ≈ baseline | **Boundary** — reads it from the story |
| **Common knowledge** (v1 co-presence gold) | 240, paired | 0.908 → Starling 1.000 (+9.2pp, p=4.8e-7) | **Definitional artifact** (see §4) |
| **Common knowledge** (v2 announcement gold, harder) | 240, paired | 0.992 → Starling 1.000 (+0.83pp, **p=0.5**) | **Boundary** — no significant lift |
| Belief aggregation (count believers) | 15 | 15/15 | **Boundary** |
| Pure-depth nested belief (clean order-5) | 15 | 15/15 | **Boundary** — reducible, model shortcuts it |
| **Multi-room non-reducible nested** (order-5, 27 events × 6-chain, forced re-convergence; answer ≠ current ≠ shortcut) | 15 | **15/15** | **Boundary** — perfect co-witness-intersection tracking |
| Temporal / responsibility / info-value | 15 | ~14/15 (1 parse, 1 enumeration slip) | **Boundary** |
| **Hearsay** (clean propagation + observation-vs-stale-tell conflict) | 15 | **CLEAN 8/8 + CONFLICT 7/7** | **Boundary** (decisive — see §4) |
| **Nested belief — HiToM order 3-4** (multi-room + deception) | full 1200 | fixed-Starling **+6.4%** (o3 +16.7%, o4 +15.8%) | **The one win** — convention-driven (§4) |

## 4. Why the only "wins" were convention-enforcement, not compute

**Common knowledge.** v1 established CK by *co-presence at a move* — a contestable convention.
`deepseek` defensibly withheld CK there ("co-presence ≠ guaranteed observation", even citing
distractor "looked at X" events as evidence of divided attention). The +9.2pp was the injection
**overriding `deepseek`'s stricter, defensible reading**, plus the gold being the operator's own
co-witness definition. The harder/cleaner **v2** moved establishment to an *explicit public
announcement* (unambiguous CK) — and the gap **vanished** (+0.83pp, p=0.5). `deepseek` even caught
two *generator bugs* by being **more** rigorous than the operator (an announcer who never witnessed
the move ⇒ unfounded announcement ⇒ not CK; a teller whose earlier distractor announcement was false
⇒ unreliable ⇒ discount their later claim). The operator does **not** check announcer grounds or
speaker reliability; `deepseek` does.

**Hearsay (the decisive closer).** We split tells into **CLEAN** (recipient absent ⇒ adopts the
told value, no observation to conflict ⇒ gold non-contestable) and **CONFLICT** (recipient saw the
current location, then a stale agent tells an older one ⇒ gold = the observation, *if* we stipulate
observation-primacy). Result: **CLEAN 8/8 and CONFLICT 7/7.** Given the convention stipulated in a
Note, `deepseek` both propagates stale hearsay correctly **and** keeps first-hand observation over a
conflicting stale tell. This is the **direct proof** that the HiToM hearsay fix (observation/hearsay
separation, part of the +6.4%) closed a gap that existed **only because HiToM left the convention
implicit** — once stipulated, `deepseek` needs no help.

**Depth/load is not the gap.** `deepseek` solved the hardest tracking eval we built — order-5,
six-agent chains, 27 events, agents leaving/returning, with the schedule *forcing re-convergence* so
the nested answer is a mid-story state that is **neither the current location nor the
first-departure shortcut** — at **15/15**, with **zero** answers equal to current-location or
shortcut. The HiToM difficulty was the deception + under-specified conventions, **not** nesting
depth or working-memory load.

## 5. Value positioning of the operators

The operators built across the arc — `is_common_knowledge`, `what_does_X_think_chain`,
`mental_state_of`, `detect_faux_pas`, `appraise_emotion` — are **correct, tested (ctest), reviewed,
and reusable**. They are sound **substrate primitives** for downstream deterministic computation and
for the OpenClaw integration (auditable, holder-robust, perception-derived). What the arc establishes
is the **negative**: they do **not** translate into generalizable `deepseek` ToM-benchmark lift,
because `deepseek` already computes these relations when the conventions are explicit. The one
benchmark win (HiToM nested) is captured, measured against HiToM's external gold, and pushed; it is
**narrow** (convention-enforcement on an under-specified benchmark) and should not be over-claimed.

## 6. Practical guidance for future probing

- **Do not** hunt flat/aggregate/tracking ToM gaps for `deepseek`-class models — exhausted here.
- If revisiting: the only residual lever is *enforcing conventions a target benchmark leaves
  implicit* (room-scoping, observation-primacy) — but that is benchmark-quality patching, not a
  capability win, and it is **convention-confounded** (the model's "error" is often a defensible
  different reading).
- Reusable harness: `scripts/build_ck_corpus_v2.py` (announcement-based CK), the multi-room
  non-reducible nested generator and the hearsay clean/conflict generator (this session's pilots),
  and the **`STARLING_PASSTHROUGH`** server flag (robust paired baseline through the same C++ adapter,
  avoiding the openai-client HTTP/2 tail-stall).

## 7. References

- HiToM nested-belief win (+6.4%): roadmap row `7e8ca88`; memory `hitom-nested-belief-fixes`.
- CK operator + boundary measure: commits `3b8e5af..c91f08f` + `0b4415d`/`8da4168`, merged/pushed
  `b94b2fc`; roadmap row; memory `ck-operator-boundary-finding`.
- Gap-hunt exhaustion: memory `social-cognition-arc-gap-hunt-exhausted`.
- Eval harness: ToMEval (`/Users/jaredguo-mini/develop/ToMEval`), `CommonKnowledge` /
  `CommonKnowledge_v2` datasets + `cfg_*_CK*.yaml`; server `scripts/starling_tomeval_server.py`.
