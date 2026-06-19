"""Per-deployment extraction configuration carrier (single construction-time object).

Injected at Memory.open(extraction=...); a default-constructed ExtractionConfig
reproduces today's behaviour exactly (the prompt constants + the validator's
built-in core predicate set + the 0.3/0.5 thresholds). belief_prompt/episodic_prompt
plumb the prompt seam that already exists in C++/bindings; extra_core_predicates +
the two floors become a C++ ValidationPolicy at the write boundary (see
MemoryCore._build_policy / statement_validator.cpp). extra_core_predicates is
ADDITIVE to the built-in constexpr core set and (because the vocab gate exempts
modality=OCCURRED) only affects belief-tier statements.
"""
from __future__ import annotations

from dataclasses import dataclass

from .prompts import EXTRACTION_PROMPT
from .episodic_prompt import EPISODIC_EXTRACTION_PROMPT
from .general_fact_prompt import GENERAL_FACT_EXTRACTION_PROMPT


@dataclass(frozen=True)
class ExtractionConfig:
    belief_prompt: str = EXTRACTION_PROMPT
    episodic_prompt: str = EPISODIC_EXTRACTION_PROMPT
    general_fact_prompt: str = GENERAL_FACT_EXTRACTION_PROMPT
    extra_core_predicates: tuple[str, ...] = ()
    confidence_drop_floor: float = 0.30
    weak_inference_floor: float = 0.50
