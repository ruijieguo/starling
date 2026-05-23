#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <string_view>

#include "starling/final_query_assertion.hpp"
#include "starling/preflight.hpp"
#include "starling/profile_capability.hpp"
#include "starling/runtime_health.hpp"
#include "starling/schema/canonicalize.hpp"
#include "starling/testing_marker.hpp"
#include "starling/version.hpp"

namespace py = pybind11;

namespace {

constexpr std::array<const char*, 6> kRefClassNames{
    "CognizerRef", "EntityRef", "StatementRef",
    "EngramRef", "PersonaRef", "KnowledgeFrontierRef",
};

bool is_known_ref_class(const std::string& name) {
    for (const char* known : kRefClassNames) {
        if (name == known) {
            return true;
        }
    }
    return false;
}

// Dispatch a Python value to the C++ canonicalize_object. Mirrors the type
// ladder in python/starling/schema/value.py — bool BEFORE int (PyBool is a
// PyLong subclass), then int → float → str → datetime → Ref → error.
py::tuple canonicalize_object_cpp(py::object value) {
    using starling::schema::canonicalize_object;
    using starling::schema::CanonicalInput;
    using starling::schema::CanonicalRefInput;

    CanonicalInput input;

    if (py::isinstance<py::bool_>(value)) {
        input = value.cast<bool>();
    } else if (py::isinstance<py::int_>(value)) {
        input = value.cast<std::int64_t>();
    } else if (py::isinstance<py::float_>(value)) {
        input = value.cast<double>();
    } else if (py::isinstance<py::str>(value)) {
        input = value.cast<std::string>();
    } else {
        // datetime?
        py::object datetime_mod = py::module_::import("datetime");
        py::object datetime_cls = datetime_mod.attr("datetime");
        py::object timezone_cls = datetime_mod.attr("timezone");
        if (py::isinstance(value, datetime_cls)) {
            if (value.attr("tzinfo").is_none()) {
                throw py::value_error(
                    "schema_invalid: naive datetime not canonicalizable");
            }
            py::object utc = value.attr("astimezone")(timezone_cls.attr("utc"));
            // Use timestamp() (returns float seconds since epoch); truncate to
            // integer seconds to match Python's strftime("%Y-%m-%dT%H:%M:%SZ"),
            // which formats whole-second resolution and drops sub-second.
            const double ts = utc.attr("timestamp")().cast<double>();
            const auto secs = static_cast<std::int64_t>(ts);
            input = std::chrono::sys_seconds{std::chrono::seconds{secs}};
        } else {
            // Ref?  Detected by class name + uuid.UUID-typed `id` attribute.
            const std::string class_name =
                py::str(py::type::of(value).attr("__name__")).cast<std::string>();
            if (!is_known_ref_class(class_name)) {
                throw py::value_error(
                    std::string("schema_invalid: unsupported type ") + class_name);
            }
            py::object uuid_mod = py::module_::import("uuid");
            py::object uuid_cls = uuid_mod.attr("UUID");
            py::object id_attr = value.attr("id");
            if (!py::isinstance(id_attr, uuid_cls)) {
                throw py::value_error(
                    "schema_invalid: Ref.id must be a uuid.UUID");
            }
            py::bytes raw = id_attr.attr("bytes").cast<py::bytes>();
            const std::string raw_str = raw.cast<std::string>();
            if (raw_str.size() != 16) {
                throw py::value_error(
                    "schema_invalid: UUID.bytes must be 16 bytes");
            }
            CanonicalRefInput ref{};
            ref.class_name = class_name;
            std::memcpy(ref.uuid_bytes.data(), raw_str.data(), 16);
            input = ref;
        }
    }

    auto result = canonicalize_object(input);
    return py::make_tuple(result.canonical, result.sha256_hex);
}

}  // namespace

PYBIND11_MODULE(_core, m) {
    m.doc() = "Starling Memory C++ core bindings";
    m.attr("__version__") = STARLING_VERSION_STRING;

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

    m.def("canonicalize_object_cpp", &canonicalize_object_cpp,
          py::arg("value"),
          "Canonicalize a value to (canonical_string, sha256_hex). MUST produce "
          "byte-for-byte identical output to "
          "starling.schema.value.canonicalize_object — the parity contract is "
          "enforced by tests/python/test_canonicalize_parity.py.");
}
