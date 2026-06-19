import dataclasses

import pytest

import starling
from starling.extractor.config import ExtractionConfig
from starling.extractor.prompts import EXTRACTION_PROMPT
from starling.extractor.episodic_prompt import EPISODIC_EXTRACTION_PROMPT


def test_defaults_match_module_constants():
    c = ExtractionConfig()
    assert c.belief_prompt == EXTRACTION_PROMPT
    assert c.episodic_prompt == EPISODIC_EXTRACTION_PROMPT
    assert c.extra_core_predicates == ()
    assert c.confidence_drop_floor == 0.30
    assert c.weak_inference_floor == 0.50


def test_frozen_immutable():
    c = ExtractionConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.belief_prompt = "x"


def test_reexported_from_starling():
    assert starling.ExtractionConfig is ExtractionConfig
