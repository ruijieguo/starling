import starling
import starling._memory_core as mc
from starling.extractor.prompts import EXTRACTION_PROMPT
from starling.extractor.episodic_prompt import EPISODIC_EXTRACTION_PROMPT


def _install_spies(monkeypatch, captured):
    def fake_remember(adapter, llm, prompt, **kw):
        captured.setdefault("belief", prompt)
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


def test_third_general_pass_runs_with_self_filled_prompt(tmp_path, monkeypatch):
    import starling._memory_core as mc
    from starling.extractor.config import ExtractionConfig
    prompts = []

    def spy(adapter, llm, prompt, **kw):
        prompts.append(prompt)
        return {"engram_ref": "eng-1", "statement_ids": [], "outcome": "stub"}

    class FakeEpisodic:
        def __init__(self, *a):
            pass

        def extract(self, **kw):
            return []

    monkeypatch.setattr(mc._core, "memory_remember", spy)
    monkeypatch.setattr(mc._core, "EpisodicExtractor", FakeEpisodic)
    mem = starling.Memory.open(
        str(tmp_path / "m.db"), agent="self",
        llm=starling.make_stub_llm(default_response="[]"))
    mem._core.remember("Postgres is a relational database.")

    assert len(prompts) == 2  # belief (#1) then general (#2)
    assert prompts[0] == ExtractionConfig().belief_prompt
    expected_general = ExtractionConfig().general_fact_prompt.replace("{self}", "self")
    assert prompts[1] == expected_general
    assert "{self}" not in prompts[1]
