// bind_03_evidence — M0.3: schema enums / IngestPolicyResolver / SourceIdentity / EngramInput / EngramRef
// Split verbatim from bindings/python/module.cpp (original lines 367-434).
// Registration order across bind_01..bind_12 mirrors the original file and is
// load-bearing (pybind11 requires base classes registered before derived).

#include "bind_common.hpp"

#include "starling/schema/enums.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/evidence/ingest_policy_resolver.hpp"

namespace starling::bindings {

void bind_03_evidence(pybind11::module_& m) {
    using namespace pybind11::literals;

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
}

}  // namespace starling::bindings
