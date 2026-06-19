#include "starling/extractor/extractor.hpp"

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/bus/pipeline_ledger.hpp"
#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/name_resolver.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/bus/statement_writer.hpp"
#include "starling/crypto/sha256.hpp"
#include "starling/extractor/extraction_span_key.hpp"
#include "starling/extractor/statement_validator.hpp"
#include "starling/extractor/json_parser.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <algorithm>
#include <chrono>
#include <optional>
#include <set>
#include <string>
#include <variant>

namespace starling::extractor {

using starling::bus::compute_idempotency_key;
using starling::bus::compute_window_bucket;
using starling::bus::BusEvent;
using starling::bus::ExtractionStatus;
using starling::bus::OutboxWriter;
using starling::bus::PipelineLedger;
using starling::bus::PipelineStatus;
using starling::bus::StatementWriteAccepted;
using starling::bus::StatementWriteChunkDuplicate;
using starling::bus::StatementWriter;

namespace {

std::string emit_pipeline_event(
        starling::persistence::Connection& conn,
        std::string_view event_type,
        std::string_view tenant_id,
        std::string_view run_id,
        std::optional<std::string> causation_parent_event_id) {
    BusEvent ev;
    ev.tenant_id    = tenant_id;
    ev.event_type   = event_type;
    ev.primary_id   = run_id;
    ev.aggregate_id = run_id;
    if (causation_parent_event_id.has_value()) {
        ev.causation_chain.push_back(*causation_parent_event_id);
    }
    const std::string causation_root = causation_parent_event_id.value_or("");
    const std::string window_bucket  = compute_window_bucket(
        event_type, std::chrono::system_clock::now());
    ev.idempotency_key = compute_idempotency_key(
        event_type, run_id, /*canonical_key=*/run_id, causation_root, window_bucket);
    ev.payload_json = std::string("{\"run_id\":\"") + std::string(run_id) + "\"}";
    OutboxWriter w(conn);
    w.append(ev);
    return ev.event_id;
}

std::string emit_extraction_event(
        starling::persistence::Connection& conn,
        std::string_view event_type,
        std::string_view tenant_id,
        std::string_view run_id,
        std::string_view chunk_span_key,
        std::optional<std::string> causation_parent_event_id,
        std::string_view canonical_suffix = {}) {
    BusEvent ev;
    ev.tenant_id    = tenant_id;
    ev.event_type   = event_type;
    ev.primary_id   = std::string(run_id);
    ev.aggregate_id = std::string(run_id);
    if (causation_parent_event_id.has_value()) {
        ev.causation_chain.push_back(*causation_parent_event_id);
    }
    const std::string causation_root = causation_parent_event_id.value_or("");
    const std::string window_bucket  = compute_window_bucket(
        event_type, std::chrono::system_clock::now());
    // Make idempotency_key unique per attempt for events that fire repeatedly
    // within the same 60s window for the same span_key (e.g. extraction.failed
    // across 3 retries). canonical_suffix carries the attempt number; for
    // events that only fire once per run+span (e.g. extraction.noop) it is
    // empty and the original (event_type, run_id, span_key, causation, window)
    // identity is preserved.
    std::string canonical_key = std::string(chunk_span_key);
    if (!canonical_suffix.empty()) {
        canonical_key.push_back('\x1f');
        canonical_key.append(canonical_suffix);
    }
    ev.idempotency_key = compute_idempotency_key(
        event_type, run_id, canonical_key, causation_root, window_bucket);
    ev.payload_json = std::string("{\"run_id\":\"") + std::string(run_id)
                    + "\",\"chunk_span_key\":\"" + std::string(chunk_span_key) + "\"}";
    OutboxWriter w(conn);
    w.append(ev);
    return ev.event_id;
}

bool extraction_span_key_already_succeeded(
        starling::persistence::Connection& conn,
        std::string_view span_key) {
    sqlite3* db = conn.raw();
    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(db,
            "SELECT 1 FROM extraction_attempt "
            "WHERE extraction_span_key = ? AND status = 'success' LIMIT 1",
            -1, &raw, nullptr) != SQLITE_OK) {
        throw starling::persistence::detail::make_sqlite_error(
            db, "extraction_span_key_already_succeeded: prepare");
    }
    starling::persistence::StmtHandle h(raw);
    starling::persistence::detail::bind_sv(h.get(), 1, span_key);
    return sqlite3_step(h.get()) == SQLITE_ROW;
}

}  // namespace

std::string Extractor::compute_prompt_input_hash(std::string_view prompt_body) {
    return starling::crypto::sha256_hex(prompt_body);
}

std::string Extractor::build_prompt_body_for_tests(
        std::string_view holder_id,
        const std::vector<std::uint8_t>& payload_bytes,
        const ExistingRefMap& refs) {
    // M0.4 prompt body format. Real prompt construction lives in
    // python/starling/extractor/prompts.py (Task 9); here we keep the C++
    // builder minimal so the LLM-side tests can drive the adapter through
    // compute_prompt_input_hash(). The body is opaque to the adapter.
    std::string body = "[M0.4 extractor prompt v1.0]\n";
    body += "holder_id=";
    body += std::string(holder_id);
    body += "\npayload_size=";
    body += std::to_string(payload_bytes.size());
    body += "\nexisting_refs=";
    body += std::to_string(refs.size());
    return body;
}

std::string Extractor::build_prompt(
        std::string_view holder_id,
        const std::vector<std::uint8_t>& payload_bytes,
        const ExistingRefMap& existing_ref_map) const {
    if (prompt_template_.empty()) {
        // FakeLLM / unit tests ignore the prompt text but key the adapter on
        // its hash; keep the prior deterministic body byte-for-byte.
        return build_prompt_body_for_tests(holder_id, payload_bytes,
                                           existing_ref_map);
    }
    const std::string convo(payload_bytes.begin(), payload_bytes.end());
    const std::string placeholder = "{convo}";
    std::string out = prompt_template_;
    const auto pos = out.find(placeholder);
    if (pos != std::string::npos) {
        out.replace(pos, placeholder.size(), convo);
    } else {
        out += "\n\nConversation:\n" + convo;
    }
    return out;
}

ExtractionRunResult Extractor::run(
        std::string_view                  engram_ref_id,
        const std::vector<std::uint8_t>&  payload_bytes,
        std::string_view                  holder_id,
        std::string_view                  holder_tenant_id,
        const ExistingRefMap&             existing_ref_map,
        std::string_view                  interlocutor) {

    ExtractionRunResult result;

    // The orchestrator uses a single transaction per run. The retry loop
    // re-prepares the LLM call but stays inside the same transaction; on
    // FAILED outcome we still COMMIT (so attempt rows + events persist),
    // just with terminal status='failed'. On exception we ROLLBACK
    // (TransactionGuard does it).
    starling::persistence::TransactionGuard tx(conn_);

    // Phase 2 (Task 2.2): when a store adapter was provided, resolve each
    // statement's subject_id (a cognizer surface) to its canonical first-seen
    // name so name-surface drift grounds to one entity. The Hub's register-on-miss
    // writes join this run's open transaction. Best-effort: the resolver returns
    // the raw surface on any error.
    std::optional<starling::cognizer::CognizerHub> cog_hub;
    if (store_adapter_ != nullptr) cog_hub.emplace(*store_adapter_);

    PipelineLedger ledger(conn_);
    const std::string run_id = ledger.start_run(holder_tenant_id, engram_ref_id, "{}");
    const std::string run_started_event_id = emit_pipeline_event(
        conn_, "pipeline.run_started", holder_tenant_id, run_id, std::nullopt);
    result.run_id = run_id;

    const std::int32_t chunk_index = 0;  // M0.4: 1 chunk per Engram
    const std::string chunk_span_key = compute_extraction_span_key(
        engram_ref_id, chunk_index, "__chunk__", "__chunk__");

    bool any_accepted  = false;
    bool all_failed    = true;
    bool result_partial = false;

    const std::string prompt_body = build_prompt(
        holder_id, payload_bytes, existing_ref_map);
    const std::string prompt_input_hash = compute_prompt_input_hash(prompt_body);

    for (int attempt = 1; attempt <= kMaxRetries; ++attempt) {
        const std::string attempt_suffix = "attempt=" + std::to_string(attempt);
        const LLMResponse resp = adapter_.extract(prompt_body, prompt_input_hash);
        if (!resp.ok) {
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  ExtractionStatus::Failed,
                                  /*raw_output=*/{},
                                  resp.error);
            emit_extraction_event(conn_, "extraction.failed",
                                  holder_tenant_id, run_id, chunk_span_key,
                                  run_started_event_id, attempt_suffix);
            if (attempt < kMaxRetries) {
                emit_extraction_event(conn_, "extraction.retry_scheduled",
                                      holder_tenant_id, run_id, chunk_span_key,
                                      run_started_event_id, attempt_suffix);
            }
            continue;
        }

        ParseResult parsed = parse_extractor_json(resp.raw_xml, existing_ref_map);
        if (!parsed.errors.empty()) {
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  ExtractionStatus::Failed,
                                  resp.raw_xml,
                                  parsed.errors.front().kind);
            emit_extraction_event(conn_, "extraction.failed",
                                  holder_tenant_id, run_id, chunk_span_key,
                                  run_started_event_id, attempt_suffix);
            if (attempt < kMaxRetries) {
                emit_extraction_event(conn_, "extraction.retry_scheduled",
                                      holder_tenant_id, run_id, chunk_span_key,
                                      run_started_event_id, attempt_suffix);
            }
            continue;
        }

        // Parse succeeded. Validate and write each statement.
        StatementWriter writer(conn_);
        bool any_rejected_this_attempt = false;
        bool wrote_anything_this_attempt = false;
        bool noop_short_circuited = false;
        // Routes intra-run duplicates: a span written earlier in THIS loop goes
        // to StatementWriter (ChunkDuplicate path) instead of the cross-run
        // noop branch. The (run, span, attempt) ledger dedup itself lives
        // inside PipelineLedger::record_attempt (INSERT OR IGNORE).
        std::set<std::string> written_span_keys;
        for (auto& stmt : parsed.statements) {
            stmt.holder_id        = std::string(holder_id);
            stmt.holder_tenant_id = std::string(holder_tenant_id);
            stmt.chunk_index      = chunk_index;
            if (stmt.source_hash.empty()) {
                stmt.source_hash = "chunk-" + std::to_string(chunk_index);
            }
            // Resolve the cognizer subject surface to its canonical first-seen
            // name (no-op when no store adapter was wired, or for non-cognizer
            // subjects — those carry an external ref, not a name surface).
            if (cog_hub && stmt.subject_kind == "cognizer" && !stmt.subject_id.empty()) {
                stmt.subject_id = starling::cognizer::resolve_or_register_cognizer(
                    *cog_hub, holder_tenant_id, stmt.subject_id);
            }
            if (!interlocutor.empty()) {
                // 对话语境：grounding 参与方 + 可见性都含 self+interlocutor（#2 前提 perceived_by⊇parties）。
                std::vector<std::string> pair{std::string(holder_id), std::string(interlocutor)};
                std::sort(pair.begin(), pair.end());
                stmt.scope_parties = pair;
                if (stmt.perceived_by.empty()) stmt.perceived_by = pair;
            } else if (stmt.perceived_by.empty()) {
                stmt.perceived_by = {std::string(holder_id)};
            }
            const ValidationOutcome v = validate_extracted_statement(stmt, policy_);
            if (!v.ok()) {
                any_rejected_this_attempt = true;
                continue;
            }
            if (v.review_status_override.has_value()) {
                stmt.review_status = *v.review_status_override;
            }

            const std::string span_key = compute_extraction_span_key(
                engram_ref_id, chunk_index, stmt.predicate, stmt.canonical_object_hash);
            // Cross-run idempotency: if a prior run already succeeded for this
            // span_key, emit noop. Intra-run duplicates (same span_key written
            // earlier in this loop) are handled by StatementWriter as
            // ChunkDuplicate — don't noop them here or we'd hit a UNIQUE
            // constraint on the attempt row.
            if (written_span_keys.find(span_key) == written_span_keys.end()
                    && extraction_span_key_already_succeeded(conn_, span_key)) {
                // One parse can yield two statements sharing a span_key (same
                // predicate+object, different subject/polarity); on a
                // re-remember BOTH reach this branch. record_attempt dedupes
                // (run, span, attempt) internally — the second call returns
                // nullopt, and the extraction.noop event is gated on the same
                // outcome so it fires exactly once per span per run.
                if (ledger.record_attempt(run_id, span_key, attempt,
                                          ExtractionStatus::Noop,
                                          /*raw_output=*/{},
                                          /*error=*/"noop:extraction_span_key_hit")) {
                    emit_extraction_event(conn_, "extraction.noop",
                                          holder_tenant_id, run_id, span_key,
                                          run_started_event_id);
                    noop_short_circuited = true;
                }
                continue;
            }

            const auto outcome = writer.write(stmt, engram_ref_id, span_key, run_started_event_id);
            if (std::holds_alternative<StatementWriteAccepted>(outcome)) {
                result.accepted_statement_ids.push_back(
                    std::get<StatementWriteAccepted>(outcome).stmt_id);
                // Record per-statement success so future runs can noop-short-circuit.
                // Two same-span Accepted statements in one parse (same
                // predicate+object, different subject/polarity, neither approved
                // → no ChunkDuplicate) yield ONE Success row: the dedup lives in
                // record_attempt (INSERT OR IGNORE), the duplicate returns nullopt.
                written_span_keys.insert(span_key);
                ledger.record_attempt(run_id, span_key, attempt,
                                      ExtractionStatus::Success,
                                      /*raw_output=*/{},
                                      /*error=*/{});
            } else {
                // StatementWriteChunkDuplicate: statement written (review_requested);
                // the span's Success row already exists from the first duplicate —
                // nothing worth recording (the ledger would drop it anyway).
                result.accepted_statement_ids.push_back(
                    std::get<StatementWriteChunkDuplicate>(outcome).stmt_id);
            }
            wrote_anything_this_attempt = true;
        }

        // Emit a chunk-level aggregate attempt row for cases not covered by
        // per-statement rows:
        // - Nothing written and nothing noop'd: all-rejected or empty parse.
        // - Something written but some were also rejected: partial_success.
        if (!wrote_anything_this_attempt && !noop_short_circuited) {
            const auto attempt_status =
                any_rejected_this_attempt ? ExtractionStatus::Failed
                                          : ExtractionStatus::Success;
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  attempt_status,
                                  resp.raw_xml, /*error=*/{});
        } else if (wrote_anything_this_attempt && any_rejected_this_attempt) {
            // Partial success: at least one statement written, at least one rejected.
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  ExtractionStatus::PartialSuccess,
                                  resp.raw_xml, /*error=*/{});
            result_partial = true;
        }
        if (wrote_anything_this_attempt) any_accepted = true;
        // Parse succeeded: this attempt is not a failure regardless of validate
        // outcome. all_failed tracks adapter/parse failures only.
        all_failed = false;
        break;  // parse succeeded; no retry regardless of validate outcome
    }

    if (any_accepted) {
        result.status = result_partial
            ? ExtractionRunResult::Status::PARTIAL_SUCCESS
            : ExtractionRunResult::Status::SUCCESS;
        ledger.finish_run(run_id, PipelineStatus::Finished);
        emit_pipeline_event(conn_, "pipeline.run_completed",
                            holder_tenant_id, run_id, run_started_event_id);
    } else if (all_failed) {
        result.status = ExtractionRunResult::Status::FAILED;
        ledger.finish_run(run_id, PipelineStatus::Failed);
        emit_pipeline_event(conn_, "pipeline.run_failed",
                            holder_tenant_id, run_id, run_started_event_id);
    } else {
        // Either every statement noop-short-circuited, or the validator
        // rejected every candidate. Either way, no transient error: terminal
        // state is finished.
        result.status = ExtractionRunResult::Status::SUCCESS;
        ledger.finish_run(run_id, PipelineStatus::Finished);
        emit_pipeline_event(conn_, "pipeline.run_completed",
                            holder_tenant_id, run_id, run_started_event_id);
    }

    tx.commit();
    return result;
}

}  // namespace starling::extractor
