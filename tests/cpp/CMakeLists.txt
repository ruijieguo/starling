include(FetchContent)
if(DEFINED FETCHCONTENT_SOURCE_DIR_GOOGLETEST)
    message(STATUS "Starling dependency GoogleTest: local source ${FETCHCONTENT_SOURCE_DIR_GOOGLETEST}")
else()
    message(STATUS "Starling dependency GoogleTest: FetchContent network fallback")
endif()
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.15.2
)
FetchContent_MakeAvailable(googletest)

# GoogleTest 1.15.2's gtest-printers.h emits an implicit char8_t -> char32_t
# conversion that Apple Clang 21+ flags under -Wcharacter-conversion. The
# warning is upstream and harmless; suppress it on gtest's own targets so our
# own -Werror build stays clean. Remove once we bump GoogleTest past the fix.
foreach(_gt_target IN ITEMS gtest gtest_main gmock gmock_main)
    if(TARGET ${_gt_target})
        target_compile_options(${_gt_target} PRIVATE -Wno-character-conversion)
    endif()
endforeach()

add_executable(starling_tests
    test_smoke.cpp
    test_profile_capability.cpp
    test_runtime_health.cpp
    test_preflight.cpp
    test_final_query_assertion.cpp
    test_canonicalize.cpp
    test_schema_enums.cpp
    test_statement_enums.cpp
    test_sqlite_link.cpp
    test_migration_runner.cpp
    test_migration_0003.cpp
    test_connection.cpp
    test_idempotency_key.cpp
    test_outbox_writer.cpp
    test_consumer_state.cpp
    test_outbox_dispatcher.cpp
    test_pipeline_ledger.cpp
    test_sqlite_adapter.cpp
    test_engram_content_hash.cpp
    test_ingest_policy_resolver.cpp
    test_evidence_validator.cpp
    test_engram_store.cpp
    test_bus_append_evidence.cpp
    test_extraction_span_key.cpp
    test_extracted_statement.cpp
    test_fake_llm_adapter.cpp
    test_json_parser.cpp
    test_statement_validator.cpp
    test_statement_writer.cpp
    test_statement_writer_interval.cpp
    test_normalized_interval.cpp
    test_canonical_scope.cpp
    test_conflict_key.cpp
    test_bus_statement_write.cpp
    test_extractor_orchestrator.cpp
    test_conflict_probe_indices.cpp
    test_conflict_probe_scan.cpp
    test_bus_write_conflict.cpp
    test_bus_write_supersedes.cpp
    test_basic_retrieve_index.cpp
    test_recalled_window_bucket.cpp
    test_basic_retriever_filter_predicates.cpp
    test_basic_retriever_multi_holder_reject.cpp
    test_basic_retriever_recalled_emit.cpp
    test_basic_retriever_frontier_filter.cpp
    test_mark_evidence_erased.cpp
    test_openai_adapter.cpp
    test_anthropic_adapter.cpp
    test_http_post_json.cpp
    test_statement_writer_derived_from.cpp
    test_uuid5.cpp
    test_alias_normalizer.cpp
    test_cognizer_types.cpp
    test_cognizer_hub_register.cpp
    test_cognizer_relations.cpp
    test_knowledge_frontier_record.cpp
    test_knowledge_frontier_visible.cpp
    test_conflict_key_unique.cpp
    test_conflict_key_backfill.cpp
    test_tom_engine_perspective.cpp
    test_nesting_depth_writer.cpp
    test_rate_limiter_tom.cpp
    test_depth_estimator_cache.cpp
    test_mentalizing.cpp
    test_belief_tracker.cpp
    test_forgetting_curve.cpp
    test_swr_sampler.cpp
    test_consolidation_compress.cpp
    test_consolidation_abstract_reinforce.cpp
    test_consolidation_decay.cpp
    test_consolidation_reconcile.cpp
    test_replay_scheduler.cpp
    test_plastic_window.cpp
    test_arbitration_mild.cpp
    test_arbitration_severe.cpp
    test_reconsolidation_engine.cpp
    test_persona_container.cpp
    test_common_ground_container.cpp
    test_common_ground_writer.cpp
    test_common_ground_subscriber.cpp
    test_projection_incremental.cpp
    test_projection_repair_guard.cpp
    test_subscriber_pump.cpp
    test_vector_math.cpp
    test_pattern_separator.cpp
    test_sqlite_blob_vector_index.cpp
    test_stub_embedding_adapter.cpp
    test_openai_embedding_adapter.cpp
    test_embedding_worker.cpp
    test_semantic_retriever.cpp
    test_proj_vector_payload.cpp
    test_vector_repair_guard.cpp
    test_vector_capability.cpp
    test_affect_vector.cpp
    test_affect_replay_weight.cpp
    test_action_guard.cpp
    test_commitment_engine.cpp
    test_commitment_protection_decay.cpp
    test_commitment_tenant_isolation.cpp
    test_trigger.cpp
    test_policy_engine_post_write.cpp
    test_policy_engine_tick.cpp
    test_policy_engine_subscriber.cpp
    test_pattern_completor.cpp
    test_persona_read.cpp
    test_common_ground_read.cpp
    test_commitment_pending.cpp
    test_persistence_stmt.cpp
    test_working_set.cpp
    test_memory_ops.cpp
    test_affect_reranker.cpp
    test_abstention_gate.cpp
    test_context_pack.cpp
    test_retrieval_planner.cpp
    test_tom_second_order.cpp
    test_store_foundation.cpp
    test_statement_store.cpp
    test_meta_store.cpp
    test_occurred_modality.cpp
    test_episodic_event_store.cpp
    test_episodic_extractor.cpp
    test_perception_state_store.cpp
)
target_include_directories(starling_tests BEFORE PRIVATE
    "${gtest_SOURCE_DIR}/include"
    "${gtest_SOURCE_DIR}")
target_link_libraries(starling_tests PRIVATE starling_core starling_testing_marker GTest::gtest_main)

# P3.b1 phase 5: ZvecVectorIndex parity 测试(仅 STARLING_VECTOR_ZVEC=ON)。link 经
# starling_core PUBLIC zvec_backend 传递(force_load plugins + main + 系统框架)。
if(STARLING_VECTOR_ZVEC)
    target_sources(starling_tests PRIVATE test_zvec_vector_index.cpp)
endif()

include(GoogleTest)
gtest_discover_tests(starling_tests)
