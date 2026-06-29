#!/usr/bin/env python3
"""Commitment-fulfillment eval — offline, deterministic, engine-driven.

Replays each scenario's actions through CommitmentEngine/PolicyEngine and checks
the observed final state matches expected, recording the turn of detection.
Metrics: detection rate (>0.80) + median timeliness (<3 turns). No LLM / no network.
"""
from __future__ import annotations
import argparse, json, sqlite3, sys, tempfile
from pathlib import Path

from starling import _core, runtime

DETECTION_THRESHOLD = 0.80
TIMELINESS_THRESHOLD = 3   # turns (strict <)

_SEED_SQL = (
    "INSERT INTO statements(id,tenant_id,holder_id,holder_perspective,subject_kind,"
    "subject_id,predicate,object_kind,object_value,canonical_object_hash,"
    "canonical_object_hash_version,modality,polarity,confidence,observed_at,salience,"
    "affect_json,activation,last_accessed,provenance,consolidation_state,review_status,"
    "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")

def _seed_commit(db_path: str, stmt_id: str, c: dict) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute(_SEED_SQL, (
            stmt_id, "default", c["holder"], "first_person", "cognizer", c["subject"],
            "owes", "str", c["object"], "a"*64, "v1", "commits", "pos", 0.9, c["observed_at"],
            0.5, "{}", 0.0, c["observed_at"], "user_input", "consolidated", "approved",
            c["observed_at"], c["observed_at"]))
        conn.commit()

def _seed_bare(db_path: str, stmt_id: str, observed_at: str) -> None:
    """Seed a bare COMMITS statement row for a renegotiation target (new stmt)."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute(_SEED_SQL, (
            stmt_id, "default", "alice", "first_person", "cognizer", "bob",
            "owes", "str", "task", "a"*64, "v1", "commits", "pos", 0.9, observed_at,
            0.5, "{}", 0.0, observed_at, "user_input", "consolidated", "approved",
            observed_at, observed_at))
        conn.commit()

def _state(db_path: str, stmt_id: str) -> str:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT state FROM commitments WHERE stmt_id=? AND tenant_id='default'",
                           (stmt_id,)).fetchone()
        return row[0] if row else "ABSENT"

def run_scenario(scn: dict) -> tuple[bool, int]:
    """Return (detected: observed final_state == expected, detect_turn)."""
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "s.db")
        rt = runtime._build_local_store_sqlite_runtime(Path(db)); rt.start()
        c = scn["commit"]; sid = c["stmt_id"]
        _seed_commit(rt.adapter.db_path, sid, c)
        ce = _core.CommitmentEngine(rt.adapter)
        pe = _core.PolicyEngine(rt.adapter)
        ce.create_from_statement(sid, "default", c["deadline"], c["observed_at"])
        want = scn["expected"]["final_state"]
        detect_turn = -1
        for act in scn["actions"]:
            op, now = act["op"], act["now"]
            if op == "tick":          pe.tick(now)
            elif op == "fulfill":     ce.fulfill(sid, "default", now)
            elif op == "withdraw":    ce.withdraw(sid, "default", now)
            elif op == "expire":      ce.on_deadline_expired(sid, "default", now)
            elif op == "renegotiate":
                # Renegotiate the tracked commitment onto a fresh statement: the old
                # (tracked) stmt becomes RENEGOTIATED, a new ACTIVE commitment is
                # created for new_stmt_id (which must exist as a statement row first).
                new_sid = act["new_stmt_id"]
                _seed_bare(rt.adapter.db_path, new_sid, now)
                ce.renegotiate(sid, new_sid, "default", now)
            if detect_turn < 0 and _state(rt.adapter.db_path, sid) == want:
                detect_turn = act["turn"]
        return (_state(rt.adapter.db_path, sid) == want, detect_turn)

def _median(xs: list[int]) -> float:
    if not xs: return 0.0
    s = sorted(xs); n = len(s)
    return float(s[n//2]) if n % 2 else (s[n//2-1]+s[n//2])/2.0

def write_report(path: Path, detection: float, timeliness: float, n: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Commitment Fulfillment Eval Report", "",
             "| metric | value | threshold | verdict |", "|---|---|---|---|",
             f"| detection rate | {detection:.4f} | >{DETECTION_THRESHOLD} | "
             f"{'PASS' if detection > DETECTION_THRESHOLD else '**FAIL**'} |",
             f"| timeliness (median turns) | {timeliness:.2f} | <{TIMELINESS_THRESHOLD} | "
             f"{'PASS' if timeliness < TIMELINESS_THRESHOLD else '**FAIL**'} |",
             f"| scenarios | {n} | | |"]
    path.write_text("\n".join(lines) + "\n")

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Commitment fulfillment eval (offline, engine-driven).")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--report", type=Path, default=Path("build/eval_commitment.md"))
    p.add_argument("--debug", action="store_true",
                   help="print per-scenario expected/observed mismatches to stderr")
    args = p.parse_args(argv)
    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr); return 1
    corpus = [json.loads(l) for l in args.corpus.read_text().splitlines() if l.strip()]
    if not corpus:
        print("ERROR: corpus is empty", file=sys.stderr); return 1
    detected = 0; turns = []
    for scn in corpus:
        ok, t = run_scenario(scn)
        if ok:
            detected += 1
            if scn["expected"]["detect_by_turn"] > 0 and t >= 0:
                turns.append(t)
        elif args.debug:
            print(f"MISMATCH {scn['scenario_id']} [{scn['category']}] "
                  f"want={scn['expected']['final_state']}", file=sys.stderr)
    detection = detected / len(corpus)
    timeliness = _median(turns)
    write_report(args.report, detection, timeliness, len(corpus))
    print(f"Report written to {args.report}", file=sys.stderr)
    ok = detection > DETECTION_THRESHOLD and timeliness < TIMELINESS_THRESHOLD
    if ok:
        print(f"PASS — detection {detection:.4f} > {DETECTION_THRESHOLD}, "
              f"timeliness {timeliness:.2f} < {TIMELINESS_THRESHOLD}")
        return 0
    print(f"BLOCKED — detection {detection:.4f} / timeliness {timeliness:.2f}")
    return 1

if __name__ == "__main__":
    sys.exit(main())
