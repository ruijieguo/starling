#include "starling/cognizer/name_resolver.hpp"

#include "starling/cognizer/cognizer.hpp"  // CognizerRegistration, Cognizer, AliasCollision, CognizerKind

#include <cctype>
#include <exception>
#include <string>

namespace starling::cognizer {

std::string fold_internal_spaces(std::string_view s) {
    std::string o;
    o.reserve(s.size());
    for (char ch : s) {
        const unsigned char c = static_cast<unsigned char>(ch);
        if (std::isspace(c)) continue;                      // drop all whitespace
        o.push_back(static_cast<char>(std::tolower(c)));    // ASCII lower; non-ASCII passes
    }
    return o;
}

namespace {

// Try existing entity by raw surface then by space-folded surface.
// Returns canonical_name on a hit, or "" on miss.
std::string try_resolve(CognizerHub& hub, std::string_view tenant, std::string_view surface) {
    if (auto id = hub.lookup_by_alias(tenant, surface)) {
        if (auto cog = hub.get(*id, tenant)) return cog->canonical_name;
    }
    const std::string folded = fold_internal_spaces(surface);
    if (folded != std::string(surface)) {
        if (auto id = hub.lookup_by_alias(tenant, folded)) {
            if (auto cog = hub.get(*id, tenant)) return cog->canonical_name;
        }
    }
    return std::string();
}

}  // namespace

std::string resolve_or_register_cognizer(CognizerHub& hub, std::string_view tenant,
                                         std::string_view surface) {
    if (surface.empty()) return std::string(surface);
    try {
        if (auto hit = try_resolve(hub, tenant, surface); !hit.empty()) return hit;
        // Register new; alias set = {surface, space-folded surface} so future
        // variants ("XiaoHong" / "xiao hong") resolve to this canonical name.
        CognizerRegistration reg;
        reg.kind           = CognizerKind::Human;   // enum, not a string (cognizer.hpp)
        reg.tenant_id      = std::string(tenant);
        reg.external_id    = std::string(surface);
        reg.canonical_name = std::string(surface);  // verbatim first-seen surface
        reg.aliases        = {std::string(surface)};
        const std::string folded = fold_internal_spaces(surface);
        if (folded != std::string(surface)) reg.aliases.push_back(folded);
        return hub.register_cognizer(reg).canonical_name;  // == surface
    } catch (const AliasCollision& e) {
        // A folded alias collided with a different existing entity → resolve to it.
        try {
            if (auto cog = hub.get(e.existing_id, tenant)) return cog->canonical_name;
        } catch (const std::exception&) {
        }
        return std::string(surface);
    } catch (const std::exception&) {
        return std::string(surface);  // best-effort: never break the caller
    }
}

std::string resolve_cognizer(CognizerHub& hub, std::string_view tenant,
                             std::string_view surface) {
    if (surface.empty()) return std::string(surface);
    try {
        if (auto hit = try_resolve(hub, tenant, surface); !hit.empty()) return hit;
    } catch (const std::exception&) {
        // best-effort: fall through to passthrough
    }
    return std::string(surface);  // unknown → passthrough, no register
}

}  // namespace starling::cognizer
