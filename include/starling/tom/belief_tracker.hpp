#pragma once
#include "starling/persistence/sqlite_adapter.hpp"

namespace starling::tom::belief_tracker {

struct TickStats {
    int events_processed = 0;
    int frontier_facts_written = 0;
    int trust_prior_updates = 0;
    int last_seen_updates = 0;
    int presence_log_writes = 0;
};

// Process events from last_processed_outbox_sequence+1 onwards in
// a single SAVEPOINT batch (default 100 events). Failures don't
// propagate (best-effort observer). Returns stats.
TickStats tick_one_batch(
    persistence::SqliteAdapter& adapter,
    int batch_size = 100);

}  // namespace starling::tom::belief_tracker
