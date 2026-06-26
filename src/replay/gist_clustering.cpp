#include "starling/replay/gist_clustering.hpp"
#include "starling/persistence/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"

#include <algorithm>
#include <iterator>
#include <set>
#include <string>
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

// Collect the distinct (predicate, canonical_object_hash) keys carried by the
// seed batch, scoped to one tenant. Deduped via a set so a batch with many rows
// sharing a key probes the tenant only once; a seed id absent from this tenant
// contributes nothing.
std::set<std::pair<std::string, std::string>> collect_seed_keys(
    sqlite3* db_handle,
    std::string_view tenant_id,
    const std::vector<std::string>& seed_stmt_ids)
{
    std::set<std::pair<std::string, std::string>> seed_keys;
    sqlite3_stmt* sel = nullptr;
    const char* sql =
        "SELECT predicate, canonical_object_hash FROM statements "
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
        if (sqlite3_step(hsel.get()) == SQLITE_ROW) {
            seed_keys.emplace(column_text(hsel.get(), 0),
                              column_text(hsel.get(), 1));
        }
    }
    return seed_keys;
}

}  // namespace

std::vector<GistCluster> find_norm_gist_clusters(
    persistence::Connection& conn,
    std::string_view tenant_id,
    const std::vector<std::string>& seed_stmt_ids,
    const GistThresholds& thresholds)
{
    std::vector<GistCluster> clusters;
    if (seed_stmt_ids.empty() || thresholds.min_distinct_holders <= 0) {
        return clusters;
    }
    sqlite3* db_handle = conn.raw();

    // 1) Distinct "hot" (predicate, canonical_object_hash) keys among the seeds.
    const auto seed_keys = collect_seed_keys(db_handle, tenant_id, seed_stmt_ids);
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
    sqlite3_stmt* mem = nullptr;
    const char* mem_sql =
        "SELECT id, holder_id, object_kind, object_value FROM statements "
        "WHERE tenant_id=? AND predicate=? AND canonical_object_hash=? "
        "  AND replay_count >= ? "
        "  AND consolidation_state IN ('volatile','consolidated') "
        "  AND review_status NOT IN ('rejected','pending_review') "
        "ORDER BY id";
    if (sqlite3_prepare_v2(db_handle, mem_sql, -1, &mem, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db_handle, "find_norm_gist_clusters: prepare members");
    }
    StmtHandle hmem(mem);

    sqlite3_stmt* idem = nullptr;
    const char* idem_sql =
        "SELECT EXISTS(SELECT 1 FROM statements WHERE tenant_id=? "
        "  AND predicate=? AND canonical_object_hash=? "
        "  AND provenance='consolidation_abstract')";
    if (sqlite3_prepare_v2(db_handle, idem_sql, -1, &idem, nullptr) != SQLITE_OK) {
        throw make_sqlite_error(db_handle, "find_norm_gist_clusters: prepare idempotency");
    }
    StmtHandle hidem(idem);

    for (const auto& [predicate, object_hash] : seed_keys) {
        // Idempotency: skip a key that already produced a gist, regardless of the
        // gist's current state (a forgotten gist stays forgotten — don't resurrect).
        // Fail CLOSED: this guard feeds the Phase-2 write, so a silently bypassed
        // probe would risk a duplicate gist. EXISTS always yields exactly one row;
        // anything else is an error, so throw rather than fall through.
        // Phase-2 NOTE: a 'consolidation_abstract' row that was REJECTED at review
        // also suppresses re-abstraction here. Phase 2 must decide rejection
        // semantics (delete / tombstone via state) if a rejected key should ever
        // be re-eligible — today "any such row → skip" matches the locked design.
        sqlite3_reset(hidem.get());
        sqlite3_clear_bindings(hidem.get());
        bind_sv(hidem.get(), 1, tenant_id);
        bind_sv(hidem.get(), 2, predicate);
        bind_sv(hidem.get(), 3, object_hash);
        if (sqlite3_step(hidem.get()) != SQLITE_ROW) {
            throw make_sqlite_error(db_handle, "find_norm_gist_clusters: idempotency step");
        }
        if (sqlite3_column_int(hidem.get(), 0) == 1) {
            continue;
        }

        // Gather qualifying members + their distinct holders for this key.
        sqlite3_reset(hmem.get());
        sqlite3_clear_bindings(hmem.get());
        bind_sv(hmem.get(), 1, tenant_id);
        bind_sv(hmem.get(), 2, predicate);
        bind_sv(hmem.get(), 3, object_hash);
        sqlite3_bind_int(hmem.get(), 4, thresholds.min_replay_count);

        GistCluster cluster;
        cluster.predicate = predicate;
        cluster.canonical_object_hash = object_hash;
        std::set<std::string> holders;
        bool first = true;
        // Fail CLOSED on a mid-iteration error: a truncated member list could
        // silently drop the cluster below K (false negative). Break on DONE,
        // throw on anything that is not another row.
        while (true) {
            const int step_rc = sqlite3_step(hmem.get());
            if (step_rc == SQLITE_DONE) {
                break;
            }
            if (step_rc != SQLITE_ROW) {
                throw make_sqlite_error(db_handle, "find_norm_gist_clusters: members step");
            }
            cluster.member_ids.push_back(column_text(hmem.get(), 0));
            holders.insert(column_text(hmem.get(), 1));
            if (first) {
                cluster.object_kind  = column_text(hmem.get(), 2);
                cluster.object_value = column_text(hmem.get(), 3);
                first = false;
            }
        }
        if (static_cast<int>(holders.size()) < thresholds.min_distinct_holders) {
            continue;
        }
        cluster.holder_ids.assign(holders.begin(), holders.end());
        clusters.push_back(std::move(cluster));
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

}  // namespace starling::replay
