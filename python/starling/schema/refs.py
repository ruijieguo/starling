"""Typed reference wrappers (M0.1).

Each Ref class wraps a UUID and is `eq=True`/`frozen=True`/`slots=True`. The
six classes do NOT share a base — cross-type equality is intentionally false
so that mixing CognizerRef with EntityRef in a dict cannot collide.
"""

import uuid
from dataclasses import dataclass


def _ref_class(name: str):
    """Define a frozen-slots dataclass that wraps a UUID under a unique name."""
    @dataclass(frozen=True, slots=True)
    class _Ref:
        id: uuid.UUID

        def __str__(self) -> str:
            return str(self.id)

        @classmethod
        def from_str(cls, raw: str):
            return cls(uuid.UUID(raw))

    _Ref.__name__ = name
    _Ref.__qualname__ = name
    return _Ref


CognizerRef = _ref_class("CognizerRef")
EntityRef = _ref_class("EntityRef")
StatementRef = _ref_class("StatementRef")
EngramRef = _ref_class("EngramRef")
PersonaRef = _ref_class("PersonaRef")
KnowledgeFrontierRef = _ref_class("KnowledgeFrontierRef")
