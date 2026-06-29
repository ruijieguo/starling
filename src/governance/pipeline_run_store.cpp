#include "starling/governance/pipeline_run_store.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <chrono>
#include <cstdint>
#include <iomanip>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>

namespace starling::governance {

using persistence::detail::bind_sv;
using persistence::detail::iso8601_utc;
using persistence::detail::make_sqlite_error;

namespace {

// CQ1: 4th copy of the random_id scheme (PipelineLedger/StatementWriter/OutboxWriter); folds into starling/util/uuid.hpp at the M0.4+1 consolidation.
std::string random_id() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t val_a = rng();
    const std::uint64_t val_b = rng();
    std::ostringstream oss;
    oss << std::hex << std::setfill('0')
        << std::setw(8) << static_cast<std::uint32_t>(val_a >> 32) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(val_a >> 16) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(val_a) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(val_b >> 48) << '-'
        << std::setw(12) << (val_b & 0xFFFFFFFFFFFFULL);
    return oss.str();
}

// Column indices for the 26-column SELECT list used in get/find_active_run/read_row_.
// Order matches kCols below; any reordering breaks map_row_.
enum ColIdx : std::uint8_t {
    kColId = 0,
    kColKind,
    kColAggregateId,
    kColTenantId,
    kColBusinessTaskId,
    kColParentRunId,
    kColProfileName,
    kColInputHash,
    kColIdempotencyKey,
    kColPipelineName,
    kColPipelineVersion,
    kColStatus,
    kColCheckpointSequence,
    kColErrorKind,
    kColRetryCount,
    kColWorkerId,
    kColLeaseUntil,
    kColItemRunIds,
    kColStepContracts,
    kColWatermark,
    kColProgress,
    kColCounters,
    kColWarnings,
    kColStageTimingsMs,
    kColStartedAt,
    kColUpdatedAt,
};

// 26-column SELECT list shared by get(), find_active_run(), and read_row_().
// MUST stay in sync with ColIdx above.
constexpr const char* kCols =
    "id,kind,aggregate_id,tenant_id,business_task_id,parent_run_id,"
    "profile_name,input_hash,idempotency_key,pipeline_name,pipeline_version,"
    "status,checkpoint_sequence,error_kind,retry_count,worker_id,lease_until,"
    "item_run_ids,step_contracts,watermark,progress,counters,warnings,"
    "stage_timings_ms,started_at,updated_at";

// Read a non-null TEXT column as std::string.
std::string col_text(sqlite3_stmt* stmt, int idx) {
    // NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
    const auto* txt = reinterpret_cast<const char*>(sqlite3_column_text(stmt, idx));
    if (txt == nullptr) {
        return {};
    }
    return {txt};
}

// Read a possibly-null TEXT column as optional<string>.
std::optional<std::string> col_text_opt(sqlite3_stmt* stmt, int idx) {
    if (sqlite3_column_type(stmt, idx) == SQLITE_NULL) {
        return std::nullopt;
    }
    return col_text(stmt, idx);
}

// Map a prepared statement row (26 columns in ColIdx order) into a PipelineRun.
PipelineRun map_row_(sqlite3_stmt* stmt) {
    PipelineRun run;
    run.id               = col_text(stmt, kColId);
    run.kind             = kind_from_string(col_text(stmt, kColKind));
    run.aggregate_id     = col_text(stmt, kColAggregateId);
    run.tenant_id        = col_text(stmt, kColTenantId);
    run.business_task_id = col_text_opt(stmt, kColBusinessTaskId);
    run.parent_run_id    = col_text_opt(stmt, kColParentRunId);
    run.profile_name     = col_text(stmt, kColProfileName);
    run.input_hash       = col_text(stmt, kColInputHash);
    run.idempotency_key  = col_text(stmt, kColIdempotencyKey);
    run.pipeline_name    = col_text(stmt, kColPipelineName);
    run.pipeline_version = col_text(stmt, kColPipelineVersion);
    run.status           = status_from_string(col_text(stmt, kColStatus));

    if (sqlite3_column_type(stmt, kColCheckpointSequence) == SQLITE_NULL) {
        run.checkpoint_sequence = std::nullopt;
    } else {
        run.checkpoint_sequence = sqlite3_column_int64(stmt, kColCheckpointSequence);
    }

    run.error_kind       = col_text_opt(stmt, kColErrorKind);
    run.retry_count      = sqlite3_column_int64(stmt, kColRetryCount);
    run.worker_id        = col_text_opt(stmt, kColWorkerId);
    run.lease_until      = col_text_opt(stmt, kColLeaseUntil);
    run.item_run_ids     = col_text(stmt, kColItemRunIds);
    run.step_contracts   = col_text(stmt, kColStepContracts);
    run.watermark        = col_text(stmt, kColWatermark);
    run.progress         = col_text(stmt, kColProgress);
    run.counters         = col_text(stmt, kColCounters);
    run.warnings         = col_text(stmt, kColWarnings);
    run.stage_timings_ms = col_text(stmt, kColStageTimingsMs);
    run.started_at       = col_text(stmt, kColStartedAt);
    run.updated_at       = col_text(stmt, kColUpdatedAt);
    return run;
}

// Build a "SELECT <kCols> FROM governance_pipeline_run WHERE id=?" query string.
// The kCols literal is assembled at compile time via string concatenation.
// Using a helper avoids repeating the 26-column list in get() and read_row_().
std::string select_by_id_sql() {
    return std::string("SELECT ") + kCols +
           " FROM governance_pipeline_run WHERE id=?";
}

// Build the find_active_run query string.
std::string select_active_sql() {
    return std::string("SELECT ") + kCols +
           " FROM governance_pipeline_run"
           " WHERE kind=? AND tenant_id=? AND aggregate_id=? AND input_hash=?"
           " AND status IN ('QUEUED','RUNNING') LIMIT 1";
}

}  // namespace

// ── Public methods ────────────────────────────────────────────────────────────

std::optional<PipelineRun> PipelineRunStore::get(std::string_view run_id) {
    sqlite3* const dbh = conn_.raw();
    const std::string sql = select_by_id_sql();

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(dbh, "PipelineRunStore::get: prepare failed");
    }
    persistence::StmtHandle hnd(raw);
    bind_sv(hnd.get(), 1, run_id);

    const int rcode = sqlite3_step(hnd.get());
    if (rcode == SQLITE_ROW) {
        return map_row_(hnd.get());
    }
    if (rcode == SQLITE_DONE) {
        return std::nullopt;
    }
    throw make_sqlite_error(dbh, "PipelineRunStore::get: step failed");
}

std::optional<PipelineRun> PipelineRunStore::find_active_run(
        PipelineKind kind, std::string_view tenant_id,
        std::string_view aggregate_id, std::string_view input_hash) {
    sqlite3* const dbh = conn_.raw();
    const std::string sql = select_active_sql();

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, sql.c_str(), -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(dbh, "PipelineRunStore::find_active_run: prepare failed");
    }
    persistence::StmtHandle hnd(raw);
    bind_sv(hnd.get(), 1, kind_to_string(kind));
    bind_sv(hnd.get(), 2, tenant_id);
    bind_sv(hnd.get(), 3, aggregate_id);
    bind_sv(hnd.get(), 4, input_hash);

    const int rcode = sqlite3_step(hnd.get());
    if (rcode == SQLITE_ROW) {
        return map_row_(hnd.get());
    }
    if (rcode == SQLITE_DONE) {
        return std::nullopt;
    }
    throw make_sqlite_error(dbh, "PipelineRunStore::find_active_run: step failed");
}

PipelineRun PipelineRunStore::enqueue(const NewRun& spec) {
    // CX-10: ComplianceErase is refused in c1 (invariant-4 coupling deferred).
    if (spec.kind == PipelineKind::ComplianceErase) {
        throw std::runtime_error(
            "PipelineRunStore::enqueue: ComplianceErase rejected in c1 "
            "(invariant-4 coupling deferred)");
    }

    // Fast path (invariant 1): return existing active run without inserting.
    auto active = find_active_run(
        spec.kind, spec.tenant_id, spec.aggregate_id, spec.input_hash);
    if (active) {
        return *active;
    }

    sqlite3* const dbh = conn_.raw();
    const std::string new_id = random_id();
    const std::string now_ts = iso8601_utc(std::chrono::system_clock::now());

    // Plain INSERT (CX-3 — NOT INSERT OR IGNORE; concurrent collision handled below).
    static constexpr const char* kInsertSql =
        "INSERT INTO governance_pipeline_run("
        "id,kind,aggregate_id,tenant_id,business_task_id,parent_run_id,"
        "profile_name,input_hash,idempotency_key,pipeline_name,pipeline_version,"
        "status,step_contracts,started_at,updated_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, kInsertSql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(dbh, "PipelineRunStore::enqueue: prepare failed");
    }
    persistence::StmtHandle hnd(raw);

    bind_sv(hnd.get(), 1, new_id);
    bind_sv(hnd.get(), 2, kind_to_string(spec.kind));
    bind_sv(hnd.get(), 3, spec.aggregate_id);
    bind_sv(hnd.get(), 4, spec.tenant_id);

    // business_task_id — nullable
    if (spec.business_task_id) {
        bind_sv(hnd.get(), 5, *spec.business_task_id);
    } else {
        sqlite3_bind_null(hnd.get(), 5);
    }

    // parent_run_id — nullable
    if (spec.parent_run_id) {
        bind_sv(hnd.get(), 6, *spec.parent_run_id);
    } else {
        sqlite3_bind_null(hnd.get(), 6);
    }

    bind_sv(hnd.get(), 7, spec.profile_name);
    bind_sv(hnd.get(), 8, spec.input_hash);
    bind_sv(hnd.get(), 9, spec.idempotency_key);
    bind_sv(hnd.get(), 10, spec.pipeline_name);
    bind_sv(hnd.get(), 11, spec.pipeline_version);
    sqlite3_bind_text(hnd.get(), 12, "QUEUED", -1, SQLITE_STATIC);
    bind_sv(hnd.get(), 13, spec.step_contracts);
    bind_sv(hnd.get(), 14, now_ts);
    bind_sv(hnd.get(), 15, now_ts);

    const int rcode = sqlite3_step(hnd.get());

    if (rcode == SQLITE_CONSTRAINT) {
        // CX-3 backstop: a concurrent writer inserted a matching active run between
        // our fast-path check and this INSERT. Re-detect and return it.
        auto raced = find_active_run(
            spec.kind, spec.tenant_id, spec.aggregate_id, spec.input_hash);
        if (raced) {
            return *raced;
        }
        // A genuine constraint (CHECK, FK, etc.) — not a dedup race.
        throw make_sqlite_error(dbh, "PipelineRunStore::enqueue: constraint violation");
    }

    if (rcode != SQLITE_DONE) {
        throw make_sqlite_error(dbh, "PipelineRunStore::enqueue: INSERT step failed");
    }

    return read_row_(new_id);
}

// CX-8: lease_until MUST be a canonical ISO-8601 UTC string (YYYY-MM-DDTHH:MM:SSZ).
// reclaim (Task 3a.5) compares lease_until lexicographically; only the canonical
// format makes that comparison valid. No runtime validation here — caller contract.
PipelineRun PipelineRunStore::claim(
        std::string_view run_id,
        std::string_view worker_id,
        std::string_view lease_until) {
    sqlite3* const dbh = conn_.raw();
    const std::string now_ts = iso8601_utc(std::chrono::system_clock::now());

    static constexpr const char* kUpdateSql =
        "UPDATE governance_pipeline_run"
        " SET status='RUNNING', worker_id=?, lease_until=?, updated_at=?"
        " WHERE id=? AND status='QUEUED'";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, kUpdateSql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(dbh, "PipelineRunStore::claim: prepare failed");
    }
    persistence::StmtHandle hnd(raw);
    bind_sv(hnd.get(), 1, worker_id);
    bind_sv(hnd.get(), 2, lease_until);
    bind_sv(hnd.get(), 3, now_ts);
    bind_sv(hnd.get(), 4, run_id);

    const int rcode = sqlite3_step(hnd.get());
    if (rcode != SQLITE_DONE) {
        throw make_sqlite_error(dbh, "PipelineRunStore::claim: step failed");
    }
    if (sqlite3_changes(dbh) == 0) {
        throw make_sqlite_error(dbh, "PipelineRunStore::claim: run not QUEUED");
    }
    return read_row_(run_id);
}

PipelineRun PipelineRunStore::confirm(
        std::string_view run_id,
        std::string_view checkpoint_json,
        PipelineRunStatus terminal) {
    // Guard: terminal must be one of the three valid terminal states.
    if (terminal != PipelineRunStatus::Completed &&
        terminal != PipelineRunStatus::PartialSuccess &&
        terminal != PipelineRunStatus::DegradedCompleted) {
        throw std::invalid_argument(
            "confirm: terminal must be Completed/PartialSuccess/DegradedCompleted");
    }

    sqlite3* const dbh = conn_.raw();
    const std::string now_ts = iso8601_utc(std::chrono::system_clock::now());

    static constexpr const char* kUpdateSql =
        "UPDATE governance_pipeline_run"
        " SET status=?, watermark=?, updated_at=?"
        " WHERE id=? AND status='RUNNING'";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, kUpdateSql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(dbh, "PipelineRunStore::confirm: prepare failed");
    }
    persistence::StmtHandle hnd(raw);
    bind_sv(hnd.get(), 1, status_to_string(terminal));
    bind_sv(hnd.get(), 2, checkpoint_json);
    bind_sv(hnd.get(), 3, now_ts);
    bind_sv(hnd.get(), 4, run_id);

    const int rcode = sqlite3_step(hnd.get());
    if (rcode != SQLITE_DONE) {
        throw make_sqlite_error(dbh, "PipelineRunStore::confirm: step failed");
    }
    if (sqlite3_changes(dbh) == 0) {
        throw make_sqlite_error(dbh, "PipelineRunStore::confirm: run not RUNNING");
    }
    return read_row_(run_id);
}

PipelineRun PipelineRunStore::reclaim(
        std::string_view run_id,
        std::string_view worker_id,
        std::string_view lease_until) {
    sqlite3* const dbh = conn_.raw();
    const std::string now_ts = iso8601_utc(std::chrono::system_clock::now());

    // CX-9: reclaim is the ONLY method that increments retry_count.
    // CX-8: lease_until compared lexicographically (both canonical ISO-8601 UTC).
    static constexpr const char* kUpdateSql =
        "UPDATE governance_pipeline_run"
        " SET worker_id=?, lease_until=?, retry_count=retry_count+1, updated_at=?"
        " WHERE id=? AND status='RUNNING' AND lease_until < ?";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, kUpdateSql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(dbh, "PipelineRunStore::reclaim: prepare failed");
    }
    persistence::StmtHandle hnd(raw);
    bind_sv(hnd.get(), 1, worker_id);
    bind_sv(hnd.get(), 2, lease_until);
    bind_sv(hnd.get(), 3, now_ts);
    bind_sv(hnd.get(), 4, run_id);
    bind_sv(hnd.get(), 5, now_ts);

    const int rcode = sqlite3_step(hnd.get());
    if (rcode != SQLITE_DONE) {
        throw make_sqlite_error(dbh, "PipelineRunStore::reclaim: step failed");
    }
    if (sqlite3_changes(dbh) == 0) {
        throw make_sqlite_error(dbh, "PipelineRunStore::reclaim: lease not expired or run not RUNNING");
    }
    return read_row_(run_id);
}

PipelineRun PipelineRunStore::record_checkpoint(
        std::string_view run_id,
        long long checkpoint_sequence,
        std::string_view watermark_json) {
    sqlite3* const dbh = conn_.raw();
    const std::string now_ts = iso8601_utc(std::chrono::system_clock::now());

    static constexpr const char* kUpdateSql =
        "UPDATE governance_pipeline_run"
        " SET checkpoint_sequence=?, watermark=?, updated_at=?"
        " WHERE id=? AND status='RUNNING'";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(dbh, kUpdateSql, -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(dbh, "PipelineRunStore::record_checkpoint: prepare failed");
    }
    persistence::StmtHandle hnd(raw);
    sqlite3_bind_int64(hnd.get(), 1, checkpoint_sequence);
    bind_sv(hnd.get(), 2, watermark_json);
    bind_sv(hnd.get(), 3, now_ts);
    bind_sv(hnd.get(), 4, run_id);

    const int rcode = sqlite3_step(hnd.get());
    if (rcode != SQLITE_DONE) {
        throw make_sqlite_error(dbh, "PipelineRunStore::record_checkpoint: step failed");
    }
    if (sqlite3_changes(dbh) == 0) {
        throw make_sqlite_error(dbh, "PipelineRunStore::record_checkpoint: run not RUNNING");
    }
    return read_row_(run_id);
}

// ── Private helpers ───────────────────────────────────────────────────────────

PipelineRun PipelineRunStore::read_row_(std::string_view run_id) {
    auto opt = get(run_id);
    if (!opt) {
        throw std::runtime_error(
            "PipelineRunStore::read_row_: run not found: " + std::string(run_id));
    }
    return *opt;
}

}  // namespace starling::governance
