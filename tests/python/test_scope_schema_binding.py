"""Python binding coverage for the native scope-marker wire schema."""

from __future__ import annotations

import json

from starling import _core


def _row(scope_markers: list[str] | None = None) -> dict:
    return {
        "holder": "Mina", "holder_perspective": "FIRST_PERSON", "subject": "Mina",
        "subject_kind": "cognizer", "predicate": "feels", "object": "sad about leaving the team",
        "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0, "confidence": None,
        "evidence": {
            "clause_id": "c0", "actor": "Mina", "attributed_to": None,
            "assertion_scope": "ASSERTED", "scope_markers": ["ASSERTED"] if scope_markers is None else scope_markers,
            "time_text": "", "topic": "leaving the team", "event_time": None,
        },
    }


def _response(row: dict) -> str:
    return json.dumps({"schema_version": 2, "statements": [row]})


def test_scope_marker_schema_is_native_and_enforced_by_native_wire_validator():
    schema = json.loads(_core.structured_output_schema(_core.OutputContractKind.ClaimExtractionV2))
    markers = schema["properties"]["statements"]["items"]["properties"]["evidence"]["properties"]["scope_markers"]
    assert markers["minItems"] == 1
    assert markers["uniqueItems"] is True

    assert _core.structured_output_validation_error(
        _response(_row([])), _core.OutputContractKind.ClaimExtractionV2
    ) == "schema_failure:minItems"
    assert _core.structured_output_validation_error(
        _response(_row(["ASSERTED", "ASSERTED"])), _core.OutputContractKind.ClaimExtractionV2
    ) == "schema_failure:uniqueItems"


def test_scope_marker_wire_schema_keeps_combined_markers_and_empty_statements_legal():
    composite = _row(["CONDITIONAL", "REPORTED", "NEGATED"])
    composite["holder_perspective"] = "QUOTED"
    composite["subject"] = "Jules"
    composite["polarity"] = "NEG"
    composite["evidence"].update(actor="Jules", attributed_to="Mina", assertion_scope="CONDITIONAL")
    assert _core.structured_output_validation_error(
        _response(composite), _core.OutputContractKind.ClaimExtractionV2
    ) == ""
    assert _core.structured_output_validation_error(
        '{"schema_version":2,"statements":[]}', _core.OutputContractKind.ClaimExtractionV2
    ) == ""


def test_primary_scope_membership_remains_a_native_parser_rule():
    row = _row(["REPORTED"])
    raw = _response(row)
    assert _core.structured_output_validation_error(raw, _core.OutputContractKind.ClaimExtractionV2) == ""
    parsed = json.loads(_core.claim_parse_response(raw, "Mina: I am sad about leaving the team.", "Mina"))
    assert parsed["errors"]
    assert parsed["statements"] == []
