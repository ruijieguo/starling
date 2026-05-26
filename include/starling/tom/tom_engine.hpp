#pragma once

#include "starling/cognizer/cognizer_hub.hpp"
#include "starling/cognizer/knowledge_frontier.hpp"
#include "starling/persistence/sqlite_adapter.hpp"
#include "starling/retrieval/statement_row.hpp"
#include "starling/tom/common_ground.hpp"

#include <string>
#include <string_view>
#include <vector>

// Forward declaration: avoids pulling all of retrieval into callers that only
// need the engine header.
namespace starling::retrieval {
struct StatementRow;
}  // namespace starling::retrieval

namespace starling::tom {

// Context is the Theory-of-Mind snapshot for a target cognizer at a given
// point in time. It bundles:
//   visible_engram_ids  — engrams the target was present for (via
//                         KnowledgeFrontier::visible_engrams_at)
//   target_beliefs      — statements the target holds (consolidated|archived,
//                         not rejected/pending) that were valid as of as_of
//   cg                  — common-ground entries shared with system_self
//                         (always empty in P2.a; P2.b adds Grounding Acts)
struct Context {
    std::vector<std::string>             visible_engram_ids;
    std::vector<retrieval::StatementRow> target_beliefs;
    std::vector<CommonGroundEntry>       cg;
};

// ToMEngine assembles a Context for a target cognizer.
//
// Constructor takes references to existing infrastructure objects — the
// caller (e.g. a pybind binding or service layer) owns the lifetime.
//
// CognizerNotFound (from starling/cognizer/cognizer.hpp) is re-exported via
// the cognizer_hub.hpp include — do NOT redefine it here.
class ToMEngine {
public:
    ToMEngine(persistence::SqliteAdapter&  adapter,
              cognizer::CognizerHub&       hub,
              cognizer::KnowledgeFrontier& frontier);

    // Build a perspective snapshot for target_cognizer_id.
    //
    // Spec §7.2:
    //   1. Query visible_engrams_at for the target.
    //   2. SELECT consolidated|archived statements where holder_id = target,
    //      filtered by as_of_iso8601 valid_from/valid_to bounds.
    //   3. Query common_ground (returns [] in P2.a).
    //
    // self_id is hardcoded to "system_self" in P2.a (spec §7.2 note:
    // P2.b reads from RuntimeConfig).
    Context perspective_take(
        std::string_view target_cognizer_id,
        std::string_view tenant_id,
        std::string_view as_of_iso8601) const;

private:
    persistence::SqliteAdapter&  adapter_;
    [[maybe_unused]] cognizer::CognizerHub& hub_;  // reserved for P2.b relation lookups
    cognizer::KnowledgeFrontier& frontier_;
};

}  // namespace starling::tom
