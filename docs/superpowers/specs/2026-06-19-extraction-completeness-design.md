# Extraction Completeness — Design

**Date:** 2026-06-19
**Status:** Approved (design); pending implementation plan.
**Context:** Second of the extraction-grounding sequence (resolution ✅ → **completeness** → configurability). Grounding-resolution lifted the ToMBench location-FB end-to-end from 0.39 to ~0.78; the dominant remaining no-ground is the **leaver-find-gap**: in a Sally-Anne scene the character who *leaves* before the object is moved must have perceived the **initial location** to hold a (now-stale) false belief, but that initial location comes from a "they **find** the X in the Y" clause the episodic extractor does not reliably capture **with a location**. Real failing item (`tests/data/eval_tom_bench/full.jsonl:353-357`, qids `tb-false-belief-task-012..016`): *"Xiao Li and Youyou … they see a suitcase, a backpack, and a storage locker, they find a hat in the suitcase, Youyou leaves the basement, Xiao Li moves the hat to the storage locker."* — asked "where does Youyou look for the hat?", gold = "Suitcase" (the initial location).

---

## 1. Goal & scope

Make the episodic extractor capture **state-establishing initial locations** ("they find X in Y" → X is located at Y) so the leaver — already a present witness — forms the correct stale belief. **This is a pure prompt change (Python config data); no C++.**

**Why the prompt is the whole fix (C0).** The leaver (Youyou) is named in her own *"Youyou leaves"* clause, so she is in the reconstructor's **cast** (every named cognizer) and **default-present from the scene start** (`perception_reconstructor.cpp` presence model). She is therefore a witness of the *find* event (seq-before her leave) **regardless of how the find names its actor** — so she grounds **iff the find event carries a non-empty `location`** (the reconstructor's physical-location branch is gated on `!ev.location.empty()`). Today the prompt's `location` rule is "the **resulting** place after the action", so "find X in Y" emits `location=null` → the reconstructor writes nothing → the leaver has no initial perception → `[name-drift]` miss (the *move* event exists for the theme, so the M5 tag reads name-drift, but the real cause is the missing find-location). **Capturing the find with a location is the whole fix for ToMBench, and it needs no code change** — a `find` with a location already routes to `state_dim="location"` in the reconstructor (`find` is in no special-set).

**No compound-cognizer split (dropped — YAGNI).** "Xiao Li and Youyou find …" yields a compound `actor` surface, but it does **not** block the leaver (she is in the cast via her own *leave* clause, C0). A deterministic read-time split was considered and **dropped**: it added zero functional value for ToMBench (the leaver grounds without it), its only-in-compound robustness was partial anyway (the read-time split outputs raw, un-re-resolved sub-surfaces that drift on casing — P1), and it added a C++ touch point. The prompt still asks the model to resolve conjoined/pronoun subjects to individuals (§3.1) — a cheap, cosmetic extraction-cleanliness ask, not a grounding requirement. If a *only-in-compound* participant ever needs robust grounding (open narratives, not ToMBench), the future path is a **write-time** split (before name resolution), a separate change.

**Out of scope (deferred):**
- **`see X in Y` as a physical initial location.** `see`/`look` already route to `state_dim="content"` (the unexpected-contents channel, `is_see` → content branch). Reusing `see` for a physical location would collide with that semantics. The prompt uses **`find`/`discover`** for physical initial location (which routes to the location branch); `see` stays content. No reconstructor routing change.
- **Stative "X is in Y" / "there is an X in Y" capture** is best-effort only (C5): the extractor is action-oriented, so it reliably emits the *action* "find/discover" but may drop a pure stative clause. The prompt instructs the stative forms too, but the design does not depend on them — ToMBench uses "find".
- **Configurability** (prompt/vocab injection) — the next spec (#3).

## 2. Current state (file:line)

- **Episodic prompt** `python/starling/extractor/episodic_prompt.py`: `location` rule (:35) = "the object's **RESULTING place after the action**" — no state-establishing/initial-location instruction; PREFER verb list (:33) = {put, place, move, take, give, remove, transfer, leave, open, close, tell, inform} — **`find` absent**; `actor` (:32) / `participants` (:36) rules — **no conjoined-subject instruction**; 4 worked examples (:43-87) — none show a "find X in Y" initial location or a conjoined subject.
- **Reconstructor** `src/cognizer/perception_reconstructor.cpp` (unchanged by this spec): presence cast = every cognizer named in any non-tell event; **default-present from scene start**, a `leave` removes the leaver only *after* its own event; physical-location branch gated on `!ev.location.empty()` (~:193) writes `perception_state(witness, theme, state_dim="location", value=location)`. A non-tell/non-presence/non-content/non-close predicate with a location (e.g. `find`) routes to this location branch **today, zero code change**. `is_see` (~:55) routes `see`/`look` to the **content** branch (~:174).
- **Schema — no blocker:** `episodic_events.location` (migration 0025) is nullable TEXT; `perception_state.state_dim='location'` (migration 0026) is ready. An initial-location find is just an `OCCURRED` statement with `location` set.

## 3. Architecture

### 3.0 Decisions locked (brainstorming)

1. **Pure prompt change.** No C++ (no split, no registry change, no reconstructor routing change); `canonicalize` untouched.
2. **Initial physical location uses `find`/`discover` in the prompt** (routes to the location branch); `see` stays content.
3. **Two-track measurement** — a deterministic machinery pin (a find-with-location grounds the leaver) + a real-model grounding-recall re-run.

### 3.1 Episodic prompt changes (the only change — Python config data)

`python/starling/extractor/episodic_prompt.py` (purely additive; existing put/move/leave/tell/see-content rules unchanged):
- **Extend the `location` rule** to cover **state-establishing initial location**: for "they **find/discover** X in Y" → `action="find"`, `theme=X`, `location=Y` (the container/place where X is found). The existing "resulting place" wording stays for action verbs; this adds the find/initial case. **(This is the load-bearing change.)**
- **Add `find` (and `discover`) to the PREFER verb list.** (Prompt-only — NOT the C++ `kActionPredicates` registry: `OCCURRED` rows accept out-of-vocab verbs verbatim, and `find` is not in any reconstructor special-set, so a `find` with a location routes to `state_dim="location"` with zero code change.)
- **Add a conjoined-subject / pronoun-coreference instruction** to the `actor`/`participants` rules: "If a clause has a conjoined subject ('X and Y …') or a plural pronoun back-reference ('they …' / 'them' referring to people named earlier), **resolve it to the individual names** and list each in `participants`; pick a single individual or omit `actor` for a group action. Do not emit a single 'X and Y' string, or a bare 'they', as a person." **This is cosmetic, not load-bearing (C0):** the find event's `actor`/`participants` are irrelevant to the leaver grounding (she witnesses via default-presence from her own *leave* clause). It exists only to keep extraction clean (no junk compound cognizer) and is cheap to include in the prompt.
- **Add a worked example** of the leaver-find 5-clause shape: the Xiao-Li/Youyou narrative → ordered events `find(hat, location=suitcase, participants=[Xiao Li, Youyou])`, `leave(Youyou)`, `move(hat → storage locker, Xiao Li)`. This is the primary lever — the prompt's effect is an **LLM-behaviour bet measurable only by the real-model eval** (C1); the worked example is how we steer it, and it may need real-model iteration.
- **`see`/`look` unchanged** — reserved for labelled-container apparent content; physical initial location uses `find` (avoids the see=content routing collision).

### 3.2 No code change

No C++ at all: no `split_compound_cognizers`, no `kActionPredicates`/registry change, no reconstructor routing change. `canonicalize_object`/`canonicalize_string` untouched (parity intact). The find-with-location event already grounds the leaver through the existing reconstructor + `what_does_X_think` (the find routes to the location branch; the leaver is a default-present witness).

## 4. Data flow

```
"they find a hat in the suitcase, Youyou leaves, Xiao Li moves the hat to the storage locker"
→ EpisodicExtractor (new prompt): find(hat, loc=suitcase, …) + leave(Youyou) + move(hat → locker, Xiao Li)
→ PerceptionReconstructor (UNCHANGED): cast includes Youyou (named in her leave clause), default-present at find(seq1)
   → find@suitcase writes perception_state(Youyou, hat, location, suitcase) (+ Xiao Li); Youyou leaves(seq2) → absent at move(seq3)
→ what_does_X_think(Youyou, hat) = suitcase (stale; ground truth=locker) ✓
```
The leaver grounds because the find now carries a location and she is a present witness via her own *leave* clause — independent of how the find's actor is phrased.

## 5. Error handling

- If the LLM still emits the find with `location=null` (the prompt is a bet, C1), the reconstructor writes nothing and the leaver misses — degrades to today's behaviour, never crashes. The real-model eval is how we detect + iterate this.
- A conjoined actor the model fails to split is harmless (a junk extra cast member; the leaver still grounds via her own clause).
- Single-scene / tenant assumption inherited from B.

## 6. Testing (two tracks — decision 3)

1. **Deterministic machinery pin** (no real LLM): a **stub-LLM leaver-find e2e** (`tests/python/`): canned episodic JSON for the Xiao-Li/Youyou scene (`find(hat, location="suitcase", …)` + `leave(Youyou)` + `move(hat→"storage locker", Xiao Li)`) → `what_does_X_think(Youyou, "hat")` = `"suitcase"`, `is_stale=true`; `(Xiao Li, "hat")` = `"storage locker"`. This **pins the machinery** (a find-with-location grounds the leaver) and documents the target behaviour. NOTE: it passes against the *current* reconstructor (no code change) — it is a regression pin, not a TDD red→green; the actual gap is whether the *real model* emits the find with a location, which only the real-model eval exercises (C1).
2. **Real-model grounding-recall re-run** (`STARLING_RUN_LLM_E2E` gate; on-demand, **after the tokenkey.dev budget window recovers — this spec burns no API**): re-run `scripts/eval_perception_starling.py`; expect the leaver-find probes to ground and the M5 `[name-drift]` tag to shrink (fewer leaver misses). **No fixed lift is promised** (C1) — the real run measures whether the prompt elicits find-with-location.
3. **Regression:** ctest 644 / pytest 625 stay green — there is no code change; the prompt additions are additive (the deterministic B/grounding tests drive stub LLMs and are prompt-independent; the gated real-LLM Sally-Anne e2e has no find/conjoined clauses, so the new rules don't fire).

## 7. Constraints

The only change is **Python prompt config data** (`python/starling/extractor/episodic_prompt.py`) + one stub-LLM e2e test. **No C++**, no migration, no binding change. Do not touch `canonicalize_object`/`canonicalize_string` or the reconstructor; reuse the existing find→location routing. Do not break belief / multi-order-ToM / six-state / conflict / A-episodic / B-perception / grounding pins. `perceived_by_json` immutable. TDD where applicable; explicit-path `git add` (never `.`/`-A`); commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; no `--no-verify`/`--amend`; an editable rebuild is not needed (no C++/binding change), but run the full pytest to confirm no regression; build from repo root `/Users/jaredguo-mini/develop/memory/starling`.
