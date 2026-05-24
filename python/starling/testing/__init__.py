"""Starling testing helpers — never import from production code paths."""
from starling._core import testing as _core_testing


def marker_loaded() -> bool:
    return _core_testing.marker_loaded()


def mark_consolidated(adapter, stmt_id: str, tenant_id: str) -> bool:
    """VOLATILE -> CONSOLIDATED dev-only state transition.

    Flips a Statement row's consolidation_state from 'volatile' to
    'consolidated' and writes a 'testing.mark_consolidated' audit event in
    the same transaction. Idempotent: returns False if the row was already
    consolidated, missing, or in any non-volatile state (no audit row is
    written in that case, so replays don't pollute bus_events).

    Used by TC-NEW-CONFLICT-SEVERE (M0.5 Task 10) to seed S_old in the
    CONSOLIDATED state before exercising Bus::write through the §15.3.4
    atomic SUPERSEDES path. Production preflight + the CI static scan reject
    any prod entrypoint that imports starling.testing — so this can never
    leak into real ingest.
    """
    return _core_testing.mark_consolidated(adapter, stmt_id, tenant_id)


def mark_evidence_erased(adapter, engram_id: str, tenant_id: str,
                         erased_at_iso8601: str) -> bool:
    """Flip engrams.erased_at from NULL to ISO8601 timestamp.

    Used by the M0.6 13_retrieval.md evidence-erased negative test
    (the BasicRetriever filter must drop engrams with non-NULL erased_at).
    Writes a 'testing.mark_evidence_erased' audit event in the same
    transaction. Idempotent: returns False on missing row or already-erased
    row (no audit row written in those cases, so replays don't pollute
    bus_events). Production preflight + the CI static scan reject any prod
    entrypoint that imports starling.testing — so this can never leak into
    real ingest.
    """
    return _core_testing.mark_evidence_erased(
        adapter, engram_id, tenant_id, erased_at_iso8601)


def relax_preflight_for_m0_2() -> tuple[str, ...]:
    """Trim engram_per_record_key + testing_helper_marker from LOCAL_STORE_REQUIRED.

    Required by M0.2 acceptance only. M0.3 ships a `null_kms` placeholder
    (identity cipher, key_ref=NULL); real per-record AES-256-GCM + KMS
    lands in M0.4, at which point `engram_per_record_key=true` and this
    helper plus `relax_preflight_for_m0_3` can both be deleted. The CI
    static scan (added in M0.0) refuses to merge prod entrypoints that
    import starling.testing — so this can never leak.

    Returns the original tuple so the caller can restore it in tearDown.
    """
    from starling import runtime as _r
    original = _r.LOCAL_STORE_REQUIRED
    _r.LOCAL_STORE_REQUIRED = tuple(
        c for c in original
        if c not in {"engram_per_record_key", "testing_helper_marker"}
    )
    return original


def relax_preflight_for_m0_3() -> tuple[str, ...]:
    """M0.3 acceptance helper. Same surgery as relax_preflight_for_m0_2 (the
    `engram_per_record_key` capability is still deferred to M0.4 + KMS). Kept
    as a separate function so the M0.3 acceptance test names what it's
    relaxing. Delete both helpers when M0.4 lands the real capability.

    Returns the original LOCAL_STORE_REQUIRED tuple so the caller can restore
    it in tearDown.
    """
    return relax_preflight_for_m0_2()


__all__ = [
    "marker_loaded",
    "mark_consolidated",
    "mark_evidence_erased",
    "relax_preflight_for_m0_2",
    "relax_preflight_for_m0_3",
]
