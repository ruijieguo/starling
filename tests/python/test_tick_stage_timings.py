"""P3.c1 Phase 3b — a real offline tick surfaces per-stage timings (9 stages, L3)."""
from __future__ import annotations

import starling

# Minimal canned extraction (mirrors test_memory_facade.py:CANNED_JSON).
CANNED_JSON = (
    '[{"holder":"alice","holder_perspective":"FIRST_PERSON",'
    '"subject":"cog-bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)

# Keep in lockstep with tick_all's StageTimer labels (L3) + the 3b.3 ctest.
EXPECTED_STAGES = [
    "embed", "policy", "common_ground",
    "replay_oscillation_guard", "replay_ttl_sweep", "replay_idle",
    "persona", "projection", "outbox",
]


def test_tick_returns_ordered_stage_timings(tmp_path):
    llm = starling.make_stub_llm(default_response=CANNED_JSON)
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=llm)
    mem.remember("Bob owns the auth module")

    stats = mem.tick()  # TickStats dataclass; the facade supplies `now`

    timings = stats.stage_timings_ms  # attribute access (L5c) — list of {stage, ms} dicts
    assert [entry["stage"] for entry in timings] == EXPECTED_STAGES
    assert all(isinstance(entry["ms"], int) and entry["ms"] >= 0 for entry in timings)
    mem.close()
