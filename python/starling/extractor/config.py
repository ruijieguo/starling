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
    # OPT-IN (default OFF → today's behaviour byte-for-byte): when True, a
    # first-order mental-state statement (nesting_depth==0, modality
    # believes/desires/intends/commits or predicate knows/prefers) is attributed
    # to its LLM-named bearer (cognizer-resolved) instead of the agent, so a
    # narrated 3rd-person attitude ("Xiao Ming wants a computer") lands under
    # holder_id=Xiao Ming and mental_state_of(character) finds it. Threaded to the
    # C++ ValidationPolicy at the write boundary (see MemoryCore._build_policy).
    attribute_first_order_mental_to_holder: bool = False
    # Preserve clause-valued objects through belief/general-fact ingestion.
    # Keep this stable per corpus; existing normalized data is not migrated.
    # Episodic entity themes retain their existing grounding normalization.
    preserve_text_objects: bool = False
    semantic_claim_contract: bool = False
    claim_allow_code_fence: bool = False
    claim_protocol_retry_budget: int = 0
    claim_batch_size: int = 0
    claim_batch_target_units: bool = False
    # Structured claim requests use the native C++ output mode.  ``legacy``
    # preserves historical behavior; evaluation arms may opt into
    # ``json_object`` without adding parsing logic to this Python carrier.
    claim_output_mode: str = "legacy"

    def __post_init__(self):
        self.to_native_policy()

    def to_native_policy(self):
        """Map configuration to the shared C++ policy and its validation."""
        from starling import _core

        policy = _core.ValidationPolicy()
        policy.extra_core_predicates = list(self.extra_core_predicates)
        policy.confidence_drop_floor = self.confidence_drop_floor
        policy.weak_inference_floor = self.weak_inference_floor
        policy.attribute_first_order_mental_to_holder = self.attribute_first_order_mental_to_holder
        policy.preserve_text_objects = self.preserve_text_objects
        policy.semantic_claim_contract = self.semantic_claim_contract
        policy.claim_allow_code_fence = self.claim_allow_code_fence
        policy.claim_protocol_retry_budget = self.claim_protocol_retry_budget
        policy.claim_batch_size = self.claim_batch_size
        policy.claim_batch_target_units = self.claim_batch_target_units
        output_modes = {
            "legacy": _core.OutputMode.Legacy,
            "json_object": _core.OutputMode.JsonObject,
            "json_schema_strict": _core.OutputMode.JsonSchemaStrict,
        }
        try:
            policy.claim_output_mode = output_modes[self.claim_output_mode]
        except KeyError as exc:
            raise ValueError(f"unsupported claim_output_mode: {self.claim_output_mode!r}") from exc
        policy.validate()
        return policy
