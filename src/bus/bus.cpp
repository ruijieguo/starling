#include "starling/bus/bus.hpp"
#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/bus/statement_writer.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/evidence/engram_store.hpp"
#include "starling/evidence/evidence_validator.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/schema/enums.hpp"

#include <chrono>
#include <cstdio>
#include <optional>
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
    StatementWriter writer(conn);
    auto outcome = writer.write(
        stmt, evidence_engram_id, extraction_span_key, std::move(causation_parent_event_id));
    tx.commit();
    return outcome;
}

}  // namespace starling::bus
