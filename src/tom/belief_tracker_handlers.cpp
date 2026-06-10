// belief_tracker_handlers.cpp — handler functions for BeliefTracker event dispatch.
// Each handler is called by belief_tracker.cpp for a specific event_type.
// Handlers are best-effort: callers wrap them in try/catch.

#include "belief_tracker_internal.hpp"

#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <nlohmann/json.hpp>
#include <sqlite3.h>

#include <chrono>
#include <cstdio>
#include <string>
#include <vector>

namespace starling::tom::belief_tracker::detail {

using starling::persistence::detail::bind_sv;
using starling::persistence::detail::iso8601_utc;
using starling::persistence::StmtHandle;

// ---------------------------------------------------------------------------
// handle_statement_written
// Payload fields (from StatementWriter::statement_written_payload):
//   stmt_id, tenant_id, holder_id, holder_perspective, predicate,
//   canonical_object_hash, consolidation_state, review_status,
//   extraction_span_key, engram_ref_id
//
// perceived_by is stored in statements.perceived_by_json (not in the event
// payload), so we look it up from the DB.
// ---------------------------------------------------------------------------
void handle_statement_written(
    const std::string& tenant_id,
    const std::string& primary_id,   // stmt_id
    const std::string& payload_json,
    cognizer::CognizerHub& hub,
    cognizer::KnowledgeFrontier& frontier,
    persistence::Connection& conn,
    TickStats& stats) {

    nlohmann::json j;
    try {
        j = nlohmann::json::parse(payload_json);
    } catch (...) {
        return;
    }

    const std::string stmt_id = j.value("stmt_id", primary_id);
    const std::string engram_ref_id = j.value("engram_ref_id", std::string{});
    if (engram_ref_id.empty()) return;

    // Look up observed_at from the statements table.
    std::string observed_at;
    std::string perceived_by_json_str;
    {
        const char* sql =
            "SELECT observed_at, perceived_by_json FROM statements "
            "WHERE id = ? AND tenant_id = ? LIMIT 1";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) return;
        StmtHandle h(raw);
        bind_sv(h.get(), 1, stmt_id);
        bind_sv(h.get(), 2, tenant_id);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            auto get_text = [&](int col) -> std::string {
                const char* t = reinterpret_cast<const char*>(
                    sqlite3_column_text(h.get(), col));
                return t ? t : "";
            };
            observed_at        = get_text(0);
            perceived_by_json_str = get_text(1);
        }
    }
    if (observed_at.empty()) {
        observed_at = iso8601_utc(std::chrono::system_clock::now());
    }

    // Parse perceived_by array.
    std::vector<std::string> perceived_by;
    try {
        auto pj = nlohmann::json::parse(perceived_by_json_str.empty() ? "[]" : perceived_by_json_str);
        if (pj.is_array()) {
            for (const auto& item : pj) {
                if (item.is_string()) {
                    perceived_by.push_back(item.get<std::string>());
                }
            }
        }
    } catch (...) {}

    if (perceived_by.empty()) return;

    // 1. record_explicit_told for each perceived_by cognizer.
    frontier.record_explicit_told(
        tenant_id, perceived_by, stmt_id, engram_ref_id, observed_at, conn);
    stats.frontier_facts_written += static_cast<int>(perceived_by.size());

    // 2. record_presence_from_statement.
    frontier.record_presence_from_statement(
        tenant_id, perceived_by, engram_ref_id, observed_at, conn);
    stats.presence_log_writes += static_cast<int>(perceived_by.size());

    // 3. update_last_seen_at for each cognizer in perceived_by.
    for (const auto& cognizer_id : perceived_by) {
        try {
            hub.update_last_seen_at(cognizer_id, tenant_id, observed_at);
            stats.last_seen_updates++;
        } catch (...) {}
    }

    // 4. negation_subject — P2.a v11 prompt has no such field; skip if absent.
    // (P2.a v12+ may add this; no-op if absent)
}

// ---------------------------------------------------------------------------
// handle_evidence_appended
// Payload fields (from Bus::accepted_payload):
//   engram_id, content_hash, retention_mode, source_kind, tenant_id
//
// adapter_name is looked up from the engrams table using engram_id.
// ---------------------------------------------------------------------------
void handle_evidence_appended(
    const std::string& tenant_id,
    const std::string& primary_id,   // engram_id
    const std::string& payload_json,
    cognizer::KnowledgeFrontier& frontier,
    persistence::Connection& conn,
    TickStats& stats) {

    nlohmann::json j;
    try {
        j = nlohmann::json::parse(payload_json);
    } catch (...) {
        return;
    }

    const std::string engram_id = j.value("engram_id", primary_id);
    if (engram_id.empty()) return;

    // Fetch adapter_name from engrams table.
    std::string adapter_name;
    {
        const char* sql =
            "SELECT adapter_name FROM engrams WHERE id = ? AND tenant_id = ? LIMIT 1";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) return;
        StmtHandle h(raw);
        bind_sv(h.get(), 1, engram_id);
        bind_sv(h.get(), 2, tenant_id);
        if (sqlite3_step(h.get()) == SQLITE_ROW) {
            const char* t = reinterpret_cast<const char*>(
                sqlite3_column_text(h.get(), 0));
            if (t) adapter_name = t;
        }
    }
    if (adapter_name.empty()) return;

    const std::string observed_at = iso8601_utc(std::chrono::system_clock::now());

    // record_accessible_source: cognizer_id = tenant_id (best-effort P2.a:
    // the event doesn't carry a cognizer reference, so we use the tenant as
    // a stand-in; real cognizer routing is a P2.c concern).
    frontier.record_accessible_source(
        tenant_id, tenant_id, adapter_name, engram_id, observed_at, conn);
    stats.frontier_facts_written++;
}

// ---------------------------------------------------------------------------
// handle_statement_archived — no-op for P2.a (just count event)
// ---------------------------------------------------------------------------
void handle_statement_archived(TickStats& stats) {
    (void)stats;
    // P2.a: no frontier update needed when a statement is archived.
}

// ---------------------------------------------------------------------------
// handle_statement_superseded — no-op for P2.a (just count event)
// ---------------------------------------------------------------------------
void handle_statement_superseded(TickStats& stats) {
    (void)stats;
    // P2.a: supersede events are informational at this stage.
}

// ---------------------------------------------------------------------------
// handle_commitment_fulfilled — stub for P2.c
// ---------------------------------------------------------------------------
void handle_commitment_fulfilled(TickStats& stats) {
    (void)stats;
    // Commitment events don't exist yet at P2.a.
}

// ---------------------------------------------------------------------------
// handle_commitment_broken — stub for P2.c
// ---------------------------------------------------------------------------
void handle_commitment_broken(TickStats& stats) {
    (void)stats;
    // Commitment events don't exist yet at P2.a.
}

}  // namespace starling::tom::belief_tracker::detail
