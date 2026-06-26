#pragma once
#include "starling/persistence/connection.hpp"

#include <optional>
#include <string>
#include <string_view>

namespace starling::bus {

// Terminal status for a pipeline_run row. 'Started' is written by start_run;
// finish_run only takes a terminal status.
enum class PipelineStatus   { Started, Finished, Failed };

// extraction_attempt.status. M0.4's LLM extractor will write one row per
// (span_key, attempt_number) tuple per pipeline_run; the uniqueness is enforced
// by migration 0002's idx_extraction_attempt_unique. The Noop variant is the
// "extraction_span_key already produced an APPROVED Statement" short-circuit
// — no new Statement is written, but the attempt is still ledger-recorded
// for audit. See docs/design/subsystems_design/05_bus.md § extraction_attempt.
enum class ExtractionStatus { Success, PartialSuccess, Failed, Noop };

// Per-attempt LLM cost, persisted on the extraction_attempt row (migration
// 0027). Mirrors the usage fields LLMResponse captures in the adapter (the
// core boundary): token counts + the network round-trip latency. Defaults to
// all-zero so callers that don't measure cost (or the FakeLLMAdapter) record an
// honest 0 rather than a sentinel. See extractor.cpp's take_cost() for why the
// cost is attributed to exactly ONE row per extract() call (no double-counting
// across the per-statement-span success rows of a single attempt).
struct AttemptCost {
    int prompt_tokens     = 0;
    int completion_tokens = 0;
    int total_tokens      = 0;
    int latency_ms        = 0;
};

// Sole sanctioned write path into pipeline_run / extraction_attempt for M0.4's
// LLM extractor. Sealing the API here, before the extractor exists, prevents
// M0.4 from inventing ad-hoc inserts that bypass the (span_key, attempt_number)
// discipline.
class PipelineLedger {
public:
    explicit PipelineLedger(starling::persistence::Connection& c) : conn_(c) {}

    // Inserts a pipeline_run row with status='started' and started_at=now (UTC).
    // Returns the generated run_id (random 128-bit hex with UUID-style dashes
    // — placeholder for real UUIDv7 in M0.4; see random_id() in the .cpp).
    std::string start_run(std::string_view tenant_id,
                          std::string_view input_ref,
                          std::string_view metadata_json = "{}");

    // UPDATE pipeline_run SET finished_at=now, status=<terminal>. Caller must
    // pass a terminal status (Finished or Failed); Started is rejected at the
    // SQL level only — the helper does not validate the enum value.
    void finish_run(std::string_view run_id, PipelineStatus terminal);

    // INSERTs an extraction_attempt row. The dedup invariant lives HERE:
    // (pipeline_run_id, span_key, attempt_number) is unique (migration 0002),
    // and a duplicate is dropped silently (INSERT OR IGNORE, first write wins)
    // — returns the new row id when recorded, std::nullopt when dropped, and
    // never throws on a duplicate. Callers gate side effects (e.g. the
    // extraction.noop event) on the return value instead of maintaining their
    // own dedup sets; four production 500s came from callers each re-deriving
    // this invariant (extractor Accepted 双写 / noop 重记 / 重忆重放). raw_output
    // and error are stored as NULL when their string_views are empty.
    std::optional<std::string> record_attempt(std::string_view run_id,
                                              std::string_view extraction_span_key,
                                              int attempt_number,
                                              ExtractionStatus status,
                                              std::string_view raw_output = {},
                                              std::string_view error = {},
                                              const AttemptCost& cost = {});

private:
    starling::persistence::Connection& conn_;
};

}  // namespace starling::bus
