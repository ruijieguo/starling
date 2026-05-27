#pragma once

#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace starling::cognizer {

enum class CognizerKind { Self, Human, Agent, Group, Role, External };

enum class FiskeMode { Communal, Authority, Equality, Market };

struct Cognizer {
    std::string id;                                            // UUID5(kStarlingCognizerNamespace, kind+"\x1f"+external_id)
    std::string tenant_id;                                     // "default" or explicit (group 强制显式)
    CognizerKind kind;
    std::string canonical_name;
    std::vector<std::string> aliases;                          // RAW strings
    std::string external_id;
    std::unordered_map<std::string, double> trust_priors;      // {cognizer_id: float}
    std::string permissions_json;                              // opaque JSON string
    std::string created_at;
    std::string last_seen_at;
};

struct CognizerRegistration {
    CognizerKind kind;
    std::string tenant_id = "default";
    bool tenant_explicitly_set = false;                        // group kind requires this true
    std::string canonical_name;                                // optional; falls back to longest alias
    std::vector<std::string> aliases;                          // RAW; will be normalized for storage
    std::string external_id;
    std::vector<std::string> group_memberships;                // for record_group_membership downstream
    std::unordered_map<std::string, double> trust_priors;
    std::string permissions_json = "{}";
};

struct RelationEdge {
    std::string id;
    std::string tenant_id;
    std::string a_id;
    std::string b_id;
    std::unordered_map<FiskeMode, double> fiske_weights;       // sum == 1.0 ± 1e-6
    double affinity = 0.5;                                     // [0,1]
    std::unordered_map<std::string, double> trust;             // {context: float}
    double power_asymmetry = 0.0;
    std::optional<std::string> interaction_history_ref;
    std::optional<std::string> valid_from;
    std::optional<std::string> valid_to;
    std::string created_at;
    std::string updated_at;
};

struct RelationEdgeInput {
    std::string tenant_id;
    std::string a_id;
    std::string b_id;
    std::unordered_map<FiskeMode, double> fiske_weights;
    double affinity = 0.5;
    std::unordered_map<std::string, double> trust;
    double power_asymmetry = 0.0;
    std::optional<std::string> interaction_history_ref;
    std::optional<std::string> valid_from;
    std::optional<std::string> valid_to;
};

// ── Error types (spec §6.7) ──

class AliasCollision : public std::runtime_error {
public:
    std::string existing_id;
    std::string alias;
    AliasCollision(std::string id, std::string a)
        : std::runtime_error("alias collides with existing cognizer"),
          existing_id(std::move(id)), alias(std::move(a)) {}
};

class FiskeWeightsInvalid : public std::invalid_argument {
public:
    FiskeWeightsInvalid()
        : std::invalid_argument("fiske_weights must sum to 1.0 ± 1e-6") {}
};

class GroupTenantImplicit : public std::invalid_argument {
public:
    GroupTenantImplicit()
        : std::invalid_argument(
            "kind=group requires explicit tenant_id "
            "(08_cognizer.md:139); 'default' implicit rejected") {}
};

class CognizerNotFound : public std::invalid_argument {
public:
    std::string id;
    std::string tenant_id;
    CognizerNotFound(std::string i, std::string t)
        : std::invalid_argument("cognizer not found"),
          id(std::move(i)), tenant_id(std::move(t)) {}
};

// ── Enum string converters (inline to avoid multiple-definition) ──

inline std::string_view to_string(CognizerKind k) {
    switch (k) {
        case CognizerKind::Self:     return "self";
        case CognizerKind::Human:    return "human";
        case CognizerKind::Agent:    return "agent";
        case CognizerKind::Group:    return "group";
        case CognizerKind::Role:     return "role";
        case CognizerKind::External: return "external";
    }
    throw std::invalid_argument("unknown CognizerKind");
}

inline CognizerKind cognizer_kind_from_string(std::string_view s) {
    if (s == "self")     return CognizerKind::Self;
    if (s == "human")    return CognizerKind::Human;
    if (s == "agent")    return CognizerKind::Agent;
    if (s == "group")    return CognizerKind::Group;
    if (s == "role")     return CognizerKind::Role;
    if (s == "external") return CognizerKind::External;
    throw std::invalid_argument(std::string("unknown CognizerKind: ") + std::string(s));
}

inline std::string_view to_string(FiskeMode m) {
    switch (m) {
        case FiskeMode::Communal:  return "communal";
        case FiskeMode::Authority: return "authority";
        case FiskeMode::Equality:  return "equality";
        case FiskeMode::Market:    return "market";
    }
    throw std::invalid_argument("unknown FiskeMode");
}

inline FiskeMode fiske_mode_from_string(std::string_view s) {
    if (s == "communal")  return FiskeMode::Communal;
    if (s == "authority") return FiskeMode::Authority;
    if (s == "equality")  return FiskeMode::Equality;
    if (s == "market")    return FiskeMode::Market;
    throw std::invalid_argument(std::string("unknown FiskeMode: ") + std::string(s));
}

}  // namespace starling::cognizer
