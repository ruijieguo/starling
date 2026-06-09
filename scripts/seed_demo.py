#!/usr/bin/env python3
"""Seed the Starling dashboard with a rich, coherent demo dataset — offline.

Populates every observability panel (Overview, Statements, Cognizers social
graph, Commitments five-state machine, Conflicts, Queues, Replay, Working Set)
with a small narrative cast so the dashboard looks alive without needing an LLM
or API keys. Deterministic and repeatable.

Single-adapter discipline (mirrors examples/quickstart.py): ONE C++ SqliteAdapter
drives the engine calls; raw sqlite3 seeds commit+close around them. Because of
that, the dashboard server MUST be stopped while this runs (it holds the only
writer). Re-embedding is left to the dashboard's own `tick` (which uses the
configured embedder), so statements land in the embedding backlog until then.

Usage:
    # stop the dashboard first (it is the single writer), then:
    .venv/bin/python scripts/seed_demo.py                 # add to ~/.starling/dashboard.db
    .venv/bin/python scripts/seed_demo.py --reset          # wipe this tenant first
    .venv/bin/python scripts/seed_demo.py --db /path/to.db --tenant default
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import uuid
from pathlib import Path

import starling  # noqa: F401  (import side-effects: _core + runtime)
from starling import _core
from starling import runtime as rt

NOW = "2026-06-09T12:00:00Z"


def nid() -> str:
    return str(uuid.uuid4())


def h64(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ── the cast (cognizers) ──────────────────────────────────────────────────────
#   id, kind, canonical_name
CAST = [
    ("cog-self", "self", "Sam"),
    ("Alice", "human", "Alice"),
    ("Bob", "human", "Bob"),
    ("Carol", "human", "Carol"),
    ("Dana", "human", "Dana"),
    ("Eve", "human", "Eve"),
    ("Frank", "human", "Frank"),
    ("Grace", "human", "Grace"),
    ("acme-corp", "group", "Acme Corp"),
]

#   a_id, b_id, affinity, power_asymmetry
RELATIONS = [
    ("cog-self", "Alice", 0.85, 0.10),
    ("cog-self", "Bob", 0.70, 0.00),
    ("cog-self", "Carol", 0.65, 0.00),
    ("cog-self", "Dana", 0.60, -0.20),
    ("cog-self", "Eve", 0.70, 0.00),
    ("cog-self", "Frank", 0.60, 0.40),
    ("cog-self", "Grace", 0.60, 0.00),
    ("Bob", "Carol", 0.50, 0.30),
    ("Bob", "Dana", 0.60, 0.40),
    ("Alice", "Frank", 0.70, 0.20),
    ("cog-self", "acme-corp", 0.40, -0.10),
]

# ── statements ────────────────────────────────────────────────────────────────
#   key, subject, predicate, object, modality, polarity, perspective, salience, affect, nesting
#   `key` lets later phases reference specific statements (commitments / conflicts).
STATEMENTS = [
    ("s_team",    "Sam",   "member_of",      "Starling engineering team",                 "knows",    "pos", "first_person", 0.5, "{}", 0),
    ("s_auth",    "Sam",   "responsible_for","the authentication service",                "believes", "pos", "first_person", 0.7, "{}", 0),
    ("s_reports", "Sam",   "reports_to",     "Frank",                                     "knows",    "pos", "first_person", 0.4, "{}", 0),
    ("s_alicepm", "Alice", "member_of",      "product management",                        "knows",    "pos", "first_person", 0.4, "{}", 0),
    ("s_alicelead","Alice","leads",          "the dashboard redesign",                    "believes", "pos", "first_person", 0.6, "{}", 0),
    ("s_frank",   "Frank", "manages",        "the platform team",                         "knows",    "pos", "first_person", 0.4, "{}", 0),
    ("s_bobbill", "Bob",   "responsible_for","billing module",                            "believes", "pos", "first_person", 0.6, "{}", 0),
    ("s_bobrate", "Bob",   "responsible_for","rate limiter",                              "believes", "pos", "first_person", 0.5, "{}", 0),
    ("s_carolbill","Carol","responsible_for","billing module",                           "believes", "pos", "hearsay",      0.7, '{"valence":-0.2,"arousal":0.4}', 0),
    ("s_danaonb", "Dana",  "works_on",       "the onboarding flow",                       "believes", "pos", "first_person", 0.4, "{}", 0),
    ("s_danamentee","Dana","mentee_of",      "Bob",                                       "knows",    "pos", "first_person", 0.3, "{}", 0),
    ("s_evedesign","Eve",  "responsible_for","the design system",                         "believes", "pos", "first_person", 0.5, "{}", 0),
    ("s_graceoncall","Grace","responsible_for","the on-call rotation",                    "believes", "pos", "first_person", 0.4, "{}", 0),
    ("s_trust",   "Sam",   "trusts",         "Alice's judgment",                          "believes", "pos", "first_person", 0.6, '{"valence":0.5,"arousal":0.2}', 0),
    ("s_cache",   "Bob",   "believes",       "the caching layer cuts API latency by 40%", "believes", "pos", "inferred",     0.5, "{}", 0),
    ("s_pg",      "Sam",   "prefers",        "Postgres over MySQL for the new service",   "believes", "pos", "first_person", 0.5, "{}", 0),
    ("s_mysql",   "Carol", "prefers",        "MySQL for the billing store",               "believes", "pos", "hearsay",      0.5, "{}", 0),
    ("s_fear",    "Sam",   "fears",          "the database migration could cause downtime","believes","pos", "first_person", 0.8, '{"valence":-0.6,"arousal":0.7}', 0),
    ("s_conf",    "Sam",   "is_confident_about","the auth rewrite now that tests pass",   "believes", "pos", "first_person", 0.6, '{"valence":0.6,"arousal":0.3}', 0),
    ("s_tom",     "Sam",   "believes",       "Frank trusts Bob to lead the caching work", "believes", "pos", "first_person", 0.5, "{}", 1),
    ("s_launch",  "Alice and Sam","agreed",  "the public launch date is June 20th, 2026", "knows",    "pos", "first_person", 0.6, "{}", 0),
    ("s_slip",    "Bob",   "thinks",         "the launch should slip to June 25th",       "believes", "pos", "first_person", 0.5, '{"valence":-0.2,"arousal":0.4}', 0),
    ("s_acme",    "Acme Corp","is",          "an external integration partner",           "knows",    "pos", "first_person", 0.3, "{}", 0),
    ("s_graceRL", "Grace", "responsible_for","rate limiter",                              "believes", "pos", "hearsay",      0.4, "{}", 0),
    # commits-modality statements → commitments (six-lane coverage)
    ("c_oauth",   "Sam",   "owes",           "finish the OAuth integration by Fri June 12th","commits","pos","first_person", 0.7, "{}", 0),
    ("c_dana",    "Sam",   "owes",           "review Dana's pull request by June 8th",    "commits",  "pos", "first_person", 0.5, "{}", 0),
    ("c_status",  "Sam",   "owes",           "the weekly status report to Alice",         "commits",  "pos", "first_person", 0.5, "{}", 0),
    ("c_capacity","Sam",   "owes",           "a capacity plan draft to Bob",              "commits",  "pos", "first_person", 0.4, "{}", 0),
    ("c_migold",  "Sam",   "owes",           "the migration runbook to Frank by June 18th","commits", "pos", "first_person", 0.6, "{}", 0),
    ("c_mignew",  "Sam",   "owes",           "the migration runbook to Frank by June 22nd","commits", "pos", "first_person", 0.6, "{}", 0),
    ("c_created", "Sam",   "owes",           "security audit notes to Grace",             "commits",  "pos", "first_person", 0.4, "{}", 0),
]

#   src_key, dst_key, weight, reason, conflict_key   (edge_kind is always CONFLICTS_WITH)
CONFLICTS = [
    ("s_bobbill",  "s_carolbill", 0.82, "billing ownership reassigned Bob->Carol", "billing:responsible_for"),
    ("s_pg",       "s_mysql",     0.70, "datastore choice Postgres vs MySQL",       "datastore:prefers"),
    ("s_launch",   "s_slip",      0.61, "launch date June 20 vs proposed June 25",  "launch:date"),
    ("s_bobrate",  "s_graceRL",   0.45, "rate limiter ownership Bob vs Grace",      "ratelimiter:responsible_for"),
]


def _reset(conn, tenant):
    tenant_tables = [
        "statements", "cognizers", "cognizer_relations", "cognizer_presence_log",
        "commitments", "commitment_triggers", "statement_edges",
        "reconsolidation_windows", "statement_vectors",
    ]
    for t in tenant_tables:
        try:
            conn.execute(f"DELETE FROM {t} WHERE tenant_id = ?", (tenant,))
        except sqlite3.OperationalError:
            pass
    conn.execute("DELETE FROM replay_ledger")  # no tenant column; demo-only data
    conn.commit()


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed a rich offline demo dataset for the Starling dashboard.")
    ap.add_argument("--db", default=os.path.expanduser("~/.starling/dashboard.db"))
    ap.add_argument("--tenant", default="default")
    ap.add_argument("--reset", action="store_true", help="Wipe this tenant's rows before seeding.")
    args = ap.parse_args()
    DB, TEN = args.db, args.tenant

    # Ensure the schema exists (no-op on an existing dashboard DB).
    rt.relax_preflight_for_embedded()
    boot = rt._build_local_store_sqlite_runtime(Path(DB))
    boot.start()
    del boot  # release the writer before raw seeding

    ids = {}  # statement key -> uuid

    # ── Phase A: raw-seed statements + the social graph + replay history ──
    a = sqlite3.connect(DB)
    a.execute("PRAGMA busy_timeout=30000")
    if args.reset:
        _reset(a, TEN)

    def seed_stmt(key, subj, pred, obj, modality, polarity, perspective, salience, affect, nesting):
        sid = nid()
        ids[key] = sid
        a.execute(
            "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
            "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
            "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
            "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
            "nesting_depth,created_at,updated_at) VALUES(?,?,?,?,'cognizer',?,?,'str',?,?,'v1',?,?,"
            "0.9,?,?,?,0.0,?,'user_input','consolidated','approved',?,?,?)",
            (sid, TEN, "self", perspective, subj, pred, obj, h64(key + obj), modality, polarity,
             NOW, salience, affect, NOW, nesting, NOW, NOW))

    for row in STATEMENTS:
        seed_stmt(*row)

    def cog(cid, kind, name):
        a.execute(
            "INSERT OR REPLACE INTO cognizers(id,tenant_id,kind,canonical_name,canonical_name_normalized,"
            "aliases_json,aliases_normalized_json,external_id,trust_priors_json,permissions_json,"
            "created_at,last_seen_at) VALUES(?,?,?,?,?,'[]','[]',?,'{}','{}',?,?)",
            (cid, TEN, kind, name, name.lower(), "", NOW, NOW))

    for cid, kind, name in CAST:
        cog(cid, kind, name)

    for aid, bid, aff, power in RELATIONS:
        a.execute(
            "INSERT INTO cognizer_relations(id,tenant_id,a_id,b_id,fiske_weights_json,affinity,"
            "trust_json,power_asymmetry,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (nid(), TEN, aid, bid, '{"communal":0.6,"authority":0.2}', aff,
             '{"competence":0.8,"integrity":0.7}', power, NOW, NOW))

    for cid, _, _ in CAST:
        a.execute("INSERT INTO cognizer_presence_log(id,tenant_id,cognizer_id,engram_id,observed_at,channel)"
                  " VALUES(?,?,?,?,?,'dashboard')", (nid(), TEN, cid, nid(), NOW))

    # replay history (Replay panel)
    for batch, mode, n, ops, fin in [
        ("rb-online-1", "online", 3, '{"reinforce":3}',          "2026-06-09T11:00:00Z"),
        ("rb-idle-1",   "idle",   8, '{"reinforce":5,"prune":3}', "2026-06-09T11:30:00Z"),
        ("rb-sleep-1",  "sleep",  12,'{"reconsolidate":12}',      None),
    ]:
        a.execute("INSERT OR REPLACE INTO replay_ledger(replay_batch_id,mode,sampled_count,"
                  "ops_applied_json,started_at,finished_at) VALUES(?,?,?,?,?,?)",
                  (batch, mode, n, ops, NOW, fin))
    a.execute("INSERT OR REPLACE INTO replay_scheduler_state(id,online_trigger_counter,"
              "last_online_run_at,last_idle_run_at,last_sleep_run_at,last_updated_at)"
              " VALUES(1,7,?,?,?,?)", (NOW, NOW, NOW, NOW))
    # a couple open/closed reconsolidation windows
    for skey, status, deadline in [("s_bobbill", "open", "2026-06-12T12:00:00Z"),
                                   ("s_fear", "closed", "2026-06-09T06:00:00Z")]:
        a.execute("INSERT OR REPLACE INTO reconsolidation_windows(stmt_id,tenant_id,opened_at,"
                  "close_deadline,status) VALUES(?,?,?,?,?)", (ids[skey], TEN, NOW, deadline, status))
    a.commit()
    a.close()

    # ── Phase B: C++ engine — commitments (six lanes) + persona + projections ──
    run = rt._build_local_store_sqlite_runtime(Path(DB))
    run.start()
    adapter = run.adapter
    ce = _core.CommitmentEngine(adapter)

    def commit(stmt_key, deadline, created):
        ce.create_from_statement(ids[stmt_key], TEN, deadline, created)

    commit("c_oauth",    "2026-06-12T17:00:00Z", "2026-06-09T09:00:00Z")   # ACTIVE (+ fired trigger below → ⚠ DUE)
    commit("c_dana",     "2026-06-08T17:00:00Z", "2026-06-07T09:00:00Z")
    ce.on_deadline_expired(ids["c_dana"], TEN, NOW)                          # → BROKEN
    commit("c_status",   "2026-06-10T17:00:00Z", "2026-06-09T08:00:00Z")
    ce.fulfill(ids["c_status"], TEN, NOW)                                    # → FULFILLED
    commit("c_capacity", "2026-06-15T17:00:00Z", "2026-06-09T08:00:00Z")
    ce.withdraw(ids["c_capacity"], TEN, NOW)                                 # → WITHDRAWN
    commit("c_migold",   "2026-06-18T17:00:00Z", "2026-06-09T08:00:00Z")
    ce.renegotiate(ids["c_migold"], ids["c_mignew"], TEN, NOW)               # old → RENEGOTIATED, new → ACTIVE

    # persona (Working Set persona section)
    try:
        _core.PersonaContainer(adapter).rebuild(
            TEN, "self",
            [_core.AnchorStatement(stmt_id=ids["s_auth"], anchor_type="self_model_anchor",
                                   dimension="traits", value="concise, security-minded", confidence=0.9),
             _core.AnchorStatement(stmt_id=ids["s_team"], anchor_type="self_model_anchor",
                                   dimension="role", value="backend engineer", confidence=0.9)],
            NOW)
    except Exception as e:
        print("  persona skipped:", e)

    # drain the outbox into the read-model projections
    try:
        pm = _core.ProjectionMaintainer(adapter)
        for _ in range(120):
            if pm.tick_one_batch(NOW).events_processed == 0:
                break
    except Exception as e:
        print("  projection maintainer skipped:", e)

    del ce
    del adapter
    del run  # release the writer before the final raw seeds

    # ── Phase C: raw-seed conflict edges + a fired trigger + a `created` commitment ──
    c = sqlite3.connect(DB)
    c.execute("PRAGMA busy_timeout=30000")
    for src, dst, weight, reason, key in CONFLICTS:
        c.execute(
            "INSERT INTO statement_edges(id,tenant_id,src_id,dst_id,edge_kind,weight,created_at,"
            "metadata_json,canonical_conflict_key) VALUES(?,?,?,?,'CONFLICTS_WITH',?,?,?,?)",
            (nid(), TEN, ids[src], ids[dst], weight, NOW, f'{{"reason":"{reason}"}}', key))
    # OAuth commitment surfaces as ⚠ DUE
    c.execute("INSERT INTO commitment_triggers(id,commitment_stmt_id,tenant_id,kind,spec_json,status,created_at)"
              " VALUES(?,?,?,'time','{}','fired',?)", (nid(), ids["c_oauth"], TEN, NOW))
    # a commitment still in the `created` lane (not yet activated)
    c.execute("INSERT OR REPLACE INTO commitments(tenant_id,stmt_id,state,broken_count,deadline,created_at,updated_at)"
              " VALUES(?,?,'created',0,?,?,?)", (TEN, ids["c_created"], "2026-06-25T17:00:00Z", NOW, NOW))
    c.commit()

    # ── summary ──
    def n(t, w=""):
        return c.execute(f"SELECT COUNT(*) FROM {t} WHERE tenant_id=? {w}", (TEN,)).fetchone()[0]
    by_state = dict(c.execute("SELECT state,COUNT(*) FROM commitments WHERE tenant_id=? GROUP BY state", (TEN,)).fetchall())
    n_conf = n("statement_edges", "AND edge_kind='CONFLICTS_WITH'")
    n_replay = c.execute("SELECT COUNT(*) FROM replay_ledger").fetchone()[0]
    print("seeded demo dataset:")
    print(f"  statements:   {n('statements')}")
    print(f"  cognizers:    {n('cognizers')}  relations: {n('cognizer_relations')}  presence: {n('cognizer_presence_log')}")
    print(f"  commitments:  {n('commitments')}  by state: {by_state}")
    print(f"  conflicts:    {n_conf} CONFLICTS_WITH edges")
    print(f"  replay batches: {n_replay}  reconsolidation windows: {n('reconsolidation_windows')}")
    print("note: statements are unembedded — run the dashboard's tick to embed via the configured embedder.")
    c.close()


if __name__ == "__main__":
    main()
