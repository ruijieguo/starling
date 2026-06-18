#pragma once
#include "starling/persistence/connection.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include <string_view>
namespace starling::cognizer {
// Post-pass: recompute per-cognizer perception for a tenant from ALL its OCCURRED
// events. Idempotent (upserts). Runs in its own transaction after the episodic pass.
//
// Phase 5 (Task 5.1): an OPTIONAL SqliteAdapter enables does_X_know event-awareness.
// When constructed with an adapter, the reconstructor ALSO records each physical
// witness's perceived event engram into KnowledgeFrontier (presence_log) so the
// tri-valued does_X_know() reflects who witnessed an event. The engram id is read
// from the OCCURRED statement's evidence_json (key "engram_ref" or "engram_id"; the
// episodic write path populates it). The connection-only ctor preserves the
// phase-1..4 behavior (perception_state only) for callers without an adapter.
class PerceptionReconstructor {
public:
    explicit PerceptionReconstructor(persistence::Connection& conn);
    // Connection + adapter: additionally records witness presence into the
    // KnowledgeFrontier (Task 5.1). adapter and conn MUST back the same database.
    PerceptionReconstructor(persistence::Connection& conn,
                            persistence::SqliteAdapter& adapter);
    void reconstruct(std::string_view tenant);
private:
    persistence::Connection& conn_;
    persistence::SqliteAdapter* adapter_ = nullptr;  // null → perception_state only
};
}  // namespace starling::cognizer
