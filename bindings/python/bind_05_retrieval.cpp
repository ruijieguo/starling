// bind_05_retrieval — M0.6: BasicRetriever + receipt/row DTOs
// Split verbatim from bindings/python/module.cpp (original lines 501-584).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include "starling/retrieval/basic_retriever.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::bindings {

void bind_05_retrieval(pybind11::module_& m) {
    using namespace pybind11::literals;

    // ----- M0.6: retrieval bindings -----

    py::enum_<starling::retrieval::QueryIntent>(m, "QueryIntent")
        .value("FACT_LOOKUP", starling::retrieval::QueryIntent::FACT_LOOKUP)
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

    py::class_<starling::retrieval::RetrievalReceipt>(m, "RetrievalReceipt")
        .def_readonly("trace_id",              &starling::retrieval::RetrievalReceipt::trace_id)
        .def_readonly("query_id",              &starling::retrieval::RetrievalReceipt::query_id)
        .def_readonly("filters_applied",       &starling::retrieval::RetrievalReceipt::filters_applied)
        .def_readonly("candidate_counts",      &starling::retrieval::RetrievalReceipt::candidate_counts)
        .def_readonly("evidence_erased_count", &starling::retrieval::RetrievalReceipt::evidence_erased_count)
        .def_readonly("frontier_masked_count", &starling::retrieval::RetrievalReceipt::frontier_masked_count)
        .def_readonly("sufficiency_status",    &starling::retrieval::RetrievalReceipt::sufficiency_status);

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
}

}  // namespace starling::bindings
