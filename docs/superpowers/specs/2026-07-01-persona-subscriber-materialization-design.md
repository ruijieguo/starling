# PersonaSubscriber — Persona Materialization Wiring — Design

**Date:** 2026-07-01
**Status:** design approved (brainstorming); pending writing-plans → /plan-eng-review → subagent-driven
**Slice:** E in the queue E→D→F→A (persona materialization live-wiring)

## Why this slice

`PersonaContainer::rebuild` (materializes a holder's persona container from anchor
statements) has **no live production caller** — invoked only in
`tests/python/test_m0_8_bindings.py`. The only live reader,
`src/hippocampus/working_set.cpp:103` (`PersonaContainer(adapter).read(...)`),
therefore reads a persona that is **never materialized in production**, so the
Working Set's `## About me` block is always empty.

**Premise (confirmed by scoping): an intentional defer of a real feature, not a
bug.** The spec (`docs/design/subsystems_design/07_neocortex.md:119`) designs
persona as the **SLOW channel** — updated per **Replay period**
(`statement.consolidated`), distinct from the fast/Belief channel (per
`Bus.write`). `quickstart.py:8` annotates it: *"not auto-built in P2.e."* The
trigger wiring was deliberately deferred; this slice builds it.

**Honesty check — passes (unlike the abandoned c2.1).** There is a **real
consumer**: once the container is populated, `working_set.read()` renders the
`## About me` block into the recall context injected into converse/query — a
user-visible improvement (the agent's self-model grounds its responses). This is
not inert theater; it closes a real, consumer-backed gap.

## Decisions (locked in brainstorming)

- **Trigger = `statement.consolidated`** (the spec's slow channel), NOT
  `statement.written` (that would violate the slow-channel design and create a
  per-write stampede). Also consume `statement.superseded` (anchor correction →
  rebuild — CommonGround precedent). This keeps the abandoned c2.1 dimension-CAS
  **correctly deferred** (low rebuild volume; revisit only on measured need).
- **Anchor scope = all consolidated+approved statements about the holder** —
  `subject_id = holder AND consolidation_state = 'consolidated' AND review_status
  = 'approved'`. Classify each: `holder_id == subject_id` → `self_model_anchor`,
  else `profile_anchor`; `predicate → dimension`, `object_value → value`,
  `confidence → confidence`. No persona-predicate allowlist (no spec basis).
- **Persona keying + per-subject rebuild (verified vs `working_set.cpp:103-104`).**
  A persona is keyed by the **`subject_id`** it describes; `PersonaContainer::rebuild`'s
  `holder_id` param semantically receives that `subject_id`. `working_set` reads
  `PersonaContainer.read(tenant_id, p.agent_id)` — i.e. **self's** persona
  (`subject == agent_id`) as the `## About me` block (comment: "self 锚点仲裁结果").
  So PersonaSubscriber rebuilds the persona of **every affected subject** — it
  processes system-level `bus_events` and cannot know which subject is "self"
  (that's a read-side notion of the caller's `agent_id`). Self's persona is the
  one `working_set` reads today (the primary live consumer); other cognizers'
  personas materialize via the same uniform mechanism (latent consumers:
  perspective-taking / "what do I know about X"). **Not inert theater** — the
  primary case has a live reader, and the per-subject generality is the
  mechanism's nature, not separate code.

## Architecture

A new `PersonaSubscriber` (C++), mirroring `src/tom/common_ground_subscriber.cpp`,
registered as **SubscriberPump slot #8**. The subscriber (trigger consumption +
anchor classification + rebuild orchestration) is CORE semantics → C++. Python
only adapts (nothing needed — it runs inside the C++ pump). `working_set.read()`
needs no change (auto-populates once the container exists).

```
statement.consolidated / .superseded (bus_events)
        │  (accumulated since persona_subscriber_checkpoint)
        ▼
PersonaSubscriber::tick_one_batch  (SubscriberPump slot #8, SAVEPOINT-isolated)
        │  dedup affected (tenant, subject_id) holders
        ▼  per holder: query consolidated+approved statements → classify → vector<AnchorStatement>
PersonaContainer::rebuild(conn, tenant, holder, sources, now_iso)   ← existing, unchanged
        │  (whole-row version CAS; ConcurrentRebuildError swallowed, CG precedent)
        ▼
containers row (kind='persona') populated
        ▼
working_set.read() → "## About me" block in the recall context   ← the real consumer
```

## Components

- **Create `include/starling/tom/persona_subscriber.hpp` + `src/tom/persona_subscriber.cpp`:**
  `static int tick_one_batch(SqliteAdapter&, Connection&, std::string_view now_iso, int batch_size = 100)`.
  1. Read `persona_subscriber_checkpoint.last_processed_outbox_sequence`.
  2. Query `bus_events WHERE outbox_sequence > ? AND event_type IN ('statement.consolidated','statement.superseded') ORDER BY outbox_sequence LIMIT ?`.
  3. For each event, resolve the statement's `tenant_id, subject_id`; accumulate a deduped `(tenant, subject_id)` set (subject_id = the persona holder).
  4. Per holder: query all `statements WHERE tenant_id=? AND subject_id=? AND consolidation_state='consolidated' AND review_status='approved'`; classify + build `vector<AnchorStatement>`.
  5. `PersonaContainer(adapter).rebuild(conn, tenant, holder, sources, now_iso)`; swallow `ConcurrentRebuildError` (move on, CG precedent).
  6. Advance the checkpoint to the batch's max `outbox_sequence`.
- **Migration `0030_persona_subscriber_checkpoint.sql`:** singleton table (id=1 CHECK, `last_processed_outbox_sequence INTEGER NOT NULL DEFAULT 0`, `last_updated_at TEXT NOT NULL`), mirroring `0022`.
- **Register in `src/bus/subscriber_pump.cpp`:** slot #8 `run_isolated(conn, "persona", [&]{ PersonaSubscriber::tick_one_batch(adapter, conn, now_iso); })`, after belief_tracker (slot 2 emits `tom_inferred` self-statements) — slot 8 (last) satisfies ordering.

## Error handling

- `ConcurrentRebuildError`: swallowed (subscriber moves on), matching `common_ground_subscriber.cpp`. Single-writer model makes this rare.
- SAVEPOINT isolation (via `run_isolated`): a persona-subscriber failure rolls back its own savepoint without affecting sibling subscribers (the established pump pattern).
- Write-reentrancy: `rebuild` writes to `containers` — this runs inside the post-write pump / subscriber path which already uses SAVEPOINT (not `BEGIN`), so no `BEGIN` nesting (the repo's write-discipline invariant).

## Testing

- **C++ ctest `tests/cpp/test_persona_subscriber.cpp`:** seed consolidated+approved anchor statements (self + profile) → `PersonaSubscriber::tick_one_batch` → assert the persona container materialized with the correct self/profile dimensions; the checkpoint advanced; a `statement.superseded` event re-triggers rebuild; idempotent re-run (no duplicate work / checkpoint doesn't regress).
- **Python full-journey test `tests/python/test_persona_materialization.py` (the real-consumer proof):** `remember` self-facts → `tick` (Replay consolidates → emits `statement.consolidated`) → the pump's PersonaSubscriber materializes the persona → `working_set`/recall shows the populated `## About me` block. This proves the end-to-end consumer benefit (the block goes from empty to populated).

## Verify-items for /plan-eng-review

- Confirm PersonaSubscriber as a pump slot does NOT add a `tick_all` stage, so the P3.c smoke's `"persona" not in report["tick"]["stage_ms_total"]` (`tests/python/test_load_test_p3c_smoke.py`) stays valid (pump slots ≠ the 8 tick_all stages — pin it).
- Confirm `statement.consolidated` / `statement.superseded` are the exact `event_type` strings emitted by `arbitration.cpp` (the scoping cited `arbitration.cpp:207-213,275-281`).
- Confirm the `bus_events` columns used (`event_type`, `outbox_sequence`) and the `statements` columns (`subject_id`, `holder_id`, `consolidation_state`, `review_status`, `predicate`, `object_value`, `confidence`) match the real schema.
- Confirm the SubscriberPump `run_post_write` runs on the live remember path so slot #8 fires (and whether it also runs in `tick_all` — the pump is post-write; the harness's tick-drain does not run the pump, which is why the smoke assertion holds).

## Non-goals (deferred)

- **c2.1 dimension-level Container CAS** — stays deferred. The slow channel keeps rebuild volume low; revisit only if a measured need appears (the P3.c harness, now on main, can measure it). Full rebuild from all sources is used here.
- **Incremental rebuild** — `PersonaContainer::rebuild` takes the full sources list; incremental (delta) rebuild is c2.1 territory.
- **A persona-predicate allowlist** — all consolidated+approved statements feed the persona (per the locked decision).
