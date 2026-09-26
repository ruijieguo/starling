"""R4.3 C++ binding contract; kept RED until the native surface exists."""
from __future__ import annotations

import importlib
import json
from pathlib import Path


def _core():
    return importlib.import_module("starling._core")


def _recall():
    return {
        "block": '[SOURCE] {"speaker":"Alice","session_id":"s1","turn_index":1,"observed_at":null} text="I changed my plan"',
        "labels": ["SOURCE"],
        "source_refs": [{"speaker": "Alice", "session_id": "s1", "turn_index": 1, "observed_at": None}],
        "statement_ids": [],
        "source_count": 1,
        "statement_count": 0,
    }


def test_r43_native_compact_prompt_exposes_state_roles():
    core = _core()
    assert hasattr(core, "compact_grounded_memory_answer_prompt")
    prompt = core.compact_grounded_memory_answer_prompt(
        "How did Alice change?", json.dumps(_recall(), ensure_ascii=False)
    )
    for marker in ("early", "trigger", "late", "evidence insufficient"):
        assert marker in prompt


def test_r43_python_does_not_duplicate_semantic_lane_rules():
    root = Path(__file__).resolve().parents[2]
    source = (root / "scripts" / "run_socialmem_r43.py").read_text()
    assert "evidence_profile_v5" in source
    assert "state_chain_missing" not in source
    assert "belief_attribution_missing" not in source
    assert "member_missing" not in source
