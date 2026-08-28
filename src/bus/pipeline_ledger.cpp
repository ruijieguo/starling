#include "starling/bus/pipeline_ledger.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/governance/pipeline_run_store.hpp"

#include <chrono>
#include <cstdint>
#include <iomanip>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>

namespace starling::bus {

using persistence::detail::bind_sv;
using persistence::detail::iso8601_utc;
using persistence::detail::make_sqlite_error;

namespace {

// 128 random bits formatted with UUID dashes — NOT a valid UUID of any version
// (version/variant nibbles are not set). Sufficient for M0.2 because the run_id
// and attempt_id are only used as primary keys. M0.4 will replace this with
// real UUIDv7 alongside the LLM extractor. Mirrors random_event_id() in
// outbox_writer.cpp; kept local because the only other caller (OutboxWriter)
// has its own copy by design (the two will both move to a shared UUIDv7 helper
// when M0.4 lands).
std::string random_id() {
    static thread_local std::mt19937_64 rng{std::random_device{}()};
    const std::uint64_t a = rng();
    const std::uint64_t b = rng();
    std::ostringstream oss;
    oss << std::hex << std::setfill('0')
        << std::setw(8) << static_cast<std::uint32_t>(a >> 32) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(a >> 16) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(a) << '-'
        << std::setw(4) << static_cast<std::uint16_t>(b >> 48) << '-'
        << std::setw(12) << (b & 0xFFFFFFFFFFFFULL);
    return oss.str();
}

const char* extraction_status_string(ExtractionStatus s) {
    switch (s) {
        case ExtractionStatus::Success:        return "success";
        case ExtractionStatus::PartialSuccess: return "partial_success";
        case ExtractionStatus::Failed:         return "failed";
        case ExtractionStatus::Noop:           return "noop";
    }
    return "unknown";
}

}  // namespace

std::string PipelineLedger::start_run(
        std::string_view tenant_id,
        std::string_view input_ref,
        std::string_view metadata_json) {
    governance::PipelineRunStore store(conn_);
    governance::NewRun spec;
    spec.kind = governance::PipelineKind::Extraction;
    spec.aggregate_id = std::string(input_ref);
    spec.tenant_id = std::string(tenant_id);
    spec.profile_name = "inline";
    spec.input_hash = crypto::sha256_hex(input_ref);
    spec.idempotency_key = random_id();
    spec.pipeline_name = "extractor";
    spec.pipeline_version = "1";
    spec.metadata_json = std::string(metadata_json);
    auto run = store.enqueue(spec);
    if (run.status == governance::PipelineRunStatus::Queued) {
        const auto lease = iso8601_utc(
            std::chrono::system_clock::now() + std::chrono::minutes(5));
        run = store.claim(run.id, "inline", lease);
    } else if (run.status == governance::PipelineRunStatus::Running) {
        throw std::runtime_error(
            "PipelineLedger::start_run: extraction run already RUNNING: " + run.id);
    }
    return run.id;
}

void PipelineLedger::finish_run(std::string_view run_id, PipelineStatus terminal) {
    governance::PipelineRunStore store(conn_);
    if (terminal == PipelineStatus::Finished) {
        store.confirm(run_id, "{}", governance::PipelineRunStatus::Completed);
    } else if (terminal == PipelineStatus::PartialSuccess) {
        store.confirm(run_id, "{}", governance::PipelineRunStatus::PartialSuccess);
    } else if (terminal == PipelineStatus::Failed) {
        store.dead_letter(run_id, "extraction_failed");
    } else {
        throw std::invalid_argument("PipelineLedger::finish_run requires terminal status");
    }
}

std::optional<std::string> PipelineLedger::record_attempt(
        std::string_view run_id,
        std::string_view extraction_span_key,
        int attempt_number,
        ExtractionStatus status,
        std::string_view raw_output,
        std::string_view error,
        const AttemptCost& cost) {
    sqlite3* const db = conn_.raw();
    const std::string id = random_id();
    const std::string ts = iso8601_utc(std::chrono::system_clock::now());

    // INSERT OR IGNORE: at most one row per (run, span, attempt) — the writer
    // owns the dedup invariant (first write wins); a duplicate reports nullopt
    // instead of surfacing the UNIQUE violation to callers.
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "INSERT OR IGNORE INTO extraction_attempt("
            "id,pipeline_run_id,extraction_span_key,attempt_number,"
            "status,raw_output,error,created_at,"
            "prompt_tokens,completion_tokens,total_tokens,latency_ms) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            -1, &raw, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db, "PipelineLedger::record_attempt: prepare failed");
    }
    starling::persistence::StmtHandle h(raw);
    bind_sv(h.get(), 1, id);
    bind_sv(h.get(), 2, run_id);
    bind_sv(h.get(), 3, extraction_span_key);
    sqlite3_bind_int(h.get(), 4, attempt_number);
    sqlite3_bind_text(h.get(), 5, extraction_status_string(status), -1, SQLITE_STATIC);
    if (raw_output.empty()) sqlite3_bind_null(h.get(), 6);
    else                    bind_sv(h.get(), 6, raw_output);
    if (error.empty())      sqlite3_bind_null(h.get(), 7);
    else                    bind_sv(h.get(), 7, error);
    bind_sv(h.get(), 8, ts);
    sqlite3_bind_int(h.get(), 9,  cost.prompt_tokens);
    sqlite3_bind_int(h.get(), 10, cost.completion_tokens);
    sqlite3_bind_int(h.get(), 11, cost.total_tokens);
    sqlite3_bind_int(h.get(), 12, cost.latency_ms);
    if (sqlite3_step(h.get()) != SQLITE_DONE) {
        throw make_sqlite_error(db, "PipelineLedger::record_attempt: INSERT step failed");
    }
    if (sqlite3_changes(db) == 0) {
        return std::nullopt;  // duplicate (run, span, attempt) dropped
    }
    return id;
}

}  // namespace starling::bus
