def _local_store(core):
    return core.ProfileCapability(
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


def test_preflight_full_capability_returns_ready(core):
    cap = _local_store(core)
    result = core.preflight(cap, [
        "transactional_outbox",
        "consumer_checkpoint",
        "engram_per_record_key",
        "c_plus_plus_core",
        "tenant_isolation_storage_enforced",
        "cross_partition_transaction",
    ])
    assert result.status == core.PreflightStatus.READY
    assert result.missing == []


def test_preflight_missing_outbox_returns_unready(core):
    cap = _local_store(core)
    cap.transactional_outbox = False
    result = core.preflight(cap, ["transactional_outbox"])
    assert result.status == core.PreflightStatus.UNREADY
    assert result.missing == ["transactional_outbox"]


def test_preflight_app_filter_blocks_storage_enforced(core):
    cap = _local_store(core)
    cap.tenant_isolation = "app_filter"
    result = core.preflight(cap, ["tenant_isolation_storage_enforced"])
    assert result.status == core.PreflightStatus.UNREADY
    assert result.missing == ["tenant_isolation_storage_enforced"]


def test_preflight_unknown_capability_treated_as_missing(core):
    cap = _local_store(core)
    result = core.preflight(cap, ["totally_made_up_capability"])
    assert result.status == core.PreflightStatus.UNREADY
    assert result.missing == ["totally_made_up_capability"]
