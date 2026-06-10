#include "starling/bus/bus_event.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <sqlite3.h>

#include <chrono>
#include <string>

namespace starling::bus {

namespace {
constexpr char kSep = '\x1f';

// Minimal JSON-array-of-strings parser tailored to causation_chain_json
// (entries are bare UUID/hex strings — no escapes, no nesting). Returns
// the entries in order. Empty array → empty vector.
std::vector<std::string> parse_chain_json(const std::string& j) {
    std::vector<std::string> out;
    if (j.size() < 2 || j.front() != '[' || j.back() != ']') return out;
    std::size_t i = 1;
    while (i < j.size() - 1) {
        // skip whitespace + commas
        while (i < j.size() - 1 && (j[i] == ' ' || j[i] == ',')) ++i;
        if (i >= j.size() - 1) break;
        if (j[i] != '"') break;
        ++i;
        std::size_t end = j.find('"', i);
        if (end == std::string::npos || end >= j.size() - 1) break;
        out.emplace_back(j.substr(i, end - i));
        i = end + 1;
    }
    return out;
}
}  // namespace

std::vector<std::string> compute_child_chain(
    starling::persistence::Connection& conn,
    const std::string& parent_event_id) {
    if (parent_event_id.empty()) return {};

    using persistence::detail::make_sqlite_error;
    using starling::persistence::StmtHandle;

    sqlite3* const db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    const char* sql =
        "SELECT causation_chain_json FROM bus_events WHERE event_id = ?";
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "compute_child_chain: prepare failed");
    }
    StmtHandle h(raw);
    sqlite3_bind_text(raw, 1, parent_event_id.c_str(), -1, SQLITE_TRANSIENT);

    std::vector<std::string> parent_chain;
    const int rc = sqlite3_step(raw);
    if (rc == SQLITE_ROW) {
        const auto* t = sqlite3_column_text(raw, 0);
        parent_chain = parse_chain_json(t ? reinterpret_cast<const char*>(t)
                                          : std::string{});
    }
    // If parent row missing (SQLITE_DONE), fall through with an empty parent
    // chain — the parent_event_id is still appended below, giving the child
    // a 1-element chain. This preserves backward compatibility with any test
    // that synthesizes a causation_parent_event_id without writing the
    // parent row, while still propagating known ancestry when available.

    parent_chain.push_back(parent_event_id);
    if (parent_chain.size() > 3) {
        const std::string root = parent_chain.front();
        const std::string source = parent_event_id;
        throw CausationOverflow(root, source,
                                static_cast<int>(parent_chain.size()));
    }
    return parent_chain;
}

std::string compute_idempotency_key(
        std::string_view event_type,
        std::string_view aggregate_id,
        std::string_view canonical_key,
        std::string_view causation_root,
        std::string_view window_bucket) {
    std::string buf;
    buf.reserve(event_type.size() + aggregate_id.size() + canonical_key.size()
                + causation_root.size() + window_bucket.size() + 4);
    buf.append(event_type);    buf.push_back(kSep);
    buf.append(aggregate_id);  buf.push_back(kSep);
    buf.append(canonical_key); buf.push_back(kSep);
    buf.append(causation_root);buf.push_back(kSep);
    buf.append(window_bucket);
    return starling::crypto::sha256_hex(buf);
}

std::string compute_window_bucket(
        std::string_view event_type,
        std::chrono::system_clock::time_point now) {
    // Per-event-type 60s bucket. Used by audit-only and rate-naturally-bursty
    // events to make repeated emissions within a window idempotent on the
    // bus_events UNIQUE(idempotency_key) constraint.
    if (event_type == "pipeline_run.started"
        || event_type == "evidence.no_store_audit"
        || event_type == "evidence.idempotent_hit") {
        const auto sec = std::chrono::duration_cast<std::chrono::seconds>(
            now.time_since_epoch()).count();
        return std::to_string(sec / 60);
    }
    if (event_type == "extraction.failed"
        || event_type == "extraction.retry_scheduled"
        || event_type == "extraction.dead_lettered"
        || event_type == "extraction.noop"
        || event_type == "pipeline.run_started"
        || event_type == "pipeline.run_completed"
        || event_type == "pipeline.run_failed"
        || event_type == "system.runaway") {
        const auto sec = std::chrono::duration_cast<std::chrono::seconds>(
            now.time_since_epoch()).count();
        return std::to_string(sec / 60);
    }
    if (event_type == "belief.conflict") {
        // 10-second debounce window per 05_bus.md §4.
        const auto sec = std::chrono::duration_cast<std::chrono::seconds>(
            now.time_since_epoch()).count();
        return std::to_string(sec / 10);
    }
    if (event_type == "statement.recalled") {
        // 2-second debounce window per docs/design/subsystems_design/13_retrieval.md
        // §"statement.recalled emit 契约". Same-key recall within 2s coalesces.
        const auto sec = std::chrono::duration_cast<std::chrono::seconds>(
            now.time_since_epoch()).count();
        return std::to_string(sec / 2);
    }
    if (event_type == "statement.archived" || event_type == "statement.superseded") {
        // Per-primary_id is unique on archive/supersede (one event per
        // statement-state-change). No window needed; empty bucket prevents
        // accidental coalescence with a re-emit window.
        return "";
    }
    return "";
}

}  // namespace starling::bus
