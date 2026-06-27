#pragma once
#include "starling/persistence/connection.hpp"
#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace starling::vector { class VectorIndex; }  // injected k-NN seam (semantic pass)

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
    std::string subject_kind;                // #38-C v2 entity-gist: the SPECIFIC entity this
    std::string subject_id;                  // consensus is about (a cognizer). BOTH EMPTY for
                                             // a people-norm cluster → the gist gets the generic
                                             // __people__ subject; SET → the gist keeps this
                                             // entity (and the entity goes into the span key).
    std::vector<std::string> member_ids;     // qualifying member statement ids, sorted
    std::vector<std::string> holder_ids;     // distinct holders, sorted; size() >= K
    std::vector<std::string> member_objects; // #38-C v2: distinct member object strings,
                                             // sorted. NON-EMPTY only for SEMANTIC clusters
                                             // (members carry VARIED objects); empty for an
                                             // exact cluster (members share object_value).
                                             // Drives the member-aware judge + per-member
                                             // entailment that guard against false-merge.
};

// A detected cluster tagged with its tenant, ready for the Phase-2 write path.
// (GistCluster itself is per-tenant by construction; this pairs it with the
// tenant so the offline writer can route each gist to the right tenant.)
struct GistProposal {
    std::string tenant_id;
    GistCluster cluster;
};

// Gist tuning knobs. A named struct (not adjacent scalars) so the values cannot
// be transposed at a call site. K/T gate CLUSTERING (find_norm_gist_clusters);
// min_confidence gates the LLM JUDGMENT downstream (gist_writer gate_candidate) —
// clustering ignores it. Defaults are the v1 production values; the dashboard
// "consolidation" config can override them (threshold config surface, v2).
struct GistThresholds {
    int min_distinct_holders = 3;   // K — distinct holders a norm must span
    int min_replay_count = 1;       // T — per-member replay_count floor (>=1 = the
                                    // belief was consolidated at least once = settled;
                                    // see kGistThresholds in replay_scheduler.cpp for
                                    // why T=1, not the eng-review's unreachable T=2)
    double min_confidence = 0.6;    // confidence floor for promoting a judged gist
                                    // (Phase-4 gate); below → gated, not written
    double similarity_threshold = 0.0;  // #38-C v2 semantic clustering: cosine floor for
                                        // k-NN NORM grouping. 0 = OFF (exact-match only —
                                        // the default; no behavior change on upgrade). Set
                                        // >0 (recommended 0.85) to enable cross-predicate
                                        // paraphrase clustering. Higher = stricter (fewer
                                        // false merges).
    bool entity_gist_enabled = false;   // #38-C v2 entity-gist: when true, a second OFFLINE
                                        // pass clusters by (subject, predicate, object) over
                                        // cognizer subjects → a consensus gist ABOUT a specific
                                        // entity ("(common_ground) believes (Bob, owns, auth)").
                                        // false = OFF (default; no behavior change).
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
// by_subject=false (default) → people-norm: cluster by (predicate, hash), subject
// dropped, gist subject = generic __people__. by_subject=true → #38-C v2 entity-gist:
// cluster by (subject, predicate, hash) over COGNIZER subjects, the cluster carries the
// specific subject (→ a consensus gist ABOUT that entity, subject in the span key).
[[nodiscard]] std::vector<GistCluster> find_norm_gist_clusters(
    persistence::Connection& conn,
    std::string_view tenant_id,
    const std::vector<std::string>& seed_stmt_ids,
    const GistThresholds& thresholds,
    bool by_subject = false);

// #38-C v2 semantic clustering (k-NN seed expansion). Sibling to the exact pass: for
// each seed not already in `claimed` (the exact-match members), query the vector index
// for its cosine neighbors; neighbors at/above thresholds.similarity_threshold that are
// settled & norm-eligible (the SAME state filter as exact, replay_count >= T) join the
// candidate. It becomes a cluster iff seed+neighbors span >= K distinct holders. The
// representative (predicate/object/hash) is the lexicographically smallest member id;
// members carry VARIED (predicate,object) by design, so downstream gating must use
// per-member entailment to guard against false-merge. Returns empty (disabled) when
// similarity_threshold <= 0. Idempotent: skips a representative key already abstracted,
// AND a candidate whose representative is a near neighbor of an existing gist.
[[nodiscard]] std::vector<GistCluster> find_semantic_gist_clusters(
    persistence::Connection& conn,
    vector::VectorIndex& index,
    std::string_view tenant_id,
    const std::vector<std::string>& seed_stmt_ids,
    const GistThresholds& thresholds,
    const std::set<std::string>& claimed);

}  // namespace starling::replay
