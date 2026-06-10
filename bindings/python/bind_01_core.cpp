// bind_01_core — ProfileCapability / preflight / final-query assertion / testing submodule / canonicalize
// Split verbatim from bindings/python/module.cpp (original lines 156-298).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include <string_view>
#include <utility>
#include "starling/final_query_assertion.hpp"
#include "starling/preflight.hpp"
#include "starling/profile_capability.hpp"
#include "starling/runtime_health.hpp"
#include "starling/testing_marker.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::bindings {

void bind_01_core(pybind11::module_& m) {
    using namespace pybind11::literals;

    py::class_<starling::ProfileCapability>(m, "ProfileCapability")
        .def(py::init<>())
        .def(py::init([](std::string profile_name,
                          std::string relational_backend,
                          std::string vector_backend,
                          std::string graph_backend,
                          bool c_plus_plus_core,
                          bool cross_partition_transaction,
                          bool transactional_outbox,
                          bool consumer_checkpoint,
                          std::string tenant_isolation,
                          bool engram_per_record_key,
                          bool engram_refcount,
                          bool projection_index_supported,
                          bool dimension_versions_supported,
                          bool testing_helper_marker) {
                  return starling::ProfileCapability{
                      .profile_name = std::move(profile_name),
                      .relational_backend = std::move(relational_backend),
                      .vector_backend = std::move(vector_backend),
                      .graph_backend = std::move(graph_backend),
                      .c_plus_plus_core = c_plus_plus_core,
                      .cross_partition_transaction = cross_partition_transaction,
                      .transactional_outbox = transactional_outbox,
                      .consumer_checkpoint = consumer_checkpoint,
                      .tenant_isolation = std::move(tenant_isolation),
                      .engram_per_record_key = engram_per_record_key,
                      .engram_refcount = engram_refcount,
                      .projection_index_supported = projection_index_supported,
                      .dimension_versions_supported = dimension_versions_supported,
                      .testing_helper_marker = testing_helper_marker,
                  };
              }),
              py::kw_only(),
              py::arg("profile_name") = "",
              py::arg("relational_backend") = "",
              py::arg("vector_backend") = "",
              py::arg("graph_backend") = "",
              py::arg("c_plus_plus_core") = false,
              py::arg("cross_partition_transaction") = false,
              py::arg("transactional_outbox") = false,
              py::arg("consumer_checkpoint") = false,
              py::arg("tenant_isolation") = "",
              py::arg("engram_per_record_key") = false,
              py::arg("engram_refcount") = false,
              py::arg("projection_index_supported") = false,
              py::arg("dimension_versions_supported") = false,
              py::arg("testing_helper_marker") = false)
        .def_readwrite("profile_name", &starling::ProfileCapability::profile_name)
        .def_readwrite("relational_backend",
                       &starling::ProfileCapability::relational_backend)
        .def_readwrite("vector_backend", &starling::ProfileCapability::vector_backend)
        .def_readwrite("graph_backend", &starling::ProfileCapability::graph_backend)
        .def_readwrite("c_plus_plus_core",
                       &starling::ProfileCapability::c_plus_plus_core)
        .def_readwrite("cross_partition_transaction",
                       &starling::ProfileCapability::cross_partition_transaction)
        .def_readwrite("transactional_outbox",
                       &starling::ProfileCapability::transactional_outbox)
        .def_readwrite("consumer_checkpoint",
                       &starling::ProfileCapability::consumer_checkpoint)
        .def_readwrite("tenant_isolation",
                       &starling::ProfileCapability::tenant_isolation)
        .def_readwrite("engram_per_record_key",
                       &starling::ProfileCapability::engram_per_record_key)
        .def_readwrite("engram_refcount",
                       &starling::ProfileCapability::engram_refcount)
        .def_readwrite("projection_index_supported",
                       &starling::ProfileCapability::projection_index_supported)
        .def_readwrite("dimension_versions_supported",
                       &starling::ProfileCapability::dimension_versions_supported)
        .def_readwrite("testing_helper_marker",
                       &starling::ProfileCapability::testing_helper_marker);

    py::enum_<starling::RuntimeHealth>(m, "RuntimeHealth")
        .value("UNREADY", starling::RuntimeHealth::UNREADY)
        .value("READY", starling::RuntimeHealth::READY)
        .value("DEGRADED", starling::RuntimeHealth::DEGRADED)
        .value("DRAINING", starling::RuntimeHealth::DRAINING);

    py::enum_<starling::PreflightStatus>(m, "PreflightStatus")
        .value("READY", starling::PreflightStatus::READY)
        .value("UNREADY", starling::PreflightStatus::UNREADY);

    py::class_<starling::PreflightResult>(m, "PreflightResult")
        .def_readonly("status", &starling::PreflightResult::status)
        .def_readonly("missing", &starling::PreflightResult::missing);

    m.def("preflight", &starling::preflight,
          py::arg("declared"), py::arg("required"),
          "Validate a ProfileCapability against required capability names. "
          "Unknown names are treated as missing (fail-closed).");

    py::register_exception<starling::FinalQueryAssertionError>(
        m, "FinalQueryAssertionError", PyExc_ValueError);

    m.def("assert_final_query_safe", &starling::assert_final_query_safe,
          py::arg("sql"),
          "Throws FinalQueryAssertionError if SQL lacks tenant_id + holder_scope "
          "predicates (outside SQL line comments).");

    m.def("is_final_query_safe",
          [](std::string_view sql) { return ::starling::is_final_query_safe(sql); },
          py::arg("sql"),
          "Pure predicate: returns True iff SQL contains tenant_id + holder_scope "
          "predicates outside line comments. Case-insensitive.");

    auto testing_submodule = m.def_submodule("testing",
        "Testing-only helpers. Prod profiles MUST NOT link this submodule.");  // NOLINT(starling-testing-isolation)
    testing_submodule.def("marker_loaded", &starling::testing::testing_marker_loaded,
                          "True iff the testing-only translation unit is linked.");  // NOLINT(starling-testing-isolation)
    testing_submodule.def("mark_consolidated",  // NOLINT(starling-testing-isolation)
        [](starling::persistence::SqliteAdapter& adapter,
           const std::string& stmt_id,
           const std::string& tenant_id) {
            return starling::testing::mark_consolidated(adapter, stmt_id, tenant_id);  // NOLINT(starling-testing-isolation)
        },
        py::arg("adapter"), py::arg("stmt_id"), py::arg("tenant_id"),
        "VOLATILE -> CONSOLIDATED dev-only transition. Returns True iff a row "
        "was actually flipped (and an audit event written); False on missing "
        "row, already-consolidated row, or any other non-volatile state.");  // NOLINT(starling-testing-isolation)

    testing_submodule.def("mark_evidence_erased",  // NOLINT(starling-testing-isolation)
        [](starling::persistence::SqliteAdapter& adapter,
           const std::string& engram_id,
           const std::string& tenant_id,
           const std::string& erased_at_iso8601) {
            return starling::testing::mark_evidence_erased(  // NOLINT(starling-testing-isolation)
                adapter, engram_id, tenant_id, erased_at_iso8601);
        },
        py::arg("adapter"), py::arg("engram_id"),
        py::arg("tenant_id"), py::arg("erased_at_iso8601"),
        "Flip engrams(id=engram_id, tenant_id=tenant_id).erased_at from NULL "
        "to erased_at_iso8601. Writes a testing.mark_evidence_erased audit "
        "event. Returns True iff a row was actually flipped (False on missing "
        "row or already-erased row; no audit row written in those cases).");  // NOLINT(starling-testing-isolation)

    m.def("canonicalize_object_cpp", &canonicalize_object_cpp,
          py::arg("value"),
          "Canonicalize a value to (canonical_string, sha256_hex). MUST produce "
          "byte-for-byte identical output to "
          "starling.schema.value.canonicalize_object — the parity contract is "
          "enforced by tests/python/test_canonicalize_parity.py.");
}

}  // namespace starling::bindings
