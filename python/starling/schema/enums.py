"""Schema enums (M0.1).

Single source of truth for all enum string values. C++ enum mirrors
(include/starling/schema/enums.hpp) MUST stringify to the same values;
the parity is asserted by tests/cpp/test_canonicalize.cpp.
"""

from enum import StrEnum

class Perspective(StrEnum):
    FIRST_PERSON = "first_person"
    QUOTED = "quoted"
    INFERRED = "inferred"
    HEARSAY = "hearsay"

class Modality(StrEnum):
    BELIEVES = "believes"
    KNOWS = "knows"
    ASSUMES = "assumes"
    DOUBTS = "doubts"
    DESIRES = "desires"
    INTENDS = "intends"
    COMMITS = "commits"
    PREFERS = "prefers"
    NORM_OUGHT = "norm_ought"
    NORM_FORBID = "norm_forbid"
    RECANTED = "recanted"
    OCCURRED = "occurred"  # episodic-event modality (sub-project A, phase 1)

class Polarity(StrEnum):
    POS = "pos"
    NEG = "neg"
    UNKNOWN = "unknown"

class ConsolidationState(StrEnum):
    VOLATILE = "volatile"
    REPLAYING_CONSOLIDATING = "replaying_consolidating"
    REPLAYING_RECONSOLIDATING = "replaying_reconsolidating"
    CONSOLIDATED = "consolidated"
    ARCHIVED = "archived"
    FORGOTTEN = "forgotten"

class EngramRetentionMode(StrEnum):
    LEGAL_HOLD = "legal_hold"
    AUDIT_RETAIN = "audit_retain"
    REDACTED_RETAIN = "redacted_retain"
    CRYPTO_ERASURE = "crypto_erasure"

class SourceKind(StrEnum):
    USER_INPUT = "user_input"
    EXTERNAL_DOC = "external_doc"
    TOOL_OBSERVATION = "tool_observation"
    SYSTEM_INTERNAL = "system_internal"
    OBSERVER_AGENT = "observer_agent"
    REPLAY_OUTPUT = "replay_output"

class IngestPolicy(StrEnum):
    STORE = "store"
    NO_STORE = "no_store"
    STORE_METADATA_ONLY = "store_metadata_only"
    REQUIRE_REVIEW = "require_review"

class IngestMode(StrEnum):
    CHUNKED_CONTENT = "chunked_content"
    WHOLE_RECORD = "whole_record"
    METADATA_ONLY = "metadata_only"

class PrivacyClass(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PERSONAL = "personal"
    SENSITIVE = "sensitive"
    REGULATED = "regulated"

class StatementProvenance(StrEnum):
    USER_INPUT = "user_input"
    REPLAY_DERIVED = "replay_derived"
    TOM_INFERRED = "tom_inferred"
    RECONSOLIDATION_DERIVED = "reconsolidation_derived"

class ReviewStatus(StrEnum):
    APPROVED = "approved"
    PENDING_REVIEW = "pending_review"
    INFERRED_UNREVIEWED = "inferred_unreviewed"
    REVIEW_REQUESTED = "review_requested"
    REJECTED = "rejected"

class EvidenceStatus(StrEnum):
    ACTIVE = "active"
    REDACTED = "redacted"
    ERASED = "erased"

class ContainerKind(StrEnum):
    PERSONA = "persona"
    COMMON_GROUND = "common_ground"
    KNOWLEDGE_FRONTIER = "knowledge_frontier"

class EdgeKind(StrEnum):
    BELIEVES_ABOUT = "believes_about"
    TRUSTS = "trusts"
    COMMITTED_TO = "committed_to"
    CONFLICTS_WITH = "conflicts_with"
    EVIDENCE_FOR = "evidence_for"
    EVIDENCE_AGAINST = "evidence_against"
    SHARED_GROUND = "shared_ground"
    OBSERVED_BY = "observed_by"
    PERCEIVED_BY = "perceived_by"
    NORM_OF = "norm_of"
    INTENT_OF = "intent_of"
    MAY_OVERLAP_WITH = "may_overlap_with"
    SUPERSEDES = "supersedes"
    DERIVED_FROM = "derived_from"

class AnchorKind(StrEnum):
    SOURCE_SPAN = "source_span"
    EPISODE = "episode"
    ENGRAM_RECORD = "engram_record"
    MESSAGE = "message"
    DOCUMENT = "document"
    DERIVED_CHAIN = "derived_chain"
    SYSTEM_NOW = "system_now"

class BuildPolicy(StrEnum):
    ON_EVENT = "on_event"
    SLEEP = "sleep"
    MANUAL = "manual"

# §3.5 transition table (T1..T11 + T7-P1). 10 distinct edges.
CONSOLIDATION_TRANSITIONS: frozenset[tuple[ConsolidationState, ConsolidationState]] = frozenset({
    # T1 (create -> VOLATILE) lives outside the state graph.
    (ConsolidationState.VOLATILE, ConsolidationState.REPLAYING_CONSOLIDATING),       # T2
    (ConsolidationState.REPLAYING_CONSOLIDATING, ConsolidationState.CONSOLIDATED),   # T3
    (ConsolidationState.REPLAYING_CONSOLIDATING, ConsolidationState.VOLATILE),       # T4
    (ConsolidationState.CONSOLIDATED, ConsolidationState.REPLAYING_RECONSOLIDATING), # T5
    (ConsolidationState.REPLAYING_RECONSOLIDATING, ConsolidationState.CONSOLIDATED), # T6
    (ConsolidationState.REPLAYING_RECONSOLIDATING, ConsolidationState.ARCHIVED),     # T7
    (ConsolidationState.CONSOLIDATED, ConsolidationState.ARCHIVED),                  # T7-P1 + T8 (same edge, different triggers)
    (ConsolidationState.ARCHIVED, ConsolidationState.REPLAYING_RECONSOLIDATING),     # T9
    (ConsolidationState.ARCHIVED, ConsolidationState.FORGOTTEN),                     # T10
    (ConsolidationState.CONSOLIDATED, ConsolidationState.FORGOTTEN),                 # T11 (purge_compliance)
})
