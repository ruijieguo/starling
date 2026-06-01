#pragma once
#include "starling/persistence/sqlite_adapter.hpp"
#include <cstdint>
#include <map>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace starling::neocortex {

struct PersonaView {
    bool found = false;
    std::string tenant_id, holder_id;
    int version = 0;
    std::map<std::string, std::string> dimensions;   // dim → arbitrated value (skips null/diverged)
};

struct AnchorStatement {
    std::string stmt_id;
    std::string anchor_type;    // "self_model_anchor" | "profile_anchor"
    std::string dimension;      // e.g. "traits", "preferences"
    std::string value;
    double confidence = 0.0;
};

class ConcurrentRebuildError : public std::runtime_error {
public:
    ConcurrentRebuildError() : std::runtime_error("persona container CAS version mismatch") {}
};

class PersonaContainer {
public:
    explicit PersonaContainer(persistence::SqliteAdapter& adapter);
    // 物化 Persona: 按 dimension 分组; 每 dimension 自陈(self_model_anchor)优先于
    // profile_anchor; 若 self 与 profile 都有且值不同且 max confidence 差 >= DIVERGE_THRESHOLD
    // → dimension 标 suspected_diverge + emit persona.suspected_diverge, 不写该 dimension 值.
    // 写 containers.content_json (kind='persona', holder_id=holder). 单 version CAS →
    // ConcurrentRebuildError on mismatch.
    //
    // CAS semantics: PersonaContainer tracks the last-successfully-written version per
    // (tenant, holder). On the first rebuild for a new row it INSERTs (version=1). On
    // subsequent rebuilds it updates WHERE version == last_known_version; if another
    // writer changed the version in between → ConcurrentRebuildError.
    void rebuild(persistence::Connection& conn, std::string_view tenant_id,
                 std::string_view holder_id, const std::vector<AnchorStatement>& sources,
                 std::string_view now_iso);

    PersonaView read(persistence::Connection& conn, std::string_view tenant_id,
                     std::string_view holder_id);

    // Python binding helper.
    persistence::Connection& connection() { return adapter_.connection(); }

private:
    [[maybe_unused]] persistence::SqliteAdapter& adapter_;
    // version cache: key = "tenant_id\x1fholder_id", value = last written version
    std::map<std::string, int64_t> version_cache_;
    static constexpr double kDivergeThreshold = 0.5;
};

}  // namespace starling::neocortex
