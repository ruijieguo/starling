#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <chrono>
#include <iomanip>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>

namespace starling::bus {

using persistence::detail::bind_sv;
using persistence::detail::iso8601_utc;
using persistence::detail::make_sqlite_error;

namespace {

// 128 random bits formatted with UUID dashes — NOT a valid UUID of any version
// (version/variant nibbles are not set). Sufficient for M0.2 because event_id
// is purely a primary key; outbox_sequence is the ordering key. M0.4 will
// replace this with real UUIDv7 alongside the LLM extractor.
std::string random_event_id() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    std::ostringstream oss;
    oss << std::hex << std::setfill('0')
        << std::setw(8) << static_cast<std::uint32_t>(a >> 32) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(a >> 16) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(a) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(b >> 48) << '-'
        << std::setw(12) << (b & 0xFFFFFFFFFFFFULL);
    return oss.str();
}

std::string causation_chain_json(const std::vector<std::string>& chain) {
    // Chain entries are UUIDs (from event_id) — no JSON-escaping needed.
    std::ostringstream oss;
    oss << '[';
    for (std::size_t i = 0; i < chain.size(); ++i) {
        if (i != 0) oss << ',';
        oss << '"' << chain[i] << '"';
    }
    oss << ']';
    return oss.str();
}

}  // namespace

int64_t OutboxWriter::claim_next_sequence() {
    sqlite3* const db = conn_.raw();

    // SELECT current next_value.
    sqlite3_stmt* sel_raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "SELECT next_value FROM outbox_sequence_counter WHERE id=1",
            -1, &sel_raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "claim_next_sequence: prepare SELECT failed");
    }
    starling::persistence::StmtHandle sel(sel_raw);
    const int sel_rc = sqlite3_step(sel.get());
    if (sel_rc != SQLITE_ROW) {
        if (sel_rc == SQLITE_DONE) {
            throw std::runtime_error(
                "claim_next_sequence: outbox_sequence_counter row id=1 missing "
                "(migration 0001 should have seeded it)");
        }
        throw make_sqlite_error(db, "claim_next_sequence: SELECT step failed");
    }
    const std::int64_t claimed = sqlite3_column_int64(sel.get(), 0);

    // UPDATE next_value = next_value + 1.
    sqlite3_stmt* upd_raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "UPDATE outbox_sequence_counter SET next_value = next_value + 1 WHERE id=1",
            -1, &upd_raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "claim_next_sequence: prepare UPDATE failed");
    }
    starling::persistence::StmtHandle upd(upd_raw);
    if (sqlite3_step(upd.get()) != SQLITE_DONE) {
        throw make_sqlite_error(db, "claim_next_sequence: UPDATE step failed");
    }
    return claimed;
}

void OutboxWriter::append(BusEvent& ev) {
    append_impl(ev, "pending", /*or_ignore=*/false);
}

void OutboxWriter::append_already_delivered(BusEvent& ev) {
    // Fire-and-forget audit/notification events (evidence.idempotent_hit /
    // no_store_audit / dispatch-failure pings): the idempotency_key + 60s
    // window bucket IS their dedup contract, so a second identical emission
    // within one window is dropped silently instead of failing the caller.
    // QA repro that motivated this: re-remember the same text twice within
    // 60s — the second evidence.idempotent_hit collided on
    // bus_events.idempotency_key UNIQUE and 500'd /api/remember.
    // (A claimed outbox_sequence is wasted on the dropped row; consumers
    // checkpoint by last-processed sequence, gaps are fine.)
    append_impl(ev, "delivered", /*or_ignore=*/true);
}

void OutboxWriter::append_impl(BusEvent& ev, const char* dispatch_status, bool or_ignore) {
    if (ev.tenant_id.empty() || ev.event_type.empty()
        || ev.aggregate_id.empty() || ev.idempotency_key.empty()
        || ev.primary_id.empty() || ev.payload_json.empty()) {
        throw std::invalid_argument("OutboxWriter::append: required field empty");
    }
    if (ev.causation_chain.size() > 3) {
        throw std::invalid_argument("OutboxWriter::append: causation_chain length > 3");
    }
    if (ev.event_id.empty())   ev.event_id = random_event_id();
    if (ev.created_at.empty()) ev.created_at = iso8601_utc(std::chrono::system_clock::now());
    ev.outbox_sequence = claim_next_sequence();

    sqlite3* const db = conn_.raw();
    const char* const sql = or_ignore
        ? "INSERT OR IGNORE INTO bus_events("
          "event_id,tenant_id,event_type,primary_id,aggregate_id,outbox_sequence,"
          "causation_chain_json,idempotency_key,payload_json,created_at,version,"
          "dispatch_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)"
        : "INSERT INTO bus_events("
          "event_id,tenant_id,event_type,primary_id,aggregate_id,outbox_sequence,"
          "causation_chain_json,idempotency_key,payload_json,created_at,version,"
          "dispatch_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)";
    sqlite3_stmt* ins_raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &ins_raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "OutboxWriter::append: prepare INSERT failed");
    }
    starling::persistence::StmtHandle s(ins_raw);
    const std::string chain_json = causation_chain_json(ev.causation_chain);

    bind_sv(s.get(),  1, ev.event_id);
    bind_sv(s.get(),  2, ev.tenant_id);
    bind_sv(s.get(),  3, ev.event_type);
    bind_sv(s.get(),  4, ev.primary_id);
    bind_sv(s.get(),  5, ev.aggregate_id);
    sqlite3_bind_int64(s.get(), 6, ev.outbox_sequence);
    bind_sv(s.get(),  7, chain_json);
    bind_sv(s.get(),  8, ev.idempotency_key);
    bind_sv(s.get(),  9, ev.payload_json);
    bind_sv(s.get(), 10, ev.created_at);
    bind_sv(s.get(), 11, ev.version);
    sqlite3_bind_text(s.get(), 12, dispatch_status, -1, SQLITE_STATIC);

    if (sqlite3_step(s.get()) != SQLITE_DONE) {
        throw make_sqlite_error(db, "OutboxWriter::append: bus_events INSERT failed");
    }
}

}  // namespace starling::bus
