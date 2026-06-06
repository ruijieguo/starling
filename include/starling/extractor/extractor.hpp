#pragma once

#include "starling/extractor/existing_ref_map.hpp"
#include "starling/extractor/llm_adapter.hpp"
#include "starling/persistence/connection.hpp"

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

// Extractor orchestrates the pipeline: open PipelineRun -> for each chunk
// retry-loop(adapter -> parser -> validator -> writer) -> close PipelineRun.
// M0.4 ships single-chunk-per-Engram with max_retries=3. The class holds
// references to the Connection and the adapter; ownership is the caller's.
class Extractor {
public:
    Extractor(starling::persistence::Connection& conn, LLMAdapter& adapter,
              std::string prompt_template = "")
        : conn_(conn), adapter_(adapter),
          prompt_template_(std::move(prompt_template)) {}

    ExtractionRunResult run(
        std::string_view                        engram_ref_id,
        const std::vector<std::uint8_t>&        payload_bytes,
        std::string_view                        holder_id,
        std::string_view                        holder_tenant_id,
        const ExistingRefMap&                   existing_ref_map);

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
    std::string prompt_template_;
};

}  // namespace starling::extractor
