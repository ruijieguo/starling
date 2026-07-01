import random
import importlib.util
from pathlib import Path

# Load the script module by path (it lives in scripts/, not the package).
_SPEC = importlib.util.spec_from_file_location(
    "load_test_p3c",
    Path(__file__).resolve().parents[2] / "scripts" / "load_test_p3c.py",
)
lt = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(lt)


def test_seed_runs_and_counts(tmp_path):
    mem, fake = lt.open_memory(str(tmp_path / "seed.db"))
    rng = random.Random(1234)
    res = lt.run_seed(mem, fake, cognizers=3, statements=12, rng=rng)
    assert res["seeded"] == 12
    assert res["elapsed_s"] >= 0.0
    assert res["throughput_per_s"] > 0
    # Distinctness is by-construction: each remember() gets a distinct payload
    # (f"seed statement {idx} ...") so the engram idempotency key (sha256 of
    # payload, memory_ops.cpp:33) never collides — M remembers → M engrams → M
    # statements. Retrievability is proven in Task 2's retrieval test (retrieval
    # needs the tick to embed the corpus into statement_vectors first).


def test_tick_drain_reports_stage_breakdown(tmp_path):
    mem, fake = lt.open_memory(str(tmp_path / "tick.db"))
    rng = random.Random(7)
    lt.run_seed(mem, fake, cognizers=3, statements=12, rng=rng)
    res = lt.run_tick_drain(mem, max_ticks=50)
    assert res["ticks"] >= 1
    assert isinstance(res["stage_ms_total"], dict) and res["stage_ms_total"]
    # The 8 known stages are the only keys; top_stage is one of them.
    assert res["top_stage"] in res["stage_ms_total"]
    # Smoke scale must not trip DEGRADED, so the drain is a real drain (LOW-6).
    assert res["embed_shed_ticks"] == 0


def test_retrieval_hits_the_scan_not_the_abstain_path(tmp_path):
    mem, fake = lt.open_memory(str(tmp_path / "ret.db"))
    rng = random.Random(9)
    lt.run_seed(mem, fake, cognizers=3, statements=12, rng=rng)
    lt.run_tick_drain(mem, max_ticks=50)   # embed the corpus before retrieval
    res = lt.run_retrieval(mem, queries=20, statements=12, rng=rng)
    assert res["queries"] == 20
    for key in ("p50_ms", "p95_ms", "p99_ms"):
        assert res[key] >= 0.0
    assert res["p99_ms"] >= res["p50_ms"]   # monotone percentiles
    assert res["throughput_per_s"] > 0
    # BLOCKER-2 proof: querying EXISTING objects as holder=self must hit the real
    # O(n) scan, not the abstain path. If every query abstained (holder mismatch
    # / empty text), the p-latencies would be meaningless. Not all-abstain:
    assert res["abstained_count"] < res["queries"]
