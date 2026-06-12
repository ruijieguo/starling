#include "starling/replay/replay_scheduler.hpp"
#include "starling/affect/affect_vector.hpp"
#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/hippocampus/affect_buffer.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/replay/swr_sampler.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <format>
#include <map>
#include <random>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace starling::replay {

using starling::bus::BusEvent;
using starling::bus::OutboxWriter;
using starling::bus::compute_idempotency_key;
using starling::bus::compute_window_bucket;
using starling::persistence::detail::bind_sv;
using starling::persistence::detail::iso8601_utc;
using starling::persistence::detail::make_sqlite_error;
using starling::persistence::StmtHandle;
using starling::persistence::TransactionGuard;

namespace {

// 32 random hex chars — same pattern as cognizer_hub.cpp random_hex_32()
std::string random_hex_32() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%016llx%016llx",
                  static_cast<unsigned long long>(a),
                  static_cast<unsigned long long>(b));
    return std::string(buf, 32);
}

// Minimal JSON string escaping (keys/values are controlled; no control chars expected)
std::string json_str(std::string_view sv) {
    std::string out;
    out.reserve(sv.size() + 2);
    out.push_back('"');
    for (char c : sv) {
        if (c == '"')  { out += "\\\""; }
        else if (c == '\\') { out += "\\\\"; }
        else { out.push_back(c); }
    }
    out.push_back('"');
    return out;
}

// Build + append a BusEvent with no causation parent (replay is a root action)
void emit_event(
    persistence::Connection& conn,
    std::string_view event_type,
    std::string_view primary_id,
    std::string_view aggregate_id,
    std::string_view tenant_id,
    std::string payload_json)
{
    BusEvent ev;
    ev.tenant_id    = std::string(tenant_id);
    ev.event_type   = std::string(event_type);
    ev.primary_id   = std::string(primary_id);
    ev.aggregate_id = std::string(aggregate_id);
    // No causation parent — replay events are roots.
    const std::string window_bucket =
        compute_window_bucket(event_type, std::chrono::system_clock::now());
    const std::string canonical_key =
        std::string(tenant_id) + ":" + std::string(primary_id);
    ev.idempotency_key = compute_idempotency_key(
        event_type, aggregate_id, canonical_key,
        /*causation_root=*/"", window_bucket);
    ev.payload_json = std::move(payload_json);
    OutboxWriter ow(conn);
    ow.append(ev);
}

// Helper: query a single int column
int query_int(sqlite3* db, const char* sql) {
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) return 0;
    StmtHandle h(raw);
    if (sqlite3_step(h.get()) != SQLITE_ROW) return 0;
    return sqlite3_column_int(h.get(), 0);
}

struct StmtRow {
    std::string id;
    std::string holder_id;
    std::string tenant_id;
    double      salience = 0.0;
    std::string last_replayed;
    double      affect_arousal = 0.0;
    std::string provenance;
    int64_t     replay_count = 0;
    int         derived_depth = 0;
    int         replay_count_int = 0;
};

// Sample VOLATILE statements with provenance in ('user_input','tom_inferred'), limit N
std::vector<StmtRow> sample_volatile(sqlite3* db, int limit, std::string_view now_iso) {
    const char* sql =
        "SELECT id, holder_id, tenant_id, salience, last_replayed, "
        "       affect_json, provenance, replay_count, derived_depth "
        "FROM statements "
        "WHERE consolidation_state='volatile' "
        "  AND provenance IN ('user_input','tom_inferred') "
        "LIMIT 200";  // over-fetch then weight-sort
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        return {};
    StmtHandle h(raw);

    std::vector<StmtRow> rows;
    SamplerConfig cfg;
    while (sqlite3_step(h.get()) == SQLITE_ROW) {
        StmtRow r;
        r.id    = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
        r.holder_id = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 1));
        r.tenant_id = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 2));
        r.salience  = sqlite3_column_double(h.get(), 3);
        const auto* lr = sqlite3_column_text(h.get(), 4);
        if (lr) r.last_replayed = reinterpret_cast<const char*>(lr);
        // P2.c: affect_json → AffectVector → 优先级重放权重 (spec §8)
        // 高 affect 用 salience() 覆盖 column salience,arousal 喂 sample_weight
        // 的 (1 + arousal_bonus·affect_arousal) 乘子;空/{} 时保留 column 行为。
        const auto* aj = sqlite3_column_text(h.get(), 5);
        const std::string affect_json_str = aj ? reinterpret_cast<const char*>(aj) : "";
        if (!affect_json_str.empty() && affect_json_str != "{}") {
            const affect::AffectVector av = affect::parse_affect_json(affect_json_str);
            r.salience       = affect::salience(av);  // 覆盖 column salience
            r.affect_arousal = av.arousal;
        } else {
            r.affect_arousal = 0.0;  // 保留 column salience + arousal=0(原行为)
        }
        r.provenance  = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 6));
        r.replay_count = sqlite3_column_int64(h.get(), 7);
        r.derived_depth = sqlite3_column_int(h.get(), 8);
        rows.push_back(std::move(r));
    }

    // Weight-sort descending, take top `limit` with weight > 0
    std::vector<std::pair<double, std::size_t>> weighted;
    for (std::size_t i = 0; i < rows.size(); ++i) {
        SamplerInputs in;
        in.salience          = rows[i].salience;
        in.last_replayed_iso = rows[i].last_replayed;
        in.has_conflict      = false;
        in.affect_arousal    = rows[i].affect_arousal;
        in.goal_relevant     = false;
        in.provenance        = rows[i].provenance;
        in.replay_count      = rows[i].replay_count;
        in.derived_depth     = rows[i].derived_depth;
        const double w = sample_weight(in, cfg, now_iso);
        if (w > 0.0) weighted.emplace_back(w, i);
    }
    std::sort(weighted.begin(), weighted.end(),
              [](const auto& a, const auto& b){ return a.first > b.first; });

    std::vector<StmtRow> out;
    const std::size_t take = static_cast<std::size_t>(limit);
    for (std::size_t i = 0; i < weighted.size() && i < take; ++i) {
        out.push_back(rows[weighted[i].second]);
    }
    return out;
}

// Write a replay_ledger row
void write_ledger(sqlite3* db,
                  std::string_view batch_id,
                  std::string_view mode,
                  int sampled_count,
                  std::string_view ops_json,
                  std::string_view now_iso) {
    const char* sql =
        "INSERT INTO replay_ledger"
        "(replay_batch_id, mode, sampled_count, ops_applied_json, started_at, finished_at)"
        " VALUES(?,?,?,?,?,?)";
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "write_ledger: prepare");
    StmtHandle h(raw);
    bind_sv(h.get(), 1, batch_id);
    bind_sv(h.get(), 2, mode);
    sqlite3_bind_int(h.get(), 3, sampled_count);
    bind_sv(h.get(), 4, ops_json);
    bind_sv(h.get(), 5, now_iso);
    bind_sv(h.get(), 6, now_iso);
    if (sqlite3_step(h.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "write_ledger: step");
}

// Run compress on sampled rows + emit statement.derived per row + return stats
ReplayStats do_compress_and_emit(
    persistence::Connection& conn,
    const std::vector<StmtRow>& rows,
    std::string_view mode,
    std::string_view now_iso)
{
    if (rows.empty()) return {};

    ReplayStats stats;
    stats.replay_batch_id = random_hex_32();
    stats.sampled = static_cast<int>(rows.size());

    std::map<std::string, std::vector<std::string>> by_tenant;
    for (const auto& r : rows) {
        by_tenant[r.tenant_id].push_back(r.id);
    }

    for (const auto& [tenant_id, ids] : by_tenant) {
        auto res = op_compress(conn, ids, tenant_id, stats.replay_batch_id);
        stats.compressed += res.affected;
    }

    // Emit statement.derived for each compressed stmt
    for (const auto& r : rows) {
        std::ostringstream payload;
        payload << "{\"replay_batch_id\":" << json_str(stats.replay_batch_id)
                << ",\"op\":\"compress\""
                << ",\"mode\":" << json_str(mode)
                << "}";
        try {
            emit_event(conn, "statement.derived",
                       r.id, r.holder_id, r.tenant_id, payload.str());
        } catch (...) {
            // idempotency_key UNIQUE collision — skip duplicate
        }
    }

    // Write ledger
    std::ostringstream ops_json;
    ops_json << "{\"compress\":" << stats.compressed << "}";
    write_ledger(conn.raw(), stats.replay_batch_id, mode,
                 stats.sampled, ops_json.str(), now_iso);

    return stats;
}

}  // namespace

ReplayScheduler::ReplayScheduler(persistence::SqliteAdapter& adapter)
    : adapter_(adapter) {
    (void)adapter_;  // held for future use (background-thread mode, M0.9+)
}

int ReplayScheduler::enforce_oscillation_guard(persistence::Connection& conn) {
    sqlite3* db = conn.raw();

    // Collect affected ids BEFORE updating so we can emit per-id
    const char* sel_sql =
        "SELECT id, holder_id, tenant_id, replay_count FROM statements "
        "WHERE replay_count >= 5 "
        "  AND consolidation_state IN ('volatile','replaying_consolidating')";
    sqlite3_stmt* sel_raw = nullptr;
    if (sqlite3_prepare_v2(db, sel_sql, -1, &sel_raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "enforce_oscillation_guard: prepare SELECT");
    StmtHandle hsel(sel_raw);

    struct Affected { std::string id, holder_id, tenant_id; int replay_count; };
    std::vector<Affected> affected;
    while (sqlite3_step(hsel.get()) == SQLITE_ROW) {
        Affected a;
        a.id         = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(), 0));
        a.holder_id  = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(), 1));
        a.tenant_id  = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(), 2));
        a.replay_count = sqlite3_column_int(hsel.get(), 3);
        affected.push_back(std::move(a));
    }

    if (affected.empty()) return 0;

    // UPDATE all matching rows
    const char* upd_sql =
        "UPDATE statements "
        "SET consolidation_state='consolidated', review_status='pending_review' "
        "WHERE replay_count >= 5 "
        "  AND consolidation_state IN ('volatile','replaying_consolidating')";
    sqlite3_stmt* upd_raw = nullptr;
    if (sqlite3_prepare_v2(db, upd_sql, -1, &upd_raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "enforce_oscillation_guard: prepare UPDATE");
    StmtHandle hupd(upd_raw);
    if (sqlite3_step(hupd.get()) != SQLITE_DONE)
        throw make_sqlite_error(db, "enforce_oscillation_guard: UPDATE step");

    // Emit one consolidation_forced event per affected stmt
    for (const auto& a : affected) {
        std::ostringstream payload;
        payload << "{\"replay_count\":" << a.replay_count
                << ",\"forced_state\":\"consolidated\"}";
        try {
            emit_event(conn, "statement.consolidation_forced",
                       a.id, a.holder_id, a.tenant_id, payload.str());
        } catch (...) {
            // idempotency collision — skip
        }
    }

    return static_cast<int>(affected.size());
}

int ReplayScheduler::sweep_volatile_ttl(persistence::Connection& conn,
                                         std::string_view now_iso) {
    sqlite3* db = conn.raw();

    // Compute cutoff: now_iso minus 7 days (ISO lexical compare works for YYYY-MM-DDTHH:MM:SSZ)
    // Parse now to epoch, subtract 7*86400, reformat.
    // Use swr_sampler's parse pattern inline here.
    int y=0, mo=0, d=0, h=0, mi=0, s=0;
    std::string now_s(now_iso);
    if (std::sscanf(now_s.c_str(), "%d-%d-%dT%d:%d:%dZ", &y,&mo,&d,&h,&mi,&s) != 6)
        return 0;
    std::tm tm{};
    tm.tm_year=y-1900; tm.tm_mon=mo-1; tm.tm_mday=d;
    tm.tm_hour=h; tm.tm_min=mi; tm.tm_sec=s;
    const std::time_t now_epoch = timegm(&tm);
    const std::time_t cutoff_epoch = now_epoch - static_cast<std::time_t>(kVolatileTtlDays) * 86400;
    std::tm cutoff_tm{};
    gmtime_r(&cutoff_epoch, &cutoff_tm);
    const std::string cutoff_iso =
        std::format("{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
                    cutoff_tm.tm_year + 1900, cutoff_tm.tm_mon + 1, cutoff_tm.tm_mday,
                    cutoff_tm.tm_hour, cutoff_tm.tm_min, cutoff_tm.tm_sec);

    // Collect affected volatile stmts older than cutoff
    const char* sel_sql =
        "SELECT id, holder_id, tenant_id FROM statements "
        "WHERE consolidation_state='volatile' AND created_at < ?";
    sqlite3_stmt* sel_raw = nullptr;
    if (sqlite3_prepare_v2(db, sel_sql, -1, &sel_raw, nullptr) != SQLITE_OK)
        throw make_sqlite_error(db, "sweep_volatile_ttl: prepare SELECT");
    StmtHandle hsel(sel_raw);
    bind_sv(hsel.get(), 1, cutoff_iso);

    struct Expired { std::string id, holder_id, tenant_id; };
    std::vector<Expired> expired;
    while (sqlite3_step(hsel.get()) == SQLITE_ROW) {
        Expired e;
        e.id        = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(), 0));
        e.holder_id = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(), 1));
        e.tenant_id = reinterpret_cast<const char*>(sqlite3_column_text(hsel.get(), 2));
        expired.push_back(std::move(e));
    }

    if (expired.empty()) return 0;

    // P3.a3:Affect Buffer 豁免(spec 10_replay:"超 7 天 AND not in Affect
    // Buffer → ARCHIVED")——高 salience 候选不被 TTL 兜底清理,留给 Replay
    // 优先采样。成员集逐租户缓存。
    std::unordered_map<std::string, std::unordered_set<std::string>> buffer_by_tenant;
    auto in_buffer = [&](const Expired& e) {
        auto it = buffer_by_tenant.find(e.tenant_id);
        if (it == buffer_by_tenant.end()) {
            it = buffer_by_tenant.emplace(
                e.tenant_id,
                hippocampus::affect_buffer::member_set(conn, e.tenant_id)).first;
        }
        return it->second.count(e.id) > 0;
    };

    int count = 0;
    for (const auto& e : expired) {
        if (in_buffer(e)) continue;
        const char* upd_sql =
            "UPDATE statements SET consolidation_state='archived' "
            "WHERE id=? AND tenant_id=? AND consolidation_state='volatile'";
        sqlite3_stmt* upd_raw = nullptr;
        if (sqlite3_prepare_v2(db, upd_sql, -1, &upd_raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "sweep_volatile_ttl: prepare UPDATE");
        StmtHandle hupd(upd_raw);
        bind_sv(hupd.get(), 1, e.id);
        bind_sv(hupd.get(), 2, e.tenant_id);
        if (sqlite3_step(hupd.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "sweep_volatile_ttl: UPDATE step");
        const int changed = sqlite3_changes(db);
        count += changed;
        if (changed > 0) {
            try {
                emit_event(conn, "statement.archived",
                           e.id, e.holder_id, e.tenant_id,
                           "{\"reason\":\"volatile_ttl_exceeded\"}");
            } catch (...) {
                // idempotency collision — skip
            }
        }
    }
    return count;
}

int ReplayScheduler::run_decay(persistence::Connection& conn,
                                const std::vector<std::string>& candidate_ids,
                                std::string_view now_iso) {
    if (candidate_ids.empty()) return 0;

    // Deduplicate input
    std::vector<std::string> deduped = candidate_ids;
    std::sort(deduped.begin(), deduped.end());
    deduped.erase(std::unique(deduped.begin(), deduped.end()), deduped.end());

    sqlite3* db = conn.raw();

    // For each candidate, record state before op_decay
    struct CandInfo { std::string id, holder_id, tenant_id, state; };
    std::vector<CandInfo> info;
    info.reserve(deduped.size());
    for (const auto& id : deduped) {
        const char* sql =
            "SELECT id, holder_id, tenant_id, consolidation_state "
            "FROM statements WHERE id=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, sql, -1, &raw, nullptr) != SQLITE_OK) continue;
        StmtHandle h(raw);
        bind_sv(h.get(), 1, id);
        while (sqlite3_step(h.get()) == SQLITE_ROW) {
            CandInfo ci;
            ci.id        = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
            ci.holder_id = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 1));
            ci.tenant_id = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 2));
            ci.state     = reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 3));
            info.push_back(std::move(ci));
        }
    }

    // Group by tenant for op_decay call
    // For M0.8: treat all as same tenant (use each row's tenant_id)
    // Call op_decay per-tenant group
    std::map<std::string, std::vector<std::string>> by_tenant;
    for (const auto& ci : info) {
        if (ci.state == "consolidated") {
            by_tenant[ci.tenant_id].push_back(ci.id);
        }
    }

    int archived = 0;
    for (auto& [tenant_id, ids] : by_tenant) {
        op_decay(conn, ids, tenant_id, now_iso);
    }

    // Now check which ones transitioned to archived
    for (const auto& ci : info) {
        if (ci.state != "consolidated") continue;
        const char* chk_sql =
            "SELECT consolidation_state FROM statements WHERE id=? AND tenant_id=?";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, chk_sql, -1, &raw, nullptr) != SQLITE_OK) continue;
        StmtHandle h(raw);
        bind_sv(h.get(), 1, ci.id);
        bind_sv(h.get(), 2, ci.tenant_id);
        if (sqlite3_step(h.get()) != SQLITE_ROW) continue;
        const std::string new_state =
            reinterpret_cast<const char*>(sqlite3_column_text(h.get(), 0));
        if (new_state == "archived") {
            ++archived;
            try {
                emit_event(conn, "statement.archived",
                           ci.id, ci.holder_id, ci.tenant_id,
                           "{\"reason\":\"decay\"}");
            } catch (...) {
                // idempotency collision — skip
            }
        }
    }
    return archived;
}

ReplayStats ReplayScheduler::tick_online(persistence::Connection& conn,
                                          std::string_view now_iso) {
    sqlite3* db = conn.raw();

    // Read current counter
    int counter = query_int(db,
        "SELECT online_trigger_counter FROM replay_scheduler_state WHERE id=1");
    counter += 1;

    if (counter < kOnlineTrigger) {
        // Just update counter
        const char* upd_sql =
            "UPDATE replay_scheduler_state "
            "SET online_trigger_counter=?, last_updated_at=? "
            "WHERE id=1";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, upd_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "tick_online: prepare UPDATE counter");
        StmtHandle h(raw);
        sqlite3_bind_int(h.get(), 1, counter);
        bind_sv(h.get(), 2, now_iso);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "tick_online: UPDATE counter step");
        return {};
    }

    // counter reached kOnlineTrigger — reset and run sampling
    {
        const char* upd_sql =
            "UPDATE replay_scheduler_state "
            "SET online_trigger_counter=0, last_online_run_at=?, last_updated_at=? "
            "WHERE id=1";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, upd_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "tick_online: prepare reset counter");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, now_iso);
        bind_sv(h.get(), 2, now_iso);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "tick_online: reset counter step");
    }

    // Sample 1-3 volatile stmts
    auto rows = sample_volatile(db, 3, now_iso);
    return do_compress_and_emit(conn, rows, "online", now_iso);
}

ReplayStats ReplayScheduler::run_idle(persistence::Connection& conn,
                                       std::string_view now_iso) {
    sqlite3* db = conn.raw();
    auto rows = sample_volatile(db, 30, now_iso);

    // Update scheduler state
    {
        const char* upd_sql =
            "UPDATE replay_scheduler_state "
            "SET last_idle_run_at=?, last_updated_at=? WHERE id=1";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, upd_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "run_idle: prepare UPDATE");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, now_iso);
        bind_sv(h.get(), 2, now_iso);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "run_idle: UPDATE step");
    }

    return do_compress_and_emit(conn, rows, "idle", now_iso);
}

ReplayStats ReplayScheduler::run_sleep(persistence::Connection& conn,
                                        std::string_view now_iso) {
    sqlite3* db = conn.raw();
    auto rows = sample_volatile(db, 200, now_iso);

    // Update scheduler state
    {
        const char* upd_sql =
            "UPDATE replay_scheduler_state "
            "SET last_sleep_run_at=?, last_updated_at=? WHERE id=1";
        sqlite3_stmt* raw = nullptr;
        if (sqlite3_prepare_v2(db, upd_sql, -1, &raw, nullptr) != SQLITE_OK)
            throw make_sqlite_error(db, "run_sleep: prepare UPDATE");
        StmtHandle h(raw);
        bind_sv(h.get(), 1, now_iso);
        bind_sv(h.get(), 2, now_iso);
        if (sqlite3_step(h.get()) != SQLITE_DONE)
            throw make_sqlite_error(db, "run_sleep: UPDATE step");
    }

    return do_compress_and_emit(conn, rows, "sleep", now_iso);
}

}  // namespace starling::replay
