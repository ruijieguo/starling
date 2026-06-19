# Entity & Theme Grounding Resolution — Design

**Date:** 2026-06-19
**Status:** Approved (design); pending implementation plan.
**Context:** A funded end-to-end ToMBench eval scored **0.39 (39/100)**. The diagnosis isolated the bottleneck precisely: sub-project B's perception machinery is **39/41 = 95% correct on every probe that grounds** (0 crashes, only 2 wrong beliefs), but **59/100 probes never ground** — extraction produces no `perception_state` row whose `(cognizer, theme)` matches the queried tuple. Decomposition of the no-ground misses: ~34 are the *leaver* (the initial "find X in Y" location is never extracted), ~22 are the *mover* (suspected cognizer-name surface drift), 2 are theme plurals/articles. The cause is **surface drift at the grounding seam**: extracted `subject_id` (cognizer names like "Xiao Hong" vs "XiaoHong") and `object_value` (themes like "cabbage" vs "the cabbage" vs "cabbages") are written **raw** and compared by **exact match** downstream, so identical entities split into non-matching buckets. This spec generalizes the grounding seam — deterministic, parity-safe resolution of cognizer and theme surfaces to canonical identities — instead of patching the action vocabulary per failing case. It is the first of a sequence (this **resolution** spec → extraction **completeness** spec [the "find" initial-location gap] → **configurability** spec); those two are explicitly out of scope here.

---

## 1. Goal & scope

Resolve extracted **cognizer names** and **theme surfaces** to canonical identities at the **extraction write path** (and symmetrically at the query input), so downstream exact-match grounding (ToM beliefs + B perception) stops splitting on surface drift. Deterministic and **byte-parity-safe** (the `canonical_object_hash` contract is preserved). Reuse the existing cognizer entity machinery where it fits.

**In scope:** (a) cognizer-name resolution (case / internal-whitespace / punctuation drift) via the existing `CognizerHub`/`alias_normalizer` (or a thin equivalent if that API doesn't fit — G1); (b) theme normalization (leading-article stripping + conservative singularization); (c) a two-track grounding-recall measurement.

**Out of scope (deferred, named here so the boundary is explicit):**
- **Extraction completeness** — the "find/see X in Y" initial-location gap (~34 leaver misses). That is a *prompt/extraction* change, a separate spec; resolution cannot recover a fact extraction never produced (G3).
- **Configurability** — injectable prompts/vocab/model per domain (a separate spec).
- **Coreference / nicknames** — "Hong" as a short form of "Xiao Hong" does NOT resolve here (normalized "hong" ≠ "xiaohong"); deterministic resolution covers *surface drift* only. Semantic/LLM coreference is a deferred **seam** (S7).
- **Semantic synonymy** — "cabbage" = "vegetable" is not resolved (the deferred semantic seam); a non-deterministic resolver cannot drive the parity-stable hash (decision 1).
- **Non-extraction write sources** — dashboard manual entry / directly-seeded statements bypass the extraction write path and are not resolved (the eval is extraction-driven). (S5/S8.)

## 2. Current state (file:line)

- **Extraction is LLM-based** (both passes). Belief: `python/starling/extractor/prompts.py` `EXTRACTION_PROMPT` → `src/memory/memory_ops.cpp:62` `Extractor::run` (`src/extractor/extractor.cpp:198`). Episodic: `python/starling/extractor/episodic_prompt.py` `EPISODIC_EXTRACTION_PROMPT` → `src/extractor/episodic_extractor.cpp:72`. Dual pass orchestrated in `python/starling/_memory_core.py:124-149`.
- **`subject_id` written raw, zero entity resolution:** belief `src/extractor/json_parser.cpp:97`; episodic `src/extractor/episodic_extractor.cpp:142` (actor) + the `participants_json` it writes from the event's `participants` array. Downstream ToM grounding keys on exact `subject_id` equality (`src/tom/mentalizing_shared.cpp`, `src/tom/second_order.cpp`, `src/tom/common_ground_subscriber.cpp`) and B perception keys on `cognizer_id` (= the resolved actor) + `theme_id` (= `object_value`).
- **`canonical_object_hash`:** `schema::canonicalize_object` → `canonicalize_string` (`src/schema/canonicalize.cpp:194-242`): NFC + lowercase + whitespace-fold → sha256. **Case/whitespace-insensitive only — NOT article/plural/synonym-aware.** Computed at `json_parser.cpp:116` (belief) + `episodic_extractor.cpp:145` (episodic). **C++/Python byte-parity is a hard contract** (`tests/python/test_canonicalize_parity.py`).
- **Existing cognizer entity machinery (the reuse target — G1):** `src/cognizer/cognizer_hub.cpp` (register API composing `canonical_name` + raw aliases + normalized aliases, with an **`AliasCollision`** check); `src/cognizer/alias_normalizer.cpp` `normalize_alias` (`:17-47`: trim + collapse whitespace runs + ASCII case-fold; **non-ASCII passes through, and a single internal space between tokens is NOT removed** — so it does NOT currently fold "Xiao Hong" vs "XiaoHong"); schema `migrations/0008_cognizer_schema.sql`. **This machinery is NOT called by the extraction write path today.**

## 3. Architecture

### 3.0 Decisions locked (brainstorming)

1. **Deterministic + registry-indirection** resolution. The content hash must stay deterministic + parity-stable, so resolution that affects grounding is deterministic; semantic/LLM resolution is a deferred seam that can only *populate a registry*, never drive the hash.
2. **Write-path resolution** for cognizers (store canonical ids; query inputs resolved the same way; downstream SQL exact-match unchanged).
3. **Theme normalization runs *before* `canonicalize_object`** (which is left UNCHANGED — parity intact, no hash migration).
4. **Two-track measurement** — deterministic resolution unit tests + a gated real-model ToMBench grounding-recall metric.

### 3.1 Cognizer resolution (decision 2; reuse target G1)

At the extraction write path, each cognizer surface (`subject_id`/`actor`, **and every name in `participants_json`** — G4) is passed through **`resolve_or_register(surface, tenant)` → canonical id**:
- First occurrence in a tenant **registers** a canonical entity whose **`canonical_name` is the first-seen surface, preserved verbatim** (NOT lowercased — so a lone "Sally" stays "Sally"; S5).
- Later surfaces whose **strengthened normalization** matches an existing entity's normalized aliases **resolve** to that canonical id.
- The stored `subject_id` / `participants` become the canonical id; surface variants live as the entity's aliases.

**Strengthened normalization (beyond today's `alias_normalizer`):** fold case + collapse ALL internal whitespace (so "Xiao Hong" → "xiaohong" matches "XiaoHong") + strip surrounding punctuation. This is a deterministic, ASCII-and-CJK-safe function; today's `normalize_alias` keeps the internal space, so it must be extended (or a new normalizer added) — confirmed gap (§2).

**G1 — reuse-pending-verification + fallback.** The *first* implementation step is to grep/verify `CognizerHub`'s actual public API: does a usable `resolve_or_register` (or `resolve` + `register`) exist, and does `AliasCollision` mean "resolve to the existing canonical" (usable) vs "throw" (must be caught and turned into a resolve)? **If `CognizerHub` fits, reuse it.** If its API does not expose a clean resolve-or-register, the **fallback** is a thin extraction-side `name_resolver` (its own per-tenant normalized-alias table + the same strengthened normalization) — still deterministic, still write-path, still keyed identically. The design principle (deterministic write-path name resolution) holds either way; "reuse `CognizerHub`" is the *preferred* impl, not a guaranteed-clean one.

`holder_id` needs no resolution (overridden to the agent/self at write — `json_parser.cpp:90-93`); only `subject_id`/`actor`/`participants` carry the drift.

**Why participant resolution is load-bearing for B (M3).** B's `PerceptionReconstructor` is a post-pass that reads the just-written `statements.subject_id` (actor) + `episodic_events.participants_json` to build its presence cast and to key `perception_state.cognizer_id`. Because the episodic write now stores **resolved** actor + participants (G4), the reconstructor's cast and `perception_state` are canonical ids — so a query `what_does_X_think(resolve(x), …)` matches. If participants were left raw while the actor was resolved, the cast would mix canonical + raw surfaces and presence reconstruction would silently break — which is exactly why G4 covers *every* participant, not just the actor.

### 3.2 Theme normalization (decision 3)

A new deterministic C++ function `normalize_theme(surface) → surface` (in `src/schema/`, beside `canonicalize.cpp`):
- **Strip leading articles** `the` / `a` / `an` (the safe core).
- **Conservative singularization** (the riskier half — S3): suffix rules (`-ies → -y`, `-es → ∅` after s/x/z/ch/sh or o, else `-s → ∅`), a small **irregular map** (leaves→leaf, knives→knife, …), and a **stoplist** of non-plural `-s` endings (`-ss`, `-us`, `-is`, plus specific words: bus, glass, boss, lens, series, …) so "bus"→"bus", "glass"→"glass". Unknown words pass through unchanged (no false merge). If singularization proves to mis-merge in the grounding-recall benchmark, it degrades to **article-strip-only** (the safe core) without redesign.

`normalize_theme` runs **before** `canonicalize_object` at every write site (so both the stored `object_value` and the hash are on the normalized surface) and at every query input. **`canonicalize_object` / `canonicalize_string` are UNCHANGED** — the parity test stays green, no existing hash migrates. `normalize_theme` has a single C++ implementation; Python calls it through the binding if needed (no dual-implementation parity burden).

**Applicability (M8) — must not corrupt non-theme objects.** `normalize_theme` applies ONLY to **entity / string theme** object_values (the grounding target: containers/objects like basket, cabbage, "Smarties tube"). It is **NOT** applied when `object_kind` ∈ {`int`, `float`, `bool`, `datetime`, `cognizer`, `statement`} — those pass to `canonicalize_object` unchanged (singularizing "2026" or stripping an article from a nested-statement id would corrupt it). The belief parser hardcodes `object_kind="str"` (`json_parser.cpp:100`), so belief objects ARE normalized; the conservative article-strip + stoplist rules avoid mangling incidental non-theme strings (e.g. quantity phrases), and the false-positive ctests guard it. Episodic events are always `object_kind=entity` (a theme) — always normalized.

**Provenance (M7) — asymmetry, by design.** The stored `object_value` becomes the *normalized* surface; the original phrasing ("the cabbages") survives in the **engram / raw text**, not the statement — a deliberate grounding choice (there is no theme registry, by decision 3). Cognizer surfaces, by contrast, ARE preserved (as `CognizerHub` aliases). This asymmetry is acceptable: the raw text is always recoverable from the engram.

### 3.3 Touch points — write + query symmetry (G2/S2, the silent-mismatch risk)

Resolution must be applied at **every** point where a cognizer or theme surface enters or is queried; missing one silently breaks matching. The complete enumeration (the plan implements a guard test that round-trips a plural theme + a drifted name through write→query):

| Surface | Write sites | Query sites |
|---|---|---|
| cognizer (`subject_id`/`actor`/`participants`) | `json_parser.cpp` (belief subject) ; `episodic_extractor.cpp` (actor + each participant) | inside `what_does_X_think` (the `x` and `observer` args) ; inside `does_X_know` / `FactKey` construction ; B `perceived_for_theme`/`last_known` callers |
| theme (`object_value`) | `json_parser.cpp` + `episodic_extractor.cpp` — `normalize_theme` **before** `canonicalize_object` | inside `what_does_X_think` (the `theme` arg) ; inside `does_X_know` FactKey object |

Resolution is centralized **inside the query primitives** (so any caller passing a raw name/theme — incl. the eval harness — is normalized internally), not duplicated in callers.

### 3.4 Deferred semantic seam (decision 1)

Resolution is invoked through a narrow interface (the `resolve_or_register` call + `normalize_theme`); the deterministic impl ships now. A later **semantic/LLM resolver** (coreference, synonymy) can *populate the cognizer registry's aliases* or pre-map theme surfaces — but it never computes the hash (which stays deterministic). No semantic code is built here; the seam is just the interface boundary.

## 4. Data flow

```
remember(text) → extraction (LLM) → per statement/event:
   subject_id / actor / each participant → resolve_or_register(tenant) → canonical id   [store canonical]
   object_value → normalize_theme() → canonical surface → canonicalize_object(hash)      [store normalized]
→ stored statements/events carry canonical entities → downstream exact-match grounding hits
query: what_does_X_think(x, theme[, observer]) / does_X_know(FactKey):
   x / observer → resolve;  theme → normalize_theme  → match stored canonical (SQL exact-join unchanged)
```

## 5. Parity & regression safety

- `canonicalize_object` / `canonicalize_string` **unchanged** → `test_canonicalize_parity.py` stays green; no `canonical_object_hash` migration; existing data unaffected.
- `normalize_theme`: single C++ impl, Python via binding → no dual-parity burden.
- Cognizer resolution is in the **extraction write path only** (NOT `StatementWriter`) → directly-seeded ctest (most of the suite) is unaffected; only real-extraction e2e tests exercise resolution. For a **single-surface name the canonical equals the surface** (idempotent) → existing belief/ToM/B pins stay green (S5/S8). The cognizer-registration write is **best-effort within the write SAVEPOINT**.

## 6. Error handling

- Resolution failure (hub error, malformed surface) → **fall back to the raw surface** (best-effort; never fail `remember`).
- Conservative singularization stoplist/irregular-map prevents over-merge; unknown words pass through.
- Tenant-scoped, single-scene assumption inherited from B: cross-narrative same-name collisions within one tenant are out of scope.

## 7. Testing (decision 4, two tracks)

1. **Deterministic ctest** (no LLM): `normalize_theme` (`cabbages→cabbage`, `the cabbage→cabbage`, `boxes→box`, `tomatoes→tomato`, `leaves→leaf` [irregular], and the false-positive guards `bus→bus`, `glass→glass`, `boss→boss`); cognizer resolution (`"Xiao Hong"`/`"XiaoHong"`/`"xiao hong"` → same canonical id; distinct names → distinct; first-seen surface preserved as canonical_name); a **write→query round-trip** test (a plural theme + a drifted name written via extraction, then queried, must ground — G2). The `canonicalize` parity test stays green (unchanged).
2. **Gated real-model grounding-recall** (`STARLING_RUN_LLM_E2E` / the eval gate): extend the perception eval to report **`grounding-rate`** (% probes producing any belief) as a first-class metric **separate from accuracy**, and to **decompose** the no-ground misses into *name-drift-recoverable* vs *extraction-incompleteness*. **Decomposition mechanism (M5):** for each no-ground probe, query whether ANY `OCCURRED` event for the *normalized* theme exists (with any cognizer); if an event exists, the miss is **name-drift / resolution-addressable**; if no event exists for the theme at all, it is **extraction-incompleteness** (the next spec's concern, not this one's). The report thus shows how much resolution alone can lift — G3. Exit signal = re-run the perception eval and **measure** the lift; **no fixed target is promised** (the 0.39 → ? lift is whatever the name-drift subset turns out to be; the residual leaver/extraction-incompleteness is the next spec's).
3. **Regression:** ctest 638 / pytest 624 stay green (cognizer write-resolution is the only behavioral touch; pinned by the single-surface-idempotent property).

## 8. Constraints

Core logic **C++** (`normalize_theme` in `src/schema/`; cognizer resolution wiring in `src/extractor/`; reuse `src/cognizer/` machinery or a thin equivalent); Python forwards/binds only. **`canonicalize_object` byte-parity preserved** (do not modify it). Reuse `CognizerHub`/`alias_normalizer` where the API fits (G1 fallback otherwise). Resolution **best-effort** (never fail `remember`); registration within the write SAVEPOINT. Do not break belief / multi-order-ToM / six-state / conflict / A-episodic / B-perception pins. `perceived_by_json` immutable. TDD; explicit-path `git add` (never `.`/`-A`); commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; no `--no-verify`/`--amend`; rebuild editable `_core` (`--python-editable`) after C++/binding changes; build from repo root `/Users/jaredguo-mini/develop/memory/starling`, ctest via `.venv/bin/ctest --test-dir build`.
