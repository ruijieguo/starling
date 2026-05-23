"""Python ↔ C++ parity for Statement enums.

For every Python StrEnum member, assert that the C++ to_string equivalent
produces the same string. The C++ side is exercised through pybind11 (M0.4
Task 9 binds these enums); until then this test reads the C++ source via
a small regex helper to extract the string literals.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from starling.schema.enums import (
    ConsolidationState, Modality, Perspective, Polarity,
    ReviewStatus, StatementProvenance,
)

ENUMS_CPP = (
    Path(__file__).resolve().parents[2] / "src" / "schema" / "statement_enums.cpp"
)


def _extract_pairs(enum_name: str) -> dict[str, str]:
    """Pull `case Foo::BAR: return "bar";` pairs out of the to_string switch."""
    text = ENUMS_CPP.read_text()
    pattern = re.compile(
        r"case\s+" + re.escape(enum_name) + r"::([A-Z_]+):\s*return\s+\"([^\"]+)\";"
    )
    return {m.group(1): m.group(2) for m in pattern.finditer(text)}


@pytest.mark.parametrize(
    "enum_cls,enum_name",
    [
        (Perspective,         "Perspective"),
        (Modality,            "Modality"),
        (Polarity,            "Polarity"),
        (ConsolidationState,  "ConsolidationState"),
        (ReviewStatus,        "ReviewStatus"),
        (StatementProvenance, "StatementProvenance"),
    ],
)
def test_enum_parity(enum_cls, enum_name):
    cpp_pairs = _extract_pairs(enum_name)
    py_pairs = {member.name: member.value for member in enum_cls}
    assert cpp_pairs == py_pairs, (
        f"{enum_name} parity drift: cpp={cpp_pairs} py={py_pairs}"
    )
