#include "starling/bus/conflict_probe.hpp"

#include "starling/bus/conflict_key.hpp"
#include "starling/bus/normalized_interval.hpp"
#include "starling/bus/sqlite_helpers.hpp"
#include "starling/persistence/sqlite_handles.hpp"
#include "starling/schema/statement_enums.hpp"

#include <sqlite3.h>

#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace starling::bus {

std::string_view to_string(ConflictKind k) {
    switch (k) {
        case ConflictKind::DirectContradiction: return "direct_contradiction";
        case ConflictKind::Superseding:         return "superseding";
        case ConflictKind::PartialOverlap:      return "partial_overlap";
        case ConflictKind::Adjacent:            return "adjacent";
    }
    return "unknown";
}

namespace {

// One row pulled from the candidate prefilter query.
struct CandidateRow {
    std::string        id;
    std::string        tenant_id;
    std::string        supersedes_root_id;             // COALESCE(supersedes_id, id)
    std::string        canonical_object_hash_version;
    std::string        polarity;                       // "pos" | "neg" | "unknown"
    std::string        consolidation_state;            // "volatile" | "consolidated"
    NormalizedInterval interval;                       // built from valid_from/valid_to/event_time_start
    double             confidence = 0.0;
};

// Closed-open interval relations on NormalizedInterval. Open end = +inf.
// Both intervals must be known (is_unknown == false) when these are called.
bool intervals_overlap(const NormalizedInterval& a, const NormalizedInterval& b) {
    // start_a < end_b AND start_b < end_a, with open ends treated as +inf.
    const bool a_before_b_end = b.to_is_open || b.to.empty() || a.from < b.to;
    const bool b_before_a_end = a.to_is_open || a.to.empty() || b.from < a.to;
    return a_before_b_end && b_before_a_end;
}

// True iff a fully covers b: start_a <= start_b AND (end_a is open OR end_a >= end_b).
bool covers(const NormalizedInterval& a, const NormalizedInterval& b) {
    if (a.from > b.from) return false;
    const bool a_open = a.to_is_open || a.to.empty();
    if (a_open) return true;
    const bool b_open = b.to_is_open || b.to.empty();
    if (b_open) return false;          // a closed, b open -> a can't cover b
    return a.to >= b.to;
}

// Touching but not overlapping: end_a == start_b OR end_b == start_a (and no overlap).
bool intervals_adjacent(const NormalizedInterval& a, const NormalizedInterval& b) {
    if (intervals_overlap(a, b)) return false;
    const bool a_closed = !a.to_is_open && !a.to.empty();
    const bool b_closed = !b.to_is_open && !b.to.empty();
    if (a_closed && a.to == b.from) return true;
    if (b_closed && b.to == a.from) return true;
    return false;
}

NormalizedInterval interval_from_columns(
    const std::string& vf, const std::string& vt, const std::string& ets) {
    return normalize_interval(
        vf.empty()  ? std::nullopt : std::optional<std::string>(vf),
        vt.empty()  ? std::nullopt : std::optional<std::string>(vt),
        ets.empty() ? std::nullopt : std::optional<std::string>(ets));
}

std::vector<CandidateRow> fetch_candidates(
    starling::persistence::Connection& conn,
    const starling::extractor::ExtractedStatement& s) {

    // hash_version intentionally omitted from the WHERE clause: cross-version
    // rows are returned and clamped to PartialOverlap in classify(). Revisit
    // when M0.5+1 ships a second canonical_object_hash version.
    //
    // KNOWN GAP: 05_bus.md canonical_object_hash_version §"双查协议" specifies
    // that during a hash-version upgrade the probe MUST query both the current
    // and previous version hashes (so a v1 row with the post-rename hash and a
    // v2 row with the pre-rename hash can both be examined). M0.5 ships v1
    // only, so the post-fetch clamp at classify():"cross-version → PartialOverlap"
    // is sufficient. When the second canonical version ships, replace this
    // single-version SELECT with the two-hash double query and add a parity
    // test that seeds a v1 + v2 collision under the same logical object.
    const char* sql =
        "SELECT id, tenant_id, "
        "       COALESCE(supersedes_id, id) AS supersedes_root_id, "
        "       canonical_object_hash_version, polarity, "
        "       consolidation_state, "
        "       COALESCE(valid_from, ''), COALESCE(valid_to, ''), "
        "       COALESCE(event_time_start, ''), confidence "
        "FROM statements "
        "WHERE tenant_id = ? AND holder_id = ? AND modality = ? "
        "  AND subject_kind = ? AND subject_id = ? AND predicate = ? "
        "  AND canonical_object_hash = ? "
        "  AND consolidation_state IN ('volatile','consolidated')";

    sqlite3_stmt* raw = nullptr;
    if (sqlite3_prepare_v2(conn.raw(), sql, -1, &raw, nullptr) != SQLITE_OK) {
        throw detail::make_sqlite_error(conn.raw(), "ConflictProbe::scan prepare candidates");
    }
    starling::persistence::StmtHandle h(raw);

    detail::bind_sv(h.get(), 1, s.holder_tenant_id);
    detail::bind_sv(h.get(), 2, s.holder_id);
    detail::bind_sv(h.get(), 3, starling::schema::to_string(s.modality));
    detail::bind_sv(h.get(), 4, s.subject_kind);
    detail::bind_sv(h.get(), 5, s.subject_id);
    detail::bind_sv(h.get(), 6, s.predicate);
    detail::bind_sv(h.get(), 7, s.canonical_object_hash);

    std::vector<CandidateRow> rows;
    while (true) {
        const int rc = sqlite3_step(h.get());
        if (rc == SQLITE_DONE) break;
        if (rc != SQLITE_ROW) {
            throw detail::make_sqlite_error(conn.raw(), "ConflictProbe::scan step candidates");
        }
        const auto col = [&](int i) {
            const auto* p = sqlite3_column_text(h.get(), i);
            return p ? std::string(reinterpret_cast<const char*>(p)) : std::string{};
        };
        CandidateRow r;
        r.id                            = col(0);
        r.tenant_id                     = col(1);
        r.supersedes_root_id            = col(2);
        r.canonical_object_hash_version = col(3);
        r.polarity                      = col(4);
        r.consolidation_state           = col(5);
        const std::string vf  = col(6);
        const std::string vt  = col(7);
        const std::string ets = col(8);
        r.confidence                    = sqlite3_column_double(h.get(), 9);
        r.interval                      = interval_from_columns(vf, vt, ets);
        rows.push_back(std::move(r));
    }
    return rows;
}

ConflictKind classify(
    const starling::extractor::ExtractedStatement& s_new,
    const NormalizedInterval& iv_new,
    const CandidateRow& cand) {

    // Cross-version: anything other than v1 is "different from S_new" since
    // M0.5 only writes v1. (When future versions ship, callers will pass
    // S_new's version explicitly here.)
    constexpr std::string_view kSNewVersion = "v1";
    if (cand.canonical_object_hash_version != kSNewVersion) {
        return ConflictKind::PartialOverlap;
    }

    // §3.5 T7-P1 only authorizes the SUPERSEDES atomic path against a
    // CONSOLIDATED S_old (the bypass goes consolidated → archived directly,
    // skipping replaying_reconsolidating). A VOLATILE S_old has not been
    // consolidated yet; archiving it via the severe path would violate the
    // lifecycle and apply_supersedes_atomic would silently rollback because
    // its `WHERE consolidation_state='consolidated'` guard matches 0 rows.
    // Clamp severe classifications to PartialOverlap when S_old is volatile.
    if (cand.consolidation_state != "consolidated") {
        return ConflictKind::PartialOverlap;
    }

    if (iv_new.is_unknown || cand.interval.is_unknown) {
        return ConflictKind::PartialOverlap;
    }

    const bool both_above_theta =
        s_new.confidence >= ConflictProbe::kThetaSevere &&
        cand.confidence  >= ConflictProbe::kThetaSevere;

    const std::string s_new_polarity{starling::schema::to_string(s_new.polarity)};
    const bool opposite_polarity = (s_new_polarity != cand.polarity);

    // Polarity::UNKNOWN must not trigger Superseding or DirectContradiction —
    // a statement of unknown polarity has no semantic conflict with anything.
    const bool polarity_known =
        s_new_polarity != "unknown" && cand.polarity != "unknown";

    if (intervals_overlap(iv_new, cand.interval)) {
        if (opposite_polarity && both_above_theta && polarity_known) {
            return ConflictKind::DirectContradiction;
        }
        if (!opposite_polarity && both_above_theta && polarity_known
            && covers(iv_new, cand.interval)) {
            return ConflictKind::Superseding;
        }
        return ConflictKind::PartialOverlap;
    }

    if (intervals_adjacent(iv_new, cand.interval)) {
        return ConflictKind::Adjacent;
    }

    // Disjoint, non-adjacent: still a same-key match per the prefilter.
    // Return PartialOverlap as the floor (caller may suppress in M0.5+1).
    return ConflictKind::PartialOverlap;
}

int severity_rank(ConflictKind k) {
    switch (k) {
        case ConflictKind::DirectContradiction: return 4;
        case ConflictKind::Superseding:         return 3;
        case ConflictKind::PartialOverlap:      return 2;
        case ConflictKind::Adjacent:            return 1;
    }
    return 0;
}

}  // namespace

std::optional<ConflictMatch> ConflictProbe::scan(
    const starling::extractor::ExtractedStatement& s_new,
    const NormalizedInterval& interval_new) const {

    auto candidates = fetch_candidates(conn_, s_new);
    if (candidates.empty()) return std::nullopt;

    std::optional<ConflictMatch> best;
    int best_rank = 0;

    for (const auto& cand : candidates) {
        const ConflictKind k = classify(s_new, interval_new, cand);
        const int rank = severity_rank(k);
        if (rank > best_rank) {
            ConflictMatch m;
            m.kind                                  = k;
            m.matched_statement_id                  = cand.id;
            m.matched_tenant_id                     = cand.tenant_id;
            m.matched_supersedes_root_id            = cand.supersedes_root_id;
            m.matched_canonical_object_hash_version = cand.canonical_object_hash_version;
            m.matched_confidence                    = cand.confidence;
            m.conflict_key_hex                      = canonical_conflict_key_hex(s_new);
            best      = std::move(m);
            best_rank = rank;
        }
    }
    return best;
}

}  // namespace starling::bus
