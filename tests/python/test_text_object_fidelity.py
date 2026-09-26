"""Free-text extraction must preserve clauses without changing theme defaults."""
import json
import sqlite3

import pytest

from starling import _core, runtime
from starling._memory_core import _build_policy
from starling.extractor.config import ExtractionConfig


def test_surface_policy_is_explicit_and_forwarded():
    assert hasattr(_core.ValidationPolicy(), "preserve_text_objects")
    assert not _core.ValidationPolicy().preserve_text_objects
    assert not ExtractionConfig().preserve_text_objects
    assert _build_policy(ExtractionConfig(preserve_text_objects=True)).preserve_text_objects


@pytest.mark.parametrize("surface", [
    "sad to leave my colleagues", "Ren with the keys", "noise from upstairs",
    "all three options", "some budgets", "both hands", "last week: unsure; today: declines", " \t\n ",
])
def test_native_commit_preserves_text_and_hashes_the_preserved_value(tmp_path, surface):
    policy = _core.ValidationPolicy()
    assert hasattr(policy, "preserve_text_objects")
    policy.preserve_text_objects = True
    policy.extra_core_predicates = ["feels"]
    database = tmp_path / "memory.db"
    rt = runtime._build_local_store_sqlite_runtime(database)
    rt.start()
    try:
        payload = b"Nora describes her situation."
        template = "Extract {convo}"
        prepared = _core.memory_remember_prepare(
            rt.adapter, tenant_id="default", holder_id="Nora", interlocutor="",
            adapter_name="test", source_prefix="text-fidelity", created_at_iso8601="2099-01-01T00:00:00Z",
            payload=payload)
        fake = _core.FakeLLMAdapter()
        fake.set_default_response(json.dumps([{
            "holder": "Nora", "holder_perspective": "FIRST_PERSON", "subject": "Nora",
            "subject_kind": "cognizer", "predicate": "feels", "object": surface,
            "modality": "BELIEVES", "polarity": "POS", "nesting_depth": 0}]))
        extracted = _core.memory_extract_llm(rt.adapter, fake, template, "Nora", payload, policy)
        receipt = _core.memory_remember_commit(
            rt.adapter, fake, tenant_id="default", holder_id="Nora", interlocutor="",
            prepared=prepared, llm_result=extracted, policy=policy)
        assert not receipt["extraction_failed"]
        with sqlite3.connect(database) as conn:
            stored = conn.execute(
                "SELECT object_value, canonical_object_hash FROM statements WHERE predicate='feels'").fetchall()
        if not surface.strip():
            assert stored == []
            return
        (value, fingerprint), = stored
        assert value == surface
        from starling.schema.value import canonicalize_object
        assert fingerprint == canonicalize_object(surface)[1]
    finally:
        del rt
