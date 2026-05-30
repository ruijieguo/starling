#include "starling/bus/subscriber_pump.hpp"
#include "starling/bus/conflict_key_backfill.hpp"
#include "starling/tom/belief_tracker.hpp"
#include "starling/reconsolidation/reconsolidation_engine.hpp"
#include "starling/projection/projection_maintainer.hpp"
#include "starling/replay/replay_scheduler.hpp"
#include <sqlite3.h>
#include <functional>
#include <string>

namespace starling::bus {
namespace {

// Run one subscriber inside a named SAVEPOINT. On any exception, ROLLBACK TO
// the savepoint so the subscriber's partial work is undone but the main write
// and other subscribers are unaffected. Best-effort: never propagates.
void run_isolated(persistence::Connection& conn, const char* name,
                  const std::function<void()>& fn) {
    const std::string sp = std::string("sub_") + name;
    sqlite3_exec(conn.raw(), ("SAVEPOINT " + sp).c_str(), nullptr, nullptr, nullptr);
    try {
        fn();
        sqlite3_exec(conn.raw(), ("RELEASE " + sp).c_str(), nullptr, nullptr, nullptr);
    } catch (...) {
        sqlite3_exec(conn.raw(), ("ROLLBACK TO " + sp).c_str(), nullptr, nullptr, nullptr);
        sqlite3_exec(conn.raw(), ("RELEASE " + sp).c_str(), nullptr, nullptr, nullptr);
    }
}

}  // namespace

void SubscriberPump::run_post_write(persistence::SqliteAdapter& adapter,
                                    persistence::Connection& conn,
                                    std::string_view now_iso) {
    // 1. conflict_key_backfill — already internally SAVEPOINT-guarded + swallows errors,
    //    but wrap anyway for uniform isolation.
    run_isolated(conn, "conflict_key", [&]{
        conflict_key_backfill::tick_one_batch(conn);
    });

    // 2. belief_tracker — takes adapter, manages its own connection internally.
    run_isolated(conn, "belief_tracker", [&]{
        starling::tom::belief_tracker::tick_one_batch(adapter);
    });

    // 3. reconsolidation — tick outbox events + close any overdue windows.
    run_isolated(conn, "reconsolidation", [&]{
        reconsolidation::ReconsolidationEngine eng(adapter);
        eng.tick_one_batch(conn, now_iso);
        eng.close_due_windows(conn, now_iso);
    });

    // 4. projection_maintainer — incremental projection update.
    run_isolated(conn, "projection", [&]{
        projection::ProjectionMaintainer(adapter).tick_one_batch(conn, now_iso);
    });

    // 5. replay_online — online trigger counter; fires sampling window every N writes.
    run_isolated(conn, "replay_online", [&]{
        replay::ReplayScheduler(adapter).tick_online(conn, now_iso);
    });
}

}  // namespace starling::bus
