# Arbitrary Multi-Order Theory-of-Mind — Design

**Date:** 2026-06-17
**Status:** Approved (design); pending implementation plan.
**Owner ruling (2026-06-17):** Starling structurally represents mental states, so
it MUST support *arbitrary* multi-order nested-belief reasoning ("self believes X
believes Y believes Z believes …"). The current deliberate cap at 3rd-order
(`nesting_depth ≤ 2`, "成人三阶 ToM 容量约束", `09_tom.md:120`) is lifted.

---

## 1. Goal

Make nested-belief **representation, production, and recall** support arbitrary
nesting depth, bounded only by *principled runaway guards* (cycle detection +
configurable soft resource caps), not by a hard semantic order cap. After this
change a caller can store, auto-produce, and fully recall an N-deep belief chain
for any N within the configured resource ceiling.

Non-goal: changing the *first-order* flat-extraction path (LLM still emits
`object_kind='str'`), the six-state consolidation machine, conflict arbitration,
or the Bus event model beyond decoupling one mislabeled field (§4.B).

## 2. Current state — the three coupled caps (file:line)

Depth↔order: `nesting_depth=0` = 1st-order (flat "X believes P"); `=1` = 2nd-order
("self believes X believes P"); `=2` = 3rd-order; etc.

| # | Mechanism | Location | Effect today |
|---|-----------|----------|--------------|
| 1 | Representation hard cap | `src/tom/nesting_depth_writer.cpp:34` `if (result > 2) throw NestingDepthOverflow` (type `include/starling/tom/nesting_depth_writer.hpp:8-14`, msg `"nesting_depth > 2 hard limit (P2.a)"`) | Any write that would land at depth ≥ 3 is rejected, on the universal write path `src/bus/statement_writer.cpp:335`. |
| 2 | Production-gate "chain" cap | `src/tom/second_order.cpp:125` `gate.causation_chain_len = src.nesting_depth` + `src/tom/limiting.cpp:11` `if (in.causation_chain_len >= kChainMax) return false` (`kChainMax = 3`) | The limiter is fed *nesting_depth* as if it were chain length (comment "嵌套层数即本链深度"), so producing from a depth-≥3 source is gated — a second, intentional nesting cap. |
| 3 | Cascade runaway guard | `src/tom/limiting.cpp:10` `if (in.derived_depth >= kDerivedDepthMax) return false` (`kDerivedDepthMax = 3`); `gate.derived_depth = src.derived_depth` (`second_order.cpp:124`) | Bounds the *event-causation* chain when auto-production cascades. Currently never deeply exercised because the auto path skips nested sources (`skip_nested_source`, `second_order.cpp:190`). This is the legitimate runaway guard, aligned to the Bus `CausationOverflow` cap (`include/starling/bus/bus_event.hpp:31`). |

Recall gap: `what_does_X_think_Y_believes` (`src/tom/mentalizing_more.cpp:48-100`)
filters `o.nesting_depth >= 1` and self-JOINs `i.id = o.object_value` exactly
**once** — a depth-2 outer surfaces with its depth-1 inner, but the depth-0
innermost is not recursively unwrapped. META_BELIEF intent
(`src/retrieval/retrieval_planner.cpp:158-161`) adds `AND nesting_depth >= 1` with
no upper bound. Estimator `count_to_depth` (`src/tom/depth_estimator.cpp:54-58`)
saturates at 2.

Caps #1 and #2 are the cognitive cap; #3 + the window rate-limiter
(`rate_limiter::allow_tom_inferred_write`) are the runaway guards. #1 and #2 are
lifted/decoupled; #3 is kept but made configurable.

**No schema migration.** `nesting_depth` is already an unbounded `INTEGER NOT NULL
DEFAULT 0` with no CHECK constraint (`migrations/0001_initial_schema.sql:57`); every
cap is enforced in C++. This change touches zero migrations and needs no data
backfill — existing depth-0/1/2 rows remain valid.

## 3. Architecture overview

Replace the hard order cap with **two invariants enforced at write time** and one
**configurable cascade guard**:

1. **Acyclicity (DAG):** a nested statement's `object_value` ancestor chain must
   not contain the statement itself. Belief nesting forms a DAG.
2. **Soft resource ceiling:** `tom.max_nesting_depth` (default 32) — a runaway
   guard, *not* a semantic order limit. 0/negative ⇒ unbounded (cycle guard still
   applies).
3. **Cascade ceiling:** `tom.max_cascade_depth` (default 8, replaces the hardcoded
   `kDerivedDepthMax = 3`) — bounds a single auto-production *event cascade*; deeper
   chains accrete across ticks/batches, never in one runaway cascade.

Nesting depth (a belief-structure property) and event-causation chain length (an
event-propagation property) become independent dimensions.

## 4. Components

All core logic is C++ (`src/tom/`, `include/starling/tom/`); Python is binding
forwarding only. New bindings that issue recursive SQL release the GIL
(`gil_scoped_release`).

### A. Representation guard — `nesting_depth_writer` (replaces cap #1)

`compute_nesting_depth` keeps returning `parent.nesting_depth + 1` for
`object_kind='statement'`. Replace the `result > 2` throw with:

- **Cycle check (write-time ancestor walk):** before accepting, walk the parent
  chain via `object_value` (each hop loads the parent's `object_kind`/`object_value`);
  if the new statement's own id appears, throw a new `NestingCycle` exception.
  The walk is O(depth) and depth is shallow by construction. (A self-referential
  write — new row pointing at an ancestor — is the only way to form a cycle, since
  inner statements pre-exist; the walk makes the invariant explicit and defensive.)
- **Soft ceiling:** if `max_nesting_depth > 0 && result > max_nesting_depth`, throw
  `NestingDepthOverflow` (kept as the type, message updated to reference the
  configurable ceiling, no longer "hard limit (P2.a)").

`NestingCycle` and the (now soft) `NestingDepthOverflow` are caught on the ToM
auto path the same way other skips are (returned as `out.reason`, never rolling
back the frontier accounting — `maybe_persist_second_order` already wraps in a
SAVEPOINT and swallows to `reason`).

### B. Production-gate decoupling — `second_order.cpp` + `limiting` (cap #2)

The `causation_chain_len = src.nesting_depth` feed (`second_order.cpp:125`) existed
*only* to cap nesting through a misused field (comment "嵌套层数即本链深度"). It is
removed: the ToM production gate no longer feeds nesting_depth into the limiter,
and the `causation_chain_len >= kChainMax` branch is dropped from the ToM gate
(nesting is now governed solely by §4.A's cycle + soft ceiling). The single
cascade guard that remains in the gate is `derived_depth` vs `max_cascade_depth`
(§4.F) — the genuine event-causation runaway guard — so nesting depth and event
chain length are no longer conflated. (`kChainMax` / the Bus `CausationOverflow`
cap on actual causation chains is untouched elsewhere; this change only stops the
ToM path from abusing it as a nesting limiter.)

### C. Recursive recall — `mentalizing_more.cpp` (fills the core gap)

Rewrite `what_does_X_think_Y_believes` to fully unwrap the chain with a
`WITH RECURSIVE` CTE: anchor on the requested holder's `nesting_depth >= 1`
belief about the partner, then recursively join `inner.id = outer.object_value`
down to the depth-0 leaf, returning every level (`level`, `holder_id`,
`subject_id`, `predicate`, `object_kind`, `object_value`). Add a `max_unwrap`
parameter (default = `tom.max_nesting_depth`) so a pathological row cannot drive
an unbounded query. The return type grows from a single `inner` to an ordered
chain; the existing `.inner` accessor is preserved as "the immediate inner" for
backward compatibility, with a new `.chain` exposing all levels.

META_BELIEF intent recall is already depth-agnostic (`>= 1`); no change beyond
benefiting from the richer chain when callers request it.

### D. Auto-production + estimator generalization — `depth_estimator` + `second_order.cpp`

- **Estimator:** `count_to_depth` generalizes from {0,1,2} to an arbitrary-order
  estimate, monotone non-decreasing in the partner's demonstrated nesting (the
  deepest `nesting_depth` the partner authored over the 7-day window, subject to
  the existing per-depth count threshold so a single fluke does not credit an
  order). It preserves today's {0,1,2} outputs for shallow partners and extends
  upward; it may return any non-negative int. The exact monotone formula is fixed
  in the plan. Cache table unchanged (the cached value's domain widens).
- **Auto path (grounded mirroring), NOT estimator-gated:** remove the
  `skip_nested_source` hard skip (`second_order.cpp:190`) and model self's belief
  about a partner's depth-k statement → self depth-(k+1), for any k. This mirrors a
  belief the partner *actually authored*, so the partner has by definition
  demonstrated that order — an estimator gate here would be a tautological no-op for
  observed sources. (The estimator's real job is gating *fabrication* on the
  explicit path, §4.E, where the attributed belief is NOT directly observed.) Auto
  depth is therefore driven by the source's depth — partner nested statements arrive
  via multi-holder / programmatic ingestion — not by cascading: an auto-produced row
  is self-held and the auto path already skips self-held sources
  (`second_order.cpp:193`), so it never re-triggers itself. Bounds: §4.A's soft
  ceiling + cycle guard (representation), the window rate-limiter (thrash), and the
  cascade ceiling (§3.3) as defense-in-depth. The Adaptive-ToM-Order intent
  ("don't over-reason about low-order partners", `09_tom.md:289`) is preserved
  because over-reasoning = fabrication, which stays estimator-gated on the explicit
  path; mirroring an observed belief is never over-reasoning.

### E. Explicit production generalization — `persist_meta_belief` (mechanical)

Replace the `estimate(partner) < 2 → gated_order` gate (`second_order.cpp:213`)
with `estimate(partner) < target_order → gated_order`, and wrap any depth-k source
→ depth-(k+1) (it already requires a nested source). No depth-2 special-casing.

### F. Configuration

Two **configurable** limits (per the owner's 配置 intent), defaulting to
runaway-safe values. Today the related limits are compile-time `constexpr` in
`limiting.hpp` (`kDerivedDepthMax`, `kChainMax`); the plan moves these two to
runtime-config-sourced values (resolving Starling's config path) that fall back to
the defaults below. `0` for `max_nesting_depth` means unbounded (cycle guard still
applies):

| key | default | meaning |
|-----|---------|---------|
| `tom.max_nesting_depth` | 32 | soft ceiling on belief nesting; 0 ⇒ unbounded (cycle guard still applies) |
| `tom.max_cascade_depth` | 8 | ceiling on a single auto-production event cascade (replaces `kDerivedDepthMax = 3`) |

## 5. Data flow — a 4th-order belief, end to end

1. Partner P authors a depth-2 statement (P believes Q believes R) via programmatic
   / multi-agent ingestion. `nesting_depth_writer` accepts it (≤ 32, acyclic).
2. `belief_tracker_tick` observes P's depth-2 `statement.written` and — grounded
   mirroring, no estimator gate — models "self believes P believes [that]" → self
   depth-3 (4th-order), `provenance=tom_inferred`, accepted under the soft ceiling
   (≤ 32) and cycle guard. (Fabricating a belief P did NOT author — e.g. a fifth
   level P never stated — would instead go through the explicit, estimator-gated
   path of §4.E.)
3. `mem.tick()` consolidates it (salience inheritance unchanged).
4. `what_does_X_think_Y_believes(self, P)` returns the full 4-level chain via the
   recursive CTE; META_BELIEF recall surfaces the depth-3 row.

## 6. Error handling

- `NestingCycle` — write rejected; on the ToM auto path returned as
  `reason="skip_cycle"`, never persisted, never an event.
- `NestingDepthOverflow` (soft) — `reason="gated_soft_cap"`.
- Cascade ceiling hit — existing `reason="gated_limiting"`.
- All ToM-path exceptions remain swallowed inside the handler's SAVEPOINT; a ToM
  failure must not roll back the triggering statement's frontier accounting.

## 7. Testing (TDD; red→green per change)

- `tests/cpp/test_nesting_depth_writer.cpp` — REPLACE the depth-3 `NestingDepthOverflow`
  assertions (`:146-190`) with: depth 3/4/5 accepted under default config; soft-cap
  overflow throws when `max_nesting_depth` is set low; **a self-referential write
  throws `NestingCycle`**.
- `tests/cpp/test_tom_second_order.cpp` — estimator returns ≥3 for a partner who
  demonstrated depth-2+; explicit `persist_meta_belief` persists depth-3; auto path
  produces depth-(k+1) gated by estimator; cascade ceiling stops a runaway cascade.
- `tests/cpp/test_depth_estimator*` (or in the above) — `count_to_depth` arbitrary-order
  generalization.
- `tests/cpp/test_mentalizing*` — recursive CTE returns the full N-level chain;
  `max_unwrap` bounds it.
- `tests/python/test_tom2_e2e.py` — extend: seed a 3-deep multi-holder chain →
  `belief_tracker_tick` → `mem.tick()` → recursive recall returns all levels.
- No regression to ctest 589 / pytest 609 beyond the intentionally-changed cap
  assertions; six-state, conflict-arbitration, recalled-idempotency pins intact.

## 8. Spec-doc revision — `docs/design/subsystems_design/09_tom.md`

Revise `:120` ("默认追踪深度 ≤ 2；深度 3 仅显式触发（成人三阶 ToM 容量约束)") and the
field docs at `:194/:273` and Adaptive-ToM-Order `:90-95` to state: arbitrary
nesting depth, bounded by acyclicity + `tom.max_nesting_depth` (soft) +
`tom.max_cascade_depth` (cascade); estimator returns the partner's demonstrated
order (any int); the cap is a runaway guard, not a cognitive-capacity limit.

## 9. Constraints

Core logic C++ only (`src/tom`, `include/starling/tom`); Python binding-forward
only. New/changed bindings issuing recursive SQL use `gil_scoped_release`.
explicit-path `git add`; commit trailer `Co-Authored-By: Claude Opus 4.8 (1M
context) <noreply@anthropic.com>`; no `--no-verify`/`--amend`. Rebuild editable
`_core` after C++/binding changes (`--python-editable`); build from repo root.
Subscriber code uses SAVEPOINT, never BEGIN IMMEDIATE.
