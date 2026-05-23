#include "starling/bus/bus_event.hpp"
#include "starling/crypto/sha256.hpp"

#include <chrono>
#include <string>

namespace starling::bus {

namespace {
constexpr char kSep = '\x1f';
}  // namespace

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
        || event_type == "pipeline.run_failed") {
        const auto sec = std::chrono::duration_cast<std::chrono::seconds>(
            now.time_since_epoch()).count();
        return std::to_string(sec / 60);
    }
    return "";
}

}  // namespace starling::bus
