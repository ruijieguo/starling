#include "starling/evidence/evidence_validator.hpp"
#include "starling/evidence/ingest_policy_resolver.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <set>
#include <string>

namespace starling::evidence {

namespace {

// P1 minimal ISO-8601 UTC check: "YYYY-MM-DDTHH:MM:SSZ" pattern, length 20+,
// 'T' separator, trailing 'Z'. Full RFC3339 parsing is deferred to a later
// milestone — this is enough to reject common producer mistakes.
bool is_iso8601_utc(const std::string& s) {
    return s.size() >= 20 && s.find('T') != std::string::npos && s.back() == 'Z';
}

ValidationOutcome make_reject(std::string reason) {
    return ValidationReject{std::move(reason)};
}

}  // namespace

ValidationOutcome EvidenceValidator::validate(
    const EngramInput& input,
    starling::persistence::Connection& conn) {

    // 1. Schema-shape checks.
    if (input.byte_preserving && !input.declared_transformations.empty()) {
        return make_reject("byte_preserving_requires_empty_transformations");
    }
    {
        std::set<std::string> seen;
        for (const auto& t : input.declared_transformations) {
            if (!seen.insert(t).second) {
                return make_reject("transformations_must_be_unique");
            }
        }
    }
    if (input.tenant_id.empty())
        return make_reject("required_field_missing:tenant_id");
    if (input.source.adapter_name.empty())
        return make_reject("required_field_missing:adapter_name");
    if (input.source.source_item_id.empty())
        return make_reject("required_field_missing:source_item_id");
    if (input.source.source_version.empty())
        return make_reject("required_field_missing:source_version");
    if (!is_iso8601_utc(input.created_at_iso8601))
        return make_reject("created_at_not_iso8601");

    // 2. Resolve IngestPolicy. EngramInput doesn't carry a producer-declared
    //    policy field in P1; we pass STORE so the resolver applies the
    //    self-pollution + privacy downgrade rules. Producer-declared NO_STORE
    //    is achievable via a future field on EngramInput; not in M0.3.
    const auto resolved = IngestPolicyResolver::resolve(
        input.source_kind, input.privacy_class, schema::IngestPolicy::STORE);

    // 3. NO_STORE short-circuits before the idempotency lookup.
    if (resolved == schema::IngestPolicy::NO_STORE) {
        return ValidationNoStore{};
    }

    // 4. Source-identity idempotency lookup within the caller's transaction.
    using starling::bus::detail::bind_sv;
    using starling::bus::detail::make_sqlite_error;
    using starling::persistence::StmtHandle;

    sqlite3* const db = conn.raw();
    sqlite3_stmt* sel_raw = nullptr;
    const char* sql =
        "SELECT id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "       privacy_class, retention_mode, adapter_version,"
        "       declared_transformations_json, byte_preserving,"
        "       redacted_content, created_at"
        "  FROM engrams"
        " WHERE tenant_id = ? AND adapter_name = ? AND source_item_id = ?"
        "   AND source_version = ? AND chunk_index = ?";
    if (sqlite3_prepare_v2(db, sql, -1, &sel_raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "EvidenceValidator: prepare idempotency SELECT");
    }
    StmtHandle sel(sel_raw);
    bind_sv(sel.get(), 1, input.tenant_id);
    bind_sv(sel.get(), 2, input.source.adapter_name);
    bind_sv(sel.get(), 3, input.source.source_item_id);
    bind_sv(sel.get(), 4, input.source.source_version);
    sqlite3_bind_int(sel.get(), 5, input.source.chunk_index);

    const int rc = sqlite3_step(sel.get());
    if (rc == SQLITE_ROW) {
        Engram existing;
        existing.id           = reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 0));
        existing.content_hash = reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 1));
        existing.tenant_id    = input.tenant_id;
        existing.source       = input.source;
        existing.source_kind  = schema::source_kind_from_string(
            reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 2)));
        existing.ingest_policy = schema::ingest_policy_from_string(
            reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 3)));
        existing.ingest_mode  = schema::ingest_mode_from_string(
            reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 4)));
        existing.privacy_class = schema::privacy_class_from_string(
            reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 5)));
        existing.retention_mode = schema::engram_retention_mode_from_string(
            reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 6)));
        existing.source.adapter_version =
            reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 7));
        // declared_transformations_json column 8: P1 leaves this unparsed on
        // the Engram POD (callers care about id + content_hash + retention_mode).
        existing.byte_preserving = sqlite3_column_int(sel.get(), 9) != 0;
        if (sqlite3_column_type(sel.get(), 10) != SQLITE_NULL) {
            existing.redacted_content =
                reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 10));
        }
        existing.created_at_iso8601 =
            reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 11));
        return ValidationIdempotentHit{std::move(existing)};
    }
    if (rc != SQLITE_DONE) {
        throw make_sqlite_error(db, "EvidenceValidator: step idempotency SELECT");
    }

    // 5. Proceed.
    return ValidationProceed{resolved};
}

}  // namespace starling::evidence
