#include "starling/bus/subscriber_pump.hpp"
#include "starling/bus/conflict_key_backfill.hpp"
#include "starling/tom/belief_tracker.hpp"
#include "starling/reconsolidation/reconsolidation_engine.hpp"
#include "starling/projection/projection_maintainer.hpp"
#include "starling/replay/replay_scheduler.hpp"
#include "starling/prospective/policy_engine.hpp"
#include "starling/tom/common_ground_subscriber.hpp"
#include <sqlite3.h>
#include <cstdio>
#include <functional>
#include <stdexcept>
#include <string>

namespace starling::bus {
namespace {

bool exec_control(sqlite3* db, const std::string& sql, std::string& error) {
    char* raw_error = nullptr;
    const int rc = sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &raw_error);
    if (rc == SQLITE_OK) return true;
    error = raw_error ? raw_error : sqlite3_errmsg(db);
    sqlite3_free(raw_error);
    return false;
}

// Restore the connection to its pre-savepoint boundary. A top-level SAVEPOINT
// may fall back to a full ROLLBACK; nested callers retain ownership of their
// outer transaction, so cleanup failure must propagate instead.
bool rollback_savepoint(sqlite3* db, const std::string& sp,
                        bool started_in_autocommit, std::string& error) {
    std::string rollback_error;
    if (exec_control(db, "ROLLBACK TO " + sp, rollback_error)) {
        std::string release_error;
        if (exec_control(db, "RELEASE " + sp, release_error)) return true;
        error = "release after rollback failed: " + release_error;
    } else {
        error = "rollback to savepoint failed: " + rollback_error;
    }

    if (started_in_autocommit && sqlite3_get_autocommit(db) == 0) {
        std::string full_rollback_error;
        if (exec_control(db, "ROLLBACK", full_rollback_error)) return true;
        error += "; full rollback failed: " + full_rollback_error;
    }
    return false;
}

// Run one subscriber inside a named SAVEPOINT. On any exception, ROLLBACK TO
// the savepoint so the subscriber's partial work is undone but the main write
// and other subscribers are unaffected. The subscriber checkpoint remains
// behind, so a later pump retries the batch.
void run_isolated(persistence::Connection& conn, const char* name,
                  const std::function<void()>& fn) {
    const std::string sp = std::string("sub_") + name;
    sqlite3* db = conn.raw();
    const bool started_in_autocommit = sqlite3_get_autocommit(db) != 0;
    std::string control_error;
    if (!exec_control(db, "SAVEPOINT " + sp, control_error)) {
        std::fprintf(stderr,
                     "[subscriber_pump] %s skipped; savepoint unavailable: %s\n",
                     name, control_error.c_str());
        return;
    }
    try {
        fn();
    } catch (const std::exception& e) {
        if (!rollback_savepoint(db, sp, started_in_autocommit, control_error)) {
            throw std::runtime_error(
                std::string("subscriber_pump: ") + name +
                " failed and transaction cleanup failed: " + control_error);
        }
        std::fprintf(stderr, "[subscriber_pump] %s failed; checkpoint retained: %s\n",
                     name, e.what());
        return;
    } catch (...) {
        if (!rollback_savepoint(db, sp, started_in_autocommit, control_error)) {
            throw std::runtime_error(
                std::string("subscriber_pump: ") + name +
                " failed and transaction cleanup failed: " + control_error);
        }
        std::fprintf(stderr, "[subscriber_pump] %s failed; checkpoint retained\n", name);
        return;
    }

    if (!exec_control(db, "RELEASE " + sp, control_error)) {
        const std::string release_error = control_error;
        if (!rollback_savepoint(db, sp, started_in_autocommit, control_error)) {
            throw std::runtime_error(
                std::string("subscriber_pump: ") + name +
                " release failed (" + release_error +
                ") and transaction cleanup failed: " + control_error);
        }
        std::fprintf(stderr,
                     "[subscriber_pump] %s release failed; batch rolled back: %s\n",
                     name, release_error.c_str());
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

    // 6. policy_engine — Prospective Loop post-write (P2.c): COMMITS→commitment
    //    生命周期 + Trigger 评估 + commitment.* 迁移。
    run_isolated(conn, "policy_engine", [&]{
        prospective::PolicyEngine(adapter).run_post_write(conn, now_iso);
    });

    // 7. common_ground — grounding 协议（assert/acknowledge/repair + 容器 rebuild）。
    run_isolated(conn, "common_ground", [&]{
        starling::tom::CommonGroundSubscriber::tick_one_batch(adapter, conn, now_iso);
    });
}

}  // namespace starling::bus
