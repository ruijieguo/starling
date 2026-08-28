#include "starling/schema/common_ground_scope.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <stdexcept>
#include <utility>

namespace starling::schema {
namespace {

constexpr std::string_view kEncodedRefPrefix = "cg:v1:";
constexpr std::string_view kLegacySeparator = "::";

}  // namespace

std::vector<std::string> canonical_common_ground_parties(
    std::vector<std::string> parties) {
    std::sort(parties.begin(), parties.end());
    parties.erase(std::unique(parties.begin(), parties.end()), parties.end());
    return parties;
}

std::string common_ground_parties_json(
    const std::vector<std::string>& parties) {
    return nlohmann::json(canonical_common_ground_parties(parties)).dump();
}

std::optional<std::vector<std::string>> parse_common_ground_parties_json(
    std::string_view parties_json) {
    const auto parsed = nlohmann::json::parse(
        parties_json.begin(), parties_json.end(), nullptr, false);
    if (!parsed.is_array()) return std::nullopt;

    std::vector<std::string> parties;
    parties.reserve(parsed.size());
    for (const auto& item : parsed) {
        if (!item.is_string()) return std::nullopt;
        parties.push_back(item.get<std::string>());
    }
    return canonical_common_ground_parties(std::move(parties));
}

std::string common_ground_ref(const std::vector<std::string>& parties) {
    const auto canonical = canonical_common_ground_parties(parties);
    if (canonical.size() < 2) {
        throw std::invalid_argument(
            "common_ground_ref requires at least two distinct parties");
    }

    if (canonical.size() == 2 &&
        canonical[0].find(kLegacySeparator) == std::string::npos &&
        canonical[1].find(kLegacySeparator) == std::string::npos) {
        const std::string legacy = canonical[0] + std::string(kLegacySeparator) + canonical[1];
        if (!legacy.starts_with(kEncodedRefPrefix)) return legacy;
    }
    return std::string(kEncodedRefPrefix) + nlohmann::json(canonical).dump();
}

std::optional<std::vector<std::string>> common_ground_parties_from_ref(
    std::string_view ref) {
    if (ref.starts_with(kEncodedRefPrefix)) {
        auto parties = parse_common_ground_parties_json(ref.substr(kEncodedRefPrefix.size()));
        if (!parties || parties->size() < 2) {
            throw std::invalid_argument("invalid encoded common-ground ref");
        }
        return parties;
    }

    const auto separator = ref.find(kLegacySeparator);
    if (separator == std::string_view::npos) return std::nullopt;
    if (ref.find(kLegacySeparator, separator + kLegacySeparator.size()) !=
        std::string_view::npos) {
        throw std::invalid_argument(
            "ambiguous legacy common-ground ref; use cg:v1 encoding");
    }
    auto parties = canonical_common_ground_parties({
        std::string(ref.substr(0, separator)),
        std::string(ref.substr(separator + kLegacySeparator.size())),
    });
    if (parties.size() != 2 || parties[0].empty() || parties[1].empty()) {
        throw std::invalid_argument("invalid legacy common-ground ref");
    }
    return parties;
}

}  // namespace starling::schema
