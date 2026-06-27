#pragma once
#include "starling/replay/gist_clustering.hpp"
#include <string>
#include <string_view>

namespace starling::replay {

// The consolidation LLM's judgment of a candidate NORM (#38-C Phase 3), parsed
// from the LLM's JSON reply to the NORM-gist prompt.
struct GistJudgment {
    bool        ok = false;        // false ⇒ LLM errored or reply unparseable → skip the gist
    double      confidence = 0.0;  // 0..1: how strongly this is a real generalizable norm
    std::string summary;           // one-sentence natural-language rendering of the norm
};

// The NORM-gist prompt is CORE consolidation logic, so it lives in the C++
// kernel as single-source — NOT as binding/Python config. Switching binding
// languages must not require rewriting it (the architecture's boundary rule).
// Python only injects the concrete LLMAdapter (the network I/O seam).
//
// build_norm_gist_prompt fills the prompt template with a cluster's candidate
// norm; parse_gist_judgment reads the LLM's JSON reply ({confidence, summary})
// into a GistJudgment (ok=false on any malformed/errored reply).
[[nodiscard]] std::string build_norm_gist_prompt(const GistCluster& cluster);
[[nodiscard]] GistJudgment parse_gist_judgment(std::string_view llm_reply);

}  // namespace starling::replay
