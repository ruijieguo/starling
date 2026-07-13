#pragma once

#include "starling/extractor/existing_ref_map.hpp"
#include "starling/extractor/json_parser.hpp"
#include "starling/extractor/llm_adapter.hpp"
#include "starling/extractor/statement_validator.hpp"
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace starling::extractor {

struct ExtractionRunResult {
    enum class Status { SUCCESS, PARTIAL_SUCCESS, FAILED };
    Status                                  status;
    std::vector<std::string>                accepted_statement_ids;
    std::vector<std::string>                rejected_fragments;   // serialized JSON
    std::string                             run_id;               // pipeline_run.id
};

// extract_llm 产出的逐 attempt 记录(LLM + parse 段);persist() 重放它们写
// ledger/attempt/statement 行。此处无任何 DB 状态——重试决策(!resp.ok 或
// parse 有错才重试、parse 成功即止)纯由 LLM 响应决定,故 attempt 序列可无 DB
// 完整确定,persist 忠实重放。
struct ExtractionLlmAttempt {
    int         attempt = 0;       // 1-based
    LLMResponse resp;              // 该 attempt 的原始 LLM 响应
    bool        parsed = false;    // resp.ok 且跑过 parser
    ParseResult parse;             // 仅 parsed==true 有效
    bool        terminal = false;  // parse 成功 → 该 attempt 结束重试循环
};

struct ExtractionLlmResult {
    std::string                       prompt_body;
    std::string                       prompt_input_hash;
    std::vector<ExtractionLlmAttempt> attempts;
};

// Extractor orchestrates the pipeline: open PipelineRun -> for each chunk
// retry-loop(adapter -> parser -> validator -> writer) -> close PipelineRun.
// M0.4 ships single-chunk-per-Engram with max_retries=3. The class holds
// references to the Connection and the adapter; ownership is the caller's.
class Extractor {
public:
    Extractor(starling::persistence::Connection& conn, LLMAdapter& adapter,
              std::string prompt_template = "", ValidationPolicy policy = {})
        : conn_(conn), adapter_(adapter),
          prompt_template_(std::move(prompt_template)), policy_(std::move(policy)) {}

    // Phase 2 (Task 2.2): an OPTIONAL SqliteAdapter enables cognizer-name
    // resolution. When present, each parsed statement's subject_id (a cognizer
    // surface) is resolved to its canonical first-seen name (via CognizerHub,
    // reusing the cognizers table) before validation + write, so name-surface
    // drift grounds to one entity. The resolver registers on a miss inside the
    // run's write transaction; it is best-effort (a failure returns the raw
    // surface). The connection-only ctor preserves the pre-phase-2 behavior.
    // store_adapter and conn MUST back the same database.
    Extractor(starling::persistence::Connection& conn, LLMAdapter& adapter,
              starling::persistence::SqliteAdapter& store_adapter,
              std::string prompt_template = "", ValidationPolicy policy = {})
        : conn_(conn), adapter_(adapter), store_adapter_(&store_adapter),
          prompt_template_(std::move(prompt_template)), policy_(std::move(policy)) {}

    ExtractionRunResult run(
        std::string_view                        engram_ref_id,
        const std::vector<std::uint8_t>&        payload_bytes,
        std::string_view                        holder_id,
        std::string_view                        holder_tenant_id,
        const ExistingRefMap&                   existing_ref_map,
        std::string_view                        interlocutor = "");

    // 方案2 拆分:run() = extract_llm() → persist()(单一语义源内联)。
    // extract_llm:跑重试循环只做 adapter_.extract + parse_extractor_json,零 DB、
    // 无 TransactionGuard——LLM 只吃 payload + existing_ref_map,不需 engram 在库。
    ExtractionLlmResult extract_llm(
        const std::vector<std::uint8_t>&        payload_bytes,
        std::string_view                        holder_id,
        const ExistingRefMap&                   existing_ref_map);

    // persist:开 TransactionGuard,重放 llm_result.attempts 写 ledger/attempt/
    // events + terminal attempt 的 statements。FAILED 仍 COMMIT attempt 行。
    ExtractionRunResult persist(
        std::string_view                        engram_ref_id,
        std::string_view                        holder_id,
        std::string_view                        holder_tenant_id,
        std::string_view                        interlocutor,
        const ExtractionLlmResult&              llm_result);

    // Public so tests can use the same hash as the adapter's keying.
    static std::string compute_prompt_input_hash(std::string_view prompt_body);

    // Builds the LLM prompt body. When prompt_template_ is non-empty, the chunk
    // payload is decoded as UTF-8 text and substituted into the "{convo}"
    // placeholder (appended if the placeholder is absent). When empty (the
    // FakeLLM / unit-test path), reproduces the deterministic build_prompt_body
    // string so prompt-hash keyed test adapters keep matching.
    std::string build_prompt(
        std::string_view holder_id,
        const std::vector<std::uint8_t>& payload_bytes,
        const ExistingRefMap& existing_ref_map) const;

    // Public for test seeding only — production callers use run() which
    // builds the same body internally. Tests need the same byte string the
    // orchestrator will hash so set_response can key on the matching hash.
    static std::string build_prompt_body_for_tests(
        std::string_view holder_id,
        const std::vector<std::uint8_t>& payload_bytes,
        const std::map<std::string, std::string>& existing_ref_map);

    // Visible constants.
    static constexpr int kMaxRetries        = 3;
    static constexpr const char* kPromptVersion    = "v1.0";
    static constexpr const char* kExtractorVersion = "m0_4_v1";

private:
    starling::persistence::Connection& conn_;
    LLMAdapter& adapter_;
    starling::persistence::SqliteAdapter* store_adapter_ = nullptr;  // null → raw subject_id (no name resolution)
    std::string prompt_template_;
    ValidationPolicy policy_;
};

}  // namespace starling::extractor
