// bind_04_bus — M0.3/M0.5: Bus (append_evidence / write)
// Split verbatim from bindings/python/module.cpp (original lines 436-499).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include <optional>
#include <type_traits>
#include <utility>
#include <variant>
#include "starling/bus/bus.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/extractor/extracted_statement.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::bindings {

void bind_04_bus(pybind11::module_& m) {
    using namespace pybind11::literals;

    // ----- M0.3: Bus -----
    // py::keep_alive<1, 2>() ties the SqliteAdapter Python object's lifetime to
    // the Bus instance, since Bus holds a reference (not a copy) to the adapter.
    py::class_<starling::bus::Bus>(m, "Bus")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("append_evidence",
             [](starling::bus::Bus& self,
                const starling::evidence::EngramInput& input,
                std::optional<std::string> causation_parent) -> py::object {
                 auto outcome = self.append_evidence(input, causation_parent);
                 return std::visit([](auto&& v) -> py::object {
                     using T = std::decay_t<decltype(v)>;
                     if constexpr (std::is_same_v<T, starling::bus::AppendEvidenceAccepted>) {
                         return py::dict("kind"_a="accepted",
                                         "engram_ref"_a=v.ref,
                                         "event_id"_a=v.event_id,
                                         "outbox_sequence"_a=v.outbox_sequence);
                     } else if constexpr (std::is_same_v<T, starling::bus::AppendEvidenceIdempotent>) {
                         return py::dict("kind"_a="idempotent",
                                         "engram_ref"_a=v.ref,
                                         "audit_event_id"_a=v.audit_event_id);
                     } else if constexpr (std::is_same_v<T, starling::bus::AppendEvidenceNoStore>) {
                         return py::dict("kind"_a="no_store",
                                         "audit_event_id"_a=v.audit_event_id);
                     } else {
                         return py::dict("kind"_a="rejected",
                                         "reason"_a=v.reason);
                     }
                 }, outcome);
             },
             py::arg("input"), py::arg("causation_parent") = std::nullopt)
        // M0.5: Bus::write — exposed for the TC-NEW-CONFLICT-SEVERE
        // acceptance smoke (system_design.md §15.3.4). Returns a dict whose
        // shape mirrors StatementWriteOutcome's variant arms; the test only
        // needs `stmt_id` but `kind` + `original_stmt_id` are surfaced for
        // completeness so future P1 acceptance tests don't need re-binding.
        .def("write",
             [](starling::bus::Bus& self,
                const starling::extractor::ExtractedStatement& stmt,
                const std::string& evidence_engram_id,
                const std::string& extraction_span_key,
                std::optional<std::string> causation_parent) -> py::object {
                 auto outcome = self.write(stmt, evidence_engram_id,
                                           extraction_span_key, causation_parent);
                 return std::visit([](auto&& v) -> py::object {
                     using T = std::decay_t<decltype(v)>;
                     if constexpr (std::is_same_v<T, starling::bus::StatementWriteAccepted>) {
                         return py::dict("kind"_a="accepted",
                                         "stmt_id"_a=v.stmt_id,
                                         "event_id"_a=v.event_id,
                                         "outbox_sequence"_a=v.outbox_sequence);
                     } else {
                         return py::dict("kind"_a="chunk_duplicate",
                                         "stmt_id"_a=v.stmt_id,
                                         "original_stmt_id"_a=v.original_stmt_id,
                                         "event_id"_a=v.event_id);
                     }
                 }, outcome);
             },
             py::arg("stmt"),
             py::arg("evidence_engram_id"),
             py::arg("extraction_span_key"),
             py::arg("causation_parent") = std::nullopt);
}

}  // namespace starling::bindings
