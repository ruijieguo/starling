"""The approved optional evidence path must be explicit and schema-visible."""
from dataclasses import fields

import pytest

from starling import schema
from starling.extractor.config import ExtractionConfig


def test_claim_policy_is_explicit_and_does_not_change_legacy_defaults():
    config = ExtractionConfig()
    assert hasattr(config, "semantic_claim_contract")
    assert not config.semantic_claim_contract
    assert not config.claim_allow_code_fence
    assert not config.preserve_text_objects
    assert config.claim_protocol_retry_budget == 0


def test_claim_policy_requires_consistent_text_and_attribution():
    with pytest.raises(ValueError, match="preserve_text_objects"):
        ExtractionConfig(semantic_claim_contract=True)
    with pytest.raises(ValueError, match="attribute_first_order"):
        ExtractionConfig(semantic_claim_contract=True, preserve_text_objects=True,
                         attribute_first_order_mental_to_holder=True)


def test_evidence_schema_keeps_scope_combination_and_times_separate():
    assert hasattr(schema, "SemanticClaimEvidence")
    evidence = schema.schema_for(schema.SemanticClaimEvidence)
    assert evidence["properties"]["scope_markers"]["type"] == "array"
    assert "CONDITIONAL" in evidence["properties"]["assertion_scope"]["enum"]
    assert {"source_time", "event_time", "time_text", "source_span", "actor", "attributed_to"} <= set(evidence["properties"])
    assert next(f for f in fields(schema.Statement) if f.name == "semantic_claim_evidence").default is None
    stmt = schema.schema_for(schema.Statement)
    assert "semantic_claim_evidence" not in stmt["required"]


def test_claim_policy_reaches_native_writer_policy():
    from starling._memory_core import _build_policy
    config = ExtractionConfig(semantic_claim_contract=True, preserve_text_objects=True,
                              claim_allow_code_fence=True)
    policy = _build_policy(config)
    assert policy.semantic_claim_contract and policy.claim_allow_code_fence
    assert policy.preserve_text_objects


def test_claim_protocol_retry_budget_is_native_and_bounded():
    config = ExtractionConfig(semantic_claim_contract=True, preserve_text_objects=True,
                              claim_protocol_retry_budget=1)
    policy = config.to_native_policy()
    assert policy.claim_protocol_retry_budget == 1
    with pytest.raises(ValueError, match="claim_protocol_retry_budget"):
        ExtractionConfig(semantic_claim_contract=True, preserve_text_objects=True,
                         claim_protocol_retry_budget=2)
