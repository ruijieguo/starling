#pragma once

#include "starling/extractor/llm_adapter.hpp"

#include <optional>
#include <string>
#include <unordered_map>

namespace starling::extractor {

// Deterministic LLMAdapter for tests. Maps prompt_input_hash → canned
// LLMResponse. Unknown hashes fall back to set_default_response() if one
// has been configured; otherwise return ok=false with error=
// "fake_adapter_no_response_for_hash" so extractor retry policy is
// exercised by tests without needing a real LLM.
//
// FakeLLMAdapter ships in starling_core (not the testing helper target)
// because pybind11 binds it for Python integration tests.
class FakeLLMAdapter : public LLMAdapter {
public:
    void set_response(std::string prompt_input_hash, LLMResponse response);
    // Sets a fallback returned for any hash not in the response map. Lets
    // orchestrator tests stub a canned LLM result without needing to mirror
    // the C++ prompt-builder's exact byte string.
    void set_default_response(LLMResponse response);
    // 测试钩子:让 extract() 在返回前睡 delay_ms——模拟真模型时延,供
    // GIL 释放回归测试制造「线程阻塞在 C++ 内」的确定性窗口(零网络)。
    void set_delay_ms(int delay_ms) { delay_ms_ = delay_ms; }
    LLMResponse extract(std::string_view prompt,
                        std::string_view prompt_input_hash) override;

private:
    std::unordered_map<std::string, LLMResponse> responses_;
    std::optional<LLMResponse>                   default_response_;
    int                                          delay_ms_ = 0;
};

}  // namespace starling::extractor
