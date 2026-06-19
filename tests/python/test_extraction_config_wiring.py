import starling
import starling._memory_core as mc
from starling.extractor.prompts import EXTRACTION_PROMPT
from starling.extractor.episodic_prompt import EPISODIC_EXTRACTION_PROMPT


def _install_spies(monkeypatch, captured):
    def fake_remember(adapter, llm, prompt, **kw):
        captured["belief"] = prompt
        return {"engram_ref": "eng-1", "statement_ids": [], "outcome": "stub"}

    class FakeEpisodic:
        def __init__(self, conn, llm, adapter, prompt):
            captured["episodic"] = prompt

        def extract(self, **kw):
            return []

    monkeypatch.setattr(mc._core, "memory_remember", fake_remember)
    monkeypatch.setattr(mc._core, "EpisodicExtractor", FakeEpisodic)


def test_custom_prompts_forwarded(tmp_path, monkeypatch):
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"),
        extraction=starling.ExtractionConfig(belief_prompt="SENTINEL-BELIEF",
                                             episodic_prompt="SENTINEL-EPISODIC"))
    mem._core.remember("hi")
    assert captured["belief"] == "SENTINEL-BELIEF"
    assert captured["episodic"] == "SENTINEL-EPISODIC"


def test_default_prompts_forwarded(tmp_path, monkeypatch):
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"))
    mem._core.remember("hi")
    assert captured["belief"] == EXTRACTION_PROMPT
    assert captured["episodic"] == EPISODIC_EXTRACTION_PROMPT


def test_policy_built_from_config(tmp_path, monkeypatch):
    captured = {}

    def fake_remember(adapter, llm, prompt, *, policy=None, **kw):
        captured["policy"] = policy
        return {"engram_ref": "", "statement_ids": [], "outcome": "stub"}

    monkeypatch.setattr(mc._core, "memory_remember", fake_remember)
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

    def fake_remember(adapter, llm, prompt, *, policy=None, **kw):
        captured["policy"] = policy
        return {"engram_ref": "", "statement_ids": [], "outcome": "stub"}

    monkeypatch.setattr(mc._core, "memory_remember", fake_remember)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"))
    mem._core.remember("hi")
    pol = captured["policy"]
    assert pol is not None
    assert list(pol.extra_core_predicates) == []
    assert pol.confidence_drop_floor == 0.30
    assert pol.weak_inference_floor == 0.50
