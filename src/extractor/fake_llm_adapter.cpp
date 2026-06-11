#include "starling/extractor/fake_llm_adapter.hpp"

#include <chrono>
#include <thread>
#include <utility>

namespace starling::extractor {

void FakeLLMAdapter::set_response(std::string prompt_input_hash,
                                  LLMResponse response) {
    responses_[std::move(prompt_input_hash)] = std::move(response);
}

void FakeLLMAdapter::set_default_response(LLMResponse response) {
    default_response_ = std::move(response);
}

LLMResponse FakeLLMAdapter::extract(std::string_view /*prompt*/,
                                    std::string_view prompt_input_hash) {
    if (delay_ms_ > 0) {
        // GIL 释放回归测试的确定性阻塞窗口(模拟真模型时延)。
        std::this_thread::sleep_for(std::chrono::milliseconds(delay_ms_));
    }
    const auto it = responses_.find(std::string(prompt_input_hash));
    if (it != responses_.end()) {
        return it->second;
    }
    if (default_response_.has_value()) {
        return *default_response_;
    }
    return LLMResponse{
        .raw_xml = "",
        .ok = false,
        .error = "fake_adapter_no_response_for_hash",
    };
}

}  // namespace starling::extractor
