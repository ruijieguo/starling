#pragma once

#include "starling/evidence/engram.hpp"
#include "starling/persistence/connection.hpp"

#include <string>
#include <variant>

namespace starling::evidence {

struct ValidationProceed {
    schema::IngestPolicy resolved_policy;
};
struct ValidationIdempotentHit {
    Engram existing;
};
struct ValidationNoStore {};
struct ValidationReject {
    std::string reason;
};

using ValidationOutcome = std::variant<
    ValidationProceed,
    ValidationIdempotentHit,
    ValidationNoStore,
    ValidationReject>;

class EvidenceValidator {
public:
    // Idempotency lookup runs against the open transaction on `conn` — caller
    // (Bus) holds a write txn so SQLite WAL gives us repeatable-read within
    // the transaction.
    static ValidationOutcome validate(
        const EngramInput& input,
        starling::persistence::Connection& conn);
};

}  // namespace starling::evidence
