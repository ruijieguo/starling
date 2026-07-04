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

// #38-C Phase 4 (gating): the INDEPENDENT entailment verification — a second LLM
// pass that checks the generated summary is faithfully entailed by the cluster
// (no unwarranted additions / over-generalization), catching a confabulated
// summary the generation pass produced. Also CORE single-source C++ (not Python).
struct EntailmentVerdict {
    bool ok = false;        // false ⇒ LLM errored or reply unparseable
    bool entailed = false;  // is the summary entailed by the cluster's evidence?
};
// `object` is the single member phrasing checked this call. EXACT / entity clusters
// call this once with the shared object_value. (Semantic clusters — varied objects —
// use build_semantic_entailment_prompt instead; see gate_candidate.)
[[nodiscard]] std::string build_entailment_prompt(const GistCluster& cluster,
                                                  std::string_view object,
                                                  std::string_view summary);

// #38-C v2 semantic-cluster entailment (set-level). A semantic cluster groups the SAME
// predicate over VARIED objects; a summary generalizing across them is never entailed by
// any single object, so per-object verification structurally rejects every semantic gist.
// This lists ALL member objects and asks for a FAITHFUL GENERALIZATION — coverage (every
// object is an instance of the summary) AND tightness (no scope broader than the set).
[[nodiscard]] std::string build_semantic_entailment_prompt(const GistCluster& cluster,
                                                           std::string_view summary);
[[nodiscard]] EntailmentVerdict parse_entailment_verdict(std::string_view llm_reply);

}  // namespace starling::replay
