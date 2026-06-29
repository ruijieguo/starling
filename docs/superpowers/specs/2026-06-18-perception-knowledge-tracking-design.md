# Perception & Knowledge Tracking (sub-project B) — Design

**Date:** 2026-06-18
**Status:** Approved (design); pending implementation plan.
**Context:** Second of three sub-projects (A episodic events → **B perception/knowledge** → C arbitrary content) extending Starling from a conversational social-mind memory into a general open-interaction memory. A made physical-action narratives ingestible as **episodic events** (`modality=OCCURRED` statements + `episodic_events` rows carrying `seq`/`event_time`/`location`/`participants_json`/`action_raw`, with `enter`/`leave` emitted as their own events, and `EpisodicEventStore::events_for_theme`/`latest_event_location`). A records events only; it explicitly deferred to B "who was *present/perceiving* at each event ... perception→knowledge inference, per-cognizer last-known state, and the false-belief query" (A design §5). B delivers exactly that, unifying four perception channels onto one per-cognizer knowledge ledger, and unlocks the ToMBench **False-Belief** and **Knowledge (Percepts→Knowledge)** tasks end-to-end.

---

## 1. Goal & scope

Turn A's episodic events into **per-cognizer perception → knowledge → (possibly stale) belief**, and expose a **false-belief query**. Cover four channels under one abstraction:

1. **Physical presence** (unexpected-transfer / Sally-Anne): a cognizer present at an event perceives it; one who left before a later event does not.
2. **Being told** (informational transfer): "Sally tells Anne the ball is in the box" → Anne learns the conveyed state without being present.
3. **Unexpected contents** (Smarties): seeing a closed labelled container yields a belief about its *apparent* content; opening it yields the *actual* content.
4. **Information access** (generalised "does X know fact F"): reuse `does_X_know` over B's materialised perception.

**Unifying abstraction.** Every false belief reduces to **"X's last-perceived *state* of theme T"**, differing only in (a) the *state dimension* (location vs content) and (b) *how* a cognizer perceives a state update (presence / told / seeing-appearance). One reconstructor materialises "which state-events X perceived" into one ledger; one query primitive returns the latest-perceived state.

**Non-goals (deferred):** multiple distinct scenes within one tenant (needs a scene/session id) and per-room co-location within a scene (decision-3 "by-location" variant) — single-scene-per-tenant assumed (§5); deep (≥3rd-order) perception nesting beyond co-presence (§4.1); semantic vector recall over perception facts (C; the embedded facade uses a stub embedder); arbitrary unstructured content (C).

## 2. Current state (file:line) — what B builds on

- **`KnowledgeFrontier`** (`include/starling/cognizer/knowledge_frontier.hpp` + `src/cognizer/knowledge_frontier.cpp`): per-cognizer, time-aware visibility ledger over tables `cognizer_presence_log` + `cognizer_frontier_facts` (`migrations/0008_cognizer_schema.sql`). Five record APIs (`record_presence_from_statement`, `record_explicit_told`, `record_accessible_source`, `record_group_membership`, `record_explicit_negation`); query `visible_engrams_at(tenant, cognizer, as_of)` (five-way union minus explicit-not-told, time-bounded). Idempotent on synthesised ids. **Fed today only from `perceived_by_json` via the belief-tracker handler.**
- **`does_X_know`** (`src/tom/mentalizing_know.cpp`): tri-valued `KnowsResult{FullKnowledge, NotKnown, Unknowable}`; input `FactKey{subject_kind, subject_id, predicate, canonical_object_hash}`. Step 1 = does X assert the POS fact; Step 2 = evidence-engram-refs ∩ `frontier.visible_engrams_at`. Bound `bindings/python/bind_08_tom.cpp:131`.
- **7 mentalizing primitives** (`include/starling/tom/mentalizing.hpp`, namespace `tom::mentalizing`): `what_does_X_believe`, `does_X_know`, `find_misalignment`, `shared_with`, `what_does_X_think_Y_believes` (recursive N-order over explicit nested **belief statements**), `predict_X_would`, `who_committed`. All Python-bound (`bind_08_tom.cpp`, `python/starling/tom/__init__.py`).
- **`belief_tracker_handlers.cpp::handle_statement_written`** (:36): per-statement bus subscriber; reads the statement's `perceived_by_json` from the DB and, per perceiver, calls `record_presence_from_statement` / `record_explicit_told` / `update_last_seen_at`. **A's OCCURRED events set `perceived_by={self}`** (`src/extractor/episodic_extractor.cpp:157`) → today only `self` is recorded; the actor (`subject_id`), `participants_json`, and the `enter`/`leave` sequence are never consulted. **This is the gap B fills.**
- **`perceived_by_json`**: real `statements` column (`migrations/0001_initial_schema.sql:50`), **immutable** (triggers `migrations/0006`/`0007`). B never mutates it.
- **A's deliverables (B's input):** `EpisodicEventStore` (`include/starling/store/episodic_event_store.hpp`) — `events_for_theme(tenant, theme)` [ordered by `seq`] and `latest_event_location(tenant, theme)` [global ground truth]; `episodic_events` columns `seq`/`event_time`/`location`/`participants_json`/`action_raw`; `enter`/`leave` are first-class OCCURRED events with their own `seq`. Theme identity links across events via the existing `canonical_object_hash`.
- **Action vocabulary** (`include/starling/extractor/predicate_registry.hpp`): `kActionPredicates {put, place, move, take, give, remove, transfer, leave, open, close}`. B extends this **additively** (§3.5).

## 3. Architecture

### 3.0 Decisions locked (brainstorming)

1. **Materialise** perception into the existing `KnowledgeFrontier` (not compute-on-query; not a parallel store).
2. False-belief query = a **new 8th mentalizing primitive** `what_does_X_think` (thin query over the materialised frontier; not materialised belief statements; not an overloaded `does_X_know`).
3. **Presence = scene-global, default-present, enter/leave override** (named cognizers presumed present from the scene start; explicit `enter` sets a later start; `leave` removes until re-enter; actor + named participants always present).
4. Materialisation runs in a **dedicated post-pass `PerceptionReconstructor`** (not a per-event handler branch; not a new bus subscriber).
5. All four channels = **one `state-update` event abstraction + per-kind perception rules** feeding one frontier; one generalised primitive.
6. **Three-track eval** (deterministic kernel / gated real-LLM e2e / ToMBench subset), mirroring P3.a2.

### 3.1 `PerceptionReconstructor` (C++, new — `src/cognizer/perception_reconstructor.{hpp,cpp}`)

Single-responsibility module: after an ingestion, (re)materialise per-cognizer perception for the tenant. It reads **all** the tenant's OCCURRED events (presence is scene-wide — see the scan below) and writes perception facts for the themes those events concern.

**Scope of the event scan (fixes self-review S1 + S2).** Presence is a property of the **scene**, not of any one theme. "Sally leaves" is *not* an event about the ball, so it is absent from `events_for_theme(ball)`. The reconstructor therefore scans **all OCCURRED events in the scene**, ordered on one timeline, and classifies each by predicate:

- **scene = the tenant's single accumulating scene** (§5, single-scene-per-tenant); the reconstructor processes **all OCCURRED events for the tenant** (so multi-turn narratives accumulate into one scene), ordered by **`(observed_at, seq)`** — a global order, since A's `seq` is monotonic only *within* an ingestion. Re-running over the full history each ingestion + idempotent writes keeps it correct across turns.
- **presence-change events** (`enter`/`leave` and synonyms, §3.5) drive the presence timeline.
- **state events** (location/content actions) are attached to their theme (via `object_value` / `canonical_object_hash`) and get a witness set computed from the presence timeline *at that event's position*.

**Presence timeline (decision 3, fixes N1).** Walk the ordered events. The scene's **physical cast** = cognizers named in **physical / `see` / `open` events** (actor `subject_id` or `participants_json`) or in an `enter`. A cognizer appearing **only as a `tell` teller/recipient is NOT added to the physical cast** — a tell conveys knowledge without implying co-location (§3.4), so it must not back-door physical presence (else "Anne phones absent Bob" would make Bob a witness to the room's physical events). Each physical-cast member is **present from the scene start** unless an explicit `enter` gives a later start; a `leave` removes them until a subsequent `enter`. The **actor and named participants of a physical/`see`/`open` event are present at that event** regardless of the timeline (you cannot act on a thing while absent). Result: a per-cognizer presence interval set.

**Per-kind perception rules (decision 5).** For each state event E (theme T, position k, state `(dim, value)`):

| Event kind (predicate) | Who perceives E | State learned |
|---|---|---|
| physical (`put`/`move`/`take`/`give`/`remove`/`transfer`/`place`) | cognizers **present** at position k | `(location, E.location)` |
| `tell`/`inform` | the **recipient** (participants minus teller, or explicit recipient) — presence not required | `(dim, value)` conveyed by the tell (§3.4) |
| `see`/`look` (closed container) | the **observer(s)** present | `(content, apparent_value)` — the label/appearance (§3.4) |
| `open`/`reveal` | cognizers **present** | `(content, actual_value)` |

For each (cognizer, perceived E), the reconstructor records into the frontier that the cognizer perceived E's engram (so `visible_engrams_at` and `does_X_know` see it), **plus** an **append-only** perception-state row `(cognizer, theme, state_dim, state_value, observed_at, position, source_event_id)` — one row per perceived state-event (the per-cognizer last-known-state substrate the query reads; append-only so `as_of`-in-the-past is answerable, §3.6). The time key is **`observed_at`** (ingest time, always present and the global-order key), not A's nullable `event_time` (fixes N3). Writes are **idempotent** keyed by `(cognizer, source_event_id)` so re-running over the full history is safe.

**Second-order via perception intersection (fixes S3 + N5).** No separate co-presence storage is needed. In the single-scene model, two cognizers both present at E are mutually aware of each other's perception, so **`observer`'s model of `x`** = the events in `perception_state` that **both `observer` and `x` perceived** (their intersection for theme T). If `x` left before a later event, that event is absent from `x`'s perceived set and so drops out of the intersection — `observer` correctly models `x` as not knowing it. The `observer` path of `what_does_X_think` (§3.3) computes this intersection at query time; nothing extra is materialised. Deeper nesting (≥3rd order) is deferred (§4.1).

### 3.2 `KnowledgeFrontier` materialisation (reuse — decision 1)

B feeds the existing per-cognizer ledger rather than a parallel store. Perception of an event is recorded through the frontier's append-only `cognizer_presence_log` / `cognizer_frontier_facts` (B reuses `record_presence_from_statement` and adds, if needed, a thin record path for the per-`(cognizer, theme, dim)` last-known value — see §3.6 for where the value lives). `perceived_by_json` is **never** touched (immutable; it carries the statement's own `self` perspective). **B's frontier writes do not pass through the statement bus** (no new `statement_written` events), so A's exclusion of OCCURRED events from belief-tracker / `second_order` auto-nesting / conflict arbitration is unaffected.

### 3.3 `what_does_X_think` (C++, new — the 8th mentalizing primitive, decision 2)

`include/starling/tom/mentalizing.hpp` + `src/tom/mentalizing_think.cpp`, namespace `tom::mentalizing`:

```cpp
struct StateBelief {
  bool has_belief;            // false → X never perceived any state-event for T (fixes S7)
  std::string state_dim;      // "location" | "content"
  std::string state_value;    // e.g. "basket"; empty when !has_belief
  std::string source_event_id;// the event X last perceived for T
  bool is_stale;              // state_value != global latest actual state
};

StateBelief what_does_X_think(StorageAdapter&, KnowledgeFrontier&,
                              const std::string& x, const std::string& theme,
                              const std::string& tenant, const std::string& as_of,
                              const std::string& observer = "");  // observer="" → first-order
```

Implementation: take the **max-position state-event for theme T that X perceived** → its `(dim, value)`. The **primary read** is the append-only `perception_state` (§3.6) via the `StorageAdapter` — the highest-`position` row with `observed_at ≤ as_of` per `(cognizer, theme, dim)`. The `frontier` parameter (matching the existing `does_X_know(adapter, frontier, …)` signature) serves the `does_X_know` access checks, and lets the implementation read from `cognizer_frontier_facts` instead should the plan home `perception_state` there (§3.6) — the signature accommodates both storage choices. Compare to the **global latest actual state** (`latest_event_location` for the location dim; the latest `open`/`reveal`/asserted-actual for content) → `is_stale`. If X perceived nothing for T → `has_belief=false` (never crash, never fall back to ground truth). The `state_dim` is **inferred from T's perceived events** (a ToMBench theme is location- or content-typed); a theme carrying both dimensions at once is out of scope (fixes N2). When `observer` is set, restrict the candidate events to the **intersection** of `observer`'s and `x`'s perceived events for T (single-scene co-presence ⟹ `observer` knows `x` perceived them; §3.1) → **second-order** "what does `observer` think `x` thinks". Bound in `bind_08_tom.cpp` + re-exported in `python/starling/tom/__init__.py`, matching the existing primitive pattern.

**Relation to existing primitives.** This is a distinct path from `what_does_X_think_Y_believes` (which recurses over **explicit nested belief statements**). B's false belief is **derived from perception**, computed on demand; the two coexist.

### 3.4 State dimensions: location vs content (fixes S4/S5)

- **Location** (`state_dim="location"`): the value is A's `episodic_events.location` (theme's resulting place). No new representation.
- **Content** (`state_dim="content"`, unexpected-contents): a theme (the container) has two perceptible states — **apparent** (from a closed container's label/appearance, captured by a `see`/`look` event) and **actual** (from an `open`/`reveal`, or a narrative "really contains X" assertion). The episodic extractor MUST emit, for a `see` of a labelled closed container, the **apparent** content as the event's value; and for an `open`/`reveal`, the **actual** content. Ground truth = the latest actual; `is_stale` (= false belief) holds when an observer's last-perceived apparent value ≠ actual. This is the **highest extraction risk** channel and is sequenced last (§7).
- **Told content** (`tell`/`inform`): the event conveys a state `(dim, value)` about a theme (e.g. `theme=ball, (location, box)`). The **recipient** is the named participant(s) other than the teller (or an explicit `recipient` the prompt emits). Truthful or false tells are handled uniformly — the recipient's last-perceived state becomes the told value; whether that equals ground truth determines `is_stale`.

### 3.5 Episodic vocabulary extension (B additive)

Extend `kActionPredicates` (`predicate_registry.hpp`) additively with the informational verbs **`tell`, `inform`, `see`, `look`** (`open`/`close` already present). Teach `python/starling/extractor/episodic_prompt.py` to emit:
- `tell`/`inform` events with the **recipient** and the conveyed **state** (`theme` + value);
- `see`/`look` events over a **closed labelled container** carrying the **apparent** content;
- `open`/`reveal` events carrying the **actual** content.
This is purely additive to A's extractor (A's spec already anticipated "extensible to arbitrary actions"); the validator's OCCURRED free-form acceptance (A §3.2) already admits these.

### 3.6 Where the per-cognizer last-known value lives (fixes S8 — do not modify A's table)

B does **not** alter A's `episodic_events` (A's `EpisodicEventStore` is its single owner). The per-cognizer perceived states are carried in **B-owned, append-only storage**: a B-owned companion table `perception_state` with one row per perceived state-event — `(tenant, cognizer, theme, state_dim, state_value, observed_at, position, source_event_id)`. The time key is **`observed_at`** (ingest time, always present; A's `event_time` is nullable — N3). Append-only makes `as_of` history queryable (pick the highest-`position` row with `observed_at ≤ as_of` per `(cognizer, theme, state_dim)`) and makes writes idempotent on `(cognizer, source_event_id)`. The reconstructor is its single writer; `what_does_X_think` is its reader. (Equivalently the columns could extend `cognizer_frontier_facts`; the exact home is a plan-level decision.) The invariant: **A's schema is untouched** and B owns its perception storage, following the migrations auto-register pattern (`migrations/NNNN_*.sql`, CMake GLOB).

## 4. Components & boundaries

- **`PerceptionReconstructor`** — owns presence reconstruction + perception-rule application + frontier/perception-state writes. Pure C++. Invoked after the dual-pass `remember` episodic pass (Python `_memory_core.py` forwards the call; **no core logic in Python**), inside the write transaction using a **SAVEPOINT** (best-effort: a reconstruction failure degrades gracefully and never rolls back the events — §6).
- **`what_does_X_think`** — read-only query primitive; first- and second-order (via `observer`).
- **`KnowledgeFrontier` / `does_X_know`** — reused; B's materialisation makes `does_X_know` event-aware. **Caveat (fixes S6):** `does_X_know`'s Step-2 path keys on `evidence_json` engram-refs; making it fire for events requires the event statements' engram-refs to be the ones B records as visible. B's **primary** query is `what_does_X_think`; the `does_X_know` reuse for the information-access subset is a **secondary integration that is verified on its own**, not assumed free.
- **A's `EpisodicEventStore`** — reused read-only for state values + ground truth.

### 4.1 Order of mind supported

- **1st order** — "what does X think" — core (§3.3).
- **2nd order** — "what does X think Y thinks" — via **perception-set intersection** (§3.1): `observer`'s model of `x` is the events both perceived, covering the canonical "both were in the room, then one left" case.
- **≥3rd order** — deferred. (Explicit *stated* nested beliefs of any order remain answerable through the existing `what_does_X_think_Y_believes`; only *perception-derived* deep nesting is out of scope.)

## 5. Data flow & the single-scene assumption (fixes S10)

```
narrative → remember()
   ├─ claim Extractor → belief/relation statements        (existing)
   ├─ EpisodicExtractor → OCCURRED events + episodic_events (A)
   └─ PerceptionReconstructor (B):
        scan ALL OCCURRED events for the tenant, ordered by (observed_at, seq)
        → presence timeline (enter/leave)
        → per-kind perception rules → frontier + perception_state   (idempotent)
        (second-order is derived at query time by perception-set intersection, §3.1)
query time:
   what_does_X_think(x, theme[, observer])  → StateBelief (possibly stale / unknown)
   does_X_know(x, factkey)                  → KnowsResult (info-access, secondary)
```

**Scene = the tenant, in a single-scene-per-tenant model.** All cognizers in a tenant share one accumulating scene; `enter`/`leave` move them in/out of it. This holds for ToMBench (each item is an isolated tenant/memory) and for a single focused interaction. Two limits are deferred: (a) **multiple distinct scenes within one tenant** (unrelated narratives whose casts should not mix — needs a scene/session id A does not provide); (b) **per-room co-location** within a scene (a cognizer in room A unaffected by room B — the decision-3 "by-location" variant). Both need scene modelling A does not supply and are out of scope.

## 6. Error handling

- `PerceptionReconstructor` failure (no events, malformed data) **degrades gracefully**: `remember` never fails because reconstruction returned nothing; frontier/perception-state writes are **best-effort within the write SAVEPOINT** (a failed perception write must not roll back the events or claims).
- **No enter/leave in a narrative** → everyone in the cast is present throughout → "everyone perceived everything" → no false belief (true belief); `what_does_X_think` still answers.
- **X perceived nothing for T** → `has_belief=false` (§3.3), not a crash and not ground truth.
- Theme identity across events relies on the existing `canonical_object_hash`.

## 7. Implementation phasing (risk-ordered, from self-review)

Each phase is independently green and testable (TDD). Ordered so the canonical false belief ships first and the highest-risk channels are isolated last.

1. **Core first-order:** scene-global presence reconstruction (S1 scene-scope + S2 global order) → frontier/perception-state materialisation → `what_does_X_think` (location) + `has_belief` unknown handling (S7). **Sally-Anne passes deterministically.**
2. **Told channel** (`tell`/`inform`, recipient + conveyed state — S5).
3. **Second-order co-presence** (`observer` param — S3).
4. **Unexpected contents** (apparent vs actual, `see`/`open` — S4; highest extraction risk).
5. **`does_X_know` info-access integration** (S6) + **three-track eval** (§8).

## 8. Testing (TDD, three tracks — decision 6)

1. **Deterministic kernel** (C++ ctest + pytest, every phase, no LLM): presence timeline (Sally `leave` ⟹ absent from `seq3`); per-kind perception rules (`tell` → recipient; `see` → apparent; `open` → actual); `what_does_X_think(Sally, ball) = basket` + `is_stale=true`; `(Anne, ball) = box`; `has_belief=false` for an outsider; second-order `what_does_X_think(Sally, ball, observer=Anne)`; `does_X_know` sees events.
2. **Gated real-LLM e2e** (`STARLING_RUN_LLM_E2E`, like A): `remember("Sally puts her ball in the basket and leaves; Anne moves it to the box")` → A extracts events → B reconstructs → `what_does_X_think(Sally, ball) = basket`, `(Anne, ball) = box`.
3. **ToMBench subset** end-to-end, scored, mirroring the P3.a2 three-track report: the `False Belief Task.jsonl` file (unexpected-transfer false belief) plus ToMBench items whose ATOMS ability is **Knowledge** (perception→knowledge access). Real-model extraction → A events → B perception → `what_does_X_think` scored against gold. Does **not** claim coverage of all ToMBench tasks or all Knowledge items — only the perception-derived subset A+B enable; the harness pins the exact files/ability tag (cf. the P3.a2 `eval_tom_bench.py` ability filters).

**Regression:** ctest 623 / pytest 619 stay green. B is additive (new reconstructor + new primitive + additive vocab + B-owned storage); it does not touch A's OCCURRED exclusion guards, the six-state machine, conflict arbitration, holder isolation, or belief / multi-order-ToM pins.

## 9. Constraints

Core logic is **C++** (`PerceptionReconstructor` in `src/cognizer/`, `what_does_X_think` in `src/tom/`); Python is **only** the episodic-prompt extension and binding/adapter forwarding (repo CLAUDE.md boundary — would another binding language need to re-implement this? then it is C++). New storage via **migration** (auto-register GLOB pattern, single-owner store). Subscriber/handler/reconstructor writes use **SAVEPOINT**, never `BEGIN IMMEDIATE`. **`perceived_by_json` is immutable** — never UPDATE in place; B uses the append-only frontier instead. **Do not modify A's `episodic_events` / `EpisodicEventStore`** (S8). Reuse `KnowledgeFrontier` / `does_X_know` / the mentalizing-primitive pattern / `EpisodicEventStore`; do not start a parallel model. Do not break A / belief / multi-order-ToM / six-state / conflict pins. TDD; explicit-path `git add` (never `.` / `-A`); no `--no-verify` / `--amend`; rebuild editable `_core` (`--python-editable`) after C++/binding changes; build from repo root `/Users/jaredguo-mini/develop/memory/starling`, ctest via `.venv/bin/ctest --test-dir build`.
