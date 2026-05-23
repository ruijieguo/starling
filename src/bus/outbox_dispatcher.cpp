#include "starling/bus/outbox_dispatcher.hpp"

#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <chrono>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace starling::bus {

using detail::bind_sv;
using detail::iso8601_utc;
using detail::make_sqlite_error;

namespace {

// Read a TEXT column as std::string. SQLite returns NULL for unset TEXT
// columns; treat that as the empty string so callers don't have to special-case
// it (this matches how BusEvent fields are populated from new rows).
std::string read_text(sqlite3_stmt* s, int col) {
    const auto* p = sqlite3_column_text(s, col);
    return p ? std::string(reinterpret_cast<const char*>(p)) : std::string();
}

}  // namespace

OutboxDispatcher::OutboxDispatcher(
        starling::persistence::Connection& conn,
        Consumer consumer,
        DispatchOptions opts)
    : conn_(conn), consumer_(std::move(consumer)), opts_(std::move(opts)) {}

DispatchStats OutboxDispatcher::run_once() {
    DispatchStats stats;
    sqlite3* const db = conn_.raw();

    // Crash recovery: reset any in_flight events back to pending. This handles
    // the TC-NEW-OUTBOX-IDEMP crash scenario where the process died after a row
    // was flipped to in_flight but before the consumer outcome was recorded.
    // Run BEFORE the SELECT so the snapshot picks up the recovered rows.
    conn_.exec("UPDATE bus_events SET dispatch_status='pending' "
               "WHERE dispatch_status='in_flight'");

    // Snapshot pending events by ascending outbox_sequence.
    std::vector<BusEvent> pending;
    std::vector<int> attempts;
    {
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db,
                "SELECT event_id,tenant_id,event_type,primary_id,aggregate_id,"
                "outbox_sequence,causation_chain_json,idempotency_key,payload_json,"
                "created_at,version,dispatch_attempts "
                "FROM bus_events WHERE dispatch_status='pending' "
                "ORDER BY outbox_sequence ASC LIMIT ?",
                -1, &raw, nullptr) != SQLITE_OK) {
            throw make_sqlite_error(db,
                "OutboxDispatcher::run_once: prepare SELECT pending failed");
        }
        starling::persistence::StmtHandle h(raw);
        sqlite3_bind_int(h.get(), 1, opts_.max_events_per_run);
        while (sqlite3_step(h.get()) == SQLITE_ROW) {
            BusEvent ev;
            ev.event_id        = read_text(h.get(), 0);
            ev.tenant_id       = read_text(h.get(), 1);
            ev.event_type      = read_text(h.get(), 2);
            ev.primary_id      = read_text(h.get(), 3);
            ev.aggregate_id    = read_text(h.get(), 4);
            ev.outbox_sequence = sqlite3_column_int64(h.get(), 5);
            ev.idempotency_key = read_text(h.get(), 7);
            ev.payload_json    = read_text(h.get(), 8);
            ev.created_at      = read_text(h.get(), 9);
            ev.version         = read_text(h.get(), 10);
            // causation_chain_json (col 6) is opaque on this side; Task 8
            // parses it when needed. Leave ev.causation_chain empty here.
            pending.push_back(std::move(ev));
            attempts.push_back(sqlite3_column_int(h.get(), 11));
        }
    }

    std::set<std::string> blocked_aggregates;

    ConsumerCheckpoint cp(conn_);
    IdempotencyInbox inbox(conn_);
    OutboxWriter writer(conn_);

    for (std::size_t i = 0; i < pending.size(); ++i) {
        BusEvent& ev = pending[i];

        // Per-aggregate ordering: once an earlier event for this aggregate was
        // retried or dead-lettered this run, do not advance past it for the
        // same aggregate.
        if (blocked_aggregates.contains(ev.aggregate_id)) {
            ++stats.skipped_blocked;
            continue;
        }

        // Mark in_flight outside the consumer call so a crash mid-call leaves
        // a recoverable trail that the next run_once() will reset to pending.
        {
            starling::persistence::TransactionGuard g(conn_);
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db,
                    "UPDATE bus_events SET dispatch_status='in_flight', "
                    "last_attempt_at=? WHERE event_id=? AND dispatch_status='pending'",
                    -1, &raw, nullptr) != SQLITE_OK) {
                throw make_sqlite_error(db,
                    "OutboxDispatcher::run_once: prepare UPDATE in_flight failed");
            }
            starling::persistence::StmtHandle h(raw);
            const std::string ts = iso8601_utc(std::chrono::system_clock::now());
            bind_sv(h.get(), 1, ts);
            bind_sv(h.get(), 2, ev.event_id);
            if (sqlite3_step(h.get()) != SQLITE_DONE) {
                throw make_sqlite_error(db,
                    "OutboxDispatcher::run_once: UPDATE in_flight step failed");
            }
            g.commit();
        }

        // Invoke consumer. Exceptions count as transient failures.
        ConsumerDecision decision = ConsumerDecision::TransientError;
        std::string err;
        try {
            decision = consumer_(ev);
        } catch (const std::exception& e) {
            err = e.what();
        }

        const int new_attempts = attempts[i] + 1;

        if (decision == ConsumerDecision::Accept) {
            starling::persistence::TransactionGuard g(conn_);
            const bool fresh = inbox.record_if_new(
                opts_.consumer_id, ev.idempotency_key,
                std::chrono::system_clock::now(), opts_.inbox_ttl);
            (void)fresh;  // Inbox dedup is observed at the consumer side; both
                          // branches commit delivered here.
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db,
                    "UPDATE bus_events SET dispatch_status='delivered',"
                    "dispatch_attempts=?, last_attempt_at=? WHERE event_id=?",
                    -1, &raw, nullptr) != SQLITE_OK) {
                throw make_sqlite_error(db,
                    "OutboxDispatcher::run_once: prepare UPDATE delivered failed");
            }
            starling::persistence::StmtHandle h(raw);
            const std::string ts = iso8601_utc(std::chrono::system_clock::now());
            sqlite3_bind_int(h.get(), 1, new_attempts);
            bind_sv(h.get(), 2, ts);
            bind_sv(h.get(), 3, ev.event_id);
            if (sqlite3_step(h.get()) != SQLITE_DONE) {
                throw make_sqlite_error(db,
                    "OutboxDispatcher::run_once: UPDATE delivered step failed");
            }
            cp.advance(opts_.consumer_id, ev.outbox_sequence);
            g.commit();
            ++stats.delivered;
            continue;
        }

        const bool exhausted =
            decision == ConsumerDecision::PermanentError
            || new_attempts >= opts_.max_retries;

        if (!exhausted) {
            starling::persistence::TransactionGuard g(conn_);
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db,
                    "UPDATE bus_events SET dispatch_status='pending',"
                    "dispatch_attempts=?, last_attempt_at=?, last_error=? "
                    "WHERE event_id=?",
                    -1, &raw, nullptr) != SQLITE_OK) {
                throw make_sqlite_error(db,
                    "OutboxDispatcher::run_once: prepare UPDATE retry failed");
            }
            starling::persistence::StmtHandle h(raw);
            const std::string ts = iso8601_utc(std::chrono::system_clock::now());
            const std::string error_text =
                err.empty() ? std::string("transient_error") : err;
            sqlite3_bind_int(h.get(), 1, new_attempts);
            bind_sv(h.get(), 2, ts);
            bind_sv(h.get(), 3, error_text);
            bind_sv(h.get(), 4, ev.event_id);
            if (sqlite3_step(h.get()) != SQLITE_DONE) {
                throw make_sqlite_error(db,
                    "OutboxDispatcher::run_once: UPDATE retry step failed");
            }
            g.commit();
            ++stats.retried;
            blocked_aggregates.insert(ev.aggregate_id);
            continue;
        }

        // Dead-letter path: flip the row to dead_letter and emit
        // system.delivery_failed with dispatch_status='delivered' so the
        // dispatcher never re-picks it up (recursion guard).
        {
            starling::persistence::TransactionGuard g(conn_);
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(db,
                    "UPDATE bus_events SET dispatch_status='dead_letter',"
                    "dispatch_attempts=?, last_attempt_at=?, last_error=? "
                    "WHERE event_id=?",
                    -1, &raw, nullptr) != SQLITE_OK) {
                throw make_sqlite_error(db,
                    "OutboxDispatcher::run_once: prepare UPDATE dead_letter failed");
            }
            starling::persistence::StmtHandle h(raw);
            const std::string ts = iso8601_utc(std::chrono::system_clock::now());
            const std::string error_text =
                err.empty() ? std::string("permanent_error") : err;
            sqlite3_bind_int(h.get(), 1, new_attempts);
            bind_sv(h.get(), 2, ts);
            bind_sv(h.get(), 3, error_text);
            bind_sv(h.get(), 4, ev.event_id);
            if (sqlite3_step(h.get()) != SQLITE_DONE) {
                throw make_sqlite_error(db,
                    "OutboxDispatcher::run_once: UPDATE dead_letter step failed");
            }

            // Emit system.delivery_failed with dispatch_status='delivered'.
            // Payload is just the original event_id; downstream consumers can
            // load the full failed row from bus_events if they need more.
            BusEvent failure_evt{
                .tenant_id = ev.tenant_id,
                .event_type = "system.delivery_failed",
                .primary_id = ev.event_id,
                .aggregate_id = ev.aggregate_id,
                .causation_chain = {ev.event_id},
                .idempotency_key = ev.idempotency_key + ":delivery_failed",
                .payload_json = std::string("{\"failed_event_id\":\"")
                                + ev.event_id + "\"}",
            };
            writer.append_already_delivered(failure_evt);
            g.commit();
        }
        ++stats.dead_lettered;
        blocked_aggregates.insert(ev.aggregate_id);
    }

    return stats;
}

}  // namespace starling::bus
