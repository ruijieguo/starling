#include "starling/extractor/extractor.hpp"
#include "starling/extractor/claim_contract.hpp"
#include "starling/evidence/engram_store.hpp"
#include <nlohmann/json.hpp>

#include "starling/bus/bus_event.hpp"
#include "starling/bus/outbox_writer.hpp"
#include "starling/bus/pipeline_ledger.hpp"
#include "starling/cognizer/cognizer.hpp"
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

bool retryable_claim_protocol_error(std::string_view kind, const ValidationPolicy& policy) {
    // 目标索引的越界输出必须整体重新生成；与格式错误共享既有额度。
    // 抽取和持久化回放使用同一判断，禁止重试状态与原生校验漂移。
    return kind == "envelope_failure" || kind == "schema_failure"
        || (kind == "batch_scope_failure" && policy.claim_batch_target_units
            && policy.claim_batch_size > 0);
}

nlohmann::json batch_policy_json(const ValidationPolicy& p) {
    nlohmann::json result{{"batch_size",p.claim_batch_size},{"retry_budget",p.claim_protocol_retry_budget},
        {"semantic_claim_contract",p.semantic_claim_contract},{"allow_code_fence",p.claim_allow_code_fence},
        {"output_mode",static_cast<int>(p.claim_output_mode)},{"preserve_text_objects",p.preserve_text_objects},
        {"attribute_first_order_mental_to_holder",p.attribute_first_order_mental_to_holder},
        {"extra_core_predicates",p.extra_core_predicates},{"confidence_drop_floor",p.confidence_drop_floor},
        {"weak_inference_floor",p.weak_inference_floor}};
    if (p.claim_batch_target_units) result["claim_batch_target_units"]=true;
    return result;
}
bool truncated(const LLMResponse& response) {
    return response.finish_reason == "length" || response.finish_reason == "max_tokens"
        || response.error.find("truncat") != std::string::npos;
}

std::string claim_failure_category(const ExtractionLlmResult& result) {
    if (!result.persistence_error.empty()) return "persistence_failure";
    // A protocol error recovered by a later terminal attempt is not a
    // technical failure of the extraction.  Admission failures remain
    // terminal failures because they are never retried by this policy.
    const bool batched = result.claim_batch_size > 0;
    const bool complete = !batched || claim_batch_integrity(result).complete;
    if (batched && complete) {
        const bool rejected = std::any_of(result.attempts.begin(), result.attempts.end(),
            [](const auto& attempt) { return attempt.terminal && attempt.semantic_rejected > 0; });
        return rejected ? "semantic_rejection" : "";
    }
    for (const auto& attempt : result.attempts) {
        if (complete && attempt.terminal && attempt.parse.errors.empty()) {
            return attempt.semantic_rejected > 0 ? "semantic_rejection" : "";
        }
    }
    for (auto it = result.attempts.rbegin(); it != result.attempts.rend(); ++it) {
        const auto& attempt = *it;
        if (!attempt.parse.errors.empty()) {
            const auto& kind = attempt.parse.errors.front().kind;
            if (kind == "envelope_failure") return "envelope_failure";
            if (kind == "scope_failure" || kind == "source_span_failure") return "scope_failure";
            if (kind == "schema_failure") return "schema_failure";
            if (kind == "upstream_failure") {
                const auto& error = attempt.admission_called && !attempt.admission_resp.ok
                    ? attempt.admission_resp.error : attempt.resp.error;
                return (error.find("timeout") != std::string::npos ||
                        error.find("timed out") != std::string::npos)
                    ? "timeout" : "transport_failure";
            }
            return kind;
        }
        if (complete && attempt.semantic_rejected > 0) return "semantic_rejection";
    }
    return batched && !complete ? "batch_integrity_failure" : "";
}

std::string extraction_failure_detail(const ExtractionLlmResult& result) {
    if (!result.persistence_error.empty()) return result.persistence_error;
    for (auto it = result.attempts.rbegin(); it != result.attempts.rend(); ++it) {
        const auto& attempt = *it;
        if (attempt.admission_called && !attempt.admission_resp.ok &&
            !attempt.admission_resp.error.empty()) {
            return attempt.admission_resp.error;
        }
        if (!attempt.parse.errors.empty()) {
            const auto& error = attempt.parse.errors.front();
            std::string detail = error.kind;
            if (!error.field_path.empty()) detail += " at " + error.field_path;
            if (!error.detail.empty()) detail += ": " + error.detail;
            return detail;
        }
        if (!attempt.resp.ok && !attempt.resp.error.empty()) return attempt.resp.error;
        if (!attempt.semantic_rejections.empty() &&
            !attempt.semantic_rejections.front().detail.empty()) {
            return attempt.semantic_rejections.front().detail;
        }
    }
    return {};
}

void finalize_claim_result(ExtractionLlmResult& result) {
    if (!result.semantic_claim_contract) return;
    result.catalog_version = claim_predicate_catalog().version;
    result.accepted_by_predicate.clear();
    result.rejected_by_predicate.clear();
    const bool complete = result.claim_batch_size == 0 || claim_batch_integrity(result).complete;
    for (const auto& attempt : result.attempts) {
        // Only a protocol-successful attempt contributes candidates.  This
        // prevents a partially parsed failed response from being counted in
        // addition to the recovered terminal response.
        if (!attempt.parse.errors.empty()) continue;
        if (complete) for (const auto& statement : attempt.parse.statements) {
            ++result.accepted_by_predicate[statement.predicate];
        }
        for (const auto& rejection : attempt.semantic_rejections)
            ++result.rejected_by_predicate[rejection.predicate];
        for (const auto& [predicate, count] : attempt.admission_rejected_by_predicate)
            result.rejected_by_predicate[predicate] += count;
    }
    result.failure_category = claim_failure_category(result);
    result.failure_detail = extraction_failure_detail(result);
}

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

// Social-graph edge from a belief relation predicate (缺陷 B / PR4).
// reports_to / member_of are cognizer→cognizer social relations. When such a
// statement lands (subject already resolved to a cognizer id), reverse-look
// the object surface to an EXISTING cognizer and upsert a DIRECTED, TYPED edge
// (a_id=subject, b_id=object). Fiske: reports_to→Authority-heavy (superior/
// subordinate), member_of→Communal-heavy (belonging). Object miss → skip (never
// register — that is the over-registration bug we just fixed; only edge between
// cognizers that already exist). Best-effort: any hub error is swallowed so a
// bad edge never aborts a good statement write.
bool is_relation_predicate(std::string_view predicate) {
    return predicate == "reports_to" || predicate == "member_of";
}

std::unordered_map<cognizer::FiskeMode, double> fiske_for_predicate(
        std::string_view predicate) {
    // Dominant mode 0.7, remaining three 0.1 each (sums to 1.0).
    if (predicate == "reports_to") {
        return {{cognizer::FiskeMode::Authority, 0.7},
                {cognizer::FiskeMode::Communal, 0.1},
                {cognizer::FiskeMode::Equality, 0.1},
                {cognizer::FiskeMode::Market, 0.1}};
    }
    // member_of → Communal (belonging).
    return {{cognizer::FiskeMode::Communal, 0.7},
            {cognizer::FiskeMode::Authority, 0.1},
            {cognizer::FiskeMode::Equality, 0.1},
            {cognizer::FiskeMode::Market, 0.1}};
}

void maybe_build_relation_edge(
        cognizer::CognizerHub& hub,
        std::string_view tenant,
        std::string_view subject_kind,
        std::string_view subject_surface,
        std::string_view predicate,
        std::string_view object_surface) {
    if (subject_kind != "cognizer") { return; }   // only cognizer→cognizer edges
    if (!is_relation_predicate(predicate)) { return; }
    if (subject_surface.empty() || object_surface.empty()) { return; }
    // Both endpoints must resolve to EXISTING cognizer ids (UUID space). The
    // caller's stmt.subject_id is the canonical_name/surface (resolve_or_register
    // returns canonical_name, not the UUID), so reverse-look BOTH sides via
    // lookup_by_alias to keep a_id/b_id in the same id space as the nodes
    // (cognizers.id = UUID). Either miss → skip (no register — the object over-
    // registration guard applies to the subject too).
    const std::optional<std::string> a_id =
        hub.lookup_by_alias(tenant, subject_surface);
    if (!a_id.has_value() || a_id->empty()) { return; }
    const std::optional<std::string> b_id =
        hub.lookup_by_alias(tenant, object_surface);
    if (!b_id.has_value() || b_id->empty()) { return; }
    if (*a_id == *b_id) { return; }  // no self-loop edge
    try {
        cognizer::RelationEdgeInput edge;
        edge.tenant_id     = std::string(tenant);
        edge.a_id          = *a_id;
        edge.b_id          = *b_id;
        edge.fiske_weights = fiske_for_predicate(predicate);
        hub.upsert_relation(edge);
    } catch (const std::exception&) {
        // Best-effort: a bad edge must never abort the statement write.
    }
}

}  // namespace

ClaimBatchIntegrity claim_batch_integrity(const ExtractionLlmResult& result, const ValidationPolicy* policy) {
    auto fail = [](std::string detail) { return ClaimBatchIntegrity{false, std::move(detail), false}; };
    auto extraction_failure = [&](std::string detail, std::size_t position) {
        return ClaimBatchIntegrity{false, std::move(detail), position == result.attempts.size()};
    };
    try {
        const auto& snapshot = result.claim_batch_policy;
        snapshot.validate();
        if (result.claim_batch_size <= 0 || !result.semantic_claim_contract
            || snapshot.claim_batch_size != result.claim_batch_size)
            return fail("missing or inconsistent batch policy");
        if (policy && batch_policy_json(*policy) != batch_policy_json(snapshot))
            return fail("claim batch policy changed between extraction and persist");
        if (crypto::sha256_hex(result.source_payload) != result.source_payload_hash)
            return fail("batch source payload hash mismatch");
        nlohmann::json expected;
        try {
            expected = nlohmann::json::parse(claim_extraction_batch_plan(result.source_payload, snapshot));
        } catch (const std::exception& error) {
            // A source rejected before planning makes no provider request and
            // has no plan. Prove that failure again from the immutable source;
            // a missing plan for a valid source still fails below.
            if (!result.claim_batch_plan.empty() || !result.prompt_body.empty()
                || !result.prompt_input_hash.empty() || result.attempts.size() != 1)
                return fail("source validation failure state was changed");
            const auto& rec = result.attempts.front();
            if (rec.attempt != 1 || rec.batch_index != -1 || !rec.target_clause_ids.empty()
                || rec.terminal || !rec.parsed || !rec.parse.statements.empty()
                || rec.parse.errors.size() != 1 || rec.parse.errors.front().kind != "source_span_failure"
                || rec.parse.errors.front().detail != error.what() || rec.parse.errors.front().byte_offset != 0
                || !rec.parse.errors.front().field_path.empty()
                || !rec.prompt_body.empty() || !rec.prompt_input_hash.empty()
                || !rec.claim_candidates.empty() || rec.admission_called || !rec.admission_prompt.empty()
                || !rec.admission_prompt_hash.empty() || !rec.semantic_rejections.empty()
                || !rec.row_diagnostics.empty() || rec.semantic_rejected != 0
                || !rec.admission_rejected_by_predicate.empty())
                return fail("source validation failure diagnostic was changed");
            const auto no_provider_evidence = [](const LLMResponse& response) {
                return response.raw_xml.empty() && response.error.empty()
                    && response.prompt_tokens == 0 && response.completion_tokens == 0
                    && response.total_tokens == 0 && response.latency_ms == 0
                    && response.raw_completion.empty() && response.raw_http_response.empty()
                    && response.http_attempts.empty() && response.finish_reason.empty()
                    && !response.refusal && response.schema_sha256.empty()
                    && response.capability_evidence_id.empty()
                    && response.output_mode == OutputMode::Legacy
                    && response.output_contract == OutputContractKind::Legacy;
            };
            if (!rec.resp.ok || rec.admission_resp.ok || !no_provider_evidence(rec.resp)
                || !no_provider_evidence(rec.admission_resp))
                return fail("source validation failure contains provider evidence");
            return {false,error.what(),true};
        }
        if (nlohmann::json::parse(result.claim_batch_plan) != expected)
            return fail("batch plan differs from deterministic complete source partition");
        std::size_t position = 0;
        for (const auto& batch : expected.at("batches")) {
            const int index = batch.at("batch_index").get<int>();
            const auto targets = batch.at("target_clause_ids").get<std::vector<std::string>>();
            std::vector<ParseError> previous_errors;
            bool terminal = false;
            for (int local = 0; local <= snapshot.claim_protocol_retry_budget; ++local) {
                if (position >= result.attempts.size()) return fail("missing batch terminal");
                const auto& rec = result.attempts[position];
                if (rec.attempt != static_cast<int>(position)+1 || rec.batch_index != index
                    || rec.target_clause_ids != targets)
                    return fail("attempt numbering or batch target ownership differs from plan");
                const auto expected_prompt = claim_extraction_batch_prompt(result.source_payload, result.source_holder,
                    index, targets, snapshot, local == 0 ? nullptr : &previous_errors);
                if (position == 0 && (result.prompt_body != expected_prompt
                    || result.prompt_input_hash != crypto::sha256_hex(expected_prompt)))
                    return fail("batch root prompt differs from the first native batch");
                if (rec.prompt_body != expected_prompt || rec.prompt_input_hash != crypto::sha256_hex(expected_prompt))
                    return fail("batch extraction prompt differs from policy, source or retry state");
                ++position;
                if (!rec.resp.ok || truncated(rec.resp)) {
                    const std::string kind = truncated(rec.resp) ? "truncation_failure" : "upstream_failure";
                    if (rec.terminal || rec.admission_called || !rec.parse.statements.empty()
                        || rec.parse.errors.empty() || rec.parse.errors.front().kind != kind)
                        return fail("failed extraction state was changed");
                    return extraction_failure("batch extraction failed", position);
                }
                if (!rec.parsed) return fail("batch parse state was changed");
                auto replay = parse_claim_response(rec.resp.raw_xml, result.source_payload,
                    result.source_holder, snapshot.claim_allow_code_fence, &targets);
                if (!replay.errors.empty()) {
                    if (rec.terminal || rec.admission_called || !rec.parse.statements.empty()
                        || rec.parse.errors.empty() || rec.parse.errors.front().kind != replay.errors.front().kind)
                        return fail("failed batch protocol state was changed");
                    const auto& kind = replay.errors.front().kind;
                    if (!retryable_claim_protocol_error(kind, snapshot))
                        return extraction_failure("batch target or source failure", position);
                    if (local == snapshot.claim_protocol_retry_budget)
                        return extraction_failure("batch protocol retries exhausted", position);
                    previous_errors = replay.errors;
                    continue;
                }
                if (rec.claim_candidates != claim_candidates_json(replay)) return fail("batch candidates differ from original response");
                if (rec.admission_called != !replay.statements.empty()) return fail("batch admission missing or unexpected");
                if (rec.admission_called) {
                    const auto prompt = claim_admission_prompt(result.source_payload, rec.claim_candidates);
                    if (rec.admission_prompt != prompt || rec.admission_prompt_hash != crypto::sha256_hex(prompt))
                        return fail("batch admission prompt changed");
                    if (!rec.admission_resp.ok || truncated(rec.admission_resp)) {
                        const std::string kind = truncated(rec.admission_resp) ? "truncation_failure" : "upstream_failure";
                        if (rec.terminal || !rec.parse.statements.empty() || rec.parse.errors.empty()
                            || rec.parse.errors.front().kind != kind) return fail("failed admission state was changed");
                        return extraction_failure("batch admission failed", position);
                    }
                    apply_claim_admission(rec.admission_resp.raw_xml, replay, snapshot.claim_allow_code_fence);
                    if (!replay.errors.empty() && !rec.terminal && rec.parse.statements.empty()
                        && !rec.parse.errors.empty() && rec.parse.errors.front().kind == replay.errors.front().kind)
                        return extraction_failure("batch admission protocol failed", position);
                }
                if (!rec.terminal || !rec.parse.errors.empty() || !replay.errors.empty()
                    || rec.parse.statements != replay.statements)
                    return fail("batch terminal or retained candidates differ from admitted response");
                terminal = true;
                break;
            }
            if (!terminal) return fail("batch has no qualified terminal");
        }
        if (position != result.attempts.size()) return fail("duplicate or unplanned batch attempts");
        return {true,{},false};
    } catch (const std::exception& e) { return fail(e.what()); }
}

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
    if (policy_.semantic_claim_contract) {
        return claim_extraction_prompt(std::string(payload_bytes.begin(), payload_bytes.end()), holder_id);
    }
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
    policy_.validate();
    ExtractionLlmResult out;
    if (policy_.semantic_claim_contract) {
        out.semantic_claim_contract = true;
        out.claim_batch_size = policy_.claim_batch_size;
        out.claim_batch_policy = policy_;
        out.source_payload.assign(payload_bytes.begin(), payload_bytes.end());
        out.source_payload_hash = crypto::sha256_hex(out.source_payload);
        out.source_holder = std::string(holder_id);
        try {
            if (out.claim_batch_size > 0) {
                out.claim_batch_plan = claim_extraction_batch_plan(out.source_payload, policy_);
                const auto first = nlohmann::json::parse(out.claim_batch_plan).at("batches").at(0);
                out.prompt_body = claim_extraction_batch_prompt(out.source_payload, holder_id, 0,
                    first.at("target_clause_ids").get<std::vector<std::string>>(), policy_);
            } else out.prompt_body = build_prompt(holder_id, payload_bytes, existing_ref_map);
            out.prompt_input_hash = compute_prompt_input_hash(out.prompt_body);
        } catch (const std::exception& e) {
            ExtractionLlmAttempt rec;
            rec.attempt = 1;
            rec.resp.ok = true;
            rec.parsed = true;
            rec.parse.errors.push_back({"source_span_failure", e.what(), 0});
            out.attempts.push_back(std::move(rec));
            finalize_claim_result(out);
            return out;
        }
        const auto batches = out.claim_batch_size > 0
            ? nlohmann::json::parse(out.claim_batch_plan).at("batches")
            : nlohmann::json::array({{{"batch_index",-1},{"target_clause_ids",nlohmann::json::array()}}});
        for (const auto& batch : batches) {
        int protocol_retries = 0;
        std::vector<ParseError> previous_protocol_errors;
        for (;;) {
            ExtractionLlmAttempt rec;
            rec.attempt = static_cast<int>(out.attempts.size()) + 1;
            rec.batch_index = batch.at("batch_index").get<int>();
            rec.target_clause_ids = batch.at("target_clause_ids").get<std::vector<std::string>>();
            rec.prompt_body = out.claim_batch_size > 0
                ? claim_extraction_batch_prompt(out.source_payload, holder_id, rec.batch_index, rec.target_clause_ids, policy_,
                               protocol_retries == 0 ? nullptr : &previous_protocol_errors)
                : (protocol_retries == 0 ? out.prompt_body
                   : claim_extraction_retry_prompt(out.source_payload, holder_id, previous_protocol_errors));
            rec.prompt_input_hash = compute_prompt_input_hash(rec.prompt_body);
            try { rec.resp = adapter_.extract_with_contract(rec.prompt_body, rec.prompt_input_hash,
                {OutputContractKind::ClaimExtractionV2, policy_.claim_output_mode}); }
            catch (const std::exception& e) { rec.resp = {.raw_xml="", .ok=false, .error=e.what()}; }

            bool retryable_protocol_failure = false;
            if (out.claim_batch_size > 0 && truncated(rec.resp)) {
                rec.parse.errors.push_back({"truncation_failure", "extraction output truncated", 0});
            } else if (rec.resp.ok) {
                rec.parsed = true;
                auto parsed = parse_claim_response(rec.resp.raw_xml, out.source_payload, holder_id,
                                                   policy_.claim_allow_code_fence,
                                                   out.claim_batch_size > 0 ? &rec.target_clause_ids : nullptr);
                rec.semantic_rejections = std::move(parsed.semantic_rejections);
                rec.row_diagnostics = std::move(parsed.row_diagnostics);
                rec.semantic_rejected = static_cast<int>(rec.semantic_rejections.size());
                rec.parse = std::move(parsed);
                if (rec.parse.errors.empty()) {
                    rec.claim_candidates = claim_candidates_json(rec.parse);
                    if (!rec.parse.statements.empty()) {
                        rec.admission_prompt = claim_admission_prompt(out.source_payload, rec.claim_candidates);
                        rec.admission_prompt_hash = compute_prompt_input_hash(rec.admission_prompt);
                        rec.admission_called = true;
                        try { rec.admission_resp = adapter_.extract_with_contract(rec.admission_prompt,
                            rec.admission_prompt_hash,
                            {OutputContractKind::ClaimAdmissionV1, policy_.claim_output_mode}); }
                        catch (const std::exception& e) { rec.admission_resp = {.raw_xml="", .ok=false, .error=e.what()}; }
                        if (out.claim_batch_size > 0 && truncated(rec.admission_resp)) {
                            rec.parse.statements.clear();
                            rec.parse.errors.push_back({"truncation_failure", "admission output truncated", 0});
                        } else if (!rec.admission_resp.ok) {
                            rec.parse.statements.clear();
                            rec.parse.errors.push_back({"upstream_failure", rec.admission_resp.error, 0});
                        } else {
                            auto admitted = apply_claim_admission(rec.admission_resp.raw_xml, rec.parse,
                                                                  policy_.claim_allow_code_fence);
                            rec.semantic_rejected += admitted.semantic_rejected;
                            rec.admission_rejected_by_predicate = std::move(admitted.rejected_by_predicate);
                        }
                    }
                    rec.terminal = rec.parse.errors.empty();
                } else {
                    const auto& kind = rec.parse.errors.front().kind;
                    retryable_protocol_failure = retryable_claim_protocol_error(kind, policy_);
                }
            } else {
                rec.parse.errors.push_back({"upstream_failure", rec.resp.error, 0});
            }
            const bool should_retry = retryable_protocol_failure
                && protocol_retries < policy_.claim_protocol_retry_budget;
            if (retryable_protocol_failure) previous_protocol_errors = rec.parse.errors;
            out.attempts.push_back(std::move(rec));
            if (!should_retry) break;
            ++protocol_retries;
        }
        if (!out.attempts.back().terminal) break;
        }
        finalize_claim_result(out);
        return out;
    }
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
        rec.parse  = parse_extractor_json(rec.resp.raw_xml, existing_ref_map,
                                         policy_.preserve_text_objects);
        rec.parsed = true;
        if (!rec.parse.errors.empty()) {
            out.attempts.push_back(std::move(rec));
            continue;
        }
        rec.terminal = true;
        out.attempts.push_back(std::move(rec));
        break;
    }
    out.failure_detail = extraction_failure_detail(out);
    return out;
}

ExtractionRunResult Extractor::persist(
        std::string_view                  engram_ref_id,
        std::string_view                  holder_id,
        std::string_view                  holder_tenant_id,
        std::string_view                  interlocutor,
        const ExtractionLlmResult&        llm_result) {

    policy_.validate();
    ExtractionRunResult result;
    ExtractionLlmResult checked = llm_result;
    llm_result.persistence_error.clear();
    checked.persistence_error.clear();
    const bool batch_boundary = policy_.claim_batch_size > 0 || checked.claim_batch_size > 0;
    std::string batch_failure;

    // 单事务(移自原 run):FAILED 仍 COMMIT(attempt 行 + events 持久化),
    // 异常 ROLLBACK(TransactionGuard)。所有 DB 写集中在 LLM 之后。
    starling::persistence::TransactionGuard tx(conn_);

    if (policy_.semantic_claim_contract || checked.semantic_claim_contract) {
        std::string failure;
        try {
            if (!policy_.semantic_claim_contract || !checked.semantic_claim_contract
                || checked.source_holder != holder_id) {
                throw std::runtime_error("contract policy/holder changed between extraction and persist");
            }
            if (batch_boundary) {
                const auto integrity = claim_batch_integrity(checked, &policy_);
                if (!integrity.complete) {
                    if (integrity.extraction_failed) batch_failure = integrity.detail;
                    else throw std::runtime_error(integrity.detail);
                }
            }
            auto engram = evidence::EngramStore::get(engram_ref_id, holder_tenant_id, conn_);
            if (!engram || engram->erased_at_iso8601 || engram->created_at_iso8601.empty()) {
                throw std::runtime_error("source Engram missing, erased, tenant-invisible or has no observation time");
            }
            const std::string payload(engram->content_ciphertext.begin(), engram->content_ciphertext.end());
            if (payload != checked.source_payload || crypto::sha256_hex(payload) != checked.source_payload_hash
                || evidence::compute_engram_content_hash(engram->content_ciphertext, engram->declared_transformations) != engram->content_hash) {
                throw std::runtime_error("source payload or Engram content hash differs from extracted source");
            }
            for (auto& rec : checked.attempts) {
                // Finalize and validate every row before any statement is written.
                for (auto& stmt : rec.parse.statements) {
                    auto claim = nlohmann::json::parse(stmt.semantic_claim_json);
                    const auto start = claim.at("source_span").at("span_start").get<size_t>();
                    const auto end = claim.at("source_span").at("span_end").get<size_t>();
                    if (claim.at("source_span").at("source_hash") != checked.source_payload_hash || start >= end || end > payload.size()) {
                        throw std::runtime_error("candidate source proof no longer matches payload");
                    }
                    claim["source_span"]["engram_ref"] = std::string(engram_ref_id);
                    claim["source_time"] = engram->created_at_iso8601;
                    stmt.semantic_claim_json = claim.dump();
                    stmt.source_hash = checked.source_payload_hash;
                    stmt.holder_id = std::string(holder_id);
                    stmt.holder_tenant_id = std::string(holder_tenant_id);
                    stmt.observed_at = engram->created_at_iso8601;
                    if (!claim["event_time"].is_null()) stmt.event_time_start = claim["event_time"]["start"].get<std::string>();
                    auto validation = validate_extracted_statement(stmt, policy_);
                    if (!validation.ok()) throw std::runtime_error(validation.error_kind + ": " + validation.detail);
                }
            }
        } catch (const std::exception& e) { failure=e.what(); }
        if (!failure.empty()) {
            llm_result.persistence_error = failure;
            if (batch_boundary) {
                // Keep every original response and every incurred cost. Reject
                // the complete claim unit before entering the statement loop.
                batch_failure = failure;
            } else {
            ExtractionLlmAttempt failed;
            if (!checked.attempts.empty()) failed = checked.attempts.front();
            failed.attempt = 1; failed.resp.ok = true; failed.parsed = true; failed.terminal = false;
            failed.parse.statements.clear();
            failed.parse.errors = {{"persistence_failure", failure, 0}};
            checked.attempts = {std::move(failed)};
            }
            result.rejected_fragments.push_back(failure);
        }
    }

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

    int persisted_attempt_index = 0;
    for (const auto& rec : checked.attempts) {
        ++persisted_attempt_index;
        const int attempt = batch_failure.empty() ? rec.attempt : persisted_attempt_index;
        const std::string attempt_suffix = "attempt=" + std::to_string(attempt);
        // cost 归属:每 attempt 只算一次,落到本轮写的第一行(移自原 run)。
        // One extract() call per iteration, but the success path records one
        // ledger row PER statement-span. Attribute this call's cost to exactly
        // the FIRST row written this iteration; take_cost() returns it once then
        // {} so SUM(total_tokens) over a run's rows equals the per-call cost
        // (no double-counting). The first record_attempt of any iteration always
        // writes a fresh (run,span,attempt) row — dups only hit on a span's 2nd
        // occurrence — so the cost always lands on a persisted row.
        bool attempt_cost_used = false;
        auto take_cost = [&]() -> AttemptCost {
            if (attempt_cost_used) {
                return {};
            }
            attempt_cost_used = true;
            return {rec.resp.prompt_tokens + rec.admission_resp.prompt_tokens,
                    rec.resp.completion_tokens + rec.admission_resp.completion_tokens,
                    rec.resp.total_tokens + rec.admission_resp.total_tokens,
                    rec.resp.latency_ms + rec.admission_resp.latency_ms};
        };
        if (!batch_failure.empty()) {
            ledger.record_attempt(run_id, chunk_span_key, attempt, ExtractionStatus::Failed,
                                  rec.resp.raw_xml, "batch_integrity_failure: " + batch_failure, take_cost());
            emit_extraction_event(conn_, "extraction.failed", holder_tenant_id, run_id,
                                  chunk_span_key, run_started_event_id, attempt_suffix);
            continue;
        }
        if (!rec.resp.ok) {
            ledger.record_attempt(run_id, chunk_span_key, attempt,
                                  ExtractionStatus::Failed,
                                  /*raw_output=*/{},
                                  rec.resp.error,
                                  take_cost());
            emit_extraction_event(conn_, "extraction.failed",
                                  holder_tenant_id, run_id, chunk_span_key,
                                  run_started_event_id, attempt_suffix);
            if (!policy_.semantic_claim_contract && attempt < kMaxRetries) {
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
            if (!policy_.semantic_claim_contract && attempt < kMaxRetries) {
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
            if (!policy_.semantic_claim_contract && cog_hub && stmt.subject_kind == "cognizer" && !stmt.subject_id.empty()) {
                // cognizer_kind 已由 json_parser 校验:要么在值域内,要么空。
                // self 特判(eng-review D6′):subject 指向 agent 自己(「我」/「me」)
                // 不新建认知体,而是解析到本次 run 的 holder_id —— 既表征 self 是
                // 一等认知主体,又堵死「我/me/myself」碎片化成一堆孤立认知体。
                if (stmt.llm_cognizer_kind == "self") {
                    stmt.subject_id = std::string(holder_id);
                } else {
                    // 空 → 默认 Human;合法非空串 → from_string(值域外已被 parser 置空,
                    // 故不会抛)。
                    const cognizer::CognizerKind resolved_kind =
                        stmt.llm_cognizer_kind.empty()
                        ? cognizer::CognizerKind::Human
                        : cognizer::cognizer_kind_from_string(stmt.llm_cognizer_kind);
                    stmt.subject_id = starling::cognizer::resolve_or_register_cognizer(
                        *cog_hub, holder_tenant_id, stmt.subject_id, resolved_kind);
                }
            }
            // Holder attribution. Default (and historical) behaviour: the agent
            // (the run arg) holds every extracted attitude. OPT-IN
            // (ValidationPolicy.attribute_first_order_mental_to_holder, default
            // OFF): a FIRST-ORDER DESIRE statement is instead attributed to its
            // cognizer-resolved subject (the desirer), so a narrated 3rd-person
            // desire ("Xiao Hong wants X") lands under holder_id="Xiao Hong".
            // Validation showed the LLM's `holder` field is always the narrator
            // (fragmented narrator/叙述者/Narrator); `subject` is reliably the
            // desirer for the desire family. BELIEVES/KNOWS are excluded — their
            // subject is the topic, not the bearer.
            // Gated to nesting_depth==0 + desire modality/predicate + non-empty
            // non-agent subject; anything else falls back to the agent — additive.
            if (!policy_.semantic_claim_contract && policy_.attribute_first_order_mental_to_holder
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

            std::string identity_hash = stmt.canonical_object_hash;
            if (policy_.semantic_claim_contract) {
                auto evidence = nlohmann::json::parse(stmt.semantic_claim_json);
                auto& markers = evidence.at("scope_markers");
                std::sort(markers.begin(), markers.end());
                // A different actor, relation polarity or source clause is a
                // different claim even when its predicate and object match.
                const nlohmann::json identity = {
                    {"version", 1}, {"tenant", holder_tenant_id},
                    {"holder", stmt.holder_id},
                    {"perspective", schema::to_string(stmt.holder_perspective)},
                    {"subject_kind", stmt.subject_kind}, {"subject", stmt.subject_id},
                    {"predicate", stmt.predicate}, {"object_kind", stmt.object_kind},
                    {"object", stmt.object_value}, {"modality", schema::to_string(stmt.modality)},
                    {"polarity", schema::to_string(stmt.polarity)}, {"evidence", evidence}};
                identity_hash = "claim-v1:" + crypto::sha256_hex(identity.dump());
            }
            const std::string span_key = compute_extraction_span_key(
                engram_ref_id, chunk_index, stmt.predicate, identity_hash);
            // Cross-run idempotency: if a prior run already succeeded for this
            // span_key, emit noop. Intra-run duplicates (same span_key written
            // earlier in this loop) are handled by StatementWriter as
            // ChunkDuplicate — don't noop them here or we'd hit a UNIQUE
            // constraint on the attempt row.
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

            const auto outcome = [&]() {
                try { return writer.write(stmt, engram_ref_id, span_key, run_started_event_id); }
                catch (const std::exception& e) {
                    if (policy_.semantic_claim_contract) llm_result.persistence_error = e.what();
                    throw;
                }
            }();
            if (std::holds_alternative<StatementWriteAccepted>(outcome)) {
                result.accepted_statement_ids.push_back(
                    std::get<StatementWriteAccepted>(outcome).stmt_id);
                written_span_keys.insert(span_key);
                ledger.record_attempt(run_id, span_key, attempt,
                                      ExtractionStatus::Success,
                                      /*raw_output=*/{},
                                      /*error=*/{},
                                      take_cost());
                // 缺陷 B(社会图边):statement 落库成功后,若这是一条认知体间的
                // 关系谓词(reports_to/member_of)且 object 能反查到【已存在】的
                // 认知体,建一条有向带类型的社会图边(subject→object)。object 只
                // 反查不注册(与 PR2 归档同源的安全侧:错建认知体是病,漏建边无害)。
                // 只对真正新写入的语句建边(此分支),去重/被拒的不建。
                if (cog_hub) {
                    maybe_build_relation_edge(*cog_hub, holder_tenant_id,
                                            stmt.subject_kind, stmt.subject_id,
                                            stmt.predicate, stmt.object_value);
                }
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
        if (!batch_boundary) break;
    }

    if (any_accepted) {
        result.status = result_partial
            ? ExtractionRunResult::Status::PARTIAL_SUCCESS
            : ExtractionRunResult::Status::SUCCESS;
        ledger.finish_run(run_id, result_partial
            ? PipelineStatus::PartialSuccess : PipelineStatus::Finished);
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
