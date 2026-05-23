#pragma once
#include <chrono>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace starling::bus {

struct BusEvent {
    std::string event_id;          // UUID
    std::string tenant_id;
    std::string event_type;        // e.g. "statement.created"
    std::string primary_id;        // table-driven: see §3.10 primary_id table
    std::string aggregate_id;      // ordering key — usually holder_id
    int64_t outbox_sequence = 0;   // claimed by OutboxWriter, monotonic
    std::vector<std::string> causation_chain;  // length ≤ 3
    std::string idempotency_key;   // sha256 hex of canonical material
    std::string payload_json;
    std::string created_at;        // ISO-8601 UTC
    std::string version = "v1";
};

// idempotency_key = sha256_hex(
//   event_type      ⊕ \x1f ⊕
//   aggregate_id    ⊕ \x1f ⊕
//   canonical_key   ⊕ \x1f ⊕
//   causation_root  ⊕ \x1f ⊕
//   window_bucket
// )
// causation_root = causation_chain.front() if non-empty else "".
// window_bucket is event-type-specific; see compute_window_bucket().
std::string compute_idempotency_key(
    std::string_view event_type,
    std::string_view aggregate_id,
    std::string_view canonical_key,
    std::string_view causation_root,
    std::string_view window_bucket);

// Per-event-type bucket. P1 events:
//   statement.created            -> ""               (already idempotent on canonical_key)
//   statement.superseded         -> ""
//   evidence.appended            -> ""               (canonical_key=engram.id, UUIDv4 unique)
//   evidence.no_store_audit      -> floor(now / 60s) (audit-only; bucketed for replay)
//   evidence.idempotent_hit      -> floor(now / 60s) (audit-only; bucketed for replay)
//   pipeline_run.started         -> floor(now / 60s)
//   pipeline_run.finished        -> ""
//   extraction_attempt.recorded  -> ""
//   conflict_probe.flagged       -> ""
//   system.delivery_failed       -> ""
std::string compute_window_bucket(
    std::string_view event_type,
    std::chrono::system_clock::time_point now);

}  // namespace starling::bus
