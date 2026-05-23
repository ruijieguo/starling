#include "starling/evidence/engram_store.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/crypto/null_kms.hpp"
#include "starling/evidence/engram.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/enums.hpp"

#include <iomanip>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>

namespace starling::evidence {

namespace {

// UUIDv4 with RFC 4122 variant bits. Sufficient for M0.3; M0.4 may switch to
// UUIDv7 for time-ordered ids if Bus.write performance requires it.
std::string generate_uuid_v4() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    std::uint8_t bytes[16];
    for (int i = 0; i < 8; ++i) bytes[i]     = static_cast<std::uint8_t>((a >> (i * 8)) & 0xff);
    for (int i = 0; i < 8; ++i) bytes[i + 8] = static_cast<std::uint8_t>((b >> (i * 8)) & 0xff);
    bytes[6] = static_cast<std::uint8_t>((bytes[6] & 0x0f) | 0x40);  // version 4
    bytes[8] = static_cast<std::uint8_t>((bytes[8] & 0x3f) | 0x80);  // variant 10xx

    static constexpr char kHex[] = "0123456789abcdef";
    std::string out(36, '-');
    std::size_t j = 0;
    for (int i = 0; i < 16; ++i) {
        if (i == 4 || i == 6 || i == 8 || i == 10) { out[j++] = '-'; }
        out[j++] = kHex[(bytes[i] >> 4) & 0x0f];
        out[j++] = kHex[bytes[i] & 0x0f];
    }
    return out;
}

// JSON-array encode the transformation list. P1 vocabulary is ASCII identifiers
// (validator enforces non-duplicate; adapter conformance defines the set), so
// no JSON escaping is required.
std::string transformations_json(const std::vector<std::string>& t) {
    std::string out = "[";
    bool first = true;
    for (const auto& s : t) {
        if (!first) out.push_back(',');
        out.push_back('"');
        out.append(s);
        out.push_back('"');
        first = false;
    }
    out.push_back(']');
    return out;
}

}  // namespace

Engram EngramStore::put(
    const EngramInput& input,
    schema::IngestPolicy resolved_policy,
    starling::persistence::Connection& conn) {

    if (resolved_policy == schema::IngestPolicy::NO_STORE) {
        throw std::invalid_argument(
            "EngramStore::put called with NO_STORE; caller must short-circuit");
    }

    Engram e;
    e.id                       = generate_uuid_v4();
    e.tenant_id                = input.tenant_id;
    e.source                   = input.source;
    e.source_kind              = input.source_kind;
    e.ingest_policy            = resolved_policy;
    e.ingest_mode              = input.ingest_mode;
    e.privacy_class            = input.privacy_class;
    e.retention_mode           = input.retention_mode;
    e.declared_transformations = input.declared_transformations;
    e.byte_preserving          = input.byte_preserving;
    e.content_hash             = compute_engram_content_hash(
                                     input.payload_bytes,
                                     input.declared_transformations);
    e.key_ref                  = starling::crypto::NullKms::generate_key_ref();
    e.content_ciphertext       = starling::crypto::NullKms::encrypt(
                                     input.payload_bytes, /*key_ref=*/"");
    e.redacted_content         = input.redacted_content;
    e.refcount                 = 0;
    e.created_at_iso8601       = input.created_at_iso8601;
    e.erased_at_iso8601        = std::nullopt;

    using starling::bus::detail::bind_sv;
    using starling::bus::detail::make_sqlite_error;
    using starling::persistence::StmtHandle;

    sqlite3* const db = conn.raw();
    sqlite3_stmt* ins_raw = nullptr;
    const char* sql =
        "INSERT INTO engrams("
        "  id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "  privacy_class, retention_mode, refcount, payload_uri, payload_inline,"
        "  created_at, erased_at,"
        "  adapter_name, adapter_version, source_item_id, source_version, chunk_index,"
        "  declared_transformations_json, byte_preserving, redacted_content,"
        "  key_ref, audit_trail_json"
        ") VALUES ("
        "  ?, ?, ?, ?, ?, ?,"
        "  ?, ?, 0, NULL, ?,"
        "  ?, NULL,"
        "  ?, ?, ?, ?, ?,"
        "  ?, ?, ?,"
        "  NULL, '[]'"
        ");";
    if (sqlite3_prepare_v2(db, sql, -1, &ins_raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "EngramStore::put: prepare INSERT");
    }
    StmtHandle ins(ins_raw);

    int i = 1;
    bind_sv(ins.get(), i++, e.id);
    bind_sv(ins.get(), i++, e.tenant_id);
    bind_sv(ins.get(), i++, e.content_hash);
    bind_sv(ins.get(), i++, schema::to_string(e.source_kind));
    bind_sv(ins.get(), i++, schema::to_string(e.ingest_policy));
    bind_sv(ins.get(), i++, schema::to_string(e.ingest_mode));
    bind_sv(ins.get(), i++, schema::to_string(e.privacy_class));
    bind_sv(ins.get(), i++, schema::to_string(e.retention_mode));
    sqlite3_bind_blob(ins.get(), i++,
        e.content_ciphertext.data(),
        static_cast<int>(e.content_ciphertext.size()),
        SQLITE_TRANSIENT);  // payload_inline
    bind_sv(ins.get(), i++, e.created_at_iso8601);
    bind_sv(ins.get(), i++, e.source.adapter_name);
    bind_sv(ins.get(), i++, e.source.adapter_version);
    bind_sv(ins.get(), i++, e.source.source_item_id);
    bind_sv(ins.get(), i++, e.source.source_version);
    sqlite3_bind_int(ins.get(), i++, e.source.chunk_index);
    const std::string transforms_json = transformations_json(e.declared_transformations);
    bind_sv(ins.get(), i++, transforms_json);
    sqlite3_bind_int(ins.get(), i++, e.byte_preserving ? 1 : 0);
    if (e.redacted_content) bind_sv(ins.get(), i++, *e.redacted_content);
    else                    sqlite3_bind_null(ins.get(), i++);

    if (sqlite3_step(ins.get()) != SQLITE_DONE) {
        throw make_sqlite_error(db, "EngramStore::put: step INSERT");
    }
    return e;
}

std::optional<Engram> EngramStore::get(
    std::string_view id,
    std::string_view tenant_id,
    starling::persistence::Connection& conn) {

    using starling::bus::detail::bind_sv;
    using starling::bus::detail::make_sqlite_error;
    using starling::persistence::StmtHandle;

    sqlite3* const db = conn.raw();
    sqlite3_stmt* sel_raw = nullptr;
    const char* sql =
        "SELECT id, tenant_id, content_hash, source_kind, ingest_policy, ingest_mode,"
        "       privacy_class, retention_mode, refcount, payload_inline,"
        "       created_at, erased_at,"
        "       adapter_name, adapter_version, source_item_id, source_version, chunk_index,"
        "       declared_transformations_json, byte_preserving, redacted_content, key_ref"
        "  FROM engrams"
        " WHERE id = ? AND tenant_id = ?;";
    if (sqlite3_prepare_v2(db, sql, -1, &sel_raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "EngramStore::get: prepare SELECT");
    }
    StmtHandle sel(sel_raw);
    bind_sv(sel.get(), 1, id);
    bind_sv(sel.get(), 2, tenant_id);

    const int rc = sqlite3_step(sel.get());
    if (rc == SQLITE_DONE) return std::nullopt;
    if (rc != SQLITE_ROW) {
        throw make_sqlite_error(db, "EngramStore::get: step SELECT");
    }

    Engram e;
    e.id              = reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 0));
    e.tenant_id       = reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 1));
    e.content_hash    = reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 2));
    e.source_kind     = schema::source_kind_from_string(
        reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 3)));
    e.ingest_policy   = schema::ingest_policy_from_string(
        reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 4)));
    e.ingest_mode     = schema::ingest_mode_from_string(
        reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 5)));
    e.privacy_class   = schema::privacy_class_from_string(
        reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 6)));
    e.retention_mode  = schema::engram_retention_mode_from_string(
        reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 7)));
    e.refcount        = sqlite3_column_int64(sel.get(), 8);

    // payload_inline (column 9) — BLOB; null if a future row stored only metadata.
    if (sqlite3_column_type(sel.get(), 9) != SQLITE_NULL) {
        const void* blob = sqlite3_column_blob(sel.get(), 9);
        const int   size = sqlite3_column_bytes(sel.get(), 9);
        const auto* p = static_cast<const std::uint8_t*>(blob);
        e.content_ciphertext.assign(p, p + size);
    }

    e.created_at_iso8601 = reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 10));
    if (sqlite3_column_type(sel.get(), 11) != SQLITE_NULL) {
        e.erased_at_iso8601 =
            reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 11));
    }
    e.source.adapter_name    = reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 12));
    e.source.adapter_version = reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 13));
    e.source.source_item_id  = reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 14));
    e.source.source_version  = reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 15));
    e.source.chunk_index     = sqlite3_column_int(sel.get(), 16);
    // column 17 declared_transformations_json: P1 leaves the field unparsed
    // on the Engram POD. content_hash already reflects the same vocabulary.
    e.byte_preserving = sqlite3_column_int(sel.get(), 18) != 0;
    if (sqlite3_column_type(sel.get(), 19) != SQLITE_NULL) {
        e.redacted_content =
            reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 19));
    }
    if (sqlite3_column_type(sel.get(), 20) != SQLITE_NULL) {
        e.key_ref = reinterpret_cast<const char*>(sqlite3_column_text(sel.get(), 20));
    }
    return e;
}

}  // namespace starling::evidence
