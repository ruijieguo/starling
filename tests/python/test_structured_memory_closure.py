"""结构化记忆闭环绑定 RED 测试：核心语义必须由 C++ 提供。"""

from starling import _core


def test_native_catalog_and_relation_family_are_exposed():
    catalog = _core.claim_predicate_catalog()
    assert catalog.version
    assert any(spec.name == "owns" for spec in catalog.predicates)


def test_native_failure_receipt_is_exposed():
    assert hasattr(_core, "memory_remember_commit")
    assert hasattr(_core, "claim_extraction_receipt")
