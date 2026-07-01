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
