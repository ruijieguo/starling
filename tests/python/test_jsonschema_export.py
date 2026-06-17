"""JSON-Schema reflection export tests (M0.1 Task 9)."""

import jsonschema

from starling.schema.jsonschema_export import schema_for, all_schemas
from starling.schema.statement import Statement
from starling.schema.cognizer import Cognizer
from starling.schema.engram import Engram
from starling.schema.affect import AffectVector


def test_statement_schema_top_level_object():
    s = schema_for(Statement)
    assert s["type"] == "object"
    assert "properties" in s
    assert "holder" in s["properties"]
    assert "canonical_object_hash" in s["properties"]


def test_statement_schema_required_fields():
    s = schema_for(Statement)
    required = set(s["required"])
    assert "holder" in required
    assert "subject" in required
    assert "predicate" in required
    assert "salience" in required


def test_affect_schema_five_floats():
    s = schema_for(AffectVector)
    props = s["properties"]
    for k in ("valence", "arousal", "dominance", "novelty", "stakes"):
        assert props[k]["type"] == "number"


def test_modality_schema_is_enum_with_twelve_values():
    s = schema_for(Statement)
    modality_schema = s["properties"]["modality"]
    assert modality_schema["type"] == "string"
    assert len(modality_schema["enum"]) == 12


def test_all_schemas_includes_fifteen_classes():
    bag = all_schemas()
    expected = {
        "Statement", "Cognizer", "Entity", "Engram",
        "AffectVector", "TemporalAnchor", "ConfidenceEvent",
        "SourceSpanRef", "EvidenceRef", "TimeRange",
        "Container", "Persona", "CommonGround", "KnowledgeFrontier",
        "RelationEdge",
    }
    assert expected.issubset(set(bag.keys()))
    assert len(bag) >= 15


def test_schema_self_validates_with_jsonschema_lib():
    """jsonschema lib should accept our generated schema as valid Draft 2020-12."""
    s = schema_for(Statement)
    jsonschema.Draft202012Validator.check_schema(s)
