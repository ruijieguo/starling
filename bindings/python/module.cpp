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
#include "starling/cognizer/cognizer.hpp"
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/tom/belief_tracker.hpp"
#include "starling/tom/common_ground.hpp"
#include "starling/tom/mentalizing.hpp"
#include "starling/tom/nesting_depth_writer.hpp"
#include "starling/tom/tom_engine.hpp"
#include "starling/evidence/ingest_policy_resolver.hpp"
#include "starling/extractor/extractor.hpp"
#include "starling/extractor/fake_llm_adapter.hpp"
#include "starling/extractor/openai_adapter.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/basic_retriever.hpp"
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
        .def_readonly("evidence_json",          &starling::retrieval::StatementRow::evidence_json);

    py::class_<starling::retrieval::BasicRetrieverParams>(m, "BasicRetrieverParams")
        .def(py::init<>())
        .def_readwrite("tenant_id",          &starling::retrieval::BasicRetrieverParams::tenant_id)
        .def_readwrite("holder_id",          &starling::retrieval::BasicRetrieverParams::holder_id)
        .def_readwrite("holder_perspective", &starling::retrieval::BasicRetrieverParams::holder_perspective)
        .def_readwrite("intent",             &starling::retrieval::BasicRetrieverParams::intent)
        .def_readwrite("subject_id",         &starling::retrieval::BasicRetrieverParams::subject_id)
        .def_readwrite("predicate",          &starling::retrieval::BasicRetrieverParams::predicate)
        .def_readwrite("as_of_iso8601",      &starling::retrieval::BasicRetrieverParams::as_of_iso8601)
        .def_readwrite("trace_id",           &starling::retrieval::BasicRetrieverParams::trace_id)
        .def_readwrite("query_id",           &starling::retrieval::BasicRetrieverParams::query_id);

    py::class_<starling::retrieval::BasicRetrieveResult>(m, "BasicRetrieveResult")
        .def_readonly("rows",    &starling::retrieval::BasicRetrieveResult::rows)
        .def_readonly("receipt", &starling::retrieval::BasicRetrieveResult::receipt);

    py::class_<starling::retrieval::BasicRetriever>(m, "BasicRetriever")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("run", &starling::retrieval::BasicRetriever::run, py::arg("params"));

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

    // ----- M0.5: ExtractedStatement DTO -----
    // Bound for the TC-NEW-CONFLICT-SEVERE acceptance test (§15.3.4): the test
    // constructs S_old / S_new in Python and feeds them to Bus::write to
    // exercise the atomic SUPERSEDES path. M0.4 extractor pipelines build
    // these structs in C++ from XML and never round-trip through Python; this
    // binding is purely for tests that need to construct an ExtractedStatement
    // outside the XML parser (the M0.5 XML schema doesn't yet carry
    // valid_from/valid_to, so the conflict-probe test must bypass it).
    py::class_<starling::extractor::ExtractedStatement>(m, "ExtractedStatement")
        .def(py::init<>())
        .def_readwrite("holder_id",             &starling::extractor::ExtractedStatement::holder_id)
        .def_readwrite("holder_tenant_id",      &starling::extractor::ExtractedStatement::holder_tenant_id)
        .def_readwrite("holder_perspective",    &starling::extractor::ExtractedStatement::holder_perspective)
        .def_readwrite("subject_kind",          &starling::extractor::ExtractedStatement::subject_kind)
        .def_readwrite("subject_id",            &starling::extractor::ExtractedStatement::subject_id)
        .def_readwrite("predicate",             &starling::extractor::ExtractedStatement::predicate)
        .def_readwrite("object_kind",           &starling::extractor::ExtractedStatement::object_kind)
        .def_readwrite("object_value",          &starling::extractor::ExtractedStatement::object_value)
        .def_readwrite("canonical_object_hash", &starling::extractor::ExtractedStatement::canonical_object_hash)
        .def_readwrite("modality",              &starling::extractor::ExtractedStatement::modality)
        .def_readwrite("polarity",              &starling::extractor::ExtractedStatement::polarity)
        .def_readwrite("confidence",            &starling::extractor::ExtractedStatement::confidence)
        .def_readwrite("observed_at",           &starling::extractor::ExtractedStatement::observed_at)
        .def_readwrite("valid_from",            &starling::extractor::ExtractedStatement::valid_from)
        .def_readwrite("valid_to",              &starling::extractor::ExtractedStatement::valid_to)
        .def_readwrite("event_time_start",      &starling::extractor::ExtractedStatement::event_time_start)
        .def_readwrite("chunk_index",           &starling::extractor::ExtractedStatement::chunk_index)
        .def_readwrite("source_hash",           &starling::extractor::ExtractedStatement::source_hash)
        .def_readwrite("perceived_by",          &starling::extractor::ExtractedStatement::perceived_by)
        .def_readwrite("provenance",            &starling::extractor::ExtractedStatement::provenance)
        .def_readwrite("review_status",         &starling::extractor::ExtractedStatement::review_status)
        .def_readwrite("derived_from",          &starling::extractor::ExtractedStatement::derived_from)
        .def_readwrite("provenance_protocol_id", &starling::extractor::ExtractedStatement::provenance_protocol_id);

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

    // ----- M0.7: OpenAIAdapter (real LLM, P2 pull-forward) -----
    {
        using starling::extractor::OpenAIAdapter;
        py::class_<OpenAIAdapter::Config>(m, "OpenAIAdapterConfig")
            .def(py::init<>())
            .def_readwrite("base_url",     &OpenAIAdapter::Config::base_url)
            .def_readwrite("model",        &OpenAIAdapter::Config::model)
            .def_readwrite("timeout_ms",   &OpenAIAdapter::Config::timeout_ms)
            .def_readwrite("max_retries",  &OpenAIAdapter::Config::max_retries)
            .def_static("from_env",        &OpenAIAdapter::Config::from_env);
        py::class_<OpenAIAdapter>(m, "OpenAIAdapter")
            .def(py::init<OpenAIAdapter::Config>());
    }

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

    // ── 08_cognizer ────────────────────────────────────────────────

    py::enum_<starling::cognizer::CognizerKind>(m, "CognizerKind")
        .value("Self",     starling::cognizer::CognizerKind::Self)
        .value("Human",    starling::cognizer::CognizerKind::Human)
        .value("Agent",    starling::cognizer::CognizerKind::Agent)
        .value("Group",    starling::cognizer::CognizerKind::Group)
        .value("Role",     starling::cognizer::CognizerKind::Role)
        .value("External", starling::cognizer::CognizerKind::External);

    py::enum_<starling::cognizer::FiskeMode>(m, "FiskeMode")
        .value("Communal",  starling::cognizer::FiskeMode::Communal)
        .value("Authority", starling::cognizer::FiskeMode::Authority)
        .value("Equality",  starling::cognizer::FiskeMode::Equality)
        .value("Market",    starling::cognizer::FiskeMode::Market);

    py::class_<starling::cognizer::Cognizer>(m, "Cognizer")
        .def_readonly("id",              &starling::cognizer::Cognizer::id)
        .def_readonly("tenant_id",       &starling::cognizer::Cognizer::tenant_id)
        .def_readonly("kind",            &starling::cognizer::Cognizer::kind)
        .def_readonly("canonical_name",  &starling::cognizer::Cognizer::canonical_name)
        .def_readonly("external_id",     &starling::cognizer::Cognizer::external_id)
        .def_readonly("aliases",         &starling::cognizer::Cognizer::aliases)
        .def_readonly("created_at",      &starling::cognizer::Cognizer::created_at)
        .def_readonly("last_seen_at",    &starling::cognizer::Cognizer::last_seen_at);

    py::class_<starling::cognizer::RelationEdge>(m, "RelationEdge")
        .def_readonly("id",               &starling::cognizer::RelationEdge::id)
        .def_readonly("tenant_id",        &starling::cognizer::RelationEdge::tenant_id)
        .def_readonly("a_id",             &starling::cognizer::RelationEdge::a_id)
        .def_readonly("b_id",             &starling::cognizer::RelationEdge::b_id)
        .def_readonly("affinity",         &starling::cognizer::RelationEdge::affinity)
        .def_readonly("power_asymmetry",  &starling::cognizer::RelationEdge::power_asymmetry)
        .def_readonly("created_at",       &starling::cognizer::RelationEdge::created_at)
        .def_readonly("updated_at",       &starling::cognizer::RelationEdge::updated_at);

    py::class_<starling::cognizer::CognizerHub>(m, "CognizerHub")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("register_cognizer",
             [](starling::cognizer::CognizerHub& hub,
                const std::string& kind_str,
                const std::string& external_id,
                const std::string& canonical_name,
                const std::string& tenant_id,
                const std::vector<std::string>& aliases,
                bool tenant_explicitly_set) {
                 starling::cognizer::CognizerRegistration req;
                 req.external_id = external_id;
                 req.canonical_name = canonical_name;
                 req.tenant_id = tenant_id;
                 req.aliases = aliases;
                 req.tenant_explicitly_set = tenant_explicitly_set;
                 if      (kind_str == "self")     req.kind = starling::cognizer::CognizerKind::Self;
                 else if (kind_str == "human")    req.kind = starling::cognizer::CognizerKind::Human;
                 else if (kind_str == "agent")    req.kind = starling::cognizer::CognizerKind::Agent;
                 else if (kind_str == "group")    req.kind = starling::cognizer::CognizerKind::Group;
                 else if (kind_str == "role")     req.kind = starling::cognizer::CognizerKind::Role;
                 else if (kind_str == "external") req.kind = starling::cognizer::CognizerKind::External;
                 else throw py::value_error("unknown kind: " + kind_str);
                 return hub.register_cognizer(req);
             },
             py::arg("kind"), py::arg("external_id"), py::arg("canonical_name"),
             py::arg("tenant_id") = "default",
             py::arg("aliases") = std::vector<std::string>{},
             py::arg("tenant_explicitly_set") = false)
        .def("lookup_by_alias",
             [](const starling::cognizer::CognizerHub& hub,
                const std::string& tenant_id,
                const std::string& alias) -> py::object {
                 auto r = hub.lookup_by_alias(tenant_id, alias);
                 if (!r) return py::none();
                 return py::str(*r);
             },
             py::arg("tenant_id"), py::arg("alias"))
        .def("get",
             [](const starling::cognizer::CognizerHub& hub,
                const std::string& id,
                const std::string& tenant_id) -> py::object {
                 auto r = hub.get(id, tenant_id);
                 if (!r) return py::none();
                 return py::cast(*r);
             },
             py::arg("id"), py::arg("tenant_id") = "default")
        .def("update_last_seen_at",
             [](starling::cognizer::CognizerHub& hub,
                const std::string& id,
                const std::string& tenant_id,
                const std::string& at_iso8601) {
                 hub.update_last_seen_at(id, tenant_id, at_iso8601);
             },
             py::arg("id"), py::arg("tenant_id"), py::arg("at"))
        .def("upsert_relation",
             [](starling::cognizer::CognizerHub& hub,
                const std::string& a_id, const std::string& b_id,
                const std::string& tenant_id,
                const std::map<std::string, double>& fiske_map,
                double affinity, double power_asymmetry) {
                 starling::cognizer::RelationEdgeInput req;
                 req.a_id = a_id;
                 req.b_id = b_id;
                 req.tenant_id = tenant_id;
                 req.affinity = affinity;
                 req.power_asymmetry = power_asymmetry;
                 for (auto& [k, v] : fiske_map) {
                     if      (k == "communal")  req.fiske_weights[starling::cognizer::FiskeMode::Communal]  = v;
                     else if (k == "authority") req.fiske_weights[starling::cognizer::FiskeMode::Authority] = v;
                     else if (k == "equality")  req.fiske_weights[starling::cognizer::FiskeMode::Equality]  = v;
                     else if (k == "market")    req.fiske_weights[starling::cognizer::FiskeMode::Market]    = v;
                 }
                 return hub.upsert_relation(req);
             },
             py::arg("a_id"), py::arg("b_id"),
             py::arg("tenant_id") = "default",
             py::arg("fiske_weights") = std::map<std::string, double>{},
             py::arg("affinity") = 0.5,
             py::arg("power_asymmetry") = 0.0)
        .def("relations_of",
             &starling::cognizer::CognizerHub::relations_of,
             py::arg("cognizer_id"), py::arg("tenant_id") = "default");

    py::class_<starling::cognizer::KnowledgeFrontier>(m, "KnowledgeFrontier")
        .def(py::init<starling::persistence::SqliteAdapter&>(),
             py::keep_alive<1, 2>(), py::arg("adapter"))
        .def("record_presence_from_statement",
             [](starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::vector<std::string>& perceived_by,
                const std::string& engram_id,
                const std::string& observed_at,
                starling::persistence::Connection& conn) {
                 f.record_presence_from_statement(tenant_id, perceived_by,
                                                   engram_id, observed_at, conn);
             },
             py::arg("tenant_id"), py::arg("perceived_by"),
             py::arg("engram_id"), py::arg("observed_at"), py::arg("conn"))
        .def("record_explicit_told",
             [](starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::vector<std::string>& perceived_by,
                const std::string& statement_id,
                const std::string& source_engram_id,
                const std::string& observed_at,
                starling::persistence::Connection& conn) {
                 f.record_explicit_told(tenant_id, perceived_by, statement_id,
                                        source_engram_id, observed_at, conn);
             },
             py::arg("tenant_id"), py::arg("perceived_by"),
             py::arg("statement_id"), py::arg("source_engram_id"),
             py::arg("observed_at"), py::arg("conn"))
        .def("record_accessible_source",
             [](starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::string& cognizer_id,
                const std::string& adapter_name,
                const std::string& source_engram_id,
                const std::string& observed_at,
                starling::persistence::Connection& conn) {
                 f.record_accessible_source(tenant_id, cognizer_id, adapter_name,
                                             source_engram_id, observed_at, conn);
             },
             py::arg("tenant_id"), py::arg("cognizer_id"),
             py::arg("adapter_name"), py::arg("source_engram_id"),
             py::arg("observed_at"), py::arg("conn"))
        .def("record_group_membership",
             [](starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::string& cognizer_id,
                const std::string& group_id,
                const std::string& at_iso8601,
                starling::persistence::Connection& conn) {
                 f.record_group_membership(tenant_id, cognizer_id, group_id,
                                            at_iso8601, conn);
             },
             py::arg("tenant_id"), py::arg("cognizer_id"),
             py::arg("group_id"), py::arg("at"), py::arg("conn"))
        .def("record_explicit_negation",
             [](starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::string& cognizer_id,
                const std::string& referenced_statement_id,
                const std::string& source_engram_id,
                const std::string& observed_at,
                starling::persistence::Connection& conn) {
                 f.record_explicit_negation(tenant_id, cognizer_id,
                                             referenced_statement_id,
                                             source_engram_id, observed_at, conn);
             },
             py::arg("tenant_id"), py::arg("cognizer_id"),
             py::arg("referenced_statement_id"), py::arg("source_engram_id"),
             py::arg("observed_at"), py::arg("conn"))
        .def("visible_engrams_at",
             [](const starling::cognizer::KnowledgeFrontier& f,
                const std::string& tenant_id,
                const std::string& cognizer_id,
                const std::string& as_of) {
                 auto s = f.visible_engrams_at(tenant_id, cognizer_id, as_of);
                 return std::vector<std::string>(s.begin(), s.end());
             },
             py::arg("tenant_id"), py::arg("cognizer_id"), py::arg("as_of"));

    // Error types (§6.7)
    py::register_exception<starling::cognizer::AliasCollision>(
        m, "AliasCollision", PyExc_RuntimeError);
    py::register_exception<starling::cognizer::FiskeWeightsInvalid>(
        m, "FiskeWeightsInvalid", PyExc_ValueError);
    py::register_exception<starling::cognizer::GroupTenantImplicit>(
        m, "GroupTenantImplicit", PyExc_ValueError);
    py::register_exception<starling::cognizer::CognizerNotFound>(
        m, "CognizerNotFound", PyExc_KeyError);

    // ── 09_tom ─────────────────────────────────────────────────────────────

    // FactKey — read-write (builders need to set fields)
    py::class_<starling::tom::mentalizing::FactKey>(m, "FactKey")
        .def(py::init<>())
        .def(py::init([](std::string subject_kind,
                         std::string subject_id,
                         std::string predicate,
                         std::string canonical_object_hash) {
            return starling::tom::mentalizing::FactKey{
                std::move(subject_kind),
                std::move(subject_id),
                std::move(predicate),
                std::move(canonical_object_hash),
            };
        }),
        py::arg("subject_kind") = "",
        py::arg("subject_id") = "",
        py::arg("predicate") = "",
        py::arg("canonical_object_hash") = "")
        .def_readwrite("subject_kind",           &starling::tom::mentalizing::FactKey::subject_kind)
        .def_readwrite("subject_id",             &starling::tom::mentalizing::FactKey::subject_id)
        .def_readwrite("predicate",              &starling::tom::mentalizing::FactKey::predicate)
        .def_readwrite("canonical_object_hash",  &starling::tom::mentalizing::FactKey::canonical_object_hash);

    // KnowsResult enum
    py::enum_<starling::tom::mentalizing::KnowsResult>(m, "KnowsResult")
        .value("FullKnowledge", starling::tom::mentalizing::KnowsResult::FullKnowledge)
        .value("NotKnown",      starling::tom::mentalizing::KnowsResult::NotKnown)
        .value("Unknowable",    starling::tom::mentalizing::KnowsResult::Unknowable);

    // SharedFact — read-only
    py::class_<starling::tom::mentalizing::SharedFact>(m, "SharedFact")
        .def_readonly("subject_kind",           &starling::tom::mentalizing::SharedFact::subject_kind)
        .def_readonly("subject_id",             &starling::tom::mentalizing::SharedFact::subject_id)
        .def_readonly("predicate",              &starling::tom::mentalizing::SharedFact::predicate)
        .def_readonly("canonical_object_hash",  &starling::tom::mentalizing::SharedFact::canonical_object_hash)
        .def_readonly("polarity",               &starling::tom::mentalizing::SharedFact::polarity)
        .def_readonly("source_statement_ids",   &starling::tom::mentalizing::SharedFact::source_statement_ids);

    // Misalignment — read-only vectors; confidence_diverges exposed as list of
    // 2-tuples (x_row, y_row) via a property lambda.
    py::class_<starling::tom::mentalizing::Misalignment>(m, "Misalignment")
        .def_readonly("only_x_believes",  &starling::tom::mentalizing::Misalignment::only_x_believes)
        .def_readonly("only_y_believes",  &starling::tom::mentalizing::Misalignment::only_y_believes)
        .def_property_readonly("confidence_diverges",
            [](const starling::tom::mentalizing::Misalignment& m_) {
                py::list result;
                for (const auto& p : m_.confidence_diverges) {
                    result.append(py::make_tuple(p.first, p.second));
                }
                return result;
            });

    // CommonGroundEntry — read-only
    py::class_<starling::tom::CommonGroundEntry>(m, "CommonGroundEntry")
        .def_readonly("id",            &starling::tom::CommonGroundEntry::id)
        .def_readonly("tenant_id",     &starling::tom::CommonGroundEntry::tenant_id)
        .def_readonly("statement_id",  &starling::tom::CommonGroundEntry::statement_id)
        .def_readonly("status",        &starling::tom::CommonGroundEntry::status)
        .def_readonly("parties_json",  &starling::tom::CommonGroundEntry::parties_json)
        .def_readonly("created_at",    &starling::tom::CommonGroundEntry::created_at)
        .def_readonly("updated_at",    &starling::tom::CommonGroundEntry::updated_at);

    // Context — read-only snapshot from perspective_take
    py::class_<starling::tom::Context>(m, "Context")
        .def_readonly("visible_engram_ids",  &starling::tom::Context::visible_engram_ids)
        .def_readonly("target_beliefs",      &starling::tom::Context::target_beliefs)
        .def_readonly("cg",                  &starling::tom::Context::cg);

    // NestingDepthOverflow exception
    py::register_exception<starling::tom::NestingDepthOverflow>(
        m, "NestingDepthOverflow", PyExc_RecursionError);

    // ToMEngine — takes references to adapter/hub/frontier (keep_alive on all).
    py::class_<starling::tom::ToMEngine>(m, "ToMEngine")
        .def(py::init<starling::persistence::SqliteAdapter&,
                      starling::cognizer::CognizerHub&,
                      starling::cognizer::KnowledgeFrontier&>(),
             py::keep_alive<1, 2>(), py::keep_alive<1, 3>(), py::keep_alive<1, 4>(),
             py::arg("adapter"), py::arg("hub"), py::arg("frontier"))
        .def("perspective_take",
             [](const starling::tom::ToMEngine& eng,
                const std::string& target,
                const std::string& tenant,
                const std::string& as_of) {
                 return eng.perspective_take(target, tenant, as_of);
             },
             py::arg("target"), py::arg("tenant"), py::arg("as_of"));

    // Free function bindings for mentalizing primitives

    m.def("what_does_X_believe",
        [](starling::persistence::SqliteAdapter& adapter,
           const std::string& x,
           const std::string& about_y,
           const std::string& tenant,
           const std::string& as_of,
           const std::string& modality_filter) {
            return starling::tom::mentalizing::what_does_X_believe(
                adapter, x, about_y, tenant, as_of, modality_filter);
        },
        py::arg("adapter"), py::arg("x"), py::arg("about_y"),
        py::arg("tenant"), py::arg("as_of"), py::arg("modality_filter") = "",
        "Return all statements held by X about Y. Optional modality_filter.");

    m.def("does_X_know",
        [](starling::persistence::SqliteAdapter& adapter,
           starling::cognizer::KnowledgeFrontier& frontier,
           const std::string& x,
           const starling::tom::mentalizing::FactKey& fact,
           const std::string& tenant,
           const std::string& as_of) {
            return starling::tom::mentalizing::does_X_know(
                adapter, frontier, x, fact, tenant, as_of);
        },
        py::arg("adapter"), py::arg("frontier"), py::arg("x"),
        py::arg("fact"), py::arg("tenant"), py::arg("as_of"),
        "Tri-valued query: FullKnowledge / NotKnown / Unknowable.");

    m.def("find_misalignment",
        [](starling::persistence::SqliteAdapter& adapter,
           const std::string& x,
           const std::string& y,
           const std::string& subject_kind,
           const std::string& subject_id,
           const std::string& tenant,
           const std::string& as_of) {
            return starling::tom::mentalizing::find_misalignment(
                adapter, x, y, subject_kind, subject_id, tenant, as_of);
        },
        py::arg("adapter"), py::arg("x"), py::arg("y"),
        py::arg("subject_kind"), py::arg("subject_id"),
        py::arg("tenant"), py::arg("as_of"),
        "Find belief misalignments between cognizers X and Y.");

    m.def("shared_with",
        [](starling::persistence::SqliteAdapter& adapter,
           const std::vector<std::string>& members,
           const std::string& tenant,
           const std::string& as_of) {
            return starling::tom::mentalizing::shared_with(adapter, members, tenant, as_of);
        },
        py::arg("adapter"), py::arg("members"), py::arg("tenant"), py::arg("as_of"),
        "Return facts believed by ALL members.");

    // TickStats — read-only
    py::class_<starling::tom::belief_tracker::TickStats>(m, "TickStats")
        .def_readonly("events_processed",       &starling::tom::belief_tracker::TickStats::events_processed)
        .def_readonly("frontier_facts_written",  &starling::tom::belief_tracker::TickStats::frontier_facts_written)
        .def_readonly("trust_prior_updates",     &starling::tom::belief_tracker::TickStats::trust_prior_updates)
        .def_readonly("last_seen_updates",       &starling::tom::belief_tracker::TickStats::last_seen_updates)
        .def_readonly("presence_log_writes",     &starling::tom::belief_tracker::TickStats::presence_log_writes);

    // belief_tracker_tick — free function for Python consumers
    m.def("belief_tracker_tick",
        [](starling::persistence::SqliteAdapter& adapter, int batch_size) {
            return starling::tom::belief_tracker::tick_one_batch(adapter, batch_size);
        },
        py::arg("adapter"), py::arg("batch_size") = 100,
        "Process one batch of bus events through BeliefTracker. Returns TickStats.");
}
