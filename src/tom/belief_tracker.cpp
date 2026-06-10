// belief_tracker.cpp -- BeliefTracker outbox subscriber main tick loop.
// Consumes bus_events from last_processed_outbox_sequence+1 onwards,
// dispatches to handlers, advances the checkpoint.
// Wraps all work in a SAVEPOINT so failures don't propagate (best-effort).

#include "starling/tom/belief_tracker.hpp"

#include "belief_tracker_internal.hpp"

#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>

#include <chrono>
#include <cstdio>
#include <string>
#include <vector>

namespace starling::tom::belief_tracker {

namespace {

using starling::persistence::detail::bind_sv;
using starling::persistence::StmtHandle;

struct EventRow {
    std::string event_id;
    std::string event_type;
    std::string primary_id;
    std::string aggregate_id;
    std::string tenant_id;
    std::string payload_json;
    int         outbox_sequence = 0;
};

}  // namespace

TickStats tick_one_batch(
    persistence::SqliteAdapter& adapter,
    int batch_size) {

    TickStats stats;
    auto& conn = adapter.connection();

    // Construct local Hub and Frontier -- they are stateless wrappers (Option B).
    cognizer::CognizerHub       hub(adapter);
    cognizer::KnowledgeFrontier frontier(adapter);

    // SAVEPOINT so any failure here cannot corrupt an outer transaction.
    try {
        conn.exec("SAVEPOINT belief_tracker_tick");
    } catch (...) {
        return stats;
    }

    try {
        // 1. Read checkpoint.
        int last_seq = 0;
        {
            const char* sql =
                "SELECT last_processed_outbox_sequence "
                "FROM tom_belief_tracker_checkpoint WHERE id = 1";
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
                throw starling::persistence::detail::make_sqlite_error(
                    conn.raw(), "belief_tracker: read checkpoint prepare");
            StmtHandle h(raw);
            if (sqlite3_step(h.get()) == SQLITE_ROW) {
                last_seq = sqlite3_column_int(h.get(), 0);
            }
        }

        // 2. SELECT next batch of events after checkpoint.
        std::vector<EventRow> batch;
        {
            const char* sql =
                "SELECT event_id, event_type, primary_id, aggregate_id, "
                "       tenant_id, payload_json, outbox_sequence "
                "FROM bus_events "
                "WHERE outbox_sequence > ? "
                "ORDER BY outbox_sequence "
                "LIMIT ?";
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
                throw starling::persistence::detail::make_sqlite_error(
                    conn.raw(), "belief_tracker: select events prepare");
            StmtHandle h(raw);
            sqlite3_bind_int(h.get(), 1, last_seq);
            sqlite3_bind_int(h.get(), 2, batch_size);
            while (sqlite3_step(h.get()) == SQLITE_ROW) {
                EventRow row;
                auto get_text = [&](int col) -> std::string {
                    const char* t = reinterpret_cast<const char*>(
                        sqlite3_column_text(h.get(), col));
                    return t ? t : "";
                };
                row.event_id        = get_text(0);
                row.event_type      = get_text(1);
                row.primary_id      = get_text(2);
                row.aggregate_id    = get_text(3);
                row.tenant_id       = get_text(4);
                row.payload_json    = get_text(5);
                row.outbox_sequence = sqlite3_column_int(h.get(), 6);
                batch.push_back(std::move(row));
            }
        }

        if (batch.empty()) {
            conn.exec("RELEASE SAVEPOINT belief_tracker_tick");
            return stats;
        }

        // 3. Dispatch each event to the appropriate handler.
        int max_seq = last_seq;
        for (const auto& ev : batch) {
            stats.events_processed++;
            if (ev.outbox_sequence > max_seq) max_seq = ev.outbox_sequence;

            try {
                if (ev.event_type == "statement.written") {
                    detail::handle_statement_written(
                        ev.tenant_id, ev.primary_id, ev.payload_json,
                        hub, frontier, conn, stats);
                } else if (ev.event_type == "evidence.appended") {
                    detail::handle_evidence_appended(
                        ev.tenant_id, ev.primary_id, ev.payload_json,
                        frontier, conn, stats);
                } else if (ev.event_type == "statement.archived") {
                    detail::handle_statement_archived(stats);
                } else if (ev.event_type == "statement.superseded") {
                    detail::handle_statement_superseded(stats);
                } else if (ev.event_type == "commitment.fulfilled") {
                    detail::handle_commitment_fulfilled(stats);
                } else if (ev.event_type == "commitment.broken") {
                    detail::handle_commitment_broken(stats);
                }
                // Unknown event types are silently skipped.
            } catch (const std::exception& e) {
                std::fprintf(stderr,
                    "[belief_tracker] WARN event %s (%s) handler threw: %s\n",
                    ev.event_id.c_str(), ev.event_type.c_str(), e.what());
            } catch (...) {
                std::fprintf(stderr,
                    "[belief_tracker] WARN event %s (%s) handler threw unknown\n",
                    ev.event_id.c_str(), ev.event_type.c_str());
            }
        }

        // 4. Advance checkpoint to max processed sequence.
        {
            const char* sql =
                "UPDATE tom_belief_tracker_checkpoint "
                "SET last_processed_outbox_sequence = ?, "
                "    last_updated_at = ? "
                "WHERE id = 1";
            sqlite3_stmt* raw = nullptr;
            if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK)
                throw starling::persistence::detail::make_sqlite_error(
                    conn.raw(), "belief_tracker: update checkpoint prepare");
            StmtHandle h(raw);
            sqlite3_bind_int(h.get(), 1, max_seq);
            const std::string now =
                starling::persistence::detail::iso8601_utc(std::chrono::system_clock::now());
            bind_sv(h.get(), 2, now);
            if (sqlite3_step(h.get()) != SQLITE_DONE)
                throw starling::persistence::detail::make_sqlite_error(
                    conn.raw(), "belief_tracker: update checkpoint step");
        }

        conn.exec("RELEASE SAVEPOINT belief_tracker_tick");

    } catch (...) {
        try {
            conn.exec("ROLLBACK TO SAVEPOINT belief_tracker_tick");
            conn.exec("RELEASE SAVEPOINT belief_tracker_tick");
        } catch (...) {}
        // Return zeroed stats -- tick failure is best-effort.
        return TickStats{};
    }

    return stats;
}

}  // namespace starling::tom::belief_tracker
