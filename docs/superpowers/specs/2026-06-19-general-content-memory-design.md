# General-Content Memory (Sub-Project C) — Design

**Date:** 2026-06-19
**Status:** Approved (design); pending implementation plan.
**Context:** Final stage of the general-memory arc (A episodic events ✅ → B perception/knowledge ✅ → **C arbitrary content**), driven by "end-to-end ToMBench showed the claim extractor extracts 0 from non-conversational, non-event text." A added a physical-event pass; B added perception/knowledge tracking; the grounding sequence (resolution/completeness/configurability ✅) fixed entity/theme grounding and made prompts/vocab/thresholds injectable. **C closes the remaining extraction gap:** declarative world-facts that fall through BOTH existing passes — definitions ("X is a Y"), statives, relationships ("A reports to B"), quantities ("the budget is $40k"), attributes — produce **zero statements** today (`_memory_core.py` runs only the belief pass + the episodic pass; no catch-all). The A spec's Non-goals explicitly defer "**arbitrary unstructured content**" to C (`docs/superpowers/specs/2026-06-17-episodic-event-memory-design.md:13`).

---

## 1. Goal & scope

Add a **third extraction pass** ("general fact") to `remember` that captures arbitrary declarative facts as **self-held `BELIEVES` statements**, so any text becomes recallable structured facts. The pass **reuses the existing belief `Extractor`** (no new C++ extractor): a new general-fact prompt produces the same claim-JSON schema the belief `Extractor` already parses/validates/writes, with `holder=self`, `perspective=FIRST_PERSON`, `modality=BELIEVES`, a general predicate, and the value as object. A new curated **`kGeneralFactPredicates`** class makes common attributive/relational predicates core (so they are approved, not downgraded to `REVIEW_REQUESTED`), mirroring A's `kActionPredicates` and B's `kPerceptionPredicates`.

**Decisions locked (brainstorming):**
1. **Direction = general arbitrary-content memory** (not the remaining ToMBench cognitive dimensions — emotion/desire/intention/non-literal are out of scope here).
2. **Representation = self-held `BELIEVES`** + a 4th curated predicate class. No new modality, no schema migration.
3. **Recall = extraction-first.** Self-held facts hit the existing default `recall(holder=self, perspective=first_person)` — no new recall surface, no holder-agnostic search.
4. **The third pass is ON by default** (`general_fact_prompt` defaults to the new constant; `remember` always runs three passes). Cost: one extra LLM call per `remember`, accepted for out-of-the-box general-content memory.

**Why reuse the belief Extractor (not a new extractor):** the belief `Extractor` is prompt-driven — it parses the LLM's claim-JSON, runs `validate_extracted_statement`, resolves the cognizer surface via `CognizerHub`, and writes (`src/memory/memory_ops.cpp:66-69`). The "conversation machinery" lives in the *prompt*, not the C++. A general-fact prompt that emits the same JSON schema (`prompts.py:21`) is handled identically. This makes C mostly **prompt data + one predicate class + wiring**, the lightest of the three sub-projects.

**Out of scope (deferred):**
- **Holder-agnostic / cross-holder semantic recall** + surfacing the verbatim engram on the recall path (the A-spec's *second* C non-goal). Self-held facts are recallable by default; a general "search everything by meaning" surface is a separate change.
- **Remaining ToMBench dimensions** (emotion/desire/intention/non-literal communication).
- **A new modality** for world-facts (`ASSERTED`/`FACT`). `BELIEVES` is reused.
- **De-duplication across passes.** The three passes may emit overlapping facts; per-statement content-hash idempotency already collapses exact duplicates, and differing framings landing as separate recall surfaces is acceptable.

## 2. Current state (file:line)

- **Two passes, no catch-all:** `python/starling/_memory_core.py:118-166` — belief via `_core.memory_remember(adapter, llm, belief_prompt, …, policy=…)` (creates the engram + extracts), then episodic via `_core.EpisodicExtractor(conn, llm, adapter, episodic_prompt).extract(…)` on the returned `engram_ref`. Content matching neither pattern → 0 statements.
- **The claim-JSON schema the belief Extractor consumes** (`python/starling/extractor/prompts.py:21`): `{"holder": str, "holder_perspective": "FIRST_PERSON"|"QUOTED"|"HEARSAY"|"INFERRED", "subject": str, "predicate": str, "object": str, "modality": "BELIEVES"|"DESIRES"|"INTENDS"|"COMMITS"|"ENFORCES"|"OBSERVES", "polarity": "POS"|"NEG"|"UNKNOWN", "nesting_depth": int}`. The general-fact prompt emits THIS shape.
- **Idempotent re-extraction is confirmed:** `src/memory/memory_ops.cpp:48-69` — `append_evidence` returns Accepted **or Idempotent** → both set `engram_ref` and **run `Extractor.run`** (only `NoStore`/`Rejected` early-return at `:57`/`:60`). So a **second `memory_remember` call with the same payload + a different prompt** re-extracts on the idempotent engram. This is the third-pass wiring.
- **Predicate registry** `include/starling/extractor/predicate_registry.hpp:16-50` — three `inline constexpr std::array` (`kCoreBeliefPredicates` {believes,doubts,forbids,knows,located_at,member_of,prefers,promises,requires,responsible_for}; `kActionPredicates`; `kPerceptionPredicates`) + `is_core_predicate` linear scan. Out-of-set non-OCCURRED predicates → `REVIEW_REQUESTED` (`statement_validator.cpp:88`).
- **Injection seam exists (from #3):** `ExtractionConfig` (`python/starling/extractor/config.py`) carries `belief_prompt`/`episodic_prompt`; `MemoryCore` stores `self._extraction` and `_build_policy`. Adding a `general_fact_prompt` field + a third pass slots into this.
- **Recall default** `_memory_core.py` `recall` → `holder = holder or self.agent`, `perspective="first_person"` → semantic retriever scopes to that holder/perspective. Self-held `BELIEVES` facts match.

## 3. Architecture

### 3.1 The general-fact prompt (new Python prompt data — the content lever)

`python/starling/extractor/general_fact_prompt.py` — `GENERAL_FACT_EXTRACTION_PROMPT` (single `{convo}` placeholder, `str.replace`, mirroring `prompts.py`). It instructs the model to extract **declarative world-facts** from any passage — the content the belief pass (focal-speaker mental-state claims) and episodic pass (physical events) skip:
- **Targets:** definitions / taxonomy ("X is a Y" → `is_a`), attributes/properties ("the server has 64GB RAM" → `has_property`/`has_value`), quantities ("budget is $40k" → `has_value`, object may be a number string), relationships ("Alice reports to Bob" → `reports_to`; "auth depends on the token service" → `depends_on`), composition ("the API is part of the platform" → `part_of`).
- **Output:** the belief claim-JSON schema (`prompts.py:21`) with `holder=`the self/agent name (a `{self}` placeholder filled by `MemoryCore` — §3.2), `holder_perspective="FIRST_PERSON"`, `modality="BELIEVES"`, `polarity="POS"`, `nesting_depth=0`, `subject`=the entity, `predicate`=a general-fact predicate (§3.3), `object`=the value (canonical short noun, or a number/string for quantities).
- **Anti-overlap guidance:** do NOT re-extract a focal speaker's *opinion/commitment* (belief pass owns those) or a *physical event* (episodic pass owns those); emit `[]` when the passage is purely conversational/eventful with no standalone declarative fact.
- The prompt is an LLM-behaviour bet steered by worked examples; real-model iteration tunes it (like A/B/completeness).

### 3.2 Wiring the third pass (`MemoryCore.remember`)

After the belief + episodic passes, run a third pass on the **same engram**:
```python
gf = _core.memory_remember(
    self.rt.adapter, self.llm, self._extraction.general_fact_prompt,
    tenant_id=self.tenant, holder_id=holder_id, interlocutor=interlocutor or "",
    adapter_name=self.adapter_name, source_prefix=self.source_prefix,
    created_at_iso8601=created_iso, payload=text.encode("utf-8"),
    policy=_build_policy(self._extraction))
# merge gf["statement_ids"] into out["statement_ids"]
```
The second `memory_remember` sees the engram as **idempotent** (same `sha256(payload)` key) → re-extracts with `general_fact_prompt` → general-fact statements (confirmed `memory_ops.cpp:48-69`). Belief + general both go through `memory_remember`/`Extractor` (different prompts); episodic stays on `EpisodicExtractor`. Statement-id merge mirrors the existing episodic merge.

**Holder = self.agent (the recall-default holder) — the one integration point to nail.** General facts must land with `holder = self.agent` so the default `recall(holder=self, first_person)` hits them. Mechanism: the `general_fact_prompt` carries a **`{self}` placeholder** (in addition to `{convo}`); `MemoryCore.remember` fills it with `self.agent` via Python `str.replace` **before** passing the prompt to `memory_remember` (whose C++ side then fills `{convo}`) — a clean two-stage fill. So every general fact is emitted with `holder=<self.agent>` + `FIRST_PERSON`, stored under the recall-default holder, robust for ANY `agent=` (default `"self"` or a custom name) and independent of how the `Extractor` treats the `holder_id` param. A custom injected `general_fact_prompt` without a `{self}` marker simply gets a no-op replace (caller's choice). **Acceptance is behavioural: a general fact is retrievable via the default `recall`/`query` for `self`** (the e2e asserts this, not the internal holder string).

### 3.3 `kGeneralFactPredicates` (new C++ predicate class)

`include/starling/extractor/predicate_registry.hpp` — add a 4th `inline constexpr std::array` and extend `is_core_predicate` to scan it (mirrors `kActionPredicates`/`kPerceptionPredicates`):
```cpp
inline constexpr std::array<std::string_view, N> kGeneralFactPredicates = {
    "is_a", "instance_of", "has_property", "has_value",
    "part_of", "related_to", "depends_on", "reports_to",
};
```
(Representative set; the plan finalizes the exact list. **No overlap** with `kCoreBeliefPredicates` — `located_at`/`member_of`/`knows` already core, so spatial/membership general facts reuse those.) These predicates are then **approved, not `REVIEW_REQUESTED`**, when emitted by the general pass. The prompt's predicate vocabulary line stays in sync with this array (the `prompts.py`↔`predicate_registry.hpp` sync convention). This is the only C++ change.

### 3.4 `ExtractionConfig.general_fact_prompt` (reuse #3's carrier)

Add a 4th field to `python/starling/extractor/config.py`:
```python
general_fact_prompt: str = GENERAL_FACT_EXTRACTION_PROMPT
```
`MemoryCore.remember` reads `self._extraction.general_fact_prompt` (default = the new constant → the third pass is ON by default, decision 4). Per-deployment override rides the existing injectable carrier.

### 3.5 Grounding reuse + recall (unchanged)

The general pass goes through the same `Extractor` → `CognizerHub` subject resolution + `normalize_theme` object normalization as the belief pass (grounding consistency, no new code). Recall is unchanged: self-held `BELIEVES` facts match the default holder/perspective scope; the embedding worker already indexes all modalities, so semantic recall over general facts works once they're stored.

## 4. Data flow

```
"Postgres is a relational database. The deploy budget is $40k. Alice reports to Bob."
→ belief pass    (no focal-speaker mental-state claim)      → []
→ episodic pass  (no physical event)                        → []
→ general pass (NEW): self BELIEVES is_a(Postgres, relational database),
                      self BELIEVES has_value(deploy budget, $40k),
                      self BELIEVES reports_to(Alice, Bob)   → 3 statements (holder=self, approved)
→ recall("who does Alice report to", holder=self) → hits reports_to(Alice, Bob)
```
Default path (no `extraction=` override): `general_fact_prompt` = the new constant, the third pass runs. With a stub/real LLM that returns `[]` for the general prompt (no declarative facts), the pass is a no-op — behaviour for belief/episodic-only content is unchanged.

## 5. Error handling

- The third pass is **best-effort** (like episodic): an empty/failed general extraction yields no statements, never crashes `remember`. The engram + belief/episodic results are unaffected (the general pass runs last on the idempotent engram).
- Overlap with belief/episodic facts → content-hash idempotency collapses exact duplicates; near-duplicates land as separate recall surfaces (acceptable).
- A general fact whose predicate is outside `kGeneralFactPredicates` (model picks a novel relation) is still **accepted**, just `REVIEW_REQUESTED` — recallable, flagged for vetting (same lightweight-tier semantics as today).
- Single-tenant/self-holder assumptions inherited from A/B.

## 6. Testing

1. **C++ ctest** (`tests/cpp/`, extend the predicate-registry/validator test): the new `kGeneralFactPredicates` members return true from `is_core_predicate`; a general-fact predicate (e.g. `is_a`) on a non-OCCURRED statement is **not** `REVIEW_REQUESTED` under the default policy; a non-registered relation still is. Confirms the 4th class is wired into `is_core_predicate`.
2. **Python e2e — roundtrip** (`tests/python/`, stub-LLM): a `make_stub_llm` returning canned declarative-fact claim-JSON (`is_a`/`has_value`/`reports_to`, `holder="self"`, `modality="BELIEVES"`, `confidence≥0.5`); `Memory.open(agent="self", …).remember(<declarative text>)`; assert the general facts (a) are **stored** with an approved review status (not `REVIEW_REQUESTED`), and (b) are **retrievable via the default `recall`/`query` for `self`** (the behavioural holder=self.agent acceptance, §3.2). **Attribution caveat (stub artifact):** the belief `Extractor` accepts the SAME claim-JSON schema, so a single `default_response` stub would let the *belief* pass also write these facts (the stub ignores the prompt; the *real* belief prompt skips declarative facts). To attribute the facts to the **general** pass specifically, EITHER prompt-key the stub so only the general prompt returns the facts (belief/episodic → `[]`; the plan computes the built-prompt hash via `Extractor.compute_prompt_input_hash`), OR rely on §6.3's spy (which proves the third `memory_remember` runs with `general_fact_prompt`) for the wiring proof and let this e2e assert only the end-to-end storage+recall. The plan picks; the default-on, holder=self.agent, approved-status, recallable assertions are the load-bearing ones.
3. **Default-on / config:** `ExtractionConfig().general_fact_prompt == GENERAL_FACT_EXTRACTION_PROMPT`; an injected custom `general_fact_prompt` is the one forwarded to the third `memory_remember` (spy, mirroring #3's wiring test).
4. **Real-model general-content eval** (`STARLING_RUN_LLM_E2E` gate; on-demand, after the tokenkey.dev budget window recovers — this spec burns no API): a small declarative-fact corpus → remember → recall, measuring general-fact grounding-rate. No fixed lift promised; the run validates the prompt elicits clean self-held facts.
5. **Regression:** ctest (650 + the new general-fact ctest) / pytest (current + new) stay green. The third pass is additive; belief/episodic/six-state/multi-order-ToM/conflict/perception/grounding/completeness/configurability pins are independent of the new prompt (their stub LLMs are prompt-keyed) and unaffected.

## 7. Constraints

Core logic is C++ where it must be — the new `kGeneralFactPredicates` class + `is_core_predicate` extension (`predicate_registry.hpp`); everything else is Python prompt data (`general_fact_prompt.py`) + carrier (`ExtractionConfig.general_fact_prompt`) + wiring (`_memory_core.py` third pass). **Reuse the belief `Extractor`** — do NOT add a new C++ extractor. Do NOT touch `canonicalize_*`, the reconstructor, `validate_*` logic, or the belief/episodic prompt *content*. No new modality, no migration. General facts are self-held `BELIEVES` and must be recallable via the default `recall` (the behavioural acceptance). `perceived_by_json` immutable. The third pass is best-effort (never fails `remember`). TDD: failing test → red → minimal impl → green → commit. After C++/binding changes rebuild with `--python-editable`; C++ tests via `.venv/bin/ctest --test-dir build`; build from repo root `/Users/jaredguo-mini/develop/memory/starling`. explicit-path `git add` (never `.`/`-A`); commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; no `--no-verify`/`--amend`. Design phase burns no API.

**Phasing (for the plan):** ① `kGeneralFactPredicates` (C++ predicate class + `is_core_predicate` + ctest) → ② `general_fact_prompt` constant + `ExtractionConfig.general_fact_prompt` field (Python) → ③ third-pass wiring in `MemoryCore.remember` + holder=self verification + roundtrip e2e. Each phase keeps the suite green.
