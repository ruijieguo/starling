#pragma once
#include "starling/bus/bus_event.hpp"
#include "starling/persistence/connection.hpp"

#include <cstdint>

namespace starling::bus {

// OutboxWriter is the only sanctioned write path into bus_events. The append
// MUST be called inside an open transaction on the same Connection — otherwise
// at-least-once delivery is lost. The monotonic outbox_sequence is claimed
// from outbox_sequence_counter under the same transaction lock, so a
// rolled-back transaction does not consume sequence numbers.
class OutboxWriter {
public:
    explicit OutboxWriter(starling::persistence::Connection& conn) : conn_(conn) {}

    // Mutates ev: assigns event_id (random 128-bit hex; M0.4 will replace
    // with real UUIDv7), outbox_sequence (claimed from outbox_sequence_counter),
    // and created_at (ISO-8601 UTC) when those fields are empty. Inserts with
    // dispatch_status='pending'.
    void append(BusEvent& ev);

    // Recursion-guard variant: writes with dispatch_status='delivered' so the
    // dispatcher never picks it up. Used by the dispatcher's own
    // system.delivery_failed emit path (M0.2 Task 7).
    void append_already_delivered(BusEvent& ev);

private:
    void append_impl(BusEvent& ev, const char* dispatch_status);
    int64_t claim_next_sequence();

    starling::persistence::Connection& conn_;
};

}  // namespace starling::bus
