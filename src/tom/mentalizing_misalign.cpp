#include "starling/tom/mentalizing.hpp"

#include "starling/store/sqlite_meta_store.hpp"

#include <cmath>
#include <string>
#include <unordered_map>
#include <vector>

namespace starling::tom::mentalizing {

namespace {

// Key for aligning beliefs: (predicate, canonical_object_hash).
struct BeliefKey {
    std::string predicate;
    std::string canonical_object_hash;
    bool operator==(const BeliefKey& o) const noexcept {
        return predicate == o.predicate &&
               canonical_object_hash == o.canonical_object_hash;
    }
};

struct BeliefKeyHash {
    std::size_t operator()(const BeliefKey& k) const noexcept {
        std::size_t h = std::hash<std::string>{}(k.predicate);
        h ^= std::hash<std::string>{}(k.canonical_object_hash) + 0x9e3779b9 + (h << 6) + (h >> 2);
        return h;
    }
};

}  // namespace

Misalignment find_misalignment(
    persistence::SqliteAdapter& adapter,
    std::string_view x,
    std::string_view y,
    std::string_view subject_kind,
    std::string_view subject_id,
    std::string_view tenant,
    std::string_view as_of)
{
    // P3.b1 phase 3:两侧信念读收编进 MetaStore.query_statements —— 默认 state
    // IN(consolidated,archived) + review 守卫 + as_of 时间窗即原 fetch_beliefs
    // WHERE。比较逻辑(polarity/confidence 对齐)保持不变。
    store::SqliteMetaStore meta(adapter.connection());
    auto fetch = [&](std::string_view holder) {
        store::StatementFilter f;
        f.tenant_id     = std::string(tenant);
        f.holder_id     = std::string(holder);
        f.subject_kind  = std::string(subject_kind);
        f.subject_id    = std::string(subject_id);
        f.as_of_iso8601 = std::string(as_of);
        return meta.query_statements(f);
    };
    auto x_rows = fetch(x);
    auto y_rows = fetch(y);

    // Build lookup maps by belief key.
    std::unordered_map<BeliefKey, retrieval::StatementRow, BeliefKeyHash> x_map, y_map;
    for (auto& r : x_rows) x_map[{r.predicate, r.canonical_object_hash}] = r;
    for (auto& r : y_rows) y_map[{r.predicate, r.canonical_object_hash}] = r;

    Misalignment result;

    // X has POS but Y doesn't (or has NEG).
    for (const auto& [key, xr] : x_map) {
        if (xr.polarity != "pos") continue;
        auto it = y_map.find(key);
        if (it == y_map.end() || it->second.polarity != "pos") {
            result.only_x_believes.push_back(xr);
        }
    }

    // Y has POS but X doesn't (or has NEG).
    for (const auto& [key, yr] : y_map) {
        if (yr.polarity != "pos") continue;
        auto it = x_map.find(key);
        if (it == x_map.end() || it->second.polarity != "pos") {
            result.only_y_believes.push_back(yr);
        }
    }

    // Both POS but confidence diverges > 0.3.
    for (const auto& [key, xr] : x_map) {
        if (xr.polarity != "pos") continue;
        auto it = y_map.find(key);
        if (it == y_map.end() || it->second.polarity != "pos") continue;
        const double diff = std::fabs(xr.confidence - it->second.confidence);
        if (diff > 0.3) {
            result.confidence_diverges.emplace_back(xr, it->second);
        }
    }

    return result;
}

}  // namespace starling::tom::mentalizing
