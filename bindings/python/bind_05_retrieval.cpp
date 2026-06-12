// bind_05_retrieval — M0.6: BasicRetriever + receipt/row DTOs
// Split verbatim from bindings/python/module.cpp (original lines 501-584).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include "starling/retrieval/basic_retriever.hpp"
#include "starling/retrieval/retrieval_planner.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::bindings {

void bind_05_retrieval(pybind11::module_& m) {
    using namespace pybind11::literals;

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
                      &starling::retrieval::RetrievalReceipt::CandidateCounts::dropped_by_evidence_erasure);

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
        .def_readonly("affect_json",            &starling::retrieval::StatementRow::affect_json);

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
        .def_readwrite("global_holder_filter",
                       &starling::retrieval::PlannerQuery::global_holder_filter);

    py::class_<starling::retrieval::PlannerEntryOut>(m, "PlannerEntry")
        .def_readonly("row",   &starling::retrieval::PlannerEntryOut::row)
        .def_readonly("score", &starling::retrieval::PlannerEntryOut::score)
        .def_readonly("label", &starling::retrieval::PlannerEntryOut::label);

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
