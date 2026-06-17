# Episodic Event Memory (sub-project A) — Design

**Date:** 2026-06-17
**Status:** Approved (design); pending implementation plan.
**Context:** First of three sub-projects (A episodic events → B perception/knowledge → C arbitrary content) extending Starling from a conversational social-mind memory into a general open-interaction memory. Driver: an end-to-end ToMBench run revealed Starling's conversational-claim extractor extracts **0** statements from physical-action narratives ("Sally puts her ball in the basket and leaves; Anne moves it to the box"), so most ToMBench tasks (and open-interaction episodic content) cannot be ingested. A makes physical-action narratives ingestible as **episodic events**; B (separate spec) will layer perception→knowledge→stale-belief on top; together they unlock the ToMBench False-Belief and Knowledge tasks end-to-end.

---

## 1. Goal & scope

Make Starling represent, extract, store, and recall **episodic events** — "who did what to what, when, where, with whom present". Scope A to the ToMBench-critical event class first (object/location/state-change actions: put, place, move, take, give, remove, transfer, leave …), extensible to arbitrary actions. A records events only; the per-cognizer knowledge/perspective derivation ("where does B *think* the ball is") is sub-project B.

Non-goals (deferred to B/C): perception/knowledge inference (who witnessed/knows an event), access/visibility, arbitrary unstructured content, semantic vector recall over events (the embedded facade uses a stub embedder).

## 2. Current state (file:line)

- Extractor `python/starling/extractor/prompts.py` is a **conversation** extractor (focal speaker's claims); controlled predicate vocab {responsible_for, knows, prefers, promises, forbids, requires, located_at, member_of, believes, doubts}; no event/action path → physical-action narratives extract nothing (verified, real LLM).
- `Modality` enum `include/starling/schema/statement_enums.hpp:21` = mental-state attitudes only {BELIEVES, KNOWS, ASSUMES, DOUBTS, DESIRES, INTENDS, COMMITS, PREFERS, NORM_OUGHT, NORM_FORBID, RECANTED} — no event modality.
- `statements` table: holder/subject/predicate/object/modality/… + `observed_at` (ingest time); **no `event_time` column**. The design (`docs/design/system_design.md:553,948-1000`) envisions `EpisodicEvent(Statement)` + `event_time`/`perceived_by`/`EpisodicView` but explicitly defers EpisodicEvent's fields to P3 (`:1000` "未落库，排 P3"). Extension-table precedent: commitments (migrations 0018-0020).

## 3. Architecture

An episodic event is a first-class `statements` row tagged `modality=OCCURRED`, plus an `episodic_events` extension row carrying the event-specific fields. Events are Statements (not a separate table) so they flow through the existing write/consolidation/recall pipeline and can be referenced as the object of a perception/belief (which B needs: "X perceived event-E" via `object_kind='statement'`).

### 3.1 Representation (decision A1)

"Sally puts her ball in the basket" →
```
statements: { holder_id=self, holder_perspective=FIRST_PERSON,
              subject_kind=cognizer, subject_id="Sally",   # actor
              predicate="put",                              # action (§3.2)
              object_kind=entity, object_value="ball",      # theme
              modality=OCCURRED, polarity=POS,
              observed_at=<ingest>, provenance=user_input }
episodic_events (extension, keyed by statement id):
            { statement_id, tenant_id,
              seq=<monotonic ordinal within the ingestion — REQUIRED>,  # event order
              event_time=<absolute story time if stated, else NULL>,
              location="basket",        # theme's resulting location/place (nullable)
              participants_json=["Sally"],  # cognizers NAMED in THIS event (raw; B derives presence)
              action_raw="put" }        # surface verb (when predicate canonicalised/free-form)
```
"Anne moves the ball to the box" → another OCCURRED row (subject=Anne, predicate="move", object=ball) + ext {location="box", seq=2, …}. The theme's location over time is its OCCURRED events ordered by `seq` (then `event_time`); A exposes a `latest_event_location(theme)` helper for the ground-truth current state, and B derives the per-cognizer last-known location from which events each cognizer perceived.

`holder=self`: an episodic event is the system's own record of something that happened (not an attitude attributed to a cognizer). `subject`=the actor.

### 3.2 Action vocabulary (decision: curated class + free-form OCCURRED fallback)

Add a curated **action** predicate class to the registry (`include/starling/extractor/predicate_registry.hpp`): put, place, move, take, give, remove, transfer, leave, open, close (the common ToMBench/object-manipulation verbs). The validator: for `modality=OCCURRED` rows, an out-of-set predicate is **accepted as free-form** (NOT downgraded to review_requested) — open-domain actions are kept verbatim; in-set actions are canonical for matching. For non-OCCURRED (belief/relation) rows the existing strict downgrade is unchanged. `action_raw` preserves the surface verb regardless.

### 3.3 Event time & extension schema (migration, commitments-pattern)

New migration adds the `episodic_events` extension table: `statement_id` (PK, FK→statements.id), `tenant_id`, `seq` (INTEGER, monotonic event order within an ingestion — **REQUIRED** so B can order events even when `event_time` is unknown; narrative order suffices for the False-Belief sequence), `event_time` (TEXT ISO8601, nullable), `location` (TEXT, nullable), `participants_json` (TEXT, default '[]'), `action_raw` (TEXT). `event_time` lives in the extension (A scope: only events have it) — no change to the 38-field `statements` table. A `store::EpisodicEventStore` (C++, in `src/store/`, owning this table) is the single writer/reader, mirroring `SqliteStatementStore`/commitments ownership.

### 3.4 OCCURRED modality

Add `OCCURRED` to the `Modality` enum + its serialization (the modality string map in the schema/validator + the Python binding enum). This is an additive enum value; existing rows/tests unaffected.

### 3.5 Extraction (decision E1: separate episodic pass)

Add a dedicated **episodic extraction prompt** (`python/starling/extractor/episodic_prompt.py`, narrative-framed: "Given a passage, extract the physical events…") producing a JSON array of events `{actor, action, theme, location, time, participants[]}`. A C++ `EpisodicExtractor` (mirroring `Extractor`, injected with the prompt) parses + writes OCCURRED statements + episodic_events rows. `remember(text)` runs **both** passes: the existing claim `Extractor` AND the `EpisodicExtractor` (dual-pass), so any input yields both attitudes and events. Each pass is independent; an empty result from either is fine. (Per-input pass-skipping is a future optimization, not in A.)

The episodic prompt MUST: (a) emit **presence-change events (enter/leave** — in the action vocab) as their own OCCURRED rows — a departure is precisely what makes a later event unwitnessed, so it cannot be dropped; (b) assign each event a `seq` in narrative order; (c) set `participants` to the cognizers **named in that event only** — it does NOT compute who-is-present (that reconstruction from the ordered enter/leave sequence is B's job). Theme identity relies on the existing `canonical_object_hash` so "ball" links across its events.

### 3.6 Pipeline integration — events are facts, not contestable beliefs

OCCURRED events participate in **consolidation** (six-state machine) and **recall** like any statement, BUT are **excluded** from the belief-specific machinery:
- `belief_tracker` / `tom::second_order` auto-nesting already only fires for *other-holder* first-hand belief statements; OCCURRED events are `holder=self`, so they are naturally skipped — but add an explicit `modality != OCCURRED` guard to be safe.
- **Conflict arbitration**: two OCCURRED events about the same theme's location at different times are a temporal *sequence*, NOT a conflict. OCCURRED rows must be excluded from `canonical_conflict_key` conflict detection (else "ball put in basket" vs "ball moved to box" would be flagged conflicting). Guard: skip conflict-key assignment/arbitration for `modality=OCCURRED`.
This keeps existing belief/ToM/conflict pins green while letting events store + recall.

## 4. Data flow

narrative text → `remember()` → [claim Extractor → belief/relation statements] + [EpisodicExtractor → OCCURRED statements + episodic_events rows] → consolidation → recall (`query`/`recall` return events; OCCURRED rows carry their extension on read via EpisodicEventStore). B (next spec) reads these events + participants to derive perception→knowledge→per-cognizer state.

## 5. A/B boundary

A delivers: the event representation, the OCCURRED modality, the episodic_events store (incl. `seq` order + `latest_event_location` helper), the episodic extractor, dual-pass remember, and event recall. A records, per event, the `participants` named in it **plus the ordered enter/leave events** — the raw spatial-presence signal. B (separate spec) reconstructs who was *present/perceiving* at each event from that ordered sequence (a departure removes a cognizer from presence, so a later event is unwitnessed by them), then adds perception→knowledge inference, per-cognizer last-known state, and the false-belief query. A must not pre-build B; it only ensures events, `seq` order, named participants, and enter/leave events are represented + retrievable.

## 6. Error handling

EpisodicExtractor failures (bad JSON, LLM error) degrade gracefully — the claim pass still runs; remember never fails because the episodic pass returned nothing. Out-of-set OCCURRED predicates are accepted (not errors). Missing event_time/location are nullable. EpisodicEventStore writes are best-effort within the write SAVEPOINT (a failed extension write must not roll back the statement).

## 7. Testing (TDD)

- C++: `EpisodicEventStore` CRUD; OCCURRED modality round-trips; validator accepts curated actions + free-form OCCURRED predicates, still downgrades out-of-set belief predicates; conflict arbitration skips OCCURRED (two location events on one theme → no conflict flagged); belief_tracker/ToM skips OCCURRED.
- Python e2e: `remember("Sally puts her ball in the basket and leaves; Anne moves it to the box")` → OCCURRED statements for both events with correct actor/action/theme + episodic_events rows (location basket/box, participants); recall returns the events. (Real-LLM gated, like the eval harnesses.)
- Regression: ctest 610 / pytest 615 stay green (additive enum + table + extractor pass; the conflict/ToM guards are the only behavioural touches and are pinned).

## 8. Constraints

Core logic C++ (`src/`, `include/starling/`; EpisodicEventStore in `src/store/`); Python = extractor prompt + binding/adapter forwarding only. New table via migration (commitments-pattern, single-owner store). Subscriber/handler code uses SAVEPOINT. Do not break existing belief/multi-order-ToM/six-state/conflict pins. TDD; explicit-path git add; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; rebuild editable `_core` after C++/binding changes. Reuse the deferred `EpisodicEvent`/`event_time` design intent; do not start a parallel model.
