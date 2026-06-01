"""P2.e Memory facade — open / remember(stub llm) / close。

Drives the public application surface end-to-end offline:
  Memory.open (preflight relax + local-store sqlite runtime)
  → remember(text): BusFacade.append_evidence(EngramInput) creates the engram,
    then _core.Extractor(conn, FakeLLMAdapter).run(...) extracts ≥1 statement
    from a deterministic canned XML (no network).
  → close.

The canned XML mirrors test_m0_4_acceptance.py SCENARIO_XML exactly: a single
<statement> with holder/perspective/subject/predicate/object/modality/polarity/
confidence/observed_at/perceived_by. The holder ref ("alice") matches the
holder_id passed to Extractor.run (Memory's agent), so the orchestrator stamps
the statement with that cognizer.
"""
import starling
from starling import _core

# Matches test_m0_4_acceptance.py SCENARIO_XML statement shape exactly.
CANNED_XML = (
    "<extraction><statement>"
    "<holder ref=\"alice\"/><perspective>first_person</perspective>"
    "<subject kind=\"cognizer\" id=\"cog-bob\"/><predicate>responsible_for</predicate>"
    "<object kind=\"str\" canonical_hash=\"hash-auth\">auth</object>"
    "<modality>believes</modality><polarity>pos</polarity>"
    "<confidence>0.9</confidence><observed_at>2026-06-01T09:00:00Z</observed_at>"
    "<perceived_by ref=\"alice\"/></statement></extraction>"
)


def test_open_remember_close(tmp_path):
    llm = starling.make_stub_llm(default_xml=CANNED_XML)
    mem = starling.Memory.open(str(tmp_path / "m.db"), agent="alice", llm=llm)
    res = mem.remember("Bob owns the auth module")
    assert res.outcome in ("accepted", "idempotent")
    assert len(res.statement_ids) >= 1
    mem.close()


def test_remember_without_llm_raises(tmp_path):
    mem = starling.Memory.open(str(tmp_path / "m2.db"), agent="alice")  # no llm
    try:
        mem.remember("anything")
        assert False, "should raise"
    except RuntimeError:
        pass
    finally:
        mem.close()


def test_openai_adapter_constructs_into_extractor(tmp_path):
    # The production llm (OpenAIAdapter) must be acceptable to the Extractor ctor.
    # We only test CONSTRUCTION (no .run — that needs a real API key); a TypeError
    # here means the binding rejects the production adapter.
    import os
    from starling import runtime as _runtime
    from starling.testing import relax_preflight_for_m0_3
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    relax_preflight_for_m0_3()
    rt = _runtime._build_local_store_sqlite_runtime(tmp_path / "oa.db")
    rt.start()
    llm = starling.make_openai_llm()                 # OpenAIAdapter, constructs offline
    ext = _core.Extractor(rt.adapter.connection(), llm)   # must NOT raise TypeError
    assert ext is not None


def test_recall_and_tick(tmp_path):
    llm = starling.make_stub_llm(default_xml=CANNED_XML)
    mem = starling.Memory.open(str(tmp_path / "m3.db"), agent="alice", llm=llm)
    mem.remember("Bob owns the auth module")
    stats = mem.tick()                       # embed + commitment tick
    assert stats.embedded >= 0
    hits = mem.recall("bob owns auth", mode="semantic", k=5)
    assert isinstance(hits, list)
    mem.close()
