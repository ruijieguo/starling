import pytest


def test_accepts_query_with_both_predicates(core):
    core.assert_final_query_safe(
        "SELECT id FROM statements WHERE tenant_id = ? AND holder_scope = ?"
    )
    assert core.is_final_query_safe(
        "SELECT id FROM statements WHERE tenant_id = ? AND holder_scope = ?"
    )


def test_rejects_missing_tenant_id(core):
    with pytest.raises(core.FinalQueryAssertionError) as exc:
        core.assert_final_query_safe(
            "SELECT id FROM statements WHERE holder_scope = ?"
        )
    assert "tenant_id" in str(exc.value)


def test_rejects_missing_holder_scope(core):
    with pytest.raises(core.FinalQueryAssertionError) as exc:
        core.assert_final_query_safe(
            "SELECT id FROM statements WHERE tenant_id = ?"
        )
    assert "holder_scope" in str(exc.value)


def test_rejects_only_in_comment(core):
    with pytest.raises(core.FinalQueryAssertionError):
        core.assert_final_query_safe(
            "SELECT * FROM statements -- tenant_id and holder_scope mandatory"
        )


def test_is_case_insensitive(core):
    assert core.is_final_query_safe(
        "select id from statements where Tenant_Id=? AND Holder_Scope=?"
    )
