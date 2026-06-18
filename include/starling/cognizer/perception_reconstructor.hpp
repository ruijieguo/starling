#pragma once
#include "starling/persistence/connection.hpp"
#include <string_view>
namespace starling::cognizer {
// Post-pass: recompute per-cognizer perception for a tenant from ALL its OCCURRED
// events. Idempotent (upserts). Runs in its own transaction after the episodic pass.
class PerceptionReconstructor {
public:
    explicit PerceptionReconstructor(persistence::Connection& conn);
    void reconstruct(std::string_view tenant);
private:
    persistence::Connection& conn_;
};
}  // namespace starling::cognizer
