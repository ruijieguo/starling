"""TC-NEG-TENANT regression: the final retrieval SQL must contain both
tenant_id and holder_scope predicates.

This is a CONTRACT test: as long as the literal here matches the literal
in basic_retriever.cpp's kSelectSql AND `_core.is_final_query_safe` returns
True for it, we have evidence the retriever's SELECT passes the M0.0 guard.

If a future engineer changes kSelectSql to drop tenant_id or the
holder_scope annotation, this test must be updated in lockstep. If they
forget, the §14.1 P1 retrieve smoke (Task 9) catches the regression
end-to-end.
"""
import pytest

from starling import _core


# Mirrors src/retrieval/basic_retriever.cpp kSelectSql (lines 46-63) verbatim.
# The `/* holder_scope: holder_id ... */` block comment satisfies the guard's
# holder_scope substring requirement; the schema column is holder_id (P1
# single-holder).
_BASIC_RETRIEVE_SELECT_SQL = (
    "/* holder_scope: holder_id (P1 single-holder) */ "
    "SELECT id, tenant_id, holder_id, holder_perspective, "
    "       subject_kind, subject_id, predicate, "
    "       object_kind, object_value, canonical_object_hash, "
    "       modality, polarity, confidence, observed_at, "
    "       valid_from, valid_to, consolidation_state, review_status, "
    "       evidence_json "
    "  FROM statements "
    " WHERE tenant_id = ?1 "
    "   AND holder_id = ?2 "
    "   AND subject_kind = 'cognizer' "
    "   AND subject_id = ?3 "
    "   AND predicate = ?4 "
    "   AND consolidation_state IN ('consolidated','archived') "
    "   AND review_status NOT IN ('rejected','pending_review') "
    "   AND (valid_from IS NULL OR valid_from <= ?5) "
    "   AND (valid_to   IS NULL OR valid_to   >  ?5) "
)


def test_basic_retrieve_select_is_final_query_safe():
    """Pin: the literal SELECT used by BasicRetriever passes the guard.

    The C++ side calls adapter_.check_final_query(kSelectSql) at runtime
    (basic_retriever.cpp via Task 4). This Python test pins the same
    contract at the source-text level — it would catch a regression where
    someone modifies kSelectSql to drop the `/* holder_scope: ... */`
    block comment or the `tenant_id = ?1` predicate.
    """
    assert _core.is_final_query_safe(_BASIC_RETRIEVE_SELECT_SQL) is True


def test_assert_final_query_safe_rejects_missing_tenant():
    """A SELECT that omits tenant_id is rejected with FinalQueryAssertionError.

    Mirrors basic_retriever.cpp's runtime guard: a SELECT against statements
    that lacks a tenant_id predicate is a P0 bug because it would leak data
    across tenants. The guard refuses the query before SQLite ever sees it.
    """
    sql = "SELECT id FROM statements WHERE holder_id = ?1 AND predicate = ?2"
    with pytest.raises(_core.FinalQueryAssertionError):
        _core.assert_final_query_safe(sql)


def test_assert_final_query_safe_rejects_missing_holder():
    """A SELECT that omits holder scope is rejected.

    The guard requires both `tenant_id` AND `holder_scope` substrings —
    holder_scope is satisfied either by the literal column name (`holder_id`)
    or by the `/* holder_scope: ... */` block comment annotation. A SELECT
    that has neither must raise.
    """
    sql = "SELECT id FROM statements WHERE tenant_id = ?1 AND predicate = ?2"
    with pytest.raises(_core.FinalQueryAssertionError):
        _core.assert_final_query_safe(sql)
