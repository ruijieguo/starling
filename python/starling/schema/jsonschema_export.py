"""JSON-Schema (Draft 2020-12) reflection export (M0.1 Task 9).

Walks dataclass field annotations and produces JSON-Schema dicts. Single
source of truth for downstream consumers:
  - M0.2 SQLite DDL generation
  - M0.4 LLM Extractor strict-output prompt

Strategy: introspect ``typing.get_origin`` / ``typing.get_args`` on each
field's runtime annotation. ``StrEnum`` values are inlined directly into
``properties[k]["enum"]`` rather than referenced via ``$ref``. ``Ref``
classes (``CognizerRef`` etc.) collapse to ``{"type": "string", "format":
"uuid"}``. Nested dataclasses recurse.

This module avoids ``from __future__ import annotations`` so that field
types are runtime objects, not strings — but ``typing.get_type_hints`` is
still used to resolve any forward-reference strings that creep in.
"""

import dataclasses
import enum
import types
import typing
import uuid
from datetime import datetime
from typing import Literal, Union

from starling.schema.affect import AffectVector
from starling.schema.cognizer import AccessPolicy, Cognizer
from starling.schema.container import (
    CommonGround, Container, KnowledgeFrontier, Persona,
)
from starling.schema.edge import RelationEdge
from starling.schema.engram import Engram, KeyRef, SourceRef
from starling.schema.entity import Entity
from starling.schema.refs import (
    CognizerRef, EngramRef, EntityRef, KnowledgeFrontierRef,
    PersonaRef, StatementRef,
)
from starling.schema.source import SourceSpanRef
from starling.schema.statement import EvidenceRef, Statement, TimeRange
from starling.schema.temporal import ConfidenceEvent, TemporalAnchor


_REF_CLASSES = (
    CognizerRef, EntityRef, StatementRef,
    EngramRef, PersonaRef, KnowledgeFrontierRef,
)

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _type_to_schema(typ) -> dict:
    """Translate a single annotation object to a JSON-Schema dict."""
    # `object` — any value
    if typ is object:
        return {}

    # Primitives
    if typ is bool:
        return {"type": "boolean"}
    if typ is int:
        return {"type": "integer"}
    if typ is float:
        return {"type": "number"}
    if typ is str:
        return {"type": "string"}
    if typ is bytes:
        return {"type": "string", "contentEncoding": "base64"}
    if typ is datetime:
        return {"type": "string", "format": "date-time"}
    if typ is uuid.UUID:
        return {"type": "string", "format": "uuid"}
    if typ is type(None):
        return {"type": "null"}

    # Ref classes — UUID strings
    if isinstance(typ, type) and typ in _REF_CLASSES:
        return {"type": "string", "format": "uuid"}

    # StrEnum — inlined
    if isinstance(typ, type) and issubclass(typ, enum.StrEnum):
        return {"type": "string", "enum": [m.value for m in typ]}

    # Nested dataclass — recurse
    if isinstance(typ, type) and dataclasses.is_dataclass(typ):
        return _dataclass_schema(typ)

    origin = typing.get_origin(typ)
    args = typing.get_args(typ)

    # Literal[...]
    if origin is Literal:
        return {"enum": list(args)}

    # Union / Optional / `T | None`
    if origin is Union or origin is types.UnionType:
        sub_schemas = [_type_to_schema(a) for a in args]
        return {"oneOf": sub_schemas}

    # tuple — bare `tuple` (no args) handled before generic tuple branch
    if typ is tuple:
        return {"type": "array"}

    # tuple[...]
    if origin is tuple:
        if len(args) == 0:
            return {"type": "array"}
        # Variable-length homogeneous: tuple[T, ...]
        if len(args) == 2 and args[1] is Ellipsis:
            return {"type": "array", "items": _type_to_schema(args[0])}
        # Fixed-length heterogeneous: tuple[A, B, ...]
        prefix = [_type_to_schema(a) for a in args]
        return {
            "type": "array",
            "prefixItems": prefix,
            "minItems": len(prefix),
            "maxItems": len(prefix),
        }

    # list[T]
    if origin is list:
        if args:
            return {"type": "array", "items": _type_to_schema(args[0])}
        return {"type": "array"}

    # dict[K, V] — open-ended object with value-type constraint
    if origin is dict:
        if args and len(args) == 2:
            return {"type": "object", "additionalProperties": _type_to_schema(args[1])}
        return {"type": "object"}

    # Fallback: treat as opaque
    return {}


def _dataclass_schema(cls: type) -> dict:
    """Build the object schema for a dataclass without the top-level $schema."""
    hints = typing.get_type_hints(cls)
    properties: dict[str, dict] = {}
    required: list[str] = []
    for f in dataclasses.fields(cls):
        annot = hints.get(f.name, f.type)
        properties[f.name] = _type_to_schema(annot)
        if (
            f.default is dataclasses.MISSING
            and f.default_factory is dataclasses.MISSING
        ):
            required.append(f.name)
    return {
        "title": cls.__name__,
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def schema_for(cls: type) -> dict:
    """Return the JSON-Schema (Draft 2020-12) document for a dataclass."""
    if not (isinstance(cls, type) and dataclasses.is_dataclass(cls)):
        raise TypeError(f"schema_for expects a dataclass, got {cls!r}")
    schema = _dataclass_schema(cls)
    return {"$schema": _DRAFT, **schema}


_EXPORT_CLASSES: tuple[type, ...] = (
    Statement, Cognizer, Entity, Engram,
    AffectVector, TemporalAnchor, ConfidenceEvent,
    SourceSpanRef, EvidenceRef, TimeRange,
    Container, Persona, CommonGround, KnowledgeFrontier,
    RelationEdge,
    # Bonus: the small placeholder dataclasses that reflect cleanly.
    AccessPolicy, SourceRef, KeyRef,
)


def all_schemas() -> dict[str, dict]:
    """Return ``{class_name: schema_dict}`` for every exported dataclass."""
    return {cls.__name__: schema_for(cls) for cls in _EXPORT_CLASSES}
