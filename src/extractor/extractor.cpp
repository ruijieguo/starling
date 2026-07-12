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
using starling::bus::AttemptCost;
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

// First-order DESIRE predicate/modality test for the opt-in holder
// re-attribution (ValidationPolicy.attribute_first_order_mental_to_holder).
// Only the desire-family is included: for DESIRES/INTENDS/PREFERS the subject
// IS the desirer/intender (the attitude bearer). BELIEVES/KNOWS/COMMITS are
// excluded — for those, the subject is the topic, not the bearer, so
// re-attributing holder to subject would be wrong.
bool is_first_order_desire(schema::Modality m, std::string_view predicate) {
    if (predicate == "prefers" || predicate == "wants"
            || predicate == "desires" || predicate == "intends") return true;
    switch (m) {
        case schema::Modality::DESIRES:
        case schema::Modality::INTENDS:
        case schema::Modality::PREFERS:
            return true;
        default:
            return false;
    }
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

ExtractionLlmResult Extractor::extract_llm(
        const std::vector<std::uint8_t>&  payload_bytes,
        std::string_view                  holder_id,
        const ExistingRefMap&             existing_ref_map) {
    ExtractionLlmResult out;
    out.prompt_body       = build_prompt(holder_id, payload_bytes, existing_ref_map);
    out.prompt_input_hash = compute_prompt_input_hash(out.prompt_body);

    // 重试循环只做 LLM + parse(零 DB)。retry 决策与单体 run 完全一致:
    // !resp.ok 或 parse 有错 → 收录并 continue;parse 成功 → terminal 并 break。
    for (int attempt = 1; attempt <= kMaxRetries; ++attempt) {
        ExtractionLlmAttempt rec;
        rec.attempt = attempt;
        rec.resp    = adapter_.extract(out.prompt_body, out.prompt_input_hash);
        if (!rec.resp.ok) {
            out.attempts.push_back(std::move(rec));
            continue;
        }
        rec.parse  = parse_extractor_json(rec.resp.raw_xml, existing_ref_map);
        rec.parsed = true;
        if (!rec.parse.errors.empty()) {
            out.attempts.push_back(std::move(rec));
            continue;
        }
        rec.terminal = true;
        out.attempts.push_back(std::move(rec));
        break;
    }
    return out;
}

ExtractionRunResult Extractor::persist(
        std::string_view                  engram_ref_id,
        std::string_view                  holder_id,
        std::string_view                  holder_tenant_id,
        std::string_view                  interlocutor,
        const ExtractionLlmResult&        llm_result) {

    ExtractionRunResult result;

    // 单事务(移自原 run):FAILED 仍 COMMIT(attempt 行 + events 持久化),
    // 异常 ROLLBACK(TransactionGuard)。所有 DB 写集中在 LLM 之后。
    starling::persistence::TransactionGuard tx(conn_);

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

    bool any_accepted   = false;
    bool all_failed     = true;
    bool result_partial = false;

    for (const auto& rec : llm_result.attempts) {
        const int attempt = rec.attempt;
        const std::string attempt_suffix = "attempt=" + std::to_string(attempt);
        // cost 归属:每 attempt 只算一次,落到本轮写的第一行(移自原 run)。
        bool attempt_cost_used = false;
        auto take_cost = [&]() -> AttemptCost {
            if (attempt_cost_used) {
                return {};
            }
            attempt_cost_used = true;
            return {rec.resp.prompt_tokens, rec.resp.completion_tokens,
                    rec.resp.total_tokens, rec.resp.latency_ms};
        };
        if (!rec.resp.ok) {
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  ExtractionStatus::Failed,
                                  /*raw_output=*/{},
                                  rec.resp.error,
                                  take_cost());
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

        if (!rec.parse.errors.empty()) {
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  ExtractionStatus::Failed,
                                  rec.resp.raw_xml,
                                  rec.parse.errors.front().kind,
                                  take_cost());
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

        // Parse 成功。逐语句校验 + 写(移自原 run:283-421,parsed 用本 attempt 的拷贝)。
        ParseResult parsed = rec.parse;   // 可变拷贝:下面会改 statements
        StatementWriter writer(conn_);
        bool any_rejected_this_attempt   = false;
        bool wrote_anything_this_attempt = false;
        bool noop_short_circuited        = false;
        std::set<std::string> written_span_keys;
        for (auto& stmt : parsed.statements) {
            stmt.holder_tenant_id = std::string(holder_tenant_id);
            stmt.chunk_index      = chunk_index;
            if (stmt.source_hash.empty()) {
                stmt.source_hash = "chunk-" + std::to_string(chunk_index);
            }
            if (cog_hub && stmt.subject_kind == "cognizer" && !stmt.subject_id.empty()) {
                stmt.subject_id = starling::cognizer::resolve_or_register_cognizer(
                    *cog_hub, holder_tenant_id, stmt.subject_id);
            }
            if (policy_.attribute_first_order_mental_to_holder
                    && stmt.llm_nesting_depth == 0
                    && is_first_order_desire(stmt.modality, stmt.predicate)
                    && !stmt.subject_id.empty()
                    && stmt.subject_id != std::string(holder_id)) {
                stmt.holder_id = stmt.subject_id;
            } else {
                stmt.holder_id = std::string(holder_id);
            }
            if (!interlocutor.empty()) {
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
            if (written_span_keys.find(span_key) == written_span_keys.end()
                    && extraction_span_key_already_succeeded(conn_, span_key)) {
                if (ledger.record_attempt(run_id, span_key, attempt,
                                          ExtractionStatus::Noop,
                                          /*raw_output=*/{},
                                          /*error=*/"noop:extraction_span_key_hit",
                                          take_cost())) {
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
                written_span_keys.insert(span_key);
                ledger.record_attempt(run_id, span_key, attempt,
                                      ExtractionStatus::Success,
                                      /*raw_output=*/{},
                                      /*error=*/{},
                                      take_cost());
            } else {
                result.accepted_statement_ids.push_back(
                    std::get<StatementWriteChunkDuplicate>(outcome).stmt_id);
            }
            wrote_anything_this_attempt = true;
        }

        if (!wrote_anything_this_attempt && !noop_short_circuited) {
            const auto attempt_status =
                any_rejected_this_attempt ? ExtractionStatus::Failed
                                          : ExtractionStatus::Success;
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  attempt_status,
                                  rec.resp.raw_xml, /*error=*/{},
                                  take_cost());
        } else if (wrote_anything_this_attempt && any_rejected_this_attempt) {
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  ExtractionStatus::PartialSuccess,
                                  rec.resp.raw_xml, /*error=*/{},
                                  take_cost());
            result_partial = true;
        }
        if (wrote_anything_this_attempt) any_accepted = true;
        all_failed = false;
        break;
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
        result.status = ExtractionRunResult::Status::SUCCESS;
        ledger.finish_run(run_id, PipelineStatus::Finished);
        emit_pipeline_event(conn_, "pipeline.run_completed",
                            holder_tenant_id, run_id, run_started_event_id);
    }

    tx.commit();
    return result;
}

ExtractionRunResult Extractor::run(
        std::string_view                  engram_ref_id,
        const std::vector<std::uint8_t>&  payload_bytes,
        std::string_view                  holder_id,
        std::string_view                  holder_tenant_id,
        const ExistingRefMap&             existing_ref_map,
        std::string_view                  interlocutor) {
    // 单体 = 三相内联(单一语义源;host 分相调用与此逐字段等价,见 test_extractor_phases）。
    const ExtractionLlmResult llm = extract_llm(payload_bytes, holder_id, existing_ref_map);
    return persist(engram_ref_id, holder_id, holder_tenant_id, interlocutor, llm);
}

}  // namespace starling::extractor
