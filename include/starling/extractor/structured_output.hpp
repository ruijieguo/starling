#pragma once
#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace starling::extractor {
enum class OutputContractKind { Legacy, ClaimExtractionV2, ClaimAdmissionV1, SourceSelectionV1 };
enum class OutputMode { Legacy, JsonObject, JsonSchemaStrict };
enum class CapabilityState { Unknown, ObservedConformant, Unsupported, Nonconformant };
struct StructuredOutputRequest {
    OutputContractKind contract = OutputContractKind::Legacy;
    OutputMode mode = OutputMode::Legacy;
};
struct CapabilityProbeObservation {
    std::string prompt;
    std::string response_json;
    bool conformant = false;
    std::string validation_error;
};
struct CapabilityEvidence {
    CapabilityState state = CapabilityState::Unknown;
    StructuredOutputRequest request;
    std::string probe_version = "structured-capability-v1";
    std::string schema_sha256;
    std::string endpoint;
    std::string model;
    std::string observed_at;
    std::string evidence_id;
    std::string error;
    std::size_t request_count = 0;
    std::vector<CapabilityProbeObservation> probes;
};
std::string_view to_string(OutputContractKind value);
std::string_view to_string(OutputMode value);
std::string_view to_string(CapabilityState value);
std::string structured_output_schema(OutputContractKind contract);
std::string structured_output_schema_sha256(OutputContractKind contract);
std::string structured_output_validation_error(std::string_view raw, OutputContractKind contract);
std::string capability_evidence_json(const CapabilityEvidence& evidence);
struct LLMResponse;
std::string llm_response_evidence_json(const LLMResponse& response);
CapabilityState structured_probe_state(const LLMResponse& response, const StructuredOutputRequest& request,
                                      std::string& validation_error);
std::string validate_capability_evidence_json(std::string_view raw);
} // namespace starling::extractor
