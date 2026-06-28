#include "starling/replay/gist_clustering.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/vector/vector_index.hpp"   // VectorIndex / SearchScope (semantic k-NN)
#include "starling/vector/vector_math.hpp"    // from_blob (index_vector → floats)

#include <algorithm>
#include <iterator>
#include <optional>
#include <set>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

namespace starling::replay {
namespace {
using starling::persistence::detail::bind_sv;
using starling::persistence::detail::make_sqlite_error;
using starling::persistence::StmtHandle;

// Read a TEXT column as std::string without a reinterpret_cast or explicit
// pointer arithmetic (both are flagged by cppcoreguidelines-* on the gate's
// changed lines). sqlite3_column_text returns const unsigned char*; the
// [first, last) iterator-range constructor builds the std::string (char is
// constructible from unsigned char), and std::next keeps the end iterator out
// of raw pointer arithmetic. A NULL column yields "".
std::string column_text(sqlite3_stmt* stmt, int idx) {
    const unsigned char* ptr = sqlite3_column_text(stmt, idx);
    if (ptr == nullptr) {
        return {};
    }
    std::string value(ptr, std::next(ptr, sqlite3_column_bytes(stmt, idx)));
    return value;
}

// A seed key: (subject_kind, subject_id, predicate, canonical_object_hash). subject_*
// are EMPTY for a people-norm key (subject dropped → aggregate across subjects) and SET
// for an entity-gist key (consensus ABOUT one cognizer). A tuple so the set dedups+orders.
using SeedKey = std::tuple<std::string, std::string, std::string, std::string>;

// Collect the distinct seed keys carried by the batch, scoped to one tenant. Deduped via
// a set so a batch with many rows sharing a key probes once; a seed id absent from this
// tenant contributes nothing. by_subject=false → people-norm keys (subject dropped, the
// v1 behavior); by_subject=true → entity keys, COGNIZER subjects only (#38-C v2: a
// consensus is formed only ABOUT a person/agent, not an arbitrary object).
std::set<SeedKey> collect_seed_keys(
    sqlite3* db_handle,
    std::string_view tenant_id,
    const std::vector<std::string>& seed_stmt_ids,
    bool by_subject)
{
    std::set<SeedKey> seed_keys;
    sqlite3_stmt* sel = nullptr;
    const char* sql =
        "SELECT subject_kind, subject_id, predicate, canonical_object_hash FROM statements "
        "WHERE tenant_id=? AND id=?";
    if (sqlite3_prepare_v2(db_handle, sql, -1, &sel, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db_handle, "collect_seed_keys: prepare");
    }
    StmtHandle hsel(sel);
    for (const auto& seed_id : seed_stmt_ids) {
        sqlite3_reset(hsel.get());
        sqlite3_clear_bindings(hsel.get());
        bind_sv(hsel.get(), 1, tenant_id);
        bind_sv(hsel.get(), 2, seed_id);
        if (sqlite3_step(hsel.get()) != SQLITE_ROW) {
            continue;
        }
        std::string subject_kind = column_text(hsel.get(), 0);
        std::string subject_id = column_text(hsel.get(), 1);
        std::string predicate = column_text(hsel.get(), 2);
        std::string object_hash = column_text(hsel.get(), 3);
        if (!by_subject) {
            seed_keys.emplace("", "", std::move(predicate), std::move(object_hash));
        } else if (subject_kind == "cognizer") {
            seed_keys.emplace(std::move(subject_kind), std::move(subject_id),
                              std::move(predicate), std::move(object_hash));
        }
    }
    return seed_keys;
}

// Build one cluster for a seed key: idempotency probe, then gather settled members +
// distinct holders (same state filter for both norm modes). nullopt if the key is
// already abstracted into a gist, or spans fewer than K distinct holders. by_subject
// pins the subject in BOTH probes (entity-gist) and the cluster carries that subject;
// people-norm leaves subject_* empty. Reuses the per-find prepared statements.
std::optional<GistCluster> build_norm_cluster(
    sqlite3* db_handle, sqlite3_stmt* idem_stmt, sqlite3_stmt* member_stmt,
    std::string_view tenant_id, const SeedKey& key, const GistThresholds& thresholds,
    bool by_subject)
{
    const auto& [subject_kind, subject_id, predicate, object_hash] = key;
    // Idempotency (fail CLOSED): skip a key that already produced a gist.
    sqlite3_reset(idem_stmt);
    sqlite3_clear_bindings(idem_stmt);
    bind_sv(idem_stmt, 1, tenant_id);
    bind_sv(idem_stmt, 2, predicate);
    bind_sv(idem_stmt, 3, object_hash);
    if (by_subject) {
        bind_sv(idem_stmt, 4, subject_kind);
        bind_sv(idem_stmt, 5, subject_id);
    }
    if (sqlite3_step(idem_stmt) != SQLITE_ROW) {
        throw make_sqlite_error(db_handle, "find_norm_gist_clusters: idempotency step");
    }
    if (sqlite3_column_int(idem_stmt, 0) == 1) {
        return std::nullopt;
    }
    // Gather qualifying members + their distinct holders for this key.
    sqlite3_reset(member_stmt);
    sqlite3_clear_bindings(member_stmt);
    bind_sv(member_stmt, 1, tenant_id);
    bind_sv(member_stmt, 2, predicate);
    bind_sv(member_stmt, 3, object_hash);
    sqlite3_bind_int(member_stmt, 4, thresholds.min_replay_count);
    if (by_subject) {
        bind_sv(member_stmt, 5, subject_kind);
        bind_sv(member_stmt, 6, subject_id);
    }
    GistCluster cluster;
    cluster.predicate = predicate;
    cluster.canonical_object_hash = object_hash;
    cluster.subject_kind = subject_kind;  // "" for people-norm → generic __people__ gist
    cluster.subject_id = subject_id;
    std::set<std::string> holders;
    bool first = true;
    // Fail CLOSED on a mid-iteration error: a truncated member list could silently
    // drop the cluster below K. Break on DONE, throw on anything not another row.
    while (true) {
        const int step_rc = sqlite3_step(member_stmt);
        if (step_rc == SQLITE_DONE) {
            break;
        }
        if (step_rc != SQLITE_ROW) {
            throw make_sqlite_error(db_handle, "find_norm_gist_clusters: members step");
        }
        cluster.member_ids.push_back(column_text(member_stmt, 0));
        holders.insert(column_text(member_stmt, 1));
        if (first) {
            cluster.object_kind = column_text(member_stmt, 2);
            cluster.object_value = column_text(member_stmt, 3);
            first = false;
        }
    }
    if (static_cast<int>(holders.size()) < thresholds.min_distinct_holders) {
        return std::nullopt;
    }
    cluster.holder_ids.assign(holders.begin(), holders.end());
    return cluster;
}

// k-NN over-fetch width for the semantic pass: pull this many cosine-nearest
// candidates per seed, then keep only those at/above similarity_threshold. Larger
// than a typical norm so a wide consensus is not truncated before the holder count.
constexpr int kSemanticKnnK = 32;

// Load a statement's stored embedding (statement_vectors.index_vector BLOB → floats)
// to use as a k-NN query. Empty when the row is absent or not yet embedded.
std::vector<float> load_stmt_vector(sqlite3* db_handle, std::string_view tenant_id,
                                    std::string_view stmt_id) {
    sqlite3_stmt* sel = nullptr;
    const char* sql =
        "SELECT index_vector FROM statement_vectors "
        "WHERE tenant_id=? AND stmt_id=? AND status='embedded'";
    if (sqlite3_prepare_v2(db_handle, sql, -1, &sel, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db_handle, "load_stmt_vector: prepare");
    }
    StmtHandle handle(sel);
    bind_sv(handle.get(), 1, tenant_id);
    bind_sv(handle.get(), 2, stmt_id);
    if (sqlite3_step(handle.get()) != SQLITE_ROW) {
        return {};
    }
    const void* ptr = sqlite3_column_blob(handle.get(), 0);
    if (ptr == nullptr) {
        return {};
    }
    const int nbytes = sqlite3_column_bytes(handle.get(), 0);
    const std::string blob(static_cast<const char*>(ptr), static_cast<std::size_t>(nbytes));
    return vector::from_blob(blob);
}

// A norm-eligible member's fields. The settled-state filter is IDENTICAL to exact
// clustering (volatile/consolidated, review not rejected/pending, replay_count >= T),
// so a semantic cluster is built only from the same class of settled beliefs.
struct MemberRow {
    std::string holder_id;
    std::string predicate;
    std::string object_kind;
    std::string object_value;
    std::string object_hash;
};
std::optional<MemberRow> load_settled_member(sqlite3_stmt* member_stmt,
                                             std::string_view tenant_id,
                                             std::string_view stmt_id, int min_replay) {
    sqlite3_reset(member_stmt);
    sqlite3_clear_bindings(member_stmt);
    bind_sv(member_stmt, 1, tenant_id);
    bind_sv(member_stmt, 2, stmt_id);
    sqlite3_bind_int(member_stmt, 3, min_replay);
    if (sqlite3_step(member_stmt) != SQLITE_ROW) {
        return std::nullopt;
    }
    MemberRow row;
    row.holder_id    = column_text(member_stmt, 0);
    row.predicate    = column_text(member_stmt, 1);
    row.object_kind  = column_text(member_stmt, 2);
    row.object_value = column_text(member_stmt, 3);
    row.object_hash  = column_text(member_stmt, 4);
    return row;
}

// Is this statement an already-written NORM gist? Used by the semantic-dedup guard:
// a candidate whose representative is a near neighbor of an existing gist is dropped.
bool is_existing_gist(sqlite3* db_handle, std::string_view tenant_id,
                      std::string_view stmt_id) {
    sqlite3_stmt* sel = nullptr;
    const char* sql =
        "SELECT EXISTS(SELECT 1 FROM statements WHERE tenant_id=? AND id=? "
        "  AND provenance='consolidation_abstract')";
    if (sqlite3_prepare_v2(db_handle, sql, -1, &sel, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db_handle, "is_existing_gist: prepare");
    }
    StmtHandle handle(sel);
    bind_sv(handle.get(), 1, tenant_id);
    bind_sv(handle.get(), 2, stmt_id);
    return sqlite3_step(handle.get()) == SQLITE_ROW && sqlite3_column_int(handle.get(), 0) == 1;
}

// Gather the semantic cluster anchored at `seed_id`: the cosine-near (>= floor),
// settled, unclaimed neighbors. Representative (predicate/object/hash) = the smallest
// member id, so the cluster identity is stable across runs. nullopt if < K holders.
std::optional<GistCluster> expand_semantic_cluster(
    sqlite3_stmt* member_stmt, std::string_view tenant_id, const std::string& seed_id,
    const MemberRow& seed_member, const std::vector<vector::ScoredId>& scored,
    const GistThresholds& thresholds, const std::set<std::string>& taken)
{
    GistCluster cluster;
    cluster.predicate = seed_member.predicate;
    cluster.object_kind = seed_member.object_kind;
    cluster.object_value = seed_member.object_value;
    cluster.canonical_object_hash = seed_member.object_hash;
    cluster.member_ids.push_back(seed_id);
    std::set<std::string> holders{seed_member.holder_id};
    std::set<std::string> objects{seed_member.object_value};  // varied member phrasings
    std::string rep_id = seed_id;
    for (const auto& hit : scored) {
        if (hit.score < thresholds.similarity_threshold || hit.stmt_id == seed_id ||
            taken.contains(hit.stmt_id)) {
            continue;
        }
        const std::optional<MemberRow> member = load_settled_member(
            member_stmt, tenant_id, hit.stmt_id, thresholds.min_replay_count);
        if (!member.has_value()) {
            continue;
        }
        cluster.member_ids.push_back(hit.stmt_id);
        holders.insert(member->holder_id);
        objects.insert(member->object_value);
        if (hit.stmt_id < rep_id) {  // keep the smallest id as the stable representative
            rep_id = hit.stmt_id;
            cluster.predicate = member->predicate;
            cluster.object_kind = member->object_kind;
            cluster.object_value = member->object_value;
            cluster.canonical_object_hash = member->object_hash;
        }
    }
    if (static_cast<int>(holders.size()) < thresholds.min_distinct_holders) {
        return std::nullopt;
    }
    std::ranges::sort(cluster.member_ids);
    cluster.holder_ids.assign(holders.begin(), holders.end());
    cluster.member_objects.assign(objects.begin(), objects.end());  // varied → member-aware gate
    return cluster;
}

// Has this representative key already been abstracted into a gist? Fail CLOSED — the
// caller feeds the Phase-2 write, so a bypassed probe risks a duplicate gist.
bool gist_key_exists(sqlite3* db_handle, std::string_view tenant_id,
                     std::string_view predicate, std::string_view object_hash) {
    sqlite3_stmt* sel = nullptr;
    const char* sql =
        "SELECT EXISTS(SELECT 1 FROM statements WHERE tenant_id=? "
        "  AND predicate=? AND canonical_object_hash=? "
        "  AND provenance='consolidation_abstract')";
    if (sqlite3_prepare_v2(db_handle, sql, -1, &sel, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db_handle, "gist_key_exists: prepare");
    }
    StmtHandle handle(sel);
    bind_sv(handle.get(), 1, tenant_id);
    bind_sv(handle.get(), 2, predicate);
    bind_sv(handle.get(), 3, object_hash);
    return sqlite3_step(handle.get()) == SQLITE_ROW && sqlite3_column_int(handle.get(), 0) == 1;
}

// Existing-gist semantic dedup: is any near neighbor already a written gist? Guards a
// drifting representative from re-emitting the same norm under a different key.
bool representative_covered(sqlite3* db_handle, std::string_view tenant_id,
                            const std::vector<vector::ScoredId>& scored, double floor) {
    return std::ranges::any_of(scored, [&](const vector::ScoredId& hit) {
        return hit.score >= floor && is_existing_gist(db_handle, tenant_id, hit.stmt_id);
    });
}

}  // namespace

std::vector<GistCluster> find_norm_gist_clusters(
    persistence::Connection& conn,
    std::string_view tenant_id,
    const std::vector<std::string>& seed_stmt_ids,
    const GistThresholds& thresholds,
    bool by_subject)
{
    std::vector<GistCluster> clusters;
    if (seed_stmt_ids.empty() || thresholds.min_distinct_holders <= 0) {
        return clusters;
    }
    sqlite3* db_handle = conn.raw();

    // 1) Distinct seed keys among the batch. by_subject → (subject, predicate, hash)
    // entity-gist keys (cognizer subjects); else people-norm (predicate, hash) keys.
    const auto seed_keys = collect_seed_keys(db_handle, tenant_id, seed_stmt_ids, by_subject);
    if (seed_keys.empty()) {
        return clusters;
    }

    // Prepared once, reused per key: (2) member gather and (3) idempotency probe.
    // A norm is built only from SETTLED beliefs, so members are deliberately
    // restricted to the two stable live states ('volatile','consolidated') and
    // exclude:
    //   - 'archived' / 'forgotten'      — gone from the retrieval/replay pool;
    //   - 'replaying_reconsolidating'   — CONTESTED (in conflict, under
    //     arbitration). Folding a contested belief into a norm is exactly what
    //     the gating must prevent, so it must not count toward the K threshold;
    //   - 'replaying_consolidating'     — a transient mid-operation state. v1 is
    //     single-threaded (no background replay thread until M0.9+), so a batch
    //     row is never observed mid-transition here; excluding it is conservative.
    // Tuning which states qualify is deferred to v2.
    // entity-gist additionally pins the SUBJECT (gather only THIS entity's holders);
    // people-norm gathers across all subjects sharing (predicate, object).
    sqlite3_stmt* mem = nullptr;
    const char* mem_sql = by_subject
        ? "SELECT id, holder_id, object_kind, object_value FROM statements "
          "WHERE tenant_id=? AND predicate=? AND canonical_object_hash=? AND replay_count >= ? "
          "  AND subject_kind=? AND subject_id=? "
          "  AND consolidation_state IN ('volatile','consolidated') "
          "  AND review_status NOT IN ('rejected','pending_review') ORDER BY id"
        : "SELECT id, holder_id, object_kind, object_value FROM statements "
          "WHERE tenant_id=? AND predicate=? AND canonical_object_hash=? AND replay_count >= ? "
          "  AND consolidation_state IN ('volatile','consolidated') "
          "  AND review_status NOT IN ('rejected','pending_review') ORDER BY id";
    if (sqlite3_prepare_v2(db_handle, mem_sql, -1, &mem, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db_handle, "find_norm_gist_clusters: prepare members");
    }
    StmtHandle hmem(mem);

    sqlite3_stmt* idem = nullptr;
    const char* idem_sql = by_subject
        ? "SELECT EXISTS(SELECT 1 FROM statements WHERE tenant_id=? AND predicate=? "
          "  AND canonical_object_hash=? AND subject_kind=? AND subject_id=? "
          "  AND provenance='consolidation_abstract')"
        : "SELECT EXISTS(SELECT 1 FROM statements WHERE tenant_id=? AND predicate=? "
          "  AND canonical_object_hash=? AND provenance='consolidation_abstract')";
    if (sqlite3_prepare_v2(db_handle, idem_sql, -1, &idem, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db_handle, "find_norm_gist_clusters: prepare idempotency");
    }
    StmtHandle hidem(idem);

    // Per key: idempotency probe + member gather (build_norm_cluster). The big
    // settled-state + idempotency rationale lives there. Fail CLOSED throughout.
    for (const auto& key : seed_keys) {
        std::optional<GistCluster> cluster = build_norm_cluster(
            db_handle, hidem.get(), hmem.get(), tenant_id, key, thresholds, by_subject);
        if (cluster.has_value()) {
            clusters.push_back(std::move(*cluster));
        }
    }

    // Deterministic order (the seed_keys set is already sorted; this makes the
    // contract explicit and survives any future change to key collection).
    std::ranges::sort(clusters,
                      [](const GistCluster& lhs, const GistCluster& rhs) {
                          if (lhs.predicate != rhs.predicate) {
                              return lhs.predicate < rhs.predicate;
                          }
                          return lhs.canonical_object_hash < rhs.canonical_object_hash;
                      });
    return clusters;
}

std::vector<GistCluster> find_semantic_gist_clusters(
    persistence::Connection& conn,
    vector::VectorIndex& index,
    std::string_view tenant_id,
    const std::vector<std::string>& seed_stmt_ids,
    const GistThresholds& thresholds,
    const std::set<std::string>& claimed)
{
    std::vector<GistCluster> clusters;
    // Opt-in: the semantic pass is OFF unless a positive cosine floor is configured
    // (0.0 default = exact-match only, no behavior change on upgrade).
    if (thresholds.similarity_threshold <= 0.0 || thresholds.min_distinct_holders <= 0 ||
        seed_stmt_ids.empty()) {
        return clusters;
    }
    sqlite3* db_handle = conn.raw();

    // Member filter: the SAME settled-state predicate as exact clustering, by id.
    sqlite3_stmt* mem = nullptr;
    const char* mem_sql =
        "SELECT holder_id, predicate, object_kind, object_value, canonical_object_hash "
        "FROM statements WHERE tenant_id=? AND id=? AND replay_count >= ? "
        "  AND consolidation_state IN ('volatile','consolidated') "
        "  AND review_status NOT IN ('rejected','pending_review')";
    if (sqlite3_prepare_v2(db_handle, mem_sql, -1, &mem, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db_handle, "find_semantic_gist_clusters: prepare members");
    }
    StmtHandle hmem(mem);

    const vector::SearchScope scope{.tenant_id = std::string(tenant_id),
                                    .holder_id = std::nullopt,
                                    .holder_perspective = std::nullopt,
                                    .visible_only = true};
    std::set<std::string> taken = claimed;  // exact-claimed + grows as semantic clusters form

    for (const auto& seed_id : seed_stmt_ids) {
        if (taken.contains(seed_id)) {
            continue;  // already in an exact cluster or a prior semantic cluster
        }
        const std::vector<float> qvec = load_stmt_vector(db_handle, tenant_id, seed_id);
        if (qvec.empty()) {
            continue;
        }
        const std::optional<MemberRow> seed_member =
            load_settled_member(hmem.get(), tenant_id, seed_id, thresholds.min_replay_count);
        if (!seed_member.has_value()) {
            continue;  // the seed itself is not norm-eligible (state / review / T)
        }

        // k-NN: over-fetch, keep cosine >= the configured floor.
        const std::vector<vector::ScoredId> scored =
            index.search_topk(conn, qvec, kSemanticKnnK, scope);

        std::optional<GistCluster> cluster = expand_semantic_cluster(
            hmem.get(), tenant_id, seed_id, *seed_member, scored, thresholds, taken);
        if (!cluster.has_value()) {
            continue;
        }
        // Idempotency (fail CLOSED): skip if the representative key was already
        // abstracted, or any near neighbor is already a written gist.
        if (gist_key_exists(db_handle, tenant_id, cluster->predicate,
                            cluster->canonical_object_hash) ||
            representative_covered(db_handle, tenant_id, scored,
                                   thresholds.similarity_threshold)) {
            continue;
        }
        for (const auto& member_id : cluster->member_ids) {
            taken.insert(member_id);  // claim so a later seed in this neighborhood won't re-emit
        }
        clusters.push_back(std::move(*cluster));
    }

    std::ranges::sort(clusters, [](const GistCluster& lhs, const GistCluster& rhs) {
        if (lhs.predicate != rhs.predicate) {
            return lhs.predicate < rhs.predicate;
        }
        return lhs.canonical_object_hash < rhs.canonical_object_hash;
    });
    return clusters;
}

}  // namespace starling::replay
