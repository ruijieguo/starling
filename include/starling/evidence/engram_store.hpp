#pragma once

#include "starling/evidence/engram.hpp"
#include "starling/persistence/connection.hpp"

#include <optional>
#include <string_view>

namespace starling::evidence {

class EngramStore {
public:
    // Inserts a new Engram row inside the caller's transaction. Generates the
    // id (UUIDv4), computes content_hash via the canonicalizer, sets refcount=0
    // and erased_at=NULL. Returns the persisted Engram so the caller can build
    // an EngramRef.
    //
    // Pre-conditions enforced by the caller (Bus, via EvidenceValidator):
    //   * resolved_policy != NO_STORE (asserted; throws std::invalid_argument)
    //   * source-identity tuple is unique (UNIQUE index will reject a dup
    //     at the storage layer if validator's pre-check raced)
    //   * declared_transformations is unique
    //   * byte_preserving consistent with declared_transformations
    static Engram put(
        const EngramInput& input,
        schema::IngestPolicy resolved_policy,
        starling::persistence::Connection& conn);

    // Tenant-scoped point lookup. Returns nullopt if the row doesn't exist
    // OR if the row exists under a different tenant.
    static std::optional<Engram> get(
        std::string_view id,
        std::string_view tenant_id,
        starling::persistence::Connection& conn);
};

}  // namespace starling::evidence
