#!/usr/bin/env python3
"""Seed the Starling dashboard demo END-TO-END through the real write pipeline.

Unlike a raw-INSERT seeder, every statement flows through `remember()` (extraction
→ validation → write → outbox → projection), so the dashboard shows data the
system actually PRODUCED, not data hand-painted into tables:

  - statements        — remember(), attributed to a holder
  - cognizers         — auto-created by holder/subject resolution
  - embeddings        — the engine tick (deterministic stub embedder)
  - supersede edges   — conflict_probe handles a same-claim contradiction
                        ("X" then "not X") as a belief CORRECTION (supersede),
                        not a standing CONFLICTS_WITH. So the Conflicts panel
                        stays empty here: a true coexisting CONFLICTS_WITH needs
                        same (subject,predicate) + overlapping intervals +
                        opposite polarity that does NOT collapse to one row, a
                        pattern these simple utterances don't hit. Honest gap;
                        left to a follow-up rather than raw-seeding an edge.
  - NORM gists        — formed by run_sleep over the settled (consolidated)
                        beliefs (>=3 distinct holders sharing predicate+object)
  - commitments       — the CommitmentEngine lifecycle (six states)
  - relations         — CognizerHub.upsert_relation (the social-graph API)

Deterministic FakeLLMAdapter for extraction + consolidation — no network, no API
key, repeatable. The dashboard server MUST be stopped while this runs (it holds the
single writer).

Usage:
    .venv/bin/python scripts/seed_demo.py            # add to ~/.starling/dashboard.db
    .venv/bin/python scripts/seed_demo.py --reset    # wipe this tenant first
    .venv/bin/python scripts/seed_demo.py --db /path/to.db --tenant default
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path

from starling import _core
from starling import runtime as rt
from starling.dashboard import DashboardConfig
from starling.dashboard.engine import DashboardEngine

NOW = "2026-06-27T12:00:00Z"
kCommitDeadline = "2026-07-15T17:00:00Z"   # future → active commitments aren't auto-broken

# ── narrative (the Sam engineering-team cast) ────────────────────────────────
# Each belief is phrased as an utterance the holder would say; `subject` differs
# per holder so distinct-holder beliefs don't dedup to one row. holder='self' is
# the agent (Sam). Modalities: BELIEVES / KNOWS. nesting_depth>0 = theory-of-mind.
BELIEFS = [
    # (holder, subject, predicate, object, perspective, modality, nesting)
    ("self",  "self",  "responsible_for", "the authentication service", "FIRST_PERSON", "BELIEVES", 0),
    ("self",  "self",  "member_of",       "the Starling engineering team", "FIRST_PERSON", "KNOWS", 0),
    ("self",  "self",  "reports_to",      "Frank",                       "FIRST_PERSON", "KNOWS", 0),
    ("self",  "Frank", "trusts",          "Bob to lead the caching work", "FIRST_PERSON", "BELIEVES", 1),
    ("Alice", "Alice", "leads",           "the dashboard redesign",      "FIRST_PERSON", "BELIEVES", 0),
    ("Bob",   "Bob",   "responsible_for", "the billing module",          "FIRST_PERSON", "BELIEVES", 0),
    ("Dana",  "Dana",  "works_on",        "the onboarding flow",         "FIRST_PERSON", "BELIEVES", 0),
    ("Eve",   "Eve",   "responsible_for", "the design system",           "FIRST_PERSON", "BELIEVES", 0),
    ("Grace", "Grace", "responsible_for", "the on-call rotation",        "FIRST_PERSON", "BELIEVES", 0),
]

# NORM consensus clusters → gists. Each: (summary, predicate, object, [holders]).
# >=3 distinct holders sharing (predicate, object); each holder's subject = self,
# so rows don't dedup but share the (predicate, canonical_object_hash) key.
NORMS = [
    ("People on this team value thorough code review.",
     "values", "thorough code review", ["Alice", "Bob", "Carol", "Dana"]),
    ("People here find focused deep-work blocks productive.",
     "finds_productive", "focused deep-work blocks", ["Sam", "Eve", "Frank", "Grace"]),
]

# Contradictions: a belief and its negation on the same claim. conflict_probe
# classifies these as a CORRECTION → emits a `supersedes` edge (the newer revises
# the older), NOT a standing CONFLICTS_WITH. Kept to exercise that real behavior.
# (subject, predicate, object, holder_pos, holder_neg).
CONFLICTS = [
    ("the launch", "should_ship", "on June 20th", "Alice", "Bob"),
    ("the new service", "should_use", "Postgres", "Sam", "Carol"),
]

# Commitments (key, text). The PolicyEngine materializes one ACTIVE commitment per
# commits-modality statement (deadline = observed_at + default window); the seeder
# then transitions review→BROKEN, status→FULFILLED, capacity→WITHDRAWN. oauth +
# runbook stay ACTIVE. (RENEGOTIATED is omitted: a renegotiation pairs two commits
# statements, which both auto-materialize — fiddly to drive cleanly here; left as a
# follow-up rather than a non-end-to-end shortcut.)
COMMITMENTS = [
    ("oauth",    "finish the OAuth integration by Friday"),
    ("review",   "review Dana's pull request"),
    ("status",   "send the weekly status report to Alice"),
    ("capacity", "draft a capacity plan for Bob"),
    ("runbook",  "write the migration runbook for Frank"),
]

# Relations (a_name, b_name, affinity, power_asymmetry, fiske). cognizer ids are
# looked up by canonical_name after the beliefs create them.
RELATIONS = [
    ("Sam", "Alice", 0.85, 0.10),
    ("Sam", "Bob",   0.70, 0.00),
    ("Sam", "Frank", 0.60, 0.40),
    ("Sam", "Carol", 0.65, 0.00),
    ("Bob", "Dana",  0.60, 0.40),
    ("Alice", "Frank", 0.70, 0.20),
]


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed the dashboard demo end-to-end via remember().")
    ap.add_argument("--db", default=os.path.expanduser("~/.starling/dashboard.db"))
    ap.add_argument("--tenant", default="default")
    ap.add_argument("--reset", action="store_true",
                    help="Drop the DB file before seeding (fresh schema, clean slate).")
    args = ap.parse_args()
    db, tenant = args.db, args.tenant

    rt.relax_preflight_for_embedded()
    if args.reset:
        # Cleanest reset: drop the DB (+ WAL/SHM sidecars) so seeding starts from a
        # fresh schema with NO residual global state. A tenant-only row-wipe leaves
        # the outbox-sequence counter, policy/projection checkpoints and prior
        # bus_events behind, which made a re-seed's remember() dedup/skip and return
        # empty statement_ids. Fresh file == the repeatable, deterministic seed.
        for suffix in ("", "-wal", "-shm"):
            Path(db + suffix).unlink(missing_ok=True)
    # Ensure the schema exists before opening the engine writer.
    boot = rt._build_local_store_sqlite_runtime(Path(db))
    boot.start()
    del boot

    cfg = DashboardConfig(db_path=db, token="", tenant=tenant)
    eng = DashboardEngine(cfg)
    extractor = _core.FakeLLMAdapter()
    eng.llm = extractor
    cons = _core.FakeLLMAdapter()
    eng._core.consolidation_llm = cons

    def remember(holder, subject, predicate, obj, *, polarity="POS",
                 modality="BELIEVES", perspective="FIRST_PERSON", nesting=0):
        extractor.set_default_response(json.dumps([{
            "holder": holder, "holder_perspective": perspective, "subject": subject,
            "predicate": predicate, "object": obj, "modality": modality,
            "polarity": polarity, "nesting_depth": nesting}]), True, "")
        text = f"{subject} {predicate} {obj}".replace("self", holder)
        return eng.remember(text, holder=holder, now=NOW)

    # ── beliefs (+ auto cognizers) ──
    for holder, subject, predicate, obj, persp, modality, nesting in BELIEFS:
        remember(holder, subject, predicate, obj, perspective=persp,
                 modality=modality, nesting=nesting)

    # ── conflicts: opposite-polarity pairs on the same (subject, predicate) ──
    for subject, predicate, obj, holder_pos, holder_neg in CONFLICTS:
        remember(holder_pos, subject, predicate, obj, polarity="POS")
        remember(holder_neg, subject, predicate, obj, polarity="NEG")

    # ── commitments: remember the commits-modality belief, then materialize it
    # with the CommitmentEngine + apply the terminal transition. (The PolicyEngine
    # does not auto-materialize from the pipeline here, so create_from_statement is
    # the seeding path — same as the engine's own commitment API; not a raw write.)
    # NOTE: a renegotiation pairs two commits statements and is omitted — it was the
    # one shape that left a duplicate-event state breaking the next tick; ACTIVE/
    # BROKEN/FULFILLED/WITHDRAWN cover the panel cleanly.
    ce = eng._core.commitment_engine
    for key, text in COMMITMENTS:
        res = remember("self", "self", "owes", text, modality="COMMITS")
        sid = res["statement_ids"][0]
        ce.create_from_statement(sid, tenant, kCommitDeadline, NOW)   # → ACTIVE
        if key == "review":
            ce.on_deadline_expired(sid, tenant, NOW)                  # → BROKEN
        elif key == "status":
            ce.fulfill(sid, tenant, NOW)                              # → FULFILLED
        elif key == "capacity":
            ce.withdraw(sid, tenant, NOW)                             # → WITHDRAWN
        # oauth + runbook stay ACTIVE

    # ── NORM gists: per cluster, set the summary, remember the members, sleep ──
    # Interleaved so each gist gets its own LLM summary (one run_sleep per cluster;
    # idempotency skips already-gisted keys). entailed:true passes the gate.
    for summary, predicate, obj, holders in NORMS:
        cons.set_default_response(
            json.dumps({"confidence": 0.82, "summary": summary, "entailed": True}), True, "")
        for holder in holders:
            remember(holder, holder, predicate, obj)
        eng.run_replay("sleep", now=NOW)

    # ── embeddings + projections drain ──
    for _ in range(60):
        if eng.tick(NOW)["dispatched"] == 0 and eng.tick(NOW)["embedded"] == 0:
            break

    # ── relations via the CognizerHub API (name → id lookup) ──
    hub = _core.CognizerHub(eng._core.rt.adapter)
    name_to_id = {}
    probe = sqlite3.connect(db)
    for cid, name in probe.execute("SELECT id, canonical_name FROM cognizers WHERE tenant_id=?", (tenant,)):
        name_to_id[name] = cid
    probe.close()
    fiske = {"communal": 0.6, "authority": 0.2, "equality": 0.2}  # must sum to 1.0
    rel_done = 0
    for a_name, b_name, affinity, power in RELATIONS:
        a_id, b_id = name_to_id.get(a_name), name_to_id.get(b_name)
        if a_id and b_id:
            hub.upsert_relation(a_id, b_id, tenant, fiske, affinity, power)
            rel_done += 1

    del eng

    # ── summary ──
    conn = sqlite3.connect(db)
    def n(sql, *p):
        return conn.execute(sql, p).fetchone()[0]
    print("seeded demo END-TO-END (via remember/run_sleep/conflict_probe/engine):")
    print(f"  statements:   {n('SELECT COUNT(*) FROM statements WHERE tenant_id=?', tenant)}")
    print(f"  cognizers:    {n('SELECT COUNT(*) FROM cognizers WHERE tenant_id=?', tenant)}"
          f"  relations: {n('SELECT COUNT(*) FROM cognizer_relations WHERE tenant_id=?', tenant)} (api: {rel_done})")
    print(f"  gists:        {n('SELECT COUNT(*) FROM statements WHERE tenant_id=? AND provenance=?', tenant, 'consolidation_abstract')}"
          f"  consolidated: {n('SELECT COUNT(*) FROM statements WHERE tenant_id=? AND consolidation_state=?', tenant, 'consolidated')}")
    edges = dict(conn.execute("SELECT edge_kind,COUNT(*) FROM statement_edges WHERE tenant_id=? GROUP BY edge_kind", (tenant,)).fetchall())
    print(f"  edges:        {edges or '{}'}  (CONFLICTS_WITH auto-forms only on a coexisting opposite-polarity overlap; same-claim contradictions supersede instead)")
    by_state = dict(conn.execute("SELECT state,COUNT(*) FROM commitments WHERE tenant_id=? GROUP BY state", (tenant,)).fetchall())
    print(f"  commitments:  {n('SELECT COUNT(*) FROM commitments WHERE tenant_id=?', tenant)}  by state: {by_state}")
    print(f"  embedded:     {n('SELECT COUNT(*) FROM statement_vectors WHERE tenant_id=?', tenant)}")
    print(f"  replay batches: {n('SELECT COUNT(*) FROM replay_ledger')}")
    conn.close()


if __name__ == "__main__":
    main()
