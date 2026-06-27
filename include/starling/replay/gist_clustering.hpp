#pragma once
#include "starling/persistence/connection.hpp"
#include <string>
#include <string_view>
#include <vector>

namespace starling::replay {

// A NORM-gist candidate cluster (#38-C Phase 1): >= K distinct holders that all
// assert the same (predicate, canonical_object_hash) — "what people generally
// believe/do". Members each have replay_count >= T and a live consolidation
// state. This is the deterministic, embedding-free v1 cluster; later phases turn
// each cluster into a gated, pipeline-written gist Statement. READ-ONLY — this
// produces candidates and writes nothing.
struct GistCluster {
    std::string predicate;
    std::string canonical_object_hash;
    std::string object_kind;                 // representative (members share the hash)
    std::string object_value;                // representative canonical object string
    std::vector<std::string> member_ids;     // qualifying member statement ids, sorted
    std::vector<std::string> holder_ids;     // distinct holders, sorted; size() >= K
};

// A detected cluster tagged with its tenant, ready for the Phase-2 write path.
// (GistCluster itself is per-tenant by construction; this pairs it with the
// tenant so the offline writer can route each gist to the right tenant.)
struct GistProposal {
    std::string tenant_id;
    GistCluster cluster;
};

// Clustering thresholds. A named struct (not two adjacent int params) so the
// K and T cannot be transposed at a call site. Defaults are the v1 locked
// values; tune later (deferred to v2).
struct GistThresholds {
    int min_distinct_holders = 3;   // K — distinct holders a norm must span
    int min_replay_count = 2;       // T — per-member replay_count floor
};

// Deterministic NORM-gist clustering. `seed_stmt_ids` is the replay batch: it
// supplies the "hot" (predicate, canonical_object_hash) keys currently being
// replayed. For each distinct seed key, all tenant statements matching that key
// with replay_count >= thresholds.min_replay_count and a live state
// (consolidation_state IN ('volatile','consolidated'), review_status NOT IN
// ('rejected','pending_review')) are gathered; the key becomes a cluster iff it
// spans >= thresholds.min_distinct_holders distinct holders. A key that already
// has a 'consolidation_abstract' gist (same predicate + hash, tenant) is skipped
// so re-replay never re-abstracts (idempotency). The result is sorted by
// (predicate, canonical_object_hash) for deterministic downstream gist text.
[[nodiscard]] std::vector<GistCluster> find_norm_gist_clusters(
    persistence::Connection& conn,
    std::string_view tenant_id,
    const std::vector<std::string>& seed_stmt_ids,
    const GistThresholds& thresholds);

}  // namespace starling::replay
