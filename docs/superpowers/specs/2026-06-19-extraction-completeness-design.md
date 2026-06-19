# Extraction Completeness — Design

**Date:** 2026-06-19
**Status:** Approved (design); pending implementation plan.
**Context:** Second of the extraction-grounding sequence (resolution ✅ → **completeness** → configurability). Grounding-resolution lifted the ToMBench location-FB end-to-end from 0.39 to ~0.78; the dominant remaining no-ground is the **leaver-find-gap**: in a Sally-Anne scene the character who *leaves* before the object is moved must have perceived the **initial location** to hold a (now-stale) false belief, but that initial location comes from a "they **find** the X in the Y" clause the episodic extractor does not reliably capture **with a location**. Real failing item (`tests/data/eval_tom_bench/full.jsonl:353-357`, qids `tb-false-belief-task-012..016`): *"Xiao Li and Youyou … they see a suitcase, a backpack, and a storage locker, they find a hat in the suitcase, Youyou leaves the basement, Xiao Li moves the hat to the storage locker."* — asked "where does Youyou look for the hat?", gold = "Suitcase" (the initial location).

---

## 1. Goal & scope

Make the episodic extractor capture **state-establishing initial locations** ("they find X in Y" → X is located at Y) so the leaver — already a present witness — forms the correct stale belief. Add a small deterministic **compound-cognizer split** as a cleanup/robustness backstop.

**The load-bearing fix is the prompt (C0).** Trace why: the leaver (Youyou) is named in her own *"Youyou leaves"* clause, so she is in the reconstructor's **cast** (every named cognizer) and **default-present from the scene start** (`perception_reconstructor.cpp` presence model). She is therefore a witness of the *find* event (seq-before her leave) **regardless of whether the find names her** — so she grounds **iff the find event carries a non-empty `location`** (the reconstructor's physical-location branch is gated on `!ev.location.empty()`). Today the prompt's `location` rule is "the **resulting** place after the action", so "find X in Y" emits `location=null` → the reconstructor writes nothing → the leaver has no initial perception → `[name-drift]` miss (the *move* event exists for the theme, so the M5 tag reads name-drift, but the real cause is the missing find-location). **Capturing the find with a location is the whole fix for ToMBench.**

**The compound split is secondary cleanup (C0), NOT the load-bearing fix.** "Xiao Li and Youyou find …" makes the find's `actor` the compound surface "Xiao Li and Youyou"; today `name_resolver` registers one junk compound cognizer and it becomes a junk extra cast member. This does **not** block the leaver (she is in the cast via her own *leave* clause). The split is worth doing because (a) it removes the junk compound cast-member/registration, and (b) it covers the *rare* case — not present in ToMBench's Sally-Anne shape but possible in open narratives — where a participant is named **only** inside a compound (then it would be load-bearing). So it ships, demoted to a backstop.

**Out of scope (deferred):**
- **`see X in Y` as a physical initial location.** `see`/`look` already route to `state_dim="content"` (the unexpected-contents channel, `is_see` → content branch). Reusing `see` for a physical location would collide with that semantics. The prompt uses **`find`/`discover`** for physical initial location (which routes to the location branch); `see` stays content. No reconstructor routing change.
- **Stative "X is in Y" / "there is an X in Y" capture** is best-effort only (C5): the extractor is action-oriented, so it reliably emits the *action* "find/discover" but may drop a pure stative clause. The prompt instructs the stative forms too, but the design does not depend on them — ToMBench uses "find".
- **Configurability** (prompt/vocab injection) — the next spec (#3). **Bare Chinese "和" splitting** — excluded (C4, see §3.2).

## 2. Current state (file:line)

- **Episodic prompt** `python/starling/extractor/episodic_prompt.py`: `location` rule (:35) = "the object's **RESULTING place after the action**" — no state-establishing/initial-location instruction; PREFER verb list (:33) = {put, place, move, take, give, remove, transfer, leave, open, close, tell, inform} — **`find` absent**; `actor` (:32) / `participants` (:36) rules — **no compound-split instruction**; 4 worked examples (:43-87) — none show a "find X in Y" initial location or a compound subject.
- **Reconstructor** `src/cognizer/perception_reconstructor.cpp`: presence cast = every cognizer named in any non-tell event (built from `participants_of(ev)` = actor + parsed `participants_json`); **default-present from scene start**, a `leave` removes the leaver only *after* its own event; physical-location branch gated on `!ev.location.empty()` (~:193) writes `perception_state(witness, theme, state_dim="location", value=location)`. A non-tell/non-presence/non-content/non-close predicate with a location (e.g. `find`) routes to this location branch **today, zero code change**. `is_see` (~:55) routes `see`/`look` to the **content** branch (~:174).
- **Resolver** `src/cognizer/name_resolver.cpp`: `resolve_or_register_cognizer("Xiao Li and Youyou")` registers one compound cognizer (`canonical_name` = the verbatim compound); no conjunction handling. `fold_internal_spaces` already exists alongside.
- **Schema — no blocker:** `episodic_events.location` (migration 0025) is nullable TEXT; `perception_state.state_dim='location'` (migration 0026) is ready. An initial-location find is just an `OCCURRED` statement with `location` set.

## 3. Architecture

### 3.0 Decisions locked (brainstorming)

1. **Prompt-primary + a deterministic compound-split backstop.** No registry change, no reconstructor routing change, `canonicalize` untouched.
2. **Compound split lives in the reconstructor's `participants_of` (read-time).** The stored statement stays as the LLM emitted it (compound `subject_id` is cosmetic); the split affects only the presence cast/witnesses.
3. **Initial physical location uses `find`/`discover` in the prompt** (routes to the location branch); `see` stays content.
4. **Two-track measurement** — deterministic (split + leaver-find grounding) + real-model grounding-recall re-run.

### 3.1 Episodic prompt changes (the load-bearing fix — Python config data)

`python/starling/extractor/episodic_prompt.py` (purely additive; existing put/move/leave/tell/see-content rules unchanged → existing scenes extract identically, C6):
- **Extend the `location` rule** to cover **state-establishing initial location**: for "they **find/discover** X in Y" → `action="find"`, `theme=X`, `location=Y` (the container/place where X is found). The existing "resulting place" wording stays for action verbs; this adds the find/initial case.
- **Add `find` (and `discover`) to the PREFER verb list.** (Prompt-only — NOT the C++ `kActionPredicates` registry: `OCCURRED` rows accept out-of-vocab verbs verbatim, and `find` is not in any reconstructor special-set, so a `find` with a location routes to `state_dim="location"` with zero code change.)
- **Add a compound-subject / pronoun-coreference instruction** to the `actor`/`participants` rules: "If a clause has a conjoined subject ('X and Y …') or a plural pronoun back-reference ('**they** …' / 'them' referring to people named earlier), **resolve it to the individual names** and list each in `participants`; pick a single individual or omit `actor` for a group action. Do not emit a single 'X and Y' string, or a bare 'they', as a person." This covers the common "they find …" phrasing. (Backstop is the reconstructor split, §3.2.) **This is cosmetic, not load-bearing (C0/N4):** the find event's `actor`/`participants` are irrelevant to the leaver grounding — she is a witness via default-presence from her own *leave* clause regardless; clean actor/participants only remove junk cast members and cover the rare only-in-compound participant.
- **Add a worked example** of the leaver-find 5-clause shape: the Xiao-Li/Youyou narrative → ordered events `find(hat, location=suitcase, participants=[Xiao Li, Youyou])`, `leave(Youyou)`, `move(hat → storage locker, Xiao Li)`. This is the primary lever (C1: the prompt's effect is an LLM-behavior bet measurable only by the real-model eval; the worked example is how we steer it, and it may need real-model iteration).
- **`see`/`look` unchanged** — reserved for labelled-container apparent content; physical initial location uses `find` (avoids the see=content routing collision).

### 3.2 Compound-cognizer split (C++ backstop — secondary)

A new deterministic free function in `src/cognizer/name_resolver.{hpp,cpp}` (the cognizer-surface utility home, beside `fold_internal_spaces`):

```cpp
// Split a conjoined cognizer surface into individuals; returns {surface} if no
// clear conjunction. Conservative + delimiter-bounded (never splits a single name).
std::vector<std::string> split_compound_cognizers(std::string_view surface);
```

Called from `perception_reconstructor.cpp`'s `participants_of(ev)`: each actor/participant surface is passed through `split_compound_cognizers` and the results flattened into the cast/witness surfaces. So a residual compound "Xiao Li and Youyou" (if the LLM didn't split it) becomes `[Xiao Li, Youyou]` in the presence cast.

**Conservative delimiter set (C4):** split on **`" and "`**, **`" & "`**, **`", "`** / **`", and "`** (English, space/punctuation-bounded — never splits "Anderson"/"Sandy"), and **`"、"`** (CJK enumeration). **Bare `"和"` is EXCLUDED** — it is a common Chinese name character with no word boundary ("和田"), so splitting on it would over-split; ToMBench's romanized names use `" and "`. A surface with no delimiter returns `{surface}` unchanged (so single names — every existing Sally/Anne/B/grounding fixture — are a no-op, C7).

The stored `subject_id` is left untouched (the write-path `name_resolver` still registers a junk compound cognizer — cosmetic and isolated: "Xiao Li" does not normalized-alias-match "xiao li and youyou", so individual resolution is unaffected, C3). Splitting at read time is sufficient because grounding reads the cast from the stored events.

### 3.3 No other changes

No `kActionPredicates`/registry change; no reconstructor routing change (`find`→location is already correct); `canonicalize_object`/`canonicalize_string` untouched (parity intact).

## 4. Data flow

```
"they find a hat in the suitcase, Youyou leaves, Xiao Li moves the hat to the storage locker"
→ EpisodicExtractor (new prompt): find(hat, loc=suitcase, participants=[Xiao Li, Youyou]) + leave(Youyou) + move(hat → locker, Xiao Li)
→ PerceptionReconstructor: participants_of splits any residual compound → cast={Xiao Li, Youyou};
   default-present at find(seq1) → both witness → perception_state(Xiao Li, hat, location, suitcase) + (Youyou, hat, location, suitcase);
   Youyou leaves(seq2) → absent at move(seq3)
→ what_does_X_think(Youyou, hat) = suitcase (stale; ground truth=locker) ✓
```
Even with a compound `actor` and an un-split participants list, the leaver grounds via default-presence (from her own *leave* clause) — the split only cleans the junk compound cast member and covers the rare only-in-compound case (C0).

## 5. Error handling

- `split_compound_cognizers` is conservative: no clear delimiter → returns the surface unchanged (no false split). Best-effort throughout (inherited from B/grounding).
- If the LLM still emits the find with `location=null` (the prompt is a bet, C1), the reconstructor writes nothing and the leaver misses — degrades to today's behaviour, never crashes. The real-model eval is how we detect + iterate this.
- Single-scene / tenant assumption inherited from B.

## 6. Testing (two tracks — decision 4)

1. **Deterministic** (no real LLM): (a) C++ `split_compound_cognizers` units — `"Xiao Li and Youyou"`→`["Xiao Li","Youyou"]`, `"A, B and C"`→`["A","B","C"]`, `"X、Y"`→`["X","Y"]`, and **guards**: `"Anderson"`/`"Sandy"`/`"和田"` (bare 和) → unchanged single. (b) Reconstructor unit **isolating the split**: a SINGLE `find` event whose `actor` is a compound ("X and Y") with a location, and **no other clause naming the individuals** → both split individuals get a `perception_state` location row (without the split only the junk compound would, so X and Y grounding proves the split adds them to the cast). (c) **stub-LLM leaver-find e2e** (`tests/python/`): canned episodic JSON for the Xiao-Li/Youyou scene (compound-actor `find@suitcase` + `leave(Youyou)` + `move(hat→locker, Xiao Li)`) → `what_does_X_think(Youyou, "hat")` = `"suitcase"`, `is_stale=true`; `(Xiao Li, "hat")` = `"locker"`. (This proves the **machinery**; it does NOT prove the prompt, which only a real LLM exercises — C1.)
2. **Real-model grounding-recall re-run** (`STARLING_RUN_LLM_E2E` gate; on-demand, **after the tokenkey.dev budget window recovers — this spec burns no API**): re-run `scripts/eval_perception_starling.py`; expect the leaver-find probes to ground and the M5 `[name-drift]` tag to purify (fewer leaver misses). **No fixed lift is promised** (C1) — the real run measures whether the prompt elicits find-with-location + split.
3. **Regression:** ctest 644 / pytest 625 stay green — the prompt additions are additive (existing scenes extract identically; stub-LLM B tests are prompt-independent) and the split is a no-op for delimiter-free single names.

## 7. Constraints

The prompt is **Python config data** (`episodic_prompt.py`); `split_compound_cognizers` is **C++** (`src/cognizer/name_resolver`). Do **not** touch `canonicalize_object`/`canonicalize_string` (parity intact); no new migration; reuse `name_resolver`/the reconstructor; do not break belief / multi-order-ToM / six-state / conflict / A-episodic / B-perception / grounding pins. `perceived_by_json` immutable. TDD; explicit-path `git add` (never `.`/`-A`); commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; no `--no-verify`/`--amend`; rebuild editable `_core` (`--python-editable`) after the C++ change; build from repo root `/Users/jaredguo-mini/develop/memory/starling`, ctest via `.venv/bin/ctest --test-dir build`.
