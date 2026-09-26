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

## 5b. Robustness across model tiers — `deepseek-v4-flash`

A natural hope: a cheaper/faster model is weaker, so the tasks `deepseek-v4-pro` aces might *open
up* for it, reviving the operators' value for cost-effective deployment (cheap model + Starling
injection ≈ pro-level ToM at lower cost). Tested directly:

- **Standard battery** (38 items across CK_v2, belief-counting, multi-room non-reducible order-5
  nesting, hearsay clean+conflict, temporal/responsibility/info-value): `deepseek-v4-flash` =
  **37/38 = 0.974** (the one miss a counting slip — the same minor enumeration error `pro` makes).
- **Cranked hard probe** (8-agent chains, ~37 events, forced re-convergence), the SAME items on
  both models: **flash 10/10, pro 10/10**.

So `flash` matches `pro` even at cranked load — there is **no "flash breaks, pro holds" band** for an
operator to fill. The conclusion is **robust across the deepseek-v4 family**, not `pro`-specific:
switching to the cheaper model does not resurrect operator value.

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
