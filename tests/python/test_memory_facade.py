"""P2.e Memory facade — open / remember(stub llm) / close。

Drives the public application surface end-to-end offline:
  Memory.open (preflight relax + local-store sqlite runtime)
  → remember(text): BusFacade.append_evidence(EngramInput) creates the engram,
    then _core.Extractor(conn, FakeLLMAdapter, prompt).run(...) extracts ≥1
    statement from a deterministic canned JSON array (no network).
  → close.

The canned JSON is a single-element array carrying the semantic core
(holder/holder_perspective/subject/predicate/object/modality/polarity/
nesting_depth). The orchestrator unconditionally stamps holder_id with the
run() caller's holder (Memory's agent "alice"); the JSON "holder" is advisory.
"""
import starling
from starling import _core

# Single-element JSON array (semantic core only). UPPERCASE enums match the
# real eval prompt; the parser lowercases them. object is a plain string;
# the canonical hash is computed C++-side.
CANNED_JSON = (
    '[{"holder":"alice","holder_perspective":"FIRST_PERSON",'
    '"subject":"cog-bob","predicate":"responsible_for","object":"auth",'
    '"modality":"BELIEVES","polarity":"POS","nesting_depth":0}]'
)


def test_open_remember_close(tmp_path):
    llm = starling.make_stub_llm(default_response=CANNED_JSON)
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
    llm = starling.make_stub_llm(default_response=CANNED_JSON)
    mem = starling.Memory.open(str(tmp_path / "m3.db"), agent="alice", llm=llm)
    mem.remember("Bob owns the auth module")
    stats = mem.tick()                       # embed + commitment tick
    assert stats.embedded >= 0
    hits = mem.recall("bob owns auth", mode="semantic", k=5)
    assert isinstance(hits, list)
    mem.close()
