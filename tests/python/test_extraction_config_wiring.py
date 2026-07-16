import starling
import starling._memory_core as mc
from starling.extractor.prompts import EXTRACTION_PROMPT
from starling.extractor.episodic_prompt import EPISODIC_EXTRACTION_PROMPT


def _install_spies(monkeypatch, captured):
    """Task 4 update (remember extraction 出锁/方案2): MemoryCore.remember() no
    longer calls a single _core.memory_remember monolith — it inlines
    remember_prepare → remember_extract → remember_commit. Prompt + policy now
    flow through _core.memory_extract_llm, called twice per remember() in a
    fixed order (belief then general-fact — the same ordering guarantee the
    old monolith had calling memory_remember twice), so a `prompts` list spy
    replaces the old single-shot `belief` capture. _core.memory_remember_commit
    (persist) needs an ExtractionLlmResult, an opaque C++ type only _core
    itself can construct, so it is faked too — echoing back prepared's REAL
    engram_ref/outcome (remember_prepare is deliberately left un-mocked and
    runs for real: it does no LLM work, just the engram write, so faking it
    would only lose coverage). EpisodicExtractor spy now exposes
    extract_llm/persist (option B: episodic LLM out of lock)."""
    def fake_extract_llm(adapter, llm, prompt, *, holder_id, payload, policy=None):
        captured.setdefault("prompts", []).append(prompt)
        captured["policy"] = policy
        return object()   # opaque placeholder; only ever re-forwarded to fake_commit below

    def fake_commit(adapter, llm, *, tenant_id, holder_id, interlocutor, prepared,
                    llm_result, policy=None):
        return {"engram_ref": prepared.engram_ref, "statement_ids": [],
                "outcome": prepared.outcome, "extraction_failed": False}

    class FakeEpisodic:
        def __init__(self, conn, llm, adapter, prompt):
            captured["episodic"] = prompt

        def extract_llm(self, passage):
            return object()   # opaque placeholder; only re-forwarded to persist below

        def persist(self, **kw):
            return []

    monkeypatch.setattr(mc._core, "memory_extract_llm", fake_extract_llm)
    monkeypatch.setattr(mc._core, "memory_remember_commit", fake_commit)
    monkeypatch.setattr(mc._core, "EpisodicExtractor", FakeEpisodic)


def test_custom_prompts_forwarded(tmp_path, monkeypatch):
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"),
        extraction=starling.ExtractionConfig(belief_prompt="SENTINEL-BELIEF",
                                             episodic_prompt="SENTINEL-EPISODIC"))
    mem._core.remember("hi")
    assert captured["prompts"][0] == "SENTINEL-BELIEF"
    assert captured["episodic"] == "SENTINEL-EPISODIC"


def test_default_prompts_forwarded(tmp_path, monkeypatch):
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"))
    mem._core.remember("hi")
    assert captured["prompts"][0] == EXTRACTION_PROMPT
    assert captured["episodic"] == EPISODIC_EXTRACTION_PROMPT


def test_policy_built_from_config(tmp_path, monkeypatch):
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"),
        extraction=starling.ExtractionConfig(extra_core_predicates=("annotates",),
                                             confidence_drop_floor=0.15,
                                             weak_inference_floor=0.7))
    mem._core.remember("hi")
    pol = captured["policy"]
    assert pol is not None
    assert list(pol.extra_core_predicates) == ["annotates"]
    assert pol.confidence_drop_floor == 0.15
    assert pol.weak_inference_floor == 0.7


def test_default_policy_built(tmp_path, monkeypatch):
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"))
    mem._core.remember("hi")
    pol = captured["policy"]
    assert pol is not None
    assert list(pol.extra_core_predicates) == []
    assert pol.confidence_drop_floor == 0.30
    assert pol.weak_inference_floor == 0.50


def test_third_general_pass_runs_with_self_filled_prompt(tmp_path, monkeypatch):
    from starling.extractor.config import ExtractionConfig
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), agent="self",
        llm=starling.make_stub_llm(default_response="[]"))
    mem._core.remember("Postgres is a relational database.")

    prompts = captured["prompts"]
    assert len(prompts) == 2  # belief (#1) then general (#2)
    assert prompts[0] == ExtractionConfig().belief_prompt
    expected_general = ExtractionConfig().general_fact_prompt.replace("{self}", "self")
    assert prompts[1] == expected_general
    assert "{self}" not in prompts[1]
