// bind_05_retrieval — M0.6: BasicRetriever + receipt/row DTOs
// Split verbatim from bindings/python/module.cpp (original lines 501-584).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include "starling/retrieval/basic_retriever.hpp"
#include "starling/retrieval/retrieval_planner.hpp"
#include "starling/retrieval/source_retriever.hpp"
#include "starling/retrieval/source_selection.hpp"
#include "starling/retrieval/evidence_answer.hpp"
#include "starling/retrieval/structured_claim_retriever.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/store/sqlite_meta_store.hpp"

namespace starling::bindings {

void bind_05_retrieval(pybind11::module_& m) {
    using namespace pybind11::literals;
    using SelectionResult=starling::retrieval::SourceSelectionResult;
    py::class_<SelectionResult>(m,"SourceSelectionResult")
        .def_readonly("ok",&SelectionResult::ok)
        .def_readonly("invoked",&SelectionResult::invoked)
        .def_readonly("budget_unknown",&SelectionResult::budget_unknown)
        .def_readonly("error",&SelectionResult::error)
        .def_readonly("prompt",&SelectionResult::prompt)
        .def_readonly("recall_json",&SelectionResult::recall_json)
        .def_readonly("response",&SelectionResult::response);
    m.def("collect_selection_pool",&starling::retrieval::collect_selection_pool,
          py::arg("observer"),py::arg("query"),py::call_guard<py::gil_scoped_release>());
    m.def("source_selection_prompt",&starling::retrieval::source_selection_prompt,
          py::arg("question"),py::arg("pool_json"),py::arg("k")=20,py::arg("max_context_bytes")=8000);
    m.def("apply_source_selection",&starling::retrieval::apply_source_selection,
          py::arg("question"),py::arg("pool_json"),py::arg("raw_plan"),py::arg("k")=20,py::arg("max_context_bytes")=8000);
    m.def("select_sources",&starling::retrieval::select_sources,
          py::arg("question"),py::arg("pool_json"),py::arg("llm"),py::arg("k")=20,py::arg("max_context_bytes")=8000,
          py::call_guard<py::gil_scoped_release>());
    m.def("select_sources_structured",&starling::retrieval::select_sources_structured,
          py::arg("question"),py::arg("pool_json"),py::arg("llm"),py::arg("k")=20,py::arg("max_context_bytes")=8000,
          py::call_guard<py::gil_scoped_release>());
    m.def("grounded_memory_answer_packet", &starling::retrieval::grounded_memory_answer_packet,
          py::arg("question"), py::arg("recall_json"));
    m.def("grounded_memory_answer_prompt", &starling::retrieval::grounded_memory_answer_prompt,
          py::arg("question"), py::arg("recall_json"));
    m.def("compact_grounded_memory_answer_prompt",
          &starling::retrieval::compact_grounded_memory_answer_prompt,
          py::arg("question"), py::arg("recall_json"));

    using EvidenceResult=starling::retrieval::EvidenceAnswerResult;
    py::class_<EvidenceResult>(m,"EvidenceAnswerResult")
        .def_readonly("evidence_response",&EvidenceResult::evidence_response)
        .def_readonly("answer_response",&EvidenceResult::answer_response)
        .def_readonly("evidence_prompt",&EvidenceResult::evidence_prompt)
        .def_readonly("answer_prompt",&EvidenceResult::answer_prompt)
        .def_readonly("validation_json",&EvidenceResult::validation_json)
        .def_readonly("fallback",&EvidenceResult::fallback)
        .def_readonly("budget_unknown",&EvidenceResult::budget_unknown)
        .def_readonly("fallback_reason",&EvidenceResult::fallback_reason);
    m.def("synthesis_source_answer_packet",&starling::retrieval::synthesis_source_answer_packet,
          py::arg("question"),py::arg("source_block"));
    m.def("synthesis_source_answer_prompt",&starling::retrieval::synthesis_source_answer_prompt,
          py::arg("question"),py::arg("source_block"));
    m.def("source_answer_ablation_prompt",&starling::retrieval::source_answer_ablation_prompt,
          py::arg("question"),py::arg("source_block"),py::arg("representation"),py::arg("guidance"));
    m.def("source_evidence_prompt",&starling::retrieval::source_evidence_prompt,
          py::arg("question"),py::arg("source_block"));
    m.def("verify_source_evidence",&starling::retrieval::verify_source_evidence,
          py::arg("source_block"),py::arg("raw_plan"));
    m.def("evidence_answer_prompt",&starling::retrieval::evidence_answer_prompt,
          py::arg("question"),py::arg("source_block"),py::arg("raw_plan"));
    m.def("answer_with_evidence",&starling::retrieval::answer_with_evidence,
          py::arg("question"),py::arg("source_block"),py::arg("llm"),
          py::call_guard<py::gil_scoped_release>());

    m.def("grounded_source_answer_prompt", &starling::retrieval::grounded_source_answer_prompt,
          py::arg("question"), py::arg("source_block"));
    m.def("compact_source_answer_prompt", &starling::retrieval::compact_source_answer_prompt,
          py::arg("question"), py::arg("source_block"));

    m.def("retain_source_turns", &starling::retrieval::retain_source_turns,
          py::arg("adapter"), py::arg("tenant_id"), py::arg("allowed_holders"),
          py::arg("turns_json"), py::arg("created_at"), py::arg("preserve_invalid_time")=false,
          py::call_guard<py::gil_scoped_release>());
    m.def("observer_holders", &starling::retrieval::observer_holders,
          py::arg("adapter"), py::arg("tenant_id"),
          py::call_guard<py::gil_scoped_release>());
    py::class_<starling::retrieval::ObserverQuery>(m, "ObserverQuery")
        .def(py::init<>())
        .def_readwrite("tenant_id", &starling::retrieval::ObserverQuery::tenant_id)
        .def_readwrite("allowed_holders", &starling::retrieval::ObserverQuery::allowed_holders)
        .def_readwrite("question", &starling::retrieval::ObserverQuery::question)
        .def_readwrite("as_of_iso8601", &starling::retrieval::ObserverQuery::as_of_iso8601)
        .def_readwrite("k", &starling::retrieval::ObserverQuery::k)
        .def_readwrite("max_context_bytes", &starling::retrieval::ObserverQuery::max_context_bytes)
        .def_readwrite("mode", &starling::retrieval::ObserverQuery::mode)
        .def_readwrite("source_strategy", &starling::retrieval::ObserverQuery::source_strategy)
        .def_readwrite("source_seed_k", &starling::retrieval::ObserverQuery::source_seed_k)
        .def_readwrite("source_seed_max_context_bytes", &starling::retrieval::ObserverQuery::source_seed_max_context_bytes)
        .def_readwrite("source_dialogue_radius", &starling::retrieval::ObserverQuery::source_dialogue_radius)
        .def_readwrite("min_source_items", &starling::retrieval::ObserverQuery::min_source_items)
        .def_readwrite("include_unknown_time", &starling::retrieval::ObserverQuery::include_unknown_time);
    py::class_<starling::retrieval::ObserverRetriever>(m, "ObserverRetriever")
        .def(py::init<starling::persistence::SqliteAdapter&,
                      starling::retrieval::SemanticRetriever&>(),
             py::keep_alive<1, 2>(), py::keep_alive<1, 3>())
        .def("run", &starling::retrieval::ObserverRetriever::run,
             py::arg("query"), py::call_guard<py::gil_scoped_release>());

    // Low-level tenant-scoped storage access for offline native rendering.
    // Product visibility/eligibility decisions remain in the native retrievers.
    m.def("get_statement_row", [](starling::persistence::SqliteAdapter& adapter,
                                   const std::string& tenant_id, const std::string& statement_id) {
        return starling::store::SqliteMetaStore(adapter.connection()).get_statement(statement_id, tenant_id);
    }, py::arg("adapter"), py::arg("tenant_id"), py::arg("statement_id"));

    // ----- M0.6: retrieval bindings -----

    py::enum_<starling::retrieval::QueryIntent>(m, "QueryIntent")
        .value("FACT_LOOKUP",     starling::retrieval::QueryIntent::FACT_LOOKUP)
        .value("BELIEF_OF_OTHER", starling::retrieval::QueryIntent::BELIEF_OF_OTHER)
        .value("META_BELIEF",     starling::retrieval::QueryIntent::META_BELIEF)
        .value("HISTORY",         starling::retrieval::QueryIntent::HISTORY)
        .value("COMMITMENT_DUE",  starling::retrieval::QueryIntent::COMMITMENT_DUE)
        .value("PREFERENCE",      starling::retrieval::QueryIntent::PREFERENCE)
        .value("NORM_LOOKUP",     starling::retrieval::QueryIntent::NORM_LOOKUP)
        .value("COMMON_GROUND",   starling::retrieval::QueryIntent::COMMON_GROUND)
        .value("ABSTAIN_CHECK",   starling::retrieval::QueryIntent::ABSTAIN_CHECK)
        .export_values();

    py::enum_<starling::retrieval::Sufficiency>(m, "Sufficiency")
        .value("SUFFICIENT",   starling::retrieval::Sufficiency::SUFFICIENT)
        .value("MISSING_INFO", starling::retrieval::Sufficiency::MISSING_INFO)
        .value("NEEDS_RAW",    starling::retrieval::Sufficiency::NEEDS_RAW)
        .value("ABSTAINED",    starling::retrieval::Sufficiency::ABSTAINED)
        .export_values();

    py::class_<starling::retrieval::FilterApplied>(m, "FilterApplied")
        .def_readonly("name",  &starling::retrieval::FilterApplied::name)
        .def_readonly("value", &starling::retrieval::FilterApplied::value);

    py::class_<starling::retrieval::RetrievalReceipt::CandidateCounts>(
        m, "RetrievalCandidateCounts")
        .def_readonly("fetched",
                      &starling::retrieval::RetrievalReceipt::CandidateCounts::fetched)
        .def_readonly("returned",
                      &starling::retrieval::RetrievalReceipt::CandidateCounts::returned)
        .def_readonly("dropped_by_review",
                      &starling::retrieval::RetrievalReceipt::CandidateCounts::dropped_by_review)
        .def_readonly("dropped_by_state",
                      &starling::retrieval::RetrievalReceipt::CandidateCounts::dropped_by_state)
        .def_readonly("dropped_by_time_anchor",
                      &starling::retrieval::RetrievalReceipt::CandidateCounts::dropped_by_time_anchor)
        .def_readonly("dropped_by_evidence_erasure",
                      &starling::retrieval::RetrievalReceipt::CandidateCounts::dropped_by_evidence_erasure)
        .def_readonly("dropped_by_claim_evidence",
                      &starling::retrieval::RetrievalReceipt::CandidateCounts::dropped_by_claim_evidence);

    // ----- P3.a1: planner DTO 前置(receipt 字段引用它们) -----
    py::class_<starling::retrieval::ScoreRow>(m, "ScoreRow")
        .def_readonly("statement_id", &starling::retrieval::ScoreRow::statement_id)
        .def_readonly("base",         &starling::retrieval::ScoreRow::base)
        .def_readonly("recency",      &starling::retrieval::ScoreRow::recency)
        .def_readonly("salience",     &starling::retrieval::ScoreRow::salience)
        .def_readonly("activation",   &starling::retrieval::ScoreRow::activation)
        .def_readonly("affect_consistency",
                      &starling::retrieval::ScoreRow::affect_consistency)
        .def_readonly("temporal_penalty",
                      &starling::retrieval::ScoreRow::temporal_penalty)
        .def_readonly("final_score",  &starling::retrieval::ScoreRow::final_score);

    py::class_<starling::retrieval::RetrievalScopeStep>(m, "RetrievalScopeStep")
        .def_readonly("scope",          &starling::retrieval::RetrievalScopeStep::scope)
        .def_readonly("holder_scope",   &starling::retrieval::RetrievalScopeStep::holder_scope)
        .def_readonly("filters",        &starling::retrieval::RetrievalScopeStep::filters)
        .def_readonly("max_candidates", &starling::retrieval::RetrievalScopeStep::max_candidates);

    py::class_<starling::retrieval::RetrievalScopePlan>(m, "RetrievalScopePlan")
        .def_readonly("plan_id",      &starling::retrieval::RetrievalScopePlan::plan_id)
        .def_readonly("mode",         &starling::retrieval::RetrievalScopePlan::mode)
        .def_readonly("steps",        &starling::retrieval::RetrievalScopePlan::steps)
        .def_readonly("stop_policy",  &starling::retrieval::RetrievalScopePlan::stop_policy)
        .def_readonly("merge_policy", &starling::retrieval::RetrievalScopePlan::merge_policy);

    py::class_<starling::retrieval::RetrievalReceipt::PlanStepTrace>(m, "PlanStepTrace")
        .def_readonly("step",   &starling::retrieval::RetrievalReceipt::PlanStepTrace::step)
        .def_readonly("detail", &starling::retrieval::RetrievalReceipt::PlanStepTrace::detail);

    py::class_<starling::retrieval::RetrievalReceipt::SkippedScope>(m, "SkippedScope")
        .def_readonly("scope",  &starling::retrieval::RetrievalReceipt::SkippedScope::scope)
        .def_readonly("reason", &starling::retrieval::RetrievalReceipt::SkippedScope::reason);

    py::class_<starling::retrieval::RetrievalReceipt::DegradedPath>(m, "DegradedPathInfo")
        .def_readonly("path",     &starling::retrieval::RetrievalReceipt::DegradedPath::path)
        .def_readonly("reason",   &starling::retrieval::RetrievalReceipt::DegradedPath::reason)
        .def_readonly("fallback", &starling::retrieval::RetrievalReceipt::DegradedPath::fallback);

    py::class_<starling::retrieval::RetrievalReceipt>(m, "RetrievalReceipt")
        .def_readonly("temporal_evidence_json", &starling::retrieval::RetrievalReceipt::temporal_evidence_json)
        .def_readonly("evidence_links_json", &starling::retrieval::RetrievalReceipt::evidence_links_json)
        .def_readonly("claim_exclusion_counts_json", &starling::retrieval::RetrievalReceipt::claim_exclusion_counts_json)
        .def_readonly("source_time_fallback_count", &starling::retrieval::RetrievalReceipt::source_time_fallback_count)
        .def_readonly("trace_id",              &starling::retrieval::RetrievalReceipt::trace_id)
        .def_readonly("query_id",              &starling::retrieval::RetrievalReceipt::query_id)
        .def_readonly("filters_applied",       &starling::retrieval::RetrievalReceipt::filters_applied)
        .def_readonly("candidate_counts",      &starling::retrieval::RetrievalReceipt::candidate_counts)
        .def_readonly("evidence_erased_count", &starling::retrieval::RetrievalReceipt::evidence_erased_count)
        .def_readonly("frontier_masked_count", &starling::retrieval::RetrievalReceipt::frontier_masked_count)
        .def_readonly("sufficiency_status",    &starling::retrieval::RetrievalReceipt::sufficiency_status)
        // P3.a1 planner 字段(纯增量;P1 路径默认空)。
        .def_readonly("querier",               &starling::retrieval::RetrievalReceipt::querier)
        .def_readonly("perspective",           &starling::retrieval::RetrievalReceipt::perspective)
        .def_readonly("intent_name",           &starling::retrieval::RetrievalReceipt::intent_name)
        .def_readonly("runtime_health",        &starling::retrieval::RetrievalReceipt::runtime_health)
        .def_readonly("trace_retention",       &starling::retrieval::RetrievalReceipt::trace_retention)
        .def_readonly("scope_plan",            &starling::retrieval::RetrievalReceipt::scope_plan)
        .def_readonly("plan_steps",            &starling::retrieval::RetrievalReceipt::plan_steps)
        .def_readonly("skipped_scopes",        &starling::retrieval::RetrievalReceipt::skipped_scopes)
        .def_readonly("stop_reason",           &starling::retrieval::RetrievalReceipt::stop_reason)
        .def_readonly("scopes_searched",       &starling::retrieval::RetrievalReceipt::scopes_searched)
        .def_readonly("score_breakdown",       &starling::retrieval::RetrievalReceipt::score_breakdown)
        .def_readonly("degraded_paths",        &starling::retrieval::RetrievalReceipt::degraded_paths)
        .def_readonly("abstention_reason",     &starling::retrieval::RetrievalReceipt::abstention_reason)
        .def_readonly("emitted_events",        &starling::retrieval::RetrievalReceipt::emitted_events)
        .def_readonly("projection_lag_events", &starling::retrieval::RetrievalReceipt::projection_lag_events);

    py::class_<starling::retrieval::StatementRow>(m, "StatementRow")
        .def_readonly("id",                     &starling::retrieval::StatementRow::id)
        .def_readonly("tenant_id",              &starling::retrieval::StatementRow::tenant_id)
        .def_readonly("holder_id",              &starling::retrieval::StatementRow::holder_id)
        .def_readonly("holder_perspective",     &starling::retrieval::StatementRow::holder_perspective)
        .def_readonly("subject_kind",           &starling::retrieval::StatementRow::subject_kind)
        .def_readonly("subject_id",             &starling::retrieval::StatementRow::subject_id)
        .def_readonly("predicate",              &starling::retrieval::StatementRow::predicate)
        .def_readonly("object_kind",            &starling::retrieval::StatementRow::object_kind)
        .def_readonly("object_value",           &starling::retrieval::StatementRow::object_value)
        .def_readonly("canonical_object_hash",  &starling::retrieval::StatementRow::canonical_object_hash)
        .def_readonly("modality",               &starling::retrieval::StatementRow::modality)
        .def_readonly("polarity",               &starling::retrieval::StatementRow::polarity)
        .def_readonly("confidence",             &starling::retrieval::StatementRow::confidence)
        .def_readonly("observed_at",            &starling::retrieval::StatementRow::observed_at)
        .def_readonly("valid_from",             &starling::retrieval::StatementRow::valid_from)
        .def_readonly("valid_to",               &starling::retrieval::StatementRow::valid_to)
        .def_readonly("consolidation_state",    &starling::retrieval::StatementRow::consolidation_state)
        .def_readonly("review_status",          &starling::retrieval::StatementRow::review_status)
        .def_readonly("evidence_json",          &starling::retrieval::StatementRow::evidence_json)
        .def_readonly("affect_json",            &starling::retrieval::StatementRow::affect_json)
        .def_readonly("semantic_claim_json", &starling::retrieval::StatementRow::semantic_claim_json)
        .def_readonly("source_spans_json", &starling::retrieval::StatementRow::source_spans_json);

    py::class_<starling::retrieval::BasicRetrieverParams>(m, "BasicRetrieverParams")
        .def(py::init<>())
        .def_readwrite("tenant_id",              &starling::retrieval::BasicRetrieverParams::tenant_id)
        .def_readwrite("holder_id",              &starling::retrieval::BasicRetrieverParams::holder_id)
        .def_readwrite("holder_perspective",     &starling::retrieval::BasicRetrieverParams::holder_perspective)
        .def_readwrite("intent",                 &starling::retrieval::BasicRetrieverParams::intent)
        .def_readwrite("subject_id",             &starling::retrieval::BasicRetrieverParams::subject_id)
        .def_readwrite("predicate",              &starling::retrieval::BasicRetrieverParams::predicate)
        .def_readwrite("as_of_iso8601",          &starling::retrieval::BasicRetrieverParams::as_of_iso8601)
        .def_readwrite("trace_id",               &starling::retrieval::BasicRetrieverParams::trace_id)
        .def_readwrite("query_id",               &starling::retrieval::BasicRetrieverParams::query_id)
        .def_readwrite("apply_frontier_filter",  &starling::retrieval::BasicRetrieverParams::apply_frontier_filter);

    py::class_<starling::retrieval::BasicRetrieveResult>(m, "BasicRetrieveResult")
        .def_readonly("rows",    &starling::retrieval::BasicRetrieveResult::rows)
        .def_readonly("receipt", &starling::retrieval::BasicRetrieveResult::receipt);

    py::class_<starling::retrieval::BasicRetriever>(m, "BasicRetriever")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("run", &starling::retrieval::BasicRetriever::run, py::arg("params"));

    // ----- P3.a1: RetrievalPlanner(7 步管线) -----
    py::enum_<starling::retrieval::ContextPackLabel>(m, "ContextPackLabel")
        .value("FACT",     starling::retrieval::ContextPackLabel::FACT)
        .value("BELIEF",   starling::retrieval::ContextPackLabel::BELIEF)
        .value("HEARSAY",  starling::retrieval::ContextPackLabel::HEARSAY)
        .value("INFERRED", starling::retrieval::ContextPackLabel::INFERRED)
        .value("COMMON",   starling::retrieval::ContextPackLabel::COMMON)
        .value("TODO",     starling::retrieval::ContextPackLabel::TODO)
        .value("CONFLICT", starling::retrieval::ContextPackLabel::CONFLICT)
        .value("ABSTAIN",  starling::retrieval::ContextPackLabel::ABSTAIN);

    {
        using namespace starling::retrieval;
        py::class_<TemporalEvidenceRequest>(m,"TemporalEvidenceRequest")
            .def(py::init<>())
            .def_readwrite("tenant_id",&TemporalEvidenceRequest::tenant_id)
            .def_readwrite("actor_id",&TemporalEvidenceRequest::actor_id)
            .def_readwrite("topic",&TemporalEvidenceRequest::topic)
            .def_readwrite("ordered_session_ids",&TemporalEvidenceRequest::ordered_session_ids)
            .def_readwrite("through_session_id",&TemporalEvidenceRequest::through_session_id)
            .def_readwrite("limit",&TemporalEvidenceRequest::limit);
        py::class_<TemporalEvidenceCandidate>(m,"TemporalEvidenceCandidate")
            .def(py::init<>()).def_readwrite("row",&TemporalEvidenceCandidate::row)
            .def_readwrite("score",&TemporalEvidenceCandidate::score);
        py::class_<TemporalEvidenceRef>(m,"TemporalEvidenceRef")
            .def_readonly("tenant_id",&TemporalEvidenceRef::tenant_id)
            .def_readonly("statement_id",&TemporalEvidenceRef::statement_id)
            .def_readonly("session_id",&TemporalEvidenceRef::session_id)
            .def_readonly("turn_index",&TemporalEvidenceRef::turn_index);
        py::class_<TemporalEvidenceView>(m,"TemporalEvidenceView")
            .def_readonly("sufficient",&TemporalEvidenceView::sufficient)
            .def_readonly("ambiguous",&TemporalEvidenceView::ambiguous)
            .def_readonly("insufficiency_reason",&TemporalEvidenceView::insufficiency_reason)
            .def_readonly("early",&TemporalEvidenceView::early)
            .def_readonly("late",&TemporalEvidenceView::late)
            .def_readonly("selected",&TemporalEvidenceView::selected)
            .def("to_json",&temporal_evidence_json);
        m.def("select_temporal_evidence",&select_temporal_evidence,py::arg("visible_candidates"),py::arg("request"));
        m.def("temporal_evidence_json",&temporal_evidence_json);

        py::class_<StructuredClaimRequest>(m, "StructuredClaimRequest")
            .def(py::init<>())
            .def_readwrite("tenant_id", &StructuredClaimRequest::tenant_id)
            .def_readwrite("holder_id", &StructuredClaimRequest::holder_id)
            .def_readwrite("subject_id", &StructuredClaimRequest::subject_id)
            .def_readwrite("predicate", &StructuredClaimRequest::predicate)
            .def_readwrite("topic", &StructuredClaimRequest::topic)
            .def_readwrite("as_of_iso8601", &StructuredClaimRequest::as_of_iso8601)
            .def_readwrite("limit", &StructuredClaimRequest::limit)
            .def_readwrite("temporal", &StructuredClaimRequest::temporal);
        py::class_<StructuredClaimView>(m, "StructuredClaimView")
            .def_readonly("selected", &StructuredClaimView::selected)
            .def_readonly("receipt_json", &StructuredClaimView::receipt_json)
            .def_readonly("sufficient", &StructuredClaimView::sufficient)
            .def_readonly("insufficiency_reason", &StructuredClaimView::insufficiency_reason)
            .def_readonly("early", &StructuredClaimView::early)
            .def_readonly("late", &StructuredClaimView::late)
            .def_readonly("input_candidates", &StructuredClaimView::input_candidates)
            .def_readonly("excluded_scope", &StructuredClaimView::excluded_scope)
            .def_readonly("excluded_invalid_evidence", &StructuredClaimView::excluded_invalid_evidence)
            .def_readonly("excluded_unknown_predicate", &StructuredClaimView::excluded_unknown_predicate)
            .def_readonly("excluded_missing_order", &StructuredClaimView::excluded_missing_order);
        m.def("select_structured_claims",
              [](starling::persistence::SqliteAdapter& adapter,
                 const std::vector<StatementRow>& candidates,
                 const StructuredClaimRequest& request) {
                  py::gil_scoped_release release;
                  return select_structured_claims(adapter.connection(), candidates, request);
              }, py::arg("adapter"), py::arg("candidates"), py::arg("request"));
        m.def("structured_claim_view_json", &structured_claim_view_json,
              py::arg("view"));
    }

    py::class_<starling::retrieval::PlannerQuery>(m, "PlannerQuery")
        .def(py::init<>())
        .def_readwrite("tenant_id",     &starling::retrieval::PlannerQuery::tenant_id)
        .def_readwrite("querier",       &starling::retrieval::PlannerQuery::querier)
        .def_readwrite("perspective",   &starling::retrieval::PlannerQuery::perspective)
        .def_readwrite("intent",        &starling::retrieval::PlannerQuery::intent)
        .def_readwrite("text",          &starling::retrieval::PlannerQuery::text)
        .def_readwrite("subject_id",    &starling::retrieval::PlannerQuery::subject_id)
        .def_readwrite("predicate",     &starling::retrieval::PlannerQuery::predicate)
        .def_readwrite("target",        &starling::retrieval::PlannerQuery::target)
        .def_readwrite("as_of_iso8601", &starling::retrieval::PlannerQuery::as_of_iso8601)
        .def_readwrite("k",             &starling::retrieval::PlannerQuery::k)
        .def_readwrite("trace_id",      &starling::retrieval::PlannerQuery::trace_id)
        .def_readwrite("query_id",      &starling::retrieval::PlannerQuery::query_id)
        .def_readwrite("runtime_health",&starling::retrieval::PlannerQuery::runtime_health)
        .def_readwrite("temporal_evidence",&starling::retrieval::PlannerQuery::temporal_evidence)
        .def_readwrite("global_holder_filter",
                       &starling::retrieval::PlannerQuery::global_holder_filter);

    py::class_<starling::retrieval::PlannerEntryOut>(m, "PlannerEntry")
        .def_readonly("row",   &starling::retrieval::PlannerEntryOut::row)
        .def_readonly("score", &starling::retrieval::PlannerEntryOut::score)
        .def_readonly("label", &starling::retrieval::PlannerEntryOut::label);

    m.def("render_context_line", &starling::retrieval::render_line,
          py::arg("row"), py::arg("label"));

    py::class_<starling::retrieval::PlannerResult>(m, "PlannerResult")
        .def_readonly("entries",      &starling::retrieval::PlannerResult::entries)
        .def_readonly("receipt",      &starling::retrieval::PlannerResult::receipt)
        .def_readonly("context_pack", &starling::retrieval::PlannerResult::context_pack)
        .def_readonly("abstained",    &starling::retrieval::PlannerResult::abstained);

    py::class_<starling::retrieval::RetrievalPlanner>(m, "RetrievalPlanner")
        .def(py::init<starling::persistence::SqliteAdapter&,
                      starling::retrieval::SemanticRetriever&>(),
             py::keep_alive<1, 2>(), py::keep_alive<1, 3>(),
             py::arg("adapter"), py::arg("semantic"))
        // fetch 含 embedder 网络调用 → 必须释放 GIL(GIL 纪律,test_gil_release 同族)。
        .def("run", &starling::retrieval::RetrievalPlanner::run,
             py::arg("query"), py::call_guard<py::gil_scoped_release>());
}

}  // namespace starling::bindings
