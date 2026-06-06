#pragma once

#include <string>
#include <string_view>

namespace starling::extractor {

struct LLMResponse {
    std::string raw_xml;   // raw LLM body (now a JSON array; name kept for blast-radius); empty when ok=false
    bool        ok = false;
    std::string error;     // semantic error code on ok=false; empty otherwise
};

// Pluggable seam: anything that can turn a prompt + a stable input hash into
// a raw LLM response (a JSON array, or a typed transient error). M0.4 ships FakeLLMAdapter
// only; P2 lands real OpenAI / Anthropic / local-compatible adapters. The
// prompt_input_hash is opaque to the adapter — extractor.cpp computes it as
// sha256(prompt_template_version + prompt_body + existing_ref_map_json) so
// the adapter can use it as a deterministic cache key without parsing the
// prompt.
class LLMAdapter {
public:
    virtual ~LLMAdapter() = default;
    virtual LLMResponse extract(
        std::string_view prompt,
        std::string_view prompt_input_hash) = 0;
};

}  // namespace starling::extractor
