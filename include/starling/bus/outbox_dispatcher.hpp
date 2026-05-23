#pragma once
#include "starling/bus/bus_event.hpp"
#include "starling/bus/consumer_state.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/persistence/connection.hpp"

#include <chrono>
#include <functional>
#include <string>

namespace starling::bus {

struct DispatchOptions {
    std::string consumer_id = "default";
    int max_retries = 5;
    int max_events_per_run = 1000;
    std::chrono::seconds inbox_ttl = std::chrono::hours(24 * 7);
};

enum class ConsumerDecision {
    Accept,            // mark delivered
    TransientError,    // increment attempts, leave pending
    PermanentError,    // jump straight to dead_letter
};

// Consumer callback. Receives the event; throwing is treated as TransientError.
using Consumer = std::function<ConsumerDecision(const BusEvent&)>;

struct DispatchStats {
    int delivered = 0;
    int retried = 0;
    int dead_lettered = 0;
    int skipped_blocked = 0;  // earlier event for same aggregate still pending
};

// OutboxDispatcher drains pending bus_events in outbox_sequence order, honoring
// per-aggregate ordering: once an event for aggregate A fails or dead-letters
// in this run, no later event for A is delivered (all subsequent events for A
// are reported as skipped_blocked). On startup, any 'in_flight' rows from a
// prior crashed run are reset to 'pending' (TC-NEW-OUTBOX-IDEMP crash recovery).
// After max_retries the row is flipped to 'dead_letter' and a
// 'system.delivery_failed' event is appended with dispatch_status='delivered'
// — the recursion guard preventing the dispatcher from re-picking its own
// failure events (Subsystem Contract D).
class OutboxDispatcher {
public:
    OutboxDispatcher(starling::persistence::Connection& conn,
                     Consumer consumer,
                     DispatchOptions opts = {});

    DispatchStats run_once();

private:
    starling::persistence::Connection& conn_;
    Consumer consumer_;
    DispatchOptions opts_;
};

}  // namespace starling::bus
