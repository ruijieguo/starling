from starling.schema import (
    Perspective, Modality, Polarity, ConsolidationState,
    EngramRetentionMode, SourceKind, IngestPolicy, IngestMode,
    PrivacyClass, StatementProvenance, ReviewStatus, EvidenceStatus,
    ContainerKind, EdgeKind, AnchorKind, BuildPolicy,
    CONSOLIDATION_TRANSITIONS,
)

def test_perspective_values():
    assert {e.value for e in Perspective} == {"first_person", "quoted", "inferred", "hearsay"}

def test_modality_twelve_values():
    assert {e.value for e in Modality} == {
        "believes", "knows", "assumes", "doubts", "desires", "intends",
        "commits", "prefers", "norm_ought", "norm_forbid", "recanted",
        "occurred",
    }

def test_consolidation_state_six():
    assert len(ConsolidationState) == 6
    assert {e.value for e in ConsolidationState} == {
        "volatile", "replaying_consolidating", "replaying_reconsolidating",
        "consolidated", "archived", "forgotten",
    }

def test_consolidation_transitions_count_and_t7p1():
    assert len(CONSOLIDATION_TRANSITIONS) == 10
    # T7-P1 + T8 share the (CONSOLIDATED, ARCHIVED) edge — design choice, locked here.
    assert (ConsolidationState.CONSOLIDATED, ConsolidationState.ARCHIVED) in CONSOLIDATION_TRANSITIONS
    assert (ConsolidationState.VOLATILE, ConsolidationState.FORGOTTEN) not in CONSOLIDATION_TRANSITIONS
    assert (ConsolidationState.VOLATILE, ConsolidationState.CONSOLIDATED) not in CONSOLIDATION_TRANSITIONS

def test_edge_kind_fourteen():
    assert len(EdgeKind) == 14
    assert EdgeKind.MAY_OVERLAP_WITH.value == "may_overlap_with"
    assert EdgeKind.DERIVED_FROM.value == "derived_from"

def test_engram_retention_four():
    assert len(EngramRetentionMode) == 4
    assert {e.value for e in EngramRetentionMode} == {
        "legal_hold", "audit_retain", "redacted_retain", "crypto_erasure",
    }

def test_source_kind_six():
    assert len(SourceKind) == 6

def test_ingest_policy_four():
    assert len(IngestPolicy) == 4

def test_review_status_five():
    assert len(ReviewStatus) == 5

def test_provenance_five():
    assert len(StatementProvenance) == 5
    assert StatementProvenance.CONSOLIDATION_ABSTRACT.value == "consolidation_abstract"

def test_evidence_status_three():
    assert {e.value for e in EvidenceStatus} == {"active", "redacted", "erased"}

def test_anchor_kind_seven():
    assert len(AnchorKind) == 7

def test_container_kind_three():
    assert {e.value for e in ContainerKind} == {"persona", "common_ground", "knowledge_frontier"}

def test_build_policy_three():
    assert {e.value for e in BuildPolicy} == {"on_event", "sleep", "manual"}

def test_str_enum_string_round_trip():
    """StrEnum guarantees: str(member) == member.value"""
    for cls in (Perspective, Modality, Polarity, ConsolidationState,
                EngramRetentionMode, SourceKind, IngestPolicy, IngestMode,
                PrivacyClass, StatementProvenance, ReviewStatus, EvidenceStatus,
                ContainerKind, EdgeKind, AnchorKind, BuildPolicy):
        for member in cls:
            assert str(member) == member.value
