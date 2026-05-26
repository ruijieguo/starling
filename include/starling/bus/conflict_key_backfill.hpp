#pragma once
#include "starling/persistence/connection.hpp"
namespace starling::bus::conflict_key_backfill {

struct TickStats {
    int rows_processed  = 0;
    int rows_backfilled = 0;
    int rows_deduped    = 0;
    bool completed_now  = false;
};

// Returns true when the backfill singleton row has completed_at set.
bool is_complete(persistence::Connection& conn);

// Process up to batch_size NULL-key conflicts_with edges.
// Internally guarded: runs in a SAVEPOINT; any SQL error is caught and
// swallowed — the function never throws.
// Returns stats for the batch (all zero + completed_now=false on early-return).
TickStats tick_one_batch(persistence::Connection& conn, int batch_size = 100);

}  // namespace starling::bus::conflict_key_backfill
