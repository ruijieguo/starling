#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <type_traits>
#include <utility>
#include <variant>

#include "starling/final_query_assertion.hpp"
#include "starling/preflight.hpp"
#include "starling/profile_capability.hpp"
#include "starling/runtime_health.hpp"
#include "starling/schema/canonicalize.hpp"
#include "starling/testing_marker.hpp"
#include "starling/version.hpp"

#include "starling/bus/bus.hpp"
#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/evidence/ingest_policy_resolver.hpp"
#include "starling/extractor/extractor.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/schema/enums.hpp"

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
    using namespace pybind11::literals;

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

    // ----- M0.2: bus + persistence bindings -----

    py::class_<starling::bus::BusEvent>(m, "BusEvent")
        .def(py::init<>())
        .def_readwrite("event_id",        &starling::bus::BusEvent::event_id)
        .def_readwrite("tenant_id",       &starling::bus::BusEvent::tenant_id)
        .def_readwrite("event_type",      &starling::bus::BusEvent::event_type)
        .def_readwrite("primary_id",      &starling::bus::BusEvent::primary_id)
        .def_readwrite("aggregate_id",    &starling::bus::BusEvent::aggregate_id)
        .def_readwrite("outbox_sequence", &starling::bus::BusEvent::outbox_sequence)
        .def_readwrite("causation_chain", &starling::bus::BusEvent::causation_chain)
        .def_readwrite("idempotency_key", &starling::bus::BusEvent::idempotency_key)
        .def_readwrite("payload_json",    &starling::bus::BusEvent::payload_json)
        .def_readwrite("created_at",      &starling::bus::BusEvent::created_at)
        .def_readwrite("version",         &starling::bus::BusEvent::version);

    m.def("compute_idempotency_key",
          [](std::string event_type, std::string aggregate_id,
             std::string canonical_key, std::string causation_root,
             std::string window_bucket) {
              // Take by value so we own stable storage; pass string_views into
              // the C++ formula. Avoids any lifetime question on the Python
              // str → string_view conversion path.
              return starling::bus::compute_idempotency_key(
                  event_type, aggregate_id, canonical_key,
                  causation_root, window_bucket);
          },
          py::arg("event_type"),
          py::arg("aggregate_id"),
          py::arg("canonical_key"),
          py::arg("causation_root"),
          py::arg("window_bucket"));

    // SqliteAdapter is non-copyable + non-movable (Adapter base deletes both).
    // The unique_ptr holder lets pybind take ownership from open()'s factory.
    py::class_<starling::persistence::SqliteAdapter,
               std::unique_ptr<starling::persistence::SqliteAdapter>>(m, "SqliteAdapter")
        .def_static("open", [](const std::string& path) {
            return starling::persistence::SqliteAdapter::open(path);
        }, py::arg("db_path"))
        .def("declare_capability",
             &starling::persistence::SqliteAdapter::declare_capability)
        .def("check_final_query",
             &starling::persistence::SqliteAdapter::check_final_query,
             py::arg("sql"))
        .def_property_readonly("db_path", [](const starling::persistence::SqliteAdapter& a) {
            return a.db_path().string();
        })
        // append_event_unsafe is a TEST-ONLY shortcut: it wraps OutboxWriter in
        // a self-contained transaction, bypassing the producer's domain write.
        // Real producers must share their own transaction with OutboxWriter —
        // this binding exists solely so TC-NEW-OUTBOX-IDEMP can seed events
        // without duplicating the schema layer in Python. The CI static scan
        // refuses any prod-entrypoint reference to this name.
        // NOLINT(starling-testing-isolation): definition site of the test-only
        // binding; prod call sites are still rejected by the scanner.
        .def("append_event_unsafe", [](starling::persistence::SqliteAdapter& a,
                                        starling::bus::BusEvent& ev) {
            starling::persistence::TransactionGuard g(a.connection());
            starling::bus::OutboxWriter w(a.connection());
            w.append(ev);
            g.commit();
        }, py::arg("event"))
        .def("connection",
             &starling::persistence::SqliteAdapter::connection,
             py::return_value_policy::reference_internal);

    // ----- M0.3: schema enums (mirror starling::schema::*) -----
    py::enum_<starling::schema::SourceKind>(m, "SourceKind")
        .value("USER_INPUT",       starling::schema::SourceKind::USER_INPUT)
        .value("EXTERNAL_DOC",     starling::schema::SourceKind::EXTERNAL_DOC)
        .value("TOOL_OBSERVATION", starling::schema::SourceKind::TOOL_OBSERVATION)
        .value("SYSTEM_INTERNAL",  starling::schema::SourceKind::SYSTEM_INTERNAL)
        .value("OBSERVER_AGENT",   starling::schema::SourceKind::OBSERVER_AGENT)
        .value("REPLAY_OUTPUT",    starling::schema::SourceKind::REPLAY_OUTPUT);

    py::enum_<starling::schema::IngestPolicy>(m, "IngestPolicy")
        .value("STORE",               starling::schema::IngestPolicy::STORE)
        .value("NO_STORE",            starling::schema::IngestPolicy::NO_STORE)
        .value("STORE_METADATA_ONLY", starling::schema::IngestPolicy::STORE_METADATA_ONLY)
        .value("REQUIRE_REVIEW",      starling::schema::IngestPolicy::REQUIRE_REVIEW);

    py::enum_<starling::schema::IngestMode>(m, "IngestMode")
        .value("CHUNKED_CONTENT", starling::schema::IngestMode::CHUNKED_CONTENT)
        .value("WHOLE_RECORD",    starling::schema::IngestMode::WHOLE_RECORD)
        .value("METADATA_ONLY",   starling::schema::IngestMode::METADATA_ONLY);

    py::enum_<starling::schema::PrivacyClass>(m, "PrivacyClass")
        .value("PUBLIC",    starling::schema::PrivacyClass::PUBLIC)
        .value("INTERNAL",  starling::schema::PrivacyClass::INTERNAL)
        .value("PERSONAL",  starling::schema::PrivacyClass::PERSONAL)
        .value("SENSITIVE", starling::schema::PrivacyClass::SENSITIVE)
        .value("REGULATED", starling::schema::PrivacyClass::REGULATED);

    py::enum_<starling::schema::EngramRetentionMode>(m, "EngramRetentionMode")
        .value("LEGAL_HOLD",      starling::schema::EngramRetentionMode::LEGAL_HOLD)
        .value("AUDIT_RETAIN",    starling::schema::EngramRetentionMode::AUDIT_RETAIN)
        .value("REDACTED_RETAIN", starling::schema::EngramRetentionMode::REDACTED_RETAIN)
        .value("CRYPTO_ERASURE",  starling::schema::EngramRetentionMode::CRYPTO_ERASURE);

    // ----- M0.3: IngestPolicyResolver -----
    py::class_<starling::evidence::IngestPolicyResolver>(m, "IngestPolicyResolver")
        .def_static("resolve", &starling::evidence::IngestPolicyResolver::resolve,
                    py::arg("source_kind"), py::arg("privacy_class"),
                    py::arg("producer_declared"));

    // ----- M0.3: SourceIdentity / EngramInput / EngramRef -----
    py::class_<starling::evidence::SourceIdentity>(m, "SourceIdentity")
        .def(py::init<>())
        .def_readwrite("adapter_name",    &starling::evidence::SourceIdentity::adapter_name)
        .def_readwrite("adapter_version", &starling::evidence::SourceIdentity::adapter_version)
        .def_readwrite("source_item_id",  &starling::evidence::SourceIdentity::source_item_id)
        .def_readwrite("source_version",  &starling::evidence::SourceIdentity::source_version)
        .def_readwrite("chunk_index",     &starling::evidence::SourceIdentity::chunk_index);

    py::class_<starling::evidence::EngramInput>(m, "EngramInput")
        .def(py::init<>())
        .def_readwrite("tenant_id",      &starling::evidence::EngramInput::tenant_id)
        .def_readwrite("source",         &starling::evidence::EngramInput::source)
        .def_readwrite("source_kind",    &starling::evidence::EngramInput::source_kind)
        .def_readwrite("ingest_mode",    &starling::evidence::EngramInput::ingest_mode)
        .def_readwrite("privacy_class",  &starling::evidence::EngramInput::privacy_class)
        .def_readwrite("retention_mode", &starling::evidence::EngramInput::retention_mode)
        .def_readwrite("declared_transformations",
                       &starling::evidence::EngramInput::declared_transformations)
        .def_readwrite("byte_preserving",  &starling::evidence::EngramInput::byte_preserving)
        .def_readwrite("payload_bytes",    &starling::evidence::EngramInput::payload_bytes)
        .def_readwrite("redacted_content", &starling::evidence::EngramInput::redacted_content)
        .def_readwrite("created_at_iso8601",
                       &starling::evidence::EngramInput::created_at_iso8601);

    py::class_<starling::evidence::EngramRef>(m, "EngramRef")
        .def_readonly("id",             &starling::evidence::EngramRef::id)
        .def_readonly("content_hash",   &starling::evidence::EngramRef::content_hash)
        .def_readonly("retention_mode", &starling::evidence::EngramRef::retention_mode);

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
             py::arg("input"), py::arg("causation_parent") = std::nullopt);

    // ----- M0.4: enums -----
    py::enum_<starling::schema::Perspective>(m, "Perspective")
        .value("FIRST_PERSON", starling::schema::Perspective::FIRST_PERSON)
        .value("QUOTED",       starling::schema::Perspective::QUOTED)
        .value("INFERRED",     starling::schema::Perspective::INFERRED)
        .value("HEARSAY",      starling::schema::Perspective::HEARSAY)
        .export_values();

    py::enum_<starling::schema::Modality>(m, "Modality")
        .value("BELIEVES",    starling::schema::Modality::BELIEVES)
        .value("KNOWS",       starling::schema::Modality::KNOWS)
        .value("ASSUMES",     starling::schema::Modality::ASSUMES)
        .value("DOUBTS",      starling::schema::Modality::DOUBTS)
        .value("DESIRES",     starling::schema::Modality::DESIRES)
        .value("INTENDS",     starling::schema::Modality::INTENDS)
        .value("COMMITS",     starling::schema::Modality::COMMITS)
        .value("PREFERS",     starling::schema::Modality::PREFERS)
        .value("NORM_OUGHT",  starling::schema::Modality::NORM_OUGHT)
        .value("NORM_FORBID", starling::schema::Modality::NORM_FORBID)
        .value("RECANTED",    starling::schema::Modality::RECANTED)
        .export_values();

    py::enum_<starling::schema::Polarity>(m, "Polarity")
        .value("POS",     starling::schema::Polarity::POS)
        .value("NEG",     starling::schema::Polarity::NEG)
        .value("UNKNOWN", starling::schema::Polarity::UNKNOWN)
        .export_values();

    py::enum_<starling::schema::ReviewStatus>(m, "ReviewStatus")
        .value("APPROVED",            starling::schema::ReviewStatus::APPROVED)
        .value("PENDING_REVIEW",      starling::schema::ReviewStatus::PENDING_REVIEW)
        .value("INFERRED_UNREVIEWED", starling::schema::ReviewStatus::INFERRED_UNREVIEWED)
        .value("REVIEW_REQUESTED",    starling::schema::ReviewStatus::REVIEW_REQUESTED)
        .value("REJECTED",            starling::schema::ReviewStatus::REJECTED)
        .export_values();

    py::enum_<starling::schema::StatementProvenance>(m, "StatementProvenance")
        .value("USER_INPUT",              starling::schema::StatementProvenance::USER_INPUT)
        .value("REPLAY_DERIVED",          starling::schema::StatementProvenance::REPLAY_DERIVED)
        .value("TOM_INFERRED",            starling::schema::StatementProvenance::TOM_INFERRED)
        .value("RECONSOLIDATION_DERIVED", starling::schema::StatementProvenance::RECONSOLIDATION_DERIVED)
        .export_values();

    // ----- M0.4: Connection (opaque) -----
    py::class_<starling::persistence::Connection>(m, "Connection");

    // ----- M0.4: LLMResponse + FakeLLMAdapter -----
    py::class_<starling::extractor::LLMResponse>(m, "LLMResponse")
        .def(py::init<>())
        .def(py::init([](std::string raw_xml, bool ok, std::string error) {
            return starling::extractor::LLMResponse{std::move(raw_xml), ok, std::move(error)};
        }), py::arg("raw_xml"), py::arg("ok"), py::arg("error") = "")
        .def_readwrite("raw_xml", &starling::extractor::LLMResponse::raw_xml)
        .def_readwrite("ok",      &starling::extractor::LLMResponse::ok)
        .def_readwrite("error",   &starling::extractor::LLMResponse::error);

    py::class_<starling::extractor::FakeLLMAdapter>(m, "FakeLLMAdapter")
        .def(py::init<>())
        .def("set_response",
             [](starling::extractor::FakeLLMAdapter& self, const std::string& hash,
                const std::string& raw_xml, bool ok, const std::string& error) {
                 self.set_response(hash, starling::extractor::LLMResponse{raw_xml, ok, error});
             },
             py::arg("hash"), py::arg("raw_xml"),
             py::arg("ok") = true, py::arg("error") = "")
        .def("set_default_response",
             [](starling::extractor::FakeLLMAdapter& self,
                const std::string& raw_xml, bool ok, const std::string& error) {
                 self.set_default_response(starling::extractor::LLMResponse{raw_xml, ok, error});
             },
             py::arg("raw_xml"), py::arg("ok") = true, py::arg("error") = "")
        .def("extract",
             &starling::extractor::FakeLLMAdapter::extract,
             py::arg("prompt"), py::arg("prompt_input_hash"));

    // ----- M0.4: ExtractionRunResult -----
    py::class_<starling::extractor::ExtractionRunResult>(m, "ExtractionRunResult")
        .def_readonly("accepted_statement_ids",
                      &starling::extractor::ExtractionRunResult::accepted_statement_ids)
        .def_readonly("rejected_fragments",
                      &starling::extractor::ExtractionRunResult::rejected_fragments)
        .def_readonly("run_id", &starling::extractor::ExtractionRunResult::run_id)
        .def_property_readonly("status",
            [](const starling::extractor::ExtractionRunResult& r) -> std::string {
                switch (r.status) {
                    case starling::extractor::ExtractionRunResult::Status::SUCCESS:
                        return "success";
                    case starling::extractor::ExtractionRunResult::Status::PARTIAL_SUCCESS:
                        return "partial_success";
                    case starling::extractor::ExtractionRunResult::Status::FAILED:
                        return "failed";
                }
                return "unknown";
            });

    // ----- M0.4: Extractor -----
    py::class_<starling::extractor::Extractor>(m, "Extractor")
        .def(py::init([](starling::persistence::Connection& conn,
                         starling::extractor::FakeLLMAdapter& a) {
            return new starling::extractor::Extractor(conn, a);
        }), py::keep_alive<1, 2>(), py::keep_alive<1, 3>(),
           py::arg("connection"), py::arg("adapter"))
        .def_static("compute_prompt_input_hash",
                    &starling::extractor::Extractor::compute_prompt_input_hash)
        .def_static("build_prompt_body",
                    [](const std::string& holder_id,
                       py::bytes payload,
                       const std::map<std::string, std::string>& refs) {
                        std::string s = payload;
                        std::vector<std::uint8_t> v(s.begin(), s.end());
                        return starling::extractor::Extractor::build_prompt_body_for_tests(
                            holder_id, v, refs);
                    },
                    py::arg("holder_id"), py::arg("payload_bytes"),
                    py::arg("existing_ref_map"))
        .def("run",
             [](starling::extractor::Extractor& self,
                const std::string& engram_ref_id,
                py::bytes payload,
                const std::string& holder_id,
                const std::string& holder_tenant_id,
                const std::map<std::string, std::string>& existing_ref_map) {
                 std::string s = payload;
                 std::vector<std::uint8_t> v(s.begin(), s.end());
                 return self.run(engram_ref_id, v, holder_id, holder_tenant_id, existing_ref_map);
             },
             py::arg("engram_ref_id"),
             py::arg("payload_bytes"),
             py::arg("holder_id"),
             py::arg("holder_tenant_id"),
             py::arg("existing_ref_map"));
}
