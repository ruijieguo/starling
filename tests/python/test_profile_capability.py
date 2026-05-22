def test_profile_capability_defaults_fail_closed(core):
    cap = core.ProfileCapability()
    assert cap.profile_name == ""
    assert cap.cross_partition_transaction is False
    assert cap.transactional_outbox is False
    assert cap.tenant_isolation == ""


def test_profile_capability_local_store_construct(core):
    cap = core.ProfileCapability(
        profile_name="local-store",
        relational_backend="seekdb",
        vector_backend="seekdb",
        graph_backend="ladybugdb",
        c_plus_plus_core=True,
        cross_partition_transaction=True,
        transactional_outbox=True,
        consumer_checkpoint=True,
        tenant_isolation="storage_enforced",
        engram_per_record_key=True,
        engram_refcount=True,
        projection_index_supported=False,
        dimension_versions_supported=False,
        testing_helper_marker=True,
    )
    assert cap.profile_name == "local-store"
    assert cap.tenant_isolation == "storage_enforced"
