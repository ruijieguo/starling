#pragma once

#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace starling::schema {

// Common-ground parties are set-like: canonical storage and keys use sorted,
// unique cognizer ids.
std::vector<std::string> canonical_common_ground_parties(
    std::vector<std::string> parties);

std::string common_ground_parties_json(
    const std::vector<std::string>& parties);

std::optional<std::vector<std::string>> parse_common_ground_parties_json(
    std::string_view parties_json);

// Keeps the historical "a::b" key for unambiguous two-party scopes. N-ary
// scopes and ids containing "::" use the injective "cg:v1:<json-array>" form.
std::string common_ground_ref(const std::vector<std::string>& parties);

// Returns nullopt for legacy unscoped refs that contain no "::". Invalid or
// ambiguous scoped refs throw std::invalid_argument instead of broadening scope.
std::optional<std::vector<std::string>> common_ground_parties_from_ref(
    std::string_view ref);

}  // namespace starling::schema
