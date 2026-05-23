#include "starling/extractor/fake_llm_adapter.hpp"

#include <utility>

namespace starling::extractor {

void FakeLLMAdapter::set_response(std::string prompt_input_hash,
                                  LLMResponse response) {
    responses_[std::move(prompt_input_hash)] = std::move(response);
}

LLMResponse FakeLLMAdapter::extract(std::string_view /*prompt*/,
                                    std::string_view prompt_input_hash) {
    const auto it = responses_.find(std::string(prompt_input_hash));
    if (it == responses_.end()) {
        return LLMResponse{
            .raw_xml = "",
            .ok = false,
            .error = "fake_adapter_no_response_for_hash",
        };
    }
    return it->second;
}

}  // namespace starling::extractor
