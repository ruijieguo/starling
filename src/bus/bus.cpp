#include "starling/bus/bus.hpp"
#include "starling/bus/bus_event.hpp"
#include "starling/bus/conflict_probe.hpp"
#include "starling/bus/normalized_interval.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/bus/statement_writer.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/evidence/engram_store.hpp"
#include "starling/evidence/evidence_validator.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/enums.hpp"

#include <sqlite3.h>

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <optional>
#include <random>
#include <sstream>
#include <string>
#include <variant>

namespace starling::bus {

namespace {

std::string source_identity_hash(const starling::evidence::SourceIdentity& s) {
    std::string blob;
    blob.reserve(64 + s.adapter_name.size() + s.source_item_id.size() + s.source_version.size());
    blob += s.adapter_name;    blob += '\x1f';
    blob += s.source_item_id;  blob += '\x1f';
    blob += s.source_version;  blob += '\x1f';
    blob += std::to_string(s.chunk_index);
    return starling::crypto::sha256_hex(blob);
}

std::string json_string(std::string_view sv) {
    std::string out;
    out.reserve(sv.size() + 2);
    out.push_back('"');
    for (char c : sv) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x",
                                  static_cast<unsigned char>(c));
                    out += buf;
                } else {
                    out.push_back(c);
                }
        }
    }
    out.push_back('"');
    return out;
}

std::string accepted_payload(const starling::evidence::Engram& e) {
    std::ostringstream os;
    os << "{"
       << "\"engram_id\":"      << json_string(e.id) << ","
       << "\"content_hash\":"   << json_string(e.content_hash) << ","
       << "\"retention_mode\":" << json_string(starling::schema::to_string(e.retention_mode)) << ","
       << "\"source_kind\":"    << json_string(starling::schema::to_string(e.source_kind)) << ","
       << "\"tenant_id\":"      << json_string(e.tenant_id)
       << "}";
    return os.str();
}

std::string no_store_payload(const starling::evidence::EngramInput& i) {
    std::ostringstream os;
    os << "{"
       << "\"tenant_id\":"      << json_string(i.tenant_id) << ","
       << "\"source_kind\":"    << json_string(starling::schema::to_string(i.source_kind)) << ","
       << "\"privacy_class\":"  << json_string(starling::schema::to_string(i.privacy_class)) << ","
       << "\"adapter_name\":"   << json_string(i.source.adapter_name) << ","
       << "\"source_item_id\":" << json_string(i.source.source_item_id) << ","
       << "\"source_version\":" << json_string(i.source.source_version) << ","
       << "\"chunk_index\":"    << i.source.chunk_index << ","
       << "\"reason\":\"self_pollution_guard_or_producer_declared_no_store\""
       << "}";
    return os.str();
}

std::string idempotent_payload(const starling::evidence::Engram& existing) {
    std::ostringstream os;
    os << "{"
       << "\"existing_engram_id\":" << json_string(existing.id) << ","
       << "\"content_hash\":"       << json_string(existing.content_hash) << ","
       << "\"tenant_id\":"          << json_string(existing.tenant_id)
       << "}";
    return os.str();
}

BusEvent make_event(
    std::string_view event_type,
    std::string_view primary_id,
    std::string_view aggregate_id,
    std::string_view tenant_id,
    std::string payload_json,
    const std::optional<std::string>& causation_parent) {

    BusEvent e;
    e.tenant_id    = std::string(tenant_id);
    e.event_type   = std::string(event_type);
    e.primary_id   = std::string(primary_id);
    e.aggregate_id = std::string(aggregate_id);
    if (causation_parent) {
        e.causation_chain = { *causation_parent };
    }
    const std::string causation_root =
        e.causation_chain.empty() ? std::string{} : e.causation_chain.front();
    const std::string window_bucket = compute_window_bucket(
        event_type, std::chrono::system_clock::now());
    e.idempotency_key = compute_idempotency_key(
        event_type, aggregate_id, primary_id, causation_root, window_bucket);
    e.payload_json = std::move(payload_json);
    return e;
}

// 32 random hex chars for statement_edges.id. Per-edge primary key only —
// not stored in user-facing protocols, so no UUID-v4/v7 nibble bits required.
std::string random_edge_id() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%016llx%016llx",
                  static_cast<unsigned long long>(a),
                  static_cast<unsigned long long>(b));
    return std::string(buf, 32);
}

void insert_statement_edge(
    starling::persistence::Connection& conn,
    std::string_view src_id,
    std::string_view dst_id,
    std::string_view tenant_id,
    std::string_view edge_kind) {
    const char* sql =
        "INSERT INTO statement_edges(id, tenant_id, src_id, dst_id, edge_kind, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
        throw detail::make_sqlite_error(conn.raw(), "insert_statement_edge prepare");
    starling::persistence::StmtHandle h(raw);
    const std::string edge_id = random_edge_id();
    const std::string now_iso = detail::iso8601_utc(std::chrono::system_clock::now());
    detail::bind_sv(h.get(), 1, edge_id);
    detail::bind_sv(h.get(), 2, tenant_id);
    detail::bind_sv(h.get(), 3, src_id);
    detail::bind_sv(h.get(), 4, dst_id);
    detail::bind_sv(h.get(), 5, edge_kind);
    detail::bind_sv(h.get(), 6, now_iso);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw detail::make_sqlite_error(conn.raw(), "insert_statement_edge step");
}

std::string conflict_payload(const ConflictMatch& m, std::string_view new_stmt_id) {
    std::ostringstream os;
    os << "{"
       << "\"new_statement_id\":"  << json_string(new_stmt_id) << ","
       << "\"old_statement_id\":"  << json_string(m.matched_statement_id) << ","
       << "\"conflict_kind\":"     << json_string(to_string(m.kind)) << ","
       << "\"conflict_key\":"      << json_string(m.conflict_key_hex)
       << "}";
    return os.str();
}

}  // namespace

Bus::Bus(starling::persistence::SqliteAdapter& adapter) : adapter_(adapter) {}

AppendEvidenceOutcome Bus::append_evidence(
    const starling::evidence::EngramInput& input,
    std::optional<std::string> causation_parent_event_id) {

    auto& conn = adapter_.connection();
    starling::persistence::TransactionGuard tx(conn);
    OutboxWriter writer(conn);

    auto outcome = starling::evidence::EvidenceValidator::validate(input, conn);

    if (auto* rej = std::get_if<starling::evidence::ValidationReject>(&outcome)) {
        return AppendEvidenceRejected{rej->reason};
    }

    if (std::holds_alternative<starling::evidence::ValidationNoStore>(outcome)) {
        const std::string sid_hash = source_identity_hash(input.source);
        BusEvent ev = make_event(
            "evidence.no_store_audit",
            sid_hash, sid_hash,
            input.tenant_id,
            no_store_payload(input),
            causation_parent_event_id);
        writer.append_already_delivered(ev);
        tx.commit();
        return AppendEvidenceNoStore{ev.event_id};
    }

    if (auto* hit = std::get_if<starling::evidence::ValidationIdempotentHit>(&outcome)) {
        const auto& existing = hit->existing;
        BusEvent ev = make_event(
            "evidence.idempotent_hit",
            existing.id, existing.id,
            input.tenant_id,
            idempotent_payload(existing),
            causation_parent_event_id);
        writer.append_already_delivered(ev);
        tx.commit();
        return AppendEvidenceIdempotent{
            starling::evidence::EngramRef{existing.id, existing.content_hash, existing.retention_mode},
            ev.event_id};
    }

    auto& proceed = std::get<starling::evidence::ValidationProceed>(outcome);
    auto engram = starling::evidence::EngramStore::put(input, proceed.resolved_policy, conn);
    BusEvent ev = make_event(
        "evidence.appended",
        engram.id, engram.id,
        input.tenant_id,
        accepted_payload(engram),
        causation_parent_event_id);
    writer.append(ev);
    tx.commit();
    return AppendEvidenceAccepted{
        starling::evidence::EngramRef{engram.id, engram.content_hash, engram.retention_mode},
        ev.event_id,
        ev.outbox_sequence};
}

StatementWriteOutcome Bus::write(
    const starling::extractor::ExtractedStatement& stmt,
    std::string_view evidence_engram_id,
    std::string_view extraction_span_key,
    std::optional<std::string> causation_parent_event_id) {

    auto& conn = adapter_.connection();
    starling::persistence::TransactionGuard tx(conn);

    // M0.5: detect conflicts BEFORE writing so the partial_overlap / adjacent
    // edge writes (and direct_contradiction / superseding atomic SUPERSEDES in
    // Task 8) all happen in one transaction.
    const NormalizedInterval iv_new = normalize_interval(
        stmt.valid_from, stmt.valid_to, stmt.event_time_start);
    ConflictProbe probe(conn);
    const auto match = probe.scan(stmt, iv_new);

    StatementWriter writer(conn);
    auto outcome = writer.write(
        stmt, evidence_engram_id, extraction_span_key, causation_parent_event_id);

    if (match.has_value()) {
        const std::string new_stmt_id =
            std::visit([](auto&& v) -> std::string { return v.stmt_id; }, outcome);

        switch (match->kind) {
            case ConflictKind::DirectContradiction:
            case ConflictKind::Superseding:
                // TODO(M0.5 Task 8): replace fall-through with apply_supersedes_atomic(...).
                // For now, leave the new statement written without superseding S_old.
                break;

            case ConflictKind::PartialOverlap: {
                insert_statement_edge(
                    conn, new_stmt_id, match->matched_statement_id,
                    stmt.holder_tenant_id, "conflicts_with");

                // Build the belief.conflict event manually rather than via
                // make_event() because debounce semantics require the
                // canonical_key in the idempotency hash to be the
                // canonical_conflict_key (not primary_id). This pins
                // idempotency to (event_type, conflict_key, causation_root,
                // 10s window) so repeated belief.conflict emissions in the
                // same window collide on UNIQUE(idempotency_key) and the
                // catch below drops the dupes. primary_id stays = new_stmt_id
                // so the event row carries traceability back to S_new.
                BusEvent ev;
                ev.tenant_id    = stmt.holder_tenant_id;
                ev.event_type   = "belief.conflict";
                ev.primary_id   = new_stmt_id;
                ev.aggregate_id = match->conflict_key_hex;
                if (causation_parent_event_id) {
                    ev.causation_chain = { *causation_parent_event_id };
                }
                const std::string causation_root =
                    ev.causation_chain.empty() ? std::string{} : ev.causation_chain.front();
                const std::string window_bucket = compute_window_bucket(
                    "belief.conflict", std::chrono::system_clock::now());
                ev.idempotency_key = compute_idempotency_key(
                    "belief.conflict",
                    match->conflict_key_hex,   // aggregate_id
                    match->conflict_key_hex,   // canonical_key (debounce on conflict_key, not primary_id)
                    causation_root,
                    window_bucket);
                ev.payload_json = conflict_payload(*match, new_stmt_id);

                OutboxWriter ow(conn);
                try {
                    ow.append(ev);
                } catch (const starling::persistence::SqliteError& e) {
                    if (e.code() != SQLITE_CONSTRAINT_UNIQUE) throw;
                    // Debounced: another belief.conflict with the same
                    // canonical_conflict_key already landed in this 10s window.
                }
                break;
            }

            case ConflictKind::Adjacent:
                insert_statement_edge(
                    conn, new_stmt_id, match->matched_statement_id,
                    stmt.holder_tenant_id, "adjacent");
                break;
        }
    }

    tx.commit();
    return outcome;
}

}  // namespace starling::bus
