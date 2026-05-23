#pragma once

#include "starling/extractor/llm_adapter.hpp"

#include <string>
#include <unordered_map>

namespace starling::extractor {

// Deterministic LLMAdapter for tests. Maps prompt_input_hash → canned
// LLMResponse. Unknown hashes return ok=false with error=
// "fake_adapter_no_response_for_hash" so extractor retry policy is
// exercised by tests without needing a real LLM.
//
// FakeLLMAdapter ships in starling_core (not the testing helper target)
// because pybind11 binds it for Python integration tests.
class FakeLLMAdapter : public LLMAdapter {
public:
    void set_response(std::string prompt_input_hash, LLMResponse response);
    LLMResponse extract(std::string_view prompt,
                        std::string_view prompt_input_hash) override;

private:
    std::unordered_map<std::string, LLMResponse> responses_;
};

}  // namespace starling::extractor
