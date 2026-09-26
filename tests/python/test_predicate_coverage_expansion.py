"""R2 结构化谓词覆盖扩展的 binding 边界测试。"""

import json

from starling import _core
from starling.extractor.config import ExtractionConfig


def test_binding_exposes_native_v3_catalog_without_python_reimplementation():
    catalog = _core.claim_predicate_catalog()
    names = {spec.name for spec in catalog.predicates}
    expected = {
        "prefers",
        "promises",
        "doubts",
        "believes",
        "responsible_for",
        "requires",
        "forbids",
    }
    assert catalog.version == "claim-predicate-v3"
    assert expected <= names
    payload = json.loads(_core.claim_predicate_catalog_json())
    assert payload["version"] == catalog.version
    assert {entry["name"] for entry in payload["predicates"]} == names
    assert _core.canonical_claim_predicate("wants") == "prefers"
    assert _core.canonical_claim_predicate("commits_to") == "promises"
    assert _core.canonical_claim_predicate("owns_area") == "responsible_for"


def test_python_config_keeps_structured_contract_opt_in():
    config = ExtractionConfig()
    assert config.semantic_claim_contract is False
    assert config.claim_allow_code_fence is False
    assert config.preserve_text_objects is False


def test_structured_contract_uses_native_json_object_output_mode():
    config = ExtractionConfig(
        semantic_claim_contract=True,
        preserve_text_objects=True,
        claim_allow_code_fence=True,
        claim_output_mode="json_object",
    )
    policy = config.to_native_policy()
    assert config.claim_output_mode == "json_object"
    assert policy.claim_output_mode == _core.OutputMode.JsonObject
