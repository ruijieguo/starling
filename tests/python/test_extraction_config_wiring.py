import starling
import starling._memory_core as mc
from starling.extractor.prompts import EXTRACTION_PROMPT
from starling.extractor.episodic_prompt import EPISODIC_EXTRACTION_PROMPT


def _install_spies(monkeypatch, captured):
    """Capture the Python-to-Core remember contract without mocking Core internals."""
    def fake_remember_all(adapter, llm, belief_prompt, episodic_prompt,
                          general_fact_prompt, *, tenant_id, holder_id,
                          interlocutor, adapter_name, source_prefix,
                          created_at_iso8601, payload, policy=None):
        captured["belief_prompt"] = belief_prompt
        captured["episodic_prompt"] = episodic_prompt
        captured["general_fact_prompt"] = general_fact_prompt
        captured["holder_id"] = holder_id
        captured["policy"] = policy
        return {"engram_ref": "spy-engram", "statement_ids": [],
                "outcome": "accepted", "extraction_failed": False}

    monkeypatch.setattr(mc._core, "memory_remember_all", fake_remember_all)


def test_custom_prompts_forwarded(tmp_path, monkeypatch):
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"),
        extraction=starling.ExtractionConfig(belief_prompt="SENTINEL-BELIEF",
                                             episodic_prompt="SENTINEL-EPISODIC"))
    mem._core.remember("hi")
    assert captured["belief_prompt"] == "SENTINEL-BELIEF"
    assert captured["episodic_prompt"] == "SENTINEL-EPISODIC"


def test_default_prompts_forwarded(tmp_path, monkeypatch):
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), llm=starling.make_stub_llm(default_response="[]"))
    mem._core.remember("hi")
    assert captured["belief_prompt"] == EXTRACTION_PROMPT
    assert captured["episodic_prompt"] == EPISODIC_EXTRACTION_PROMPT


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


def test_general_prompt_and_holder_forwarded_to_core(tmp_path, monkeypatch):
    from starling.extractor.config import ExtractionConfig
    captured = {}
    _install_spies(monkeypatch, captured)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), agent="self",
        llm=starling.make_stub_llm(default_response="[]"))
    mem._core.remember("Postgres is a relational database.")

    assert captured["belief_prompt"] == ExtractionConfig().belief_prompt
    assert captured["general_fact_prompt"] == ExtractionConfig().general_fact_prompt
    assert captured["holder_id"] == "self"
