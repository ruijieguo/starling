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
    Extractor(starling::persistence::Connection& conn, LLMAdapter& adapter)
        : conn_(conn), adapter_(adapter) {}

    ExtractionRunResult run(
        std::string_view                        engram_ref_id,
        const std::vector<std::uint8_t>&        payload_bytes,
        std::string_view                        holder_id,
        std::string_view                        holder_tenant_id,
        const ExistingRefMap&                   existing_ref_map);

    // Public so tests can use the same hash as the adapter's keying.
    static std::string compute_prompt_input_hash(std::string_view prompt_body);

    // Visible constants.
    static constexpr int kMaxRetries        = 3;
    static constexpr const char* kPromptVersion    = "v1.0";
    static constexpr const char* kExtractorVersion = "m0_4_v1";

private:
    starling::persistence::Connection& conn_;
    LLMAdapter& adapter_;
};

}  // namespace starling::extractor
