"""Common-knowledge operator — binding smoke + end-to-end round-trip.

Verifies:
  1. is_common_knowledge symbol exists on starling._core (binding smoke).
  2. CommonKnowledgeResult has the expected POD fields.
  3. Public scene: A/B/C all co-witness a ball move to L → is_ck is True,
     ck_value == "L".

Story pattern mirrors test_faux_pas_roundtrip.py: one remember() using a stub
LLM; no external API calls.

The story: Alice, Bob and Carol all enter together; all see the ball placed in
the cupboard (co-witnessed). We query is_common_knowledge for group
["Alice","Bob","Carol"], theme="ball". Because all three co-witnessed the
SAME event (the place/move event), is_ck must be True and ck_value == "cupboard".
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import starling
import starling._core as _core


# ---------------------------------------------------------------------------
# Story JSON: all three are present at the single ball-placement event.
# No departures — every cast member co-witnesses the same event, so
# is_common_knowledge must be True.
# ---------------------------------------------------------------------------
_STORY_PUBLIC = json.dumps([
    {"actor": "Alice", "action": "enter", "theme": "room", "location": None,
     "participants": ["Alice", "Bob", "Carol"], "time": None},
    {"actor": "Alice", "action": "put", "theme": "ball", "location": "cupboard",
     "participants": ["Alice", "Bob", "Carol"], "time": None},
])


# ---------------------------------------------------------------------------
# 1. Binding smoke — symbol must exist before we even build a memory.
# ---------------------------------------------------------------------------

def test_is_common_knowledge_symbol_exists():
    """The C++ binding must export is_common_knowledge on _core."""
    assert hasattr(_core, "is_common_knowledge"), (
        "starling._core has no attribute 'is_common_knowledge' — "
        "bind_08_tom.cpp binding is missing")


def test_common_knowledge_result_fields():
    """CommonKnowledgeResult class must be exported with the three POD fields."""
    assert hasattr(_core, "CommonKnowledgeResult"), (
        "starling._core has no attribute 'CommonKnowledgeResult'")
    cls = _core.CommonKnowledgeResult
    for field in ("is_ck", "ck_value", "establishing_event_id"):
        assert hasattr(cls, field), (
            f"CommonKnowledgeResult missing field '{field}'")


# ---------------------------------------------------------------------------
# 2. End-to-end: public co-witness scene → is_ck True.
# ---------------------------------------------------------------------------

def test_is_common_knowledge_public_scene(tmp_path):
    """All three cognizers co-witness a single ball-placement event.
    is_common_knowledge must return is_ck=True and ck_value='cupboard'."""
    mem = starling.Memory.open(
        str(tmp_path / "ck.db"), agent="narrator",
        llm=starling.make_stub_llm(default_response=_STORY_PUBLIC))
    try:
        mem.remember(
            "Alice, Bob and Carol entered the room together. "
            "Alice placed the ball in the cupboard.")
        mem.tick()

        adapter = mem._rt.adapter
        tenant = mem._core.tenant
        frontier = _core.KnowledgeFrontier(adapter)
        as_of = datetime(9999, 1, 1, tzinfo=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

        result = _core.is_common_knowledge(
            adapter, frontier,
            ["Alice", "Bob", "Carol"],
            "ball",
            tenant,
            as_of,
        )
        assert result.is_ck is True, (
            f"Expected is_ck=True for a publicly co-witnessed event; "
            f"got is_ck={result.is_ck!r}, ck_value={result.ck_value!r}, "
            f"establishing_event_id={result.establishing_event_id!r}")
        assert result.ck_value == "cupboard", (
            f"Expected ck_value='cupboard', got {result.ck_value!r}")
        assert isinstance(result.establishing_event_id, str)
    finally:
        mem.close()
