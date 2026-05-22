def test_profile_capability_defaults_fail_closed(core):
    cap = core.ProfileCapability()
    assert cap.profile_name == ""
    assert cap.relational_backend == ""
    assert cap.vector_backend == ""
    assert cap.graph_backend == ""
    assert cap.c_plus_plus_core is False
    assert cap.cross_partition_transaction is False
    assert cap.transactional_outbox is False
    assert cap.consumer_checkpoint is False
    assert cap.tenant_isolation == ""
    assert cap.engram_per_record_key is False
    assert cap.engram_refcount is False
    assert cap.projection_index_supported is False
    assert cap.dimension_versions_supported is False
    assert cap.testing_helper_marker is False


def test_profile_capability_local_store_construct(core):
    # Each same-typed adjacent group uses distinct values so a silent
    # reordering of lambda params vs. py::arg(...) chain in module.cpp
    # shows up here as a test failure (the kw-only binding is name-fragile
    # only across same-typed adjacent slots).
    cap = core.ProfileCapability(
        profile_name="local-store",
        relational_backend="REL",
        vector_backend="VEC",
        graph_backend="GRA",
        c_plus_plus_core=True,
        cross_partition_transaction=True,
        transactional_outbox=False,
        consumer_checkpoint=True,
        tenant_isolation="storage_enforced",
        engram_per_record_key=True,
        engram_refcount=False,
        projection_index_supported=False,
        dimension_versions_supported=True,
        testing_helper_marker=True,
    )
    assert cap.profile_name == "local-store"
    assert cap.relational_backend == "REL"
    assert cap.vector_backend == "VEC"
    assert cap.graph_backend == "GRA"
    assert cap.c_plus_plus_core is True
    assert cap.cross_partition_transaction is True
    assert cap.transactional_outbox is False
    assert cap.consumer_checkpoint is True
    assert cap.tenant_isolation == "storage_enforced"
    assert cap.engram_per_record_key is True
    assert cap.engram_refcount is False
    assert cap.projection_index_supported is False
    assert cap.dimension_versions_supported is True
    assert cap.testing_helper_marker is True
