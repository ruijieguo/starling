"""R4.4 metadata lane contract; RED until the native v6 surface is implemented."""
from __future__ import annotations

from pathlib import Path


def test_r44_strategy_and_metadata_diagnostics_are_native():
    root = Path(__file__).resolve().parents[2]
    runner = (root / "scripts" / "run_socialmem_r44.py").read_text()
    assert "evidence_profile_v6" in runner
    assert "claim_metadata_loaded" not in runner
    assert "claim_rejection_reasons" not in runner


def test_r44_python_does_not_add_a_second_claim_semantic_implementation():
    root = Path(__file__).resolve().parents[2]
    source = (root / "scripts" / "run_socialmem_r44.py").read_text()
    assert "semantic_claim_json" not in source
    assert "claim_metadata_loaded" not in source
