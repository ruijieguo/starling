"""Native contract boundary: strict parsing, byte proof and channel receipts."""
import hashlib
import json

import pytest
from starling import _core


def candidate(**changes):
    row = dict(holder="Mina", holder_perspective="FIRST_PERSON", subject="Mina",
               subject_kind="cognizer", predicate="feels", object="sad about leaving the team",
               modality="BELIEVES", polarity="POS", nesting_depth=0,
               evidence=dict(clause_id="c0", actor="Mina", assertion_scope="ASSERTED",
                             scope_markers=["ASSERTED"], time_text="", event_time=None))
    row.update(changes)
    return row


def parse(rows, source="Mina: I am sad about leaving the team.", **kwargs):
    raw = rows if isinstance(rows, str) else json.dumps(dict(schema_version=2, statements=rows))
    return json.loads(_core.claim_parse_response(raw, source, "Mina", **kwargs))


def test_binding_preserves_canonical_predicate_on_scope_rejection():
    result = parse([candidate(holder="Other", predicate="has")])
    assert result["errors"] == []
    assert result["statements"] == []
    rejection, = result["semantic_rejections"]
    assert rejection["predicate"] == "owns"
    assert rejection["kind"] == "scope_failure"


def test_r1b_binding_loads_state_coverage_and_native_topic_guard():
    prompt = _core.claim_extraction_prompt("Mina: I am cheerful.", "Mina")
    assert "Review every source unit" in prompt
    assert "state or state change" in prompt
    result = parse([candidate(predicate="indifferent_to", object="either way")],
                   "Mina: either way.")
    assert result["errors"] == []
    assert result["statements"] == []
    assert result["semantic_rejections"][0]["kind"] == "scope_failure"


def test_native_policy_and_exact_utf8_units():
    assert hasattr(_core.ValidationPolicy(), "semantic_claim_contract"), "native contract policy missing"
    assert not _core.ValidationPolicy().semantic_claim_contract
    payload = "米娜：如果下雨，我就不去。\n\n米娜：我很伤心。"
    units = json.loads(_core.claim_source_units(payload))
    assert [u["clause_id"] for u in units] == ["c0", "c1"]
    assert units[0]["text"] == "米娜：如果下雨，我就不去。"
    assert units[0]["byte_start"] == 0
    assert units[0]["byte_end"] == len("米娜：如果下雨，我就不去。".encode())
    assert units[1]["byte_start"] == len("米娜：如果下雨，我就不去。\n\n".encode())
    for u in units:
        assert u["payload_hash"] == hashlib.sha256(payload.encode()).hexdigest()
        assert payload.encode()[u["byte_start"]:u["byte_end"]].decode() == u["text"]


def test_v2_preserves_object_and_unknown_event_time():
    parsed = parse([candidate()])
    assert parsed["errors"] == []
    row, = parsed["statements"]
    assert row["object"] == "sad about leaving the team"
    assert row["evidence"]["event_time"] is None
    assert row["evidence"]["source_time"] is None  # populated only from Engram at persist


@pytest.mark.parametrize("mutate", [
    lambda r: r["evidence"].update(clause_id="c999"),
    lambda r: r["evidence"].pop("event_time"),
    lambda r: r["evidence"].update(byte_start=5),
    lambda r: r["evidence"].update(scope_markers=["ASSERTED", "ASSERTED"]),
])
def test_malformed_row_rejects_complete_response(mutate):
    bad = candidate()
    mutate(bad)
    parsed = parse([candidate(), bad])
    assert parsed["errors"]
    assert parsed["statements"] == []


@pytest.mark.parametrize("raw", [
    '{"schema_version":2,"schema_version":2,"statements":[]}',
    '{"schema_version":2,"statements":[]} {}',
    'Here is JSON: {"schema_version":2,"statements":[]}',
    '```json\n{"schema_version":2,"statements":[]}\n``` trailing',
    '[]',
])
def test_envelope_rejects_duplicate_keys_prose_multiple_values_and_legacy(raw):
    assert parse(raw, allow_code_fence=True)["errors"]


def test_fence_requires_explicit_transport_opt_in():
    raw = '```json\n{"schema_version":2,"statements":[]}\n```'
    assert parse(raw)["errors"]
    assert parse(raw, allow_code_fence=True) == {"errors": [], "statements": [], "semantic_rejections": [],
                                                "row_diagnostics_schema_version": 1, "row_diagnostics": []}


def test_conditional_consequence_cannot_be_asserted():
    result = parse([candidate()], "Mina: If I leave the team, I will feel sad about leaving the team.")
    assert result["errors"] == []
    assert result["statements"] == []
    assert result["semantic_rejections"][0]["kind"] == "scope_failure"


def test_quoted_report_preserves_combined_condition_negation():
    row = candidate(subject="Jules", holder_perspective="QUOTED", polarity="NEG")
    row["evidence"].update(actor="Jules", attributed_to="Mina", assertion_scope="REPORTED",
                           scope_markers=["REPORTED", "CONDITIONAL", "NEGATED"])
    parsed = parse([row], "Mina: Jules said if he leaves the team, he will not feel sad about leaving the team.")
    assert parsed["errors"] == []
    assert parsed["statements"][0]["evidence"]["scope_markers"] == ["REPORTED", "CONDITIONAL", "NEGATED"]


def test_historical_time_cannot_be_dropped_or_fabricated():
    assert parse([candidate()], "Mina: Yesterday I felt sad about leaving the team.")["semantic_rejections"]
    row = candidate()
    row["evidence"].update(time_text="Yesterday", event_time={"start": "2030-01-01T00:00:00Z", "end": None})
    assert parse([row], "Mina: Yesterday I felt sad about leaving the team.")["semantic_rejections"]


def test_policy_validation_is_owned_by_native_core():
    policy = _core.ValidationPolicy()
    assert hasattr(policy, "validate"), "native policy validation missing"
    policy.validate()
    policy.semantic_claim_contract = True
    with pytest.raises(ValueError, match="preserve_text_objects"):
        policy.validate()
    policy.preserve_text_objects = True
    policy.attribute_first_order_mental_to_holder = True
    with pytest.raises(ValueError, match="attribute_first_order_mental_to_holder"):
        policy.validate()
    policy.attribute_first_order_mental_to_holder = False
    policy.validate()


def test_native_source_turn_metadata_and_speech_act_guards():
    units = json.loads(_core.claim_source_units(
        "Session 2 | Marcus | turn 6 | I am indifferent about parking spaces.\n"
    ))
    assert units[0]["speaker"] == "Marcus"
    assert units[0]["session_id"] == "Session 2"
    assert units[0]["turn_index"] == 6

    cognitive = candidate(object="that the missing keys are in the kitchen")
    parsed = parse([cognitive], "Mina: I feel that the missing keys are in the kitchen.")
    assert parsed["statements"] == []
    assert parsed["semantic_rejections"][0]["kind"] == "scope_failure"

    decided = candidate(predicate="decided_on", modality="INTENDS", object="accept the Swindon job")
    parsed = parse([decided], "Mina: I said yes to the Swindon job.")
    assert parsed["errors"] == []
    assert len(parsed["statements"]) == 1
@pytest.mark.parametrize("mutate", [
    lambda r: r.update(holder="Jules"),
    lambda r: r.update(subject="Jules"),
    lambda r: r.update(subject_kind="entity"),
    lambda r: r.update(modality="DESIRES"),
    lambda r: r.update(predicate="uncertain_about", polarity="UNKNOWN"),
])
def test_semantic_rejections_are_separate_from_technical_errors(mutate):
    wrong = candidate()
    mutate(wrong)
    parsed = parse([candidate(), wrong])
    assert parsed["errors"] == []
    assert len(parsed["statements"]) == 1
    assert len(parsed["semantic_rejections"]) == 1
    assert parsed["semantic_rejections"][0]["index"] == 1


@pytest.mark.parametrize("predicate,object_text,source", [
    ("uncertain_about", "whether to attend the retreat", "Mina: I have not decided whether to attend the retreat."),
    ("uncertain_about", "是否参加团建", "Mina：我还没决定是否参加团建。"),
    ("decided_on", "not attend the retreat", "Mina: I decided not to attend the retreat."),
    ("decided_on", "不参加团建", "Mina：我决定不参加团建。"),
    ("feels", "sad about leaving the team", "Mina: I am sad about leaving the team, but not about the commute."),
])
def test_negative_words_do_not_automatically_negate_mental_relation(predicate, object_text, source):
    row = candidate(predicate=predicate, object=object_text, modality="INTENDS" if predicate == "decided_on" else "BELIEVES")
    parsed = parse([row], source)
    assert parsed["errors"] == []
    assert parsed["semantic_rejections"] == []
    assert len(parsed["statements"]) == 1


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(predicate="unknown_predicate"),
    lambda r: r.update(nesting_depth=1),
    lambda r: r.update(holder_perspective="UNKNOWN"),
    lambda r: r["evidence"].update(event_time={"start":"not-a-date", "end":None}),
    lambda r: r.pop("evidence"),
])
def test_later_technical_error_is_never_hidden_by_earlier_semantic_rejection(mutate):
    wrong = candidate(holder="Jules")
    malformed = candidate()
    mutate(malformed)
    parsed = parse([wrong, malformed])
    assert parsed["errors"]
    assert parsed["statements"] == []
    assert parsed["semantic_rejections"] == []


def test_leading_scope_binding_returns_native_coordinates_and_raw_indexes():
    good = candidate(object="relieved about the rehearsal")
    bad = candidate(subject="Other", object="relieved about the rehearsal")
    payload = "Mina: I am relieved about the rehearsal. Can you bring the chairs?"
    result = parse([good, bad, good], payload)
    assert result["errors"] == []
    assert len(result["statements"]) == 2
    assert result["row_diagnostics_schema_version"] == 1
    assert [r["index"] for r in result["row_diagnostics"]] == [0, 1, 2]
    assert [r["candidate_index"] for r in result["row_diagnostics"]] == [0, None, 1]
    scope = result["row_diagnostics"][0]["scope_resolution"]
    assert payload.encode()[scope["begin"]:scope["end"]] == b"I am relieved about the rehearsal."
    assert scope["coordinate_space"] == "source_unit_text_utf8"
    assert result["row_diagnostics"][1]["scope_resolution"] is None
    evidence = result["statements"][0]["evidence"]
    assert evidence["source_span"]["span_end"] == len(payload.encode())
    assert evidence["source_span"]["source_hash"] == hashlib.sha256(payload.encode()).hexdigest()
    assert "scope_resolution" not in evidence
