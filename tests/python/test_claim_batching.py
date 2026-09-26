"""The Python carrier delegates batch validation and planning to C++."""
import hashlib
import json

import pytest
from starling import _core
from starling.extractor.config import ExtractionConfig


def test_native_batch_policy_and_plan_binding_exist():
    assert hasattr(_core.ValidationPolicy(), "claim_batch_size"), "native batch policy missing"
    assert hasattr(_core, "claim_extraction_batch_plan"), "native batch planner missing"


def test_config_maps_batch_size_and_uses_native_validation():
    assert "claim_batch_size" in ExtractionConfig.__dataclass_fields__
    policy = ExtractionConfig(semantic_claim_contract=True, preserve_text_objects=True,
                              claim_batch_size=8).to_native_policy()
    assert policy.claim_batch_size == 8
    for n in [-1, 33]:
        with pytest.raises(ValueError):
            ExtractionConfig(semantic_claim_contract=True, preserve_text_objects=True,
                             claim_batch_size=n)
    with pytest.raises(ValueError):
        ExtractionConfig(claim_batch_size=1)


def test_planner_preserves_full_utf8_source_and_source_turns():
    assert hasattr(_core, "claim_extraction_batch_plan"), "native batch planner missing"
    policy = _core.ValidationPolicy()
    policy.semantic_claim_contract = True
    policy.preserve_text_objects = True
    policy.claim_batch_size = 1
    policy.claim_protocol_retry_budget = 1
    payload = "Mina: 我很伤心。\n\nMina: I feel calm."
    plan = json.loads(_core.claim_extraction_batch_plan(payload, policy))
    assert plan["source_units"] == json.loads(_core.claim_source_units(payload))
    assert plan["source_payload_hash"] == hashlib.sha256(payload.encode()).hexdigest()
    assert plan["batches"] == [dict(batch_index=0, target_clause_ids=["c0"]),
                                dict(batch_index=1, target_clause_ids=["c1"])]
    assert plan["belief_request_upper_bound"] == 6
    empty = json.loads(_core.claim_extraction_batch_plan("\n", policy))
    assert empty["batches"] == [dict(batch_index=0, target_clause_ids=[])]
    assert empty["belief_request_upper_bound"] == 3


def test_planner_preserves_source_turn_identity_and_crlf_utf8_offsets():
    policy = ExtractionConfig(semantic_claim_contract=True, preserve_text_objects=True,
                              claim_batch_size=1).to_native_policy()
    turns = [dict(speaker="Mina", text="我很伤心。\nAbout leaving.", turn_id="t-a", turn_index=4,
                  session_id="session-a", observed_at="2025-05-05T11:04:00Z"),
             dict(speaker="Mina", text="Now I feel calm.", turn_id="t-b", turn_index=8,
                  session_id="session-b", observed_at="2025-05-06T11:04:00Z")]
    payload = _core.claim_source_turn_payload(json.dumps(turns, ensure_ascii=False)).replace("\n", "\r\n")
    plan = json.loads(_core.claim_extraction_batch_plan(payload, policy))
    units = plan["source_units"]
    assert units == json.loads(_core.claim_source_units(payload))
    assert [u["clause_id"] for u in units] == ["c0", "c1"]
    for unit, turn in zip(units, turns):
        assert unit["turn_id"] == turn["turn_id"]
        assert unit["turn_index"] == turn["turn_index"]
        assert unit["session_id"] == turn["session_id"]
        assert unit["speaker"] == turn["speaker"]
        assert unit["utterance"] == turn["text"]
        assert payload.encode()[unit["byte_start"]:unit["byte_end"]].decode() == unit["text"]
