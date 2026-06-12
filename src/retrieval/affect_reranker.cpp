#include "starling/retrieval/affect_reranker.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <ctime>

namespace starling::retrieval {

namespace {
double parse_iso_epoch(std::string_view iso) {
    if (iso.empty()) return 0.0;
    std::tm tm{}; int y, mo, d, h, mi, s;
    if (std::sscanf(std::string(iso).c_str(), "%d-%d-%dT%d:%d:%d",
                    &y, &mo, &d, &h, &mi, &s) != 6) return 0.0;
    tm.tm_year = y - 1900; tm.tm_mon = mo - 1; tm.tm_mday = d;
    tm.tm_hour = h; tm.tm_min = mi; tm.tm_sec = s;
    return static_cast<double>(timegm(&tm));
}
double clamp01(double v) { return v < 0.0 ? 0.0 : (v > 1.0 ? 1.0 : v); }
}  // namespace

double recency_factor(std::string_view observed_at_iso, std::string_view as_of_iso) {
    const double dt = parse_iso_epoch(as_of_iso) - parse_iso_epoch(observed_at_iso);
    if (dt <= 0.0) return 1.0;
    return std::exp(-dt / (30.0 * 86400.0));
}

double activation_level(double activation) { return clamp01(activation); }

double temporal_distance_penalty(const StatementRow& row, std::string_view as_of_iso) {
    if (row.valid_to.empty()) return 0.0;
    return parse_iso_epoch(row.valid_to) <= parse_iso_epoch(as_of_iso) ? 0.3 : 0.0;
}

double affect_consistency(std::string_view affect_json,
                          const affect::AffectVector& querier) {
    const affect::AffectVector c = affect::parse_affect_json(affect_json);
    const double l1 = std::abs(double(c.valence)   - double(querier.valence))
                    + std::abs(double(c.arousal)   - double(querier.arousal))
                    + std::abs(double(c.dominance) - double(querier.dominance))
                    + std::abs(double(c.novelty)   - double(querier.novelty))
                    + std::abs(double(c.stakes)    - double(querier.stakes));
    const double sim = clamp01(1.0 - l1 / 5.0);
    return 0.5 + 0.5 * sim;
}

std::vector<ScoreRow> rerank(std::vector<RerankCandidate>& cands,
                             const QuerierAffectState& querier,
                             std::string_view as_of_iso) {
    std::vector<ScoreRow> breakdown;
    breakdown.reserve(cands.size());
    std::vector<std::pair<double, std::size_t>> order;
    order.reserve(cands.size());
    for (std::size_t i = 0; i < cands.size(); ++i) {
        const auto& c = cands[i];
        ScoreRow s;
        s.statement_id       = c.row.id;
        s.base               = c.base_relevance;
        s.recency            = recency_factor(c.row.observed_at, as_of_iso);
        s.salience           = clamp01(c.salience);
        s.activation         = activation_level(c.activation);
        s.affect_consistency = affect_consistency(c.row.affect_json, querier.affect);
        s.temporal_penalty   = temporal_distance_penalty(c.row, as_of_iso);
        s.final_score = s.base * (1 + 0.3 * s.recency) * (1 + 0.4 * s.salience)
                      * (1 + 0.3 * s.activation) * s.affect_consistency
                      * (1 - s.temporal_penalty);
        breakdown.push_back(std::move(s));
        order.emplace_back(breakdown.back().final_score, i);
    }
    std::sort(order.begin(), order.end(),
              [](const auto& a, const auto& b) { return a.first > b.first; });
    std::vector<RerankCandidate> sorted_c; sorted_c.reserve(cands.size());
    std::vector<ScoreRow> sorted_b; sorted_b.reserve(breakdown.size());
    for (const auto& [score, idx] : order) {
        sorted_c.push_back(std::move(cands[idx]));
        sorted_b.push_back(std::move(breakdown[idx]));
    }
    cands = std::move(sorted_c);
    return sorted_b;
}

}  // namespace starling::retrieval
